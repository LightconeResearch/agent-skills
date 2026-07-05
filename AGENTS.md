# AGENTS.md

This repository is the **source of truth for the Lightcone Research agent skills**.
It is not an application — it packages `SKILL.md`-based skills for three install
targets (the `npx skills` CLI, the Claude Code plugin marketplace, and Codex plugins)
from a single canonical source. Two plugins: `astra` (spec reference) and
`lightcone` (the `lc` project workflow + hooks), which depends on `astra`. Plugin
skills are namespaced by plugin name (e.g. `/lightcone:start`, `/astra:astra`).

## Where things live

- `skills/<name>/SKILL.md` — the canonical skills. **Edit these.** One directory per
  skill; the directory name must equal the `name:` in the frontmatter.
- `agents/` — Claude subagents (`lc-extractor`, used by the `start` skill). `hooks/` —
  plugin `hooks.json` + bash scripts.
- `skills.config.json` — declares how skills compose into the plugins
  (`astra`, `lightcone`) and their dependencies.
- `scripts/build.mjs`, `scripts/validate.mjs` — the generator and the validator.

## Generated — do not hand-edit

`.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`, the entire
`plugins/` tree, and `manifest.json` are **generated** from `skills.config.json` +
`skills/`. After changing any skill or the config:

```bash
npm run build     # regenerate all target files
npm test          # validate frontmatter + assert nothing drifted
```

Commit the regenerated files alongside your source change. CI runs `npm test` and
fails if the generated files are out of sync. The generator is zero-dependency
(Node ≥ 18 built-ins only) — no `npm install` is required.

## Build tooling — design & rationale

If you arrived expecting a plain skills folder and found a generator, here's why it
exists and the shape it takes, so nothing surprises you.

**Why a generator at all (not hand-maintained JSON).** The three targets disagree on
layout. `npx skills` and the Claude marketplace both read the flat canonical `skills/`
tree (Claude uses one `marketplace.json` with `source: "./"` + `skills: [...]` arrays,
no per-plugin dirs). **Codex** (OpenAI Codex CLI) wants the opposite:
`.agents/plugins/marketplace.json` plus a `plugins/<name>/.codex-plugin/plugin.json`
*with its own `skills/` directory* per plugin — and, for a plugin that ships hooks,
its own `hooks/` directory too (Codex reads the same `hooks.json`
protocol; hook commands use `${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}`, so the generator declares the same
`hooks` file and symlinks the canonical `hooks/` tree under the plugin root).
Maintaining both against one set of skills by hand is exactly what drifts
silently. So `skills.config.json` + `skills/` is the single source, and everything
per-target is generated and drift-checked. **Do not edit a generated file to fix a
target — change the source and rebuild.** If a manifest looks wrong, the bug is in
`skills.config.json` or `scripts/lib.mjs`, not in the output.

**How the pieces fit.** `scripts/lib.mjs` is the engine: it loads the config, parses
each `SKILL.md` frontmatter, computes the transitive skill closure per plugin (own +
dependency skills — Codex plugins are self-contained, so they bundle the whole
closure), and returns the exact files + symlinks every target needs. `build.mjs` writes
them; `validate.mjs` regenerates in memory and diffs against disk. Both import `lib.mjs`
so the generator and the checker agree by construction.

**Two deliberate, non-obvious choices** (don't "fix" these without reading this):

- **Zero dependencies / hand-written frontmatter parser.** `lib.mjs` parses YAML
  frontmatter itself (inline + folded/literal scalars) instead of pulling in
  `gray-matter`, and there's no `tsx`/`vitest`. This is intentional: the generator runs
  with no `npm install`, so it works in a fresh checkout and in CI without a setup step.
  If you add a dependency, you give that up. The parser only needs to handle `name` and
  `description` — if a skill ever needs richer frontmatter parsing, that's the tradeoff
  to weigh.
- **Codex skills (and hooks) are symlinks, not copies.** Each
  `plugins/<name>/skills/<skill>` is a relative symlink back to the canonical
  `skills/<skill>`, and for a hooks-bearing plugin `plugins/<name>/hooks` symlinks
  back to the canonical `hooks/` (git tracks them as symlinks, mode `120000`). This
  keeps one source of truth instead of duplicating bodies into `plugins/`.
  `validate.mjs` checks skill symlinks resolve to a real `SKILL.md` and other
  symlinks resolve to a directory.

**Prior art.** The pattern is borrowed: databricks/databricks-agent-skills (a generated
`manifest.json` registry from skill frontmatter, CI-validated, plus per-agent plugin
dirs incl. `.codex-plugin/`) and supabase/agent-skills (the `source: "./"` + `strict:
false` Claude marketplace style, and a build + sanity-test workflow). We trimmed both to
zero-dep and reconciled them to the three-target need.

## Authoring conventions

- `name`: 1–64 chars, lowercase letters/digits/hyphens, matches the directory.
- `description`: ≤ 1024 chars; say *what it does* and *when to use it*, with trigger
  keywords (this is what an agent reads to decide whether to load the skill).
- Keep `SKILL.md` under ~500 lines; push depth into `references/` and load it on demand.
- Any skill that shells out to `lc`/`astra` must open with the **Prerequisites**
  preflight: confirm the CLI resolves, point to `uv tool install lightcone-cli` if not,
  and discover command syntax with `--help` rather than guessing.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full add-a-skill walkthrough.
