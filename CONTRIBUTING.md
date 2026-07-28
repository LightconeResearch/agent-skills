# Contributing

This repo turns one canonical set of skills into three install targets. The golden
rule: **edit the source, then regenerate.** Never hand-edit a generated file.

## Layout

| Path | Role | Edit? |
|---|---|---|
| `skills/<name>/SKILL.md` (+ `references/`, `scripts/`, `assets/`, `templates/`) | Canonical skills | ✅ |
| `agents/*.md` | Claude subagents | ✅ |
| `hooks/<plugin>/hooks.json`, `hooks/<plugin>/scripts/*.sh` | Per-plugin hooks | ✅ |
| `skills.config.json` | How skills compose into plugins | ✅ |
| `scripts/*.mjs` | Generator + validator | ✅ |
| `.claude-plugin/marketplace.json` | Claude marketplace manifest | ⚙️ generated |
| `.agents/plugins/marketplace.json` | Codex marketplace manifest | ⚙️ generated |
| `plugins/**` | Per-plugin dirs — self-contained byte-copies | ⚙️ generated |
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
- `dependencies` — other plugins this one **bundles**. The generator inlines the full
  transitive closure (own + dependency skills, hooks, agents) as byte-copies (installers
  archive the dir and don't follow outward symlinks, so copies are required) under `plugins/<name>/`, so the plugin
  is self-contained and installs identically on both harnesses. Example: `reproduction`
  bundles `astra`.
- `requires` — other plugins this one **depends on but does not bundle**. Documented
  only: the user installs the required plugin separately (surfaced in the README and the
  plugin description). Nothing is added to the closure.
- `hooks` — path to this plugin's own `hooks/<plugin>/hooks.json` (a plugin owns at
  most one). Hook commands reference the plugin root as `${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}` —
  `CLAUDE_PLUGIN_ROOT` is the one root variable every harness defines (the `$PLUGIN_ROOT`
  fallback covers older harness versions) — and always spell script paths `hooks/scripts/<name>.sh`
  — the build flattens every closure hook tree under one `hooks/scripts/` dir. When a
  plugin bundles a dependency that also ships hooks (e.g. `reproduction` + `astra`), the
  generator **merges** the manifests: hook groups concatenate per event, scripts copy
  side by side (canonical script basenames must stay unique across plugins). `agents` —
  Claude subagent file paths.

Then `npm run build && npm test`.

## Validation

`npm test` (alias `node scripts/validate.mjs`) checks:

- every skill's `name` is lowercase-hyphen and matches its directory;
- `description` is present and ≤ 1024 chars;
- plugins reference only skills/agents/hooks/deps that exist;
- the generated manifests and `plugins/` byte-copies match what the current source
  would produce (drift check).

## Local testing of the install paths

```bash
# Claude Code, against your local checkout:
claude plugin marketplace add ./           # or: /plugin marketplace add ./ in-session
claude plugin install reproduction@lightcone-research

# Validate the Claude plugin/marketplace manifests:
claude plugin validate .
claude plugin validate ./plugins/reproduction   # (Codex plugin.json layout)

# npx skills, from the repo:
npx skills add ./ --list
```
