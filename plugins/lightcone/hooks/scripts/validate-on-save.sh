#!/bin/bash
# PostToolUse(Write|Edit) hook: re-validate after writes to astra.yaml or a
# universe file, push errors back to the agent as additionalContext.
#
# astra is resolved project-venv-first (PATH is prepended at SessionStart by
# activate-venv.sh), falling back to an ephemeral `uvx --from astra-tools astra`
# run when there is no project install. Validation is stateless, so uvx is a
# safe fallback; `lc` execution is project-bound and never runs this way.

input=$(cat)
file_path=$(echo "$input" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')
[ -z "$file_path" ] && exit 0

filename=$(basename "$file_path")
parent=$(basename "$(dirname "$file_path")")

# Filter to astra.yaml at any depth and universe files (universes/*.yaml)
if [ "$filename" = "astra.yaml" ]; then
    project_root=$(dirname "$file_path")
elif [ "$parent" = "universes" ] && [[ "$filename" == *.yaml ]]; then
    project_root=$(dirname "$(dirname "$file_path")")
else
    exit 0
fi

# Resolve an astra runner: project CLI on PATH first, else no-install uvx.
if command -v astra &>/dev/null; then
    astra_cmd=(astra)
elif command -v uvx &>/dev/null; then
    astra_cmd=(uvx --from astra-tools astra)
else
    exit 0
fi

cd "$project_root" 2>/dev/null || exit 0

if [ "$filename" = "astra.yaml" ]; then
    result=$("${astra_cmd[@]}" validate astra.yaml 2>&1)
else
    result=$("${astra_cmd[@]}" validate "$file_path" 2>&1)
fi
exit_code=$?

if [ $exit_code -eq 0 ]; then
    msg="ASTRA validation passed for $filename"
else
    msg=$(printf 'ASTRA validation FAILED for %s:\n%s' "$filename" "$result")
fi

jq -n --arg ctx "$msg" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
exit 0
