#!/usr/bin/env node
// Regenerate every per-target file from skills.config.json + skills/.
// Usage: npm run build

import { chmodSync, copyFileSync, mkdirSync, readFileSync, writeFileSync, rmSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { ROOT, loadModel, buildArtifacts, applyPins, UNPINNED_RE, PIN_SCAN_EXTS } from "./lib.mjs";

const model = loadModel();
const { files, copies, dirs } = buildArtifacts(model);

// plugins/ is fully generated — wipe it so renamed/removed plugins don't linger.
rmSync(join(ROOT, "plugins"), { recursive: true, force: true });

for (const [rel, content] of Object.entries(files)) {
  const abs = join(ROOT, rel);
  mkdirSync(dirname(abs), { recursive: true });
  writeFileSync(abs, content);
}

for (const d of dirs) mkdirSync(join(ROOT, d), { recursive: true });

for (const { source, dest, pins } of copies) {
  const src = join(ROOT, source);
  const dst = join(ROOT, dest);
  mkdirSync(dirname(dst), { recursive: true });
  // Packaged copies replace the canonical @x.y.z tool-pin placeholders with
  // the bundling plugin's pinned versions; anything else is a byte copy.
  if (pins && Object.keys(pins).length && PIN_SCAN_EXTS.test(source)) {
    const content = applyPins(readFileSync(src, "utf8"), pins);
    const leak = content.match(UNPINNED_RE);
    if (leak)
      throw new Error(`${dest}: "${leak[0]}" left unpinned — declare the tool in a plugin's "tools" map`);
    writeFileSync(dst, content);
  } else {
    copyFileSync(src, dst);
  }
  chmodSync(dst, statSync(src).mode);
}

console.log(
  `Generated ${Object.keys(files).length} metadata files and ${copies.length} packaged files ` +
    `(skills + agents + hooks) across Claude (.claude-plugin), Codex (.agents/plugins), ` +
    `the shared plugins/ dirs, and manifest.json.`,
);
