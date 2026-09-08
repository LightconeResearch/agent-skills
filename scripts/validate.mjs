#!/usr/bin/env node
// Validate skills + confirm the generated files are in sync with the source.
// Usage: npm test   (CI fails on any error below)

import { readFileSync, existsSync, statSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
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
  npmPackageName,
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

// 1b. Progressive disclosure holds together: a skill's references/ files are
//     the ones it points at, and they stay one level deep. A reference loads
//     only when the agent reads it, so a pointer to a file that moved is a
//     silent hole rather than an error, and a reference reachable only from
//     another reference tends to be previewed with `head` instead of read.
for (const [dir] of Object.entries(skills)) {
  const refDir = join(ROOT, "skills", dir, "references");
  if (!existsSync(refDir)) continue;
  const onDisk = readdirSync(refDir).filter((f) => f.endsWith(".md"));
  const body = readFileSync(join(ROOT, "skills", dir, "SKILL.md"), "utf8");
  const pointed = new Set([...body.matchAll(/references\/([\w.-]+\.md)/g)].map((m) => m[1]));
  for (const name of pointed)
    if (!onDisk.includes(name))
      errors.push(`skills/${dir}/SKILL.md: points at references/${name}, which does not exist`);
  for (const name of onDisk)
    if (!pointed.has(name))
      errors.push(
        `skills/${dir}/references/${name}: nothing in SKILL.md points at it — an unreferenced file never loads`,
      );
  for (const name of onDisk) {
    const text = readFileSync(join(refDir, name), "utf8");
    for (const [, target] of text.matchAll(/references\/([\w.-]+\.md)/g)) {
      if (target === name) continue;
      if (!onDisk.includes(target))
        errors.push(`skills/${dir}/references/${name}: points at references/${target}, which does not exist`);
    }
  }
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

// 6. The npm packages. Each plugins/<name>/ is also the npm package OpenCode
//    and Pi install, so on top of the drift check (which proves the generated
//    text is what the generator produces) this proves the package is what those
//    harnesses can consume:
//    - both modules import as ES modules with a function default export
//      (OpenCode imports the main; Pi imports pi/index.js via jiti);
//    - the OpenCode module exposes ONLY that export — OpenCode iterates every
//      export and throws on a non-function;
//    - the manifest names the package from marketplace.npmScope and carries the
//      plugin's version, and its `pi` entries point at existing paths;
//    - no dependencies, no scripts, no lockfile: a package.json + lockfile at a
//      Claude Code plugin root makes Claude run an install for the plugin.
{
  const mk = config.marketplace;
  if (!/^@[a-z0-9-]+$/.test(mk.npmScope || ""))
    errors.push(`skills.config.json: marketplace.npmScope must be an npm scope like "@lightcone-research" (got ${JSON.stringify(mk.npmScope)})`);
  const LOCKFILES = ["package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb"];
  for (const p of config.plugins) {
    const dir = join(ROOT, "plugins", p.name);
    const manifestPath = join(dir, "package.json");
    if (!existsSync(manifestPath)) continue; // reported by the drift check
    let manifest;
    try { manifest = JSON.parse(readFileSync(manifestPath, "utf8")); } catch (e) { errors.push(`plugins/${p.name}/package.json: ${e.message}`); continue; }
    const expectedName = mk.npmScope ? npmPackageName(mk, p.name) : null;
    if (expectedName && manifest.name !== expectedName)
      errors.push(`plugins/${p.name}/package.json: name ${manifest.name} ≠ ${expectedName}`);
    if (manifest.version !== p.version)
      errors.push(`plugins/${p.name}/package.json: version ${manifest.version} ≠ plugin version ${p.version}`);
    for (const key of ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies", "scripts"])
      if (manifest[key]) errors.push(`plugins/${p.name}/package.json: must not declare ${key} (the modules are dependency-free by design)`);
    for (const rel of [...(manifest.pi?.extensions || []), ...(manifest.pi?.skills || [])])
      if (!existsSync(join(dir, rel))) errors.push(`plugins/${p.name}/package.json: pi entry ${rel} does not exist`);
    for (const lock of LOCKFILES)
      if (existsSync(join(dir, lock)))
        errors.push(`plugins/${p.name}/${lock}: a lockfile next to package.json makes Claude Code run an install for this plugin — remove it`);
    for (const rel of ["opencode/index.js", "pi/index.js"]) {
      const abs = join(dir, rel);
      if (!existsSync(abs)) continue; // only plugins with hooks ship modules; drift check reports a missing one
      try {
        const mod = await import(pathToFileURL(abs).href);
        if (typeof mod.default !== "function") errors.push(`plugins/${p.name}/${rel}: default export is not a function`);
        const exported = Object.keys(mod);
        if (rel.startsWith("opencode/") && (exported.length !== 1 || exported[0] !== "default"))
          errors.push(`plugins/${p.name}/${rel}: exports ${JSON.stringify(exported)} — OpenCode loads every export, so only \`default\` may exist`);
      } catch (e) {
        errors.push(`plugins/${p.name}/${rel}: failed to import as an ES module — ${e.message}`);
      }
    }
  }
}

if (errors.length) {
  console.error(`✗ ${errors.length} problem(s):\n` + errors.map((e) => `  - ${e}`).join("\n"));
  process.exit(1);
}
console.log(
  `✓ ${Object.keys(skills).length} skills, ${config.plugins.length} plugins, ` +
  `${copies.length} packaged files — frontmatter valid, generated files in sync, npm packages consistent.`,
);
