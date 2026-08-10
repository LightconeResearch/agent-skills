#!/bin/bash
# Single source of truth for the astra toolchain pin — both hooks source this.
#
# Only astra-tools is pinned. astra-spec is deliberately NOT pinned: the spec
# version is whatever the pinned tools release declares, so bumping the tools
# pin is the one act that moves the whole toolchain. Requires astra-tools >=
# 0.2.12, the first release with the `astra-tools` console-script alias (what
# makes the terse `uvx astra-tools@<version>` form work), no-arg project-wide
# `astra validate`, and the `Layout:` line in `astra info` — the hooks lean on
# all three.
ASTRA_TOOLS_PIN="0.2.12"

# Where to send the user when uv is missing. The hooks NEVER install uv
# themselves — installing software is the user's call, not the agent's.
ASTRA_UV_INSTALL="https://docs.astral.sh/uv/getting-started/installation/"

# The one way to run astra: an ephemeral, pinned `uvx` invocation (cached after
# first use) — never an `astra` found on PATH, whose version is unknown.
# Callers check `command -v uvx` and degrade to a message pointing at
# ASTRA_UV_INSTALL when it is absent.
ASTRA_CMD=(uvx "astra-tools@${ASTRA_TOOLS_PIN}")

# Escape stdin into a JSON string body: backslash, quote, tab, CR, and
# newlines (one trailing \n per line, matching the emitted-context style).
# Deliberately awk, not jq — the hooks run on machines we don't control, and
# bash + awk/sed are the only dependencies beyond uv itself.
astra_json_escape() {
  awk '{
    gsub(/\\/, "\\\\"); gsub(/"/, "\\\""); gsub(/\t/, "\\t"); gsub(/\r/, "\\r");
    printf "%s\\n", $0
  }'
}

# Wrap stdin in the hookSpecificOutput envelope. $1 = hookEventName.
astra_emit() {
  printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}\n' \
    "$1" "$(astra_json_escape)"
}
