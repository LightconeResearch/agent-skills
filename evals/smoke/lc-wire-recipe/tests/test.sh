#!/bin/bash
set +e
# reward = all-or-nothing: min of five 0/1 dimensions, all reported.
#   spec_valid     `astra validate` exits 0
#   output_value   results/baseline/summary.txt reads "sum of x^2 over 10 numbers = 385"
#   status_current `lc status --json` reports baseline/summary as "current"
#   check_passes   `lc materialize --check --json baseline/summary` exits 0 with ok=true
#   manifest       results/baseline/.summary.manifest.json names summary/baseline and its
#                  data_version equals the sha256 of summary.txt (lc wrote the run record)
#                  and its rendered recipe runs src/report.py
# A summary.txt written by hand fails status_current/check_passes/manifest.
mkdir -p /logs/verifier
cd /root/toy-moments
OUT=results/baseline/summary.txt
MAN=results/baseline/.summary.manifest.json

dim() { # $1 name, rest: the check to run; logs it and sets $1 to 1 when it exits 0
  local name=$1; shift
  "$@" > "/logs/verifier/$name.txt" 2>&1
  local rc=$?
  echo "exit code: $rc" >> "/logs/verifier/$name.txt"
  echo "== $name"; cat "/logs/verifier/$name.txt"
  [ "$rc" -eq 0 ] && eval "$name=1" || eval "$name=0"
}

check_output() {
  [ -f "$OUT" ] || { echo "missing $OUT"; return 1; }
  printf 'content: %s\n' "$(cat "$OUT")"
  [ "$(cat "$OUT")" = "sum of x^2 over 10 numbers = 385" ]
}
check_status() {
  lc status --json > /tmp/status.json || return 1
  cat /tmp/status.json
  python3 -c '
import json, sys
outs = {o["output"]: o for o in json.load(open("/tmp/status.json"))["outputs"]}
s = outs.get("baseline/summary", {}).get("status")
print("baseline/summary status:", s)
sys.exit(0 if s == "current" else 1)'
}
check_check() {
  lc materialize --check --json baseline/summary > /tmp/check.json
  local rc=$?
  cat /tmp/check.json
  [ "$rc" -eq 0 ] && python3 -c 'import json,sys; sys.exit(0 if json.load(open("/tmp/check.json")).get("ok") is True else 1)'
}
check_manifest() {
  [ -f "$MAN" ] || { echo "missing $MAN"; return 1; }
  cat "$MAN"
  python3 - "$MAN" "$OUT" <<'PY'
import hashlib, json, sys
m = json.load(open(sys.argv[1]))
digest = "sha256:" + hashlib.sha256(open(sys.argv[2], "rb").read()).hexdigest()
ok = (m.get("output_id") == "summary" and m.get("universe_id") == "baseline"
      and m.get("data_version") == digest and "src/report.py" in m.get("recipe", ""))
print("manifest matches output:", ok)
sys.exit(0 if ok else 1)
PY
}

dim spec_valid astra validate
dim output_value check_output
dim status_current check_status
dim check_passes check_check
dim manifest check_manifest

python3 - "$spec_valid" "$output_value" "$status_current" "$check_passes" "$manifest" <<'PY'
import json, sys
names = ["spec_valid", "output_value", "status_current", "check_passes", "manifest"]
dims = {n: int(v) for n, v in zip(names, sys.argv[1:])}
reward = float(min(dims.values()))
json.dump({"reward": reward, **dims}, open("/logs/verifier/reward.json", "w"))
open("/logs/verifier/reward.txt", "w").write(f"{reward:.2f}\n")
PY
cat /logs/verifier/reward.json; echo
exit 0
