#!/usr/bin/env node
// Validate skills + confirm the generated files are in sync with the source.
// Usage: npm test   (CI fails on any error below)

import { readFileSync, existsSync, statSync } from "node:fs";
import { join } from "node:path";
import { ROOT, NAME_RE, loadModel, buildArtifacts, closure, toolPins, pinScanFiles } from "./lib.mjs";

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
  for (const r of p.requires || []) if (!byName[r]) errors.push(`plugin "${p.name}": unknown required plugin "${r}"`);
  for (const a of p.agents || []) if (!existsSync(join(ROOT, a))) errors.push(`plugin "${p.name}": missing agent file ${a}`);
  if (p.hooks && !existsSync(join(ROOT, p.hooks))) errors.push(`plugin "${p.name}": missing hooks file ${p.hooks}`);
}

// 3. Tool pins: skills.config.json's `tools` map is the single source of
//    truth; every `<name>@<version>` (or ==) occurrence in canonical skills/
//    and hooks/ must match it exactly (`npm run build` stamps them). astra-spec
//    is deliberately unpinned (the astra-tools release resolves it), so any
//    spec pin in canonical text is stale by definition.
{
  const pins = toolPins(model.config);
  for (const rel of pinScanFiles()) {
    const text = readFileSync(join(ROOT, rel), "utf8");
    for (const [name, pin] of pins) {
      const re = new RegExp(`\\b${name}(?:@|==)([\\w.+-]+)`, "g");
      for (const [, version] of text.matchAll(re)) {
        if (version.replace(/\.+$/, "") !== pin)
          errors.push(
            `${rel}: pins ${name} ${version}, but skills.config.json pins ${pin} (run npm run build)`,
          );
      }
    }
    if (/\bastra-spec(?:@|==)/.test(text))
      errors.push(`${rel}: pins astra-spec — the spec is not pinned; the astra-tools pin resolves it`);
  }
}

// 4. Generated files match what the current source would produce (no drift).
const { files, copies } = buildArtifacts(model);
for (const [rel, expected] of Object.entries(files)) {
  const abs = join(ROOT, rel);
  if (!existsSync(abs)) { errors.push(`generated file missing: ${rel} (run npm run build)`); continue; }
  if (readFileSync(abs, "utf8") !== expected) errors.push(`generated file out of date: ${rel} (run npm run build)`);
}

// 5. Every packaged closure file exists, matches its canonical source bytes,
//    and preserves executable permission where relevant.
for (const { source, dest } of copies) {
  const src = join(ROOT, source);
  const dst = join(ROOT, dest);
  if (!existsSync(dst)) {
    errors.push(`generated packaged file missing: ${dest} (run npm run build)`);
    continue;
  }
  if (!readFileSync(src).equals(readFileSync(dst))) {
    errors.push(`generated packaged file out of date: ${dest} (run npm run build)`);
  }
  if ((statSync(src).mode & 0o111) !== (statSync(dst).mode & 0o111)) {
    errors.push(`generated packaged file mode differs: ${dest} (run npm run build)`);
  }
}

if (errors.length) {
  console.error(`✗ ${errors.length} problem(s):\n` + errors.map((e) => `  - ${e}`).join("\n"));
  process.exit(1);
}
console.log(
  `✓ ${Object.keys(skills).length} skills, ${config.plugins.length} plugins, ` +
  `${copies.length} packaged files — frontmatter valid and generated files in sync.`,
);
