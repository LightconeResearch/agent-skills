#!/usr/bin/env node
// Refresh skills/astra/references/getting-started.md verbatim from astra-spec
// at the version the astra plugin's pinned astra-tools (its `tools` map in
// skills.config.json) resolves to — the spec itself is not pinned, so uv
// resolves it the same way the hooks' uvx invocation does. Opt-in: run it when
// the tools pin bumps (npm run fetch-getting-started), then commit the result.
// If the resolved release predates the page (404), the checked-in copy is left
// untouched.

import { spawnSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { loadModel, pluginTools } from "./lib.mjs";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const { config } = loadModel();
const byName = Object.fromEntries(config.plugins.map((p) => [p.name, p]));
const toolsPin = pluginTools("astra", byName)["astra-tools"];
const toolsReq = `astra-tools==${toolsPin}`;

const probe = spawnSync(
  "uv",
  ["run", "--no-project", "--with", toolsReq, "python", "-c",
    "from importlib.metadata import version; print(version('astra-spec'))"],
  { encoding: "utf8" },
);
if (probe.error || probe.status !== 0) {
  console.error(
    `Could not resolve astra-spec from ${toolsReq} via uv (is uv installed?):\n` +
      `${probe.error ?? probe.stderr}`,
  );
  process.exit(1);
}
const specVersion = probe.stdout.trim();
const ref = `v${specVersion}`;
const url = `https://raw.githubusercontent.com/LightconeResearch/astra-spec/${ref}/docs/getting-started.md`;

const res = await fetch(url).catch((err) => {
  console.error(`Could not reach ${url}: ${err.cause ?? err}`);
  process.exit(1);
});
if (!res.ok) {
  console.warn(`No getting-started page at ${url} (HTTP ${res.status}); keeping the checked-in copy.`);
  process.exit(0);
}
writeFileSync(join(ROOT, "skills/astra/references/getting-started.md"), await res.text());
console.log(`Wrote skills/astra/references/getting-started.md verbatim from astra-spec ${ref}.`);
