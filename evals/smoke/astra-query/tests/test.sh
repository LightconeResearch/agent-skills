#!/bin/bash
set +e
# One 0/1 dimension per answer.json key; reward = all-or-nothing min of them.
# Expected values are re-derived here from the pristine spec in /tests/spec with
# astra's resolver and `astra universe check` (derive_expected.py) and must equal
# /tests/expected.json; a mismatch means astra's semantics drifted under the
# task, and scores 0 with a DRIFT line in expected_drift.txt.
mkdir -p /logs/verifier
python3 /tests/derive_expected.py /tests/spec > /logs/verifier/derived.json 2> /logs/verifier/expected_drift.txt
python3 /tests/check_answers.py
exit 0
