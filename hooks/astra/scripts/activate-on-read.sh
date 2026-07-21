#!/bin/bash
# PostToolUse(Read) hook: when an agent reads an ASTRA file, drop a soft reminder
# to load the astra skill. The harness can't tell us whether the skill is already
# active, so the reminder is deliberately gentle and fires at most once per
# session (a per-session marker suppresses the repeats) — enough to catch an agent
# that wandered into an astra.yaml cold, without nagging one already oriented.

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')
[ -z "$file_path" ] && exit 0

filename=$(basename "$file_path")
parent=$(basename "$(dirname "$file_path")")

# Same detection as validate-on-save: astra.yaml at any depth, universes/*.yaml.
if [ "$filename" != "astra.yaml" ] && ! { [ "$parent" = "universes" ] && [[ "$filename" == *.yaml ]]; }; then
    exit 0
fi

# Fire once per session.
session_id=$(echo "$input" | jq -r '.session_id // "nosession"')
marker="${TMPDIR:-/tmp}/astra-activate-${session_id}"
[ -e "$marker" ] && exit 0
: >"$marker" 2>/dev/null

read -r -d '' ctx <<'EOF'
You just read an ASTRA file. If you'll author or
edit the spec, load the astra skill if it's not already loaded.
EOF

jq -n --arg ctx "$ctx" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: ($ctx + "\n")}}'
exit 0
