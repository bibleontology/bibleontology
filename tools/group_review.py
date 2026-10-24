"""A book's proposed grouping, laid out to be judged before it is merged.

2026-09-01: groupings are to be visualised before merging in, starting with
Mark.

**This is a review document, not a diagram.** The Titus and Sermon charts draw
the shape, which is the right thing when the shape is the question. Here the
question is whether each seam is real, and a seam is judged by the words that
mark it -- so every passage shows its `because` quote, and the page is a tree
of evidence rather than a picture of boxes.

Three things it deliberately does:

  shows the evidence     `because` under every passage. A seam whose evidence
                         is a restatement of the label is exactly what this
                         page exists to catch, and it is invisible in a chart.

  quotes the verse       the first words of the opening verse, beside the
                         claim. The gate that checks quotations does not run
                         on seams, so a reader is the only check there is.

  flags its own faults   coverage and nesting arithmetic, per level, in place
                         rather than in a log somewhere else.

Collapsed by default with an expand-all, because sixteen chapters of this is
not something anyone reads top to bottom, and the reader-mode spec asks for
the same control on the same shape.
"""
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bibleont.group import check, Grouping                      # noqa: E402
from bibleont.decompose import chapter                          # noqa: E402


def verse_text(book, ch, v):
    for ref, t in chapter(book, ch):
        if ref.rsplit(":", 1)[1] == str(v):
            return t
    return ""


def build(book: str) -> pathlib.Path:
    src = ROOT / "ontology" / "proposals" / f"{book.lower()}-groups"
    files = sorted(x for x in src.glob("*.json") if x.stem.isdigit())
    if not files:
        raise SystemExit(f"no grouping at {src}")

    blocks, tot_p, tot_pat, faulty = [], 0, 0, 0
    for f in files:
        ch = int(f.stem)
        d = json.loads(f.read_text(encoding="utf-8"))
        ps = d.get("passages") or []
        pats = d.get("patterns") or []
        tot_p += len(ps)
        tot_pat += len(pats)
        g = Grouping(ref=f"{book} {ch}", ok=True, passages=ps,
                     patterns=pats, note=d.get("note") or "")
        faults = check(book, ch, g)
        faulty += bool(faults)

        by_id = {str(p.get("id")): p for p in ps}
        kids = {}
        roots = []
        for p in ps:
            par = (p.get("part_of") or "").strip()
            (kids.setdefault(par, []) if par in by_id else roots).append(p)

        def render(p, depth=0):
            vs = p.get("verses") or ["?", "?"]
            span = f"{vs[0]}" if vs[0] == vs[-1] else f"{vs[0]}-{vs[-1]}"
            because = (p.get("because") or "").strip()
            opener = verse_text(book, ch, vs[0])[:96]
            addr = ('<span class="addr">addressed to '
                    f'{html.escape(p.get("addressed_to"))}</span>'
                    if p.get("addressed_to") else "")
            # A seam whose evidence does not quote anything is the one a
            # reader has to look at, so it is marked rather than left to be
            # noticed.
            noquote = "" if re.search(r"[\"'“‘]", because) else \
                ' <span class="flag">no quotation in the evidence</span>'
            body = (f'<li class="d{min(depth,2)}">'
                    f'<span class="sp">{ch}:{span}</span> '
                    f'<b>{html.escape(str(p.get("name") or ""))}</b> {addr}'
                    f'<div class="because">{html.escape(because)}{noquote}</div>'
                    f'<div class="verse">{html.escape(opener)}&hellip;</div>')
            sub = kids.get(str(p.get("id"))) or []
            if sub:
                body += "<ul>" + "".join(render(k, depth + 1)
                                         for k in sorted(sub, key=lambda x: (x.get("verses") or [0])[0])) + "</ul>"
            return body + "</li>"

        tree = "<ul class='tree'>" + "".join(
            render(p) for p in sorted(roots, key=lambda x: (x.get("verses") or [0])[0])) + "</ul>"

        pat_html = ""
        if pats:
            pat_html = "<div class='pats'><b>Patterns in this chapter</b><ul>" + "".join(
                f"<li>{html.escape(str(q.get('name') or ''))} "
                f"<span class='n'>({len(q.get('instances') or [])} instances)</span>"
                f"<div class='because'>{html.escape((q.get('because') or '')[:220])}</div></li>"
                for q in pats) + "</ul></div>"

        fault_html = ("<div class='faults'>" + "<br>".join(
            html.escape(x) for x in faults) + "</div>") if faults else ""
        note_html = (f"<div class='note2'>note: {html.escape(g.note[:400])}</div>"
                     if g.note else "")

        blocks.append(
            f"<details{' open' if faults else ''}><summary>"
            f"<span class='ch'>{book} {ch}</span>"
            f"<span class='c'>{len(ps)} passages</span>"
            f"<span class='c'>{len(pats)} patterns</span>"
            f"{'<span class=bad>faults</span>' if faults else ''}"
            f"</summary>{fault_html}{note_html}{tree}{pat_html}</details>")

    page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>{book}: proposed grouping</title><style>
 body{{font:15px/1.55 system-ui,sans-serif;margin:0 auto;padding:2rem;max-width:1080px;
      background:#faf9f7;color:#191919}}
 h1{{font-size:1.5rem;margin:0 0 .2rem}}
 .lede{{color:#5a5a5a;margin:.2rem 0 1rem;font-size:.94rem}}
 .bar{{display:flex;gap:1.6rem;margin:.8rem 0 1.2rem;font-size:.9rem;flex-wrap:wrap}}
 .bar b{{font-variant-numeric:tabular-nums;font-size:1.25rem;display:block}}
 button{{font:inherit;padding:.35rem .8rem;border:1px solid #cfc8b8;border-radius:5px;
   background:#fff;cursor:pointer}}
 details{{background:#fff;border:1px solid #e3e0da;border-radius:7px;margin:.5rem 0;
   padding:.4rem .8rem}}
 summary{{cursor:pointer;display:flex;gap:1rem;align-items:baseline;padding:.25rem 0}}
 .ch{{font-weight:600;min-width:5.5rem}}
 .c{{color:#8a8375;font-size:.85rem;font-variant-numeric:tabular-nums}}
 .bad{{color:#a4432b;font-size:.8rem;font-weight:600;text-transform:uppercase;
   letter-spacing:.04em}}
 ul.tree{{list-style:none;padding-left:0;margin:.5rem 0}}
 ul.tree ul{{list-style:none;padding-left:1.3rem;border-left:2px solid #eee8e0;
   margin:.35rem 0}}
 li{{margin:.55rem 0}}
 .sp{{font-variant-numeric:tabular-nums;color:#7a6f52;font-weight:600;
   background:#f4f1e8;padding:1px 6px;border-radius:3px;font-size:.85em}}
 .because{{color:#4a4a4a;font-size:.88rem;margin:.15rem 0 0 .2rem}}
 .verse{{color:#93897a;font-size:.83rem;font-style:italic;margin-left:.2rem}}
 .addr{{color:#5f7d4f;font-size:.78rem;border:1px solid #cfe0c4;border-radius:3px;
   padding:0 5px}}
 .flag{{color:#a4432b;font-size:.78rem}}
 .faults{{background:#fdf0ec;border-left:3px solid #a4432b;padding:.5rem .8rem;
   border-radius:0 5px 5px 0;font-size:.86rem;margin:.4rem 0}}
 .note2{{color:#6a6a6a;font-size:.87rem;margin:.4rem 0;font-style:italic}}
 .pats{{background:#f7f5ef;border-radius:6px;padding:.5rem .9rem;margin:.6rem 0 .3rem;
   font-size:.9rem}}
 .pats ul{{padding-left:1.1rem;margin:.3rem 0}}
 .n{{color:#8a8375;font-size:.85em}}
 @media(prefers-color-scheme:dark){{
  body{{background:#15140f;color:#ededed}}
  details{{background:#201e17;border-color:#3a362b}} button{{background:#241f14;
   color:#ededed;border-color:#4a4436}}
  .lede,.c,.because,.note2{{color:#a8a8a8}} .verse{{color:#8a8272}}
  .sp{{background:#2a2820;color:#cdbf95}} ul.tree ul{{border-color:#2f2c22}}
  .pats{{background:#241f14}} .faults{{background:#2b1d18}}}}
</style></head><body>
<h1>{book}: the leaf level</h1>
<p class="lede"><b>This is the bottom of the hierarchy, not the hierarchy.</b>
Passages were found one chapter at a time, so what nesting appears here is
nesting <em>inside</em> a chapter &mdash; and a chapter is only six or seven
units wide, so it is shallow by construction. Everything above this, the runs
that cross chapters and the forms repeated across the book, is built by
separate passes climbing to the scroll. Reading this page as the finished
structure is reading it as flatter than it will be.</p>
<p class="lede">Not merged. Every passage shows the evidence the model gave for
its seam, and the opening words of its first verse, because <b>a seam is
judged by the words that mark it</b> and there is no mechanical gate on seams
the way there is on quotations. <b>That judgement is the one that matters
most</b>: every level above inherits these boundaries, and a wrong seam here
is wrong all the way up.</p>
<div class="bar">
  <div><b>{len(files)}</b>chapters</div>
  <div><b>{tot_p}</b>passages</div>
  <div><b>{tot_pat}</b>patterns</div>
  <div><b>{faulty}</b>chapters with faults</div>
</div>
<p><button onclick="document.querySelectorAll('details').forEach(d=>d.open=true)">
Expand all</button>
<button onclick="document.querySelectorAll('details').forEach(d=>d.open=false)">
Collapse all</button></p>
{''.join(blocks)}
</body></html>"""
    out = ROOT / "out" / f"{book.lower()}-grouping-review.html"
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    b = sys.argv[1] if len(sys.argv) > 1 else "Mark"
    p = build(b)
    print(f"wrote {p}")
