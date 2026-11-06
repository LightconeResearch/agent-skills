# The literature pass

Read this when prior insights from published papers are to be added to
`astra.yaml`. The per-paper reading is done by subagents; this file is the
caller's side of the procedure.

## Collect

Take the papers the user names, then search for a *limited* set of directly
relevant ones (~2 per topic, max 10 per section). Present the list via
`AskUserQuestion` with a one-line relevance note each, and let the user
approve, reject, and add.

## Extract

1. **Cache** each approved paper: `uvx astra-tools@x.y.z paper add <doi>`
   (`--version N` to pin an arXiv revision). A paper must be cached before
   its subagent is spawned — the subagent will not cache it itself.
2. **Spawn one subagent per paper**, all in a single message so they run in
   parallel. Never read a PDF in the main context — it consumes too much
   of it.
3. **Brief each subagent** with `references/extraction-brief.md` — which
   carries the output shape, the verification loop, and the failure table —
   plus what only you know:
   - the analysis context — what the analysis is, and which decisions this
     paper might inform;
   - the paper's DOI (and arXiv version, if any) and its cached-PDF path
     (`uvx astra-tools@x.y.z paper path <doi>`);
   - the target decisions: each id, its label, and its options;
   - the current timestamp, ISO 8601, for `created_at`.
4. **Show progress** as results land, so a long pass doesn't look stalled:

   ```
     ✓ Ba et al. 2016 — 3 prior insights
     ○ Wu & He 2018 (reading…)
   ```

5. **Write** extracted insights under `prior_insights:` in `astra.yaml` as
   they land, and synthesize by topic for the user rather than pasting raw
   returns into the conversation.

## Translate `decision_links` — never copy it

Each subagent returns a `decision_links:` block mapping decisions to options
to insight ids. It is not an ASTRA field, and writing it into `astra.yaml`
produces a spec that fails validation. It means: add these insight ids to
the `insights:` list on that option (`Option.insights` in the astra skill's
spec reference).

## Dropped quotes stay dropped

If a subagent reports quotes it could not verify, they are gone — do not add
them back by hand, and do not cite the paper for a claim whose quote failed.
