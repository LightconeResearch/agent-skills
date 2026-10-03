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
                        "toolUseID": "toolu_1", "content": ["ASTRA validation passed"]}},
    ]
    (tmp_path / "agent" / "sessions" / "projects" / "p" / "s.jsonl").write_text(
        "\n".join(json.dumps(h) for h in hooks))
    rows = trialview.timeline(tmp_path)
    assert [r["kind"] for r in rows] == ["hook", "call", "hook", "call", "final"]
    assert rows[2]["text"] == "PostToolUse:Write: ASTRA validation passed"
    assert rows[3]["error"] and rows[3]["exit"] == 1 and "Extra inputs" in rows[3]["output"]
    assert not rows[1]["error"] and rows[-1]["text"] == "Done."


def test_model_labels():
    assert trialview.model_label("claude-sonnet-5-5") == "Sonnet 5.5"
    assert trialview.model_label("claude-haiku-4-5") == "Haiku 4.5"
    assert trialview.model_label("gpt-6-luna") == "Luna (GPT-6)"
