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
- [HPC and venues](#hpc-and-venues)

## The CLI itself

What `lc --version` told you, and what each answer needs. Every remedy is
the same command with a different flag, because `uv tool install` at an
exact version installs when nothing is there and replaces an older install
in place.

| Outcome | What it means | Remedy |
|---|---|---|
| Nothing on PATH | The CLI was never installed | `uv tool install lightcone-cli==0.5.0rc1` |
| A version below the floor | The rebuild changed the verbs and the status vocabulary, so the skill's instructions will produce errors rather than results | `uv tool install lightcone-cli==0.5.0rc1` — **not** `uv tool upgrade`, which will not move onto a pre-release |
| A version above the floor | Nothing. Newer is fine | — |
| `lc` runs but reports no version | A broken install, or some other `lc` shadowing it — check `type lc` | `uv tool install --force lightcone-cli==0.5.0rc1` |
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

## A recipe fails

Read the sandbox note on stderr — the boundary appends one whenever a
sandboxed command exits non-zero, and it names the path or tool that was
blocked.

- **`ModuleNotFoundError` / `No module named ...`** → `uv add <pkg>`,
  commit, re-run. Never `pip install`: an install that bypasses the lock
  reaches nothing a recipe sees.
- **Reading outside the project** → declare the path as an ASTRA input.
- **Writing outside `{output}`** → a recipe writes only its own output
  directory. Send scratch files to `tempfile.mkdtemp()` instead.
- **A blocked system tool** → the environment has no such tool; see
  containerizing below.

Reproduce any of these cheaply with `lc run <command>`, which runs one
command under exactly the policy a recipe gets. If it works there, it works
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
  with `uv tool install --force lightcone-cli==0.5.0rc1`. Do not commit past
  such an error: the file would go into history in the wrong form.
- **`the content is not in this clone`** — the pointer is here but the bytes
  were never fetched. `lc materialize` fetches what a recipe declares; use
  `git annex get <path>` only for bytes you want to inspect yourself.

## HPC and venues

- **Login-node refusal (NERSC etc.)** — `lc materialize` runs on compute
  nodes; the refusal prints the center's own `salloc`/`sbatch` lines to
  copy. `lc status`, `lc materialize --check`, `lc run`, and `lc build`
  work anywhere.
- Inside a multi-node allocation the run spans nodes by itself — there is
  no `--jobs` and nothing to configure.
