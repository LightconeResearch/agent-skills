#!/bin/bash
# Antigravity hook adapter: runs a canonical hook script — written to the
# Claude Code / Codex hook protocol — under Antigravity's hooks.json contract.
# Every command in a generated plugins/<name>/hooks.json calls this file
# (see antigravityHooks() in scripts/lib.mjs), so the canonical scripts under
# src/hooks/ stay single-protocol.
#
#   antigravity-hook.sh SessionStart  <script>   run it, inject its context
#   antigravity-hook.sh PostToolUse   <script>   run it, stash its context
#   antigravity-hook.sh PreInvocation            deliver stashed context, once
#
# The two protocols differ in exactly three ways, and this file is those
# three translations:
#
#   1. Where the agent is. Antigravity runs a plugin hook in the plugin's own
#      directory and names the agent's working directory in the payload
#      (`cwd`, or only `workspacePaths` on older releases). The canonical
#      scripts look for ./astra.yaml, so the adapter cd's there first.
#   2. The payload. Antigravity sends camelCase protojson (`toolCall.args.
#      TargetFile`); the scripts read Claude's snake_case shape. The adapter
#      hands them a minimal Claude-shaped payload — the directory and the
#      edited file — not the raw one, whose `lastUserInput` would trip
#      validate-on-save's substring prefilter on every edit of a session whose
#      prompt mentioned astra.yaml.
#   3. The way back to the model. The scripts answer with
#      hookSpecificOutput.additionalContext. Antigravity's SessionStart takes
#      that text as an injected system message. Its PostToolUse can only answer
#      `{}`, so the context is stashed under the conversation id, and the
#      PreInvocation handler — which runs before the next model call — injects
#      it and removes the stash.
#
# Self-contained on purpose — no sourcing, no jq/sed/awk. JSON strings are
# never decoded: they are cut out of one envelope and spliced into another
# still escaped, the same move the canonical scripts make with astra's --json
# output. Every path prints exactly one JSON object, as Antigravity requires.
#
#   SessionStart|PostToolUse ──▶ agent dir in payload? ──no──▶ {}
#                                    │yes, cd there
#                                    ▼
#                       run script on a Claude-shaped payload
#                                    │
#                       additionalContext? ──no──▶ {}
#                                    │yes
#                  SessionStart ◀────┴────▶ PostToolUse
#                       │                        │
#               inject it now          stash it; answer {}
#
#   PreInvocation ──▶ stash for this conversation? ──no──▶ {}
#                                    │yes
#                                    ▼
#                         inject it; remove the stash

event=$1
script=$2

src=${BASH_SOURCE[0]}
case "$src" in */*) here=${src%/*} ;; *) here=. ;; esac
case "$here" in /*) ;; *) here=$PWD/$here ;; esac # survives the cd below

input=$(cat)

empty() { printf '{}\n'; exit 0; }

inject() { # $1: an already-escaped JSON string body
    printf '{"injectSteps":[{"systemMessage":{"systemMessage":"%s"}}]}\n' "$1"
    exit 0
}

# json_string KEY [array] — the first "KEY": "…" in the payload (or, with
# `array`, the first element of "KEY": ["…"]), still escaped, in $REPLY.
# Tolerates the whitespace protojson inserts around the colon. The key is
# matched only as a key: inside a JSON string value its quotes are escaped.
# One unanchored regex match, never ${input#*…}: a write_to_file payload
# carries the whole file, and bash's prefix removal is quadratic in it (a 2 MB
# payload outlives any hook timeout), while a regex match stays linear.
json_string() {
    local re='"'"$1"'"[[:space:]]*:[[:space:]]*'
    [ "${2:-}" = array ] && re+='\[[[:space:]]*'
    re+='"(([^"\\]|\\.)*)"'
    [[ $input =~ $re ]] || return 1
    REPLY=${BASH_REMATCH[1]}
}

# The private dir that holds stashed context, created on first use and
# trusted only if it is a real directory we own: $PLUGIN_DATA for an
# installed plugin, else a per-user dir under $TMPDIR.
stash_file() {
    local dir id
    if [ -n "${PLUGIN_DATA:-}" ]; then dir=$PLUGIN_DATA/antigravity-context
    else dir=${TMPDIR:-/tmp}/antigravity-hook-context-$UID; fi
    mkdir -p -m 700 "$dir" 2>/dev/null
    [ -d "$dir" ] && [ ! -L "$dir" ] && [ -O "$dir" ] || return 1
    json_string conversationId && id=${REPLY//[^A-Za-z0-9_-]/}
    REPLY=$dir/${id:-unknown}.ctx
}

case "$event" in
    SessionStart|PostToolUse)
        [ -n "$script" ] && [ -f "$here/$script" ] || {
            echo "antigravity-hook: no hook script '$script' beside the adapter" >&2
            empty
        }

        # 1. The agent's directory: `cwd`, else the first workspace path.
        json_string cwd || json_string workspacePaths array || empty
        cwd_json=${REPLY#file://}
        dir=$cwd_json
        case "$dir" in *\\*) dir=${dir//\\\//\/}; dir=${dir//\\\"/\"}; dir=${dir//\\\\/\\} ;; esac
        cd "$dir" 2>/dev/null || empty

        # 2. The Claude-shaped payload the script was written against.
        file_json=''
        json_string TargetFile && file_json=$REPLY
        payload='{"hook_event_name":"'$event'","cwd":"'$cwd_json'","tool_input":{'
        [ -n "$file_json" ] && payload+='"file_path":"'$file_json'"'
        payload+='}}'

        out=$(printf '%s' "$payload" | bash "$here/$script")

        # 3. Its additionalContext, still escaped. The scripts print the
        #    envelope exactly as {"hookSpecificOutput":{…,"additionalContext":"…"}}.
        #    (A regex here too: the report can be long.)
        re='"additionalContext":"(.*)"\}\}$'
        [[ $out =~ $re ]] || empty
        context=${BASH_REMATCH[1]}

        [ "$event" = SessionStart ] && inject "$context"
        # Several edits can land before the next model call: each context is
        # appended, newline-separated (an escaped \n, as the JSON body needs).
        stash_file && printf '%s\\n' "$context" >>"$REPLY"
        empty
        ;;
    PreInvocation)
        stash_file && [ -f "$REPLY" ] || empty
        # Claim the stash before reading it, so a context is delivered once.
        claimed=$REPLY.$$
        mv -f "$REPLY" "$claimed" 2>/dev/null || empty
        context=$(<"$claimed")
        rm -f "$claimed"
        [ -n "$context" ] || empty
        inject "$context"
        ;;
    *)
        echo "antigravity-hook: unsupported event '$event'" >&2
        empty
        ;;
esac
