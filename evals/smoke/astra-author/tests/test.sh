#!/bin/bash
set +e
# reward = all-or-nothing: min(spec_valid, declares_pipeline); each 0/1, all reported.
#   spec_valid         `astra validate` (whole project) exits 0 in /root/line-fit
#   declares_pipeline  astra's own resolver (astra.resolve.resolve_outputs on the
#                      default universe) sees raw_data -> clean_data -> fit_result,
#                      each output with a recipe command running its script
mkdir -p /logs/verifier
cd /root/line-fit

if [ -f astra.yaml ]; then
  astra validate > /logs/verifier/spec_valid.txt 2>&1
  rc=$?
else
  echo "no /root/line-fit/astra.yaml" > /logs/verifier/spec_valid.txt; rc=1
fi
echo "exit code: $rc" >> /logs/verifier/spec_valid.txt
cat /logs/verifier/spec_valid.txt
[ "$rc" -eq 0 ] && spec_valid=1 || spec_valid=0

python3 /tests/check_pipeline.py > /logs/verifier/declares_pipeline.txt 2>&1
[ $? -eq 0 ] && declares_pipeline=1 || declares_pipeline=0
cat /logs/verifier/declares_pipeline.txt

python3 - "$spec_valid" "$declares_pipeline" <<'PY'
import json, sys
dims = {"spec_valid": int(sys.argv[1]), "declares_pipeline": int(sys.argv[2])}
reward = float(min(dims.values()))
json.dump({"reward": reward, **dims}, open("/logs/verifier/reward.json", "w"))
open("/logs/verifier/reward.txt", "w").write(f"{reward:.2f}\n")
PY
cat /logs/verifier/reward.json; echo
exit 0
