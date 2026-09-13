#!/usr/bin/env node
// Hermetic tests for the OpenCode adapter as packaged (plugins/<name>/opencode/index.js,
// the npm package main, running plugins/<name>/hooks/hooks.json). No OpenCode
// binary, no network, no real astra: the module is imported into this process
// and its hooks are called the way OpenCode calls them, with the fake `uvx` from
// test-lib.mjs on PATH so the scripts' behaviour is observable.
//
// What this proves, on top of test-hooks.mjs (the scripts) and validate.mjs
// (the packaged files are byte copies of their sources):
//   - the wiring: PostToolUse groups fire from "tool.execute.after" for the
//     tools the hooks.json matcher names (OpenCode's `write`, `edit` and
//     `apply_patch`, matched case-insensitively) and stay silent for the rest;
//   - the routing: a script's additionalContext lands in output.output (tool
//     result) or output.system (system prompt), and non-envelope noise does not;
//   - the primer contract: one SessionStart run per session (session.created
//     starts it), re-emitted on every request;
//   - a bundling plugin (lightcone) runs its dependency's hooks too, in order.

import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { ROOT, assertIncludes, fail, hermeticEnv, makeScratch } from "./test-lib.mjs";

const { project, elsewhere, bin, uvxCalls, cleanup } = makeScratch("opencode-plugin-");
hermeticEnv(bin);

async function load(name, directory) {
  const mod = await import(pathToFileURL(join(ROOT, `plugins/${name}/opencode/index.js`)).href);
  if (typeof mod.default !== "function") fail(`${name}: module has no default-exported plugin function`);
  // OpenCode iterates EVERY export of a plugin module and throws on a non-function,
  // so the module must expose exactly the one default export.
  const exported = Object.keys(mod);
  if (exported.length !== 1 || exported[0] !== "default") fail(`${name}: unexpected exports ${JSON.stringify(exported)}`);
  return mod.default({ directory, worktree: directory, project: {}, client: {}, $: null });
}

// One "tool.execute.after" call as OpenCode makes it; returns the tool output
// the model would read afterwards.
async function afterTool(hooks, tool, args, sessionID = "s") {
  const output = { title: `${tool} result`, output: "tool said ok", metadata: {} };
  await hooks["tool.execute.after"]({ tool, sessionID, callID: "c1", args }, output);
  return output.output;
}

async function systemFor(hooks, sessionID) {
  const output = { system: ["base prompt"] };
  await hooks["experimental.chat.system.transform"]({ sessionID, model: {} }, output);
  return output.system;
}

const sessionCreated = (hooks, id) => hooks.event({ event: { type: "session.created", properties: { info: { id } } } });

try {
  const astra = await load("astra", project);
  for (const hook of ["tool.execute.after", "experimental.chat.system.transform", "event"])
    if (typeof astra[hook] !== "function") fail(`astra: hook ${hook} not registered`);

  // --- validate-on-save via tool.execute.after -------------------------------
  const spec = join(project, "astra.yaml");
  let out = await afterTool(astra, "write", { filePath: spec, content: "id: test\n" });
  assertIncludes("write/fail", out, "tool said ok"); // the original result is kept…
  assertIncludes("write/fail", out, "ASTRA validation FAILED for ./astra.yaml"); // …and decorated
  assertIncludes("write/fail", out, "fake report:");
  assertIncludes("write/fail uvx args", uvxCalls().at(-1), "validate astra.yaml --json");

  process.env.FAKE_UVX_RC = "0";
  out = await afterTool(astra, "edit", { filePath: spec, oldString: "a", newString: "b" });
  assertIncludes("edit/pass", out, "ASTRA validation passed");
  delete process.env.FAKE_UVX_RC;

  // OpenCode's apply_patch tool (lowercase id) matches the Codex name in the matcher.
  out = await afterTool(astra, "apply_patch", { patchText: "*** Update File: astra.yaml" });
  assertIncludes("apply_patch", out, "ASTRA validation FAILED");

  // Tools outside the matcher never run the script, even when they mention the spec.
  let before = uvxCalls().length;
  out = await afterTool(astra, "read", { filePath: spec });
  if (out !== "tool said ok") fail(`read/untouched: output was decorated\n${out}`);
  if (uvxCalls().length !== before) fail("read/untouched: uvx was invoked for a non-matching tool");

  // A matching tool whose payload does not mention the spec is silent too
  // (the script's own prefilter), and output is returned untouched.
  before = uvxCalls().length;
  out = await afterTool(astra, "write", { filePath: join(project, "README.md"), content: "hello" });
  if (out !== "tool said ok") fail(`write/other-file: output was decorated\n${out}`);
  if (uvxCalls().length !== before) fail("write/other-file: uvx was invoked");

  // --- session primer via experimental.chat.system.transform ---------------
  process.env.FAKE_UVX_RC = "0";
  before = uvxCalls().length;
  let system = await systemFor(astra, "s1");
  if (system[0] !== "base prompt") fail("primer: existing system prompt was disturbed");
  assertIncludes("primer", system.join("\n"), "ASTRA project — spec at ./astra.yaml");
  assertIncludes("primer", system.join("\n"), "Activate the astra skill");
  assertIncludes("primer uvx args", uvxCalls().at(-1), "info --json");
  if (uvxCalls().length !== before + 1) fail("primer: expected exactly one uvx run for the session");

  // Same session, next request: re-emitted from cache, no second run. The
  // agent-generation path calls the transform without a sessionID: served too.
  system = await systemFor(astra, "s1");
  assertIncludes("primer/cached", system.join("\n"), "ASTRA project — spec at ./astra.yaml");
  system = await systemFor(astra, undefined);
  assertIncludes("primer/no-session", system.join("\n"), "ASTRA project");
  if (uvxCalls().length !== before + 1) fail("primer/cached: SessionStart ran again within the session");

  // A new session runs it again — once: session.created starts the run and
  // the first transform shares it.
  await sessionCreated(astra, "s2");
  system = await systemFor(astra, "s2");
  assertIncludes("primer/new-session", system.join("\n"), "ASTRA project");
  if (uvxCalls().length !== before + 2) fail("primer/new-session: expected exactly one more run");
  delete process.env.FAKE_UVX_RC;

  // Outside an ASTRA project the astra primer stays silent.
  const astraElsewhere = await load("astra", elsewhere);
  system = await systemFor(astraElsewhere, "s3");
  if (system.length !== 1) fail(`primer/elsewhere: expected no injection, got\n${system.slice(1).join("\n")}`);

  // --- lightcone bundles astra: both primers, dependency first -------------
  process.env.FAKE_UVX_RC = "0";
  const lightcone = await load("lightcone", project);
  system = await systemFor(lightcone, "l1");
  const joined = system.slice(1).join("\n");
  assertIncludes("lightcone/astra-primer", joined, "ASTRA project — spec at ./astra.yaml");
  assertIncludes("lightcone/engine-primer", joined, "Lightcone project");
  assertIncludes("lightcone/engine-primer", joined, "is not installed"); // no `lc` on the hermetic PATH
  assertIncludes("lightcone/mode", joined, "Ask the user"); // no harness variable → ask
  if (joined.indexOf("ASTRA project") > joined.indexOf("Lightcone project"))
    fail("lightcone: dependency (astra) primer must precede the plugin's own");
  out = await afterTool(lightcone, "write", { filePath: spec });
  assertIncludes("lightcone/validate", out, "ASTRA validation passed");
  delete process.env.FAKE_UVX_RC;

  console.log("✓ OpenCode adapter: tool matching, result/system routing, and the per-session primer all behave.");
} finally {
  cleanup();
}
