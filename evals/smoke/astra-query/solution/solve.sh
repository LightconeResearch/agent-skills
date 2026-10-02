#!/bin/bash
set -euo pipefail
# Derive every answer with astra's own resolver and `astra universe check`
# (derive_expected.py is a copy of the verifier's).
python3 /solution/derive_expected.py /root/line-fit > /root/line-fit/answer.json
cat /root/line-fit/answer.json
