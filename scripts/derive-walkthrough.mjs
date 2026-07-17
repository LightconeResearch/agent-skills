#!/usr/bin/env node
// Derive skills/astra/references/walkthrough.md from the astra-spec docs at the
// pinned schema version. The walkthrough is not authored by hand — it is a
// mechanical transform of upstream `docs/getting-started.md` (the ground-up tour
// of the format), so it can never teach a version the tool doesn't speak. Re-run
// at every pin bump, in the same PR:
//
//     npm run derive:walkthrough && npm run build
//
// The single source for the version is hooks/astra/scripts/astra-pins.sh
// (ASTRA_SPEC_PIN); this script reads it, fetches the doc at tag v<pin>, and
// applies deterministic rewrites (banner, H1, relative-link resolution, and the
// two mkdocs constructs the source uses). Network is needed only here, not at
// build time — the derived file is committed.

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = "LightconeResearch/astra-spec";
const SRC_DOC = "docs/getting-started.md";
const OUT = "skills/astra/references/walkthrough.md";

const pins = readFileSync(join(ROOT, "hooks/astra/scripts/astra-pins.sh"), "utf8");
const pin = pins.match(/^ASTRA_SPEC_PIN="([^"]+)"/m)?.[1];
if (!pin) throw new Error("could not read ASTRA_SPEC_PIN from hooks/astra/scripts/astra-pins.sh");
const tag = `v${pin}`;
const blob = `https://github.com/${REPO}/blob/${tag}/docs`;

const rawUrl = `https://raw.githubusercontent.com/${REPO}/${tag}/${SRC_DOC}`;
const res = await fetch(rawUrl);
if (!res.ok) throw new Error(`fetch ${rawUrl} → HTTP ${res.status}`);
const source = await res.text();

// --- deterministic transforms ---------------------------------------------

/** Resolve mkdocs content tabs (`=== "Label"`) and admonitions (`!!! type "Title"`)
 *  into plain markdown, de-indenting the 4-space block each introduces. */
function normalizeAdmonitions(md) {
  const lines = md.split("\n");
  const out = [];
  for (let i = 0; i < lines.length; i++) {
    const tab = /^=== "(.+)"\s*$/.exec(lines[i]);
    const adm = /^!!! (\w+)(?: "(.+)")?\s*$/.exec(lines[i]);
    if (!tab && !adm) { out.push(lines[i]); continue; }
    const quote = Boolean(adm); // admonitions become blockquotes; tabs become bold headers
    if (tab) out.push(`**${tab[1]}**`);
    else out.push(`> **${cap(adm[1])}${adm[2] ? `: ${adm[2]}` : ""}**`);
    // consume the following blank-or-indented block, de-indenting by 4 spaces.
    let j = i + 1;
    const body = [];
    for (; j < lines.length; j++) {
      const l = lines[j];
      if (l === "") { body.push(""); continue; }
      if (/^ {4}/.test(l)) { body.push(l.slice(4)); continue; }
      break;
    }
    while (body.length && body[0] === "") body.shift();
    while (body.length && body[body.length - 1] === "") body.pop();
    out.push("", ...(quote ? body.map((l) => (l === "" ? ">" : `> ${l}`)) : body), "");
    i = j - 1;
  }
  return out.join("\n");
}

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

let body = normalizeAdmonitions(source);

// Resolve relative doc links (`foo.md`, `foo.md#anchor`) to the pinned source on
// GitHub, so every reference in the derived file still points somewhere real.
body = body.replace(/\]\(([a-z0-9-]+)\.md(#[^)]*)?\)/gi, (_m, name, anchor = "") => `](${blob}/${name}.md${anchor})`);

// Retitle: this is the plugin's walkthrough, not the upstream page title.
body = body.replace(/^# .*$/m, "# ASTRA Walkthrough");

const banner = [
  "<!--",
  "  GENERATED FILE — do not edit by hand.",
  `  Derived from ${REPO} ${SRC_DOC} at ${tag} by scripts/derive-walkthrough.mjs.`,
  "  Re-run `npm run derive:walkthrough && npm run build` at every pin bump.",
  "-->",
  "",
  `> Narrative tour of the ASTRA format, derived from the [astra-spec getting-started guide](${blob}/getting-started.md) at \`${tag}\` (the pinned schema version). For the field-level grammar, use \`astra spec <term>\`.`,
  "",
  "",
].join("\n");

mkdirSync(dirname(join(ROOT, OUT)), { recursive: true });
writeFileSync(join(ROOT, OUT), banner + body.replace(/\s*$/, "") + "\n");
console.log(`Derived ${OUT} from ${REPO} ${SRC_DOC}@${tag}.`);
