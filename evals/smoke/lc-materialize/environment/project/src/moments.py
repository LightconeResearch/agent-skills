"""Sum the input numbers raised to the chosen power; write JSON to --output."""

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--numbers", required=True)
parser.add_argument("--power", choices=["linear", "square"], required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()

values = [int(line) for line in Path(args.numbers).read_text().split()]
exponent = {"linear": 1, "square": 2}[args.power]
total = sum(v**exponent for v in values)
Path(args.output).write_text(json.dumps({"n": len(values), "power": exponent, "total": total}) + "\n")
