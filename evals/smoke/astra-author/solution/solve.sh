#!/bin/bash
set -euo pipefail
# Reference solution: the spec the verifier is calibrated against.
cp /solution/astra.yaml /root/line-fit/astra.yaml
cd /root/line-fit
astra validate
