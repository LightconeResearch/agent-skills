#!/usr/bin/env node
// Refresh skills/astra/references/getting-started.md verbatim from astra-spec at
// ASTRA_SPEC_PIN (hooks/astra/scripts/astra-pins.sh). Opt-in: run it when the
// pin bumps (npm run fetch-getting-started), then commit the result. If the pinned
// release predates the page (404), the checked-in copy is left untouched.

import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const pins = readFileSync(join(ROOT, "hooks/astra/scripts/astra-pins.sh"), "utf8");
const pin = pins.match(/^ASTRA_SPEC_PIN="([^"]+)"/m)[1];
// TEMP: the pinned release predates the standalone getting-started page
// (astra-spec#50). Fetch from the PR branch until a release contains it,
// then delete DOCS_REF so the pin takes over.
const DOCS_REF = "main"; // ← delete when ASTRA_SPEC_PIN >= the release with astra-spec#50
const ref = DOCS_REF || `v${pin}`;
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
