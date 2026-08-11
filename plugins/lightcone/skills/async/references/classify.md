# Classify Production Execution

Choose the execution mode from fresh environment facts. Treat resource estimates
as reusable inputs and classification as ephemeral: repeat this workflow whenever
the allocation, remaining walltime, target DAG, or user lifetime requirement
changes.

## Contents

- [Resolve the run](#1-resolve-the-run)
- [Identify the execution environment](#2-identify-the-execution-environment)
- [Compare demand with the current budget](#3-compare-demand-with-the-current-budget)
- [Classify](#4-classify)
- [Execute only when requested](#5-execute-only-when-requested)
- [Report the result](#result)

## 1. Resolve the run

Confirm that `lc run --async` is available from the command surface discovered
by the main skill. If it is unavailable, record that limitation and continue the
classification. If the result is asynchronous, stop and recommend upgrading
lightcone-cli. Never substitute a hand-written `sbatch` command.

Async v1 is available only when Lightcone detects a configured NERSC Perlmutter
site. A local Slurm client, account string, or reachable remote scheduler does
not make `lc run --async` available from an unrecognized local host.

Identify the exact outputs and universes the user intends to materialize. Inspect
the root and relevant sub-analysis specs, universe files, and `lc status --json`.
Resolve the missing or stale work in the upstream sub-DAG rather than checking
only the named leaf or counting every already-materialized dependency.

Classify output by output. Within the unresolved DAG, find each explicit
materialized output whose recipe is expensive enough to need detached execution.
That output is the async boundary: its unresolved upstream dependencies travel
with it, while cheap downstream outputs wait until it materializes and are
classified again later. If the named final output is itself the expensive
boundary, target it directly. Assume the user's ASTRA structure provides the
required boundary; do not rewrite the analysis merely to manufacture one.

Never plan a bare `lc run --async`. Async submission requires one or more explicit
output ids and is intended for expensive materialized boundaries, not an implicit
whole-analysis run.

Read `recipe.resources` for every unresolved rule that may run up to each
candidate boundary. Already-current upstream recipes do not contribute to the
new allocation. If CPU, memory, GPU, or `time_limit` requirements are missing,
stale relative to the recipe/workload, or too uncertain to defend, return
**Estimate first**. Read the estimation reference, update and validate ASTRA,
then restart this workflow with fresh environment facts. Do not invent resource
values during classification.

## 2. Identify the execution environment

Use this execution model as an invariant:

| Environment | Plain `lc run` | `lc run --async` |
|---|---|---|
| SLURM compute allocation (`SLURM_JOB_ID` set) | Reuses the current allocation; starts the scheduler and `srun` workers inside it; does not queue or acquire new resources | Submits a separate batch allocation |
| Recognized cluster login/submit node without an allocation | Prohibited for compute work | Allowed; submission itself may run here |
| Non-cluster local machine | Runs on local resources when the pending DAG fits | Unsupported in v1; does not provide detached local execution |

Do not use `SLURM_JOB_ID` to decide whether async submission is available: login
nodes legitimately have no allocation. First inspect Lightcone's configured site,
then use the same read-only reachability probe as the CLI when the site is unknown:

```bash
command -v sinfo
sinfo --noheader --format='%P'
```

Classify the result explicitly:

- configured Perlmutter site: async is supported from login or compute nodes;
- `sinfo` succeeds but the site is unrecognized: SLURM is reachable, but async v1
  remains unsupported because QoS, node shapes, and shared paths are unknown;
- `sinfo` is absent, times out, or cannot contact a controller: treat the host as
  local for execution planning.

Use `SLURM_JOB_ID` only after this distinction to determine whether plain `lc run`
will reuse a current compute allocation.

On a non-cluster local machine, classification remains a production-fit and
safety check, not a choice between local sync and async. Determine whether the
pending DAG fits the host and whether remaining coupled to the current process is
acceptable. If either condition fails, direct the user to a supported cluster or
larger environment; never present local `--async` as a fallback.

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
3. The conservative runtime for the unresolved required sub-DAG fits the
   allocation's remaining walltime or the acceptable local run window, including
   pending upstream work, startup, and shutdown margin.
4. The work may remain coupled to the current agent/allocation lifetime.

Use the recorded padded `time_limit` values and DAG structure. Do not compare
only the leaf rule or the original unpadded pilot runtime. Never assume multi-node
or multi-GPU speedup that the estimate did not measure.

## 4. Classify

Return one of these decisions:

- **Synchronous:** all rules and conservative total runtime fit the current
  allocation or local host, with adequate margin and acceptable lifetime coupling.
- **Asynchronous:** Lightcone detects a supported configured async site and the
  agent is on its login node, the job does not fit the current allocation,
  remaining walltime is insufficient, or the work must survive the current
  session/allocation.
- **Move to a supported environment:** the current host is local or otherwise
  lacks a supported async policy, and the job does not fit safely or must detach.
- **Estimate first:** declared resources are missing, stale, or too uncertain.

On a local machine, recommend a larger local machine or moving to a supported
cluster instead of claiming async submission will work. If several Perlmutter
shapes are valid, prefer the smallest shape that fits `shared`; use a larger
`regular` shape only when measured speedup or memory need justifies it.

Treat `lc` preflight failures as authoritative. If plain `lc run` reports that
declared resources or walltime cannot fit, preserve its diagnostic and use the
copyable `lc run --async ...` retry it provides only when the current site
supports async submission.

When an expensive boundary has cheap dependents, classify the boundary now and
mark those dependents **deferred**. After the async job materializes the boundary,
refresh `lc status`, repeat classification with current environment facts, and
normally run the cheap dependents synchronously. Do not submit the boundary and
its downstream consumer concurrently: Lightcone serializes project runs with a
project lock, and the consumer's provenance must be built from the completed
boundary manifest.

## 5. Execute only when requested

If the user asked only for classification, report the decision and exact next
command without running or submitting it. If execution was requested, always use
`lc`:

```bash
# Reuse the current allocation or local host
lc run <output> --universe <universe>

# Submit a detached SLURM allocation from a supported configured site
lc run --async <output> --universe <universe>

# Observe materialization and queued/running state
lc status --universe <universe>

# After the boundary completes, materialize a cheap dependent
lc run <downstream-output> --universe <universe>
```

Pass `--account` when requested or when configuration does not supply one.
Submission may originate on a login or compute node of a supported site. Do not
run `lc run --async` on a local machine or describe it as background local
execution. Never forward a hand-built whole-analysis submission in place of an
explicit output target. Do not call `sbatch`, `srun`, Snakemake, or `podman-hpc`
yourself. The submitted batch job must enter the same plain `lc run` path so
container wrapping—including `podman-hpc`—validation, locking, and manifests
stay identical to synchronous execution.

## Result

Conclude with a compact table:

| Output boundary / universe | Pending sub-DAG demand | Current environment | Decision | Next command |
|---|---|---|---|---|

State remaining walltime, the limiting pending rule or resource, lifetime
requirements, and any assumption that could change the decision. List cheap
downstream outputs separately as deferred and give their post-completion command.
