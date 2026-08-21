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
#   - It NEVER installs anything itself. A hook runs without a permission
#     prompt, so an install here would mutate the user's machine with no
#     moment of consent. It reports; the agent acts; who consents depends on
#     whether anyone is there to consent (see the mode probe below).
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

# Is anyone there to answer? A headless run (`claude -p`, an SDK embed, CI)
# has nobody to ask, and a question there only stalls the run — so it acts and
# reports instead. The default leans the cautious way on purpose: assume a
# human is present unless something positively says otherwise, because a
# needless question costs a stalled task while a needless install puts
# software on somebody's machine they never agreed to.
# Verified: the interactive TUI sets CLAUDE_CODE_ENTRYPOINT=cli, `claude -p`
# sets sdk-cli. An unset value means a harness we don't know (Codex, say),
# where a human is the safer assumption.
autonomous=0
case "${CLAUDE_CODE_ENTRYPOINT:-}" in sdk-*) autonomous=1 ;; esac
[ -n "${CI:-}" ] && autonomous=1

if [ "$autonomous" -eq 1 ]; then
    install_remedy="No one can be asked in this session, so do it: run \`uv tool install lightcone-cli\`, then say in your final message that you installed it."
    upgrade_remedy="No one can be asked in this session, so do it: run \`uv tool upgrade lightcone-cli\`, then say in your final message that you upgraded it."
    repair_remedy="No one can be asked in this session, so do it: run \`uv tool install --force lightcone-cli\`, then say in your final message that you repaired the install."
else
    install_remedy="Ask the user whether to install it with \`uv tool install lightcone-cli\`, and wait for an answer. Never install it unasked."
    upgrade_remedy="Ask the user whether to upgrade with \`uv tool upgrade lightcone-cli\`, and wait for an answer. Never upgrade it unasked."
    repair_remedy="Ask the user whether to repair it with \`uv tool install --force lightcone-cli\`, and wait for an answer."
fi

emit() { # $1: the engine-state paragraph
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Lightcone project — the execution layer for ./astra.yaml\\n%s\\nActivate the lightcone skill to work on this project.\\n"}}\n' "$1"
}

if ! command -v lc &>/dev/null; then
    emit "The Lightcone engine is not installed, so nothing here can be materialized, published, or diagnosed — \`lc status\`, \`lc materialize\` and \`lc run\` are all unavailable. The install also puts \`git-annex\` on PATH, which the user's own \`git add\` needs in a Lightcone project. $install_remedy"
    exit 0
fi

# `lc --version` prints e.g. "lc, version 0.5.0"; take the last field.
version_line=$(lc --version 2>/dev/null)
rc=$?
found="${version_line##* }"

if [ $rc -ne 0 ] || [ -z "$found" ] || [ "$found" = "$version_line" ]; then
    emit "\`lc\` is on PATH but \`lc --version\` did not report a version (exit $rc) — the install is broken, or that \`lc\` is not the Lightcone engine. $repair_remedy"
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
    emit "The installed Lightcone engine is $found, older than the $required this skill is written against — its verbs and status vocabulary have changed, so following the skill against $found will produce errors rather than results. $upgrade_remedy"
    exit 0
fi

emit "Engine ready: lc $found. Run \`lc status\` to see what state the analysis's outputs are in."
exit 0
