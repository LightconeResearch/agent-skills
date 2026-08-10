#!/bin/bash
# PostToolUse(Read) hook: when an agent reads an ASTRA file, drop a soft reminder
# to load the astra skill. The harness can't tell us whether the skill is already
# active, so the reminder is deliberately gentle and fires at most once per
# session (a per-session marker suppresses the repeats) — enough to catch an agent
# that wandered into an astra.yaml cold, without nagging one already oriented.
#
# No jq: the path and session id are pulled from the raw payload with sed.
# Exotic paths (embedded quotes or backslashes) simply don't match, which only
# costs this one-time reminder.
#
#   Read ──▶ ASTRA file? ──no──▶ exit silent
#              │yes
#              ▼
#         marker for this session_id exists? ──yes──▶ exit silent (already nudged)
#              │no
#              ▼
#         create marker, inject "load the astra skill" reminder

input=$(cat)

case "$input" in
    *astra.yaml* | *universes/*) ;;
    *) exit 0 ;;
esac

extract() {
    printf '%s' "$input" | sed -n 's/.*"'"$1"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
}

file_path=$(extract file_path)
[ -z "$file_path" ] && file_path=$(extract filePath)
[ -z "$file_path" ] && exit 0

filename=$(basename "$file_path")
parent=$(basename "$(dirname "$file_path")")

# Same detection as validate-on-save: astra.yaml at any depth, universes/*.yaml.
if [ "$filename" != "astra.yaml" ] && ! { [ "$parent" = "universes" ] && [[ "$filename" == *.yaml ]]; }; then
    exit 0
fi

# Fire once per session.
session_id=$(extract session_id)
marker="${TMPDIR:-/tmp}/astra-activate-${session_id:-nosession}"
[ -e "$marker" ] && exit 0
: >"$marker" 2>/dev/null

printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"You just read an ASTRA file. If you will author or\nedit the spec, load the astra skill if it is not already loaded.\n"}}'
exit 0
