#!/bin/bash
# PostToolUse(Write|Edit|apply_patch) hook: when a save plausibly touched the
# ASTRA spec, re-validate ./astra.yaml and push the result back to the agent
# as additionalContext.
#
# There is deliberately no parsing here — no jq, no sed, no awk:
#   - trigger: a bash substring match on the raw payload ("astra.yaml"
#     mentioned anywhere). It can over-trigger, which costs one harmless
#     validation run; the [ -f ] gate keeps non-ASTRA sessions silent.
#   - target: always ./astra.yaml in the session directory (universe files
#     are not validated at hook level — the spec is what the agent authors).
#   - JSON: `astra validate --json` emits its report as ONE JSON-encoded
#     string, so the response is assembled by splicing that string into a
#     printf template; the only string surgery is stripping the outer quotes.
#
#   Write/Edit/apply_patch ──▶ payload mentions astra.yaml? ──no──▶ exit silent
#                     │yes
#                     ▼
#                ./astra.yaml exists? ──no──▶ exit silent
#                     │yes
#                     ▼
#                uvx present? ──no──▶ inject "saved but NOT validated; ask user to install uv"
#                     │yes
#                     ▼
#                astra validate astra.yaml --json ──pass──▶ inject "validation passed"
#                     │fail                       │not a JSON string
#                     ▼                           ▼
#                inject verbatim report      inject "toolchain problem"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/astra-pins.sh"

input=$(cat)

case "$input" in
    *astra.yaml*) ;;
    *) exit 0 ;;
esac

[ -f astra.yaml ] || exit 0

# If uv is not present, ask the USER to install it rather than failing
# silently. Never install uv from here.
if ! command -v uvx &>/dev/null; then
    printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"ASTRA file saved but not validated: `uv` is not installed. Ask the user if they would like to install it (%s) to enable validation.\\n"}}\n' \
        "$ASTRA_UV_INSTALL"
    exit 0
fi

report=$("${ASTRA_CMD[@]}" validate astra.yaml --json 2>/dev/null)
rc=$?

case "$report" in
    \"*\")
        body="${report#\"}"
        body="${body%\"}"
        if [ "$rc" -eq 0 ]; then
            printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"ASTRA validation passed for ./astra.yaml\\n"}}\n'
        else
            printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"ASTRA validation FAILED for ./astra.yaml:\\n%s"}}\n' \
                "$body"
        fi
        ;;
    *)
        # astra produced no JSON string — uvx resolution, network, or a crash.
        printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"ASTRA file saved but not validated: the pinned astra toolchain failed to run (exit %s) — a toolchain problem, not a statement about the spec.\\n"}}\n' \
            "$rc"
        ;;
esac
exit 0
