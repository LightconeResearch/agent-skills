# ASTRA

The `astra` plugin helps an agent write and revise an `astra.yaml`: a
machine-readable record of an analysis's inputs, outputs, and consequential
methodological decisions.

The skill focuses on the judgment that is hard to capture in a schema alone,
including what should count as a decision, how choices should be parameterized
in code, and when an analysis should be split into smaller units. The bundled
hooks load this guidance when an agent reads an ASTRA file and validate the file
when it is saved.

```bash
codex plugin add astra@lightcone-research
```

[View the `astra` skill on GitHub](https://github.com/LightconeResearch/agent-skills/tree/main/skills/astra).
