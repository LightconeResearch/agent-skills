# Lightcone Research Agent Skills

Portable, open-standard skills for **ASTRA**.

These skills follow the [Agent Skills standard](https://agentskills.io), work
across Claude Code and Codex, and are also packaged as plugins with their hooks
included.

[:simple-github: **View on GitHub**](https://github.com/LightconeResearch/agent-skills){ .md-button .md-button--primary }

## Plugins

| Plugin | What it provides |
|---|---|
| **[`astra`](astra.md)** | ASTRA authoring guidance and validation hooks. |

## Install

=== "Claude Code"

    ```bash
    claude plugin marketplace add LightconeResearch/agent-skills
    claude plugin install astra@lightcone-research
    ```

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

## Skills

- **ASTRA:** [`astra`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/astra)
