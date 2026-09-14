// Shared build logic for the multi-target skills repo.
//
// One source of truth: skills.config.json + the canonical skills/ directory.
// buildArtifacts() returns the exact generated files/copies each target needs, so the
// generator (build.mjs) and the drift check (validate.mjs) agree by construction.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

export const NAME_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** Return every regular file below a repo-relative directory, deterministically. */
function filesUnder(relDir) {
  const out = [];
  const visit = (rel) => {
    for (const name of readdirSync(join(ROOT, rel)).sort()) {
      const child = `${rel}/${name}`;
      const st = statSync(join(ROOT, child));
      if (st.isDirectory()) visit(child);
      else if (st.isFile()) out.push(child);
    }
  };
  visit(relDir);
  return out;
}

// --- Tool pins -------------------------------------------------------------
// Each plugin may declare `tools: { <name>: <version> }` — the CLI tools its
// skills and hooks invoke via `uvx <name>@<version>`. Canonical skills/ and
// hooks/ never carry a concrete version: they write the literal `@x.y.z`
// placeholder, and the build substitutes each bundling plugin's EFFECTIVE
// pins — merged over its dependency closure, own entries win — when the
// plugins/ tree is generated. So different plugins can ship the same skill
// pinned to different tool versions, and nothing in the canonical sources
// ever looks like a number a contributor should wonder about updating.

const PIN_SCAN_DIRS = ["skills", "hooks"];
export const PIN_SCAN_EXTS = /\.(md|sh|json|ya?ml)$/;
export const PIN_PLACEHOLDER = "x.y.z";

/** The frontmatter keys the Agent Skills spec defines — the portable set.
 *  Claude Code accepts many more, but the `npx skills` CLI and the Skills API
 *  packaging path reject an unknown key outright, so canonical skills stay
 *  inside this set. */
export const SPEC_FIELDS = new Set([
  "name",
  "description",
  "license",
  "compatibility",
  "metadata",
  "allowed-tools",
]);
// A tool invocation whose placeholder survived pin substitution (the tool name
// sits right before the separator — prose mentions of "@x.y.z" don't match).
export const UNPINNED_RE = /[A-Za-z0-9_-]+(?:@|==)x\.y\.z/;
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function declaredTools(plugin) {
  return Object.fromEntries(
    Object.entries(plugin.tools || {}).filter(([k]) => !k.startsWith("$")),
  );
}

/** Effective tool pins for a plugin: merged over its closure, own entries win. */
export function pluginTools(pluginName, byName) {
  const out = {};
  for (const p of closurePlugins(pluginName, byName)) Object.assign(out, declaredTools(p));
  return out;
}

/** Union of every tool name declared by any plugin. */
export function declaredToolNames(config) {
  return [...new Set(config.plugins.flatMap((p) => Object.keys(declaredTools(p))))];
}

/** Replace each tool's `@x.y.z` / `==x.y.z` placeholder with its pinned version. */
export function applyPins(text, pins) {
  let out = text;
  for (const [name, pin] of Object.entries(pins)) {
    out = out.replace(
      new RegExp(`(${escapeRe(name)}(?:@|==))${escapeRe(PIN_PLACEHOLDER)}`, "g"),
      `$1${pin}`,
    );
  }
  return out;
}

/** Every canonical file subject to pin policy checks. */
export function pinScanFiles() {
  return PIN_SCAN_DIRS.flatMap((dir) => filesUnder(dir)).filter((rel) => PIN_SCAN_EXTS.test(rel));
}

function pluginDisplayName(name) {
  return name
    .split("-")
    .map((part) => (part === "astra" ? "ASTRA" : part[0].toUpperCase() + part.slice(1)))
    .join(" ");
}

/** Minimal YAML-frontmatter reader — handles inline, quoted, and folded/literal
 *  (`>` / `|`) scalars, which is all SKILL.md frontmatter uses. */
export function parseFrontmatter(text) {
  if (!text.startsWith("---")) throw new Error("missing frontmatter");
  const end = text.indexOf("\n---", 3);
  if (end === -1) throw new Error("unterminated frontmatter");
  const block = text.slice(text.indexOf("\n") + 1, end).split("\n");
  const out = {};
  for (let i = 0; i < block.length; i++) {
    const line = block[i];
    const m = /^([A-Za-z0-9_-]+):(.*)$/.exec(line);
    if (!m) continue; // continuation line, already consumed
    const key = m[1];
    let rest = m[2].trim();
    if (rest === ">" || rest === "|" || rest === "") {
      const parts = [];
      while (i + 1 < block.length && (block[i + 1] === "" || /^\s/.test(block[i + 1]))) {
        parts.push(block[++i].trim());
      }
      out[key] = parts.join(" ").replace(/\s+/g, " ").trim();
    } else {
      out[key] = rest.replace(/^["']|["']$/g, "");
    }
  }
  return out;
}

/** Read skills.config.json + every skill's frontmatter. */
export function loadModel() {
  const config = JSON.parse(readFileSync(join(ROOT, "skills.config.json"), "utf8"));
  const skillsDir = join(ROOT, "skills");
  const skills = {};
  for (const name of readdirSync(skillsDir)) {
    const skillMd = join(skillsDir, name, "SKILL.md");
    let st;
    try { st = statSync(skillMd); } catch { continue; }
    if (!st.isFile()) continue;
    const fm = parseFrontmatter(readFileSync(skillMd, "utf8"));
    // `frontmatter` keeps every key as authored, so the validator can hold
    // the file to the spec's field set rather than only the fields we read.
    skills[name] = { dir: name, name: fm.name, description: fm.description || "", frontmatter: fm };
  }
  return { config, skills };
}

/** Transitive plugin closure: this plugin plus every plugin it depends on
 *  (deduped, dependency-first). Every generated plugin dir is self-contained —
 *  it bundles this whole closure — so the two harnesses install identically and
 *  neither relies on native dependency resolution. */
export function closurePlugins(pluginName, byName, seen = new Set()) {
  if (seen.has(pluginName)) return [];
  seen.add(pluginName);
  const p = byName[pluginName];
  const out = [];
  for (const dep of p.dependencies || []) out.push(...closurePlugins(dep, byName, seen));
  out.push(p);
  return out;
}

/** Transitive skill closure (own skills + all dependency skills). */
export function closure(pluginName, byName) {
  const out = [];
  for (const p of closurePlugins(pluginName, byName)) out.push(...(p.skills || []));
  return [...new Set(out)];
}

/** Transitive agent-file closure (repo-relative paths). */
export function closureAgents(pluginName, byName) {
  const out = [];
  for (const p of closurePlugins(pluginName, byName)) out.push(...(p.agents || []));
  return [...new Set(out)];
}

/** Transitive hooks closure — the distinct hooks.json paths across the closure,
 *  in dependency-first order (a dependency's hooks precede the plugin's own).
 *  A plugin owns at most one hooks.json, but its closure can bundle several
 *  (a bundling plugin inherits its dependencies'), so the list is merged at build time by
 *  mergeHooks() — hook groups concatenate per event, and the shared scripts tree
 *  flattens under one `hooks/scripts/` dir (canonical script basenames are unique
 *  across plugins, which mergeHooks asserts). */
export function closureHooks(pluginName, byName) {
  return [...new Set(closurePlugins(pluginName, byName).flatMap((p) => (p.hooks ? [p.hooks] : [])))];
}

/** Merge several canonical hooks.json files into one manifest string. Each source
 *  is `{ hooks: { <Event>: [group, ...] } }`; the merge concatenates groups per
 *  event in source order, so a dependency's hooks fire alongside the plugin's own.
 *  Emitted through jsonl() for byte-stable, drift-checkable output. */
export function mergeHooks(hookPaths) {
  return jsonl({ hooks: mergeHooksObject(hookPaths) });
}

/** The merged `{ <Event>: [group, ...] }` map behind mergeHooks(), for targets
 *  that consume the hook wiring as data rather than as a hooks.json file. */
export function mergeHooksObject(hookPaths) {
  const merged = {};
  for (const rel of hookPaths) {
    const { hooks } = JSON.parse(readFileSync(join(ROOT, rel), "utf8"));
    for (const [event, groups] of Object.entries(hooks || {})) (merged[event] ||= []).push(...groups);
  }
  return merged;
}

// --- npm package targets: OpenCode and Pi ------------------------------------
// OpenCode and Pi both read the Agent Skills format directly, so their skills
// need no manifest — but neither has a hooks.json. OpenCode plugins are JS
// modules exporting `async (input) => hooks`, installed from npm through the
// `plugin` array in opencode.json; Pi extensions are JS modules default-
// exporting `function (pi) { pi.on(...) }`, installed from npm through the
// `pi` field of package.json. So every plugin dir doubles as ONE npm package
// (`<npmScope>/<name>-plugin`): a generated package.json, an OpenCode module
// (`opencode/index.js`, the package main) and a Pi extension (`pi/index.js`,
// listed under `pi.extensions`), with the packaged `skills/` tree listed under
// `pi.skills`. Both modules embed the closure's hook SCRIPTS verbatim (tool pins
// substituted like every other packaged copy) and map the hooks.json events
// onto the harness API:
//
//   PostToolUse (matcher, scripts)
//     OpenCode "tool.execute.after": additionalContext appended to the tool
//       result the model reads.
//     Pi "tool_result": appended as a text block to the result content.
//   SessionStart (scripts)
//     OpenCode "experimental.chat.system.transform": the primer runs once per
//       session (pre-warmed on the session.created event) and is appended to
//       the system prompt on every request — OpenCode rebuilds the prompt each
//       time, so a one-shot injection would be forgotten after the first turn.
//     Pi "before_agent_start": same primer, appended to event.systemPrompt on
//       every turn — Pi resets to the base prompt whenever a handler returns
//       none. Pi re-invokes the extension factory per session, so module state
//       is per session by construction.
//
// Scripts are embedded rather than referenced because an npm-installed module
// has no plugin root to resolve (${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT} never
// appears here), and the modules have zero dependencies so the package installs
// with scripts ignored, as OpenCode does. Plain ESM JavaScript: OpenCode and Pi
// (via jiti) load it as-is, and `node` imports it for the hermetic tests.
export const HOOK_EVENTS = ["PostToolUse", "SessionStart"];
const SCRIPT_REF_RE = /hooks\/scripts\/([\w.-]+\.sh)/;

/** npm package name for a plugin: `<npmScope>/<name>-plugin`. */
export function npmPackageName(marketplace, pluginName) {
  if (!marketplace.npmScope) throw new Error('skills.config.json: marketplace.npmScope is required (e.g. "@lightcone-research")');
  return `${marketplace.npmScope}/${pluginName}-plugin`;
}

/** Hook wiring for the module templates: per event, [{ matcher, scripts: [{ name, timeout }] }]. */
function hookGroups(hooks, event) {
  return (hooks[event] || []).map((group) => ({
    matcher: group.matcher || "",
    scripts: (group.hooks || [])
      .filter((h) => h.type === "command")
      .map((h) => {
        const m = SCRIPT_REF_RE.exec(h.command || "");
        if (!m) throw new Error(`${event} hook command does not reference hooks/scripts/<name>.sh: ${h.command}`);
        return { name: m[1], timeout: h.timeout || 60 };
      }),
  }));
}

/** The data half shared by both modules: embedded scripts + wiring constants. */
function hookDataJs({ name, hooks, scripts }) {
  const postToolUse = hookGroups(hooks, "PostToolUse");
  const sessionStart = hookGroups(hooks, "SessionStart");
  for (const g of [...postToolUse, ...sessionStart])
    for (const s of g.scripts)
      if (!(s.name in scripts)) throw new Error(`hooks.json references ${s.name}, which no closure hooks/ tree ships`);
  const unknown = Object.keys(hooks).filter((e) => !HOOK_EVENTS.includes(e));
  if (unknown.length) throw new Error(`no OpenCode/Pi mapping for hook event(s): ${unknown.join(", ")}`);
  const scriptEntries = Object.keys(scripts)
    .sort()
    .map((n) => `  ${JSON.stringify(n)}: ${JSON.stringify(scripts[n])},`)
    .join("\n");
  const js = `const PLUGIN = ${JSON.stringify(name)};

// The hook scripts, byte-identical to plugins/${name}/hooks/scripts/*.sh.
const SCRIPTS = {
${scriptEntries}
};

// Wiring lifted from hooks.json. Matchers are the Claude/Codex tool-name
// regexes; harness tool ids are lowercase, so matching is case-insensitive.
const POST_TOOL_USE = ${JSON.stringify(postToolUse, null, 2)};
const SESSION_START = ${JSON.stringify(sessionStart, null, 2)};
`;
  return { js, postToolUse, sessionStart };
}

// The runtime half shared by both modules. Written without template literals
// so it can sit inside this file's template literal unescaped.
const HOOK_RUNTIME_JS = `import { spawn } from "node:child_process";

function matches(matcher, tool) {
  if (!matcher) return true;
  return new RegExp("^(?:" + matcher + ")$", "i").test(tool || "");
}

// Run one embedded script with the payload on stdin (what the harness would
// have piped), in the project directory, killed after its hooks.json timeout.
// Resolves to whatever it printed — never rejects: a hook must not break the
// tool call or the request it decorates. No bash on PATH → silent.
function runScript(name, payload, cwd, timeoutSeconds) {
  return new Promise((resolve) => {
    let out = "";
    let child;
    try {
      child = spawn("bash", ["-c", SCRIPTS[name]], { cwd, env: process.env, stdio: ["pipe", "pipe", "ignore"] });
    } catch {
      return resolve("");
    }
    const timer = setTimeout(() => child.kill(), timeoutSeconds * 1000);
    child.stdout.on("data", (chunk) => (out += chunk));
    child.on("error", () => { clearTimeout(timer); resolve(out); });
    child.on("close", () => { clearTimeout(timer); resolve(out); });
    child.stdin.on("error", () => {});
    child.stdin.end(payload);
  });
}

// Each script prints hook envelopes, one JSON object per line; collect their
// additionalContext and drop anything that is not an envelope.
function contextOf(stdout) {
  const parts = [];
  for (const line of stdout.split("\\n")) {
    if (!line.trim()) continue;
    try {
      const ctx = JSON.parse(line)?.hookSpecificOutput?.additionalContext;
      if (typeof ctx === "string" && ctx.trim()) parts.push(ctx.trim());
    } catch {}
  }
  return parts.join("\\n\\n");
}

async function runGroups(groups, tool, payload, cwd) {
  const parts = [];
  for (const group of groups) {
    if (!matches(group.matcher, tool)) continue;
    for (const script of group.scripts) {
      const ctx = contextOf(await runScript(script.name, payload, cwd, script.timeout));
      if (ctx) parts.push(ctx);
    }
  }
  return parts.join("\\n\\n");
}

// The payload mirrors the Claude Code hook JSON the scripts were written for.
function hookPayload(event, cwd, extra) {
  return JSON.stringify(Object.assign({ hook_event_name: event, cwd: cwd, plugin: PLUGIN }, extra));
}
`;

function generatedHeader(kind, { name, version, pkg }) {
  return `// GENERATED by \`npm run build\` from hooks/*/hooks.json — do not edit; change the
// source and rebuild (see AGENTS.md). Drift is a CI failure.
//
// ${kind} for the "${name}" plugin, version ${version} — installed from npm as
// ${pkg}. Runs the very same hook scripts the Claude Code and Codex packages of
// this plugin run (embedded below, tool versions already pinned) and routes their
// output the harness's way. Needs \`bash\` on PATH; the scripts need \`uvx\` and say
// so themselves when it is missing. Nothing else.
`;
}

/** Render the OpenCode plugin module (`opencode/index.js`, the package main). */
export function renderOpencodePlugin({ name, version, pkg, hooks, scripts }) {
  const data = hookDataJs({ name, hooks, scripts });
  return `${generatedHeader("OpenCode plugin", { name, version, pkg })}//
//   PostToolUse  → "tool.execute.after": additionalContext is appended to the
//                  tool result the model reads.
//   SessionStart → "experimental.chat.system.transform": the primer runs once
//                  per session (pre-warmed on the session.created event) and is
//                  appended to the system prompt on every request.

${HOOK_RUNTIME_JS}
${data.js}
/** @type {import("@opencode-ai/plugin").Plugin} */
export default async function ({ directory }) {
  const cwd = directory || process.cwd();
  const primers = new Map(); // sessionID → Promise<string>; one SessionStart per session
  const primer = (sessionID) => {
    const key = sessionID ?? "";
    if (!primers.has(key)) {
      const payload = hookPayload("SessionStart", cwd, { session_id: key, source: "startup" });
      primers.set(key, runGroups(SESSION_START, "", payload, cwd));
    }
    return primers.get(key);
  };

  const hooks = {};
${data.sessionStart.length ? `  hooks.event = async ({ event }) => {
    if (event?.type === "session.created") void primer(event.properties?.info?.id);
  };
  hooks["experimental.chat.system.transform"] = async (input, output) => {
    const ctx = await primer(input?.sessionID);
    if (ctx) output.system.push(ctx);
  };
` : ""}${data.postToolUse.length ? `  hooks["tool.execute.after"] = async (input, output) => {
    const payload = hookPayload("PostToolUse", cwd, {
      session_id: input.sessionID,
      tool_name: input.tool,
      tool_input: input.args,
      tool_response: { title: output?.title },
    });
    const ctx = await runGroups(POST_TOOL_USE, input.tool, payload, cwd);
    if (ctx) output.output = (output.output ?? "") + "\\n\\n" + ctx;
  };
` : ""}  return hooks;
}
`;
}

/** Render the Pi extension (`pi/index.js`, listed under package.json `pi.extensions`). */
export function renderPiExtension({ name, version, pkg, hooks, scripts }) {
  const data = hookDataJs({ name, hooks, scripts });
  return `${generatedHeader("Pi extension", { name, version, pkg })}//
//   PostToolUse  → "tool_result": additionalContext is appended to the result
//                  content as a text block.
//   SessionStart → "before_agent_start": the primer runs once per session (from
//                  session_start) and is appended to the system prompt on every
//                  turn — Pi resets to the base prompt when a handler returns none.

${HOOK_RUNTIME_JS}
${data.js}
/** @param {import("@earendil-works/pi-coding-agent").ExtensionAPI} pi */
export default function (pi) {
  let primer; // Promise<string>; Pi re-invokes this factory per session
  const prime = (cwd) => (primer ??= runGroups(SESSION_START, "", hookPayload("SessionStart", cwd, { source: "startup" }), cwd));
${data.sessionStart.length ? `
  pi.on("session_start", async (_event, ctx) => {
    primer = undefined;
    void prime(ctx.cwd);
  });

  pi.on("before_agent_start", async (event, ctx) => {
    const text = await prime(ctx.cwd);
    if (text) return { systemPrompt: (event.systemPrompt ?? "") + "\\n\\n" + text };
  });
` : ""}${data.postToolUse.length ? `
  pi.on("tool_result", async (event, ctx) => {
    const payload = hookPayload("PostToolUse", ctx.cwd, {
      tool_name: event.toolName,
      tool_input: event.input,
      tool_response: { isError: event.isError },
    });
    const text = await runGroups(POST_TOOL_USE, event.toolName, payload, ctx.cwd);
    if (text) return { content: [...(event.content ?? []), { type: "text", text }] };
  });
` : ""}}
`;
}

/** The generated package.json for a plugin dir (never dependencies, never scripts). */
export function renderPackageJson({ p, mk, pkg, hasHooks, skillNames }) {
  const manifest = {
    name: pkg,
    version: p.version,
    description: p.description,
    type: "module",
  };
  if (hasHooks) {
    manifest.main = "./opencode/index.js";
    manifest.exports = {
      ".": "./opencode/index.js",
      "./server": "./opencode/index.js",
      "./pi": "./pi/index.js",
      "./package.json": "./package.json",
    };
  }
  Object.assign(manifest, {
    files: ["opencode/", "pi/", "skills/", "README.md", "LICENSE"],
    pi: { extensions: ["./pi"], skills: ["./skills"] },
    keywords: ["opencode", "opencode-plugin", "pi-package", "agent-skills", ...skillNames],
    license: "BSD-3-Clause",
    author: mk.owner,
    homepage: `https://github.com/${mk.repo}`,
    repository: { type: "git", url: `git+https://github.com/${mk.repo}.git`, directory: `plugins/${p.name}` },
    publishConfig: { access: "public" },
    engines: { node: ">=20" },
  });
  return jsonl(manifest);
}

/** The npm-page README for a plugin package. */
export function renderPackageReadme({ p, mk, pkg, hasHooks, skillNames }) {
  const repo = `https://github.com/${mk.repo}`;
  const docs = `https://${mk.repo.split("/")[0].toLowerCase()}.github.io/${mk.repo.split("/")[1]}/`;
  return `# ${pkg}

${p.description}

Generated from [${mk.repo}](${repo}) — the same skills and hooks that ship as the
\`${p.name}\` plugin for Claude Code and Codex, packaged for harnesses that install
from npm. Version ${p.version} of the plugin.

## OpenCode

Hooks: add the package to \`opencode.json\` (\`~/.config/opencode/opencode.json\` for
every project, or a project's own):

\`\`\`json
{ "$schema": "https://opencode.ai/config.json", "plugin": ["${pkg}@${p.version}"] }
\`\`\`

Skills: \`npx skills add ${repo}/tree/main/plugins/${p.name} -a opencode -g\`

## Pi

\`\`\`bash
pi install npm:${pkg}@${p.version}
\`\`\`

Installs the skills and the hooks together; invoke a skill as \`/skill:<name>\`.

## Contents

- Skills: ${skillNames.map((s) => `\`${s}\``).join(", ")}
${hasHooks ? "- Hooks: the plugin's SessionStart primer and PostToolUse validation, as an OpenCode plugin module (`opencode/index.js`) and a Pi extension (`pi/index.js`). Needs `bash` on PATH; the scripts need `uvx` and say so when it is missing.\n" : ""}
Documentation: ${docs}opencode/ and ${docs}pi/ · License: BSD-3-Clause
`;
}

/** Produce every generated artifact. Returns:
 *   - files: { relPath: jsonString }  (deterministic, newline-terminated)
 *   - copies: [{ source: canonicalRelPath, dest: generatedRelPath, kind }]
 *   - dirs: [relPath]  (directories that must exist even when otherwise empty)
 */
export function buildArtifacts(model) {
  const { config, skills } = model;
  const mk = config.marketplace;
  const byName = Object.fromEntries(config.plugins.map((p) => [p.name, p]));
  const files = {};
  const copies = [];
  const dirs = [];

  // --- Both marketplaces point every plugin at its self-contained dir -------
  // One mechanism, both harnesses: each plugins/<name>/ (generated below)
  // bundles the plugin's full transitive closure — skills, hooks, agents — so
  // installing it never triggers native dependency resolution. The two
  // marketplace manifests differ only in surface syntax; the source dir is the
  // same. `dependencies` in skills.config.json defines the build-time closure
  // and is deliberately NOT emitted to either harness.
  files[".claude-plugin/marketplace.json"] = jsonl({
    name: mk.name,
    owner: mk.owner,
    metadata: { description: mk.description },
    plugins: config.plugins.map((p) => ({
      name: p.name,
      description: p.description,
      version: p.version,
      source: `./plugins/${p.name}`,
    })),
  });

  files[".agents/plugins/marketplace.json"] = jsonl({
    name: mk.name,
    interface: { displayName: mk.displayName },
    plugins: config.plugins.map((p) => ({
      name: p.name,
      description: p.description,
      source: { source: "local", path: `./plugins/${p.name}` },
      policy: { installation: "AVAILABLE", authentication: "ON_INSTALL" },
      category: "Development",
    })),
  });

  // --- Self-contained per-plugin dirs (plugins/<name>/) --------------------
  // Each dir carries the whole closure and ships both harnesses' plugin
  // manifests. Skills/agents/hooks are generated copies of the canonical trees;
  // this is necessary because plugin installers archive the plugin directory
  // without following symlinks that point outside it. Claude and Codex both
  // auto-discover skills/, agents/, and hooks/hooks.json under the plugin root.
  //
  // Hooks: Codex reads the same hooks.json protocol (SessionStart/PostToolUse
  // with hookSpecificOutput.additionalContext); commands locate the plugin root
  // as ${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}, so one hooks.json + one scripts tree
  // serves both. CLAUDE_PLUGIN_ROOT is the one plugin-root variable both
  // harnesses define: Claude Code sets only this name; Codex sets its native
  // PLUGIN_ROOT and also CLAUDE_PLUGIN_ROOT as a compatibility alias (see the
  // OpenAI hooks docs). The $PLUGIN_ROOT fallback covers Codex versions that
  // predate the alias. The fallback is inline because the root is what locates
  // the script — it cannot be hoisted into a script that hasn't been found yet.
  // Neither plugin manifest declares dependencies — the closure is already
  // bundled.
  for (const p of config.plugins) {
    const closureSkills = closure(p.name, byName);
    const closAgents = closureAgents(p.name, byName);
    const closHooks = closureHooks(p.name, byName); // repo-relative hooks.json paths
    // The bundling plugin's effective tool pins: stamped into its packaged
    // copies at build time, so a plugin can bundle a dependency's skills and
    // hooks while pinning the tools they invoke to its own chosen versions.
    const pins = pluginTools(p.name, byName);
    const pkg = npmPackageName(mk, p.name);

    // Shared metadata for both harnesses' manifests.
    const base = {
      name: p.name,
      version: p.version,
      description: p.description,
      author: mk.owner,
      homepage: `https://github.com/${mk.repo}`,
      repository: `https://github.com/${mk.repo}`,
      license: "BSD-3-Clause",
    };

    // Claude Code: components auto-discovered from skills/ agents/ hooks/ — the
    // manifest just carries metadata. No dependencies (closure is bundled).
    files[`plugins/${p.name}/.claude-plugin/plugin.json`] = jsonl(base);

    // Codex: declare the supported skill root and required interface metadata.
    // Agents and hooks remain packaged for harness auto-discovery, but are not
    // declared because the current Codex manifest schema rejects those fields.
    const displayName = pluginDisplayName(p.name);
    const codexManifest = {
      ...base,
      skills: "./skills/",
      interface: {
        displayName,
        shortDescription: `Use ${displayName} in Codex.`,
        longDescription: p.description,
        developerName: mk.owner.name,
        category: "Development",
        capabilities: [],
        defaultPrompt: [`Help me use ${displayName}.`],
      },
    };
    files[`plugins/${p.name}/.codex-plugin/plugin.json`] = jsonl(codexManifest);

    // skills/ — materialize the full closure from canonical skills/. This keeps
    // generated plugins self-contained while skills/ remains the authoring source.
    dirs.push(`plugins/${p.name}/skills`);
    for (const s of closureSkills) {
      const sourceRoot = `skills/${s}`;
      for (const source of filesUnder(sourceRoot)) copies.push({
        kind: "skill",
        pins,
        source,
        dest: `plugins/${p.name}/skills/${s}/${source.slice(sourceRoot.length + 1)}`,
      });
    }

    // agents/ — materialize the full closure file-by-file.
    if (closAgents.length) dirs.push(`plugins/${p.name}/agents`);
    for (const a of closAgents) {
      const file = a.replace(/^agents\//, "");
      copies.push({
        kind: "agent",
        pins,
        source: a,
        dest: `plugins/${p.name}/agents/${file}`,
      });
    }

    // hooks/ — flatten every canonical hooks tree in the closure under one
    // plugins/<name>/hooks/ dir. Scripts (and any non-manifest files) copy
    // byte-for-byte from hooks/<plugin>/scripts/* into hooks/scripts/*, which is
    // where each hooks.json command resolves them (${CLAUDE_PLUGIN_ROOT}/hooks/
    // scripts/…). The manifest itself is a single byte-copy when the closure has
    // one source, or a generated merge when it inherits more (a plugin bundling
    // astra); the merged file is drift-checked like any other generated output.
    if (closHooks.length) {
      dirs.push(`plugins/${p.name}/hooks`);
      const seenDest = new Map();
      const scriptSources = {}; // basename → canonical path, for the OpenCode module
      for (const hp of closHooks) {
        const srcDir = dirname(hp); // e.g. "hooks/astra"
        for (const source of filesUnder(srcDir)) {
          const rel = source.slice(srcDir.length + 1); // "hooks.json" | "scripts/x.sh"
          if (rel === "hooks.json") continue; // manifest handled below
          const dest = `plugins/${p.name}/hooks/${rel}`;
          const prior = seenDest.get(dest);
          if (prior && prior !== source)
            throw new Error(`plugin "${p.name}": hook file collision at ${dest} (${prior} vs ${source})`);
          seenDest.set(dest, source);
          copies.push({ kind: "hook", pins, source, dest });
          if (rel.startsWith("scripts/") && rel.endsWith(".sh")) scriptSources[rel.slice("scripts/".length)] = source;
        }
      }
      const manifestDest = `plugins/${p.name}/hooks/hooks.json`;
      if (closHooks.length === 1) copies.push({ kind: "hook", pins, source: closHooks[0], dest: manifestDest });
      else files[manifestDest] = mergeHooks(closHooks);

      // The npm-package modules: opencode/index.js and pi/index.js — the same
      // hooks, the scripts embedded with this plugin's pins applied. Generated
      // text, so they go through `files` and are drift-checked as a whole.
      const scripts = {};
      for (const [base, source] of Object.entries(scriptSources)) {
        const content = applyPins(readFileSync(join(ROOT, source), "utf8"), pins);
        const leak = content.match(UNPINNED_RE);
        if (leak) throw new Error(`plugins/${p.name}: "${leak[0]}" in ${source} left unpinned — declare the tool in a plugin's "tools" map`);
        scripts[base] = content;
      }
      const moduleInput = { name: p.name, version: p.version, pkg, hooks: mergeHooksObject(closHooks), scripts };
      files[`plugins/${p.name}/opencode/index.js`] = renderOpencodePlugin(moduleInput);
      files[`plugins/${p.name}/pi/index.js`] = renderPiExtension(moduleInput);
    }

    // The npm package manifest, README and LICENSE: plugins/<name>/ IS the
    // package (`files` in package.json keeps the Claude/Codex manifests and the
    // hooks/ tree out of the tarball). Never dependencies, never a lockfile —
    // Claude Code would run an install for a plugin root that carries both.
    const pkgInput = { p, mk, pkg, hasHooks: closHooks.length > 0, skillNames: closureSkills };
    files[`plugins/${p.name}/package.json`] = renderPackageJson(pkgInput);
    files[`plugins/${p.name}/README.md`] = renderPackageReadme(pkgInput);
    copies.push({ kind: "license", pins: {}, source: "LICENSE", dest: `plugins/${p.name}/LICENSE` });
  }

  // --- Registry (manifest.json) --------------------------------------------
  const skillToPlugins = {};
  for (const p of config.plugins)
    for (const s of closure(p.name, byName))
      (skillToPlugins[s] ||= []).push(p.name);
  files["manifest.json"] = jsonl({
    name: mk.name,
    description: mk.description,
    repository: `https://github.com/${mk.repo}`,
    generated: "Run `npm run build` to regenerate. Do not edit by hand.",
    skills: Object.keys(skills)
      .sort()
      .map((s) => {
        const inPlugins = (skillToPlugins[s] || []).sort();
        return {
          name: skills[s].name,
          // Point at a packaged copy when one exists: canonical skills/ carries
          // the @x.y.z tool-pin placeholder, packaged copies carry real pins.
          path: inPlugins.length ? `plugins/${inPlugins[0]}/skills/${s}` : `skills/${s}`,
          description: skills[s].description,
          plugins: inPlugins,
        };
      }),
    plugins: config.plugins.map((p) => ({
      name: p.name,
      version: p.version,
      description: p.description,
      skills: closure(p.name, byName).sort(),
      dependencies: p.dependencies || [],
      // Documented-only prerequisites: not bundled, the user installs them.
      requires: p.requires || [],
      // Reflect the bundled closure — what installing this one plugin gives you.
      hasHooks: closureHooks(p.name, byName).length > 0,
      hasAgents: closureAgents(p.name, byName).length > 0,
      // The npm package OpenCode and Pi install (plugins/<name>/ is the package).
      npmPackage: npmPackageName(mk, p.name),
    })),
  });

  return { files, copies, dirs };
}

function jsonl(obj) {
  return JSON.stringify(obj, null, 2) + "\n";
}
