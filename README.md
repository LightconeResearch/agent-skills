<div align="center">

# 🔭 Lightcone Research — Agent Skills

**Portable, open-standard skills that teach coding agents the [Lightcone Research](https://github.com/LightconeResearch) stack: [`ASTRA`](skills/astra).**

[![Agent Skills standard](https://img.shields.io/badge/standard-Agent%20Skills-7c3aed?style=for-the-badge)](https://agentskills.io)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-blue?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.2-success?style=for-the-badge)](skills.config.json)

[![Claude Code](https://img.shields.io/badge/Claude%20Code-✓-d97757?style=flat-square&logo=anthropic&logoColor=white)](https://claude.com/claude-code)
[![Codex](https://img.shields.io/badge/Codex-✓-000000?style=flat-square&logo=openai&logoColor=white)](https://github.com/openai/codex)
[![Skills](https://img.shields.io/badge/skills-1-7c3aed?style=flat-square)](#-skills)
[![Plugins](https://img.shields.io/badge/plugins-1-7c3aed?style=flat-square)](#-plugins)

</div>

---

Agent skills for the [Lightcone Research](https://github.com/LightconeResearch)
stack. The skills follow the open
[Agent Skills standard](https://agentskills.io) (a `SKILL.md` plus optional
`references/`, `scripts/`, and `assets/`), so they work across Claude Code, Codex,
and other compatible agents — and are also packaged as Claude Code and Codex
**plugins** for hooks that plain skills can't carry.

> [!TIP]
> **New here?** Get started by running `claude plugin marketplace add LightconeResearch/agent-skills && claude plugin install astra@lightcone-research` and ask your agent to help author an `astra.yaml`.

## 📦 Prerequisites

Some plugins have Python dependencies that install themselves on first use.
The only prerequisite is [uv](https://docs.astral.sh/uv/getting-started/installation/).

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

| Plugin | Skills | Adds |
|---|---|---|
| **`astra`** | `astra` | standalone ASTRA authoring skill; validate-on-save & session-start hooks |

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

## ✨ Skills

| Skill | What it does |
|---|---|
| [`astra`](skills/astra) | Authoring an `astra.yaml` — orientation and judgment (what deserves to be a decision, when to split a sub-analysis); the field-level grammar comes from `astra spec <term>`. |

## 🗂️ Repository layout

```
skills/                     Canonical skills — one dir per skill (single source of truth)
hooks/astra/                ASTRA validate-on-save and activate-on-read hooks
skills.config.json          Source of truth for how skills compose into plugins
scripts/build.mjs           Regenerates every per-target file from the above
scripts/validate.mjs        Frontmatter checks + generated-file drift check (npm test)
.claude-plugin/             Generated — Claude Code marketplace manifest
.agents/plugins/            Generated — Codex marketplace manifest
plugins/                    Generated — self-contained per-plugin dirs both harnesses
                            install (full skills+hooks closure copied from source)
manifest.json               Generated — registry of all skills/plugins
scripts/smoke.mjs           Install smoke tests — real claude/codex + tmux (npm run smoke)
```

The per-target manifests and the `plugins/` tree are **generated** from
`skills.config.json` + `skills/`. Don't edit them by hand — run `npm run build` and
commit the result. `npm test` fails if they drift. See [CONTRIBUTING.md](CONTRIBUTING.md).

## ✅ Verifying install

`npm test` runs frontmatter validation and the generated-file drift check. For the
real thing — installing each plugin into a throwaway environment and confirming it
loads — run the smoke suite (needs `claude`, `codex`, and `tmux` on PATH; no LLM/API
calls):

```bash
npm run smoke            # CLI install (both harnesses) + interactive tmux install (Claude)
npm run smoke -- --cli   # CLI only (hermetic; isolated config dirs)
```

## 📄 License

BSD 3-Clause — see [LICENSE](LICENSE). Copyright (c) 2026, Centre National de la Recherche Scientifique (CNRS) and The Regents of the University of California.

<div align="center">
<sub>Built with ❤️ by <a href="https://github.com/LightconeResearch">Lightcone Research</a> · Skills follow the open <a href="https://agentskills.io">Agent Skills standard</a></sub>
</div>
