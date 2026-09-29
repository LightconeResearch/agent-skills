# Compute: allocations, offers and recipe resources

Read this when the local shortcut is not enough: sizing an allocation,
running on Slurm, using GPUs, or declaring what a recipe needs. The
everyday loop — reuse, `lc compute launch --wait`, pass the name, `down` —
is in the skill itself.

- [Choosing a shape](#choosing-a-shape)
- [Slurm](#slurm)
- [GPUs](#gpus)
- [Recipe resources](#recipe-resources)
- [Waiting and lifetime](#waiting-and-lifetime)

## Choosing a shape

`lc compute resources` lists the offers this host can request, in catalog
order: per-node shape, node limit, default and maximum time, startup class
(`fast` or `batch`). Free capacity is never known. A request selects the
**first** offer that satisfies it:

```bash
lc compute launch --cpus 32+ --memory 128GB+ --num-nodes 2 --time 2h --name fit-sweep --dry-run
```

- Quantities are **per node**. `32` is exact, `32+` at least 32. Compute
  memory is binary: `128`, `128GB` and `128GiB` all mean 128 GiB.
- Give `--cpus` and `--memory` together, or neither — neither is the local
  shortcut, which never selects a remote offer. The reverse can happen:
  the built-in local offer comes after the configured ones, so a request
  no remote offer fits lands on it. The plan's `offer` and `connection`
  say which you got.
- `--gpus A100:4` is exactly four A100s; `--gpus GPU:4` any model; the
  default `0` selects CPU-only offers. No `+` on GPU counts.
- `--startup fast` filters to fast-start offers; it promises no queue time.
- Without `--name`, an explicit request is named `lc-<12 hex>`. Name it
  after the work instead (`--name fit-sweep`): you will type it again.

Size it from the recipes. Each recipe runs on **one worker**, so the
largest `recipe.resources` must fit a single node; more nodes add recipes
in parallel, never room for one. The lifetime must cover the whole run you
are about to start.

Show the user the `--dry-run` plan before any non-local launch and wait
for agreement. When nothing matches, the error names why each offer was
skipped — relay it rather than retrying with other numbers.

## Slurm

The catalog (`~/.lightcone/compute.yaml`, or the file `LC_COMPUTE_CONFIG`
names) declares `connections` (a stable `namespace` UUID,
`provider: slurm`, `context:` the Slurm cluster name) and ordered `offers`
whose `config` carries `submit` (`sbatch` or `salloc`), `account`, `qos`,
`constraint`, `partition`, `reservation` and `gpu_type`. It is the user's:
the account is theirs to name and the file theirs to approve.

Its `local` block governs the built-in local offer, which follows the
configured ones. `local: {resources: {cpus: 4, memory: 8GiB}}` shrinks it
(both fields, or neither); `local: {enabled: false}` blocks local launch
and execution, while existing local clusters stay inspectable and
stoppable. Recognized NERSC login nodes need neither: `lc` refuses local
compute there on its own, and no setting overrides that — interactive
compute nodes stay eligible. Elsewhere, a login node's catalog sets
`enabled: false`. The name `local` is reserved: no configured connection,
nor (while local is enabled) offer, may take it.

Things that surprise on a first Slurm run:

- **Shell `SBATCH_*` / `SALLOC_*` / `SLURM_*` variables are dropped**
  before `lc` calls Slurm. An account in the profile does nothing; it
  belongs in the offer's `config.account`.
- **Workers run the driver's `lc` install.** Launch from a
  `uv tool install`ed `lc`, never through `uvx`, whose environment can be
  pruned mid-allocation. After upgrading `lc`, launch a new allocation.
- **NERSC: move uv's cache first.** Compute nodes cannot lock files in
  `$HOME`, so every recipe fails with `Could not acquire lock (os error
  524)`. `export UV_CACHE_DIR=$PSCRATCH/uv-cache` in the user's profile,
  then relaunch — workers keep the environment they started with.
- **Active is not ready.** A job can run with no Dask workers connected.
  The reason is in the submission log under
  `~/.lightcone/compute/submissions/<token>/`, on a line starting
  `Slurm Dask startup failed:`.
- **Containerized projects** need the image on every node; at NERSC,
  `podman-hpc` exposes the migrated image across nodes.

## GPUs

GPUs exist only where an offer declares them (`accelerators: A100:4` or
`{A100: 4}`); `lc` probes no hardware. On Slurm the offer's
`config.gpu_type` maps the label to the site's GRES name. A local GPU
offer also needs the device mask at launch:

```bash
CUDA_VISIBLE_DEVICES=0 lc compute launch --cpus 4 --memory 8GB --gpus GPU:1 --wait
```

- A recipe with `gpus: N` needs at least N on its worker, reserves all of
  that worker's GPUs, and sees the whole mask — possibly more than N. One
  GPU recipe runs per worker at a time; recipes without `gpus` see none.
- **Containerized GPU recipes run only on `podman-hpc`** (or with no
  container at all). Under plain Docker or Podman, `lc materialize` refuses
  them before building anything.
- An `lc run` probe under plain Docker or Podman runs **without** GPUs and
  says so in a note — the allocation may still have them. Do not conclude
  from such a probe that the hardware is missing.
- A standalone `datalad rerun` of a GPU output needs its own
  `CUDA_VISIBLE_DEVICES`; it inherits nothing from the old allocation.

## Recipe resources

`recipe.resources` is ASTRA schema (the astra skill covers the format).
What `lc` does with it:

```yaml
recipe:
  command: python src/fit.py --output {output}
  resources: {cpus: 4, memory: 8Gi, gpus: 1}
```

| Field | `lc` |
|---|---|
| `cpus` | Whole number, default 1 |
| `memory` | Units required: `512Mi`, `8Gi` (binary), `8GB` (decimal). Omitted reserves no RAM |
| `gpus` | Whole number, default 0; the type is chosen at allocation, not here |
| `time_limit`, `disk`, fractional `cpus` | **Refused** by `lc materialize` before anything runs — `lc status` and `--check` accept them, so the refusal only shows up at run time. Walltime belongs to `lc compute launch --time` |

- The request must fit one worker, or the run refuses up front. Only
  outputs that may rebuild are checked; current ones reserve nothing.
- Reservations are **scheduling, not enforcement**. A recipe that spawns
  more threads or allocates more RAM than it declared will get them and
  starve its neighbours — declare what the code really uses.
- **Numerical-library threads default to 1** on every worker
  (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`), whatever
  `cpus` says. A recipe that should use N threads declares `cpus: N` *and*
  gets the variables: exported before `lc compute launch` (then every
  recipe on that cluster has them), or set in the command
  (`env OMP_NUM_THREADS=8 python …`), which changes the recipe string and
  so makes the output `stale`.
- Editing `resources:` alone makes nothing `stale`: an output's identity is
  its rendered recipe, decisions and format.

## Waiting and lifetime

- `launch` without `--wait` returns once the allocation is accepted;
  `lc compute status <name> --wait` then waits for readiness. Both default
  to a 300-second deadline — pass `--timeout` for a batch queue. A timeout
  exits 1 and leaves the allocation queued: check it again rather than
  launching a second one. Running `lc compute status <name> --wait` in the
  background while other work proceeds is fine.
- An uncertain submission error carries a `submission_token` and maybe an
  `id`: run `lc compute status --json` before retrying, since the first
  submission may have been accepted.
- `lc compute status` cannot tell you the time left. Note when you
  launched and what `--time` the plan shows. A run that will not fit in
  the remaining lifetime goes on a fresh, longer allocation — walltime
  kills recipes mid-write.
- After an allocation dies under a run, its partial outputs stay in
  `results/`. Confirm it has ended (`lc compute status <full-id>` shows
  `ended`), then discard them as the dirty-tree refusal instructs.
