# Contributing

This repo turns one canonical set of skills into three install targets. The golden
rule: **edit the source, then regenerate.** Never hand-edit a generated file.

## Layout

| Path | Role | Edit? |
|---|---|---|
| `skills/<name>/SKILL.md` (+ `references/`, `scripts/`, `assets/`, `templates/`) | Canonical skills | ✅ |
| `agents/*.md` | Claude subagents | ✅ |
| `hooks/hooks.json`, `hooks/scripts/*.sh` | Plugin hooks | ✅ |
| `skills.config.json` | How skills compose into plugins | ✅ |
| `scripts/*.mjs` | Generator + validator | ✅ |
| `.claude-plugin/marketplace.json` | Claude marketplace manifest | ⚙️ generated |
| `.agents/plugins/marketplace.json` | Codex marketplace manifest | ⚙️ generated |
| `plugins/**` | Codex per-plugin dirs (symlinked skills) | ⚙️ generated |
| `manifest.json` | Skill/plugin registry | ⚙️ generated |

## Add a skill

1. Create `skills/<name>/SKILL.md` with frontmatter:
   ```yaml
   ---
   name: <name>            # lowercase-hyphen, must equal the directory name
   description: >          # ≤1024 chars: what it does + when to use it (trigger words)
     ...
   ---
   ```
   Keep the body under ~500 lines; offload detail to `skills/<name>/references/`.
2. If it shells out to `lc`/`astra`, add the **Prerequisites** preflight block (copy
   the pattern from `skills/start/SKILL.md`): check the CLI resolves, point to
   `uv tool install lightcone-cli` if missing, and use `--help` to discover syntax.
3. Add the skill to the relevant plugin(s) in `skills.config.json` (`plugins[].skills`).
4. `npm run build && npm test`, then commit source **and** regenerated files together.

## Add or change a plugin

Edit `skills.config.json`:

- `skills` — directly-owned skills (Claude exposes exactly these).
- `dependencies` — other plugins this one builds on. Claude resolves these on install;
  Codex plugins are self-contained, so the generator bundles the full transitive
  closure (own + dependency skills) as symlinks under `plugins/<name>/skills/`.
- `hooks` — path to a `hooks.json` (hook commands reference the plugin root as
  `${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}` so both harnesses resolve it). `agents` — Claude subagent file paths.

Then `npm run build && npm test`.

## Validation

`npm test` (alias `node scripts/validate.mjs`) checks:

- every skill's `name` is lowercase-hyphen and matches its directory;
- `description` is present and ≤ 1024 chars;
- plugins reference only skills/agents/hooks/deps that exist;
- the generated manifests and `plugins/` symlinks match what the current source
  would produce (drift check).

## Local testing of the install paths

```bash
# Claude Code, against your local checkout:
claude plugin marketplace add ./           # or: /plugin marketplace add ./ in-session
claude plugin install lightcone@lightcone-research

# Validate the Claude plugin/marketplace manifests:
claude plugin validate .
claude plugin validate ./plugins/lightcone   # (Codex plugin.json layout)

# npx skills, from the repo:
npx skills add ./ --list
```
