#!/bin/bash
# Single source of truth for the astra toolchain pin — both hooks source this.
#
# Only astra-tools is pinned. astra-spec is deliberately NOT pinned: the spec
# version is whatever the pinned tools release declares, so bumping the tools
# pin is the one act that moves the whole toolchain. Requires astra-tools >=
# 0.2.12, the first release whose `astra-tools` console script matches the
# package name (what makes the terse `uvx astra-tools@<version>` form work).
ASTRA_TOOLS_PIN="0.2.12"

# Where to send the user when uv is missing. The hooks NEVER install uv
# themselves — installing software is the user's call, not the agent's.
ASTRA_UV_INSTALL="https://docs.astral.sh/uv/getting-started/installation/"

# The one way to run astra: an ephemeral, pinned `uvx` invocation (cached after
# first use) — never an `astra` found on PATH, whose version is unknown.
# Callers check `command -v uvx` and degrade to a message pointing at
# ASTRA_UV_INSTALL when it is absent.
ASTRA_CMD=(uvx "astra-tools@${ASTRA_TOOLS_PIN}")
