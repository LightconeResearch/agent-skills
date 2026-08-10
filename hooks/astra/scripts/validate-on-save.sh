#!/bin/bash
# PostToolUse(Write|Edit|apply_patch) hook: when a save plausibly touched an
# ASTRA file, validate the whole project and push the result back to the agent
# as additionalContext.
#
# No JSON parsing happens here — the raw payload is only string-matched for
# ASTRA file names. Anything smarter lives in the pinned astra CLI itself:
# `astra validate` with no argument validates every analysis and universe file
# under the session directory, which also catches cross-file breakage that a
# single-file check would miss. Two accepted consequences of that design: a
# save whose payload merely *mentions* astra.yaml costs one harmless
# validation run (silenced when no project exists here), and a save to an
# ASTRA file *outside* the session tree validates the session's project, not
# that file.
#
#   Write/Edit/apply_patch ──▶ payload mentions an ASTRA file? ──no──▶ exit silent
#                     │yes
#                     ▼
#                an astra.yaml under the session dir? ──no──▶ exit silent
#                     │yes
#                     ▼
#                uvx present? ──no──▶ inject "saved but NOT validated; ask user to install uv"
#                     │yes
#                     ▼
#                astra validate (whole project) ──pass──▶ inject "validation passed"
#                     │fail
#                     ▼
#                inject verbatim validate output

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/astra-pins.sh"

input=$(cat)

case "$input" in
    *astra.yaml* | *universes/*) ;;
    *) exit 0 ;;
esac

astra_cd_payload_cwd "$input"

# Not an ASTRA project (the payload mention was incidental) — stay silent.
[ -n "$(find . -name astra.yaml -print -quit 2>/dev/null)" ] || exit 0

# If uv is not present, ask the USER to install it rather than failing
# silently. Never install uv from here.
if ! command -v uvx &>/dev/null; then
    printf '%s' "ASTRA file saved but not validated: \`uv\` is not installed. Ask the user if they would like to install it ($ASTRA_UV_INSTALL) to enable validation." |
        astra_emit PostToolUse
    exit 0
fi

result=$(astra_run validate 2>&1)
if [ $? -eq 0 ]; then
    printf '%s' "ASTRA validation passed (all analysis and universe files)." | astra_emit PostToolUse
else
    printf 'ASTRA validation FAILED:\n%s' "$result" | astra_emit PostToolUse
fi
exit 0
