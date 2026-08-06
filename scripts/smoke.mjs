#!/usr/bin/env node
// Install smoke tests — prove each plugin actually installs and loads on both
// harnesses. No LLM/API calls: only `claude plugin …` / `codex plugin …` (which
// run headless without auth) and, for the interactive path, tmux send-keys into a
// real REPL whose state is asserted out-of-band.
//
//   npm run smoke              # everything available on this machine
//   npm run smoke -- --cli     # hermetic CLI installs only (no tmux, no real config)
//   npm run smoke -- --tmux    # interactive tmux install only
//
// CLI phase (hermetic): each harness installs every plugin into a throwaway config
// dir and we assert the "installed / enabled" confirmation. Isolated config needs
// no login, so this is the CI-grade gate.
//
// tmux phase (needs a logged-in `claude`): drives the in-session `/plugin install`
// flow with send-keys against the *real* config, installs to a throwaway project,
// asserts, and cleans up. Auto-skips when no authenticated REPL is reachable.

import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(import.meta.url), "..", "..");
const PLUGINS = ["astra", "lightcone"];
const MARKET = "lightcone-research";
const CODEX_PROBE_SKILLS = {
  astra: "astra",
  lightcone: "async",
};
// Hooks auto-discover from a packaged hooks/hooks.json (no manifest declaration),
// so their presence in the cache is what makes them load — probe the plugins that
// ship them. Same silent-omission risk as skills; keep the assertions symmetric.
const CODEX_PROBE_HOOKS = {
  astra: "hooks/hooks.json",
  lightcone: "hooks/hooks.json",
};

const args = process.argv.slice(2);
const only = args.includes("--cli") ? "cli" : args.includes("--tmux") ? "tmux" : "all";

let failures = 0;
const pass = (m) => console.log(`  \x1b[32m✓\x1b[0m ${m}`);
const fail = (m) => { console.log(`  \x1b[31m✗ ${m}\x1b[0m`); failures++; };
const skip = (m) => console.log(`  \x1b[33m∅ skip\x1b[0m ${m}`);
const have = (bin) => spawnSync("sh", ["-c", `command -v ${bin}`]).status === 0;
const mktemp = (p) => mkdtempSync(join(tmpdir(), p));

// Run a command, capturing combined output; never throws.
function run(bin, argv, env = {}) {
  const r = spawnSync(bin, argv, { encoding: "utf8", env: { ...process.env, ...env } });
  return { out: (r.stdout || "") + (r.stderr || ""), status: r.status };
}

// Is `id` present-and-enabled in a `claude plugin list` dump? Anchor to the
// plugin's own block (name line → next block) and require an enabled Status
// there — a bare `[\s\S]*?enabled` would cross into a later plugin's row.
function claudeEnabled(listOut, id) {
  const lines = listOut.split("\n");
  const start = lines.findIndex((l) => l.includes(id));
  if (start === -1) return false;
  let end = lines.length;
  for (let i = start + 1; i < lines.length; i++) if (/^\s*❯\s/.test(lines[i])) { end = i; break; }
  const block = lines.slice(start, end).join("\n");
  return /Status:.*(enabled|✔)/i.test(block) && !/failed to load/i.test(block);
}

// Codex `plugin list` is one row per plugin: the id and its status share a line.
function codexEnabled(listOut, id) {
  return listOut.split("\n").some((l) => l.includes(id) && /installed, enabled/i.test(l));
}

// Installation can report success even when an archive silently omits packaged
// component trees. Assert a known file exists in at least one cached version.
function codexFileCached(codexHome, plugin, relPath) {
  const versions = join(codexHome, "plugins", "cache", MARKET, plugin);
  if (!existsSync(versions)) return false;
  return readdirSync(versions).some((version) =>
    existsSync(join(versions, version, relPath)),
  );
}

// ---- CLI phase (hermetic) ------------------------------------------------
function cliClaude() {
  console.log("\nClaude Code — CLI install (isolated config)");
  if (!have("claude")) return skip("`claude` not on PATH");
  const cfg = mktemp("smoke-cc-");
  const env = { CLAUDE_CONFIG_DIR: join(cfg, "config") };
  try {
    const add = run("claude", ["plugin", "marketplace", "add", ROOT], env);
    if (!/added marketplace/i.test(add.out)) return fail(`marketplace add failed: ${add.out.trim().slice(-200)}`);
    for (const p of PLUGINS) {
      const ins = run("claude", ["plugin", "install", `${p}@${MARKET}`, "--scope", "user"], env);
      if (!/Successfully installed plugin/i.test(ins.out)) { fail(`${p}: install gave no confirmation`); continue; }
      const list = run("claude", ["plugin", "list"], env);
      if (claudeEnabled(list.out, `${p}@${MARKET}`)) pass(`${p}: installed + enabled`);
      else fail(`${p}: not enabled after install:\n${list.out.trim().slice(-300)}`);
    }
  } finally { rmSync(cfg, { recursive: true, force: true }); }
}

function cliCodex() {
  console.log("\nCodex — CLI install (isolated CODEX_HOME)");
  if (!have("codex")) return skip("`codex` not on PATH");
  const home = mktemp("smoke-cx-");
  const env = { CODEX_HOME: join(home, "codex") };
  mkdirSync(env.CODEX_HOME, { recursive: true }); // codex requires CODEX_HOME to pre-exist
  try {
    const add = run("codex", ["plugin", "marketplace", "add", ROOT], env);
    if (!/Added marketplace/i.test(add.out)) return fail(`marketplace add failed: ${add.out.trim().slice(-200)}`);
    for (const p of PLUGINS) {
      const ins = run("codex", ["plugin", "add", `${p}@${MARKET}`], env);
      if (!/Added plugin/i.test(ins.out)) { fail(`${p}: add gave no confirmation`); continue; }
      const list = run("codex", ["plugin", "list"], env);
      if (codexEnabled(list.out, `${p}@${MARKET}`)) pass(`${p}: installed + enabled`);
      else fail(`${p}: not enabled after add:\n${list.out.trim().slice(-300)}`);
      const skill = CODEX_PROBE_SKILLS[p];
      if (codexFileCached(env.CODEX_HOME, p, `skills/${skill}/SKILL.md`)) pass(`${p}: ${skill} skill packaged in cache`);
      else fail(`${p}: installed cache is missing skills/${skill}/SKILL.md`);
      const hook = CODEX_PROBE_HOOKS[p];
      if (hook && codexFileCached(env.CODEX_HOME, p, hook)) pass(`${p}: ${hook} packaged in cache`);
      else if (hook) fail(`${p}: installed cache is missing ${hook}`);
    }
  } finally { rmSync(home, { recursive: true, force: true }); }
}

// ---- tmux phase (interactive, real config) -------------------------------
const tmux = (...a) => run("tmux", a);
const sleep = (ms) => execFileSync("sh", ["-c", `sleep ${ms / 1000}`]);

// Poll a tmux pane until it reaches a ready `claude` prompt. Returns "ready",
// or "login"/"onboarding" if the REPL is blocked on auth/setup, or "timeout".
function waitForRepl(s, timeoutMs = 30000) {
  let trusted = false;
  for (let waited = 0; waited < timeoutMs; waited += 1000) {
    sleep(1000);
    const pane = tmux("capture-pane", "-t", s, "-p").out;
    if (/Select login method|Paste code here|oauth\/authorize/i.test(pane)) return "login";
    if (/Choose the text style|Dark mode|Light mode/i.test(pane)) return "onboarding";
    // Launching in a fresh dir raises a "trust this folder?" gate — confirm once.
    if (!trusted && /trust this folder|Is this a project you (created|trust)/i.test(pane)) {
      tmux("send-keys", "-t", s, "Enter");
      trusted = true;
      continue;
    }
    if (/auto mode|Welcome to Claude Code|shift\+tab to cycle/i.test(pane)) return "ready";
  }
  if (process.env.SMOKE_DEBUG) console.log("--- timeout pane ---\n" + tmux("capture-pane", "-t", s, "-p").out + "\n--- end ---");
  return "timeout";
}

function tmuxClaude() {
  console.log("\nClaude Code — interactive install (tmux send-keys, real config)");
  if (!have("claude") || !have("tmux")) return skip("need both `claude` and `tmux`");
  const target = "astra"; // smallest plugin; the interactive path is what we assert
  // Snapshot what we might mutate, so cleanup restores exactly the prior state and
  // never touches a marketplace/plugin the user already had installed for real.
  const preexisting = new RegExp(`\\b${MARKET}\\b`).test(run("claude", ["plugin", "marketplace", "list"]).out);
  const preInstalled = new RegExp(`${target}@${MARKET}`).test(run("claude", ["plugin", "list"]).out);

  const proj = mktemp("smoke-proj-");
  const s = `smoke-int-${process.pid}`;
  let added = false;
  try {
    if (!preexisting) { run("claude", ["plugin", "marketplace", "add", ROOT]); added = true; }
    tmux("kill-session", "-t", s);
    tmux("new-session", "-d", "-s", s, "-x", "200", "-y", "50");
    tmux("send-keys", "-t", s, `cd ${proj}; command claude`, "Enter");
    const state = waitForRepl(s);
    if (state !== "ready") {
      tmux("kill-session", "-t", s);
      return skip(`no authenticated \`claude\` REPL (${state}) — run \`claude\` once to log in, then retry`);
    }
    // Type the command WITHOUT Enter first: an autocomplete menu pops up, and a
    // same-burst Enter would select the suggestion instead of submitting.
    tmux("send-keys", "-t", s, `/plugin install ${target}@${MARKET}`);
    sleep(2500);
    tmux("send-keys", "-t", s, "Enter"); // submit → opens the details/scope pane
    sleep(3500);
    tmux("send-keys", "-t", s, "Enter"); // confirm default "Install for you (user scope)"
    sleep(4000);
    // Ground truth, not screen-scraping: query the real config out-of-band.
    let installed = false;
    for (let i = 0; i < 5 && !installed; i++) {
      installed = new RegExp(`${target}@${MARKET}`).test(run("claude", ["plugin", "list"]).out);
      if (!installed) sleep(1500);
    }
    const pane = tmux("capture-pane", "-t", s, "-p", "-S", "-200").out; // scrollback, for diagnostics
    tmux("send-keys", "-t", s, "Escape");
    sleep(500);
    tmux("kill-session", "-t", s);
    if (installed) pass(`${target}: interactive /plugin install landed in config`);
    else fail(`${target}: not installed after interactive flow:\n${pane.trim().slice(-500)}`);
  } finally {
    // Restore the real config to exactly how we found it: only undo what we did.
    // Never uninstall a plugin the user already had, and never touch anything on
    // the skip path (where preInstalled is still the user's true state).
    if (!preInstalled) run("claude", ["plugin", "uninstall", `${target}@${MARKET}`]);
    if (added) run("claude", ["plugin", "marketplace", "remove", MARKET]);
    rmSync(proj, { recursive: true, force: true });
    tmux("kill-session", "-t", s);
  }
}

// ---- run -----------------------------------------------------------------
console.log(`Smoke tests — repo ${ROOT}\nmode: ${only}`);
if (only === "all" || only === "cli") { cliClaude(); cliCodex(); }
if (only === "all" || only === "tmux") { tmuxClaude(); }

console.log(failures ? `\n\x1b[31m✗ ${failures} smoke failure(s)\x1b[0m` : "\n\x1b[32m✓ all smoke checks passed\x1b[0m");
process.exit(failures ? 1 : 0);
