#!/bin/bash
# SessionStart hook: surface a terse project status to the agent.
#
# Reports materialization counts and a tight CLI primer so the agent
# knows what substrate commands exist. Deliberately NOT here:
#   - skill listing -- the harness already advertises installed skills;
#     repeating them costs context and duplicates the skill system.
#   - astra validate -- validation is an opinion about the work, not
#     session state; it belongs to validate-on-save, which fires at the
#     moment an ASTRA file actually changes.
#   - project name / decision count / universe count -- trivia the agent
#     reads from astra.yaml when needed; costs against the 10k
#     additionalContext budget.

input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd // empty')

[ -z "$cwd" ] && exit 0
cd "$cwd" 2>/dev/null || exit 0
[ -f "astra.yaml" ] || exit 0

# lc comes from the project venv (prepended to PATH by activate-venv.sh).
# If it didn't resolve, the venv setup is broken and there is nothing
# useful we can report.
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

summary="ASTRA project.
Materialization: ok=$ok_count stale=$stale_count missing=$missing_count alias=$alias_count

Substrate CLIs (use --help on any):
  lc init / lc run / lc status / lc verify / lc build / lc export wrroc
  astra validate / astra paper add / astra universe generate"

needs_run=$((missing_count + stale_count))
if [ "$needs_run" -gt 0 ]; then
    summary="$summary

ACTION REQUIRED: $needs_run output(s) need \`lc run\` ($missing_count missing, $stale_count stale)."
fi

jq -n --arg ctx "$summary" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $ctx}}'
exit 0
