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

=== "Claude Code"

    ```bash
    claude plugin marketplace add LightconeResearch/agent-skills
    claude plugin install reproduction@lightcone-research
    ```

=== "Codex"

    ```bash
    codex plugin marketplace add LightconeResearch/agent-skills
    codex plugin add reproduction@lightcone-research
    ```

Replace `reproduction` with `astra` to install the standalone ASTRA plugin.

## Skills

- **ASTRA:** [`astra`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/astra)
- **Reproduction:** [`assess-reproducibility`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/assess-reproducibility), [`reproduce`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/reproduce), and [`figure-comparison`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/figure-comparison)
