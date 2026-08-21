#!/usr/bin/env node
// Validate skills + confirm the generated files are in sync with the source.
// Usage: npm test   (CI fails on any error below)

import { readFileSync, existsSync, statSync } from "node:fs";
import { join } from "node:path";
import {
  ROOT,
  NAME_RE,
  loadModel,
  buildArtifacts,
  closure,
  declaredToolNames,
  pinScanFiles,
  applyPins,
  PIN_PLACEHOLDER,
  UNPINNED_RE,
  PIN_SCAN_EXTS,
  SPEC_FIELDS,
} from "./lib.mjs";

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
  // Only the six fields the Agent Skills spec defines. Claude Code accepts
  // roughly twenty more (`paths`, `argument-hint`, `context`, `model`, …),
  // but two of this repo's three targets — the `npx skills` CLI and the
  // Skills API packaging path — reject an unknown key with a hard error
  // rather than ignoring it. A skill that loads here and fails to package
  // elsewhere is the drift this check exists to catch.
  for (const key of Object.keys(s.frontmatter || {}))
    if (!SPEC_FIELDS.has(key))
      errors.push(
        `skills/${dir}: frontmatter key "${key}" is outside the Agent Skills spec ` +
          `(${[...SPEC_FIELDS].join(", ")}) — it would fail packaging for the non-Claude targets`,
      );
}

// 2. Every skill referenced by a plugin exists; plugin names are valid & unique.
const seen = new Set();
const byName = Object.fromEntries(config.plugins.map((p) => [p.name, p]));
for (const p of config.plugins) {
  if (!NAME_RE.test(p.name)) errors.push(`plugin "${p.name}": name must be lowercase-hyphen`);
  if (!/^\d+\.\d+\.\d+$/.test(p.version || ""))
    errors.push(`plugin "${p.name}": missing or non-semver "version" (both harnesses resolve updates from it)`);
  if (seen.has(p.name)) errors.push(`plugin "${p.name}": duplicate plugin name`);
  seen.add(p.name);
  for (const s of p.skills) if (!skills[s]) errors.push(`plugin "${p.name}": references unknown skill "${s}"`);
  for (const d of p.dependencies || []) if (!byName[d]) errors.push(`plugin "${p.name}": unknown dependency "${d}"`);
  for (const r of p.requires || []) if (!byName[r]) errors.push(`plugin "${p.name}": unknown required plugin "${r}"`);
  for (const a of p.agents || []) if (!existsSync(join(ROOT, a))) errors.push(`plugin "${p.name}": missing agent file ${a}`);
  if (p.hooks && !existsSync(join(ROOT, p.hooks))) errors.push(`plugin "${p.name}": missing hooks file ${p.hooks}`);
}

// 3. Tool pins: canonical skills/ and hooks/ never carry a concrete tool
//    version — they write the literal `@x.y.z` placeholder, and the build
//    substitutes each bundling plugin's pin (its `tools` map in
//    skills.config.json) into the generated plugins/ copies. astra-spec is
//    deliberately unpinned (the astra-tools release resolves it), so any spec
//    pin in canonical text is stale by definition.
{
  const toolNames = declaredToolNames(model.config);
  for (const rel of pinScanFiles()) {
    const text = readFileSync(join(ROOT, rel), "utf8");
    for (const name of toolNames) {
      for (const [, version] of text.matchAll(new RegExp(`\\b${name}(?:@|==)([\\w.+-]+)`, "g"))) {
        if (version.replace(/\.+$/, "") !== PIN_PLACEHOLDER)
          errors.push(
            `${rel}: pins ${name} ${version} — canonical sources write the @${PIN_PLACEHOLDER} placeholder; the version comes from skills.config.json at build time`,
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

// 5. Every packaged closure file exists, matches its canonical source content
//    (with the bundling plugin's tool pins applied — a byte copy when they
//    match the canonical pins), and preserves executable permission.
for (const { source, dest, pins } of copies) {
  const src = join(ROOT, source);
  const dst = join(ROOT, dest);
  if (!existsSync(dst)) {
    errors.push(`generated packaged file missing: ${dest} (run npm run build)`);
    continue;
  }
  const stamped = pins && Object.keys(pins).length && PIN_SCAN_EXTS.test(source);
  let upToDate;
  if (stamped) {
    const expected = applyPins(readFileSync(src, "utf8"), pins);
    const leak = expected.match(UNPINNED_RE);
    if (leak)
      errors.push(`${dest}: "${leak[0]}" left unpinned — declare the tool in a plugin's "tools" map`);
    upToDate = readFileSync(dst, "utf8") === expected;
  } else {
    upToDate = readFileSync(src).equals(readFileSync(dst));
  }
  if (!upToDate) {
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
