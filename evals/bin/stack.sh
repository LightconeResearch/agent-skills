#!/usr/bin/env bash
# Resolve the stack under test into the build args of lightcone-smoke-stack,
# printed as KEY=VALUE lines (source them, or append them to $GITHUB_ENV).
#
#   evals/bin/stack.sh                                   # the plugin pins in skills.config.json
#   ASTRA_REF=main LIGHTCONE_REF=main evals/bin/stack.sh # the "latest" leg
#   LIGHTCONE_REF=<sha> evals/bin/stack.sh               # a lightcone-cli PR
#
# An empty ref means the pinned release from PyPI. A ref is resolved to a commit
# sha (a 40-hex sha is taken as is), so a moving branch never hits a stale build
# cache. ASTRA_PIN is always the plugin's pin: it is what the skills and hooks
# run through uvx, whatever astra-tools the image installs as `astra`.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ASTRA_REPO=https://github.com/LightconeResearch/astra-tools.git
LIGHTCONE_REPO=https://github.com/LightconeResearch/lightcone-cli.git

pin() {  # the lightcone plugin's effective pin for a tool (own entries over its dependencies')
  python3 - "$ROOT/skills.config.json" "$1" <<'PY'
import json, sys
plugins = {p["name"]: p for p in json.load(open(sys.argv[1]))["plugins"]}
def pins(name):
    p = plugins[name]
    out = {}
    for dep in p.get("dependencies", []):
        out.update(pins(dep))
    out.update({k: v for k, v in p.get("tools", {}).items() if not k.startswith("$")})
    return out
print(pins("lightcone")[sys.argv[2]])
PY
}

sha() {  # sha <repo> <ref>
  if [[ "$2" =~ ^[0-9a-f]{40}$ ]]; then echo "$2"; return; fi
  local out
  local refs out
  refs="$(git ls-remote "$1")"
  for name in "refs/heads/$2" "refs/tags/$2^{}" "refs/tags/$2"; do  # a peeled tag names its commit
    out="$(awk -v n="$name" '$2 == n {print $1; exit}' <<<"$refs")"
    [ -n "$out" ] && break
  done
  [ -n "$out" ] || { echo "stack.sh: no ref '$2' in $1" >&2; exit 1; }
  echo "$out"
}

astra_pin="$(pin astra-tools)"
lightcone_pin="$(pin lightcone-cli)"

if [ -n "${ASTRA_REF:-}" ]; then
  astra="astra-tools @ git+$ASTRA_REPO@$(sha "$ASTRA_REPO" "$ASTRA_REF")"
else
  astra="astra-tools==$astra_pin"
fi
if [ -n "${LIGHTCONE_REF:-}" ]; then
  lightcone="lightcone-cli @ git+$LIGHTCONE_REPO@$(sha "$LIGHTCONE_REPO" "$LIGHTCONE_REF")"
else
  lightcone="lightcone-cli==$lightcone_pin"
fi

echo "ASTRA_TOOLS=$astra"
echo "ASTRA_PIN=$astra_pin"
echo "LIGHTCONE_CLI=$lightcone"
