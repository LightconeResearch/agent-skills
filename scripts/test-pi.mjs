#!/usr/bin/env node
// Hermetic tests for the Pi adapter as packaged (plugins/<name>/pi/index.js,
// listed under package.json `pi.extensions`, running plugins/<name>/hooks/hooks.json).
// No Pi binary, no network, no real astra: the module is imported into this
// process and its factory is handed a fake `pi` that records handlers, which
// are then called the way Pi calls them, with the fake `uvx` from test-lib.mjs
// on PATH so the scripts' behaviour is observable.
//
// What this proves, on top of test-hooks.mjs (the scripts) and validate.mjs
// (the packaged files are byte copies of their sources):
//   - the wiring: `tool_result` runs the PostToolUse scripts for the tools the
//     hooks.json matcher names (Pi's `write`, `edit`) and returns undefined for
//     the rest — Pi keeps the result untouched when a handler returns nothing;
//   - the routing: context is appended to event.content as a text block, and
//     the primer to event.systemPrompt;
//   - the primer contract: one SessionStart run per session, re-appended on
//     every before_agent_start (Pi resets to the base prompt otherwise), and
//     undefined outside an ASTRA project so the base prompt stays untouched;
//   - a bundling plugin (lightcone) runs its dependency's hooks too, in order.

import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { ROOT, assertIncludes, fail, hermeticEnv, makeScratch } from "./test-lib.mjs";

const { project, elsewhere, bin, uvxCalls, cleanup } = makeScratch("pi-extension-");
hermeticEnv(bin);

// Load a plugin's Pi extension and register it against a fake `pi`. Returns
// the handlers by event name.
async function load(name) {
  const mod = await import(pathToFileURL(join(ROOT, `plugins/${name}/pi/index.js`)).href);
  if (typeof mod.default !== "function") fail(`${name}: pi/index.js has no default-exported factory`);
  const handlers = {};
  mod.default({ on: (event, fn) => { handlers[event] = fn; } });
  return handlers;
}
const ctxFor = (cwd) => ({ cwd, hasUI: true });

// A Pi tool_result event as the runtime emits it for a built-in tool.
const toolResult = (toolName, input) => ({
  toolName,
  toolCallId: "call-1",
  input,
  content: [{ type: "text", text: "tool said ok" }],
  details: {},
  isError: false,
});

try {
  const astra = await load("astra");
  for (const event of ["session_start", "before_agent_start", "tool_result"])
    if (typeof astra[event] !== "function") fail(`astra: no handler for ${event}`);

  // --- validate-on-save via tool_result -----------------------------------
  const spec = join(project, "astra.yaml");
  let patch = await astra.tool_result(toolResult("write", { path: spec, content: "id: test\n" }), ctxFor(project));
  if (!patch?.content) fail("write/fail: expected a content patch");
  if (patch.content[0].text !== "tool said ok") fail("write/fail: original content was not preserved");
  assertIncludes("write/fail", patch.content.at(-1).text, "ASTRA validation FAILED for ./astra.yaml");
  assertIncludes("write/fail", patch.content.at(-1).text, "fake report:");
  assertIncludes("write/fail uvx args", uvxCalls().at(-1), "validate astra.yaml --json");

  // Pi's edit tool: { path, edits: [...] } — the path in the payload is enough.
  process.env.FAKE_UVX_RC = "0";
  patch = await astra.tool_result(toolResult("edit", { path: spec, edits: [{ oldText: "a", newText: "b" }] }), ctxFor(project));
  assertIncludes("edit/pass", patch.content.at(-1).text, "ASTRA validation passed");
  delete process.env.FAKE_UVX_RC;

  // Tools outside the matcher: handler returns nothing, uvx never runs.
  let before = uvxCalls().length;
  patch = await astra.tool_result(toolResult("read", { path: spec }), ctxFor(project));
  if (patch !== undefined) fail(`read/untouched: expected undefined, got ${JSON.stringify(patch)}`);
  if (uvxCalls().length !== before) fail("read/untouched: uvx was invoked for a non-matching tool");

  // A matching tool that did not touch the spec: silent too.
  before = uvxCalls().length;
  patch = await astra.tool_result(toolResult("write", { path: join(project, "README.md"), content: "hi" }), ctxFor(project));
  if (patch !== undefined) fail("write/other-file: expected undefined");
  if (uvxCalls().length !== before) fail("write/other-file: uvx was invoked");

  // --- session primer via session_start + before_agent_start ---------------
  process.env.FAKE_UVX_RC = "0";
  before = uvxCalls().length;
  await astra.session_start({ reason: "startup" }, ctxFor(project));
  let result = await astra.before_agent_start({ prompt: "hi", systemPrompt: "base prompt" }, ctxFor(project));
  if (!result?.systemPrompt?.startsWith("base prompt")) fail("primer: base system prompt was not preserved");
  assertIncludes("primer", result.systemPrompt, "ASTRA project — spec at ./astra.yaml");
  assertIncludes("primer", result.systemPrompt, "Activate the astra skill");
  assertIncludes("primer uvx args", uvxCalls().at(-1), "info --json");
  if (uvxCalls().length !== before + 1) fail("primer: expected exactly one SessionStart run");

  // Next turn: re-appended from the cached run, no second script run.
  result = await astra.before_agent_start({ prompt: "again", systemPrompt: "base prompt" }, ctxFor(project));
  assertIncludes("primer/cached", result.systemPrompt, "ASTRA project — spec at ./astra.yaml");
  if (uvxCalls().length !== before + 1) fail("primer/cached: SessionStart ran again within the session");

  // A new session (Pi re-fires session_start) runs it again — once.
  await astra.session_start({ reason: "new" }, ctxFor(project));
  result = await astra.before_agent_start({ prompt: "x", systemPrompt: "base prompt" }, ctxFor(project));
  assertIncludes("primer/new-session", result.systemPrompt, "ASTRA project");
  if (uvxCalls().length !== before + 2) fail("primer/new-session: expected one more run");

  // before_agent_start without a prior session_start still primes itself.
  const fresh = await load("astra");
  before = uvxCalls().length;
  result = await fresh.before_agent_start({ prompt: "x", systemPrompt: "base prompt" }, ctxFor(project));
  assertIncludes("primer/lazy", result.systemPrompt, "ASTRA project");
  if (uvxCalls().length !== before + 1) fail("primer/lazy: expected one run");
  delete process.env.FAKE_UVX_RC;

  // Outside an ASTRA project the handler returns nothing, so Pi keeps its base prompt.
  const away = await load("astra");
  await away.session_start({ reason: "startup" }, ctxFor(elsewhere));
  result = await away.before_agent_start({ prompt: "x", systemPrompt: "base prompt" }, ctxFor(elsewhere));
  if (result !== undefined) fail(`primer/elsewhere: expected undefined, got ${JSON.stringify(result)}`);

  // --- lightcone bundles astra: both primers, dependency first -------------
  process.env.FAKE_UVX_RC = "0";
  const lightcone = await load("lightcone");
  await lightcone.session_start({ reason: "startup" }, ctxFor(project));
  result = await lightcone.before_agent_start({ prompt: "x", systemPrompt: "base prompt" }, ctxFor(project));
  const sys = result.systemPrompt;
  assertIncludes("lightcone/astra-primer", sys, "ASTRA project — spec at ./astra.yaml");
  assertIncludes("lightcone/engine-primer", sys, "Lightcone project");
  assertIncludes("lightcone/engine-primer", sys, "is not installed"); // no `lc` on the hermetic PATH
  assertIncludes("lightcone/mode", sys, "Ask the user"); // no harness variable → ask
  if (sys.indexOf("ASTRA project") > sys.indexOf("Lightcone project"))
    fail("lightcone: dependency (astra) primer must precede the plugin's own");
  patch = await lightcone.tool_result(toolResult("write", { path: spec, content: "" }), ctxFor(project));
  assertIncludes("lightcone/validate", patch.content.at(-1).text, "ASTRA validation passed");
  delete process.env.FAKE_UVX_RC;

  console.log("✓ Pi adapter: tool matching, result/system-prompt routing, and the per-session primer all behave.");
} finally {
  cleanup();
}
