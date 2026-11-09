# The literature pass

Read this when the user wants the analysis informed by published work. The
pass turns papers into `prior_insights` attached to the options they support
(the option → insight → evidence → DOI chain, described in the astra skill
under *Citations, quotes, and supporting evidence*), so it runs against the
spec's decisions, in one order — collect, then extract.

## Collect

Ask for papers the user already has in mind, then search for a *limited* set
of directly relevant ones (~2 per topic, max 10 per section). Relevant means
bearing on a decision in the spec: a paper that compares its options,
justifies one of them, or fixes a threshold or cut the analysis depends on.
Present the list via `AskUserQuestion` with a one-line relevance note each,
and let the user approve, reject, and add.

## Extract

Cache each approved paper with the astra skill's evidence workflow, then
spawn **one subagent per paper**, all in a single message so they run in
parallel. Never read a PDF in the main context — it consumes too much of it.

Give each subagent `references/extraction-brief.md` — which carries the
output shape, the verification loop, and the failure table — plus what only
you know:

- the analysis context — what the analysis is, and which decisions this
  paper might inform;
- the paper's DOI (and arXiv version, if any) and its cached-PDF path;
- the target decisions: each id, its label, and its options;
- the current timestamp, ISO 8601, for `created_at`.

Show progress as results land, so a long pass doesn't look stalled:

```
  ✓ Ba et al. 2016 — 3 prior insights
  ○ Wu & He 2018 (reading…)
```

Write extracted insights to `astra.yaml` as they land, and synthesize by
topic for the user rather than pasting raw returns into the conversation.

**Translate `decision_links` — never copy it.** Each subagent returns a
`decision_links:` block mapping decisions to options to insight ids. It is
not an ASTRA field, and writing it into `astra.yaml` produces a spec that
fails validation. It means: add these insight ids to the `insights:` list on
that option (`Option.insights` in the astra skill's spec reference). The
insights themselves go under `prior_insights:`.

If a subagent reports quotes it could not verify, they are gone — do not
add them back by hand, and do not cite the paper for a claim whose quote
failed.
