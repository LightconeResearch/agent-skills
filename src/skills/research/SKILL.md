---
name: research
description: >
  Scoping interview for a new scientific analysis: sharpen the research
  question, walk the analysis structure, offer a literature deep dive,
  then finalize. Parked here while the lightcone skill is trimmed to
  mechanics; not yet part of any plugin. Use only when the user explicitly
  asks for a scoping interview. Project setup, `lc`, and the astra.yaml
  format are the lightcone and astra skills' — this one repeats none of it.
---

# Scoping a new analysis

Read this when the user wants an analysis defined through conversation
before any implementation code is written. The mechanics — `lc init`, the
astra.yaml format, universe generation, `AGENTS.md` — are the lightcone and
astra skills'; this skill carries only the interview.

- [1. Research question](#1-research-question)
- [2. Analysis structure](#2-analysis-structure)
- [3. Literature deep dive](#3-literature-deep-dive)
- [4. Finalize](#4-finalize)

Build the spec through conversation, writing to `astra.yaml` after each
phase. Announce each phase with its banner so the user can follow.

**You are a specification agent in this mode, not an implementation agent** —
create or modify only `astra.yaml`, `universes/*`, and `AGENTS.md`, and write
no Python/R/implementation code until scoping is done.

## 1. Research question

Stage banner: **RESEARCH QUESTION**

> "What are you trying to learn? Describe the question in your own words."

Sharpen it: what would a clear answer look like, and why does it matter?
"Analyze this data" is not a research question — push back until it is. Set
`name` in `astra.yaml`. (Leave the scaffolded empty `description` for the
finalize step — written too early it goes stale.)

## 2. Analysis structure

Stage banner: **ANALYSIS STRUCTURE**

> "Walk me through your analysis step by step. What goes in, what comes out?"

- **Scope one analysis, flat.** However many stages the work has, they
  are outputs of this one analysis — training + evaluation is a single
  analysis, the product being the validated estimator.
- **One output per output.** A single metric, a single plot, or a single
  artifact each — never a bundle like "performance_metrics". Give every
  output a `format:` (its file extension) as you declare it, and split
  anything that wanted to be two files into two outputs.

Update `astra.yaml` with `inputs` and `outputs`.

## 3. Literature deep dive

Stage banner: **DEEP DIVE — [SECTION NAME]**

Optional per section. Offer a literature pass; skip straight to decision
identification if declined. When a pass is worth proposing, what makes a
paper relevant, and how to identify decisions from the papers:
`references/literature.md`. The procedure — collecting papers, fanning out
one subagent per paper, writing the insights — is the lightcone skill's
`references/literature.md`.

Every extracted quote must survive evidence verification before scoping is
done — never fabricate one.

### Identify decisions

Per `references/literature.md`, from the conversation *and* the papers.
Write candidates to `astra.yaml` as a batch for review; keep the chat output
to a summary with ids.

### Review

Confirm or set each decision's `default`, keep the option structure and its
evidence links, and drop any decision the user rejects.

## 4. Finalize

Stage banner: **FINALIZING**, and **SPECIFICATION COMPLETE** when done.

1. Checkpoint: "Anything else that should inform this analysis?"
2. Regenerate the baseline universe, validate, fill in `description:`, and
   write `AGENTS.md` — the steps are the lightcone skill's
   *Start a new project*.
3. Show a summary table and confirm with the user. Scoping is done:
   everything needed to carry the work into implementation is now in
   `astra.yaml` and `AGENTS.md`.

   ```
   | Decisions | Outputs | Prior insights |
   |-----------|---------|----------------|
   | 3         | 2       | 5              |
   ```
