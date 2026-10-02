`/root/line-fit` is an analysis described in ASTRA (`astra.yaml`, plus one universe in `universes/baseline.yaml`). The `astra` CLI is installed.

The fit step hides a real methodological choice: `scripts/fit.py` takes `--model linear` (y = a + b x, the script's default) or `--model quadratic` (adds a c x² term). Record it in the spec:

1. Add a decision with id `fit_model` and exactly two options, `linear` and `quadratic`, with `linear` as the default.
2. Make the `fit_result` output depend on `fit_model` and pass it to `scripts/fit.py`'s `--model` flag in its recipe.
3. Add a universe with id `quadratic` in `universes/quadratic.yaml` that selects `quadratic` for `fit_model`.

The existing `baseline` universe must keep validating, and `astra validate`, run in `/root/line-fit`, must pass for the whole project. You do not need to run the scripts.
