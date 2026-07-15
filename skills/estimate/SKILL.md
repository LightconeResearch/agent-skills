---
name: estimate
description: >
  Estimate CPU, memory, GPU, disk, and walltime requirements for Lightcone
  outputs; record them in ASTRA recipe.resources; and decide whether a target
  fits the current local/SLURM allocation or should use lc run --async. Use for
  expensive simulations, training, scaling studies, resource-related scheduling
  failures, first asynchronous submissions, or any request to size, benchmark,
  queue, or classify a Lightcone job.
---

# Estimate Lightcone Resources

Estimate from evidence, write the estimate into the ASTRA specification, and
recommend synchronous or asynchronous execution. Do not turn judgment calls
into engine policy: `lc` owns deterministic validation and submission, while
this skill owns measurement, extrapolation, and run-shape choices.

## Prerequisites

1. Confirm the CLIs resolve:

   ```bash
   command -v lc
   command -v astra
   ```

   If either is missing, tell the user to run `uv tool install lightcone-cli`
   and stop.

2. Work from the project containing `astra.yaml`. Read the relevant root or
   sub-analysis spec, universe file, recipe, and source code before estimating.

3. Discover the installed command surface rather than guessing:

   ```bash
   lc run --help
   lc status --help
   lc --help
   ```

   If `lc run --async` is unavailable, explain that the installed
   lightcone-cli does not yet support asynchronous submission and recommend an
   upgrade. Never replace it with a hand-written `sbatch`, which would bypass
   Lightcone's snapshot, container, validation, and manifest path.

## 1. Resolve the target

Identify the output(s) and universe(s) being estimated. If the request is
ambiguous, inspect `astra.yaml`, `universes/`, and `lc status --json`, then ask
only for the choice that materially changes the estimate.

For every rule in the requested output's upstream sub-DAG, inspect:

- `recipe.command`, `recipe.container`, and existing `recipe.resources`;
- source code, configs, and data sizes that control cost;
- declared inputs and decisions, including production-scale values;
- actual parallelism: process/thread count, GPU use, and whether one rule can
  span nodes. A Dask rule must fit on one worker node unless the recipe itself
  launches distributed work.

Do not estimate only the named leaf when an expensive upstream rule is also
required.

## 2. Inspect available capacity

Inside SLURM, collect the current allocation facts without launching work:

```bash
env | grep '^SLURM_' | sort
squeue -h -j "$SLURM_JOB_ID" -O TimeLeft
```

Use `SLURM_CPUS_ON_NODE`, `SLURM_MEM_PER_NODE`, `SLURM_GPUS_ON_NODE`, and
`SLURM_NNODES` when present. Outside SLURM, inspect local CPU count, available
memory, and GPUs with platform-appropriate tools such as `nproc`, `free -b`,
and `nvidia-smi`.

Distinguish **capacity** from **availability**: the resource request describes
what a rule needs; sync/async classification additionally considers the time
remaining in the current allocation.

## 3. Decide whether to measure

Skip pilots when cost is obvious and small: file conversion, plotting, or a
short deterministic script over already-materialized inputs. Use conservative
static estimates based on code paths and input sizes.

Measure when the production run is expensive, nonlinear, GPU-memory-sensitive,
or uncertain enough that a wrong request could waste an allocation or time out.
Before running pilots, state the scale points, expected pilot duration, and what
will be extrapolated. Never launch a full production or queued run merely
because the user asked for an estimate.

### Pilot design

1. Identify the dominant scale axis: samples, grid resolution, particles,
   epochs, steps, simulations, or another decision/config value.
2. Choose 2-3 points that finish quickly in the current allocation and are
   large enough to get past startup overhead.
3. Keep algorithm, container, precision, batch size, and hardware fixed while
   varying one scale axis. If job shape changes, treat it as a separate model.
4. Prefer provenance-tracked pilot universes when the scale is already an ASTRA
   decision. Otherwise run an isolated command with a temporary output path;
   never overwrite canonical `results/`.
5. Measure walltime and peak resident memory with `/usr/bin/time -v`. For GPU
   jobs, sample per-process memory with `nvidia-smi` during the run. Record the
   exact command, scale, node shape, exit status, elapsed time, peak RSS, and
   peak GPU memory.

Store raw measurements in `.lightcone/estimates.json`, merging rather than
overwriting prior entries. Include the timestamp, output/universe, scale axis,
samples, model, safety factor, and resulting request so the estimate can be
audited and revised.

### Extrapolation

- Use a stated model justified by the algorithm: linear for epochs or samples,
  quadratic/cubic only when code structure or measurements support it.
- With noisy or sparse samples, prefer a conservative upper envelope over a
  precise-looking fit.
- Estimate memory separately from runtime. Peak memory often follows batch
  size, model size, or resolution rather than the runtime scale axis.
- Do not assume multi-GPU or multi-node speedup. Measure that shape or describe
  it as an unverified alternative.
- Pad projected runtime by at least 1.5x; use 2x or more for weak evidence or
  high variance. Pad peak memory by at least 25% and round upward to a practical
  request.

## 4. Record resources in ASTRA

Write the final per-rule request into the owning recipe:

```yaml
recipe:
  command: python src/train.py --output {output}
  container: Containerfile
  resources:
    cpus: 32
    memory: "128GB"
    gpus: 1
    time_limit: "8h"
```

Use ASTRA names (`cpus`, `memory`, `gpus`, `disk`, `time_limit`), not internal
Snakemake names such as `mem_mb` or `gpus_per_task`. Omit `disk` when there is
no meaningful temporary-storage requirement. Preserve unrelated spec content,
then validate:

```bash
astra validate astra.yaml
```

Fix validation errors before recommending a run. Resource estimates do not
change scientific provenance, but the measurement notes must explain their
basis.

## 5. Classify sync versus async

Classify each requested target after all required rules have estimates:

- **Synchronous:** every rule fits one available worker node and the padded
  `time_limit` fits the current allocation's remaining walltime with room for
  upstream work and shutdown.
- **Asynchronous:** the shape does not fit the current allocation, remaining
  walltime is insufficient, the work should survive the agent session, or the
  current environment is a login node where compute is prohibited.
- **Pilot first:** uncertainty is still large enough that neither request is
  defensible.

On a local machine without a configured SLURM backend, recommend a larger local
or interactive allocation instead of claiming `--async` will work. If several
shapes are valid on Perlmutter, prefer the smallest shape that fits `shared`;
only recommend a larger `regular` shape when the measured speedup or memory need
justifies it.

Treat `lc` preflight failures as authoritative. If synchronous `lc run` reports
that declared resources or walltime cannot fit, preserve the diagnostic and
recommend its copyable `lc run --async ...` retry.

## 6. Execute only when requested

If the user asked only for an estimate or recommendation, stop after updating
and validating the spec. Report the evidence, request, classification, and exact
next command without submitting anything.

When the user has asked to run or submit, always use `lc`:

```bash
# Fits the current allocation
lc run <output> --universe <universe>

# Needs a detached SLURM allocation
lc run --async <output> --universe <universe>

# Observe materialization and queued/running job state
lc status --universe <universe>
```

Pass `--account` when requested or when no configured/current allocation account
is available. Submission may originate on a login or compute node. Do not call
`sbatch`, `srun`, Snakemake, or `podman-hpc` yourself: the asynchronous job must
enter the same synchronous `lc run` path so container wrapping, including
`podman-hpc`, validation, locking, and manifests remain identical.

## Result

Conclude with a compact table:

| Output / universe | Evidence | Declared resources | Decision | Next command |
|---|---|---|---|---|

Call out extrapolation model, safety factor, QoS-cap risk, missing measurements,
and any assumption that could change the classification.
