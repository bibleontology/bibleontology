"""docs/PLAN.md as a page, for reading on demand at /plan.

2026-09-25: an expanded version of the plan, readable on demand. The file is the plan; this only draws it. A
small renderer rather than a Markdown library, because the plan uses only
headings, lists, quotes, bold, italics and code — and a status word at the
head of an item, drawn as a pill so the state of the plan reads at a glance.
"""
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "PLAN.md"
# Proposed changes waiting on the site's owner — drawn below the plan, and marked as not
# in it, so the page shows both what is agreed and what is only proposed.
PROPOSALS = ROOT / "docs" / "PLAN-PROPOSALS.md"

STATUS = ("built", "in progress", "open", "fault", "parked", "proposed")


def _inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<i>\1</i>", s)
    return s


def _pill(s):
    # "1.4 **fault** — ..." → the number, then the status as a pill
    m = re.match(r"^([A-Z]?\d*\.?\d+) \*\*(" + "|".join(STATUS)
                 + r")\*\* — (.*)$", s, re.S)
    if not m:
        return _inline(s)
    num, st, rest = m.groups()
    return (f'<span class="num">{num}</span>'
            f'<span class="pill {st.replace(" ", "-")}">{st}</span> '
            + _inline(rest))


def render(text):
    out, para, items, quote = [], [], [], []

    def flush():
        if para:
            out.append("<p>" + _inline(" ".join(para)) + "</p>")
            para.clear()
        if quote:
            out.append("<blockquote>" + _inline(" ".join(quote))
                       + "</blockquote>")
            quote.clear()
        if items:
            h = ["<ul>"]
            for depth, t in items:
                cls = ' class="sub"' if depth else ""
                h.append(f"<li{cls}>{_pill(t)}</li>")
            h.append("</ul>")
            out.append("".join(h))
            items.clear()

    for line in text.splitlines():
        s = line.rstrip()
        if not s.strip():
            flush()
            continue
        m = re.match(r"^(#{1,3}) (.*)$", s)
        if m:
            flush()
            n = len(m.group(1))
            out.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
            continue
        if s.strip() == "---":
            flush()
            out.append("<hr>")
            continue
        if s.startswith("> "):
            quote.append(s[2:])
            continue
        m = re.match(r"^(\s*)- (.*)$", s)
        if m:
            if para:
                flush()
            items.append([1 if m.group(1) else 0, m.group(2)])
            continue
        if items and s.startswith(" "):
            items[-1][1] += " " + s.strip()
            continue
        para.append(s.strip())
    flush()
    return "\n".join(out)


def page():
    body = render(PLAN.read_text(encoding="utf-8"))
    if PROPOSALS.exists():
        text = PROPOSALS.read_text(encoding="utf-8")
        n = sum(1 for ln in text.splitlines() if ln.startswith("### P-"))
        body += (f'<hr><section class="queue">'
                 f'<div class="qhead">Waiting on Doug · {n} proposed '
                 f'change{"" if n == 1 else "s"} · not in the plan</div>'
                 + render(text) + "</section>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>The plan</title>
<style>
:root {{ --bg:#fbfaf7; --fg:#1f1d1a; --mute:#6b665e; --rule:#e4e0d8;
  --code:#f0ede6; --built:#2f7d4f; --progress:#2a5fa8; --open:#6b665e;
  --fault:#b23a2a; --parked:#8a6d1f; --proposed:#7a4fa0; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#171614; --fg:#e8e4dc; --mute:#a39d92; --rule:#34312c; --code:#24221f;
  --built:#5dbb83; --progress:#73a3e8; --open:#a39d92; --fault:#e5735f;
  --parked:#d4b04f; --proposed:#b48be0; }} }}
body {{ background:var(--bg); color:var(--fg); margin:0;
  font:16px/1.55 Georgia, "Iowan Old Style", serif; }}
main {{ max-width:760px; margin:0 auto; padding:24px 16px 80px; }}
h1 {{ font-size:30px; margin:8px 0 12px; }}
h2 {{ font-size:22px; margin:34px 0 8px; }}
h3 {{ font-size:17px; margin:22px 0 6px; color:var(--mute); }}
blockquote {{ margin:12px 0; padding:4px 14px; border-left:3px solid var(--rule);
  color:var(--mute); font-style:italic; }}
code {{ background:var(--code); padding:1px 4px; border-radius:3px;
  font:13px ui-monospace, Consolas, monospace; }}
hr {{ border:0; border-top:1px solid var(--rule); margin:30px 0; }}
ul {{ padding-left:0; list-style:none; }}
li {{ margin:9px 0; }}
li.sub {{ margin-left:26px; list-style:disc; }}
.num {{ font:600 13px ui-monospace, Consolas, monospace; color:var(--mute);
  margin-right:8px; }}
.pill {{ font:600 11px system-ui, sans-serif; text-transform:uppercase;
  letter-spacing:.04em; padding:2px 7px; border-radius:10px;
  border:1px solid currentColor; white-space:nowrap; }}
.built {{ color:var(--built); }} .in-progress {{ color:var(--progress); }}
.open {{ color:var(--open); }} .fault {{ color:var(--fault); }}
.parked {{ color:var(--parked); }} .proposed {{ color:var(--proposed); }}
.queue {{ border:1px dashed var(--parked); border-radius:8px; padding:4px 18px 10px; }}
.queue h1 {{ font-size:20px; }}
.qhead {{ font:600 12px system-ui, sans-serif; text-transform:uppercase;
  letter-spacing:.05em; color:var(--parked); margin-top:12px; }}
</style></head><body><main>{body}</main></body></html>"""
