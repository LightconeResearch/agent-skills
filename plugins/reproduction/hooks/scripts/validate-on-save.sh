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

# Claude Code's Write/Edit payload carries a file_path object. Codex's
# apply_patch payload carries patch text in tool_input.command; retain the raw
# string and tool_input.patch forms for older harnesses. Extract paths from the
# patch's Add/Update/Move headers. Keep both paths at this boundary; the
# validation policy below is shared across harnesses.
file_paths=$(echo "$input" | jq -r '
    if (.tool_input | type) == "object" then
        if (.tool_input.file_path | type) == "string" then
            .tool_input.file_path
        else
            empty
        end
    else
        empty
    end,
    if (.tool_response | type) == "object" then
        if (.tool_response.filePath | type) == "string" then
            .tool_response.filePath
        else
            empty
        end
    else
        empty
    end
')

patch_text=$(echo "$input" | jq -r '
    if (.tool_input | type) == "string" then
        .tool_input
    elif (.tool_input | type) == "object" then
        if (.tool_input.command | type) == "string" then
            .tool_input.command
        elif (.tool_input.patch | type) == "string" then
            .tool_input.patch
        else
            empty
        end
    else
        empty
    end
')

if [ -n "$patch_text" ]; then
    patch_paths=$(printf '%s\n' "$patch_text" | sed -nE \
        -e 's/^\*\*\* (Add|Update) File: (.+)$/\2/p' \
        -e 's/^\*\*\* Move to: (.+)$/\1/p')
    if [ -n "$patch_paths" ]; then
        file_paths="${file_paths}${file_paths:+$'\n'}${patch_paths}"
    fi
fi

[ -z "$file_paths" ] && exit 0

# Resolve relative paths against the event cwd. The fallback keeps direct hook
# invocation and older harness payloads useful.
cwd=$(echo "$input" | jq -r '
    if (.cwd | type) == "string" then .cwd else empty end
')
[ -z "$cwd" ] && cwd=$(pwd)

# Filter to astra.yaml at any depth and universe files (universes/*.yaml),
# while retaining absolute paths for validation and readable diagnostics.
candidate_paths=""
while IFS= read -r file_path; do
    [ -z "$file_path" ] && continue
    case "$file_path" in
        /*) ;;
        *) file_path="${cwd%/}/$file_path" ;;
    esac

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
    [ -z "$file_path" ] && continue
    filename=$(basename "$file_path")
    project_root=$(dirname "$file_path")
    if [ "$filename" != "astra.yaml" ]; then
        project_root=$(dirname "$project_root")
    fi

    if [ "$filename" = "astra.yaml" ]; then
        result=$(cd "$project_root" 2>/dev/null && "${ASTRA_CMD[@]}" validate astra.yaml 2>&1)
    else
        result=$(cd "$project_root" 2>/dev/null && "${ASTRA_CMD[@]}" validate "$file_path" 2>&1)
    fi
    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        message="ASTRA validation passed for $file_path"
    else
        message=$(printf 'ASTRA validation FAILED for %s:\n%s' "$file_path" "$result")
    fi
    if [ -n "$messages" ]; then
        messages="${messages}"$'\n'"${message}"
    else
        messages="$message"
    fi
done < <(printf '%s\n' "$candidate_paths" | awk 'NF && !seen[$0]++')

jq -n --arg ctx "$messages" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: ($ctx + "\n")}}'
exit 0
