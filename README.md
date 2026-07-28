<div align="center">

# 🔭 Lightcone Research — Agent Skills

**Portable, open-standard skills that teach coding agents the [Lightcone Research](https://github.com/LightconeResearch) stack — [`ASTRA`](skills/astra), the `lc` project workflow, and scientific paper reproduction.**

[![Agent Skills standard](https://img.shields.io/badge/standard-Agent%20Skills-7c3aed?style=for-the-badge)](https://agentskills.io)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-blue?style=for-the-badge)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.0.2-success?style=for-the-badge)](skills.config.json)

[![Claude Code](https://img.shields.io/badge/Claude%20Code-✓-d97757?style=flat-square&logo=anthropic&logoColor=white)](https://claude.com/claude-code)
[![Codex](https://img.shields.io/badge/Codex-✓-000000?style=flat-square&logo=openai&logoColor=white)](https://github.com/openai/codex)
[![Skills](https://img.shields.io/badge/skills-8-7c3aed?style=flat-square)](#-skills)
[![Plugins](https://img.shields.io/badge/plugins-3-7c3aed?style=flat-square)](#-plugins)

</div>

---

Agent skills for the [Lightcone Research](https://github.com/LightconeResearch)
stack: the **ASTRA** specification, the **lightcone-cli** (`lc`) project workflow,
and scientific paper reproduction. The skills follow the open
[Agent Skills standard](https://agentskills.io) (a `SKILL.md` plus optional
`references/`, `scripts/`, and `assets/`), so they work across Claude Code, Codex,
and other compatible agents — and are also packaged as Claude Code and Codex
**plugins** for the capabilities (hooks, subagents) that plain skills can't carry.

> [!TIP]
> **New here?** Install the [toolchain](#-prerequisites), then `claude plugin marketplace add LightconeResearch/agent-skills && claude plugin install lightcone@lightcone-research` and ask your agent to `/lightcone:new`.

## 📦 Prerequisites

Most of these skills drive the `lc` and `astra` command-line tools, which are **not
bundled** with the skills — they ship the playbook, not the binaries. Install the
toolchain (one package ships both):

```bash
uv tool install lightcone-cli
```

This manual step is a stopgap — the plan is for each skill to install the tools it
needs itself.

## 🧩 Plugins

The `lightcone` and `reproduction` plugins are **self-contained**: each bundles the
full closure of its dependencies, including `astra`'s skill and hooks, so either
installs identically on **Claude Code** and **Codex** without a separate ASTRA
dependency step.

| Plugin | Skills | Bundles | Requires | Adds |
|---|---|---|---|---|
| **`astra`** | `astra` | — | — | standalone ASTRA authoring skill; validate-on-save & activate-on-read hooks (self-installing via `uvx`) |
| **`lightcone`** *(recommended)* | `new`, `report`, `feedback`, `cli` | `astra` | — | session-primer hook (+ astra's validate-on-save / activate-on-read); `lc-extractor` subagent |
| **`reproduction`** | `assess-reproducibility`, `reproduce`, `figure-comparison` | `astra` | — | feasibility triage, end-to-end replication, independent verification, and result comparison |

## 🚀 Install

### Claude Code

**From the terminal:**

```bash
claude plugin marketplace add LightconeResearch/agent-skills
claude plugin install lightcone@lightcone-research
```

**From inside a Claude Code session:**

```
/plugin marketplace add LightconeResearch/agent-skills
/plugin install lightcone@lightcone-research
```

(`/plugin install` opens a details pane; pick a scope — user / project / local —
to confirm.)

### Codex

**From the terminal:**

```bash
codex plugin marketplace add LightconeResearch/agent-skills
codex plugin add lightcone@lightcone-research
```

**From inside a Codex session:**

```
/plugins        # browse astra / lightcone / reproduction
```

### After installing

Plugin skills are namespaced by plugin name: `/lightcone:new`,
`/lightcone:report`, `/lightcone:feedback`, `/lightcone:cli`, and (from the bundled `astra`)
`/lightcone:astra`. The session-primer/validation **hooks** and the `lc-extractor`
**subagent** ride along inside the `lightcone` plugin automatically. Swap
`lightcone` for `astra` or `reproduction` in any command above.

## ✨ Skills

### Core

| Skill | What it does |
|---|---|
| [`astra`](skills/astra) | Authoring an `astra.yaml` — orientation and judgment (what deserves to be a decision, when to split a sub-analysis); the field-level grammar comes from `astra spec <term>`. |
| [`new`](skills/new) | Scope a new ASTRA analysis from a research question — structure inputs/outputs, identify decisions through literature, land `astra.yaml`. |
| [`report`](skills/report) | Author the project's MyST report — prose that references `astra.yaml` elements by path (via the [MySTRA](https://github.com/LightconeResearch/MySTRA) plugin), so write-ups never drift from the analysis. |
| [`cli`](skills/cli) | The `lc` execution reference — spec–code invariant, status interpretation, failure diagnosis. |
| [`feedback`](skills/feedback) | File a bug report against the right Lightcone repo with version/error context. |

### Reproduction

| Skill | What it does |
|---|---|
| [`assess-reproducibility`](skills/assess-reproducibility) | Assess and rank papers by full-replication feasibility, public inputs, and compute requirements. |
| [`reproduce`](skills/reproduce) | Reproduce a scientific paper end to end in ASTRA, including independent verification. |
| [`figure-comparison`](skills/figure-comparison) | Compare reproduced figures, tables, and values against the paper's originals. |

## 🗂️ Repository layout

```
skills/                     Canonical skills — one dir per skill (single source of truth)
agents/                     Claude subagents (lc-extractor)
hooks/<plugin>/             Per-plugin hooks.json + bash scripts (astra: validate-on-save,
                            activate-on-read, pins; lightcone: session primer)
skills.config.json          Source of truth for how skills compose into plugins
scripts/build.mjs           Regenerates every per-target file from the above
scripts/validate.mjs        Frontmatter checks + generated-file drift check (npm test)
.claude-plugin/             Generated — Claude Code marketplace manifest
.agents/plugins/            Generated — Codex marketplace manifest
plugins/                    Generated — self-contained per-plugin dirs both harnesses
                            install (full skills+hooks+agents closure, symlinked to source)
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
