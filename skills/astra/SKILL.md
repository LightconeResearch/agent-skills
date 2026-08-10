---
name: astra
description: >
  ASTRA (astra.yaml) support: what the format is, and how to drive the pinned
  `astra` CLI — orientation via `astra guide` and `astra spec`, the validate
  loop, universes, and the paper-evidence workflow. Invoke whenever reading,
  writing, validating, or restructuring an astra.yaml spec, working with
  universes or evidence, or when the user asks about ASTRA.
---

# ASTRA

## What ASTRA is

An ASTRA analysis (`astra.yaml`) is an intermediate layer of abstraction
between code and paper: a machine-readable record of the inputs, outputs, and
every consequential methodological decision — with its reasoning — at the
level needed to make the scientific claims verifiable and reproducible. The
goal is to make the full decision space explicit, so that alternative
defensible choices can be systematically explored (as *universes*) rather
than silently baked in. The structure is self-similar: a top-level analysis
and a nested sub-analysis have exactly the same shape.

## Running `astra`

Run every `astra` command through uv's pinned runner, so the CLI and the
schema it validates against match the version this skill is written for:

```bash
uvx astra-tools@x.y.z <command>
```

Never run a bare `astra` found on PATH — its version is unknown and may not
match what this skill assumes. The rest of this document writes bare `astra`
for readability; always substitute the pinned invocation when you run it.
(`uvx` caches the environment, so repeated calls are fast. If `uvx` is
missing, ask the user to install uv:
https://docs.astral.sh/uv/getting-started/installation/ — never install it
yourself.)

## Orient before authoring

The CLI serves everything this skill deliberately does not repeat:

- `astra guide` — the complete agent briefing on the format: core concepts,
  worked examples, the authoring workflow and judgment (what deserves to be a
  decision, when to split a sub-analysis, universes, evidence), and the
  format rules. **Read it before any substantial authoring or restructuring
  work.** It ships with the installed toolchain, so it always matches the
  validator (same text as https://astra-spec.org/llms.txt).
- `astra spec` — the field-level ground truth, served in sync with the schema
  that `astra validate` enforces: `astra spec` for the concept map,
  `astra spec <term>` for one concept in full (the mode to reach for while
  editing), `astra spec --full` for the entire reference (long).

Re-validate after every change: `astra validate` with no argument checks
every spec and universe file under the current directory (this plugin's hook
also validates automatically when an ASTRA file is saved).

## Citing papers

Always run `astra paper add <doi>` when you cite a paper. Three steps wire a
paper into the analysis:

1. **Cache the PDF** — `astra paper add <doi>` resolves the DOI and downloads
   the paper to the project's paper cache. Pass `--version N` for a specific
   arXiv version.
2. **Add a `prior_insights:` entry** that cites the DOI (and optionally
   `version`) under `evidence:`. The `quote.exact` text must match the PDF
   verbatim; optional `prefix`/`suffix` (~20–100 chars on either side)
   disambiguate when the exact string occurs more than once.
3. **Verify** — `astra paper verify-quotes <doi>` for one paper, or
   `astra validate astra.yaml --verify-evidence` to check every quote in the
   spec. A wrong `exact` string fails validation.

`astra paper list` shows what's cached; `astra paper path <doi>` prints the
PDF path so you can open it for review.

## CLI reference

All commands below run through the pinned invocation from
[Running `astra`](#running-astra).

`astra` validates and inspects; it never executes recipes. The separation is
deliberate — the spec stays stable while agents and execution layers evolve,
and the choice of runner stays yours — so don't encode runner-specific
behavior into the spec.

```bash
astra init [DIRECTORY]                          # Scaffold a new analysis
astra validate [FILE]                           # Validate the whole project, or one file (run after every change)
astra validate astra.yaml --verify-evidence     # + verify insight quotes against PDFs
astra guide                                     # Full agent briefing on the format (read before authoring)
astra spec [TERM|--full]                        # Schema reference (see above)
astra info [--decisions|--inputs|--outputs]     # Analysis summary / element details
astra universe generate -n NAME [-d "desc"]     # Generate universe from defaults
astra universe check universes/x.yaml           # Check universe constraints
astra viz [--fmt ascii|mermaid]                 # Visualize decision space
astra paper add DOI [--version N]               # Cache a paper (resolved from its DOI)
astra paper list                                # List cached papers
astra paper show DOI                            # Show metadata for a cached paper
astra paper path DOI [--version N]              # Print the cached PDF's path
astra paper verify-quotes DOI                   # Batch-verify quotes; reads {"quotes":[...]} JSON from stdin
```
