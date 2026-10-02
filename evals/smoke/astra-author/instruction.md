The project in `/root/line-fit` is a small two-step analysis:

1. `scripts/clean.py` reads `data/raw.csv` and drops rows whose `y` is missing or `-999`, writing `results/clean.csv` (usage: `python scripts/clean.py <raw.csv> <clean.csv>`).
2. `scripts/fit.py` fits a polynomial to the cleaned table and writes `results/fit.json` (usage: `python scripts/fit.py --clean <clean.csv> --out <fit.json>`).

Describe this analysis in ASTRA. The `astra` CLI is installed. Write `/root/line-fit/astra.yaml` declaring:

- a data input with id `raw_data` whose source is `data/raw.csv`;
- an output with id `clean_data` that depends on `raw_data`, with a recipe command that runs `scripts/clean.py`;
- an output with id `fit_result` that depends on `clean_data`, with a recipe command that runs `scripts/fit.py`.

`astra validate`, run in `/root/line-fit`, must pass. You do not need to run the scripts.
