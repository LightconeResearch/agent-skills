---
name: assess-reproducibility
description: Assess scientific papers for full-replication feasibility and rank the easiest candidates. Use when given arXiv links, DOIs, or a bibliography and asked to check reproducibility, find code and data, estimate compute requirements, detect access blockers, or select papers an autonomous agent can reproduce.
---

# Assess Reproducibility

Judge whether an agent could fully replicate each paper today on a modest machine. For a batch, surface the easiest astronomy science papers first.

## Target machine

9 CPU cores, 20 GB RAM, 100 GB disk. No GPU, logins, paid APIs, or private data. Flag anything that exceeds this.

**Full replication** means regenerating every key figure, table, numerical result, and central claim from the most upstream public inputs. Author-produced figures, posteriors, fitted catalogs, or other result files cannot substitute for a missing pipeline stage.

## Per paper

1. Read the full paper, appendices, figure captions, and data/code availability statements.
2. Find the code: paper links, author pages, GitHub, Zenodo, searches for the title and arXiv ID. Inspect the repo and confirm it covers the central analysis — a plotting-only or unrelated repo doesn't count.
3. List every input the central results require. Open each link and verify the files are public and downloadable without authentication. A public survey does not mean the paper's exact sample, labels, or simulations are public.
4. Trace the pipeline from public inputs to each key result. Note missing code, unreleased intermediates, pretrained models, manual classifications, external services, and broken links.
5. Estimate peak resources for a fresh run: CPU-hours, RAM, and disk including downloads and intermediates. Give ranges, state your basis, mark inferred numbers, and never invent precise figures.

Cite direct paper, code, and data links for every claim.

## Labels

**Code** — `Yes`: covers the central analysis with identifiable entrypoints. `Partial`: only some stages, notebooks, plotting, or precomputed outputs. `No`: nothing relevant found.

**Data** — `Yes`: every essential input is public without authentication. `Partial`: some inputs or only author-derived products. `No`: an essential input is private, request-only, login-gated, or missing.

Missing code is not fatal when the method is small and clearly specified. It is `Hard` or `Blocked` when it means rebuilding a complex model, simulation, training run, or selection pipeline.

## Verdict

- `Easy`: data `Yes`; no auth, paid API, or GPU; ≤24 CPU-hours, ≤20 GB RAM, ≤100 GB disk; code works or is trivial to reconstruct.
- `Medium`: feasible on the target machine but needs modest code repair or 24–216 CPU-hours (≈24 h wall on 9 cores).
- `Hard`: possible in principle but needs major reconstruction, a GPU, >216 CPU-hours or a serial job >24 h, >20 GB RAM, >100 GB disk, or difficult data assembly.
- `Blocked`: an essential input or method is unavailable, or the resources cannot be adapted to the target machine.

Name the decisive blocker. Never award `Easy` or `Medium` while any essential link or pipeline stage is unverified.

## Batches

1. Deduplicate arXiv/journal versions; account for every unique paper.
2. Exclude software releases, reviews, opinion pieces, instrumentation/survey/data-release papers, and pure methodology papers unless they contain a standalone science result. Excluded papers appear only in `Excluded`, not the table.
3. Rank feasible papers by: verified public data, complete code, no auth/GPU, lower compute, clearer targets.
4. Shortlist all `Easy` papers, then the strongest `Medium`. Keep `Hard` in the table but off the shortlist; drop `Blocked` from the shortlist entirely. Never shortlist a paper with an unresolved blocker.

## Output

One row per assessed paper, sorted easiest first:

| Paper | Code | Code link | Data | Data link | CPU-hours | RAM GB | Disk GB | GPU | Verdict | Blocker |
|---|---|---|---|---|---:|---:|---:|---|---|---|

Use `—` where nothing applies (e.g. no GPU, no blocker). Then:

- `Shortlist`: papers in launch order, one sentence each.
- `Excluded`: non-science and duplicate entries, with reasons.
- `Uncertainties`: only assumptions that could change a verdict.

For a single paper, use the same table, then list the minimum figures, tables, and claims a full replication must regenerate.
