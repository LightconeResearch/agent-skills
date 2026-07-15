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
    skills[name] = { dir: name, name: fm.name, description: fm.description || "" };
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

/** Transitive agent-file closure (repo-relative paths, e.g. "agents/lc-extractor.md"). */
export function closureAgents(pluginName, byName) {
  const out = [];
  for (const p of closurePlugins(pluginName, byName)) out.push(...(p.agents || []));
  return [...new Set(out)];
}

/** Transitive hooks closure — the distinct hooks.json paths across the closure.
 *  Only one canonical hooks tree exists today; more than one distinct source
 *  would need a merge step, so we assert the single-source invariant here. */
export function closureHooks(pluginName, byName) {
  const out = [...new Set(closurePlugins(pluginName, byName).flatMap((p) => (p.hooks ? [p.hooks] : [])))];
  if (out.length > 1) {
    throw new Error(
      `plugin "${pluginName}": closure bundles ${out.length} distinct hooks.json sources ` +
        `(${out.join(", ")}); merging hooks across dependencies is not implemented.`,
    );
  }
  return out;
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
    metadata: { description: mk.description, version: mk.version },
    plugins: config.plugins.map((p) => ({
      name: p.name,
      description: p.description,
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
  // with hookSpecificOutput.additionalContext); commands reference the plugin
  // root harness-neutrally as ${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT} (Claude Code
  // sets the former, Codex the latter), so one hooks.json + one scripts tree
  // serves both. Neither plugin manifest declares dependencies — the closure
  // is already bundled.
  for (const p of config.plugins) {
    const closureSkills = closure(p.name, byName);
    const closAgents = closureAgents(p.name, byName);
    const closHooks = closureHooks(p.name, byName); // 0 or 1 entry
    const hooksPath = closHooks[0]; // repo-relative, e.g. "hooks/hooks.json"

    // Shared metadata for both harnesses' manifests.
    const base = {
      name: p.name,
      version: mk.version,
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
        source: a,
        dest: `plugins/${p.name}/agents/${file}`,
      });
    }

    // hooks/ — materialize the whole canonical hooks tree (hooks.json + scripts)
    // when the closure includes hooks. The destination is derived from the
    // canonical manifest path so the generated tree cannot drift if it is renamed.
    if (hooksPath) {
      const hooksDir = dirname(hooksPath); // e.g. "hooks"
      for (const source of filesUnder(hooksDir)) copies.push({
        kind: "hook",
        source,
        dest: `plugins/${p.name}/${hooksDir}/${source.slice(hooksDir.length + 1)}`,
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
    version: mk.version,
    description: mk.description,
    repository: `https://github.com/${mk.repo}`,
    generated: "Run `npm run build` to regenerate. Do not edit by hand.",
    skills: Object.keys(skills)
      .sort()
      .map((s) => ({
        name: skills[s].name,
        path: `skills/${s}`,
        description: skills[s].description,
        plugins: (skillToPlugins[s] || []).sort(),
      })),
    plugins: config.plugins.map((p) => ({
      name: p.name,
      description: p.description,
      skills: closure(p.name, byName).sort(),
      dependencies: p.dependencies || [],
      // Documented-only prerequisites: not bundled, the user installs them.
      requires: p.requires || [],
      // Reflect the bundled closure — what installing this one plugin gives you.
      hasHooks: closureHooks(p.name, byName).length > 0,
      hasAgents: closureAgents(p.name, byName).length > 0,
    })),
  });

  return { files, copies, dirs };
}

function jsonl(obj) {
  return JSON.stringify(obj, null, 2) + "\n";
}
