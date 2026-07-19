#!/bin/bash
# SessionStart hook (astra plugin): orient the agent in an ASTRA project.
#
# Everything here is dynamic — read from the environment at session start:
# where the spec lives, and the analysis's shape (`astra info` header:
# name, version, input/output/decision counts; plus universe and
# sub-analysis file counts). The one static line is the skill pointer.
#
# Deliberately NOT here:
#   - lc / lightcone-cli anything -- this plugin is about the ASTRA spec;
#     execution-layer status belongs to the lightcone plugin's own
#     SessionStart hook (lightcone-session-start.sh).
#   - astra validate -- validation is an opinion about the work, not
#     session state; it belongs to validate-on-save, which fires at the
#     moment an ASTRA file actually changes.
#   - skill listing -- the harness already advertises installed skills.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/astra-pins.sh"

input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd // empty')

[ -z "$cwd" ] && exit 0
cd "$cwd" 2>/dev/null || exit 0
[ -f "astra.yaml" ] || exit 0

summary="ASTRA project — spec at $cwd/astra.yaml"

# Shape of the analysis, straight from the spec: `astra info` opens with
# name, version, and "Inputs: N | Outputs: M | Decisions: K" before the
# detail tables; keep just that header.
if astra_resolve; then
    shape=$("${ASTRA_CMD[@]}" info 2>/dev/null | awk '/^Inputs:/ { print; exit } NF { print }')
    if [ -z "$shape" ] || [ "$(echo "$shape" | head -1)" = "Unknown" ]; then
        summary="$summary
Could not read the analysis shape — the spec is likely malformed. Run \`astra validate astra.yaml\` to see why."
    else
        summary="$summary
$shape"
    fi
fi

# Layout: sub-analysis specs and universe files, found on disk. Paths, not
# counts — the agent can go read a path. Capped so a many-universe project
# doesn't flood the primer.
list_capped() {  # list_capped <label> <path>... : "label: a, b, c (+N more)"
    local label="$1"; shift
    local cap=6 total=$# shown
    [ "$total" -eq 0 ] && return
    shown=$(printf '%s\n' "$@" | head -$cap | awk 'NR > 1 { printf ", " } { printf "%s", $0 } END { print "" }')
    [ "$total" -gt "$cap" ] && shown="$shown (+$((total - cap)) more)"
    echo "$label: $shown"
}
subs=$(find . -mindepth 2 -name astra.yaml -not -path "./universes/*" 2>/dev/null | sed 's|^\./||' | sort)
universes=$(find universes -maxdepth 1 -name "*.yaml" 2>/dev/null | sort)
layout=$( { [ -n "$subs" ] && list_capped "Sub-analyses" $subs; [ -n "$universes" ] && list_capped "Universes" $universes; } )
[ -n "$layout" ] && summary="$summary
$layout"

summary="$summary

Activate the astra skill when working with ASTRA analyses."

jq -n --arg ctx "$summary" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
exit 0
