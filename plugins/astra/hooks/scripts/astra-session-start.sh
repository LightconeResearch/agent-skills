#!/bin/bash
# SessionStart hook (astra plugin): orient the agent in an ASTRA project.
#
# Everything here is dynamic — read from the environment at session start:
# where the spec lives, and the analysis's shape straight from the `astra info`
# header (name, version, input/output/decision counts, and the on-disk Layout
# line). The one static line is the skill pointer.
#
# Deliberately NOT here:
#   - execution-layer status -- this plugin is about the ASTRA spec.
#   - astra validate -- validation is an opinion about the work, not
#     session state; it belongs to validate-on-save, which fires at the
#     moment an ASTRA file actually changes.
#   - skill listing -- the harness already advertises installed skills.
#
#   SessionStart ──▶ ./astra.yaml present? ──no──▶ exit silent
#                          │yes
#                          ▼
#                     uvx present? ──no──▶ inject "install uv to enable astra"
#                          │yes
#                          ▼
#                     astra info fails? ──yes──▶ inject "toolchain problem" / "spec likely malformed"
#                          │no
#                          ▼
#                     inject spec path + info header (shape + layout)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/astra-pins.sh"

input=$(cat)
astra_cd_payload_cwd "$input"
[ -f astra.yaml ] || exit 0

summary="ASTRA project — spec at ./astra.yaml"

if ! command -v uvx &>/dev/null; then
    printf '%s' "$summary
\`uv\` is not installed, so the astra CLI is unavailable. Ask the user if they would like to install it ($ASTRA_UV_INSTALL).

Activate the astra skill when working with ASTRA analyses." | astra_emit SessionStart
    exit 0
fi

# Shape of the analysis, straight from the spec: `astra info` opens with the
# name, version, "Inputs: N | Outputs: M | Decisions: K", and a "Layout:" line
# (sub-analyses and universes on disk) before the detail tables; keep just
# that header. The counts-guard rule runs first so nothing after the counts
# line leaks except an immediately following Layout line.
info_out=$(astra_run info 2>/dev/null)
info_rc=$?
shape=$(printf '%s\n' "$info_out" | awk '
    counts && !/^Layout:/ { exit }
    NF { print }
    /^Layout:/ { exit }
    /^Inputs:.*Decisions:/ { counts = 1 }
')
if [ "$info_rc" -ne 0 ] || [ -z "$shape" ]; then
    # astra itself failed (uvx resolution, network, version mismatch) —
    # an environment problem, not a statement about the spec.
    summary="$summary
Could not run \`astra info\` (exit $info_rc) — toolchain problem, not necessarily the spec."
elif [ "$(printf '%s\n' "$shape" | head -1)" = "Unknown" ]; then
    summary="$summary
Could not read the analysis shape — the spec is likely malformed. Run \`astra validate\` to see why."
else
    summary="$summary
$shape"
fi

summary="$summary

Activate the astra skill when working with ASTRA analyses."

printf '%s' "$summary" | astra_emit SessionStart
exit 0
