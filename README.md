# Lightcone Research — Agent Skills

Agent skills for the [Lightcone Research](https://github.com/LightconeResearch) stack:
the **ASTRA** specification, the **lightcone-cli** (`lc`) project workflow, and
end-to-end **paper reproduction**. The skills follow the open
[Agent Skills standard](https://agentskills.io) (a `SKILL.md` plus optional
`references/`, `scripts/`, and `assets/`), so they work across Claude Code, Codex,
Cursor, and other compatible agents — and are also packaged as Claude Code and
Codex **plugins** for the capabilities (hooks, subagents) that plain skills can't carry.

> This repository is private for now. All install paths below work against a private
> repo as long as your local Git/GitHub credentials can read it (see
> [Private-repo access](#private-repo-access)).

## Prerequisites

Most of these skills drive the `lc` and `astra` command-line tools, which are **not
bundled** with the skills — they ship the playbook, not the binaries. Install the
toolchain (one package ships both):

```bash
uv tool install lightcone-cli      # preferred
# or: pipx install lightcone-cli
```

Each CLI-dependent skill opens with a short preflight: it checks the tools resolve,
points you here if they don't, and always discovers command syntax via `--help`
rather than guessing. `astra`-only reference skills work without the CLI for reading,
but need it for validation.

## Install

### `npx skills` — any compatible agent (Claude Code, Codex, Cursor, …)

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
subagents. For the venv/validation hooks (`lightcone-core`) and the `lc-extractor`
subagent (`lightcone-reproduction`), use the native plugin paths below.

### Claude Code plugin marketplace

```bash
# In a Claude Code session:
/plugin marketplace add LightconeResearch/agent-skills
/plugin install lightcone-core@lightcone-research
/plugin install lightcone-reproduction@lightcone-research

# Or from the terminal:
claude plugin marketplace add LightconeResearch/agent-skills
claude plugin install lightcone-core@lightcone-research
```

`lightcone-core` depends on `astra`, and `lightcone-reproduction` depends on
`lightcone-core`; installing the higher-level plugin pulls in what it needs. This is
the **only** path that ships the SessionStart/PostToolUse hooks and the `lc-extractor`
subagent.

### Codex plugin

```bash
codex plugin marketplace add LightconeResearch/agent-skills
codex /plugins        # browse + install lightcone-core / lightcone-reproduction
```

Codex consumes the bundled skills natively. (Claude-specific hooks and subagents are
not portable to Codex; the skills themselves carry the full workflow.)

### Private-repo access

While the repo is private, the installer/marketplace commands authenticate with your
existing Git credentials — any one of:

- an authenticated **`gh` CLI** session (`gh auth login`),
- a **`GITHUB_TOKEN`** (or `GH_TOKEN`) env var with `repo` scope, or
- an **SSH** remote (`git@github.com:LightconeResearch/agent-skills.git`) with your key in `ssh-agent`.

## Plugins

| Plugin | Skills | Adds |
|---|---|---|
| **`astra`** | `astra` | — |
| **`lightcone-core`** | `lc-cli`, `lc-new`, `lc-from-code`, `lc-feedback` (+ `astra`) | venv-activation & validate-on-save hooks |
| **`lightcone-reproduction`** | `lc-from-paper`, `ralph`, `narrative`, `paper-extraction`, `figure-comparison`, `check-sentence-by-sentence` (+ core) | `lc-extractor` subagent |

## Skills

| Skill | What it does |
|---|---|
| [`astra`](skills/astra) | Reference for the `astra.yaml` spec — decisions, options, prior insights, findings, evidence, sub-analyses, narrative anchors. |
| [`lc-cli`](skills/lc-cli) | Reference for the `lc` workflow — commands, the Spec-Code Invariant, status interpretation, failure diagnosis, multiverse runs, WRROC export. |
| [`lc-new`](skills/lc-new) | Scope a new ASTRA analysis from a research question into a full `astra.yaml`. |
| [`lc-from-code`](skills/lc-from-code) | Bring an existing codebase into ASTRA — scan, spec, parameterize, run. |
| [`lc-feedback`](skills/lc-feedback) | File a bug report against the right Lightcone repo with version/error context. |
| [`lc-from-paper`](skills/lc-from-paper) | Reproduce a published paper end-to-end (orchestrates the reproduction bundle). |
| [`ralph`](skills/ralph) | Author a constitution and run a ralph loop — adaptive, long-running autonomous iteration. |
| [`narrative`](skills/narrative) | Author the `narrative:` prose and decision `rationale:` throughout an `astra.yaml`. |
| [`paper-extraction`](skills/paper-extraction) | Turn an arXiv ID or DOI into a standardized, indexed `work/reference/` substrate. |
| [`figure-comparison`](skills/figure-comparison) | Build a self-contained HTML side-by-side of original vs replicated figures/tables/numerics. |
| [`check-sentence-by-sentence`](skills/check-sentence-by-sentence) | Audit paper claims against code locations (`file:line` or `NOT FOUND`). |

## Repository layout

```
skills/                     Canonical skills — one dir per skill (single source of truth)
agents/                     Claude subagents (e.g. lc-extractor)
hooks/                      Plugin hooks.json + bash scripts (venv, validation, session primer)
skills.config.json          Source of truth for how skills compose into plugins
scripts/build.mjs           Regenerates every per-target file from the above
scripts/validate.mjs        Frontmatter checks + generated-file drift check (npm test)
.claude-plugin/             Generated — Claude Code marketplace manifest
.agents/plugins/            Generated — Codex marketplace manifest
plugins/                    Generated — Codex per-plugin dirs (skills symlinked back to skills/)
manifest.json               Generated — registry of all skills/plugins
```

The per-target manifests and the `plugins/` tree are **generated** from
`skills.config.json` + `skills/`. Don't edit them by hand — run `npm run build` and
commit the result. `npm test` fails if they drift. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

BSD 3-Clause — see [LICENSE](LICENSE).
