#!/usr/bin/env bash
# Build lightcone-eval-base (agent CLIs) and lightcone-smoke-stack (the stack
# under test) into the local Docker image store; every evals/smoke task image
# builds FROM lightcone-smoke-stack.
#
#   evals/bin/build-images.sh                          # stack at the skills.config.json pins
#   LIGHTCONE_REF=my-branch evals/bin/build-images.sh  # any ref stack.sh resolves
#   evals/bin/build-images.sh --set '*.platform=linux/amd64'   # extra args go to bake
#
# Harbor builds the task images with the active buildx builder, which must be
# a docker-driver one (`desktop-linux` on Docker Desktop, `default` on Linux):
# a docker-container builder cannot see the local lightcone-smoke-stack image.
# One stack at a time per Docker daemon: the task images build FROM whichever
# lightcone-smoke-stack was built last.
set -euo pipefail

BIN="$(cd "$(dirname "$0")" && pwd)"
set -a
eval "$("$BIN/stack.sh" | sed 's/=\(.*\)/="\1"/')"
set +a
echo "stack: $ASTRA_TOOLS | $LIGHTCONE_CLI | uvx pin $ASTRA_PIN" >&2
cd "$BIN/../images"
docker buildx bake -f docker-bake.hcl --load "$@"

active="$(docker buildx inspect | awk '/^Driver:/ {print $2; exit}')"
if [ "$active" != docker ]; then
  echo "warning: the active buildx builder uses the '$active' driver; Harbor's task" >&2
  echo "builds cannot FROM lightcone-smoke-stack through it (docker buildx use desktop-linux)." >&2
fi
