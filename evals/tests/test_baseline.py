"""evals/bin/baseline.py: the append-only log of recorded runs, and the pool readers build from it."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import baseline  # noqa: E402


def write_run(root: Path, number: int, k: int):
    (root / "runs").mkdir(parents=True, exist_ok=True)
    rec = {"leg-a/task": {"k": k, "n": 1, "turns": [number], "stack_calls": [1]}}
    (root / "runs" / f"{number}-sha{number}.json").write_text(
        json.dumps({"run_number": number, "run_id": f"id{number}", "sha": f"sha{number}", "record": rec}))


def test_pool_is_the_newest_runs_by_number_whatever_the_publish_order(tmp_path):
    for number in (12, 3, 7, 1, 11, 5, 9, 2, 10, 4, 8, 6):  # published out of order
        write_run(tmp_path, number, k=number % 2)
    index = baseline.regenerate_index(tmp_path)
    assert [r["run_number"] for r in index["runs"]] == list(range(1, 13))
    built = baseline.build(index, lambda f: json.loads((tmp_path / f).read_text()))
    assert [r["run_number"] for r in built["pool"]["leg-a/task"]] == [8, 9, 10, 11, 12]
    assert [r["run_number"] for r in built["history"]["leg-a/task"]] == list(range(3, 13))
    assert built["commit"] == "sha12" and built["run"] == "id12"


def test_two_concurrent_publishers_both_land(tmp_path):
    # Each adds only its own file and rebuilds the index from the directory: nothing to lose.
    write_run(tmp_path, 1, 1)
    write_run(tmp_path, 2, 1)
    baseline.regenerate_index(tmp_path)
    write_run(tmp_path, 3, 0)  # A
    write_run(tmp_path, 4, 1)  # B, published before A's index update
    index = baseline.regenerate_index(tmp_path)
    assert [r["run_number"] for r in index["runs"]] == [1, 2, 3, 4]
