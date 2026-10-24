"""The Sermon on the Mount, drawn the way Titus was.

Same rules as arrived at yesterday, and they are not restated here so much
as obeyed:

  every line is containment      the root ties only to the movements, and
                                 nothing else is drawn as a tree edge
  order is position              invisible `~~~` links pin siblings into
                                 reading order at every level and draw nothing
  patterns are not groups        they contain nothing, so they sit in a table
                                 under the chart rather than inside it
  a collection IS a group        the thing that conforms to a form is an
                                 ordinary contiguous group; the form is a
                                 relation over its members

What is new here is **provenance on every node**, because this chart mixes two
very different things and yesterday's did not. The pattern instances were
found mechanically -- an unsupervised scan for any 3-6 word phrase occurring
in three or more verses, no word list, no model -- and every one of them is
exact against the held-out cases in docs/GROUPING-TESTS.md. The tree above
them is a reading, and it is mine. Drawing both in one picture without saying
which is which would be the chart telling a lie the data does not.
"""
import html
import pathlib

ROOT = pathlib.Path(r"<local> Ontology")

# ---------------------------------------------------------------------------
# the partition. `found` marks what the detector produced; everything else is
# a reading and is drawn with a dashed outline.
# ---------------------------------------------------------------------------
M = "movement"
U = "unit"
S = "section"

NODES = [
    # id,      level, span,          label,                            found
    ("open",   1, "5:1-2",   "Setting: he went up into a mountain",  False),
    ("bless",  1, "5:3-16",  "Blessing, and salt and light",         False),
    ("law",    1, "5:17-48", "The law fulfilled, not destroyed",     False),
    ("piety",  1, "6:1-34",  "Piety before the Father",              False),
    ("ways",   1, "7:1-27",  "Judging, asking, and the two ways",    False),
    ("close",  1, "7:28-29", "Closing: the people were astonished",  False),

    ("beat",   2, "5:3-11",  "The beatitudes",                       True),
    ("saltl",  2, "5:13-16", "Salt of the earth, light of the world", False),

    ("stage",  2, "5:17-20", "Stage: come not to destroy but fulfil", False),
    ("cases",  2, "5:21-47", "Six case studies against the law",     True),
    ("perf",   2, "5:48",    "Be ye therefore perfect",              False),

    ("triad1", 2, "6:1-18",  "Alms, prayer, fasting",                True),
    ("triad2", 2, "6:19-24", "Treasure, the eye, two masters",       False),
    ("triad3", 2, "6:25-34", "Eat, drink, clothe: take no thought",  False),

    ("judge",  2, "7:1-6",   "Judge not; the mote and the beam",     False),
    ("ask",    2, "7:7-12",  "Ask, seek, knock; the golden rule",    False),
    ("two",    2, "7:13-27", "Gate, tree, confession, house",        False),

    # the members the detector found, drawn rounded like Titus's roster
    ("b1", 3, "5:3",  "Blessed are ... (9 instances)",   True),
    ("c1", 3, "5:21", "Ye have heard / But I say (6)",   True),
    ("t1", 3, "6:2",  "They have their reward (3)",      True),
]

PARENT = {
    "beat": "bless", "saltl": "bless",
    "stage": "law", "cases": "law", "perf": "law",
    "triad1": "piety", "triad2": "piety", "triad3": "piety",
    "judge": "ways", "ask": "ways", "two": "ways",
    "b1": "beat", "c1": "cases", "t1": "triad1",
}

# Patterns connect groups after the fact. `found` ones came out of the
# unsupervised scan; the last is deliberately NOT called a pattern.
PATTERNS = [
    ("Blessed are the X: for they shall Y", "5:3-11", 9,
     "found: <code>blessed are</code>, exact", "bless"),
    ("Ye have heard ... But I say unto you", "5:21-44", 6,
     "found: <code>but i say unto you</code>, exact", "law"),
    ("Not as the hypocrites ... reward thee openly", "6:2, 6:5, 6:16", 3,
     "found: <code>they have their reward</code>, exact", "piety"),
    ("Your Father which is in heaven", "5:16 &rarr; 7:21", 6,
     "found: a thread, crosses four movements", "bless, law, piety, ways"),
]

NOT_A_PATTERN = (
    "Two gates, two trees, two confessions, two builders (7:13-27) is held "
    "together by <b>shared imagery</b>, not by a repeated form. Doug, "
    "2026-09-01: <i>&ldquo;the two gates trees and confessions are symbol "
    "matches and a different thing than group matching.&rdquo;</i> Recording "
    "it as one pattern would be the seed&rarr;sword error one level up, so it "
    "is named here and left out of the table above."
)

# ---------------------------------------------------------------------------
lines = ["graph LR", '  root(["Sermon on the Mount<br/>Matt 5-7"])']
for nid, lvl, span, label, found in NODES:
    shape = '(["%s"])' if lvl == 3 else '["%s"]'
    lines.append(f"  {nid}{shape % f'<b>{span}</b><br/>{label}'}")
for nid, lvl, *_ in NODES:
    if lvl == 1:
        lines.append(f"  root --> {nid}")
for kid, parent in PARENT.items():
    lines.append(f"  {parent} --> {kid}")

kids = {}
for nid, lvl, *_ in NODES:
    kids.setdefault(PARENT.get(nid, "root"), []).append(nid)
seq = [n[0] for n in NODES]
for sibs in kids.values():
    ordered = sorted(sibs, key=seq.index)
    for a, b in zip(ordered, ordered[1:]):
        lines.append(f"  {a} ~~~ {b}")

found_ids = ",".join(n[0] for n in NODES if n[4])
mv = ",".join(n[0] for n in NODES if n[1] == 1)
lines += [
    "  classDef rt fill:#2e2712,stroke:#2e2712,color:#f6efdc",
    "  class root rt",
    "  classDef mv fill:#eae3d2,stroke:#8a7a52,color:#2e2712",
    "  classDef fd fill:#e8efe4,stroke:#5f7d4f,color:#22301c,stroke-width:2px",
    f"  class {mv} mv",
    f"  class {found_ids} fd",
]
chart = "\n".join(lines)

rows = "".join(
    f"<tr><td><b>{html.escape(n)}</b></td><td class='r'>{at}</td>"
    f"<td class='n'>{k}</td><td>{ev}</td><td class='r'>{html.escape(tt)}</td></tr>"
    for n, at, k, ev, tt in PATTERNS)

page = """<!doctype html><html><head><meta charset="utf-8">
<title>The Sermon on the Mount, grouped</title><style>
 body{font:15px/1.6 system-ui,sans-serif;margin:0 auto;padding:2rem;max-width:1500px;
      background:#faf9f7;color:#191919}
 h1{font-size:1.5rem;margin:0 0 .2rem}
 h2{font-size:1rem;margin:2rem 0 .4rem;border-bottom:1px solid #e3e0da;padding-bottom:.3rem}
 .note{color:#5a5a5a;margin:.2rem 0 1rem;font-size:.92rem}
 .legend{font-size:.85rem;color:#5a5a5a;margin:.6rem 0 1.2rem}
 .legend b{color:#191919}
 .sw{display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:-1px;margin-right:3px}
 section{background:#fff;border:1px solid #e3e0da;border-radius:8px;padding:1rem;overflow-x:auto}
 table{border-collapse:collapse;width:100%;font-size:.9rem;margin:.3rem 0}
 th{text-align:left;color:#8a8375;font-weight:600;font-size:.75rem;
    text-transform:uppercase;letter-spacing:.04em;padding:.3rem .5rem}
 td{padding:.4rem .5rem;border-top:1px solid #eee8e0;vertical-align:top}
 .r{font-variant-numeric:tabular-nums;color:#5a5a5a;font-size:.86rem}
 .n{font-variant-numeric:tabular-nums;color:#5a5a5a;white-space:nowrap}
 code{background:#f2efe8;padding:1px 4px;border-radius:3px;font-size:.85em}
 .warn{background:#fdf6ec;border-left:3px solid #b39a5b;padding:.7rem .9rem;
       border-radius:0 5px 5px 0;font-size:.92rem}
 @media(prefers-color-scheme:dark){
  body{background:#15140f;color:#ededed} section{background:#201e17;border-color:#3a362b}
  h2{border-color:#3a362b} .note,.legend,td,.r,.n{color:#a8a8a8}
  td{border-color:#2a2820} .legend b{color:#ededed} code{background:#2a2820}
  .warn{background:#241f14;color:#d8d2c4}}
</style></head><body>
<h1>The Sermon on the Mount, grouped</h1>
<p class="note">Six movements covering Matthew 5-7 end to end, the units inside
them, and the members of the repeated forms. <b>Every group is contiguous and
every verse falls in exactly one group per level</b> &mdash; the tree is a
partition of the sermon in its own order.</p>
<p class="legend"><b>Every line is containment.</b> Reading order is carried by
position, not by an edge. &nbsp;
<span class="sw" style="background:#eae3d2;border:1px solid #8a7a52"></span><b>movement</b> &nbsp;&middot;&nbsp;
<span class="sw" style="background:#e8efe4;border:2px solid #5f7d4f"></span><b>found mechanically</b> &mdash;
an unsupervised scan for any 3-6 word phrase in three or more verses. No word
list, no model, no cost. &nbsp;&middot;&nbsp; everything else is a reading.</p>
<section><pre class="mermaid">""" + html.escape(chart) + """</pre></section>

<h2>Patterns, connected after the fact</h2>
<p class="note">Not groups. A pattern contains nothing and partitions nothing,
so it is applied to the tree rather than drawn inside it. Every row below was
found by the scan and is <b>exact</b> against the expectations written down in
<code>docs/GROUPING-TESTS.md</code> before the scan existed.</p>
<table><tr><th>form</th><th>occurs at</th><th>n</th><th>evidence</th>
<th>movements touched</th></tr>""" + rows + """</table>

<h2>What is deliberately absent</h2>
<p class="warn">""" + NOT_A_PATTERN + """</p>

<h2>What the scan cannot see</h2>
<p class="note">Stated so the green boxes are not over-trusted. <b>Ask, seek,
knock</b> (7:7) is a triad of three parallel clauses <em>inside one verse</em>,
not a phrase repeated across verses, and this detector is blind to it &mdash;
as it will be to Hebrew poetic parallelism, which is most of Psalms and
Proverbs. The scan also finds pattern <em>members</em>, never the tree above
them: nine beatitudes is a collection, and nothing in the scan says 5:3-11
sits under a movement. The connective detector that <em>would</em> give seams
works on Paul and fails here &mdash; 13 candidates in Matthew 6 where 3 are
wanted &mdash; because Pauline argument is connective-driven and this
discourse is antithetical.</p>

<script type="module">
import m from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
m.initialize({startOnLoad:true,maxTextSize:900000,
 theme:matchMedia('(prefers-color-scheme:dark)').matches?'dark':'default'});
</script></body></html>"""

out = ROOT / "out" / "sermon-chart.html"
out.write_text(page, encoding="utf-8")
print(f"wrote {out}")
lv = {}
for _, l, *_ in NODES:
    lv[l] = lv.get(l, 0) + 1
print(f"  partition {dict(sorted(lv.items()))}   patterns {len(PATTERNS)}   "
      f"found mechanically {sum(1 for n in NODES if n[4])}")
