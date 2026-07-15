#!/usr/bin/env node
// Regenerate every per-target file from skills.config.json + skills/.
// Usage: npm run build

import { chmodSync, copyFileSync, mkdirSync, writeFileSync, rmSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { ROOT, loadModel, buildArtifacts } from "./lib.mjs";

const { files, copies, dirs } = buildArtifacts(loadModel());

// plugins/ is fully generated — wipe it so renamed/removed plugins don't linger.
rmSync(join(ROOT, "plugins"), { recursive: true, force: true });

for (const [rel, content] of Object.entries(files)) {
  const abs = join(ROOT, rel);
  mkdirSync(dirname(abs), { recursive: true });
  writeFileSync(abs, content);
}

for (const d of dirs) mkdirSync(join(ROOT, d), { recursive: true });

for (const { source, dest } of copies) {
  const src = join(ROOT, source);
  const dst = join(ROOT, dest);
  mkdirSync(dirname(dst), { recursive: true });
  copyFileSync(src, dst);
  chmodSync(dst, statSync(src).mode);
}

console.log(
  `Generated ${Object.keys(files).length} metadata files and ${copies.length} packaged files ` +
    `(skills + agents + hooks) across Claude (.claude-plugin), Codex (.agents/plugins), ` +
    `the shared plugins/ dirs, and manifest.json.`,
);
