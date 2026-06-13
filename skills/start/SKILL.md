---
name: start
description: >
  Entry point for working with a Lightcone / ASTRA analysis. Inspects the
  project state first, then routes: for an empty or freshly-scaffolded
  directory it scopes a new analysis from your research question; for an
  existing project it summarizes the analysis state (validation,
  materialization, decisions, findings, universes) and helps you choose the
  next step — run or verify outputs, refine decisions, write narrative, or
  publish. Use whenever you start, open, set up, continue, or resume work on
  a lightcone-cli / ASTRA project, or ask "what next" — e.g. "start a
  lightcone analysis", "set up my project", "continue the analysis", "what
  should I do next", or any session opened in a directory that has (or will
  have) an `astra.yaml`.
allowed-tools: Read, Write(astra.yaml), Write(universes/*), Write(CLAUDE.md), Edit(astra.yaml), Edit(universes/*), Edit(CLAUDE.md), Glob, Grep, Bash(astra:*), Bash(lc:*), WebSearch, WebFetch, AskUserQuestion, Agent
---

# /start

The entry point for working with a Lightcone / ASTRA analysis. **Always read the project state first, then route** — don't assume the user is starting fresh. A directory with a substantive `astra.yaml` calls for "what next, given where this analysis stands"; an empty or freshly-scaffolded one calls for scoping a new analysis.

## Prerequisites

This skill uses the `lc` and `astra` CLIs, which are **not bundled with the skill**. Confirm they resolve first — `command -v lc && command -v astra || echo "lightcone-cli toolchain not found"` — and if missing, install the toolchain (one package ships both): `uv tool install lightcone-cli` (or `pipx install lightcone-cli`). New projects start with `lc init <dir>`, which also creates the project venv. Discover command syntax with `--help` rather than guessing. For the full `lc` execution workflow — commands, the Spec-Code Invariant, `lc status` interpretation, failure diagnosis, and WRROC export — read [references/cli.md](references/cli.md).

## Triage: read the project state first

1. **Find the spec.** Look for `astra.yaml` at the working directory root (and note any nested sub-analyses under `analyses/*/astra.yaml`). Use Glob/Read; don't run a full scan yet.
2. **Classify it:**
   - **No `astra.yaml`**, or only the placeholder scaffold `lc init` writes (a single example decision/input/output plus a TODO `narrative` skeleton, no real research content) → **Route A (new project)**.
   - **A real `astra.yaml`** with the user's own decisions/inputs/outputs → **Route B (existing analysis)**.
3. **Gather state (Route B only, before deciding anything):**
   ```bash
   astra validate astra.yaml      # valid, or what's broken
   lc status --json               # ok / stale / missing / alias per output, per universe
   ```
   Also note: how many decisions (and whether any lack evidence), whether `narrative.findings` is still TODO, and whether only `baseline` exists under `universes/` or it's a multiverse.
4. **Announce the state** to the user in 2–3 lines (what the analysis is, validation status, what's materialized vs. pending) before proposing anything. The session-start hook may already have surfaced a status summary — build on it rather than repeating it.

## Route A — set up a new analysis

The project is empty or only scaffolded. Scope the analysis from the user's research question into a validated `astra.yaml` + project `CLAUDE.md`. Follow the full playbook in **[references/new-project.md](references/new-project.md)** — research question → analysis structure → literature & decisions → finalize. Honor its restrictions (you are a specification agent: only `astra.yaml`, `universes/*.yaml`, and `CLAUDE.md`; no implementation code; never read PDFs in the main context — delegate to `lc-extractor`).

## Route B — continue an existing analysis

The project already holds a real analysis. Summarize where it stands (from the Triage state) and route to the next valuable step, **informed by that state** — follow **[references/next-steps.md](references/next-steps.md)**. In short: validation errors come first, then unmaterialized or stale outputs (`lc run`), then evidence/decision gaps, then narrative/findings once results exist, then verification and publishing. Use `AskUserQuestion` to confirm direction when more than one step is reasonable; default your recommendation to the most pressing item the state reveals.

When a chosen next step is itself substantial scoping work (e.g. adding a whole new sub-analysis or a literature deep-dive on a fresh section), reuse the relevant phase from [references/new-project.md](references/new-project.md) rather than reinventing it.
