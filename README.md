# Lightcone Research — Agent Skills

Agent skills for the [Lightcone Research](https://github.com/LightconeResearch) stack:
the **ASTRA** specification and the **lightcone-cli** (`lc`) project workflow. The
skills follow the open [Agent Skills standard](https://agentskills.io) (a `SKILL.md`
plus optional `references/`, `scripts/`, and `assets/`), so they work across Claude
Code, Codex, Cursor, and other compatible agents — and are also packaged as Claude
Code and Codex **plugins** for the capabilities (hooks, subagents) that plain skills
can't carry.

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

Once installed, plugin skills are namespaced by plugin name: `/lightcone:new`,
`/lightcone:from-code`, `/lightcone:feedback`, and `/astra:astra`. The `lightcone`
plugin depends on `astra`; installing it pulls in the `astra` reference too. This is
the **only** path that ships the SessionStart/PostToolUse hooks and the `lc-extractor`
subagent (used by `new` for literature extraction).

### Codex plugin

```bash
codex plugin marketplace add LightconeResearch/agent-skills
codex /plugins        # browse + install astra / lightcone
```

Codex consumes the bundled skills natively. (Claude-specific hooks and the
`lc-extractor` subagent are not portable to Codex; the skills themselves carry the
core workflow.)

### Private-repo access

While the repo is private, the installer/marketplace commands authenticate with your
existing Git credentials — any one of:

- an authenticated **`gh` CLI** session (`gh auth login`),
- a **`GITHUB_TOKEN`** (or `GH_TOKEN`) env var with `repo` scope, or
- an **SSH** remote (`git@github.com:LightconeResearch/agent-skills.git`) with your key in `ssh-agent`.

## Plugins

| Plugin | Skills (invocation) | Adds |
|---|---|---|
| **`astra`** | `astra` (`/astra:astra`) | — |
| **`lightcone`** | `new` (`/lightcone:new`), `from-code` (`/lightcone:from-code`), `feedback` (`/lightcone:feedback`); depends on `astra` | venv-activation & validate-on-save hooks; `lc-extractor` subagent |

## Skills

| Skill | What it does |
|---|---|
| [`astra`](skills/astra) | Reference for the `astra.yaml` spec — decisions, options, prior insights, findings, evidence, sub-analyses, narrative anchors. |
| [`new`](skills/new) | Scope a new ASTRA analysis from a research question into a full `astra.yaml`. Bundles the full `lc` execution reference at [`references/cli.md`](skills/new/references/cli.md) — commands, the Spec-Code Invariant, status interpretation, failure diagnosis, WRROC export. |
| [`from-code`](skills/from-code) | Bring an existing codebase into ASTRA — scan, spec, parameterize, run. |
| [`feedback`](skills/feedback) | File a bug report against the right Lightcone repo with version/error context. |

## Repository layout

```
skills/                     Canonical skills — one dir per skill (single source of truth)
agents/                     Claude subagents (lc-extractor)
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
