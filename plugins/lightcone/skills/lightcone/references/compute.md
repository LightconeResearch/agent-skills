# Compute: shapes, GPUs and recipe resources

Read this when the local shortcut is not enough: a bigger or remote shape,
GPUs, or declaring what a recipe needs.

- [Choosing a shape](#choosing-a-shape)
- [GPUs](#gpus)
- [Recipe resources](#recipe-resources)
- [Waiting and lifetime](#waiting-and-lifetime)

## Choosing a shape

`lc compute resources` lists the offers in selection order; free capacity
is never known. When nothing on it fits the work, tell the user. A
request takes the **first** offer that satisfies it:

```bash
lc compute launch --cpus 32+ --memory 128GB+ --num-nodes 2 --time 2h --name fit-sweep --dry-run
```

- Quantities are **per node**. `32` is exact, `32+` at least 32. Compute
  memory is binary: `128`, `128GB` and `128GiB` all mean 128 GiB.
- Give `--cpus` and `--memory` together, or neither — neither is the local
  shortcut, which never selects a remote offer. The reverse can happen: a
  request nothing earlier in the list fits lands on the local offer. The
  plan's `offer` says which.
- `--gpus A100:4` is exactly four A100s; `--gpus GPU:4` any model; the
  default `0` selects CPU-only offers. No `+` on GPU counts.
- `--startup fast` filters to fast-start offers; it promises no queue time.
- Name an explicit request after the work (`--name fit-sweep`); otherwise
  it gets `lc-<12 hex>`, which you will have to type again.

Size it from the recipes. Each recipe runs on **one worker**, so the
largest `recipe.resources` must fit a single node; more nodes add recipes
in parallel, never room for one.

## GPUs

GPUs exist only where `lc compute resources` lists them; `lc` probes no
hardware. A local GPU offer also needs the device mask at launch:

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

- `--wait` gives up after 300 seconds; pass `--timeout` for an offer that
  is not `fast`, or launch without `--wait` and run
  `lc compute status <name> --wait` in the background.
- A cluster that stays unready: relay its `phase` and `reason` from
  `lc compute status <name>` to the user rather than relaunching.
- A launch that failed or timed out may still hold an allocation: its
  error carries the `id` or a `submission_token`. Check
  `lc compute status --json` before retrying, never launch a second one.
- `lc compute status` cannot tell you the time left. Note when you
  launched and the plan's `--time`; a run that will not fit goes on a
  fresh, longer allocation.
