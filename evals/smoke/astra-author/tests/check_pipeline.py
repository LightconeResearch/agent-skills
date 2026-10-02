"""Check the declared pipeline through astra's own resolver; exit 1 on any miss."""
import os
import sys

from astra.helpers import create_universe_from_defaults, load_yaml
from astra.resolve import resolve_outputs

failures = []
try:
    spec = load_yaml("/root/line-fit/astra.yaml")
    outputs = {o.id: o for o in resolve_outputs(spec, create_universe_from_defaults(spec, "check"))}
except Exception as exc:  # unreadable spec: nothing to check
    print(f"FAIL could not resolve astra.yaml: {exc!r}")
    sys.exit(1)

print("resolved outputs:", {k: [(i.id, i.produced_by, i.source) for i in o.inputs] for k, o in outputs.items()})


def expect(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


for oid, dep, script, kind in [
    ("clean_data", "raw_data", "scripts/clean.py", "source"),
    ("fit_result", "clean_data", "scripts/fit.py", "produced_by"),
]:
    out = outputs.get(oid)
    expect(out is not None, f"output {oid} is declared")
    if out is None:
        continue
    match = [i for i in out.inputs if i.id == dep]
    expect(bool(match), f"{oid} declares input {dep}")
    if match and kind == "source":
        expect(os.path.normpath(match[0].source or "") == "data/raw.csv", f"{dep} resolves to source data/raw.csv (got {match[0].source!r})")
    if match and kind == "produced_by":
        expect(match[0].produced_by == dep, f"{dep} is produced by output {dep} (got {match[0].produced_by!r})")
    expect(script in (out.command or ""), f"{oid} recipe command runs {script} (got {out.command!r})")

sys.exit(1 if failures else 0)
