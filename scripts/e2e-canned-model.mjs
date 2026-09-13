#!/usr/bin/env node
// A canned OpenAI-compatible model for the e2e hook-dispatch legs whose
// harnesses (OpenCode, Pi) persist no trace of hook-injected context: neither
// records the system prompt a SessionStart hook extends, so the only place
// every injected byte can be observed is the model request itself. This server
// IS that trace: it logs each chat-completions request and answers with a
// scripted reply, so a leg needs no API key and no retries — the "model" is
// only ever a means to trigger events, and this one triggers them on demand.
//
// It runs as its OWN process (the runner drives sessions with spawnSync, which
// would block an in-process server), talking to the runner through a
// directory: `plan.json` scripts the reply, `requests.jsonl` gets one line per
// request received.
//
//   node scripts/e2e-canned-model.mjs <dir>     # prints "LISTENING <url>" once up
//
// The plan is per session: `{ "write": { "path", "content" } }` makes the model
// call the harness's `write` tool on that file with that content (once; after
// the tool result it answers with text), `{}` answers with text. The write
// tool's argument names differ per harness (OpenCode `filePath`, Pi `path`),
// so they are read from the tool schema the harness sends, not assumed.
//
// Speaks the chat-completions protocol both harnesses' OpenAI-compatible
// providers use (streaming SSE and plain JSON), plus GET /v1/models. Zero
// dependencies, node:http only.

import { spawn } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const SELF = fileURLToPath(import.meta.url);

function serve(dir) {
  mkdirSync(dir, { recursive: true });
  const planFile = join(dir, "plan.json");
  const logFile = join(dir, "requests.jsonl");
  const readPlan = () => (existsSync(planFile) ? JSON.parse(readFileSync(planFile, "utf8")) : {});

  const reply = (body) => {
    const plan = readPlan();
    const last = body.messages?.at(-1);
    if (plan.write && last?.role !== "tool") {
      const tool = (body.tools || []).map((t) => t.function ?? t).find((t) => t.name === "write");
      if (tool) {
        const props = Object.keys(tool.parameters?.properties || {});
        const pathKey = props.find((k) => /path/i.test(k)) || "path";
        const args = { [pathKey]: plan.write.path, content: plan.write.content };
        return { toolCall: { id: "call_e2e_write", name: "write", arguments: JSON.stringify(args) } };
      }
    }
    return { text: "OK" };
  };

  const server = createServer((req, res) => {
    if (req.method === "GET" && req.url.endsWith("/models")) {
      res.setHeader("content-type", "application/json");
      return res.end(JSON.stringify({ object: "list", data: [{ id: "canned", object: "model", owned_by: "e2e" }] }));
    }
    if (req.method !== "POST" || !req.url.endsWith("/chat/completions")) {
      res.statusCode = 404;
      return res.end();
    }
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => {
      const body = JSON.parse(raw);
      appendFileSync(logFile, JSON.stringify(body) + "\n");
      const r = reply(body);
      const base = { id: "chatcmpl-e2e", object: "chat.completion", created: 0, model: "canned" };
      const usage = { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 };
      const toolCalls = r.toolCall
        ? [{ id: r.toolCall.id, type: "function", function: { name: r.toolCall.name, arguments: r.toolCall.arguments } }]
        : null;
      const finish = r.toolCall ? "tool_calls" : "stop";
      if (!body.stream) {
        const message = toolCalls ? { role: "assistant", content: null, tool_calls: toolCalls } : { role: "assistant", content: r.text };
        res.setHeader("content-type", "application/json");
        return res.end(JSON.stringify({ ...base, choices: [{ index: 0, message, finish_reason: finish }], usage }));
      }
      res.setHeader("content-type", "text/event-stream");
      res.setHeader("cache-control", "no-cache");
      const chunk = (delta, finish_reason = null, extra = {}) =>
        res.write(`data: ${JSON.stringify({ ...base, object: "chat.completion.chunk", choices: [{ index: 0, delta, finish_reason }], ...extra })}\n\n`);
      chunk(toolCalls ? { role: "assistant", tool_calls: [{ index: 0, ...toolCalls[0] }] } : { role: "assistant", content: r.text });
      chunk({}, finish, { usage });
      res.end("data: [DONE]\n\n");
    });
  });
  server.listen(0, "127.0.0.1", () => console.log(`LISTENING http://127.0.0.1:${server.address().port}/v1`));
}

/** Start the canned model in a child process. Resolves once it listens, to
 *  { url, script(plan), requests(), close() }. `requests()` returns every
 *  request body received so far, oldest first. */
export function startCannedModel(dir) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [SELF, dir], { stdio: ["ignore", "pipe", "inherit"] });
    let out = "";
    child.stdout.on("data", (c) => {
      out += c;
      const m = /LISTENING (\S+)/.exec(out);
      if (!m) return;
      resolve({
        url: m[1],
        script: (plan) => writeFileSync(join(dir, "plan.json"), JSON.stringify(plan)),
        requests: () => {
          const f = join(dir, "requests.jsonl");
          return existsSync(f) ? readFileSync(f, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l)) : [];
        },
        close: () => child.kill(),
      });
    });
    child.on("exit", (code) => reject(new Error(`canned model exited with ${code} before listening`)));
  });
}

if (process.argv[1] === SELF) serve(process.argv[2] || ".");
