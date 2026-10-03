"""evals/bin/trialview.py: the timeline, with hook messages and errors, from a synthetic trial."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
import trialview  # noqa: E402


def test_timeline_marks_errors_and_places_hooks_after_their_call(tmp_path):
    (tmp_path / "agent" / "sessions" / "projects" / "p").mkdir(parents=True)
    steps = [
        {"source": "user", "message": "do it"},
        {"source": "agent", "message": "Writing the spec.", "tool_calls": [
            {"tool_call_id": "toolu_1", "function_name": "Write", "arguments": {"file_path": "/root/x/astra.yaml"}}],
         "observation": {"results": [{"source_call_id": "toolu_1", "content": "File created"}]}},
        {"source": "agent", "message": "Validating.", "tool_calls": [
            {"tool_call_id": "toolu_2", "function_name": "Bash", "arguments": {"command": "astra validate"}}],
         "observation": {"results": [{"source_call_id": "toolu_2",
                                      "content": "Exit code 1\nSchema validation errors:\n  • analysis: Extra inputs"}]}},
        {"source": "agent", "message": "Done."},
    ]
    (tmp_path / "agent" / "trajectory.json").write_text(json.dumps({"steps": steps}))
    hooks = [
        {"attachment": {"type": "hook_additional_context", "hookName": "SessionStart",
                        "toolUseID": "SessionStart", "content": ["Lightcone CLI ready"]}},
        {"attachment": {"type": "hook_additional_context", "hookName": "PostToolUse:Write",
                        "toolUseID": "toolu_1", "content": ["ASTRA validation passed for the project"]}},
    ]
    (tmp_path / "agent" / "sessions" / "projects" / "p" / "s.jsonl").write_text(
        "\n".join(json.dumps(h) for h in hooks))
    rows = trialview.timeline(tmp_path)
    assert [r["kind"] for r in rows] == ["hook", "call", "hook", "call", "final"]
    assert rows[2]["name"] == "validate-on-save hook" and rows[2]["claim"] == "pass"
    assert rows[2]["contradicted"] == "contradicted: `astra validate` at turn 2 exits 1"
    assert rows[3]["error"] and rows[3]["exit"] == 1 and "Extra inputs" in rows[3]["output"]
    assert not rows[1]["error"] and rows[-1]["text"] == "Done."


def test_model_labels():
    assert trialview.model_label("claude-sonnet-5-5") == "Sonnet 5.5"
    assert trialview.model_label("claude-haiku-4-5") == "Haiku 4.5"
    assert trialview.model_label("gpt-6-luna") == "Luna (GPT-6)"


def test_first_error_line():
    assert trialview.first_error_line(
        "Validating astra.yaml...\n\nSchema validation errors:\n  • version: Input should be a valid string\n") \
        == "version: Input should be a valid string"
    assert trialview.first_error_line("resolved outputs: {}\nok   a\nFAIL output clean_data is declared") \
        == "FAIL output clean_data is declared"


def test_every_task_has_a_plain_language_summary_for_each_check():
    for task_dir in sorted(trialview.TASKS_DIR.glob("*/task.toml")):
        meta = trialview.task_meta(task_dir.parent.name)
        assert meta["proves"] and meta["had_to"], task_dir.parent.name
        tests = "".join(p.read_text() for p in (task_dir.parent / "tests").glob("*.*") if p.suffix in (".sh", ".py"))
        for check in meta["checks"]:
            assert check in tests, (task_dir.parent.name, check)
