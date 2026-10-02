"""Write a one-line summary of the moments output to --output."""

import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--moments", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()

m = json.loads(Path(args.moments).read_text())
Path(args.output).write_text(f"sum of x^{m['power']} over {m['n']} numbers = {m['total']}\n")
