#!/usr/bin/env python3
"""The smoke baseline: an append-only log of recorded main runs (stdlib only).

The orphan branch `smoke-baseline` holds one file per recorded run,
`runs/<run number>-<sha>.json` ({run_number, run_id, sha, record}, where record
maps "<leg>/<task>" to that run's {k, n, turns, stack_calls}), and `index.json`,
the list of those files that the publisher regenerates from the directory each
time it adds one. Publishers never edit each other's files, so concurrent or
out-of-order publications cannot lose a record; readers order by run number.

    baseline.py fetch [--repo OWNER/NAME] [--out baseline.json]
        Reads index.json and the newest runs from raw.githubusercontent.com (no
        token) and writes {pool, history, runs, commit, run}: pool is each cell's
        records over the last POOL_RUNS runs, history over the last HISTORY_RUNS.
        Exit 0 with a baseline, 2 if there is none yet (404), 3 on any other error.
    baseline.py index DIR
        Regenerates DIR/index.json from DIR/runs/*.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

POOL_RUNS = 5
HISTORY_RUNS = 10
RAW = "https://raw.githubusercontent.com/{repo}/smoke-baseline/{path}"


def build(index: dict, load) -> dict:
    """Pool and history from an index and a loader of run files (path -> dict)."""
    runs = sorted(index.get("runs", []), key=lambda r: r["run_number"])[-HISTORY_RUNS:]
    loaded = [(meta, load(meta["file"])) for meta in runs]
    history: dict[str, list[dict]] = {}
    for meta, run in loaded:
        for cell, rec in (run.get("record") or {}).items():
            history.setdefault(cell, []).append({**rec, "run_number": meta["run_number"]})
    pool_numbers = {meta["run_number"] for meta, _ in loaded[-POOL_RUNS:]}
    pool = {cell: [r for r in recs if r["run_number"] in pool_numbers] for cell, recs in history.items()}
    newest = loaded[-1][0] if loaded else {}
    return {"pool": {c: r for c, r in pool.items() if r}, "history": history,
            "runs": [meta for meta, _ in loaded[-POOL_RUNS:]],
            "commit": newest.get("sha", ""), "run": newest.get("run_id", "")}


def fetch(repo: str, out: Path) -> int:
    def get(path: str) -> dict:
        with urllib.request.urlopen(RAW.format(repo=repo, path=path), timeout=30) as resp:
            return json.loads(resp.read())
    try:
        index = get("index.json")
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return 2
        print(f"baseline index: HTTP {err.code}", file=sys.stderr)
        return 3
    except (urllib.error.URLError, OSError, ValueError) as err:
        print(f"baseline index: {err}", file=sys.stderr)
        return 3
    try:
        out.write_text(json.dumps(build(index, get), indent=1))
    except (urllib.error.URLError, OSError, ValueError, KeyError) as err:
        print(f"baseline runs: {err}", file=sys.stderr)
        return 3
    return 0


def regenerate_index(root: Path) -> dict:
    runs = []
    for path in sorted((root / "runs").glob("*.json")):
        data = json.loads(path.read_text())
        runs.append({"run_number": data["run_number"], "run_id": data.get("run_id"), "sha": data.get("sha"),
                     "file": f"runs/{path.name}"})
    index = {"runs": sorted(runs, key=lambda r: r["run_number"])}
    (root / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    return index


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--repo", default="LightconeResearch/agent-skills")
    f.add_argument("--out", default="baseline.json")
    i = sub.add_parser("index")
    i.add_argument("dir")
    args = ap.parse_args()
    if args.cmd == "fetch":
        return fetch(args.repo, Path(args.out))
    regenerate_index(Path(args.dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
