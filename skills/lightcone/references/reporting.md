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
- [Check that it resolved](#check-that-it-resolved)
- [Paths](#paths)
- [The five surfaces](#the-five-surfaces)
  - [Interpolating a value](#interpolating-a-value)
  - [Name the result file](#name-the-result-file)
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
myst build          # plain build — the one that PRINTS reference diagnostics
myst start          # live preview (port 3000, or the next free port)
myst build --html   # static site in _build/html/ (gitignored)
```

Preview watches the Markdown files, not `astra.yaml` — after editing the
spec, re-save any `.md` to refresh. `myst start` prints the port it actually
bound; it is not always 3000.

## Check that it resolved

**A report that builds is not a report that resolved.** Nothing here fails
the build: the exit code is `0` even when every reference on the page is
broken, and `--strict` does not change that. Checking is a separate act, and
it takes both steps below because the two role families fail differently.

**1. Run `myst build` and read the `⛔️` lines.** Value lookups report
themselves, with a file, line and column:

```
⛔️ index.md:254:4 astra:value: no column "nope" in "parameter_constraints"
```

Run the *plain* `myst build` for this. `myst build --html` and `myst start`
launch a server whose request log buries these lines, and the messages
contain neither "error" nor "warning", so a `grep -i error` misses them —
grep for `⛔️` or read the output.

**2. Check `{astra}` reference ids yourself — they fail silently.** A value
role that cannot resolve leaves a visible `⟨value: …⟩` token in the page. The
plain `{astra}` role does not: given an id that does not exist it prints the
id humanized, with no diagnostic, no error token and no clue to the reader.

```
{astra}`outputs.does_not_exist`   →   renders as: does not exist
```

That reads as ordinary prose, so a typo'd or renamed id can sit in a report
indefinitely. After renaming anything, grep the report for the old id, and
check the ids you reference against `uvx astra-tools@x.y.z info`.

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
| ``{astra:value col=… where="…"}`outputs.fit_params` `` | interpolate a measured number into prose — options go on the role, see below |
| ``{astra:ref}`outputs.fit` `` | numbered cross-reference ("Figure 3"); `%s` is the number's placeholder in custom text |
| ``{astra:cite}`findings.sig` `` | citation from DOI-backed evidence — `(Author et al., Year)`; `{astra:cite:t}` for the textual `Author et al. (Year)`. Findings and prior insights only |
| `:::{astra} outputs.fit` … `:::` | embed the element as a block |

### Interpolating a value

**Options go on the role, never in the path.** This is the one piece of
syntax worth getting right first, because a table output *cannot* be read
without `col=`, and anything appended to the path is rejected:

```markdown
{astra:value col=mean where="parameter=H0" err=sigma}`outputs.constraints`
```

```markdown
{astra:value}`outputs.constraints col=mean`   ✗ unexpected content
{astra:value}`outputs.constraints?col=mean`   ✗ swallowed into the path
{astra:value}`outputs.constraints`            ✗ missing col=
```

| Option | Effect |
|---|---|
| `col=<column>` | Which column to read. **Required for table outputs.** |
| `where="<k>=<v>"` | Row filter; space- or comma-separated pairs, matched case-insensitively. Must select *exactly* the row you mean. |
| `sig=<N>` | Significant figures on the value (default 4). The uncertainty is always rendered at 2. |
| `pm=true` | Append `± <uncertainty>`, read from the column named `<col>_std`. |
| `err=<column>` | Name the uncertainty column explicitly; implies `pm`. |

`pm=true` looks for `<col>_std` and **silently renders no uncertainty** if no
such column exists — so a table whose uncertainty column is called anything
else (`sigma`, `err`, `stddev`) needs `err=` instead.

It reads three kinds of target:

- **Table outputs** — a materialized `.csv` or `.json`; `col=` required.
- **Metric outputs** — a `.json` file holding either a bare number, a
  two-element `[value, uncertainty]` array, or an object with a `value` key
  (plus optional `uncertainty`, `error`, `unit`, `units`, `label`). No
  `col=` needed. A metric written to any other extension is not read.
- **Decisions** — renders the option label the active universe selected.

**Values cannot go inside math.** A role inside `$…$` or `$$…$$` is not
expanded — it renders as literal source, and a stray `$` around it can open
an unterminated math run that swallows the rest of the paragraph. Neither
failure produces a diagnostic or an error token. Put the symbol in math and
the value outside it:

```markdown
$\Omega_\Lambda$ = {astra:value col=mean err=sigma}`outputs.constraints`   ✓
$$\Omega_\Lambda = \text{{astra:value col=mean}`outputs.constraints`}$$    ✗
```

### Name the result file

An output is a *directory*, so a recipe may write several files into
`{output}`. Resolution ignores dotfiles (the run manifest never interferes)
and then picks, in order:

1. the file whose name before the extension equals the **output id**;
2. otherwise the **alphabetically first** file.

So an output `parameter_constraints` that writes `constraints.csv` and
`summary.json` resolves to `constraints.csv` — by alphabetical luck, not by
intent, and adding an `analysis.csv` later would silently redirect every
value on the page. **Write the primary artifact as `<output_id>.csv` (or
`.json`)** and the choice stops being a lottery. Secondary files alongside it
are then free to be named anything.

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

MySTRA reads the **alphabetically first `.yaml` file in `universes/`** for
its decision selections, and that is what "the active universe" means in
everything above. There is no way to choose it, so the name decides: a new
`ablation.yaml` silently becomes the universe the whole report renders,
displacing `baseline.yaml`. Keep the intended default first alphabetically,
and check which one is active before reading a number off the page.

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
- Renaming an output or a decision breaks every reference to it, and a plain
  `{astra}` reference to the old id renders as innocuous humanized text
  rather than an error. Grep the report for the old id in the same change —
  nothing else will tell you.
- `myst.yml` loads MySTRA from a `latest` URL. For a build that reproduces,
  pin the release tag instead (`.../releases/download/v0.0.1/mystra.mjs`).
- MySTRA is pre-1.0: syntax can change between releases. Where the preview
  or the docs disagree with this file, they win.
