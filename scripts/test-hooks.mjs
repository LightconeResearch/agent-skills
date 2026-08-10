#!/usr/bin/env node
// Hermetic tests for the astra hook shims (no jq, no network, no real astra).
//
// The shims are deliberately thin: string-match the raw payload, then delegate
// real work to the pinned `uvx astra-tools@<pin>` invocation. So the tests
// stub uvx (controllable exit code + invocation log) and assert the shim's
// halves: the prefilter (non-ASTRA events exit silently WITHOUT invoking uvx),
// the delegation (correct astra subcommand), and the JSON emission (every
// emitted line must JSON.parse — this exercises the bash escaper).
//
// A fake `astra` that always SUCCEEDS also sits on PATH: if any script ever
// regresses to running a PATH astra instead of uvx, the expected FAILED
// message flips to passed and the assertions break.

import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(import.meta.url), "..", "..");
const SCRIPTS = join(ROOT, "hooks/astra/scripts");
const scratch = mkdtempSync(join(tmpdir(), "astra-hook-"));
const project = join(scratch, "project");
const bin = join(scratch, "bin");
const uvxLog = join(scratch, "uvx-invocations.log");

mkdirSync(project, { recursive: true });
mkdirSync(bin);
writeFileSync(join(project, "astra.yaml"), "id: test\n");
writeFileSync(
  join(bin, "uvx"),
  `#!/bin/sh
echo "$*" >> "${uvxLog}"
printf 'fake output: %s\\n' "$*"
printf 'tricky "quotes" and \\\\backslashes\\n'
printf 'ansi \\033[31mred\\033[0m end\\n'
exit "\${FAKE_UVX_RC:-1}"
`,
  { mode: 0o755 },
);
writeFileSync(join(bin, "astra"), "#!/bin/sh\nexit 0\n", { mode: 0o755 });

function run(script, input, env = {}) {
  const result = spawnSync("bash", [join(SCRIPTS, script)], {
    cwd: project,
    encoding: "utf8",
    env: { ...process.env, PATH: `${bin}:${process.env.PATH}`, TMPDIR: scratch, ...env },
    input,
  });
  if (result.status !== 0) {
    throw new Error(`${script}: exited ${result.status}\n${result.stdout}${result.stderr}`);
  }
  return result.stdout;
}

function parsedContext(label, stdout, expectedEvent) {
  let parsed;
  try {
    parsed = JSON.parse(stdout);
  } catch {
    throw new Error(`${label}: output is not valid JSON\n${stdout}`);
  }
  const out = parsed.hookSpecificOutput;
  if (out.hookEventName !== expectedEvent) {
    throw new Error(`${label}: expected ${expectedEvent}, got ${out.hookEventName}`);
  }
  return out.additionalContext;
}

function assertIncludes(label, haystack, needle) {
  if (!haystack.includes(needle)) {
    throw new Error(`${label}: missing ${JSON.stringify(needle)}\n${haystack}`);
  }
}

const uvxCalls = () => (existsSync(uvxLog) ? readFileSync(uvxLog, "utf8").trim().split("\n") : []);

try {
  // --- validate-on-save ---------------------------------------------------
  const writePayload = JSON.stringify({
    cwd: project,
    tool_name: "Write",
    tool_input: { file_path: join(project, "astra.yaml") },
    tool_response: {},
  });

  // Failing validation → FAILED message with the validator's output, escaped.
  let context = parsedContext(
    "save/fail",
    run("validate-on-save.sh", writePayload),
    "PostToolUse",
  );
  assertIncludes("save/fail", context, "ASTRA validation FAILED");
  assertIncludes("save/fail", context, "fake output:");
  assertIncludes("save/fail", context, 'tricky "quotes" and \\backslashes');
  // Control characters (ANSI escapes from a forced-color Rich) must be
  // stripped, not passed through as illegal JSON string bytes.
  assertIncludes("save/fail ansi", context, "red");
  if (context.includes("\u001b")) throw new Error("save/fail ansi: raw ESC byte in context");
  const [firstCall] = uvxCalls();
  assertIncludes("save/fail uvx args", firstCall, "astra-tools@");
  assertIncludes("save/fail uvx args", firstCall, " validate");

  // Passing validation → single-line passed message.
  context = parsedContext(
    "save/pass",
    run("validate-on-save.sh", writePayload, { FAKE_UVX_RC: "0" }),
    "PostToolUse",
  );
  assertIncludes("save/pass", context, "ASTRA validation passed");

  // Codex apply_patch payloads trigger through the same string prefilter.
  const patchPayload = JSON.stringify({
    cwd: project,
    tool_name: "apply_patch",
    tool_input: { command: "*** Begin Patch\n*** Update File: astra.yaml\n*** End Patch" },
    tool_response: {},
  });
  context = parsedContext("save/patch", run("validate-on-save.sh", patchPayload), "PostToolUse");
  assertIncludes("save/patch", context, "ASTRA validation FAILED");

  // Non-ASTRA event → silent, and uvx is never invoked.
  const before = uvxCalls().length;
  const silent = run(
    "validate-on-save.sh",
    JSON.stringify({
      cwd: project,
      tool_name: "Write",
      tool_input: { file_path: join(project, "README.md") },
      tool_response: {},
    }),
  );
  if (silent !== "") throw new Error(`save/silent: expected no output\n${silent}`);
  if (uvxCalls().length !== before) throw new Error("save/silent: uvx was invoked");

  // Payload mentions astra.yaml, but the session dir has no ASTRA project →
  // silent (the mention was incidental, e.g. docs content), and no uvx run.
  const noProject = join(scratch, "no-project");
  mkdirSync(noProject);
  const incidental = spawnSync("bash", [join(SCRIPTS, "validate-on-save.sh")], {
    cwd: noProject,
    encoding: "utf8",
    env: { ...process.env, PATH: `${bin}:${process.env.PATH}` },
    input: JSON.stringify({
      cwd: noProject,
      tool_name: "Write",
      tool_input: { file_path: join(noProject, "README.md"), content: "see astra.yaml docs" },
      tool_response: {},
    }),
  });
  if (incidental.status !== 0 || incidental.stdout !== "") {
    throw new Error(`save/no-project: expected silent success\n${incidental.stdout}`);
  }
  if (uvxCalls().length !== before) throw new Error("save/no-project: uvx was invoked");

  // --- activate-on-read ---------------------------------------------------
  const readPayload = (file, session) =>
    JSON.stringify({
      cwd: project,
      session_id: session,
      tool_name: "Read",
      tool_input: { file_path: file },
      tool_response: {},
    });

  context = parsedContext(
    "read/nudge",
    run("activate-on-read.sh", readPayload(join(project, "astra.yaml"), "s1")),
    "PostToolUse",
  );
  assertIncludes("read/nudge", context, "load the astra skill");

  // Second read in the same session → marker suppresses the nudge.
  const again = run("activate-on-read.sh", readPayload(join(project, "astra.yaml"), "s1"));
  if (again !== "") throw new Error(`read/again: expected no output\n${again}`);

  // Non-ASTRA read → silent.
  const other = run("activate-on-read.sh", readPayload(join(project, "notes.md"), "s2"));
  if (other !== "") throw new Error(`read/other: expected no output\n${other}`);

  // --- session-start ------------------------------------------------------
  // Fake uvx exits 1, so `astra info` fails → toolchain-problem message.
  context = parsedContext(
    "session/toolchain",
    run("astra-session-start.sh", JSON.stringify({ cwd: project })),
    "SessionStart",
  );
  assertIncludes("session/toolchain", context, "ASTRA project — spec at ./astra.yaml");
  assertIncludes("session/toolchain", context, "toolchain problem");
  assertIncludes("session/toolchain", context, "Activate the astra skill");

  // Outside an ASTRA project → silent.
  const elsewhere = spawnSync("bash", [join(SCRIPTS, "astra-session-start.sh")], {
    cwd: scratch,
    encoding: "utf8",
    env: { ...process.env, PATH: `${bin}:${process.env.PATH}` },
    input: "{}",
  });
  if (elsewhere.status !== 0 || elsewhere.stdout !== "") {
    throw new Error(`session/elsewhere: expected silent success\n${elsewhere.stdout}`);
  }

  console.log("✓ ASTRA hook shims: prefilter, uvx delegation, and JSON emission all behave.");
} finally {
  rmSync(scratch, { recursive: true, force: true });
}
