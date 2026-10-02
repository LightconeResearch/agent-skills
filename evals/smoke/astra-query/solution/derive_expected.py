"""Derive the answers to the astra-query questions from a spec, with astra's own tools.

Usage: python3 derive_expected.py <project dir>   (prints the answer JSON)

Every value comes from astra-tools: universe resolution and output resolution
from astra.resolve, legality of option combinations from `astra universe check`.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from astra.helpers import create_universe_from_defaults, get_decisions, load_yaml
from astra.resolve import resolve_outputs, resolve_universe

root = Path(sys.argv[1])
spec = load_yaml(root / "astra.yaml")
universes = {p.stem: load_yaml(p) for p in sorted((root / "universes").glob("*.yaml"))}

# Q1, Q2: the option a universe settles for clip_threshold (None when inactive).
robust = resolve_universe(spec, universes["robust"])
baseline = resolve_universe(spec, universes["baseline"])

# Q3: outputs whose content can change with clip_threshold — declared directly,
# or downstream of one that does — in any universe where it is active.
affected = set()
for universe in universes.values():
    outputs = resolve_outputs(spec, universe)
    hit = {o.id for o in outputs if "clip_threshold" in o.decisions}
    changed = True
    while changed:
        new = {o.id for o in outputs if any(i.produced_by in hit for i in o.inputs)} - hit
        hit |= new
        changed = bool(new)
    affected |= hit

# Q4: the outputs universe baseline produces.
baseline_outputs = sorted(o.id for o in resolve_outputs(spec, universes["baseline"]))

# Q5: uncertainty options a universe may select together with outlier_cut=sigma_clip.
allowed = []
with tempfile.TemporaryDirectory() as tmp:
    for option in get_decisions(spec)["uncertainty"]["options"]:
        candidate = create_universe_from_defaults(spec, "probe")
        candidate["decisions"].update(
            outlier_cut="sigma_clip",
            clip_threshold=get_decisions(spec)["clip_threshold"]["default"],
            uncertainty=option,
        )
        path = Path(tmp) / "probe.yaml"
        path.write_text(yaml.safe_dump(candidate))
        check = subprocess.run(
            ["astra", "universe", "check", str(path), "--analysis", str(root / "astra.yaml")],
            capture_output=True, text=True,
        )
        if check.returncode == 0:
            allowed.append(option)

print(json.dumps({
    "robust_clip_threshold": robust.get("clip_threshold"),
    "baseline_clip_threshold": baseline.get("clip_threshold"),
    "clip_threshold_affected_outputs": sorted(affected),
    "baseline_outputs": baseline_outputs,
    "sigma_clip_uncertainty_options": sorted(allowed),
}, indent=2))
