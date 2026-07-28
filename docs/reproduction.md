# Reproduction

We developed a skill called `/reproduce`. You can call it like this:

```text
/reproduce https://arxiv.org/abs/1809.03507
```

Your agent will download the paper source, look for the original code, and
attempt to fully reproduce every key result and figure in the paper. This can
require significant compute and storage.

The agent is instructed not to stop until a fresh, independent verifier
subagent can confirm that the reproduction is broadly successful. We wrote a
dedicated prompt for the verifier with best practices for spotting major,
minor, and stylistic issues in the reproduction compared with the original
paper.

The plugin also includes `/assess-reproducibility`, which checks papers for
public code and data, estimates compute requirements, identifies blockers, and
ranks the best candidates to reproduce. `/figure-comparison` builds a portable
side-by-side HTML report comparing the original and reproduced figures, tables,
and reported values.

```bash
codex plugin add reproduction@lightcone-research
```

[View the reproduction skills on GitHub](https://github.com/LightconeResearch/agent-skills#reproduction).
