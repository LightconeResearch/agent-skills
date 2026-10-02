#!/bin/bash
# Reference solution (runs as root): give summary a format and a recipe,
# commit the spec (lc refuses to run from a dirty tree), then launch the local
# cluster, materialize the one target and release the cluster.
set -euo pipefail
cd /root/toy-moments
cp /solution/astra.yaml astra.yaml
astra validate
git add astra.yaml && git commit -qm "Wire the summary recipe"
lc compute launch --wait --time 10m
lc materialize local baseline/summary
lc compute down local
