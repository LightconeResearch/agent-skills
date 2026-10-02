`/root/toy-moments` is a Lightcone project: an analysis declared in `astra.yaml` and executed with the `lc` CLI, which is installed.

The output `moments` is already wired up. The output `summary` is declared in `astra.yaml` but has no recipe yet, so `lc` cannot make it. The script `src/report.py` produces it (read its arguments): it takes the `moments` output's file and writes a one-line text summary.

Wire `summary` up in `astra.yaml` so that `lc` writes it as a text file at `results/baseline/summary.txt` (format `txt`), running `src/report.py`. Then materialize the output `summary` for the universe `baseline` with `lc`, so that `lc` itself produces that file and records it as current.

Do not edit `src/` or the universe file.
