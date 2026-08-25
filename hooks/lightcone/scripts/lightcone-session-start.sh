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
#   - The check is not gated on there being a project. The skill's first job
#     is often to create one from nothing, and a CLI that is missing or too
#     old blocks that just as surely as it blocks a run — so waiting for
#     ./astra.yaml to appear would withhold the warning exactly when it is
#     most useful. Only the framing changes with a project present; the
#     verdict is always reported.
#   - It NEVER installs anything itself. A hook runs without a permission
#     prompt, so an install here would mutate the user's machine with no
#     moment of consent. It reports; the agent acts; who consents depends on
#     whether anyone is there to consent (see the mode probe below).
#   - The floor version comes from the bundling plugin's `tools` pin in
#     skills.config.json: canonical sources write the lightcone-cli==x.y.z
#     placeholder and `npm run build` substitutes the pin into the packaged
#     copies. Nothing here is a number a contributor should hand-edit.
#
# Self-contained on purpose — no sourcing, no jq/sed/awk.
#
#   SessionStart ──▶ lc present? ──no──▶ inject "not installed, ask to install"
#                        │yes
#                        ▼
#                  lc --version parses? ──no──▶ inject "unreadable, ask to repair"
#                        │yes
#                        ▼
#                  version >= floor? ──no──▶ inject "too old, ask to upgrade"
#                        │yes
#                        ▼
#                  inject "Lightcone CLI ready: lc <version>" — the exact
#                  sentence the skill takes as its own preflight, so it can
#                  skip running `lc --version` a second time. Emitted whether
#                  or not a project is present, because silence would be
#                  indistinguishable from a hook that never ran.

cat >/dev/null # consume the payload; everything needed comes from the cwd

# Whether this directory is already a project changes the framing, and
# whether a healthy engine is worth mentioning at all — not whether the
# engine gets checked.
if [ -f astra.yaml ]; then
    where="Lightcone project — the execution layer for ./astra.yaml"
    closing="Activate the lightcone skill to work on this project."
    in_project=1
else
    where="Lightcone plugin active — this directory holds no astra.yaml, so there is no project here yet."
    closing="Activate the lightcone skill to scope one, or to work on a project elsewhere."
    in_project=0
fi

# The `==` form is what the pin substitution rewrites; the floor is its tail.
required_spec="lightcone-cli==x.y.z"
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
    install_remedy="No one can be asked in this session, so do it: run \`uv tool install $required_spec\`, then say in your final message that you installed it."
    upgrade_remedy="No one can be asked in this session, so do it: run \`uv tool install $required_spec\` (which replaces the older install), then say in your final message that you upgraded it."
    repair_remedy="No one can be asked in this session, so do it: run \`uv tool install --force $required_spec\`, then say in your final message that you repaired the install."
else
    install_remedy="Ask the user whether to install it with \`uv tool install $required_spec\`, and wait for an answer. Never install it unasked."
    upgrade_remedy="Ask the user whether to run \`uv tool install $required_spec\`, which replaces the older install, and wait for an answer. Never upgrade it unasked."
    repair_remedy="Ask the user whether to repair it with \`uv tool install --force $required_spec\`, and wait for an answer."
fi

emit() { # $1: the engine-state paragraph
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s\\n%s\\n%s\\n"}}\n' \
        "$where" "$1" "$closing"
}

if ! command -v lc &>/dev/null; then
    emit "The Lightcone CLI is not installed, so nothing can be scoped into a project, materialized, published, or diagnosed — \`lc init\`, \`lc status\`, \`lc materialize\` and \`lc run\` are all unavailable. $install_remedy"
    exit 0
fi

# `lc --version` prints e.g. "lc, version 0.5.0"; take the last field.
version_line=$(lc --version 2>/dev/null)
rc=$?
found="${version_line##* }"

if [ $rc -ne 0 ] || [ -z "$found" ] || [ "$found" = "$version_line" ]; then
    emit "\`lc\` is on PATH but \`lc --version\` did not report a version (exit $rc) — the install is broken, or that \`lc\` is not the Lightcone CLI. $repair_remedy"
    exit 0
fi

# Past this point the version is spliced into the JSON envelope, and it came
# from whatever binary answered to `lc` — so keep it to characters a version
# can be made of. An unescaped quote or backslash would produce a line that
# does not parse, which the harness drops silently: the hook would look like
# it never fired, in exactly the case (a foreign `lc`) it exists to report.
found="${found//[^A-Za-z0-9._+:-]/}"
[ -n "$found" ] || { emit "\`lc\` is on PATH but reported no readable version — the install is broken, or that \`lc\` is not the Lightcone CLI. $repair_remedy"; exit 0; }

# Version floor, in PEP 440 order — which `sort -V` does not implement. Verified:
# sort -V puts 0.5.0 BEFORE 0.5.0.dev1, 0.5.0a1, 0.5.0b1 and 0.5.0rc1, while
# PEP 440 has every one of those precede the release they lead up to. Left to
# sort -V a release candidate would read as newer than its release, so a floor
# of 0.5.0rc1 would tell someone on the final 0.5.0 they are behind.
#
# So split each version into its release part and a pre-release rank and
# compare in steps: release (sort -V, correct for plain dotted numbers), then
# rank (dev < a < b < rc < final), then the rank's own number.
pep_split() { # $1 -> pep_rel, pep_rank, pep_num, pep_dev ("" when not a .dev build)
    local v="${1%%+*}"
    pep_dev=""
    case "$v" in *.dev*) pep_dev="${v##*.dev}"; v="${v%%.dev*}" ;; esac
    case "$v" in
        *rc*) pep_rel="${v%%rc*}"; pep_rank=3; pep_num="${v##*rc}" ;;
        *a*)  pep_rel="${v%%a*}";  pep_rank=1; pep_num="${v##*a}" ;;
        *b*)  pep_rel="${v%%b*}";  pep_rank=2; pep_num="${v##*b}" ;;
        # No pre-release segment: rank 4 for the release itself, but rank 0
        # when it is a bare .dev build — 0.5.0.dev1 precedes 0.5.0a1, since a
        # dev build of a release leads up to that release's own alphas.
        *)    pep_rel="$v";        pep_num=0
              if [ -n "$pep_dev" ]; then pep_rank=0; else pep_rank=4; fi ;;
    esac
    case "$pep_num" in ''|*[!0-9]*) pep_num=0 ;; esac
    case "$pep_dev" in *[!0-9]*) pep_dev=0 ;; esac
}

precedes() { # $1 candidate, $2 floor — true when $1 comes before $2
    local a_rel a_rank a_num a_dev b_rel b_rank b_num b_dev oldest
    pep_split "$1"; a_rel="$pep_rel" a_rank="$pep_rank" a_num="$pep_num" a_dev="$pep_dev"
    pep_split "$2"; b_rel="$pep_rel" b_rank="$pep_rank" b_num="$pep_num" b_dev="$pep_dev"
    if [ "$a_rel" != "$b_rel" ]; then
        oldest=$(printf '%s\n%s\n' "$a_rel" "$b_rel" | sort -V | head -n1)
        [ "$oldest" = "$a_rel" ]; return
    fi
    [ "$a_rank" -ne "$b_rank" ] && { [ "$a_rank" -lt "$b_rank" ]; return; }
    [ "$a_num" -ne "$b_num" ] && { [ "$a_num" -lt "$b_num" ]; return; }
    # Same release and same pre-release: a .dev build precedes the thing it
    # leads to, and an earlier .dev precedes a later one.
    [ -n "$a_dev" ] && [ -z "$b_dev" ] && return 0
    [ -z "$a_dev" ] && [ -n "$b_dev" ] && return 1
    [ -n "$a_dev" ] && [ "$a_dev" -lt "$b_dev" ]
}

if precedes "$found" "$required"; then
    emit "The installed Lightcone CLI is $found, older than the $required this skill is written against — its verbs and status vocabulary have changed, so following the skill against $found will produce errors rather than results. $upgrade_remedy"
    exit 0
fi

# Say "Lightcone CLI ready: lc <version>" in both cases, in exactly those words: the
# skill treats that sentence as the answer to its own preflight and skips
# running `lc --version` a second time. Silence cannot carry that meaning —
# the agent has no way to tell a healthy engine from a hook that never fired
# (another harness, hooks turned off, a subagent that missed session start),
# and a signal that is ambiguous is not a signal.
#
# Outside a project the line is kept to one sentence, since its only job
# there is to spare that round trip.
if [ "$in_project" -eq 1 ]; then
    emit "Lightcone CLI ready: lc $found. Run \`lc status\` to see what state the analysis's outputs are in."
else
    printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Lightcone CLI ready: lc %s (Lightcone plugin active; this directory holds no astra.yaml yet).\\n"}}\n' "$found"
fi
exit 0
