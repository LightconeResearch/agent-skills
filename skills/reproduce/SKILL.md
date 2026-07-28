---
name: reproduce
description: Fully reproduce a scientific paper from its source and any available code, regenerate all figures and key scientific results with executable code, describe the work in a validated ASTRA specification, build a figure comparison report, and iterate through independent verification until the replication is broadly successful. Use when Codex is asked to reproduce or replicate an academic paper end to end.
---

# Reproduce a scientific paper

## Prerequisites

Run `astra --help` silently to confirm the CLI resolves. If it is missing, tell
the user to run `uv tool install lightcone-cli`, then stop until `astra --help`
succeeds. Use `astra --help` to confirm current command syntax rather than
guessing.

Reproduce the assigned paper using the paper source and any available code.
Produce the full replication in ASTRA format in `astra.yaml`, following the
bundled `astra` skill, and validate it with:

```bash
astra validate astra.yaml
```

Do not stop until you have a full replication of every figure and all key
tables, numerical results, and scientific claims in the paper, unless you are
absolutely sure this cannot be achieved.

Write and run the full replication code in `src/`. It must not depend on
`resources/` as a runtime input. Do not use, copy, extract, trace, hash-match,
or otherwise transform the paper's included figures, tables, or results files
into reproduced outputs. Do not hard-code published results and present them as
recomputed. Regenerate every claimed output from the implemented analysis and
declared inputs.

When the replication appears complete, follow the bundled
`figure-comparison` skill to create `comparison.html`. Include every
reproduced figure and key result so a human can verify that they were replicated
successfully and not copied.

Then spawn a fresh independent verifier subagent. Do not give it the
reproduction conversation or your implementation reasoning. Give it only the
replication directory, the original paper and allowed source materials, and
instruct it to read
[`references/VERIFIER.md`](references/VERIFIER.md) before reviewing the
replication.

Do not finish until an independent verifier reports that the replication is
broadly successful and identifies no major issues affecting the key results or
claims and no easily addressable minor or stylistic issues remain. If it finds a major issue, fix the replication, rerun the code,
revalidate `astra.yaml`, rebuild `comparison.html`, and ask a new fresh
independent verifier to review it. Stop without success only when you are
absolutely sure a demonstrated external blocker makes completion impossible.

This is a full replication attempt and may take many hours.
