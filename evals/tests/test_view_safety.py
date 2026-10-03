"""The report page cannot be made to run script by a hostile summary.json.

Two layers: a lint over evals/bin/view.py (every value interpolated into HTML
goes through an escaping helper or is an already-built *_html fragment), and a
property test that poisons each leaf of a real summary.json in turn and checks
that `report.py show --validate` either rejects it or renders nothing active.
"""

import ast
import copy
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

BIN = Path(__file__).resolve().parents[1] / "bin"
sys.path.insert(0, str(BIN))
import report  # noqa: E402
import view  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "summary.json"
SAFE_CALLS = {"h", "e", "md", "num", "aid", "url", "cls", "dots", "hist"}
PAYLOAD = '"><script>x</script><img src=x onerror=y>'


def _allowed(node: ast.AST) -> bool:
    if isinstance(node, ast.Call):
        name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        return name in SAFE_CALLS or name.endswith("_html")
    if isinstance(node, ast.Name):
        return node.id.endswith("_html") or node.id.isupper()
    return False


def _page_functions(tree: ast.Module):
    start = next(n.lineno for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "CSS" for t in n.targets))
    return [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.lineno > start]


def test_every_html_interpolation_is_escaped_or_a_built_fragment():
    tree = ast.parse((BIN / "view.py").read_text())
    offenders = []
    for fn in _page_functions(tree):
        for node in ast.walk(fn):
            if isinstance(node, ast.JoinedStr):
                literal = "".join(v.value for v in node.values if isinstance(v, ast.Constant))
                if "<" not in literal and '="' not in literal:
                    continue
                for v in node.values:
                    if isinstance(v, ast.FormattedValue) and not _allowed(v.value):
                        offenders.append(f"{fn.name}:{v.lineno}: {ast.unparse(v.value)}")
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                for side, other in ((node.left, node.right), (node.right, node.left)):
                    if isinstance(side, ast.Constant) and isinstance(side.value, str) and "<" in side.value:
                        if not (_allowed(other) or isinstance(other, (ast.Constant, ast.JoinedStr, ast.BinOp))):
                            offenders.append(f"{fn.name}:{node.lineno}: + {ast.unparse(other)}")
    assert not offenders, "raw interpolation into HTML:\n" + "\n".join(offenders)


def _leaves(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _leaves(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _leaves(v, path + (i,))
    else:
        yield path


def _set(obj, path, value):
    for p in path[:-1]:
        obj = obj[p]
    obj[path[-1]] = value


class _Active(HTMLParser):
    """Collects what a browser would execute: script elements, on* attributes, javascript: links."""

    def __init__(self):
        super().__init__()
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.found.append("<script>")
        for name, value in attrs:
            if name.startswith("on"):
                self.found.append(f"{tag} {name}=")
            if name in ("href", "src", "action") and (value or "").strip().lower().startswith(("javascript:", "data:")):
                self.found.append(f"{tag} {name}={value}")


def _active(page: str) -> list[str]:
    parser = _Active()
    parser.feed(page)
    # The literal string check too: escaped payload text reads "&lt;script", never "<script".
    return parser.found + (["<script"] if "<script" in page.lower() else [])


def test_poisoning_any_leaf_never_yields_active_content():
    base = json.loads(FIXTURE.read_text())
    assert report.validate_summary(base) == [] and not _active(view.page(base))
    rendered = rejected = 0
    for path in _leaves(base):
        poisoned = copy.deepcopy(base)
        _set(poisoned, path, PAYLOAD)
        if report.validate_summary(poisoned):
            rejected += 1
            continue
        try:
            page = view.page(poisoned)
        except Exception:  # noqa: BLE001  a crash publishes nothing, which is safe
            continue
        rendered += 1
        assert not _active(page), f"active content via {'.'.join(map(str, path))}"
    assert rendered > 100 and rejected > 10  # both branches were exercised


def test_numbers_must_be_numbers():
    base = json.loads(FIXTURE.read_text())
    bad = copy.deepcopy(base)
    bad["trials"][0]["stack_calls"] = "3"
    bad["tasks"][0]["history"] = [{"k": True, "n": 1}]
    errors = report.validate_summary(bad)
    assert any("stack_calls" in x for x in errors) and any("history" in x for x in errors)


def test_fixture_has_no_secrets():
    assert not re.search(r"sk-(ant-)?[A-Za-z0-9_-]{20,}", FIXTURE.read_text())
