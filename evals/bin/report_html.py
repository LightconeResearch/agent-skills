"""The smoke run as one self-contained HTML page (stdlib only; report.py builds the model).

One card per trial, failures first: the prompt, each verifier check with its
output, the judge's summary and badges, a turn-by-turn timeline with hook
messages inline, the deliverable against the reference, and the cell's history
on main from the baseline pool.
"""

from __future__ import annotations

import html
import statistics

import trialview
from trialview import leg_label, money, outcome

CSS = """
:root{--bg:#fbfaf7;--card:#ffffff;--fg:#1d1d1b;--mute:#6b6a65;--line:#e4e1d9;--code:#f4f2ec;
--bad:#b3261e;--bad-bg:#fbe9e7;--warn:#8a5a00;--warn-bg:#fdf3dc;--ok:#2e6b3a;--ok-bg:#e6f2e8;--hook:#3c5a99;--hook-bg:#e8eefb}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#171715;--card:#1f1f1c;--fg:#ecebe6;
--mute:#a19f97;--line:#36352f;--code:#262622;--bad:#ff8a80;--bad-bg:#3a1f1c;--warn:#f2c46d;--warn-bg:#352a14;
--ok:#8fd19e;--ok-bg:#1c2e20;--hook:#9db7ee;--hook-bg:#1d2538}}
:root[data-theme="dark"]{--bg:#171715;--card:#1f1f1c;--fg:#ecebe6;--mute:#a19f97;--line:#36352f;--code:#262622;
--bad:#ff8a80;--bad-bg:#3a1f1c;--warn:#f2c46d;--warn-bg:#352a14;--ok:#8fd19e;--ok-bg:#1c2e20;--hook:#9db7ee;--hook-bg:#1d2538}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,sans-serif;margin:0 auto;padding:16px;max-width:1100px}
h1{font-size:22px;margin:4px 0}h2{font-size:17px;margin:0}h3{font-size:14px;margin:16px 0 6px;color:var(--mute);text-transform:uppercase;letter-spacing:.04em}
a{color:inherit}.mute{color:var(--mute)}code,pre{font:12.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}
pre{background:var(--code);padding:10px;border-radius:6px;overflow-x:auto;white-space:pre-wrap;word-break:break-word;margin:6px 0}
.meta{color:var(--mute);margin:4px 0 12px}
.notes{list-style:none;padding:0;margin:12px 0}.notes li{padding:8px 12px;border-radius:6px;margin:6px 0}
.notes .bad{background:var(--bad-bg);color:var(--bad)}.notes .warn{background:var(--warn-bg);color:var(--warn)}
.grid{width:100%;border-collapse:collapse;margin:12px 0}.grid td,.grid th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}
.wrap{overflow-x:auto}
.pill{display:inline-block;border-radius:10px;padding:1px 9px;font-size:13px;text-decoration:none;white-space:nowrap}
.pill.ok{background:var(--ok-bg);color:var(--ok)}.pill.bad{background:var(--bad-bg);color:var(--bad)}.pill.warn{background:var(--warn-bg);color:var(--warn)}
.chip{display:inline-block;background:var(--warn-bg);color:var(--warn);border-radius:9px;padding:0 8px;margin:0 4px 4px 0;font-size:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:16px 0}
.card.failed{border-left:4px solid var(--bad)}.card.passed{border-left:4px solid var(--ok)}
.card header{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:baseline}
.nums{color:var(--mute);font-size:13px}
.checks{list-style:none;padding:0;margin:0}.checks li{margin:4px 0}
.y{color:var(--ok)}.n{color:var(--bad);font-weight:600}
.history{display:flex;gap:3px;align-items:center;flex-wrap:wrap}
.history span{display:inline-block;min-width:26px;height:20px;border-radius:4px;font-size:11px;text-align:center;line-height:20px;padding:0 3px}
.history .ok{background:var(--ok-bg);color:var(--ok)}.history .bad{background:var(--bad-bg);color:var(--bad)}.history .warn{background:var(--warn-bg);color:var(--warn)}
.history .now{outline:2px solid var(--fg)}
.tl{list-style:none;padding:0;margin:0;font-size:13px}
.tl li{padding:4px 6px;border-bottom:1px solid var(--line);display:grid;grid-template-columns:2.2em 1fr;gap:6px}
.tl .t{color:var(--mute);text-align:right}.tl .tool{font-weight:600}.tl .what{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;word-break:break-all}
.tl .say{color:var(--mute);font-size:12.5px}
.tl li.err{background:var(--bad-bg)}.tl li.err .tool{color:var(--bad)}
.tl li.hook{background:var(--hook-bg);color:var(--hook)}.tl li.final{background:var(--code)}
.tl pre{margin:4px 0 0}
.msg{white-space:pre-wrap}.more{margin-top:10px}.more>summary{font-weight:600}
details>summary{cursor:pointer;color:var(--mute)}details[open]>summary{margin-bottom:4px}
.diff .add{color:var(--ok)}.diff .del{color:var(--bad)}
@media (max-width:600px){body{padding:12px;font-size:14px}.card{padding:12px}.tl li{grid-template-columns:1.8em 1fr}}
"""


def e(text) -> str:
    return html.escape(str(text if text is not None else ""))


def fmt(v, spec="{:.0f}"):
    return "—" if v is None else spec.format(v)


def history(records: list[dict] | None, now: dict | None) -> str:
    """The cell's recorded main runs (oldest first) and this run, as small boxes."""
    boxes = []
    for r in records or []:
        cls = "ok" if r["k"] == r["n"] else "bad" if r["k"] == 0 else "warn"
        turns = statistics.median(r["turns"]) if r.get("turns") else None
        boxes.append(f'<span class="{cls}" title="main: {r["k"]}/{r["n"]} passed, median {fmt(turns)} turns">'
                     f'{r["k"]}/{r["n"]}</span>')
    if now:
        cls = "ok" if now["k"] == now["n"] else "bad" if now["k"] == 0 else "warn"
        boxes.append(f'<span class="{cls} now" title="this run">{now["k"]}/{now["n"]}</span>')
    if not records:
        boxes.insert(0, '<em class="mute" style="margin-right:6px">no runs on main yet</em>')
    return f'<div class="history">{"".join(boxes)}</div>'


def timeline_html(rows: list[dict]) -> str:
    items = []
    for r in rows:
        if r["kind"] == "hook":
            items.append(f'<li class="hook"><span class="t">⚓</span><div>{e(r["text"])}</div></li>')
        elif r["kind"] == "final":
            items.append(f'<li class="final"><span class="t">■</span><div><b>Final message</b><div class="msg">{e(r["text"])}</div></div></li>')
        else:
            code = f' <span class="mute">exit {r["exit"]}</span>' if r["exit"] not in (None, 0) else ""
            say = f'<div class="say">{e(r["note"][:200])}</div>' if r["note"] else ""
            out = f"<pre>{e(r['output'])}</pre>" if r["output"] else ""
            items.append(f'<li class="{"err" if r["error"] else ""}"><span class="t">{r["turn"]}</span><div>'
                         f'<span class="tool">{e(r["tool"])}</span> <span class="what">{e(r["what"][:300])}</span>'
                         f'{code}{say}{out}</div></li>')
    return f'<ol class="tl">{"".join(items)}</ol>' if items else '<p class="mute">No trajectory.</p>'


def diff_html(diff: str) -> str:
    out = []
    for line in diff.splitlines():
        cls = "add" if line.startswith("+") and not line.startswith("+++") else (
            "del" if line.startswith("-") and not line.startswith("---") else "")
        out.append(f'<span class="{cls}">{e(line)}</span>')
    return '<pre class="diff">' + "\n".join(out) + "</pre>"


def card(t: dict, m: dict) -> str:
    tdir = m["jobs"] / t["dir"]
    cell = m["now"].get(f"{t['leg']}/{t['task']}")
    status = "passed" if t["passed"] else "failed"
    mark = "✓" if t["passed"] else "✗"
    leg = "oracle" if t["leg"] == "oracle" else leg_label(t["leg"], m["trials"])
    parts = [f'<section class="card {status}" id="{e(t["anchor"])}"><header>'
             f'<h2>{mark} {e(t["task"])}</h2><span class="mute">{e(leg)}</span>'
             f'<span class="pill {"ok" if t["passed"] else "bad"}">{e(outcome(t))}</span>'
             + (f'<span class="nums">{fmt(t["turns"])} turns · {t["stack_calls"]} astra/lc calls · '
                f'{fmt(t["cost_usd"], "${:.3f}")} · {fmt(t["agent_s"] and t["agent_s"] / 60, "{:.1f}")} min</span>'
                if t["leg"] != "oracle" else "")
             + '</header>']
    if t["leg"] != "oracle":
        parts.append("<h3>History on main</h3>" + history((m["pool"] or {}).get(f"{t['leg']}/{t['task']}"), cell))
    j = t.get("judge")
    judge = ""
    if j:
        chips = "".join(f'<span class="chip">{e(b)}</span>' for b in t["badges"])
        crit = "".join(f"<li><b>{e(k)}</b> <i>{e(v.get('outcome'))}</i>: {e(v.get('explanation'))}</li>"
                       for k, v in (j.get("checks") or {}).items())
        judge = (f"<h3>What happened, from the judge</h3><p>{e(j.get('summary', '').strip())}</p>{chips}"
                 f"<details><summary>every criterion</summary><ul>{crit}</ul></details>")
    checks = []
    for ch in t["checks"]:
        body = f"<pre>{e(trialview.trim(ch['output'], 40))}</pre>" if ch["output"] else ""
        if ch["ok"]:
            checks.append(f'<li><details><summary><span class="y">✓</span> {e(ch["name"])}</summary>{body}</details></li>')
        else:
            checks.append(f'<li><span class="n">✗ {e(ch["name"])}</span>{body}</li>')
    if t["exception"]:
        checks.insert(0, f'<li><span class="n">✗ {e(t["exception"])}</span>'
                         f'<pre>{e(trialview.trim(trialview.exception_text(tdir), 30))}</pre></li>')
    body = []
    prompt = trialview.instruction(t["task"])
    if prompt:
        body.append(f"<details><summary>The task prompt</summary><pre>{e(prompt)}</pre></details>")
    body.append(f'<h3>Verifier</h3><ul class="checks">{"".join(checks) or "<li class=mute>no checks recorded</li>"}</ul>')
    if not t["passed"]:
        body.append(judge)
    body.append(f"<h3>Timeline</h3>{timeline_html(trialview.timeline(tdir))}")
    d = trialview.deliverable(tdir, t["task"])
    if d:
        inner = f"<pre>{e(d['body'])}</pre>"
        if d["diff"]:
            inner = (f"<p class='mute'>Diff against the reference solution (a valid answer need not match it):</p>"
                     f"{diff_html(d['diff'])}<details><summary>the file as written</summary>{inner}</details>")
        body.append(f"<h3>Deliverable: {e(d['name'])}</h3>{inner}")
    if t["passed"]:  # a pass shows its judge notes; the rest is one click away
        parts.append(judge + "<details class='more'><summary>verifier, timeline, deliverable</summary>"
                     + "".join(body) + "</details>")
    else:
        parts += body
    parts.append("</section>")
    return "".join(parts)


def page(m: dict) -> str:
    args, trials = m["args"], m["trials"]
    notes = [("bad", f"blocking · {r}") for r in m["upstream"]]
    notes += [("bad", f"{g['state']} · {g['leg']}: {g['reason']}") for g in m["unmeasured"]]
    notes += [("bad", f"blocking · {g['leg']}: {g['x']}/{g['n']} passed against {g['base_k']}/{g['base_n']} on main")
              for g in m["blocking_legs"]]
    notes += [("warn", f"warning · {ef['leg']}: {100 * (ef['ratio'] - 1):+.0f}% {ef['metric']} vs main")
              for ef in m["effort"] if ef["flag"]]
    notes += [("warn", f"warning · {c['leg']} · {c['task']}: {c['k']}/{c['n']} on a cell that passes on main")
              for c in m["warnings"]]
    if args.baseline_error:
        notes.append(("warn", args.baseline_error))
    notes_html = ("<ul class='notes'>" + "".join(f"<li class='{c}'>{e(t)}</li>" for c, t in notes) + "</ul>") if notes else ""

    legs = m["agent_legs"]
    grid = ""
    if legs:
        head = "".join(f"<th>{e(leg_label(leg, trials))}</th>" for leg in legs)
        rows = []
        for task in m["tasks"]:
            cells = []
            for leg in ["oracle"] + legs:
                ts = [t for t in trials if t["leg"] == leg and t["task"] == task]
                state = next((g["state"] for g in m["status"] if g["leg"] == leg), "measured")
                if not ts:
                    cells.append(f"<td class='mute'>{'not run' if state == 'not run' else '—'}</td>")
                    continue
                pills = "".join(f'<a class="pill {"ok" if t["passed"] else "bad"}" href="#{e(t["anchor"])}">'
                                f'{"✓" if t["passed"] else "✗"} {fmt(t["turns"]) if t["leg"] != "oracle" else ""}</a> '
                                for t in ts)
                cells.append(f"<td>{pills}</td>")
            rows.append(f"<tr><td>{e(task)}</td>{''.join(cells)}</tr>")
        grid = (f"<div class='wrap'><table class='grid'><tr><th>task</th><th>oracle</th>{head}</tr>"
                f"{''.join(rows)}</table></div><p class='mute'>Agent pills show turns; click one for its card.</p>")

    order = sorted(trials, key=lambda t: (t["passed"], t["leg"] == "oracle", t["leg"], t["task"]))
    cards = "".join(card(t, m) for t in order if not (t["leg"] == "oracle" and t["passed"]))
    runs = max((b["runs"] for b in m["bases"].values() if b), default=0)
    meta = [m["stack_line"], f"baseline {args.base_label or 'main'} ({runs} run{'s' * (runs != 1)})" if m["pool"] is not None else "no baseline yet",
            f"cost {money(m['agent_cost'] + m['judge_cost'])} (agent {money(m['agent_cost'])}, judge {money(m['judge_cost'])})"]
    run = f' · <a href="{e(args.run_url)}">workflow run</a>' if args.run_url else ""
    title = leg_label(legs[0], trials) if len(legs) == 1 else f"{len(legs)} legs"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Plugin smoke report</title>
<style>{CSS}</style></head><body>
<h1>Plugin smoke · {e(title)}</h1><p style="font-size:18px;margin:2px 0">{e(m['headline'])}</p>
<p class="meta">{' · '.join(e(x) for x in meta if x)}{run}</p>
{notes_html}{grid}{cards}
<p class="mute">Badges are pain points the judge (evals/rubrics/pain-points.toml) found in the trajectory.
Hook rows (⚓) come from the Claude Code session log. Oracle trials that passed are not shown.</p>
</body></html>"""
