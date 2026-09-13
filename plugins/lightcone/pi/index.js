// Pi extension (listed under package.json `pi.extensions`). Maps this plugin's
// hooks.json (shipped next door under hooks/, run by ../hooks/run.js) onto the
// Pi extension API:
//
//   PostToolUse  → "tool_result": additionalContext is appended to the result
//                  content as a text block.
//   SessionStart → "before_agent_start": the primer runs once per session
//                  (started from session_start) and is appended to the system
//                  prompt on every turn — Pi resets to the base prompt when a
//                  handler returns nothing. Pi rebinds extensions per session,
//                  so the cached primer is per session by construction.
//
// Needs `bash` on PATH; the scripts need `uvx` and say so themselves when it
// is missing. No dependencies.

import { runHooks } from "../hooks/run.js";

/** @param {import("@earendil-works/pi-coding-agent").ExtensionAPI} pi */
export default function (pi) {
  let primer; // Promise<string>: one SessionStart run per session
  const prime = (cwd) => (primer ??= runHooks("SessionStart", "", cwd, { source: "startup" }));

  pi.on("session_start", async (_event, ctx) => {
    primer = undefined;
    void prime(ctx.cwd);
  });

  pi.on("before_agent_start", async (event, ctx) => {
    const text = await prime(ctx.cwd);
    if (text) return { systemPrompt: (event.systemPrompt ?? "") + "\n\n" + text };
  });

  pi.on("tool_result", async (event, ctx) => {
    const text = await runHooks("PostToolUse", event.toolName, ctx.cwd, {
      tool_name: event.toolName,
      tool_input: event.input,
      tool_response: { isError: event.isError },
    });
    if (text) return { content: [...(event.content ?? []), { type: "text", text }] };
  });
}
