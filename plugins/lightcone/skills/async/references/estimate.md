# Estimate Resource Requirements

Estimate from evidence and write the result into the ASTRA specification. Own
measurement, extrapolation, and the candidate job shape; do not choose the
current run mode or submit production work.

## Contents

- [Resolve the target](#1-resolve-the-target)
- [Inspect the measurement environment](#2-inspect-the-measurement-environment)
- [Decide whether to measure](#3-decide-whether-to-measure)
- [Record resources in ASTRA](#4-record-resources-in-astra)
- [Report the result](#result)

## 1. Resolve the target

Identify the output(s) and universe(s) being estimated. If the request is
ambiguous, inspect `astra.yaml`, `universes/`, and `lc status --json`, then ask
only for the choice that materially changes the estimate.

Read the relevant root or sub-analysis specification, universe file, recipes,
and source code. For every rule in the requested output's upstream sub-DAG,
inspect:

- `recipe.command`, `recipe.container`, and existing `recipe.resources`;
- source code, configs, and data sizes that control cost;
- declared inputs and decisions, including production-scale values;
- actual parallelism: process/thread count, GPU use, and whether one rule can
  span nodes. A Dask rule must fit on one worker node unless the recipe itself
  launches distributed work.

Do not estimate only the named leaf when an expensive upstream rule is also
required.

## 2. Inspect the measurement environment

Before launching a pilot, distinguish these environments so the pilot stays
within currently available resources:

- **Existing SLURM allocation (`SLURM_JOB_ID` is set):** the agent is already
  running inside a compute allocation. Pilot commands and plain `lc run` reuse
  that allocation; plain `lc run` does not submit another job. Keep pilots within
  its node shape and remaining walltime.
- **Cluster login/submit node without `SLURM_JOB_ID`:** do not run compute pilots
  on the login node. Request an interactive allocation or make a conservative
  static estimate from prior measurements.
- **Non-cluster local machine:** run only pilots that fit local CPU, memory, and
  GPU availability.

Inside a SLURM allocation, collect facts without launching work:

```bash
env | grep '^SLURM_' | sort
squeue -h -j "$SLURM_JOB_ID" -O TimeLeft
```

Use `SLURM_CPUS_ON_NODE`, `SLURM_MEM_PER_NODE`, `SLURM_GPUS_ON_NODE`, and
`SLURM_NNODES` when present. Outside SLURM, inspect local CPU count, available
memory, and GPUs with platform-appropriate tools such as `nproc`, `free -b`,
and `nvidia-smi`, but first establish that the host is not a cluster login node.

Record the process/thread count, container, precision, and workload settings that
can change the result. Use current capacity only to keep the pilot safe; hardware
provenance, hardware profiles, and cross-machine calibration are outside this
workflow.

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
3. Keep algorithm, container, precision, batch size, and execution environment
   fixed while varying one scale axis. If job shape changes, treat it as a
   separate model.
4. Prefer provenance-tracked pilot universes when the scale is already an ASTRA
   decision. Otherwise run an isolated command with a temporary output path;
   never overwrite canonical `results/`.
5. Measure walltime and peak resident memory with `/usr/bin/time -v`. For GPU
   jobs, sample per-process memory with `nvidia-smi` during the run. Record the
   exact command, scale, exit status, elapsed time, peak RSS, and peak GPU memory.

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

Use ASTRA names (`cpus`, `memory`, `gpus`, `time_limit`), not internal Snakemake
names such as `mem_mb` or `gpus_per_task`. Preserve unrelated spec content, then
validate:

```bash
uvx astra-tools@0.2.13 validate astra.yaml
```

Fix validation errors before returning the estimate. Resource estimates do not
change scientific provenance, but the measurement notes must explain their
basis.

## Result

Conclude with a compact table:

| Output / universe | Evidence | Pilot setup | Declared resources | Confidence |
|---|---|---|---|---|

Call out the extrapolation model, safety factor, QoS-cap risk, missing
measurements, and assumptions that would invalidate the estimate. Return to the
main async router. Do not classify or submit production work unless the user
also requested execution; in that case, perform the classification workflow
with fresh environment facts.
