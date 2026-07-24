#!/bin/bash
# SessionStart hook (lightcone plugin): surface execution-layer status.
#
# The bundled astra plugin's own SessionStart hook (astra-session-start.sh)
# already orients the agent in the spec — project location, analysis shape,
# skill pointer. This hook adds only what the lc toolchain knows:
# materialization state from `lc status`.
#
# Deliberately NOT here:
#   - CLI cheat-sheet -- the lightcone cli skill carries the lc surface;
#     teaching commands is skill territory, not hook territory.
#   - skill listing -- the harness already advertises installed skills.
#   - astra validate -- validation belongs to validate-on-save, which
#     fires when an ASTRA file actually changes.
#
#   SessionStart ──▶ cwd + ./.lightcone/ present? ──no──▶ exit silent
#                          │yes
#                          ▼
#                     `lc` on PATH? ──no──▶ exit silent (toolchain missing)
#                          │yes
#                          ▼
#                     `lc status --json` ──▶ tally ok/stale/missing/alias
#                          │
#                          ▼
#                     stale+missing > 0? ──yes──▶ append "ACTION REQUIRED: lc run"
#                          │no
#                          ▼
#                     lc version outside plugin's pinned range? ──yes──▶ append warning
#                          │
#                          ▼
#                     inject summary

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lc-version.sh
. "$SCRIPT_DIR/lc-version.sh"

input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd // empty')

[ -z "$cwd" ] && exit 0
cd "$cwd" 2>/dev/null || exit 0
# .lightcone/ is created by `lc init` and marks an lc-managed project. Gate
# on it rather than astra.yaml -- astra.yaml marks any ASTRA project,
# including astra-only ones with no lc execution layer, and this is an
# execution-layer hook.
[ -d ".lightcone" ] || exit 0

# lc is a global tool (installed alongside astra from the lightcone-cli
# wheel). If it isn't on PATH, the toolchain isn't installed and there is
# nothing useful we can report.
command -v lc &>/dev/null || exit 0

status_json=$(lc status --json 2>/dev/null)
counts=$(echo "$status_json" | jq -r '
    [.universes[].outputs[].status] as $s |
    {
        ok: ($s | map(select(. == "ok")) | length),
        stale: ($s | map(select(. == "stale")) | length),
        missing: ($s | map(select(. == "missing")) | length),
        alias: ($s | map(select(. == "alias")) | length)
    } | "\(.ok) \(.stale) \(.missing) \(.alias)"
' 2>/dev/null)
read -r ok_count stale_count missing_count alias_count <<<"$counts"
ok_count=${ok_count:-0}
stale_count=${stale_count:-0}
missing_count=${missing_count:-0}
alias_count=${alias_count:-0}

summary="This is a Lightcone project — activate the lightcone skills appropriate for the current work.
lc run materialization: ok=$ok_count stale=$stale_count missing=$missing_count alias=$alias_count"

needs_run=$((missing_count + stale_count))
if [ "$needs_run" -gt 0 ]; then
    summary="$summary
ACTION REQUIRED: $needs_run output(s) need \`lc run\` ($missing_count missing, $stale_count stale)."
fi

# Warn (never block) when the installed lc drifts outside the range this plugin
# was built against. Empty when lc is in range or its version is unparseable.
lc_warning=$(lc_version_warning)
if [ -n "$lc_warning" ]; then
    summary="$summary
$lc_warning"
fi

jq -n --arg ctx "$summary" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: ($ctx + "\n")}}'
exit 0
