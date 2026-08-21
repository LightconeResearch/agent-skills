---
name: lightcone
description: >
  Companion for working with the user on a Lightcone project — an ASTRA
  analysis (astra.yaml) executed with the `lc` CLI. Covers the project model
  (a uv project: pyproject.toml + uv.lock + astra.yaml, direct or
  containerized, stored as a DataLad dataset), the development workflow
  (probe with `lc run`, integrate recipes, commit, `lc materialize`),
  status interpretation (current/behind/stale) and failure diagnosis,
  publishing the RO-Crate view — and how to engage the user at each phase:
  interview to scope a brand-new project, orient and summarize when resuming
  an existing one. Invoke whenever the user wants to start, resume, plan,
  run, debug, or discuss a Lightcone/ASTRA analysis project — "new
  analysis", "scope a project", "resume/continue the project", "where were
  we", "run the pipeline", "lc status/materialize/run", "publish the
  analysis".
---

# Lightcone Projects

A Lightcone project is a scientific analysis with two synchronized layers:

- **The spec** — `astra.yaml` plus its universe files: the ASTRA record of
  the analysis and its decision space. Everything about this layer — the
  format, authoring judgment, the `astra` CLI, evidence and quotes,
  validation — belongs to the `astra` skill; this skill assumes it and
  repeats none of it.
- **The execution** — a uv project (`pyproject.toml` + `uv.lock` +
  `.python-version`), analysis code, `recipe:` blocks wiring outputs to
  shell commands, and the `lc` CLI, which materializes outputs under a
  filesystem sandbox and commits each one with its provenance as it lands.

This skill owns the execution layer and the workflow around the whole
project: recognizing which phase the project is in, engaging the user
accordingly, and driving `lc`.

**Invoke the `astra` skill before any spec work** — reading or writing
`astra.yaml`, running an `astra` command, collecting evidence, validating.
Wherever this document says "validate the spec", "cache a paper", or
"generate a universe", the exact commands are the astra skill's.

## Prerequisites

Always invoke `lc` through uv's pinned runner, exactly as written in this
document:

```bash
uvx --from git+https://github.com/LightconeResearch/lightcone-cli@x.y.z lc <command>
```

Never run a bare `lc` found on PATH — its version is unknown and may not
match what this skill assumes. (`uvx` caches the environment, so repeated
calls are fast. If `uvx` is missing, ask the user to install uv:
https://docs.astral.sh/uv/getting-started/installation/ — never install it
yourself.) When unsure of a command's syntax, discover it with `--help`
rather than guessing. The `astra` CLI has its own pinned invocation — take
it from the astra skill, never from memory or PATH.

Two more things `lc materialize` requires up front:

- **A git committer identity.** If missing, have the user set
  `git config --global user.name` / `user.email`.
- **Annex plumbing pinned into the repo.** Plain `git add`/`git commit` in
  a Lightcone project invoke git-annex through the repo's filter config and
  hooks. git-annex does not need to be on PATH — pin the invocation into
  the repo itself (see **Pin the annex plumbing** below) immediately after
  every `lc init`. Until that's done, a missing git-annex makes `git add`
  exit 0 while printing `git-annex: command not found` and staging annexed
  files' raw bytes into git history — treat that error as a hard stop,
  never commit past it.

## The project model

- **The current directory is the project.** `lc` never walks up — run it
  from the project root. A project is `pyproject.toml` + `uv.lock` +
  `astra.yaml` (+ `universes/*.yaml`); there is no global config or state
  outside the directory.
- **uv is the only environment substrate.** Declare what scripts import
  with `uv add <pkg>` / `uv remove <pkg>`. Never `pip` or `uv pip install`
  — an install that bypasses the lock reaches nothing a recipe sees.
- **Mode is derived, never configured**: *direct* by default (recipes run
  in the project's `.venv` under a Landlock/Seatbelt sandbox);
  *containerized* the moment `pyproject.toml` declares a
  `[tool.lightcone.image]` table (recipes run in a content-addressed image
  committed into the repository). Deleting the table is the way back.
- **The project is a DataLad dataset**: git carries history, git-annex
  carries the bytes, behind ordinary `git add` / `git commit`. Never run a
  git-annex command yourself (exception: `git annex get <path>` to fetch
  bytes you want to inspect); never write into `results/` by hand; never
  commit outputs yourself — `lc materialize` commits each output with a
  run record that `datalad rerun` can replay.

### Pin the annex plumbing (run after every `lc init`)

git-annex serves the repo through git's filter config and four hooks,
which `git annex init` writes assuming `git-annex` is on PATH. When the
machine has git-annex, that stock plumbing is correct — leave it alone.
When it doesn't, pin the invocation into the repo itself instead of
installing anything. Either way, make a missing filter loud. Run this
after every `lc init` (idempotent, a no-op once applied):

```bash
git config filter.annex.required true
if ! command -v git-annex >/dev/null; then
  LC_ANNEX="uvx --from git+https://github.com/LightconeResearch/lightcone-cli@x.y.z git-annex"
  git config filter.annex.process "$LC_ANNEX filter-process"
  for h in .git/hooks/pre-commit .git/hooks/post-checkout .git/hooks/post-merge .git/hooks/post-receive; do
    [ -f "$h" ] || continue
    sed "s|git annex |$LC_ANNEX |g" "$h" > "$h.tmp" && mv "$h.tmp" "$h" && chmod +x "$h"
  done
fi
```

With this in place, plain `git add` / `git commit` work for you and for
the user's own terminal alike, with uv as the machine's only prerequisite;
`required=true` turns a missing filter into a hard
`fatal: clean filter 'annex' failed` instead of git silently staging
annexed bytes into history (the remedy is re-running this snippet, which
then pins). Run it after every `lc init` — a fresh clone included, since
`.git/config` and hooks are local state that doesn't travel with the
repository. And when this document says to run `git annex <cmd>` yourself
on a machine without git-annex, spell it with the same pinned prefix:
`uvx --from git+https://github.com/LightconeResearch/lightcone-cli@x.y.z git-annex <cmd>`.

## Orient before anything else

This skill can be invoked at any point in a project's life. First determine
where the project is, then match how you engage:

1. **Look for `astra.yaml`** in the working directory.
2. **No spec (or a freshly scaffolded placeholder)** → this is a new project.
   Switch to **Scoping** below: interview the user; don't start writing code.
3. **Spec exists** → read `astra.yaml` and `CLAUDE.md`, then check the
   directory is workable with `lc init --check --json` and read
   `lc status` (for a large spec, the astra skill's CLI reference has an
   `info` command that summarizes structure). Do **not** re-interview the
   user about things the spec already answers.

When resuming an existing project, open with a short state-of-the-project
summary before asking anything: the research question in one line, the
structure (sub-analyses, decision count, universes), what `lc status` shows
(which outputs are `current` / `behind` / `stale`, per universe), and
anything notable from `CLAUDE.md`. Then ask what to work on next, offering
the obvious candidates — e.g. materialize the `stale` outputs, `--refresh`
the `behind` ones, integrate a script that has no recipe yet, add a
universe, or discuss results. `AskUserQuestion` with the concrete options
works well here.

The phase determines the mode of interaction:

| Phase | Cues | How to engage |
|---|---|---|
| Scoping | no/placeholder spec | Interview; build the spec together; no implementation code |
| Implementation | spec exists, outputs `stale`, scripts absent or unwired | Pair on scripts, integrate recipes, materialize one output at a time |
| Interpretation | outputs `current` | Discuss results, record findings, explore alternative universes |
| Publishing | user wants to share/archive | Declare a license, converge the RO-Crate, archive |

These phases overlap in practice — a resumed project may need scoping-style
conversation for a new sub-analysis while the rest is being materialized.
Pick the mode per task, not once per session.

## Working with the user

- **Interview, don't lecture.** During scoping, ask one focused question at a
  time and let the answers drive the spec. During implementation, surface
  choices as they arise instead of silently deciding.
- **Write early, write often.** Update `astra.yaml` the moment a decision
  crystallizes, not in bulk at the end — the user should see the spec grow.
- **Review in the file, not in chat.** Write candidate decisions and findings
  to `astra.yaml` for the user to review; keep chat output to a concise
  summary with IDs. Don't dump full YAML in the conversation.
- **Confirm before expensive steps.** Materializing a full multiverse or
  containerizing the project can be long; check scope with the user first
  and build iteratively instead.
- **Keep `CLAUDE.md` current.** It carries the context that isn't in the spec
  and would be lost after `/clear` — update its Project Notes when
  conversation produces durable context. After a long scoping session,
  recommend `/clear`: everything needed to continue lives in `astra.yaml`
  and `CLAUDE.md`.

## Scoping a new project

Scaffold first if needed: `lc init [DIR]` converges the directory into a
standard project — `astra.yaml` placeholder, `universes/baseline.yaml`, a
dependency-free `pyproject.toml`, `uv.lock`, `.venv`, git + git-annex +
`.datalad/config`, `data/`, `results/`, and a MyST report skeleton
(`myst.yml`, `index.md`). It is idempotent and never overwrites files you
own — safe to re-run any time. It does **not** create `CLAUDE.md`; create
one yourself. Follow it with the annex-plumbing snippet (see **Pin the
annex plumbing** above). Then build the spec through conversation, updating
`astra.yaml` after each phase. Announce each phase with a short stage
banner so the user can follow.

**You are a specification agent in this mode, not an implementation agent** —
create or modify only `astra.yaml`, `universes/*`, and `CLAUDE.md`, and write
no Python/R/implementation code until scoping is done.

### 1. Research question

> "What are you trying to learn? Describe the question in your own words."

Sharpen it: what would a clear answer look like, and why does it matter?
"Analyze this data" is not a research question — push back until it is. Set
`name` in `astra.yaml`. (Leave the scaffolded `description` TODO for the
finalize step — written too early it goes stale.)

### 2. Analysis structure

> "Walk me through your analysis step by step. What goes in, what comes out?"

- **Default to a single analysis.** Split into sub-analyses only when each
  part is genuinely a self-contained product with materially different
  inputs and outputs (training + evaluation is usually *one* analysis — the
  product is the validated estimator). The full splitting judgment is the
  astra skill's; when a split does seem warranted, confirm the stage
  boundaries with the user before restructuring.
- **One output per output.** A single metric, a single plot, or a single
  artifact each — never a bundle like "performance_metrics".

Update `astra.yaml` with `inputs` and `outputs`.

### 3. Literature deep dive (optional per section)

Offer a literature pass; skip straight to decision identification if
declined.

- **Collect** — ask for papers the user already has in mind, search for a
  *limited* set of directly relevant ones (~2 per topic, max 10 per
  section), and present the list via `AskUserQuestion` with a one-line
  relevance note each for the user to approve.
- **Extract** — cache each approved paper with the astra skill's evidence
  workflow, then spawn **one subagent per paper** (all in parallel) to read
  the cached PDF and return candidate prior insights — verbatim quotes with
  their locating context — and the decisions they might inform. Give each
  subagent the analysis context, the paper's DOI and cached-PDF path, and
  the target decisions. Never read a PDF in the main context — it consumes
  too much of it. Write extracted insights to `astra.yaml` as they land and
  synthesize by topic for the user.
- **Identify decisions** — from conversation and literature: what could be
  done differently and still be defensible? Where did papers disagree? Where
  was the user uncertain? Probe the blind spots analysts neglect — data
  exclusion, variable operationalization, inference criteria — not just
  method choices. Write candidates to `astra.yaml` as a batch for review.
- **Review** — confirm or set each decision's `default`; drop rejected ones.

Every extracted quote must survive the astra skill's evidence verification
before scoping is done — never fabricate one.

### 4. Finalize

1. Checkpoint: "Anything else that should inform this analysis?"
2. Validate the spec per the astra skill — verifying evidence too, if any
   was extracted — and iterate until clean.
3. Generate only a `baseline` universe unless the user asks for more
   (universe commands: astra skill).
4. Replace the `description:` TODO with a short orientation paragraph now
   that structure is stable.
5. Fill `CLAUDE.md`'s Project Notes with conversation context that isn't in
   the spec.
6. Show a summary table (decisions / outputs / prior insights per section),
   confirm with the user, and recommend `/clear` before implementation.

## Development workflow

Three overlapping phases:

1. **Write & debug** — iterate with `lc run`, which runs one command in the
   project environment under the same sandbox a recipe gets:
   `lc run python src/fit.py --outliers clip`. Argv style, like `uv run` —
   never one quoted shell string (`lc run bash -c '...'` when shell syntax
   is needed). If it works under `lc run` it works as a recipe — the one
   difference is that a probe may write anywhere under `results/` while a
   recipe writes only its own output directory. Missing imports are
   environment work: `uv add <pkg>`, then re-probe. Write scripts
   recipe-ready from the start: parameterize every decision as a CLI flag
   (never hardcode option values), write to convention paths, one script
   per output.
2. **Integrate** — add `recipe:` blocks to outputs in `astra.yaml`. A recipe
   is a shell command template: `{output}` is the output's own results
   directory (created and emptied for it), `{inputs.<id>}` an input's path
   (an upstream output's directory, for output-to-output dependencies),
   `{decisions.<id>}` the active option id in the current universe.
   Everything a command references must be listed in that output's
   `inputs:` / `decisions:` lists — dependencies between outputs come from
   `inputs:` declarations.
3. **Materialize** — commit your edits (`git add -A && git commit`), then
   `lc materialize [TARGETS...]`. It refuses on a dirty tree, remakes
   whatever is `stale` (dependencies included), and commits each output as
   it lands. Bare `lc materialize` takes every output in every universe;
   `lc materialize fit` narrows to one output across universes;
   `lc materialize robust/fit` to one universe's output. Re-running is
   idempotent. Done when `lc materialize --check` passes (it exits 1 while
   anything still needs making — that, not `lc status`, is the gate).

**Always materialize through `lc`.** Treat the engine as a black box —
never invoke schedulers, container runtimes, or git-annex directly, and
never hand-place files in `results/`; that bypasses the provenance
guarantees (a hand-placed file has no run record, and the engine detects
the foreign write and remakes the output). A probe run is for debugging
only: **an output is not done until `lc materialize` produces it.**

**Build iteratively.** Name one upstream output at a time
(`lc materialize <output_id>`) so each intermediate can be inspected before
chaining downstream — not the whole DAG debugged from the bottom of a long
failure trace.

Outputs land at `results/<universe>/<output_id>/`, with the manifest at
`<output_dir>/.lightcone-manifest.json`. A sub-analysis output uses its
qualified id as the directory name: `results/<universe>/<sub>.<output_id>/`.

### Spec–Code Invariant

**`astra.yaml` must always reflect the code and vice versa.** When one
changes, update the other immediately:

- Add a decision to code? Add it to `astra.yaml` and all universe files.
- Add an output or change a script? Update its `recipe:` block.
- Remove or rename something? Update both sides and re-validate the spec.

One nuance to surface early: the recipe *string* and its decisions are the
output's identity — **editing a script in `src/` does not, by itself, make
its outputs `stale`.** When code changes should cascade, declare the script
as one of the output's ASTRA `inputs:` so its content is part of the
provenance.

### Creating sub-analyses

Each sub-analysis is just another `astra.yaml` nested in a directory:

1. Create `analyses/<name>/` with its own `astra.yaml` (and optionally
   `src/`, `universes/baseline.yaml`).
2. Add a `path:` entry under the parent's `analyses:`
   (`analyses: { my_sub: { path: ./analyses/my_sub } }`).
3. Add `<name>: { universe: baseline }` to each existing parent universe
   file.

Wire inputs and decisions to the parent or siblings with `from:` references
— the grammar is in the astra skill's spec reference.

### Containerizing (when recipes need system tools)

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
(`podman-hpc` on NERSC). Confirm with the user before containerizing: it
requires a runtime, the first build takes minutes, and every existing
output goes `behind`.

## CLI reference

```bash
uvx --from git+https://github.com/LightconeResearch/lightcone-cli@x.y.z lc init [DIR] [--check] [--json]   # Converge DIR into a standard project (idempotent)
uvx --from git+https://github.com/LightconeResearch/lightcone-cli@x.y.z lc status [--json]                 # Report each output's state; always exits 0
uvx --from git+https://github.com/LightconeResearch/lightcone-cli@x.y.z lc materialize [TARGETS...] [--check] [--refresh] [--json]  # Make outputs, committing each
uvx --from git+https://github.com/LightconeResearch/lightcone-cli@x.y.z lc run COMMAND...                  # Probe: run one command in the project env, sandboxed
uvx --from git+https://github.com/LightconeResearch/lightcone-cli@x.y.z lc build [--json]                  # Build & commit the system-layer image (containerized)
```

That is the whole surface — there is no `--universe` (universe selection is
the `<universe>/<output>` target form), no `--force` (nothing suppresses or
forces a rebuild; a `stale` output is always remade), no `--verbose`
(`--json` is the machine form; notes go to stderr), no `lc verify` and no
`lc export` (foreign writes are detected from git history, and the RO-Crate
is maintained in-repo by `lc materialize` — see Publishing). Machine
consumers use `--json`; the pass/fail gate is `lc materialize --check`.

## Status interpretation

`lc status` prints a header — mode (`direct`/`containerized`), image state,
sandbox mechanism, crate currency — then one row per `(universe, output)`
with its state, the short sha of the commit it was made at, and a reason.
Exactly three states:

- `current` — exactly what the spec asks for, made from these inputs, under
  this environment. Left alone, always.
- `behind` — still what the spec asks for, but made under an earlier
  environment (`uv.lock`, `.python-version`, an install setting, or the
  image moved). Reported and left alone; `lc materialize --refresh` remakes
  behind outputs too. Everything going `behind` after a `uv add` is normal,
  not a problem.
- `stale` — contradicts the project: never materialized, the recipe or its
  decisions changed, an input changed or is no longer declared, or the
  bytes were last touched by something other than their own run record (a
  foreign write — the reason names the offending commit). The next
  `lc materialize` remakes it, always.

An engine (`lc`) upgrade invalidates nothing — the engine version is
recorded in manifests but is not part of any output's identity.

## Failure diagnosis

`lc` refusals are designed to be pasted: each names the problem and carries
its remedy — follow the remedy rather than working around it. The common
ones:

- **`uncommitted changes in ...`** — every materialization is committed
  with the code that produced it. Commit your edits; the refusal itself
  separates files to commit from stray `results/` files to discard.
- **`... is not a Lightcone project`** — `lc` uses the invocation
  directory; `cd` to the project root. In a fresh clone, run `lc init` once
  to rebuild `.venv` and the annex.
- **Recipe fails with `Permission denied` / `No module named ...`** — read
  the sandbox note on stderr. `ModuleNotFoundError` → `uv add`, commit,
  re-run. Reading outside the project → declare the path as an ASTRA
  input. Writing outside `{output}` → write scratch files to
  `tempfile.mkdtemp()` instead. A blocked system tool → `apt-install` in
  `[tool.lightcone.image]`. Reproduce cheaply with `lc run <command>`.
- **Everything `stale` after a spec edit** — the invalidation model
  working; re-materialize. Everything `behind` after `uv add` — nothing
  invalidated; `--refresh` only when the user wants remakes.
- **`git-annex: command not found` during `git add` (exit 0!), or
  `fatal: clean filter 'annex' failed`** — the repo's annex plumbing isn't
  pinned (or drifted). Re-run the **Pin the annex plumbing** snippet; in
  the exit-0 form, `git reset` anything it staged before retrying.
- **`the content is not in this clone`** — annexed bytes not fetched.
  `lc materialize` fetches declared inputs itself; `git annex get <path>`
  only for bytes you want to inspect.
- **Login-node refusal (NERSC etc.)** — `lc materialize` runs on compute
  nodes; the refusal prints the center's own `salloc`/`sbatch` lines to
  copy. `lc status`, `lc materialize --check`, `lc run`, and `lc build`
  work anywhere. Inside a multi-node allocation the run spans nodes by
  itself — there is no `--jobs` and nothing to configure.
- **Containerized** — `image absent` → `lc build`; no runtime → ask the
  user to install podman (or docker); architecture mismatch → build where
  the architecture matches (e.g. a NERSC login node), commit, push.

## Publishing

The project itself is the publishable object — there is no export step.
Declaring a license turns on the publication view:

1. Add an SPDX `license` (e.g. `license = "CC-BY-4.0"`) under `[project]`
   in `pyproject.toml`, and set authorship in the spec per the astra skill.
2. Commit, then run `lc materialize` — nothing is remade; it converges
   `ro-crate-metadata.json` (a Workflow/Provenance Run RO-Crate rendered
   from repository state) and commits it. `lc status`'s `crate:` line says
   whether the view is current.
3. Gate: the astra skill's validation passes, `lc materialize --check`
   passes, and `ro-crate-metadata.json` exists.
4. Deposit is an archive of the repository: `git archive` (or
   `datalad export-archive`), pushed to wherever the user publishes. A
   durable copy of the data is `git push` plus `git annex copy --to
   <remote>` — offer to help set that up.

## Anti-patterns

- **Re-interviewing on resume** — the spec and `CLAUDE.md` already answer
  the scoping questions; summarize state and ask what's *next* instead.
- **Skipping orientation** — acting before reading `astra.yaml` and running
  `lc status` on an existing project.
- **Writing code during scoping** — the spec comes first; implementation
  starts after finalize.
- **Waiting to write** — update `astra.yaml` as each decision crystallizes,
  not in bulk at the end.
- **Chat dumps** — decisions and findings belong in the file for review, not
  pasted wholesale into the conversation.
- **Reading PDFs in the main context** — always delegate paper extraction
  to one subagent per paper.
- **Skipping verification** — if quotes were extracted, run the astra
  skill's evidence verification before calling scoping done.
- **Bypassing `lc`** — direct scheduler/container/git-annex invocations,
  hand-placed files in `results/`, or treating a probe run as a
  materialized result.
- **Fighting the sandbox or the invalidation model** — a denial's remedy
  (declare the input, the package, or the system tool) is the fix; there
  is no `--force` and no sandbox opt-out, by design.
- **`pip install` in any form** — the lock is the environment; use
  `uv add`.
- **Hardcoding decision values in scripts** — every decision is a CLI flag
  wired through `{decisions.<id>}`.
- **Running the whole DAG at once** — materialize one output at a time
  while integrating.
