#!/bin/bash
# Single source of truth for the astra toolchain pins used across the astra
# plugin — both hooks source this, and scripts/derive-walkthrough.mjs reads the
# schema pin from it when re-deriving the walkthrough. Bump both here, in one
# place, then re-run the derivation and `npm run build`.
#
# Dual pin: astra-tools declares only a floating `astra-spec>=0.0.7`, so pinning
# the tools alone does not pin the schema. astra spec / astra validate must speak
# the same schema the skill teaches, so we pin astra-spec exactly too.
ASTRA_TOOLS_PIN="0.2.10"
ASTRA_SPEC_PIN="0.0.11"

# One-line uv installer, surfaced when neither a project astra nor uv is present.
ASTRA_UV_INSTALL="curl -LsSf https://astral.sh/uv/install.sh | sh"

# Resolve an astra runner into the ASTRA_CMD array:
#   project venv `astra` (on PATH) first — respects a project's own toolchain;
#   else an ephemeral, dual-pinned `uvx` run that installs on first use.
# Returns 1 (with ASTRA_CMD unset) when neither astra nor uv is available; the
# caller degrades to a message pointing at ASTRA_UV_INSTALL.
astra_resolve() {
  if command -v astra &>/dev/null; then
    ASTRA_CMD=(astra)
  elif command -v uvx &>/dev/null; then
    ASTRA_CMD=(uvx --from "astra-tools==${ASTRA_TOOLS_PIN}" --with "astra-spec==${ASTRA_SPEC_PIN}" astra)
  else
    return 1
  fi
  return 0
}
