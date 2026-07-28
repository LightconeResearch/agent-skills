# Lightcone Research Agent Skills

Portable, open-standard skills for **ASTRA** and **scientific paper
reproduction**.

These skills follow the [Agent Skills standard](https://agentskills.io), work
across Claude Code and Codex, and are also packaged as plugins with their hooks
included.

[:simple-github: **View on GitHub**](https://github.com/LightconeResearch/agent-skills){ .md-button .md-button--primary }

## Plugins

| Plugin | What it provides |
|---|---|
| **[`astra`](astra.md)** | ASTRA authoring guidance and validation hooks. |
| **[`reproduction`](reproduction.md)** | Paper assessment, reproduction, and figure comparison, with ASTRA bundled. |

## Install

First, pick a plugin:

- `astra` if you want to write and validate ASTRA analyses.
- `reproduction` if you want to assess and reproduce papers and compare the
  results. It already includes ASTRA.

The commands below install `astra`. Use `reproduction@lightcone-research`
instead if you want the full reproduction toolkit.

=== "Claude Code"

    ```bash
    claude plugin marketplace add LightconeResearch/agent-skills
    claude plugin install astra@lightcone-research
    ```

=== "Claude App"

    Go to **Customize → Plugins**, click **Add**, then choose
    **Add marketplace → Add from repo**. Paste
    `https://github.com/LightconeResearch/agent-skills`, pick a plugin, and call
    it with `/astra:astra` or `/reproduction:reproduce`.

=== "Codex CLI"

    ```bash
    codex plugin marketplace add LightconeResearch/agent-skills
    codex plugin add astra@lightcone-research
    ```

=== "Codex App"

    Click the arrow beside **Create** and open **Plugins**. Install the
    `LightconeResearch/agent-skills` marketplace, search for `astra` or
    `reproduction`, and install one. Then call `/astra:astra` or
    `/reproduction:reproduce`.

## Skills

- **ASTRA:** [`astra`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/astra)
- **Reproduction:** [`assess-reproducibility`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/assess-reproducibility), [`reproduce`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/reproduce), and [`figure-comparison`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/figure-comparison)
