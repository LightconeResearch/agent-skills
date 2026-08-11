---
name: lightcone
description: >
  Companion for working with the user on a Lightcone project — an ASTRA
  analysis (astra.yaml) executed with the `lc` CLI. Covers how to structure
  the project, drive the development workflow (write & debug, integrate
  recipes, materialize with `lc run`), interpret status and diagnose
  failures, publish results — and how to engage the user at each phase:
  interview to scope a brand-new project, orient and summarize when resuming
  an existing one. Invoke whenever the user wants to start, resume, plan,
  run, debug, or discuss a Lightcone/ASTRA analysis project — "new
  analysis", "scope a project", "resume/continue the project", "where were
  we", "run the pipeline", "lc status/run/verify", "publish the analysis".
---

# Lightcone Projects

A Lightcone project is a scientific analysis with two synchronized layers:

- **The spec** — `astra.yaml` plus its universe files: the ASTRA record of
  the analysis and its decision space. Everything about this layer — the
  format, authoring judgment, the `astra` CLI, evidence and quotes,
  validation — belongs to the `astra` skill; this skill assumes it and
  repeats none of it.
- **The execution** — code in `src/`, `recipe:` blocks wiring outputs to
  scripts, and the `lc` CLI, which materializes outputs inside containers
  and writes content-addressed provenance manifests under `results/`.

This skill owns the execution layer and the workflow around the whole
project: recognizing which phase the project is in, engaging the user
accordingly, and driving `lc`.

**Invoke the `astra` skill before any spec work** — reading or writing
`astra.yaml`, running an `astra` command, collecting evidence, validating.
Wherever this document says "validate the spec", "cache a paper", or
"generate a universe", the exact commands are the astra skill's.

## Prerequisites

Always invoke `lc` through uv's pinned runner, exactly as written in this
document:

```bash
uvx --from lightcone-cli@0.4.0 lc <command>
```

Never run a bare `lc` found on PATH — its version is unknown and may not
match what this skill assumes. (`uvx` caches the environment, so repeated
calls are fast. If `uvx` is missing, ask the user to install uv:
https://docs.astral.sh/uv/getting-started/installation/ — never install it
yourself.) When unsure of a command's syntax, discover it with `--help`
rather than guessing. The `astra` CLI has its own pinned invocation — take
it from the astra skill, never from memory or PATH.

## Orient before anything else

This skill can be invoked at any point in a project's life. First determine
where the project is, then match how you engage:

1. **Look for `astra.yaml`** in the working directory.
2. **No spec (or a freshly scaffolded placeholder)** → this is a new project.
   Switch to **Scoping** below: interview the user; don't start writing code.
3. **Spec exists** → read `astra.yaml` and `CLAUDE.md`, then run
   `uvx --from lightcone-cli@0.4.0 lc status` (for a large spec, the astra
   skill's CLI reference has an `info` command that summarizes structure).
   Do **not** re-interview the user about things the spec already answers.

When resuming an existing project, open with a short state-of-the-project
summary before asking anything: the research question in one line, the
structure (sub-analyses, decision count, universes), what `lc status` shows
(which outputs are `ok` / `stale` / `missing`, per universe), and anything
notable from `CLAUDE.md`. Then ask what to work on next, offering the
obvious candidates — e.g. materialize the `missing` outputs, refresh `stale`
ones, integrate a script that has no recipe yet, add a universe, or discuss
results. `AskUserQuestion` with the concrete options works well here.

The phase determines the mode of interaction:

| Phase | Cues | How to engage |
|---|---|---|
| Scoping | no/placeholder spec | Interview; build the spec together; no implementation code |
| Implementation | spec exists, outputs `missing`/`stale`, scripts absent or unwired | Pair on scripts, integrate recipes, run outputs one at a time |
| Interpretation | outputs `ok` | Discuss results, record findings, explore alternative universes |
| Publishing | user wants to share/archive | Verify provenance, export the RO-Crate bundle |

These phases overlap in practice — a resumed project may need scoping-style
conversation for a new sub-analysis while the rest is being materialized.
Pick the mode per task, not once per session.

## Working with the user

- **Interview, don't lecture.** During scoping, ask one focused question at a
  time and let the answers drive the spec. During implementation, surface
  choices as they arise instead of silently deciding.
- **Write early, write often.** Update `astra.yaml` the moment a decision
  crystallizes, not in bulk at the end — the user should see the spec grow.
- **Review in the file, not in chat.** Write candidate decisions and findings
  to `astra.yaml` for the user to review; keep chat output to a concise
  summary with IDs. Don't dump full YAML in the conversation.
- **Confirm before expensive steps.** Materializing a full multiverse or
  forcing rebuilds can be long; check scope with the user first and build
  iteratively instead.
- **Keep `CLAUDE.md` current.** It carries the context that isn't in the spec
  and would be lost after `/clear` — update its Project Notes when
  conversation produces durable context. After a long scoping session,
  recommend `/clear`: everything needed to continue lives in `astra.yaml`
  and `CLAUDE.md`.

## Scoping a new project

Scaffold first if needed: `uvx --from lightcone-cli@0.4.0 lc init [DIR]`
creates the project skeleton, a placeholder `astra.yaml`, and `CLAUDE.md`.
Then build the spec through conversation, updating `astra.yaml` after each
phase. Announce each phase with a short stage banner so the user can follow.

**You are a specification agent in this mode, not an implementation agent** —
create or modify only `astra.yaml`, `universes/*`, and `CLAUDE.md`, and write
no Python/R/implementation code until scoping is done.

### 1. Research question

> "What are you trying to learn? Describe the question in your own words."

Sharpen it: what would a clear answer look like, and why does it matter?
"Analyze this data" is not a research question — push back until it is. Set
`name` in `astra.yaml`. (Leave the scaffolded `description` TODO for the
finalize step — written too early it goes stale.)

### 2. Analysis structure

> "Walk me through your analysis step by step. What goes in, what comes out?"

- **Default to a single analysis.** Split into sub-analyses only when each
  part is genuinely a self-contained product with materially different
  inputs and outputs (training + evaluation is usually *one* analysis — the
  product is the validated estimator). The full splitting judgment is the
  astra skill's; when a split does seem warranted, confirm the stage
  boundaries with the user before restructuring.
- **One output per output.** A single metric, a single plot, or a single
  artifact each — never a bundle like "performance_metrics".

Update `astra.yaml` with `inputs` and `outputs`.

### 3. Literature deep dive (optional per section)

Offer a literature pass; skip straight to decision identification if
declined.

- **Collect** — ask for papers the user already has in mind, search for a
  *limited* set of directly relevant ones (~2 per topic, max 10 per
  section), and present the list via `AskUserQuestion` with a one-line
  relevance note each for the user to approve.
- **Extract** — cache each approved paper with the astra skill's evidence
  workflow, then spawn **one subagent per paper** (all in parallel) to read
  the cached PDF and return candidate prior insights — verbatim quotes with
  their locating context — and the decisions they might inform. Give each
  subagent the analysis context, the paper's DOI and cached-PDF path, and
  the target decisions. Never read a PDF in the main context — it consumes
  too much of it. Write extracted insights to `astra.yaml` as they land and
  synthesize by topic for the user.
- **Identify decisions** — from conversation and literature: what could be
  done differently and still be defensible? Where did papers disagree? Where
  was the user uncertain? Probe the blind spots analysts neglect — data
  exclusion, variable operationalization, inference criteria — not just
  method choices. Write candidates to `astra.yaml` as a batch for review.
- **Review** — confirm or set each decision's `default`; drop rejected ones.

Every extracted quote must survive the astra skill's evidence verification
before scoping is done — never fabricate one.

### 4. Finalize

1. Checkpoint: "Anything else that should inform this analysis?"
2. Validate the spec per the astra skill — verifying evidence too, if any
   was extracted — and iterate until clean.
3. Generate only a `baseline` universe unless the user asks for more
   (universe commands: astra skill).
4. Replace the `description:` TODO with a short orientation paragraph now
   that structure is stable.
5. Fill `CLAUDE.md`'s Project Notes with conversation context that isn't in
   the spec.
6. Show a summary table (decisions / outputs / prior insights per section),
   confirm with the user, and recommend `/clear` before implementation.

## Development workflow

Three overlapping phases:

1. **Write & debug** — run scripts directly (`python src/compute.py`) to
   iterate. Write them recipe-ready from the start: parameterize decisions as
   CLI flags, write to convention paths, one script per output.
2. **Integrate** — add `recipe:` blocks to outputs in `astra.yaml`. Set
   `container:` at analysis level or per-recipe — an image name
   (`python:3.12-slim`) or a Containerfile path. Track with `lc status`.
3. **Materialize** — `lc run` executes recipes inside their declared
   containers and writes a content-addressed manifest next to each output.
   Done when `lc status` shows all `ok`.

**Always execute through `lc`.** Recipes must run via `lc run` so container
builds, option resolution, resource limits, and result paths apply. Treat
the underlying execution engine as a black box — never invoke schedulers or
container runtimes directly; that bypasses the reproducibility guarantees.
Running scripts directly is for debugging only: **an output is not done
until `lc run` produces it.**

**Build iteratively.** Bare `lc run` materializes every output across every
universe. Instead, name one upstream output at a time
(`lc run <output_id> --universe <name>`) so each intermediate can be
inspected before chaining downstream — not the whole DAG debugged from the
bottom of a long failure trace.

Outputs land at `results/<universe>/<output_id>/`, with the manifest at
`<output_dir>/.lightcone-manifest.json`. Path-rooted sub-analyses prefix
their own path: `<sub_path>/results/<universe>/<output_id>/`.

### Spec–Code Invariant

**`astra.yaml` must always reflect the code and vice versa.** When one
changes, update the other immediately:

- Add a decision to code? Add it to `astra.yaml` and all universe files.
- Add an output or change a script? Update its `recipe:` block.
- Remove or rename something? Update both sides and re-validate the spec.

### Creating sub-analyses

Each sub-analysis is just another `astra.yaml` nested in a directory:

1. Create `analyses/<name>/` with its own `astra.yaml` (and optionally
   `src/`, `universes/baseline.yaml`, `results/`).
2. Add a `path:` entry under the parent's `analyses:`
   (`analyses: { my_sub: { path: ./analyses/my_sub } }`).
3. Add `<name>: { universe: baseline }` to each existing parent universe
   file.

Wire inputs and decisions to the parent or siblings with `from:` references
— the grammar is in the astra skill's spec reference.

## CLI reference

```bash
uvx --from lightcone-cli@0.4.0 lc init [DIR] [--permissions yolo|recommended|minimal] [--scratch PATH]  # Scaffold a new project
uvx --from lightcone-cli@0.4.0 lc run [OUTPUTS...] [--universe NAME] [--force] [--verbose] [--rerun-triggers TRIGGERS]  # Materialize outputs
uvx --from lightcone-cli@0.4.0 lc build [--force] [--runtime docker]   # Build container images from specs
uvx --from lightcone-cli@0.4.0 lc status [--universe NAME] [--json]    # Materialization status
uvx --from lightcone-cli@0.4.0 lc verify [--universe NAME]             # Recompute hashes, walk the provenance chain
uvx --from lightcone-cli@0.4.0 lc export wrroc [--output PATH] [--universe NAME] [--zip] [--metadata-only] [--author "NAME <EMAIL>"]  # Export RO-Crate bundle
```

`lc run` is quiet by default — pass `--verbose` for worker output. It
auto-builds container images on demand, so `lc build` is only for
pre-warming or forcing a rebuild. `--scratch` matters only on HPC sites
where `$HOME` doesn't honor `flock` (NERSC etc.). The first `lc` invocation
auto-creates `~/.lightcone/config.yaml` (`container.runtime: auto`, or
`docker | podman | podman-hpc | none`).

## Status interpretation

`lc status` shows each declared output's state per universe (`--json` for
machine-readable):

- `ok` — recipe exists, results on disk, manifest matches the spec. Done.
- `stale` — recipe or decisions changed since the last run. Re-run `lc run`.
- `missing` — recipe exists but no manifest (never run, or deleted). Run
  `lc run`.
- `alias` — no recipe of its own; produced as a side effect of an upstream
  output or a `from:` reference. Not independently materializable.

## Failure diagnosis

- **Script arg not recognized** — the recipe's `command` template controls
  how decisions reach the script: each `{decisions.<id>}` must pair with a
  flag the script's argparse defines (`--<id> {decisions.<id>}` ↔
  `parser.add_argument('--<id>')`).
- **Recipe input not found** — materialize upstream outputs first.
- **Undeclared placeholder** — a `{decisions.<id>}` / `{inputs.<id>}` in the
  recipe isn't listed in the Output's `decisions` / `inputs`. Declare it or
  remove the placeholder.
- **`lc verify` failure** — `missing_manifest` (output dir with no
  manifest), `tampered_data` (bytes no longer hash to the recorded
  `data_version`), or `broken_chain` (an upstream's `data_version` drifted
  from what this manifest recorded). Re-run the affected output to repair.

After a fix: `uvx --from lightcone-cli@0.4.0 lc run <output_id> --universe <name>`.

## Publishing

`lc export wrroc` bundles manifests, workflow definition, decisions, and
(optionally) data files into a
[Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/)
— a JSON-LD package readable by RO-Crate-aware archives (WorkflowHub,
Zenodo's RO-Crate plugin, etc.). On-disk manifests are unchanged; the
bundle is generated on demand.

```bash
uvx --from lightcone-cli@0.4.0 lc export wrroc                              # ./wrroc/ directory
uvx --from lightcone-cli@0.4.0 lc export wrroc -o run.zip --zip             # zip bundle
uvx --from lightcone-cli@0.4.0 lc export wrroc --metadata-only              # no data files
uvx --from lightcone-cli@0.4.0 lc export wrroc -u baseline -u alt_method    # specific universes
uvx --from lightcone-cli@0.4.0 lc export wrroc --author "Name <email@host>" # override git config
```

Before publishing, run `lc verify` so the provenance chain is known-good.

## Anti-patterns

- **Re-interviewing on resume** — the spec and `CLAUDE.md` already answer
  the scoping questions; summarize state and ask what's *next* instead.
- **Skipping orientation** — acting before reading `astra.yaml` and running
  `lc status` on an existing project.
- **Writing code during scoping** — the spec comes first; implementation
  starts after finalize.
- **Waiting to write** — update `astra.yaml` as each decision crystallizes,
  not in bulk at the end.
- **Chat dumps** — decisions and findings belong in the file for review, not
  pasted wholesale into the conversation.
- **Reading PDFs in the main context** — always delegate paper extraction
  to one subagent per paper.
- **Skipping verification** — if quotes were extracted, run the astra
  skill's evidence verification before calling scoping done.
- **Bypassing `lc`** — direct scheduler/container invocations, or treating a
  debug run of a script as a materialized result.
- **Running the whole DAG at once** — materialize one output at a time while
  integrating.
