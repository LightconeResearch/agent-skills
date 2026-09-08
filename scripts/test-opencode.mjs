#!/usr/bin/env node
// Hermetic tests for the generated OpenCode plugin modules
// (plugins/<name>/opencode/<name>.js). No OpenCode binary, no network, no real
// astra: the modules are imported into this process and their hooks are
// called the way OpenCode calls them, with a fake `uvx` on PATH (same fake as
// test-hooks.mjs) so the embedded scripts' behaviour is observable.
//
// What this proves, on top of test-hooks.mjs (the scripts) and validate.mjs
// (the module text is what the generator produces):
//   - the wiring: PostToolUse groups fire from "tool.execute.after" for the
//     tools the hooks.json matcher names — including OpenCode's `patch`, which
//     the matcher knows as `apply_patch` — and stay silent for the rest;
//   - the routing: a script's additionalContext lands in output.output (tool
//     result) or output.system (system prompt), and non-envelope noise does not;
//   - the primer contract: one SessionStart run per session, re-emitted on
//     every request, pre-warmable from the session.created event;
//   - a bundling plugin (lightcone) runs its dependency's hooks too, in order.

import { existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = join(fileURLToPath(import.meta.url), "..", "..");
const scratch = mkdtempSync(join(tmpdir(), "opencode-plugin-"));
const project = join(scratch, "project");
const elsewhere = join(scratch, "elsewhere");
const bin = join(scratch, "bin");
const uvxLog = join(scratch, "uvx-invocations.log");

mkdirSync(project, { recursive: true });
mkdirSync(elsewhere, { recursive: true });
mkdirSync(bin);
writeFileSync(join(project, "astra.yaml"), "id: test\n");
writeFileSync(
  join(bin, "uvx"),
  `#!/bin/sh
echo "$*" >> "${uvxLog}"
printf '%s\\n' "\\"fake report: $*\\""
exit "\${FAKE_UVX_RC:-1}"
`,
  { mode: 0o755 },
);

// The embedded scripts inherit this process's environment: a hermetic PATH
// (fake uvx, no `lc`), and none of the harness variables the lightcone hook
// reads to pick its mode.
process.env.PATH = `${bin}:/usr/bin:/bin`;
delete process.env.CLAUDE_CODE_ENTRYPOINT;
delete process.env.CI;

const uvxCalls = () => (existsSync(uvxLog) ? readFileSync(uvxLog, "utf8").trim().split("\n").filter(Boolean) : []);
const fail = (msg) => { throw new Error(msg); };
const assertIncludes = (label, haystack, needle) => {
  if (!haystack.includes(needle)) fail(`${label}: missing ${JSON.stringify(needle)}\n${haystack}`);
};

async function load(name, directory) {
  const mod = await import(pathToFileURL(join(ROOT, `plugins/${name}/opencode/${name}.js`)).href);
  if (typeof mod.default !== "function") fail(`${name}: module has no default-exported plugin function`);
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

  // OpenCode's `patch` tool is the matcher's `apply_patch`.
  out = await afterTool(astra, "patch", { patchText: "*** Update File: astra.yaml" });
  assertIncludes("patch/alias", out, "ASTRA validation FAILED");

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

  // Same session, next request: re-emitted from cache, no second run.
  system = await systemFor(astra, "s1");
  assertIncludes("primer/cached", system.join("\n"), "ASTRA project — spec at ./astra.yaml");
  if (uvxCalls().length !== before + 1) fail("primer/cached: SessionStart ran again for the same session");

  // A new session runs it again — once — and session.created pre-warms it.
  await astra.event({ event: { type: "session.created", properties: { info: { id: "s2" } } } });
  system = await systemFor(astra, "s2");
  assertIncludes("primer/prewarmed", system.join("\n"), "ASTRA project");
  if (uvxCalls().length !== before + 2) fail("primer/prewarmed: expected one run for s2 (pre-warm + transform shared it)");
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

  console.log("✓ OpenCode plugin modules: tool matching, result/system routing, and the per-session primer all behave.");
} finally {
  rmSync(scratch, { recursive: true, force: true });
}
