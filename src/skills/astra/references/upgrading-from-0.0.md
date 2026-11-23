# Upgrading an `astra.yaml` written before ASTRA 0.1

Read this when an `astra.yaml` has `version: "0.0.x"` where 0.1 writes
`spec_version:`, or a `universes/` folder sits beside it. The pinned astra
reads only 0.1, so such a spec fails nearly every rule at once
(`MISSING_FIELD` for `spec_version`, `UNKNOWN_FIELD` for most of the rest).
There is no converter: rewrite the file in one pass with the tables below,
then validate until clean. A half-converted file validates nothing, so
convert it whole before reading any report.

Keep every id. Recipes, scripts, reports and the user know the analysis by
them, and nothing here needs one renamed.

- [Top level](#top-level)
- [Collections become maps keyed by id](#collections-become-maps-keyed-by-id)
- [Inputs](#inputs)
- [Outputs](#outputs)
- [Decisions and options](#decisions-and-options)
- [Universes](#universes)
- [Insights and evidence](#insights-and-evidence)
- [Sub-analyses become declared analyses](#sub-analyses-become-declared-analyses)
- [Check the result](#check-the-result)

## Top level

| 0.0.x | 0.1 |
|---|---|
| `version: "0.0.14"` | `spec_version: "0.1.0"` — always three parts, quoted |
| `name:` | `label:` (optional) |
| `id:` | removed: a folder at a commit is the analysis's identity |
| `container:` | removed: the environment is the runner's |
| `path:` | removed (see [sub-analyses](#sub-analyses-become-declared-analyses)) |
| `narrative:`, `authors:` | removed: a one-paragraph `description` here, the prose and authorship in the report |

## Collections become maps keyed by id

`inputs`, `outputs`, `universes` and `analyses` were lists of `{id: …}`;
they become maps, like `decisions`, `options` and the insights already were.
An element's id is its key, never an `id` field — drop any `id:` left inside
an element of any collection:

```yaml
# 0.0.x                          # 0.1
inputs:                          inputs:
  - id: catalog                    catalog:
    type: data                       path: data/catalog.csv
    source: data/catalog.csv
```

## Inputs

An input is now one file in the analysis's own folder, tracked in git.

| 0.0.x | 0.1 |
|---|---|
| `type: data` | removed |
| `source:` naming a file in the analysis's folder | `path:` the same file — then `git add` it, or validation fails with `INPUT_NOT_TRACKED` |
| `source:` naming anything else — a file outside the folder, a URL, a loader, a dataset id — or no `source` | an output **built once** (no `decisions`) whose recipe gets the data, under the same id so its readers don't change |
| `type: analysis`, `from:`, `ref:`, `ref_version:`, `use_outputs:` | a declaration under `analyses:` (below), its elements read by address |

An input fetched by its recipe, keeping its id:

```yaml
outputs:
  catalog:
    type: data
    format: fits
    recipe:
      command: curl -fsSL https://example.org/catalog.fits -o {output}
```

Where the bytes cannot be fetched by a command (a file on a shared disk, say),
copy the file into the analysis's folder (`data/` by convention) and track it;
a large-file tool keeps it out of git's own history. Ask the user which: a
recipe that downloads depends on the source staying up.

## Outputs

| 0.0.x | 0.1 |
|---|---|
| `type:` optional | required: `metric`, `figure`, `table`, `data` or `report` |
| `format:` optional | required: the result's file extension, no dot (`png`, `csv`, `json`) |
| no `recipe`, or `recipe` without `command` | required: `recipe.command`. An output nothing makes is not an output — write its recipe, or drop it |
| `recipe.container:` | removed: the environment is the runner's |
| `from:` | removed: read another analysis's output by address in `inputs` |
| `when:` | removed: an output exists in a universe when what it reads is built there. Read the conditional thing through a **switch** on the gating decision, whose `cases` name it only for the options where it exists (`uvx astra-tools@x.y.z spec output`) |

Placeholders keep their meaning — `{output}`, `{inputs}`,
`{inputs.<entry>}`, `{decisions.<entry>}` — and each names an entry of the
output's `inputs` / `decisions` exactly as listed there, addresses and pins
included (`{decisions.cleaning.cut}`, `{inputs.fit#robust}`).

## Decisions and options

| 0.0.x | 0.1 |
|---|---|
| `default:` | removed: the baseline universe makes that choice |
| `excluded: true` + `excluded_reason: R` | `excluded: R` — the reason *is* the exclusion |
| `excluded: false` | removed |
| option `label:` required | optional, as every label now is |
| `from:` (a parent's decision) | removed: declare the analysis that holds it and name it by address (`decisions: [parent.method]`, `{decisions.parent.method}`) |
| `when:` | removed: a decision is in play in a universe only when something built there uses it — model the condition with a switch, as for outputs |

## Universes

| 0.0.x | 0.1 |
|---|---|
| `universes/<id>.yaml` | an entry `<id>:` under `universes:` in `astra.yaml`, holding the same `decisions` and `description` (and an optional `label`); then delete the folder |
| a universe generated from the decisions' defaults | keep it, written out: it is now the only record of those choices |
| `analyses:` / presets inside a universe | flat keys by address: `stage.method: robust` |

A universe now sets every decision it uses and **only** those it uses on
some branch — an old universe that listed every decision of the file may
fail `UNUSED_DECISION`. Let variants inherit from the baseline with
`derived_from: baseline` and set only what they change.

## Insights and evidence

| 0.0.x | 0.1 |
|---|---|
| insight `id:`, `created_at:`, `derived:` | removed |
| insight `notes:` | `description:` |
| evidence `id:`, `snapshot:`, `source_commit:` | removed |
| `location: {page: 8}` | `location: {value: page=8}` — and the quote must then be **on** page 8 |
| `artifact: fit` where `fit` is built per universe | pin it, `artifact: fit#baseline`, to say which universe's result the claim rests on; unpinned, it cites every universe's |

Cached papers now live in the user's astra cache. On Linux that is still
`~/.cache/astra`; on macOS it moved to `~/Library/Caches/astra`, so papers
cached there by an older astra need `paper add` again. Then run
`uvx astra-tools@x.y.z validate --verify-evidence`: 0.1 checks a quote on
the page its location gives, so a quote that passed before can fail now.

## Sub-analyses become declared analyses

Inline `analyses:` entries are no longer part of the file. Each becomes a
folder with its own `astra.yaml` (`spec_version`, its inputs, outputs and
decisions), declared from the parent and read by address:

```yaml
analyses:
  cleaning: {path: cleaning}        # the folder cleaning/, with its own astra.yaml
outputs:
  fit:
    inputs: [cleaning.clean_catalog]
    decisions: [method, cleaning.cut]
```

- `from: ../x` in a sub-analysis becomes a declaration of the parent
  (`parent: {path: ..}`) and the address `parent.x`.
- A re-exported output becomes a direct read by address; evidence that cited
  it cites the declared analysis's output.
- The parent's universes set a declared analysis's decisions by address
  (`cleaning.cut: strict`); once one universe does, every universe sets the
  ones it uses.
- A sub-analysis with no decisions of its own and nothing reusable was only
  passing data through: fold its recipes into the parent instead.

The `guide` covers when a split is worth having at all; most analyses are
better flat.

## Check the result

1. `uvx astra-tools@x.y.z validate` until clean — the codes name each rule
   at its line.
2. `uvx astra-tools@x.y.z info` and `uvx astra-tools@x.y.z view <universe>`:
   each universe selects what the old one did, and each command expands as
   the old recipe did.
3. `uvx astra-tools@x.y.z validate --verify-evidence` if the analysis cites
   papers.

Results made under 0.0.x have no 0.1 record, so every result is `missing`
until a runner makes it again — that is expected, not a sign the conversion
went wrong.
