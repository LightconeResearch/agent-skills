# @lightcone-research/astra-plugin

Reference for the ASTRA specification (astra.yaml): top-level structure, sub-analyses, inputs/outputs, decisions and options, prior insights and findings, evidence and quote verification, and composition mechanics. Invoke when reading, writing, validating, or debugging an astra.yaml spec, or when the user asks about ASTRA schema or sub-analysis composition. Ships hooks that validate astra.yaml on save and remind agents to load the skill when they read an ASTRA file.

Generated from [LightconeResearch/agent-skills](https://github.com/LightconeResearch/agent-skills) — the same skills and hooks that ship as the
`astra` plugin for Claude Code and Codex, packaged for harnesses that install
from npm. Version 0.0.5 of the plugin.

## OpenCode

Hooks: add the package to `opencode.json` (`~/.config/opencode/opencode.json` for
every project, or a project's own):

```json
{ "$schema": "https://opencode.ai/config.json", "plugin": ["@lightcone-research/astra-plugin@0.0.5"] }
```

Skills: `npx skills add https://github.com/LightconeResearch/agent-skills/tree/main/plugins/astra -a opencode -g`

## Pi

```bash
pi install npm:@lightcone-research/astra-plugin@0.0.5
```

Installs the skills and the hooks together; invoke a skill as `/skill:<name>`.

## Contents

- Skills: `astra`
- Hooks: the plugin's SessionStart primer and PostToolUse validation, as an OpenCode plugin module (`opencode/index.js`) and a Pi extension (`pi/index.js`). Needs `bash` on PATH; the scripts need `uvx` and say so when it is missing.

Documentation: https://lightconeresearch.github.io/agent-skills/opencode/ and https://lightconeresearch.github.io/agent-skills/pi/ · License: BSD-3-Clause
