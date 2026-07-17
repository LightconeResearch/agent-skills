#!/bin/bash
# PostToolUse(Write|Edit) hook: re-validate after writes to astra.yaml or a
# universe file, and push the result back to the agent as additionalContext.
#
# On failure the hook also runs `astra spec <term>` for the concept types named
# in the errors, so the correction reference arrives together with the error.
# That subcommand ships in a later astra-tools than the current pin, so its use
# degrades gracefully: if `astra spec` is absent, the appendix is simply omitted.
#
# astra is resolved project-venv-first (activate-venv.sh prepends the venv to
# PATH at SessionStart), falling back to an ephemeral, dual-pinned `uvx` run when
# there is no project install. Validation is stateless, so uvx is a safe fallback.

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

# Resolve an astra runner; if neither astra nor uv is present, say so with the
# one-line installer rather than failing silently.
if ! astra_resolve; then
    jq -n --arg ctx "ASTRA file saved ($filename) but not validated: no \`astra\` on PATH and \`uv\` is not installed. Install uv to enable validation: $ASTRA_UV_INSTALL" \
        '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
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
        '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
    exit 0
fi

msg=$(printf 'ASTRA validation FAILED for %s:\n%s' "$filename" "$result")

# Map the concept types named in the errors to `astra spec` terms. Read ONLY the
# structured field path of each error line — the `<path>:` prefix before the
# message — never the message body: a generic "Extra inputs are not permitted"
# would otherwise be misread as the `input` concept. Walk the path's dotted
# segments, fold plurals to the spec term, and keep the LAST recognised concept —
# the most specific one, i.e. the concept that actually failed. A nested
# `analysis.…decisions.2.options` error thus surfaces `option`, not the outer
# `analysis`; a path whose leaf is an unrecognised field (`…decisions.2.rationale`)
# falls back to its deepest recognised ancestor (`decision`).
terms=$(
    awk '
        BEGIN {
            split("input output decision option recipe insight evidence analysis universe", a, " ")
            for (i in a) concept[a[i]] = 1
            fold["inputs"]="input"; fold["outputs"]="output"; fold["decisions"]="decision"
            fold["options"]="option"; fold["prior_insights"]="insight"; fold["findings"]="insight"
            fold["analyses"]="analysis"; fold["universes"]="universe"
        }
        { idx = index($0, ": "); if (idx == 0) next
          path = substr($0, 1, idx - 1)
          sub(/^[[:space:]]*\[[^]]*\][[:space:]]*/, "", path)      # drop a leading [code] tag
          if (!match(path, /[a-z_][a-z0-9_]*(\.[a-z0-9_]+)*$/)) next   # trailing dotted path token
          n = split(substr(path, RSTART, RLENGTH), seg, ".")
          chosen = ""
          for (i = 1; i <= n; i++) { s = seg[i]; if (s in fold) s = fold[s]; if (s in concept) chosen = s }
          if (chosen != "") print chosen }' <<<"$result" \
      | awk '!seen[$0]++' | head -4
)

# Append `astra spec <term>` for each failing concept — but only if the installed
# astra actually has the subcommand (older releases do not; degrade to no appendix).
if [ -n "$terms" ] && "${ASTRA_CMD[@]}" spec --help &>/dev/null; then
    while read -r term; do
        [ -z "$term" ] && continue
        spec_out=$("${ASTRA_CMD[@]}" spec "$term" 2>/dev/null) || continue
        [ -n "$spec_out" ] && msg=$(printf '%s\n\n--- astra spec %s ---\n%s' "$msg" "$term" "$spec_out")
    done <<<"$terms"
fi

jq -n --arg ctx "$msg" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
exit 0
