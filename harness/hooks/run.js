// Runs this plugin's hooks.json on harnesses that have no hooks.json of their
// own (OpenCode, Pi). Copied verbatim into every plugin's npm package next to
// the very same hooks/ tree the Claude Code and Codex packages ship, so the
// wiring (events, matchers, commands, timeouts) and the scripts are shared by
// construction — nothing here is generated or per-plugin.
//
// Each hook command is run exactly as Claude Code runs it: through `bash -c`,
// in the project directory, with the payload on stdin, CLAUDE_PLUGIN_ROOT set
// to the package root (which is what the commands resolve their script from),
// and killed after its hooks.json timeout. A hook never fails the tool call or
// the request it decorates: any problem — no bash on PATH, a crash, a timeout,
// non-JSON output — just yields no context.

import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const PLUGIN_ROOT = fileURLToPath(new URL("..", import.meta.url)).replace(/[\\/]$/, "");
const { hooks: HOOKS } = JSON.parse(readFileSync(new URL("hooks.json", import.meta.url), "utf8"));

// Matchers are the Claude/Codex tool-name regexes ("Write|Edit"); OpenCode and
// Pi name the same tools in lowercase, so matching is case-insensitive.
function matches(matcher, tool) {
  if (!matcher) return true;
  return new RegExp("^(?:" + matcher + ")$", "i").test(tool || "");
}

function runCommand(command, payload, cwd, timeoutSeconds) {
  return new Promise((resolve) => {
    let out = "";
    let child;
    try {
      child = spawn("bash", ["-c", command], {
        cwd,
        env: { ...process.env, CLAUDE_PLUGIN_ROOT: PLUGIN_ROOT },
        stdio: ["pipe", "pipe", "ignore"],
      });
    } catch {
      return resolve("");
    }
    const timer = setTimeout(() => child.kill(), timeoutSeconds * 1000);
    const done = () => { clearTimeout(timer); resolve(out); };
    child.stdout.on("data", (chunk) => (out += chunk));
    child.on("error", done);
    child.on("close", done);
    child.stdin.on("error", () => {});
    child.stdin.end(payload);
  });
}

// A script prints hook envelopes, one JSON object per line; collect their
// additionalContext and drop anything that is not an envelope.
function contextOf(stdout) {
  const parts = [];
  for (const line of stdout.split("\n")) {
    if (!line.trim()) continue;
    try {
      const ctx = JSON.parse(line)?.hookSpecificOutput?.additionalContext;
      if (typeof ctx === "string" && ctx.trim()) parts.push(ctx.trim());
    } catch {}
  }
  return parts.join("\n\n");
}

/** Run every hooks.json command registered for `event` whose matcher accepts
 *  `tool`, in order, and return their additionalContext joined ("" when none).
 *  `fields` are merged into the Claude Code-shaped payload the scripts read. */
export async function runHooks(event, tool, cwd, fields = {}) {
  const payload = JSON.stringify({ hook_event_name: event, cwd, ...fields });
  const parts = [];
  for (const group of HOOKS[event] || []) {
    if (!matches(group.matcher, tool)) continue;
    for (const hook of group.hooks || []) {
      if (hook.type !== "command") continue;
      const ctx = contextOf(await runCommand(hook.command, payload, cwd, hook.timeout || 60));
      if (ctx) parts.push(ctx);
    }
  }
  return parts.join("\n\n");
}
