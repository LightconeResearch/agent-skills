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

/** Transitive skill closure for a plugin (its own skills + all dependency skills).
 *  Codex plugins are self-contained, so they bundle the whole closure. */
export function closure(pluginName, byName, seen = new Set()) {
  if (seen.has(pluginName)) return [];
  seen.add(pluginName);
  const p = byName[pluginName];
  const out = [...(p.skills || [])];
  for (const dep of p.dependencies || []) out.push(...closure(dep, byName, seen));
  return [...new Set(out)];
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

  // --- Claude Code marketplace (.claude-plugin/marketplace.json) -----------
  // supabase pattern: source "./" + strict:false, components selected by path.
  const claudePlugins = config.plugins.map((p) => {
    const entry = {
      name: p.name,
      description: p.description,
      source: "./",
      strict: false,
      skills: p.skills.map((s) => `./skills/${s}`),
    };
    if (p.agents) entry.agents = p.agents.map((a) => `./${a}`);
    if (p.hooks) entry.hooks = `./${p.hooks}`;
    if (p.dependencies && p.dependencies.length) entry.dependencies = p.dependencies;
    return entry;
  });
  files[".claude-plugin/marketplace.json"] = jsonl({
    name: mk.name,
    owner: mk.owner,
    metadata: { description: mk.description, version: mk.version },
    plugins: claudePlugins,
  });

  // --- Codex marketplace (.agents/plugins/marketplace.json) ----------------
  const codexPlugins = config.plugins.map((p) => ({
    name: p.name,
    description: p.description,
    source: { source: "local", path: `./plugins/${p.name}` },
    policy: { installation: "AVAILABLE" },
    category: "Development",
  }));
  files[".agents/plugins/marketplace.json"] = jsonl({
    name: mk.name,
    interface: { displayName: mk.displayName },
    plugins: codexPlugins,
  });

  // --- Codex per-plugin dirs (plugins/<name>/) -----------------------------
  // Codex plugins are self-contained: bundle the transitive skill closure as
  // relative symlinks back to the canonical skills/ tree (single source).
  //
  // Hooks: OpenAI Codex CLI reads the same Claude-compatible hooks.json
  // protocol (SessionStart/PostToolUse with hookSpecificOutput.additionalContext)
  // and aliases ${CLAUDE_PLUGIN_ROOT} → ${PLUGIN_ROOT}. So a plugin that ships
  // hooks for Claude can declare the *same* hooks.json + scripts here — we just
  // need them reachable under the Codex plugin root, so the hooks/ tree is
  // symlinked back to the canonical hooks/ (same single-source pattern as skills).
  for (const p of config.plugins) {
    const pluginManifest = {
      name: p.name,
      version: mk.version,
      description: p.description,
      author: mk.owner,
      homepage: `https://github.com/${mk.repo}`,
      repository: `https://github.com/${mk.repo}`,
      license: "BSD-3-Clause",
      skills: "./skills/",
    };
    // p.hooks is repo-relative (e.g. "hooks/hooks.json"); under the plugin root
    // the symlinked hooks/ tree puts it at the same relative path.
    if (p.hooks) pluginManifest.hooks = `./${p.hooks}`;
    files[`plugins/${p.name}/.codex-plugin/plugin.json`] = jsonl(pluginManifest);
    dirs.push(`plugins/${p.name}/skills`);
    for (const s of closure(p.name, byName)) {
      symlinks.push({
        kind: "skill",
        link: `plugins/${p.name}/skills/${s}`,
        target: `../../../skills/${s}`,
      });
    }
    if (p.hooks) {
      symlinks.push({
        kind: "dir",
        link: `plugins/${p.name}/hooks`,
        target: `../../hooks`,
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
      hasHooks: Boolean(p.hooks),
      hasAgents: Boolean(p.agents),
    })),
  });

  return { files, symlinks, dirs };
}

function jsonl(obj) {
  return JSON.stringify(obj, null, 2) + "\n";
}
