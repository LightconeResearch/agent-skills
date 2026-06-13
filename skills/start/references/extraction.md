# Prior-insight extraction procedure

Canonical procedure for extracting prior insights from a single paper into an
ASTRA spec. This is the **single source of truth** for the extraction logic and
output format. It is written to be followed in either of two ways:

- **As a subagent** — on harnesses with subagents (e.g. Claude Code's
  `lc-extractor`), one agent processes one paper in an isolated context. This is
  preferred: PDFs are large and stay out of the main conversation.
- **In-context** — on harnesses without subagents (Codex and others), the main
  agent follows this procedure itself, **one paper at a time**, clearing or
  compacting context between papers so PDF text does not accumulate.

Either way the steps, verification loop, and output format are identical — only
*who* runs them differs.

## Inputs you need per paper

- **Analysis context** — the problem statement and the decisions this paper might
  inform (id, label, and each option with its description).
- **DOI** and, for arXiv papers, the **version**.
- **PDF path** — the absolute path from `astra paper path <doi>`.

## Steps

1. Read the PDF at the path above.
2. Identify claims relevant to the target decisions.
3. For each relevant claim, extract:
   - A clear claim (1–2 sentences stating what we learned).
   - An exact quote from the paper (verbatim, 1–3 sentences).
   - The page number where the quote appears (as a hint).
   - Prefix and suffix context (~20–100 chars each) for robust matching.
4. Validate all quotes using batch verification (see below).
5. Keep only verified prior insights.

## Batch verification loop

After extracting all quotes from the paper:

1. Build a JSON object with all quotes:
   ```json
   {"quotes": [
     {"text": "exact quote 1", "page": 5, "prefix": "context before", "suffix": "context after"},
     {"text": "exact quote 2", "page": 12, "prefix": "context before", "suffix": "context after"}
   ]}
   ```
2. Run batch verification (extracts PDF text once, verifies all quotes):
   ```bash
   echo '<json>' | astra paper verify-quotes "<DOI>" [--version N]
   ```
3. Parse the JSON response. Check each result's `status`: `verified` or `not_found`.
4. For any `not_found` quote: re-read the relevant PDF section; correct the quote
   text, prefix, and suffix.
5. Repeat batch verification with corrected quotes (max 3 iterations).
6. If still failing after 3 attempts, drop those quotes and note which could not
   be verified.

## Output format

Produce this YAML structure (written into `astra.yaml`'s `prior_insights:` and
`decision_links:` for the in-context path; returned verbatim by a subagent for the
main agent to merge in):

```yaml
prior_insights:
  <insight_id>:
    id: <insight_id>
    claim: "<What we learned from this paper>"
    created_at: "<TIMESTAMP>"
    evidence:
      - id: ev1
        doi: "<DOI>"
        version: <version if arXiv, omit otherwise>
        quote:
          exact: "<VERIFIED exact quote from paper>"
          prefix: "<~20-100 chars BEFORE the quote>"
          suffix: "<~20-100 chars AFTER the quote>"
        location:
          page: <page number hint>
    scope: "<when this applies -- optional, include only if applicability is limited>"

decision_links:
  <decision_id>:
    <option_id>:
      - <insight_id>

verification_summary:
  total_quotes: <N>
  verified: <N>
  failed: <N>
  failed_details: "<description of any quotes that could not be verified, or 'none'>"
```

## Rules

- Use `lowercase_with_underscores` for insight IDs.
- Quotes must be EXACT — copy verbatim from the PDF.
- One claim per insight — do not combine multiple claims.
- Only extract insights relevant to the target decisions.
- Only include insights whose quotes passed verification.
- If no relevant insights are found, return `prior_insights: {}`.
- `prefix` and `suffix` are REQUIRED for every quote.
- For arXiv papers, always include the `version` field in evidence.

## Troubleshooting: verification failures

| Failure | Cause | Fix |
|---------|-------|-----|
| `Quote not found` | Paraphrased or introduced typos | Re-read the PDF page, copy the exact text, re-verify |
| `Paper not in cache` | Paper was not downloaded before validation | Run `astra paper add <doi>` |
| `Wrong page` | Page number is incorrect (quote exists elsewhere) | Check `found_pages` in JSON output, update page number |
| `prefix/suffix mismatch` | Context text does not match surrounding text | Re-read the area around the quote, copy exact surrounding text |
| Persistent `not_found` | OCR artifacts, ligatures, or Unicode differences | Try a shorter quote avoiding problem characters; increase prefix/suffix |

**Recovery**: re-read the failing page, copy the exact text, update prefix/suffix,
verify with `astra paper verify-quotes`, then run
`astra validate astra.yaml --verify-evidence`.
