#!/bin/bash
# SessionStart hook (astra plugin): orient the agent in an ASTRA project.
#
# Everything here is dynamic — read from the environment at session start:
# where the spec lives, and the analysis's shape from `astra info`. The one
# static line is the skill pointer.
#
# Self-contained on purpose — no sourcing, no jq/sed/awk. The astra-tools
# version in the uvx invocation comes from the bundling plugin's `tools` pin
# in skills.config.json: canonical sources write the @x.y.z placeholder and
# `npm run build` substitutes the pin into the packaged copies. `astra info`
# prints a plain-text summary (or, for an analysis that breaks a rule, the
# validation report) on stdout; it is JSON-escaped in pure bash and spliced
# into the envelope. A toolchain that never reached astra prints nothing on
# stdout, which is how the two are told apart.
#
# Deliberately NOT here:
#   - execution-layer status -- this plugin is about the ASTRA spec.
#   - a separate `astra validate` -- `astra info` already shows an analysis
#     that breaks a rule as `astra validate` would, and validate-on-save
#     covers every later edit.
#   - skill listing -- the harness already advertises installed skills.
#
#   SessionStart ──▶ ./astra.yaml present? ──no──▶ exit silent
#                          │yes
#                          ▼
#                     written before ASTRA 0.1? ──yes──▶ add "convert it first"
#                          │
#                          ▼
#                     uvx present? ──no──▶ inject "install uv to enable astra"
#                          │yes
#                          ▼
#                     astra info ──exit 0──▶ inject spec path + summary
#                          │report, exit≠0     │no output
#                          ▼                   ▼
#                     inject the report   inject "toolchain problem"

cat >/dev/null # consume the payload; everything needed comes from the cwd
[ -f astra.yaml ] || exit 0

# JSON-escape $1 into $escaped. Written for bash 3.2 too (macOS's
# /bin/bash): unquoted assignments, control characters held in variables.
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

# An astra.yaml from before ASTRA 0.1 names its version `version:`; 0.1
# renamed it `spec_version:`. The pinned astra reads only 0.1, so such a
# spec fails every rule at once — say what that wall of errors means.
legacy=""
spec=$(<astra.yaml)
case "$nl$spec" in
    *"${nl}spec_version:"*) ;;
    *"${nl}version:"*)
        legacy="This astra.yaml predates ASTRA 0.1 (it has \`version:\`, not \`spec_version:\`), and the pinned astra reads only 0.1: convert it before anything else — the astra skill's references/upgrading-from-0.0.md maps every field.\\n" ;;
esac

if ! command -v uvx &>/dev/null; then
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"ASTRA project — spec at ./astra.yaml\\n%s`uv` is not installed, so the astra CLI is unavailable. Ask the user if they would like to install it (https://docs.astral.sh/uv/getting-started/installation/).\\n\\nActivate the astra skill when working with ASTRA analyses.\\n"}}\n' \
        "$legacy"
    exit 0
fi

summary=$(NO_COLOR=1 TERM=dumb uvx astra-tools@0.3.0rc4 info 2>/dev/null)
rc=$?

if [ "$rc" -eq 0 ]; then
    json_escape "$summary"
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"ASTRA project — spec at ./astra.yaml\\n%s\\n\\nActivate the astra skill when working with ASTRA analyses.\\n"}}\n' \
        "$escaped"
elif [ -n "$summary" ]; then
    json_escape "$summary"
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"ASTRA project — spec at ./astra.yaml\\n%sThe analysis does not validate, so `astra info` shows its report instead of a summary:\\n%s\\n\\nActivate the astra skill when working with ASTRA analyses.\\n"}}\n' \
        "$legacy" "$escaped"
else
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"ASTRA project — spec at ./astra.yaml\\n%sCould not run `astra info` (exit %s) — the pinned astra toolchain failed to run, which says nothing about the spec.\\n\\nActivate the astra skill when working with ASTRA analyses.\\n"}}\n' \
        "$legacy" "$rc"
fi
exit 0
