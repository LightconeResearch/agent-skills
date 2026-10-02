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

The baseline is a pool: per cell, the records of the last POOL_RUNS recording
runs (pushes to main). Each summary.json carries the next pool, the baseline's
records plus this run's, oldest dropped, so one artifact is the whole history.

`select` prints the trial dirs worth judging, one per line: every failed trial,
and every trial whose turns or astra/lc calls are outliers against the pooled
baseline median (at least twice it and at least OUTLIER_GAP above it).

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
at least EFFORT_RATIO times the sum of its trials' cell medians. Failures in cells already weak on main are known.
--record (runs on main) gates on the oracle only: main records what is true.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import statistics
import sys
import math
from collections import Counter
from pathlib import Path

MARKER = "<!-- lightcone-smoke-report -->"
OUTLIER_GAP = 5
POOL_RUNS = 5
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


def next_pool(pool: dict | None, trials: list[dict]) -> dict:
    out = {key: list(records) for key, records in (pool or {}).items()}
    by_cell: dict[str, list[dict]] = {}
    for t in trials:
        if t["leg"] != "oracle":
            by_cell.setdefault(f"{t['leg']}/{t['task']}", []).append(t)
    for key, ts in by_cell.items():
        record = {"k": sum(t["passed"] for t in ts), "n": len(ts),
                  "turns": [t["turns"] for t in ts if t["turns"] is not None],
                  "stack_calls": [t["stack_calls"] for t in ts]}
        out[key] = (out.get(key, []) + [record])[-POOL_RUNS:]
    return dict(sorted(out.items()))


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
        owed = k * len(tasks) if tasks and k else len(ok) + len(bad)
        missing = max(owed - len(ok), len(bad))
        total = max(owed, len(ok) + len(bad))
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
            never = missing - len(bad)
            parts = ([f"{len(bad)} hit {why}"] if bad else []) + ([f"{never} never ran"] if never else [])
            reason = (f"{len(bad)}/{total} trials hit {why}" if not never
                      else f"{missing}/{total} trials missing: " + "; ".join(parts))
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
        "pool": next_pool(pool, trials),
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

    # --- PR comment -------------------------------------------------------------
    n_pass = sum(t["passed"] for t in trials if t["leg"] != "oracle")
    n_all = sum(1 for t in trials if t["leg"] != "oracle")
    n_block = len(blocking) + len(blocking_legs) + len(unmeasured_blocking) + len(upstream)
    if n_block:
        head = f"## Plugin smoke: failing ({n_block} blocking)"
    elif warnings or any(e["flag"] for e in effort):
        n_warn = len(warnings) + sum(e["flag"] for e in effort)
        head = f"## Plugin smoke: passing, {n_warn} warning{'s' * (n_warn != 1)}"
    elif any(c["verdict"] in ("known", "new") for c in now.values()):
        head = "## Plugin smoke: passing, with known failures"
    else:
        head = "## Plugin smoke: passing"
    runs = max((b["runs"] for b in bases.values() if b), default=0)
    lines = [MARKER, head, "",
             (f"{n_pass}/{n_all} measured agent trials passed across {len(agent_legs)} legs × {len(tasks)} tasks. "
              if n_all else "No agent trial was measured. ")
             + (f"Baseline: {args.base_label}, pooled over the last {runs} run{'s' * (runs != 1)} on main."
                if pool is not None and args.base_label else
                f"Baseline pooled over the last {runs} run{'s' * (runs != 1)} on main." if pool is not None else
                "No baseline on main yet, so every 0/n cell blocks.")]
    if args.baseline_error:
        lines.append(f"**{args.baseline_error}**")
    if stack:
        lines.append(stack_line() + ".")
    lines.append("")

    for reason in upstream:
        lines.append(f"- **blocking** · {reason}")
    for g in unmeasured:
        lines.append(f"- **{g['state']}** · {g['leg']}: {g['reason']}")
    for e in (e for e in effort if e["flag"]):
        lines.append(f"- **warning** · {e['leg']}: {100 * (e['ratio'] - 1):+.0f}% {e['metric']} vs main "
                     f"across {e['cells_up']}/{e['cells']} cells ({e['above']}/{e['n']} passing trials above "
                     f"their cell's median, p = {e['p']:.3f})")
    for g in blocking_legs:
        lines.append(f"- **blocking** · leg {g['leg']}: {g['x']}/{g['n']} passed, against "
                     f"{g['base_k']}/{g['base_n']} on main (P = {g['tail']:.1e} < {LEG_ALPHA})")
    order = {"blocking": 0, "warning": 1, "new": 2, "known": 3, "pass": 4}
    failures = [t for t in trials if not t["passed"]]
    failures.sort(key=lambda t: (order[now[f"{t['leg']}/{t['task']}"]["verdict"]], t["leg"], t["task"]))
    for t in failures:
        c = now[f"{t['leg']}/{t['task']}"]
        label = {"blocking": "**blocking**", "warning": "**warning**", "new": "failing (no baseline)",
                 "known": "known failure"}[c["verdict"]]
        b = c["base"]
        b_txt = f", main {b['k']}/{b['n']}" if b else ""
        badge = " ".join(f"`{x}`" for x in t["badges"])
        lines.append(f"- {label} · {t['leg']} · **{t['task']}** ({c['k']}/{c['n']}{b_txt}): {outcome(t)}, "
                     f"{fmt(t['turns'])} turns, {t['stack_calls']} astra/lc calls"
                     + (f" — judge: {badge}" if badge else " — judge: no pain points" if t["trial"] in judged else ""))
    if failures or blocking_legs or unmeasured or upstream or any(e["flag"] for e in effort):
        lines.append("")

    if not agent_legs:
        lines.append("No agent leg was planned or run.")
    else:
        head_row = "| task | " + " | ".join(agent_legs) + " |"
        lines += [head_row, "|---" * (len(agent_legs) + 1) + "|"]
        for task in tasks:
            row = []
            for leg in agent_legs:
                c = now.get(f"{leg}/{task}")
                b = c["base"] if c else None
                state = next(g["state"] for g in status if g["leg"] == leg)
                if c:
                    txt = cell_text(c)
                elif state == "not run":
                    txt = "not run"
                elif any(t["leg"] == leg and t["task"] == task for t in infra):
                    txt = "not measured"
                else:
                    txt = "—"
                if c and c["verdict"] in ("blocking", "warning"):
                    txt = f"**{txt}**"
                if b:
                    txt += f" <sub>(main {b['k']}/{b['n']} · {fmt(b['turns'])})</sub>"
                row.append(txt)
            lines.append(f"| {task} | " + " | ".join(row) + " |")
    oracle = [c for c in now.values() if c["leg"] == "oracle"]
    if oracle:
        ok = all(c["verdict"] == "pass" for c in oracle)
        lines += ["", f"Oracle: {'all reference solutions score 1.0' if ok else '**a reference solution failed**'}."]
    if args.judge_note:
        lines += ["", args.judge_note]
    lines += ["", f"Cost of this run: **{money(agent_cost + judge_cost)}** "
              f"(agents {money(agent_cost)}, judge {money(judge_cost)}; the harnesses' API-price estimates)."]

    noted = [t for t in trials if t["trial"] in judged and t["passed"]]  # judged outliers
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
        cls = "ok" if t["passed"] else ("bad" if verdict == "blocking" else "warn")
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
    pool = load_pool(args.baseline) or {}
    for t in collect(jobs):
        if t["leg"] == "oracle" or t["infra"]:
            continue
        if not t["passed"] or is_outlier(t, pooled(pool.get(f"{t['leg']}/{t['task']}"))):
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
