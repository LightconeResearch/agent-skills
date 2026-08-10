#!/bin/bash
# SessionStart hook (astra plugin): orient the agent in an ASTRA project.
#
# Everything here is dynamic — read from the environment at session start:
# where the spec lives, and the analysis's shape from `astra info --brief`
# (name, version, description, element counts, layout). The one static line
# is the skill pointer.
#
# There is deliberately no parsing here — no jq, no sed, no awk: the --json
# mode emits the header as ONE JSON-encoded string, spliced into a printf
# template; the only string surgery is stripping the outer quotes.
#
# Deliberately NOT here:
#   - execution-layer status -- this plugin is about the ASTRA spec.
#   - astra validate -- validation is an opinion about the work, not
#     session state; it belongs to validate-on-save, which fires at the
#     moment an ASTRA file actually changes.
#   - skill listing -- the harness already advertises installed skills.
#
#   SessionStart ──▶ ./astra.yaml present? ──no──▶ exit silent
#                          │yes
#                          ▼
#                     uvx present? ──no──▶ inject "install uv to enable astra"
#                          │yes
#                          ▼
#                     astra info --brief --json ──ok──▶ inject spec path + header
#                          │not a JSON string
#                          ▼
#                     inject "toolchain problem or malformed spec"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/astra-pins.sh"

cat >/dev/null # consume the payload; everything needed comes from the cwd
[ -f astra.yaml ] || exit 0

if ! command -v uvx &>/dev/null; then
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"ASTRA project — spec at ./astra.yaml\\n`uv` is not installed, so the astra CLI is unavailable. Ask the user if they would like to install it (%s).\\n\\nActivate the astra skill when working with ASTRA analyses.\\n"}}\n' \
        "$ASTRA_UV_INSTALL"
    exit 0
fi

header=$("${ASTRA_CMD[@]}" info --brief --json 2>/dev/null)
rc=$?

case "$rc:$header" in
    0:\"*\")
        body="${header#\"}"
        body="${body%\"}"
        printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"ASTRA project — spec at ./astra.yaml\\n%s\\nActivate the astra skill when working with ASTRA analyses.\\n"}}\n' \
            "$body"
        ;;
    *)
        printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"ASTRA project — spec at ./astra.yaml\\nCould not run `astra info` (exit %s) — a toolchain problem, or a malformed spec; run `astra validate astra.yaml` to see which.\\n\\nActivate the astra skill when working with ASTRA analyses.\\n"}}\n' \
            "$rc"
        ;;
esac
exit 0
