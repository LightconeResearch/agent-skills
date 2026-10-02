`/root/line-fit` is an analysis described in ASTRA: `astra.yaml` plus the universes in `universes/`. The `astra` CLI is installed.

Answer these questions about the analysis as it is declared, and write the answers to `/root/line-fit/answer.json` as one JSON object with exactly these keys:

- `robust_clip_threshold` (string): the option id that universe `robust` uses for decision `clip_threshold`.
- `baseline_clip_threshold` (string or `null`): the option id that universe `baseline` uses for decision `clip_threshold`, or `null` if that decision is not active in `baseline`.
- `clip_threshold_affected_outputs` (list of output ids): every output whose content can change when the option chosen for `clip_threshold` changes — outputs parameterized by it directly, plus outputs downstream of those through their inputs — counting any universe in which the decision is active.
- `baseline_outputs` (list of output ids): every output that universe `baseline` produces.
- `sigma_clip_uncertainty_options` (list of option ids): the options of decision `uncertainty` that a valid universe can select together with `outlier_cut: sigma_clip`.

List order does not matter. Do not modify `astra.yaml` or the universe files.
