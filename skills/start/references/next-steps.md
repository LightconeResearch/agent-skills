# Next steps on an existing analysis (Route B)

The project already holds a real `astra.yaml`. The job here is not to re-scope it — it's to read where the analysis stands and route to the next valuable move. Ground every recommendation in the actual state, not assumptions.

## 1. Read the state

Gather these before proposing anything (the Triage step in `SKILL.md` already runs the first two):

```bash
astra validate astra.yaml      # valid, or a concrete error block
lc status --json               # ok / stale / missing / alias per output, per universe
lc verify                      # (optional) provenance integrity of materialized outputs
```

From the spec itself, note:

- **Decisions** — how many, and whether any lack `insights:` / evidence (candidates for a literature pass).
- **Narrative** — is `narrative.findings` still TODO while results exist on disk? (findings should be written once, after results land.)
- **Universes** — only `baseline`, or a multiverse? An analysis with meaningful decisions but a single universe is a candidate for `astra universe generate`.
- **Sub-analyses** — any `analyses:` entries that are stubs vs. fully specified.

## 2. Summarize the situation

Tell the user, in a few lines: what the analysis is, validation status, how many outputs are `ok` vs `stale`/`missing`, and the one or two things that most stand out. Build on the session-start hook's summary rather than repeating it.

## 3. Route to the next step

Pick the most pressing item the state reveals; use `AskUserQuestion` when more than one direction is reasonable. Rough priority order:

| If the state shows… | Next step | How |
|---|---|---|
| **Validation errors** | Fix the spec | Edit `astra.yaml`, re-run `astra validate astra.yaml` until clean. The PostToolUse hook re-validates on every save. |
| **`missing` / `stale` outputs** | Materialize them | `lc run <output_id> --universe <name>` — build iteratively, upstream first. See [cli.md](cli.md) for status interpretation and failure diagnosis. |
| **Decisions without evidence, or known gaps** | Literature & decisions pass | Reuse the Paper Collection → Extraction → Decision Identification flow in [new-project.md](new-project.md) (Phase 3); delegate PDFs to the `lc-extractor` subagent, one paper per agent. |
| **Results exist but `narrative.findings` is TODO** | Write the findings/narrative | Fill the `narrative:` block in `astra.yaml` (see `/astra` → Narrative for the five-key structure and `#anchor` cross-references). Keep it grounded in the materialized results. |
| **Outputs `ok` but never integrity-checked** | Verify provenance | `lc verify` — recompute hashes, walk the chain; repair any failures with `lc run`. |
| **Meaningful decisions, single universe** | Explore the multiverse | `astra universe generate -n <name>` for alternative defensible paths, then `lc run` across universes. |
| **Analysis complete, ready to share** | Publish | `lc export wrroc` — Workflow Run RO-Crate bundle (see [cli.md](cli.md)). |

## Restrictions

This skill orchestrates and authors the spec — it does **not** write implementation code. It may run `lc`/`astra` commands (status, validate, run, verify, universe generate, export) and edit `astra.yaml` / `universes/*.yaml`. When a next step needs new analysis *code* (a new recipe's script, a parameterization), that's the user's implementation work; this skill helps wire it into the spec and run it, not write it. Never fabricate evidence — all quotes must pass `astra validate --verify-evidence`.
