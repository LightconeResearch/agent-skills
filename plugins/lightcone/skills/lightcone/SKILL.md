---
name: lightcone
description: >
  Companion for working with the user on a Lightcone project — an ASTRA
  analysis (astra.yaml) executed with the `lc` CLI. Covers the project model
  (a uv project stored as a DataLad dataset, direct or containerized), the
  development workflow (probe with `lc run`, integrate recipes, commit,
  `lc materialize`), status interpretation (current/behind/stale), failure
  diagnosis, publishing, and how to engage the user at each phase: interview
  to scope a brand-new project, orient and summarize when resuming one. Use
  this skill whenever the user wants to start, resume, plan, run, debug, or
  discuss a Lightcone/ASTRA analysis project — "new analysis", "scope a
  project", "resume the project", "where were we", "run the pipeline", "lc
  status/materialize/run", "publish the analysis" — and whenever the working
  directory holds an astra.yaml and the user asks to run, re-run, fix, or
  interpret an analysis, even if they never say "Lightcone", "ASTRA" or
  "lc".
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

## Further reading

Each of these loads only when you read it, so reach for the one the moment
its trigger applies:

| Read | When |
|---|---|
| `references/scoping.md` | The project has no spec, or only `lc init`'s placeholder — you are about to interview the user |
| `references/literature.md` | Scoping reaches the literature pass, or the user wants decisions grounded in published work |
| `references/extraction-brief.md` | You are about to spawn the per-paper subagents — hand each one this file |
| `references/diagnosis.md` | A command refuses, a recipe exits non-zero, or `lc status` says something unexpected |
| `references/publishing.md` | The user wants to share, archive, deposit, or cite the analysis |

## Prerequisites

The engine is a tool the user installs once, on their machine:

```bash
uv tool install lightcone-cli==0.5.0rc1
```

That single install is the whole setup. It puts `lc` on PATH for you *and*
for the user's own terminal and batch scripts, and it carries `git-annex`
with it — which their plain `git add` needs in a Lightcone project, since
the repository routes large files through the annex filter.

**Name the version, exactly as written above.** It is the engine this skill
was written against, so the install does not depend on what the index
currently calls latest — and while the release line is a pre-release, a
bare `uv tool install lightcone-cli` quietly resolves to an *older* stable
release instead.

**Check before driving it, and check the version, not just the presence:**

```bash
lc --version            # this skill assumes lightcone-cli==0.5.0rc1 or newer
```

- **Not installed** — nothing in the project can be materialized,
  published, or diagnosed until the engine is there. Remedy:
  `uv tool install lightcone-cli==0.5.0rc1`.
- **Older than the version above** — the verbs and status vocabulary
  changed in the rebuild, so following this skill against an older engine
  produces errors rather than results. Remedy: the same command; it
  replaces an older install in place. (Not `uv tool upgrade`, which will
  not move onto a pre-release.) A *newer* engine is fine and needs nothing.
- **`lc` missing right after an install** — uv puts it in `~/.local/bin`;
  have the user run `uv tool update-shell` (or check for a shell alias
  shadowing `lc` with `type lc`).

**Who runs that remedy depends on whether anyone is there to ask.** The
session-start hook works this out and says which case you are in; when it
hasn't spoken, judge it yourself. With a person in the session, say what the
missing engine costs, offer to run the command, and wait — **never install
or upgrade unasked**, since it puts software on the user's machine, not just
in this project. In a headless run (`claude -p`, a scheduled job, CI) a
question is answered by no one, so run the remedy directly and say plainly
in your final message what you changed on the machine; if permissions refuse
it, report that the engine is missing and name what to allow rather than
working around it.

Some things stay the user's in **either** mode, because no one else can do
them: setting their git identity, and any step that needs a browser sign-in
or a credential. Those stop the work and get reported, never automated.

When unsure of a command's syntax, discover it with `--help` rather than
guessing. The `astra` CLI is invoked differently — through a pinned `uvx`
runner — so take its exact form from the astra skill, never from memory or
PATH.

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
- **A fresh clone is not yet a working project.** Some of what a project
  needs lives in `.git/` and the working tree, which cloning does not
  carry: the annex initialization, the filter settings and hooks that route
  large files, and the `.venv`. **Run `lc init` once in a new clone**,
  before anything else touches the repository. Until then a plain `git add`
  can stage annexed files' raw bytes into history instead of pointers, and
  recipes have no environment to run in. `lc init` is idempotent and
  repairs only what it manages, so re-running it in a clone you are unsure
  about costs nothing.

## Orient before anything else

This skill can be invoked at any point in a project's life. First determine
where the project is, then match how you engage:

1. **Look for `astra.yaml`** in the working directory.
2. **No spec (or a freshly scaffolded placeholder)** → this is a new project.
   Read `references/scoping.md` and interview the user; don't start writing
   code.
3. **Spec exists** → read `astra.yaml` and `CLAUDE.md`, then check the
   directory is workable with `lc init --check --json`. If it reports
   anything to create or repair — which a fresh clone always will, since
   the environment and the annex plumbing never travel with one — run
   `lc init` to converge it before doing anything else. Then read
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
  conversation produces durable context.

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
3. **Materialize** — commit your own edits, then `lc materialize
   [TARGETS...]`. Commit by path (`git add src/ astra.yaml && git commit`),
   never `git add -A`: a probe may have left files under `results/`, and
   sweeping those into a commit gives them bytes with no run record — the
   foreign write this skill warns about, which lands the output as `stale`.
   Discard them instead; the dirty-tree refusal separates the two lists for
   you. `lc materialize` refuses on a dirty tree, remakes whatever is
   `stale` (dependencies included), and commits each output as it lands.
   Bare `lc materialize` takes every output in every universe;
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

When a recipe needs a system tool the environment doesn't have, the project
can be containerized — see `references/diagnosis.md`.

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

## CLI reference

```bash
lc init [DIR] [--check] [--json]   # Converge DIR into a standard project (idempotent)
lc status [--json]                 # Report each output's state; always exits 0
lc materialize [TARGETS...] [--check] [--refresh] [--json]  # Make outputs, committing each
lc run COMMAND...                  # Probe: run one command in the project env, sandboxed
lc build [--json]                  # Build & commit the system-layer image (containerized)
```

That is the whole surface — there is no `--universe` (universe selection is
the `<universe>/<output>` target form), no `--force` (nothing suppresses or
forces a rebuild; a `stale` output is always remade), no `--verbose`
(`--json` is the machine form; notes go to stderr), no `lc verify` and no
`lc export` (foreign writes are detected from git history, and the RO-Crate
is maintained in-repo by `lc materialize`). Machine consumers use `--json`;
the pass/fail gate is `lc materialize --check`.

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

When something refuses or fails, read `references/diagnosis.md`; every `lc`
refusal carries its own remedy, and the two you will meet most are a dirty
tree (commit your edits, discard stray `results/` files) and being outside
the project root (`cd` there, and `lc init` in a fresh clone).

## Gotchas

Facts that defy a reasonable assumption — the ones worth knowing before you
trip over them:

- **A probe run is not a result.** An output is not done until
  `lc materialize` produces it, however well the script ran under `lc run`.
- **Editing code does not invalidate outputs.** The recipe string is the
  identity; declare a script as an ASTRA input when its changes should
  cascade.
- **`lc status` is a report, not a gate.** It always exits 0. The gate is
  `lc materialize --check`.
- **`behind` is not a problem.** An environment move is reported and left
  alone by design; only `--refresh` remakes those.
- **Never `git add -A` in a project.** It sweeps a probe's stray `results/`
  files into a commit with no run record, which lands the output `stale`.
- **A fresh clone needs `lc init`** before any git command touches it.
- **`pip install` reaches nothing.** The lock is the environment; use
  `uv add`.
- **Don't re-interview on resume.** The spec and `CLAUDE.md` already answer
  the scoping questions; summarize state and ask what's *next*.
- **Don't fight the sandbox or the invalidation model.** A denial's remedy
  (declare the input, the package, or the system tool) is the fix; there is
  no `--force` and no sandbox opt-out, by design.
