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

## Before you start

`lc init [DIR]` scaffolds the project — spec placeholder, baseline universe,
uv project, git repository (with `data/` and `results/` backed by git-annex,
so a plain `git add` there stores the bytes properly), and a MyST report. It
is idempotent, never overwrites what you own, and does **not** create
`CLAUDE.md`; you write that at finalize.

Build the spec through conversation, writing to `astra.yaml` after each
phase. Announce each phase with its banner so the user can follow.

**You are a specification agent in this mode, not an implementation agent** —
create or modify only `astra.yaml`, `universes/*`, and `CLAUDE.md`, and write
no Python/R/implementation code until scoping is done.

## 1. Research question

Stage banner: **RESEARCH QUESTION**

> "What are you trying to learn? Describe the question in your own words."

Sharpen it: what would a clear answer look like, and why does it matter?
"Analyze this data" is not a research question — push back until it is. Set
`name` in `astra.yaml`. (Leave the scaffolded `description` TODO for the
finalize step — written too early it goes stale.)

## 2. Analysis structure

Stage banner: **ANALYSIS STRUCTURE**

> "Walk me through your analysis step by step. What goes in, what comes out?"

- **Scope one analysis, flat.** However many stages the work has, they
  are outputs of this one analysis — training + evaluation is a single
  analysis, the product being the validated estimator.
- **One output per output.** A single metric, a single plot, or a single
  artifact each — never a bundle like "performance_metrics". This is
  enforced, not advisory: `lc` writes each output to one file,
  `results/<universe>/<id>.<format>`, so give every output a `format:` (its
  file extension) as you declare it, and split anything that wanted to be
  two files into two outputs.

Update `astra.yaml` with `inputs` and `outputs`.

## 3. Literature deep dive

Stage banner: **DEEP DIVE — [SECTION NAME]**

Optional per section. Offer a literature pass; skip straight to decision
identification if declined. The full procedure — collecting papers,
fanning out one subagent per paper, identifying and reviewing decisions —
is in `references/literature.md`. Read it before starting the pass.

Every extracted quote must survive the astra skill's evidence verification
before scoping is done — never fabricate one.

## 4. Finalize

Stage banner: **FINALIZING**, and **SPECIFICATION COMPLETE** when done.

1. Checkpoint: "Anything else that should inform this analysis?"
2. Validate the spec per the astra skill — verifying evidence too, if any
   was extracted — and iterate until clean.
3. Generate only a `baseline` universe unless the user asks for more
   (universe commands: astra skill).
4. Replace the `description:` TODO with a short orientation paragraph now
   that structure is stable — what the analysis is and how its pieces fit
   together. Keep it brief; per-element prose belongs on each input, output,
   decision and option.
5. **Repoint the report.** `lc init` scaffolds `index.md` against the
   *placeholder* spec: it references `decisions.example_method` (both an
   inline `{astra}` mention and an `:::{astra}` block) and
   `outputs.main_result`. Those ids no longer exist once scoping has
   replaced the boilerplate. Swap them for
   one representative top-level decision id and one representative
   top-level output id from the finished spec. **Only the reference ids** —
   leave the TODO narrative under Introduction / Methods / Results for the
   user to write.
6. Write `CLAUDE.md`. It carries what the spec cannot: how to work in this
   project, and the conversation context that would be lost after `/clear`.
   A useful one has a short orientation paragraph (what the analysis is,
   where the spec lives), the handful of commands this project actually uses
   day to day, and a `## Project Notes` section holding the scoping
   outcome — constraints the user mentioned, avenues considered and
   rejected, data quirks. The spec stays the source of truth for structure,
   decisions and evidence; don't restate it here.
7. Show a summary table, confirm with the user, and recommend `/clear`
   before implementation — everything needed to continue is now in
   `astra.yaml` and `CLAUDE.md`.

   ```
   | Decisions | Outputs | Prior insights |
   |-----------|---------|----------------|
   | 3         | 2       | 5              |
   ```

