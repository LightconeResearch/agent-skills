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


VALIDATE_CLAIM = re.compile(r"ASTRA validation (passed|FAILED)")
WRITES = {"write", "edit", "multiedit", "apply_patch", "notebookedit"}


def hook_name(hook: str, text: str) -> str:
    if VALIDATE_CLAIM.search(text):
        return "validate-on-save hook"
    if hook.startswith("SessionStart"):
        return "SessionStart hook"
    return f"{hook.split(':', 1)[0]} hook"


def content_text(content) -> str:
    """A hook attachment's content as text, whatever shape the session log used."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return str(content.get("text") or json.dumps(content))
    if isinstance(content, list):
        return "\n".join(content_text(c) for c in content)
    return "" if content is None else str(content)


def _hooks(tdir: Path) -> tuple[list[dict], dict[str, list[dict]]]:
    """Hook messages from the Claude Code session log: (session start, by tool call id).

    A record that is not shaped as expected is skipped and counted, never fatal:
    the count comes back as a final "note" row in the session-start list.
    """
    start, by_call, skipped = [], {}, 0
    for log in sorted((tdir / "agent" / "sessions" / "projects").glob("*/*.jsonl")):
        for line in _text(log).splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            att = event.get("attachment") if isinstance(event, dict) else None
            if not isinstance(att, dict) or att.get("type") != "hook_additional_context":
                continue
            try:
                text = content_text(att.get("content")).strip()
                hook = str(att.get("hookName") or "hook")
                claim = VALIDATE_CLAIM.search(text)
                row = {"kind": "hook", "hook": hook, "name": hook_name(hook, text), "text": text,
                       "claim": ("pass" if claim.group(1) == "passed" else "fail") if claim else None}
                call = str(att.get("toolUseID") or "")
            except (TypeError, ValueError, AttributeError):
                skipped += 1
                continue
            if call.startswith("toolu_") or call.startswith("call_"):
                by_call.setdefault(call, []).append(row)
            else:
                start.append(row)
    if skipped:
        start.append({"kind": "note", "text": f"{skipped} malformed hook record(s) in the session log skipped"})
    return start, by_call


def timeline(tdir: Path, checks: list[dict] | None = None) -> list[dict]:
    """One row per tool call and hook message, in order, ending with the agent's last message.

    Row kinds: "hook" (with the hook's validation claim, if any), "call" (with
    exit code and error flag) and "final"; call rows and the hooks that followed
    them carry the trajectory step_id the judge cites as evidence. A validation claim that disagrees
    with what happened next carries "contradicted": the text saying by what.
    """
    traj = _load(tdir / "agent" / "trajectory.json") or {}
    start, by_call = _hooks(tdir)
    rows = list(start)
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
            rows.append({"kind": "call", "turn": turn, "step": step.get("step_id"), "tool": tool, "what": what,
                         "exit": code, "error": error, "output": trim(output, 6) if error else "",
                         "note": (step.get("message") or "").strip()})
            rows += [{**h, "step": step.get("step_id")} for h in by_call.get(call.get("tool_call_id"), [])]
    final = final_message(traj)
    if final:
        rows.append({"kind": "final", "text": final})
    mark_contradictions(rows, checks or [])
    return rows


ASTRA_VALIDATE = re.compile(r"(^|[\s;&|(])(astra|astra-tools(@\S+)?)\s+validate(\s+(\./)?astra\.ya?ml)?\s*($|[;&|)]|2>|>|--)")
SHELLS = {"bash", "shell", "exec", "exec_command", "local_shell"}


def is_astra_validate(row: dict) -> bool:
    """A project-wide `astra validate` (no file, or astra.yaml): the same target the save hook checks."""
    return row["kind"] == "call" and row["tool"].lower() in SHELLS and bool(ASTRA_VALIDATE.search(row["what"]))


def may_change_files(row: dict) -> bool:
    """A write, or any shell command other than astra validate: what it touched is unknown."""
    if row["kind"] != "call":
        return False
    tool = row["tool"].lower()
    return tool in WRITES or (tool in SHELLS and not is_astra_validate(row))


def mark_contradictions(rows: list[dict], checks: list[dict]) -> None:
    """Flag ASTRA validation claims that astra itself contradicts, on the same files.

    A claim is compared with the next project-wide `astra validate` when nothing
    that could change files ran in between, and with the verifier's spec_valid
    only when nothing that could change files ran after it at all. A FAILED
    claim whose own text reports that every file passed contradicts itself.
    Anything less certain gets no chip.
    """
    verdict = next((c["ok"] for c in checks if c["name"] == "spec_valid"), None)
    for i, row in enumerate(rows):
        if row["kind"] != "hook" or not row.get("claim"):
            continue
        claim_ok = row["claim"] == "pass"
        if not claim_ok and re.search(r"passed validation|Validation successful", row["text"]):
            row["contradicted"] = "contradicts itself: it says FAILED, and its own output says every file passed"
            continue
        later = rows[i + 1:]
        actual, by = None, ""
        for r in later:
            if may_change_files(r):
                break
            if is_astra_validate(r) and r["exit"] is not None:
                actual, by = r["exit"] == 0, f"`{r['what']}` at turn {r['turn']} exits {r['exit']}"
                break
        else:
            if verdict is not None:
                actual, by = verdict, ("the verifier's spec_valid passes on this file" if verdict
                                       else "the verifier's `astra validate` rejects this file")
        if actual is not None and actual != claim_ok:
            row["contradicted"] = f"contradicted: {by}"


def first_error_line(output: str) -> str:
    """The first line of a check's output that says what is wrong."""
    lines = [ln.strip() for ln in output.splitlines()]
    for i, ln in enumerate(lines):
        if re.search(r"errors?:\s*$", ln, re.I):
            for nxt in lines[i + 1:]:
                if nxt:
                    return nxt.lstrip("•*- ").strip()
    for ln in lines:
        if ln.startswith(("FAIL", "DRIFT", "Error", "error:")):
            return ln
    for ln in lines:
        if ln and not ln.startswith(("ok ", "exit code", "Validating", "⚠", "✓")):
            return ln
    return ""


def task_meta(task: str) -> dict:
    """The task's plain-language summary (smoke.json): proves, had_to, and a line per check."""
    meta = _load(TASKS_DIR / task / "smoke.json") or {}
    return {"proves": meta.get("proves", ""), "had_to": meta.get("had_to", ""), "checks": meta.get("checks", {})}


def final_message(traj: dict) -> str:
    for step in reversed((traj or {}).get("steps", [])):
        if step.get("source") == "agent" and isinstance(step.get("message"), str) and step["message"].strip():
            return step["message"].strip()
    return ""


def last_message(tdir: Path) -> str:
    return final_message(_load(tdir / "agent" / "trajectory.json") or {})


ERROR_PATH = re.compile(r"^\s*[•*-]?\s*(?:\[[A-Z_]+\]\s*)?([A-Za-z_][\w.]*)\s*:\s*(.+)$")


def yaml_paths(body: str) -> dict[str, int]:
    """Dotted key path -> 1-based line, for block-style YAML (list items count from 0).

    Enough for the specs the agent writes: mappings, block lists ("- key: v"),
    flow values left as values. Not a YAML parser; unknown shapes just map less.
    """
    paths: dict[str, int] = {}
    stack: list[tuple[int, str, bool]] = []  # (indent, name, is_list_item)
    counters: dict[str, int] = {}
    for n, raw in enumerate(body.splitlines(), 1):
        line = raw.split(" #", 1)[0].rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        text = line.strip()
        if text.startswith("- "):
            while stack and (stack[-1][0] > indent or (stack[-1][0] == indent and stack[-1][2])):
                stack.pop()
            parent = ".".join(x[1] for x in stack)
            idx = counters.get(parent, 0)
            counters[parent] = idx + 1
            stack.append((indent, str(idx), True))
            paths[".".join(x[1] for x in stack)] = n
            text, indent = text[2:].strip(), indent + 2
            if ":" not in text:
                continue
        while stack and stack[-1][0] >= indent and not (stack[-1][2] and stack[-1][0] < indent):
            stack.pop()
        m = re.match(r"([^:\s][^:]*?)\s*:(\s|$)", text)
        if m:
            stack.append((indent, m.group(1).strip("'\""), False))
            key = ".".join(x[1] for x in stack)
            paths.setdefault(key, n)
            counters.pop(key, None)
    return paths


def error_lines(body: str, checks: list[dict]) -> list[dict]:
    """The deliverable's lines that the verifier's errors point at: [{line, path, error}]."""
    paths = yaml_paths(body)
    out, seen = [], set()
    for c in checks:
        if c["ok"]:
            continue
        for ln in c["output"].splitlines():
            m = ERROR_PATH.match(ln)
            if not m or not re.search(r"[A-Z]|not|invalid|required|missing|extra", m.group(2), re.I):
                continue
            path = m.group(1)
            parts = path.split(".")
            while parts and ".".join(parts) not in paths:
                parts.pop()
            if not parts:
                continue
            line = paths[".".join(parts)]
            if (line, m.group(2)) in seen:
                continue
            seen.add((line, m.group(2)))
            out.append({"line": line, "path": path, "error": m.group(2).strip()})
    return sorted(out, key=lambda x: x["line"])


def deliverable(tdir: Path, task: str, checks: list[dict] | None = None) -> dict | None:
    """The agent's final file, the lines the verifier's errors point at, and a diff against the reference."""
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
        changed = sum(1 for ln in diff.splitlines()
                      if ln[:1] in "+-" and not ln.startswith(("+++", "---")))
        marks = error_lines(body, checks or []) if name.endswith((".yaml", ".yml")) else []
        return {"name": name, "body": body, "diff": diff, "changed_lines": changed,
                "has_reference": ref_path.is_file(), "error_lines": marks}
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
