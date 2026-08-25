---
name: lightcone
description: >
  Companion for a Lightcone project — an ASTRA analysis (astra.yaml)
  executed with the `lc` CLI. Use this skill whenever the user wants to
  scope, resume, plan, run, debug, publish or discuss such a project: "new
  analysis", "scope a project", "resume the project", "where were we", "run
  the pipeline", "lc status/materialize/run", "publish the analysis". Also
  use it whenever the working directory holds an astra.yaml and the user
  asks to run, re-run, fix or interpret an analysis, even if they never say
  "Lightcone", "ASTRA" or "lc". Do NOT use it for the astra.yaml format
  itself — schema, decisions, universes, evidence and quotes are the astra
  skill's.
---

# Lightcone projects

An analysis declared in `astra.yaml`, executed by `lc`, and documented in index.md: recipes turn
declared inputs and decisions into outputs under `results/`, each committed
with the code that produced it, the MyST report of the analysis is in index.md.

| What you are doing | Where to go |
|---|---|
| A research question, no spec yet | `references/scoping.md` — interview first, write no code |
| Picking up an existing project | `lc status`, then summarize before asking what is next |
| Writing or debugging a script | `lc run <argv>` — the sandbox a recipe gets |
| Producing an output for real | [Make an output](#make-an-output) |
| A refusal, a failing recipe, a surprising status | `references/diagnosis.md` |
| Papers, quotes, prior insights | `references/literature.md`, and `references/extraction-brief.md` per paper |
| Writing or updating the report | `references/reporting.md` — MyST + `{astra}` references |
| Sharing, archiving, citing | `references/publishing.md` |
| Anything about `astra.yaml` itself | the `astra` skill — this one repeats none of it |

## Before you drive `lc`

The user installs the CLI once, on their machine, and that is the whole
setup — it puts `lc` on their PATH:

```bash
uv tool install lightcone-cli==0.5.0rc1
```

Name that version. While the line is a pre-release, a bare
`uv tool install lightcone-cli` resolves to an older stable release.

Before doing anything else, evaluate whether the `lc` CLI is present through this
checklist:
- **Seen `Lightcone CLI ready: lc <version>` this session?** That is this
  check, already run by the session-start hook. Don't repeat it. You are all good.
- **Seen the hook report a problem?** It names the remedy and who runs it.
- **Seen neither?** Run `lc --version` yourself — this skill assumes
  `lightcone-cli==0.5.0rc1` or newer. Silence is not an all-clear: the skill
  also ships without that hook, and a subagent never sees session start.
  Remedies are in `references/diagnosis.md`.

Where a person can answer, offer and wait — **never install or upgrade
unasked**, it is their machine. Where none can (headless, CI), act and say
what you changed.

## Make an output

1. **Probe.** `lc run python src/fit.py --outliers clip` — argv, like
   `uv run`; `lc run bash -c '...'` for shell syntax. What works here works
   as a recipe. A missing import is environment work: `uv add <pkg>`, which
   is the only way to change the environment.
2. **Wire.** Give the output a `recipe:` in `astra.yaml`. `{output}` is its
   own results directory, `{inputs.<id>}` a declared input (an upstream
   output's directory, when outputs chain), `{decisions.<id>}` the active
   option. Everything a command references must appear in that output's
   `inputs:` / `decisions:` — that is also how dependencies are declared.
3. **Commit your edits**, by path: `git add src/ astra.yaml && git commit`.
4. **`lc materialize [targets]`.** Remakes what is `stale`, dependencies
   first, and commits each output as it lands. Bare takes every output in
   every universe; `fit` takes that output across universes; `robust/fit`
   takes one universe's. Re-running is idempotent. You are done when
   `lc materialize --check` passes — that, not `lc status`, is the gate.

Outputs land at `results/<universe>/<output_id>/` — a sub-analysis uses its
qualified id, `results/<universe>/<sub>.<output_id>/`. Each directory carries
a `.lightcone-manifest.json` beside the bytes — the run record: the rendered
`recipe`, the `decisions` it ran under, `git_sha`, `lc_version`/`uv_version`,
the `hermeticity` the sandbox enforced, timestamps, and the hashes
(`definition_version`, `env_version`, `data_version`, `input_versions`) that
`lc status` compares against the spec to reach its verdict. Read it to answer
how an output came to be; never write one. Name one output at a time while
integrating, so each intermediate can be inspected rather than debugged from
the bottom of a long trace.

Write scripts recipe-ready: one script per output, every decision a CLI flag
(never a hardcoded option value), everything written under `{output}`.

## Read `lc status`

| State | Means | What to do |
|---|---|---|
| `current` | Matches the spec, made under this environment | Nothing |
| `behind` | Still matches the spec; the environment moved | Nothing, unless the user wants it remade: `--refresh` |
| `stale` | Contradicts the spec, or its bytes were last touched by something other than its own run record | The next `lc materialize` remakes it |

Everything going `behind` after a `uv add` is normal, not damage. An `lc`
upgrade invalidates nothing.

## Ask for `--json`

Every verb that reports takes `--json`, and that is the form to drive from:
one object on stdout, with the reasons already spelled out per output —
nothing to scrape out of a table. Read JSON; show the user the plain output
when they want to look at something themselves.

```bash
lc status --json               # {mode, image, sandbox, crate, counts{current,behind,stale},
                               #  outputs[{output, status, why, git_sha, data_version, foreign_write}],
                               #  warnings}
lc materialize --check --json  # {ok, up_to_date, planned{target: why}, made, current, behind,
                               #  failed, blocked, warnings, notes}
lc init --json                 # {converged, created, repaired, unchanged, blocked, warnings}
lc build --json                # the build's result
```

`why` and `planned` carry the engine's own reason a thing is stale or is
about to run — quote it rather than inferring one. `lc status` always exits
0, so its JSON is the whole answer; `lc materialize --check` exits nonzero
when anything is out of date, which is the gate.

## Keep the spec and the code in step

Change one, change the other in the same breath: a decision added in code
goes into `astra.yaml` and every universe file, a renamed output updates its
`recipe:`, anything removed gets re-validated.

The recipe *string* and its decisions are an output's identity, so editing
`src/` makes nothing `stale` by itself. Declare a script as an ASTRA input
when its changes should cascade.

## Work with the user

Write to `astra.yaml` as each decision crystallizes rather than in bulk, and
keep the conversation to a summary with ids — candidate decisions and
findings belong in the file, where they can be reviewed. Confirm scope
before anything long (a full multiverse, a first container build). Keep
`CLAUDE.md`'s Project Notes current: it holds what the spec cannot and what
`/clear` would otherwise lose.

## Gotchas

- **A probe is not a result.** Nothing is done until `lc materialize`
  produced it, however well the script ran under `lc run`.
- **`lc` never walks up.** It acts on the current directory; `cd` to the
  project root.
- **A fresh clone needs `lc init`** before any git command touches it —
  cloning carries neither the environment nor the settings the project
  needs to store its files.
- **Large files are already handled.** `data/` and `results/` are taken
  care of by config the project carries, so plain `git add` / `git commit`
  is right anywhere in the tree — there is nothing else for you to run.
- **`lc materialize` commits the outputs it makes.** Don't commit results
  yourself, and never write into `results/` by hand: bytes arriving any
  other way carry no run record, and the next run notices and remakes them.
- **Never `git add -A`.** It sweeps a probe's stray `results/` files into a
  commit without a run record, which lands the output `stale`.
- **`pip install` reaches nothing.** The lock is the environment: `uv add`.
- **Don't re-interview on resume.** The spec and `CLAUDE.md` already answer
  the scoping questions; summarize state and ask what is *next*.
- **Five verbs, and `--help` is the authority.** `init`, `status`,
  `materialize`, `run`, `build`. Universes and outputs are selected by
  target (`robust/fit`), not by a flag: there is no `--universe`, no
  `--force`, no `--verbose`, no `lc verify` and no `lc export`.
- **Everything runs through `lc`.** Never invoke the container runtime, the
  sandbox or a scheduler yourself — `podman run`, `srun`, and friends
  bypass the environment, the isolation and the run record, and whatever
  they write into `results/` is a foreign write the next run will remake.
- **A denial is telling you the truth.** Declare the input, the package or
  the system tool it names; there is no `--force` and no sandbox opt-out.
