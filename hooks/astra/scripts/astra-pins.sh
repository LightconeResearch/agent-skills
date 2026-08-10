#!/bin/bash
# Single source of truth for the astra toolchain pin — all hooks source this.
#
# Only astra-tools is pinned, always as a plain version (the `pkg@version` uvx
# form supports nothing else — no git requirements). astra-spec is deliberately
# NOT pinned: the spec version is whatever the pinned tools release declares,
# so bumping the tools pin is the one act that moves the whole toolchain.
# Requires astra-tools >= 0.2.13: the `astra-tools` console-script alias
# arrived in 0.2.12 (enables `uvx astra-tools@<version>`), and no-arg
# project-wide `astra validate` plus the `Layout:` line in `astra info`
# land in 0.2.13 — the hooks lean on all three.
ASTRA_TOOLS_PIN="0.2.13"

# Where to send the user when uv is missing. The hooks NEVER install uv
# themselves — installing software is the user's call, not the agent's.
ASTRA_UV_INSTALL="https://docs.astral.sh/uv/getting-started/installation/"

# The one way to run astra: an ephemeral, pinned `uvx` invocation (cached after
# first use) — never an `astra` found on PATH, whose version is unknown.
# Callers check `command -v uvx` and degrade via astra_emit to a message
# pointing at ASTRA_UV_INSTALL when it is absent.
ASTRA_CMD=(uvx "astra-tools@${ASTRA_TOOLS_PIN}")

# Run the pinned astra with color forced off: hook output is parsed (awk) and
# embedded in JSON, and a forced-color environment (FORCE_COLOR /
# CLICOLOR_FORCE, common in agent and CI shells) would lace it with ANSI
# sequences. The escaper strips stray control bytes as a backstop, but the
# text must be plain for the header slicing to work at all.
astra_run() {
  env -u FORCE_COLOR -u CLICOLOR_FORCE NO_COLOR=1 "${ASTRA_CMD[@]}" "$@"
}

# Escape stdin into a JSON string body: backslash, quote, tab, CR, newlines
# (one trailing \n per line, matching the emitted-context style) — then strip
# any remaining control characters (ANSI escapes from a forced-color Rich,
# etc.), which are illegal inside a JSON string. Deliberately awk, not jq —
# the hooks run on machines we don't control, and bash + awk/sed are the only
# dependencies beyond uv itself.
astra_json_escape() {
  awk '{
    gsub(/\\/, "\\\\"); gsub(/"/, "\\\""); gsub(/\t/, "\\t"); gsub(/\r/, "\\r");
    gsub(/[[:cntrl:]]/, "");
    printf "%s\\n", $0
  }'
}

# Wrap stdin in the hookSpecificOutput envelope. $1 = hookEventName.
astra_emit() {
  printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":"%s"}}\n' \
    "$1" "$(astra_json_escape)"
}

# Best-effort cd to the payload's cwd ($1 = raw payload): most harnesses spawn
# hooks in the session directory already, but the payload field is
# authoritative when present. Content-embedded "cwd" strings can't spoof the
# match — inside a JSON string their quotes are escaped, so the pattern's bare
# quotes don't match them.
astra_cd_payload_cwd() {
  local cwd
  cwd=$(printf '%s' "$1" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
  [ -n "$cwd" ] && [ -d "$cwd" ] && cd "$cwd"
  return 0
}
