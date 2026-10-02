"""Drop rows with a missing or sentinel (-999) y value: data/raw.csv -> results/clean.csv."""
import csv
import sys
from pathlib import Path

src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw.csv")
dst = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("results/clean.csv")
dst.parent.mkdir(parents=True, exist_ok=True)
with src.open() as fin, dst.open("w", newline="") as fout:
    rows = [r for r in csv.DictReader(fin) if r["y"] not in ("", "-999")]
    writer = csv.DictWriter(fout, fieldnames=["x", "y"])
    writer.writeheader()
    writer.writerows(rows)
print(f"kept {len(rows)} rows -> {dst}")
