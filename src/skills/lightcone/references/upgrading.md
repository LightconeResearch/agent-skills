# Upgrading a project made before ASTRA 0.1

Read this when a project's `astra.yaml` has `version: "0.0.x"` where 0.1
writes `spec_version:` — or it has a `universes/` folder,
`.<id>.manifest.json` files under `results/`, or a `ro-crate-metadata.json`.
Such a project was made with `lc` 0.5 or older. This `lc` reads only ASTRA
0.1 and carries no compatibility code: every verb refuses the old spec
(`… does not validate`, a wall of `MISSING_FIELD`, `UNKNOWN_FIELD` and
`WRONG_TYPE`), and results made by the old engine are invisible to it.
Nothing migrates by itself; upgrading is a one-time rewrite, done with the
user.

- [Before you start](#before-you-start)
- [1. Convert the spec](#1-convert-the-spec)
- [2. Clear what the old engine left](#2-clear-what-the-old-engine-left)
- [3. Converge, validate, commit](#3-converge-validate-commit)
- [4. Rebuild](#4-rebuild)
- [5. The report, the notes, sharing](#5-the-report-the-notes-sharing)
- [What changed, at a glance](#what-changed-at-a-glance)

## Before you start

Tell the user what the upgrade does and get a yes: it rewrites `astra.yaml`,
deletes `universes/` and every old result, and **every result is then made
again** — the whole multiverse's compute, once. The old results stay in git
history. Offer to work on a branch (`git switch -c astra-0.1`).

- The tree is clean, and `lc --version` is at least `x.y.z` (the floor in
  `SKILL.md`; installing it is the user's call).
- Clusters launched by the old `lc` are not reused: `lc compute status`,
  `down` the ones you launched (ask about the rest), and launch afresh when
  it is time to build.
- Note what exists — `ls results/*/`, the outputs and universes the old spec
  declares — so you can say afterwards that the same results came back.

## 1. Convert the spec

Rewrite `astra.yaml` in one pass with the astra skill's upgrade reference
(`upgrading-from-0.0.md`, under its `references/`), which maps every field (lists become
maps keyed by id, `version` → `spec_version`, `name` → `label`, decision
`default`s go, evidence ids go, `location: {page: N}` → `{value: page=N}`, …).
Keep every id. What only a Lightcone project brings to it:

- **Universes move into `astra.yaml`.** Each `universes/<id>.yaml` becomes
  an entry under `universes:`, its `id:` dropped. A baseline that was
  generated from decision defaults is kept as written: with `default:` gone,
  it is now the only record of those choices.
- **Inputs must be files in the project.** The old sandbox let a recipe
  read a declared `source:` anywhere; this one reads only the project tree.
  An input already under `data/` keeps its file: `source:` → `path:`. One
  outside the project either moves in — copy it under `data/` and `git add`
  it, which puts its bytes in the project's annex (mind the size) — or
  becomes an output built once whose recipe downloads it, under the same id.
  Ask the user which.
- **Every output needs a recipe.** An output the old `lc status` listed as
  `no recipe` needs its `recipe.command` now, or has to go.
- **Authors** are no part of ASTRA 0.1: move them to `myst.yml`
  (`project.authors`).
- **Declared analyses build now.** The old engine refused a nested spec;
  this one builds an analysis declared by `path` inside the project. The
  advice is unchanged all the same — keep the analysis flat unless a part is
  a genuine unit of its own.

Validate as you go: `uvx astra-tools@x.y.z validate`. An input that is not
yet tracked fails `INPUT_NOT_TRACKED` until you `git add` it.

## 2. Clear what the old engine left

```bash
git rm -r -q universes/            # now in astra.yaml
git rm -r -q results/              # old results and their .manifest.json files
git rm -q ro-crate-metadata.json   # if present: the RO-Crate view is gone
```

The old results cannot be adopted: ASTRA 0.1 judges a result by its record
under `.astra/records/`, which the old engine never wrote, so each is
`missing` either way, and the leftover manifests would linger in `results/`
for good. `git rm -r results/` removes `results/README.md` too; `lc init`
writes it back.

## 3. Converge, validate, commit

```bash
lc init                              # repairs .gitattributes, restores results/README.md
uvx astra-tools@x.y.z validate
git add astra.yaml .gitattributes results/README.md data/ && git commit -m "Upgrade to ASTRA 0.1"
```

`lc init` appends the line that keeps records in git
(`.astra/** annex.largefiles=nothing`). The old
`results/**/.*.manifest.json` line it leaves above it no longer matches
anything; removing it is tidy but optional. Add by path — never
`git add -A` — and check `git status` comes out clean.

## 4. Rebuild

`lc status` now lists every result `missing`; `lc materialize --check` shows
the plan, each with ASTRA's reason (`no record is at
.astra/records/<universe>/<id>.json`). Confirm the compute with the user, get
a cluster, and `lc materialize <cluster>` (SKILL.md, *Get a cluster*). Done
when `lc materialize --check` passes and the results you noted before are
back — targets are spelled `fit` and `fit#baseline` now, not
`baseline/fit`.

## 5. The report, the notes, sharing

- **The report** (`references/reporting.md`): pin MySTRA to a release that
  reads ASTRA 0.1 in `myst.yml`; evidence is addressed by index
  (`findings.sig.0`), not by id; the page's universe is the first one
  written in `astra.yaml`, not the first file in `universes/`; `{astra:ref}`
  is gone — a block's `:label:` and MyST's `{ref}` replace it. Build it and
  read the diagnostics.
- **`AGENTS.md`**: update its commands and anything naming the old states,
  targets, manifests or `universes/` files, and add a Project Notes line
  saying when and how the project was upgraded.
- **Sharing**: the RO-Crate view is gone; a project is shared with
  `lc publish` (`references/publishing.md`), whose two choices — who can
  read it and where its data lives — are the user's. A project the old
  engine already put on GitHub with `git push` has its commits there but
  not its bytes; the first `lc publish` sends them.

## What changed, at a glance

| Before (lc ≤ 0.5, ASTRA 0.0.x) | Now (lc ≥ 0.6, ASTRA 0.1) |
|---|---|
| `lc status`: `current` / `behind` / `stale` / `no recipe` | `ok` / `behind` / `stale` / `missing`, and `unfetched` on what a remote holds |
| target `robust/fit` | target `fit#robust` (`fit` for every universe) |
| `results/<u>/.<id>.manifest.json`, `lc`'s own run record | `.astra/records/<u>/<id>.json`, ASTRA's record, in git |
| an output built in every universe | an output with no decisions, reading nothing per universe, is built once: `results/<id>.<format>` |
| `universes/*.yaml`, decision `default:` | `universes:` in `astra.yaml`; no defaults |
| input `source:` anywhere the recipe could read | input `path:` to a file committed in the project |
| editing a declared script stales its outputs | still true; an undeclared script's edit stales nothing — `--refresh` its results |
| license + `lc materialize` → `ro-crate-metadata.json` | `lc publish` → GitHub plus a data store |
| `git annex get` for bytes | `lc fetch`; no git-annex command, ever |
