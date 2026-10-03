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
import json
import re
import statistics
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trialview  # noqa: E402
import view  # noqa: E402
from trialview import leg_label  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

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
            if res.get("trial_name") and res.get("error"):
                index.setdefault(res["trial_name"], {"error": res["error"]})
            elif res.get("trial_name") and res.get("summary") is not None:
                index[res["trial_name"]] = res
    return index, cost


def badges(judge: dict | None) -> list[str]:
    return [k for k, v in ((judge or {}).get("checks") or {}).items() if v.get("outcome") == "fail"]


def fmt(v, spec="{:.0f}"):
    return "—" if v is None else spec.format(v)


# --- reasons: the deterministic floor -----------------------------------------------
#
# Every reason the run can fail or warn for, in one place. Each class turns data
# into a terse headline of facts (no explanatory prose) and, only for the
# classes whose remedy is mechanical (skew, override, missing key), a fix. The
# judge's ranked pain points render separately, attributed. Order matters: the
# first blocking reason, most root-cause first, becomes the verdict.

ORDER = ("skew", "override", "oracle_red", "no_oracle", "key_missing", "not_run", "infra", "coverage_gap",
         "agent_check", "leg_test", "upstream_job", "effort", "baseline_error")


def pin_line(tool: str) -> int | None:
    """The line of a tool's pin in skills.config.json, for annotations."""
    try:
        for i, line in enumerate((ROOT / "skills.config.json").read_text().splitlines(), 1):
            if re.search(rf'"{re.escape(tool)}"\s*:\s*"', line):
                return i
    except OSError:
        pass
    return None


def marks(checks: list[str]) -> str:
    return " ".join(f"{c} ✗" for c in checks)


def reason(cls: str, **d) -> dict:
    """One reason, rendered from its class template and the data d."""
    r = {"class": cls, "blocking": d.get("blocking", True), "headline": "", "fix": "",
         "annotation": None, "data": {k: v for k, v in d.items() if k != "blocking"}}
    if cls == "skew":
        pin, req, lc = d["pin"], d["required"], d["lightcone_cli"]
        exact = re.fullmatch(r"==\s*([\w.+-]+)", req)
        line = pin_line("astra-tools")
        r["headline"] = f"version skew · lightcone-cli {lc} requires astra-tools {req} · plugin pins {pin}"
        target = f'"astra-tools": "{exact.group(1)}"' if exact else f"an astra-tools satisfying {req}"
        r["fix"] = (f"`{target}` in `skills.config.json`" + (f":{line}" if line else "")
                    + f", or a lightcone-cli that accepts {pin}; then `npm run build`")
        r["annotation"] = {"file": "skills.config.json", "line": line, "title": "smoke: version skew"}
    elif cls == "override":
        r["headline"] = (f"override · lightcone-cli {d['lightcone_cli']} requires astra-tools {d['required']} "
                         f"· testing astra-tools {d['installed']}")
        r["fix"] = f"widen lightcone-cli's astra-tools requirement to accept {d['installed']} before releasing"
    elif cls == "oracle_red":
        r["headline"] = (f"reference solution · {d['task']} · {marks(d['checks'])}"
                         + (f" · “{d['error']}”" if d.get("error") else ""))
        r["annotation"] = {"file": d.get("solution"), "line": None, "title": "smoke: reference solution fails"}
    elif cls == "no_oracle":
        r["headline"] = f"no reference run · {', '.join(d['tasks'])}"
    elif cls == "key_missing":
        r["headline"] = f"not run · {d['label']} · {d['key']} not set"
        r["fix"] = f"add the {d['key']} repository secret (forks never receive secrets)"
    elif cls == "not_run":
        r["headline"] = f"not run · {d['label']} · {d['reason']}"
    elif cls == "infra":
        r["headline"] = (f"not measured · {d['label']} · {d['infra']}/{d['total']} "
                         + ", ".join(d["kinds"]))
    elif cls == "coverage_gap":
        r["headline"] = f"partly measured · {d['label']} · {d['reason']}"
    elif cls == "agent_check":
        what = marks(d["checks"]) if d["checks"] else "failed"
        if d.get("exception"):
            what = d["exception"]
        r["headline"] = f"{d['task']} · {what}" + (f" · “{d['error']}”" if d.get("error") else "")
        if d.get("contradiction"):
            r["headline"] += f" · {d['contradiction']}"
        base = d.get("base")
        r["headline"] += f" · {d['k']}/{d['n']}" + (f" (main {base['k']}/{base['n']})" if base else "")
        r["blocking"] = d["verdict"] == "blocking"
    elif cls == "leg_test":
        r["headline"] = (f"leg test · {d['label']} · {d['x']}/{d['n']} vs {d['base_k']}/{d['base_n']} on main "
                         f"· P = {d['tail']:.1e}")
    elif cls == "upstream_job":
        r["headline"] = f"{d['job']} job · {d['result']}"
    elif cls == "effort":
        r["headline"] = (f"effort · {d['label']} · {100 * (d['ratio'] - 1):+.0f}% {d['metric']} · "
                         f"{d['cells_up']}/{d['cells']} tasks above main · p = {d['p']:.3f}")
        r["blocking"] = False
    elif cls == "baseline_error":
        r["headline"] = "baseline · fetch failed · gating as if none"
        r["blocking"] = False
    return r


def contradiction(rows: list[dict]) -> str:
    """The first contradicted hook claim, as terse data for a headline."""
    for row in rows:
        if row.get("contradicted"):
            if "itself" in row["contradicted"]:
                return f"{row['name']} said FAILED · its output says passed"
            return f"{row['name']} said {'pass' if row['claim'] == 'pass' else 'FAILED'} · contradicted"
    return ""


# --- the summary: everything the comment and the report render from ----------------

def parse_judge(j: dict | None) -> dict | None:
    """The judge's ranked pain points: [{badge, point, evidence, step}], most important first.

    The rubric prompt has the judge write its summary as a JSON array; anything
    else is kept as one unbadged item, marked unparsed, rather than dropped.
    """
    if not j:
        return None
    if j.get("error"):
        return {"items": [], "error": "the judge produced no valid result for this trial", "badges": [],
                "checks": {}, "cost_usd": None}
    text = (j.get("summary") or "").strip()
    try:
        raw = json.loads(text) if text.startswith("[") else None
    except ValueError:
        raw = None
    if isinstance(raw, list):
        items = [{"badge": str(i.get("badge") or ""), "point": str(i.get("point") or "").strip(),
                  "evidence": str(i.get("evidence") or "")} for i in raw if isinstance(i, dict) and i.get("point")]
    else:
        items = [{"badge": "", "point": text, "evidence": "", "unparsed": True}] if text else []
    for item in items:
        m = re.search(r"step\s+(\d+)", item["evidence"])
        item["step"] = int(m.group(1)) if m else None
    ranked = list(dict.fromkeys(i["badge"] for i in items if i["badge"]))
    return {"items": items, "badges": ranked if isinstance(raw, list) else badges(j),
            "checks": j.get("checks") or {}, "cost_usd": j.get("cost_usd")}


def trial_view(t: dict, jobs: Path, judged: dict, bases: dict) -> dict:
    tdir = jobs / t["dir"]
    result = load(tdir / "result.json") or {}
    rewards = (result.get("verifier_result") or {}).get("rewards") or {}
    meta = trialview.task_meta(t["task"])
    checks = trialview.verifier_checks(tdir, rewards)
    for c in checks:
        c["desc"] = meta["checks"].get(c["name"], "")
        c["output"] = trialview.trim(c["output"], 60)
        c["first_error"] = "" if c["ok"] else trialview.first_error_line(c["output"])
    rows = trialview.timeline(tdir, checks) if t["leg"] != "oracle" else []
    view = {k: t[k] for k in ("leg", "task", "trial", "model", "passed", "reward", "failed_checks", "exception",
                              "turns", "stack_calls", "max_repeat", "cost_usd", "agent_s")}
    view.update({
        "anchor": f"{t['leg']}-{t['task']}-{t['trial'].rsplit('__', 1)[-1]}",
        "label": "reference solution" if t["leg"] == "oracle" else None,
        "checks": checks,
        "stdout": trialview.trim(trialview.verifier_stdout(tdir), 60),
        "exception_text": trialview.trim(trialview.exception_text(tdir), 40),
        "deliverable": trialview.deliverable(tdir, t["task"], checks),
        "timeline": rows,
        "last_message": trialview.last_message(tdir),
        "contradiction": contradiction(rows),
        "judge": parse_judge(judged.get(t["trial"])),
        "outlier": t.get("outlier", False),
        "base": bases.get(f"{t['leg']}/{t['task']}"),
    })
    return view


def chain(stack, reasons_, oracle_trials, agent_trials, status, judge_info, legs) -> list[dict]:
    classes = {r["class"] for r in reasons_ if r["blocking"]}
    links = []
    if stack:
        links.append({"key": "stack", "title": "Stack", "state": "ok", "value": "built",
                      "sub": f"astra-tools {stack.get('astra_tools')} · lightcone-cli {stack.get('lightcone_cli')}"})
    else:
        links.append({"key": "stack", "title": "Stack", "state": "skip", "value": "unknown", "sub": "no stack.json"})
    if not stack:
        links.append({"key": "version", "title": "Version check", "state": "skip", "value": "not run", "sub": ""})
    elif stack.get("skew") or stack.get("override"):
        req = stack.get("lightcone_cli_requires_astra_tools")
        links.append({"key": "version", "title": "Version check", "state": "bad",
                      "value": "skew" if stack.get("skew") else "override",
                      "sub": f"lc needs {req}; " + (f"plugin pins {stack.get('plugin_astra_tools_pin')}"
                                                     if stack.get("skew") else f"testing {stack.get('astra_tools')}")})
    else:
        links.append({"key": "version", "title": "Version check", "state": "ok", "value": "consistent",
                      "sub": f"lc needs {stack.get('lightcone_cli_requires_astra_tools') or 'any'}; "
                             f"plugin pins {stack.get('plugin_astra_tools_pin')}"})
    if oracle_trials:
        tasks = sorted({t["task"] for t in oracle_trials})
        bad = sorted({t["task"] for t in oracle_trials if not t["passed"]})
        n_checks = sum(len(t["checks"]) for t in oracle_trials)
        ok_checks = sum(c["ok"] for t in oracle_trials for c in t["checks"])
        links.append({"key": "oracle", "title": "Reference solutions",
                      "state": "bad" if bad or "no_oracle" in classes else "ok",
                      "value": f"{len(tasks) - len(bad)} / {len(tasks)} tasks",
                      "sub": f"{', '.join(bad)} fails" if bad else f"{ok_checks} / {n_checks} checks pass"})
    else:
        links.append({"key": "oracle", "title": "Reference solutions", "state": "skip", "value": "not run",
                      "sub": ""})
    blocker = ("the version check" if links[1]["state"] == "bad"
               else "the reference solutions" if links[2]["state"] == "bad" else "")
    measured = [g for g in status if g["state"] in ("measured", "partly measured")]
    if agent_trials:
        tasks = sorted({t["task"] for t in agent_trials})
        passed = [task for task in tasks if all(t["passed"] for t in agent_trials if t["task"] == task)]
        state = "ok" if len(passed) == len(tasks) and len(measured) == len(status) else "bad"
        links.append({"key": "agent", "title": "Agent", "state": state,
                      "value": f"{len(passed)} / {len(tasks)} tasks",
                      "sub": ", ".join(leg_label(g["leg"], agent_trials) for g in status) if status else ""})
    else:
        why = next((g["reason"] for g in status if g["state"] == "not run"), "")
        if blocker and (not why or why == "oracle failed"):
            why = f"blocked by {blocker}"
        links.append({"key": "agent", "title": "Agent", "state": "skip" if not status or why else "bad",
                      "value": "not run" if not any(g["state"] == "not measured" for g in status) else "not measured",
                      "sub": why or "no agent leg planned"})
    if judge_info["ran"]:
        n = judge_info["pain_points"]
        links.append({"key": "judge", "title": "Judge", "state": "warn" if n else "ok",
                      "value": f"{n} pain point{'s' * (n != 1)}" if n else "no pain points",
                      "sub": " · ".join(judge_info["badges"]) or f"{judge_info['judged']} trials read"})
    else:
        links.append({"key": "judge", "title": "Judge", "state": "skip", "value": "not run",
                      "sub": judge_info["reason"]})
    return links


def build_summary(args) -> dict:
    jobs = Path(args.jobs)
    trials = collect(jobs)
    # An oracle trial is never set aside as infra: the reference solutions must all score.
    infra = [t for t in trials if t["infra"] and t["leg"] != "oracle"]
    trials = [t for t in trials if not (t["infra"] and t["leg"] != "oracle")]
    now = cells(trials)
    expect_tasks = args.expect_tasks.split()
    status = leg_status(jobs, args.expect_legs.split(), trials, infra,
                        args.not_run_reason or "no trials (see the leg's job log)", expect_tasks, args.k)
    base_doc = load(Path(args.baseline)) if args.baseline else None
    pool = load_pool(args.baseline)
    history = (base_doc or {}).get("history") or pool or {}
    bases = {key: pooled((pool or {}).get(key)) for key in now}
    judged, _ = judge_index(args.judge)
    names = {t["trial"] for t in trials}
    judged = {k: v for k, v in judged.items() if k in names}  # a shared judge dir may hold other runs
    judge_cost = sum(v.get("cost_usd") or 0.0 for v in judged.values())
    stack = load(Path(args.stack)) if args.stack else None
    for key, c in now.items():
        c["verdict"] = verdict(c, bases[key])
        c["base"] = bases[key]
    leg_gate = leg_tests(now, bases)
    effort = effort_tests(trials, bases)
    for t in trials:
        t["badges"] = badges(judged.get(t["trial"]))
        t["outlier"] = is_outlier(t, bases.get(f"{t['leg']}/{t['task']}"))
    views = []
    for t in trials:  # one unreadable trial must not take the whole report down
        try:
            views.append(trial_view(t, jobs, judged, bases))
        except Exception as err:  # noqa: BLE001
            v = {k: t.get(k) for k in ("leg", "task", "trial", "model", "passed", "reward", "failed_checks",
                                       "exception", "turns", "stack_calls", "max_repeat", "cost_usd", "agent_s")}
            v.update({"anchor": f"{t['leg']}-{t['task']}-{t['trial'].rsplit('__', 1)[-1]}", "label": None,
                      "checks": [], "stdout": f"report could not read this trial: {type(err).__name__}: {err}",
                      "exception_text": "", "deliverable": None, "timeline": [], "last_message": "",
                      "contradiction": "", "judge": None, "outlier": False, "base": None})
            views.append(v)
    for v in views:
        if v["leg"] != "oracle":
            v["label"] = leg_label(v["leg"], trials)
    oracle_views = [v for v in views if v["leg"] == "oracle"]
    agent_views = [v for v in views if v["leg"] != "oracle"]

    rs = []
    if stack and stack.get("skew"):
        rs.append(reason("skew", pin=stack.get("plugin_astra_tools_pin"),
                         required=stack.get("lightcone_cli_requires_astra_tools"),
                         lightcone_cli=stack.get("lightcone_cli")))
    if stack and stack.get("override"):
        rs.append(reason("override", lightcone_cli=stack.get("lightcone_cli"),
                         required=stack.get("lightcone_cli_requires_astra_tools"), installed=stack.get("astra_tools")))
    for v in oracle_views:
        if not v["passed"]:
            bad = [c["name"] for c in v["checks"] if not c["ok"]] or [v["exception"] or "reward"]
            err = next((c["first_error"] for c in v["checks"] if not c["ok"] and c["first_error"]), "")
            sol = next((f"evals/smoke/{v['task']}/{p}" for p in ("solution/astra.yaml", "solution/solve.sh")
                        if (trialview.TASKS_DIR / v["task"] / p).is_file()), None)
            rs.append(reason("oracle_red", task=v["task"], checks=bad, error=err, solution=sol,
                             astra=(stack or {}).get("astra_tools", "?"), lc=(stack or {}).get("lightcone_cli", "?")))
    no_oracle = [task for task in expect_tasks if not any(v["task"] == task for v in oracle_views)]
    if no_oracle:
        rs.append(reason("no_oracle", tasks=no_oracle))
    keys = {"codex": "OPENAI_API_KEY"}
    for g in status:
        label = leg_label(g["leg"], trials)
        key = keys.get(g["leg"].split("-", 1)[0], "ANTHROPIC_API_KEY")
        if g["state"] == "not run" and "not set" in g["reason"]:
            rs.append(reason("key_missing", leg=g["leg"], label=label, key=g["reason"].split()[0]))
        elif g["state"] == "not measured" or (g["state"] == "partly measured" and g["infra"]):
            kinds = [e for e, _ in Counter(t["exception"] for t in infra if t["leg"] == g["leg"]).most_common()]
            if g["state"] == "not measured" or not g["missing"] > g["infra"]:
                rs.append(reason("infra", leg=g["leg"], label=label, kinds=kinds, infra=g["infra"],
                                 total=g["infra"] + g["measured"], key=key))
            else:
                rs.append(reason("coverage_gap", leg=g["leg"], label=label, reason=g["reason"]))
        elif g["state"] == "partly measured":
            rs.append(reason("coverage_gap", leg=g["leg"], label=label, reason=g["reason"]))
        elif g["state"] == "not run":  # a planned leg with no trials blocks, whatever else reported success
            rs.append(reason("not_run", leg=g["leg"], label=label, reason=g["reason"]))
    for key, c in now.items():
        if c["leg"] == "oracle" or c["verdict"] == "pass":
            continue
        failing = [v for v in agent_views if f"{v['leg']}/{v['task']}" == key and not v["passed"]]
        first = failing[0]
        bad = [ch["name"] for ch in first["checks"] if not ch["ok"]]
        err = next((ch["first_error"] for ch in first["checks"] if not ch["ok"] and ch["first_error"]), "")
        rs.append(reason("agent_check", task=c["task"], leg=c["leg"], checks=bad, error=err,
                         exception=first["exception"], contradiction=first["contradiction"],
                         verdict=c["verdict"], k=c["k"], n=c["n"], base=c["base"], anchor=first["anchor"]))
    for g in leg_gate:
        if g["blocking"]:
            rs.append(reason("leg_test", label=leg_label(g["leg"], trials), **{k: g[k] for k in
                             ("x", "n", "base_k", "base_n", "tail")}))
    for e in effort:
        if e["flag"]:
            rs.append(reason("effort", label=leg_label(e["leg"], trials), **{k: e[k] for k in
                             ("metric", "ratio", "cells_up", "cells", "above", "n", "p")}))
    if args.baseline_error:
        rs.append(reason("baseline_error"))
    if args.record:  # main records what is true; only the oracle and the stack gate there
        for r in rs:
            if r["class"] not in ("skew", "override", "oracle_red", "no_oracle"):
                r["blocking"] = False
    failed_jobs = [j.split("=", 1) for j in args.job if j.split("=", 1)[-1] in ("failure", "cancelled")]
    if failed_jobs and not any(r["blocking"] for r in rs):
        rs += [reason("upstream_job", job=name, result=result) for name, result in failed_jobs]
    rs.sort(key=lambda r: (not r["blocking"], ORDER.index(r["class"])))

    judge_reason = args.judge_not_run or ("nothing to read: the agent did not run" if not agent_views else "")
    judged_views = [v for v in agent_views if v["judge"] and not v["judge"].get("error")]
    judge_info = {"ran": bool(judged_views), "reason": "" if judged_views else (judge_reason or "not run"),
                  "judged": len(judged_views), "cost_usd": judge_cost,
                  "badges": sorted({b for v in judged_views for b in v["judge"]["badges"]}),
                  "pain_points": sum(len(v["judge"]["items"]) for v in judged_views)}

    blocking = [r for r in rs if r["blocking"]]
    gate = "fail" if blocking else "pass"
    agent_cost = sum(v["cost_usd"] or 0.0 for v in agent_views)
    task_names = sorted({t["task"] for t in trials + infra} | set(expect_tasks))
    default_leg = next((g["leg"] for g in status), None)
    tasks = []
    for name in task_names:
        meta = trialview.task_meta(name)
        ref = [v for v in oracle_views if v["task"] == name]
        tasks.append({
            "name": name, "proves": meta["proves"], "had_to": meta["had_to"],
            "instruction": trialview.instruction(name),
            "reference": {"passed": all(v["passed"] for v in ref) if ref else None,
                          "checks": [{"name": c["name"], "ok": c["ok"]} for c in ref[0]["checks"]] if ref else [],
                          "anchor": ref[0]["anchor"] if ref else None},
            "agent": {g["leg"]: {"state": g["state"],
                                 "trials": [{"anchor": v["anchor"], "passed": v["passed"], "turns": v["turns"]}
                                            for v in agent_views if v["leg"] == g["leg"] and v["task"] == name],
                                 "infra": sum(1 for t in infra if t["leg"] == g["leg"] and t["task"] == name)}
                      for g in status},
            "history": [{"k": r["k"], "n": r["n"]} for r in history.get(f"{default_leg}/{name}", [])][-10:]
                       if default_leg else [],
        })

    top = blocking[0] if blocking else None
    state = "fail" if blocking else ("warn" if rs or any(not v["passed"] for v in agent_views) else "pass")
    if top:
        n_fail = sum(r["class"] == "agent_check" for r in blocking)
        headline = (f"{n_fail} tasks failed · " if top["class"] == "agent_check" and n_fail > 1 else "") + top["headline"]
        verdict_ = {"state": state, "headline": headline, "fix": top["fix"], "class": top["class"]}
    elif rs:
        verdict_ = {"state": "warn", "headline": rs[0]["headline"], "fix": rs[0]["fix"], "class": rs[0]["class"]}
    elif agent_views:
        n_tasks = len({v["task"] for v in agent_views})
        verdict_ = {"state": "pass", "headline": f"all {n_tasks} tasks passed", "fix": "", "class": "pass"}
    else:
        verdict_ = {"state": "pass", "headline": "reference solutions pass · no agent leg ran", "fix": "",
                    "class": "pass"}

    return {
        "schema": 1,
        "verdict": verdict_,
        "reasons": rs,
        "chain": chain(stack, rs, oracle_views, agent_views, status, judge_info, default_leg),
        "tasks": tasks,
        "trials": views,
        "legs": [{**g, "label": leg_label(g["leg"], trials)} for g in status],
        "judge": judge_info,
        "stack": stack,
        "run": {"id": args.run_id, "url": args.run_url, "report_url": args.report_url, "pr": args.pr,
                "sha": args.sha, "base_label": args.base_label,
                "baseline_runs": max((b["runs"] for b in bases.values() if b), default=0),
                "has_baseline": pool is not None, "k": args.k},
        "cost_usd": {"agents": agent_cost, "judge": judge_cost},
        "gate": gate,
        # the gate's inputs, for agents and tests
        "cells": now, "leg_tests": leg_gate, "leg_status": status, "effort": effort,
        "record": run_record(trials),
    }


def annotations(summary: dict) -> list[str]:
    """GitHub workflow commands that put each reason on the PR, at its cause where known."""
    def prop(v):  # workflow-command property escaping
        return str(v).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C")

    def data(v):
        return str(v).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    out = []
    for r in summary["reasons"]:
        level = "error" if r["blocking"] else "warning"
        a = r.get("annotation") or {}
        props = [f"file={prop(a['file'])}"] if a.get("file") else []
        props += [f"line={a['line']}"] if a.get("line") else []
        props.append(f"title={prop(a.get('title') or 'smoke ' + r['class'].replace('_', ' '))}")
        msg = (r["headline"] + (f" · fix: {r['fix']}" if r["fix"] else "")).replace("`", "")
        out.append(f"::{level} {','.join(props)}::{data(msg)}")
    return out


def write_outputs(summary: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str))
    comment = view.comment_md(summary)
    (out / "comment.md").write_text(comment)
    (out / "summary.md").write_text(comment.replace(MARKER + "\n", ""))
    (out / "report.html").write_text(view.page(summary))


def render(args) -> int:
    summary = build_summary(args)
    write_outputs(summary, Path(args.out))
    for line in annotations(summary):
        print(line)
    return 1 if summary["gate"] == "fail" else 0


SUMMARY_KEYS = {"schema": int, "verdict": dict, "reasons": list, "chain": list, "tasks": list, "trials": list,
                "legs": list, "judge": dict, "run": dict, "cost_usd": dict, "gate": str}
URL_OK = re.compile(r"^(https://github\.com/|https://lightconeresearch\.github\.io/)[\w./#%?=&~+-]*$")
MAX_STRING = 100_000
MAX_DEPTH = 12


def validate_summary(s) -> list[str]:
    """Shape checks for a summary.json from an artifact, before rendering it for publication.

    Rendering escapes every string, so this guards the rest: plain JSON types
    only, bounded sizes and depth, the top-level shape, and links that can only
    point at GitHub or this project's Pages site (no javascript: or data: URLs).
    """
    errors: list[str] = []
    if not isinstance(s, dict):
        return ["summary.json is not an object"]
    for key, kind in SUMMARY_KEYS.items():
        if not isinstance(s.get(key), kind):
            errors.append(f"{key}: expected {kind.__name__}")

    def walk(v, path: str, depth: int) -> None:
        if depth > MAX_DEPTH:
            errors.append(f"{path}: nested deeper than {MAX_DEPTH}")
        elif isinstance(v, dict):
            for k, x in v.items():
                if not isinstance(k, str) or len(k) > 200:
                    errors.append(f"{path}: bad key")
                walk(x, f"{path}.{k}", depth + 1)
        elif isinstance(v, list):
            for i, x in enumerate(v[:5000]):
                walk(x, f"{path}[{i}]", depth + 1)
            if len(v) > 5000:
                errors.append(f"{path}: more than 5000 items")
        elif isinstance(v, str):
            if len(v) > MAX_STRING:
                errors.append(f"{path}: string longer than {MAX_STRING}")
        elif not (v is None or isinstance(v, (bool, int, float))):
            errors.append(f"{path}: unexpected type {type(v).__name__}")

    walk(s, "summary", 0)
    for key in ("url", "report_url"):
        url = (s.get("run") or {}).get(key) if isinstance(s.get("run"), dict) else None
        if url and not (isinstance(url, str) and URL_OK.match(url)):
            errors.append(f"run.{key}: not a GitHub or Pages URL")
    for t in s.get("trials") or []:
        if isinstance(t, dict) and not re.fullmatch(r"[\w.-]{1,200}", str(t.get("anchor", ""))):
            errors.append("trials[].anchor: unexpected characters")
            break
    return errors[:50]


def show(args) -> int:
    """Re-render comment.md and report.html from a summary.json alone (--validate first, for publication)."""
    try:
        summary = json.loads(Path(args.summary).read_text())
    except (OSError, ValueError) as err:
        print(f"::error::summary.json unreadable: {err}")
        return 2
    if args.validate:
        errors = validate_summary(summary)
        if errors:
            for err in errors:
                print(f"::error::summary.json rejected: {err}")
            return 2
    write_outputs(summary, Path(args.out))
    return 0


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
        p.add_argument("--baseline", help="baseline.json from baseline.py fetch")
        if name == "select":
            p.add_argument("--all", action="store_true", help="every measured agent trial, not only failures and outliers")
        if name == "render":
            p.add_argument("--judge")
            p.add_argument("--stack")
            p.add_argument("--run-url", default="")
            p.add_argument("--run-id", default="")
            p.add_argument("--pr", default="")
            p.add_argument("--sha", default="")
            p.add_argument("--report-url", default="", help="where the HTML report is published")
            p.add_argument("--base-label", default="")
            p.add_argument("--out", default=".")
            p.add_argument("--record", action="store_true")
            p.add_argument("--judge-not-run", default="", help="why the judge did not run, when it did not")
            p.add_argument("--expect-legs", default="", help="space-separated legs the run planned")
            p.add_argument("--baseline-error", default="", help="set when the baseline fetch failed")
            p.add_argument("--expect-tasks", default="", help="space-separated task dirs the run planned")
            p.add_argument("--k", type=int, help="attempts each agent leg owes per task")
            p.add_argument("--not-run-reason", default="", help="why a planned leg without trials did not run")
            p.add_argument("--job", action="append", default=[], help="upstream job result, name=result")
    p = sub.add_parser("show", help="re-render comment.md and report.html from summary.json")
    p.add_argument("summary")
    p.add_argument("--out", default=".")
    p.add_argument("--validate", action="store_true", help="reject a summary.json of the wrong shape (for publication)")
    args = ap.parse_args()
    return {"select": select, "render": render, "show": show}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
