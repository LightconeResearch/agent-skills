---
document_version: '0.3'
verifier:
  name: smoke-astra-query-verifier
  default_strategy: script
  strategies:
    script: { type: script, command: ./test.sh }
  rubric:
    combine: min  # all-or-nothing
    dimensions:
      robust_clip_threshold: { source: astra.resolve.resolve_universe }
      baseline_clip_threshold: { source: astra.resolve.resolve_universe }
      clip_threshold_affected_outputs: { source: astra.resolve.resolve_outputs }
      baseline_outputs: { source: astra.resolve.resolve_outputs }
      sigma_clip_uncertainty_options: { source: astra universe check }
  outputs:
    reward_text: /logs/verifier/reward.txt
    reward_json: /logs/verifier/reward.json
---

Each key needs one ASTRA concept beyond reading a field: a conditional decision
(`clip_threshold` has `when: [outlier_cut.sigma_clip]`, so it is inactive in
`baseline` despite having a `default` — the trap is answering `five_sigma`), a
conditional output (`clip_report`), transitive dependency through output inputs,
and an `incompatible_with` constraint stated on the *other* decision's option
(`uncertainty.analytic` excludes `outlier_cut.sigma_clip`).

`tests/spec/` is a copy of the starting project's `astra.yaml` and `universes/`;
keep it in step with `environment/project/` when editing either.
