#!/bin/bash
# Single source of truth for the astra toolchain pins used across the astra
# plugin — both hooks source this. Bump both here, in one place.
#
# Dual pin: astra-tools declares only a floating `astra-spec>=0.0.11`, so pinning
# the tools alone does not pin the schema. astra validate must speak the same
# schema the skill teaches, so we pin astra-spec exactly too. The tools pin may
# be a version ("0.2.10") or, exceptionally, a pinned git requirement.
ASTRA_TOOLS_PIN="0.2.11"
ASTRA_SPEC_PIN="0.0.12"

# Where to send the user when uv is missing. The hooks NEVER install uv
# themselves — installing software is the user's call, not the agent's.
ASTRA_UV_INSTALL="https://docs.astral.sh/uv/getting-started/installation/"

# Resolve an astra runner into the ASTRA_CMD array:
#   a global `astra` (on PATH) first — respects the installed toolchain;
#   else an ephemeral, dual-pinned `uvx` run that installs on first use.
# Returns 1 (with ASTRA_CMD unset) when neither astra nor uv is available; the
# caller degrades to a message asking the user to install uv (ASTRA_UV_INSTALL).
# Never install uv (or anything else) from a hook.
astra_resolve() {
  if command -v astra &>/dev/null; then
    ASTRA_CMD=(astra)
  elif command -v uvx &>/dev/null; then
    # A pin containing "+" is already a full requirement (git ref); a bare
    # version becomes an exact PyPI pin.
    local tools_req="${ASTRA_TOOLS_PIN}"
    [[ "$tools_req" != *+* ]] && tools_req="astra-tools==${tools_req}"
    ASTRA_CMD=(uvx --from "$tools_req" --with "astra-spec==${ASTRA_SPEC_PIN}" astra)
  else
    return 1
  fi
  return 0
}
