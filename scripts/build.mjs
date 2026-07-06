#!/usr/bin/env node
// Regenerate every per-target file from skills.config.json + skills/.
// Usage: npm run build

import { mkdirSync, writeFileSync, rmSync, symlinkSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { ROOT, loadModel, buildArtifacts } from "./lib.mjs";

const { files, symlinks, dirs } = buildArtifacts(loadModel());

// plugins/ is fully generated — wipe it so renamed/removed plugins don't linger.
rmSync(join(ROOT, "plugins"), { recursive: true, force: true });

for (const [rel, content] of Object.entries(files)) {
  const abs = join(ROOT, rel);
  mkdirSync(dirname(abs), { recursive: true });
  writeFileSync(abs, content);
}

for (const d of dirs) mkdirSync(join(ROOT, d), { recursive: true });

for (const { link, target } of symlinks) {
  const abs = join(ROOT, link);
  mkdirSync(dirname(abs), { recursive: true });
  if (existsSync(abs)) rmSync(abs, { recursive: true, force: true });
  symlinkSync(target, abs);
}

console.log(
  `Generated ${Object.keys(files).length} files and ${symlinks.length} closure symlinks ` +
    `(skills + agents + hooks) across Claude (.claude-plugin), Codex (.agents/plugins), ` +
    `the shared plugins/ dirs, and manifest.json.`,
);
