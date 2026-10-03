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
SAFE_CALLS = {"h", "e", "md", "num", "aid", "url", "cls"}  # escaping helpers, defined above the page section
SAFE_CONSTANTS = {"CSS"}  # module-level string literals
PAYLOAD = '"><script>x</script><img src=x onerror=y>'


def _is_html_literal(node) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and ("<" in node.value or '="' in node.value)


class HtmlLint:
    """What may reach the page: escaping helpers, literals, page builders, and *_html locals built only from those.

    Builders are the functions defined in the page section of view.py (after CSS),
    nested ones included; they are linted too, return statements included, so a
    builder cannot hand back a raw value. A *_html local counts only if every
    assignment, augmented assignment and append to it is itself safe.
    """

    def __init__(self, tree: ast.Module):
        start = next(n.lineno for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "CSS" for t in n.targets))
        self.functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.lineno > start]
        self.builders = {f.name for top in self.functions for f in ast.walk(top) if isinstance(f, ast.FunctionDef)}
        self.offenders: list[str] = []

    # -- what counts as safe --------------------------------------------------------
    def safe(self, node, ok_names) -> bool:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return True
        if isinstance(node, ast.JoinedStr):
            return all(not isinstance(v, ast.FormattedValue) or self.safe(v.value, ok_names) for v in node.values)
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                return f.id in SAFE_CALLS or f.id in self.builders
            if isinstance(f, ast.Attribute) and f.attr == "join" and isinstance(f.value, ast.Constant):
                return len(node.args) == 1 and self.safe_iter(node.args[0], ok_names)
            return False
        if isinstance(node, ast.Name):
            return node.id in SAFE_CONSTANTS or node.id in ok_names
        if isinstance(node, ast.IfExp):
            return self.safe(node.body, ok_names) and self.safe(node.orelse, ok_names)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self.safe(node.left, ok_names) and self.safe(node.right, ok_names)
        return False

    def safe_iter(self, node, ok_names) -> bool:
        if isinstance(node, ast.Name):
            return node.id in ok_names
        if isinstance(node, (ast.GeneratorExp, ast.ListComp)):
            return self.safe(node.elt, ok_names)
        if isinstance(node, ast.List):
            return all(self.safe(x, ok_names) for x in node.elts)
        return False

    def verified_names(self, fn) -> set[str]:
        """*_html locals whose every write is safe (to a fixed point)."""
        writes: dict[str, list] = {}
        for node in ast.walk(fn):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        writes.setdefault(t.id, []).append(("value", node.value))
                    elif isinstance(t, ast.Tuple) and isinstance(node.value, ast.Tuple):
                        for tt, vv in zip(t.elts, node.value.elts):
                            if isinstance(tt, ast.Name):
                                writes.setdefault(tt.id, []).append(("value", vv))
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                writes.setdefault(node.target.id, []).append(("iter_or_value", node.value))
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr in ("append", "insert") and isinstance(node.func.value, ast.Name)):
                writes.setdefault(node.func.value.id, []).append(("value", node.args[-1]))
        ok: set[str] = set()
        while True:
            grown = {name for name, ws in writes.items() if name.endswith("_html") and all(
                self.safe(v, ok) or self.safe_iter(v, ok) or (kind == "iter_or_value" and self.safe(v, ok))
                for kind, v in ws)}
            if grown == ok:
                return ok
            ok = grown

    # -- the checks -----------------------------------------------------------------
    def run(self) -> list[str]:
        for fn in self.functions:
            for inner in [n for n in ast.walk(fn) if isinstance(n, ast.FunctionDef)]:
                ok = self.verified_names(inner) | (self.verified_names(fn) if inner is not fn else set())
                self.check(inner, ok)
        return self.offenders

    def check(self, fn, ok) -> None:
        for node in ast.walk(fn):
            if isinstance(node, ast.JoinedStr):
                literal = "".join(v.value for v in node.values if isinstance(v, ast.Constant))
                if "<" in literal or '="' in literal:
                    for v in node.values:
                        if isinstance(v, ast.FormattedValue) and not self.safe(v.value, ok):
                            self.offenders.append(f"{fn.name}:{v.lineno}: {ast.unparse(v.value)}")
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                for side, other in ((node.left, node.right), (node.right, node.left)):
                    if _is_html_literal(side) and not self.safe(other, ok):
                        self.offenders.append(f"{fn.name}:{node.lineno}: + {ast.unparse(other)}")
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) and _is_html_literal(node.left):
                self.offenders.append(f"{fn.name}:{node.lineno}: % formatting of HTML")
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr == "format" and _is_html_literal(node.func.value)):
                self.offenders.append(f"{fn.name}:{node.lineno}: .format() of HTML")
            elif isinstance(node, ast.Return) and node.value is not None and fn.name in self.builders:
                if not self.safe(node.value, ok):
                    self.offenders.append(f"{fn.name}:{node.lineno}: returns {ast.unparse(node.value)}")


def lint(source: str) -> list[str]:
    return HtmlLint(ast.parse(source)).run()


def test_every_html_interpolation_is_escaped_or_a_built_fragment():
    offenders = lint((BIN / "view.py").read_text())
    assert not offenders, "raw interpolation into HTML:\n" + "\n".join(offenders)


def test_the_lint_catches_the_ways_around_it():
    head = 'import html\ndef h(x): return x\nCSS = """x"""\n'
    cases = {
        "raw value in a *_html name": "def a_html(v):\n    x_html = v\n    return f'<b>{x_html}</b>'\n",
        "uppercase name": "def b_html(v):\n    RAW = v\n    return f'<b>{RAW}</b>'\n",
        ".format": "def c_html(v):\n    return '<b>{}</b>'.format(v)\n",
        "% formatting": "def d_html(v):\n    return '<b>%s</b>' % v\n",
        "builder returning raw": "def e_html(v):\n    return v\n",
        "raw append": "def f_html(v):\n    parts_html = []\n    parts_html.append(v)\n    return ''.join(parts_html)\n",
        "unknown call": "def g_html(v):\n    return f'<b>{str(v)}</b>'\n",
    }
    for name, body in cases.items():
        assert lint(head + body), name
    assert not lint(head + "def ok_html(v):\n    x_html = f'<i>{h(v)}</i>'\n    return f'<b>{x_html}</b>'\n")


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
