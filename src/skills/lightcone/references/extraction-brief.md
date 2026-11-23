# Per-paper extraction brief

This is the brief to hand a subagent that reads **one** paper. Pass it along
with the paper-specific context listed in `references/literature.md`; the
subagent does not need this skill, only this file and its paper.

It is written as instructions to that subagent. Everything in it exists
because quotes that were never checked against the PDF are the single way
this workflow produces something worse than nothing: a citation that looks
verifiable and isn't.

- [What to extract](#what-to-extract)
- [Verify before returning](#verify-before-returning)
- [Return format](#return-format)
- [Rules](#rules)
- [When verification keeps failing](#when-verification-keeps-failing)

## What to extract

Read the cached PDF at the path you were given. Find the claims that bear on
the target decisions you were given — not everything the paper says. For
each one, capture:

- **the claim** — one or two sentences saying what we learned, in your own
  words;
- **an exact quote** — verbatim from the paper, one to three sentences,
  copied not paraphrased;
- **the page** it appears on;
- **prefix and suffix** — roughly 20–100 characters of the surrounding text
  on either side, which is what makes the quote locatable when the same
  words occur more than once.

One claim per insight. Never combine two findings into one.

## Verify before returning

Every quote must be checked against the PDF text before you return it. Check
them in one batch rather than one at a time — the tool extracts the PDF text
once and matches everything against it. Each item is a quote and its page,
written exactly as `astra.yaml` writes them:

```bash
echo '[
  {"quote": {"exact": "…", "prefix": "…", "suffix": "…"}, "location": {"value": "page=5"}},
  {"quote": {"exact": "…", "prefix": "…", "suffix": "…"}, "location": {"value": "page=12"}}
]' | uvx astra-tools@x.y.z paper verify-quotes "<DOI>"
```

Add `--version N` for an arXiv paper. The result is a JSON list in the same
order: each quote's `state` — `found`; `elsewhere`, in the paper but not on
the page you gave; `not_found`; or `no_paper` — and, where it is in the
paper, the `page` it is on.

For `elsewhere`, take the page from the tool's answer: validation requires
the quote on the page its location gives. For anything `not_found`, re-read
that part of the PDF, correct the text, prefix and suffix, and verify again.
**Stop after three rounds.** Drop the quotes that still fail, and say which
ones you dropped and why — a dropped quote is a normal outcome, an
unverified one is not.

## Return format

Return only this YAML, with no prose around it:

```yaml
prior_insights:
  <insight_id>:
    claim: "<what we learned from this paper>"
    evidence:
      - doi: "<DOI>"
        version: <arXiv version, omit for non-arXiv>
        quote:
          exact: "<verified quote>"
          prefix: "<~20-100 chars before>"
          suffix: "<~20-100 chars after>"
        location:
          value: page=<page number>
    scope: "<when this applies — omit unless the claim is genuinely limited>"

decision_links:
  <decision_id>:
    <option_id>:
      - <insight_id>

verification_summary:
  total_quotes: <n>
  verified: <n>
  failed: <n>
  failed_details: "<what could not be verified, or 'none'>"
```

`decision_links` is **not** an ASTRA field — it is how you tell the caller
which option each insight bears on. The caller translates it; you never
write it into `astra.yaml` yourself.

The rest of that shape is ASTRA's own, reproduced here so you need nothing
but this file: the insight's id is its key, and neither an insight nor its
evidence carries an `id` field. If a field is ever rejected downstream, the
authority is `uvx astra-tools@x.y.z spec insight` (and `spec evidence`),
which is served in sync with the validator — not this copy.

## Rules

- Insight ids are `lowercase_with_underscores`.
- Only insights relevant to the target decisions. A paper with nothing
  relevant returns `prior_insights: {}` — that is a useful answer, not a
  failure.
- Only insights whose quotes verified.
- `prefix` and `suffix` are required on every quote.
- For arXiv papers, always include the version — a whole number, `2` for
  the second revision.
- The page goes in `location.value` as `page=<n>`, and must be the page the
  quote is on.
- Never invent a quote, and never smooth one out. If the PDF has an odd
  line break or a ligature, the quote has it too.

## When verification keeps failing

| What you see | Usually means | Do this |
|---|---|---|
| `not_found`, quote looks right | Paraphrased, or a typo crept in | Re-read the page and copy the text again, character for character |
| `not_found` on a short quote | The words appear in several places | Lengthen the quote, or give more prefix/suffix |
| `no_paper` | The caller was meant to cache it before spawning you | Stop and report that; do not cache it yourself |
| `elsewhere` | The quote is on another page than the one you gave | Take the page from the tool's own output |
| Persistent `not_found` | OCR artifacts, ligatures, unicode dashes | Choose a shorter span that avoids the problem characters |
