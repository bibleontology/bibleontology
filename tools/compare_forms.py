"""Two stories side by side, whole, down to the claims -- to see their forms.

2026-09-02: the forms of the two are needed as trees, to diagnose this.

The flood and Sodom share five nodes and four are useless, so an
entity-overlap matcher finds nothing. The parallel a reader sees is a repeated
SHAPE -- wickedness assessed, one righteous man, a warning, the family brought
out, destruction from heaven, drunkenness and shame after -- and every step of
it is carried by different entities in the two stories. Noah is not Lot, water
is not fire.

So this page draws both trees to full depth with the claims at every leaf, and
marks the **relation types** that occur in both. If the parallel is anywhere
in the graph it is in the verbs, not the nouns, and a page showing node names
alone would hide exactly the thing being looked for.

**It is a diagnostic and not a finding.** What it mostly shows is what is
missing: the graph records what each verse claims and nothing records the
relation between claims, so the shape has no edges to live in.
"""
import collections
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bibleont.group import units_at, climb                     # noqa: E402


def claims(book):
    pat = re.compile(re.escape(book) + r" (\d+):(\d+)$")
    per = collections.defaultdict(list)
    freq = collections.Counter()
    for p in (ROOT / "ontology" / "relations").glob("*.jsonl"):
        for line in p.open(encoding="utf-8"):
            r = json.loads(line)
            for ref in (r.get("refs") or []):
                if (m := pat.match(str(ref))):
                    per[(int(m.group(1)), int(m.group(2)))].append(r)
                    break
            for n in (r.get("src"), r.get("dst")):
                if n:
                    freq[n] += 1
    return per, freq


def leaf_kids(book):
    kids = {}
    d = ROOT / "ontology" / "proposals" / f"{book.lower()}-groups"
    for f in sorted(x for x in d.glob("*.json") if x.stem.isdigit()):
        ch = int(f.stem)
        for p in json.loads(f.read_text(encoding="utf-8")).get("passages") or []:
            par = (p.get("part_of") or "").strip()
            if par:
                vs = p.get("verses") or [0, 0]
                kids.setdefault(par, []).append(
                    {"id": str(p.get("id")), "ch": ch, "lo": vs[0], "hi": vs[-1],
                     "name": p.get("name") or ""})
    for v in kids.values():
        v.sort(key=lambda x: x["lo"])
    return kids


def build(book, specs, out_name):
    top = len(climb(book))
    levels = {lv: {u["id"]: u for u in units_at(book, lv)} for lv in range(1, top + 1)}
    per, freq = claims(book)
    kids = leaf_kids(book)

    # Which relation types occur in each story, so the shared verbs can be
    # marked. The nouns differ by construction; the verbs are where a shape
    # would show if the graph held one.
    verbs = []
    for _, chs in specs:
        v = collections.Counter()
        for (c, _), rs in per.items():
            if c in chs:
                for r in rs:
                    v[r["type"]] += 1
        verbs.append(v)
    shared_verbs = set(verbs[0]) & set(verbs[1])

    def rels_for(ch, lo, hi):
        out, seen = [], set()
        for v in range(lo, hi + 1):
            for r in per.get((ch, v), []):
                k = (r["src"], r["type"], r["dst"])
                if k in seen:
                    continue
                seen.add(k)
                out.append(r)
        return out

    def render(uid, lv):
        u = levels.get(lv, {}).get(uid)
        if u is None:
            return ""
        sp = f"{u['ch']}:{u['lo']}-{u.get('hi_ch', u['ch'])}:{u['hi']}"
        members = u.get("members") or []
        if members:
            sub = "".join(render(m, lv - 1) for m in members)
        else:
            sub = ""
            ks = kids.get(uid) or [{"ch": u["ch"], "lo": u["lo"], "hi": u["hi"],
                                    "name": "", "id": uid}]
            for k in ks:
                rs = rels_for(k["ch"], k["lo"], k["hi"])
                rows = "".join(
                    f"<div class='rel{' sh' if r['type'] in shared_verbs else ''}'>"
                    f"<span class='s'>{html.escape(r['src'][:22])}</span>"
                    f"<span class='ty'>{html.escape(r['type'])}</span>"
                    f"<span class='s'>{html.escape(r['dst'][:22])}</span></div>"
                    for r in rs[:9])
                more = (f"<div class='more'>+{len(rs)-9} more</div>"
                        if len(rs) > 9 else "")
                empty = "<div class='more none'>no claims</div>" if not rs else ""
                nm = k["name"] or u["name"]
                sub += (f"<li class='leaf'><span class='sp'>{k['ch']}:{k['lo']}"
                        f"-{k['hi']}</span><span class='nm'>{html.escape(nm[:52])}</span>"
                        f"<div class='rels'>{rows}{more}{empty}</div></li>")
        head = (f"<span class='sp'>{sp}</span>"
                f"<span class='nm'>{html.escape(u['name'][:52])}</span>"
                f"<span class='lv'>L{lv}</span>")
        return f"<li><details open><summary>{head}</summary><ul>{sub}</ul></details></li>"

    cols = []
    for (label, chs), vc in zip(specs, verbs):
        root = None
        for lv in range(top, 0, -1):
            for u in levels[lv].values():
                if u["ch"] <= chs[0] and u.get("hi_ch", u["ch"]) >= chs[-1]:
                    root = (lv, u["id"]); break
            if root:
                break
        tree = f"<ul class='tree'>{render(root[1], root[0])}</ul>" if root else "<p>not found</p>"
        top_verbs = "".join(
            f"<span class='vb{' sh' if v in shared_verbs else ''}'>{html.escape(v)}"
            f"<i>{n}</i></span>" for v, n in vc.most_common(12))
        cols.append(f"<section><h2>{html.escape(label)}</h2>"
                    f"<div class='verbs'>{top_verbs}</div>{tree}</section>")

    page = """<!doctype html><html><head><meta charset="utf-8">
<title>Two forms compared</title><style>
 body{font:14px/1.45 system-ui,sans-serif;margin:0 auto;padding:1.6rem;
      max-width:1600px;background:#faf9f7;color:#191919}
 h1{font-size:1.4rem;margin:0 0 .2rem} h2{font-size:1rem;margin:0 0 .5rem}
 .note{color:#5a5a5a;font-size:.9rem;margin:.3rem 0 1.2rem}
 .cols{display:flex;gap:1.4rem;align-items:flex-start}
 section{flex:1;min-width:0;background:#fff;border:1px solid #e3e0da;
   border-radius:8px;padding:.9rem}
 ul.tree,ul.tree ul{list-style:none;padding-left:0;margin:0}
 ul.tree ul{padding-left:14px;border-left:2px solid #ece6da;margin:2px 0 5px 6px}
 summary{cursor:pointer;padding:.2rem .3rem;display:flex;gap:.45rem;
   align-items:baseline;border-radius:4px}
 summary:hover{background:#f4f1e8}
 li.leaf{padding:.25rem .3rem}
 .sp{font-variant-numeric:tabular-nums;font-weight:600;color:#6d6144;
   font-size:.78rem;background:#f4f1e8;border-radius:3px;padding:0 5px;
   white-space:nowrap}
 .nm{font-size:.87rem} .lv{font-size:.64rem;color:#a09781;margin-left:auto}
 .rels{margin:.25rem 0 .2rem .3rem}
 .rel{font-size:.72rem;color:#6a6a6a;display:flex;gap:.3rem;align-items:baseline;
   padding:1px 0}
 .rel .ty{color:#8a7a52;font-weight:600}
 .rel.sh .ty{background:#e6efdc;color:#33452a;border-radius:3px;padding:0 4px}
 .rel .s{color:#7d7568}
 .more{font-size:.7rem;color:#a8a196;font-style:italic}
 .more.none{color:#b8735c}
 .verbs{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:.6rem}
 .vb{font-size:.7rem;background:#f2efe8;border:1px solid #e3ded1;border-radius:9px;
   padding:1px 7px;color:#6a6357}
 .vb.sh{background:#e6efdc;border-color:#7d9b63;color:#33452a;font-weight:600}
 .vb i{font-style:normal;opacity:.55;margin-left:3px}
 @media(prefers-color-scheme:dark){
  body{background:#15140f;color:#ededed} .note{color:#a8a8a8}
  section{background:#201e17;border-color:#3a362b}
  .sp{background:#2a2820;color:#cdbf95} summary:hover{background:#262219}
  ul.tree ul{border-color:#2a2720} .rel{color:#9a9284} .rel .s{color:#8a8272}
  .vb{background:#241f14;border-color:#3a352a;color:#a09781}
  .vb.sh,.rel.sh .ty{background:#26331d;color:#c6dcb2}}
</style></head><body>
<h1>Two forms compared</h1>
<p class="note">Both trees to full depth, with the claims at every leaf.
<b>Green</b> marks a relation type that occurs in both stories &mdash; the nouns
differ by construction (Noah is not Lot, water is not fire), so if a shared
shape is anywhere in this graph it is in the verbs.</p>
<div class="cols">""" + "".join(cols) + """</div>
</body></html>"""
    out = ROOT / "out" / out_name
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    print("wrote", build("Gen",
                         [("The flood — Genesis 6:5–9:29", (6, 7, 8, 9)),
                          ("Sodom and Gomorrah — Genesis 18–19", (18, 19))],
                         "forms-flood-sodom.html"))
