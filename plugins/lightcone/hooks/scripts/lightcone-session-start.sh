#!/bin/bash
# SessionStart hook (lightcone plugin): report whether the execution layer is
# usable in this project, before the agent tries to drive it.
#
# The astra plugin's own SessionStart hook covers the SPEC layer (it runs in
# the same session — lightcone bundles astra — and prints the analysis shape).
# This one covers the ENGINE: is `lc` installed, and is it new enough for the
# skill that is about to drive it?
#
# Three deliberate constraints:
#   - It only speaks inside a Lightcone project (./astra.yaml). A plugin that
#     announces itself in unrelated repositories is noise, not help.
#   - It NEVER installs anything. A hook runs without a permission prompt, so
#     an install here would mutate the user's machine with no moment of
#     consent. It reports; the skill asks; the user decides.
#   - The floor version comes from the bundling plugin's `tools` pin in
#     skills.config.json: canonical sources write the lightcone-cli==0.5.0
#     placeholder and `npm run build` substitutes the pin into the packaged
#     copies. Nothing here is a number a contributor should hand-edit.
#
# Self-contained on purpose — no sourcing, no jq/sed/awk.
#
#   SessionStart ──▶ ./astra.yaml present? ──no──▶ exit silent
#                          │yes
#                          ▼
#                       lc present? ──no──▶ inject "not installed, ask to install"
#                          │yes
#                          ▼
#                    lc --version parses? ──no──▶ inject "unreadable, ask to reinstall"
#                          │yes
#                          ▼
#                    version >= floor? ──no──▶ inject "too old, ask to upgrade"
#                          │yes
#                          ▼
#                       inject "engine ready (version)"

cat >/dev/null # consume the payload; everything needed comes from the cwd
[ -f astra.yaml ] || exit 0

# The `==` form is what the pin substitution rewrites; the floor is its tail.
required_spec="lightcone-cli==0.5.0"
required="${required_spec##*==}"

emit() { # $1: the engine-state paragraph
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Lightcone project — the execution layer for ./astra.yaml\\n%s\\nActivate the lightcone skill to work on this project.\\n"}}\n' "$1"
}

if ! command -v lc &>/dev/null; then
    emit "The Lightcone engine is not installed, so nothing here can be materialized, published, or diagnosed — \`lc status\`, \`lc materialize\` and \`lc run\` are all unavailable. Ask the user whether to install it with \`uv tool install lightcone-cli\` (this also puts \`git-annex\` on PATH, which their own \`git add\` needs in a Lightcone project). Never install it without asking."
    exit 0
fi

# `lc --version` prints e.g. "lc, version 0.5.0"; take the last field.
version_line=$(lc --version 2>/dev/null)
rc=$?
found="${version_line##* }"

if [ $rc -ne 0 ] || [ -z "$found" ] || [ "$found" = "$version_line" ]; then
    emit "\`lc\` is on PATH but \`lc --version\` did not report a version (exit $rc) — the install is broken or is not the Lightcone engine. Ask the user to repair it with \`uv tool install --force lightcone-cli\`."
    exit 0
fi

# Version floor. `lc --version` can report a dev build (0.5.0.dev4+g4fa2d1b4e),
# so compare on the release part alone: strip the local segment, then the .devN
# suffix. `sort -V` is not PEP 440 aware — it reads 0.5.0.dev4 as NEWER than
# 0.5.0 — so a dev build of exactly the floor is caught separately below: devN
# precedes its own release, and is not the release the skill was written against.
core="${found%%+*}"
base="${core%%.dev*}"
oldest=$(printf '%s\n%s\n' "$required" "$base" | sort -V | head -n1)
if { [ "$base" != "$required" ] && [ "$oldest" = "$base" ]; } ||
   { [ "$base" = "$required" ] && [ "$base" != "$core" ]; }; then
    emit "The installed Lightcone engine is $found, older than the $required this skill is written against — its verbs and status vocabulary have changed, so following the skill against $found will produce errors. Ask the user whether to upgrade with \`uv tool upgrade lightcone-cli\`. Never upgrade it without asking."
    exit 0
fi

emit "Engine ready: lc $found. Run \`lc status\` to see what state the analysis's outputs are in."
exit 0
