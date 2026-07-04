// Shared build logic for the multi-target skills repo.
//
// One source of truth: skills.config.json + the canonical skills/ directory.
// buildArtifacts() returns the exact bytes/symlinks each target needs, so the
// generator (build.mjs) and the drift check (validate.mjs) agree by construction.

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

export const NAME_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

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
 *   - symlinks: [{ link: relPath, target: relTargetFromLinkDir }]
 *   - dirs: [relPath]  (directories that must exist even if only holding symlinks)
 */
export function buildArtifacts(model) {
  const { config, skills } = model;
  const mk = config.marketplace;
  const byName = Object.fromEntries(config.plugins.map((p) => [p.name, p]));
  const files = {};
  const symlinks = [];
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
      policy: { installation: "AVAILABLE" },
      category: "Development",
    })),
  });

  // --- Self-contained per-plugin dirs (plugins/<name>/) --------------------
  // Each dir carries the whole closure and ships both harnesses' plugin
  // manifests. Skills/agents/hooks are relative symlinks back to the canonical
  // trees (single source, no content duplication); Claude and Codex both
  // auto-discover skills/, agents/, and hooks/hooks.json under the plugin root.
  //
  // Hooks: OpenAI Codex CLI reads the same Claude-compatible hooks.json
  // protocol (SessionStart/PostToolUse with hookSpecificOutput.additionalContext)
  // and aliases ${CLAUDE_PLUGIN_ROOT} → ${PLUGIN_ROOT}, so one hooks.json + one
  // scripts tree serves both. Neither plugin manifest declares dependencies —
  // the closure is already bundled.
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

    // Codex: declares component roots explicitly (its convention).
    const codexManifest = { ...base, skills: "./skills/" };
    if (closAgents.length) codexManifest.agents = "./agents/";
    if (hooksPath) codexManifest.hooks = `./${hooksPath}`;
    files[`plugins/${p.name}/.codex-plugin/plugin.json`] = jsonl(codexManifest);

    // skills/ — full closure, symlinked to canonical skills/.
    dirs.push(`plugins/${p.name}/skills`);
    for (const s of closureSkills) {
      symlinks.push({
        kind: "skill",
        link: `plugins/${p.name}/skills/${s}`,
        target: `../../../skills/${s}`,
      });
    }

    // agents/ — full closure, symlinked file-by-file to canonical agents/.
    if (closAgents.length) dirs.push(`plugins/${p.name}/agents`);
    for (const a of closAgents) {
      const file = a.replace(/^agents\//, "");
      symlinks.push({
        kind: "agent",
        link: `plugins/${p.name}/agents/${file}`,
        target: `../../../${a}`,
      });
    }

    // hooks/ — the whole canonical hooks tree (hooks.json + scripts), symlinked
    // when the closure includes hooks. Link location is derived from the manifest
    // path (dirname of hooksPath) so the symlink and the `hooks: ./<path>` the
    // manifests reference can never drift, even if the canonical tree is renamed.
    if (hooksPath) {
      const hooksDir = dirname(hooksPath); // e.g. "hooks"
      symlinks.push({
        kind: "dir",
        link: `plugins/${p.name}/${hooksDir}`,
        target: `../../${hooksDir}`,
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
      // Reflect the bundled closure — what installing this one plugin gives you.
      hasHooks: closureHooks(p.name, byName).length > 0,
      hasAgents: closureAgents(p.name, byName).length > 0,
    })),
  });

  return { files, symlinks, dirs };
}

function jsonl(obj) {
  return JSON.stringify(obj, null, 2) + "\n";
}
