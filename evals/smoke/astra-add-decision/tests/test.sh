#!/bin/bash
set +e
# reward = all-or-nothing: min(spec_valid, decision_declared, universe_resolves); each 0/1, all reported.
#   spec_valid         `astra validate` (spec + every universe) exits 0
#   decision_declared  fit_model has options {linear, quadratic}, default linear
#                      (astra.helpers.get_decisions)
#   universe_resolves  `astra universe check universes/quadratic.yaml` exits 0, and
#                      astra.resolve settles fit_model=quadratic there, with
#                      fit_result's recipe parameterized by {decisions.fit_model}
mkdir -p /logs/verifier
cd /root/line-fit

astra validate > /logs/verifier/spec_valid.txt 2>&1
rc=$?
echo "exit code: $rc" >> /logs/verifier/spec_valid.txt
cat /logs/verifier/spec_valid.txt
[ "$rc" -eq 0 ] && spec_valid=1 || spec_valid=0

python3 /tests/check.py decision_declared > /logs/verifier/decision_declared.txt 2>&1
[ $? -eq 0 ] && decision_declared=1 || decision_declared=0
cat /logs/verifier/decision_declared.txt

{
  if [ -f universes/quadratic.yaml ]; then
    astra universe check universes/quadratic.yaml; c=$?
    echo "astra universe check exit code: $c"
  else
    echo "FAIL no universes/quadratic.yaml"; c=1
  fi
  python3 /tests/check.py universe_resolves; p=$?
  [ "$c" -eq 0 ] && [ "$p" -eq 0 ]
} > /logs/verifier/universe_resolves.txt 2>&1
[ $? -eq 0 ] && universe_resolves=1 || universe_resolves=0
cat /logs/verifier/universe_resolves.txt

python3 - "$spec_valid" "$decision_declared" "$universe_resolves" <<'PY'
import json, sys
dims = dict(zip(["spec_valid", "decision_declared", "universe_resolves"], map(int, sys.argv[1:])))
reward = float(min(dims.values()))
json.dump({"reward": reward, **dims}, open("/logs/verifier/reward.json", "w"))
open("/logs/verifier/reward.txt", "w").write(f"{reward:.2f}\n")
PY
cat /logs/verifier/reward.json; echo
exit 0
