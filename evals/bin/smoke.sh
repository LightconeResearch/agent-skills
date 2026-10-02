#!/usr/bin/env bash
# Run the plugin smoke suite (evals/smoke) for one or more legs, one Harbor job
# per leg in $OUT/<leg>/. Build the images first (evals/bin/build-images.sh).
#
#   evals/bin/smoke.sh oracle                                  # reference solutions, no LLM
#   evals/bin/smoke.sh claude-code:claude-haiku-4-5:plugin
#   K=1 TASKS='astra-*' evals/bin/smoke.sh codex:gpt-6-luna:skill
#   evals/bin/smoke.sh --name codex:gpt-6-luna:skill            # print the leg's name: codex-luna-skill
#
# A leg is `oracle` or <agent>:<model>:<config>, and is named oracle or
# <agent>-<model word>-<config> (claude-haiku-plugin, codex-luna-skill):
#   skill   the lightcone plugin's skills (lightcone + astra) via Harbor --skill, no hooks
#   plugin  the whole lightcone plugin (skills + SessionStart/validate-on-save hooks) via
#           claude --plugin-dir (evals/bin/plugin_agent.py); claude-code only
#   bare    no skill and no plugin: the prompt names the CLI, nothing more
#
# Env:
#   K        attempts per task (default 2)
#   N        concurrent trials (default 4)
#   TASKS    space-separated globs over the task dir names (default '*'; e.g. 'astra-* lc-materialize')
#   OUT      jobs directory (default evals/jobs)
#   PLUGIN   the plugin under test (default plugins/lightcone of this checkout)
#
# Credentials come from the environment: ANTHROPIC_API_KEY for claude-code,
# OPENAI_API_KEY for codex. Off CI, CLAUDE_CODE_OAUTH_TOKEN (a subscription)
# also works for claude-code, and CODEX_FORCE_AUTH_JSON=1 uses ~/.codex/auth.json.
# A finished job is skipped, so re-running resumes; delete a job dir to redo it.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
K="${K:-2}"
N="${N:-4}"
TASKS="${TASKS:-*}"
OUT="${OUT:-$ROOT/evals/jobs}"
PLUGIN="${PLUGIN:-$ROOT/plugins/lightcone}"

die() { echo "smoke.sh: $*" >&2; exit 1; }

leg_name() {  # claude-code:claude-haiku-4-5:plugin -> claude-haiku-plugin
  local agent model config word
  IFS=: read -r agent model config <<<"$1"
  for word in ${model//-/ }; do [[ "$word" =~ [a-z] && "$word" != claude && "$word" != gpt ]] && break; done
  echo "${agent%%-*}-$word-$config"
}

if [ "${1:-}" = --name ]; then leg_name "$2"; exit 0; fi

[ $# -gt 0 ] || die "name at least one leg (oracle, or agent:model:config)"
docker image inspect lightcone-smoke-stack >/dev/null 2>&1 \
  || die "lightcone-smoke-stack is not built: run evals/bin/build-images.sh"
[ -f "$PLUGIN/.claude-plugin/plugin.json" ] || die "no plugin at $PLUGIN"

include=()
set -f; for glob in $TASKS; do include+=(-i "$glob"); done; set +f   # globs for harbor, not the shell

status=0
for leg in "$@"; do
  if [ "$leg" = oracle ]; then
    job=oracle; args=(-a oracle)
  else
    IFS=: read -r agent model config <<<"$leg"
    [ -n "${config:-}" ] || die "leg '$leg' is not agent:model:config"
    job="$(leg_name "$leg")"
    case "$agent" in
      claude-code)
        if [ -n "${CI:-}" ] && [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
          die "CLAUDE_CODE_OAUTH_TOKEN is set on CI; CI runs on ANTHROPIC_API_KEY only"
        fi
        # With both set, Claude Code prefers the API key over the subscription token.
        [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && unset ANTHROPIC_API_KEY
        [ -n "${ANTHROPIC_API_KEY:-}${CLAUDE_CODE_OAUTH_TOKEN:-}" ] \
          || die "$job needs ANTHROPIC_API_KEY" ;;
      codex)
        export CODEX_FORCE_AUTH_JSON="${CODEX_FORCE_AUTH_JSON:-0}"
        [ -n "${OPENAI_API_KEY:-}" ] || [ "$CODEX_FORCE_AUTH_JSON" = 1 ] \
          || die "$job needs OPENAI_API_KEY" ;;
      *) die "unknown agent $agent" ;;
    esac
    args=(-a "$agent" -m "$model")
    case "$config" in
      bare) ;;
      skill) for s in "$PLUGIN"/skills/*/; do args+=(--skill "${s%/}"); done ;;
      plugin)
        [ "$agent" = claude-code ] || die "the plugin config is claude-code only"
        export PYTHONPATH="$ROOT/evals/bin${PYTHONPATH:+:$PYTHONPATH}"
        args=(-a plugin_agent:ClaudeCodePlugin -m "$model" --ak "plugin_dirs=$PLUGIN") ;;
      *) die "unknown config $config" ;;
    esac
  fi
  if [ -f "$OUT/$job/$job/result.json" ]; then echo "skip $job (done)"; continue; fi
  echo "=== $job $(date +%H:%M:%S)"
  harbor run -p "$ROOT/evals/smoke" "${include[@]}" "${args[@]}" -e docker -k "$K" -n "$N" \
    --agent-setup-timeout-multiplier 2 -o "$OUT/$job" --job-name "$job" -q -y
  rc=$?
  echo "=== $job exit $rc $(date +%H:%M:%S)"
  [ "$rc" -eq 0 ] || status=$rc
done
exit "$status"
