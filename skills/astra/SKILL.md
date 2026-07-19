---
name: astra
description: >
  Orientation and judgment for authoring an ASTRA analysis (astra.yaml): what
  the format is for, what deserves to be a decision, when to split a
  sub-analysis, and how to write it for and with a human. Invoke whenever
  reading, writing, or restructuring an astra.yaml spec, deciding whether a
  methodological choice should be a decision, weighing a sub-analysis split, or
  when the user asks about ASTRA.
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

## Orient with `astra spec`

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
fixed by the analysis structure.

**Every decision must be parameterized in code — never hardcode a decision
value.** The recipe's `command:` references it via `{decisions.<id>}`. When the
code cannot yet vary a consequential value, that is a prompt to parameterize it
into a decision, not to leave it out.

Decisions may carry an optional `tags:` list for grouping (e.g.
`[preprocessing]`, `[physics]`, `[stats]`). Keep the tag vocabulary small and
consolidated — reuse existing tags rather than minting new ones: tags exist for
cross-cutting views over a shared decision space, and that view fragments when
every decision invents its own label.

### Recipes

ASTRA is asset-centric: the **Output** declares its provenance (`inputs`,
`decisions`) and when it's active (`when`); the recipe is pure *how*. Text
outside `{...}` placeholders is literal command text and isn't validated —
static constants (`--max-iter 1000`), per-output specialisations, and shell
features (`${VAR}`, pipes, redirects) all live as plain text; there is no
separate `params` channel.

### When to split a sub-analysis

Each ASTRA file — root or nested — represents a **unit of work**: meaningful
inputs, its own decisions, meaningful outputs; something that can be
understood, run, and evaluated on its own terms, and is a reasonable amount of
work to consider at once. Default to a **single analysis**; split only when a
genuine unit is really present:

- **Decision ownership** — a stage has its own decisions that could vary,
  cleanly scoped to it. Shared decisions live at the parent and are inherited;
  stage-specific ones live in the sub-analysis. If you cannot assign decisions
  to levels cleanly, the split is wrong.
- **Reusability** — someone on a different paper could take this stage's output
  as-is (a cleaned catalog, a trained emulator, a set of mocks).
- **Side quests** — an independent investigation (a calibration, a simulation
  study, a diagnostic) with its own inputs, outputs, and code. That is a
  sub-analysis, not a universe; universes are different option selections on
  the *same* pipeline.

Two calibrating examples. A paper that builds mock catalogs and then trains a
photo-z network on them splits naturally in two: the noise-model and
selection-function decisions belong to mock-building, the architecture and
training decisions to estimation — and someone else could reuse the mocks. A
paper that downloads galaxies, applies quality cuts, corrects for extinction,
and fits a Schechter function does not split: five steps, but one objective,
shared decisions, one end product.

A side quest's conclusions flow back through evidence: reference its output as
artifact evidence in a `prior_insights` entry (e.g.
`artifact: "build_mocks.noise_diagnostics"`) and cite that insight from the
decision it informs — a traceable chain from sub-analysis conclusion to
downstream choice.

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

## Universes

A universe selects one option per decision — a defensible alternative analysis
path. Bug fixes and refactors are normal commits, not universes. Universe IDs
use `^[a-z][a-z0-9_-]*$` (hyphens allowed, unlike other ASTRA IDs).

**Adding a new decision** touches every universe: (1) add it to the spec with
options/default/rationale, (2) add the parameter to code, (3) add it to all
existing universe files with the default, (4) create the new universe,
(5) `astra validate`.

## The working relationship

You author the spec **for and with a human** — a researcher who owns the
science and will answer for it. That framing decides how you work.

**Consequential choices surface as decisions; they are never made silently.**
When you hit a fork that could move a result — an estimator, a cut, a prior, a
calibration — do not quietly pick the one you'd default to. Make it a
`decision` with real `options`, set a `default`, and say why in the
`rationale`. The human can then see it, agree or override, and the sweep can
explore it later. Even apparently defensible choices must be recorded in
ASTRA; when you are unsure whether a choice matters, encode it rather than
resolve it silently.

**Write the prose as you go.** Inputs, outputs, and options carry a
`description`; decisions carry a `rationale`. Fill them while the reasoning is
fresh, so the next reader can reconstruct the thinking. Fuller write-ups —
reports with figures, citations, multi-page structure — can be maintained
outside ASTRA, referencing the spec's elements rather than restating them.

## Adding a paper as prior insight

Always run `astra paper add <doi>` when you cite a paper. Three steps wire a
paper into the analysis:

1. **Cache the PDF** — `astra paper add <doi>` downloads it to the project's
   paper cache. Pass `--pdf PATH` if you already have a local copy, or
   `--version N` for a specific arXiv version.
2. **Add a `prior_insights:` entry** that cites the DOI (and optionally
   `version`) under `evidence:`. The `quote.exact` text must match the PDF
   verbatim; optional `prefix`/`suffix` (~20–100 chars on either side)
   disambiguate when the exact string occurs more than once.
3. **Verify** — `astra paper verify-quotes <doi>` for one paper, or
   `astra validate astra.yaml --verify-evidence` to check every quote in the
   spec. A wrong `exact` string fails validation.

`astra paper list` shows what's cached; `astra paper path <doi>` prints the PDF
path so you can open it for review.

## CLI reference

`astra` validates and inspects; it never executes recipes. The separation is
deliberate — the spec stays stable while agents and execution layers evolve,
and the choice of runner stays yours — so don't encode runner-specific behavior
into the spec.

```bash
astra init [DIRECTORY]                          # Scaffold a new analysis
astra validate astra.yaml                       # Validate (run after every change)
astra validate astra.yaml --verify-evidence     # + verify insight quotes against PDFs
astra spec [TERM|--full]                        # Schema reference (see above)
astra info [--decisions|--inputs|--outputs]     # Analysis summary / element details
astra universe generate -n NAME [-d "desc"]     # Generate universe from defaults
astra universe check universes/x.yaml           # Check universe constraints
astra viz [--fmt ascii|mermaid]                 # Visualize decision space
astra paper add DOI [--version N] [--pdf PATH]  # Cache a paper for evidence checks
astra paper list                                # List cached papers
astra paper show DOI                            # Show metadata for a cached paper
astra paper path DOI [--version N]              # Print the cached PDF's path
astra paper verify-quotes DOI                   # Batch-verify quotes; reads {"quotes":[...]} JSON from stdin
```

## References

- `references/walkthrough.md` — a ground-up, tutorial-style tour of the format.
  Long, so not for every touch — but worth reading before any substantial
  authoring or restructuring work; for small edits to a developed astra.yaml,
  `astra spec` suffices.
