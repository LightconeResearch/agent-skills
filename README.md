<div align="center">

# 🔭 Lightcone Research — Agent Skills

**Portable, open-standard skills that teach coding agents the [Lightcone Research](https://github.com/LightconeResearch) stack.**

[![Agent Skills standard](https://img.shields.io/badge/standard-Agent%20Skills-7c3aed?style=for-the-badge)](https://agentskills.io)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-blue?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.2-success?style=for-the-badge)](skills.config.json)

[![Claude Code](https://img.shields.io/badge/Claude%20Code-✓-d97757?style=flat-square&logo=anthropic&logoColor=white)](https://claude.com/claude-code)
[![Codex](https://img.shields.io/badge/Codex-✓-000000?style=flat-square&logo=openai&logoColor=white)](https://github.com/openai/codex)
[![Skills](https://img.shields.io/badge/skills-4-7c3aed?style=flat-square)](#-skills)
[![Plugins](https://img.shields.io/badge/plugins-2-7c3aed?style=flat-square)](#-plugins)

</div>

---

Agent skills for the [Lightcone Research](https://github.com/LightconeResearch)
stack, packaged as plugins to work across Claude Code, Codex,
and other compatible agents.

## 📦 Prerequisites

Some plugins have Python dependencies that install themselves on first use.
The only prerequisite is `uv`: [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/).

## 🛒 Add the marketplace

One-time setup: register this repository as a plugin marketplace in your
harness. It registers under the name `lightcone-research`, which is the
`@lightcone-research` suffix in the install commands below.

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

| Plugin | Skills | Bundles | Adds |
|---|---|---|---|
| **`astra`** | `astra` | — | authoring guidance for [ASTRA](#-skills) analysis specs (`astra.yaml`); validate-on-save & session-start hooks |
| **`reproduction`** | `assess-reproducibility`, `reproduce`, `figure-comparison` | `astra` | feasibility triage, end-to-end replication, independent verification, and result comparison |

Choose one plugin, not both: `astra` provides the ASTRA authoring and
validation skill on its own, while `reproduction` is **self-contained** — it
bundles the `astra` skill and hooks, so it installs identically on Claude Code
and Codex without a separate ASTRA dependency step.

## 🚀 Install a plugin

Plugin skills are namespaced by plugin name: once a plugin is installed, invoke
its skills as `/<plugin>:<skill>` in Claude or `$<plugin>:<skill>` in Codex.
The examples below install `astra`; substitute `reproduction` for the full
reproduction toolkit.

<details>
<summary><b>Claude Code</b></summary>

```bash
claude plugin install astra@lightcone-research
```

Then invoke `/astra:astra` in a session (or `/reproduction:reproduce` after
installing `reproduction`).

</details>

<details>
<summary><b>Claude App</b></summary>

In **Customize → Plugins**, choose `astra` or `reproduction` from the
`lightcone-research` marketplace, then invoke `/astra:astra` or
`/reproduction:reproduce`.

</details>

<details>
<summary><b>Codex CLI</b></summary>

```bash
codex plugin add astra@lightcone-research
```

Then invoke the skill in Codex, for example `$astra:astra` (or
`$reproduction:reproduce` after installing `reproduction`).

</details>

<details>
<summary><b>Codex App</b></summary>

Open **Plugins** from the arrow beside **Create**, then search for and install
`astra` or `reproduction`. Invoke `/astra:astra` or `/reproduction:reproduce`.

</details>

## ✨ Skills

### ASTRA

| Skill | What it does |
|---|---|
| [`astra`](skills/astra) | Teaches the agent to author and revise an `astra.yaml`: the judgment a schema can't carry — what deserves to be a decision, when to split a sub-analysis, how to back claims with verifiable evidence. |

### Reproduction

| Skill | What it does |
|---|---|
| [`assess-reproducibility`](skills/assess-reproducibility) | Assess and rank papers by full-replication feasibility, public inputs, and compute requirements. |
| [`reproduce`](skills/reproduce) | Reproduce a scientific paper end to end in ASTRA, including independent verification. |
| [`figure-comparison`](skills/figure-comparison) | Compare reproduced figures, tables, and values against the paper's originals. |

## 📄 License

BSD 3-Clause — see [LICENSE](LICENSE). Copyright (c) 2026, Centre National de la Recherche Scientifique (CNRS) and The Regents of the University of California.

<div align="center">
<sub>Built with ❤️ by <a href="https://github.com/LightconeResearch">Lightcone Research</a> · Skills follow the open <a href="https://agentskills.io">Agent Skills standard</a></sub>
</div>
