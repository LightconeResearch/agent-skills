#!/usr/bin/env node
// Live end-to-end hook-DISPATCH tests. The other suites each prove one layer:
// test-hooks.mjs proves the hook *scripts* behave (payload in → envelope out),
// smoke.mjs proves the *install* mechanics (marketplace add → plugin cached).
// Neither proves the layer in between: that a real harness session actually
// fires the events, matches `Write|Edit|apply_patch`, resolves
// `${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}`, and executes the packaged scripts.
// That wiring has broken upstream before without any install-time symptom
// (openai/codex#16430: plugin-bundled hooks silently never ran), so this
// suite runs REAL headless sessions against a marketplace-installed plugin.
//
//   node scripts/e2e-hooks.mjs             # both harnesses
//   node scripts/e2e-hooks.mjs --claude    # one harness only
//   node scripts/e2e-hooks.mjs --codex
//
// Auth comes from the environment (ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN
// for Claude Code; CODEX_API_KEY or OPENAI_API_KEY for Codex). A leg whose
// auth or binary is missing is skipped LOCALLY (a dev without one CLI or key
// can still run the rest), but in CI every skip is a hard FAILURE: the
// workflow installs both CLIs and is expected to have both secrets, so a
// skip there means a missing/forgotten secret or a broken install — exactly
// what must not silently green the check. (Consequence: PRs from forks fail
// these legs, since GitHub does not expose secrets to forks.)
//
// The sentinel: hooks delegate to `uvx`, so each leg prepends a stub `uvx` to
// PATH that appends its argv to a log file and prints the canned JSON-encoded
// string the real `astra-tools --json` mode would. A new log line therefore
// proves the whole dispatch chain ran — event fired → matcher matched → plugin
// root resolved → packaged script executed — deterministically, with no
// dependence on model wording and no network or real astra-tools install.
// Model output is never asserted; the model is only a means to trigger events.

import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(import.meta.url), "..", "..");
const MARKET = "lightcone-research";
const PLUGIN = "astra";
const SESSION_PROMPT = "Reply with exactly: OK";
// Mechanical on purpose: the model's only job is to cause one file-edit tool
// call on astra.yaml so PostToolUse fires. Anything fancier adds flake.
const EDIT_PROMPT =
  "A file named astra.yaml exists in the current directory. Append the comment " +
  "line `# e2e-touch` to the end of astra.yaml using your file editing tool. " +
  "Do nothing else, and do not explain.";
const EDIT_ATTEMPTS = 2; // one retry for the rare run where the model never edits

const args = process.argv.slice(2);
const wantClaude = args.includes("--claude") || !args.includes("--codex");
const wantCodex = args.includes("--codex") || !args.includes("--claude");

let failures = 0;
const pass = (m) => console.log(`  \x1b[32m✓\x1b[0m ${m}`);
const fail = (m) => { console.log(`  \x1b[31m✗ ${m}\x1b[0m`); failures++; };
const skip = (m) => {
  if (process.env.GITHUB_ACTIONS) {
    console.log(`::error::e2e-hooks: ${m} — skips are failures in CI (check repo secrets / CLI install)`);
    return fail(`${m} — skips are failures in CI`);
  }
  console.log(`  \x1b[33m∅ skip\x1b[0m ${m}`);
};
const have = (bin) => spawnSync("sh", ["-c", `command -v ${bin}`]).status === 0;
const tail = (s, n = 400) => (s || "").trim().slice(-n);

function run(bin, argv, { cwd, env = {}, timeout = 120_000, input } = {}) {
  const r = spawnSync(bin, argv, {
    cwd,
    encoding: "utf8",
    env: { ...process.env, ...env },
    input,
    timeout,
  });
  return { out: (r.stdout || "") + (r.stderr || ""), status: r.status };
}

// One scratch area per leg: an isolated config home, a fake ASTRA project the
// session runs in, and the stub-uvx bin dir. The log path is embedded in the
// stub (not passed via env) so the assertion cannot be defeated by a harness
// that launders hook environments.
function makeScratch(prefix) {
  const scratch = mkdtempSync(join(tmpdir(), prefix));
  const project = join(scratch, "project");
  const bin = join(scratch, "bin");
  const uvxLog = join(scratch, "uvx-invocations.log");
  mkdirSync(project);
  mkdirSync(bin);
  writeFileSync(join(project, "astra.yaml"), "id: e2e-test\n");
  // rc 0 + a JSON-encoded string on stdout: both hook scripts take their happy
  // path and emit benign context, so the session itself is undisturbed.
  writeFileSync(
    join(bin, "uvx"),
    `#!/bin/sh\necho "$*" >> "${uvxLog}"\nprintf '%s\\n' '"e2e stub: ok"'\nexit 0\n`,
    { mode: 0o755 },
  );
  const uvxCalls = () =>
    existsSync(uvxLog) ? readFileSync(uvxLog, "utf8").trim().split("\n") : [];
  return { scratch, project, bin, uvxCalls };
}

// Drive one harness through both events. `session(prompt)` and `edit(prompt)`
// run a fresh headless session in the project dir and return {out, status}.
function testHarness(name, { project, uvxCalls }, session, edit) {
  // SessionStart: every headless run is a new session, so a minimal one-turn
  // prompt must produce an `info --json` delegation from astra-session-start.sh.
  let before = uvxCalls().length;
  const s = session(SESSION_PROMPT);
  if (s.status !== 0) {
    fail(`${name}: session run exited ${s.status}:\n${tail(s.out)}`);
  } else if (uvxCalls().slice(before).some((l) => l.includes("info --json"))) {
    pass(`${name}: SessionStart hook fired (uvx got \`info --json\`)`);
  } else {
    fail(`${name}: SessionStart hook did not fire — no \`info --json\` uvx call.\n${tail(s.out)}`);
  }

  // PostToolUse: the model must edit astra.yaml; the matcher must then route
  // the event into validate-on-save.sh. A changed file WITHOUT a validate call
  // is the smoking gun (dispatch broken); an unchanged file means the model
  // never edited, which is inconclusive → retry once, then fail loudly as such.
  const spec = join(project, "astra.yaml");
  for (let attempt = 1; attempt <= EDIT_ATTEMPTS; attempt++) {
    before = uvxCalls().length;
    const preContent = readFileSync(spec, "utf8");
    const e = edit(EDIT_PROMPT);
    const validated = uvxCalls().slice(before).some((l) => l.includes("validate astra.yaml --json"));
    const edited = readFileSync(spec, "utf8") !== preContent;
    if (validated) {
      return pass(`${name}: PostToolUse hook fired (uvx got \`validate astra.yaml --json\`)`);
    }
    if (edited) {
      return fail(`${name}: astra.yaml WAS edited but the PostToolUse hook never ran — dispatch is broken.\n${tail(e.out)}`);
    }
    if (attempt === EDIT_ATTEMPTS) {
      fail(`${name}: model never edited astra.yaml in ${EDIT_ATTEMPTS} attempts (exit ${e.status}) — PostToolUse untested.\n${tail(e.out)}`);
    }
  }
}

// ---- Claude Code ---------------------------------------------------------
function claudeLeg() {
  console.log("\nClaude Code — live hook dispatch (isolated config)");
  if (!have("claude")) return skip("`claude` not on PATH");
  if (!process.env.ANTHROPIC_API_KEY && !process.env.CLAUDE_CODE_OAUTH_TOKEN)
    return skip("no ANTHROPIC_API_KEY / CLAUDE_CODE_OAUTH_TOKEN — Claude leg needs auth");

  const sc = makeScratch("e2e-cc-");
  const env = {
    CLAUDE_CONFIG_DIR: join(sc.scratch, "config"),
    PATH: `${sc.bin}:${process.env.PATH}`,
  };
  try {
    const add = run("claude", ["plugin", "marketplace", "add", ROOT], { env });
    if (!/added marketplace/i.test(add.out)) return fail(`marketplace add failed: ${tail(add.out)}`);
    const ins = run("claude", ["plugin", "install", `${PLUGIN}@${MARKET}`, "--scope", "user"], { env });
    if (!/Successfully installed plugin/i.test(ins.out)) return fail(`plugin install failed: ${tail(ins.out)}`);

    const claude = (prompt, extra) =>
      run("claude", ["-p", prompt, "--model", "haiku", ...extra], {
        cwd: sc.project,
        env,
        timeout: 300_000,
      });
    testHarness(
      "claude",
      sc,
      (p) => claude(p, ["--max-turns", "2"]),
      // acceptEdits: headless runs can't answer a permission prompt, and the
      // whole point is to let the Edit/Write through so PostToolUse fires.
      (p) => claude(p, ["--max-turns", "6", "--permission-mode", "acceptEdits"]),
    );
  } finally {
    rmSync(sc.scratch, { recursive: true, force: true });
  }
}

// ---- Codex ---------------------------------------------------------------
function codexLeg() {
  console.log("\nCodex — live hook dispatch (isolated CODEX_HOME)");
  if (!have("codex")) return skip("`codex` not on PATH");
  const key = process.env.CODEX_API_KEY || process.env.OPENAI_API_KEY;
  if (!key) return skip("no CODEX_API_KEY / OPENAI_API_KEY — Codex leg needs auth");

  const sc = makeScratch("e2e-cx-");
  const env = {
    CODEX_HOME: join(sc.scratch, "codex"),
    CODEX_API_KEY: key,
    OPENAI_API_KEY: key,
    PATH: `${sc.bin}:${process.env.PATH}`,
  };
  mkdirSync(env.CODEX_HOME, { recursive: true });
  // Belt and braces: some Codex versions read the key from the environment,
  // others want it persisted in auth.json. Harmless where redundant.
  run("codex", ["login", "--with-api-key"], { env, input: key });
  try {
    const add = run("codex", ["plugin", "marketplace", "add", ROOT], { env });
    if (!/Added marketplace/i.test(add.out)) return fail(`marketplace add failed: ${tail(add.out)}`);
    const ins = run("codex", ["plugin", "add", `${PLUGIN}@${MARKET}`], { env });
    if (!/Added plugin/i.test(ins.out)) return fail(`plugin add failed: ${tail(ins.out)}`);

    // --dangerously-bypass-hook-trust: plugin-bundled hooks require an
    // interactive trust review before they run; this flag is the documented
    // escape hatch for automation, and everything here is a throwaway home
    // running this repo's own hooks.
    const codex = (prompt, extra) =>
      run(
        "codex",
        ["exec", "--skip-git-repo-check", "--dangerously-bypass-hook-trust", ...extra, prompt],
        { cwd: sc.project, env, timeout: 300_000 },
      );
    testHarness(
      "codex",
      sc,
      (p) => codex(p, []),
      // workspace-write so apply_patch on astra.yaml is allowed in the sandbox.
      (p) => codex(p, ["--sandbox", "workspace-write"]),
    );
  } finally {
    rmSync(sc.scratch, { recursive: true, force: true });
  }
}

// ---- run -----------------------------------------------------------------
console.log(`E2E hook-dispatch tests — repo ${ROOT}`);
if (wantClaude) claudeLeg();
if (wantCodex) codexLeg();

console.log(failures ? `\n\x1b[31m✗ ${failures} e2e failure(s)\x1b[0m` : "\n\x1b[32m✓ all e2e checks passed\x1b[0m");
process.exit(failures ? 1 : 0);
