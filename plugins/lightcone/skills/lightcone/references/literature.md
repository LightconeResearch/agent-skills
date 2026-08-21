# The literature pass

Read this during scoping phase 3, when the user wants the analysis informed
by published work. It runs in one order — collect, then extract, then
identify decisions — because decisions identified before the papers are read
end up being the ones the analyst already had in mind.

## Collect

Ask for papers the user already has in mind, then search for a *limited* set
of directly relevant ones (~2 per topic, max 10 per section). Present the
list via `AskUserQuestion` with a one-line relevance note each, and let the
user approve, reject, and add.

Collect candidates *during* the conversation phases, and process them here.

## Extract

Cache each approved paper with the astra skill's evidence workflow, then
spawn **one subagent per paper**, all in a single message so they run in
parallel. Never read a PDF in the main context — it consumes too much of it.

Give each subagent:

- the analysis context — what the analysis is, and which decisions this
  paper might inform;
- the paper's DOI (and arXiv version, if any) and its cached-PDF path;
- the target decisions: each id, its label, and its options.

Write extracted insights to `astra.yaml` as they land, and synthesize by
topic for the user rather than pasting raw returns into the conversation.

## Identify decisions

From the conversation *and* the literature: what could be done differently
and still be defensible? Where did papers disagree or compare alternatives?
Where was the user uncertain?

Probe the blind spots analysts neglect — data exclusion, variable
operationalization, inference criteria — not just method choices.

Write candidates to `astra.yaml` as a batch for review; keep the chat output
to a summary with ids.

## Review

Confirm or set each decision's `default`, keep the option structure and its
evidence links, and drop any decision the user rejects.
