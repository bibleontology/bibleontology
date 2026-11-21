"""Explore's visualizations, generated only from the graph (plan A.53, approved 2026-11-14).

Every view has four parts, printed on the view itself:
  a QUESTION; a GRAPH DEFINITION (which records qualify); an ENCODING (what size, color, position mean, as a key);
  an EVIDENCE TRAIL (every mark opens its records and verses on bibleontology.org).
The renderer may make the data beautiful and adds nothing: each view's dataset (out/viz/<id>.json) holds only graph
records with their verses, and the page is drawn from that file alone. Self-contained HTML + inline SVG, no external
script, so it can be served under the site's strict CSP later.

    python tools/viz/build.py            -> out/viz/<id>.json and out/viz/<id>.html for every view
    python tools/viz/build.py canon      -> one view
"""
import collections
import contextlib
import datetime
import html
import io
import itertools
import json
import math
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
sys.stdout.reconfigure(encoding="utf-8")
OUT = ROOT / "out" / "viz"
SITE = "https://bibleontology.org"
TODAY = datetime.date.today().isoformat()


def load():
    with contextlib.redirect_stdout(io.StringIO()):
        import server as S
        d = S.load()
    return S, d


def vkey(S, d, ref):
    """'1Cor 11:25' or 'Gen.1.3' -> ('Gen', 1, 3) in site codes, or None."""
    if re.match(r"^[1-3]?[A-Za-z]+\.\d+\.\d+$", ref or ""):
        b, c, v = ref.split(".")
        b = S.MACULA_BACK.get(b, b) if b not in S.ORDER else b
        return (b, int(c), int(v)) if b in S.ORDER else None
    sp = S._site_span(d, ref)
    return tuple(sp[:3]) if sp and sp[0] in S.ORDER else None


def vlabel(S, k):
    return f"{S.TITLE.get(k[0], k[0])} {k[1]}:{k[2]}"


# ------------------------------------------------------------------ view 1: the canon, book to book
def canon(S, d):
    """Where does the Bible take up its own words? Book-to-book links, by who made the link."""
    links = collections.defaultdict(list)       # (from_book, to_book, tier) -> [(later verse, earlier verse)]
    why = {}                                     # (later, earlier) -> one line on what joins them
    seen = set()
    for k, rows in S._quote_index(d).items():
        a = vkey(S, d, k)
        for row in rows:
            other, _x, how = row[0], row[1], row[2]
            if how != "quotes":
                continue
            b = vkey(S, d, other)
            if not a or not b or (a, b) in seen:
                continue
            seen.add((a, b))
            links[(a[0], b[0], "editors")].append((a, b))
            why[(a, b)] = "quoted, as the Berean editors' note marks it"
    for line in open(ROOT / "ontology" / "allusions.jsonl", encoding="utf-8"):
        r = json.loads(line)
        a, b = vkey(S, d, r.get("nt")), vkey(S, d, r.get("ot"))
        if not a or not b or (a, b) in seen:
            continue
        tier = {"words_taken_up": "words", "shared_image": "image", "story_echo": "story"}.get(r.get("kind"), "words")
        links[(a[0], b[0], tier)].append((a, b))
        why[(a, b)] = (f"shared words: {r['words']}" if r.get("words") else "") or (r.get("explanation") or "")[:160]
    # STORIES TOLD AGAIN: the graph's same_steps_as relations between events (the site's "Stories told again", 117 on
    # 2026-11-14), each with its steps as verse pairs; the later telling takes up the earlier. The first view read only
    # the 2 story echoes in allusions.jsonl (Doug: "it is odd that there are only 2 stories told again")
    done_pairs = set()
    for eid, rs in d["rels"].items():
        for r in rs:
            if r["type"] != "same_steps_as" or frozenset((eid, r["other"])) in done_pairs:
                continue
            done_pairs.add(frozenset((eid, r["other"])))
            rec = S._told_again(eid, r["other"])
            if not rec:
                continue
            mine = 0 if rec["later_event"] == eid else 1
            for s in rec["beats"]:
                a, b = vkey(S, d, s[mine][0]), vkey(S, d, s[1 - mine][0])
                if a and b and (a, b) not in seen:
                    seen.add((a, b))
                    links[(a[0], b[0], "story")].append((a, b))
                    why[(a, b)] = f"a step of {d['ents'].get(eid, {}).get('name', '')} told again in {d['ents'].get(r['other'], {}).get('name', '')}"
    books = [b for b in S.ORDER]
    data = {
        "id": "canon", "date": TODAY,
        "question": "Where does the Bible take up its own words?",
        "definition": ("Every link from a later passage to an earlier one that the graph holds: quotations the Berean "
                       "editors mark in their notes (above the line), and words, images and story steps the graph "
                       "itself found and judged (below the line)."),
        "encoding": {"position": "the 66 books in canonical order, Genesis at the left",
                     "arc": "one arc per pair of books; its width grows with the number of verse pairs",
                     "color": {"editors": "a quotation the Berean editors mark",
                               "words": "words taken up, found by the graph",
                               "image": "a shared image, found by the graph",
                               "story": "a story told again, found by the graph"}},
        "books": [{"code": b, "name": S.TITLE.get(b, b), "nt": i >= S._NT_FROM} for i, b in enumerate(books)],
        "links": [{"from": f, "to": t, "tier": tier, "n": len(v),
                   "pairs": [[vlabel(S, x), f"{x[0]}.{x[1]}.{x[2]}", vlabel(S, y), f"{y[0]}.{y[1]}.{y[2]}", why.get((x, y), "")]
                             for x, y in sorted(v)]}
                  for (f, t, tier), v in sorted(links.items())],
    }
    data["totals"] = {t: sum(l["n"] for l in data["links"] if l["tier"] == t) for t in ("editors", "words", "image", "story")}
    return data


# ------------------------------------------------------------------ view 2: one person's world
def person(S, d, eid="david"):
    """Who and what does the text connect to David, and how? Every relation of the card, grouped by kind."""
    ents = d["ents"]
    groups = collections.defaultdict(dict)       # category -> other id -> {name, type, labels, refs}
    for r in d["rels"].get(eid, ()):
        o = r["other"]
        if o not in ents or not r.get("refs") or r["type"] in ("speaks_of", "in_theme", "asserted_by"):
            continue
        cat = (d["cats"].get(r["type"]) or {}).get("category") or "other"
        lab = r.get("label_out" if r["dir"] == "out" else "label_in") or r["type"].replace("_", " ")
        g = groups[cat].setdefault(o, {"id": o, "addr": S._addr(o), "name": ents[o].get("name") or o,
                                       "type": ents[o].get("type"), "labels": [], "refs": []})
        if lab not in g["labels"]:
            g["labels"].append(lab)
        g["refs"] += [x for x in r["refs"] if x not in g["refs"]]
    cats = sorted(groups, key=lambda c: -len(groups[c]))
    name = ents[eid].get("name") or eid
    return {
        "id": f"person-{eid}", "date": TODAY, "center": {"id": eid, "addr": S._addr(eid), "name": name},
        "question": f"Who and what does the text connect to {name}, and how?",
        "definition": (f"Every relation the graph holds for {name} that cites a verse, other than word and theme "
                       "index links. Each dot is one person, place, thing or event; held relations are left out."),
        "encoding": {"angle": "relations of one kind sit together in one sector, the largest first",
                     "distance": "nearer the center: more verses cite the link",
                     "size": "the number of verses citing the link",
                     "color": "the kind of thing at the other end"},
        "groups": [{"category": c, "members": sorted(groups[c].values(), key=lambda g: -len(g["refs"]))} for c in cats],
    }


# ------------------------------------------------------------------ view 3: the people, connected
DIVINE = {"god", "the_father", "holy_spirit", "holy_ghost", "spirit_of_the_lord_in_the_hebrew_bible", "spirit_of_god"}
KIN = {"father_of", "mother_of", "sibling_of", "half_sibling_of", "spouse_of", "ancestor_of", "descended_from_person",
       "concubine_of", "adoptive_parent_of", "uncle_of", "cousin_of", "betrothed_to"}


# THE GRAPH, EVERY KIND (Doug, 2026-11-14): people and deities on by default; places, objects, images, concepts,
# events and angels as boxes to turn on. Jesus is both a person and a deity; God, the Father and the Holy Spirit are
# deities. Word and theme index links are left out: they say where a word stands, not what the text says.
KINDS = {"person": "person", "being": "angel", "place": "place", "object": "object", "creature": "object",
         "image": "image", "concept": "concept", "event": "event"}
DEITIES = {"god": ["deity"], "the_father": ["deity"], "holy_spirit": ["deity"], "holy_ghost": ["deity"],
           "jesus": ["person", "deity"]}
SKIP = {"speaks_of", "in_theme", "asserted_by", "spoken_in", "states"}
PER_KIND = {"person": 450, "deity": 4, "angel": 40, "place": 200, "object": 150, "image": 150, "concept": 200,
            "event": 200}
KIND_UI = [("person", "people", "#1f5fbf"), ("deity", "deities", "#c9a000"), ("angel", "angels", "#6a3fb5"),
           ("place", "places", "#2e8b3e"), ("object", "objects", "#8a5a1f"), ("image", "images", "#b8237a"),
           ("concept", "concepts", "#0f8a8a"), ("event", "events", "#c24a00")]


def people(S, d):
    """How is everything in the Bible connected? The most connected of each kind, laid out once together, so the
    page's kind boxes and slider only show and hide."""
    import numpy as np
    ents = d["ents"]

    def kinds(e):
        if e in DEITIES:
            return DEITIES[e]
        k = KINDS.get((ents.get(e) or {}).get("type"))
        return [k] if k else []
    pairs = {}
    for eid, rs in d["rels"].items():
        if not kinds(eid):
            continue
        for r in rs:
            o = r["other"]
            if o == eid or r["type"] in SKIP or not r.get("refs") or not kinds(o):
                continue
            k = tuple(sorted((eid, o)))
            p_ = pairs.setdefault(k, {"kin": False, "labels": set(), "refs": set()})
            p_["kin"] |= r["type"] in KIN
            lab = r.get("label_out" if r["dir"] == "out" else "label_in") or r["type"].replace("_", " ")
            p_["labels"].add(f"{ents[eid].get('name')} {lab} {ents[o].get('name')}")
            p_["refs"].update(r["refs"])
    # WEIGHT IS VERSES, NOT NAMES (Doug, 2026-11-14: "size by verses"): a node's weight is the number of distinct
    # verses its relations cite. Counting linked names made Haman (16, ten of them his sons in one list, Esth 9:7-10)
    # outweigh Esther (7), a genealogy outweighing the book's heroine. Size, the slider's order and the pool use it.
    deg = collections.Counter()
    verses = collections.defaultdict(set)
    for (x, y), v in pairs.items():
        deg[x] += 1
        deg[y] += 1
        verses[x] |= v["refs"]
        verses[y] |= v["refs"]
    w = {e: len(vs) for e, vs in verses.items()}
    keep = set()
    for kd, cap in PER_KIND.items():
        ids = sorted((e for e in deg if kd in kinds(e) and deg[e] >= 2), key=lambda e: -w[e])
        keep |= set(ids[:cap])
    edges = [(x, y, v) for (x, y), v in pairs.items() if x in keep and y in keep]
    nodes = sorted(keep, key=lambda e: -w[e])
    idx = {e: i for i, e in enumerate(nodes)}
    n = len(nodes)
    rng = np.random.default_rng(20261114)
    pos = rng.normal(size=(n, 2))
    E = np.array([(idx[x], idx[y]) for x, y, _ in edges])
    for it in range(300):
        delta = pos[:, None, :] - pos[None, :, :]
        dist2 = (delta ** 2).sum(-1) + 1e-3
        rep = (delta / dist2[..., None] ** 1.5).sum(1) * 0.01
        att = np.zeros_like(pos)
        dv = pos[E[:, 1]] - pos[E[:, 0]]
        np.add.at(att, E[:, 0], dv * 0.04)
        np.add.at(att, E[:, 1], -dv * 0.04)
        step = rep + att - pos * 0.01
        cap = 0.2 * (1 - it / 300) + 0.01
        ln = np.sqrt((step ** 2).sum(-1, keepdims=True)) + 1e-9
        pos += step * np.minimum(1, cap / ln)
    pos -= pos.min(0)
    pos /= pos.max(0)
    return {
        "id": "people", "date": TODAY,
        "question": "How is everything in the Bible connected?",
        "definition": ("The most connected people, deities, angels, places, things, images, concepts and events in the "
                       "graph, and every relation between two of them that cites a verse. Word and theme index links "
                       "are left out. Choose the kinds to show; Jesus is both a person and a deity."),
        "encoding": {"size": "how many verses its relations cite", "color": "its kind",
                     "position": "linked things pull together"},
        "nodes": [{"id": e, "addr": S._addr(e), "name": ents[e].get("name") or e, "deg": deg[e], "w": w[e], "k": kinds(e),
                   "x": round(float(pos[i, 0]), 4), "y": round(float(pos[i, 1]), 4)} for i, e in enumerate(nodes)],
        "edges": [{"a": idx[x], "b": idx[y], "kin": v["kin"], "labels": sorted(v["labels"])[:4],
                   "refs": sorted(v["refs"])[:12]} for x, y, v in edges],
        "totals": {"nodes": n, "links": len(edges)},
    }


def render_people(data):
    """Drawn in the page from DATA: a slider for how many show (the most connected first) and a type filter
    (people, beings); Jesus shows whenever either is on; a name label follows the cursor (Doug, 2026-11-14)."""
    W, H = 1100, 900
    svg = (f'<div class="ctl" style="font:14px system-ui,sans-serif;display:flex;flex-wrap:wrap;gap:8px 22px;align-items:center;margin:4px 0 10px">'
           f'<label>Show the <b id="nlab"></b> most written about <input id="n" type="range" min="25" max="{len(data["nodes"])}" value="{min(150, len(data["nodes"]))}" step="5" style="vertical-align:middle;width:220px"></label>'
           + "".join(f'<label style="color:{c};font-weight:600"><input class="kb" data-k="{k}" type="checkbox"{" checked" if k in ("person", "deity") else ""}> {lab}</label>' for k, lab, c in KIND_UI) +
           f'<label>labels <input id="nl" type="range" min="0" max="120" value="28" step="2" style="vertical-align:middle;width:120px"></label>'
           f'<span id="cnt" style="color:var(--mute)"></span></div>'
           f'<div style="position:relative"><svg id="g" viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(data["question"])}"></svg>'
           f'<div id="tip" style="position:absolute;pointer-events:none;display:none;background:var(--ink);color:var(--bg);font:600 12px system-ui,sans-serif;padding:3px 7px;border-radius:4px;white-space:nowrap"></div></div>')
    key = ('<span><i style="background:var(--a)"></i>a family tie</span><span><i style="background:var(--mute)"></i>any other relation</span>'
           '<span>Larger: more verses about its relations. Positions are fixed, so a dot stays put as you change what shows.</span>')
    script = """
const W=1100,H=900,pad=40,NS='http://www.w3.org/2000/svg';
const g=document.getElementById('g'),P=document.getElementById('panel'),tip=document.getElementById('tip');
const nIn=document.getElementById('n'),nl=document.getElementById('nl'),kbs=[...document.querySelectorAll('.kb')];
const COL={person:'#1f5fbf',deity:'#c9a000',angel:'#6a3fb5',place:'#2e8b3e',object:'#8a5a1f',image:'#b8237a',concept:'#0f8a8a',event:'#c24a00'};
const X=x=>pad+x*(W-2*pad),Y=y=>pad+y*(H-2*pad),mx=Math.max(...DATA.nodes.map(n=>n.w));
const el=(t,a)=>{const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);return e;};
let vis=new Set();
function visible(){const N=+nIn.value,on=new Set(kbs.filter(b=>b.checked).map(b=>b.dataset.k));
  const s=new Set();let c=0;DATA.nodes.forEach((n,i)=>{if(c<N&&n.k.some(k=>on.has(k))){s.add(i);c++;}});return s;}
function draw(){vis=visible();g.textContent='';document.getElementById('nlab').textContent=nIn.value;
  let ne=0;DATA.edges.forEach(e=>{if(!vis.has(e.a)||!vis.has(e.b))return;ne++;const A=DATA.nodes[e.a],B=DATA.nodes[e.b];
    g.appendChild(el('line',{x1:X(A.x),y1:Y(A.y),x2:X(B.x),y2:Y(B.y),stroke:e.kin?'var(--a)':'var(--mute)','stroke-opacity':e.kin?.5:.2,'stroke-width':.8}));});
  const order=[...vis].sort((a,b)=>DATA.nodes[a].w-DATA.nodes[b].w);
  order.forEach(i=>{const n=DATA.nodes[i],r=2.5+12*Math.sqrt(n.w/mx);
    const c=el('circle',{cx:X(n.x),cy:Y(n.y),r:r,fill:COL[n.k[n.k.length-1]],'fill-opacity':.85,class:'hit dot','data-i':i});
    c.addEventListener('mouseenter',ev=>{show(i);});c.addEventListener('mousemove',ev=>{const b=g.parentNode.getBoundingClientRect();
      tip.style.left=(ev.clientX-b.left+12)+'px';tip.style.top=(ev.clientY-b.top-10)+'px';tip.textContent=n.name;tip.style.display='block';});
    c.addEventListener('mouseleave',()=>{tip.style.display='none';});c.addEventListener('click',()=>show(i));g.appendChild(c);});
  const top=[...vis].sort((a,b)=>DATA.nodes[b].w-DATA.nodes[a].w).slice(0,+nl.value);
  top.forEach(i=>{const n=DATA.nodes[i],r=2.5+12*Math.sqrt(n.w/mx);const t=el('text',{x:X(n.x)+r+2,y:Y(n.y)+4,class:'lab',style:'fill:var(--ink);font-weight:600;pointer-events:none'});t.textContent=n.name;g.appendChild(t);});
  document.getElementById('cnt').textContent=vis.size+' shown, '+ne+' links among them';}
function show(i){const n=DATA.nodes[i];const es=DATA.edges.filter(e=>(e.a==i||e.b==i)&&vis.has(e.a)&&vis.has(e.b));
  const nb=new Set(es.flatMap(e=>[e.a,e.b]));g.querySelectorAll('.dot').forEach(d=>d.classList.toggle('dim',!nb.has(+d.dataset.i)&&+d.dataset.i!==i));
  P.innerHTML=`<b><a href="${SITE}/e/${n.addr}" target="_blank">${n.name}</a></b> (${n.k.join(' and ')}): ${n.w} verses, linked to ${n.deg}; ${es.length} shown<ul>`+
  es.slice(0,25).map(e=>`<li>${e.labels.join('; ')}: `+e.refs.slice(0,4).map(r=>`<a href="${SITE}/p/${r}" target="_blank">${r}</a>`).join(', ')+'</li>').join('')+
  (es.length>25?`<li>and ${es.length-25} more</li>`:'')+'</ul>';}
[nIn,nl,...kbs].forEach(x=>x.addEventListener('input',draw));draw();
g.addEventListener('mouseleave',()=>{g.querySelectorAll('.dot').forEach(d=>d.classList.remove('dim'));tip.style.display='none';});
"""
    # A PHONE OPENS ON THE 30 MOST PROMINENT DOTS, near enough to read their names (2026-11-15)
    return page(data, svg, script, key, {"focus": "dots"})


# ------------------------------------------------------------------ view 4: where the great ideas live
# Concept cards whose verse lists hold up (2026-11-14): "repentance" is left out (its card counts every "turn/return",
# 969 verses), and "mercy" (21 verses, far too few): a map drawn from either would teach something false. "Justice"
# too: its card holds no Greek word, so its row would say justice is only an Old Testament idea.
# THE VERSES COME FROM EACH BUILT HUB'S `forms` (out/concept-hubs/<id>.json): its own words in its own sense, both
# Testaments. The first draw used the entity-verses list, which returned 53 verses for forgiveness, all Old Testament,
# where the hub holds 125 with the New Testament's aphiemi and aphesis (2026-11-14).
IDEA_GROUPS = [
    ("positive", ["love", "faith", "grace", "mercy", "salvation", "righteousness", "justice", "holiness", "forgiveness",
                  "redemption", "repentance", "truth", "peace", "hope", "joy", "wisdom", "glory", "power", "blessing",
                  "life", "light"]),
    ("neutral", ["covenant", "law", "sacrifice", "prayer", "judgment", "kingdom", "heart", "blood"]),
    ("negative", [("sin", ["sin", "iniquity", "transgression"]), "evil", "wrath", "death", "idolatry", "pride", "curse",
                  "darkness", "shame", "violence", "hatred"]),
]
PRIOR = 20      # pretend mentions given to every book, spread by each idea's share in the whole Bible


def idea_verses(S, d, cid):
    """A concept's verses: its built hub's own-sense verses where there is a hub (out/concept-hubs/<id>.json,
    `forms`); else the card's verse list. A Testament imbalance is kept: it is part of what the map shows (Doug,
    2026-11-14: "the imbalance actually makes them more interesting")."""
    hubf = ROOT / "out" / "concept-hubs" / f"{cid}.json"
    if hubf.exists():
        forms = json.dumps(json.loads(hubf.read_text(encoding="utf-8")).get("forms"))
        refs = set(re.findall(r'"([1-3]?[A-Z][a-z]{1,4}\.\d+\.\d+)"', forms))
    else:
        with contextlib.redirect_stdout(io.StringIO()):
            ev = S.api_entity_verses(d, {"id": [cid]})
        refs = {it["eref"] for bk in ev.get("books") or [] for it in bk["items"]}
    return {k for k in (vkey(S, d, r) for r in refs) if k}


def ideas(S, d):
    """Where in the Bible does each great idea live? EMPHASIS, not raw density (Doug, 2026-11-14: "3 John
    emphasizes peace more than any other book when it only has one reference in 14 verses"): a book's share of its
    own idea-mentions given to each idea, smoothed toward the whole Bible's shares (PRIOR pretend mentions, so a
    short book needs a real lean to color), divided by that idea's share in the whole Bible. 1 = as the Bible does
    overall; 2 = twice its usual share. Grouped positive, neutral, negative."""
    per_book = collections.Counter(k[0] for k in d["verses"])
    rows = []
    for group, items in IDEA_GROUPS:
        for it in items:
            cid, parts = (it, [it]) if isinstance(it, str) else (it[0], it[1])
            if not all(d["ents"].get(x) for x in parts):
                parts = [x for x in parts if d["ents"].get(x)]
                if not parts:
                    continue
            vs = set()
            for x in parts:
                vs |= idea_verses(S, d, x)
            if not vs:
                continue
            cells = collections.defaultdict(list)
            for k in vs:
                cells[k[0]].append(k)
            name = " & ".join((d["ents"][x].get("name") or x) for x in parts[:2])   # "sin & iniquity": a third name clipped the label
            rows.append({"id": cid, "addr": S._addr(cid), "name": name, "group": group, "total": len(vs),
                         "cells": {bk: {"n": len(v), "verses": [[vlabel(S, k), f"{k[0]}.{k[1]}.{k[2]}"] for k in sorted(v)[:12]]}
                                   for bk, v in cells.items()}})
    total = sum(r["total"] for r in rows)
    share = {r["id"]: r["total"] / total for r in rows}
    for bk in S.ORDER:
        tb = sum(r["cells"].get(bk, {}).get("n", 0) for r in rows)
        for r in rows:
            c = r["cells"].get(bk)
            if c is None:
                continue
            s = (c["n"] + PRIOR * share[r["id"]]) / (tb + PRIOR)
            c["share"] = round(100 * c["n"] / tb, 1) if tb else 0
            c["lift"] = round(s / share[r["id"]], 2)
            c["of"] = tb
    return {
        "id": "ideas", "date": TODAY,
        "question": "Where in the Bible does each great idea live?",
        "definition": (f"For each of {len(rows)} concept cards, grouped positive, neutral and negative, the verses where "
                       "one of the card's own Hebrew or Greek words carries the card's sense. Each cell shows how much "
                       "of a book's attention, among these ideas, goes to this one, against the whole Bible's: smoothed, "
                       "so a short book has to lean clearly before it colors. Imbalance between the Testaments is kept: "
                       "it is part of the picture."),
        "encoding": {"row": "one idea", "column": "the 66 books in order",
                     "shade": "darker: the book gives the idea a larger share of its attention than the Bible does overall"},
        "books": [{"code": bk, "name": S.TITLE.get(bk, bk), "nt": i >= S._NT_FROM, "verses": per_book[bk]}
                  for i, bk in enumerate(S.ORDER)],
        "rows": rows,
    }


def render_ideas(data):
    cw, ch, left, top = 15, 22, 165, 120
    B, R = data["books"], data["rows"]
    gap = 14
    groups = []
    for r in R:
        if not groups or groups[-1] != r["group"]:
            groups.append(r["group"])
    H = top + ch * len(R) + gap * len(groups) + 20
    W = left + cw * len(B) + 20
    cells, heads, rows_l = [], [], []
    for j, b in enumerate(B):
        x = left + j * cw
        heads.append(f'<text class="lab" x="{x + cw / 2:.1f}" y="{top - 6}" transform="rotate(-60 {x + cw / 2:.1f} {top - 6})">{html.escape(b["name"])}</text>')
    nt_x = left + next(j for j, b in enumerate(B) if b["nt"]) * cw
    y, last = top, None
    import math
    for i, r in enumerate(R):
        if r["group"] != last:
            y += gap
            rows_l.append(f'<text x="{left - 8}" y="{y - 2}" text-anchor="end" style="font:600 10px system-ui;letter-spacing:.12em;text-transform:uppercase;fill:var(--mute)">{r["group"]}</text>')
            last = r["group"]
        rows_l.append(f'<text x="{left - 8}" y="{y + ch / 2 + 4:.1f}" text-anchor="end" style="font:600 12px Georgia;fill:var(--ink)">{html.escape(r["name"])}</text>')
        for j, b in enumerate(B):
            c = r["cells"].get(b["code"])
            if not c:
                op = 0.05
            else:
                op = 0.08 + 0.92 * max(0.0, min(1.0, math.log2(max(c["lift"], 0.5)) / 3.0)) if c["lift"] > 1 else 0.10
            cells.append(f'<rect class="hit cell" data-r="{i}" data-b="{b["code"]}" x="{left + j * cw + .5}" y="{y + .5}" '
                         f'width="{cw - 1}" height="{ch - 1}" rx="2" fill="{"var(--d)" if b["nt"] else "var(--b)"}" fill-opacity="{op:.2f}"/>')
        y += ch
    # the book names and the row names in groups of their own, each on the page's color, so the zoom can keep them at
    # the top and the left edge as the map pans (PHONE.sticky, 2026-11-15); the row names over the book names' corner
    svg = (f'<svg id="map" viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(data["question"])}">' + "".join(cells)
           + f'<line x1="{nt_x - .5}" y1="{top - 2}" x2="{nt_x - .5}" y2="{H - 16}" stroke="var(--ink)" stroke-width="1"/>'
           + f'<g id="colhead"><rect x="0" y="0" width="{W}" height="{top - 2}" fill="var(--bg)"/>' + "".join(heads) + '</g>'
           + f'<g id="rowlab"><rect x="0" y="0" width="{left - 2}" height="{H}" fill="var(--bg)"/>' + "".join(rows_l) + '</g></svg>')
    n_ot = next(j for j, b in enumerate(B) if b["nt"])
    # A PHONE OPENS ON A STRETCH OF ABOUT 22 BOOKS, the names pinned at the left, each part of the canon a tap away: a
    # whole Testament at once drew the names at about 6 pixels (the first try, 2026-11-15), 22 books at about 9
    span = 22
    codes = [b["code"] for b in B]

    def box(code):
        j = codes.index(code) if code in codes else 0
        return [left + j * cw - left, 0, left + span * cw + 6, H]
    parts = [["Law & History", "Gen"], ["Poetry & Prophets", "Job"], ["Gospels & Acts", "Matt"], ["Letters", "Rom"]]
    jumps = [[lab, box(code)] for lab, code in parts if code in codes]
    phone = {"vb": jumps[0][1], "jumps": jumps, "sticky": {"left": "rowlab", "top": "colhead"}}
    _ = (n_ot, nt_x)
    key = ('<span><i style="background:var(--b)"></i>Old Testament</span><span><i style="background:var(--d)"></i>New Testament</span>'
           '<span>Darker: the book gives the idea a larger share of its attention than the Bible does overall '
           '(darkest at eight times or more). Pale: no more than usual, or none.</span>')
    script = """
const P=document.getElementById('panel'),cells=[...document.querySelectorAll('.cell')],P0=P.innerHTML;
function show(r,b){const row=DATA.rows[r],c=row.cells[b],bk=DATA.books.find(x=>x.code==b);
cells.forEach(x=>x.classList.toggle('dim',!(x.dataset.r==r||x.dataset.b==b)));
if(!c){P.innerHTML=`<b><a href="${SITE}/e/${row.addr}" target="_blank">${row.name}</a> in ${bk.name}</b>: no verse holds its words.`;return;}
P.innerHTML=`<b><a href="${SITE}/e/${row.addr}" target="_blank">${row.name}</a> in ${bk.name}</b>: ${c.n} verse${c.n>1?'s':''}, `+
`${c.share}% of the ${c.of} mentions of these ideas in ${bk.name}; ${c.lift}× its share in the whole Bible<br>`+
c.verses.map(v=>`<a href="${SITE}/p/${v[1]}" target="_blank">${v[0]}</a>`).join(' · ')+(c.n>c.verses.length?` and ${c.n-c.verses.length} more`:'');}
cells.forEach(x=>{x.addEventListener('mouseenter',()=>show(x.dataset.r,x.dataset.b));x.addEventListener('click',()=>show(x.dataset.r,x.dataset.b));});
document.getElementById('map').addEventListener('mouseleave',()=>{cells.forEach(x=>x.classList.remove('dim'));P.innerHTML=P0;});
"""
    return page(data, svg, script, key, phone)


# ------------------------------------------------------------------ view 5: who says what kind of thing
GROUP_ORDER = ["Performative speech", "Prayer", "Proclamation", "Confrontation", "Set forms of speech"]
GROUP_COLOR = {"Performative speech": "#c9a000", "Prayer": "#1f5fbf", "Proclamation": "#2e8b3e",
               "Confrontation": "#c2342e", "Set forms of speech": "#6a3fb5"}
UNNAMED = {"another speaker", "the narrative", "", None}


VOICE_DEF = {   # what each voice includes, from the rule that assigns it (tools/themes/messages.py: a speaker the
    # original marks, else the book's voice); Doug, 2026-11-14: "definitions or elaborations of what is included"
    "God": "Speech the original text itself attributes to God (MACULA's speaker annotation), in any book.",
    "Jesus": "Speech the original attributes to Jesus, almost all in the Gospels.",
    "Moses": "Speech attributed to Moses; and Deuteronomy, Moses' address, where no other speaker is marked.",
    "an angel": "Speech attributed to an angel or messenger (Hebrew mal'ak, Greek angelos).",
    "a prophet": "Speech attributed to a prophet in the narrative books, named (such as Huldah or Deborah) or not.",
    "an apostle": "Speech attributed to Peter or Paul, in Acts and elsewhere.",
    "a psalmist": "A verse in Psalms with no other speaker marked: the psalm's own voice, praying, praising, lamenting.",
    "the teacher": "Proverbs and Ecclesiastes where no other speaker is marked: the wisdom teacher's voice.",
    "a prophet's oracle": ("A verse in the prophetic books, Isaiah to Malachi with Lamentations and Daniel, where no other "
                           "speaker is marked: the oracle's voice, whether the LORD's words or the prophet's own."),
    "the letter's writer": "A verse in the letters, Romans to Jude, where no other speaker is marked: the letter's writer.",
    "John's vision": "A verse in Revelation where no other speaker is marked: the voice of the vision.",
    "Job's speakers": "Job, his three friends and Elihu: the book's speeches, which this layer does not tell apart.",
    "the Song": "The Song of Songs: its voices, which this layer does not tell apart.",
}


def speech(S, d, top=30):
    """Who in the Bible blesses, curses, prays, commands and accuses? The speech-act layer (out/speech-act-view.json:
    31 kinds in five groups, each instance with its verse and speaker), speakers against kinds (Doug, 2026-11-14:
    "Speech act patterns"; a view for a secular audience: a literary fact about the text, no doctrine)."""
    v = json.loads((ROOT / "out" / "speech-act-view.json").read_text(encoding="utf-8"))
    acts = [a for a in v["acts"].values() if a.get("group_name") in GROUP_ORDER]
    acts.sort(key=lambda a: (GROUP_ORDER.index(a["group_name"]), -int(a.get("count") or 0)))
    flows = collections.defaultdict(list)
    who_n, unnamed = collections.Counter(), 0
    for a in acts:
        for ins in a.get("instances") or []:
            w = ins.get("who")
            if w in UNNAMED:
                unnamed += 1
                continue
            flows[(w, a["id"])].append(ins["v"])
            who_n[w] += 1
    speakers = [w for w, _ in who_n.most_common(top)]
    keep = set(speakers)

    def lab(k):
        kk = vkey(S, d, k)
        return [vlabel(S, kk), f"{kk[0]}.{kk[1]}.{kk[2]}"] if kk else [k, k]
    total = sum(len(x) for x in flows.values())
    return {
        "id": "speech", "date": TODAY,
        "question": "Who in the Bible blesses, curses, prays, commands and accuses?",
        "definition": (f"Every instance the graph's speech-act layer records ({total + unnamed:,}), sorted into 31 kinds of "
                       f"speech in five groups, drawn for each voice the layer names ({len(speakers)}: a person such as Moses, or a "
                       f"voice such as a psalmist or a prophet's oracle). {unnamed:,} instances "
                       "whose speaker is unnamed or is the narrative itself are counted here but not drawn."),
        "encoding": {"left": "a speaker, the most speech at the top", "right": "a kind of speech, by group",
                     "band": "its width: how many times this speaker does this kind of speech"},
        "speakers": [{"name": w, "n": who_n[w], "def": VOICE_DEF.get(w, ""),
                      "books": [[S.TITLE.get(b, b), n] for b, n in collections.Counter(
                          k[0] for (ww, _a), vs in flows.items() if ww == w for k in (vkey(S, d, x) for x in vs) if k).most_common(4)]}
                     for w in speakers],
        "acts": [{"id": a["id"], "name": a["name"], "group": a["group_name"], "def": (a.get("definition") or "")[:160],
                  "n": sum(len(flows.get((w, a["id"]), [])) for w in speakers)} for a in acts],
        "flows": [{"who": w, "act": aid, "n": len(vs), "verses": [lab(x) for x in vs[:30]]}
                  for (w, aid), vs in flows.items() if w in keep],
        "groups": [{"name": g, "color": GROUP_COLOR[g]} for g in GROUP_ORDER],
    }


def render_speech(data):
    # THE PHONE'S OWN DRAWING (2026-11-15): the same voices, kinds and bands at 520 units wide instead of 1,100, the
    # bands shortened, so the names read at about 9 points before any zoom; the page shows one or the other (.v-desk,
    # .v-phone) and the script binds both
    desk = _speech_svg(data, 1100, 230, 820, "v-desk")
    phone = _speech_svg(data, 520, 180, 320, "v-phone")
    return _speech_page(data, desk + phone)


def _speech_svg(data, W, xs, xa, cls):
    top = 40
    S_, A_ = data["speakers"], [a for a in data["acts"] if a["n"]]
    rowA = 21
    rowS = max(26, (len(A_) * rowA + 5 * 14) / len(S_))      # the voices spread over the kinds' full height
    H = top + max(len(S_) * rowS, len(A_) * rowA + 5 * 14) + 30
    sy = {s["name"]: top + i * rowS + rowS / 2 for i, s in enumerate(S_)}
    ay, y, last = {}, top, None
    gcol = {g["name"]: g["color"] for g in data["groups"]}
    heads = []
    for a in A_:
        if a["group"] != last:
            heads.append(f'<text x="{xa + 10}" y="{y + 10}" style="font:600 10px system-ui;letter-spacing:.12em;text-transform:uppercase;fill:{gcol[a["group"]]}">{html.escape(a["group"])}</text>')
            y += 14
            last = a["group"]
        ay[a["id"]] = y + rowA / 2
        y += rowA
    mxs = max(s["n"] for s in S_)
    mxf = max(f["n"] for f in data["flows"])
    bands = []
    A_ids = {a["id"] for a in A_}
    agrp = {a["id"]: a["group"] for a in A_}
    for i, f in enumerate(sorted(data["flows"], key=lambda f: -f["n"])):
        if f["act"] not in A_ids:
            continue
        y1, y2 = sy[f["who"]], ay[f["act"]]
        w = 0.6 + 9 * (f["n"] / mxf) ** 0.6
        bands.append(f'<path class="hit band" data-who="{html.escape(f["who"])}" data-act="{f["act"]}" data-i="{data["flows"].index(f)}" '
                     f'd="M{xs},{y1:.1f} C{(xs + xa) / 2:.1f},{y1:.1f} {(xs + xa) / 2:.1f},{y2:.1f} {xa},{y2:.1f}" fill="none" '
                     f'stroke="{gcol[agrp[f["act"]]]}" stroke-opacity=".45" stroke-width="{w:.1f}"/>')
    labels = []
    for s in S_:
        r = 3 + 6 * (s["n"] / mxs) ** 0.5
        labels.append(f'<g class="hit spk" data-who="{html.escape(s["name"])}"><circle cx="{xs}" cy="{sy[s["name"]]:.1f}" r="{r:.1f}" fill="var(--ink)"/>'
                      f'<text x="{xs - 12}" y="{sy[s["name"]] + 4:.1f}" text-anchor="end" style="font:600 13px Georgia;fill:var(--ink)">{html.escape(s["name"])} <tspan style="font:11px system-ui;fill:var(--mute)">{s["n"]}</tspan></text></g>')
    for a in A_:
        labels.append(f'<g class="hit act" data-act="{a["id"]}"><circle cx="{xa}" cy="{ay[a["id"]]:.1f}" r="4" fill="{gcol[a["group"]]}"/>'
                      # the count flows after the name in one text (2026-11-16: placed by an estimated width it ran into
                      # "Command92" and "Summons44" and stood far off "Confession of faith")
                      f'<a href="{SITE}/e/{a["id"]}" target="_blank"><text x="{xa + 10}" y="{ay[a["id"]] + 4:.1f}" style="font:13px Georgia;fill:var(--ink)">'
                      f'<tspan class="aname" style="text-decoration:underline;text-decoration-color:var(--rule)">{html.escape(a["name"])}</tspan>'
                      f'<tspan style="font:11px system-ui;fill:var(--mute)"> {a["n"]}</tspan></text></a></g>')
    return (f'<svg class="sp {cls}" viewBox="0 0 {W} {H:.0f}" role="img" aria-label="{html.escape(data["question"])}">'
            + "".join(bands) + "".join(heads) + "".join(labels) + "</svg>")


def _speech_page(data, svg):
    key = "".join(f'<span><i style="background:{g["color"]}"></i>{html.escape(g["name"])}</span>' for g in data["groups"]) + \
        '<span>Band width: how many times. Hover a speaker, a kind or a band.</span>'
    svg += ('<details style="font:14px system-ui,sans-serif;margin-top:10px"><summary><b>Who the voices are</b></summary><dl style="margin:8px 0">'
            + "".join(f'<dt style="font-weight:600;margin-top:6px">{html.escape(s["name"])} <span style="color:var(--mute);font-weight:400">{s["n"]}</span></dt>'
                      f'<dd style="margin:0 0 0 14px">{html.escape(s["def"])} <span style="color:var(--mute)">Mostly in '
                      + ", ".join(f"{html.escape(b)} ({n})" for b, n in s["books"]) + '.</span></dd>' for s in data["speakers"])
            + '</dl></details>')
    script = """
const P=document.getElementById('panel'),P0=P.innerHTML,bands=[...document.querySelectorAll('.band')];
const actName=Object.fromEntries(DATA.acts.map(a=>[a.id,a]));
function list(fs,head){P.innerHTML=head+'<ul>'+fs.sort((a,b)=>b.n-a.n).slice(0,12).map(f=>`<li><b>${f.who}</b>, ${actName[f.act].name.toLowerCase()} (${f.n}): `+
 f.verses.slice(0,6).map(v=>`<a href="${SITE}/p/${v[1]}" target="_blank">${v[0]}</a>`).join(', ')+(f.n>6?' …':'')+'</li>').join('')+'</ul>';}
function only(test){bands.forEach(b=>b.classList.toggle('dim',!test(b)));}
document.querySelectorAll('.spk').forEach(g=>g.addEventListener('mouseenter',()=>{const w=g.dataset.who;only(b=>b.dataset.who===w);
 const s=DATA.speakers.find(x=>x.name===w);
 list(DATA.flows.filter(f=>f.who===w),`<b>${w}</b>: ${s.def} <span style="color:var(--mute)">Mostly in ${s.books.map(b=>b[0]+' ('+b[1]+')').join(', ')}.</span>`);}));
document.querySelectorAll('.act').forEach(g=>g.addEventListener('mouseenter',()=>{const a=g.dataset.act;only(b=>b.dataset.act===a);
 list(DATA.flows.filter(f=>f.act===a),`<b>${actName[a].name}</b>: ${actName[a].def}`);}));
bands.forEach(b=>b.addEventListener('mouseenter',()=>{only(x=>x===b);list([DATA.flows[+b.dataset.i]],'');}));
document.querySelectorAll('svg.sp').forEach(s=>s.addEventListener('mouseleave',()=>{bands.forEach(b=>b.classList.remove('dim'));P.innerHTML=P0;}));
"""
    return page(data, svg, script, key)


# ------------------------------------------------------------------ rendering
STYLE = """
:root{--bg:#fbf8f2;--ink:#1d1b17;--mute:#6b645a;--rule:#d9d1c3;--a:#c26a00;--b:#1f5fbf;--c:#2e8b3e;--d:#b8237a;--e:#6a3fb5}
@media (prefers-color-scheme:dark){:root{--bg:#16140f;--ink:#efe9dd;--mute:#a59d90;--rule:#3a352c;--a:#ffa53a;--b:#5aa2ff;--c:#55d16a;--d:#ff5fb4;--e:#b48cff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 Georgia,'Times New Roman',serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 40px}
.kicker{font:600 11px/1 system-ui,sans-serif;letter-spacing:.14em;text-transform:uppercase;color:var(--mute)}
.kicker a.home{color:inherit;text-decoration:underline;text-decoration-color:var(--line,#ccc);text-underline-offset:3px}.kicker a.home:hover{color:var(--ink)}
h1{font-size:30px;line-height:1.15;margin:8px 0 6px}.def{color:var(--mute);max-width:820px;margin:0 0 12px}
.key{display:flex;flex-wrap:wrap;gap:6px 18px;font:13px system-ui,sans-serif;color:var(--mute);margin:8px 0 14px}
.key span i{display:inline-block;width:14px;height:4px;border-radius:2px;margin-right:6px;vertical-align:middle}
svg{width:100%;height:auto;display:block}.panel{border-top:1px solid var(--rule);margin-top:10px;padding-top:10px;font:14px system-ui,sans-serif}
.panel a{color:var(--b)}.panel li{margin:2px 0}.foot{font:12px system-ui,sans-serif;color:var(--mute);margin-top:18px}
.lab{font:11px system-ui,sans-serif;fill:var(--mute)}.hit{cursor:pointer}.dim{opacity:.12}
.zoombar{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 6px;font:13px system-ui,sans-serif}
.zoombar button{font:inherit;min-width:36px;min-height:34px;padding:4px 10px;border:1px solid var(--rule);border-radius:6px;background:var(--bg);color:var(--ink);cursor:pointer}
.zoombar button:hover{border-color:var(--mute)}
svg[viewBox]{touch-action:pan-y}
.v-phone{display:none}
@media (max-width:700px){h1{font-size:24px}.v-desk{display:none}.v-phone{display:block}
 .cn .lab.sparse{display:none}.cn .lab{font-size:24px}#g .lab{font-size:15px}}
"""


def words_html(data):
    """THE FINDINGS IN WORDS, with real links (Doug, 2026-11-14: "can these visual deeplinks be done in such a way
    that they are fully appreciated by search engines?"): search engines and screen readers read text and links, not
    shapes, so each view states its strongest findings as sentences, every one linked to its cards and verses."""
    a = lambda href, t: f'<a href="{SITE}{href}">{html.escape(t)}</a>'   # noqa: E731
    items = []
    vid = data["id"]
    if vid == "canon":
        for l in sorted(data["links"], key=lambda l: -l["n"])[:15]:
            nm = {b["code"]: b["name"] for b in data["books"]}
            p0 = l["pairs"][0]
            items.append(f'{html.escape(nm[l["from"]])} takes up {html.escape(nm[l["to"]])} in {l["n"]} verse pair{"s" * (l["n"] > 1)} '
                         f'({ {"editors": "quotations the Berean editors mark", "words": "words the graph found", "image": "shared images", "story": "a story told again"}[l["tier"]] }), '
                         f'for example {a("/p/" + p0[1], p0[0])} and {a("/p/" + p0[3], p0[2])}.')
    elif vid == "ideas":
        bk = {b["code"]: b["name"] for b in data["books"]}
        for r in data["rows"]:
            top = sorted(((c["lift"], code, c) for code, c in r["cells"].items() if c["n"] >= 2), reverse=True)[:3]
            if top:
                items.append(f'{a("/e/" + r["addr"], r["name"].capitalize())} is most emphasized in '
                             + ", ".join(f'{html.escape(bk[code])} ({lift}× its usual share; {a("/p/" + c["verses"][0][1], c["verses"][0][0])})'
                                         for lift, code, c in top) + ".")
    elif vid == "people":
        for n in data["nodes"][:40]:
            items.append(f'{a("/e/" + n["addr"], n["name"])} ({" and ".join(n["k"])}): {n["w"]} verses in its relations, linked to {n["deg"]} others.')
    elif vid == "speech":
        acts = {x["id"]: x for x in data["acts"]}
        for s in data["speakers"]:
            fl = sorted((f for f in data["flows"] if f["who"] == s["name"]), key=lambda f: -f["n"])[:4]
            items.append(f'<b>{html.escape(s["name"])}</b> ({html.escape(s["def"])}): '
                         + ", ".join(f'{a("/e/" + f["act"], acts[f["act"]]["name"].lower())} {f["n"]} '
                                     f'(as at {a("/p/" + f["verses"][0][1], f["verses"][0][0])})' for f in fl) + ".")
    elif vid == "patterns":
        # THE PHONE'S LIST TOO (A.58: "a phone gets a list"): each pattern, its stages in order, and its stories
        st = {s["id"]: s for s in data["stories"]}
        for f in sorted(data["families"], key=lambda f: -len(f["stories"])):
            stages = " → ".join(("(" + s["name"] + ")") if s["optional"] else s["name"] for s in f["stages"])
            items.append(f'{a("/e/tpl_" + f["id"], f["name"])} ({html.escape(stages)}): '
                         + ", ".join(a("/e/" + sid, st[sid]["title"])
                                     + (" <i>(a reading)</i>" if st[sid]["conj"][st[sid]["fams"].index(f["id"])] else "")
                                     for sid in f["stories"]) + ".")
    if not items:
        return ""
    return ('<section class="words" id="words" style="font:14px/1.55 system-ui,sans-serif;margin-top:22px;border-top:1px solid var(--rule);padding-top:10px">'
            '<h2 style="font:600 17px Georgia;margin:0 0 6px">In words</h2><ul style="margin:0;padding-left:18px">'
            + "".join(f"<li>{x}</li>" for x in items) + "</ul></section>")


# ZOOM AND PAN, EVERY VIEW (Doug, 2026-11-15: "a better solution for mobile users of the 4 new graph views - perhaps
# an ability to drill in and pan"; "Zoom + phone layouts"). Each drawing is 1,100 units wide, a third of its size on a
# phone. One script for all four, working on the drawing's viewBox:
#   - buttons: + and - (around the middle), Reset (the view's own start), and a view's own jumps;
#   - pinch to zoom, drag to pan once zoomed; at full size a drag scrolls the page (touch-action pan-y), so the
#     drawing never traps a reader's thumb;
#   - a tap after a drag is not a tap: the click that ends a pan is swallowed before the pin layer sees it;
#   - `phone`: the view's start on a narrow screen: "vb" (a box) or "focus" ("dots": the 30 largest dots), "jumps"
#     ([label, box]), and "sticky" ({"left": id, "top": id}: a group kept at the view's left or top edge as it pans,
#     the heat map's row and book labels).
ZOOM_JS = """(function(){
const all=[...document.querySelectorAll('.wrap svg[viewBox]')];const sv=all.find(s=>s.getBoundingClientRect().width>0);if(!sv)return;
const base=sv.getAttribute('viewBox').trim().split(/[\\s,]+/).map(Number);let vb=base.slice(),moved=false;
const narrow=matchMedia('(max-width:700px)').matches,PH=(typeof PHONE!=='undefined'&&PHONE)||{};
function sticky(){const st=PH.sticky||{};if(st.left){const g=document.getElementById(st.left);if(g)g.setAttribute('transform',`translate(${vb[0]-base[0]},0)`);}
 if(st.top){const g=document.getElementById(st.top);if(g)g.setAttribute('transform',`translate(0,${vb[1]-base[1]})`);}}
function set(v,keep){let[x,y,w,h]=v;const[bx,by,bw,bh]=base;
 if(w>bw){h=h*bw/w;w=bw;}if(h>bh){w=w*bh/h;h=bh;}const mn=bw/10;if(w<mn){h=h*mn/w;w=mn;}
 x=Math.min(bx+bw-w,Math.max(bx,x));y=Math.min(by+bh-h,Math.max(by,y));vb=[x,y,w,h];
 sv.setAttribute('viewBox',vb.map(n=>+n.toFixed(1)).join(' '));sv.style.touchAction=(w<bw-1||h<bh-1)?'none':'pan-y';sticky();}
function start(){let v=base.slice();
 if(narrow&&PH.vb)v=PH.vb.slice();
 if(narrow&&PH.focus==='dots'){const ds=[...sv.querySelectorAll('circle.dot')].sort((a,b)=>b.r.baseVal.value-a.r.baseVal.value).slice(0,30);
  if(ds.length){let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;ds.forEach(c=>{const cx=c.cx.baseVal.value,cy=c.cy.baseVal.value;x0=Math.min(x0,cx);y0=Math.min(y0,cy);x1=Math.max(x1,cx);y1=Math.max(y1,cy);});
   /* the box around all 30 was two thirds of the drawing (names at 5.5px, 2026-11-15): centered on them, 520 wide */
   let sx=0,sy=0,sw=0;ds.forEach(c=>{const r=c.r.baseVal.value;sx+=c.cx.baseVal.value*r;sy+=c.cy.baseVal.value*r;sw+=r;});
   const w=Math.min(520,x1-x0+120),h=w*1.15;v=[sx/sw-w/2,sy/sw-h/2,w,h];}}
 set(v);}
function zoom(f,cx,cy){const[x,y,w,h]=vb;cx=cx==null?x+w/2:cx;cy=cy==null?y+h/2:cy;set([cx-(cx-x)/f,cy-(cy-y)/f,w/f,h/f]);}
const bar=document.createElement('div');bar.className='zoombar';
const btn=(t,lab,fn)=>{const b=document.createElement('button');b.type='button';b.textContent=t;b.title=lab;b.setAttribute('aria-label',lab);b.onclick=fn;bar.appendChild(b);};
btn('+','Zoom in',()=>zoom(1.6));btn('\\u2212','Zoom out',()=>zoom(1/1.6));btn('Reset','Back to the start',start);
if(narrow)(PH.jumps||[]).forEach(j=>btn(j[0],'Show '+j[0],()=>set(j[1].slice())));
sv.parentNode.insertBefore(bar,sv);
const pts=new Map();let last=null,d0=0;
const toVB=(px,py)=>{const r=sv.getBoundingClientRect();return[vb[0]+(px-r.left)*vb[2]/r.width,vb[1]+(py-r.top)*vb[3]/r.height];};
sv.addEventListener('pointerdown',e=>{pts.set(e.pointerId,[e.clientX,e.clientY]);moved=false;last=[e.clientX,e.clientY];
 if(pts.size===2){const[a,b]=[...pts.values()];d0=Math.hypot(a[0]-b[0],a[1]-b[1]);}});
sv.addEventListener('pointermove',e=>{if(!pts.has(e.pointerId))return;pts.set(e.pointerId,[e.clientX,e.clientY]);
 if(pts.size===2){const[a,b]=[...pts.values()],d=Math.hypot(a[0]-b[0],a[1]-b[1]);if(d0&&Math.abs(d-d0)>2){const c=toVB((a[0]+b[0])/2,(a[1]+b[1])/2);zoom(d/d0,c[0],c[1]);d0=d;moved=true;}return;}
 if(sv.style.touchAction!=='none'||!last)return;const dx=e.clientX-last[0],dy=e.clientY-last[1];
 if(!moved&&Math.hypot(dx,dy)<6)return;moved=true;const r=sv.getBoundingClientRect();
 set([vb[0]-dx*vb[2]/r.width,vb[1]-dy*vb[3]/r.height,vb[2],vb[3]]);last=[e.clientX,e.clientY];});
const up=e=>{pts.delete(e.pointerId);if(pts.size<2)d0=0;if(!pts.size)last=null;};
sv.addEventListener('pointerup',up);sv.addEventListener('pointercancel',up);
window.addEventListener('click',e=>{if(moved&&sv.contains(e.target)){e.stopImmediatePropagation();e.preventDefault();moved=false;}},true);
start();})();"""


def page(data, svg, script, key_html, phone=None):
    url = f"{SITE}/visual/{data['id']}"
    desc = (data["definition"][:155].rsplit(" ", 1)[0] + "…") if len(data["definition"]) > 158 else data["definition"]
    ld = {"@context": "https://schema.org", "@type": "Dataset", "name": data["question"], "description": data["definition"],
          "url": url, "dateModified": data["date"], "isAccessibleForFree": True,
          "license": "https://creativecommons.org/licenses/by/4.0/",
          "creator": {"@type": "Organization", "name": "Bible Ontology", "url": SITE + "/"},
          "isBasedOn": [SITE + "/", "https://github.com/Clear-Bible/macula-hebrew", "https://github.com/Clear-Bible/macula-greek"],
          "keywords": ["Bible", "knowledge graph", "visualization", data["question"]]}
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(data['question'])} · Bible Ontology</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article"><meta property="og:title" content="{html.escape(data['question'])}">
<meta property="og:description" content="{html.escape(desc)}"><meta property="og:url" content="{url}">
<meta property="og:site_name" content="Bible Ontology"><meta name="twitter:card" content="summary">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")}</script>
<style>{STYLE}</style></head><body><div class="wrap">
<div class="kicker"><a class="home" href="/">Bible Ontology</a> · <a class="home" href="/#explore">Explore</a> · generated from the graph</div>
<h1>{html.escape(data['question'])}</h1>
<p class="def">{html.escape(data['definition'])}</p>
{f'<p class="def"><a href="{html.escape(data["post"]["href"])}">{html.escape(data["post"]["text"])}</a></p>' if data.get("post") else ""}
<div class="key">{key_html}</div>
{svg}
<div class="hint" style="font:12px system-ui,sans-serif;color:var(--mute);margin-top:6px">Hover or tap to look; click to hold it while you read below; click an empty spot in the drawing to let go. + and − zoom (or pinch); a zoomed drawing can be dragged. <b id="pinhint" style="display:none;color:var(--ink)">Held.</b></div><div class="panel" id="panel">Tap or hover a mark to see the verses behind it.</div>
{words_html(data)}
<div class="foot">Scope: {html.escape(data['definition'])} Generated {data['date']} from the Bible Ontology graph; every mark
links to its records at bibleontology.org. Structural prominence here is a count of links, not a judgment of
importance.<span class="home-line"> <a class="home" href="/#explore">More views, and the whole graph, in Explore →</a></span></div>
<script>const DATA={json.dumps(data, ensure_ascii=False)};const SITE=(location.origin.startsWith("http")?location.origin:"{SITE}");/* CLICK TO PIN (Doug, 2026-11-14: "the verse references are below but when I cursor down they are gone"): a click on a mark shows it and holds it; while held, hovering and leaving the drawing change nothing; a click on empty space in the drawing lets go and restores the whole view. */let PIN=false;const isMark=e=>e.target&&e.target.closest&&e.target.closest(".hit");const inDraw=e=>e.target&&e.target.closest&&e.target.closest("svg");document.addEventListener("mouseenter",e=>{{if(PIN&&inDraw(e))e.stopImmediatePropagation();}},true);document.addEventListener("mouseleave",e=>{{if(PIN&&e.target&&e.target.tagName==="svg")e.stopImmediatePropagation();}},true);document.addEventListener("click",e=>{{const m=isMark(e);if(m){{PIN=false;m.dispatchEvent(new MouseEvent("mouseenter"));PIN=true;const h=document.getElementById("pinhint");if(h)h.style.display="inline";return;}}const s=inDraw(e);if(s&&PIN){{PIN=false;s.dispatchEvent(new MouseEvent("mouseleave"));const h=document.getElementById("pinhint");if(h)h.style.display="none";}}}},true);const PHONE={json.dumps(phone or {})};{script}
{ZOOM_JS}
/* inside the app (a card), a link opens its card or chapter there instead of a new page */
/* THE WAY BACK (Doug, 2026-11-15: a view shared as a link should lead a new reader to the site as a whole): the kicker and the foot link the site and Explore; inside the app's own frame they would load the site in the frame, so there they are plain text */if(window.parent!==window){{document.querySelectorAll("a.home").forEach(a=>a.replaceWith(a.textContent));const hl=document.querySelector(".home-line");if(hl)hl.remove();}}
if(window.parent!==window)document.addEventListener("click",e=>{{const a=e.target.closest("a");if(!a)return;const m=a.getAttribute("href").match(/\/(e|p)\/([^?#]+)/);if(!m)return;e.preventDefault();parent.postMessage(m[1]==="e"?{{ent:decodeURIComponent(m[2])}}:{{go:m[2]}},location.origin);}});</script>
</div></body></html>"""


def render_canon(data):
    W, H, base = 1100, 560, 300
    n = len(data["books"])
    x = {b["code"]: 40 + i * (W - 80) / (n - 1) for i, b in enumerate(data["books"])}
    color = {"editors": "var(--a)", "words": "var(--b)", "image": "var(--c)", "story": "var(--d)"}
    arcs = []
    for i, l in enumerate(data["links"]):
        x1, x2 = sorted((x[l["from"]], x[l["to"]]))
        # a curve whose height grows with the span but stays inside the drawing (Genesis to Revelation fits)
        h = 30 + 220 * ((x2 - x1) / (W - 80)) ** 0.7
        up = l["tier"] == "editors"
        cy = base - 2 * h if up else base + 2 * h
        w = min(1 + l["n"] ** 0.6, 12)
        arcs.append(f'<path class="hit arc" data-i="{i}" d="M{x1:.1f},{base} Q{(x1 + x2) / 2:.1f},{cy:.1f} {x2:.1f},{base}" '
                    f'fill="none" stroke="{color[l["tier"]]}" stroke-width="{w:.1f}" stroke-opacity=".55"/>')
    ticks = []
    for i, b in enumerate(data["books"]):
        bx = x[b["code"]]
        ticks.append(f'<line x1="{bx:.1f}" y1="{base-3}" x2="{bx:.1f}" y2="{base+3}" stroke="var(--rule)"/>')
        if i % 3 == 0 or b["code"] in ("Matt", "Ps", "Isa", "Rev", "Rom", "Heb"):
            # on a phone the names are drawn larger and every sixth only, with the landmarks (.sparse is hidden there)
            sparse = "" if (i % 6 == 0 or b["code"] in ("Matt", "Ps", "Isa", "Rev", "Rom")) else " sparse"
            ticks.append(f'<text class="lab{sparse}" x="{bx:.1f}" y="{base+16}" text-anchor="middle" transform="rotate(50 {bx:.1f} {base+16})">{html.escape(b["name"])}</text>')
    mx = x["Matt"] - (x["Matt"] - x["Mal"]) / 2
    svg = (f'<svg class="cn" viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(data["question"])}">'
           f'<line x1="30" y1="{base}" x2="{W-30}" y2="{base}" stroke="var(--rule)"/>'
           f'<line x1="{mx:.1f}" y1="{base-260}" x2="{mx:.1f}" y2="{base+250}" stroke="var(--rule)" stroke-dasharray="3 4"/>'
           f'<text class="lab" x="{mx-8:.1f}" y="{base-262}" text-anchor="end">Old Testament</text>'
           f'<text class="lab" x="{mx+8:.1f}" y="{base-262}">New Testament</text>'
           f'<text class="lab" x="34" y="24">Above: links the Berean editors make</text>'
           f'<text class="lab" x="34" y="{H-10}">Below: links the graph found and judged</text>'
           + "".join(arcs) + "".join(ticks) + "</svg>")
    t = data["totals"]
    key = "".join(f'<span><i style="background:{color[k]}"></i>{html.escape(v)} ({t[k]})</span>'
                  for k, v in data["encoding"]["color"].items()) + '<span>Arc width: the number of verse pairs.</span>'
    script = """
const P=document.getElementById('panel'),arcs=[...document.querySelectorAll('.arc')];
const name=c=>DATA.books.find(b=>b.code==c).name;
const tierName={editors:'quoted, by the Berean editors\\' notes',words:'words taken up, found by the graph',image:'a shared image, found by the graph',story:'a story told again, found by the graph'};
function show(i){const l=DATA.links[i];arcs.forEach(a=>a.classList.toggle('dim',a.dataset.i!=i));
P.innerHTML=`<b>${name(l.from)} → ${name(l.to)}</b>: ${l.n} verse pair${l.n>1?'s':''}, ${tierName[l.tier]}<ul>`+
l.pairs.slice(0,40).map(p=>`<li><a href="${SITE}/p/${p[1]}" target="_blank">${p[0]}</a> takes up <a href="${SITE}/p/${p[3]}" target="_blank">${p[2]}</a>${p[4]?` <span style="color:var(--mute)">— ${p[4]}</span>`:''}</li>`).join('')+
(l.pairs.length>40?`<li>and ${l.pairs.length-40} more</li>`:'')+'</ul>';}
arcs.forEach(a=>{a.addEventListener('mouseenter',()=>show(a.dataset.i));a.addEventListener('click',()=>show(a.dataset.i));});
const P0=P.innerHTML;document.querySelector('svg').addEventListener('mouseleave',()=>{arcs.forEach(a=>a.classList.remove('dim'));});
"""
    return page(data, svg, script, key)


def render_person(data):
    W = H = 900
    cx = cy = 450
    pal = ["var(--a)", "var(--b)", "var(--c)", "var(--d)", "var(--e)"]
    types = sorted({m["type"] for g in data["groups"] for m in g["members"]})
    tcol = {t: pal[i % len(pal)] for i, t in enumerate(types)}
    total = sum(len(g["members"]) for g in data["groups"])
    marks, labels, a0 = [], [], -1.5708
    maxr = max((len(m["refs"]) for g in data["groups"] for m in g["members"]), default=1)
    for gi, g in enumerate(data["groups"]):
        span = 6.2832 * len(g["members"]) / total
        mid = a0 + span / 2
        import math
        lx, ly = cx + 395 * math.cos(mid), cy + 395 * math.sin(mid)
        labels.append(f'<text class="lab" x="{lx:.0f}" y="{ly:.0f}" text-anchor="middle" style="font-weight:600">'
                      f'{html.escape(g["category"])} · {len(g["members"])}</text>')
        for mi, m in enumerate(g["members"]):
            a = a0 + span * (mi + 0.5) / len(g["members"])
            k = len(m["refs"])
            r = 360 - 250 * (k / maxr) ** 0.5
            px, py = cx + r * math.cos(a), cy + r * math.sin(a)
            s = 3 + 9 * (k / maxr) ** 0.5
            marks.append(f'<line x1="{cx}" y1="{cy}" x2="{px:.1f}" y2="{py:.1f}" stroke="var(--rule)" stroke-width=".6"/>'
                         f'<circle class="hit dot" data-g="{gi}" data-m="{mi}" cx="{px:.1f}" cy="{py:.1f}" r="{s:.1f}" '
                         f'fill="{tcol[m["type"]]}" fill-opacity=".8"/>')
        a0 += span
    c = data["center"]
    svg = (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(data["question"])}">' + "".join(marks)
           + f'<circle cx="{cx}" cy="{cy}" r="34" fill="var(--ink)"/><text x="{cx}" y="{cy+5}" text-anchor="middle" '
           f'style="fill:var(--bg);font:600 15px Georgia">{html.escape(c["name"])}</text>' + "".join(labels) + "</svg>")
    key = "".join(f'<span><i style="background:{tcol[t]}"></i>{html.escape(t or "?")}</span>' for t in types) + \
        '<span>Nearer and larger: more verses cite the link.</span>'
    script = """
const P=document.getElementById('panel'),dots=[...document.querySelectorAll('.dot')];
function show(g,m){const x=DATA.groups[g].members[m];dots.forEach(d=>d.classList.toggle('dim',!(d.dataset.g==g&&d.dataset.m==m)));
P.innerHTML=`<b><a href="${SITE}/e/${x.addr}" target="_blank">${x.name}</a></b> (${x.type}): ${DATA.center.name} ${x.labels.join('; ')}<br>`+
x.refs.slice(0,30).map(r=>`<a href="${SITE}/p/${r}" target="_blank">${r}</a>`).join(' · ')+(x.refs.length>30?` and ${x.refs.length-30} more`:'');}
dots.forEach(d=>{d.addEventListener('mouseenter',()=>show(d.dataset.g,d.dataset.m));d.addEventListener('click',()=>show(d.dataset.g,d.dataset.m));});
"""
    return page(data, svg, script, key)


def patterns(S, d):
    """THE STORY PATTERNS AS CLUSTERS (plan A.58; Doug, 2026-11-16: "the pattern name in the middle and attributes
    surrounding within the shape like numbers on a clock. The stories themselves are their own nodes and can connect
    to more than one pattern ... the stories around the perimeter near the patterns they match"). Sixteen patterns
    (Doug, 2026-11-17: the 16 story patterns, not the role patterns), from the graph's own instances
    (out/event-template-instances.json, tools/events/template_nodes.py). A placement the template pass marked
    `conjectured` -- a story fitted to a pattern by a reading, not yet confirmed by hand -- is set in italic, its dot hollow."""
    t = json.loads((ROOT / "out" / "event-template-instances.json").read_text(encoding="utf-8"))
    fams, stories = [], {}
    for fid, f in t["families"].items():
        for i in f["instances"]:
            s = stories.setdefault(i["instance"], {"id": i["instance"], "title": (i.get("title") or i["instance"]).split(" (")[0],
                                                    "full": i.get("title") or "", "fams": [], "conj": []})
            s["fams"].append(fid)
            s["conj"].append(bool(i.get("conjectured")))
        fams.append({"id": fid, "name": f["name"], "note": f.get("note") or "",
                     "stages": [{"name": s_["name"], "optional": bool(s_.get("optional")), "kind": s_.get("stage")} for s_ in f["stages"]],
                     "stories": [i["instance"] for i in f["instances"]]})
    # the patterns round the ring so that two sharing a story sit close: random starts, improved by swaps
    ids = [f["id"] for f in fams]
    shared = collections.Counter()
    for s in stories.values():
        for a_, b_ in itertools.combinations(sorted(s["fams"]), 2):
            shared[(a_, b_)] += 1
    n = len(ids)

    def cost(seq):
        pos = {f: i for i, f in enumerate(seq)}
        return sum(w * min(abs(pos[a_] - pos[b_]), n - abs(pos[a_] - pos[b_])) for (a_, b_), w in shared.items())
    rng, best = random.Random(20261117), ids[:]
    for _ in range(30):
        seq = ids[:]
        rng.shuffle(seq)
        better = True
        while better:
            better = False
            for i in range(n):
                for j in range(i + 1, n):
                    t2 = seq[:]
                    t2[i], t2[j] = t2[j], t2[i]
                    if cost(t2) < cost(seq):
                        seq, better = t2, True
        if cost(seq) < cost(best):
            best = seq
    n_conj = sum(sum(s["conj"]) for s in stories.values())
    n_place = sum(len(s["fams"]) for s in stories.values())
    two = sum(len(s["fams"]) > 1 for s in stories.values())
    return {"id": "patterns", "question": "What shapes does the Bible tell its stories in?",
            "definition": (f"Every story the graph files under one of its {len(fams)} story patterns: {len(stories)} stories, "
                           f"{two} of them told in two. Each pattern is a sequence of stages (open dots: a stage that may be "
                           f"missing); each story is placed beside the patterns it follows. {n_conj} of the {n_place} "
                           f"placements are a reading, a story fitted to a pattern and not yet confirmed by hand: set in italic."),
            # the blog post on one of them (Doug, 2026-11-21: the r/DigitalHumanities post links only this page, "the
            # diagram card will link to the blog")
            "post": {"href": "/blog/story-patterns-and-the-pattern-of-the-bible",
                     "text": "The story behind one of these patterns, Judgment and a remnant spared: a post by the site's maker →"},
            "date": datetime.date.today().isoformat(), "families": fams, "stories": list(stories.values()), "order": best}


def render_patterns(data):
    # ONE CIRCLE, A SLICE FOR EACH STORY PATTERN (Doug, 2026-11-17: "Maybe one big circle with slices for the story
    # patterns", after "can it do anything to increase the use of space. Larger fonts relative to the size of the
    # diagram would be welcome"). The first drawing put 16 small circles on a ring round an empty middle. Now:
    #   - each pattern a slice, as wide as its stories; its name inside, its stages in order along its outer edge;
    #   - each story once, outside the rim beside its slice; a story told in two neighbouring patterns sits on the
    #     line between them, and one told in two apart is joined to its second slice by a curve across the middle;
    #   - a placement that is a reading (`conjectured`) in italic, its dot hollow.
    FS, FN, FT = 21, 24, 15
    R0, R1, R2 = 300, 560, 700                     # the hollow middle, the names' band, the rim (stages in R1-R2)
    W = 2 * (R2 + 40 + 330)
    C = W / 2
    fams = {f["id"]: f for f in data["families"]}
    seq = data["order"]
    st = {s["id"]: s for s in data["stories"]}
    idx = {f: i for i, f in enumerate(seq)}
    n = len(seq)
    # where each story sits: its own slice; on the boundary of two neighbours; or in its first slice, with a curve
    home, between, chords = collections.defaultdict(list), {}, []
    for s in data["stories"]:
        fs = s["fams"]
        if len(fs) == 2 and (idx[fs[0]] - idx[fs[1]]) % n in (1, n - 1):
            a_, b_ = sorted(fs, key=lambda f: idx[f])
            if idx[a_] == 0 and idx[b_] == n - 1:
                a_, b_ = b_, a_                    # the pair across the start of the ring: the boundary after the last
            between[s["id"]] = (a_, b_)            # on the boundary after a_
        else:
            home[fs[0]].append(s["id"])
            if len(fs) == 2:
                chords.append((s["id"], fs[1]))
    units = {f: len(home[f]) + 0.5 * sum(1 for v in between.values() if f in v) for f in seq}
    per = 2 * math.pi / sum(units.values())
    start, a0 = {}, -math.pi / 2
    for f in seq:
        start[f] = a0
        a0 += units[f] * per
    end = {f: start[f] + units[f] * per for f in seq}
    # each wedge: half a place for every shared story on its leading and trailing boundary, its own stories evenly
    # in between; the stories on one boundary take a place each, straddling the line (two between the barren woman
    # and promise kept stood on one spot)
    at = collections.defaultdict(list)                  # the boundary after f -> its shared stories
    for sid, (a_, b_) in between.items():
        at[a_].append(sid)
    sang = {}
    for f in seq:
        prev = seq[(idx[f] - 1) % n]
        lead, tail = 0.5 * len(at[prev]), 0.5 * len(at[f])
        ids = sorted(home[f], key=lambda x: st[x]["title"])
        span = units[f] - lead - tail
        for k, sid in enumerate(ids):
            sang[sid] = start[f] + (lead + (k + 0.5) * span / max(len(ids), 1)) * per
        for j, sid in enumerate(sorted(at[f], key=lambda x: st[x]["title"])):
            sang[sid] = end[f] + (j - (len(at[f]) - 1) / 2) * per

    def pt(r, a):
        return C + r * math.cos(a), C + r * math.sin(a)

    def wedge(r_in, r_out, a1, a2):
        x1, y1 = pt(r_out, a1)
        x2, y2 = pt(r_out, a2)
        x3, y3 = pt(r_in, a2)
        x4, y4 = pt(r_in, a1)
        big = 1 if a2 - a1 > math.pi else 0
        return (f"M{x1:.1f} {y1:.1f} A{r_out} {r_out} 0 {big} 1 {x2:.1f} {y2:.1f} L{x3:.1f} {y3:.1f} "
                f"A{r_in} {r_in} 0 {big} 0 {x4:.1f} {y4:.1f}Z")

    def radial(r, a, text, size, weight="", style="", fill="var(--ink)", anchor_out=True, extra=""):
        x, y = pt(r, a)
        deg = math.degrees(a) % 360
        flip = 90 < deg < 270
        anchor = ("end" if flip else "start") if anchor_out else ("start" if flip else "end")
        return (f'<text x="{x:.1f}" y="{y:.1f}" transform="rotate({deg + 180 if flip else deg:.1f} {x:.1f} {y:.1f})" '
                f'text-anchor="{anchor}" dominant-baseline="middle" {extra}style="font:{style}{weight}{size}px Georgia;'
                f'fill:{fill}">{html.escape(text)}</text>')

    slices, stages, names, labels, dots, curves = [], [], [], [], [], []
    for i, f in enumerate(seq):
        fam = fams[f]
        a1, a2 = start[f], end[f]
        tint = ".10" if i % 2 else ".18"
        slices.append(f'<path d="{wedge(R0, R2, a1, a2)}" fill="var(--b)" fill-opacity="{tint}" stroke="var(--bg)" '
                      f'stroke-width="3"/>')
        # its stages in order along the outer band, first to last in the reading direction
        stg = fam["stages"]
        for j, s_ in enumerate(stg):
            a = a1 + (j + 0.5) * (a2 - a1) / len(stg)
            x, y = pt(R2 - 12, a)
            # each stage opens its card, the kind of stage across every pattern that has it
            stages.append(f'<a href="{SITE}/e/tplstage_{s_["kind"]}"><g class="hit stg"><circle cx="{x:.1f}" cy="{y:.1f}" r="5" '
                          f'fill="{"var(--bg)" if s_["optional"] else "var(--b)"}" stroke="var(--b)" stroke-width="1.8"/>'
                          + radial(R2 - 24, a, s_["name"], FT, fill="var(--mute)", anchor_out=False) + '</g></a>')
        # the name inside, along the radius, in up to two lines across the slice
        words, rows = fam["name"].split(), [[]]
        for w_ in words:
            if rows[-1] and len(" ".join(rows[-1] + [w_])) > 18:
                rows.append([])
            rows[-1].append(w_)
        am = (a1 + a2) / 2
        dang = (FN * 1.15) / ((R0 + R1) / 2)
        flip = 90 < math.degrees(am) % 360 < 270          # turned text runs the other way round: so do its lines
        for r_, row in enumerate(rows):
            a = am + (r_ - (len(rows) - 1) / 2) * dang * (-1 if flip else 1)
            names.append(radial(R0 + 16, a, " ".join(row), FN, weight="600 "))
        slices.append(f'<a href="{SITE}/e/tpl_{f}"><path class="hit pat" data-f="{f}" d="{wedge(R0, R1 + 30, a1, a2)}" '
                      f'fill="transparent"/></a>')
    for sid, a in sang.items():
        s = st[sid]
        two = len(s["fams"]) > 1
        conj = any(s["conj"])
        col = "var(--a)" if two else "var(--mute)"
        x, y = pt(R2 + 18, a)
        dots.append(f'<a href="{SITE}/e/{html.escape(sid)}"><circle class="hit" cx="{x:.1f}" cy="{y:.1f}" '
                    f'r="{7 if two else 5}" fill="{"var(--bg)" if conj else col}" stroke="{col}" stroke-width="2"/></a>')
        labels.append(f'<a href="{SITE}/e/{html.escape(sid)}">'
                      + radial(R2 + 34, a, s["title"], FS, weight="600 " if two else "", style="italic " if conj else "",
                               extra=f'class="hit st" data-s="{html.escape(sid)}" ') + "</a>")
    for sid, other in chords:
        a1 = sang[sid]
        a2 = (start[other] + end[other]) / 2
        x1, y1 = pt(R0, a1)
        x2, y2 = pt(R0, a2)
        mx, my = pt(R0 * 0.45, (a1 + a2) / 2 if abs(a1 - a2) < math.pi else (a1 + a2) / 2 + math.pi)
        dash = ' stroke-dasharray="7 6"' if st[sid]["conj"][1] else ""
        curves.append(f'<a href="{SITE}/e/{html.escape(sid)}"><path class="hit ch" data-s="{html.escape(sid)}" '
                      f'd="M{x1:.1f} {y1:.1f} Q{mx:.1f} {my:.1f} {x2:.1f} {y2:.1f}" fill="none" stroke="var(--a)" '
                      f'stroke-width="2.4" stroke-opacity=".8"{dash}/></a>')
        # and the story's own line from the rim to the middle edge, so the curve reads as its
        xa, ya = pt(R2 + 10, a1)
        curves.append(f'<line x1="{xa:.1f}" y1="{ya:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="var(--a)" stroke-width="1.2" '
                      f'stroke-opacity=".5"/>')
    n_two = sum(len(s["fams"]) > 1 for s in data["stories"])
    middle = (f'<a href="#words"><g class="hit"><text x="{C}" y="{C - 40}" text-anchor="middle" style="font:700 110px '
              f'Georgia;fill:var(--b)">{n}</text><text x="{C}" y="{C + 6}" text-anchor="middle" style="font:26px Georgia;'
              f'fill:var(--ink)">story patterns</text><text x="{C}" y="{C + 52}" text-anchor="middle" style="font:24px '
              f'Georgia;fill:var(--mute)">{len(data["stories"])} stories, {n_two} in two</text><text x="{C}" y="{C + 92}" '
              f'text-anchor="middle" style="font:20px system-ui;fill:var(--b);text-decoration:underline">every one, in '
              f'words ↓</text></g></a>')
    svg = (f'<svg viewBox="0 0 {W:.0f} {W:.0f}" role="img" aria-label="{html.escape(data["question"])}">'
           + "".join(slices[::2]) + "".join(curves) + middle + "".join(stages) + "".join(names) + "".join(dots)
           + "".join(labels) + "".join(slices[1::2]) + "</svg>")
    key = ('<span><i style="background:var(--b)"></i>a story pattern; its stages along the rim, in order (open dot: may be '
           'missing)</span><span><i style="background:var(--a)"></i>a story told in two patterns: on the line between '
           'them, or joined across the middle</span><span><em>Italic</em>, hollow dot: a reading, not yet confirmed by hand. '
           'Hover a slice or a story.</span>')
    script = """
const P=document.getElementById('panel'),P0=P.innerHTML,SL=[...document.querySelectorAll('.pat')],TX=[...document.querySelectorAll('.st')];
const F=Object.fromEntries(DATA.families.map(f=>[f.id,f])),ST=Object.fromEntries(DATA.stories.map(s=>[s.id,s]));
const sl=id=>`<a href="${SITE}/e/${id}" target="_blank">${ST[id].title}</a>`;
const show=(fs,ss)=>{TX.forEach(t=>t.classList.toggle('dim',!ss.has(t.dataset.s)));SL.forEach(p=>p.style.fill=fs.has(p.dataset.f)?'color-mix(in srgb, var(--b) 22%, transparent)':'transparent');};
SL.forEach(g=>g.addEventListener('mouseenter',()=>{const f=F[g.dataset.f];show(new Set([f.id]),new Set(f.stories));
 P.innerHTML=`<b>${f.name}</b>: ${f.stages.map(s=>s.optional?'('+s.name+')':s.name).join(' → ')}. ${f.note}<br>Told in: `+f.stories.map(sl).join(', ');}));
TX.forEach(t=>t.addEventListener('mouseenter',()=>{const s=ST[t.dataset.s];show(new Set(s.fams),new Set([s.id]));
 P.innerHTML=`<b>${s.full||s.title}</b> follows `+s.fams.map((f,i)=>`<b>${F[f].name}</b>${s.conj[i]?' (a reading)':''}`).join(' and ')+'.';}));
document.querySelectorAll('svg').forEach(s=>s.addEventListener('mouseleave',()=>{TX.forEach(t=>t.classList.remove('dim'));SL.forEach(p=>p.style.fill='transparent');P.innerHTML=P0;}));
"""
    return page(data, svg, script, key, phone={"vb": [C - R2 - 40, C - R2 - 40, 2 * R2 + 80, 2 * R2 + 80]})


RELEASED = {"canon", "people", "ideas", "speech", "patterns"}   # David held: too close to the Navigator (Doug, 2026-11-14)        # views approved for the site, released one at a time (Doug, 2026-11-14)
# "patterns" (A.58) released 2026-11-17 (Doug: "Perfect, but make it all hyperlinked"; then the push that night)
VIEWS = {"canon": (canon, render_canon), "people": (people, render_people), "ideas": (ideas, render_ideas), "speech": (speech, render_speech), "david": (lambda S, d: person(S, d, "david"), render_person),
         "patterns": (patterns, render_patterns)}

if __name__ == "__main__":
    S, d = load()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in (sys.argv[1:] or list(VIEWS)):
        build, render = VIEWS[name]
        data = build(S, d)
        (OUT / f"{data['id']}.json").write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")
        page_html = render(data)
        (OUT / f"{data['id']}.html").write_text(page_html, encoding="utf-8")
        # RELEASED VIEWS are served at /visual/<id> (app2/static/visual/), one at a time as each is approved
        if name in RELEASED:
            rel = ROOT / "app2" / "static" / "visual"
            rel.mkdir(parents=True, exist_ok=True)
            (rel / f"{data['id']}.html").write_text(page_html, encoding="utf-8", newline="\n")
        print(name, "->", OUT / f"{data['id']}.html", {k: v for k, v in data.items() if k == "totals"})
