"""Least-squares polynomial fit of y(x): results/clean.csv -> results/fit.json.

--model linear fits y = a + b x; --model quadratic adds a c x^2 term.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--clean", default="results/clean.csv")
parser.add_argument("--model", choices=["linear", "quadratic"], default="linear")
parser.add_argument("--out", default="results/fit.json")
args = parser.parse_args()

with open(args.clean) as fh:
    rows = list(csv.DictReader(fh))
x = np.array([float(r["x"]) for r in rows])
y = np.array([float(r["y"]) for r in rows])
degree = {"linear": 1, "quadratic": 2}[args.model]
coeffs = np.polyfit(x, y, degree)[::-1]
Path(args.out).parent.mkdir(parents=True, exist_ok=True)
Path(args.out).write_text(json.dumps({"model": args.model, "coefficients": coeffs.tolist()}, indent=2) + "\n")
print(f"{args.model} fit -> {args.out}")
