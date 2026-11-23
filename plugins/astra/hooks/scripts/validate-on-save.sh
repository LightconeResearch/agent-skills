#!/bin/bash
# PostToolUse(Write|Edit|apply_patch) hook: when a save plausibly touched an
# ASTRA analysis (an astra.yaml, universes included — ASTRA 0.1 writes them
# in it), re-validate every analysis under the session directory and push the
# result back to the agent as additionalContext.
#
# Self-contained on purpose — no sourcing, no jq/sed/awk. The astra-tools
# version in the uvx invocation comes from the bundling plugin's `tools` pin
# in skills.config.json: canonical sources write the @x.y.z placeholder and
# `npm run build` substitutes the pin into the packaged copies.
#   - trigger: a bash substring match on the raw payload ("astra.yaml"
#     mentioned anywhere). It can over-trigger, which costs one harmless
#     validation run; the [ -f ] gate keeps non-ASTRA sessions silent.
#   - target: `astra validate` with no FILE, which validates every root
#     analysis under the session directory together with every analysis it
#     declares — so an edit to a declared analysis's own astra.yaml that
#     breaks the analysis reading it fails here too.
#   - report: astra's plain-text report, one line per broken rule with its
#     line and column. It is JSON-escaped below in pure bash and spliced into
#     the envelope. astra always prints that report on stdout; a toolchain
#     that never reached astra (uvx resolution, network) prints nothing
#     there, which is how the two are told apart.
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
#                astra validate ──exit 0──▶ inject "validation passed"
#                     │report, exit≠0     │no report
#                     ▼                   ▼
#                inject the report   inject "toolchain problem"

input=$(cat)

case "$input" in
    *astra.yaml*) ;;
    *) exit 0 ;;
esac

[ -f astra.yaml ] || exit 0

# If uv is not present, ask the USER to install it rather than failing
# silently. Never install uv from here.
if ! command -v uvx &>/dev/null; then
    printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"ASTRA file saved but not validated: `uv` is not installed. Ask the user if they would like to install it (https://docs.astral.sh/uv/getting-started/installation/) to enable validation.\\n"}}\n'
    exit 0
fi

# JSON-escape $1 into $escaped: backslashes and quotes first, then the
# whitespace a report carries, then any other control character (an ANSI
# escape, should one slip through NO_COLOR) is dropped rather than left to
# break the envelope. Written for bash 3.2 too (macOS's /bin/bash): unquoted
# assignments, and the control characters held in variables rather than
# written as $'...' inside a pattern — verified byte-identical on 3.2 and 5.3.
tab=$'\t' cr=$'\r' nl=$'\n' lo=$'\001' hi=$'\037'
json_escape() {
    local s=$1
    s=${s//\\/\\\\}
    s=${s//\"/\\\"}
    s=${s//$tab/\\t}
    s=${s//$cr/}
    s=${s//$nl/\\n}
    escaped=${s//[$lo-$hi]/}
}

report=$(NO_COLOR=1 TERM=dumb uvx astra-tools@0.3.0rc4 validate 2>/dev/null)
rc=$?

if [ "$rc" -eq 0 ]; then
    printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"ASTRA validation passed for every analysis under this directory\\n"}}\n'
elif [ -n "$report" ]; then
    json_escape "$report"
    printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"ASTRA validation FAILED (exit %s) — astra validate reports:\\n%s\\n"}}\n' \
        "$rc" "$escaped"
else
    # astra produced no report — uvx resolution, network, or a crash.
    printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"ASTRA file saved but not validated: the pinned astra toolchain failed to run (exit %s) — a toolchain problem, not a statement about the spec.\\n"}}\n' \
        "$rc"
fi
exit 0
