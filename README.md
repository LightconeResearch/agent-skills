<div align="center">

# 🔭 Lightcone Research — Agent Skills

**Portable, open-standard skills that teach coding agents the [Lightcone Research](https://github.com/LightconeResearch) stack.**

[![Agent Skills standard](https://img.shields.io/badge/standard-Agent%20Skills-7c3aed?style=for-the-badge)](https://agentskills.io)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-blue?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.2-success?style=for-the-badge)](skills.config.json)

[![Claude Code](https://img.shields.io/badge/Claude%20Code-✓-d97757?style=flat-square&logo=anthropic&logoColor=white)](https://claude.com/claude-code)
[![Codex](https://img.shields.io/badge/Codex-✓-000000?style=flat-square&logo=openai&logoColor=white)](https://github.com/openai/codex)
[![OpenCode](https://img.shields.io/badge/OpenCode-✓-1f6feb?style=flat-square)](https://opencode.ai)
[![Pi](https://img.shields.io/badge/Pi-✓-5b21b6?style=flat-square)](https://github.com/badlogic/pi-mono)
[![Skills](https://img.shields.io/badge/skills-2-7c3aed?style=flat-square)](#-skills)
[![Plugins](https://img.shields.io/badge/plugins-2-7c3aed?style=flat-square)](#-plugins)

</div>

---

Agent skills for the [Lightcone Research](https://github.com/LightconeResearch)
stack, packaged as plugins to work across Claude Code, Codex, OpenCode, Pi,
and other agents that read the Agent Skills format.

## 📦 Prerequisites

Some plugins have Python dependencies that install themselves on first use.
The only prerequisite is `uv`: [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/).

## 🛒 Add the marketplace

One-time setup: register this repository as a plugin marketplace in your
harness. It registers under the name `lightcone-research`, which is the
`@lightcone-research` suffix in the install commands below.

OpenCode and Pi have no marketplace step — skip straight to
[Install a plugin](#-install-a-plugin).

<details>
<summary><b>Claude Code</b></summary>

```bash
claude plugin marketplace add LightconeResearch/agent-skills
```

</details>

<details>
<summary><b>Claude App</b></summary>

Open **Customize → Plugins → Add → Add marketplace → Add from repo** and paste
`https://github.com/LightconeResearch/agent-skills`.

</details>

<details>
<summary><b>Codex CLI</b></summary>

```bash
codex plugin marketplace add LightconeResearch/agent-skills
```

</details>

<details>
<summary><b>Codex App</b></summary>

Open **Plugins** from the arrow beside **Create** and add the
`LightconeResearch/agent-skills` marketplace.

</details>

## 🧩 Plugins

| Plugin | Skills | Adds |
|---|---|---|
| **`astra`** | `astra` | authoring guidance for [ASTRA](#-skills) analysis specs (`astra.yaml`); validate-on-save & session-start hooks |
| **`lightcone`** | `lightcone`, `astra` | end-to-end guidance for working on a Lightcone project with the `lc` CLI — scoping, implementation, materialization, publishing. Bundles the `astra` plugin (skill + hooks), so installing `lightcone` alone gets the full stack — don't install `astra` alongside it |

## 🚀 Install a plugin

Plugin skills are namespaced by plugin name: once a plugin is installed, invoke
its skills as `/<plugin>:<skill>` in Claude or `$<plugin>:<skill>` in Codex.
The examples below install `astra`; substitute any plugin from the table above.

<details>
<summary><b>Claude Code</b></summary>

```bash
claude plugin install astra@lightcone-research
```

Then invoke `/astra:astra` in a session.

</details>

<details>
<summary><b>Claude App</b></summary>

In **Customize → Plugins**, choose `astra` from the `lightcone-research`
marketplace, then invoke `/astra:astra`.

</details>

<details>
<summary><b>Codex CLI</b></summary>

```bash
codex plugin add astra@lightcone-research
```

Then invoke the skill in Codex, for example `$astra:astra`.

</details>

<details>
<summary><b>Codex App</b></summary>

Open **Plugins** from the arrow beside **Create**, then search for and install
`astra`. Invoke `/astra:astra`.

</details>

<details>
<summary><b>OpenCode</b></summary>

OpenCode reads skills in the open Agent Skills format directly and installs
plugins from npm, so a plugin arrives in two parts:

```bash
# 1. skills — for every project (installs to ~/.agents/skills/, which OpenCode reads);
#    drop -g for the current project only (./.agents/skills/)
npx skills add https://github.com/LightconeResearch/agent-skills/tree/main/plugins/astra -a opencode -g
```

```json
// 2. hooks — in ~/.config/opencode/opencode.json (or a project's opencode.json);
//    installed automatically at the next start. Keep the version pinned.
{ "$schema": "https://opencode.ai/config.json", "plugin": ["@lightcone-research/astra-plugin@0.0.5"] }
```

`@lightcone-research/<plugin>-plugin` is the plugin's `plugins/<plugin>/`
directory published to npm; its `opencode/index.js` runs the same
validate-on-save and session-start hooks as the Claude Code and Codex packages.
`lightcone-plugin` includes `astra`'s hooks — list one or the other. OpenCode
loads a skill when the task matches its description; you can also just ask it
to "use the astra skill". Details in the
[OpenCode page](https://lightconeresearch.github.io/agent-skills/opencode/).

</details>

<details>
<summary><b>Pi</b></summary>

Pi installs skills and hooks together from the same npm package:

```bash
pi install npm:@lightcone-research/astra-plugin@0.0.5
```

Then invoke `/skill:astra`, or let the agent load it when the task matches.
`lightcone-plugin` ships both skills and includes `astra`'s hooks — install one
or the other. Details in the
[Pi page](https://lightconeresearch.github.io/agent-skills/pi/).

</details>

## ✨ Skills

| Skill | What it does |
|---|---|
| [`astra`](skills/astra) | Teaches the agent to author and revise an `astra.yaml`: the judgment a schema can't carry — what deserves to be a decision, when to split a sub-analysis, how to back claims with verifiable evidence. |
| [`lightcone`](skills/lightcone) | Teaches the agent to work on a Lightcone project at any phase: interview the user to scope a new analysis, orient and summarize when resuming one, and drive the `lc` workflow — integrate recipes, materialize outputs, interpret status, diagnose failures, publish. |

## 📄 License

BSD 3-Clause — see [LICENSE](LICENSE). Copyright (c) 2026, Centre National de la Recherche Scientifique (CNRS) and The Regents of the University of California.

<div align="center">
<sub>Built with ❤️ by <a href="https://github.com/LightconeResearch">Lightcone Research</a> · Skills follow the open <a href="https://agentskills.io">Agent Skills standard</a></sub>
</div>
