#!/bin/bash
# PostToolUse(Write|Edit) hook: re-validate after writes to astra.yaml or a
# universe file, and push the result back to the agent as additionalContext.
#
# The hook surfaces astra validate's output verbatim — no parsing. Pointers to
# the relevant schema docs belong in astra-tools' own error messages (upstream).
#
# astra is resolved global-first (the astra on PATH, installed from the
# lightcone-cli wheel), falling back to an ephemeral, dual-pinned `uvx` run when
# there is no global install. Validation is stateless, so uvx is a safe fallback.
#
#   Write/Edit ──▶ astra.yaml or universes/*.yaml? ──no──▶ exit silent
#                     │yes
#                     ▼
#                astra resolves? ──no──▶ inject "saved but NOT validated; ask user to install uv"
#                     │yes
#                     ▼
#                astra validate ──pass──▶ inject "validation passed"
#                     │fail
#                     ▼
#                inject verbatim validate output

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/astra-pins.sh"

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')
[ -z "$file_path" ] && exit 0

filename=$(basename "$file_path")
parent=$(basename "$(dirname "$file_path")")

# Filter to astra.yaml at any depth and universe files (universes/*.yaml).
if [ "$filename" = "astra.yaml" ]; then
    project_root=$(dirname "$file_path")
elif [ "$parent" = "universes" ] && [[ "$filename" == *.yaml ]]; then
    project_root=$(dirname "$(dirname "$file_path")")
else
    exit 0
fi

# Resolve an astra runner; if neither astra nor uv is present, ask the USER to
# install uv rather than failing silently. Never install uv from here.
if ! astra_resolve; then
    jq -n --arg ctx "ASTRA file saved ($filename) but not validated: \`uv\` is not installed. Ask the user if they'd like to install it ($ASTRA_UV_INSTALL) to enable validation." \
        '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: ($ctx + "\n")}}'
    exit 0
fi

cd "$project_root" 2>/dev/null || exit 0

if [ "$filename" = "astra.yaml" ]; then
    result=$("${ASTRA_CMD[@]}" validate astra.yaml 2>&1)
else
    result=$("${ASTRA_CMD[@]}" validate "$file_path" 2>&1)
fi
exit_code=$?

if [ $exit_code -eq 0 ]; then
    jq -n --arg ctx "ASTRA validation passed for $filename" \
        '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: ($ctx + "\n")}}'
    exit 0
fi

msg=$(printf 'ASTRA validation FAILED for %s:\n%s' "$filename" "$result")
jq -n --arg ctx "$msg" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: ($ctx + "\n")}}'
exit 0
