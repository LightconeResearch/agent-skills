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


def test_schema_error_paths_map_to_yaml_lines():
    body = ('version: "0.0.14"\nname: x\noutputs:\n  - id: a\n    recipe:\n      command: c\n'
            '  - id: b\n    recipe:\n      run: python f\n')
    paths = trialview.yaml_paths(body)
    assert paths["outputs.1.recipe.run"] == 9 and paths["outputs.0.id"] == 4 and paths["version"] == 1
    out = "Schema validation errors:\n  • outputs.1.recipe.run: Extra inputs are not permitted\n  • name: Input should be x"
    marks = trialview.error_lines(body, [{"ok": False, "output": out}])
    assert [(m["line"], m["path"]) for m in marks] == [(2, "name"), (9, "outputs.1.recipe.run")]


def test_semantic_error_paths_fall_back_to_the_nearest_key():
    body = "inputs:\n  - id: raw\n"
    out = "Semantic validation errors:\n  • [MISSING_ROOT_FIELD] version: Root analysis is missing required field"
    assert trialview.error_lines(body, [{"ok": False, "output": out}]) == []  # no such line: nothing to mark
    body2 = "version: 1\n"
    assert trialview.error_lines(body2, [{"ok": False, "output": "• version: Input should be a valid string"}]) \
        == [{"line": 1, "path": "version", "error": "Input should be a valid string"}]


def rows_for(*calls, hook_after=0, claim="pass", text="ASTRA validation passed for the project"):
    rows = []
    for i, (tool, what, code) in enumerate(calls):
        rows.append({"kind": "call", "turn": i + 1, "tool": tool, "what": what, "exit": code})
        if i == hook_after:
            rows.append({"kind": "hook", "name": "validate-on-save hook", "claim": claim, "text": text})
    return rows


def test_no_chip_when_a_later_bash_may_have_changed_the_file():
    rows = rows_for(("Write", "/root/x/astra.yaml", None), ("Bash", "sed -i s/a/b/ astra.yaml", 0),
                    ("Bash", "astra validate", 1))
    trialview.mark_contradictions(rows, [{"name": "spec_valid", "ok": False}])
    assert not any(r.get("contradicted") for r in rows)


def test_an_unrelated_validate_command_is_not_astra_validate():
    rows = rows_for(("Write", "/root/x/astra.yaml", None), ("Bash", "python validate_catalog.py", 1))
    trialview.mark_contradictions(rows, [])
    assert not any(r.get("contradicted") for r in rows)


def test_chip_when_astra_validate_right_after_disagrees():
    rows = rows_for(("Write", "/root/x/astra.yaml", None), ("Bash", "uvx astra-tools@0.2.18 validate", 1))
    trialview.mark_contradictions(rows, [])
    assert rows[1]["contradicted"] == "contradicted: `uvx astra-tools@0.2.18 validate` at turn 2 exits 1"


def test_malformed_hook_records_are_skipped_not_fatal(tmp_path):
    (tmp_path / "agent" / "sessions" / "projects" / "p").mkdir(parents=True)
    (tmp_path / "agent" / "trajectory.json").write_text(json.dumps({"steps": []}))
    lines = [
        {"attachment": {"type": "hook_additional_context", "hookName": "SessionStart",
                        "content": {"text": "Lightcone CLI ready"}}},
        {"attachment": {"type": "hook_additional_context", "hookName": "PostToolUse:Write",
                        "content": [{"text": "ASTRA validation passed"}, 3]}},
        {"attachment": {"type": "hook_additional_context", "hookName": {"bad": 1}, "content": "x",
                        "toolUseID": ["not", "a", "string"]}},
        "not json at all",
    ]
    (tmp_path / "agent" / "sessions" / "projects" / "p" / "s.jsonl").write_text(
        "\n".join(json.dumps(x) if isinstance(x, dict) else x for x in lines))
    rows = trialview.timeline(tmp_path)
    texts = [r["text"] for r in rows]
    assert "Lightcone CLI ready" in texts[0] and any("ASTRA validation passed" in t for t in texts)
