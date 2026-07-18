---
name: astra
description: >
  Orientation and judgment for authoring an ASTRA analysis (astra.yaml): what
  the format is for, what deserves to be a decision, when to split a
  sub-analysis, and how to write it for and with a human. Invoke whenever
  reading, writing, or restructuring an astra.yaml spec, deciding whether a
  methodological choice should be a decision, weighing a sub-analysis split, or
  when the user asks about ASTRA. The field-level grammar is not here — it
  comes from the installed tool via `astra spec <term>`.
---

# Authoring ASTRA

## What ASTRA is for

An ASTRA analysis is an intermediate layer of abstraction between code and
paper: a machine-readable record of the inputs, outputs, and every
consequential methodological decision — with its reasoning — at the level
needed to make the scientific claims verifiable and reproducible. The goal is
to make the full decision space explicit, so that alternative defensible
choices can be systematically explored rather than silently baked in.

An `astra.yaml` spec captures this for a single unit of work. The structure is
**self-similar**: a top-level analysis and a nested sub-analysis have exactly
the same shape. Everything here applies equally to both.

## Judgment

### What deserves to be a decision

A decision is a methodological choice where a different defensible option could
plausibly change a numerical result — even modestly, since small choices
compound. When in doubt, include it.

**These are decisions:** algorithmic choices (MCMC vs optimization, KDE vs
histogram); numerical parameters and thresholds (sigma-clip level, bin width,
convergence tolerance); statistical method (bootstrap vs analytic errors,
Bayesian vs frequentist); data selection (quality cuts, magnitude limits,
spatial masks); corrections and calibrations (which reddening law, which
zero-point, which prior).

**These are not.** Tooling choices that produce identical numbers (language,
framework, file format, parallelization) are not decisions — they cannot change
a result. Fixed constraints with no live alternative ("use the data that
exists") are not decisions. And *what to produce* is not a decision: decisions
govern *how* an output is computed, not *which* outputs exist — the output set is
fixed by the analysis structure. A decision must be parameterized in code and
referenced from the recipe; when the code cannot yet vary a consequential
value, that is a prompt to parameterize it into a decision, not to leave it
out.

### When to split a sub-analysis

Default to a **single analysis**. A sub-analysis is a genuine unit of work —
meaningful inputs, its own decisions, meaningful outputs — that can be
understood and run on its own terms, and is a reasonable amount of work to
consider at once. Split only when one is really present:

- **Decision ownership** — a stage has its own decisions that could vary,
  cleanly scoped to it. Shared decisions live at the parent and are inherited;
  stage-specific ones live in the sub-analysis. If you cannot assign decisions
  to levels cleanly, the split is wrong.
- **Reusability** — someone on a different paper could take this stage's output
  as-is (a cleaned catalog, a trained emulator, a set of mocks).
- **Side quests** — an independent investigation (a calibration, a simulation
  study, a diagnostic) with its own inputs, outputs, and code. That is a
  sub-analysis, not a universe; universes are different option selections on the
  *same* pipeline.

If boundaries are unclear, **start flat and split later**, when separate stage
outputs, explicit inherited links, and clear per-level decision ownership have
actually emerged. Splitting a working flat analysis is easy; merging a broken
hierarchy is not.

### Anti-patterns

- **Splitting by script** instead of by analytical unit.
- **Zero-decision sub-analyses** that only pass data through — make those output
  recipes in the parent.
- **Premature splitting** — hierarchy invented before the boundaries are real.
- **Forcing a linear DAG** — independent stages wired in sequence just because
  the paper narrated them that way.
- **The silent default** — the choice made in code that should have been a
  decision. The worst one, because nothing flags it.

## The working relationship

You author the spec **for and with a human** — a researcher who owns the
science and will answer for it. That framing decides how you work.

**Consequential choices surface as decisions; they are never made silently.**
When you hit a fork that could move a result — an estimator, a cut, a prior, a
calibration — do not quietly pick the one you'd default to. Make it a
`decision` with real `options`, set a `default`, and say why in the
`rationale`. The human can then see it, agree or override, and the sweep can
explore it later. Even apparently defensible choices must be recorded in ASTRA.

**When you are unsure whether a choice matters, encode it in ASTRA rather than
resolve it silently.**

**Write the prose as you go.** Inputs, outputs, and options carry a
`description`; decisions carry a `rationale`. Fill them while the reasoning is
fresh, so the next reader can reconstruct the thinking.

## Vocabulary index

The installed `astra` CLI is the ground truth for the format: the field-level
grammar — every concept, its fields, constraints, and cross-references — is
served in sync with the schema that `astra validate` checks against (saved
files are validated automatically). Do not begin writing or editing an
astra.yaml until you have a clear understanding of the needed concepts and the
relations between them — begin by calling `astra spec`:

- `astra spec` — the concept map, one line each.
- `astra spec <term>` — one concept in full (description, field table, rules,
  cross-references). The mode to reach for while authoring.
- `astra spec --full` — the entire reference (long).

Concepts fall into three families — analysis, universe, insight — but read them
from `astra spec`, not here.

`references/walkthrough.md` is a ground-up, tutorial-style tour of the format.
Most useful before there is a developed astra.yaml to learn from; once one
exists, `astra spec` largely suffices.
