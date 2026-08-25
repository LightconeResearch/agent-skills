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

  // --- lightcone engine preflight -----------------------------------------
  // The PACKAGED copy is under test, not the canonical one: the version floor
  // arrives by pin substitution, so only the packaged script carries a real
  // number to compare against. `npm test` fails on drift between the two, so
  // testing the generated copy still tests the source.
  //
  // Versions are chosen relative to the floor without arithmetic: 0.0.1 is
  // below any floor, 999.0.0 above any, and "<floor>.dev1" is the floor's own
  // pre-release — the case `sort -V` gets backwards.
  // The canonical script carries the `lightcone-cli==x.y.z` placeholder, so
  // substituting a floor here is exactly what the build does — which lets the
  // cases below pin a floor of their own (an rc floor orders differently from
  // a release one) instead of being hostage to whatever the repo pins today.
  const lcSource = readFileSync(
    join(ROOT, "hooks/lightcone/scripts/lightcone-session-start.sh"),
    "utf8",
  );
  const floor = JSON.parse(readFileSync(join(ROOT, "skills.config.json"), "utf8")).plugins.find(
    (p) => p.name === "lightcone",
  ).tools["lightcone-cli"];
  const scriptWithFloor = (v) => {
    const path = join(scratch, `lc-hook-${v.replaceAll(/[^\w.]/g, "_")}.sh`);
    writeFileSync(path, lcSource.replaceAll("lightcone-cli==x.y.z", `lightcone-cli==${v}`));
    return path;
  };
  const lcBin = join(scratch, "lc-bin");
  mkdirSync(lcBin);
  const lcPath = join(lcBin, "lc");

  // No ...process.env: a real CI= or CLAUDE_CODE_ENTRYPOINT= in the ambient
  // environment would otherwise decide the mode these cases are asserting.
  function runLc({ version, env = {}, cwd = project, lcScript = scriptWithFloor(floor) } = {}) {
    if (version === undefined) rmSync(lcPath, { force: true });
    else if (version === "broken") writeFileSync(lcPath, "#!/bin/sh\nexit 127\n", { mode: 0o755 });
    // Single-quoted in sh so a version carrying " or \ reaches the hook
    // intact instead of being eaten by the fake's own quoting.
    else writeFileSync(lcPath, `#!/bin/sh\nprintf '%s\\n' 'lc, version ${version}'\n`, { mode: 0o755 });
    const r = spawnSync("bash", [lcScript], {
      cwd,
      encoding: "utf8",
      input: "{}",
      env: { PATH: `${lcBin}:/usr/bin:/bin`, ...env },
    });
    if (r.status !== 0) throw new Error(`lightcone hook: exited ${r.status}\n${r.stdout}${r.stderr}`);
    return r.stdout;
  }
  const lcContext = (label, opts) => parsedContext(label, runLc(opts), "SessionStart");
  const TUI = { CLAUDE_CODE_ENTRYPOINT: "cli" };
  const HEADLESS = { CLAUDE_CODE_ENTRYPOINT: "sdk-cli" };

  // Outside a Lightcone project the engine is still checked — the skill's
  // first job is often to create a project from nothing.
  const elsewhereAbsent = parsedContext(
    "lc/elsewhere-absent",
    runLc({ cwd: scratch, env: TUI }),
    "SessionStart",
  );
  assertIncludes("lc/elsewhere-absent", elsewhereAbsent, "no astra.yaml");
  assertIncludes("lc/elsewhere-absent", elsewhereAbsent, "is not installed");
  assertIncludes("lc/elsewhere-absent", elsewhereAbsent, "lc init");

  // The all-clear is phrased identically in and out of a project, because
  // the skill matches on that sentence to skip its own `lc --version`.
  // Silence would be indistinguishable from a hook that never ran.
  for (const [label, cwdArg] of [
    ["lc/ok-signal-in-project", project],
    ["lc/ok-signal-elsewhere", scratch],
  ])
    assertIncludes(
      label,
      parsedContext(label, runLc({ version: floor, cwd: cwdArg, env: TUI }), "SessionStart"),
      `Lightcone CLI ready: lc ${floor}`,
    );

  // …and no *other* state may carry that sentence, or the skill would skip
  // a check it needed to run.
  for (const [label, opts] of [
    ["lc/no-false-ok-absent", {}],
    ["lc/no-false-ok-broken", { version: "broken" }],
    ["lc/no-false-ok-old", { version: "0.0.1" }],
  ]) {
    const ctx = parsedContext(label, runLc({ ...opts, env: TUI }), "SessionStart");
    if (ctx.includes("Lightcone CLI ready"))
      throw new Error(`${label}: emitted the all-clear for an unusable engine\n${ctx}`);
  }

  // Engine state.
  assertIncludes("lc/absent", lcContext("lc/absent", { env: TUI }), "is not installed");
  assertIncludes("lc/broken", lcContext("lc/broken", { version: "broken", env: TUI }), "not the Lightcone CLI");
  assertIncludes("lc/old", lcContext("lc/old", { version: "0.0.1", env: TUI }), `older than the ${floor}`);
  assertIncludes("lc/ready", lcContext("lc/ready", { version: floor, env: TUI }), "Lightcone CLI ready");
  assertIncludes("lc/newer", lcContext("lc/newer", { version: "999.0.0", env: TUI }), "Lightcone CLI ready");
  // PEP 440 ordering, which `sort -V` gets backwards: every pre-release of the
  // floor precedes it, and a release candidate floor is satisfied by the
  // release it led to. Each case names the floor it is judged against.
  const ordering = [
    // [floor, installed, satisfies the floor?]
    ["0.5.0", "0.5.0.dev1+gabc123", false],
    ["0.5.0", "0.5.0rc1", false],
    ["0.5.0", "0.5.0a1", false],
    ["0.5.0", "0.5.0b9", false],
    ["0.5.0", "0.5.0", true],
    ["0.5.0", "0.5.1rc1", true], // a later release line, still ahead of 0.5.0
    ["0.5.0rc1", "0.5.0rc1", true],
    ["0.5.0rc1", "0.5.0", true], // the release the candidate led to
    ["0.5.0rc1", "0.5.0rc2", true],
    ["0.5.0rc2", "0.5.0rc1", false],
    ["0.5.0rc1", "0.5.0rc1.dev2+gabc", false], // a dev build of the candidate
    ["0.5.0rc1", "0.4.9", false],
    // A bare .dev build carries no pre-release segment, and still precedes
    // every pre-release of its own version.
    ["0.5.0a1", "0.5.0.dev1", false],
    ["0.5.0.dev1", "0.5.0a1", true],
  ];
  for (const [floorV, installed, ok] of ordering) {
    const label = `lc/order ${installed} vs floor ${floorV}`;
    const ctx = parsedContext(
      label,
      runLc({ version: installed, env: TUI, lcScript: scriptWithFloor(floorV) }),
      "SessionStart",
    );
    assertIncludes(label, ctx, ok ? "Lightcone CLI ready" : `older than the ${floorV}`);
  }

  // Mode: ask where a person is, act where none can be, and default to
  // asking when the launcher is unrecognized.
  assertIncludes("lc/tui", lcContext("lc/tui", { env: TUI }), "Ask the user");
  assertIncludes("lc/headless", lcContext("lc/headless", { env: HEADLESS }), "No one can be asked");
  assertIncludes("lc/ci", lcContext("lc/ci", { env: { ...TUI, CI: "true" } }), "No one can be asked");
  assertIncludes("lc/unknown-harness", lcContext("lc/unknown-harness", { env: {} }), "Ask the user");

  // A foreign `lc` whose version carries JSON metacharacters must not break
  // the envelope — parsedContext throws if the line no longer parses.
  lcContext("lc/hostile-version", { version: '1.0"x\\y', env: TUI });

  console.log("✓ lightcone preflight: engine states, version floor, and ask/act mode all behave.");
} finally {
  rmSync(scratch, { recursive: true, force: true });
}
