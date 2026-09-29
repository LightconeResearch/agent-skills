# When `lc` refuses, or a recipe fails

Read this when a command refuses, a recipe exits non-zero, or `lc status`
reports something you did not expect. `lc` refusals are designed to be
pasted: each names the problem and carries its remedy — follow the remedy
rather than working around it.

- [The CLI itself](#the-cli-itself)
- [Refusals before a run starts](#refusals-before-a-run-starts)
- [A recipe fails](#a-recipe-fails)
- [Reaching for a system tool: containerizing](#reaching-for-a-system-tool-containerizing)
- [Unexpected status](#unexpected-status)
- [Clones and bytes](#clones-and-bytes)
- [Compute and clusters](#compute-and-clusters)

## The CLI itself

What `lc --version` told you, and what each answer needs. Every remedy is
the same command with a different flag, because `uv tool install` at an
exact version installs when nothing is there and replaces an older install
in place.

| Outcome | What it means | Remedy |
|---|---|---|
| Nothing on PATH | The CLI was never installed | `uv tool install lightcone-cli==x.y.z` |
| A version below the floor | The rebuild changed the verbs and the status vocabulary, so the skill's instructions will produce errors rather than results | `uv tool install lightcone-cli==x.y.z` — **not** `uv tool upgrade`, which will not move onto a pre-release |
| A version above the floor | Nothing. Newer is fine | — |
| `lc` runs but reports no version | A broken install, or some other `lc` shadowing it — check `type lc` | `uv tool install --force lightcone-cli==x.y.z` |
| `lc` not found right after installing | uv put it in `~/.local/bin`, which is not on PATH | `uv tool update-shell`, or check for a shell alias with `type lc` |

Who runs it: offer and wait where a person can answer, act and report where
none can. Never install or upgrade unasked — it is the user's machine, and
they may be running other projects against the version they have. If
permissions refuse the command in a headless run, report that the CLI is
missing and name what to allow rather than working around it.

## Refusals before a run starts

- **`uncommitted changes in ...`** — every materialization is committed
  with the code that produced it. Commit your edits; the refusal itself
  separates files to commit from stray `results/` files to discard.
- **`... is not a Lightcone project`** — `lc` uses the invocation
  directory and never walks up; `cd` to the project root. In a fresh clone,
  run `lc init` once to rebuild what the clone did not carry.
- **git identity missing** — `lc materialize` needs a committer before it
  will start. The user sets `git config --global user.name` / `user.email`;
  this is theirs to do, never yours.
- **`N output(s) declare no format:`** — every executable output is
  written to `results/<universe>/<id>.<format>`, so without one there is
  nowhere to put it. The refusal names all of them at once; add each
  artifact's extension (`format: png`) in a single edit.
- **`output id ... contains a dot`** — the manifest sidecar
  (`.<id>.manifest.json`) is recovered by partitioning the filename on its
  first dot, so a dotted id would let two outputs share a manifest. This is
  also what makes a **nested spec unbuildable today**: ASTRA qualifies a
  sub-analysis's output as `<sub>.<output>`. Keep the analysis flat.

## A recipe fails

Read the sandbox note on stderr — the boundary appends one whenever a
sandboxed command exits non-zero, and it names the path or tool that was
blocked.

- **`ModuleNotFoundError` / `No module named ...`** → `uv add <pkg>`,
  commit, re-run. Never `pip install`: an install that bypasses the lock
  reaches nothing a recipe sees.
- **Reading outside the project** → declare the path as an ASTRA input.
  The read set is the project tree, every declared `source:`, the
  environment and the OS; a denial names what is undeclared.
- **`Permission denied` writing a relative path** → the cwd is the project
  root and the tree is read-only, so `open("chain.npz", "w")` is denied
  wherever the script sits. The writable set is `results/` (a recipe: only
  its own `results/<universe>/`), `$TMPDIR`/`$HOME` — private, per-run and
  discarded — and `/tmp`, `/var/tmp`, `/dev/shm`. Send a probe's scratch to
  `tempfile.mkdtemp()`; send a recipe's artifact to `{output}`.
- **`the recipe exited 0 but left nothing / a directory at ...`** → the
  script wrote a different name, or `mkdir`'d the path. `{output}` is the
  file itself: open it as handed, don't join a filename onto it.
- **A blocked system tool** → the environment has no such tool; see
  containerizing below.

Reproduce any of these cheaply with `lc run <cluster> -- <command>`, which
runs one command under exactly the policy a recipe gets. If it works there, it works
as a recipe.

## Reaching for a system tool: containerizing

When a recipe needs more than Python packages (a system library, a compiler,
`latex`…), declare a system layer in `pyproject.toml` — never write a
Containerfile:

```toml
[tool.lightcone.image]
base = "docker.io/library/debian@sha256:..."  # optional; must be digest-pinned
apt-install = ["libfftw3-dev"]
run-commands = ["curl -L ... | tar xz"]
env = { OMP_NUM_THREADS = "1" }
```

Declaring the table switches the project to containerized mode: recipes run
inside a content-addressed image that `lc build` builds and commits into
the repository (`lc materialize` also builds it on demand; `lc run` never
does — it asks for `lc build` first). Requires podman or docker
(`podman-hpc` on NERSC).

**Confirm with the user before containerizing**: it requires a runtime, the
first build takes minutes, and every existing output goes `behind`.

Once containerized: `image absent` → `lc build`; no runtime → ask the user
to install podman (or docker); architecture mismatch → build where the
architecture matches (e.g. a NERSC login node), commit, push.

## Unexpected status

- **An output `stale` with a reason naming a commit** — a foreign write:
  those bytes were last touched by something other than their own run
  record. Inspect that commit before remaking, in case work is about to be
  lost.

## Clones and bytes

`data/` and `results/` are backed by **git-annex**, already configured by the
project: a `git add` anywhere under either directory writes the file's bytes
into the annex and commits a small pointer in their place, which is how a
repository holds results and datasets without swelling. That configuration is
the whole interface — plain `git add` / `git commit` from anywhere in the tree
does the right thing, and there is no annex command to run to make it happen.

- **A `git add` that fails on a filter** — the project's file storage is
  not set up in this working tree. In a fresh clone, `lc init` is the
  answer; if it persists, the install is broken and the user repairs it
  with `uv tool install --force lightcone-cli==x.y.z`. Do not commit past
  such an error: the file would go into history in the wrong form.
- **`the content is not in this clone`** — the pointer is here but the bytes
  were never fetched. `lc materialize` fetches what a recipe declares; use
  `git annex get <path>` only for bytes you want to inspect yourself.

## Compute and clusters

`lc run` and `lc materialize` refuse rather than wait or fall back; each
refusal names its remedy.

| You see | It means | Do |
|---|---|---|
| `Missing CLUSTER; create an allocation with lc compute launch.` | No cluster argument | Reuse one from `lc compute status`, or `lc compute launch --wait` |
| `… has not started yet; wait for readiness with lc compute status CLUSTER --wait` | Allocated, workers not all connected | `lc compute status <name> --wait`, then re-run |
| A name that no longer resolves | The allocation ended (walltime or `down`) | Launch a new one; names are reused, so never assume it is the same cluster |
| `a local cluster is already running or starting for this user on this machine; allocation …` | One local cluster per user per machine; the refusal names it and the catalog it was launched with | Reuse it — `LC_COMPUTE_CONFIG=<that catalog> lc compute status` if the current catalog does not list it. The printed `down` command is for a cluster you launched, or on the user's word |
| The same, ending `retry shortly` | Another launch is still starting that cluster | Wait, then reuse it |
| The same, with `owner process <pid> has no usable allocation record` | The cluster's record is lost or damaged | Tell the user; `kill <pid>` only with their agreement |
| `local compute is disabled on NERSC login nodes; …` | `lc` refuses local compute on a NERSC login node, whatever the catalog says | Nothing overrides it: a Slurm shape with `--cpus`/`--memory` after the user agrees, or an interactive compute node |
| `local compute is disabled by the compute configuration` | The catalog sets `local.enabled: false` | Request a remote shape with `--cpus`/`--memory`, after the user agrees |
| `no configured offer matches this resource request; … <offer>: <why>` | Nothing in `lc compute resources` fits | Relay the per-offer reasons; ask before loosening the request |
| `task needs … on one worker; no worker in this cluster can satisfy that request` | A recipe's `resources` exceed one node of this allocation | A larger shape, or a smaller declaration if the code allows it |
| `time_limit` / `disk` / fractional `cpus` refused | `lc` does not honor them | Remove them from `recipe.resources`; walltime is `launch --time` |
| A GPU recipe refused before the build | Plain Docker/Podman cannot pass GPUs | `podman-hpc`, or a direct (uncontainerized) project — ask first |
| `Could not acquire lock (os error 524)` from uv | uv's cache is on a filesystem without locks (`$HOME` at NERSC) | User exports `UV_CACHE_DIR=$PSCRATCH/uv-cache`; `down` and relaunch |
| Active on Slurm, never ready | Dask startup failed on the nodes | Read `Slurm Dask startup failed:` in `~/.lightcone/compute/submissions/<token>/` |
| `Interrupted; the remote command may still be running.` | The client detached; the worker did not stop | `lc compute down <full-id>`, confirm `ended`, then clean `results/` |

After an interrupted or killed run, the dirty-tree refusal lists stray
`results/` files. Discard them only once the allocation is confirmed
`ended`: a recipe still running would write them again, and a local
container can outlive `down` — check the container runtime too.

A multi-node allocation spreads recipes over its nodes by itself; no
recipe spans nodes, and there is nothing to configure per run.
