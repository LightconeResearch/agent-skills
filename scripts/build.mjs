#!/usr/bin/env node
// Regenerate every per-target file from skills.config.json + skills/.
// Usage: npm run build

import { chmodSync, copyFileSync, mkdirSync, readFileSync, writeFileSync, rmSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { ROOT, loadModel, buildArtifacts, pinStamps, applyPins, PIN_SCAN_EXTS } from "./lib.mjs";

const model = loadModel();

// Stamp each canonical tree with its owning plugin's tool pins first, so the
// packaged copies below start from pinned sources.
const stamps = pinStamps(model);
for (const { rel, content } of stamps) writeFileSync(join(ROOT, rel), content);
if (stamps.length)
  console.log(`Stamped tool pins into ${stamps.length} canonical file(s): ${stamps.map((s) => s.rel).join(", ")}`);

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
  // Packaged copies carry the bundling plugin's tool pins — a byte copy when
  // they match the canonical pins (the common case).
  if (pins && Object.keys(pins).length && PIN_SCAN_EXTS.test(source)) {
    writeFileSync(dst, applyPins(readFileSync(src, "utf8"), pins));
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
