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

summary="ASTRA project — spec at ./astra.yaml"

# Shape of the analysis, straight from the spec: `astra info` opens with
# name, version, and "Inputs: N | Outputs: M | Decisions: K" before the
# detail tables; keep just that header.
if astra_resolve; then
    info_out=$("${ASTRA_CMD[@]}" info 2>/dev/null)
    info_rc=$?
    shape=$(echo "$info_out" | awk '/^Inputs:/ { print; exit } NF { print }')
    if [ "$info_rc" -ne 0 ] || [ -z "$shape" ]; then
        # astra itself failed (uvx resolution, network, version mismatch) —
        # an environment problem, not a statement about the spec.
        summary="$summary
Could not run \`astra info\` (exit $info_rc) — toolchain problem, not necessarily the spec."
    elif [ "$(echo "$shape" | head -1)" = "Unknown" ]; then
        summary="$summary
Could not read the analysis shape — the spec is likely malformed. Run \`astra validate astra.yaml\` to see why."
    else
        summary="$summary
$shape"
    fi
fi

# Layout: sub-analysis specs and universe files, found on disk — a count
# plus the directory holding them, so the primer stays one line no matter
# how many there are and the agent still knows where to look.
# TODO(upstream): this could move into `astra info` itself; drop this block
# once it does.
subs=$(find . -mindepth 2 -name astra.yaml -not -path "./universes/*" 2>/dev/null | sed 's|^\./||')
sub_count=$(echo "$subs" | grep -c . )
sub_dirs=$(echo "$subs" | sed 's|/[^/]*/astra.yaml$||' | sort -u | awk 'NR > 1 { printf ", " } { printf "./%s/", $0 } END { print "" }')
universe_count=$(find universes -maxdepth 1 -name "*.yaml" 2>/dev/null | grep -c .)
layout=""
[ "$sub_count" -gt 0 ] && layout="$sub_count sub-analys$( [ "$sub_count" -eq 1 ] && echo is || echo es) in $sub_dirs"
[ "$universe_count" -gt 0 ] && layout="${layout:+$layout, }$universe_count universe$( [ "$universe_count" -ne 1 ] && echo s) in ./universes/"
[ -n "$layout" ] && summary="$summary
Layout: $layout"

summary="$summary

Activate the astra skill when working with ASTRA analyses."

jq -n --arg ctx "$summary" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: ($ctx + "\n")}}'
exit 0
