---
name: async
description: >
  Prepare and select asynchronous execution for Lightcone jobs. Estimate CPU,
  memory, GPU, and walltime requirements and record them in ASTRA
  recipe.resources when requested or when declarations are missing, stale, or
  uncertain; immediately before every production lc run or submission, inspect
  the unresolved DAG and classify explicit expensive output boundaries for
  synchronous execution in the current local or SLURM allocation versus lc run
  --async. Use when asked to estimate or size a Lightcone job, prepare async
  execution, run, queue, submit, detach, resume, survive a session, or choose
  sync versus async execution.
---

# Prepare Lightcone Async Jobs

Keep reusable estimates separate from the environment-dependent sync/async
decision. Load only the workflow required for the current request.

## Prerequisites

1. Confirm the CLIs resolve:

   ```bash
   command -v lc
   command -v astra
   ```

   If either is missing, tell the user to run `uv tool install lightcone-cli`
   and stop.

2. Work from the project containing `astra.yaml` and discover the installed
   command surface rather than guessing:

   ```bash
   lc run --help
   lc status --help
   lc --help
   ```

## Route the request

- **Estimate or revise resources only:** read
  [references/estimate.md](references/estimate.md) completely. Do not classify,
  run, or submit production work.
- **Classify, run, queue, submit, or resume:** read
  [references/classify.md](references/classify.md) completely immediately before
  deciding. Repeat its environment checks even when resources were estimated
  earlier.
- **Classification returns “estimate first”:** read
  [references/estimate.md](references/estimate.md) completely, update and
  validate ASTRA, then repeat the classification workflow with fresh environment
  facts.
- **Estimate and execute in one request:** finish estimation first, then perform
  a fresh classification. Do not let the measurement environment decide the
  later execution mode.

Always execute production workflows through `lc`; use only the isolated pilots
allowed by the estimation reference. Never invoke `sbatch`, `srun`, Snakemake,
Dask, or a container runtime directly.
