---
name: astra
description: >
  Orientation and judgment for authoring an ASTRA analysis (astra.yaml): what
  the format is for, how to write it for and with a human, what deserves to be
  a decision, and when to split a sub-analysis. Invoke whenever reading,
  writing, or restructuring an astra.yaml spec, deciding whether a methodological
  choice should be a decision, weighing a sub-analysis split, or when the user
  asks about ASTRA. The field-level grammar is not here — it comes from the
  installed tool via `astra spec <term>`.
---

# Authoring ASTRA

## What ASTRA is for

An ASTRA analysis is a structured layer between the code and the paper. A paper
compresses months of work into a linear narrative and erases the structure
underneath: which choices were live, which alternatives were defensible, what
evidence backed each one. ASTRA keeps that structure. An `astra.yaml` names the
inputs a computation depends on, the outputs it produces, and — the part that
matters most — every methodological decision that could plausibly have gone
another way.

Three properties are the whole point, and every judgment below serves them:

- **Provenance-certified.** Every output traces to its inputs, the decisions
  that shaped it, and the recipe that produced it. Every claim traces to
  evidence — a quote in a paper, an artifact from a run. Nothing is asserted
  without a path back to where it came from.
- **Observable.** The full decision space is machine-readable, so alternative
  defensible analyses can be enumerated and run rather than argued about. A
  choice you bury in code is invisible; a choice you name as a decision can be
  swept.
- **Legible.** A person who never saw the work can read the spec and understand
  what was done and why. Legibility is the acceptance test for everything you
  write here.

The structure is **self-similar**: a top-level analysis and a nested
sub-analysis have exactly the same shape, so everything here applies to both.

## The working relationship

You author the spec **for and with a human** — a researcher who owns the
science and will answer for it. That framing decides how you work.

**Consequential choices surface as decisions; they are never made silently.**
When you hit a fork that could move a result — an estimator, a cut, a prior, a
calibration — the move is not to quietly pick the one you'd default to. It is to
make it a `decision` with real `options`, set a `default`, and say why in the
`rationale`. That is how a choice becomes reviewable: the human can see it, agree
or override, and the sweep can explore it later. Silently baking in a defensible
choice is the one failure that ASTRA exists to prevent — it is exactly the
erasure the format is fighting.

**When you are unsure, surface it rather than resolve it.** A decision you
flagged and the human waved through costs a moment. A choice you made silently
that turns out to matter costs the result's credibility. Bias toward making the
choice visible.

**Write the prose as you go.** Each element carries a `description` /
`rationale` / `notes`; the analysis carries a top-level `description`. Fill them
while the reasoning is fresh — a decision without a rationale is a decision no
reviewer can weigh. The point is not documentation for its own sake; it is that
the next reader (often the human, sometimes a later you) can reconstruct the
thinking.

## Judgment

The grammar tells you what is *legal*. Judgment tells you what is *right*. This
is the part no schema can serve.

### What deserves to be a decision

A decision is a methodological choice where a different defensible option could
plausibly change a numerical result. Include it if flipping the choice could
shift a quantitative outcome — even modestly, since small choices compound.
When genuinely in doubt, include it: the cost of a spurious decision is a wasted
option; the cost of a missing one is a silent bake-in.

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
referenced from the recipe; a value you cannot vary from the spec is not one.

### When to split a sub-analysis

Default to a **single analysis**. A sub-analysis is a genuine unit of work —
meaningful inputs, its own decisions, meaningful outputs — that can be
understood and run on its own terms. Split only when one is really present:

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

## Vocabulary index

The field-level grammar — every concept, its fields, constraints, and
cross-references — is served by the installed tool, in sync with the schema
that `astra validate` checks against. Do not carry it in your head or paste it
from memory; read it from the source:

- `astra spec` — the concept map, one line each.
- `astra spec <term>` — one concept in full (description, field table, rules,
  cross-references). The mode to reach for while authoring.
- `astra spec --full` — the entire reference (long).

The concepts, by family:

- **Analysis** — `analysis`, `input`, `output`, `decision`, `option`, `recipe`,
  `resources` (plus the `inputtype` / `outputtype` enums).
- **Universe** — `universe`, `universenode`, `decisionselection`.
- **Insight** — `insight`, `evidence`, `textquoteselector`, `fragmentselector`,
  `insightcollection`.

`references/walkthrough.md` is a ground-up narrative tour of the format, derived
from the astra-spec docs at the pinned version — most useful before there is a
developed astra.yaml to learn from. Once one exists, `astra spec` largely
suffices.

## Prerequisites

Everything here runs through `astra`. The plugin's hooks resolve it for you —
the project venv first, otherwise an ephemeral, dual-pinned `uvx` run that
installs on first use — so no hand install is needed; if `uv` itself is missing,
install it (`curl -LsSf https://astral.sh/uv/install.sh | sh`). Saved ASTRA
files are validated automatically; run `astra validate astra.yaml` yourself
whenever you want to check before saving.
