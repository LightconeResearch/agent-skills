#!/bin/bash
# Single source of truth for the astra toolchain pin — the hooks source this.
#
# Only astra-tools is pinned, always as a plain version (the `pkg@version` uvx
# form supports nothing else — no git requirements). astra-spec is deliberately
# NOT pinned: the spec version is whatever the pinned tools release declares,
# so bumping the tools pin is the one act that moves the whole toolchain.
# Requires astra-tools >= 0.2.13: the `astra-tools` console-script alias
# arrived in 0.2.12 (enables `uvx astra-tools@<version>`), and the --json
# output mode (one JSON-encoded string, safe to splice into hook responses)
# plus `info --brief` land in 0.2.13 — the hooks lean on all of them.
ASTRA_TOOLS_PIN="0.2.13"

# Where to send the user when uv is missing. The hooks NEVER install uv
# themselves — installing software is the user's call, not the agent's.
ASTRA_UV_INSTALL="https://docs.astral.sh/uv/getting-started/installation/"

# The one way to run astra: an ephemeral, pinned `uvx` invocation (cached
# after first use) — never an `astra` found on PATH, whose version is unknown.
# Color is forced off: hook output is embedded in JSON responses, and a
# forced-color environment (FORCE_COLOR / CLICOLOR_FORCE, common in agent and
# CI shells) would lace it with ANSI sequences.
ASTRA_CMD=(uvx "astra-tools@${ASTRA_TOOLS_PIN}")
astra_run() {
  env -u FORCE_COLOR -u CLICOLOR_FORCE NO_COLOR=1 "${ASTRA_CMD[@]}" "$@"
}
