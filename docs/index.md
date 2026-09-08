# Lightcone Research Agent Skills

Portable, open-standard skills that teach coding agents the
[Lightcone Research](https://github.com/LightconeResearch) stack.

The skills follow the [Agent Skills standard](https://agentskills.io), work
across Claude Code, Codex and OpenCode, and are packaged as plugins with their
hooks included.

[:simple-github: **View on GitHub**](https://github.com/LightconeResearch/agent-skills){ .md-button .md-button--primary }

## Plugins

| Plugin | What it provides |
|---|---|
| **[`astra`](astra.md)** | ASTRA authoring guidance and validation hooks. |
| **`lightcone`** | Companion for a whole Lightcone project — scoping, the `lc` execution workflow, publishing. Bundles `astra`, so installing it alone gives the full stack. |

## Install

The only prerequisite is
[`uv`](https://docs.astral.sh/uv/getting-started/installation/): plugins with
Python dependencies install them on first use.

=== "Claude Code"

    ```bash
    claude plugin marketplace add LightconeResearch/agent-skills
    claude plugin install astra@lightcone-research
    ```

    Then invoke `/astra:astra` in a session.

=== "Claude App"

    Go to **Customize → Plugins**, click **Add**, then choose
    **Add marketplace → Add from repo**. Paste
    `https://github.com/LightconeResearch/agent-skills`, pick `astra`, and call
    it with `/astra:astra`.

=== "Codex CLI"

    ```bash
    codex plugin marketplace add LightconeResearch/agent-skills
    codex plugin add astra@lightcone-research
    ```

    Then invoke the skill in Codex, for example `$astra:astra`.

=== "Codex App"

    Click the arrow beside **Create** and open **Plugins**. Install the
    `LightconeResearch/agent-skills` marketplace, search for `astra`, and
    install it. Then call `/astra:astra`.

=== "OpenCode"

    OpenCode reads Agent Skills directly and loads plugins as JavaScript
    files, so there is no marketplace step: install the skills with the
    [`skills` CLI](https://github.com/vercel-labs/skills), then drop the
    generated hooks file into OpenCode's plugin directory.

    ```bash
    npx skills add https://github.com/LightconeResearch/agent-skills/tree/main/plugins/astra -a opencode -g
    mkdir -p ~/.config/opencode/plugins
    curl -fsSL https://raw.githubusercontent.com/LightconeResearch/agent-skills/main/plugins/astra/opencode/astra.js -o ~/.config/opencode/plugins/astra.js
    ```

    The skill lands in `~/.agents/skills/` (drop `-g` for `./.agents/skills/`);
    the agent loads it when the task matches, or when you ask it to "use the
    astra skill". See the [OpenCode page](opencode.md) for what the plugin
    file does.

## Tutorial

New to ASTRA? [Get started](getting-started.md) by working through a complete
analysis — fitting ΛCDM to 580 Type Ia supernovae — with an agent doing the
work and ASTRA keeping the record.
