"""Score /root/line-fit/answer.json against the astra-derived expected values."""
import json
from pathlib import Path

LOGS = Path("/logs/verifier")
KEYS = [
    "robust_clip_threshold",
    "baseline_clip_threshold",
    "clip_threshold_affected_outputs",
    "baseline_outputs",
    "sigma_clip_uncertainty_options",
]

expected = json.loads(Path("/tests/expected.json").read_text())
drift = LOGS / "expected_drift.txt"
try:
    derived = json.loads((LOGS / "derived.json").read_text())
except Exception as exc:
    derived = None
    drift.write_text(drift.read_text() + f"\nDRIFT could not derive expected values: {exc!r}\n")
if derived is not None and derived != expected:
    drift.write_text(drift.read_text() + f"\nDRIFT astra now derives {derived}\n  but tests/expected.json says {expected}\n")
drifted = derived != expected
print(drift.read_text())

try:
    answer = json.loads(Path("/root/line-fit/answer.json").read_text())
    if not isinstance(answer, dict):
        raise ValueError("answer.json is not a JSON object")
except Exception as exc:
    print(f"FAIL could not read answer.json: {exc!r}")
    answer = {}


def same(key, got, want):
    if isinstance(want, list):
        return isinstance(got, list) and all(isinstance(g, str) for g in got) and sorted(set(got)) == sorted(want) and len(got) == len(set(got))
    return got == want and (want is not None or (key in answer and got is None))


dims = {}
for key in KEYS:
    got = answer.get(key, "<missing>")
    ok = (not drifted) and same(key, got, expected[key])
    dims[key] = int(ok)
    line = f"{'ok  ' if ok else 'FAIL'} {key}: got {json.dumps(got)}, expected {json.dumps(expected[key])}"
    (LOGS / f"{key}.txt").write_text(line + "\n")
    print(line)

reward = float(min(dims.values()))
(LOGS / "reward.json").write_text(json.dumps({"reward": reward, **dims}) + "\n")
(LOGS / "reward.txt").write_text(f"{reward:.2f}\n")
print(json.dumps({"reward": reward, **dims}))
