# Contributing

This repo turns one canonical set of skills into four install targets. The golden
rule: **edit the source, then regenerate.** Never hand-edit a generated file.

## Layout

| Path | Role | Edit? |
|---|---|---|
| `src/skills/<name>/SKILL.md` (+ `references/`, `scripts/`, `assets/`, `templates/`) | Canonical skills | ✅ |
| `src/agents/*.md` | Claude subagents | ✅ |
| `src/hooks/<plugin>/hooks.json`, `src/hooks/<plugin>/scripts/*.sh` | Per-plugin hooks (Claude/Codex protocol) | ✅ |
| `src/adapters/antigravity-hook.sh` | Runs those hook scripts under Antigravity's protocol | ✅ |
| `src/assets/logo.svg` | Plugin logo bundled into each generated plugin | ✅ |
| `skills.config.json` | How skills compose into plugins | ✅ |
| `scripts/*.mjs` | Generator + validator | ✅ |
| `.claude-plugin/marketplace.json` | Claude marketplace manifest | ⚙️ generated |
| `.agents/plugins/marketplace.json` | Codex marketplace manifest | ⚙️ generated |
| `skills/**` | Flat skill copies for `npx skills` — owning plugin's tool pins substituted | ⚙️ generated |
| `plugins/**` | Per-plugin dirs — self-contained copies, tool pins substituted; each also carries `.antigravity-plugin/plugin.json` and a root `hooks.json` for Antigravity | ⚙️ generated |
| `manifest.json` | Skill/plugin registry | ⚙️ generated |

## Add a skill

1. Create `src/skills/<name>/SKILL.md` with frontmatter:
   ```yaml
   ---
   name: <name>            # lowercase-hyphen, must equal the directory name
   description: >          # ≤1024 chars: what it does + when to use it (trigger words)
     ...
   ---
   ```
   Keep the body under ~500 lines; offload detail to `src/skills/<name>/references/`.
2. If it shells out to a CLI tool (e.g. `astra`), invoke it through the pinned
   `uvx` form with the **literal version placeholder** — `uvx astra-tools@x.y.z
   <command>` — and add the **Prerequisites** preflight block (copy the pattern
   from `src/skills/astra/SKILL.md`): check the pinned CLI resolves, point to
   the uv install docs if `uvx` is missing, and use `--help` to discover
   syntax. See [Tool pins](#tool-pins) for how `x.y.z` becomes a real version.
3. Add the skill to the relevant plugin(s) in `skills.config.json` (`plugins[].skills`).
4. `npm run build && npm test`, then commit source **and** regenerated files together.

## Add or change a plugin

Edit `skills.config.json`:

- `version` — this plugin's own semver, independent of every other plugin.
  Both harnesses resolve updates per plugin from it: Claude Code skips
  `claude plugin update` when the resolved version matches its cache, and
  Codex uses it as the install cache key. **Bump the version of every plugin
  whose generated `plugins/<name>/` dir changes in a PR** — including plugins
  that merely bundle a changed dependency (an `astra` change also bumps every
  plugin bundling it) — and leave the others untouched.
- `skills` — directly-owned skills (Claude exposes exactly these).
- `dependencies` — other plugins this one **bundles**. The generator inlines the full
  transitive closure (own + dependency skills, hooks, agents) as byte-copies (installers
  archive the dir and don't follow outward symlinks, so copies are required) under `plugins/<name>/`, so the plugin
  is self-contained and installs identically on every harness.
- `requires` — other plugins this one **depends on but does not bundle**. Documented
  only: the user installs the required plugin separately (surfaced in the README and the
  plugin description). Nothing is added to the closure.
- `hooks` — path to this plugin's own `src/hooks/<plugin>/hooks.json` (a plugin owns at
  most one). Hook commands reference the plugin root as `${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}` —
  `CLAUDE_PLUGIN_ROOT` is the one root variable Claude and Codex both define (the `$PLUGIN_ROOT`
  fallback covers older Codex versions) — and always spell script paths `hooks/scripts/<name>.sh`
  — the build flattens every closure hook tree under one `hooks/scripts/` dir. When a
  plugin bundles a dependency that also ships hooks (e.g. a plugin bundling `astra`), the
  generator **merges** the manifests: hook groups concatenate per event, scripts copy
  side by side (canonical script basenames must stay unique across plugins). `agents` —
  Claude subagent file paths.

  **Antigravity** gets its own translated root `hooks.json` per plugin, generated from
  the same canonical manifests. The translation is strict, so keep a hook inside what
  it understands, or extend `antigravityHooks()` in `scripts/lib.mjs`. The build fails
  loudly rather than dropping a hook:
  - Commands must keep exactly the form
    `bash "${CLAUDE_PLUGIN_ROOT:-$PLUGIN_ROOT}/hooks/scripts/<name>.sh"`. The build
    rewrites each one to run through `src/adapters/antigravity-hook.sh`.
  - Events: `SessionStart` and `PostToolUse`. Every `PostToolUse` matcher token needs
    an entry in `ANTIGRAVITY_TOOLS`.
  - Output: a script speaks to the model only through
    `{"hookSpecificOutput":{…,"additionalContext":"…"}}`, printed in that exact form.
    The adapter converts it to a system message. Antigravity's PostToolUse cannot
    talk to the model, so that context is held until the next model call and
    injected then.

Then `npm run build && npm test`.

## Tool pins

Skills and hooks that invoke a CLI tool do it through a version-pinned `uvx`
run, and the version is **templated**, never written by hand:

- **Canonical sources use the literal placeholder** `x.y.z` — e.g.
  `uvx astra-tools@x.y.z validate astra.yaml`. A concrete version in
  `src/skills/` or `src/hooks/` fails `npm test`, so nothing in the sources ever looks
  like a number a contributor should wonder about updating.
- **Pins are declared per plugin** in `skills.config.json`, in each plugin's
  `tools` map (e.g. `"tools": { "astra-tools": "0.2.13" }`). A plugin's
  *effective* pins merge over its dependency closure — dependencies first, own
  entries win — so a plugin bundling `astra` inherits its pin unless it
  declares its own, and two plugins can ship the same skill pinned to
  different versions.
- **`npm run build` substitutes the pins** into the generated `plugins/<name>/`
  copies, and the owning plugin's pins (the first plugin listing the skill in
  its own `skills`) into the flat `skills/` copies (canonical files are never rewritten). The drift check compares each
  packaged file against the pin-substituted source, so generator and checker
  agree by construction.
- **Unpinned placeholders fail the build.** If a skill invokes
  `sometool@x.y.z` and no plugin bundling it declares a `sometool` pin, both
  `npm run build` and `npm test` fail naming the invocation — that's the
  reminder to add the pin.
- **To bump a version**: edit the one number in `skills.config.json`, run
  `npm run build`, commit. No other file changes.

Pin only the tool itself — never its transitive schema/data packages (e.g.
astra-spec is deliberately unpinned; the astra-tools release resolves it).

## Validation

`npm test` (alias `node scripts/validate.mjs`) checks:

- every skill's `name` is lowercase-hyphen and matches its directory;
- `description` is present and ≤ 1024 chars;
- plugins reference only skills/agents/hooks/deps that exist;
- canonical `src/skills/`, `src/hooks/` and `src/adapters/` use the `@x.y.z` tool-pin placeholder (no
  concrete versions, no astra-spec pin), and no placeholder is left unpinned
  by the plugins that bundle it;
- the generated manifests and `skills/` + `plugins/` copies match what the current source
  would produce — packaged copies compared with the bundling plugin's tool
  pins applied (drift check);
- `skills/` and `plugins/` hold nothing the build didn't produce, and no
  `SKILL.md` exists outside `src/skills/` and those trees — `npx skills`
  installs the first copy of each skill name it finds, so a stray one (say, an
  `.agents/skills/` left by running the CLI inside this repo) would shadow the
  pinned copy.

For the real thing — installing each plugin into a throwaway environment and
confirming it loads — run the smoke suite (needs `claude`, `codex`, and `tmux`
on PATH; no LLM/API calls):

```bash
npm run smoke            # CLI install (both harnesses) + interactive tmux install (Claude)
npm run smoke -- --cli   # CLI only (hermetic; isolated config dirs)
```

## Local testing of the install paths

```bash
# Claude Code, against your local checkout:
claude plugin marketplace add ./           # or: /plugin marketplace add ./ in-session
claude plugin install astra@lightcone-research

# Validate the Claude plugin/marketplace manifests:
claude plugin validate .
claude plugin validate ./plugins/astra   # (Codex plugin.json layout)

# Antigravity, from the generated plugin dir (build first):
agy plugin validate ./plugins/astra      # may warn that hooks/hooks.json (Claude/Codex only) is not loaded
agy plugin install ./plugins/astra

# npx skills, from the repo (lists the generated skills/ copies — build first):
npx skills add ./ --list
```
