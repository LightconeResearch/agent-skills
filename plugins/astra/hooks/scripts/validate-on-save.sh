#!/bin/bash
# PostToolUse(Write|Edit|apply_patch) hook: re-validate after writes to
# astra.yaml or a universe file, and push the result back to the agent as
# additionalContext.
#
# The hook surfaces astra validate's output verbatim — no parsing. Pointers to
# the relevant schema docs belong in astra-tools' own error messages (upstream).
#
# astra is resolved global-first (the astra on PATH, installed from the
# lightcone-cli wheel), falling back to an ephemeral, dual-pinned `uvx` run when
# there is no global install. Validation is stateless, so uvx is a safe fallback.
#
#   Write/Edit/apply_patch ──▶ ASTRA file touched? ──no──▶ exit silent
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

# Claude Code's Write/Edit payload carries a file_path string. Codex's
# apply_patch payload carries patch text in tool_input.command; take the paths
# from the patch's Add/Update/Move headers. The two are mutually exclusive.
file_paths=$(echo "$input" | jq -r '.tool_input.file_path // .tool_response.filePath // empty')
patch_text=$(echo "$input" | jq -r '.tool_input.command // empty')

[ -n "$patch_text" ] && file_paths=$(printf '%s\n' "$patch_text" | sed -nE \
    -e 's/^\*\*\* (Add|Update) File: (.+)$/\2/p' \
    -e 's/^\*\*\* Move to: (.+)$/\1/p')

# Resolve relative paths against the event cwd. The fallback keeps direct hook
# invocation useful.
cwd=$(echo "$input" | jq -r '.cwd // empty')
[ -z "$cwd" ] && cwd=$(pwd)

# Filter to astra.yaml at any depth and universe files (universes/*.yaml),
# while retaining absolute paths for validation and readable diagnostics.
# Skip paths that do not exist: a Move header names the pre-rename source too.
candidate_paths=""
while IFS= read -r file_path; do
    case "$file_path" in
        /*) ;;
        *) file_path="${cwd%/}/$file_path" ;;
    esac
    [ -f "$file_path" ] || continue

    filename=$(basename "$file_path")
    parent=$(basename "$(dirname "$file_path")")
    if [ "$filename" = "astra.yaml" ] || {
        [ "$parent" = "universes" ] && [[ "$filename" == *.yaml ]]
    }; then
        candidate_paths="${candidate_paths}${candidate_paths:+$'\n'}${file_path}"
    fi
done < <(printf '%s\n' "$file_paths" | awk 'NF && !seen[$0]++')

[ -z "$candidate_paths" ] && exit 0

# Resolve an astra runner; if neither astra nor uv is present, ask the USER to
# install uv rather than failing silently. Never install uv from here.
if ! astra_resolve; then
    jq -n --arg ctx "ASTRA file saved but not validated: \`uv\` is not installed. Ask the user if they'd like to install it ($ASTRA_UV_INSTALL) to enable validation." \
        '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: ($ctx + "\n")}}'
    exit 0
fi

messages=""
while IFS= read -r file_path; do
    filename=$(basename "$file_path")
    project_root=$(dirname "$file_path")
    [ "$filename" = "astra.yaml" ] || project_root=$(dirname "$project_root")

    result=$(cd "$project_root" && "${ASTRA_CMD[@]}" validate "$file_path" 2>&1)
    if [ $? -eq 0 ]; then
        message="ASTRA validation passed for $file_path"
    else
        message=$(printf 'ASTRA validation FAILED for %s:\n%s' "$file_path" "$result")
    fi
    messages="${messages}${messages:+$'\n'}${message}"
done < <(printf '%s\n' "$candidate_paths")

jq -n --arg ctx "$messages" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: ($ctx + "\n")}}'
exit 0
