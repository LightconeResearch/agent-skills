---
name: astra
description: >
  ASTRA (astra.yaml) support: what the format is, and how to drive the
  `astra` CLI. Invoke whenever reading, writing, validating, or restructuring
  an astra.yaml spec, working with universes, declared analyses, evidence or
  how results stand against their records, upgrading a spec written before
  ASTRA 0.1, or when the user asks about ASTRA.
---

# ASTRA

## What ASTRA is

An ASTRA analysis is a folder in a git repository with an `astra.yaml` at its
top: an intermediate layer of abstraction between code and paper, recording
the inputs, outputs, and every consequential methodological decision — with
its reasoning — at the level needed to make the scientific claims verifiable
and reproducible. The goal is to make the full decision space explicit, so
that alternative defensible choices can be systematically explored (as
*universes*) rather than silently baked in. An analysis can declare others
and read their elements by address (`stage.output3`); a declared analysis is
a folder with its own `astra.yaml`, of exactly the same shape.

A **runner** (such as `lc`) builds each result from committed files and writes
a **record** of how it was made; `astra` validates, shows, and checks results
against their records. It never runs a recipe.

This skill is written for **ASTRA 0.1** (`spec_version: "0.1.0"`). An
`astra.yaml` that has `version:` instead, or a `universes/` folder beside it,
predates 0.1 and is not read at all: convert it first, with
[references/upgrading-from-0.0.md](references/upgrading-from-0.0.md).

## Running `astra`

Always invoke the `astra` CLI through uv's pinned runner, exactly as written
everywhere in this document:

```bash
uvx astra-tools@0.3.0rc4 <command>
```

Never run a bare `astra` found on PATH — its version is unknown and may not
match what this skill assumes. (`uvx` caches the environment, so repeated
calls are fast. If `uvx` is missing, ask the user to install uv:
https://docs.astral.sh/uv/getting-started/installation/ — never install it
yourself.)

## Orient before authoring

The CLI serves everything this skill deliberately does not repeat:

- `uvx astra-tools@0.3.0rc4 guide` — the complete agent briefing on the format:
  core concepts, worked examples, the authoring workflow and judgment (what
  deserves to be a decision, when to split out a declared analysis,
  universes, evidence), and the format rules. **Read it before any
  substantial authoring or restructuring work.**
- `uvx astra-tools@0.3.0rc4 spec` — the field-level ground truth, served in sync
  with the schema the validator enforces: no argument prints the concept map;
  `uvx astra-tools@0.3.0rc4 spec <term>` prints one concept in full (the mode to
  reach for while editing); `uvx astra-tools@0.3.0rc4 spec --full` prints the
  entire reference (long).
- `uvx astra-tools@0.3.0rc4 info` — the analysis as it resolves: its inputs,
  outputs, decisions, each universe's selections, and every analysis it
  declares.
- `uvx astra-tools@0.3.0rc4 view <universe>` — what one universe builds: each
  result planned in it, where its file goes, what each entry reads, and its
  command exactly as it runs. Check a recipe's expansion here, before
  anything runs it.

Re-validate after every change: `uvx astra-tools@0.3.0rc4 validate` with no
argument checks every analysis under the current directory, each with every
analysis it declares.

## What validation needs that the file cannot say

The validator reads git as well as the file, so a correct `astra.yaml` can
still fail for reasons outside it:

- **The analysis is in a git working tree** (`NOT_IN_REPOSITORY`).
  `uvx astra-tools@0.3.0rc4 init` makes one when there is none.
- **An input is one file, tracked in git** (`INPUT_NOT_TRACKED`): declare
  `path: data/catalog.csv` *and* `git add data/catalog.csv` — staged is
  enough to validate. It sits in the analysis's own folder, outside
  `results/` and `.astra/` (the runner's) and outside any folder below with
  its own `astra.yaml`. A large-file pointer (git-annex, Git LFS) stands in
  for the bytes. Data that is downloaded, or lives elsewhere, is not an
  input: it comes in as an output built once whose recipe gets it.
- **Every output but a switch has `type`, `format` and `recipe.command`.**
  `format` is the file extension of its result, without the dot.
- **Universes are entries of `universes:` in `astra.yaml`.** There is no
  `universes/` folder, no decision `default`, and nothing generates a
  universe: write a `baseline` selecting an option for every decision it
  uses, and derive variants from it (`derived_from: baseline`), setting only
  what changes. A universe sets every decision it uses (`MISSING_DECISION`)
  and only those it uses on some branch (`UNUSED_DECISION`).

## Results, pins and records

An output is **built per universe** if it lists `decisions`, or reads,
without a pin, a switch or an output built per universe; otherwise it is
**built once**. Its result lands at `results/<universe>/<id>.<format>`, or
`results/<id>.<format>` when built once, and its record at
`.astra/records/<universe>/<id>.json` (`.astra/records/<id>.json`). A
reference ending in a **pin**, `#` and a universe's id (`fit#robust`), reads
the result of that universe only: that is how an output built once compares
universes, and how a finding says which universe's result it rests on.
Placeholders name entries exactly as listed, pins included:
`{inputs.fit#robust}`.

`uvx astra-tools@0.3.0rc4 status` gives each planned result's record status —
`unchanged`, `stale` (something it is made from changed since its record's
commit) or `missing` — its bytes, `present` or `absent`, and why; then each
evidence with the status of what it cites. A result is made from its
output's command, inputs in order and their content, decisions and the
options selected, format, and the results it reads. Code is recorded, not
compared: an edited script stales nothing until a rebuild gives other bytes.
`uvx astra-tools@0.3.0rc4 history timeline|lineage|get|find <address>` reads a
result's records back through git. Where a runner is in use, its own status
verb adds what it alone knows (the environment, what a clone has fetched) —
prefer it there.

## Citations, quotes, and supporting evidence

Claims in ASTRA are backed by verifiable evidence: `prior_insights` (imported
claims that motivate decisions) and `findings` (claims the analysis produces)
both carry `evidence` entries — a `doi` with a verbatim quote for literature,
or an `artifact` naming an output. Insights and evidence carry no `id` field
of their own: an insight's id is its key.

```yaml
prior_insights:
  robust_fits_resist_outliers:
    claim: Robust estimators reduce the influence of outliers on fitted relations.
    evidence:
      - doi: "10.48550/arXiv.2008.03833"
        version: 2                        # arXiv revision; omit for other DOIs
        quote:
          exact: "robust estimators reduce the influence of outliers"
          prefix: "As expected, "
          suffix: " in every simulated sample"
        location: {value: page=6}
findings:
  scatter_reduced:
    claim: The robust universe reduces the fit's scatter.
    evidence:
      - artifact: fit_params#robust      # pinned: this universe's result
```

The `paper` utilities manage the literature side end to end:

1. **Cache the source at authoring time.** An arXiv paper downloads by its
   DOI: `uvx astra-tools@0.3.0rc4 paper add 10.48550/arXiv.2008.03833` (pass
   `--version N` to pin a revision). **Nothing else downloads**: for any
   other DOI, ask the user for the PDF and add it with
   `uvx astra-tools@0.3.0rc4 paper add <doi> --pdf <file>`. Papers live in the
   user's astra cache (`ASTRA_CACHE_DIR` moves it), not in the project.
2. **Pull exact quotes from the cached PDF** —
   `uvx astra-tools@0.3.0rc4 paper path <doi>` prints the cached file's path so
   you can open it and copy the supporting text *verbatim* into
   `quote.exact`; add `prefix`/`suffix` (~20–100 chars on either side) when
   the exact string occurs more than once, and the page as
   `location: {value: page=N}`. Write every quote as if a machine will look
   for it — one will.
3. **Verify before you're done** —
   `uvx astra-tools@0.3.0rc4 paper verify-quotes <doi>` checks one paper's
   quotes in one pass (below);
   `uvx astra-tools@0.3.0rc4 validate --verify-evidence` checks every quote in
   the analysis, each as an error at its line where it fails:
   `EVIDENCE_PAPER_MISSING` (not cached), `EVIDENCE_PAPER_UNREADABLE`, or
   `EVIDENCE_QUOTE_NOT_FOUND` — which includes a quote found only on another
   page than its `location` gives.

`paper verify-quotes` reads a JSON list on stdin, one item per quote,
written as `astra.yaml` writes them, and returns each quote's `state` —
`found`, `elsewhere` (on another page than given), `not_found` or
`no_paper` — and the `page` it is on:

```bash
echo '[{"quote": {"exact": "…", "prefix": "…", "suffix": "…"},
        "location": {"value": "page=6"}}]' \
  | uvx astra-tools@0.3.0rc4 paper verify-quotes <doi> [--version N]
```

`uvx astra-tools@0.3.0rc4 paper list` shows the cache;
`uvx astra-tools@0.3.0rc4 paper show <doi>` prints a cached paper's metadata.
Evidence citing an output is skipped by `--verify-evidence`; its standing is
`astra status`'s.

## CLI reference

The `astra` CLI validates and inspects; it never executes recipes. The
separation is deliberate — the spec stays stable while agents and execution
layers evolve, and the choice of runner stays yours — so don't encode
runner-specific behavior into the spec.

```bash
uvx astra-tools@0.3.0rc4 init [DIRECTORY]                        # Scaffold an empty analysis (and a git repository)
uvx astra-tools@0.3.0rc4 validate [FILE]                         # Validate every analysis here, or one (run after every change)
uvx astra-tools@0.3.0rc4 validate --verify-evidence              # + verify every quote against its cached paper
uvx astra-tools@0.3.0rc4 guide                                   # Full agent briefing on the format (read before authoring)
uvx astra-tools@0.3.0rc4 spec [TERM|--full]                      # Schema reference (see above)
uvx astra-tools@0.3.0rc4 info [-d|-i|-o]                         # The analysis as it resolves, its universes and declared analyses
uvx astra-tools@0.3.0rc4 view UNIVERSE                           # What one universe builds, commands expanded
uvx astra-tools@0.3.0rc4 status                                  # How each result and evidence stands against its record
uvx astra-tools@0.3.0rc4 history timeline|lineage|get|find ADDR  # A result's records through git history
uvx astra-tools@0.3.0rc4 paper add DOI [--version N] [--pdf F]   # Cache a paper (arXiv downloads; anything else needs --pdf)
uvx astra-tools@0.3.0rc4 paper list                              # List cached papers
uvx astra-tools@0.3.0rc4 paper show DOI                          # Show metadata for a cached paper
uvx astra-tools@0.3.0rc4 paper path DOI [--version N]            # Print the cached PDF's path
uvx astra-tools@0.3.0rc4 paper verify-quotes DOI                 # Batch-verify quotes; reads a JSON list from stdin
```

Every reporting command takes `--json`; `--help` on any of them is the
authority where this table and the CLI disagree.
