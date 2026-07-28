---
name: cli
description: >
  Reference for `lc` CLI execution: commands (init/run/status/verify/build/export),
  the Spec-Code Invariant (`astra.yaml` and code never diverge), status
  interpretation (ok/stale/missing/alias), failure diagnosis, multiverse
  runs, scratch overrides for HPC, sub-analysis scaffolding, publishing
  via WRROC. Invoke whenever running, debugging, or diagnosing `lc`
  workflows; whenever interpreting `lc status` / `lc verify` output; or
  whenever the user asks about the development workflow surrounding
  `astra.yaml`.
---

# lightcone-cli Reference

Reference for lightcone-cli execution: CLI commands, development workflow, status interpretation, and failure diagnosis. For `astra.yaml` spec syntax, invoke `/astra`.

## Prerequisites

Run `lc --version` and inspect `lc <subcommand> --help` before relying on flags; use the installed CLI as the command-surface authority.

## CLI Reference

```bash
lc init [DIR] [--no-git] [--no-venv] [--permissions yolo|recommended|minimal] [--scratch PATH]  # Scaffold a new ASTRA project
lc run [OUTPUTS...] [--universe NAME] [--jobs N] [--force] [--verbose] [--rerun-triggers TRIGGERS]  # Materialize outputs
lc build [--force] [--runtime docker|podman|podman-hpc|kubernetes]  # Build container images from specs
lc status [--universe NAME] [--json]                              # Materialization status (text or JSON)
lc verify [--universe NAME]                                       # Recompute hashes and walk the provenance chain
lc export wrroc [--output PATH] [--universe NAME] [--zip] [--metadata-only] [--author "NAME <EMAIL>"] [--license SPDX_OR_URL]  # Export Workflow Run RO-Crate bundle
```

`lc run` shows each completed recipe's stdout/stderr as a clean narrative. Pass `--verbose` to additionally expose Dask, Snakemake, and executor output. `lc init --scratch PATH` records a project scratch override for Snakemake state, Dask spill, and the run lock. Without it, scratch resolves from `LIGHTCONE_SCRATCH`, project configuration, the detected site, then the system temporary directory.

The first `lc` invocation auto-creates `~/.lightcone/config.yaml`:

```yaml
container:
  runtime: auto    # or: docker | podman | podman-hpc | kubernetes | none
```

`lc run` always dispatches through Dask. It connects to `DASK_SCHEDULER_ADDRESS` when set; otherwise it creates a run-scoped Dask Gateway cluster on a configured JupyterHub, launches workers with `srun` when invoked inside a SLURM allocation, or uses a local cluster. Obtain the SLURM allocation before running it. On JupyterHub, `lc build` uses the deployment's Cloud Build service and recipes run directly in Gateway worker pods. A Gateway run supports one resolved container image, so consolidate projects that declare multiple images. Keep the `lightcone-cli` requirement scaffolded in `requirements.txt`; Gateway worker images need the execution stack it installs.

If `runtime: auto` finds no local container runtime, recipes run on the host and `lc` warns that recorded container provenance will not match execution. Use an explicit `runtime: none` only when that tradeoff is intentional.

Only one `lc run` may operate on a project at a time. Use `--jobs N` on a single invocation for parallel work rather than launching concurrent runs.

**Always run via `lc`.** Recipes must execute through `lc run` so that container builds, option resolution, dependency wiring, provenance, and result paths are applied. Treat the underlying execution engine as a black box — never invoke schedulers or container runtimes directly, because that bypasses reproducibility guarantees.

## Creating Sub-Analyses

Execution currently supports the root analysis plus one direct sub-analysis level. Sub-analyses are scaffolded by hand, since each one is another `astra.yaml` nested in a directory. Do not nest another `analyses:` tree inside a child spec. To add one:

1. Create `analyses/<name>/` with its own `astra.yaml` and `universes/baseline.yaml` (and optionally `src/` and `results/`).
2. Add a `path:` entry to the parent `astra.yaml` under `analyses:` (e.g. `analyses: { my_sub: { path: ./analyses/my_sub } }`).
3. Add a `<name>: { universe: baseline }` entry to each existing parent universe file.

Populate the sub-analysis's `astra.yaml` with inputs, outputs, and decisions. Use `from:` references to wire inputs to parent or sibling outputs and decisions to the parent — invoke `/astra` and see "Composition Mechanics" for the grammar.

## Development Workflow

Three overlapping phases:

1. **Write & Debug** — Run scripts directly (`python src/compute.py`) to iterate. Write them recipe-ready from the start: parameterize decisions, write to convention paths, one script per output.
2. **Integrate** — Add `recipe:` blocks to outputs in `astra.yaml`. Track with `lc status` (`alias` / `missing` / `stale` / `ok`). Set `container:` at analysis level or per-recipe — pass an image name (e.g., `python:3.12-slim`) or a path to a Containerfile (e.g., `Containerfile`).
3. **Materialize** — `lc run` executes recipes inside their declared containers and writes a content-addressed manifest next to each output. Done when every recipe-bearing output is `ok`; recipe-less outputs remain `alias`.

Bare `lc run` materializes every recipe-bearing output across every discovered universe; pass `OUTPUT_ID...` to scope to specific outputs and `--universe NAME` to scope to one universe. If an output id is ambiguous across analyses, qualify it as `<analysis_id>.<output_id>`. **Build iteratively** — name one upstream output at a time (`lc run <output_id> --universe <name>`) so you can inspect each intermediate before chaining further downstream, rather than running the whole DAG and debugging from the bottom of a long failure trace. `lc run` auto-builds container images on demand, so `lc build` is only needed for pre-warming or forcing a rebuild with `--force`.

Outputs land at `results/<universe>/<output_id>/`, with the per-output manifest at `<output_dir>/.lightcone-manifest.json`. Path-rooted sub-analyses prefix the sub's path: `<sub_path>/results/<universe>/<output_id>/`.

**An output is not done until `lc run` produces it.** Running scripts directly is for debugging only — final results must always come from `lc run` so they are reproducible.

### Spec-Code Invariant

**`astra.yaml` must always reflect the code and vice versa.** When you change one, update the other immediately:
- Add a decision to code? Add it to `astra.yaml` and all universe files.
- Add an output or change a script? Update the `recipe:` block in `astra.yaml`.
- Remove or rename something? Update both sides and run `astra validate astra.yaml`.

## Status Interpretation

`lc status` shows each declared output's materialization state per universe. Pass `--json` for machine-readable output.

- `ok` — Recipe exists and its manifest's code version matches the current recipe command, resolved container image, and declared decisions. This does not verify result bytes; use `lc verify` for integrity.
- `stale` — The recipe command, resolved image, or one of the output's declared decisions changed. Re-run `lc run`.
- `missing` — Recipe exists but no readable manifest was found. Run `lc run`.
- `alias` — Output has no recipe of its own; produced as a side effect of an upstream output (or a `from:` reference into a sub-analysis). Not independently materializable.

## Failure Diagnosis

- **Script arg not recognized** — The recipe's `command` template controls how decisions reach the script. Make sure each `{decisions.<id>}` is paired with a flag the script's argparse defines (e.g. `--<id> {decisions.<id>}` ↔ `parser.add_argument('--<id>')`).
- **Declared input not found** — Targeting a downstream output automatically includes declared upstream recipes. Validate `astra.yaml`, then fix the output's `inputs:` / `from:` wiring or the missing external input's `source:`.
- **Undeclared placeholder error** — A `{decisions.<id>}` or `{inputs.<id>}` in the recipe references something not listed in `Output.decisions` / `Output.inputs`. Add it to the Output's declaration, or remove the placeholder.
- **`lc verify` failure** — `missing_manifest` (output dir exists with no `.lightcone-manifest.json`), `tampered_data` (bytes on disk no longer hash to the recorded `data_version`), or `broken_chain` (an upstream's `data_version` drifted from what this output's manifest recorded). Use `lc run --force <output> --universe <name>` to intentionally regenerate tampered data; a normal targeted `lc run` repairs missing manifests and broken downstream chains.

After a workflow failure, read the recipe output already printed in the terminal. `--verbose` adds executor diagnostics; in non-verbose mode, an engine failure prints the path of a bounded `snakemake-stderr-<pid>.log` under the resolved scratch root. Fix, then run `lc run <output_id> --universe <name>`.

## Publishing Analyses

`lc export wrroc` bundles the project's manifests, workflow definition, decisions, and (optionally) data files into a [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/) — a JSON-LD package readable by RO-Crate-aware archives (WorkflowHub, Zenodo's RO-Crate plugin, etc.). The lightcone manifest format on disk is unchanged; the bundle is generated on demand.

```bash
lc export wrroc                                # ./wrroc/ directory
lc export wrroc -o run.zip --zip               # zip bundle
lc export wrroc --metadata-only                # provenance graph + manifests only (no data files)
lc export wrroc -u baseline -u alt_method      # restrict to specific universes
lc export wrroc --author "Name <email@host>"   # override git config
lc export wrroc --license BSD-3-Clause         # override the default CC-BY-4.0 license
```

The bundle's `@graph` contains a `ComputationalWorkflow` (the astra.yaml), one `CreateAction` per materialized output (with `object` referencing upstream datasets and external inputs, `result` referencing the produced dataset, and `instrument` referencing the recipe `SoftwareApplication`), `PropertyValue` entries for decisions and provenance metadata (`code_version`, `data_version`), and a `Person` for the author.
