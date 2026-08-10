#!/bin/bash
# PostToolUse(Read) hook: when an agent reads an astra.yaml, drop a soft reminder
# to load the astra skill. The harness can't tell us whether the skill is already
# active, so the reminder is deliberately gentle and fires at most once per
# session (a per-session marker suppresses the repeats) — enough to catch an agent
# that wandered into an astra.yaml cold, without nagging one already oriented.
#
# No jq: the path and session id are pulled from the raw payload with sed.
# Content-embedded fields can't spoof the match (their quotes are escaped
# inside a JSON string). Detection is simply "astra.yaml appears in the file
# path" — universe files are not worth a special case here, since anyone deep
# enough to read one has read the spec. Exotic paths (embedded quotes or
# backslashes) simply don't match, which only costs this one-time reminder.
#
#   Read ──▶ file path contains astra.yaml? ──no──▶ exit silent
#              │yes
#              ▼
#         marker for this session_id exists? ──yes──▶ exit silent (already nudged)
#              │no
#              ▼
#         create marker, inject "load the astra skill" reminder

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/astra-pins.sh"

input=$(cat)

extract() {
    printf '%s' "$input" | sed -n 's/.*"'"$1"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1
}

file_path=$(extract file_path)
[ -z "$file_path" ] && file_path=$(extract filePath)

case "$file_path" in
    *astra.yaml*) ;;
    *) exit 0 ;;
esac

# Fire once per session.
session_id=$(extract session_id)
marker="${TMPDIR:-/tmp}/astra-activate-${session_id:-nosession}"
[ -e "$marker" ] && exit 0
: >"$marker" 2>/dev/null

printf '%s' "You just read an ASTRA file. If you will author or
edit the spec, load the astra skill if it is not already loaded." | astra_emit PostToolUse
exit 0
