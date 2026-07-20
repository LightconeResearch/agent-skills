#!/usr/bin/env node
// Refresh skills/astra/references/walkthrough.md verbatim from astra-spec at
// ASTRA_SPEC_PIN (hooks/astra/scripts/astra-pins.sh). Opt-in: run it when the
// pin bumps (npm run fetch-walkthrough), then commit the result. If the pinned
// release predates the page (404), the checked-in copy is left untouched.

import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const pins = readFileSync(join(ROOT, "hooks/astra/scripts/astra-pins.sh"), "utf8");
const pin = pins.match(/^ASTRA_SPEC_PIN="([^"]+)"/m)[1];
const url = `https://raw.githubusercontent.com/LightconeResearch/astra-spec/v${pin}/docs/walkthrough.md`;

const res = await fetch(url).catch((err) => {
  console.error(`Could not reach ${url}: ${err.cause ?? err}`);
  process.exit(1);
});
if (!res.ok) {
  console.warn(`No walkthrough at ${url} (HTTP ${res.status}); keeping the checked-in copy.`);
  process.exit(0);
}
writeFileSync(join(ROOT, "skills/astra/references/walkthrough.md"), await res.text());
console.log(`Wrote skills/astra/references/walkthrough.md verbatim from astra-spec v${pin}.`);
