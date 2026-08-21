# Scoping a new project

Read this when a project has no spec, or only the placeholder `lc init`
scaffolds — the phase where the analysis gets defined and no implementation
code is written yet. For the literature pass inside phase 3, read
`references/literature.md`.

- [Before you start](#before-you-start)
- [1. Research question](#1-research-question)
- [2. Analysis structure](#2-analysis-structure)
- [3. Literature deep dive](#3-literature-deep-dive)
- [4. Finalize](#4-finalize)
- [Creating sub-analyses](#creating-sub-analyses)

## Before you start

Scaffold first if needed: `lc init [DIR]` converges the directory into a
standard project — `astra.yaml` placeholder, `universes/baseline.yaml`, a
dependency-free `pyproject.toml`, `uv.lock`, `.venv`, git + git-annex +
`.datalad/config`, `data/`, `results/`, and a MyST report skeleton
(`myst.yml`, `index.md`). It is idempotent and never overwrites files you
own — safe to re-run any time. It does **not** create `CLAUDE.md`; create
one yourself.

Then build the spec through conversation, updating `astra.yaml` after each
phase. Announce each phase with a short stage banner so the user can follow.

**You are a specification agent in this mode, not an implementation agent** —
create or modify only `astra.yaml`, `universes/*`, and `CLAUDE.md`, and write
no Python/R/implementation code until scoping is done.

## 1. Research question

> "What are you trying to learn? Describe the question in your own words."

Sharpen it: what would a clear answer look like, and why does it matter?
"Analyze this data" is not a research question — push back until it is. Set
`name` in `astra.yaml`. (Leave the scaffolded `description` TODO for the
finalize step — written too early it goes stale.)

## 2. Analysis structure

> "Walk me through your analysis step by step. What goes in, what comes out?"

- **Default to a single analysis.** Split into sub-analyses only when each
  part is genuinely a self-contained product with materially different
  inputs and outputs (training + evaluation is usually *one* analysis — the
  product is the validated estimator). The full splitting judgment is the
  astra skill's; when a split does seem warranted, confirm the stage
  boundaries with the user before restructuring.
- **One output per output.** A single metric, a single plot, or a single
  artifact each — never a bundle like "performance_metrics".

Update `astra.yaml` with `inputs` and `outputs`.

## 3. Literature deep dive

Optional per section. Offer a literature pass; skip straight to decision
identification if declined. The full procedure — collecting papers,
fanning out one subagent per paper, identifying and reviewing decisions —
is in `references/literature.md`. Read it before starting the pass.

Every extracted quote must survive the astra skill's evidence verification
before scoping is done — never fabricate one.

## 4. Finalize

1. Checkpoint: "Anything else that should inform this analysis?"
2. Validate the spec per the astra skill — verifying evidence too, if any
   was extracted — and iterate until clean.
3. Generate only a `baseline` universe unless the user asks for more
   (universe commands: astra skill).
4. Replace the `description:` TODO with a short orientation paragraph now
   that structure is stable.
5. Fill `CLAUDE.md`'s Project Notes with conversation context that isn't in
   the spec.
6. Show a summary table (decisions / outputs / prior insights per section),
   confirm with the user, and recommend `/clear` before implementation.

## Creating sub-analyses

Each sub-analysis is just another `astra.yaml` nested in a directory:

1. Create `analyses/<name>/` with its own `astra.yaml` (and optionally
   `src/`, `universes/baseline.yaml`).
2. Add a `path:` entry under the parent's `analyses:`
   (`analyses: { my_sub: { path: ./analyses/my_sub } }`).
3. Add `<name>: { universe: baseline }` to each existing parent universe
   file.

Wire inputs and decisions to the parent or siblings with `from:` references
— the grammar is in the astra skill's spec reference.
