#!/usr/bin/env python3
"""Summarize, gate and render a plugin smoke run (stdlib only).

    report.py select JOBS [--baseline summary.json]
    report.py render JOBS [--baseline summary.json] [--judge DIR] [--stack stack.json]
                          [--run-url URL] [--base-label TEXT] [--out DIR]
                          [--record] [--judge-failed]

JOBS holds one Harbor job dir per leg (evals/bin/smoke.sh: oracle,
claude-haiku-plugin, ...). A cell is one (leg, task): k of n trials passed,
median turns (agent steps) and median astra/lc calls (shell commands invoking
astra, astra-tools or lc).

`select` prints the trial dirs worth judging, one per line: every failed trial,
and every trial whose turns or astra/lc calls are outliers against the
baseline cell (at least twice its median and at least OUTLIER_GAP above it).

`render` writes summary.json (the next baseline, when the run is on main),
summary.md (the job summary), comment.md (the PR comment) and report.html into
--out, and exits 1 when the gate fails (--record, for runs on main, renders
without gating the cells: main records what is true, including known failures):
  - any oracle trial scored below 1.0, or
  - a cell is 0/n and the baseline had at least one success there (a
    regression), or there is no baseline for it. A cell already 0/n in the
    baseline is a known failure: shown red, not blocking.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

MARKER = "<!-- lightcone-smoke-report -->"
OUTLIER_GAP = 5
STACK_CALL = re.compile(r"(^|[\s;&|(/])(astra|astra-tools(@[\w.]+)?|lc)\s")
CODEX_CMD = re.compile(r'cmd\s*:\s*"((?:[^"\\]|\\.)*)"')


def load(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def shell_commands(traj) -> list[str]:
    """Every shell command the agent ran, for claude-code and codex trajectories."""
    out = []
    for step in (traj or {}).get("steps", []):
        for call in step.get("tool_calls") or []:
            args = call.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {"command": args}
            if not isinstance(args, dict):
                continue
            if isinstance(args.get("input"), str):  # codex: JS calling tools.exec_command({cmd: "..."})
                for m in CODEX_CMD.findall(args["input"]):
                    try:
                        out.append(json.loads(f'"{m}"').strip())
                    except ValueError:
                        out.append(m.strip())
                continue
            cmd = args.get("command", args.get("cmd"))
            if isinstance(cmd, list):
                cmd = " ".join(map(str, cmd))
            if isinstance(cmd, str):
                out.append(cmd.strip())
    return out


def trial_record(leg: str, tdir: Path, root: Path) -> dict | None:
    result = load(tdir / "result.json")
    if not isinstance(result, dict) or not result.get("trial_name"):
        return None
    traj = load(tdir / "agent" / "trajectory.json")
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    exc = (result.get("exception_info") or {}).get("exception_type")
    cmds = shell_commands(traj)
    steps = (traj or {}).get("steps") or []
    agent_cost = (result.get("agent_result") or {}).get("cost_usd")
    timing = result.get("agent_execution") or {}
    return {
        "leg": leg,
        "task": result.get("task_name", "").removeprefix("lightcone/smoke-"),
        "trial": result["trial_name"],
        "dir": str(tdir.relative_to(root)),
        "reward": rewards.get("reward"),
        "failed_checks": [k for k, v in rewards.items() if k != "reward" and not v],
        "exception": exc,
        "passed": exc is None and (rewards.get("reward") or 0) >= 1.0,
        "turns": sum(1 for s in steps if s.get("source") == "agent") if traj else None,
        "stack_calls": sum(1 for c in cmds if STACK_CALL.search(" " + c + " ")),
        "max_repeat": max(Counter(cmds).values(), default=0),
        "cost_usd": agent_cost if isinstance(agent_cost, (int, float)) else None,
        "agent_s": seconds(timing),
    }


def seconds(block: dict) -> float | None:
    from datetime import datetime
    try:
        a, b = (datetime.fromisoformat(str(block[k]).replace("Z", "+00:00"))
                for k in ("started_at", "finished_at"))
    except (KeyError, TypeError, ValueError):
        return None
    return (b - a).total_seconds()


def collect(jobs: Path) -> list[dict]:
    trials = []
    for job in sorted(p for p in jobs.iterdir() if p.is_dir() and (p / p.name).is_dir()):
        for result in sorted((job / job.name).glob("*/result.json")):
            rec = trial_record(job.name, result.parent, jobs)
            if rec:
                trials.append(rec)
    return trials


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def cells(trials: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for t in trials:
        out.setdefault(f"{t['leg']}/{t['task']}", []).append(t)
    return {key: {
        "leg": ts[0]["leg"], "task": ts[0]["task"], "n": len(ts),
        "k": sum(t["passed"] for t in ts),
        "turns": median(t["turns"] for t in ts),
        "stack_calls": median(t["stack_calls"] for t in ts),
    } for key, ts in sorted(out.items())}


def is_outlier(t: dict, base: dict | None) -> bool:
    if not base:
        return False
    for field in ("turns", "stack_calls"):
        ref, val = base.get(field), t.get(field)
        if ref is not None and val is not None and val >= 2 * ref and val >= ref + OUTLIER_GAP:
            return True
    return False


def baseline_cells(path: str | None) -> dict | None:
    if not path:
        return None
    data = load(Path(path))
    return data.get("cells") if isinstance(data, dict) else None


def judge_index(judge_dir: str | None) -> tuple[dict[str, dict], float]:
    """Trial name -> judge result, and the judge's total cost."""
    if not judge_dir:
        return {}, 0.0
    index, cost = {}, 0.0
    for path in Path(judge_dir).glob("**/analysis.json"):
        for res in (load(path) or {}).get("results", []):
            cost += res.get("cost_usd") or 0.0
            if res.get("trial_name") and res.get("summary") and not res.get("error"):
                index[res["trial_name"]] = res
    return index, cost


def badges(judge: dict | None) -> list[str]:
    return [k for k, v in ((judge or {}).get("checks") or {}).items() if v.get("outcome") == "fail"]


def verdict(cell: dict, base: dict | None, have_baseline: bool) -> str:
    """pass | flaky | regressed | known | new-fail"""
    if cell["leg"] == "oracle":
        return "pass" if cell["k"] == cell["n"] else "regressed"
    if cell["k"] == cell["n"]:
        return "pass"
    if cell["k"] > 0:
        return "flaky"
    if base is None:
        return "new-fail"  # no baseline cell: blocking (with no baseline at all, every 0/n blocks)
    return "regressed" if base["k"] > 0 else "known"


BLOCKING = {"regressed", "new-fail"}


def outcome(t: dict) -> str:
    if t["exception"]:
        return f"error: {t['exception']}"
    if t["reward"] is None:
        return "unscored"
    if t["passed"]:
        return "pass"
    return f"fail {t['reward']:.2f} ({', '.join(t['failed_checks']) or 'reward'})"


def fmt(v, spec="{:.0f}"):
    return "—" if v is None else spec.format(v)


def money(v):
    return f"${v:.2f}" if v >= 0.1 else f"${v:.3f}"


def cell_text(cell: dict | None) -> str:
    if not cell:
        return "—"
    return f"{cell['k']}/{cell['n']} · {fmt(cell['turns'])} turns"


def render(args) -> int:
    jobs = Path(args.jobs)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    trials = collect(jobs)
    now = cells(trials)
    base = baseline_cells(args.baseline)
    judged, judge_cost = judge_index(args.judge)
    stack = load(Path(args.stack)) if args.stack else None

    for c in now.values():
        c["verdict"] = verdict(c, (base or {}).get(f"{c['leg']}/{c['task']}"), base is not None)
    for t in trials:
        t["badges"] = badges(judged.get(t["trial"]))
        t["outlier"] = is_outlier(t, (base or {}).get(f"{t['leg']}/{t['task']}"))
    agent_cost = sum(t["cost_usd"] or 0.0 for t in trials)
    blocking = [c for c in now.values() if c["verdict"] in BLOCKING]

    summary = {
        "cells": now,
        "trials": trials,
        "cost_usd": {"agents": agent_cost, "judge": judge_cost},
        "stack": stack,
        "gate": "fail" if blocking else "pass",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1))

    legs = sorted({c["leg"] for c in now.values()}, key=lambda leg: (leg != "oracle", leg))
    tasks = sorted({c["task"] for c in now.values()})
    agent_legs = [leg for leg in legs if leg != "oracle"]

    def stack_line() -> str:
        if not stack:
            return ""
        return (f"Stack: astra-tools {stack.get('astra_tools')} · lightcone-cli "
                f"{stack.get('lightcone_cli')} · plugin pin astra-tools "
                f"{stack.get('plugin_astra_tools_pin')}")

    # --- PR comment -------------------------------------------------------------
    n_pass = sum(t["passed"] for t in trials if t["leg"] != "oracle")
    n_all = sum(1 for t in trials if t["leg"] != "oracle")
    if blocking:
        head = f"## Plugin smoke: failing ({len(blocking)} blocking cell{'s' * (len(blocking) != 1)})"
    elif any(c["verdict"] in ("known", "flaky") for c in now.values()):
        head = "## Plugin smoke: passing, with known or flaky failures"
    else:
        head = "## Plugin smoke: passing"
    lines = [MARKER, head, "",
             f"{n_pass}/{n_all} agent trials passed across {len(agent_legs)} legs × {len(tasks)} tasks."
             + (f" Baseline: {args.base_label}." if base is not None and args.base_label else
                " No baseline on main yet, so every 0/n cell blocks." if base is None else "")]
    if stack:
        lines.append(stack_line() + ".")
    lines.append("")

    failures = [t for t in trials if not t["passed"]]
    order = {"regressed": 0, "new-fail": 1, "known": 2, "flaky": 3, "pass": 4}
    failures.sort(key=lambda t: (order[now[f"{t['leg']}/{t['task']}"]["verdict"]], t["leg"], t["task"]))
    if failures:
        lines += ["### Failures", ""]
        for t in failures:
            v = now[f"{t['leg']}/{t['task']}"]["verdict"]
            label = {"regressed": "**regressed**", "new-fail": "**failing**",
                     "known": "known failure", "flaky": "flaky"}[v]
            b = " ".join(f"`{x}`" for x in t["badges"])
            lines.append(f"- {label} · {t['leg']} · **{t['task']}**: {outcome(t)}, "
                         f"{fmt(t['turns'])} turns, {t['stack_calls']} astra/lc calls"
                         + (f" — judge: {b}" if b else " — judge: no pain points" if t["trial"] in judged else ""))
        lines.append("")

    head_row = "| task | " + " | ".join(agent_legs) + " |"
    lines += [head_row, "|---" * (len(agent_legs) + 1) + "|"]
    for task in tasks:
        row = []
        for leg in agent_legs:
            c = now.get(f"{leg}/{task}")
            b = (base or {}).get(f"{leg}/{task}")
            txt = cell_text(c)
            if c and c["verdict"] in BLOCKING | {"known"}:
                txt = f"**{txt}**"
            if b:
                txt += f" <sub>(main {b['k']}/{b['n']} · {fmt(b['turns'])})</sub>"
            row.append(txt)
        lines.append(f"| {task} | " + " | ".join(row) + " |")
    oracle = [c for c in now.values() if c["leg"] == "oracle"]
    if oracle:
        ok = all(c["verdict"] == "pass" for c in oracle)
        lines += ["", f"Oracle: {'all reference solutions score 1.0' if ok else '**a reference solution failed**'}."]
    if args.judge_failed:
        lines += ["", "**The judge did not run to completion**; failures above carry no judge notes. See the run log."]
    lines += ["", f"Cost of this run: **{money(agent_cost + judge_cost)}** "
              f"(agents {money(agent_cost)}, judge {money(judge_cost)}; the harnesses' API-price estimates)."]

    noted = [t for t in trials if t["trial"] in judged and (t["passed"] or t["badges"])]
    lines += ["", "<details><summary>Per-trial detail and judge notes</summary>", "",
              "| leg | task | outcome | turns | astra/lc calls | max repeat | agent min | cost | judge |",
              "|---|---|---|---|---|---|---|---|---|"]
    for t in sorted(trials, key=lambda t: (t["leg"] != "oracle", t["leg"], t["task"])):
        judge = " ".join(t["badges"]) or ("clean" if t["trial"] in judged else "")
        if t["outlier"]:
            judge = ("outlier; " + judge).strip("; ")
        lines.append(f"| {t['leg']} | {t['task']} | {outcome(t)} | {fmt(t['turns'])} | {t['stack_calls']} "
                     f"| {t['max_repeat']} | {fmt(t['agent_s'] and t['agent_s'] / 60, '{:.1f}')} "
                     f"| {fmt(t['cost_usd'], '${:.3f}')} | {judge} |")
    for t in failures + noted:
        j = judged.get(t["trial"])
        if not j:
            continue
        lines += ["", f"**{t['leg']} · {t['task']}** ({outcome(t)})", "", j.get("summary", "").strip()]
        for b in t["badges"]:
            lines.append(f"- `{b}`: {j['checks'][b].get('explanation', '').strip()}")
    lines += ["", "</details>"]
    if args.run_url:
        lines += ["", f"Trajectories, verifier logs and the HTML report: [workflow run]({args.run_url})."]
    comment = "\n".join(lines) + "\n"
    (out / "comment.md").write_text(comment)
    (out / "summary.md").write_text(comment.replace(MARKER + "\n", ""))
    (out / "report.html").write_text(html_page(trials, now, judged, stack_line(), agent_cost, judge_cost))

    for c in blocking:
        print(f"::error::smoke {c['leg']} · {c['task']}: {c['k']}/{c['n']} ({c['verdict']})")
    if args.record:
        return 1 if any(c["leg"] == "oracle" for c in blocking) else 0
    return 1 if blocking else 0


def html_page(trials, now, judged, stack_line, agent_cost, judge_cost) -> str:
    rows = []
    for t in sorted(trials, key=lambda t: (t["task"], t["leg"] != "oracle", t["leg"])):
        j = judged.get(t["trial"])
        chips = "".join(f'<span class="chip">{html.escape(b)}</span>' for b in t["badges"])
        if t["outlier"]:
            chips = '<span class="chip">outlier</span>' + chips
        detail = ""
        if j:
            checks = "".join(
                f"<li><b>{html.escape(k)}</b> <i>{html.escape(v.get('outcome', ''))}</i> — "
                f"{html.escape(v.get('explanation', ''))}</li>" for k, v in (j.get("checks") or {}).items())
            detail = (f"<details><summary>judge</summary><p>{html.escape(j.get('summary', ''))}</p>"
                      f"<ul>{checks}</ul></details>")
        verdict = now[f"{t['leg']}/{t['task']}"]["verdict"]
        cls = "ok" if t["passed"] else ("warn" if verdict in ("known", "flaky") else "bad")
        rows.append(
            f"<tr><td>{html.escape(t['task'])}</td><td>{html.escape(t['leg'])}</td>"
            f"<td class='{cls}'>{html.escape(outcome(t))}</td><td>{fmt(t['turns'])}</td>"
            f"<td>{t['stack_calls']}</td><td>{t['max_repeat']}</td>"
            f"<td>{fmt(t['cost_usd'], '${:.3f}')}</td><td>{chips}{detail}</td></tr>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Plugin smoke report</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--mute:#6b6a65;--line:#e4e1d9;--bad:#b3261e;--warn:#8a5a00;--ok:#2e6b3a;--chip:#f3e2dc}}
@media (prefers-color-scheme: dark){{:root{{--bg:#191917;--fg:#ecebe6;--mute:#a19f97;--line:#36352f;--bad:#ff8a80;--warn:#f2c46d;--ok:#8fd19e;--chip:#4a2b26}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0 auto;padding:16px;max-width:1200px}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left}}
.ok{{color:var(--ok)}}.bad{{color:var(--bad);font-weight:600}}.warn{{color:var(--warn)}}small,.mute{{color:var(--mute)}}
.chip{{display:inline-block;background:var(--chip);border-radius:9px;padding:1px 8px;margin:0 4px 4px 0;font-size:12px}}
details p,details li{{font-size:13px}}.wrap{{overflow-x:auto}}
</style></head><body><h1>Plugin smoke report</h1>
<p class="mute">{html.escape(stack_line)}. Cost: agents {money(agent_cost)}, judge {money(judge_cost)}.
Chips are pain points the judge (evals/rubrics/pain-points.toml) found; only failed and outlier trials are judged.</p>
<div class="wrap"><table><tr><th>task</th><th>leg</th><th>outcome</th><th>turns</th><th>astra/lc calls</th>
<th>max repeat</th><th>cost</th><th>judge</th></tr>{''.join(rows)}</table></div></body></html>"""


def select(args) -> int:
    jobs = Path(args.jobs)
    base = baseline_cells(args.baseline) or {}
    for t in collect(jobs):
        if t["leg"] == "oracle":
            continue
        if not t["passed"] or is_outlier(t, base.get(f"{t['leg']}/{t['task']}")):
            print(jobs / t["dir"])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("select", "render"):
        p = sub.add_parser(name)
        p.add_argument("jobs")
        p.add_argument("--baseline")
        if name == "render":
            p.add_argument("--judge")
            p.add_argument("--stack")
            p.add_argument("--run-url", default="")
            p.add_argument("--base-label", default="")
            p.add_argument("--out", default=".")
            p.add_argument("--record", action="store_true")
            p.add_argument("--judge-failed", action="store_true")
    args = ap.parse_args()
    return select(args) if args.cmd == "select" else render(args)


if __name__ == "__main__":
    sys.exit(main())
