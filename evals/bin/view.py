"""The PR comment and the HTML report, each a pure function of summary.json (stdlib only).

Both lead with the verdict (a deterministic headline, its consequence and, when
knowable, a fix), then the five-link chain (stack -> version check -> reference
solutions -> agent -> judge), then the tasks. Anything the judge wrote is
labelled "Judge"; the system never speaks in its voice.
"""

from __future__ import annotations

import html
import re

MARKER = "<!-- lightcone-smoke-report -->"
ICON = {"ok": "✅", "bad": "❌", "skip": "⏭", "warn": "⚠️"}
MARK = {"fail": "❌", "warn": "⚠️", "pass": "✅"}


def e(text) -> str:
    return html.escape(str(text if text is not None else ""))


def md(text) -> str:
    """Escaped text with `inline code` as <code>: the summary's prose uses markdown backticks."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", e(text))


def fmt(v, spec="{:.0f}"):
    return "—" if v is None else spec.format(v)


def money(v: float) -> str:
    return f"${v:.2f}"


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
        j = t["judge"]
        if j:
            badges = " ".join(f"`{b}`" for b in j["badges"])
            lines.append(f"**Judge:** {j['summary']}" + (f" {badges}" if badges else ""))
            if j["fix"]:
                lines.append(f"**Judge suggests:** {j['fix']}")
        else:
            lines.append(f"**Judge not run:** {s['judge']['reason']}")
        if t["last_message"]:
            first = " / ".join(ln.strip() for ln in t["last_message"].splitlines() if ln.strip())[:240]
            lines.append(f"**Agent's last message:** {first}")
        base = t.get("base")
        nums = [f"{fmt(t['turns'])} turns", f"{t['stack_calls']} astra/lc calls"]
        if base:
            nums.append(f"main: {base['k']}/{base['n']}")
        if s["run"].get("report_url"):
            nums.append(f"[card →]({s['run']['report_url']}#{t['anchor']})")
        lines.append(" · ".join(nums))
    lines.append("")
    return lines


def comment_md(s: dict) -> str:
    v = s["verdict"]
    lines = [MARKER, f"## {MARK[v['state']]} Plugin smoke · {v['headline']}", ""]
    meta = [leg_title(s)] + stack_bits(s) + ([f"**{task_score(s)}**"] if task_score(s) else [])
    lines += [" · ".join(meta), ""]
    if v["consequence"]:
        lines += [v["consequence"], ""]
    if v["fix"]:
        lines += [f"**Fix:** {v['fix']}", ""]
    if v.get("judge_fix"):
        lines += [f"**Judge suggests:** {v['judge_fix']}", ""]
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
.diff .del{color:var(--bad)}.diff .add{color:var(--ok)}
.note{font-size:13px;color:var(--mute)}
"""


def dots(flags: list[bool]) -> str:
    return '<span class="dots">' + "".join(f'<i class="{"" if f else "x"}"></i>' for f in flags) + "</span>"


def hist(records: list[dict]) -> str:
    if not records:
        return '<span class="note">no runs on main yet</span>'
    cells = "".join(f'<i class="{"" if r["k"] == r["n"] else "x" if r["k"] == 0 else "p"}" '
                    f'title="{r["k"]}/{r["n"]}"></i>' for r in records)
    return f'<span class="hist">{cells}</span>'


def diff_html(diff: str) -> str:
    out = []
    for line in diff.splitlines():
        cls = "add" if line.startswith("+") and not line.startswith("+++") else (
            "del" if line.startswith("-") and not line.startswith("---") else "")
        out.append(f'<span class="{cls}">{e(line)}</span>')
    return '<pre class="diff">' + "\n".join(out) + "</pre>"


def check_html(c: dict, open_: bool) -> str:
    desc = f' <span class="cd">— {md(c["desc"])}</span>' if c["desc"] else ""
    out = f'<div class="out"><pre>{e(c["output"])}</pre></div>' if c["output"] else ""
    return (f'<details class="check {"ok" if c["ok"] else "bad"}"{" open" if open_ else ""}><summary>'
            f'<span class="ic">{"✓" if c["ok"] else "✗"}</span><span><span class="cn">{e(c["name"])}</span>{desc}'
            f'</span></summary>{out}</details>')


def timeline_html(rows: list[dict]) -> str:
    items = []
    for r in rows:
        if r["kind"] == "hook":
            chip = f'<div class="contra">{md(r["contradicted"])}</div>' if r.get("contradicted") else ""
            text = r["text"] if len(r["text"]) < 400 else r["text"][:400] + "…"
            items.append(f'<li class="hook"><span class="dot"></span><div class="t">{e(r["name"])}</div>'
                         f'<div class="d">{e(text)}</div>{chip}</li>')
        elif r["kind"] == "final":
            items.append(f'<li class="end"><span class="dot"></span><div class="t">Agent\'s last message</div>'
                         f'<div class="d">{e(r["text"])}</div></li>')
        else:
            code = f" · exit {r['exit']}" if r["exit"] not in (None, 0) else ""
            detail = r["output"] if r["error"] else r["note"][:220]
            items.append(f'<li class="{"err" if r["error"] else "tool"}"><span class="dot"></span>'
                         f'<div class="t">{e(r["turn"])}. {e(r["tool"])} · <code>{e(r["what"][:240])}</code>{e(code)}</div>'
                         f'<div class="d">{e(detail)}</div></li>')
    return f'<ol class="tl">{"".join(items)}</ol>' if items else '<p class="note">No trajectory.</p>'


def judge_html(t: dict, s: dict) -> str:
    j = t["judge"]
    if not j:
        return f'<div class="judge"><span class="who">Judge not run</span><div>{e(s["judge"]["reason"])}</div></div>'
    badges = "".join(f'<span class="badge">{e(b)}</span>' for b in j["badges"])
    fix = f'<div><b>Judge suggests:</b> {md(j["fix"])}</div>' if j["fix"] else ""
    crit = "".join(f"<li><b>{e(k)}</b> <i>{e(v.get('outcome'))}</i>: {e(v.get('explanation'))}</li>"
                   for k, v in j["checks"].items())
    return (f'<div class="judge"><span class="who">Judge</span><div>{md(j["summary"])}</div>{fix}<div>{badges}</div>'
            f'<details class="more"><summary>every criterion</summary><ul>{crit}</ul></details></div>')


def card_html(t: dict, s: dict, folded: bool = False) -> str:
    task = next((x for x in s["tasks"] if x["name"] == t["task"]), {})
    bad = [c["name"] for c in t["checks"] if not c["ok"]]
    if t["passed"]:
        head, pill = "", '<span class="pill ok">✓ passed</span>'
    else:
        head = (" and ".join(f"`{b}`" for b in bad) + " failed") if bad else (t["exception"] or "failed")
        if t["contradiction"]:
            head += f" — the {t['contradiction']}"
        pill = '<span class="pill bad">✗ failed</span>'
    who = "reference solution" if t["leg"] == "oracle" else t["label"]
    top = (f'<span class="name">{e(t["task"])}</span>{pill}<span class="note">{e(who)}</span>'
           + (f'<span class="head">{md(head)}</span>' if head else ""))
    left = ["<h3>What was checked</h3>"]
    if t["exception"]:
        left.append(f'<div class="check bad"><div class="out" style="padding:8px 10px"><b>{e(t["exception"])}</b>'
                    f'<pre>{e(t["exception_text"])}</pre></div></div>')
    left += [check_html(c, not c["ok"]) for c in t["checks"]]
    if not t["checks"] and t["stdout"]:
        left.append(f"<pre>{e(t['stdout'])}</pre>")
    d = t.get("deliverable")
    if d:
        if d["diff"]:
            left.append(f"<h3>The deliverable vs the reference</h3>{diff_html(d['diff'])}"
                        f"<details class='more'><summary>{e(d['name'])} as written</summary><pre>{e(d['body'])}</pre></details>")
        else:
            left.append(f"<h3>The deliverable</h3><details class='more'><summary>{e(d['name'])}</summary>"
                        f"<pre>{e(d['body'])}</pre></details>")
    if task.get("instruction"):
        left.append(f"<details class='more'><summary>The task prompt</summary><pre>{e(task['instruction'])}</pre></details>")
    if t["leg"] == "oracle":
        body = f'<div class="col">{"".join(left)}</div>'
        stats = ""
    else:
        right = ["<h3>What happened</h3>", judge_html(t, s), "<h3>Timeline</h3>", timeline_html(t["timeline"])]
        body = f'<div class="body"><div class="col">{"".join(left)}</div><div class="col">{"".join(right)}</div></div>'
        base = t.get("base")
        stats = (f'<div class="stats"><span><b>{fmt(t["turns"])}</b> turns</span><span><b>{t["stack_calls"]}</b> '
                 f'astra/lc calls</span><span>{"$%.3f" % t["cost_usd"] if t["cost_usd"] is not None else "—"}</span>'
                 f'<span>{fmt(t["agent_s"] and t["agent_s"] / 60, "{:.1f}")} min</span>'
                 + (f'<span>main: {base["k"]}/{base["n"]} passed, median {fmt(base["turns"])} turns</span>' if base else "")
                 + "</div>")
    cls = "bad" if not t["passed"] else ""
    if folded:
        return (f'<details class="card {cls}" id="{e(t["anchor"])}"><summary>{top}</summary>{body}{stats}</details>')
    return f'<section class="card {cls}" id="{e(t["anchor"])}"><header>{top}</header>{body}{stats}</section>'


def chain_html(s: dict) -> str:
    parts = []
    for i, c in enumerate(s["chain"], 1):
        if i > 1:
            parts.append('<div class="arrow">→</div>')
        parts.append(f'<div class="link {c["state"]}"><div class="k">{i} · {e(c["title"])}</div>'
                     f'<div class="v">{e(c["value"])}</div><div class="s">{e(c["sub"])}</div></div>')
    return f'<div class="chain">{"".join(parts)}</div>'


def tasks_html(s: dict) -> str:
    agent_ran = bool(agent_trials(s))
    legs = s["legs"]
    head = ("<th>task</th><th>" + ("the agent had to…" if agent_ran else "the reference solution shows that…")
            + "</th><th>reference</th>" + "".join(f"<th>{e(g['label'])}</th>" for g in legs)
            + ("<th>turns</th>" if agent_ran else "") + "<th>main, last 10</th>")
    rows = []
    for task in s["tasks"]:
        ref = task["reference"]
        if ref["passed"] is None:
            ref_cell = '<span class="pill skip">not run</span>'
        else:
            flags = [c["ok"] for c in ref["checks"]]
            ref_cell = (f'<span class="pill {"ok" if ref["passed"] else "bad"}">{"✓" if ref["passed"] else "✗"} '
                        f'{sum(flags)}/{len(flags)}{dots(flags)}</span>')
        cells, turns = [], []
        for g in legs:
            a = task["agent"].get(g["leg"]) or {"trials": [], "state": g["state"], "infra": 0}
            ts = a["trials"]
            if not ts:
                label = "not run" if g["state"] == "not run" else "not measured" if a["infra"] else "not in this run"
                cells.append(f'<td><span class="pill skip">{label}</span></td>')
                continue
            k = sum(t["passed"] for t in ts)
            cls = "ok" if k == len(ts) else "bad"
            cells.append(f'<td><a class="pill {cls}" href="#{e(ts[0]["anchor"])}">{"✓" if cls == "ok" else "✗"} '
                         f'{k}/{len(ts)}{dots([t["passed"] for t in ts])}</a></td>')
            turns.append(" · ".join(fmt(t["turns"]) for t in ts))
        what = task["had_to"] if agent_ran else task["proves"]
        rows.append(f'<tr><td class="task">{e(task["name"])}</td><td class="what">{md(what)}</td><td>{ref_cell}</td>'
                    + "".join(cells) + (f"<td>{e(' / '.join(turns)) or '—'}</td>" if agent_ran else "")
                    + f"<td>{hist(task['history'])}</td></tr>")
    return f'<h2>{"Tasks" if agent_ran else "What each task proves"}</h2><div class="wrap"><table class="grid">' \
           f'<tr>{head}</tr>{"".join(rows)}</table></div>'


def stack_card(s: dict) -> str:
    st = s.get("stack") or {}
    if not (st.get("skew") or st.get("override")):
        return ""
    lines = [f"version skew: {st['skew']}" if st.get("skew") else f"override: {st['override']}", "",
             f"installed  astra-tools {st.get('astra_tools')}   lightcone-cli {st.get('lightcone_cli')}",
             f"lc needs   astra-tools {st.get('lightcone_cli_requires_astra_tools')}",
             f"plugin pin astra-tools {st.get('plugin_astra_tools_pin')}"]
    return (f'<section class="card bad"><header><span class="name">version check</span>'
            f'<span class="pill bad">✗ {"skew" if st.get("skew") else "override"}</span></header>'
            f'<div class="col"><pre>$ evals/bin/stack-info.sh\n{e(chr(10).join(lines))}</pre></div></section>')


def page(s: dict) -> str:
    v = s["verdict"]
    run = s["run"]
    meta = [leg_title(s)] + stack_bits(s) + ([task_score(s)] if task_score(s) else [])
    if run.get("pr"):
        meta.insert(0, f"PR #{run['pr']}")
    meta.append(cost_line(s))
    link = f' · <a href="{e(run["url"])}">workflow run</a>' if run.get("url") else ""
    parts = [f'<div class="verdict {v["state"]}"><h1>{MARK[v["state"]]} {md(v["headline"])}</h1>']
    if v["consequence"]:
        parts.append(f"<p>{md(v['consequence'])}</p>")
    if v["fix"]:
        parts.append(f'<div class="fix"><b>Fix</b>{md(v["fix"])}</div>')
    if v.get("judge_fix"):
        parts.append(f'<div class="fix judge"><b>Judge suggests</b>{md(v["judge_fix"])}</div>')
    parts.append(f'<div class="meta">{" · ".join(e(m) for m in meta)}{link}</div></div>')
    others = [r for r in s["reasons"][1:] if r["headline"] != v["headline"]]
    if others:
        parts.append('<ul class="reasons">' + "".join(
            f'<li class="{"blocking" if r["blocking"] else "warning"}"><b>{"blocking" if r["blocking"] else "warning"}</b> · '
            f'{md(r["headline"])}' + (f" — <i>Fix:</i> {md(r['fix'])}" if r["fix"] else "") + "</li>" for r in others) + "</ul>")
    parts.append(chain_html(s))
    parts.append(tasks_html(s))
    if not agent_trials(s) and all(t["passed"] for t in s["trials"] if t["leg"] == "oracle") and \
            any(t["leg"] == "oracle" for t in s["trials"]) and (s.get("stack") or {}).get("skew"):
        parts.append('<p class="note">The reference solutions still pass: the skew breaks the plugin\'s promise '
                     "to users, not these tasks' verifiers. That is why the version check is its own link.</p>")
    parts.append(stack_card(s))
    failed = failed_trials(s)
    for t in failed:
        parts.append(card_html(t, s))
    passing = [t for t in agent_trials(s) if t["passed"]] + [t for t in agent_trials(s) if not t["passed"] and t not in failed]
    if passing:
        parts.append(f'<details class="more"><summary>Other attempts ({len(passing)}), folded</summary>'
                     + "".join(card_html(t, s, folded=True) for t in passing) + "</details>")
    oracle_ok = [t for t in s["trials"] if t["leg"] == "oracle" and t["passed"]]
    if oracle_ok:
        n = sum(len(t["checks"]) for t in oracle_ok)
        parts.append(f'<details class="more"><summary>Reference-solution checks, all {n} (expand)</summary>'
                     + "".join(card_html(t, s, folded=True) for t in oracle_ok) + "</details>")
    parts.append('<h2>For agents reading this run</h2><p class="note">Every value on this page comes from '
                 '<code>summary.json</code> (in the run\'s <code>smoke-summary</code> artifact): the verdict, the '
                 'blocking reasons with their fixes, each check\'s output, the timelines and the judge\'s notes. '
                 'The PR also carries GitHub annotations at each cause, such as the pin line in '
                 '<code>skills.config.json</code> for a version skew. Headlines and fixes are rule-based '
                 '(evals/bin/report.py); text marked Judge is the model judge\'s.</p>')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>Plugin smoke run</title>'
            f'<style>{CSS}</style></head><body><div class="page">{"".join(parts)}</div></body></html>')
