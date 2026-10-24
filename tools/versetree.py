"""Draw one verse: MACULA's tree above the words, our edges below them.

2026-09-21: work on verse examples one at a time until the node structures
within the sentence level are always constructed correctly, and then a really
good way to visualize the tree for a verse.

## Why the two halves face each other

The question being asked of each verse is always the same: **does the
structure we built say what MACULA's tree says?** So the source tree is drawn
above the words as nested constituents with their rule and role labels, and
the edges we extracted are drawn below the same words as arcs. A relation that
MACULA binds and we did not shows up as a box above with no arc beneath it.

That is not hypothetical. Exodus 8:6 is tagged `rule="P-PP"` over
*there-is-not · like · Yahweh*, and the extraction produced two edges hanging
off nothing:

    {"type": "is",   "src": null, "dst": "#thereNoOne"}
    {"type": "like", "src": null, "dst": "#lord"}

**55.6% of the corpus's 261,919 edges had fewer than two ends** when this was
written, so an arc with a loose end is drawn dashed and red — it is the thing
to look for.

## Reading direction

Hebrew is laid out right to left, as it is written, with a marker saying so.
For the reader view: an arrow indicator next to the Hebrew reminding novices
to read right to left.

    python tools/versetree.py Exo.8.6
    python tools/versetree.py Gen.1.4 --open
"""
from __future__ import annotations

import argparse
import collections
import gzip
import html
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from verse import BOOKCODE, source_file, words_of          # noqa: E402

OUT = ROOT / "out"

# What MACULA's role letters mean, spelled out for a reader who is new to it.
ROLE = {"v": "verb", "s": "subject", "o": "object", "o2": "object 2",
        "io": "indirect", "p": "predicate", "pp": "prep. phrase",
        "motive": "motive",
        "adv": "adverbial", "aux": "auxiliary", "cj": "conjunction"}

# WHAT THE MOOD NAMES MEAN. 2026-09-21: the question what "wayyiqtol" means,
# and the decision to go ahead because it is not only one reader who wonders.
#
# The page was printing MACULA's raw grammatical labels at a reader, which is
# a fault in the page rather than in the reader — the role letters were
# already expanded to "subject" and "prep. phrase" and the moods were not.
#
# The names are forbidding and the reason is dull: they are all built from one
# paradigm verb, קטל, so the label spells out the SHAPE of the form rather
# than saying what it does. `wayyiqtol` is the prefix וַ fused onto a `yiqtol`,
# and the fusion flips the sense to a past that carries sequence.
#
# This distinction is not decoration here. Genesis 1:3 pairs a JUSSIVE "let
# there be light" with a WAYYIQTOL "and there was light" — same verb, and the
# mood is the only thing separating the command from its fulfilment.
MOOD = {
    "wayyiqtol": "and then — narrative past",
    "qatal": "did — completed",
    "yiqtol": "will do — incomplete",
    "weqatal": "and will do",
    "imperative": "do it! — a command",
    "jussive": "let it be — a command in the third person",
    "cohortative": "let me, let us",
    "participle active": "doing — ongoing",
    "participle passive": "being done",
    "infinitive construct": "to do",
    "infinitive absolute": "doing — emphatic",
}


# Group-member links whose id is not what a reader should see: `agent_act`
# is so named only because the superseded flat layer already has an "act".
LINK_SHOWN = {"agent_act": "act", "until_limit": "until",
              "when_if_though": "when / if / though",
              "conceded": "even though",
              "holds_anyway": "still", "its_ground": "because"}


def word_label(n, fallback=""):
    """A word node's label: the Hebrew word's usual rendering first, this
    verse's under it, where they differ. 2026-09-26, on Psa 23:2
    'waters of quiet' (מְנוּחָה, most often 'resting place'): going with the
    Hebrew is preferable, 'From Hebrew' might be the clearest label, and the
    BSB is not named where the word did not come from it. Both come from
    MACULA's English; neither is the BSB's word, so neither is labelled so.
    Nor is the first labelled "From Hebrew": the usual rendering is not
    always the literal one — פָּנִים is "face" and most often rendered
    "presence" (Psa 143:7 "hide your FACE"), אִשָּׁה most often "wife" (Gen
    2:23 "she shall be called WOMAN"). It is labelled what it is."""
    txt = (n or {}).get("text") or fallback
    u = (n or {}).get("usual")
    return f"usually: {u}<br/><i>here: {txt}</i>" if u else txt


def gloss_mood(m):
    """`wayyiqtol` -> `and then — narrative past · wayyiqtol`."""
    if not m or m not in MOOD:
        return m
    return f"{MOOD[m]} · {m}"


# One stylesheet for every page this tool renders, so the verse page
# and the suite page cannot drift apart.
_CSS = """:root{--bg:#fbfaf7;--ink:#241f1a;--muted:#6b6257;--faint:#a89e90;
--line:#d9d2c6;--ochre:#9a6b2f;--blue:#2f5d8a;--red:#a83232;--card:#fff}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
--bg:#16141f;--ink:#ece7e1;--muted:#a49c91;--faint:#6f665c;--line:#3a3530;
--ochre:#d79b4e;--blue:#7fb0e0;--red:#e08585;--card:#201d2a}}
body{background:var(--bg);color:var(--ink);margin:0;padding:22px 18px;
font:15px/1.5 ui-sans-serif,system-ui,sans-serif}
h1{font-size:20px;margin:0 0 4px}
h2{font-size:13px;letter-spacing:.09em;text-transform:uppercase;
color:var(--muted);font-weight:600;margin:26px 0 8px}
p.h{color:var(--muted);margin:0 0 16px}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:8px;
background:var(--card);padding:10px}
.verse{display:flex;flex-wrap:wrap;gap:12px;border:1px solid var(--line);
border-radius:8px;padding:14px;background:var(--card)}
.vw{display:flex;flex-direction:column;align-items:center;min-width:54px}
.vw b{font-size:19px;font-weight:600}
.vw i{font-size:11px;color:var(--muted);font-style:normal;text-align:center}
.eng{margin:10px 2px 0;max-width:72ch}
.dir{color:var(--muted);font-size:12px;margin:6px 2px 0}
.key{margin-top:14px;color:var(--muted);font-size:13px;max-width:74ch}
.key b{color:var(--red)}
form{margin:0 0 18px} input{font:inherit;padding:6px 9px;
border:1px solid var(--line);border-radius:6px;background:var(--card);
color:var(--ink)}
"""


def verse_words(ref):
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if d.get("ref") == ref:
            return d.get("words") or []
    return []


def our_graph(ref):
    nodes, edges = {}, []
    for line in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if d.get("ref") == ref:
            nodes[d["id"]] = d
    for line in gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt",
                          encoding="utf-8"):
        e = json.loads(line)
        if e.get("ref") == ref:
            edges.append(e)
    return nodes, edges


def build(ref):
    ws = verse_words(ref)
    if not ws:
        raise SystemExit(f"no words for {ref}")
    rtl = any("֐" <= c <= "׿" for w in ws for c in (w.get("t") or ""))
    nodes, edges = our_graph(ref)

    # --- MACULA constituents over this verse -----------------------------
    spans = []
    src = source_file(ref)
    if src and src.exists():
        try:
            root = ET.parse(src).getroot()
            mw = words_of(ref, root)
            pos = {id(w): i for i, w in enumerate(mw)}
            parent = {c: p for p in root.iter() for c in p}
            for g in root.iter("wg"):
                inner = [pos[id(w)] for w in g.iter("w") if id(w) in pos]
                if len(inner) < 1:
                    continue
                depth = 0
                cur = g
                while cur in parent:
                    cur = parent[cur]
                    depth += 1
                # THE CLAUSE'S OWN PARTS, BY ROLE. 2026-09-21: start
                # with the command node 'be light', which has tuple relationships
                # with the command 'be' and the object 'light'. That is a
                # clause REIFIED — the utterance is a node, and its verb and
                # its subject hang off it as typed relations — and it is what
                # makes a clause-to-clause relation expressible at all. The
                # roles are MACULA's own, not invented: `v` and `s` here.
                parts = []
                for ch in list(g):
                    if not ch.get("role"):
                        continue
                    kids = [pos[id(w)] for w in
                            ([ch] if ch.tag == "w" else ch.iter("w"))
                            if id(w) in pos]
                    if kids:
                        parts.append({"role": ch.get("role"),
                                      "lo": min(kids), "hi": max(kids)})
                # THE VERB'S MOOD, CARRIED ON THE CLAUSE. It is the feature
                # that separates a command from a statement, and 0 of 261,920
                # edges hold it, because a verb is an edge LABEL and a label
                # has no room for morphology. A clause node does.
                vlem = vmood = None
                for ch in list(g):
                    if ch.get("role") != "v":
                        continue
                    hw = ch if ch.tag == "w" else next(iter(ch.iter("w")), None)
                    if hw is not None:
                        vlem, vmood = hw.get("lemma"), hw.get("type")
                    break
                spans.append({"lo": min(inner), "hi": max(inner),
                              "rule": g.get("rule") or "",
                              "cls": g.get("class") or "",
                              "role": g.get("role") or "",
                              "parts": parts,
                              "verb_lemma": vlem, "verb_mood": vmood,
                              "words": sorted(inner),
                              "depth": depth})
        except ET.ParseError:
            pass
    # outermost first, then longest, so the stack reads top-down
    spans.sort(key=lambda s: (s["depth"], -(s["hi"] - s["lo"])))
    # assign each span a row, packing non-overlapping ones together
    rows = []
    for s in spans:
        for r, used in enumerate(rows):
            if all(s["hi"] < u[0] or s["lo"] > u[1] for u in used):
                used.append((s["lo"], s["hi"]))
                s["row"] = r
                break
        else:
            rows.append([(s["lo"], s["hi"])])
            s["row"] = len(rows) - 1

    # --- our edges, mapped onto word positions ---------------------------
    # a node is placed at the position of the word whose lemma and text it
    # matches; composites take the leftmost member they cover
    def place(nid_):
        if not nid_:
            return None
        n = nodes.get(nid_) or {}
        lem, txt = n.get("lemma"), (n.get("text") or "").lower()
        best = None
        for i, w in enumerate(ws):
            if lem and w.get("l") == lem:
                return i
            g = (w.get("g") or "").lower()
            if txt and g and (g == txt or txt.startswith(g)):
                best = i if best is None else best
        return best

    arcs = []
    for e in edges:
        a, b = place(e.get("src")), place(e.get("dst"))
        arcs.append({"a": a, "b": b, "type": e.get("type") or "",
                     "loose": is_lost(e),
                     "bydesign": one_ended_by_design(e),
                     "note": ",".join(k for k in
                                      ("negated", "comparison", "scopes_over",
                                       "inferred_subject")
                                      if e.get(k))})
    # WHICH CLAUSE EACH NODE SITS IN. 2026-09-21, sketching the expected
    # shape: "(God -> issues -> (command node -> be -> light)) -> causes ->
    # ..." — clauses as nodes that other relations can point at. Drawing the
    # verse as a flat edge list is why it could not be pictured; MACULA's own
    # clause spans give the nesting, so each node is filed under the
    # innermost clause whose words cover it.
    clause_of = {}
    cls = [s for s in spans if s.get("cls") == "cl"]
    for nid_ in nodes:
        i = place(nid_)
        if i is None:
            continue
        inner = [s for s in cls if s["lo"] <= i <= s["hi"]]
        if inner:
            inner.sort(key=lambda s: (s["hi"] - s["lo"]))
            clause_of[nid_] = cls.index(inner[0])
    return ws, rtl, spans, len(rows), arcs, edges, cls, clause_of


def one_ended_by_design(e):
    """Is this edge missing an end for a REASON the extraction recorded?

    Not every one-ended edge is a fault, and treating them alike overstated
    the damage badly: an intransitive verb has no object, and an agentless
    passive has no agent on purpose. Counting those as broken put the loss at
    55.6% of edges when the real figure is 32%.

        no object, marked intransitive     52,695   20.1%   correct
        no agent, deliberately unexpressed 10,343    3.9%   correct
        no object, unresolved possessor    18,153    6.9%   honest unknown
    """
    if e.get("dst") is None and (e.get("intransitive")
                                 or e.get("unresolved_possessor")):
        return True
    return e.get("src") is None and e.get("agent") == "unexpressed"


def is_lost(e):
    """An end that is missing with nothing to explain it."""
    if one_ended_by_design(e):
        return False
    return e.get("src") is None or e.get("dst") is None


def mermaid_built(ref, graph=None, force=None, back=None, jump=None,
                  extra=(), click=None, only=None, show_ref=None):
    """The clause layer AS BUILT — read from the graph, not re-derived.

    `graph` is an optional (nodes, edges) already loaded for a whole passage,
    so drawing fifteen verses does not rescan 700,000 records fifteen times;
    `force` optionally maps a clause id to its meaning-layer force from the
    ontology, shown on the clause. With a passage loaded, a pair member in
    ANOTHER verse is drawn as a dashed ghost instead of silently dropped —
    Exodus 8:2's pairs point back to the command in 8:1. `back` names a page
    function each clause calls when clicked, so a passage overview and this
    diagram can link to each other node for node; `jump` the one a ghost
    calls, to go to its own verse's diagram. `extra` is (src, dst, label)
    relations computed outside the graph — previews of proposed kinds —
    drawn dashed, with a ghost for any end in another verse. `click` names a
    page function every node calls with its GRAPH id — the passage page uses
    it to show the stretch of the Berean text the node covers.

    A GROUPING THAT SPANS VERSES IS DRAWN IN EVERY VERSE IT TOUCHES.
    2026-09-25: nodes should not live in verses; verses are layered on top
    of the graph as a reference mapping (PRINCIPLES 46). A speech turn over
    BSB 8:1-4 had an id "in" 8:2 and so appeared in 8:2's diagram only; the
    view now asks which groupings have a member here, not which were minted
    here.

    The first version of this drew clauses straight from the MACULA XML, and
    on Psalm 107:1 it showed SIX clause nodes where the graph holds three: it
    was rendering the `ClCl` and `cjpCLx` wrappers that `_bears_roles`
    deliberately skips. A suite page that re-derives its own picture can show
    a structure the extractor never produced, and go green doing it.

    So this reads `placeholder-nodes` and `placeholder-edges` — the same
    files `tests/test_verse_structure.py` checks — and draws what is actually
    there. If the drawing and the test ever disagree now, one of them is
    broken rather than merely different.
    """
    def esc(s):
        return (str(s or "").replace('"', "'").replace("[", "")
                .replace("]", "").replace("(", "").replace(")", "")
                .replace("|", "/").replace("{", "").replace("}", "").strip())

    if graph is None:
        nodes, edges = our_graph(ref)
        everything = nodes
    else:
        everything = graph[0]
        nodes = {k: v for k, v in graph[0].items() if v.get("ref") == ref}
        edges = [e for e in graph[1] if e.get("ref") == ref]
        # groupings minted elsewhere that have a member here — repeated
        # until stable, since a turn may reach this verse through a grouping
        # that itself reaches it
        here = set(nodes)
        while True:
            # MEMBERSHIP only: a sender or addressee named here does not put
            # the communication in this verse — Psalm 23:4-5's addresses
            # were being drawn in 23:1 because their sender, David, is named
            # in the heading
            more = {e["src"] for e in graph[1]
                    if e.get("clause_link") and e.get("dst") in here
                    and e.get("type") not in ("sender", "addressee")
                    and (graph[0].get(e.get("src")) or {}).get("pair")
                    and e["src"] not in here}
            if not more:
                break
            here |= more
            for m in more:
                nodes[m] = graph[0][m]
        known_e = {id(e) for e in edges}
        edges += [e for e in graph[1] if e.get("src") in nodes
                  and nodes[e["src"]].get("pair") and id(e) not in known_e]
        # ONLY WHAT BEARS ON THIS VERSE. 2026-09-25: visually there is no
        # need to show every sibling part for every verse; show the parent and
        # the nodes that have a direct bearing. A speech turn
        # or a psalm's Writing has members all through its span; drawing
        # every one as a ghost in every verse buried the verse. For these
        # large groupings only the members HERE — and the groupings above
        # them — are drawn; the rest is a count on the node. A small
        # grouping (a pair, an if/then) keeps its other member: that
        # member IS the relation.
        agg = {nid for nid, n_ in nodes.items()
               if n_.get("pair") and n_.get("kind") in ("turn", "writing",
                                                        "address")}
        hidden = collections.Counter()
        kept = []
        for e in edges:
            if e.get("src") in agg and e.get("clause_link") and \
                    e.get("dst") not in nodes:
                hidden[e["src"]] += 1
                continue
            kept.append(e)
        edges = kept
    if graph is None:
        hidden = collections.Counter()
    cls = sorted((n for n in nodes.values() if n.get("clause")
                  and n.get("ref") == ref),
                 key=lambda n: n.get("order", 0))
    pairs = [n for n in nodes.values() if n.get("pair")]

    # ONE CLAUSE ONLY. 2026-09-25, on the reader's structure chip: the
    # verse diagrams are too wide to sit under a verse, so the panel shows
    # the verse's clauses compactly and a click opens ONE clause: its
    # content and roles (and the event a causative wraps), the groupings it
    # belongs to, and its links — every other clause it touches a dotted
    # reference. Big only for the clause asked about.
    if only:
        keep = {only}
        grew = True
        while grew:
            grew = False
            for e in edges:
                if e.get("src") in keep and e.get("dst") not in keep and (
                        e.get("type") in ("asserts", "causes", "member")
                        or e.get("clause_role")):
                    keep.add(e.get("dst"))
                    grew = True
        mine = {p["id"] for p in pairs
                if any(e.get("src") == p["id"] and e.get("dst") == only
                       for e in edges)}
        cls = [n for n in cls if n["id"] == only]
        pairs = [p for p in pairs if p["id"] in mine]
        nodes = {k: v for k, v in nodes.items()
                 if k in keep or k in mine or not (v.get("clause")
                                                   or v.get("content")
                                                   or v.get("pair"))}
        edges = [e for e in edges
                 if e.get("src") in keep or e.get("src") in mine
                 or (e.get("clause_link") and e.get("src") == only)]

    # WHERE A GROUPING IS INTRODUCED: the earliest verse its members reach.
    # 2026-09-25: if the display goes verse by verse, a dotted box encapsulates
    # nodes introduced earlier and children described later.
    # So a grouping is SOLID in the verse that introduces it and DOTTED in
    # every other verse it spans; a member in another verse is a dotted ghost.
    # Each verse shows what it contributes, with its context around it.
    def vkey(r):
        return [int(x) if x.isdigit() else 0 for x in r.split(".")[1:]]
    src_edges = graph[1] if graph is not None else edges
    members = collections.defaultdict(list)
    for e in src_edges:
        if e.get("clause_link") and (everything.get(e.get("src")) or {}) \
                .get("pair"):
            members[e["src"]].append(e.get("dst"))

    def first_ref(nid, depth=0):
        n = everything.get(nid) or nodes.get(nid) or {}
        if not n.get("pair") or depth > 4:
            return n.get("ref") or nid.split("#")[0]
        refs_ = [first_ref(m, depth + 1) for m in members.get(nid, []) if m]
        return min(refs_, key=vkey) if refs_ else n.get("ref")
    if not cls:
        return 'graph LR\n  none["no clause layer built for this verse"]'

    ids = {}
    lines = ["graph LR"]
    for n in cls:
        i = f"c{n['order']}"
        ids[n["id"]] = i
        mood = gloss_mood(n.get("verb_mood")) or n.get("rule") or "clause"
        conn = n.get("connective_sense")
        up = (force or {}).get(n["id"])
        lines.append(f'  {i}(["{esc(n.get("text"))}<br/>'
                     + (f'<b>{esc(up)}</b> · ' if up else "")
                     + f'{esc(mood)}'
                     + (f' · {esc(conn)}' if conn else "") + '"])')
        if click:
            lines.append(f'  click {i} call {click}("{n["id"]}")')
        elif back:
            lines.append(f'  click {i} call {back}("{ref}", {n["order"]})')
    try:
        moved = json.loads((OUT / "versemap.json").read_text(
            encoding="utf-8")).get("moved") or {}
    except (OSError, ValueError):
        moved = {}

    all_edges = graph[1] if graph is not None else edges
    for n in pairs:
        ids[n["id"]] = f"p{len(ids)}"
        if n.get("kind") == "turn":
            # A SPEECH TURN SAYS WHAT IT SPANS AND WHERE IT IS SAID.
            # 2026-09-25, reading 7:27: is that part of a single speech turn
            # that aggregates almost all of BSB 8:1-4? It is — but the node
            # was labelled with the rule's own description, "a speech still
            # open at a verse's end", which reads as if it were about this
            # verse alone.
            mem = [e for e in all_edges if e.get("src") == n["id"]]
            # what it SAYS spans the verses — not where its sender was
            # named (Moses in 8:5 for the reply in 8:6-7) — and that includes
            # every communication nested inside it: the LORD's words to
            # Moses run as far as the message he gives him to deliver
            def says_in(nid, depth=0):
                out = set()
                if depth > 6:                           # circuit breaker
                    return out
                for e in all_edges:
                    if e.get("src") == nid and \
                            e.get("type") in ("frame", "part"):
                        d = e.get("dst") or ""
                        out.add(d.split("#")[0])
                        if (everything.get(d) or {}).get("pair"):
                            out |= says_in(d, depth + 1)
                return out
            span = sorted(says_in(n["id"]),
                          key=lambda r: [int(x) if x.isdigit() else 0
                                         for x in r.split(".")[1:]])
            fr = next((e.get("dst") for e in mem
                       if e.get("type") == "frame"), None)
            said = (everything.get(fr) or {}).get("text") if fr else None
            def cv(r):
                return r.split(".", 1)[1].replace(".", ":")

            def rng(a, b):
                ca, cb = cv(a), cv(b)
                if ca.split(":")[0] == cb.split(":")[0]:
                    return f'{ca}–{cb.split(":")[1]}'
                return f"{ca}–{cb}"
            # performed or commanded, and who to whom where the text says —
            # "speech turn · commanded · Moses → ?"
            sid = next((e.get("dst") for e in mem
                        if e.get("type") == "sender"), None)
            aid = next((e.get("dst") for e in mem
                        if e.get("type") == "addressee"), None)
            who_ = ""
            if sid or aid:
                who_ = (f' · {(everything.get(sid) or {}).get("text") or "?"}'
                        f' → {(everything.get(aid) or {}).get("text") or "?"}')
            what = f'speech turn · {n.get("mode") or "performed"}{who_}'
            if len(span) > 1:
                heb = rng(span[0], span[-1])
                bsb = rng(moved.get(span[0], span[0]),
                          moved.get(span[-1], span[-1]))
                # in the reader the Berean numbering alone (the Hebrew is
                # shown with the original text); on the working pages, both
                what += (f" · {bsb}" if show_ref else
                         f" · BSB {bsb} (Hebrew {heb})" if bsb != heb
                         else f" · {heb}")
            more = hidden.get(n["id"])
            lines.append(f'  {ids[n["id"]]}{{{{"{what}'
                         + (f'<br/>said in: {esc(said)}' if said else "")
                         + (f'<br/><i>+{more} parts in other verses</i>'
                            if more else "")
                         + '"}}')
        elif n.get("kind") == "address":
            sid = next((e.get("dst") for e in all_edges
                        if e.get("src") == n["id"]
                        and e.get("type") == "sender"), None)
            frm = (everything.get(sid) or {}).get("text") if sid else None
            more = hidden.get(n["id"])
            lines.append(f'  {ids[n["id"]]}{{{{"address · to you'
                         + (f' · from {esc(frm)}' if frm else "")
                         + '<br/>the writer turns to speak TO someone;'
                           '<br/>who, the text leaves to context'
                         + (f'<br/><i>+{more} in other verses</i>'
                            if more else "")
                         + '"}}')
        elif n.get("kind") == "writing":
            # THE WRITING SAYS WHAT IT IS AND WHO IT IS FROM — the heading's
            # own claim, which every node of the psalm sits inside
            sid = next((e.get("dst") for e in all_edges
                        if e.get("src") == n["id"]
                        and e.get("type") == "sender"), None)
            frm = (everything.get(sid) or {}).get("text") if sid else None
            more = hidden.get(n["id"])
            lines.append(f'  {ids[n["id"]]}{{{{"writing · {esc(n.get("text"))}'
                         + (f'<br/>from {esc(frm)}, as its heading states'
                            if frm else '<br/>no writer named')
                         + (f'<br/><i>+{more} parts in other verses</i>'
                            if more else "")
                         + '"}}')
        elif n.get("kind") == "concession":
            # THE OBSTACLE, WHAT HOLDS ANYWAY, AND WHAT IS DENIED.
            # 2026-09-26: an obstacle overcome, an overridden motivation.
            # The denied response is the text's own negated verb.
            den = n.get("denied")
            lines.append(f'  {ids[n["id"]]}{{{{"concession'
                         + (f' · denied: {esc(den)}' if den else "")
                         + '<br/>even though ... still'
                         + ('<br/>the response it would bring is named '
                            'and denied' if den else "")
                         + '"}}')
        elif n.get("kind") == "acts":
            # ACTS OF ONE AGENT names its agent: the group's subject is the
            # claim (2026-09-26: a collection of 4 actions of the Lord
            # with a single subject)
            aid = next((e.get("dst") for e in all_edges
                        if e.get("src") == n["id"] and e.get("type") == "s"),
                       None)
            who = (everything.get(aid) or {}).get("text") if aid else None
            more = hidden.get(n["id"])
            lines.append(f'  {ids[n["id"]]}{{{{"acts of one agent'
                         + (f' · {esc(who)}' if who else "")
                         + '<br/>in a row, joined by no word;<br/>every '
                           'subject is the same one'
                         + (f'<br/><i>+{more} acts in other verses</i>'
                            if more else "")
                         + '"}}')
        else:
            lines.append(f'  {ids[n["id"]]}{{{{"{esc(n.get("kind"))} · '
                         f'ordered<br/>{esc(n.get("evidence"))}"}}}}')
        if click:
            lines.append(f'  click {ids[n["id"]]} call {click}("{n["id"]}")')
        if first_ref(n["id"]) != ref:
            lines.append(f"  style {ids[n['id']]} stroke-dasharray:2 3,"
                         f"fill:none,opacity:.85")
    # CONTENT NODES ARE DRAWABLE TOO, and forgetting to register them is
    # what dropped their parts: `s` was resolved from `ids`, which held only
    # clauses and pairs, so every `ct0 --v--> ...` edge fell out at the first
    # guard. The content box appeared with nothing hanging off it.
    for n in nodes.values():
        if n.get("content"):
            # by LOCAL, not order: a causative's inner content (ct0c) shares
            # its clause's order with the outer one (ct0)
            ids[n["id"]] = n.get("local") or f"ct{n.get('order', 0)}"

    def ghost(far_id):
        """A clause in ANOTHER verse, drawn with a dotted border and — on a
        passage page — clickable through to the same node in its own verse's
        diagram. 2026-09-25: in the diagram in v8.2, add a node
        with a dotted border that references the node in the diagram for
        v8.1."""
        if far_id in ids:
            return ids[far_id]
        # a node outside what was loaded (the reader loads a chapter, and a
        # link may reach past it) is still a reference, drawn by its id
        far = everything.get(far_id) or {"ref": far_id.split("#")[0],
                                         "text": far_id.split("#")[-1]}
        gid = f"g{len(ids)}"
        ids[far_id] = gid
        # the reader shows verse references in the BERean numbering (2026-09-25: the BSB
        # verse references are primary); it passes
        # `show_ref` to map a graph reference for display
        shown = show_ref(far["ref"]) if show_ref else far["ref"]
        vref = shown.split(".", 1)[1].replace(".", ":")
        # BOTH where they differ (the structure shows either both
        # or neither) — the Berean first, the Hebrew beside it
        if show_ref and shown != far["ref"]:
            vref += f' (Heb {far["ref"].split(".", 1)[1].replace(".", ":")})'
        what = (f'{far.get("kind")}: {far.get("text")}' if far.get("pair")
                else far.get("text"))
        lines.append(f'  {gid}(["↗ {esc(vref)} · {esc(what)[:70]}"])')
        lines.append(f"  style {gid} stroke-dasharray:2 3,stroke-width:1.5px,"
                     f"fill:none,opacity:.85")
        if click:
            lines.append(f'  click {gid} call {click}("{far_id}")')
        elif jump and far.get("pair"):
            # a grouping has no stable position in its verse's diagram, so a
            # ghost of one goes to the verse
            lines.append(f'  click {gid} call goVerse("{far["ref"]}")')
        elif jump:
            lines.append(f'  click {gid} call {jump}("{far["ref"]}", '
                         f'{far.get("order", 0)})')
        return gid

    parts_total = collections.Counter(
        e.get("src") for e in all_edges if e.get("type") == "part")
    possessor_of = {e.get("src"): e.get("dst") for e in all_edges
                    if e.get("type") == "possessor"}
    # WHO a pronoun is, where the graph resolved it (one agreeing candidate)
    refers_of = {e.get("src"): e.get("dst") for e in all_edges
                 if e.get("type") == "refers_to"}
    # the BSB's readings (S6, their own layer) are labelled as the
    # translators', not as the graph's inference
    by_bsb = {e.get("src") for e in all_edges
              if e.get("type") == "refers_to" and e.get("reading") == "BSB"}
    # the structure sweep's readings (their own layer, plan 1.34), in the
    # site's words for model output
    by_sweep = {e.get("src") for e in all_edges
                if e.get("type") == "refers_to" and e.get("reading") == "sweep"}

    def is_label(src):
        return ("is · BSB reading" if src in by_bsb else
                "is · automated analysis" if src in by_sweep else "is · inferred")

    members_of = collections.defaultdict(list)
    for e in all_edges:
        if e.get("type") == "member" and (everything.get(e.get("src")) or {}).get("kind") == "together":
            members_of[e["src"]].append(e.get("dst"))
    # a generic that is one of, or some of, a group the text names (plan 1.41)
    one_of = {e.get("src"): e.get("dst") for e in all_edges if e.get("type") == "partitive"}

    def ref_text(x, depth=0):
        """What a referent is called. A group the sweep made of several
        referents is named by its members' words ("Jesus and the twelve
        disciples"): its stored text was their local ids, and Matthew 20:18's
        "we" read "w1 and generic:the-twelve-disciples" (2026-10-18). A
        generic the generic check found the same as the text's own word says
        which word, and where ("the twelve disciples = "the Twelve", 20:17";
        plan 1.41)."""
        n = everything.get(x) or {}
        if n.get("kind") == "together" and members_of.get(x) and depth < 2:
            return " and ".join(ref_text(m, depth + 1) for m in members_of[x])
        t = n.get("text") or x.split("#")[-1]
        if n.get("kind") == "generic" and depth < 2 and (refers_of.get(x) or one_of.get(x)):
            w = refers_of.get(x) or one_of[x]
            wt = (everything.get(w) or {}).get("text")
            if wt:
                b, c, v = (w.split("#")[0].split(".") + ["", "", ""])[:3]
                t += (f" = “{wt}”, {c}:{v}" if refers_of.get(x)
                      else f", one of “{wt}”, {c}:{v}")
        return t

    def owner(mid_, rid_):
        """A drawn referent's own owner, one step on: "your" → soul →
        whose → the psalmist (Psa 103:3; better if it resolved
        to the psalmist's soul)."""
        o_ = possessor_of.get(rid_)
        if not o_:
            return
        ow = f"ow{len(lines)}"
        otxt = (everything.get(o_) or {}).get("text") or o_.split("#")[-1]
        lines.append(f'    {ow}(["{esc(otxt)}"])')
        lines.append(f"    style {ow} stroke-dasharray:2 3")
        lines.append(f'    {mid_} -.->|"whose · inferred"| {ow}')
    word_mid = {}              # word node id -> its mermaid id, once drawn
    mention = {}               # (word node id, clause order) -> mermaid id
    whose_heads = {e.get("src") for e in all_edges
                   if e.get("type") == "qualifier" and e.get("rel") == "whose"}
    has_verb = {e.get("src") for e in all_edges
                if e.get("type") == "v" and e.get("clause_role")}
    seen = {}
    for e in edges:
        s, d = ids.get(e.get("src")), e.get("dst")
        if not s or not d:
            continue

        if e.get("type") == "causes" and nodes.get(d):
            # THE CAUSED EVENT, as its own content: "he makes [me lie down in
            # green pastures]" (Psa 23:2)
            inner = nodes[d]
            lines.append(f'    {ids[d]}["<b>effect</b><br/>'
                         f'{esc(inner.get("key"))}"]')
            lines.append(f"    style {ids[d]} stroke-dasharray:4 2")
            lines.append(f'  {s} ==>|"causes · effect"| {ids[d]}')
            if click:
                lines.append(f'  click {ids[d]} call {click}("{e["src"]}")')

        elif e.get("type") == "asserts" and nodes.get(d):
            # THE CONTENT SHOWS ITS KEY, NOT THE CLAUSE'S WORDS AGAIN. It was
            # given the same `text` as its clause, so the diagram drew
            # "give.thanks to Yahweh" twice side by side and the second box
            # said nothing. A content's identity is its KEY — `v=יָדָה
            # pp:לְ=lord` — which recurs across the corpus in 38% of cases and
            # is the only reason the node exists.
            ct = nodes[d]
            lines.append(f'    {ids[d]}["{esc(ct.get("key") or ct.get("text"))}"]')
            if click:
                # a content says what its clause says: same stretch of text
                lines.append(f'  click {ids[d]} call {click}("{e["src"]}")')
            force = e.get("force")
            lines.append(f'  {s} -->|"asserts'
                         + (f' · {esc(gloss_mood(force))}'
                            if force and force != "-" else "")
                         + f'"| {ids[d]}')

        elif e.get("clause_role"):
            # A MERMAID ID CANNOT HOLD `.` OR `#`, and a node id here is
            # `Psa.107.1#lord`. Numbered instead, with the pair remembered so
            # a part shared by two clauses is drawn once.
            key = (s, d)
            if key not in seen:
                seen[key] = f"w{len(seen)}"
                tgt = nodes.get(d) or {}
                txt = word_label(tgt, d.split("#")[-1])
                if tgt.get("verb") and tgt.get("mood"):
                    txt += f'<br/>{gloss_mood(tgt["mood"])}'
                lines.append(f'    {seen[key]}["{esc(txt)}"]')
                if click:
                    lines.append(f'  click {seen[key]} call {click}("{d}")')
                word_mid[d] = seen[key]
                # the MENTION: this word as the clause at `order` uses it, so
                # its qualifiers are only the ones read in that clause
                mention[(d, (nodes.get(e.get("src")) or {}).get("order"))] = \
                    seen[key]
                # WHOSE: "my shepherd" is DAVID's shepherd (Psa 23:1) — the
                # possessor hangs off the noun, dotted, since it is inferred
                pos_ = possessor_of.get(d)
                # a noun with a "whose" suffix has its possessor drawn off the
                # SUFFIX ("their → is · inferred → magicians"), below — one
                # chain, not two arrows saying the same thing
                if pos_ and d not in whose_heads:
                    pw = f"po{len(seen)}"
                    ptxt = (everything.get(pos_) or {}).get("text") or \
                        pos_.split("#")[-1]
                    lines.append(f'    {pw}(["{esc(ptxt)}"])')
                    lines.append(f"    style {pw} stroke-dasharray:2 3")
                    lines.append(f'    {seen[key]} -.->|"whose · inferred"| '
                                 f'{pw}')
                # A COLLECTION SHOWS ITS MEMBERS. 2026-09-25, on Exo
                # 8:13: livestock was missing and should be in a collection
                # with humans. The role now points at the collection; its
                # members hang under it, as a phrase's qualifiers do.
                if tgt.get("composite"):
                    for me in all_edges:
                        if me.get("type") != "member" or \
                                me.get("src") != d:
                            continue
                        mm = me.get("dst")
                        if mm in word_mid:
                            continue
                        word_mid[mm] = f"mb{len(word_mid)}"
                        mtxt = word_label(everything.get(mm) or
                                          nodes.get(mm), mm.split("#")[-1])
                        lines.append(f'    {word_mid[mm]}["{esc(mtxt)}"]')
                        lines.append(f'    {seen[key]} -->|"member"| '
                                     f'{word_mid[mm]}')
                        # a member carries its own qualifiers: "slow OF
                        # ANGER and great OF COVENANT LOYALTY" (Psa 103:8,
                        # 2026-09-27: why not have a node for
                        # anger)
                        mention[(mm, (nodes.get(e.get("src")) or {})
                                 .get("order"))] = word_mid[mm]
                        if click:
                            lines.append(f'  click {word_mid[mm]} call '
                                         f'{click}("{mm}")')
                # WHO: "he makes me lie down" — the "he" is the LORD of 23:1,
                # the only agreeing referent in the leading text. Built, so
                # drawn like the possessor; it was a dashed "he = LORD?"
                # preview until the unique-candidate rule was written.
                ref_ = refers_of.get(d)
                if ref_:
                    rw = f"rf{len(seen)}"
                    rtxt = ref_text(ref_)
                    lines.append(f'    {rw}(["{esc(rtxt)}"])')
                    lines.append(f"    style {rw} stroke-dasharray:2 3")
                    lines.append(f'    {seen[key]} -.->|"{is_label(d)}"| '
                                 f'{rw}')
                    owner(rw, ref_)
            # THE PREPOSITION IS THE RELATION, so it is on the label rather
            # than left as a bare `pp`. "give thanks TO the LORD" and "stood
            # BEFORE the LORD" are the same role and not the same claim.
            lbl = ROLE.get(e["type"], e["type"])
            # A VERBLESS CLAUSE'S PREDICATE IS "IS". 2026-09-25, on BSB
            # 8:19 "[is] the finger of God it": should there be a verb of
            # is? Hebrew states X-is-Y by putting them side by side: there
            # is no verb, so no verb node — but the predicate link says the
            # "is" the construction carries, and that it is not a word.
            if e["type"] == "p" and e.get("src") not in has_verb:
                lbl = "is · no verb in Hebrew"
            # A GAPPED VERB, CARRIED: "and all within me [bless] his holy
            # name" (Psa 103:1) — the verb is the line before's
            if e["type"] == "v" and e.get("inferred"):
                lbl = "verb · carried from the line before"
            if e.get("prep_gloss"):
                lbl = f'{lbl}: {e["prep_gloss"]}'
            lines.append(f'    {s} -->|"{esc(lbl)}"| {seen[key]}')

        elif e.get("clause_link") and not ids.get(d) and \
                ((everything.get(d) or {}).get("clause")
                 or (everything.get(d) or {}).get("pair")):
            # A MEMBER IN ANOTHER VERSE: drawn as a ghost, not dropped.
            ghost(d)
            order = e.get("order")
            t_ = LINK_SHOWN.get(e["type"], e["type"])
            lbl = (f'{order} · {t_}' if order else t_)
            lines.append(f'  {s} ==>|"{esc(lbl)}"| {ids[d]}')

        elif e.get("clause_link") and ids.get(d):
            order = e.get("order")
            t_ = LINK_SHOWN.get(e["type"], e["type"])
            lbl = (f'{order} · {t_}' if order else t_)
            if e["type"] == "part" and \
                    (e.get("src") or "").endswith("#writing"):
                # A PSALM IS A SEQUENCED COLLECTION OF ASSERTIONS.
                # 2026-09-25: a psalm is a sequenced collection
                # of assertions by the psalmist. Each verse shows where its
                # own assertions fall in the psalm's order.
                lbl = f"assertion {order} of {parts_total[e['src']]}"
            if e["type"] == "within":
                # the role the inner clause fills: "you refuse [to let them
                # go]" is inside as the prepositional object of refusing
                lbl = "inside · " + ROLE.get(e.get("role"), e.get("role") or "")
                if e.get("prep_gloss"):
                    lbl += f': {e["prep_gloss"]}'
            arrow = "==>" if order else "-->"
            lines.append(f'  {s} {arrow}|"{esc(lbl)}"| {ids[d]}')
    # QUALIFIERS hang off the head they qualify — "pastures -of-> grass"
    # (Psa 23:2) — drawn from each head already on the page, recursively, so
    # a phrase unfolds from the word the clause points at
    qual = collections.defaultdict(list)
    for e in edges:
        # a preposition made the predicate carries its object the same way
        # a head carries its qualifier: "with → me" (Psa 23:4)
        if e.get("type") in ("qualifier", "prep_object"):
            qual[e["src"]].append(e)
    # Per MENTION: a word two clauses of the verse share ("the dust of the
    # earth", Exo 8:13, struck in one clause and becoming gnats in the next)
    # carries each clause's qualifiers only under that clause's drawing of it.
    # An edge without `clause_order` (built before 2026-09-25) goes anywhere.
    # A qualifier is drawn once PER HEAD, too: "all the dust" and "all the
    # land" in one clause are two words "all" that share a node id (ids are
    # per word text within a verse until plan 2.5 re-keys them by span).
    todo = [(h, k, key) for key, (h, k) in
            ((key, key) for key in list(mention))]
    drawn_ref = set()
    guard = 0
    while todo and guard < 500:                         # circuit breaker
        guard += 1
        h, k, hkey = todo.pop()
        for e in qual.get(h, []):
            ck = e.get("clause_order")
            if ck is not None and k is not None and ck != k:
                continue
            d = e.get("dst")
            dkey = (d, k, hkey)
            if dkey not in mention:
                mention[dkey] = f"qd{len(mention) + len(word_mid)}"
                lines.append(f'    {mention[dkey]}["'
                             f'{esc(word_label(nodes.get(d), d))}"]')
                if click:
                    lines.append(f'  click {mention[dkey]} call '
                                 f'{click}("{d}")')
                todo.append((d, k, dkey))
            lbl = "object" if e.get("type") == "prep_object" else \
                (e.get("rel") or "qualifier")
            if e.get("prep_gloss"):
                lbl += f": {e['prep_gloss']}"
            lines.append(f'    {mention[hkey]} -->|"{esc(lbl)}"| '
                         f'{mention[dkey]}')
            # WHO a pronoun under a phrase is ("with ME" → the psalmist). A
            # "whose" suffix's owner is drawn just below from its head's
            # possessor — and where the head has none, from the suffix's own
            # resolution: Psa 23:5 "before ME" (לְפָנַי, "before my face").
            # 2026-09-26: 'me' should resolve to the psalmist — it
            # did in the graph; the diagram did not show it.
            if refers_of.get(d) and dkey not in drawn_ref and not (
                    e.get("rel") == "whose" and possessor_of.get(h)):
                drawn_ref.add(dkey)
                rw = f"rq{len(mention)}{len(lines)}"
                rtxt = ref_text(refers_of[d])
                lines.append(f'    {rw}(["{esc(rtxt)}"])')
                lines.append(f"    style {rw} stroke-dasharray:2 3")
                lines.append(f'    {mention[dkey]} -.->|"{is_label(d)}"| {rw}')
                owner(rw, refers_of[d])
            # WHOSE, resolved: the suffix is who the text means — "their"
            # secret arts are the magicians' (the clause's own subject)
            if e.get("rel") == "whose" and possessor_of.get(h):
                pos_ = possessor_of[h]
                pw = f"pw{len(mention)}{len(lines)}"
                ptxt = (everything.get(pos_) or {}).get("text") or \
                    pos_.split("#")[-1]
                lines.append(f'    {pw}(["{esc(ptxt)}"])')
                lines.append(f"    style {pw} stroke-dasharray:2 3")
                lines.append(f'    {mention[dkey]} -.->|"is · inferred"| {pw}')
                owner(pw, pos_)
    # PREVIEWS: relations a proposed kind would add, not in the graph. An end
    # in another verse is a ghost, so the relation is visible from BOTH
    # verses it joins, and one click away from the other end.
    for src, dst, lbl in extra:
        ends = []
        for x in (src, dst):
            if x in ids:
                ends.append(ids[x])
            elif (everything.get(x) or {}).get("clause") or \
                    (everything.get(x) or {}).get("pair"):
                ends.append(ghost(x))
        if len(ends) == 2:
            lines.append(f'  {ends[0]} -.->|"{esc(lbl)} · proposed"| '
                         f'{ends[1]}')
    lines.append("  classDef cl fill:none,stroke:#9a6b2f,color:#9a6b2f;")
    lines.append("  class " + ",".join(ids[n["id"]] for n in cls) + " cl;")
    if pairs:
        lines.append("  classDef pr fill:none,stroke:#2f5d8a,color:#2f5d8a,"
                     "stroke-width:2px;")
        lines.append("  class " + ",".join(ids[n["id"]] for n in pairs) + " pr;")
    return "\n".join(lines)


def mermaid_clauses(ref, ws, clauses):
    """The verse as REIFIED CLAUSES: each one a node, its parts hung off it.

    2026-09-21, drawing the expected shape that could not be found on the
    page: "(God -> issues -> (command node -> be -> light)) -> causes -> …",
    then concretely: start with the command node 'be light', which has tuple
    relationships with the command 'be' and the object 'light'.

    That is a clause treated as a thing rather than as a bundle of edges, and
    it is the step that makes the level above expressible — you cannot say
    *this command caused that event* until the command is a node.

    Everything drawn here is MACULA's: the clause boundaries, the rule, and
    the role of each part. The one thing NOT drawn is a name for the relation
    BETWEEN clauses — `issues`, `causes` — because the source does not state
    it and inventing it would be a reading rather than an extraction. It is
    the dashed `?`, and it is the gap this whole pass is about.
    """
    def esc(s):
        return (str(s or "").replace('"', "'").replace("[", "")
                .replace("]", "").replace("(", "").replace(")", "")
                .replace("|", "/").replace("{", "").replace("}", "").strip())

    def phrase(lo, hi):
        return " ".join((ws[i].get("g") or "") for i in range(lo, hi + 1)
                        if i < len(ws)).strip()

    cls = [c for c in clauses if c.get("cls") == "cl"]
    if not cls:
        return "graph LR\n  none[\"no clauses found\"]"
    lines = ["graph LR"]
    for i, c in enumerate(cls):
        mood = c.get("verb_mood")
        lines.append(f'  c{i}(["{esc(phrase(c["lo"], c["hi"]))}<br/>'
                     + (f'{esc(mood)}' if mood else esc(c.get("rule")))
                     + '"])')
        for j, p in enumerate(c.get("parts") or []):
            role = ROLE.get(p["role"], p["role"])
            lines.append(f'    c{i}p{j}["{esc(phrase(p["lo"], p["hi"]))}"]')
            lines.append(f'    c{i} -->|"{esc(role)}"| c{i}p{j}')
    # THE CAUSE/EFFECT NODE AT THE ROOT. 2026-09-21: the diagram …
    # still did not start with the cause/effect pattern (which can have
    # specializations) as the foundational node.
    #
    # AND IT IS A PAIR, NOT YET A CAUSE. Immediately after: the call
    # that "and" implies cause and effect was an inference; it might start as a
    # simple pair until such relationships can be inferred well.
    #
    # That is right, and the first version of this named it `cause / effect`,
    # which was an inference written down as data. What the source supports is
    # narrower and still worth having: MACULA marks mood, so a JUSSIVE clause
    # is a command and a following WAYYIQTOL OF THE SAME LEMMA repeats it as
    # something that happened — 65 such pairs in the Hebrew Bible,
    # "swear/he.swore", "go/she.went", "let.it.be/it.was". That the second
    # follows FROM the first is an inference on top.
    #
    # So the root is a PAIR carrying its evidence, and its members are `first`
    # and `second` rather than `cause` and `effect`. Typing it — cause and
    # effect, or command and compliance, or any other specialization — is a
    # later layer's job, and it will have this node to attach to.
    speech = {"אָמַר", "דָּבַר", "צָוָה", "קָרָא", "עָנָה", "שָׁאַל"}
    cause = effect = content = None
    for i, c in enumerate(cls):
        if c.get("verb_mood") not in ("jussive", "imperative", "cohortative"):
            continue
        for j in range(i + 1, len(cls)):
            d = cls[j]
            if d.get("verb_mood") == "wayyiqtol" and \
                    d.get("verb_lemma") == c.get("verb_lemma"):
                effect, content = j, i
                # the cause is the SAYING that issued the command, where one
                # precedes it; otherwise the command itself
                cause = next((k for k in range(i) if cls[k].get("verb_lemma")
                              in speech), i)
                break
        if effect is not None:
            break

    if effect is not None:
        lem = cls[content].get("verb_lemma") or ""
        # A PARTICULAR TYPE OF PAIR: ACTION, THEN STATE. 2026-09-21:
        # cause and effect may not be known, but a command->event looking
        # pattern can be seen, simplified to action and then state grouped
        # together: a particular type of pair.
        #
        # That is the right altitude and better than either name tried before
        # it. `cause / effect` claimed a relation the text does not state.
        # Bare `pair` threw away something it does: the FIRST member is a
        # command — MACULA marks it jussive — and the SECOND is the same
        # lemma reported as having happened. Action then state describes what
        # is observable and stops there, and it is a specialization of pair
        # rather than a reading laid over it.
        #
        # NOTE the quadrupled brace: this is an f-string, so `}}}}` is needed
        # to emit the `}}` that closes a Mermaid hexagon. Written as `}}` it
        # produced `root{{"…"}` and Mermaid rejected the whole diagram.
        # ORDERED, AND THE ORDER IS THE CONTENT. 2026-09-21: order
        # does matter with this pattern, so it is more than just a pair.
        #
        # A pair is a set of two and says nothing about which came first.
        # Reverse these and it is not the same thing: a command reported as
        # having happened is a fulfilment, and an act followed by a command to
        # do it is nonsense. So the members carry positions, not just names.
        #
        # This is also what separates it from a COORDINATION. "heaven and
        # earth" is a pair whose order is stylistic and which means the same
        # reversed; this one does not. Both would otherwise be "two clauses
        # under one parent", and collapsing them would lose the distinction.
        #
        # The order is document order, which MACULA gives, so it is read
        # rather than assumed.
        lines.append('  root{{"ordered pair · action then state<br/>'
                     f'jussive then wayyiqtol, same lemma {esc(lem)}"}}}}')
        lines.append(f'  root ==>|"1 · action"| c{cause}')
        lines.append(f'  root ==>|"2 · state"| c{effect}')
        if cause != content:
            lines.append(f'  c{cause} -->|"content"| c{content}')
        lines.append("  classDef root fill:none,stroke:#2f5d8a,"
                     "color:#2f5d8a,stroke-width:2px;")
        lines.append("  class root root;")
    elif len(cls) > 1:
        lines.append('  grp{{"one container<br/>relations unknown"}}')
        for i in range(len(cls)):
            lines.append(f'  grp -. "?" .-> c{i}')
    lines.append("  classDef cl fill:none,stroke:#9a6b2f,color:#9a6b2f;")
    lines.append("  class " + ",".join(f"c{i}" for i in range(len(cls)))
                 + " cl;")
    return "\n".join(lines)


def mermaid(ref, nodes, edges, clauses=(), clause_of=None):
    """The verse as a left-to-right Mermaid graph.

    2026-09-21: show it like a graph, and Mermaid might
    be easiest for a graph going left to right. Right on both counts —
    laying it out by hand fought the crossings, and Mermaid does that work.

    A LOST END gets a dashed red arrow into a `?` node, because the thing
    being looked for is a relation the source binds and we did not. An end
    that is missing BY DESIGN — an intransitive verb has no object, an
    agentless passive no agent — is grey and solid, since that is a correct
    analysis rather than a gap.
    """
    def esc(s):
        """Mermaid is whitespace- and bracket-sensitive inside labels.

        The first version emitted `-. said (intransitive) .->` and
        `n0["there is no one<br/><i>אַיִן</i>"]`, and Mermaid answered with a
        syntax error for the whole diagram. Brackets, quotes and pipes are the
        characters that end a label, so they are replaced rather than escaped,
        and every label is quoted.
        """
        return (str(s or "").replace('"', "'").replace("\n", " ")
                .replace("[", "").replace("]", "").replace("(", "")
                .replace(")", "").replace("|", "/").replace("{", "")
                .replace("}", "").strip())

    clause_of = clause_of or {}
    clauses = list(clauses)

    ids, lines = {}, ["graph LR"]
    # NODES INSIDE THEIR CLAUSE. A clause is a thing the text asserts, and
    # relations hold between clauses as well as inside them — which is the
    # structure that was drawn and the structure a flat edge list cannot show.
    # MACULA's clause boxes are drawn as subgraphs so the two levels are
    # visibly different.
    bucket = {}
    for nid_ in nodes:
        bucket.setdefault(clause_of.get(nid_), []).append(nid_)
    k = 0
    for ci in sorted(bucket, key=lambda x: (x is None, x)):
        members = bucket[ci]
        inside = ci is not None and ci < len(clauses)
        if inside:
            c = clauses[ci]
            lines.append(f'  subgraph cl{ci}["{esc(c.get("rule") or "clause")}"]')
        for nid_ in members:
            n = nodes[nid_]
            ids[nid_] = f"n{k}"
            lem = n.get("lemma") or ""
            lbl = esc(n.get("text") or nid_.split("#")[-1])
            pad = "    " if inside else "  "
            lines.append(f'{pad}n{k}["{lbl}'
                         + (f"<br/>{esc(lem)}" if lem else "") + '"]')
            k += 1
        if inside:
            lines.append("  end")
    ghost = 0
    lost_ids, design_ids = [], []
    for e in edges:
        s, t = e.get("src"), e.get("dst")
        note = [k for k in ("negated", "comparison", "intransitive",
                            "inferred_subject", "unresolved_possessor")
                if e.get(k)]
        lbl = esc(e.get("type") or "")
        if note:
            lbl += " · " + ", ".join(note)
        lost = is_lost(e)
        design = one_ended_by_design(e)
        for end in ("src", "dst"):
            if e.get(end) is None:
                ghost += 1
                gid = f"g{ghost}"
                lines.append(f'  {gid}(("?"))')
                (lost_ids if lost else design_ids).append(gid)
                if end == "src":
                    s = gid
                else:
                    t = gid
        a = ids.get(s, s if str(s).startswith("g") else None)
        b = ids.get(t, t if str(t).startswith("g") else None)
        if not a or not b:
            continue
        arrow = (f'-. "{lbl}" .->' if lost else f'-->|"{lbl}"|')
        lines.append(f"  {a} {arrow} {b}")
    # THE RELATION BETWEEN CLAUSES, WHICH WE DO NOT HAVE. Genesis 1:3 is God
    # said · let there be light · there was light: a speech and its content,
    # then a fulfilment. MACULA gives the three clauses as siblings under one
    # container and nothing more, so the link between them is drawn as an
    # unnamed dashed arrow rather than guessed at. Naming it `issues` and
    # `causes` would be a reading, and a reading is not extraction.
    if len(clauses) > 1:
        present = sorted({c for c in clause_of.values()
                          if c is not None and c < len(clauses)})
        for a, b in zip(present, present[1:]):
            lines.append(f'  cl{a} -. "?" .-> cl{b}')
    if lost_ids:
        lines.append("  classDef lost stroke:#a83232,fill:none,"
                     "color:#a83232,stroke-dasharray:4 3;")
        lines.append("  class " + ",".join(lost_ids) + " lost;")
    if design_ids:
        lines.append("  classDef ok stroke:#a89e90,fill:none,color:#a89e90;")
        lines.append("  class " + ",".join(design_ids) + " ok;")
    return "\n".join(lines)


def verse_block(ref, ws):
    """The verse itself, so a reader can see what the graph is made from."""
    rtl = any("֐" <= c <= "׿" for w in ws for c in (w.get("t") or ""))
    cells = "".join(
        f'<span class="vw"><b>{html.escape(w.get("t") or "")}</b>'
        f'<i>{html.escape(w.get("g") or "")}</i></span>'
        for w in (reversed(ws) if rtl else ws))
    # THROUGH THE VERSIFICATION MAP, like every other lookup of English at a
    # graph reference. Written without it, this panel printed "So Aaron
    # stretched out his hand over the waters of Egypt" under Exodus 8:6 —
    # the very verse mix-up that started this whole thread, reintroduced in
    # the tool built to investigate it. See tools/versify.py.
    eng = ""
    eref = ref
    vp = OUT / "versemap.json"
    if vp.exists():
        try:
            eref = (json.loads(vp.read_text(encoding="utf-8"))
                    .get("moved") or {}).get(ref, ref)
        except (OSError, ValueError):
            pass
    try:
        for line in gzip.open(OUT / "bsb-align.jsonl.gz", "rt",
                              encoding="utf-8"):
            if line.startswith('{"ref"'):
                d = json.loads(line)
                if d.get("ref") == eref:
                    eng = d.get("text") or ""
                    break
    except OSError:
        pass
    if eref != ref:
        eng += f"   (Berean {eref.split('.', 1)[1].replace('.', ':')})"
    return (f'<div class="verse">{cells}</div>'
            + (f'<p class="eng">{html.escape(eng)}</p>' if eng else "")
            + ('<p class="dir">Hebrew reads right to left &#8592;</p>'
               if rtl else ""))


def graph_svg(ref, nodes, edges):
    """The verse AS A GRAPH — nodes, and labelled arrows between them.

    2026-09-21: show it like a graph. Right question to ask
    of it: the constituency diagram shows what MACULA says, but what is being
    checked is what WE built, and that is a graph. Drawn as one, a lost end is
    not a subtle dash — it is an arrow coming out of nowhere.

    Layered left to right by edge direction, so reading across the page
    follows the relation: subject, then what it does, then what it does it to.
    """
    ids = list(nodes)
    lab = {i: (nodes[i].get("text") or i.split("#")[-1]) for i in ids}
    lem = {i: (nodes[i].get("lemma") or "") for i in ids}

    real = [(e.get("src"), e.get("dst"), e) for e in edges]
    # phantom targets for the ends that are missing, so an arrow still has
    # somewhere to land and the gap is visible rather than silent
    ghosts = {}
    pairs = []
    for s, t, e in real:
        if not s:
            s = ghosts.setdefault(("s", id(e)), f"?src{len(ghosts)}")
        if not t:
            t = ghosts.setdefault(("t", id(e)), f"?dst{len(ghosts)}")
        pairs.append((s, t, e))

    allids = ids + sorted(set(ghosts.values()))
    # longest-path layering
    outs = {i: [] for i in allids}
    indeg = {i: 0 for i in allids}
    for s, t, _e in pairs:
        if s in outs and t in indeg:
            outs[s].append(t)
            indeg[t] += 1
    layer = {i: 0 for i in allids}
    for _ in range(len(allids)):
        moved = False
        for s, t, _e in pairs:
            if s in layer and t in layer and layer[t] < layer[s] + 1:
                layer[t] = layer[s] + 1
                moved = True
        if not moved:
            break
    cols = {}
    for i in allids:
        cols.setdefault(layer[i], []).append(i)

    CW, RH = 250, 92
    width = 60 + (max(cols) + 1) * CW
    height = 70 + max(len(v) for v in cols.values()) * RH
    pos = {}
    for c, members in cols.items():
        for k, i in enumerate(sorted(members)):
            pos[i] = (40 + c * CW + 84, 56 + k * RH)

    o = [f'<svg viewBox="0 0 {width} {height}" width="{width}" '
         f'height="{height}" xmlns="http://www.w3.org/2000/svg" '
         f'font-family="ui-sans-serif,system-ui,sans-serif">',
         '<defs>'
         '<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" '
         'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
         '<path d="M0,0 L10,5 L0,10 z" fill="var(--blue)"/></marker>'
         '<marker id="r" viewBox="0 0 10 10" refX="9" refY="5" '
         'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
         '<path d="M0,0 L10,5 L0,10 z" fill="var(--red)"/></marker>'
         '</defs>']

    for s, t, e in pairs:
        if s not in pos or t not in pos:
            continue
        lost = is_lost(e)
        col = "var(--red)" if lost else ("var(--muted)"
                                         if one_ended_by_design(e)
                                         else "var(--blue)")
        mk = "r" if lost else "a"
        x1, y1 = pos[s]
        x2, y2 = pos[t]
        dx = max(abs(x2 - x1) * 0.45, 40)
        o.append(f'<path d="M {x1+74} {y1} C {x1+74+dx} {y1} '
                 f'{x2-74-dx} {y2} {x2-74} {y2}" fill="none" '
                 f'stroke="{col}" stroke-width="1.6" '
                 f'marker-end="url(#{mk})"'
                 + (' stroke-dasharray="5 4"' if lost else '') + '/>')
        note = [k for k in ("negated", "comparison", "intransitive",
                            "inferred_subject", "unresolved_possessor")
                if e.get(k)]
        txt = (e.get("type") or "") + (f'  ({", ".join(note)})' if note else "")
        o.append(f'<text x="{(x1+x2)/2:.0f}" y="{(y1+y2)/2 - 8:.0f}" '
                 f'text-anchor="middle" font-size="12" fill="{col}">'
                 f'{html.escape(txt)}</text>')

    for i in allids:
        x, y = pos[i]
        ghost = i.startswith("?")
        if ghost:
            o.append(f'<circle cx="{x}" cy="{y}" r="15" fill="none" '
                     f'stroke="var(--red)" stroke-dasharray="4 3"/>')
            o.append(f'<text x="{x}" y="{y+5}" text-anchor="middle" '
                     f'font-size="15" fill="var(--red)">?</text>')
            continue
        o.append(f'<rect x="{x-74}" y="{y-21}" width="148" height="42" '
                 f'rx="7" fill="var(--card)" stroke="var(--line)"/>')
        o.append(f'<text x="{x}" y="{y-3}" text-anchor="middle" '
                 f'font-size="13" fill="var(--ink)">'
                 f'{html.escape(lab[i][:22])}</text>')
        if lem[i]:
            o.append(f'<text x="{x}" y="{y+13}" text-anchor="middle" '
                     f'font-size="12" fill="var(--muted)">'
                     f'{html.escape(lem[i])}</text>')
    o.append("</svg>")
    return "\n".join(o)


def svg(ref, ws, rtl, spans, nrows, arcs):
    W = 132
    pad = 30
    n = len(ws)
    top = nrows * 30 + 46
    base = top + 60
    arch = 34
    height = base + max(len(arcs), 1) * 20 + 80
    width = pad * 2 + n * W

    def x(i):
        j = (n - 1 - i) if rtl else i
        return pad + j * W + W / 2

    # A FIXED WIDTH, SO THE PANEL SCROLLS INSTEAD OF SHRINKING. At 100% the
    # whole diagram was squeezed to the pane and every label became
    # unreadable — which defeats the one thing it is for. 2026-09-21:
    # nested boxes could work as an alternate rendering — they do,
    # once they are large enough to read.
    out = [f'<svg viewBox="0 0 {width} {height}" width="{width}" '
           f'height="{height}" '
           f'xmlns="http://www.w3.org/2000/svg" font-family="ui-sans-serif,'
           f'system-ui,sans-serif">']
    out.append(f'<rect width="{width}" height="{height}" fill="var(--bg)"/>')

    # reading direction
    if rtl:
        out.append(f'<text x="{width-pad}" y="20" text-anchor="end" '
                   f'font-size="13" fill="var(--muted)">'
                   f'Hebrew reads this way &#8592;</text>')

    # constituent boxes
    for s in spans:
        lo, hi = min(x(s["lo"]), x(s["hi"])), max(x(s["lo"]), x(s["hi"]))
        y = 30 + s["row"] * 30
        out.append(f'<rect x="{lo-W/2+8:.0f}" y="{y}" '
                   f'width="{hi-lo+W-16:.0f}" height="22" rx="5" '
                   f'fill="none" stroke="var(--line)"/>')
        lbl = s["rule"] or s["cls"]
        if s["role"]:
            lbl += f'  [{ROLE.get(s["role"], s["role"])}]'
        out.append(f'<text x="{(lo+hi)/2:.0f}" y="{y+15}" '
                   f'text-anchor="middle" font-size="11" '
                   f'fill="var(--ochre)">{html.escape(lbl)}</text>')

    # the words
    for i, w in enumerate(ws):
        cx = x(i)
        out.append(f'<text x="{cx:.0f}" y="{top+16}" text-anchor="middle" '
                   f'font-size="19" fill="var(--ink)">'
                   f'{html.escape(w.get("t") or "")}</text>')
        out.append(f'<text x="{cx:.0f}" y="{top+36}" text-anchor="middle" '
                   f'font-size="12" fill="var(--muted)">'
                   f'{html.escape((w.get("g") or "")[:18])}</text>')
        out.append(f'<text x="{cx:.0f}" y="{top+50}" text-anchor="middle" '
                   f'font-size="10" fill="var(--faint)">'
                   f'{html.escape((w.get("p") or "")[:11])}</text>')

    # our edges, as arcs below
    for k, arc in enumerate(arcs):
        y = base + 14 + k * 20
        colour = "var(--red)" if arc["loose"] else "var(--blue)"
        dash = ' stroke-dasharray="4 3"' if arc["loose"] else ""
        a, b = arc["a"], arc["b"]
        if a is None and b is None:
            continue
        if a is None or b is None:
            here = x(b if a is None else a)
            out.append(f'<line x1="{here-26:.0f}" y1="{y}" '
                       f'x2="{here+26:.0f}" y2="{y}" stroke="{colour}"{dash}/>')
            out.append(f'<circle cx="{here + (26 if a is None else -26):.0f}" '
                       f'cy="{y}" r="4" fill="none" stroke="{colour}"/>')
        else:
            x1, x2 = x(a), x(b)
            mid = (x1 + x2) / 2
            out.append(f'<path d="M {x1:.0f} {y} Q {mid:.0f} {y-arch} '
                       f'{x2:.0f} {y}" fill="none" stroke="{colour}"{dash}/>')
            out.append(f'<circle cx="{x2:.0f}" cy="{y}" r="4" '
                       f'fill="{colour}"/>')
        lbl = arc["type"] + (f'  ({arc["note"]})' if arc["note"] else "")
        anchor = x(a if a is not None else b)
        out.append(f'<text x="{anchor:.0f}" y="{y-6}" text-anchor="middle" '
                   f'font-size="11" fill="{colour}">{html.escape(lbl)}</text>')

    out.append("</svg>")
    return "\n".join(out)


def suite_page():
    """Every verse in the regression suite, newest first.

    2026-09-21: create a visualization that shows the whole suite at
    once in reverse order of when they were taken on.

    Newest first because the most recent verse is the one being argued about,
    and the ones below it are the ground already taken — reading down the page
    is reading backwards through the decisions. `tests/verses.json` keeps
    insertion order, so that order is simply reversed.

    The pass/fail state comes from `tests/test_verse_structure.py` itself
    rather than from a second copy of the checks here, which would drift from
    it inside a day.
    """
    sys.path.insert(0, str(ROOT / "tests"))
    import test_verse_structure as T          # noqa: PLC0415
    spec, per = T.results()
    refs = [k for k in spec if not k.startswith("_")][::-1]
    # WHICH KINDS EACH VERSE BROUGHT INTO THE ONTOLOGY, so reading down the
    # suite is also reading how the ontology was built.
    try:
        onto = json.loads((ROOT / "ontology" / "kinds.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        onto = {"classes": [], "relations": []}
    made = collections.defaultdict(list)
    for item in onto["classes"] + onto["relations"]:
        r = (item.get("established") or {}).get("ref")
        if r:
            made[r].append(item)

    blocks = []
    for ref in refs:
        fails = per.get(ref) or []
        kinds = "".join(
            f'<a class="kind {html.escape(k["status"])}" '
            f'href="/ontology#{html.escape(k["id"])}">'
            f'{html.escape(k["label"])}</a>' for k in made.get(ref, []))
        try:
            ws, _rtl, _sp, _nr, _ar, edges, cls, _cof = build(ref)
            mmd = mermaid_built(ref)
            verse = verse_block(ref, ws)
        except SystemExit:
            mmd, verse, edges = "graph LR\n  x[\"not built\"]", "", []
        badge = (f'<span class="bad">{len(fails)} failing</span>' if fails
                 else '<span class="good">holds</span>')
        detail = ("".join(f"<li>{html.escape(f)}</li>" for f in fails)
                  if fails else "")
        blocks.append(
            f'<section><h2><a href="/tree?ref={html.escape(ref)}">'
            f'{html.escape(ref)}</a> {badge}</h2>'
            # NOT TRUNCATED. The cap was set when these notes were a sentence;
            # they are now the record of why each verse is in the suite,
            # and cutting one mid-word ("could not be drawn or pointed at,
            # an") loses exactly the part that says what was learned.
            f'<p class="why">{html.escape(spec[ref].get("why") or "")}'
            f'</p>'
            + (f'<p class="kinds">made the ontology add: {kinds}</p>'
               if kinds else "")
            + (f'<ul class="fails">{detail}</ul>' if detail else "")
            + f'<div class="wrap"><pre class="mermaid">{html.escape(mmd)}'
              f'</pre></div>{verse}</section>')

    n = len(refs)
    bad = sum(1 for r in refs if per.get(r))
    return f"""<!doctype html><meta charset="utf-8">
<title>Verse suite</title>
<style>
{_CSS}
section{{margin:0 0 44px;padding:0 0 30px;border-bottom:1px solid var(--line)}}
section:last-child{{border-bottom:0}}
h2{{font-size:17px;text-transform:none;letter-spacing:0;color:var(--ink);
margin:0 0 6px}}
h2 a{{color:var(--ink)}}
.why{{color:var(--muted);max-width:76ch;margin:0 0 12px}}
.good{{color:#2f6d3f;font-size:12px;border:1px solid #2f6d3f;border-radius:4px;
padding:1px 6px;margin-left:8px;vertical-align:2px}}
.bad{{color:var(--red);font-size:12px;border:1px solid var(--red);
border-radius:4px;padding:1px 6px;margin-left:8px;vertical-align:2px}}
.fails{{color:var(--red);font-size:13px}}
.kinds{{font-size:13px;color:var(--muted);margin:-4px 0 12px}}
.kind{{display:inline-block;border:1px solid var(--line);border-radius:999px;
padding:0 9px;margin:2px 4px 2px 0;color:var(--ink);text-decoration:none}}
.kind.proposed{{border-style:dashed}}
.kind.withdrawn{{color:var(--faint);text-decoration:line-through}}
</style>
<p style="font-size:13px;margin:0 0 10px"><a href="/ontology">the ontology
these verses built →</a></p>
<h1>Verse suite · {n} verse{'' if n == 1 else 's'}</h1>
<p class="h">{'all hold' if not bad else str(bad) + ' failing'} · newest first,
so the top of the page is the verse being argued about and everything below it
is ground already taken. Each links to its own <code>/tree</code>.</p>
{''.join(blocks)}
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
mermaid.initialize({{startOnLoad:true, theme: dark ? 'dark' : 'neutral',
  flowchart:{{curve:'basis', nodeSpacing:34, rankSpacing:70}}}});
</script>
"""


def page(ref, mmd, verse, tree, loose, total, clausal=""):
    return f"""<!doctype html><meta charset="utf-8">
<title>{html.escape(ref)}</title>
<style>
{_CSS}</style>
<h1>{html.escape(ref)}</h1>
<p class="h">{total - loose} of {total} edges have both ends
{'· <b style="color:var(--red)">' + str(loose) + ' do not</b>' if loose else ''}
</p>
<form method="get" action="/tree">
  <input name="ref" value="{html.escape(ref)}" size="16"
         aria-label="verse reference"> <input type="submit" value="show">
</form>

<h2>The shape, as clauses</h2>
<div class="wrap"><pre class="mermaid">{html.escape(clausal)}</pre></div>
<p class="key">Each clause is a node and its parts hang off it by the role
MACULA gives them — the “be light” node with its verb and its subject, and the
verb’s <b>mood</b>, which is what separates a command from a statement and
which no edge in the graph currently carries.
<br><br>
The root is an <b>ordered pair</b>, and a particular type of one: <b>action,
then state</b>. A jussive followed by a wayyiqtol of the same lemma is a
command reported as having happened — 65 of them in the Hebrew Bible,
<i>swear/he.swore</i>, <i>go/she.went</i>. <b>The order is the content</b>:
reversed, it would be an act followed by a command to do it. That also
separates this from a coordination like “heaven and earth”, which means the
same either way round.
<br><br>
What the name keeps is observable — the first is a command, the second is the
same act as a fact. What it drops is that the second happened <i>because of</i>
the first. Cause and effect is a further specialization, and this node is what
it would attach to.</p>

<h2>What we built</h2>
<div class="wrap"><pre class="mermaid">{html.escape(mmd)}</pre></div>
<p class="key">Arrows are the edges we extracted. <b>Dashed red into a “?” is
an end we lost</b> — a relation with one side. Grey is an end that is
<i>meant</i> to be absent: an intransitive verb has no object, an agentless
passive no agent.</p>

<h2>The verse we are working from</h2>
{verse}

<h2>MACULA's own constituents</h2>
<div class="wrap">{tree}</div>
<p class="key">Boxes are MACULA's word groups with the rule and role it
assigns. This is the source of truth: a relation boxed here and missing above
is one the extraction dropped.</p>

<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
mermaid.initialize({{startOnLoad:true, theme: dark ? 'dark' : 'neutral',
  flowchart:{{curve:'basis', nodeSpacing:34, rankSpacing:70}}}});
</script>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ref")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    ws, rtl, spans, nrows, arcs, edges, cls, cof = build(a.ref)
    loose = sum(1 for e in edges if is_lost(e))
    nodes, _ = our_graph(a.ref)
    html_page = page(a.ref, mermaid(a.ref, nodes, edges, cls, cof),
                     verse_block(a.ref, ws),
                     svg(a.ref, ws, rtl, spans, nrows, arcs),
                     loose, len(edges),
                     mermaid_built(a.ref))
    dest = pathlib.Path(a.out) if a.out else (
        OUT / f"tree-{a.ref.replace('.', '_')}.html")
    dest.write_text(html_page, encoding="utf-8")
    print(f"{a.ref}: {len(ws)} words, {len(spans)} constituents, "
          f"{len(edges)} edges, {loose} with a loose end")
    print(f"  -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
