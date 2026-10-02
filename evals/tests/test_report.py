"""The smoke gate (evals/bin/report.py) on synthetic Harbor job dirs.

    uv run --with pytest pytest evals/tests -q
"""

import json
import subprocess
import sys
from pathlib import Path

REPORT = Path(__file__).resolve().parents[1] / "bin" / "report.py"


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


def run(tmp: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPORT), *args], cwd=tmp, capture_output=True, text=True)


def render(tmp: Path, baseline: Path | None = None, *extra) -> tuple[int, dict]:
    out = tmp / "out"
    args = ["render", str(tmp / "jobs"), "--out", str(out), *extra]
    if baseline:
        args += ["--baseline", str(baseline)]
    proc = run(tmp, *args)
    return proc.returncode, json.loads((out / "summary.json").read_text())


def baseline_with(tmp: Path, k: int, n: int = 2) -> Path:
    path = tmp / "base.json"
    path.write_text(json.dumps({"cells": {"claude-haiku-plugin/astra-author": {
        "leg": "claude-haiku-plugin", "task": "astra-author", "n": n, "k": k,
        "turns": 10, "stack_calls": 10}}}))
    return path


def test_regression_blocks(tmp_path):
    for i in range(2):
        trial(tmp_path / "jobs", "claude-haiku-plugin", "astra-author", i, 0.0)
    rc, summary = render(tmp_path, baseline_with(tmp_path, k=2))
    assert rc == 1
    assert summary["cells"]["claude-haiku-plugin/astra-author"]["verdict"] == "regressed"


def test_known_failure_does_not_block(tmp_path):
    for i in range(2):
        trial(tmp_path / "jobs", "claude-haiku-plugin", "astra-author", i, 0.0)
    rc, summary = render(tmp_path, baseline_with(tmp_path, k=0))
    assert rc == 0
    assert summary["cells"]["claude-haiku-plugin/astra-author"]["verdict"] == "known"


def test_no_baseline_blocks_any_zero_cell(tmp_path):
    trial(tmp_path / "jobs", "claude-haiku-plugin", "astra-author", 0, 0.0)
    trial(tmp_path / "jobs", "claude-haiku-plugin", "astra-query", 0, 1.0)
    rc, summary = render(tmp_path)
    assert rc == 1
    assert summary["cells"]["claude-haiku-plugin/astra-author"]["verdict"] == "new-fail"


def test_flaky_and_record(tmp_path):
    trial(tmp_path / "jobs", "claude-haiku-plugin", "astra-author", 0, 0.0)
    trial(tmp_path / "jobs", "claude-haiku-plugin", "astra-author", 1, 1.0)
    trial(tmp_path / "jobs", "claude-haiku-plugin", "astra-query", 0, 0.0)
    rc, summary = render(tmp_path, None, "--record")
    assert rc == 0  # main records; only the oracle gates there
    assert summary["cells"]["claude-haiku-plugin/astra-author"]["verdict"] == "flaky"


def test_oracle_below_one_blocks_even_when_recording(tmp_path):
    trial(tmp_path / "jobs", "oracle", "astra-author", 0, 0.5)
    rc, _ = render(tmp_path, None, "--record")
    assert rc == 1


def test_select_failures_and_outliers(tmp_path):
    jobs = tmp_path / "jobs"
    trial(jobs, "claude-haiku-plugin", "astra-author", 0, 0.0)            # failure
    trial(jobs, "claude-haiku-plugin", "astra-author", 1, 1.0, turns=30)  # outlier vs median 10
    trial(jobs, "claude-haiku-plugin", "astra-author", 2, 1.0, turns=12)  # ordinary
    proc = run(tmp_path, "select", str(jobs), "--baseline", str(baseline_with(tmp_path, k=2)))
    picked = sorted(Path(p).name for p in proc.stdout.split())
    assert picked == ["astra-author__claude-haiku-plugin0", "astra-author__claude-haiku-plugin1"]
