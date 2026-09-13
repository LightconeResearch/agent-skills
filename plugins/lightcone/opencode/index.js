// OpenCode plugin: the package main. Maps this plugin's hooks.json (shipped
// next door under hooks/, run by ../hooks/run.js) onto the OpenCode plugin API:
//
//   PostToolUse  → "tool.execute.after": additionalContext is appended to the
//                  tool result the model reads.
//   SessionStart → "experimental.chat.system.transform": the primer runs once
//                  per session (started on the session.created event) and is
//                  appended to the system prompt on every request — OpenCode
//                  rebuilds the prompt each time, so a one-shot injection would
//                  be forgotten after the first turn.
//
// Needs `bash` on PATH; the scripts need `uvx` and say so themselves when it
// is missing. No dependencies.

import { runHooks } from "../hooks/run.js";

/** @type {import("@opencode-ai/plugin").Plugin} */
export default async function ({ directory }) {
  const cwd = directory || process.cwd();
  let primer; // Promise<string>: one SessionStart run per session
  const prime = () => (primer ??= runHooks("SessionStart", "", cwd, { source: "startup" }));

  return {
    event: async ({ event }) => {
      if (event?.type === "session.created") {
        primer = undefined;
        void prime();
      }
    },
    "experimental.chat.system.transform": async (_input, output) => {
      const ctx = await prime();
      if (ctx) output.system.push(ctx);
    },
    "tool.execute.after": async (input, output) => {
      const ctx = await runHooks("PostToolUse", input.tool, cwd, {
        session_id: input.sessionID,
        tool_name: input.tool,
        tool_input: input.args,
        tool_response: { title: output?.title },
      });
      if (ctx) output.output = (output.output ?? "") + "\n\n" + ctx;
    },
  };
}
