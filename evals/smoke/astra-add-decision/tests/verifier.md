---
document_version: '0.3'
verifier:
  name: smoke-astra-add-decision-verifier
  default_strategy: script
  strategies:
    script: { type: script, command: ./test.sh }
  rubric:
    combine: min  # all-or-nothing
    dimensions:
      spec_valid: { weight: 0.333, source: astra validate }
      decision_declared: { weight: 0.333, source: astra.helpers.get_decisions }
      universe_resolves: { weight: 0.333, source: astra universe check + astra.resolve }
  outputs:
    reward_text: /logs/verifier/reward.txt
    reward_json: /logs/verifier/reward.json
---

The starting project already validates with an empty `baseline` universe, so
adding `fit_model` without updating `baseline` makes `spec_valid` fail
(MISSING_DECISION): the guide's "a new decision touches every universe" rule.
`universe_resolves` asks the CLI whether the new universe is legal and astra's
resolver whether it actually reaches the fit recipe.
