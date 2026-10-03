#!/usr/bin/env python3
"""Summarize, gate and render a plugin smoke run (stdlib only).

    report.py select JOBS [--baseline summary.json]
    report.py render JOBS [--baseline summary.json] [--judge DIR] [--stack stack.json]
                          [--run-url URL] [--base-label TEXT] [--out DIR]
                          [--record] [--judge-failed]

JOBS holds one Harbor job dir per leg (evals/bin/smoke.sh: oracle,
claude-haiku-plugin, ...). A cell is one (leg, task): k of n trials passed,
turns (agent steps) and astra/lc calls (shell commands invoking astra,
astra-tools or lc).

The baseline (--baseline, written by baseline.py fetch) is a pool: per cell,
the records of the last few recorded main runs. Each summary.json carries this
run's own per-cell record, which smoke-publish.yml appends to that log.

`select` prints the trial dirs worth judging, one per line: every failed trial,
and every trial whose turns or astra/lc calls are outliers against the pooled
baseline median (at least twice it and at least OUTLIER_GAP above it); with
--all, every measured agent trial (a pass with friction is a finding too).

`render` writes summary.json, summary.md (the job summary), comment.md (the PR
comment) and report.html into --out, and exits 1 when the gate blocks:
  - an oracle trial scored below 1.0;
  - a cell whose pooled baseline rate is >= STRONG went 0/n;
  - a leg passed improbably few trials against its baseline: P(X <= x) <
    LEG_ALPHA, where x is this run's passes over the leg's baselined cells
    and X sums, per cell, Binomial(this run's attempts, that cell's pooled
    rate smoothed to (s + 1) / (t + 2)) — a Poisson-binomial lower tail, so a
    leg mixing solid and known-failing cells is judged cell by cell, and a
    spotless history does not make a single failure impossible;
  - with no baseline for a cell, it went 0/n.
Trials that died on the harness or the provider (INFRA: quota, rate limit,
auth, setup timeout, ...) are not agent results: they are not judged, not
counted in k/n or the pool, and collapse to one "not measured" line per leg.
A leg that did not run at all (an expected leg, --expect-legs, with no trials)
shows as "not run", with the reason from its <leg>.status file. Either one
blocks: an unmeasured leg must not pass silently.
A version skew or an astra-tools override recorded in --stack blocks. So does any upstream job that
failed (--job name=result, from the workflow's `needs`) when nothing else
already explains the failure: a failed job never renders as passing.
Any failure in a cell with baseline rate >= STRONG that does not block is a
warning, listed first.
Effort (a warning, never a block), per leg and separately for turns and
astra/lc calls: each passing trial is compared with its cell's pooled median.
The leg is flagged when a one-sided sign test over those comparisons gives
P(X >= above | n, 1/2) < EFFORT_ALPHA (ties dropped) and the leg's total is
at least EFFORT_RATIO times the sum of its trials' cell medians.
Failures in cells already weak on main are known.
--record (runs on main) gates on the oracle only: main records what is true.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import statistics
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import report_html  # noqa: E402
import trialview  # noqa: E402
from trialview import leg_label, money, outcome  # noqa: E402

MARKER = "<!-- lightcone-smoke-report -->"
OUTLIER_GAP = 5
# Harbor exception types that mean the harness or the provider failed, not the agent.
INFRA = {
    "ApiUsageLimitError": "provider quota",
    "ApiRateLimitError": "rate limit",
    "ApiOverloadedError": "provider overloaded",
    "ApiInternalServerError": "provider error",
    "UnknownApiError": "provider error",
    "ApiConnectionError": "provider connection",
    "ApiConnectionClosedError": "provider connection",
    "ApiResponseStalledError": "provider stalled",
    "ApiProviderResourceNotFoundError": "model not found",
    "ModelNotFoundError": "model not found",
    "ApiKeyRejectedError": "API key rejected",
    "AgentAuthenticationError": "authentication",
    "AuthenticationError": "authentication",
    "NotAuthenticatedError": "authentication",
    "NetworkConnectionError": "network",
    "AgentSetupTimeoutError": "agent setup timeout",
    "EnvironmentStartTimeoutError": "container start timeout",
    "SandboxBuildFailedError": "image build",
    "HealthcheckError": "container healthcheck",
}
STRONG = 0.8
LEG_ALPHA = 0.01
EFFORT_ALPHA = 0.05
EFFORT_RATIO = 1.25
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
        "infra": exc in INFRA,
        "model": ((result.get("agent_info") or {}).get("model_info") or {}).get("name"),
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


def load_pool(path: str | None) -> dict | None:
    """Cell key -> per-run records {k, n, turns: [...], stack_calls: [...]}, or None."""
    data = load(Path(path)) if path else None
    pool = data.get("pool") if isinstance(data, dict) else None
    return pool if isinstance(pool, dict) else None


def pooled(records: list[dict] | None) -> dict | None:
    if not records:
        return None
    k, n = sum(r["k"] for r in records), sum(r["n"] for r in records)
    return {"k": k, "n": n, "rate": k / n if n else None, "runs": len(records),
            "turns": median(v for r in records for v in r.get("turns", [])),
            "stack_calls": median(v for r in records for v in r.get("stack_calls", []))}


def run_record(trials: list[dict]) -> dict:
    """This run's per-cell {k, n, turns, stack_calls}: what a recorded main run adds to the baseline."""
    by_cell: dict[str, list[dict]] = {}
    for t in trials:
        if t["leg"] != "oracle":
            by_cell.setdefault(f"{t['leg']}/{t['task']}", []).append(t)
    return {key: {"k": sum(t["passed"] for t in ts), "n": len(ts),
                  "turns": [t["turns"] for t in ts if t["turns"] is not None],
                  "stack_calls": [t["stack_calls"] for t in ts]}
            for key, ts in sorted(by_cell.items())}


def binom_cdf(x: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(x + 1))


def verdict(cell: dict, base: dict | None) -> str:
    """pass | blocking | warning | known | new (a partial failure with no baseline)"""
    if cell["k"] == cell["n"]:
        return "pass"
    if cell["leg"] == "oracle":
        return "blocking"
    if base is None or base["rate"] is None:
        return "blocking" if cell["k"] == 0 else "new"
    if base["rate"] >= STRONG:
        return "blocking" if cell["k"] == 0 else "warning"
    return "known"


def poisson_binomial_cdf(x: int, trials: list[tuple[int, float]]) -> float:
    """P(X <= x) for X a sum of independent Binomial(n, p), one per (n, p)."""
    dist = [1.0]  # dist[j] = P(j successes so far)
    for n, p in trials:
        for _ in range(n):
            dist = [a * (1 - p) + b * p for a, b in zip(dist + [0.0], [0.0] + dist)]
    return sum(dist[: x + 1])


def leg_tests(now: dict[str, dict], bases: dict[str, dict | None]) -> list[dict]:
    """Per agent leg: this run's passes against each baselined cell's pooled rate."""
    out = []
    for leg in sorted({c["leg"] for c in now.values()} - {"oracle"}):
        cs = [(c, bases[key]) for key, c in now.items() if c["leg"] == leg and bases[key]]
        if not cs:
            continue
        x, n = sum(c["k"] for c, _ in cs), sum(c["n"] for c, _ in cs)
        s, t = sum(b["k"] for _, b in cs), sum(b["n"] for _, b in cs)
        rates = [(c["n"], (b["k"] + 1) / (b["n"] + 2)) for c, b in cs]
        tail = poisson_binomial_cdf(x, rates)
        out.append({"leg": leg, "x": x, "n": n, "base_k": s, "base_n": t,
                    "expected": sum(n_c * p_c for n_c, p_c in rates),
                    "tail": tail, "blocking": tail < LEG_ALPHA})
    return out


def leg_status(jobs: Path, expected: list[str], trials: list[dict], infra: list[dict],
               not_run_reason: str = "no trials (see the leg's job log)",
               tasks: list[str] | None = None, k: int | None = None) -> list[dict]:
    """Per agent leg: measured, partly measured, not measured (every trial hit INFRA) or not run.

    With `tasks` and `k`, a leg owes k measured trials per task; any shortfall
    (infra errors, or trials that never ran) makes it partly measured.
    """
    out = []
    for leg in sorted(set(expected) | {t["leg"] for t in trials + infra} - {"oracle"}):
        ok = [t for t in trials if t["leg"] == leg]
        bad = [t for t in infra if t["leg"] == leg]
        if tasks and k:  # each planned (leg, task) owes k measured trials; extras elsewhere don't count
            short = {task: max(0, k - sum(t["task"] == task for t in ok)) for task in tasks}
            missing, total = sum(short.values()), k * len(tasks)
        else:
            short, missing, total = {}, len(bad), len(ok) + len(bad)
        kinds = Counter(t["exception"] for t in bad)
        why = ", ".join(f"{e} ({INFRA[e]})" for e, _ in kinds.most_common())
        if not ok and not bad:
            note = jobs / f"{leg}.status"
            state = "not run"
            reason = note.read_text().strip() if note.is_file() else not_run_reason
        elif missing == 0:
            state, reason = "measured", ""
        else:
            state = "not measured" if not ok else "partly measured"
            never = max(0, missing - len(bad))
            parts = ([f"{len(bad)} hit {why}"] if bad else []) + ([f"{never} never ran"] if never else [])
            gaps = ", ".join(f"{task} {k - n}/{k}" for task, n in short.items() if n)
            reason = (f"{len(bad)}/{total} trials hit {why}" if not never
                      else f"{missing}/{total} trials missing: " + "; ".join(parts)
                      + (f" ({gaps})" if gaps else ""))
        out.append({"leg": leg, "state": state, "reason": reason,
                    "measured": len(ok), "infra": len(bad), "missing": missing})
    return out


def effort_tests(trials: list[dict], bases: dict[str, dict | None]) -> list[dict]:
    """Per agent leg and metric: passing trials against their cells' pooled medians."""
    out = []
    for leg in sorted({t["leg"] for t in trials} - {"oracle"}):
        for field, what in (("turns", "turns"), ("stack_calls", "astra/lc calls")):
            rows = []  # (task, this trial's value, the cell's pooled median)
            for t in trials:
                base = bases.get(f"{leg}/{t['task']}")
                if t["leg"] == leg and t["passed"] and t[field] is not None and base and base[field] is not None:
                    rows.append((t["task"], t[field], base[field]))
            above = sum(v > m for _, v, m in rows)
            n = sum(v != m for _, v, m in rows)
            ref = sum(m for _, _, m in rows)
            ratio = sum(v for _, v, _ in rows) / ref if ref else None
            p = 1 - binom_cdf(above - 1, n, 0.5) if above else 1.0
            cell_meds = {task: median(v for t2, v, _ in rows if t2 == task) for task, _, _ in rows}
            cells_up = sum(cell_meds[task] > m for task, m in {(t, m) for t, _, m in rows})
            out.append({"leg": leg, "metric": what, "above": above, "n": n, "p": p, "ratio": ratio,
                        "cells_up": cells_up, "cells": len(cell_meds),
                        "flag": p < EFFORT_ALPHA and ratio is not None and ratio >= EFFORT_RATIO})
    return out


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


def fmt(v, spec="{:.0f}"):
    return "—" if v is None else spec.format(v)


def cell_text(cell: dict | None) -> str:
    if not cell:
        return "—"
    return f"{cell['k']}/{cell['n']} · {fmt(cell['turns'])} turns"


def headline(trials, now, status, upstream, gate) -> str:
    """The verdict in words: what failed or went unmeasured, and how many tasks passed."""
    agent = [t for t in trials if t["leg"] != "oracle"]
    failed = sorted({t["task"] for t in agent if not t["passed"]})
    oracle_bad = sorted({t["task"] for t in trials if t["leg"] == "oracle" and not t["passed"]})
    unmeasured = [g for g in status if g["state"] != "measured"]
    mark = "❌" if gate == "fail" else "⚠️" if failed or unmeasured else "✅"
    tasks = sorted({t["task"] for t in agent})
    passed = sum(1 for task in tasks if all(t["passed"] for t in agent if t["task"] == task))
    count = f" ({passed}/{len(tasks)} tasks passed)" if tasks else ""
    if oracle_bad:
        return f"{mark} oracle failed on {', '.join(oracle_bad)}"
    if upstream:
        return f"{mark} blocked: {upstream[0].split(':', 1)[0]}{count}"
    if failed:
        return f"{mark} {', '.join(failed)} failed{count}"
    if unmeasured:
        return f"{mark} " + ", ".join(f"{g['leg']} {g['state']}" for g in unmeasured) + count
    if not tasks:
        return f"{mark} no agent trial was measured"
    return f"{mark} all {len(tasks)} tasks passed"


def fence(text: str) -> list[str]:
    body = trialview.trim(text) or "(no output)"
    return ["```text", body.replace("```", "ˋˋˋ"), "```"]


def comment_md(m: dict) -> str:
    args, trials, now = m["args"], m["trials"], m["now"]
    agent_legs = m["agent_legs"]
    single = len(agent_legs) == 1
    title = leg_label(agent_legs[0], trials) if single else f"{len(agent_legs)} legs" if agent_legs else "no legs"
    lines = [MARKER, f"## Plugin smoke · {title} · {m['headline']}", ""]
    if not agent_legs:
        lines += ["No agent leg was planned or run.", ""]
    runs = max((b["runs"] for b in m["bases"].values() if b), default=0)
    base = (f"baseline {args.base_label or 'main'} ({runs} run{'s' * (runs != 1)})" if m["pool"] is not None
            else "no baseline yet, so any 0/K cell blocks")
    lines.append(" · ".join(x for x in (m["stack_line"], base) if x) + ".")
    if args.baseline_error:
        lines.append(f"**{args.baseline_error}**")
    lines.append("")

    notes = [f"- **blocking** · {r}" for r in m["upstream"]]
    notes += [f"- **{g['state']}** · {g['leg']}: {g['reason']}" for g in m["unmeasured"]]
    notes += [f"- **blocking** · {g['leg']}: {g['x']}/{g['n']} passed against {g['base_k']}/{g['base_n']} "
              f"on main (P = {g['tail']:.1e})" for g in m["blocking_legs"]]
    notes += [f"- **warning** · {e['leg']}: {100 * (e['ratio'] - 1):+.0f}% {e['metric']} vs main across "
              f"{e['cells_up']}/{e['cells']} cells ({e['above']}/{e['n']} passing trials above their cell's median)"
              for e in m["effort"] if e["flag"]]
    if notes:
        lines += notes + [""]

    order = {"blocking": 0, "warning": 1, "new": 2, "known": 3, "pass": 4}
    failed = [t for t in trials if not t["passed"]]
    failed.sort(key=lambda t: (t["leg"] != "oracle", order[now[f"{t['leg']}/{t['task']}"]["verdict"]], t["task"]))
    for t in failed:
        c = now[f"{t['leg']}/{t['task']}"]
        where = "oracle (reference solution)" if t["leg"] == "oracle" else (
            "" if single else leg_label(t["leg"], trials))
        b = c["base"]
        status_txt = {"blocking": "blocking", "warning": "warning, not blocking", "new": "new, no baseline",
                      "known": "known failure on main"}[c["verdict"]] + (f" (main {b['k']}/{b['n']})" if b else "")
        lines.append(f"### ❌ {t['task']}" + (f" · {where}" if where else "") + f" · {status_txt}")
        lines.append("")
        bad = [ch for ch in t["checks"] if not ch["ok"]]
        if t["exception"]:
            lines.append(f"**Why:** the trial ended in `{t['exception']}`.")
            lines += fence(trialview.exception_text(m["jobs"] / t["dir"]))
        elif bad:
            lines.append("**Why, from the verifier:** " + ", ".join(f"✗ `{ch['name']}`" for ch in bad))
            for ch in bad:
                lines += ["", f"`{ch['name']}`"] + fence(ch["output"])
        else:
            lines.append(f"**Why, from the verifier:** reward {t['reward']}")
            lines += fence(trialview.verifier_stdout(m["jobs"] / t["dir"]))
        j = t["judge"]
        if j:
            lines += ["", "**What happened, from the judge:** " + j.get("summary", "").strip()
                      + ("  " + " ".join(f"`{x}`" for x in t["badges"]) if t["badges"] else "")]
        if t["last_message"] and t["leg"] != "oracle":
            first = [ln.strip() for ln in t["last_message"].splitlines() if ln.strip()][:2]
            last = " / ".join(first)
            lines += ["", f"**The agent's last message:** {last[:280]}{'…' if len(last) > 280 else ''}"]
        nums = [f"{fmt(t['turns'])} turns", f"{t['stack_calls']} astra/lc calls",
                fmt(t["cost_usd"], "${:.3f}")] if t["leg"] != "oracle" else []
        if args.report_url:
            nums.append(f"[card]({args.report_url}#{t['anchor']})")
        if nums:
            lines += ["", " · ".join(nums)]
        lines.append("")

    passing = [t for t in trials if t["passed"] and t["leg"] != "oracle"]
    if passing:
        if failed:
            lines.append("**Passed:**")
        for t in sorted(passing, key=lambda t: (t["leg"], t["task"])):
            b = t["base"]
            delta = f" (main {fmt(b['turns'])})" if b and b.get("turns") is not None else ""
            label = t["task"] if single else f"{t['task']} · {leg_label(t['leg'], trials)}"
            badge = " " + " ".join(f"`{x}`" for x in t["badges"]) if t["badges"] else ""
            lines.append(f"- ✅ {label} · {fmt(t['turns'])} turns{delta}{badge}")
        lines.append("")
    oracle = [t for t in trials if t["leg"] == "oracle"]
    if oracle and all(t["passed"] for t in oracle):
        lines.append(f"Oracle ✓ all {len(oracle)} reference solutions score 1.0.")
    if args.judge_note:
        lines.append(args.judge_note)
    cost = m["agent_cost"] + m["judge_cost"]
    tail = [f"Cost of this run: **{money(cost)}** (agent {money(m['agent_cost'])}, judge {money(m['judge_cost'])})"]
    if args.report_url:
        tail.append(f"[full report]({args.report_url})")
    if args.run_url:
        tail.append(f"[workflow run]({args.run_url})")
    lines += ["", " · ".join(tail) + "."]

    lines += ["", "<details><summary>Every trial</summary>", "",
              "| leg | task | outcome | turns | astra/lc calls | agent min | cost | judge |",
              "|---|---|---|---|---|---|---|---|"]
    for t in sorted(trials, key=lambda t: (t["leg"] != "oracle", t["leg"], t["task"])):
        judge = " ".join(t["badges"]) or ("clean" if t["judge"] else "")
        lines.append(f"| {t['leg']} | {t['task']} | {outcome(t)} | {fmt(t['turns'])} | {t['stack_calls']} "
                     f"| {fmt(t['agent_s'] and t['agent_s'] / 60, '{:.1f}')} | {fmt(t['cost_usd'], '${:.3f}')} "
                     f"| {judge} |")
    lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


def render(args) -> int:
    jobs = Path(args.jobs)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    trials = collect(jobs)
    # An oracle trial is never set aside as infra: the reference solutions must all score.
    infra = [t for t in trials if t["infra"] and t["leg"] != "oracle"]
    trials = [t for t in trials if not (t["infra"] and t["leg"] != "oracle")]
    now = cells(trials)
    expect_tasks = args.expect_tasks.split()
    status = leg_status(jobs, args.expect_legs.split(), trials, infra,
                        args.not_run_reason or "no trials (see the leg's job log)",
                        expect_tasks, args.k)
    pool = load_pool(args.baseline)
    bases = {key: pooled((pool or {}).get(key)) for key in now}
    judged, judge_cost = judge_index(args.judge)
    stack = load(Path(args.stack)) if args.stack else None

    for key, c in now.items():
        c["verdict"] = verdict(c, bases[key])
        c["base"] = bases[key]
    leg_gate = leg_tests(now, bases)
    effort = effort_tests(trials, bases)
    for t in trials:
        t["badges"] = badges(judged.get(t["trial"]))
        t["outlier"] = is_outlier(t, bases.get(f"{t['leg']}/{t['task']}"))
    agent_cost = sum(t["cost_usd"] or 0.0 for t in trials)
    blocking = [c for c in now.values() if c["verdict"] == "blocking"]
    blocking_legs = [g for g in leg_gate if g["blocking"]]
    unmeasured = [g for g in status if g["state"] != "measured"]
    if args.record:  # main records what is true; only the oracle gates there
        blocking = [c for c in blocking if c["leg"] == "oracle"]
        blocking_legs = []
        unmeasured_blocking = []
    else:
        unmeasured_blocking = unmeasured
    warnings = [c for c in now.values() if c["verdict"] == "warning"]
    upstream = []  # blocking reasons that are not cells or legs
    no_oracle = [task for task in expect_tasks
                 if not any(t["leg"] == "oracle" and t["task"] == task for t in trials)]
    if no_oracle:
        upstream.append(f"oracle: no reference run for {', '.join(no_oracle)}")
    if stack and stack.get("skew"):
        upstream.append(f"version skew: {stack['skew']}")
    if stack and stack.get("override"):
        upstream.append(f"override: {stack['override']}")
    failed_jobs = [j.split("=", 1) for j in args.job if j.split("=", 1)[-1] in ("failure", "cancelled")]
    if failed_jobs and not (upstream or blocking or blocking_legs or unmeasured_blocking):
        upstream += [f"the {name} job ended in {result}; see the run log" for name, result in failed_jobs]

    summary = {
        "cells": now,
        "legs": leg_gate,
        "leg_status": status,
        "effort": effort,
        "record": run_record(trials),
        "trials": trials,
        "cost_usd": {"agents": agent_cost, "judge": judge_cost},
        "stack": stack,
        "gate": "fail" if blocking or blocking_legs or unmeasured_blocking or upstream else "pass",
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=1))

    tasks = sorted({t["task"] for t in trials + infra})
    agent_legs = sorted({g["leg"] for g in status})

    def stack_line() -> str:
        if not stack:
            return ""
        return (f"Stack: astra-tools {stack.get('astra_tools')} · lightcone-cli "
                f"{stack.get('lightcone_cli')} · plugin pin astra-tools "
                f"{stack.get('plugin_astra_tools_pin')}")

    # --- what each trial looked like ----------------------------------------------
    for t in trials:
        tdir = jobs / t["dir"]
        t["checks"] = trialview.verifier_checks(tdir, (load(tdir / "result.json") or {}).get(
            "verifier_result", {}).get("rewards") or {}) if (tdir / "result.json").exists() else []
        t["last_message"] = trialview.last_message(tdir)
        t["judge"] = judged.get(t["trial"])
        t["anchor"] = f"{t['leg']}-{t['task']}-{t['trial'].rsplit('__', 1)[-1]}"
        t["base"] = bases.get(f"{t['leg']}/{t['task']}")
    model = {
        "trials": trials, "now": now, "status": status, "pool": pool, "bases": bases,
        "upstream": upstream, "unmeasured": unmeasured, "blocking": blocking,
        "blocking_legs": blocking_legs, "warnings": warnings, "effort": effort,
        "stack": stack, "stack_line": stack_line(), "agent_cost": agent_cost, "judge_cost": judge_cost,
        "gate": summary["gate"], "jobs": jobs, "args": args, "agent_legs": agent_legs, "tasks": tasks,
        "headline": headline(trials, now, status, upstream, summary["gate"]),
    }
    comment = comment_md(model)

    (out / "comment.md").write_text(comment)
    (out / "summary.md").write_text(comment.replace(MARKER + "\n", ""))
    (out / "report.html").write_text(report_html.page(model))

    for c in blocking:
        print(f"::error::smoke {c['leg']} · {c['task']}: {c['k']}/{c['n']}")
    for reason in upstream:
        print(f"::error::smoke {reason}")
    for g in unmeasured:
        print(f"::error::smoke {g['leg']}: {g['state']}: {g['reason']}")
    for g in blocking_legs:
        print(f"::error::smoke leg {g['leg']}: {g['x']}/{g['n']} against {g['base_k']}/{g['base_n']} on main")
    for c in warnings:
        print(f"::warning::smoke {c['leg']} · {c['task']}: {c['k']}/{c['n']}")
    for e in (e for e in effort if e["flag"]):
        print(f"::warning::smoke {e['leg']}: {100 * (e['ratio'] - 1):+.0f}% {e['metric']} vs main")
    return 1 if blocking or blocking_legs or unmeasured_blocking or upstream else 0


def select(args) -> int:
    jobs = Path(args.jobs)
    pool = load_pool(args.baseline) or {}
    for t in collect(jobs):
        if t["leg"] == "oracle" or t["infra"]:
            continue
        if args.all or not t["passed"] or is_outlier(t, pooled(pool.get(f"{t['leg']}/{t['task']}"))):
            print(jobs / t["dir"])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("select", "render"):
        p = sub.add_parser(name)
        p.add_argument("jobs")
        p.add_argument("--baseline")
        if name == "select":
            p.add_argument("--all", action="store_true", help="every measured agent trial, not only failures and outliers")
        if name == "render":
            p.add_argument("--judge")
            p.add_argument("--stack")
            p.add_argument("--run-url", default="")
            p.add_argument("--report-url", default="", help="where the HTML report is published")
            p.add_argument("--base-label", default="")
            p.add_argument("--out", default=".")
            p.add_argument("--record", action="store_true")
            p.add_argument("--judge-note", default="", help="a line for the comment about the judge")
            p.add_argument("--expect-legs", default="", help="space-separated legs the run planned")
            p.add_argument("--baseline-error", default="", help="a line for the comment when the baseline fetch failed")
            p.add_argument("--expect-tasks", default="", help="space-separated task dirs the run planned")
            p.add_argument("--k", type=int, help="attempts each agent leg owes per task")
            p.add_argument("--not-run-reason", default="", help="why a planned leg without trials did not run")
            p.add_argument("--job", action="append", default=[], help="upstream job result, name=result")
    args = ap.parse_args()
    return select(args) if args.cmd == "select" else render(args)


if __name__ == "__main__":
    sys.exit(main())
