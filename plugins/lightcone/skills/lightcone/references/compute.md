# Compute: allocations, offers and recipe resources

Read this when the local shortcut is not enough: sizing an allocation,
running on Slurm, using GPUs, or declaring what a recipe needs.

- [Choosing a shape](#choosing-a-shape)
- [Slurm](#slurm)
- [GPUs](#gpus)
- [Recipe resources](#recipe-resources)
- [Waiting and lifetime](#waiting-and-lifetime)

## Choosing a shape

`lc compute resources` lists the offers in selection order; free capacity
is never known. A request takes the **first** offer that satisfies it:

```bash
lc compute launch --cpus 32+ --memory 128GB+ --num-nodes 2 --time 2h --name fit-sweep --dry-run
```

- Quantities are **per node**. `32` is exact, `32+` at least 32. Compute
  memory is binary: `128`, `128GB` and `128GiB` all mean 128 GiB.
- Give `--cpus` and `--memory` together, or neither — neither is the local
  shortcut, which never selects a remote offer. The reverse can happen: a
  request no configured offer fits falls to the built-in local one. The
  plan's `offer` says which.
- `--gpus A100:4` is exactly four A100s; `--gpus GPU:4` any model; the
  default `0` selects CPU-only offers. No `+` on GPU counts.
- `--startup fast` filters to fast-start offers; it promises no queue time.
- Name an explicit request after the work (`--name fit-sweep`); otherwise
  it gets `lc-<12 hex>`, which you will have to type again.

Size it from the recipes. Each recipe runs on **one worker**, so the
largest `recipe.resources` must fit a single node; more nodes add recipes
in parallel, never room for one.

## Slurm

The catalog (`~/.lightcone/compute.yaml`, or the file `LC_COMPUTE_CONFIG`
names) declares `connections` (a stable `namespace` UUID,
`provider: slurm`, `context:` the Slurm cluster name) and ordered `offers`
whose `config` carries `submit` (`sbatch` or `salloc`), `account`, `qos`,
`constraint`, `partition`, `reservation` and `gpu_type`.

Its `local` block shapes the built-in offer: `resources: {cpus: 4,
memory: 8GiB}` (both or neither) shrinks it, `enabled: false` turns local
compute off — what a login node's catalog wants, except at NERSC, where
`lc` already refuses it on login nodes. No connection or offer may be
named `local`; that name is the built-in's.

Things that surprise on a first Slurm run:

- **Shell `SBATCH_*` / `SALLOC_*` / `SLURM_*` variables are dropped**
  before `lc` calls Slurm. An account in the profile does nothing; it
  belongs in the offer's `config.account`.
- **Workers run the driver's `lc` install.** Launch from a
  `uv tool install`ed `lc`, never through `uvx`, whose environment can be
  pruned mid-allocation.
- **NERSC: move uv's cache first.** Compute nodes cannot lock files in
  `$HOME`, so every recipe fails with `Could not acquire lock (os error
  524)`. `export UV_CACHE_DIR=$PSCRATCH/uv-cache` in the user's profile,
  then relaunch.
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

- A recipe with `gpus: N` takes a worker with at least N to itself and
  sees its whole mask — possibly more than N. Recipes without `gpus` see
  none.
- **Containerized GPU recipes run only on `podman-hpc`** (or with no
  container at all). Under plain Docker or Podman, `lc materialize` refuses
  them before building anything.
- An `lc run` probe under plain Docker or Podman gets no GPUs, and its
  note says so; that says nothing about the allocation's hardware.
- A standalone `datalad rerun` of a GPU output needs its own
  `CUDA_VISIBLE_DEVICES`; it inherits nothing from the old allocation.

## Recipe resources

What `lc` does with ASTRA's `recipe.resources`:

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
| `time_limit`, `disk`, fractional `cpus` | **Refused** by `lc materialize`, though `lc status` and `--check` pass them. Walltime is `lc compute launch --time` |

- Reservations are **scheduling, not enforcement**. A recipe that spawns
  more threads or allocates more RAM than it declared will get them and
  starve its neighbours — declare what the code really uses.
- **Numerical-library threads default to 1** on every worker
  (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`), whatever
  `cpus` says. A recipe that should use N threads declares `cpus: N` *and*
  gets the variables: exported before `lc compute launch` (every recipe on
  that cluster gets them), or set in the command
  (`env OMP_NUM_THREADS=8 python …`), which changes the recipe string and
  so makes the output `stale`.
- Editing `resources:` alone makes nothing `stale`: an output's identity is
  its rendered recipe, decisions and format.

## Waiting and lifetime

- `--wait` gives up after 300 seconds; pass `--timeout` for a batch queue,
  or launch without `--wait` and run `lc compute status <name> --wait` in
  the background.
- A launch that failed or timed out may still hold an allocation: its
  error carries the `id` or a `submission_token`. Check
  `lc compute status --json` before retrying, never launch a second one.
- `lc compute status` cannot tell you the time left. Note when you
  launched and the plan's `--time`; a run that will not fit goes on a
  fresh, longer allocation.
