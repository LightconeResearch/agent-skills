"""The smoke gate (evals/bin/report.py) on synthetic Harbor job dirs.

    uv run --with pytest pytest evals/tests -q
"""

import json
import subprocess
import sys
from pathlib import Path

REPORT = Path(__file__).resolve().parents[1] / "bin" / "report.py"
LEG = "claude-haiku-skill"
TASKS = ("astra-author", "astra-add-decision", "astra-query")


def trial(jobs: Path, leg: str, task: str, i: int, reward: float, turns: int = 10):
    tdir = jobs / leg / leg / f"{task}__{leg}{i}"
    (tdir / "agent").mkdir(parents=True)
    (tdir / "result.json").write_text(json.dumps({
        "trial_name": tdir.name,
        "task_name": f"lightcone/smoke-{task}",
        "verifier_result": {"rewards": {"reward": reward}},
        "agent_result": {"cost_usd": 0.05},
    }))
    steps = [{"source": "agent", "tool_calls": [{"function_name": "Bash",
                                                 "arguments": {"command": "astra validate"}}]}] * turns
    (tdir / "agent" / "trajectory.json").write_text(json.dumps({"steps": steps}))


def run_cell(jobs: Path, task: str, k: int, n: int = 2, leg: str = LEG):
    for i in range(n):
        trial(jobs, leg, task, i, 1.0 if i < k else 0.0)


def baseline(tmp: Path, cells: dict[str, tuple[int, int]], runs: int = 5) -> Path:
    """A pool of `runs` recording runs, the cell's (k, n) spread evenly over them."""
    pool = {}
    for task, (k, n) in cells.items():
        records = []
        for r in range(runs):
            rk = k // runs + (1 if r < k % runs else 0)
            records.append({"k": rk, "n": n // runs, "turns": [10] * (n // runs),
                            "stack_calls": [10] * (n // runs)})
        pool[f"{LEG}/{task}"] = records
    path = tmp / "base.json"
    path.write_text(json.dumps({"pool": pool}))
    return path


def render(tmp: Path, base: Path | None = None, *extra) -> tuple[int, dict]:
    out = tmp / "out"
    args = [sys.executable, str(REPORT), "render", str(tmp / "jobs"), "--out", str(out), *extra]
    if base:
        args += ["--baseline", str(base)]
    proc = subprocess.run(args, capture_output=True, text=True)
    assert proc.returncode in (0, 1), proc.stderr
    return proc.returncode, json.loads((out / "summary.json").read_text())


def verdicts(summary: dict) -> dict[str, str]:
    return {c["task"]: c["verdict"] for c in summary["cells"].values()}


def test_strong_cell_going_to_zero_blocks(tmp_path):
    run_cell(tmp_path / "jobs", "astra-author", 0)
    rc, summary = render(tmp_path, baseline(tmp_path, {"astra-author": (10, 10)}))
    assert rc == 1
    assert verdicts(summary) == {"astra-author": "blocking"}


def test_weak_cell_going_to_zero_is_known(tmp_path):
    run_cell(tmp_path / "jobs", "astra-author", 0)
    rc, summary = render(tmp_path, baseline(tmp_path, {"astra-author": (2, 10)}))
    assert rc == 0
    assert verdicts(summary) == {"astra-author": "known"}


def test_no_baseline_blocks_any_zero_cell_only(tmp_path):
    run_cell(tmp_path / "jobs", "astra-author", 0)
    run_cell(tmp_path / "jobs", "astra-query", 1)
    rc, summary = render(tmp_path)
    assert rc == 1
    assert verdicts(summary) == {"astra-author": "blocking", "astra-query": "new"}


def test_mutation_one_shape_warns_without_blocking(tmp_path):
    # 1/2 on a 10/10 cell, the leg's other cells clean: a warning, not a block.
    run_cell(tmp_path / "jobs", "astra-author", 1)
    for task in TASKS[1:]:
        run_cell(tmp_path / "jobs", task, 2)
    rc, summary = render(tmp_path, baseline(tmp_path, {t: (10, 10) for t in TASKS}))
    assert rc == 0
    assert verdicts(summary)["astra-author"] == "warning"
    assert not summary["legs"][0]["blocking"]


def test_same_shape_in_three_cells_blocks_via_the_leg(tmp_path):
    for task in TASKS:
        run_cell(tmp_path / "jobs", task, 1)
    rc, summary = render(tmp_path, baseline(tmp_path, {t: (10, 10) for t in TASKS}))
    assert rc == 1
    assert set(verdicts(summary).values()) == {"warning"}
    leg = summary["legs"][0]
    assert leg["blocking"] and leg["x"] == 3 and leg["n"] == 6 and leg["tail"] < 0.01


def test_record_gates_only_on_the_oracle(tmp_path):
    run_cell(tmp_path / "jobs", "astra-author", 0)
    rc, _ = render(tmp_path, baseline(tmp_path, {"astra-author": (10, 10)}), "--record")
    assert rc == 0
    trial(tmp_path / "jobs", "oracle", "astra-author", 0, 0.5)
    rc, _ = render(tmp_path, None, "--record")
    assert rc == 1


def test_pool_rolls_over_the_last_five_runs(tmp_path):
    run_cell(tmp_path / "jobs", "astra-author", 1)
    _, summary = render(tmp_path, baseline(tmp_path, {"astra-author": (10, 10)}))
    records = summary["pool"][f"{LEG}/astra-author"]
    assert len(records) == 5 and records[-1]["k"] == 1 and records[-1]["n"] == 2
    assert sum(r["n"] for r in records) == 10  # oldest (2 trials) dropped, this run's 2 added


def test_select_failures_and_outliers(tmp_path):
    jobs = tmp_path / "jobs"
    trial(jobs, LEG, "astra-author", 0, 0.0)            # failure
    trial(jobs, LEG, "astra-author", 1, 1.0, turns=30)  # outlier against the pooled median of 10
    trial(jobs, LEG, "astra-author", 2, 1.0, turns=12)  # ordinary
    proc = subprocess.run([sys.executable, str(REPORT), "select", str(jobs), "--baseline",
                           str(baseline(tmp_path, {"astra-author": (10, 10)}))],
                          capture_output=True, text=True)
    picked = sorted(Path(p).name for p in proc.stdout.split())
    assert picked == [f"astra-author__{LEG}0", f"astra-author__{LEG}1"]


def infra_trial(jobs: Path, leg: str, task: str, i: int, exc: str = "ApiUsageLimitError"):
    tdir = jobs / leg / leg / f"{task}__{leg}{i}"
    tdir.mkdir(parents=True)
    (tdir / "result.json").write_text(json.dumps({
        "trial_name": tdir.name, "task_name": f"lightcone/smoke-{task}",
        "exception_info": {"exception_type": exc}}))


def test_infra_errors_are_not_failures_but_block_as_unmeasured(tmp_path):
    jobs = tmp_path / "jobs"
    for task in TASKS:
        infra_trial(jobs, "codex-luna-skill", task, 0)
        infra_trial(jobs, "codex-luna-skill", task, 1)
    run_cell(jobs, "astra-author", 2)
    base = baseline(tmp_path, {"astra-author": (10, 10)})
    rc, summary = render(tmp_path, base)
    assert rc == 1
    assert not any(c["leg"] == "codex-luna-skill" for c in summary["cells"].values())
    assert not any(k.startswith("codex-luna-skill/") for k in summary["pool"])
    luna = next(g for g in summary["leg_status"] if g["leg"] == "codex-luna-skill")
    assert luna["state"] == "not measured"
    assert luna["reason"] == "6/6 trials hit ApiUsageLimitError (provider quota)"
    comment = (tmp_path / "out" / "comment.md").read_text()
    assert comment.count("ApiUsageLimitError") == 1  # one line for the leg, none per trial
    proc = subprocess.run([sys.executable, str(REPORT), "select", str(jobs)], capture_output=True, text=True)
    assert proc.stdout == ""  # infra trials are never judged


def test_expected_leg_without_trials_shows_as_not_run(tmp_path):
    jobs = tmp_path / "jobs"
    run_cell(jobs, "astra-author", 2)
    (jobs / "claude-haiku-plugin.status").write_text("ANTHROPIC_API_KEY not set\n")
    rc, summary = render(tmp_path, baseline(tmp_path, {"astra-author": (10, 10)}),
                         "--expect-legs", f"{LEG} claude-haiku-plugin")
    assert rc == 1
    plugin = next(g for g in summary["leg_status"] if g["leg"] == "claude-haiku-plugin")
    assert plugin == {"leg": "claude-haiku-plugin", "state": "not run",
                      "reason": "ANTHROPIC_API_KEY not set", "measured": 0, "infra": 0, "missing": 0}
    comment = (tmp_path / "out" / "comment.md").read_text()
    assert "**not run** · claude-haiku-plugin: ANTHROPIC_API_KEY not set" in comment
    assert "| task | claude-haiku-plugin | claude-haiku-skill |" in comment


def effort(summary: dict, metric: str = "turns") -> dict:
    return next(e for e in summary["effort"] if e["metric"] == metric)


def test_effort_warns_when_most_trials_run_long(tmp_path):
    jobs = tmp_path / "jobs"
    tasks = [f"task-{i}" for i in range(5)]
    for task in tasks:
        for i in range(2):
            trial(jobs, LEG, task, i, 1.0, turns=15)  # pooled median is 10
    rc, summary = render(tmp_path, baseline(tmp_path, {t: (10, 10) for t in tasks}))
    e = effort(summary)
    assert rc == 0 and e["flag"] and e["above"] == 10 and round(e["ratio"], 2) == 1.5
    assert "+50% turns vs main across 5/5 cells" in (tmp_path / "out" / "comment.md").read_text()


def test_effort_stays_quiet_on_mixed_or_small_shifts(tmp_path):
    jobs = tmp_path / "jobs"
    tasks = [f"task-{i}" for i in range(5)]
    for task in tasks:
        trial(jobs, LEG, task, 0, 1.0, turns=12)
        trial(jobs, LEG, task, 1, 1.0, turns=9)
    _, summary = render(tmp_path, baseline(tmp_path, {t: (10, 10) for t in tasks}))
    assert not effort(summary)["flag"]


def test_version_skew_blocks_and_leads_the_comment(tmp_path):
    jobs = tmp_path / "jobs"
    for task in TASKS:
        trial(jobs, "oracle", task, 0, 1.0)
    skew = "lightcone-cli 0.5.0rc5 requires astra-tools ==0.2.18, the plugin pins astra-tools 0.2.17"
    (jobs / "stack.json").write_text(json.dumps({"astra_tools": "0.2.17", "skew": skew}))
    rc, summary = render(tmp_path, None, "--stack", str(jobs / "stack.json"),
                         "--expect-legs", f"{LEG} codex-luna-skill", "--not-run-reason", "oracle failed",
                         "--job", "oracle=failure", "--job", "legs=skipped")
    assert rc == 1 and summary["gate"] == "fail"
    comment = (tmp_path / "out" / "comment.md").read_text()
    lines = [line for line in comment.splitlines() if line.startswith("- ")]
    assert lines[0] == f"- **blocking** · version skew: {skew}"
    assert f"- **not run** · {LEG}: oracle failed" in lines
    assert "passing" not in comment.splitlines()[1]
    assert f"| task | {LEG} | codex-luna-skill |" in comment
    assert "| astra-author | not run | not run |" in comment


def test_failed_upstream_job_with_no_legs_never_passes(tmp_path):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    rc, summary = render(tmp_path, None, "--job", "oracle=failure", "--job", "legs=skipped")
    assert rc == 1 and summary["gate"] == "fail"
    comment = (tmp_path / "out" / "comment.md").read_text()
    assert "- **blocking** · the oracle job ended in failure; see the run log" in comment
    assert "No agent leg was planned or run." in comment
    assert "| task |  |" not in comment


def test_oracle_infra_error_still_blocks(tmp_path):
    jobs = tmp_path / "jobs"
    trial(jobs, "oracle", "astra-author", 0, 1.0)
    infra_trial(jobs, "oracle", "astra-query", 0, "EnvironmentStartTimeoutError")
    rc, summary = render(tmp_path, None, "--expect-tasks", "astra-author astra-query")
    assert rc == 1
    assert summary["cells"]["oracle/astra-query"]["verdict"] == "blocking"


def test_every_planned_task_needs_an_oracle_run(tmp_path):
    jobs = tmp_path / "jobs"
    trial(jobs, "oracle", "astra-author", 0, 1.0)
    rc, _ = render(tmp_path, None, "--expect-tasks", "astra-author astra-query")
    assert rc == 1
    assert "oracle: no reference run for astra-query" in (tmp_path / "out" / "comment.md").read_text()


def test_a_leg_short_of_k_trials_is_partly_measured(tmp_path):
    jobs = tmp_path / "jobs"
    for task in TASKS:
        trial(jobs, "oracle", task, 0, 1.0)
    run_cell(jobs, "astra-author", 2)
    run_cell(jobs, "astra-query", 1, n=1)  # one attempt never ran
    infra_trial(jobs, LEG, "astra-add-decision", 0, "ApiRateLimitError")
    trial(jobs, LEG, "astra-add-decision", 1, 1.0)
    rc, summary = render(tmp_path, baseline(tmp_path, {t: (10, 10) for t in TASKS}),
                         "--expect-tasks", " ".join(TASKS), "--expect-legs", LEG, "--k", "2")
    assert rc == 1
    leg = next(g for g in summary["leg_status"] if g["leg"] == LEG)
    assert leg["state"] == "partly measured"
    assert leg["reason"] == "2/6 trials missing: 1 hit ApiRateLimitError (rate limit); 1 never ran"
    _, recorded = render(tmp_path, baseline(tmp_path, {t: (10, 10) for t in TASKS}),
                         "--expect-tasks", " ".join(TASKS), "--expect-legs", LEG, "--k", "2", "--record")
    assert recorded["gate"] == "pass"  # main records; coverage gates PRs


def test_astra_override_blocks_with_a_labelled_line(tmp_path):
    jobs = tmp_path / "jobs"
    trial(jobs, "oracle", "astra-author", 0, 1.0)
    override = "lightcone-cli 0.5.1.dev3 requires astra-tools ==0.2.18, testing astra-tools 0.2.19.dev7"
    (jobs / "stack.json").write_text(json.dumps({"skew": None, "override": override}))
    rc, _ = render(tmp_path, None, "--stack", str(jobs / "stack.json"))
    assert rc == 1
    assert f"- **blocking** · override: {override}" in (tmp_path / "out" / "comment.md").read_text()


def test_leg_test_judges_cells_by_their_own_rates(tmp_path):
    # History: 15/15 on one task, 0/2 on four. This run: the same outcomes, 2/2 and four 0/2.
    # A leg-wide pooled p (16/19) made this look improbable (p = 0.006); per cell it is ordinary.
    jobs = tmp_path / "jobs"
    tasks = [f"task-{i}" for i in range(5)]
    run_cell(jobs, tasks[0], 2)
    for task in tasks[1:]:
        run_cell(jobs, task, 0)
    pool = {f"{LEG}/{tasks[0]}": [{"k": 3, "n": 3, "turns": [10] * 3, "stack_calls": [1] * 3}] * 5}
    for task in tasks[1:]:
        pool[f"{LEG}/{task}"] = [{"k": 0, "n": 2, "turns": [10, 10], "stack_calls": [1, 1]}]
    base = tmp_path / "base.json"
    base.write_text(json.dumps({"pool": pool}))
    rc, summary = render(tmp_path, base)
    leg = summary["legs"][0]
    assert (leg["x"], leg["n"], leg["base_k"], leg["base_n"]) == (2, 10, 15, 23)
    assert leg["tail"] > 0.1 and not leg["blocking"]
    assert rc == 0
    assert {c["verdict"] for c in summary["cells"].values()} == {"pass", "known"}
