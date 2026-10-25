#!/bin/bash
# PostToolUse(Write|Edit|apply_patch) hook: when a save plausibly touched the
# ASTRA project (astra.yaml or a universe file), re-validate the whole project
# and push the result back to the agent as additionalContext.
#
# Self-contained on purpose — no sourcing, no jq/sed/awk. The astra-tools
# version in the uvx invocation comes from the bundling plugin's `tools` pin
# in skills.config.json: canonical sources write the @x.y.z placeholder and
# `npm run build` substitutes the pin into the packaged copies.
#   - trigger: a bash substring match on the raw payload ("astra.yaml" or
#     "universe" mentioned anywhere). It can over-trigger, which costs one
#     harmless validation run; the [ -f ] gate keeps non-ASTRA sessions silent.
#   - target: the whole project rooted at the session directory. `astra
#     validate` with no FILE checks astra.yaml AND every universe file, so a
#     spec edit that strands a universe reference (e.g. a deleted decision a
#     universe still selects) fails here instead of surviving until a reader
#     opens the project. Validating astra.yaml alone missed exactly that.
#   - JSON: `astra validate --json` emits its report as ONE JSON-encoded,
#     ANSI-free string, so the response is assembled by splicing that string
#     into a printf template; the only string surgery is stripping the outer
#     quotes.
#
#   Write/Edit/apply_patch ──▶ payload mentions astra.yaml|universe? ──no──▶ exit silent
#                     │yes
#                     ▼
#                ./astra.yaml exists? ──no──▶ exit silent
#                     │yes
#                     ▼
#                uvx present? ──no──▶ inject "saved but NOT validated; ask user to install uv"
#                     │yes
#                     ▼
#                astra validate --json ──pass──▶ inject "validation passed"
#                     │fail            │not a JSON string
#                     ▼                ▼
#                inject verbatim report      inject "toolchain problem"

input=$(cat)

case "$input" in
    *astra.yaml*|*universe*) ;;
    *) exit 0 ;;
esac

[ -f astra.yaml ] || exit 0

# If uv is not present, ask the USER to install it rather than failing
# silently. Never install uv from here.
if ! command -v uvx &>/dev/null; then
    printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"ASTRA file saved but not validated: `uv` is not installed. Ask the user if they would like to install it (https://docs.astral.sh/uv/getting-started/installation/) to enable validation.\\n"}}\n'
    exit 0
fi

report=$(uvx astra-tools@x.y.z validate --json 2>/dev/null)
rc=$?

case "$report" in
    \"*\")
        body="${report#\"}"
        body="${body%\"}"
        if [ "$rc" -eq 0 ]; then
            printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"ASTRA validation passed for the project (astra.yaml + universes)\\n"}}\n'
        else
            printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"ASTRA validation FAILED for the project (astra.yaml + universes):\\n%s"}}\n' \
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
