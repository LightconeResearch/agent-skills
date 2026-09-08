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

// --- OpenCode -----------------------------------------------------------------
// OpenCode reads the Agent Skills format directly, so its skills need no
// manifest — the `skills` CLI installs plugins/<name>/skills/ as-is. Hooks are
// the gap: OpenCode has no hooks.json; its plugins are JS modules exporting
// `async (input) => hooks`. renderOpencodePlugin() closes it by generating one
// such module per plugin that ships hooks. The module embeds the plugin's hook
// SCRIPTS verbatim (tool pins already substituted, like every other packaged
// copy) and maps the hooks.json events onto OpenCode's hook API:
//
//   PostToolUse (matcher, scripts)  → "tool.execute.after": the script's
//       additionalContext is appended to the tool result the model reads.
//   SessionStart (scripts)          → "experimental.chat.system.transform":
//       the primer runs once per session (pre-warmed on the session.created
//       event) and is appended to the system prompt on every request — the
//       system prompt is rebuilt per request, so a one-shot injection would
//       be forgotten after the first turn.
//
// The scripts are embedded rather than referenced so the plugin is ONE file a
// user drops into ~/.config/opencode/plugins/ — there is no plugin root to
// resolve, which is why ${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT} never appears
// here. The output is plain ESM JavaScript (no build step, no dependency), so
// OpenCode loads it as-is and `node` can import it for the hermetic tests.
export const OPENCODE_EVENTS = { PostToolUse: "tool.execute.after", SessionStart: "experimental.chat.system.transform" };
const SCRIPT_REF_RE = /hooks\/scripts\/([\w.-]+\.sh)/;

/** Hook wiring for the OpenCode template: per event, [{ matcher, scripts: [{ name, timeout }] }]. */
function opencodeHookGroups(hooks, event) {
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

/** Render the OpenCode plugin module for one plugin. `scripts` maps each hook
 *  script basename to its packaged (pin-substituted) content. */
export function renderOpencodePlugin({ name, version, description, hooks, scripts }) {
  const postToolUse = opencodeHookGroups(hooks, "PostToolUse");
  const sessionStart = opencodeHookGroups(hooks, "SessionStart");
  for (const g of [...postToolUse, ...sessionStart])
    for (const s of g.scripts)
      if (!(s.name in scripts)) throw new Error(`hooks.json references ${s.name}, which no closure hooks/ tree ships`);
  const unknown = Object.keys(hooks).filter((e) => !(e in OPENCODE_EVENTS));
  if (unknown.length) throw new Error(`no OpenCode mapping for hook event(s): ${unknown.join(", ")}`);

  const lit = (v) => JSON.stringify(v, null, 2);
  const scriptEntries = Object.keys(scripts)
    .sort()
    .map((n) => `  ${JSON.stringify(n)}: ${JSON.stringify(scripts[n])},`)
    .join("\n");

  return `// GENERATED by \`npm run build\` from hooks/*/hooks.json — do not edit; change the
// source and rebuild (see AGENTS.md). Drift is a CI failure.
//
// OpenCode plugin for the "${name}" plugin, version ${version}.
// ${description.length > 96 ? description.slice(0, 93).trimEnd() + "..." : description}
//
// OpenCode has no hooks.json: its plugins are JavaScript modules with a hook
// API. This module runs the very same hook scripts the Claude Code and Codex
// packages of this plugin run — embedded below, tool versions already pinned —
// and routes their output the OpenCode way:
//
//   PostToolUse  → "tool.execute.after": the script's additionalContext is
//                  appended to the tool result the model reads.
//   SessionStart → "experimental.chat.system.transform": the primer runs once
//                  per session (pre-warmed on the session.created event) and
//                  is appended to the system prompt on every request.
//
// Install: copy this file into ~/.config/opencode/plugins/ (every project) or
// .opencode/plugins/ (one project). Needs \`bash\` on PATH; the scripts need
// \`uvx\` and say so themselves when it is missing. Nothing else.

import { spawn } from "node:child_process";

const PLUGIN = ${JSON.stringify(name)};

// The hook scripts, byte-identical to plugins/${name}/hooks/scripts/*.sh.
const SCRIPTS = {
${scriptEntries}
};

// Wiring lifted from hooks.json. Matchers are the Claude/Codex tool-name
// regexes; OpenCode tool ids are lowercase, so matching is case-insensitive
// and the ids whose name differs are aliased to the name the matcher uses.
const POST_TOOL_USE = ${lit(postToolUse)};
const SESSION_START = ${lit(sessionStart)};
const TOOL_ALIASES = { patch: "apply_patch" };

function matches(matcher, tool) {
  if (!matcher) return true;
  const re = new RegExp(\`^(?:\${matcher})$\`, "i");
  return re.test(tool) || re.test(TOOL_ALIASES[tool] ?? "");
}

// Run one embedded script with the payload on stdin (what the harness would
// have piped), in the project directory, killed after its hooks.json timeout.
// Resolves to whatever it printed — never rejects: a hook must not break the
// tool call or the request it decorates.
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

/** @type {import("@opencode-ai/plugin").Plugin} */
export default async function ({ directory }) {
  const cwd = directory || process.cwd();
  const primers = new Map(); // sessionID → Promise<string>; one SessionStart per session
  const primer = (sessionID) => {
    const key = sessionID ?? "";
    if (!primers.has(key)) {
      const payload = JSON.stringify({ session_id: key, cwd, hook_event_name: "SessionStart", source: "startup", plugin: PLUGIN });
      primers.set(key, runGroups(SESSION_START, "", payload, cwd));
    }
    return primers.get(key);
  };

  const hooks = {};
${sessionStart.length ? `  hooks.event = async ({ event }) => {
    if (event?.type === "session.created") void primer(event.properties?.info?.id);
  };
  hooks[${JSON.stringify(OPENCODE_EVENTS.SessionStart)}] = async (input, output) => {
    const ctx = await primer(input?.sessionID);
    if (ctx) output.system.push(ctx);
  };
` : ""}${postToolUse.length ? `  hooks[${JSON.stringify(OPENCODE_EVENTS.PostToolUse)}] = async (input, output) => {
    const payload = JSON.stringify({
      session_id: input.sessionID,
      cwd,
      hook_event_name: "PostToolUse",
      tool_name: input.tool,
      tool_input: input.args,
      tool_response: { title: output?.title },
    });
    const ctx = await runGroups(POST_TOOL_USE, input.tool, payload, cwd);
    if (ctx) output.output = \`\${output.output ?? ""}\\n\\n\${ctx}\`;
  };
` : ""}  return hooks;
}
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

      // opencode/<name>.js — the same hooks as ONE OpenCode plugin module, the
      // scripts embedded with this plugin's pins applied (the module is
      // generated text, so it goes through `files` and is drift-checked as a
      // whole rather than copied).
      const scripts = {};
      for (const [base, source] of Object.entries(scriptSources)) {
        const content = applyPins(readFileSync(join(ROOT, source), "utf8"), pins);
        const leak = content.match(UNPINNED_RE);
        if (leak) throw new Error(`plugins/${p.name}/opencode: "${leak[0]}" in ${source} left unpinned — declare the tool in a plugin's "tools" map`);
        scripts[base] = content;
      }
      files[`plugins/${p.name}/opencode/${p.name}.js`] = renderOpencodePlugin({
        name: p.name,
        version: p.version,
        description: p.description,
        hooks: mergeHooksObject(closHooks),
        scripts,
      });
    }
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
      // OpenCode gets its hooks as a generated plugin module, one per plugin
      // that ships hooks: plugins/<name>/opencode/<name>.js.
      hasOpencodePlugin: closureHooks(p.name, byName).length > 0,
    })),
  });

  return { files, copies, dirs };
}

function jsonl(obj) {
  return JSON.stringify(obj, null, 2) + "\n";
}
