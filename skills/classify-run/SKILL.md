---
name: classify-run
description: >
  Decide whether a Lightcone target should run synchronously in the current
  local or SLURM allocation or asynchronously through lc run --async. Detect
  compute allocation versus cluster login node, compare ASTRA recipe.resources
  with worker-node capacity and remaining walltime, and return or execute the
  exact lc command. Use immediately before every production lc run or submission,
  after allocation or session changes, when resuming work, or whenever asked to
  run, queue, submit, or choose sync versus async execution.
---

# Classify Lightcone Run

Choose the execution mode from fresh environment facts. Treat resource estimates
as reusable inputs and classification as ephemeral: repeat this workflow whenever
the allocation, remaining walltime, target DAG, or user lifetime requirement changes.

## Prerequisites

1. Confirm the CLIs resolve:

   ```bash
   command -v lc
   command -v astra
   ```

   If either is missing, tell the user to run `uv tool install lightcone-cli`
   and stop.

2. Work from the project containing `astra.yaml`. Discover the installed surface:

   ```bash
   lc run --help
   lc status --help
   lc --help
   ```

   If `lc run --async` is unavailable, record that limitation and continue the
   classification. If the result is asynchronous, stop and recommend upgrading
   lightcone-cli. Never substitute a hand-written `sbatch` command.

## 1. Resolve the run

Identify the exact outputs and universes the user intends to materialize. Inspect
the root and relevant sub-analysis specs, universe files, and `lc status --json`.
Resolve the required upstream sub-DAG rather than checking only the named leaf.

Read `recipe.resources` for every rule that may run. If CPU, memory, GPU, or
`time_limit` requirements are missing, stale relative to the recipe/workload, or
too uncertain to defend, stop and use `estimate`. Do not invent resource values
inside this skill.

## 2. Identify the execution environment

Use this execution model as an invariant:

| Environment | Plain `lc run` | `lc run --async` |
|---|---|---|
| SLURM compute allocation (`SLURM_JOB_ID` set) | Reuses the current allocation; starts the scheduler and `srun` workers inside it; does not queue or acquire new resources | Submits a separate batch allocation |
| Cluster login/submit node without an allocation | Prohibited for compute work | Allowed; submission itself may run here |
| Non-cluster local machine | Runs on local resources | Only valid when a SLURM backend/account is configured and reachable |

Do not equate “outside SLURM” with “local machine.” First determine whether the
host is a known/configured cluster login or submit node using site configuration,
hostname, and available scheduler commands.

When `SLURM_JOB_ID` is set, collect the current synchronous budget immediately
before deciding:

```bash
env | grep '^SLURM_' | sort
squeue -h -j "$SLURM_JOB_ID" -O TimeLeft
```

Use `SLURM_CPUS_ON_NODE`, `SLURM_MEM_PER_NODE`, `SLURM_GPUS_ON_NODE`, and
`SLURM_NNODES` when present. If essential facts are absent, inspect the current
job with scheduler read-only commands. Outside a cluster, inspect local CPU,
available memory, and GPUs with tools such as `nproc`, `free -b`, and `nvidia-smi`.

## 3. Compare demand with the current budget

For synchronous execution, require all of the following:

1. Every rule fits on one available worker node unless its recipe explicitly
   launches distributed work.
2. The requested CPU/GPU concurrency fits the current allocation or local host.
3. The conservative runtime for the required sub-DAG fits the allocation's
   remaining walltime, including upstream work, startup, and shutdown margin.
4. The work may remain coupled to the current agent/allocation lifetime.

Use the recorded padded `time_limit` values and DAG structure. Do not compare
only the leaf rule or the original unpadded pilot runtime. Never assume multi-node
or multi-GPU speedup that the estimate did not measure.

## 4. Classify

Return one of these decisions:

- **Synchronous:** all rules and conservative total runtime fit the current
  allocation or local host, with adequate margin and acceptable lifetime coupling.
- **Asynchronous:** the agent is on a cluster login node, the job does not fit
  the current allocation, remaining walltime is insufficient, or the work must
  survive the current session/allocation.
- **Estimate first:** declared resources are missing, stale, or too uncertain.

On a local machine without a configured SLURM backend, recommend a larger local
or interactive allocation instead of claiming async submission will work. If
several Perlmutter shapes are valid, prefer the smallest shape that fits `shared`;
use a larger `regular` shape only when measured speedup or memory need justifies it.

Treat `lc` preflight failures as authoritative. If plain `lc run` reports that
declared resources or walltime cannot fit, preserve its diagnostic and use the
copyable `lc run --async ...` retry it provides.

## 5. Execute only when requested

If the user asked only for classification, report the decision and exact next
command without running or submitting it. If execution was requested, always use
`lc`:

```bash
# Reuse the current allocation or local host
lc run <output> --universe <universe>

# Submit a detached SLURM allocation
lc run --async <output> --universe <universe>

# Observe materialization and queued/running state
lc status --universe <universe>
```

Pass `--account` when requested or when neither configuration nor the current
allocation supplies one. Submission may originate on a login or compute node.
Do not call `sbatch`, `srun`, Snakemake, or `podman-hpc` yourself. The submitted
batch job must enter the same plain `lc run` path so container wrapping—including
`podman-hpc`—validation, locking, and manifests stay identical to synchronous
execution.

## Result

Conclude with a compact table:

| Output / universe | Declared demand | Current environment | Decision | Next command |
|---|---|---|---|---|

State remaining walltime, the limiting rule or resource, lifetime requirements,
and any assumption that could change the decision.
