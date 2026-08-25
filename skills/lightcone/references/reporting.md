# The report

Read this when the project's report is in play — writing it, previewing it,
or keeping it honest after the analysis moved.

`lc init` scaffolds a MyST project next to the spec: `myst.yml` (which loads
the **MySTRA** plugin) and `index.md`. MySTRA resolves `{astra}` paths
against `astra.yaml`, so the report *references* the analysis instead of
restating it — one source of truth for every number, figure and decision.
Docs: <https://lightconeresearch.github.io/MySTRA/>.

- [Whose report it is](#whose-report-it-is)
- [The golden rule](#the-golden-rule)
- [Preview it](#preview-it)
- [Paths](#paths)
- [The five surfaces](#the-five-surfaces)
- [Cross-references](#cross-references)
- [Universes and materialization](#universes-and-materialization)
- [Multi-page reports](#multi-page-reports)
- [Keeping it in sync](#keeping-it-in-sync)

## Whose report it is

The prose is the author's. Ask what they want written, and follow their lead
on structure, voice and what to claim.

**Absent instructions, keep the report in sync with the analysis** — that is
the standing job, and it needs no permission. An output added, renamed or
removed, a decision whose options changed, a finding that gained evidence:
each one lands in the same change as its reference in the report. Never
invent prose, and never write a claim the analysis does not support — if
what the report says is contradicted by what the analysis now shows, say so
to the author rather than quietly rewriting their argument.

## The golden rule

**Never hard-type a measured number, restate a decision, or re-describe an
output.** Reference it. A hard-typed number is correct until the next
`lc materialize` and wrong after it, silently — which is the failure this
whole arrangement exists to prevent.

## Preview it

Needs Node ≥ 18 and the MyST CLI (`npm i -g mystmd` — the user's machine,
so ask before installing).

```bash
myst start          # live preview on http://localhost:3000
myst build --html   # static site in _build/html/ (gitignored)
```

Preview watches the Markdown files, not `astra.yaml` — after editing the
spec, re-save any `.md` to refresh.

Unresolved paths and bad value lookups do **not** break the build: they
render as visible error tokens (`⟨value: no column "alpha2"⟩`) or error
admonitions and the page builds around them. So previewing is how you find
them — a report that builds is not a report that resolved.

## Paths

Dot-separated, mirroring `astra.yaml`, and always resolved **from the root
analysis** so a path means the same thing on every page.

The collections: `inputs`, `outputs`, `decisions`, `findings`,
`prior_insights`, `analyses`, `universes`.

| Path | What it addresses |
|---|---|
| `outputs.hubble_diagram` | one output |
| `outputs` | the whole collection — renders as a registry |
| `decisions.algorithm.gp` | an option of a decision |
| `findings.sig.fig1` | an evidence record of a finding |
| `reconstruction.outputs.xi` | an output inside a sub-analysis |
| `clustering.correlation.outputs.xi` | nested to any depth |

Leading segments step into sub-analyses (no `analyses.` prefix needed); the
first collection keyword fixes the target. Children — decision options,
evidence records — omit their own collection keyword, since each parent has
exactly one kind of child. Labels come from a declared `label:` where there
is one, otherwise the id.

## The five surfaces

| Surface | Use |
|---|---|
| ``{astra}`outputs.fit` `` | mention an element inline; ``{astra}`our method <decisions.algorithm>` `` for custom text |
| ``{astra:value}`outputs.fit_params` `` | interpolate a measured number into prose |
| ``{astra:ref}`outputs.fit` `` | numbered cross-reference ("Figure 3"); `%s` is the number's placeholder in custom text |
| ``{astra:cite}`findings.sig` `` | citation from DOI-backed evidence — `(Author et al., Year)`; `{astra:cite:t}` for the textual `Author et al. (Year)`. Findings and prior insights only |
| `:::{astra} outputs.fit` … `:::` | embed the element as a block |

`{astra:value}` options: `col=<column>` (which column, required for tables),
`where="<key>=<val>"` (row filter — it must select *exactly* the row you
mean), `sig=<N>` (significant figures, default 4), `pm=true` (render the
uncertainty alongside), `err=<column>` (a custom uncertainty column). It
reads table outputs (materialized CSV/JSON), metric outputs (a scalar, or a
JSON object carrying value and uncertainty), and decisions — where it
renders the option the active universe selected.

The block directive renders by target: a decision as label, rationale and
options-as-tabs with the universe's selection marked; an output as the
figure, table or metric with its provenance; a finding as claim, notes,
scope and evidence; a prior insight as a "see also" admonition; an input as
a one-row registry; a plural path as the full registry. Its options are
MyST-style `:key: value` — `:caption:` (Markdown allowed), `:label:` (a
custom anchor), `:compact:` and `:show:`/`:hide:` (which parts of a finding
appear), `:class:` (extra CSS classes).

## Cross-references

Every embedded element gets a stable anchor — `output-<id>`,
`decision-<id>`, unless `:label:` overrode it. Link to it with plain MyST
(`[](#output-hubble_diagram)`) or with `{astra:ref}` from anywhere in the
report.

## Universes and materialization

MySTRA reads the **first `.yaml` file in `universes/`** for its decision
selections, and that is what "the active universe" means in everything
above.

Live values read the materialized results on disk, so the report is only as
current as the last `lc materialize`. Materialize before rendering anything
you intend to show someone; a value whose output has never been made
renders an error token, which is the correct outcome and not something to
work around by typing the number.

## Multi-page reports

A page's filename maps it to an analysis scope — `index.md` is the root,
`reconstruction.md` is that sub-analysis, `reconstruction.features.md` the
`features` inside it. Override with frontmatter when the name cannot say it:

```yaml
---
astra_scope: reconstruction.features
---
```

(`astra_scope: ""` is the root; a list assigns several.) Scope decides which
elements a page's themed output shows — roles and directives still resolve
from the root on every page. List the pages under `project.toc` in
`myst.yml`, and get navigation cards by embedding a sub-analysis
(`:::{astra} reconstruction` / `:::{astra} analyses`).

## Keeping it in sync

- `lc init` scaffolds `index.md` against the *placeholder* spec
  (`decisions.example_method`, `outputs.main_result`). Repoint those ids at
  real ones as soon as the spec is real — see `references/scoping.md`.
- Renaming an output or a decision breaks every reference to it. Grep the
  report for the old id in the same change.
- `myst.yml` loads MySTRA from a `latest` URL. For a build that reproduces,
  pin the release tag instead (`.../releases/download/v0.0.1/mystra.mjs`).
- MySTRA is pre-1.0: syntax can change between releases. Where the preview
  or the docs disagree with this file, they win.
