"""The PR comment and the HTML report, each a pure function of summary.json (stdlib only).

Both lead with the verdict (a terse, data-built headline and, for mechanical
causes, a fix), then the five-link chain (stack -> version check -> reference
solutions -> agent -> judge), then the tasks. The only prose is the judge's
ranked list of pain points, labelled Judge, each linked to its evidence.
"""

from __future__ import annotations

import html
import re

MARKER = "<!-- lightcone-smoke-report -->"
ICON = {"ok": "✅", "bad": "❌", "skip": "⏭", "warn": "⚠️"}
MARK = {"fail": "❌", "warn": "⚠️", "pass": "✅"}


def e(text) -> str:
    """Escape for HTML text and double-quoted attribute values alike."""
    return html.escape(str(text if text is not None else ""), quote=True)


h = e  # the page's one interpolation helper for strings


def md(text) -> str:
    """Escaped text with `inline code` as <code>: the summary's prose uses markdown backticks."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", e(text))


def is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def fmt(v, spec="{:.0f}"):
    """A number formatted by spec; anything that is not a number renders as a dash."""
    return spec.format(v) if is_num(v) else "—"


num = fmt  # numbers interpolated into the page go through this


def aid(v) -> str:
    """An element id or fragment: word characters, dots and dashes only."""
    v = str(v)
    return v if re.fullmatch(r"[\w.-]{1,240}", v) else "invalid"


def url(v) -> str:
    """A link target: GitHub or this project's Pages site only, escaped."""
    v = str(v or "")
    return e(v) if re.fullmatch(r"https://(github\.com|lightconeresearch\.github\.io)/[\w./#%?=&~+-]*", v) else "#"


def cls(v, allowed: tuple[str, ...]) -> str:
    """A CSS class from a fixed set."""
    return v if v in allowed else ""


def money(v) -> str:
    return f"${v:.2f}" if is_num(v) else "$—"


def cost_line(s: dict) -> str:
    total = s["cost_usd"]["agents"] + s["cost_usd"]["judge"]
    if not total and not any(t["leg"] != "oracle" for t in s["trials"]):
        return "$0.00 (no model was called)"
    return f"agent {money(s['cost_usd']['agents'])} · judge {money(s['cost_usd']['judge'])}"


def leg_title(s: dict) -> str:
    labels = [g["label"] for g in s["legs"]]
    return labels[0] if len(labels) == 1 else f"{len(labels)} legs" if labels else "reference solutions only"


def stack_bits(s: dict) -> list[str]:
    st = s.get("stack") or {}
    return [f"{name} {st[key]}" for name, key in (("astra-tools", "astra_tools"), ("lightcone-cli", "lightcone_cli"))
            if st.get(key)]


def agent_trials(s: dict) -> list[dict]:
    return [t for t in s["trials"] if t["leg"] != "oracle"]


def failed_trials(s: dict) -> list[dict]:
    """The failed trials worth a section: one per failing (leg, task), oracle first."""
    seen, out = set(), []
    for t in sorted(s["trials"], key=lambda t: (t["leg"] != "oracle", t["task"])):
        key = (t["leg"], t["task"])
        if not t["passed"] and key not in seen:
            seen.add(key)
            out.append(t)
    return out


def task_score(s: dict) -> str:
    agent = agent_trials(s)
    tasks = sorted({t["task"] for t in agent})
    if not tasks:
        return ""
    passed = sum(all(t["passed"] for t in agent if t["task"] == task) for task in tasks)
    return f"{passed}/{len(tasks)} tasks passed"


# --- the comment ----------------------------------------------------------------------

def md_fence(text: str, lines: int = 15) -> list[str]:
    rows = (text or "").rstrip().splitlines()
    body = "\n".join(rows[:lines] + (["…"] if len(rows) > lines else [])) or "(no output)"
    return ["```", body.replace("```", "ˋˋˋ"), "```"]


def md_trial(t: dict, s: dict) -> list[str]:
    who = "reference solution" if t["leg"] == "oracle" else (t["label"] if len(s["legs"]) > 1 else "")
    lines = [f"### ❌ {t['task']}" + (f" · {who}" if who else ""), ""]
    if t["exception"]:
        lines.append(f"The trial ended in `{t['exception']}`.")
        lines += md_fence(t["exception_text"])
    for c in (c for c in t["checks"] if not c["ok"]):
        desc = f" ({c['desc']})" if c["desc"] else ""
        rows = c["output"].strip().splitlines()
        if len(rows) <= 2 and c["first_error"]:
            lines.append(f"**`{c['name']}`** ✗{desc}: `{c['first_error']}`")
        else:
            lines.append(f"**`{c['name']}`** ✗{desc}")
            lines += md_fence(c["output"])
    if t["leg"] != "oracle":
        lines += md_judge(t, s, top=3)
        if t["last_message"]:
            first = " / ".join(ln.strip() for ln in t["last_message"].splitlines() if ln.strip())[:240]
            lines.append(f"last message: “{first}”")
        base = t.get("base")
        nums = [f"{fmt(t['turns'])} turns", f"{t['stack_calls']} astra/lc calls"]
        if base:
            nums.append(f"main: {base['k']}/{base['n']}")
        if s["run"].get("report_url"):
            nums.append(f"[card →]({s['run']['report_url']}#{t['anchor']})")
        lines.append(" · ".join(nums))
    lines.append("")
    return lines


def evidence_link(t: dict, item: dict, s: dict) -> str:
    if item.get("step") is None:
        return item.get("evidence") or ""
    url = s["run"].get("report_url")
    label = item["evidence"]
    return f"[{label}]({url}#{t['anchor']}-s{item['step']})" if url else label


def md_judge(t: dict, s: dict, top: int | None = None) -> list[str]:
    j = t["judge"]
    if not j or j.get("error"):
        return [f"Judge not run: {j['error'] if j else s['judge']['reason']}"]
    items = j["items"][:top] if top else j["items"]
    if not items:
        return ["Judge: —"]
    out = ["Judge:"]
    for i, item in enumerate(items, 1):
        badge = f"`{item['badge']}` " if item["badge"] else ""
        ev = evidence_link(t, item, s)
        out.append(f"{i}. {badge}{item['point']}" + (f" ({ev})" if ev else ""))
    more = len(j["items"]) - len(items)
    if more > 0:
        out.append(f"   …and {more} more on the card")
    return out


def comment_md(s: dict) -> str:
    v = s["verdict"]
    lines = [MARKER, f"## {MARK[v['state']]} Plugin smoke · {v['headline']}", ""]
    meta = [leg_title(s)] + stack_bits(s) + ([f"**{task_score(s)}**"] if task_score(s) else [])
    lines += [" · ".join(meta), ""]
    if v["fix"]:
        lines += [f"**Fix:** {v['fix']}", ""]
    links = []
    for c in s["chain"]:
        text = f"{c['title'].lower()} {ICON[c['state']]}"
        if c["key"] in ("oracle", "agent", "judge") or c["state"] != "ok":
            text += f" {c['value']}"
        links.append(f"**{text}**" if c["state"] == "bad" else text)
    chain = " → ".join(links)
    lines += [chain, ""]
    others = [r for r in s["reasons"][1:] if r["blocking"] or r["class"] != "agent_check"]
    shown = {s["verdict"]["headline"]}
    for r in others:
        if r["headline"] in shown:
            continue
        shown.add(r["headline"])
        tag = "blocking" if r["blocking"] else "warning"
        lines.append(f"- **{tag}** · {r['headline']}" + (f". Fix: {r['fix']}" if r["fix"] else ""))
    if len(shown) > 1:
        lines.append("")
    for t in failed_trials(s):
        lines += md_trial(t, s)
    passing = [t for t in agent_trials(s) if t["passed"]]
    failed_tasks = {t["task"] for t in agent_trials(s) if not t["passed"]}
    if passing:
        tasks = sorted({t["task"] for t in passing} - failed_tasks)
        bits = []
        for task in tasks:
            ts = [t for t in passing if t["task"] == task]
            turns = "·".join(fmt(t["turns"]) for t in ts)
            badge = " ⚠️ " + " ".join(f"`{b}`" for b in sorted({b for t in ts if t["judge"] for b in t["judge"]["badges"]})) \
                if any(t["judge"] and t["judge"]["badges"] for t in ts) else ""
            base = ts[0].get("base")
            delta = f" (main {fmt(base['turns'])})" if base and base.get("turns") is not None else ""
            bits.append(f"{task} {turns} turns{delta}{badge}")
        if tasks:
            lines += [f"### ✅ {len(tasks)} passed", " · ".join(bits), ""]
    oracle = [t for t in s["trials"] if t["leg"] == "oracle"]
    if oracle:
        n_ok = sum(t["passed"] for t in oracle)
        checks = sum(len(t["checks"]) for t in oracle)
        ok_checks = sum(c["ok"] for t in oracle for c in t["checks"])
        lines += [f"<details><summary>Reference solutions: {n_ok}/{len(oracle)} tasks, "
                  f"{ok_checks}/{checks} checks</summary>", "",
                  "| task | proves | checks |", "|---|---|---|"]
        for task in s["tasks"]:
            ref = next((t for t in oracle if t["task"] == task["name"]), None)
            if not ref:
                continue
            marks = " · ".join(f"{'✅' if c['ok'] else '❌'} {c['name']}" for c in ref["checks"])
            lines.append(f"| {task['name']} | {task['proves']} | {marks} |")
        lines += ["", "</details>", ""]
    tail = []
    if s["run"].get("report_url"):
        tail.append(f"**[Full report →]({s['run']['report_url']})**")
    if s["run"].get("url"):
        tail.append(f"[run {s['run'].get('id') or ''}]({s['run']['url']})".replace("[run ]", "[workflow run]"))
    tail.append(cost_line(s))
    lines.append(" · ".join(tail))
    return "\n".join(lines) + "\n"


# --- the page -------------------------------------------------------------------------

CSS = """
:root{--bg:#f7f6f2;--card:#ffffff;--ink:#1c1b18;--mute:#6c6a63;--line:#e3e0d7;
--ok:#2f6f3e;--ok-bg:#e6f1e8;--bad:#b0301f;--bad-bg:#fbe9e5;--warn:#8a5a00;--warn-bg:#fbf1dc;
--skip:#8b8980;--skip-bg:#efeee9;--hook:#3d5ba0;--hook-bg:#e8edf8;--code:#f2f0ea;
--mono:ui-monospace,"JetBrains Mono","IBM Plex Mono",Menlo,monospace;--sans:system-ui,-apple-system,"Segoe UI",sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161614;--card:#1f1f1c;--ink:#ecebe6;--mute:#a3a198;
--line:#34332e;--ok:#8fd19e;--ok-bg:#1d3324;--bad:#ff8f80;--bad-bg:#3a1f1a;--warn:#f2c46d;--warn-bg:#3a2e14;
--skip:#8f8d85;--skip-bg:#2a2a26;--hook:#9db4ec;--hook-bg:#1f2840;--code:#262622}}
:root[data-theme="dark"]{--bg:#161614;--card:#1f1f1c;--ink:#ecebe6;--mute:#a3a198;--line:#34332e;--ok:#8fd19e;--ok-bg:#1d3324;
--bad:#ff8f80;--bad-bg:#3a1f1a;--warn:#f2c46d;--warn-bg:#3a2e14;--skip:#8f8d85;--skip-bg:#2a2a26;--hook:#9db4ec;--hook-bg:#1f2840;--code:#262622}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 var(--sans)}
.page{max-width:1080px;margin:0 auto;padding:20px 16px 64px}
.verdict{border-radius:12px;padding:16px 18px;margin-bottom:14px;border:1px solid var(--line);background:var(--card)}
.verdict.fail{border-left:6px solid var(--bad)}.verdict.warn{border-left:6px solid var(--warn)}.verdict.pass{border-left:6px solid var(--ok)}
.verdict h1{font-size:20px;line-height:1.3;margin:0 0 6px}.verdict p{margin:4px 0}
.fix{margin-top:10px;padding:10px 12px;border-radius:8px;background:var(--code)}
.fix b{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--mute);margin-right:6px}
.fix.judge{border-left:3px solid var(--warn)}
.meta{font-size:13px;color:var(--mute);margin-top:8px}.meta a{color:inherit}
.reasons{list-style:none;padding:0;margin:8px 0}.reasons li{font-size:14px;padding:6px 10px;border-radius:8px;margin:4px 0;background:var(--card);border:1px solid var(--line)}
.reasons li.blocking{border-left:4px solid var(--bad)}.reasons li.warning{border-left:4px solid var(--warn)}
code,.mono{font-family:var(--mono);font-size:.9em}
pre{font:12.5px/1.45 var(--mono);background:var(--code);border-radius:8px;padding:10px 12px;margin:6px 0;overflow-x:auto;white-space:pre-wrap;word-break:break-word}
.chain{display:flex;align-items:stretch;margin:16px 0 22px;overflow-x:auto;padding-bottom:4px}
.link{flex:1 1 0;min-width:128px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.arrow{flex:0 0 18px;display:flex;align-items:center;justify-content:center;color:var(--mute)}
.link .k{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--mute)}
.link .v{font-weight:600;margin-top:2px}.link .s{font-size:12.5px;color:var(--mute);margin-top:2px}
.link.ok{border-top:4px solid var(--ok)}.link.ok .v{color:var(--ok)}
.link.bad{border-top:4px solid var(--bad);background:var(--bad-bg)}.link.bad .v{color:var(--bad)}
.link.skip{border-top:4px dashed var(--skip);background:var(--skip-bg)}.link.skip .v{color:var(--skip)}
.link.warn{border-top:4px solid var(--warn)}.link.warn .v{color:var(--warn)}
@media (max-width:600px){.chain{flex-direction:column}.link{min-width:0}.arrow{flex:0 0 16px;transform:rotate(90deg)}
.grid td.what,.grid th:nth-child(2){display:none}}
h2{font-size:15px;letter-spacing:.04em;text-transform:uppercase;color:var(--mute);margin:26px 0 8px;font-weight:600}
.wrap{overflow-x:auto}
.grid{width:100%;border-collapse:separate;border-spacing:0;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.grid th,.grid td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:middle}
.grid tr:last-child td{border-bottom:0}.grid th{font-size:12px;color:var(--mute);font-weight:600;background:var(--bg)}
.grid td.task{font-family:var(--mono);font-size:13px;white-space:nowrap}.grid td.what{color:var(--mute);font-size:13px}
.grid a{color:inherit}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:600;border-radius:999px;padding:2px 9px;white-space:nowrap}
.pill.ok{color:var(--ok);background:var(--ok-bg)}.pill.bad{color:var(--bad);background:var(--bad-bg)}
.pill.skip{color:var(--skip);background:var(--skip-bg)}.pill.warn{color:var(--warn);background:var(--warn-bg)}
.dots{display:inline-flex;gap:3px;vertical-align:middle;margin-left:4px}
.dots i{width:8px;height:8px;border-radius:50%;display:block;background:var(--ok)}.dots i.x{background:var(--bad)}
.hist{display:inline-flex;gap:2px;vertical-align:middle}
.hist i{width:7px;height:14px;border-radius:2px;background:var(--ok);opacity:.85}.hist i.x{background:var(--bad)}.hist i.p{background:var(--warn)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:14px 0;overflow:hidden}
.card>header,.card>summary{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;padding:12px 16px;border-bottom:1px solid var(--line)}
.card>summary{cursor:pointer;list-style:none;border-bottom:0}.card[open]>summary{border-bottom:1px solid var(--line)}
.card .name{font-family:var(--mono);font-weight:600}.card .head{font-weight:600}
.card.bad>header{background:var(--bad-bg)}
.body{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr)}
@media (max-width:760px){.body{grid-template-columns:1fr}}
.col{padding:12px 16px;min-width:0}.col+.col{border-left:1px solid var(--line)}
@media (max-width:760px){.col+.col{border-left:0;border-top:1px solid var(--line)}}
.col h3{font-size:12px;letter-spacing:.07em;text-transform:uppercase;color:var(--mute);margin:4px 0 8px;font-weight:600}
.check{border:1px solid var(--line);border-radius:8px;margin:8px 0;overflow:hidden}
.check>summary{list-style:none;cursor:pointer;padding:8px 10px;display:flex;gap:8px;align-items:flex-start}
.check>summary::-webkit-details-marker{display:none}
.check .ic{font-weight:700;width:16px;flex:0 0 16px}.check.ok .ic{color:var(--ok)}.check.bad .ic{color:var(--bad)}
.check.bad{border-color:var(--bad)}.check .cn{font-family:var(--mono);font-size:13px;font-weight:600}
.check .cd{font-size:13px;color:var(--mute)}.check .out{padding:0 10px 8px 34px}
.judge{border-left:3px solid var(--warn);padding:2px 0 2px 12px;margin:6px 0 10px}
.pains{margin:4px 0 0;padding-left:20px}.pains li{margin:4px 0}.ev{font:12px var(--mono);color:var(--mute)}
.judge .who{font-size:12px;font-weight:600;color:var(--warn);text-transform:uppercase;letter-spacing:.06em}
.badge{display:inline-block;font:600 11.5px var(--mono);border-radius:6px;padding:1px 7px;margin:2px 4px 2px 0;background:var(--warn-bg);color:var(--warn)}
.tl{list-style:none;margin:0;padding:0;position:relative}
.tl:before{content:"";position:absolute;left:11px;top:6px;bottom:6px;width:2px;background:var(--line)}
.tl li{position:relative;padding:4px 0 8px 32px}
.tl li .dot{position:absolute;left:4px;top:7px;width:16px;height:16px;border-radius:50%;background:var(--card);border:2px solid var(--mute)}
.tl li.tool .dot{border-color:var(--ink)}.tl li.hook .dot{border-color:var(--hook);background:var(--hook-bg)}
.tl li.err .dot{border-color:var(--bad);background:var(--bad-bg)}.tl li.end .dot{border-color:var(--ok)}
.tl .t{font-size:13.5px}.tl .d{font:12.5px var(--mono);color:var(--mute);word-break:break-word;white-space:pre-wrap}
.tl li.hook .t{color:var(--hook);font-weight:600}.tl li.err .t{color:var(--bad)}
.contra{display:inline-block;margin-top:4px;font-size:12.5px;font-weight:600;color:var(--bad);background:var(--bad-bg);border-radius:6px;padding:2px 8px}
.stats{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--mute);padding:10px 16px;border-top:1px solid var(--line)}
.stats b{color:var(--ink);font-weight:600}
details.more>summary{cursor:pointer;color:var(--mute);font-size:13px;margin:6px 0}
.file{padding:8px 0;white-space:pre;overflow-x:auto;word-break:normal}.file .ln{display:block;padding:0 10px}.file .no{display:inline-block;width:2.4em;color:var(--mute);user-select:none}
.file .ln.hl{background:var(--bad-bg)}.file .gerr{display:block;margin-left:2.4em;color:var(--bad);font-weight:600}
.diff .del{color:var(--bad)}.diff .add{color:var(--ok)}
.note{font-size:13px;color:var(--mute)}
"""


STATES = ("ok", "bad", "skip", "warn")


def dots(flags: list[bool]) -> str:
    dots_html = "".join(f'<i class="{h("" if f is True else "x")}"></i>' for f in flags)
    return f'<span class="dots">{dots_html}</span>'


def hist(records: list[dict]) -> str:
    if not records:
        return '<span class="note">no runs on main yet</span>'
    cells_html = "".join(
        f'<i class="{h("" if r.get("k") == r.get("n") else "x" if r.get("k") == 0 else "p")}" '
        f'title="{num(r.get("k"))}/{num(r.get("n"))}"></i>' for r in records)
    return f'<span class="hist">{cells_html}</span>'


def diff_html(diff: str) -> str:
    lines_html = "\n".join(
        f'<span class="{h(cls_)}">{h(line)}</span>'
        for line, cls_ in ((ln, "add" if ln.startswith("+") and not ln.startswith("+++") else
                            "del" if ln.startswith("-") and not ln.startswith("---") else "")
                           for ln in str(diff).splitlines()))
    return f'<pre class="diff">{lines_html}</pre>'


SMALL_DIFF = 12  # changed lines up to which the diff against the reference shows inline


def deliverable_html(d: dict, open_: bool) -> str:
    """The file as written, the lines the verifier's errors point at marked; the diff only when small."""
    marks: dict[int, list[str]] = {}
    for m in d.get("error_lines") or []:
        if is_num(m.get("line")):
            marks.setdefault(int(m["line"]), []).append(f"{m.get('path')}: {m.get('error')}")
    rows_html = "".join(
        f'<span class="ln{h(" hl" if n in marks else "")}"><span class="no">{num(n)}</span>'
        f'<span class="src">{h(line or " ")}</span>'
        + "".join(f'<span class="gerr">{h(x)}</span>' for x in marks.get(n, []))
        + "</span>"
        for n, line in enumerate(str(d.get("body", "")).rstrip("\n").splitlines(), 1))
    file_html = f'<pre class="file">{rows_html}</pre>'
    changed = d.get("changed_lines") if is_num(d.get("changed_lines")) else 0
    diff_part_html = ""
    if d.get("diff") and changed <= SMALL_DIFF:
        diff_part_html = f"<h3>Diff vs reference ({num(changed)} lines)</h3>{diff_html(d['diff'])}"
    elif d.get("diff"):
        diff_part_html = (f"<details class='more'><summary>diff vs reference ({num(changed)} changed lines)</summary>"
                          f"{diff_html(d['diff'])}</details>")
    flagged = f" · {len(marks)} line{'s' * (len(marks) != 1)} flagged" if marks else ""
    head_html = f"<h3>The deliverable: {h(d.get('name'))}{h(flagged)}</h3>"
    if open_ or marks:
        return f"{head_html}{file_html}{diff_part_html}"
    return f"<details class='more'><summary>{h(d.get('name'))} as written</summary>{file_html}</details>{diff_part_html}"


def check_html(c: dict, open_: bool) -> str:
    ok = c.get("ok") is True
    desc_html = f' <span class="cd">— {md(c["desc"])}</span>' if c.get("desc") else ""
    out_html = f'<div class="out"><pre>{h(c["output"])}</pre></div>' if c.get("output") else ""
    open_attr_html = " open" if open_ else ""
    return (f'<details class="check {h("ok" if ok else "bad")}"{open_attr_html}><summary>'
            f'<span class="ic">{h("✓" if ok else "✗")}</span><span><span class="cn">{h(c.get("name"))}</span>'
            f'{desc_html}</span></summary>{out_html}</details>')


def timeline_html(rows: list[dict], prefix: str = "") -> str:
    seen: set[str] = set()

    def anchor_html(r: dict, suffix: str = "") -> str:
        if not is_num(r.get("step")) or not prefix:
            return ""
        ident = f"{aid(prefix)}-s{int(r['step'])}{suffix}"
        if ident in seen:
            return ""
        seen.add(ident)
        return f' id="{aid(ident)}"'

    items_html = []
    for r in rows:
        kind = r.get("kind")
        if kind == "hook":
            chip_html = f'<div class="contra">{md(r["contradicted"])}</div>' if r.get("contradicted") else ""
            text = str(r.get("text", ""))
            text = text if len(text) < 400 else text[:400] + "…"
            items_html.append(f'<li class="hook"{anchor_html(r, "-hook")}><span class="dot"></span>'
                              f'<div class="t">{h(r.get("name"))}</div><div class="d">{h(text)}</div>{chip_html}</li>')
        elif kind == "note":
            items_html.append(f'<li class="tool"><span class="dot"></span><div class="d">{h(r.get("text"))}</div></li>')
        elif kind == "final":
            items_html.append(f'<li class="end"><span class="dot"></span><div class="t">Agent\'s last message</div>'
                              f'<div class="d">{h(r.get("text"))}</div></li>')
        else:
            code = f" · exit {num(r.get('exit'))}" if is_num(r.get("exit")) and r.get("exit") != 0 else ""
            detail = r.get("output", "") if r.get("error") is True else ""
            items_html.append(f'<li class="{h("err" if r.get("error") is True else "tool")}"{anchor_html(r)}>'
                              f'<span class="dot"></span><div class="t">{num(r.get("turn"))}. {h(r.get("tool"))} · '
                              f'<code>{h(str(r.get("what", ""))[:240])}</code>{h(code)}</div>'
                              f'<div class="d">{h(detail)}</div></li>')
    all_items_html = "".join(items_html)
    return f'<ol class="tl">{all_items_html}</ol>' if items_html else '<p class="note">No trajectory.</p>'


def judge_html(t: dict, s: dict) -> str:
    """The judge's ranked pain points, each with a link to its evidence row in the timeline."""
    j = t.get("judge")
    if not j or j.get("error"):
        why = j["error"] if j else s["judge"].get("reason")
        return f'<div class="judge"><span class="who">Judge not run</span> <span class="note">{h(why)}</span></div>'
    if not j.get("items"):
        return '<div class="judge"><span class="who">Judge</span> <span class="note">—</span></div>'
    rows_html = []
    for item in j["items"]:
        badge_html = f'<span class="badge">{h(item["badge"])}</span>' if item.get("badge") else ""
        ev_html = ""
        if is_num(item.get("step")):
            ev_html = (f' <a class="ev" href="#{aid(t["anchor"])}-s{num(int(item["step"]))}">'
                       f'{h(item.get("evidence"))}</a>')
        elif item.get("evidence"):
            ev_html = f' <span class="note">{h(item["evidence"])}</span>'
        rows_html.append(f"<li>{badge_html}{md(item.get('point'))}{ev_html}</li>")
    list_html = "".join(rows_html)
    return f'<div class="judge"><span class="who">Judge</span><ol class="pains">{list_html}</ol></div>'


def card_html(t: dict, s: dict, folded: bool = False) -> str:
    task = next((x for x in s["tasks"] if x.get("name") == t.get("task")), {})
    passed = t.get("passed") is True
    bad = [c.get("name") for c in t.get("checks", []) if c.get("ok") is not True]
    if passed:
        head, pill_html = "", '<span class="pill ok">✓ passed</span>'
    else:
        head = " ".join(f"`{b}` ✗" for b in bad) if bad else str(t.get("exception") or "failed")
        first = next((c.get("first_error") for c in t.get("checks", []) if c.get("ok") is not True and c.get("first_error")), "")
        if first:
            head += f" · “{first}”"
        if t.get("contradiction"):
            head += f" · {t['contradiction']}"
        pill_html = '<span class="pill bad">✗ failed</span>'
    who = "reference solution" if t.get("leg") == "oracle" else t.get("label")
    head_html = f'<span class="head">{md(head)}</span>' if head else ""
    top_html = f'<span class="name">{h(t.get("task"))}</span>{pill_html}<span class="note">{h(who)}</span>{head_html}'
    left_html = ["<h3>What was checked</h3>"]
    if t.get("exception"):
        left_html.append(f'<div class="check bad"><div class="out" style="padding:8px 10px"><b>{h(t["exception"])}</b>'
                         f'<pre>{h(t.get("exception_text"))}</pre></div></div>')
    left_html += [check_html(c, c.get("ok") is not True) for c in t.get("checks", [])]
    if not t.get("checks") and t.get("stdout"):
        left_html.append(f"<pre>{h(t['stdout'])}</pre>")
    if t.get("deliverable"):
        left_html.append(deliverable_html(t["deliverable"], open_=not passed))
    if task.get("instruction"):
        left_html.append(f"<details class='more'><summary>The task prompt</summary><pre>{h(task['instruction'])}</pre></details>")
    left_col_html = "".join(left_html)
    anchor = aid(t.get("anchor"))
    if t.get("leg") == "oracle":
        body_html = f'<div class="col">{left_col_html}</div>'
        stats_html = ""
    else:
        right_col_html = f'{judge_html(t, s)}<h3>Timeline</h3>{timeline_html(t.get("timeline", []), anchor)}'
        body_html = f'<div class="body"><div class="col">{left_col_html}</div><div class="col">{right_col_html}</div></div>'
        base = t.get("base") or {}
        base_html = (f'<span>main: {num(base.get("k"))}/{num(base.get("n"))} passed, median {num(base.get("turns"))} turns</span>'
                     if base else "")
        minutes = t["agent_s"] / 60 if is_num(t.get("agent_s")) else None
        stats_html = (f'<div class="stats"><span><b>{num(t.get("turns"))}</b> turns</span>'
                      f'<span><b>{num(t.get("stack_calls"))}</b> astra/lc calls</span>'
                      f'<span>{h(money(t.get("cost_usd")) if is_num(t.get("cost_usd")) else "—")}</span>'
                      f'<span>{num(minutes, "{:.1f}")} min</span>{base_html}</div>')
    if folded:
        return (f'<details class="card {h("" if passed else "bad")}" id="{aid(anchor)}"><summary>{top_html}</summary>'
                f'{body_html}{stats_html}</details>')
    return (f'<section class="card {h("" if passed else "bad")}" id="{aid(anchor)}"><header>{top_html}</header>'
            f'{body_html}{stats_html}</section>')


def chain_html(s: dict) -> str:
    parts_html = []
    for i, c in enumerate(s["chain"], 1):
        if i > 1:
            parts_html.append('<div class="arrow">→</div>')
        parts_html.append(f'<div class="link {cls(c.get("state"), STATES)}"><div class="k">{num(i)} · {h(c.get("title"))}</div>'
                          f'<div class="v">{h(c.get("value"))}</div><div class="s">{h(c.get("sub"))}</div></div>')
    links_html = "".join(parts_html)
    return f'<div class="chain">{links_html}</div>'


def tasks_html(s: dict) -> str:
    agent_ran = bool(agent_trials(s))
    legs = s["legs"]
    leg_heads_html = "".join(f"<th>{h(g.get('label'))}</th>" for g in legs)
    what_head = "the agent had to…" if agent_ran else "the reference solution shows that…"
    turns_head_html = "<th>turns</th>" if agent_ran else ""
    rows_html = []
    for task in s["tasks"]:
        ref = task.get("reference") or {}
        if ref.get("passed") is None:
            ref_cell_html = '<span class="pill skip">not run</span>'
        else:
            flags = [c.get("ok") is True for c in ref.get("checks", [])]
            ok = ref.get("passed") is True
            ref_cell_html = (f'<span class="pill {h("ok" if ok else "bad")}">{h("✓" if ok else "✗")} '
                             f'{num(sum(flags))}/{num(len(flags))}{dots(flags)}</span>')
        cells_html, turns = [], []
        for g in legs:
            a = (task.get("agent") or {}).get(g.get("leg")) or {"trials": [], "state": g.get("state"), "infra": 0}
            ts = a.get("trials") or []
            if not ts:
                label = ("not run" if g.get("state") == "not run" else "not measured" if a.get("infra")
                         else "not in this run")
                cells_html.append(f'<td><span class="pill skip">{h(label)}</span></td>')
                continue
            k = sum(x.get("passed") is True for x in ts)
            ok = k == len(ts)
            cells_html.append(f'<td><a class="pill {h("ok" if ok else "bad")}" href="#{aid(ts[0].get("anchor"))}">'
                              f'{h("✓" if ok else "✗")} {num(k)}/{num(len(ts))}'
                              f'{dots([x.get("passed") is True for x in ts])}</a></td>')
            turns.append(" · ".join(num(x.get("turns")) for x in ts))
        what = task.get("had_to") if agent_ran else task.get("proves")
        agent_cells_html = "".join(cells_html)
        turns_cell_html = f"<td>{h(' / '.join(turns) or '—')}</td>" if agent_ran else ""
        rows_html.append(f'<tr><td class="task">{h(task.get("name"))}</td><td class="what">{md(what)}</td>'
                         f'<td>{ref_cell_html}</td>{agent_cells_html}{turns_cell_html}'
                         f'<td>{hist(task.get("history") or [])}</td></tr>')
    title = "Tasks" if agent_ran else "What each task proves"
    body_rows_html = "".join(rows_html)
    return (f'<h2>{h(title)}</h2><div class="wrap"><table class="grid"><tr><th>task</th><th>{h(what_head)}</th>'
            f'<th>reference</th>{leg_heads_html}{turns_head_html}<th>main, last 10</th></tr>{body_rows_html}</table></div>')


def stack_card(s: dict) -> str:
    st = s.get("stack") or {}
    if not (st.get("skew") or st.get("override")):
        return ""
    lines = [f"version skew: {st['skew']}" if st.get("skew") else f"override: {st['override']}", "",
             f"installed  astra-tools {st.get('astra_tools')}   lightcone-cli {st.get('lightcone_cli')}",
             f"lc needs   astra-tools {st.get('lightcone_cli_requires_astra_tools')}",
             f"plugin pin astra-tools {st.get('plugin_astra_tools_pin')}"]
    kind = "skew" if st.get("skew") else "override"
    return (f'<section class="card bad"><header><span class="name">version check</span>'
            f'<span class="pill bad">✗ {h(kind)}</span></header>'
            f'<div class="col"><pre>$ evals/bin/stack-info.sh\n{h(chr(10).join(lines))}</pre></div></section>')


def page(s: dict) -> str:
    v = s["verdict"]
    run = s["run"]
    meta = [leg_title(s)] + stack_bits(s) + ([task_score(s)] if task_score(s) else [])
    if run.get("pr"):
        meta.insert(0, f"PR #{run['pr']}")
    meta.append(cost_line(s))
    link_html = f' · <a href="{url(run.get("url"))}">workflow run</a>' if run.get("url") else ""
    fix_html = f'<div class="fix"><b>Fix</b>{md(v["fix"])}</div>' if v.get("fix") else ""
    meta_html = " · ".join(h(m) for m in meta)
    parts_html = [f'<div class="verdict {cls(v.get("state"), ("fail", "warn", "pass"))}">'
                  f'<h1>{h(MARK.get(v.get("state"), ""))} {md(v.get("headline"))}</h1>{fix_html}'
                  f'<div class="meta">{meta_html}{link_html}</div></div>']
    others = [r for r in s["reasons"][1:] if r.get("headline") != v.get("headline")]
    if others:
        reasons_html = "".join(
            f'<li class="{h("blocking" if r.get("blocking") is True else "warning")}">'
            f'<b>{h("blocking" if r.get("blocking") is True else "warning")}</b> · {md(r.get("headline"))}'
            + (f" — <i>Fix:</i> {md(r['fix'])}" if r.get("fix") else "") + "</li>" for r in others)
        parts_html.append(f'<ul class="reasons">{reasons_html}</ul>')
    parts_html += [chain_html(s), tasks_html(s), stack_card(s)]
    failed = failed_trials(s)
    parts_html += [card_html(t, s) for t in failed]
    passing = [t for t in agent_trials(s) if t.get("passed") is True] + \
              [t for t in agent_trials(s) if t.get("passed") is not True and t not in failed]
    if passing:
        folded_html = "".join(card_html(t, s, folded=True) for t in passing)
        parts_html.append(f'<details class="more"><summary>Passing attempts ({num(len(passing))}), folded</summary>'
                          f'{folded_html}</details>')
    oracle_ok = [t for t in s["trials"] if t.get("leg") == "oracle" and t.get("passed") is True]
    if oracle_ok:
        n = sum(len(t.get("checks", [])) for t in oracle_ok)
        oracle_html = "".join(card_html(t, s, folded=True) for t in oracle_ok)
        parts_html.append(f'<details class="more"><summary>Reference-solution checks, all {num(n)} (expand)</summary>'
                          f'{oracle_html}</details>')
    parts_html.append('<p class="note">for agents: every value here is in <code>summary.json</code> (artifact '
                      '<code>smoke-summary</code>) · headlines and fixes: rules in <code>evals/bin/report.py</code> · '
                      'Judge: the model judge</p>')
    page_html = "".join(parts_html)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>Plugin smoke run</title>'
            f'<style>{CSS}</style></head><body><div class="page">{page_html}</div></body></html>')
