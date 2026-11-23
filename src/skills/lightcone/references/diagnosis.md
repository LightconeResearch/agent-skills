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
| A version below the floor | Its commands or behavior may differ from the release this skill expects | `uv tool install lightcone-cli==x.y.z` |
| A version above the floor | Nothing. Newer is fine | — |
| `lc` runs but reports no version | A broken install, or some other `lc` shadowing it — check `type lc` | `uv tool install --force lightcone-cli==x.y.z` |
| `lc` not found right after installing | uv put it in `~/.local/bin`, which is not on PATH | `uv tool update-shell`, or check for a shell alias with `type lc` |
| `git-annex is required … and is not on PATH` | git-annex installs with `lc`; this install lost it | `uv tool install --force lightcone-cli==x.y.z` |

Who runs it: offer and wait where a person can answer, act and report where
none can. Never install or upgrade unasked — it is the user's machine, and
they may be running other projects against the version they have. If
permissions refuse the command in a headless run, report that the CLI is
missing and name what to allow rather than working around it.

When upgrading, stop running clusters with the old CLI first: old cluster
IDs and compute catalogs may no longer be accepted, and an allocation keeps
the engine it was launched with. A project made with an `lc` older than
0.6 is written in ASTRA 0.0.x, which this `lc` does not read at all:
`references/upgrading.md`.

## Refusals before a run starts

- **`… does not validate, so there is nothing to materialize from it`** —
  every verb that reads the analysis refuses one that breaks an ASTRA rule,
  `lc status` included, and lists ASTRA's diagnostics, each at its line. Fix
  the spec (the astra skill), never `lc`. The commonest after an edit:
  `INPUT_NOT_TRACKED` — a newly declared input's file is not in git yet;
  `git add` it.
- **`uncommitted changes in …`** — every result is committed with the code
  that produced it, so a run starts only from a clean tree. Commit your
  edits; the refusal itself separates files to commit from what `lc` wrote
  into `results/` and `.astra/`, which is never yours to commit — discard
  those (it prints the `git clean`), after the checks in
  [Compute and clusters](#compute-and-clusters) if a run was interrupted.
- **`… is not a Lightcone project`** — `lc` uses the invocation directory
  and never walks up; `cd` to the project root. **`… has not been built yet
  — missing …`**: a fresh clone; run `lc init` once to rebuild what the
  clone did not carry.
- **git identity missing** — `lc materialize` needs a committer before it
  will start. The user sets `git config --global user.name` / `user.email`;
  this is theirs to do, never yours.
- **`another git command holds the project's index`** — wait for it; if no
  git is running, a killed one left `.git/index.lock`, and removing it is
  the remedy. Ask before deleting it.
- **`no result matches \`x\``** — targets are a result's id (`fit#robust`)
  or an output's id (`fit`); the refusal lists the valid ones. There is no
  `robust/fit` form.
- **`the analysis in … is outside the project's folder`** — a declared
  analysis read from the working tree must sit inside the project. Move it
  in, or declare it with a `commit` to read its results instead.
- **`… is a repository of its own`** — `lc` commits only into the project's
  repository; declare it with a `commit`, or run `lc` in it.
- **`… on that commit's files … (NOT_AT_COMMIT)`** — `lc` builds nothing
  from an analysis declared with a `commit`; it only reads the results
  recorded there. Declare it by `path` alone to build it.
- **`this project's results would not be stored as lc stores them`** — a
  `.gitattributes` line sends a result or record where it does not belong;
  `lc init` restores lightcone's lines, and a later line overriding them
  has to go. A declared analysis in a subfolder keeps its results in its own
  `results/`: the refusal names the line to append for it,
  `<folder>/results/** annex.largefiles=anything`.
- **`the lock has dependencies that cannot be audited`** — a path,
  directory or editable dependency in `uv.lock` records where code was, not
  what it was. Publish it, or vendor it into the project.

## A recipe fails

Read the sandbox note on stderr — the boundary appends one whenever a
sandboxed command exits non-zero, and it names the path or tool that was
blocked.

- **`ModuleNotFoundError` / `No module named ...`** → `uv add <pkg>`,
  commit, re-run. Never `pip install`: an install that bypasses the lock
  reaches nothing a recipe sees.
- **`cannot read <path>`, reading outside the project** → the read set is
  the project tree, the environment and the OS. A data file belongs in the
  project: commit it under `data/` and declare it as an input, listed in the
  `inputs` of the output that reads it. Data a recipe downloads is an output
  of its own, built once.
- **`Permission denied` writing a relative path** → the cwd is the
  analysis's folder and the tree is read-only, so `open("chain.npz", "w")`
  is denied wherever the script sits. The writable set is `results/` (a
  recipe: only the directory its own result lands in), `$TMPDIR`/`$HOME` —
  private, per-run and discarded — and `/tmp`, `/var/tmp`, `/dev/shm`. Send
  a probe's scratch to `tempfile.mkdtemp()`; send a recipe's artifact to
  `{output}`.
- **`the recipe exited 0 but left … at …`** → the script wrote a different
  name, or `mkdir`'d the path, or left a large-file pointer. `{output}` is
  the file itself: open it as handed, don't join a filename onto it.
- **`` `x`, which `y` reads, … `` (blocked)** → an upstream result failed,
  or could not be read; fix that one first — `blocked` lists what waited on
  it.
- **A blocked system tool** → the environment has no such tool; see
  containerizing below.

Reproduce any of these cheaply with `lc run <cluster> -- <command>`, which
runs one command under exactly the policy a recipe gets. If it works there,
it works as a recipe.

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
first build takes minutes, and every existing result goes `behind`.

Once containerized: `image absent` → `lc build`; no runtime → ask the user
to install podman (or docker); architecture mismatch → build where the
architecture matches (e.g. a NERSC login node), commit, push.

## Unexpected status

Quote the `why` from `lc status --json` (or `lc materialize --check`) — it
is ASTRA's own reason, and it names what changed.

- **`stale`, with a reason naming the file at its place** — the bytes there
  are not the ones its record names: something other than its run wrote
  them. Look at what is there before remaking, in case work is about to be
  lost.
- **`stale` after a `git pull`, or everything `stale` at once** — something
  shared changed: an input's content, a decision's selection, a command.
  The reason says which; a cascade stops wherever a rebuild comes out
  byte-identical.
- **`missing` in a clone, though it was made elsewhere** — its bytes were
  never sent where this clone can reach them (a `git push` instead of
  `lc publish`). From the clone that has them, `lc publish` sends them;
  otherwise `lc materialize` makes it again.
- **Nothing `stale` after editing a script** — expected: code is recorded,
  not compared. `--refresh` the results it makes.

## Clones and bytes

`data/` and `results/` are backed by **git-annex**, already configured by the
project: a `git add` anywhere under either directory writes the file's bytes
into the annex and commits a small pointer in their place, which is how a
repository holds results and datasets without swelling. That configuration is
the whole interface — plain `git add` / `git commit` from anywhere in the tree
does the right thing. **Never run a git-annex command**: `lc fetch` brings
bytes into a clone and `lc publish` sends them out (`references/publishing.md`).

- **A `git add` that fails on a filter** — the project's file storage is
  not set up in this working tree. In a fresh clone, `lc init` is the
  answer; if it persists, the install is broken and the user repairs it
  with `uv tool install --force lightcone-cli==x.y.z`. Do not commit past
  such an error: the file would go into history in the wrong form.
- **`the content is not in this clone`**, or a result `unfetched` — the
  pointer is here but the bytes are not. `lc fetch <id>` brings a result or
  an input; `lc materialize` fetches by itself what its recipes read.
- **Content kept by Git LFS or DVC** — `lc` fetches only what git-annex
  keeps, and refuses before anything runs; the refusal names the command
  that fetches the rest (`git lfs pull`; for DVC, `dvc pull`).

## Compute and clusters

Most compute refusals name their own remedy; these need more than the
message says.

| You see | Do |
|---|---|
| `cluster name 'local' is already in use; choose another name` | Reuse `local`. Another name is refused too: one local cluster per user per machine |
| `a local cluster is already running or starting for this user on this machine; …` | Reuse the cluster it names. The `down` or `kill` it prints is for a cluster you launched, or on the user's word |
| `local compute is disabled …` | Nothing in `lc` overrides it: propose a shape from `lc compute resources` and launch it once the user agrees |
| `no configured offer matches this resource request; …` | Relay the per-offer reasons it lists; ask before loosening the request |
| `task needs … on one worker; no worker in this cluster can satisfy that request` | A recipe's `resources` exceed one node: a larger shape, or a smaller declaration if the code allows it |

After an interrupted run, or an allocation that ended under one, the
dirty-tree refusal lists stray `results/` and `.astra/` files. Discard them
only once `lc compute status <full-id>` shows `ended`: a recipe still
running would write them again, and a local container can outlive `down` —
check the container runtime too.
