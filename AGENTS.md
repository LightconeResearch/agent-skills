# AGENTS.md

This repository is the **source of truth for the Lightcone Research agent skills**.
It is not an application — it packages `SKILL.md`-based skills for three install
targets (the `npx skills` CLI, the Claude Code plugin marketplace, and Codex plugins)
from a single canonical source.

## Where things live

- `skills/<name>/SKILL.md` — the canonical skills. **Edit these.** One directory per
  skill; the directory name must equal the `name:` in the frontmatter.
- `agents/` — Claude subagents. `hooks/` — plugin `hooks.json` + bash scripts.
- `skills.config.json` — declares how skills compose into the three plugins
  (`astra`, `lightcone-core`, `lightcone-reproduction`) and their dependencies.
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

## Authoring conventions

- `name`: 1–64 chars, lowercase letters/digits/hyphens, matches the directory.
- `description`: ≤ 1024 chars; say *what it does* and *when to use it*, with trigger
  keywords (this is what an agent reads to decide whether to load the skill).
- Keep `SKILL.md` under ~500 lines; push depth into `references/` and load it on demand.
- Any skill that shells out to `lc`/`astra` must open with the **Prerequisites**
  preflight: confirm the CLI resolves, point to `uv tool install lightcone-cli` if not,
  and discover command syntax with `--help` rather than guessing.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full add-a-skill walkthrough.
