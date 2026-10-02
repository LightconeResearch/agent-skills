#!/bin/bash
set -euo pipefail
cp /solution/astra.yaml /root/line-fit/astra.yaml
cp /solution/universes/*.yaml /root/line-fit/universes/
cd /root/line-fit
astra validate
