#!/usr/bin/env node
// Live end-to-end hook-DISPATCH tests, driven by declarative specs in
// tests/<plugin>.yaml. The other suites each prove one layer: test-hooks.mjs
// proves the hook *scripts* behave (payload in → envelope out), smoke.mjs
// proves the *install* mechanics (marketplace add → plugin cached). Neither
// proves the layer in between: that a real harness session actually fires the
// events, matches the hook matchers, resolves
// `${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}`, and executes the packaged scripts.
// That wiring has broken upstream before without any install-time symptom
// (openai/codex#16430: plugin-bundled hooks silently never ran), so this
// suite runs REAL headless sessions against marketplace-installed plugins.
//
//   node scripts/e2e-hooks.mjs             # every spec, both harnesses
//   node scripts/e2e-hooks.mjs --claude    # one harness only
//   node scripts/e2e-hooks.mjs --codex
//
// To cover a new plugin, add tests/<plugin>.yaml — see tests/astra.yaml for
// the spec format. No runner changes should be needed: everything
// plugin-specific (project fixture files, sentinel stubs, prompts,
// expectations) lives in the spec.
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
// The sentinel mechanism: each spec declares stub binaries its hooks are
// known to invoke (astra's delegate to `uvx`). The runner prepends stubs to
// PATH that append their argv to a log file and print the spec's canned
// stdout. A new log line therefore proves the whole dispatch chain ran —
// deterministically, with no dependence on model wording and no network or
// real toolchain install. The model is only a means to trigger events.

import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(import.meta.url), "..", "..");
const MARKET = "lightcone-research";

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

// ---- yaml-lite -----------------------------------------------------------
// Hand-written parser for the strict YAML subset the test specs use, keeping
// the repo's zero-dependency rule (same tradeoff as lib.mjs's frontmatter
// parser — see AGENTS.md). Supported: nested maps, lists of maps or scalars,
// plain/quoted scalars (ints and booleans coerced), inline comments on plain
// scalars, and `|`/`>` block scalars with optional `-` chomping. Not
// supported: anchors, flow syntax, multi-line quoted strings.
function parseYamlLite(src) {
  const raw = src.split("\n");
  let pos = 0;
  const indentOf = (s) => s.length - s.trimStart().length;
  const isSkip = (s) => !s.trim() || /^\s*#/.test(s);
  const peek = () => {
    while (pos < raw.length && isSkip(raw[pos])) pos++;
    return pos < raw.length ? raw[pos] : null;
  };
  const scalar = (s) => {
    if (s.startsWith('"')) return JSON.parse(s);
    if (s.startsWith("'")) return s.slice(1, -1).replaceAll("''", "'");
    const cut = s.search(/\s#/);
    if (cut !== -1) s = s.slice(0, cut);
    s = s.trim();
    if (/^-?\d+$/.test(s)) return Number(s);
    if (s === "true" || s === "false") return s === "true";
    return s;
  };
  // Block scalars read `raw` directly (not peek) so blank and `#` lines
  // inside the block survive.
  const blockScalar = (marker, indent) => {
    const body = [];
    while (pos < raw.length && (!raw[pos].trim() || indentOf(raw[pos]) > indent)) body.push(raw[pos++]);
    while (body.length && !body.at(-1).trim()) body.pop();
    if (!body.length) return "";
    const base = Math.min(...body.filter((l) => l.trim()).map(indentOf));
    const lines = body.map((l) => l.slice(base));
    const s = marker[0] === "|" ? lines.join("\n") : lines.join(" ").replace(/\s+/g, " ").trim();
    return marker.endsWith("-") ? s : s + "\n";
  };
  function parseMap(indent) {
    const obj = {};
    for (;;) {
      const line = peek();
      if (line === null || indentOf(line) !== indent || line.trim().startsWith("- ")) break;
      const m = line.trim().match(/^([^:]+):\s*(.*)$/);
      if (!m) throw new Error(`yaml-lite: cannot parse line: ${line.trim()}`);
      pos++;
      const [, key, rest] = m;
      if (rest === "") obj[key.trim()] = parseChild(indent);
      else if (/^[|>]-?$/.test(rest)) obj[key.trim()] = blockScalar(rest, indent);
      else obj[key.trim()] = scalar(rest);
    }
    return obj;
  }
  function parseList(indent) {
    const arr = [];
    for (;;) {
      const line = peek();
      if (line === null || indentOf(line) !== indent || !line.trim().startsWith("- ")) break;
      const content = line.trim().slice(2);
      if (/^[^:]+:(\s|$)/.test(content)) {
        // Map item: rewrite the dash line as its own content two columns in,
        // and let parseMap pick it up along with the item's following lines.
        raw[pos] = " ".repeat(indent + 2) + content;
        arr.push(parseMap(indent + 2));
      } else {
        pos++;
        arr.push(scalar(content));
      }
    }
    return arr;
  }
  function parseChild(indent) {
    const line = peek();
    if (line === null || indentOf(line) <= indent) return null;
    return line.trim().startsWith("- ") ? parseList(indentOf(line)) : parseMap(indentOf(line));
  }
  const first = peek();
  return first === null ? {} : parseMap(indentOf(first));
}

// Quote a string for safe single-quoted embedding in a POSIX shell script.
const shQuote = (s) => `'${String(s).replaceAll("'", `'\\''`)}'`;

// ---- spec loading --------------------------------------------------------
const TESTS_DIR = join(ROOT, "tests");
const specs = readdirSync(TESTS_DIR)
  .filter((f) => f.endsWith(".yaml"))
  .sort()
  .map((f) => {
    const spec = parseYamlLite(readFileSync(join(TESTS_DIR, f), "utf8"));
    for (const field of ["plugin", "tests"]) {
      if (!spec[field]) throw new Error(`tests/${f}: missing required field \`${field}\``);
    }
    return spec;
  });

// One scratch area per spec per leg: a fake project built from the spec's
// `project` files, and the stub bin dir. The log path is embedded in each
// stub (not passed via env) so the assertion cannot be defeated by a harness
// that launders hook environments.
function makeScratch(prefix, spec) {
  const scratch = mkdtempSync(join(tmpdir(), prefix));
  const project = join(scratch, "project");
  const bin = join(scratch, "bin");
  const stubLog = join(scratch, "stub-invocations.log");
  mkdirSync(project);
  mkdirSync(bin);
  for (const [rel, content] of Object.entries(spec.project || {})) {
    mkdirSync(dirname(join(project, rel)), { recursive: true });
    writeFileSync(join(project, rel), content);
  }
  for (const [name, cfg] of Object.entries(spec.stubs || {})) {
    writeFileSync(
      join(bin, name),
      `#!/bin/sh\necho "${name} $*" >> ${shQuote(stubLog)}\n` +
        `printf '%s\\n' ${shQuote(cfg.stdout ?? "")}\nexit ${Number(cfg.exit ?? 0)}\n`,
      { mode: 0o755 },
    );
  }
  const stubCalls = () =>
    existsSync(stubLog) ? readFileSync(stubLog, "utf8").trim().split("\n") : [];
  return { scratch, project, bin, stubCalls };
}

// Run one spec's tests against one harness. `session(test)` runs a fresh
// headless session in the project dir and returns {out, status}; the harness
// decides its own flags (write access when `edits_file` is set, etc.).
function runSpecTests(harness, spec, sc, session) {
  for (const t of spec.tests) {
    const label = `${harness}/${spec.plugin}/${t.name}`;
    const attempts = t.edits_file ? t.attempts || 1 : 1;
    const editPath = t.edits_file ? join(sc.project, t.edits_file) : null;
    for (let attempt = 1; attempt <= attempts; attempt++) {
      const before = sc.stubCalls().length;
      const pre = editPath && existsSync(editPath) ? readFileSync(editPath, "utf8") : null;
      const r = session(t);
      // The stub call IS the fact under test; when it happened the hook
      // dispatched, whatever the session exit code was.
      if (sc.stubCalls().slice(before).some((l) => l.includes(t.expect_stub_call))) {
        pass(`${label}: ${t.event} hook fired (stub got \`${t.expect_stub_call}\`)`);
        break;
      }
      const post = editPath && existsSync(editPath) ? readFileSync(editPath, "utf8") : null;
      if (editPath && pre !== post) {
        // The triggering edit happened, the hook still never ran: this is the
        // real failure mode this suite exists to catch.
        fail(`${label}: ${t.edits_file} WAS edited but the ${t.event} hook never ran — dispatch is broken.\n${tail(r.out)}`);
        break;
      }
      if (attempt < attempts) continue; // model never edited — inconclusive, retry
      if (editPath) {
        fail(`${label}: model never edited ${t.edits_file} in ${attempts} attempts (exit ${r.status}) — ${t.event} untested.\n${tail(r.out)}`);
      } else {
        fail(`${label}: ${t.event} hook did not fire — no \`${t.expect_stub_call}\` stub call (exit ${r.status}).\n${tail(r.out)}`);
      }
    }
  }
}

// ---- Claude Code ---------------------------------------------------------
function claudeLeg() {
  console.log("\nClaude Code — live hook dispatch (isolated config)");
  if (!have("claude")) return skip("`claude` not on PATH");
  if (!process.env.ANTHROPIC_API_KEY && !process.env.CLAUDE_CODE_OAUTH_TOKEN)
    return skip("no ANTHROPIC_API_KEY / CLAUDE_CODE_OAUTH_TOKEN — Claude leg needs auth");

  const cfg = mkdtempSync(join(tmpdir(), "e2e-cc-cfg-"));
  const baseEnv = { CLAUDE_CONFIG_DIR: join(cfg, "config") };
  try {
    const add = run("claude", ["plugin", "marketplace", "add", ROOT], { env: baseEnv });
    if (!/added marketplace/i.test(add.out)) return fail(`marketplace add failed: ${tail(add.out)}`);
    for (const spec of specs) {
      const ins = run("claude", ["plugin", "install", `${spec.plugin}@${MARKET}`, "--scope", "user"], { env: baseEnv });
      if (!/Successfully installed plugin/i.test(ins.out)) { fail(`${spec.plugin}: install failed: ${tail(ins.out)}`); continue; }
      const sc = makeScratch(`e2e-cc-${spec.plugin}-`, spec);
      try {
        runSpecTests("claude", spec, sc, (t) =>
          run(
            "claude",
            [
              "-p", t.prompt, "--model", "haiku",
              // acceptEdits when the test needs a file edit: headless runs
              // can't answer a permission prompt, and the whole point is to
              // let the edit through so the hook can fire.
              ...(t.edits_file
                ? ["--max-turns", "6", "--permission-mode", "acceptEdits"]
                : ["--max-turns", "2"]),
            ],
            { cwd: sc.project, env: { ...baseEnv, PATH: `${sc.bin}:${process.env.PATH}` }, timeout: 300_000 },
          ),
        );
      } finally { rmSync(sc.scratch, { recursive: true, force: true }); }
    }
  } finally { rmSync(cfg, { recursive: true, force: true }); }
}

// ---- Codex ---------------------------------------------------------------
function codexLeg() {
  console.log("\nCodex — live hook dispatch (isolated CODEX_HOME)");
  if (!have("codex")) return skip("`codex` not on PATH");
  const key = process.env.CODEX_API_KEY || process.env.OPENAI_API_KEY;
  if (!key) return skip("no CODEX_API_KEY / OPENAI_API_KEY — Codex leg needs auth");

  const home = mkdtempSync(join(tmpdir(), "e2e-cx-home-"));
  const baseEnv = { CODEX_HOME: join(home, "codex"), CODEX_API_KEY: key, OPENAI_API_KEY: key };
  mkdirSync(baseEnv.CODEX_HOME, { recursive: true });
  // Belt and braces: some Codex versions read the key from the environment,
  // others want it persisted in auth.json. Harmless where redundant.
  run("codex", ["login", "--with-api-key"], { env: baseEnv, input: key });
  try {
    const add = run("codex", ["plugin", "marketplace", "add", ROOT], { env: baseEnv });
    if (!/Added marketplace/i.test(add.out)) return fail(`marketplace add failed: ${tail(add.out)}`);
    for (const spec of specs) {
      const ins = run("codex", ["plugin", "add", `${spec.plugin}@${MARKET}`], { env: baseEnv });
      if (!/Added plugin/i.test(ins.out)) { fail(`${spec.plugin}: plugin add failed: ${tail(ins.out)}`); continue; }
      const sc = makeScratch(`e2e-cx-${spec.plugin}-`, spec);
      try {
        runSpecTests("codex", spec, sc, (t) =>
          run(
            "codex",
            [
              "exec", "--skip-git-repo-check",
              // Plugin-bundled hooks require an interactive trust review
              // before they run; this flag is the documented escape hatch for
              // automation, and everything here is a throwaway home running
              // this repo's own hooks.
              "--dangerously-bypass-hook-trust",
              // danger-full-access when the test needs a file edit: Codex's
              // bubblewrap sandbox cannot initialize on GitHub Actions
              // runners (AppArmor blocks the unprivileged-userns loopback
              // setup: "bwrap: loopback: Failed RTM_NEWADDR"), which fails
              // every apply_patch before the hook can ever fire. The
              // throwaway CI VM / scratch dir is the isolation boundary.
              ...(t.edits_file ? ["--sandbox", "danger-full-access"] : []),
              t.prompt,
            ],
            { cwd: sc.project, env: { ...baseEnv, PATH: `${sc.bin}:${process.env.PATH}` }, timeout: 300_000 },
          ),
        );
      } finally { rmSync(sc.scratch, { recursive: true, force: true }); }
    }
  } finally { rmSync(home, { recursive: true, force: true }); }
}

// ---- run -----------------------------------------------------------------
console.log(`E2E hook-dispatch tests — repo ${ROOT}\nspecs: ${specs.map((s) => s.plugin).join(", ")}`);
if (wantClaude) claudeLeg();
if (wantCodex) codexLeg();

console.log(failures ? `\n\x1b[31m✗ ${failures} e2e failure(s)\x1b[0m` : "\n\x1b[32m✓ all e2e checks passed\x1b[0m");
process.exit(failures ? 1 : 0);
