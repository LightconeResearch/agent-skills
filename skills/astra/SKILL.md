---
name: astra
description: >
  ASTRA (astra.yaml) support: what the format is, and how to drive the pinned
  `astra` CLI — orientation via the agent guide and schema reference, the
  validate loop, universes, and handling citations, quotes, and supporting
  evidence through the paper utilities. Invoke whenever reading, writing,
  validating, or restructuring an astra.yaml spec, working with universes or
  evidence, or when the user asks about ASTRA.
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

Always invoke the `astra` CLI through uv's pinned runner, exactly as written
everywhere in this document:

```bash
uvx astra-tools@x.y.z <command>
```

Never run a bare `astra` found on PATH — its version is unknown and may not
match what this skill assumes. (`uvx` caches the environment, so repeated
calls are fast. If `uvx` is missing, ask the user to install uv:
https://docs.astral.sh/uv/getting-started/installation/ — never install it
yourself.)

## Orient before authoring

The CLI serves everything this skill deliberately does not repeat:

- `uvx astra-tools@x.y.z guide` — the complete agent briefing on the format:
  core concepts, worked examples, the authoring workflow and judgment (what
  deserves to be a decision, when to split a sub-analysis, universes,
  evidence), and the format rules. **Read it before any substantial authoring
  or restructuring work.** It ships with the installed toolchain, so it
  always matches the validator (same text as https://astra-spec.org/llms.txt).
- `uvx astra-tools@x.y.z spec` — the field-level ground truth, served in sync
  with the schema the validator enforces: no argument prints the concept map;
  `uvx astra-tools@x.y.z spec <term>` prints one concept in full (the mode to
  reach for while editing); `uvx astra-tools@x.y.z spec --full` prints the
  entire reference (long).

Re-validate after every change: `uvx astra-tools@x.y.z validate` with no
argument checks every spec and universe file under the current directory
(this plugin's hook also validates automatically when an ASTRA file is
saved).

## Citations, quotes, and supporting evidence

Claims in ASTRA are backed by verifiable evidence: `prior_insights` (imported
claims that motivate decisions) and `findings` (claims the analysis produces)
both carry `evidence` entries — a `doi` with a verbatim quote for literature,
or an `artifact` naming an output. The `paper` utilities manage the
literature side end to end:

1. **Cache the source at authoring time** — run
   `uvx astra-tools@x.y.z paper add <doi>` the moment you cite a paper (pass
   `--version N` to pin an arXiv revision). The PDF lands in the project's
   paper cache, so the citation stays checkable without asking the reader to
   fetch anything.
2. **Pull exact quotes from the cached PDF** —
   `uvx astra-tools@x.y.z paper path <doi>` prints the cached file's path so
   you can open it and copy the supporting text *verbatim* into
   `quote.exact`; add `prefix`/`suffix` (~20–100 chars on either side) when
   the exact string occurs more than once. Write every quote as if a machine
   will look for it — one will.
3. **Verify before you're done** —
   `uvx astra-tools@x.y.z paper verify-quotes <doi>` checks one paper's
   quotes; `uvx astra-tools@x.y.z validate astra.yaml --verify-evidence`
   checks every quote in the spec. A quote that doesn't match the PDF fails
   validation.

`uvx astra-tools@x.y.z paper list` shows the cache;
`uvx astra-tools@x.y.z paper show <doi>` prints a cached paper's metadata.
Artifact-backed evidence (typical for findings whose outputs aren't
materialized yet) is reported as SKIPPED, not failed.

## CLI reference

The `astra` CLI validates and inspects; it never executes recipes. The
separation is deliberate — the spec stays stable while agents and execution
layers evolve, and the choice of runner stays yours — so don't encode
runner-specific behavior into the spec.

```bash
uvx astra-tools@x.y.z init [DIRECTORY]                          # Scaffold a new analysis
uvx astra-tools@x.y.z validate [FILE]                           # Validate the whole project, or one file (run after every change)
uvx astra-tools@x.y.z validate astra.yaml --verify-evidence     # + verify insight quotes against PDFs
uvx astra-tools@x.y.z guide                                     # Full agent briefing on the format (read before authoring)
uvx astra-tools@x.y.z spec [TERM|--full]                        # Schema reference (see above)
uvx astra-tools@x.y.z info [--decisions|--inputs|--outputs]     # Analysis summary / element details
uvx astra-tools@x.y.z universe generate -n NAME [-d "desc"]     # Generate universe from defaults
uvx astra-tools@x.y.z universe check universes/x.yaml           # Check universe constraints
uvx astra-tools@x.y.z paper add DOI [--version N]               # Cache a paper (resolved from its DOI)
uvx astra-tools@x.y.z paper list                                # List cached papers
uvx astra-tools@x.y.z paper show DOI                            # Show metadata for a cached paper
uvx astra-tools@x.y.z paper path DOI [--version N]              # Print the cached PDF's path
uvx astra-tools@x.y.z paper verify-quotes DOI                   # Batch-verify quotes; reads {"quotes":[...]} JSON from stdin
```
