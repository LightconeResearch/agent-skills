#!/bin/bash
# Reference solution (runs as root): launch the local cluster, materialize the
# one target, release the cluster.
set -euo pipefail
cd /root/toy-moments
lc compute launch --wait --time 10m
lc materialize local baseline/summary
lc compute down local
