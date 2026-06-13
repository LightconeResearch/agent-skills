#!/usr/bin/env node
// Validate skills + confirm the generated files are in sync with the source.
// Usage: npm test   (CI fails on any error below)

import { readFileSync, readlinkSync, existsSync, statSync } from "node:fs";
import { join } from "node:path";
import { ROOT, NAME_RE, loadModel, buildArtifacts, closure } from "./lib.mjs";

const errors = [];
const model = loadModel();
const { config, skills } = model;

// 1. Per-skill frontmatter conforms to the Agent Skills standard.
for (const [dir, s] of Object.entries(skills)) {
  if (!s.name) errors.push(`skills/${dir}: missing 'name' in frontmatter`);
  else if (!NAME_RE.test(s.name)) errors.push(`skills/${dir}: name "${s.name}" must be lowercase-hyphen`);
  else if (s.name !== dir) errors.push(`skills/${dir}: name "${s.name}" must match its directory`);
  if (!s.description) errors.push(`skills/${dir}: missing 'description'`);
  else if (s.description.length > 1024) errors.push(`skills/${dir}: description exceeds 1024 chars (${s.description.length})`);
}

// 2. Every skill referenced by a plugin exists; plugin names are valid & unique.
const seen = new Set();
const byName = Object.fromEntries(config.plugins.map((p) => [p.name, p]));
for (const p of config.plugins) {
  if (!NAME_RE.test(p.name)) errors.push(`plugin "${p.name}": name must be lowercase-hyphen`);
  if (seen.has(p.name)) errors.push(`plugin "${p.name}": duplicate plugin name`);
  seen.add(p.name);
  for (const s of p.skills) if (!skills[s]) errors.push(`plugin "${p.name}": references unknown skill "${s}"`);
  for (const d of p.dependencies || []) if (!byName[d]) errors.push(`plugin "${p.name}": unknown dependency "${d}"`);
  for (const a of p.agents || []) if (!existsSync(join(ROOT, a))) errors.push(`plugin "${p.name}": missing agent file ${a}`);
  if (p.hooks && !existsSync(join(ROOT, p.hooks))) errors.push(`plugin "${p.name}": missing hooks file ${p.hooks}`);
}

// 3. Generated files match what the current source would produce (no drift).
const { files, symlinks } = buildArtifacts(model);
for (const [rel, expected] of Object.entries(files)) {
  const abs = join(ROOT, rel);
  if (!existsSync(abs)) { errors.push(`generated file missing: ${rel} (run npm run build)`); continue; }
  if (readFileSync(abs, "utf8") !== expected) errors.push(`generated file out of date: ${rel} (run npm run build)`);
}

// 4. Codex symlinks exist and resolve: skill symlinks to a real SKILL.md,
//    other (e.g. hooks) symlinks to an existing directory.
for (const { link, kind } of symlinks) {
  const abs = join(ROOT, link);
  try {
    readlinkSync(abs); // must be a symlink
    if (kind === "skill") {
      if (!statSync(join(abs, "SKILL.md")).isFile()) throw new Error("no SKILL.md");
    } else if (!statSync(abs).isDirectory()) {
      throw new Error("not a directory");
    }
  } catch {
    errors.push(`broken Codex symlink: ${link} (run npm run build)`);
  }
}

if (errors.length) {
  console.error(`✗ ${errors.length} problem(s):\n` + errors.map((e) => `  - ${e}`).join("\n"));
  process.exit(1);
}
console.log(
  `✓ ${Object.keys(skills).length} skills, ${config.plugins.length} plugins, ` +
    `${symlinks.length} symlinks — frontmatter valid and generated files in sync.`,
);
