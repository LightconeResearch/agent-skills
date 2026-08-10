#!/usr/bin/env node
// Hermetic tests for the astra hook shims (no jq/sed/awk contracts, no
// network, no real astra).
//
// The shims are deliberately thin: string-match the raw payload, then
// delegate to the pinned `uvx astra-tools@<pin>` invocation, whose --json
// mode returns ONE JSON-encoded string that the shim splices into the
// response envelope. So the tests stub uvx (controllable exit code +
// invocation log) and assert the shim's halves: the prefilter (non-ASTRA
// events exit silently WITHOUT invoking uvx), the delegation (correct astra
// arguments), and the envelope (every emitted line must JSON.parse, with the
// spliced report intact).
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
// The fake emits what the real --json mode emits: one JSON-encoded string
// (here with embedded quotes and a backslash, to prove the splice needs no
// re-escaping). FAKE_UVX_GARBAGE simulates a toolchain that never got to
// astra (uvx resolution failure, crash) — non-JSON noise on stdout.
writeFileSync(
  join(bin, "uvx"),
  `#!/bin/sh
echo "$*" >> "${uvxLog}"
if [ -n "\${FAKE_UVX_GARBAGE}" ]; then
  echo "error: no interpreter found"
  exit 2
fi
printf '%s\\n' "\\"fake report: $* | with \\\\\\"quotes\\\\\\" and a \\\\\\\\backslash\\""
exit "\${FAKE_UVX_RC:-1}"
`,
  { mode: 0o755 },
);
writeFileSync(join(bin, "astra"), "#!/bin/sh\nexit 0\n", { mode: 0o755 });

function run(script, input, env = {}, cwd = project) {
  const result = spawnSync("bash", [join(SCRIPTS, script)], {
    cwd,
    encoding: "utf8",
    env: { ...process.env, PATH: `${bin}:${process.env.PATH}`, ...env },
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

function assertSilent(label, stdout, before) {
  if (stdout !== "") throw new Error(`${label}: expected no output\n${stdout}`);
  if (uvxCalls().length !== before) throw new Error(`${label}: uvx was invoked`);
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

  // Failing validation → FAILED message with the spliced report.
  let context = parsedContext(
    "save/fail",
    run("validate-on-save.sh", writePayload),
    "PostToolUse",
  );
  assertIncludes("save/fail", context, "ASTRA validation FAILED for ./astra.yaml");
  assertIncludes("save/fail", context, "fake report:");
  assertIncludes("save/fail", context, 'with "quotes" and a \\backslash');
  const [firstCall] = uvxCalls();
  assertIncludes("save/fail uvx args", firstCall, "astra-tools@");
  assertIncludes("save/fail uvx args", firstCall, "validate astra.yaml --json");

  // Passing validation → single-line passed message.
  context = parsedContext(
    "save/pass",
    run("validate-on-save.sh", writePayload, { FAKE_UVX_RC: "0" }),
    "PostToolUse",
  );
  assertIncludes("save/pass", context, "ASTRA validation passed");

  // Toolchain failure (no JSON string on stdout) → toolchain message, valid JSON.
  context = parsedContext(
    "save/toolchain",
    run("validate-on-save.sh", writePayload, { FAKE_UVX_GARBAGE: "1" }),
    "PostToolUse",
  );
  assertIncludes("save/toolchain", context, "toolchain problem");

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
  let before = uvxCalls().length;
  assertSilent(
    "save/silent",
    run(
      "validate-on-save.sh",
      JSON.stringify({
        cwd: project,
        tool_name: "Write",
        tool_input: { file_path: join(project, "README.md") },
        tool_response: {},
      }),
    ),
    before,
  );

  // Payload mentions astra.yaml, but the session dir has no spec → silent
  // (the mention was incidental, e.g. docs content), and no uvx run.
  const noProject = join(scratch, "no-project");
  mkdirSync(noProject);
  before = uvxCalls().length;
  assertSilent(
    "save/no-project",
    run(
      "validate-on-save.sh",
      JSON.stringify({
        cwd: noProject,
        tool_name: "Write",
        tool_input: { file_path: join(noProject, "README.md"), content: "see astra.yaml docs" },
        tool_response: {},
      }),
      {},
      noProject,
    ),
    before,
  );

  // --- session-start ------------------------------------------------------
  // Healthy toolchain → primer with the spliced info header.
  context = parsedContext(
    "session/primer",
    run("astra-session-start.sh", "{}", { FAKE_UVX_RC: "0" }),
    "SessionStart",
  );
  assertIncludes("session/primer", context, "ASTRA project — spec at ./astra.yaml");
  assertIncludes("session/primer", context, "fake report:");
  assertIncludes("session/primer", context, "Activate the astra skill");
  assertIncludes("session/primer uvx args", uvxCalls().at(-1), "info --json");

  // Toolchain failure → degraded message, still valid JSON.
  context = parsedContext(
    "session/toolchain",
    run("astra-session-start.sh", "{}", { FAKE_UVX_GARBAGE: "1" }),
    "SessionStart",
  );
  assertIncludes("session/toolchain", context, "Could not run `astra info`");

  // Outside an ASTRA project → silent.
  before = uvxCalls().length;
  assertSilent("session/elsewhere", run("astra-session-start.sh", "{}", {}, scratch), before);

  console.log("✓ ASTRA hook shims: prefilter, uvx delegation, and JSON splicing all behave.");
} finally {
  rmSync(scratch, { recursive: true, force: true });
}
