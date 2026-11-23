---
name: lightcone
description: >
  Companion for a Lightcone project — an ASTRA analysis (astra.yaml)
  executed with the `lc` CLI. Use this skill whenever the user wants to
  scope, resume, plan, run, debug, share, publish or discuss such a project:
  "new analysis", "scope a project", "resume the project", "where were we",
  "run the pipeline", "lc status/materialize/run/fetch/publish",
  "lc compute", "launch a cluster", "run on GPUs", "put it on GitHub",
  "clone the analysis", "upgrade the project". Also use it whenever the
  working directory holds an astra.yaml and the user asks to run, re-run,
  fix or interpret an analysis, even if they never say "Lightcone", "ASTRA"
  or "lc". Do NOT use it for the astra.yaml format itself — schema,
  decisions, universes, evidence and quotes are the astra skill's.
---

# Lightcone projects

An analysis declared in `astra.yaml` (ASTRA 0.1), executed by `lc`, and
written up in `index.md`: recipes turn declared inputs and decisions into
results under `results/` — one result is one file, at the place ASTRA gives
it — each committed with ASTRA's record of how it was made, under `.astra/`.

| What you are doing | Where to go |
|---|---|
| A research question, no spec yet | `references/scoping.md` — interview first, write no code |
| Picking up an existing project | `lc status`, then summarize before asking what is next |
| A project whose `astra.yaml` has `version:`, not `spec_version:` | `references/upgrading.md` — before anything else |
| Anything that executes — `lc run`, `lc materialize` | [Get a cluster](#get-a-cluster) first |
| Writing or debugging a script | `lc run <cluster> -- <argv>` — the sandbox a recipe gets |
| Producing a result for real | [Make a result](#make-a-result) |
| A bigger or remote shape, GPUs, recipe `resources:` | `references/compute.md` |
| A refusal, a failing recipe, a surprising status | `references/diagnosis.md` |
| Papers, quotes, prior insights | `references/literature.md`, and `references/extraction-brief.md` per paper |
| Writing or updating the report | `references/reporting.md` — MyST + `{astra}` references |
| Sharing, cloning, pulling, publishing | `references/publishing.md` |
| Anything about `astra.yaml` itself | the `astra` skill — this one repeats none of it |

## Before you drive `lc`

The user installs the CLI once, on their machine, and that is the whole
setup — it puts `lc` (and git-annex) on their PATH:

```bash
uv tool install lightcone-cli==0.6.0rc2
```

Name that version so the install selects the release this skill was
written against; an already-installed newer version is fine.

Before doing anything else, evaluate whether the `lc` CLI is present through this
checklist:
- **Seen `Lightcone CLI ready: lc <version>` this session?** That is this
  check, already run by the session-start hook. Don't repeat it. You are all good.
- **Seen the hook report a problem?** It names the remedy and who runs it.
- **Seen neither?** Run `lc --version` yourself — this skill assumes
  `lightcone-cli==0.6.0rc2` or newer. Silence is not an all-clear: the skill
  also ships without that hook, and a subagent never sees session start.
  Remedies are in `references/diagnosis.md`.

Where a person can answer, offer and wait — **never install or upgrade
unasked**, it is their machine. Where none can (headless, CI), act and say
what you changed.

## Get a cluster

`lc run` and `lc materialize` execute on an allocation named as their first
argument. Neither starts one, waits for one, or falls back to running
locally. `lc status`, `lc materialize --check`, `lc fetch`, `lc publish`,
`lc init`, `lc build` and `lc compute` need none.

`lc compute` is an abstracted view of the user's compute, whatever
machines and schedulers lie behind it, and it is the only view to use:
`lc compute resources` lists every shape you can get.

1. **Reuse.** `lc compute status --json` lists this user's live
   allocations; `pending` is still queued. For an `active` one,
   `lc compute status <name> --wait` returns once its workers are
   connected.
2. **Launch.** On a workstation, `lc compute launch --wait` takes the
   built-in local offer — every usable CPU and all RAM, one node, plus
   the GPUs exposed by `CUDA_VISIBLE_DEVICES` on Linux — names it `local`,
   and prints that name once it is ready. Only one local cluster runs per
   user per machine; a second launch is refused and names the live one:
   reuse it. The built-in offer has no hard walltime and stops after 30
   minutes idle; active tasks keep it alive. Add `--time 1h30m` only when
   a hard limit is wanted: it kills the allocation at that age, even
   mid-write if a recipe is still running.
3. **Pass the name.** `lc run local -- python src/fit.py …`,
   `lc materialize local fit`. Shell variables do not survive between your
   tool calls, so carry the name itself, not `$CLUSTER`.
4. **Release it** with `lc compute down <name>` once the work is done and
   the user has not asked to keep it.

The local shortcut is routine: launch it when there is something to run,
and say that you did. Anything else `lc compute resources` lists — a
remote shape, several nodes, GPUs — can spend the user's allocation hours
and queue time: show the `lc compute launch … --dry-run` plan and wait for
a yes. Never `down` an allocation you did not launch unless the user asks
— `lc compute status` lists theirs too, some possibly serving another
session.

## Make a result

1. **Probe.** `lc run local -- python src/fit.py --outliers clip` —
   everything after `--` is argv, like `uv run`;
   `lc run local -- bash -c '...'` for shell syntax. What works here works
   as a recipe. A missing import is environment work: `uv add <pkg>`, which
   is the only way to change the environment. Have the probe write where a
   probe may write (below) — the project root is read-only, so a script
   saving `chain.npz` beside itself dies at the last line, having done all
   the work.
2. **Wire.** Declare the output in `astra.yaml` with its `type`, its
   `format` (the result's file extension, no dot: `png`, `csv`, `json`,
   `parquet`, `fits`, `tar.gz`) and a `recipe.command` — ASTRA requires all
   three. In the command, `{output}` is the one file the recipe must write,
   `{inputs.<entry>}` what an entry of its `inputs` reads (an input's file,
   or an upstream result's file), `{inputs}` all of them in order, and
   `{decisions.<entry>}` the option selected. Everything a command
   references must appear in that output's `inputs:` / `decisions:`,
   exactly as listed there — that is also how dependencies are declared. A
   data file the recipe reads is an input: commit it under `data/`
   (`git add` it — ASTRA validates an input only once git tracks it) and
   declare its `path`. Data that is downloaded is an output built once
   whose recipe fetches it. A recipe needing more than one CPU, a set
   amount of RAM or a GPU declares it under `recipe.resources`
   (`references/compute.md`).
3. **Commit your edits**, by path: `git add src/ astra.yaml && git commit`.
   `lc init` leaves its own scaffold uncommitted, so a new project's first
   commit takes those files too.
4. **`lc materialize <cluster> [targets]`.** Makes what is `missing` or
   `stale`, dependencies first, in parallel where the graph and the cluster
   allow, and commits each result as it lands. No target takes every result
   of every universe; `fit` takes that output's results in every universe;
   `fit#robust` takes one result. Re-running is idempotent, and a rebuild
   that comes out byte-identical stops there instead of remaking what reads
   it. You are done when `lc materialize --check` passes.

A result lands at `results/<universe>/<output_id>.<format>` — or
`results/<output_id>.<format>` for an output built once (one that lists no
decisions and reads nothing per universe without a pin) — and ASTRA's
record of it at `.astra/records/<universe>/<output_id>.json`
(`.astra/records/<output_id>.json`). `lc` takes both places from ASTRA; no
recipe chooses them, so the whole of `results/` is a function of the spec,
and a consumer knows what every result *is* from `astra.yaml` alone. The
record stays in git, not the annex, so it reads on a clone that has fetched
no data: the result's `address` (`fit#robust`), its `content_hash` and
`size`, and under `generated_by` the `commit` the run started from, each
input's `entry`, hash and size, the `environment` (`urn:lightcone:env:…`),
the `runner` and its version, and when it ran. Read it to answer how a
result came to be — `uvx astra-tools@0.3.0rc4 history lineage <address>` walks
it back through git; never write one. Name one output at a time while
integrating, so each intermediate can be inspected rather than debugged
from the bottom of a long trace.

Write scripts recipe-ready: one script per output, every decision a CLI flag
(never a hardcoded option value), and the artifact written to the path
`{output}` hands them, opened exactly as given — `fig.savefig(args.output)`,
`Path(args.output).write_text(...)`, never a filename joined onto it. A
recipe that exits 0 having written a directory, some other name, or nothing
at that path is a failure, not a result.

## What a command may touch

`lc run` and a recipe run under the same boundary, which is why a working
probe means a working recipe. The project tree is **readable but read-only**;
the writable set is small and nothing else in it is writable:

| Writable | `lc run` (probe) | A recipe |
|---|---|---|
| `results/` | the whole directory | only the directory its own result lands in |
| `$TMPDIR`, `$HOME` | a private per-run directory, gone afterwards | same |
| `/tmp`, `/var/tmp`, `/dev/shm` | yes | yes |

So a probe's scratch belongs in `tempfile` / `$TMPDIR` (`TMPDIR` already
points inside the private HOME, so `tempfile.mkdtemp()` needs nothing
declared), or in `results/` when you want to keep looking at it — remembering
that anything a probe leaves in `results/` carries no record and must go
before you commit.

**Readable:** the project tree — declared inputs are files in it — the
project environment, and the OS. Nothing outside the project is: a denied
read names a file to commit under `data/` and declare, not an obstacle to
work around. The network is not controlled.

The tree being read-only includes `.venv`: `uv add` changes the environment
because it runs *outside* the boundary, and nothing inside one ever can.

## Read `lc status`

| State | Means | What to do |
|---|---|---|
| `ok` | Matches the spec, made under this environment | Nothing |
| `behind` | Still matches the spec; the environment moved | Nothing, unless the user wants it remade: `--refresh` |
| `stale` | Something it is made from changed since its record's commit — its command, a decision or the option selected, the content of what it reads — or the file at its place is not the one its recipe made | The next `lc materialize` remakes it |
| `missing` | Never made, no valid record, or its bytes are in neither this clone nor any of its remotes | The next `lc materialize` makes it |

An `ok` or `behind` result whose bytes this clone lacks is also marked
**`unfetched`**, with the remotes that hold them: that is a transfer, not
compute — `lc fetch` brings it (`references/publishing.md`). Everything
going `behind` after a `uv add` is normal, not damage. An `lc` upgrade
invalidates nothing.

## Ask for `--json`

Every verb that reports takes `--json`, and that is the form to drive from:
one object on stdout, with the reasons already spelled out per result —
nothing to scrape out of a table. Read JSON; show the user the plain output
when they want to look at something themselves.

```bash
lc status --json               # {image, environment, online, counts{ok,behind,stale,missing},
                               #  results[{result, state, why, unfetched, remotes,
                               #           astra{state, bytes, why[], stale_inputs}}],
                               #  warnings}
lc materialize --check --json  # {ok, up_to_date, made, unchanged, behind{}, failed,
                               #  blocked, planned{result: why}, warnings, notes}
lc fetch --json                # {ok, fetched, present, left{result: state}, failed{id: why},
                               #  inputs, warnings}
lc publish --check --json      # {ok, published, target, visibility, store, confirmed,
                               #  unsent, unpushed, uncommitted, warnings, …}
lc init --json                 # {converged, created, repaired, unchanged, blocked, warnings}
lc build --json                # the build's result
lc compute status --json       # {clusters[{id, name, phase, allocation,
                               #  dask{observation, ready, workers}, reason}], errors}
lc compute launch --wait --json  # {plan, id, name, accepted, ready}
```

`why` and `planned` carry ASTRA's own reason a result is in its state or is
about to run — quote it rather than inferring one; the plain `lc status`
shows the state and the commit, never the reason. `lc status` always exits
0 on an analysis that validates, so its JSON is the whole answer (one that
does not validate is refused with ASTRA's report). `lc materialize --check`
exits nonzero when anything is out of date, which is the gate. In the
materialize report, `ok` means nothing attempted failed or was blocked, and
`up_to_date` that nothing needed doing; `behind` counts against neither.
`lc compute status` exits nonzero when part of its query failed (`errors`),
even though the allocations it did find are listed. A compute failure under
`--json` still prints one object, `{error, id, submission_token}`: keep
that `id`.

## Keep the spec and the code in step

Change one, change the other in the same breath: a decision added in code
goes into `astra.yaml` and into every universe that uses it, a renamed
output updates its `recipe:`, anything removed gets re-validated.

A result is made from its command, its inputs' content, its decisions and
the results it reads — not from the code the command runs. Editing `src/`
makes nothing `stale`: after changing a script, remake what it produces
with `lc materialize <cluster> <target> --refresh` (its readers follow only
if its bytes change). Where a script's changes should always cascade,
declare the script itself as an input of the outputs that run it.

## Work with the user

Write to `astra.yaml` as each decision crystallizes rather than in bulk, and
keep the conversation to a summary with ids — candidate decisions and
findings belong in the file, where they can be reviewed. Confirm scope
before anything long (a full multiverse, a first container build). Who may
read a project and where its data lives are the user's choices, never
yours (`references/publishing.md`). Keep `AGENTS.md`'s Project Notes
current: it holds what the spec cannot, and it is what a later session
reads to pick the work up.

## Gotchas

- **A probe is not a result.** Nothing is done until `lc materialize`
  produced it, however well the script ran under `lc run`.
- **`lc` never walks up.** It acts on the current directory; `cd` to the
  project root.
- **A fresh clone needs `lc init`** before any git command touches it —
  cloning carries neither the environment nor the git-annex setup the
  project needs to store its files. Then `lc fetch` brings the bytes you
  want to read.
- **Large files are already handled.** `data/` and `results/` are taken
  care of by config the project carries, so plain `git add` / `git commit`
  is right anywhere in the tree. Never run a git-annex command yourself:
  `lc fetch` reads bytes, `lc publish` sends them.
- **`git push` is not publishing.** It sends commits without their bytes,
  and every clone then sees those results as `missing`: share with
  `lc publish`; take others' work in with `git pull`.
- **`lc materialize` commits the results it makes.** Don't commit results
  or records yourself, and never write into `results/` or `.astra/` by hand:
  bytes that are not the ones a record names are made again.
- **Never `git add -A`.** It sweeps a probe's stray `results/` files into a
  commit without a record, which lands the result `stale`.
- **One output is one file.** A recipe cannot emit a bundle: split it into
  separate outputs, or declare a container format (`format: tar.gz`,
  `format: hdf5`) and write the one archive.
- **`pip install` reaches nothing.** The lock is the environment: `uv add`.
- **Don't re-interview on resume.** The spec and `AGENTS.md` already answer
  the scoping questions; summarize state and ask what is *next*.
- **Eight verbs, and `--help` is the authority.** `init`, `status`,
  `materialize`, `run`, `fetch`, `publish`, `build`, and `compute`
  (`resources`, `launch`, `status`, `down`). Results are selected by target
  (`fit`, `fit#robust`), not by a flag: there is no `--universe`, no
  `--force`, no `--verbose`, no `--jobs` (concurrency is the cluster's), no
  `lc verify`, `lc export` or `lc view`, and no `lc clone`, `lc pull` or
  `lc push` (`git clone` + `lc init`, `git pull`, `lc publish`).
- **Everything runs through `lc`.** Never invoke the container runtime, the
  sandbox or a job scheduler yourself — `podman run` and friends bypass
  the environment, the isolation and the record, and whatever they write
  into `results/` is bytes no record names, which the next run remakes.
- **An allocation keeps the environment it was launched with.** A variable
  exported afterwards never reaches its workers, nor does `NAME=value lc
  run …` — write `lc run local -- env NAME=value python …` for a probe.
  After changing such a variable, or upgrading `lc`, `down` the cluster and
  launch a new one.
- **An interrupted run is still running.** Killing `lc run` or
  `lc materialize` detaches the client only; the command goes on on the
  worker. `lc compute down <full-id>` — the `id` from `--json`, since a
  name can already belong to a newer allocation — before touching
  `results/`.
- **stdin never reaches a command.** Pipe nothing into `lc run`; a file the
  command reads is a declared input.
- **A denial is telling you the truth.** Declare the input, the package or
  the system tool it names; there is no `--force` and no sandbox opt-out.
