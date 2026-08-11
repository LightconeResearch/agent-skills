# ASTRA

The `astra` plugin helps an agent write and revise an `astra.yaml`: a
machine-readable record of an analysis's inputs, outputs, and consequential
methodological decisions.

The skill focuses on the judgment that is hard to capture in a schema alone,
including what should count as a decision, how choices should be parameterized
in code, and when an analysis should be split into smaller units.

## What the plugin ships

- **The [`astra` skill](https://github.com/LightconeResearch/agent-skills/tree/main/skills/astra)** —
  the authoring guidance itself. Once the plugin is installed, invoke it as
  `/astra:astra` in Claude or `$astra:astra` in Codex; agents also load it on
  their own when they work with an ASTRA file.
- **A validate-on-save hook** — whenever the agent saves an ASTRA file, the
  spec is re-validated and the result is pushed straight back to the agent.
- **A session-start hook** — starting a session in a directory that contains
  an `astra.yaml` orients the agent with the spec's location and the
  analysis's shape.

## Install

The only prerequisite is
[`uv`](https://docs.astral.sh/uv/getting-started/installation/): the plugin
runs the ASTRA CLI through `uvx`, which installs everything else it needs on
first use.

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

## Try it

The best introduction is the
[getting started tutorial](getting-started.md): it fits the standard
cosmological model to 580 supernovae, with an agent doing the work and ASTRA
keeping the record.

## Going further

The full ASTRA documentation lives at
[astra-spec.org](https://astra-spec.org) — the format reference, the schema,
and a ground-up
[getting started](https://astra-spec.org/latest/getting-started/) guide.
