# The report

Read this when the project's report is in play — writing it, previewing it,
or keeping it honest after the analysis moved.

`lc init` scaffolds a MyST project next to the spec: `myst.yml` (which loads
the **MySTRA** plugin and the ASTRA article theme) and `index.md`, a skeleton
of TODO sections that references nothing yet. MySTRA resolves `{astra}` paths
against `astra.yaml`, so the report *references* the analysis instead of
restating it — one source of truth for every number, figure and decision.
Docs: <https://astra-project.github.io/MySTRA/>.

- [Whose report it is](#whose-report-it-is)
- [The golden rule](#the-golden-rule)
- [Load a MySTRA that reads ASTRA 0.1](#load-a-mystra-that-reads-astra-01)
- [Preview it](#preview-it)
- [Check that it resolved](#check-that-it-resolved)
- [Paths](#paths)
- [The surfaces](#the-surfaces)
  - [Interpolating a value](#interpolating-a-value)
  - [Which file a reference resolves to](#which-file-a-reference-resolves-to)
- [Cross-references](#cross-references)
- [Universes and materialization](#universes-and-materialization)
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

Authorship lives here, not in the spec: ASTRA 0.1 has no `authors` field.
Put authors in `myst.yml`'s project frontmatter (`project.authors`).

## The golden rule

**Never hard-type a measured number, restate a decision, or re-describe an
output.** Reference it. A hard-typed number is correct until the next
`lc materialize` and wrong after it, silently — which is the failure this
whole arrangement exists to prevent.

## Load a MySTRA that reads ASTRA 0.1

The scaffold loads MySTRA from `…/releases/latest/download/mystra.mjs`.
GitHub's `latest` skips release candidates, so until MySTRA 0.1.0 is final
that URL loads v0.0.8, which predates ASTRA 0.1 and cannot read this
analysis. Pin the first release that does, in `myst.yml`:

```yaml
project:
  plugins:
    - https://github.com/astra-project/MySTRA/releases/download/v0.1.0rc1/mystra.mjs
```

The scaffolded ASTRA article theme was last released before MySTRA 0.1. A
rich theme that cannot decode MySTRA's output falls back to its neutral
rendering, which stock MyST themes display as they are: if the page looks
wrong under the article theme, try `site.template: book-theme` before
debugging references, and tell the user what you changed.

## Preview it

Needs Node ≥ 20 and the MyST CLI (`npm install -g mystmd`, or
`uv tool install mystmd` — the user's machine, so ask before installing).
MySTRA needs git on PATH and nothing else; run MyST from the project root.

```bash
myst build          # plain build — the one that PRINTS reference diagnostics
myst start          # live preview (port 3000, or the next free port)
myst build --html   # static site in _build/html/ (gitignored)
```

Preview watches the Markdown files, not `astra.yaml` or `results/` — after
editing the spec or materializing, re-save any `.md` to refresh. `myst start`
prints the port it actually bound; it is not always 3000.

## Check that it resolved

**A report that builds is not a report that resolved.** A broken reference
does not fail the build. Checking is a separate act, and it takes both steps
below because the two role families fail differently.

**1. Run `myst build` and read its diagnostics.** MySTRA reports what it
cannot resolve as MyST errors and warnings, with a file and position, and
renders a value it cannot read as a visible `⟨value: …⟩` token in the page.
Run the *plain* `myst build` for this: `myst build --html` and `myst start`
launch a server whose request log buries those lines. Grep for `⛔️` or read
the output; the messages do not all contain "error".

**2. Check `{astra}` reference ids yourself — they fail quietly.** An inline
`{astra}` role given a path that does not resolve still renders a plain
label made from the path, so the sentence reads on:

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
`prior_insights`, `analyses`.

| Path | What it addresses |
|---|---|
| `outputs.hubble_diagram` | one output |
| `outputs` | the whole collection — renders as a registry |
| `decisions.algorithm.gp` | an option of a decision |
| `findings.sig.0` | the first evidence record of a finding — evidence has no ids in ASTRA 0.1, only a zero-based index |
| `cleaning.outputs.clean_catalog` | an output of the declared analysis `cleaning` (`analyses.` is implied) |
| `cleaning` | the declared analysis itself — a summary card |

The leading collection keyword fixes the target; segments before it step
into declared analyses. Children — decision options, evidence records — omit
their own collection keyword, since each parent has exactly one kind of
child. Labels come from a declared `label:` where there is one, otherwise
the id with underscores as spaces.

## The surfaces

| Surface | Use |
|---|---|
| ``{astra}`outputs.fit` `` | mention an element inline; ``{astra}`our method <decisions.algorithm>` `` for custom text |
| ``{astra:value col=… where="…"}`outputs.fit_params` `` | interpolate a measured number into prose — options go on the role, see below |
| ``{astra:cite}`findings.sig` `` | citation from DOI-backed evidence — `(Author et al., Year)`; `{astra:cite:t}` for the textual `Author et al. (Year)`. Findings and prior insights only |
| `:::{astra} outputs.fit` … `:::` | embed the element as a block |

There is no `{astra:ref}` role: a numbered reference is MyST's own `{ref}`
to a block's `:label:` ([Cross-references](#cross-references)).

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
| `where="<k>=<v>"` | Row filter; space- or comma-separated pairs, matched case-insensitively. Must select *exactly* the row you mean — with several matches, the first is used. |
| `sig=<N>` | Significant figures on the value (default 4). The uncertainty is always rendered at 2. |
| `pm=true` | Append `± <uncertainty>`: the column named `<col>_std` for a table, the metric's own uncertainty for a metric. |
| `err=<column>` | Name the uncertainty column explicitly; implies `pm`. |
| `universe=<ref>` | Read another universe than the page's, as a complete ref: `universe=universes.robust`. |

`pm=true` on a table looks for `<col>_std` and renders no uncertainty if no
such column exists — so a table whose uncertainty column is called anything
else (`sigma`, `err`, `stddev`) needs `err=` instead.

It reads three kinds of target:

- **Table outputs** — a materialized `.csv` or `.json` result; `col=`
  required.
- **Metric outputs** — a `.json` result holding either a bare number, a
  two-element `[value, uncertainty]` array, or an object with a `value` key
  (plus optional `uncertainty`, `unit`). No `col=` needed.
- **Decisions** — renders the label of the option the page's universe
  selects (where the plain `{astra}` role names the decision itself).

`data` outputs are never read, by any surface: a block embed or evidence
citing one renders its label and its result's file path.

**Values cannot go inside math.** A role inside `$…$` or `$$…$$` is not
expanded — it renders as literal source, and a stray `$` around it can open
an unterminated math run that swallows the rest of the paragraph. Put the
symbol in math and the value outside it:

```markdown
$\Omega_\Lambda$ = {astra:value col=mean err=sigma}`outputs.constraints`   ✓
$$\Omega_\Lambda = \text{{astra:value col=mean}`outputs.constraints`}$$    ✗
```

### Which file a reference resolves to

Nothing to choose: a result *is* one file, at the place ASTRA gives it —
`results/<universe>/<output_id>.<format>`, or `results/<output_id>.<format>`
for an output built once — and MySTRA takes that place from ASTRA too. The
`format:` in `astra.yaml` is what tells the page whether it is embedding a
figure, a table or a metric, so a `{astra}` reference is answerable from the
spec before anything has been materialized.

The consequence for authoring is upstream, in `astra.yaml`: an output that
wants to be *both* a `.csv` of values and a `.png` of them is two outputs,
not one, and only then can a page point at each. A bundle behind one id
(`format: tar.gz`) is opaque to the report — nothing on the page can reach
inside it.

The block directive renders by target: a decision as label, rationale and
options-as-tabs with the universe's selection marked; an output as the
figure, table or metric; a finding as claim, description, scope and
evidence; a prior insight as a "see also" admonition; an input as a one-row
registry; a declared analysis as a summary card; a plural path as the full
registry. Its options are MyST-style `:key: value` — `:caption:` (Markdown
allowed), `:label:` (an anchor, replacing the default `<kind>-<id>`),
`:compact:` and `:show:`/`:hide:` (which parts of a finding appear),
`:universe:` (another universe for this block), `:class:` (extra CSS
classes).

## Cross-references

Give a block an explicit `:label:` and reference it with MyST's standard
`{ref}` role; MyST numbers figures and tables and resolves the reference
across pages:

```markdown
:::{astra} outputs.hubble_diagram
:label: fig-hubble
:::

As {ref}`fig-hubble` shows, …
```

## Universes and materialization

A page presents **the first universe written under `universes:` in
`astra.yaml`** — authored order, not alphabetical. Reordering the file
changes the universe every page renders, so keep the intended default first.
To choose explicitly, set it in a page's frontmatter, or per block and per
value:

```markdown
---
astra_universe: universes.baseline
---
```

`:universe: universes.robust` on a block, `universe=universes.robust` on a
value. A result built once is the same in every universe.

Live values read the materialized results, so the report is only as current
as the last `lc materialize`. Materialize before rendering anything you
intend to show someone — in a clone, `lc fetch` the results the page shows;
a value whose result has never been made renders an error token, which is
the correct outcome and not something to work around by typing the number.

## Keeping it in sync

- Renaming an output or a decision breaks every reference to it, and a plain
  `{astra}` reference to the old id renders as innocuous text rather than an
  error. Grep the report for the old id in the same change — nothing else
  will tell you.
- Evidence is addressed by position (`findings.sig.0`): inserting or
  reordering a finding's evidence moves every reference after it.
- A multi-page report maps each page to an analysis by file name
  (`cleaning.md` → the declared analysis `cleaning`) or an `astra_scope:`
  key in its frontmatter; references still resolve from the root on every
  page.
- Pin MySTRA to a tag for a build that reproduces, as above. MyST caches the
  theme under `_build/templates/` and keeps using that copy;
  `myst clean --templates` fetches it afresh.
- MySTRA is pre-1.0: syntax can change between releases. Where the preview
  or the docs disagree with this file, they win.
