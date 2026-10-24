"""The ontology of the sentence-level build: declared, checked, and drawn.

2026-09-24: the ontology is key to making this happen; it is to be built out
and made visible as structures are discovered, working through verse by verse.

`ontology/kinds.json` declares every kind of unit and relation the build
produces. This tool holds the graph to it in BOTH directions:

    every node, edge and force value in the graph must be declared, and
    every kind declared `built` must have instances in the graph.

That is a closed-world check, the job SHACL does for RDF. It is deliberately
not an OWL-style open world, where a missing thing is assumed to exist
somewhere: here a missing thing is a fault, and an undeclared thing is a kind
nobody decided on. On its first run it found both — 30,462 Greek clauses with
no force, and 100 Hebrew clauses whose "force" was the word class of a noun.

    python tools/ontology.py            census + check; exit 1 on any fault
    python tools/ontology.py --page     also write out/ontology.html

The census is cached in out/ontology-census.json, keyed on the graph's build
time, so the page does not rescan 700,000 records per view.
"""
from __future__ import annotations

import collections
import gzip
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
KINDS = ROOT / "ontology" / "kinds.json"
CENSUS = OUT / "ontology-census.json"
# `order_link` is the ordered chain. Unlisted, `next` was matched with flag
# "none", so a flat-layer edge whose ENGLISH relation happened to be "next"
# (Num 22:5 `they -next->`) counted as the chain — found by the domain and
# range check (plan N.1).
FLAGS = ("clause_role", "clause_link", "order_link")


def load():
    return json.loads(KINDS.read_text(encoding="utf-8"))


def lineage(kind, onto=None):
    """[kind, parent, grandparent, ...] up the `parent` chain.

    PRINCIPLES 47: a node's kind is the most specific the graph can say now,
    and a pattern slot matches that kind or any specialization of it. This
    is the chain a slot is checked against. Capped, so a cycle written into
    kinds.json by mistake cannot hang a pattern run.
    """
    onto = onto or load()
    parent = {x["id"]: x.get("parent")
              for x in onto["classes"] + onto["relations"]}
    out = []
    while kind and kind not in out and len(out) < 20:
        out.append(kind)
        kind = parent.get(kind)
    return out


def is_a(kind, ancestor, onto=None):
    """Does a slot typed `ancestor` accept a node of `kind`? (PRINCIPLES 47)"""
    return ancestor in lineage(kind, onto)


def common_kind(kinds, onto=None):
    """The most specific kind every one of `kinds` is — their least common
    subsumer — or None if they share nothing.

    PRINCIPLES 47.3: a pattern slot's KIND is what all its fillers have in
    common. If every filler is an illustration the slot is 'an illustration'
    and the content may vary freely; if they are an illustration and a plain
    assertion, the slot is 'an assertion'.
    """
    onto = onto or load()
    chains = [lineage(k, onto) for k in kinds if k]
    if not chains:
        return None
    shared = set(chains[0]).intersection(*chains[1:])
    return next((k for k in chains[0] if k in shared), None)


def _node_matchers(onto):
    """MOST SPECIFIC FIRST. A node is counted under the deepest kind it
    matches (PRINCIPLES 47): an assertion is an Assertion, not merely a
    Clause. In declaration order, Clause matched first and Assertion would
    have counted none — and the check would have said so."""
    ms = [(c["id"], c["match"]) for c in onto["classes"] if c.get("match")]
    return sorted(ms, key=lambda m: -len(lineage(m[0], onto)))


def _edge_matchers(onto):
    # Specific types before the wildcard, whatever order the file lists them.
    ms = [(r["id"], r["match"]) for r in onto["relations"] if r.get("match")]
    return sorted(ms, key=lambda m: m[1]["type"] == "*")


def _within(kind, declared, onto):
    """Is `kind` the declared end, or a specialization of it? A relation's
    `from` / `to` is one kind or a list of kinds."""
    if kind is None:
        return False
    opts = declared if isinstance(declared, list) else [declared]
    return any(is_a(kind, o, onto) for o in opts)


def _ends(declared):
    return " | ".join(declared) if isinstance(declared, list) else \
        str(declared)


def _primary(declared):
    return declared[0] if isinstance(declared, list) else declared


def classify_node(d, matchers):
    for cid, m in matchers:
        if "has" in m and d.get(m["has"]):
            return cid
        # a list is any of its values: one kind spelled two ways, by the
        # builder and by the sweep's import (AgentActs: "acts", "agent_acts")
        if "eq" in m and all(d.get(k) in v if isinstance(v, list) else d.get(k) == v
                             for k, v in m["eq"].items()):
            return cid
    return None


def classify_edge(e, matchers):
    flag = next((f for f in FLAGS if e.get(f)), "none")
    for rid, m in matchers:
        if m["flag"] != flag:
            continue
        if m["type"] == "*" or e.get("type") in m["type"]:
            return rid
    return None


def _graph_built():
    try:
        return json.loads((OUT / "placeholder-summary.json")
                          .read_text(encoding="utf-8")).get("built")
    except (OSError, ValueError):
        return None


def census(force=False, write=True):
    """Count every declared kind in the graph, and everything undeclared.
    `write=False` leaves the cached census alone (the preflight test: the
    cache is a tracked file, and a check must not dirty the tree it checks)."""
    built = _graph_built()
    if not force and CENSUS.exists():
        c = json.loads(CENSUS.read_text(encoding="utf-8"))
        if c.get("graph_built") == built and \
                c.get("kinds_mtime") == KINDS.stat().st_mtime:
            return c
    onto = load()
    nm, em = _node_matchers(onto), _edge_matchers(onto)
    nodes = collections.Counter()
    edges = collections.Counter()
    inferred = collections.defaultdict(collections.Counter)
    forces = collections.defaultdict(collections.Counter)
    by_lang = collections.defaultdict(collections.Counter)
    example = {}
    stray_n = collections.Counter()
    stray_e = collections.Counter()
    stray_ex = {}
    # DOMAIN AND RANGE. Every relation declares `from` and `to`; until
    # 2026-09-25 they were only drawn. Checked, the first run found 11,332 of
    # 790,127 edges outside them: 7,653 verb roles on plain words (a second
    # `v` edge, which also doubled 7,734 content keys) and 3 flat edges
    # counted as the ordered chain — plus declarations too narrow for data
    # that was right. Plan N.1: conform to standard practice if it is free or helpful.
    rels = {r["id"]: r for r in onto["relations"]}
    kind_of = {}
    outside = collections.Counter()
    outside_ex = {}

    for line in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if "_source" in d:
            continue
        k = classify_node(d, nm)
        if k is not None:
            kind_of[d.get("id")] = k
        if k is None:
            sig = ",".join(sorted(x for x in d if x not in
                                  ("id", "ref", "local", "lang", "text")))
            stray_n[sig] += 1
            stray_ex.setdefault("node:" + sig, d.get("id"))
            continue
        nodes[k] += 1
        by_lang[k][d.get("lang") or "?"] += 1
        example.setdefault(k, d.get("ref"))

    for line in gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt",
                          encoding="utf-8"):
        e = json.loads(line)
        if "_source" in e:
            continue
        k = classify_edge(e, em)
        if k is None:
            flag = next((f for f in FLAGS if e.get(f)), "none")
            sig = f"{e.get('type')} [{flag}]"
            stray_e[sig] += 1
            stray_ex.setdefault("edge:" + sig, e.get("ref"))
            continue
        edges[k] += 1
        by_lang[k][e.get("lang") or "?"] += 1
        example.setdefault(k, e.get("ref"))
        r_ = rels.get(k) or {}
        if r_.get("from") and r_["status"] != "superseded":
            sk, dk = kind_of.get(e.get("src")), kind_of.get(e.get("dst"))
            if not (_within(sk, r_["from"], onto)
                    and _within(dk, r_["to"], onto)):
                sig = f"{k}: {sk} → {dk}"
                outside[sig] += 1
                outside_ex.setdefault(sig, f'{e.get("src")} → {e.get("dst")}')
        if e.get("inferred"):
            inferred[k][e["inferred"]] += 1
        if k == "asserts":
            forces[e.get("lang") or "?"][e.get("force") or "-"] += 1

    c = {"graph_built": built, "kinds_mtime": KINDS.stat().st_mtime,
         "nodes": dict(nodes), "edges": dict(edges),
         "inferred": {k: dict(v) for k, v in inferred.items()},
         "forces": {k: dict(v) for k, v in forces.items()},
         "by_lang": {k: dict(v) for k, v in by_lang.items()},
         "example": example,
         "stray_nodes": dict(stray_n), "stray_edges": dict(stray_e),
         "stray_example": stray_ex,
         "outside_ends": dict(outside), "outside_example": outside_ex}
    if write:
        CENSUS.write_text(json.dumps(c, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    return c


LAYER = OUT / "sweep-layer.jsonl.gz"


def layer_census(onto, path=LAYER):
    """THE READINGS COUNTED TOO (plan 1.43; approved 2026-10-18). The census above reads the builder's graph only, so the sweep's
    layer, drawn over every verse, could add a kind the file never declares,
    and a kind only the readings make (`partitive`) looked absent. Each layer
    record goes through the same matchers: a node it adds, a link it adds, a
    link it takes away (a removal names a type too, and must be a declared
    one)."""
    nm, em = _node_matchers(onto), _edge_matchers(onto)
    nodes, edges = collections.Counter(), collections.Counter()
    stray_n, stray_e, ex = collections.Counter(), collections.Counter(), {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("node"):
                k = classify_node(d, nm)
                if k is None:
                    sig = f"kind={d.get('kind')}"
                    stray_n[sig] += 1
                    ex.setdefault("node:" + sig, d.get("id"))
                else:
                    nodes[k] += 1
            elif d.get("type"):
                k = classify_edge(d, em)
                if k is None:
                    flag = next((f_ for f_ in FLAGS if d.get(f_)), "none")
                    sig = f"{d['type']} [{flag}]" + (" (a removal)" if d.get("action") == "remove" else "")
                    stray_e[sig] += 1
                    ex.setdefault("edge:" + sig, f"{d.get('src')} → {d.get('dst')}")
                elif d.get("action") != "remove":
                    edges[k] += 1
    return {"nodes": dict(nodes), "edges": dict(edges), "stray_nodes": dict(stray_n),
            "stray_edges": dict(stray_e), "stray_example": ex}


def check_layer(onto, lc):
    """The layer's faults: a kind or type it uses that the file does not
    declare, and a kind only the readings make that the layer does not have."""
    faults = [f"layer: {n:,} nodes of an undeclared kind ({sig}), e.g. {lc['stray_example'].get('node:' + sig)}"
              for sig, n in lc["stray_nodes"].items()]
    faults += [f"layer: {n:,} records of an undeclared type {sig}, e.g. {lc['stray_example'].get('edge:' + sig)}"
               for sig, n in lc["stray_edges"].items()]
    counts = {**lc["nodes"], **lc["edges"]}
    for item in onto["classes"] + onto["relations"]:
        n = counts.get(item["id"])
        if item.get("made_by") == "readings" and item["status"] == "built" and not n:
            faults.append(f"{item['id']} is made by the readings and the layer has none")
        if not n:
            continue
        # DEFERRED IN THE BUILDER, SUPPLIED BY THE SWEEP: allowed, and the
        # file must say so (1.42's wording does, for all 21 the layer used on
        # 2026-10-18); a kind still proposed or withdrawn is not shown at all
        if item["status"] == "deferred" and "sweep" not in (item.get("deferred") or ""):
            faults.append(f"{item['id']} is deferred, the layer has {n:,}, and its reason does not say the sweep supplies it")
        if item["status"] in ("proposed", "withdrawn"):
            faults.append(f"{item['id']} is declared {item['status']} and the layer has {n:,}")
    return faults


def check(onto, c):
    """Every fault, as a sentence. Empty means the file and the graph agree."""
    faults = []
    # ONE ID, ONE TERM: a second `participant` (2026-10-18, a parent for a
    # group's roles) went unnoticed here; only the vocabulary's publisher,
    # merging the two into one address, showed the clash
    seen_ids = collections.Counter(x["id"] for x in onto["classes"] + onto["relations"])
    faults += [f"{i} is declared {n} times" for i, n in seen_ids.items() if n > 1]
    for sig, n in c["stray_nodes"].items():
        faults.append(f"{n:,} nodes of an undeclared kind ({sig}), e.g. "
                      f"{c['stray_example'].get('node:' + sig)}")
    for sig, n in c["stray_edges"].items():
        faults.append(f"{n:,} edges of an undeclared type {sig}, e.g. "
                      f"{c['stray_example'].get('edge:' + sig)}")
    counts = {**c["nodes"], **c["edges"]}
    for item in onto["classes"] + onto["relations"]:
        # a kind only the readings make (the sweep's layer, never the builder:
        # `partitive`, 2026-10-18) is built where they are, which this census
        # of the builder's graph cannot see
        if item.get("made_by") == "readings":
            continue
        if item.get("match") and item["status"] in ("built", "superseded") \
                and not counts.get(item["id"]):
            faults.append(f"{item['id']} is declared {item['status']} and "
                          f"the graph has none")
        # deferred (plan 1.42): built by the earlier builder, not by this one;
        # one that has instances again is built, and the file must say so
        if item["status"] in ("proposed", "withdrawn", "deferred") and \
                counts.get(item["id"]):
            faults.append(f"{item['id']} is declared {item['status']} and "
                          f"the graph has {counts[item['id']]:,}")
    for sig, n in (c.get("outside_ends") or {}).items():
        rel = sig.split(":", 1)[0]
        r_ = next((r for r in onto["relations"] if r["id"] == rel), {})
        faults.append(f"{n:,} {rel} edges outside the declared "
                      f"{_ends(r_.get('from'))} → {_ends(r_.get('to'))} "
                      f"({sig.split(': ', 1)[1]}), e.g. "
                      f"{c['outside_example'].get(sig)}")
    # THE RST MAPPING IS COMPLETE AND CLOSED (plan N.4): every built relation
    # that links clauses or is a group member's role has an entry, and no
    # entry names a relation that is not declared
    rst = ((onto.get("mappings") or {}).get("rst") or {}).get("relations")
    if rst is not None:
        rels_ = {r["id"]: r for r in onto["relations"]}
        linking = {"clause_link", "member_of_group", "imperative_qualifier"}
        for r in onto["relations"]:
            if r["status"] == "built" and not r.get("abstract") and \
                    r["id"] not in linking and \
                    (r.get("parent") in linking or r["id"] == "causes") \
                    and r["id"] not in rst:
                faults.append(f"relation {r['id']} links clauses and has no "
                              f"RST mapping (mappings.rst)")
        for rid in rst:
            if rid not in rels_:
                faults.append(f"RST mapping names undeclared relation {rid}")
    # every upper force names a family that is declared, and a family marked
    # built is reached by at least one built upper force (plan N.3)
    fams = {f["id"]: f for f in
            (onto["forces"].get("families") or {}).get("list", [])}
    for u in onto["forces"]["upper"]:
        if u.get("family") and u["family"] not in fams:
            faults.append(f"force {u['id']} names undeclared family "
                          f"{u['family']}")
    for f in fams.values():
        if f["status"] == "built" and not any(
                u.get("family") == f["id"] and u["status"] == "built"
                for u in onto["forces"]["upper"]):
            faults.append(f"family {f['id']} is declared built and no built "
                          f"force reaches it")
    for lang, vals in c["forces"].items():
        known = onto["forces"].get(lang) or {}
        for v, n in vals.items():
            if v not in known:
                faults.append(f"{n:,} {lang} clauses with undeclared force "
                              f"'{v}'")
    return faults


# ---------------------------------------------------------------------------
# The page


def _mermaid(onto, c):
    """Kinds as boxes, relations as arrows — the built layer only, with counts.

    Proposed kinds are drawn dashed so the shape of what is coming is visible
    beside what exists, and cannot be mistaken for it."""
    counts = {**c["nodes"], **c["edges"]}
    cls = {x["id"]: x for x in onto["classes"]}
    show = [x for x in onto["classes"]
            if x["status"] in ("built", "proposed") and x["id"] != "Unit"]
    out = ["graph LR"]
    for x in show:
        n = counts.get(x["id"])
        sub = f"<br/><small>{n:,}</small>" if n else (
            "<br/><small>proposed</small>" if x["status"] == "proposed"
            else "")
        out.append(f'  {x["id"]}["<b>{x["label"]}</b>{sub}"]')
    # Specialization, drawn as a hollow-headed link from child to parent.
    for x in show:
        if x.get("parent") and x["parent"] in cls and x["parent"] != "Unit":
            out.append(f'  {x["id"]} -. is a .-> {x["parent"]}')
    seen = set()
    arrows = {}
    rels = {r["id"]: r for r in onto["relations"]}
    for r in onto["relations"]:
        if r["status"] not in ("built", "proposed") or r.get("abstract"):
            continue
        top = r
        while top.get("parent") and top["parent"] in rels:
            top = rels[top["parent"]]
        # a relation may allow several end kinds; the drawing uses the first,
        # its primary one, and the card lists them all
        a, b = _primary(r["from"]), _primary(r["to"])
        if a not in cls or b not in cls or r["id"] == "flat":
            continue
        # One arrow per family between the same two kinds: the eight
        # connectives are one arrow labelled with the family.
        key = (a, b, top["id"], r["status"])
        if key in seen:
            continue
        seen.add(key)
        # Only the members of the family that join THESE two kinds: an
        # action-state pair's arrow counts `action` and `state`, not every
        # group member in the graph.
        fam = [x for x in onto["relations"]
               if (x is top or x.get("parent") == top["id"])
               and _primary(x["from"]) == a and _primary(x["to"]) == b
               and x["status"] == r["status"]]
        n = sum(counts.get(x["id"], 0) for x in fam)
        named = [x["label"] for x in fam if not x.get("abstract")]
        lbl = (" / ".join(named) if 1 <= len(named) <= 2 else top["label"]) \
            + (f" · {n:,}" if n else "")
        arrows.setdefault((a, b, top["id"]), {})[r["status"]] = lbl
    # Built and proposed members of one family between the same two kinds
    # share ONE arrow: mermaid draws two self-loops on top of each other, and
    # the built count vanished under the proposed label.
    for (a, b, _t), lab in arrows.items():
        if "built" in lab:
            lbl = lab["built"] + (f"<br/><i>next: {lab['proposed']}</i>"
                                  if "proposed" in lab else "")
            out.append(f'  {a} -->|"{lbl}"| {b}')
        else:
            out.append(f'  {a} -.->|"next: {lab["proposed"]}"| {b}')
    for x in show:
        if x["status"] == "proposed":
            out.append(f"  class {x['id']} proposed")
    out.append("  classDef proposed stroke-dasharray:5 4,opacity:.75")
    return "\n".join(out)


def _q(item):
    est = item.get("established") or {}
    bits = []
    if est.get("ref"):
        bits.append(f'<a href="/tree?ref={html.escape(est["ref"])}">'
                    f'{html.escape(est["ref"])}</a>')
    if est.get("date"):
        bits.append(html.escape(est["date"]))
    head = " · ".join(bits)
    q = est.get("quote")
    note = est.get("note") or est.get("why")
    s = f'<div class="est">{head}</div>' if head else ""
    if q:
        s += f'<blockquote>{html.escape(q)}<cite>Doug</cite></blockquote>'
    if note:
        s += f'<p class="note">{html.escape(note)}</p>'
    return s


_ONTO_FOR_CARDS = None            # set by page(), so cards can read mappings


def _card(item, counts, c):
    n = counts.get(item["id"])
    st = item["status"]
    badge = f'<span class="st {st}">{st}</span>'
    num = f'<span class="n">{n:,}</span>' if n else ""
    langs = c["by_lang"].get(item["id"]) or {}
    lang = (" · ".join(f"{k} {v:,}" for k, v in sorted(langs.items()))
            if len(langs) > 1 else "")
    body = []
    for key, lab in (("definition", ""), ("reads", "reads"),
                     ("rule", "rule"), ("proof", "shown by"),
                     ("also", ""), ("known_fault", "known fault"),
                     ("falsified_by", "would be wrong if"),
                     ("was", "was"), ("instead", "replaced by"),
                     # the reasons a kind is not built, or was reversed —
                     # the part of a card that stops it being re-proposed
                     ("why_not_built", "not built because"),
                     ("deferred", "deferred because"),
                     ("withdrawn", "withdrawn because")):
        v = item.get(key)
        if not v:
            continue
        cls = ' class="fault"' if key == "known_fault" else ""
        text = html.escape(v)
        if key == "reads":
            # A relation read as a sentence, with its two ends named — the
            # test that caught 'he is good BECAUSE we give thanks'.
            text = (text.replace("{src}", f'<i>[{html.escape(_ends(item["from"]))}]</i>')
                        .replace("{dst}", f'<i>[{html.escape(_ends(item["to"]))}]</i>')
                        .replace("{prep_gloss}", "<i>[preposition]</i>")
                        .replace("{force}", "<i>[force]</i>"))
        body.append(f'<p{cls}>' + (f'<b>{lab}</b> ' if lab else "")
                    + text + "</p>")
    # the RST relation this corresponds to (plan N.4)
    m_ = (((_ONTO_FOR_CARDS or {}).get("mappings") or {}).get("rst") or {}) \
        .get("relations", {}).get(item["id"])
    if m_:
        body.append(
            f'<p class="note"><b>RST</b> {html.escape(m_.get("rst") or "—")}'
            f' · <i>{html.escape(m_["fit"])}</i>'
            + (f' — {html.escape(m_["note"])}' if m_.get("note") else "")
            + "</p>")
    if item.get("extension_points"):
        body.append("<p><b>extended by</b></p><ul class=ext>" + "".join(
            f"<li>{html.escape(x)}</li>" for x in item["extension_points"])
            + "</ul>")
    inf = c["inferred"].get(item["id"]) or {}
    if inf:
        body.append("<p><b>inferred</b> " + "; ".join(
            f"{v:,} by “{html.escape(k)}”" for k, v in inf.items()) + "</p>")
    if item.get("queue"):
        body.append(f'<p class="note">queue item {item["queue"]} in '
                    f'docs/BACKLOG.md</p>')
    ends = (f'<div class="ends">{html.escape(_ends(item["from"]))} → '
            f'{html.escape(_ends(item["to"]))}</div>' if item.get("from")
            else "")
    return (f'<article id="{html.escape(item["id"])}" class="{st}">'
            f'<header><h3>{html.escape(item["label"])}</h3>{badge}{num}'
            f'</header>{ends}'
            f'{"<div class=langs>" + lang + "</div>" if lang else ""}'
            + "".join(body) + _q(item) + "</article>")


def _tree(items, parent, counts, c, depth=0):
    kids = [x for x in items if x.get("parent") == parent]
    out = []
    for x in kids:
        sub = _tree(items, x["id"], counts, c, depth + 1)
        out.append(f'<div class="node d{depth}">{_card(x, counts, c)}'
                   + (f'<div class="kids">{sub}</div>' if sub else "")
                   + "</div>")
    return "".join(out)


def _forces(onto, c):
    rows = []
    ups = {u["id"]: u for u in onto["forces"]["upper"]}
    for lang in ("hebrew", "greek"):
        got = c["forces"].get(lang) or {}
        decl = onto["forces"].get(lang) or {}
        for form, spec in decl.items():
            n = got.get(form, 0)
            up = ups.get(spec["upper"], {})
            caution = (f'<div class="fault">{html.escape(spec["caution"])}'
                       f'</div>' if spec.get("caution") else "")
            rows.append(
                f"<tr><td>{lang}</td><td><code>{html.escape(form)}</code></td>"
                f"<td>{html.escape(spec.get('gloss', ''))}{caution}</td>"
                f"<td class=r>{n:,}</td>"
                f"<td><span class='st {up.get('status', '')}'>"
                f"{html.escape(up.get('label', spec['upper']))}</span></td>"
                f"</tr>")
    table = ("<table><thead><tr><th>language</th><th>form (what is stored "
             "today)</th><th>what it does</th><th class=r>clauses</th>"
             "<th>meaning-layer force</th></tr></thead><tbody>"
             + "".join(rows) + "</tbody></table>")
    # the speech-act families force is framed by (plan N.3)
    fam = onto["forces"].get("families") or {}
    frows = []
    for f in fam.get("list", []):
        via = [u["label"] for u in onto["forces"]["upper"]
               if u.get("family") == f["id"]]
        extra = "".join(
            f'<div class="{cls}">{html.escape(f[k])}</div>'
            for k, cls in (("markers", "note"), ("caution", "fault"),
                           ("why_not_built", "note")) if f.get(k))
        frows.append(
            f"<tr><td><span class='st {f['status']}'>{html.escape(f['id'])}"
            f"</span></td><td>{html.escape(f['definition'])}{extra}</td>"
            f"<td>{html.escape(', '.join(via) or '—')}</td></tr>")
    if frows:
        table += (f"<h3>Speech-act families</h3><p>{html.escape(fam['_what'])}"
                  "</p><table><thead><tr><th>family</th><th>what it is, and "
                  "what marks it</th><th>reached by</th></tr></thead><tbody>"
                  + "".join(frows) + "</tbody></table>")
    return table


def _passages(onto):
    """The log of passages worked — the method, and the measure of it."""
    p = onto.get("passages") or {}
    rows = []
    for w in reversed(p.get("worked") or []):
        def lst(k, cls=""):
            v = w.get(k) or []
            return ("<ul" + (f' class="{cls}"' if cls else "") + ">"
                    + "".join(f"<li>{html.escape(x)}</li>" for x in v)
                    + "</ul>") if v else "<p class=note>none</p>"
        rows.append(
            f'<article><header><h3><a href="/passage?from='
            f'{html.escape(w["from"])}&to={html.escape(w["to"])}">'
            f'{html.escape(w["name"])}</a></h3>'
            f'<span class="n">{html.escape(w.get("english", ""))} · '
            f'{html.escape(w.get("date", ""))}</span></header>'
            + (f'<p class="fault"><b>{html.escape(w["status"])}</b></p>'
               if w.get("status") else "")
            + f'<p class="note">{html.escape(w.get("shape", ""))}</p>'
            f'<div class="pw"><div><b>added</b>{lst("added")}</div>'
            f'<div><b>corrected</b>{lst("corrected")}</div>'
            f'<div><b>faults found</b>{lst("faults", "fault")}</div>'
            # first retrieval: what the graph got wrong before any fix made
            # for this passage — the measure set: "clean at first
            # retrieval"
            + (f'<div><b>first retrieval</b>{lst("first_draw", "fault")}'
               f'</div>' if w.get("first_draw") else "")
            + (f'<div><b>questions</b>{lst("questions")}</div>'
               if w.get("questions") else "")
            + '</div>'
            f'</article>')
    return (f'<section class="layer" id="passages"><h2>Passages worked'
            f'<small>newest first</small></h2>'
            f'<p>{html.escape(p.get("_what", ""))}</p>'
            + "".join(rows) + "</section>")


_STYLE = """
.lead{max-width:78ch;color:var(--muted)}
.status{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 4px}
.pill{border:1px solid var(--line);border-radius:999px;padding:3px 11px;
font-size:13px;background:var(--card)}
.pill.bad{border-color:var(--red);color:var(--red)}
.pill.good{border-color:#2f6d3f;color:#2f6d3f}
.layer{margin:34px 0 0}
.layer>h2 small{text-transform:none;letter-spacing:0;font-weight:400;
margin-left:8px;color:var(--faint)}
.layer>p{max-width:78ch;color:var(--muted);margin:-2px 0 12px}
.node{margin:0 0 10px}
.kids{margin:8px 0 0 22px;padding-left:14px;border-left:2px solid var(--line)}
article{border:1px solid var(--line);border-radius:8px;background:var(--card);
padding:11px 14px;max-width:80ch}
article.proposed{border-style:dashed}
article.withdrawn,article.superseded{opacity:.72}
article header{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap}
article h3{margin:0;font-size:16px}
article p{margin:6px 0 0}
.n{margin-left:auto;font-variant-numeric:tabular-nums;color:var(--muted)}
.ends,.langs{font-size:12px;color:var(--faint);margin-top:2px}
.st{font-size:11px;border-radius:4px;padding:1px 6px;border:1px solid}
.st.built{color:#2f6d3f;border-color:#2f6d3f}
.st.proposed{color:var(--blue);border-color:var(--blue)}
.st.superseded{color:var(--ochre);border-color:var(--ochre)}
.st.withdrawn{color:var(--faint);border-color:var(--faint)}
.fault{color:var(--red)}
.est{font-size:12px;color:var(--muted);margin-top:8px}
blockquote{margin:6px 0 0;padding:4px 0 4px 12px;border-left:3px solid
var(--ochre);font-style:italic}
blockquote cite{font-style:normal;color:var(--faint);font-size:12px;
margin-left:8px}
blockquote cite:before{content:"— "}
.note{color:var(--muted);font-size:13px}
table{border-collapse:collapse;font-size:14px;max-width:100%}
td,th{border-bottom:1px solid var(--line);padding:5px 10px;text-align:left;
vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600}
.r{text-align:right;font-variant-numeric:tabular-nums}
.tw{overflow-x:auto}
ul.faults{color:var(--red)}
.pw{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
gap:10px;margin-top:6px;font-size:13px}
.pw ul{margin:4px 0 0;padding-left:18px}
#passages article{max-width:100ch;box-sizing:border-box}
article{box-sizing:border-box}
nav.top{font-size:13px;margin:0 0 12px}
nav.top a{margin-right:14px}
@media (max-width:640px){.kids{margin-left:8px;padding-left:8px}}
"""


def page():
    sys.path.insert(0, str(ROOT / "tools"))
    import versetree                                    # noqa: PLC0415
    global _ONTO_FOR_CARDS
    onto = load()
    _ONTO_FOR_CARDS = onto
    c = census()
    faults = check(onto, c)
    counts = {**c["nodes"], **c["edges"]}
    # THE RULES the ontology holds itself to — `_rules` in kinds.json, which
    # now include the two lessons adopted from ontology practice (N.1, N.2)
    rules_html = "".join(
        f"<li><b>{html.escape(r.split('.', 1)[0])}.</b>"
        f"{html.escape(r.split('.', 1)[1]) if '.' in r else ''}</li>"
        for r in onto.get("_rules") or [])
    # RST relations not yet met — the catalogue's questions for next passages
    nym = ((onto.get("mappings") or {}).get("rst") or {}).get("not_yet_met",
                                                               {})
    nym_html = "".join(f"<li><b>{html.escape(k)}</b> — {html.escape(v)}</li>"
                       for k, v in nym.items() if not k.startswith("_"))
    # the export: files present, and their namespaces (N.4)
    ttl = OUT / "ontology.ttl"
    shp = OUT / "ontology-shapes.ttl"
    export_html = ""
    if ttl.exists():
        import ontology_rdf as R                        # noqa: PLC0415
        ns_rows = "".join(
            f"<tr><td><code>{html.escape(p)}:</code></td>"
            f"<td><code>{html.escape(R.NS[k])}</code></td>"
            f"<td>{html.escape(k)}</td></tr>" for k, p in R.PREFIX.items())
        ns_rows += (f"<tr><td><code>shapes:</code></td><td><code>"
                    f"{html.escape(R.SH_NS)}</code></td><td>the SHACL checks"
                    f"</td></tr><tr><td><code>meta:</code></td><td><code>"
                    f"{html.escape(R.META)}</code></td><td>our annotations: "
                    f"status, established, falsified by, withdrawn, RST</td>"
                    f"</tr>")
        export_html = f"""<section class="layer" id="export"><h2>As RDFS and
SHACL<small>for readers who use the standard tools</small></h2>
<p>The same ontology in the W3C vocabularies: RDFS + SKOS say what the kinds
are (<code>out/ontology.ttl</code>, {ttl.stat().st_size:,} bytes) and SHACL
says what the check enforces (<code>out/ontology-shapes.ttl</code>,
{shp.stat().st_size:,} bytes). Written by <code>tools/ontology_rdf.py</code>
from this file, which stays the source. <code>tools/shacl_check.py</code> runs
the shapes against a passage beside the Python check: they agree edge for edge
on Psalm 23, Exodus 8 and Genesis 1, clean and with faults planted — when
SHACL runs <b>without RDFS inference</b>. With it, a word made the source of
<i>asserts</i> was inferred to be a Clause instead of reported.</p>
<p>One namespace per ontology, pathed to mirror the layers. The path is for
people; the layering is stated as a triple (<code>meta:over</code>). Term IRIs
carry no version.</p>
<div class="tw"><table><thead><tr><th>prefix</th><th>namespace</th>
<th>layer</th></tr></thead><tbody>{ns_rows}</tbody></table></div></section>"""
    items = onto["classes"]
    rels = onto["relations"]

    def section(layer, what):
        lay = next(x for x in onto["layers"] if x["id"] == layer)
        cs = [x for x in items if x["layer"] == layer]
        rs = [x for x in rels if x["layer"] == layer]
        top_c = [x for x in cs if x.get("parent") not in
                 {y["id"] for y in cs}]
        blocks = []
        for x in top_c:
            sub = _tree(cs, x["id"], counts, c)
            blocks.append(f'<div class="node">{_card(x, counts, c)}'
                          + (f'<div class="kids">{sub}</div>' if sub else "")
                          + "</div>")
        top_r = [x for x in rs if x.get("parent") not in
                 {y["id"] for y in rs}]
        for x in top_r:
            sub = _tree(rs, x["id"], counts, c)
            blocks.append(f'<div class="node">{_card(x, counts, c)}'
                          + (f'<div class="kids">{sub}</div>' if sub else "")
                          + "</div>")
        return (f'<section class="layer" id="layer-{layer}"><h2>{lay["label"]}'
                f'<small>{what}</small></h2><p>{html.escape(lay["what"])}</p>'
                + "".join(blocks) + "</section>")

    n_built = sum(1 for x in items + rels if x["status"] == "built"
                  and not x.get("abstract"))
    n_prop = sum(1 for x in items + rels if x["status"] == "proposed")
    n_wd = sum(1 for x in items + rels if x["status"] == "withdrawn")
    n_deferred = sum(1 for x in items + rels if x["status"] == "deferred")
    health = (f'<span class="pill good">graph and ontology agree</span>'
              if not faults else
              f'<span class="pill bad">{len(faults)} disagreement'
              f'{"s" if len(faults) > 1 else ""}</span>')
    fault_list = ("<ul class=faults>" + "".join(
        f"<li>{html.escape(f)}</li>" for f in faults) + "</ul>"
        if faults else "")
    return f"""<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Structure ontology</title>
<style>{versetree._CSS}{_STYLE}</style>
<nav class="top"><a href="/suite">verse suite</a><a href="/tree">verse tree</a>
<a href="/passage">frog plague</a><a href="#passages">passages</a>
<a href="#layer-upper">meaning</a><a href="#forces">forces</a>
<a href="#layer-lexical">words</a><a href="#rst">RST</a>
<a href="#export">RDFS · SHACL</a><a href="/plan">plan</a></nav>
<h1>The structure ontology</h1>
<p class="lead">Every kind of unit and relation the sentence-level build makes,
with the verse that made it necessary. Nothing here was written first and fitted
to the text: each kind arrived when a verse could not be drawn without it.
Counts are read from the graph built {html.escape(c.get('graph_built') or '?')}.
</p>
<div class="status">{health}
<span class="pill">{n_built} built</span>
<span class="pill">{n_prop} proposed</span>
<span class="pill">{n_wd} withdrawn, kept with the reason</span>
<span class="pill">{n_deferred} deferred, built before and kept for re-entry</span></div>
{fault_list}
<p class="lead" style="margin-top:14px">The check is closed-world: anything in
the graph that is not declared here is a fault, and so is anything declared
built that the graph does not have, and so is any edge outside the kinds its
relation declares it joins. Solid boxes exist; dashed ones are on the
queue.</p>

<details class="rules" open><summary><h2 style="display:inline">The rules it
holds itself to</h2></summary><ol>{rules_html}</ol></details>

<h2>The shape</h2>
<div class="wrap"><pre class="mermaid">{html.escape(_mermaid(onto, c))}</pre></div>

{_passages(onto)}

{section("upper", "language-independent — patterns are matched here")}

<section class="layer" id="forces"><h2>Forces<small>what a clause does
with its content</small></h2>
<p>{html.escape(onto["forces"]["_what"])}</p>
<div class="tw">{_forces(onto, c)}</div></section>

{section("language", "how Hebrew, Aramaic and Greek mark it")}
{section("lexical", "the words themselves")}

<section class="layer" id="rst"><h2>What discourse theory has that we have
not met<small>Rhetorical Structure Theory's relations with no counterpart here
yet</small></h2>
<p>Each clause link above shows the RST relation it corresponds to. These are
the other way round — questions to put to the next passages, not kinds to
add.</p><ul>{nym_html}</ul></section>

{export_html}

<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
const dark = matchMedia('(prefers-color-scheme: dark)').matches;
mermaid.initialize({{startOnLoad:true, theme: dark ? 'dark' : 'neutral',
  flowchart:{{curve:'basis', nodeSpacing:30, rankSpacing:80, htmlLabels:true}}}});
</script>
</html>
"""


def main():
    onto = load()
    c = census(force="--fresh" in sys.argv)
    faults = check(onto, c)
    counts = {**c["nodes"], **c["edges"]}
    print(f"graph built {c.get('graph_built')}")
    for item in onto["classes"] + onto["relations"]:
        if item.get("match"):
            print(f"  {item['status']:<11} {item['id']:<16} "
                  f"{counts.get(item['id'], 0):>9,}")
    for lang, vals in c["forces"].items():
        print(f"  force {lang}: " + ", ".join(
            f"{k} {v:,}" for k, v in sorted(vals.items(), key=lambda x: -x[1])))
    if "--page" in sys.argv:
        (OUT / "ontology.html").write_text(page(), encoding="utf-8")
        print(f"  wrote {OUT / 'ontology.html'}")
    if faults:
        print(f"\n{len(faults)} disagreement(s) between ontology/kinds.json "
              f"and the graph:")
        for f in faults:
            print("  - " + f)
        return 1
    print("\nok - graph and ontology agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
