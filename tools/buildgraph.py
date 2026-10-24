"""Assemble every derived layer into one graph, and report what came out.

2026-09-12: a best effort to build out the entire new graph, to see what happens.

This does not derive anything. Every layer in `out/` was produced by its own
tool with its own provenance; this reads them and states the graph they imply --
which nodes exist, which edges connect them, and where the holes are.

## What it refuses to do

**No cross-verse identity is invented.** `tools/graphnodes.py` emits one node
per OCCURRENCE and says so in its own header: *"No cross-verse identity is
claimed; merging is a later pass with evidence."* That restraint is kept here.
Where a layer supplies identity with evidence -- `people-xref` via Strong's
numbers, `places` via STEPBible tags -- the identity node is emitted and the
edge says which layer claimed it.

**Nothing is counted twice.** A relation present in two layers is emitted once
with both sources listed, because a graph that inflates its own edge count is
the failure recorded earlier: 75% of 16,124 relations turned out to record
which words are where rather than what any passage says.

## The levels

    word occurrence   placeholder-nodes         the floor
    verse             every ref seen anywhere
    section           structure.jsonl.gz        translator headings
    book
    person / place    people-xref, places       identity WITH evidence
    pattern           formulaic, clauseforms    a shape, not a location

Edges are typed by what licenses them, never by what they look like.

    python tools/buildgraph.py            # report
    python tools/buildgraph.py --write    # emit out/graph-nodes/edges.jsonl.gz
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"


def rows(name, quiet=True):
    p = OUT / name
    if not p.exists():
        if not quiet:
            print(f"    (missing {name})")
        return
    op = gzip.open if name.endswith(".gz") else open
    try:
        with op(p, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(d, dict) and any(k.startswith("_") for k in d):
                    continue
                yield d
    except OSError:
        return


def vkey(ref):
    try:
        b, c, v = ref.split(".")
        return (b, int(c), int(v))
    except Exception:
        return None


class Graph:
    def __init__(self):
        self.nodes = {}                       # id -> dict
        self.edges = {}                       # (src,type,dst) -> dict
        self.layer_edges = collections.Counter()
        self.layer_nodes = collections.Counter()

    def node(self, nid, kind, layer, **kw):
        n = self.nodes.get(nid)
        if n is None:
            n = self.nodes[nid] = {"id": nid, "kind": kind, "src": []}
            self.layer_nodes[kind] += 1
        if layer not in n["src"]:
            n["src"].append(layer)
        for k, v in kw.items():
            if v is not None and k not in n:
                n[k] = v
        return nid

    def edge(self, src, typ, dst, layer, **kw):
        if src is None or dst is None or src == dst:
            return
        k = (src, typ, dst)
        e = self.edges.get(k)
        if e is None:
            e = self.edges[k] = {"src": src, "type": typ, "dst": dst, "by": []}
            self.layer_edges[layer] += 1
        if layer not in e["by"]:
            e["by"].append(layer)
        for a, b in kw.items():
            if b is not None and a not in e:
                e[a] = b


def build(g: Graph):
    seen_refs = set()

    def verse(ref):
        if not ref or vkey(ref) is None:
            return None
        if ref not in seen_refs:
            seen_refs.add(ref)
            b, c, v = ref.split(".")
            g.node(ref, "verse", "refs", book=b, chapter=int(c), verse=int(v))
            g.node(f"book:{b}", "book", "refs", name=b)
            g.edge(ref, "in_book", f"book:{b}", "refs")
        return ref

    # ---- the floor: one node per word occurrence, plus its syntactic edges
    n = 0
    for d in rows("placeholder-nodes.jsonl.gz"):
        if not d.get("id"):
            continue
        verse(d.get("ref"))
        g.node(d["id"], "occurrence", "graphnodes", ref=d.get("ref"),
               lemma=d.get("lemma"), text=d.get("text"), pos=d.get("pos"))
        g.edge(d["id"], "occurs_in", d.get("ref"), "graphnodes")
        n += 1
    print(f"  occurrences                 {n:>8,}", flush=True)
    for d in rows("placeholder-edges.jsonl.gz"):
        g.edge(d.get("src"), d.get("type") or "member", d.get("dst"), "graphnodes")

    # ---- sections from the translator vote
    secs = 0
    for d in rows("structure.jsonl.gz"):
        ref = d.get("ref")
        if not ref or vkey(ref) is None:
            continue
        verse(ref)
        if d.get("level") != "section":
            continue
        sid = f"sec:{ref}"
        g.node(sid, "section", "structure", title=d.get("title"),
               agree=d.get("agree"), of=d.get("of"), starts=ref)
        g.edge(sid, "starts_at", ref, "structure")
        secs += 1
    print(f"  sections (translator vote)  {secs:>8,}")

    # ---- identity WITH evidence
    for d in rows("people-xref.jsonl.gz"):
        ref = verse(d.get("ref"))
        for p in d.get("people") or []:
            pid = f"person:{p.get('strong')}"
            g.node(pid, "person", "people-xref", name=p.get("name"),
                   occurrences=p.get("occurrences"))
            g.edge(ref, "mentions_person", pid, "people-xref")
    for d in rows("places.jsonl.gz"):
        ref = verse(d.get("ref"))
        for key in ("places", "place"):
            val = d.get(key)
            if not val:
                continue
            for p in (val if isinstance(val, list) else [val]):
                label = p.get("label") if isinstance(p, dict) else p
                if not label:
                    continue
                pid = f"place:{label}"
                g.node(pid, "place", "places", name=label)
                g.edge(ref, "mentions_place", pid, "places")

    # ---- relations between people
    for d in rows("kinship.jsonl.gz"):
        ref = verse(d.get("ref"))
        a, b, rel = d.get("a"), d.get("b"), d.get("rel")
        if not (a and b and rel):
            continue
        na = g.node(f"name:{a}", "named", "kinship", name=a)
        nb = g.node(f"name:{b}", "named", "kinship", name=b)
        g.edge(na, rel, nb, "kinship", at=ref)

    # ---- who speaks
    for d in rows("speakers.jsonl.gz"):
        ref = verse(d.get("ref"))
        sp = d.get("speaker")
        if not sp:
            continue
        sid = g.node(f"name:{sp}", "named", "speakers", name=sp)
        g.edge(sid, "speaks", ref, "speakers", by=d.get("by"))

    # ---- figures
    for d in rows("comparisons.jsonl.gz"):
        ref = verse(d.get("ref"))
        for v in d.get("vehicle") or []:
            g.node(f"name:{v}", "named", "comparisons", name=v)
            g.edge(ref, "compares_to", f"name:{v}", "comparisons")
        for t in d.get("tenor") or []:
            g.node(f"name:{t}", "named", "comparisons", name=t)
            g.edge(ref, "compares", f"name:{t}", "comparisons")
    for d in rows("metaphor.jsonl.gz"):
        ref = verse(d.get("ref"))
        for v in d.get("vehicle") or []:
            g.node(f"name:{v}", "named", "metaphor", name=v)
            g.edge(ref, "image_of", f"name:{v}", "metaphor")

    # ---- events and their participants
    ev = 0
    for d in rows("events.jsonl.gz"):
        ref = verse(d.get("ref"))
        lem = d.get("lemma")
        if not lem:
            continue
        eid = f"event:{ref}:{lem}"
        g.node(eid, "event", "events", lemma=lem, gloss=d.get("gloss"), ref=ref)
        g.edge(eid, "happens_in", ref, "events")
        ev += 1
        for role, names in (d.get("participants") or {}).items():
            for nm in names:
                g.node(f"name:{nm}", "named", "events", name=nm)
                g.edge(eid, f"role_{role}", f"name:{nm}", "events")
    print(f"  events                      {ev:>8,}")

    # ---- patterns: a shape, plus the instances that realise it
    #
    # The first version of this read only the `form`/`pattern` rows and skipped
    # `kind: "instance_of"` entirely, which left all 35,613 pattern nodes with
    # no edges and produced a confident report of a structural hole in the
    # project. The hole was in this function. The instance edges were already
    # there -- 14,017 in clauseforms and 112,894 in formulaic.
    pat = inst = 0

    def span_node(src):
        """`Mat.1.1` is a verse; `Mat.21.31-33` is a span over verses."""
        if "-" not in src:
            return verse(src)
        head, last = src.rsplit("-", 1)
        b, c, v0 = head.split(".")
        try:
            lo, hi = int(v0), int(last)
        except ValueError:
            return verse(head)
        sid = f"span:{src}"
        g.node(sid, "span", "patterns", book=b, chapter=int(c),
               start=lo, end=hi)
        for v in range(lo, hi + 1):
            r = verse(f"{b}.{c}.{v}")
            if r:
                g.edge(sid, "covers", r, "patterns")
        return sid

    for layer, kindkey in (("clauseforms.jsonl.gz", "form"),
                           ("formulaic.jsonl.gz", "pattern")):
        for d in rows(layer):
            k = d.get("kind")
            if k == kindkey:
                pid = d.get("id")
                if not pid:
                    continue
                g.node(f"form:{pid}", "pattern", layer.split(".")[0],
                       function=d.get("function"), roles=d.get("roles"),
                       formula=d.get("formula"),
                       occurrences=d.get("occurrences"),
                       runs=d.get("runs"), scope=d.get("scope"))
                pat += 1
            elif k == "instance_of":
                src, dst = d.get("src"), d.get("dst")
                if not (src and dst):
                    continue
                sid = span_node(src)
                g.edge(sid, "instance_of", f"form:{dst}", layer.split(".")[0])
                inst += 1
    print(f"  patterns (shapes)           {pat:>8,}")
    print(f"  pattern instances           {inst:>8,}", flush=True)

    # ---- passage-to-passage links, deduplicated across layers
    links = 0
    for layer, typ in (("allusions.jsonl.gz", "alludes_to"),
                       ("crosslinks.jsonl.gz", "crosslink"),
                       ("xrefs.jsonl.gz", "parallel")):
        for d in rows(layer):
            a = verse(d.get("ref") or d.get("from"))
            if not a:
                continue
            targets = d.get("links") or []
            if d.get("to"):
                targets = [{"ref": d["to"]}]
            for l in targets:
                b = verse(l.get("ref"))
                if b:
                    g.edge(a, typ, b, layer.split(".")[0], idf=l.get("idf"))
                    links += 1
    print(f"  passage links               {links:>8,}")

    # ---- semantic class, the WordNet overlay (never the floor)
    lexn = 0
    for d in rows("wordnet-map.jsonl.gz"):
        lem = d.get("lemma")
        if not lem or not d.get("reliable"):
            continue
        best = {}
        for m in d.get("map") or []:
            best[m.get("lexname")] = best.get(m.get("lexname"), 0) + (m.get("n") or 0)
        if not best:
            continue
        top = max(best, key=best.get)
        g.node(f"class:{top}", "semantic_class", "wordnet", name=top)
        g.node(f"name:{lem}", "named", "wordnet", name=lem)
        g.edge(f"name:{lem}", "has_class", f"class:{top}", "wordnet")
        lexn += 1
    print(f"  lemmas given a class        {lexn:>8,}")

    # ---- higher-level patterns, from tools/patternnodes.py
    #
    # The graph already held 35,613 `pattern` nodes and every one was
    # subsentence -- clause forms and predicate formulas. The kind and the
    # `instance_of` edge worked; nothing above the clause had used them.
    # These carry family, traits, instance counts and EVERY interest score,
    # because the measures disagree informatively and the reader is to pick
    # the sort order rather than have one chosen silently.
    pn = 0
    for d in rows("pattern-nodes.jsonl.gz"):
        if not d.get("id"):
            continue
        g.node(d["id"], "pattern", "patternnodes",
               family=d.get("family"), traits=d.get("traits"),
               form=d.get("form"), arc=d.get("arc"), books=d.get("books"),
               scores=d.get("scores"), level="section")
        pn += 1
    print(f"  higher-level patterns       {pn:>8,}")
    pe = 0
    for d in rows("pattern-edges.jsonl.gz"):
        if d.get("src") and d.get("dst"):
            # the edge carries the FILL -- how this instance realises the
            # form. A pattern node is a template; without the fill the graph
            # records only that a passage matched, not how.
            g.edge(d["src"], d.get("type") or "instance_of", d["dst"],
                   "patternnodes", fill=d.get("fill"))
            pe += 1
    print(f"  pattern + hierarchy edges   {pe:>8,}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    g = Graph()
    print("BUILDING\n")
    build(g)
    print(f"\nGRAPH\n  nodes {len(g.nodes):>10,}   edges {len(g.edges):>10,}")
    print("\n  nodes by kind")
    for k, n in g.layer_nodes.most_common():
        print(f"    {k:<18}{n:>10,}")
    print("\n  edges by type")
    et = collections.Counter(e["type"] for e in g.edges.values())
    for k, n in et.most_common(18):
        print(f"    {k:<18}{n:>10,}")
    multi = sum(1 for e in g.edges.values() if len(e["by"]) > 1)
    print(f"\n  edges attested by more than one layer: {multi:,}")
    # degree, computed in ONE pass. The first version of this line rebuilt
    # list(g.edges.values()) inside a per-node generator -- O(nodes x edges)
    # for a variable that was never printed. Dead code still costs.
    deg = collections.Counter()
    for e in g.edges.values():
        deg[e["src"]] += 1
        deg[e["dst"]] += 1
    iso = sum(1 for nid in g.nodes if deg[nid] == 0)
    print(f"  isolated nodes (no edge at all): {iso:,} "
          f"({100*iso/max(len(g.nodes),1):.1f}%)")
    if a.write:
        with gzip.open(OUT / "graph-nodes.jsonl.gz", "wt", encoding="utf-8") as f:
            f.write(json.dumps({"_note": "Assembled by tools/buildgraph.py from "
                                "the derived layers. No cross-verse identity is "
                                "invented; see the module header."}) + "\n")
            for n in g.nodes.values():
                f.write(json.dumps(n, ensure_ascii=False) + "\n")
        with gzip.open(OUT / "graph-edges.jsonl.gz", "wt", encoding="utf-8") as f:
            f.write(json.dumps({"_note": "Every edge lists the layer(s) that "
                                "licensed it in `by`."}) + "\n")
            for e in g.edges.values():
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"\nwrote out/graph-nodes.jsonl.gz and out/graph-edges.jsonl.gz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
