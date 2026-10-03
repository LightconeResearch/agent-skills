"""What one Harbor trial looked like, for the PR comment and the HTML report (stdlib only).

Everything here reads a trial dir (and the task dir under evals/smoke) and
returns plain data: the verifier's checks with their output, the agent's last
message, a turn-by-turn timeline with hook messages from the Claude Code
session log, and the deliverable with a diff against the reference solution.
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

TASKS_DIR = Path(__file__).resolve().parents[1] / "smoke"
CODEX_CMD = re.compile(r'cmd\s*:\s*"((?:[^"\\]|\\.)*)"')
EXIT_CODE = re.compile(r"^(?:Exit code|Process exited with code)\s+(-?\d+)", re.M)
DELIVERABLES = ("astra.yaml", "answer.json", "summary.txt")
REFERENCES = {"astra.yaml": "solution/astra.yaml", "answer.json": "tests/expected.json"}


def _load(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _text(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def trim(text: str, lines: int = 15) -> str:
    rows = text.rstrip().splitlines()
    return "\n".join(rows[:lines] + (["…"] if len(rows) > lines else []))


def instruction(task: str) -> str:
    return _text(TASKS_DIR / task / "instruction.md").strip()


def verifier_checks(tdir: Path, rewards: dict) -> list[dict]:
    """Each check the verifier scored: name, ok, and the output it wrote for that check."""
    out = []
    for name, value in rewards.items():
        if name == "reward":
            continue
        out.append({"name": name, "ok": bool(value), "output": _text(tdir / "verifier" / f"{name}.txt").strip()})
    return out


def verifier_stdout(tdir: Path) -> str:
    return _text(tdir / "verifier" / "test-stdout.txt").strip()


def exception_text(tdir: Path) -> str:
    return _text(tdir / "exception.txt").strip()


def _call_label(call: dict) -> tuple[str, str]:
    """(tool, what it acted on) for one tool call, harness-agnostically."""
    name = str(call.get("function_name", "?"))
    args = call.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {"command": args}
    args = args if isinstance(args, dict) else {}
    if isinstance(args.get("input"), str):  # codex: JS calling tools.exec_command({cmd: "..."})
        cmds = CODEX_CMD.findall(args["input"])
        if cmds:
            try:
                return "shell", "; ".join(json.loads(f'"{c}"') for c in cmds)
            except ValueError:
                return "shell", "; ".join(cmds)
        return name, args["input"][:200]
    for key in ("command", "cmd", "file_path", "path", "pattern", "skill", "url", "description"):
        value = args.get(key)
        if isinstance(value, list):
            value = " ".join(map(str, value))
        if isinstance(value, str) and value:
            return name, value
    return name, ""


def _hooks(tdir: Path) -> tuple[list[str], dict[str, list[str]]]:
    """Hook messages from the Claude Code session log: (session start, by tool call id)."""
    start, by_call = [], {}
    for log in sorted((tdir / "agent" / "sessions" / "projects").glob("*/*.jsonl")):
        for line in _text(log).splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            att = event.get("attachment") if isinstance(event, dict) else None
            if not isinstance(att, dict) or att.get("type") != "hook_additional_context":
                continue
            content = att.get("content")
            text = "\n".join(content) if isinstance(content, list) else str(content or "")
            label = f"{att.get('hookName', 'hook')}: {text.strip()}"
            call = att.get("toolUseID") or ""
            if call.startswith("toolu_") or call.startswith("call_"):
                by_call.setdefault(call, []).append(label)
            else:
                start.append(label)
    return start, by_call


def timeline(tdir: Path) -> list[dict]:
    """One row per tool call (and hook message), in order, ending with the agent's last message.

    Row kinds: "hook", "call" (with exit code and error flag) and "final".
    """
    traj = _load(tdir / "agent" / "trajectory.json") or {}
    start, by_call = _hooks(tdir)
    rows = [{"kind": "hook", "text": h} for h in start]
    turn = 0
    for step in traj.get("steps", []):
        if step.get("source") != "agent":
            continue
        turn += 1
        results = {r.get("source_call_id"): r for r in ((step.get("observation") or {}).get("results") or [])
                   if isinstance(r, dict)}
        for call in step.get("tool_calls") or []:
            tool, what = _call_label(call)
            content = results.get(call.get("tool_call_id"), {}).get("content")
            output = content if isinstance(content, str) else json.dumps(content) if content else ""
            m = EXIT_CODE.search(output[:200])
            code = int(m.group(1)) if m else None
            error = (code not in (None, 0)) or "<tool_use_error>" in output[:500]
            rows.append({"kind": "call", "turn": turn, "tool": tool, "what": what, "exit": code,
                         "error": error, "output": trim(output, 6) if error else "",
                         "note": (step.get("message") or "").strip()})
            rows += [{"kind": "hook", "text": h} for h in by_call.get(call.get("tool_call_id"), [])]
    final = final_message(traj)
    if final:
        rows.append({"kind": "final", "text": final})
    return rows


def final_message(traj: dict) -> str:
    for step in reversed((traj or {}).get("steps", [])):
        if step.get("source") == "agent" and isinstance(step.get("message"), str) and step["message"].strip():
            return step["message"].strip()
    return ""


def last_message(tdir: Path) -> str:
    return final_message(_load(tdir / "agent" / "trajectory.json") or {})


def deliverable(tdir: Path, task: str) -> dict | None:
    """The agent's final file, and a diff against the reference where one exists."""
    for name in DELIVERABLES:
        path = tdir / "artifacts" / name
        if not path.is_file():
            continue
        body = _text(path)
        ref_path = TASKS_DIR / task / REFERENCES.get(name, "-")
        diff = ""
        if ref_path.is_file():
            ref = _text(ref_path)
            if name.endswith(".json"):
                try:  # compare canonical JSON, so key order and spacing do not show as changes
                    ref = json.dumps(json.loads(ref), indent=2, sort_keys=True) + "\n"
                    body_cmp = json.dumps(json.loads(body), indent=2, sort_keys=True) + "\n"
                except ValueError:
                    body_cmp = body
            else:
                body_cmp = body
            diff = "".join(difflib.unified_diff(ref.splitlines(True), body_cmp.splitlines(True),
                                                "reference", "agent", n=2))
        return {"name": name, "body": body, "diff": diff, "has_reference": ref_path.is_file()}
    return None


def outcome(t: dict) -> str:
    if t["exception"]:
        return f"error: {t['exception']}"
    if t["reward"] is None:
        return "unscored"
    if t["passed"]:
        return "pass"
    return f"fail {t['reward']:.2f} ({', '.join(t['failed_checks']) or 'reward'})"


def money(v):
    return f"${v:.2f}" if v >= 0.1 else f"${v:.3f}"


def model_label(model: str | None) -> str:
    """claude-sonnet-5-5 -> Sonnet 5.5, gpt-6-luna -> Luna (GPT-6)."""
    if not model:
        return "?"
    m = re.fullmatch(r"claude-([a-z]+)-(\d+)(?:-(\d+))?(?:-\d{8})?", model)
    if m:
        return f"{m.group(1).title()} {m.group(2)}" + (f".{m.group(3)}" if m.group(3) else "")
    m = re.fullmatch(r"gpt-([\d.]+)-([a-z]+)", model)
    if m:
        return f"{m.group(2).title()} (GPT-{m.group(1)})"
    return model


def leg_label(leg: str, trials: list[dict]) -> str:
    """Sonnet 5.5 + plugin; from the leg name alone (claude-sonnet-plugin -> Sonnet + plugin) when no trial ran."""
    model = next((t["model"] for t in trials if t["leg"] == leg and t.get("model")), None)
    config = leg.rsplit("-", 1)[-1]
    if model:
        return f"{model_label(model)} + {config}"
    parts = leg.split("-")
    return f"{parts[1].title()} + {config}" if len(parts) == 3 else leg
