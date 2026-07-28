# Lightcone Research Agent Skills

Portable, open-standard skills for **ASTRA**, the **Lightcone** project workflow,
and **scientific paper reproduction**.

These skills follow the [Agent Skills standard](https://agentskills.io), work
across Claude Code and Codex, and are also packaged as plugins with their hooks
and subagents included.

[:simple-github: **View on GitHub**](https://github.com/LightconeResearch/agent-skills){ .md-button .md-button--primary }

## Plugins

| Plugin | What it provides |
|---|---|
| **[`astra`](astra.md)** | ASTRA authoring guidance and validation hooks. |
| **[`lightcone`](lightcone.md)** | The `lc` project workflow, with ASTRA bundled. |
| **[`reproduction`](reproduction.md)** | Paper assessment, reproduction, and figure comparison, with ASTRA bundled. |

## Install

=== "Claude Code"

    ```bash
    claude plugin marketplace add LightconeResearch/agent-skills
    claude plugin install lightcone@lightcone-research
    ```

=== "Codex"

    ```bash
    codex plugin marketplace add LightconeResearch/agent-skills
    codex plugin add lightcone@lightcone-research
    ```

Replace `lightcone` with `astra` or `reproduction` to install either plugin
directly.

## Skills

- **ASTRA:** [`astra`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/astra)
- **Lightcone:** [`new`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/new), [`report`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/report), [`feedback`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/feedback), and [`cli`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/cli)
- **Reproduction:** [`assess-reproducibility`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/assess-reproducibility), [`reproduce`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/reproduce), and [`figure-comparison`](https://github.com/LightconeResearch/agent-skills/tree/main/skills/figure-comparison)
