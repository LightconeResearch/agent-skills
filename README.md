<div align="center">

# 🔭 Lightcone Research — Agent Skills

**Portable, open-standard skills that teach coding agents the [Lightcone Research](https://github.com/LightconeResearch) stack — the [`ASTRA`](skills/astra) spec and the `lc` project workflow.**

[![Agent Skills standard](https://img.shields.io/badge/standard-Agent%20Skills-7c3aed?style=for-the-badge)](https://agentskills.io)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-blue?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.2.0-success?style=for-the-badge)](skills.config.json)

[![Claude Code](https://img.shields.io/badge/Claude%20Code-✓-d97757?style=flat-square&logo=anthropic&logoColor=white)](https://claude.com/claude-code)
[![Codex](https://img.shields.io/badge/Codex-✓-000000?style=flat-square&logo=openai&logoColor=white)](https://github.com/openai/codex)
[![Skills](https://img.shields.io/badge/skills-10-7c3aed?style=flat-square)](#-skills)
[![Plugins](https://img.shields.io/badge/plugins-3-7c3aed?style=flat-square)](#-plugins)

</div>

---

Agent skills for the [Lightcone Research](https://github.com/LightconeResearch) stack:
the **ASTRA** specification and the **lightcone-cli** (`lc`) project workflow. The
skills follow the open [Agent Skills standard](https://agentskills.io) (a `SKILL.md`
plus optional `references/`, `scripts/`, and `assets/`), so they work across Claude
Code, Codex, and other compatible agents — and are also packaged as Claude
Code and Codex **plugins** for the capabilities (hooks, subagents) that plain skills
can't carry.

> [!TIP]
> **New here?** Install the [toolchain](#-prerequisites), then `npx skills add LightconeResearch/agent-skills` and ask your agent to `/lightcone:lc-new`.

> [!NOTE]
> **Skill content is mid-migration.** These skills were just moved out of `lightcone-cli` into this repo; their packaging is settled but their bodies are being raised to high quality one at a time. Expect rough edges — especially in the `lightcone-experimental` plugin.

## 📦 Prerequisites

Most of these skills drive the `lc` and `astra` command-line tools, which are **not
bundled** with the skills — they ship the playbook, not the binaries. Install the
toolchain (one package ships both):

```bash
uv tool install lightcone-cli
```

## 🚀 Install

### `npx skills` — any compatible agent (Claude Code, Codex, …)

```bash
# Everything
npx skills add LightconeResearch/agent-skills

# A single skill
npx skills add LightconeResearch/agent-skills --skill astra

# Target a specific agent
npx skills add LightconeResearch/agent-skills -a codex
npx skills add LightconeResearch/agent-skills -a claude-code
```

`npx skills` installs the `SKILL.md` trees only — it does **not** install hooks or
subagents. For the venv/validation hooks and the `lc-extractor` subagent (both in
`lightcone`), use the native plugin paths below.

### Claude Code plugin marketplace

```bash
# In a Claude Code session:
/plugin marketplace add LightconeResearch/agent-skills
/plugin install lightcone@lightcone-research

# Or from the terminal:
claude plugin marketplace add LightconeResearch/agent-skills
claude plugin install lightcone@lightcone-research
```

Once installed, plugin skills are namespaced by plugin name: `/lightcone:lc-new`,
`/lightcone:lc-feedback`, `/lightcone:lc-cli`, and `/astra:astra`. The `lightcone`
plugin depends on `astra`; installing it pulls in the `astra` reference too. Add
`/plugin install lightcone-experimental@lightcone-research` for the opt-in
experimental skills.

### Codex plugin

```bash
codex plugin marketplace add LightconeResearch/agent-skills
codex /plugins        # browse + install astra / lightcone / lightcone-experimental
```

### Private-repo access

While the repo is private, the installer/marketplace commands authenticate with your
existing Git credentials — any one of:

- an authenticated **`gh` CLI** session (`gh auth login`),
- a **`GITHUB_TOKEN`** (or `GH_TOKEN`) env var with `repo` scope, or
- an **SSH** remote (`git@github.com:LightconeResearch/agent-skills.git`) with your key in `ssh-agent`.

## 🧩 Plugins

| Plugin | Skills (invocation) | Adds |
|---|---|---|
| **`astra`** | `astra` (`/astra:astra`) | — standalone; use ASTRA without the rest of the stack |
| **`lightcone`** | `lc-new`, `lc-feedback`, `lc-cli`; depends on `astra` | venv-activation & validate-on-save hooks; `lc-extractor` subagent |
| **`lightcone-experimental`** | `lc-from-paper`, `lc-from-code`, `paper-extraction`, `ralph`, `check-sentence-by-sentence`, `figure-comparison`; depends on `lightcone` | opt-in; under active development |

## ✨ Skills

### Core

| Skill | What it does |
|---|---|
| [`astra`](skills/astra) | Reference for the `astra.yaml` spec — decisions, options, prior insights, findings, evidence, sub-analyses, composition. |
| [`lc-new`](skills/lc-new) | Scope a new ASTRA analysis from a research question — structure inputs/outputs, identify decisions through literature, land `astra.yaml`. |
| [`lc-cli`](skills/lc-cli) | The `lc` execution reference — spec–code invariant, status interpretation, failure diagnosis. |
| [`lc-feedback`](skills/lc-feedback) | File a bug report against the right Lightcone repo with version/error context. |

### Experimental

| Skill | What it does |
|---|---|
| [`lc-from-paper`](skills/lc-from-paper) | Reproduce a paper end-to-end into an ASTRA analysis (staged reproduction workflow). |
| [`lc-from-code`](skills/lc-from-code) | Import an existing code repository into an ASTRA analysis. |
| [`paper-extraction`](skills/paper-extraction) | Extract literature substrate — claims and verbatim quotes — from a paper's source. |
| [`ralph`](skills/ralph) | Autonomous constitution-driven iteration loop for long-running reproduction work. |
| [`check-sentence-by-sentence`](skills/check-sentence-by-sentence) | Verify a manuscript sentence by sentence against its sources. |
| [`figure-comparison`](skills/figure-comparison) | Compare reproduced figures against the paper's originals. |

## 🗂️ Repository layout

```
skills/                     Canonical skills — one dir per skill (single source of truth)
agents/                     Claude subagents (lc-extractor)
hooks/                      Plugin hooks.json + bash scripts (venv, validation, session primer)
skills.config.json          Source of truth for how skills compose into plugins
scripts/build.mjs           Regenerates every per-target file from the above
scripts/validate.mjs        Frontmatter checks + generated-file drift check (npm test)
.claude-plugin/             Generated — Claude Code marketplace manifest
.agents/plugins/            Generated — Codex marketplace manifest
plugins/                    Generated — Codex per-plugin dirs (skills + hooks symlinked back to source)
manifest.json               Generated — registry of all skills/plugins
```

The per-target manifests and the `plugins/` tree are **generated** from
`skills.config.json` + `skills/`. Don't edit them by hand — run `npm run build` and
commit the result. `npm test` fails if they drift. See [CONTRIBUTING.md](CONTRIBUTING.md).

## 📄 License

BSD 3-Clause — see [LICENSE](LICENSE). Copyright © 2026 Centre National de la Recherche Scientifique (CNRS).

<div align="center">
<sub>Built with ❤️ by <a href="https://github.com/LightconeResearch">Lightcone Research</a> · Skills follow the open <a href="https://agentskills.io">Agent Skills standard</a></sub>
</div>
