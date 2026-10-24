"""A book's climbed structure, whole and expandable, from the scroll to the verse.

2026-09-01: the earlier views did not go very deep but were spot on at the
high level. The first version drew the top two
levels and hid the rest -- for Mark that is 3 and 12 shown against 31 and 101
hidden, which is most of the book.

So this draws **every level**, collapsed, with an expand-all. Which is also
the shape the reader view wants, and not by coincidence: the reader-mode
spec asks for a group tree with an expand-all where each node lists the verses
it covers. This is that tree with the data actually in it.

Three conventions, set by hand, and none restated in the page itself because a
chart that has to explain its own conventions has the wrong conventions:

  containment only          every line is a group holding a group. Reading
                            order is position; there is no arrow for it.

  collections sit outside   they connect groups without containing them, so
                            they are listed under the tree rather than in it.
                            An inclusio spanning half a book would otherwise
                            have to break contiguity to be drawn.

  the tree is ragged        a unit the passes refused to bind hangs off the
                            scroll at whatever level it stopped at. Depth
                            follows how strongly the text binds. **Every one
                            of them is drawn**, in reading order, beside the
                            groups that climbed -- that view was judged
                            really logical. `--fold`
                            collapses consecutive unbound runs into a strip
                            for a tighter top level, and is off by default
                            because equal treatment is the honest drawing.

**The text is the destination.** Most readers want to approach it
sooner or later from the text. So every node carries its span, the leaves
carry the words their seam was cut on, and nothing here is a node panel -- a
reader following this tree is walking toward verses.
"""
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bibleont.group import units_at, climb, _level_path          # noqa: E402


def span_of(u):
    hi_ch = u.get("hi_ch", u["ch"])
    a = f"{u['ch']}:{u['lo']}"
    return a if (hi_ch == u["ch"] and u["hi"] == u["lo"]) else f"{a}-{hi_ch}:{u['hi']}"


def chapter_pass(book):
    """Seam evidence and in-chapter nesting, from the leaf pass."""
    because, kids = {}, {}
    d = ROOT / "ontology" / "proposals" / f"{book.lower()}-groups"
    for f in sorted(x for x in d.glob("*.json") if x.stem.isdigit()):
        ch = int(f.stem)
        for p in json.loads(f.read_text(encoding="utf-8")).get("passages") or []:
            pid = str(p.get("id"))
            because[pid] = p.get("because") or ""
            par = (p.get("part_of") or "").strip()
            if par:
                vs = p.get("verses") or [0, 0]
                kids.setdefault(par, []).append(
                    {"id": pid, "ch": ch, "lo": vs[0], "hi": vs[-1],
                     "name": p.get("name") or "", "because": because[pid]})
    for v in kids.values():
        v.sort(key=lambda x: x["lo"])
    return because, kids


def build(book: str, fold: bool = False) -> pathlib.Path:
    heights = climb(book)
    top = len(heights)
    levels = {lv: {u["id"]: u for u in units_at(book, lv)}
              for lv in range(1, top + 1)}
    because, kids_leaf = chapter_pass(book)

    # Where each unit left the climb, so an unbound one can say so.
    left_at, cols = {}, []
    for lv in range(2, top + 1):
        got = json.loads(_level_path(book, lv).read_text(encoding="utf-8"))
        for s in got.get("to_scroll") or []:
            left_at[s] = lv - 1
        cols += [(lv, c) for c in (got.get("collections") or [])]

    def node(sp, name, why, level=None, count=0, leaf=False):
        tag = f"<span class='lv'>L{level}</span>" if level and level > 1 else ""
        cnt = f"<span class='cnt'>{count}</span>" if count else ""
        w = f"<div class='why'>{html.escape(why[:150])}</div>" if why else ""
        return (f"<span class='sp'>{sp}</span>"
                f"<span class='nm'>{html.escape(name)}</span>{tag}{cnt}", w)

    def render(uid, lv):
        u = levels.get(lv, {}).get(uid)
        if u is None:
            return ""
        members = u.get("members") or []
        if members:
            sub = "".join(render(m, lv - 1) for m in members)
            n = len(members)
        else:
            ks = kids_leaf.get(uid, [])
            n = len(ks)
            sub = ""
            for k in ks:
                sp = f"{k['ch']}:{k['lo']}" + ("" if k['lo'] == k['hi'] else f"-{k['hi']}")
                head, why = node(sp, k["name"], k["because"], leaf=True)
                sub += f"<li class='leaf'>{head}{why}</li>"
        head, why = node(span_of(u), u["name"], because.get(uid, ""), lv, n)
        if not sub:
            return f"<li class='leaf'>{head}{why}</li>"
        return f"<li><details><summary>{head}</summary>{why}<ul>{sub}</ul></details></li>"

    # The scroll's children: the top level plus everything that left early,
    # in text order. An unbound unit is not lesser and is not filed away.
    roots = [(u, top, False) for u in units_at(book, top)]
    for uid, lv in left_at.items():
        u = levels.get(lv, {}).get(uid)
        if u:
            roots.append((u, lv, True))
    roots.sort(key=lambda x: (x[0]["ch"], x[0]["lo"]))

    # SPATIAL AT THE TOP, DEEP ON DEMAND.
    #
    # The feedback: mentally combining the last two views of Mark is spot on
    # as well. The column chart showed the shape at a glance and
    # could not go deep; the tree went deep and lost the shape. Combining them
    # in a reader's head is work the page should have done.
    #
    # So the top level keeps the left-to-right row -- the scroll on the left,
    # one row per unit, reading down the column is reading the book -- and
    # each row's contents are the expandable tree rather than a flat list.
    # FOLD RUNS OF UNBOUND UNITS.
    #
    # The feedback: the 9 rows were liked but the grouping seen a level lower
    # was missed; there tends to be more hierarchy in mind.
    #
    # A group holding twelve passages and a single unbound scene were drawn as
    # peers, so 27 loose units diluted the 3 that climbed. Folding consecutive
    # unbound runs into one strip restores the fewness that was liked WITHOUT the
    # dishonesty of the view that produced it -- that one had 9 rows because it
    # silently dropped 21 units, where this has 9-ish rows because it says
    # "seven scenes, unbound, 1:1-3:35" and opens.
    #
    # Order is preserved and nothing is hidden, which are the two things that
    # made the tidy version wrong.
    folded, run = [], []
    for r in roots:
        if r[2] and fold:
            run.append(r)
            continue
        if run:
            folded.append(("fold", run))
            run = []
        folded.append(("unit", r))
    if run:
        folded.append(("fold", run))

    rows_html = []
    for kind, item in folded:
        if kind == "fold":
            first, last = item[0][0], item[-1][0]
            span = (f"{first['ch']}:{first['lo']}-"
                    f"{last.get('hi_ch', last['ch'])}:{last['hi']}")
            inner = "".join(
                render(u["id"], lv) for u, lv, _ in item)
            rows_html.append(
                f"<div class='row fold'><div class='unit unbound folded'>"
                f"<div class='uh'><span class='sp'>{span}</span></div>"
                f"<div class='un'>{len(item)} unbound</div>"
                f"<div class='meta'>the text binds nothing here</div></div>"
                f"<div class='kids'><ul>{inner}</ul></div></div>")
            continue
        u, lv, unbound = item
        inner = render(u["id"], lv)
        # The unit's own head is drawn in the left column, so unwrap the top
        # node of its subtree and keep only what is under it.
        body = ""
        if "<ul>" in inner:
            body = inner[inner.index("<ul>"):inner.rindex("</ul>") + 5]
        n = len(u.get("members") or []) or len(kids_leaf.get(u["id"], []))
        cls = "unit unbound" if unbound else "unit"
        why = because.get(u["id"], "")
        rows_html.append(
            f"<div class='row'><div class='{cls}'>"
            f"<div class='uh'><span class='sp'>{span_of(u)}</span>"
            f"<span class='lv'>L{lv}</span></div>"
            f"<div class='un'>{html.escape(u['name'])}</div>"
            + (f"<div class='why'>{html.escape(why[:120])}</div>" if why else "")
            + (f"<div class='meta'>{n} inside</div>" if n else
               "<div class='meta'>unbound</div>")
            + f"</div><div class='kids'>{body}</div></div>")
    tree = ("<div class='org'><div class='scroll'>" + html.escape(book)
            + "<span>the scroll</span></div><div class='rows'>"
            + "".join(rows_html) + "</div></div>")

    rows = "".join(
        f"<tr><td><b>{html.escape(str(c.get('name') or ''))}</b>"
        f"<div class='why'>{html.escape(str(c.get('because') or '')[:170])}</div></td>"
        f"<td class='n'>{len(c.get('instances') or [])}</td><td class='n'>L{lv}</td></tr>"
        for lv, c in sorted(cols, key=lambda x: -len(x[1].get("instances") or [])))

    nunbound = sum(1 for _, _, ub in roots if ub)
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>{book}, climbed</title><style>
 body{{font:15px/1.5 system-ui,sans-serif;margin:0 auto;padding:2rem;max-width:1100px;
      background:#faf9f7;color:#191919}}
 h1{{font-size:1.5rem;margin:0 0 .2rem}}
 h2{{font-size:1rem;margin:2rem 0 .4rem;border-bottom:1px solid #e3e0da;
     padding-bottom:.3rem}}
 .note{{color:#5a5a5a;margin:.2rem 0 1rem;font-size:.92rem}}
 .bar{{display:flex;gap:1.7rem;margin:.8rem 0;font-size:.85rem;flex-wrap:wrap}}
 .bar b{{font-variant-numeric:tabular-nums;font-size:1.25rem;display:block}}
 button{{font:inherit;padding:.3rem .75rem;border:1px solid #cfc8b8;border-radius:5px;
   background:#fff;cursor:pointer;margin-right:.4rem}}
 .org{{display:flex;align-items:stretch}}
 .scroll{{flex:0 0 108px;background:#2e2712;color:#f6efdc;border-radius:7px;
   display:flex;flex-direction:column;justify-content:center;align-items:center;
   font-weight:600;padding:.8rem .5rem;position:sticky;top:1rem;
   align-self:flex-start;margin-right:24px}}
 .scroll span{{font-weight:400;font-size:.76rem;opacity:.72;margin-top:.2rem}}
 .rows{{flex:1;border-left:2px solid #ddd6c6;padding-left:24px}}
 .row{{display:flex;gap:20px;align-items:flex-start;margin:0 0 16px;
   padding-bottom:14px;border-bottom:1px solid #f0ece2;position:relative}}
 .row:last-child{{border-bottom:none}}
 .row::before{{content:"";position:absolute;left:-24px;top:20px;width:24px;
   height:2px;background:#ddd6c6}}
 .unit{{flex:0 0 300px;background:#eae3d2;border:1px solid #8a7a52;
   border-radius:6px;padding:.55rem .7rem;position:sticky;top:1rem}}
 .unit.unbound{{background:#f6efdc;border-style:dashed;border-color:#b39a5b}}
 .unit.folded{{background:#f7f4ec;border-color:#cfc4a4}}
 .unit.folded .un{{color:#8b8067;font-weight:600}}
 .row.fold{{opacity:.92}}
 .uh{{display:flex;align-items:baseline;gap:.5rem;margin-bottom:.15rem}}
 .un{{font-weight:600;font-size:.95rem;line-height:1.3}}
 .meta{{font-size:.74rem;color:#8b8067;margin-top:.3rem;
   font-variant-numeric:tabular-nums}}
 .kids{{flex:1;min-width:0}}
 ul.tree,ul.tree ul,.kids ul{{list-style:none;padding-left:0;margin:0}}
 ul.tree ul,.kids ul ul{{padding-left:18px;border-left:2px solid #ece6da;
   margin:2px 0 6px 8px}}
 li{{margin:3px 0}}
 summary{{cursor:pointer;padding:.3rem .5rem;border-radius:5px;
   display:flex;align-items:baseline;gap:.55rem}}
 summary:hover{{background:#f2efe8}}
 li.leaf{{padding:.3rem .5rem}}
 .sp{{font-variant-numeric:tabular-nums;font-weight:600;color:#6d6144;
   font-size:.83rem;white-space:nowrap;background:#f4f1e8;border-radius:3px;
   padding:1px 6px;margin-right:.45rem}}
 .nm{{font-size:.92rem}}
 .lv{{font-size:.67rem;color:#a09781;border:1px solid #e0d9c8;border-radius:3px;
   padding:0 4px;white-space:nowrap}}
 .cnt{{margin-left:auto;font-size:.72rem;color:#9a9284;background:#f4f1e8;
   border-radius:9px;padding:0 7px;font-variant-numeric:tabular-nums}}
 .why{{color:#8d8474;font-size:.8rem;margin:.05rem 0 .15rem 4.6rem;font-style:italic}}
 li.unbound>details>summary,li.leaf.unbound{{border-left:3px dashed #b39a5b;
   background:#fbf7ec;border-radius:0 5px 5px 0}}
 table{{border-collapse:collapse;width:100%;font-size:.9rem}}
 th{{text-align:left;color:#8a8375;font-weight:600;font-size:.75rem;
    text-transform:uppercase;letter-spacing:.04em;padding:.3rem .5rem}}
 td{{padding:.45rem .5rem;border-top:1px solid #eee8e0;vertical-align:top}}
 .n{{font-variant-numeric:tabular-nums;color:#5a5a5a;text-align:right;
    white-space:nowrap}}
 @media(prefers-color-scheme:dark){{
  body{{background:#15140f;color:#ededed}} .note,.n,td{{color:#a8a8a8}}
  button{{background:#241f14;color:#ededed;border-color:#4a4436}}
  summary:hover{{background:#231f16}} .sp{{background:#2a2820;color:#cdbf95}}
  ul.tree ul{{border-color:#2a2720}} .why{{color:#857c6c}}
  .cnt{{background:#2a2820;color:#8a8272}} td{{border-color:#2a2820}}
  h2{{border-color:#3a362b}}
  li.unbound>details>summary,li.leaf.unbound{{background:#221e14}}
  .unit{{background:#2b2617;border-color:#6b5f3f;color:#efe8d6}}
  .unit.unbound{{background:#221e13;border-color:#5a5138}}
  .meta{{color:#8a8272}} .rows{{border-color:#3a3529}}
  .row{{border-bottom-color:#26231b}} .row::before{{background:#3a3529}}}}
</style></head><body>
<h1>{book}, climbed</h1>
<p class="note">Built bottom-up in passes: {' &rarr; '.join(str(h) for h in heights)}.
Every level is here &mdash; open a node to descend, down to the passages the
chapter pass found and the words their seams were cut on. <b>Dashed</b> means
the passes refused to bind it, so it hangs off the scroll.</p>
<div class="bar">
  <div><b>{len(heights)}</b>levels</div>
  <div><b>{heights[0]}</b>passages</div>
  <div><b>{len(roots)}</b>under the scroll</div>
  <div><b>{nunbound}</b>unbound</div>
  <div><b>{len(cols)}</b>collections</div>
</div>
<p><button onclick="document.querySelectorAll('details').forEach(d=>d.open=true)">Expand all</button>
<button onclick="document.querySelectorAll('details').forEach(d=>d.open=false)">Collapse all</button></p>
{tree}

<h2>Collections, connected after the fact</h2>
<p class="note">Not groups. A collection contains nothing and partitions
nothing &mdash; it is a relation <em>between</em> units that share a form, so it
is applied to the tree rather than drawn inside it.</p>
<table><tr><th>form</th><th>n</th><th>found at</th></tr>{rows}</table>
</body></html>"""
    out = ROOT / "out" / f"{book.lower()}-climbed.html"
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    b = args[0] if args else "Mark"
    print(f"wrote {build(b, fold='--fold' in sys.argv)}")
