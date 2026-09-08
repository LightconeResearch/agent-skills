# @lightcone-research/lightcone-plugin

Companion for working on a Lightcone project — an ASTRA analysis (astra.yaml) executed with the `lc` CLI. Covers the project model (a uv project, direct or containerized, stored as a DataLad dataset), the development workflow (probe with `lc run`, integrate recipes, commit, `lc materialize`), status interpretation (current/behind/stale) and failure diagnosis, publishing the RO-Crate view, and how to engage the user at each phase: interview to scope a brand-new project, orient and summarize when resuming an existing one. Invoke whenever the user wants to start, resume, plan, run, debug, or discuss a Lightcone/ASTRA analysis project. Bundles the `astra` plugin (spec reference, validate-on-save & session-start hooks) — install `lightcone` alone to get the full stack.

Generated from [LightconeResearch/agent-skills](https://github.com/LightconeResearch/agent-skills) — the same skills and hooks that ship as the
`lightcone` plugin for Claude Code and Codex, packaged for harnesses that install
from npm. Version 0.0.2 of the plugin.

## OpenCode

Hooks: add the package to `opencode.json` (`~/.config/opencode/opencode.json` for
every project, or a project's own):

```json
{ "$schema": "https://opencode.ai/config.json", "plugin": ["@lightcone-research/lightcone-plugin@0.0.2"] }
```

Skills: `npx skills add https://github.com/LightconeResearch/agent-skills/tree/main/plugins/lightcone -a opencode -g`

## Pi

```bash
pi install npm:@lightcone-research/lightcone-plugin@0.0.2
```

Installs the skills and the hooks together; invoke a skill as `/skill:<name>`.

## Contents

- Skills: `astra`, `lightcone`
- Hooks: the plugin's SessionStart primer and PostToolUse validation, as an OpenCode plugin module (`opencode/index.js`) and a Pi extension (`pi/index.js`). Needs `bash` on PATH; the scripts need `uvx` and say so when it is missing.

Documentation: https://lightconeresearch.github.io/agent-skills/opencode/ and https://lightconeresearch.github.io/agent-skills/pi/ · License: BSD-3-Clause
