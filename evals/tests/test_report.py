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
