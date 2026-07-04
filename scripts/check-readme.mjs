#!/usr/bin/env node
// Install-doc completeness check: the README must document, for BOTH harnesses
// (Claude Code + Codex) and BOTH modes (interactive session + terminal CLI), how
// to install a plugin. Pure text checks — no external binaries — so it runs as
// part of `npm test`. The real install is exercised by `npm run smoke`.
//
// Usage: node scripts/check-readme.mjs   (or via `npm test`)

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ROOT, loadModel } from "./lib.mjs";

const readme = readFileSync(join(ROOT, "README.md"), "utf8");
const { config } = loadModel();
const errors = [];
const has = (re) => re.test(readme);

// Each install vector must be documented. `need` is a human label; `re` a probe.
const vectors = [
  ["Claude Code — terminal CLI: marketplace add", /claude plugin marketplace add/],
  ["Claude Code — terminal CLI: install", /claude plugin install \w+@/],
  ["Claude Code — interactive: /plugin marketplace add", /\/plugin marketplace add/],
  ["Claude Code — interactive: /plugin install", /\/plugin install \w+@/],
  ["Codex — terminal CLI: marketplace add", /codex plugin marketplace add/],
  ["Codex — terminal CLI: add", /codex plugin add \w+@/],
  ["Codex — interactive: /plugins", /\/plugins\b/],
];
for (const [need, re] of vectors) if (!has(re)) errors.push(`README missing install doc: ${need}`);

// The marketplace id and repo slug must both appear (they're what users type).
if (!has(/lightcone-research/)) errors.push("README missing marketplace id `lightcone-research`");
if (!has(/LightconeResearch\/agent-skills/)) errors.push("README missing repo slug `LightconeResearch/agent-skills`");

// Every plugin must be named somewhere in the README.
for (const p of config.plugins)
  if (!readme.includes(p.name)) errors.push(`README never mentions plugin \`${p.name}\``);

// The unified-mechanism promise must be stated, and the stale native-dependency
// phrasing must be gone (installing a plugin does NOT trigger a separate install).
if (!/self-contained|bundle/i.test(readme))
  errors.push("README should state that plugins are self-contained / bundle their dependencies");
if (/pulls in the `?astra/i.test(readme))
  errors.push('README still uses stale native-dependency phrasing ("pulls in astra") — plugins now bundle their closure');

// Basic hygiene: a prerequisites section and a plugins overview must exist.
if (!/##[^\n]*Prerequisite/i.test(readme)) errors.push("README missing a Prerequisites section");
if (!/##[^\n]*Plugin/i.test(readme)) errors.push("README missing a Plugins section");

if (errors.length) {
  console.error(`✗ README install-doc check — ${errors.length} problem(s):\n` + errors.map((e) => `  - ${e}`).join("\n"));
  process.exit(1);
}
console.log(`✓ README documents install for both harnesses × both modes, all ${config.plugins.length} plugins named.`);
