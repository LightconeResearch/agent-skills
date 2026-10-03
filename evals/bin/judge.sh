#!/usr/bin/env bash
# Pain-point judge: `harbor analyze` with evals/rubrics/pain-points.toml over the
# given trial dirs (typically `report.py select`'s output), as one analyze job.
#
#   evals/bin/report.py select evals/jobs --baseline base.json | evals/bin/judge.sh
#   evals/bin/judge.sh evals/jobs/claude-haiku-plugin/claude-haiku-plugin/<trial> ...
#
# Trials are copied into $OUT/judge-src/ (harbor analyze writes analysis.json
# into each trial it reads; the copies keep the leg artifacts untouched) and the
# analyze job lands in $OUT/judge/analysis.json: per trial a summary and one
# pass/fail/not_applicable check per rubric criterion, plus the judge's cost.
# Needs ANTHROPIC_API_KEY (or, off CI, CLAUDE_CODE_OAUTH_TOKEN).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
JUDGE_MODEL="${JUDGE_MODEL:-claude-sonnet-5-5}"
OUT="${OUT:-$ROOT/evals/jobs}"
N="${N:-4}"

trials=("$@")
if [ ${#trials[@]} -eq 0 ] && [ ! -t 0 ]; then
  while IFS= read -r line; do [ -n "$line" ] && trials+=("$line"); done
fi
[ ${#trials[@]} -gt 0 ] || { echo "judge.sh: nothing to judge" >&2; exit 0; }
[ -n "${ANTHROPIC_API_KEY:-}${CLAUDE_CODE_OAUTH_TOKEN:-}" ] \
  || { echo "judge.sh: the judge needs ANTHROPIC_API_KEY" >&2; exit 1; }
[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && unset ANTHROPIC_API_KEY

src="$OUT/judge-src"
rm -rf "$src" "$OUT/judge"
mkdir -p "$src"
touch "$src/job.log"   # what makes harbor analyze treat the dir as a job of trials
for t in "${trials[@]}"; do cp -R "$t" "$src/"; done

# The judge's container is a bare python image, so Harbor installs Claude Code
# in it first (apt-get + npm): give that install room (Harbor's default allows
# 360 s), and retry a judgement whose setup or provider call failed transiently.
cat > "$OUT/judge-config.yaml" <<'YAML'
agent_setup_timeout_multiplier: 3
retry:
  max_retries: 2
  include_exceptions: [NetworkConnectionError, AgentSetupTimeoutError, ApiConnectionError,
                       ApiOverloadedError, ApiRateLimitError, ApiInternalServerError]
YAML

# harbor analyze runs the judge in its own task, a prebuilt python:3.13-slim
# container, where Harbor installs Claude Code with apt-get + npm before every
# judgement (minutes, and flaky). lightcone-eval-base is python:3.13-slim plus
# the agent CLIs, so while judging we point that tag at it and Harbor skips the
# install; the original tag is restored on exit. JUDGE_IMAGE= turns this off.
JUDGE_IMAGE="${JUDGE_IMAGE-lightcone-eval-base}"
if [ -n "$JUDGE_IMAGE" ] && docker image inspect "$JUDGE_IMAGE" >/dev/null 2>&1; then
  original="$(docker image inspect -f '{{.Id}}' python:3.13-slim 2>/dev/null || true)"
  restore() {
    if [ -n "$original" ]; then docker tag "$original" python:3.13-slim
    else docker rmi -f python:3.13-slim >/dev/null 2>&1 || true; fi
  }
  trap restore EXIT
  docker tag "$JUDGE_IMAGE" python:3.13-slim
fi

echo "=== judge: ${#trials[@]} trial(s) with $JUDGE_MODEL"
harbor analyze "$src" -c "$OUT/judge-config.yaml" -r "$ROOT/evals/rubrics/pain-points.toml" -p "$ROOT/evals/rubrics/pain-points-prompt.txt" \
  -a claude-code -m "$JUDGE_MODEL" -e docker -n "$N" -o "$OUT" --job-name judge -q
