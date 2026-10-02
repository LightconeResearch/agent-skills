#!/usr/bin/env python3
"""Redact API keys from a directory tree in place (stdlib only).

    evals/bin/redact.py evals/jobs [more dirs...]

Replaces the literal values of SECRET_VARS found in the environment, and any
token shaped like an Anthropic or OpenAI key, with [REDACTED] in every file.
Run before uploading trial artifacts, before judging and before rendering:
trajectories record whatever the agent printed. Prints a GitHub warning
naming how many files changed, never the values.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SECRET_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
KEY_SHAPES = re.compile(rb"sk-ant-[A-Za-z0-9_-]{20,}|sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}")
MASK = b"[REDACTED]"


def redact(data: bytes, literals: list[bytes]) -> bytes:
    for value in literals:
        data = data.replace(value, MASK)
    return KEY_SHAPES.sub(MASK, data)


def main(roots: list[str]) -> int:
    literals = [v.encode() for v in (os.environ.get(n, "") for n in SECRET_VARS) if len(v) >= 8]
    changed = 0
    for root in roots:
        for path in Path(root).rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            data = path.read_bytes()
            clean = redact(data, literals)
            if clean != data:
                path.write_bytes(clean)
                changed += 1
    if changed:
        print(f"::warning::redacted API-key-shaped strings in {changed} file(s) under {' '.join(roots)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["evals/jobs"]))
