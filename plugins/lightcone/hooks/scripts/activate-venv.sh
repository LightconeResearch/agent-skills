#!/bin/bash
# SessionStart hook: prepend the project venv to PATH for every Bash command
# Claude Code spawns this session.
#
# We don't `source` activate -- we only need PATH and VIRTUAL_ENV. Sourcing
# activate also runs prompt mutations and defines a deactivate function we
# don't want, and any non-zero status under `set -e` would silently skip
# the writeback (the failure mode behind issue #103). Writing the two
# exports directly to CLAUDE_ENV_FILE is the documented mechanism and is
# what every downstream hook implicitly relies on for `astra` / `lc` to
# resolve to the project venv rather than whatever system install happens
# to be on PATH.
#
# `lc init` creates this venv empty -- it's the analysis environment the
# agent populates, not a copy of the lightcone-cli toolchain itself (that's
# global, see lc-version.sh). $CLAUDE_PROJECT_DIR isn't reliably set in
# plugin context, so read cwd from the hook's stdin JSON like the sibling
# lightcone-session-start.sh hook does.
#
# Gated on .lightcone/ (created by `lc init`), not astra.yaml -- astra.yaml
# marks any ASTRA project including astra-only ones with no lc execution
# layer, and only lc-managed projects have a project venv to activate.

input=$(cat)
cwd=$(echo "$input" | jq -r '.cwd // empty')

[ -n "$cwd" ] || exit 0
[ -d "$cwd/.lightcone" ] || exit 0

VENV="$cwd/.venv"
[ -d "$VENV/bin" ] || exit 0
[ -n "$CLAUDE_ENV_FILE" ] || exit 0

{
    echo "export VIRTUAL_ENV=$VENV"
    echo "export PATH=$VENV/bin:\$PATH"
} >> "$CLAUDE_ENV_FILE"

exit 0
