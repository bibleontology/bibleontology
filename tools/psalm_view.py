"""A psalm, whole, with its structure laid over the text.

2026-09-02: the psalms are highly repetitive, and the aim is to see what
groups emerge for pattern matching purposes.

The tree views suit a book of fifty chapters. A psalm is twenty verses, and
for twenty verses the honest view is **the text with the structure drawn on
it** rather than a tree of labels standing in for text nobody can see. That is
also the direction the reader view has to go: *"most Christians want to
approach it sooner or later from the text."*

So this page is the psalm, verse by verse, with three things marked on it:

  groups        drawn as bands down the left, one column per level, so
                nesting reads as depth rather than as indentation

  repetition    every phrase of two or more words occurring in three or more
                verses, highlighted in place. **Found with no model and no
                word list** -- which on Psalm 103 caught both collections the
                model missed: `who` at 3-5 and `bless` at 20-22.

  the key       where a reader wrote down what the structure should be before
                the run, those seams are drawn beside the machine's, so agreement
                and disagreement are visible without reading two documents.

The last is the point of the page. A psalm's structure is contested in a way a
narrative's is not, and a view that shows only the machine's answer invites
belief in it.
"""
import collections
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# A reader's readings, recorded before the runs. Empty where none was given.
KEYS = {
    103: {"seams": [1, 7, 13, 19],
          "note": "4 main parts; 7 then 8-12, 13 then 14-18, 19 then 20-22; "
                  "collections at both ends",
          "subs": [(7, 8), (13, 14), (19, 20)]},
    88: {"seams": [], "note": "", "subs": []},
}


def nodes_at(ch):
    """Which extracted nodes sit at each verse, and how common each is here.

    2026-09-02: the visualization was to make clear where the nodes are.
    Principle 9 says group on nodes and treat the
    verse as an index -- but a page showing only text and bands lets a reader
    judge the grouping against words while the algorithm judged it against
    something they cannot see.

    **Commonness is what the page has to show, not presence.** Psalm 103's
    every adjacent pair shares one to three nodes and they are the same ones
    each time: `david`, `god`, and the per-verse speech node. Verses 7 and 8 --
    the statement and its unfolding, in the held reading -- share no content node
    at all, because the link between them is that what was made known IS the
    mercy, and no edge in the graph says that. So a node shown without its
    frequency invites the reader to see connection where there is only
    ubiquity.
    """
    import collections as _c
    import re as _re
    at = _c.defaultdict(set)
    ds = sorted((ROOT / "ontology" / "proposals").glob("*-farm-*"),
                key=lambda x: x.stat().st_mtime, reverse=True)
    for d in ds:
        rel = d / "relations.jsonl"
        if not rel.exists():
            continue
        rows = [json.loads(l) for l in rel.open(encoding="utf-8")]
        if not any(f"Ps {ch}:" in str(r.get("refs")) for r in rows):
            continue
        for r in rows:
            for ref in (r.get("refs") or []):
                m = _re.match(rf"Ps {ch}:(\d+)$", str(ref))
                if m:
                    at[int(m.group(1))] |= {r["src"], r["dst"]}
                    break
        break
    freq = _c.Counter()
    for s in at.values():
        for n in s:
            freq[n] += 1
    return at, freq


def verses(ch):
    out = {}
    with (ROOT / "data" / "bible" / "verses.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            if d.get("b") == "Ps" and d.get("c") == ch:
                out[d["v"]] = d["t"]
    return out


def repeats(V, min_verses=3, min_words=2):
    """Phrases occurring in `min_verses` or more verses. No word list."""
    at = collections.defaultdict(set)
    for v, t in V.items():
        w = re.findall(r"[a-z]+", t.lower())
        for n in range(min_words, 7):
            for i in range(len(w) - n + 1):
                at[" ".join(w[i:i + n])].add(v)
    keep = {}
    for p, vs in sorted(at.items(), key=lambda x: (-len(x[0]), -len(x[1]))):
        if len(vs) < min_verses:
            continue
        if any(p in q and vs <= keep[q] for q in keep):
            continue
        keep[p] = vs
    return keep


def mark(text, phrases):
    """Highlight the repeated phrases inside one verse."""
    spans = []
    low = text.lower()
    for p in phrases:
        for m in re.finditer(re.escape(p.replace(" ", r" ")), re.sub(r"[^a-z ]", " ", low)):
            spans.append((m.start(), m.end()))
    if not spans:
        return html.escape(text)
    spans.sort()
    merged = [spans[0]]
    for a, b in spans[1:]:
        if a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    out, last = [], 0
    for a, b in merged:
        out.append(html.escape(text[last:a]))
        out.append(f"<mark>{html.escape(text[a:b])}</mark>")
        last = b
    out.append(html.escape(text[last:]))
    return "".join(out)


def build(ch: int) -> pathlib.Path:
    V = verses(ch)
    NODES, FREQ = nodes_at(ch)
    src = ROOT / "out" / f"ps{ch}-grouping.json"
    got = json.loads(src.read_text(encoding="utf-8")) if src.exists() else {}
    ps = got.get("passages") or []
    by = {str(p.get("id")): p for p in ps}

    def depth(p, seen=()):
        par = (p.get("part_of") or "").strip()
        return 1 if (not par or par not in by or par in seen) else 1 + depth(by[par], seen + (par,))

    bands = []
    for p in sorted(ps, key=lambda x: ((x.get("verses") or [0])[0], depth(x))):
        vs = p.get("verses") or []
        if len(vs) == 2:
            bands.append({"lo": vs[0], "hi": vs[1], "d": depth(p),
                          "name": p.get("name") or "", "why": p.get("because") or ""})
    maxd = max((b["d"] for b in bands), default=1)

    key = KEYS.get(ch, {"seams": [], "subs": [], "note": ""})
    phr = repeats(V)
    words = sorted(phr, key=len, reverse=True)

    rows = []
    for v in sorted(V):
        opens = [b for b in bands if b["lo"] == v]
        cells = ""
        for d in range(1, maxd + 1):
            here = [b for b in bands if b["d"] == d and b["lo"] <= v <= b["hi"]]
            if not here:
                cells += "<td class='b empty'></td>"
                continue
            b = here[0]
            cls = "b start" if b["lo"] == v else "b"
            label = (f"<span class='gl'>{html.escape(b['name'][:46])}</span>"
                     if b["lo"] == v else "")
            cells += f"<td class='{cls}' data-d='{d}'>{label}</td>"
        dk = " dk" if v in key["seams"] else ""
        ds = " sub" if any(v == s[1] for s in key["subs"]) else ""

        # Nodes, with the ubiquitous ones dimmed. A node in most verses of the
        # psalm tells a reader nothing about which verses belong together --
        # that is the rule to weight shared evidence by how rare it is --
        # and showing it at full strength is the page arguing for a connection
        # the node does not support.
        here = NODES.get(v, set())
        prev = NODES.get(v - 1, set())
        chips = []
        for n in sorted(here, key=lambda x: (FREQ[x], x)):
            common = FREQ[n] >= max(3, len(V) // 3)
            per_verse = bool(re.match(rf"ps_{ch}_\d+", n))
            shared = n in prev and not common and not per_verse
            cls = ("chip dim" if (common or per_verse) else
                   "chip bond" if shared else "chip")
            chips.append(f"<span class='{cls}' title='in {FREQ[n]} verses'>"
                         f"{html.escape(n[:26])}</span>")
        rare_shared = sum(1 for n in here & prev
                          if FREQ[n] < max(3, len(V) // 3)
                          and not re.match(rf"ps_{ch}_\d+", n))
        link = (f"<span class='tie t{min(rare_shared,3)}'>{rare_shared}</span>"
                if v > min(V) else "<span class='tie'></span>")
        rows.append(
            f"<tr class='v{dk}{ds}'><td class='n'>{v}</td>{cells}"
            f"<td class='t'>{mark(V[v], words)}"
            f"<div class='nodes'>{link}{''.join(chips)}</div></td></tr>")

    reps = "".join(
        f"<tr><td><code>{html.escape(p)}</code></td>"
        f"<td class='n'>{len(vs)}</td>"
        f"<td class='r'>{' '.join(str(x) for x in sorted(vs))}</td></tr>"
        for p, vs in sorted(phr.items(), key=lambda x: (-len(x[1]), -len(x[0])))[:14])

    pats = "".join(
        f"<tr><td><b>{html.escape(str(q.get('name') or ''))}</b>"
        f"<div class='why'>{html.escape(str(q.get('because') or '')[:150])}</div></td>"
        f"<td class='n'>{len(q.get('instances') or [])}</td></tr>"
        for q in got.get("patterns") or [])

    keyline = (f"<p class='key'><b>Doug's reading, recorded before the run:</b> "
               f"{html.escape(key['note'])}. His seams are the "
               f"<span class='dk'>marked rows</span>.</p>" if key["note"] else "")

    page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Psalm {ch}, grouped</title><style>
 body{{font:15px/1.5 system-ui,sans-serif;margin:0 auto;padding:2rem;max-width:1000px;
      background:#faf9f7;color:#191919}}
 h1{{font-size:1.45rem;margin:0 0 .2rem}}
 h2{{font-size:.95rem;margin:2rem 0 .4rem;border-bottom:1px solid #e3e0da;
     padding-bottom:.3rem}}
 .note,.key{{color:#5a5a5a;font-size:.9rem;margin:.3rem 0 1rem}}
 table.psalm{{border-collapse:collapse;width:100%}}
 table.psalm td{{padding:.28rem .35rem;vertical-align:top}}
 td.n{{width:1.8rem;text-align:right;color:#a09781;font-size:.8rem;
   font-variant-numeric:tabular-nums}}
 td.b{{width:12px;padding:0;border-left:3px solid #cdbf95;background:#f4f1e8;
   position:relative}}
 td.b.empty{{border-left:3px solid transparent;background:none}}
 td.b[data-d="2"]{{border-left-color:#a8bfa0;background:#eef3ea}}
 td.b[data-d="3"]{{border-left-color:#b9a8c4;background:#f2eef4}}
 td.b.start{{border-top:2px solid #8a7a52}}
 td.b[data-d="2"].start{{border-top-color:#5f7d4f}}
 td.t{{line-height:1.55}}
 .gl{{position:absolute;left:16px;top:-2px;white-space:nowrap;font-size:.72rem;
   font-weight:600;color:#6d6144;background:#faf9f7;padding:0 4px;z-index:2}}
 tr.dk td.t{{border-top:2px dashed #a4432b}}
 tr.sub td.t{{border-top:1px dotted #c58b78}}
 .dk{{border-top:2px dashed #a4432b;padding-top:1px}}
 mark{{background:#fdf2c4;padding:0 1px;border-radius:2px}}
 .nodes{{margin:.2rem 0 .1rem;display:flex;flex-wrap:wrap;gap:3px;
   align-items:center}}
 .chip{{font-size:.68rem;padding:1px 6px;border-radius:9px;background:#eef1ea;
   border:1px solid #d5ddcf;color:#4c5647;white-space:nowrap}}
 .chip.dim{{background:#f6f5f1;border-color:#e8e5dc;color:#b4afa2}}
 .chip.bond{{background:#e6efdc;border-color:#7d9b63;color:#33452a;
   font-weight:600}}
 .tie{{font-size:.66rem;width:1.15rem;text-align:center;border-radius:3px;
   color:#b4afa2;font-variant-numeric:tabular-nums}}
 .tie.t1{{background:#e6efdc;color:#3f5733}} .tie.t2{{background:#cfe1bd;color:#2c4222}}
 .tie.t3{{background:#b5d19c;color:#22331a}}
 table.side{{border-collapse:collapse;width:100%;font-size:.88rem}}
 table.side th{{text-align:left;color:#8a8375;font-size:.72rem;font-weight:600;
   text-transform:uppercase;letter-spacing:.04em;padding:.3rem .4rem}}
 table.side td{{padding:.35rem .4rem;border-top:1px solid #eee8e0;
   vertical-align:top}}
 td.r{{color:#8a8375;font-variant-numeric:tabular-nums;font-size:.82rem}}
 .why{{color:#8d8474;font-size:.8rem;font-style:italic}}
 code{{background:#f2efe8;padding:1px 5px;border-radius:3px;font-size:.85em}}
 @media(prefers-color-scheme:dark){{
  body{{background:#15140f;color:#ededed}} .note,.key,td.r{{color:#a8a8a8}}
  td.b{{background:#231f16;border-left-color:#6b5f3f}}
  td.b[data-d="2"]{{background:#1b211a;border-left-color:#4f6b45}}
  td.b[data-d="3"]{{background:#201c23;border-left-color:#6d5f78}}
  .gl{{background:#15140f;color:#cdbf95}}
  mark{{background:#4a3f1c;color:#f4ecd4}}
  .chip{{background:#1e211c;border-color:#333a30;color:#9aa892}}
  .chip.dim{{background:#1a1915;border-color:#26241e;color:#5d5a51}}
  .chip.bond{{background:#26331d;border-color:#5f7d4f;color:#c6dcb2}}
  .tie{{color:#5d5a51}}
  table.side td{{border-color:#2a2820}} code{{background:#2a2820}}
  h2{{border-color:#3a362b}} .why{{color:#857c6c}}}}
</style></head><body>
<h1>Psalm {ch}, grouped</h1>
<p class="note">The text with the structure over it. <b>Bands</b> on the left
are groups, one column per level. <b>Highlights</b> are every phrase of two or
more words occurring in three or more verses &mdash; found with no model and no
word list. <b>Chips</b> under each verse are the nodes extracted there:
<span class='chip dim'>dimmed</span> where the node is in a third of the psalm
or is that verse's own speech node, and so says nothing about what belongs
with what; <span class='chip bond'>green</span> where a node is shared with
the verse above and is rare enough to mean something. The number at the left
of the chips is how many such ties a verse has to the one before it.</p>
{keyline}
<table class="psalm">{''.join(rows)}</table>

<h2>Repetition, found mechanically</h2>
<p class="note">This is the whole detector: any phrase in three or more verses,
longest kept. On Psalm 103 it finds both collections the model missed.</p>
<table class="side"><tr><th>phrase</th><th>n</th><th>verses</th></tr>{reps}</table>

<h2>Patterns the model proposed</h2>
<table class="side"><tr><th>form</th><th>n</th></tr>{pats or
  "<tr><td colspan=2 class='why'>none</td></tr>"}</table>
</body></html>"""
    out = ROOT / "out" / f"psalm-{ch}.html"
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    for c in (int(x) for x in (sys.argv[1:] or ["103"])):
        print(f"wrote {build(c)}")
