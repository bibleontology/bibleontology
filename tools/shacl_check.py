"""Run the SHACL shapes against a passage of the graph, exported as RDF, and
compare with tools/ontology.py's own domain-and-range check. Plan N.4.

The shapes (out/ontology-shapes.ttl) are meant to BE the Python check in the
standard's terms. This proves it on real data rather than asserting it: both
are run on the same nodes and edges, clean and then with faults planted, and
must report the same edges.

Run:  python tools/shacl_check.py [Psa.23]      (a book.chapter prefix)
"""
import gzip
import json
import sys
from pathlib import Path
from urllib.parse import quote

import rdflib
from pyshacl import validate
from rdflib import RDF, URIRef

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ontology as O                                      # noqa: E402
import ontology_rdf as R                                  # noqa: E402

DATA = "https://bibleontology.org/id/"


def node_iri(nid):
    return URIRef(DATA + quote(nid.replace("#", "/"), safe="/"))


def load_passage(prefix):
    onto = O.load()
    nm, em = O._node_matchers(onto), O._edge_matchers(onto)
    rels = {r["id"]: r for r in onto["relations"]}
    edges = []
    for line in gzip.open(ROOT / "out" / "placeholder-edges.jsonl.gz", "rt",
                          encoding="utf-8"):
        e = json.loads(line)
        if not (e.get("ref") or "").startswith(prefix + "."):
            continue
        k = O.classify_edge(e, em)
        r = rels.get(k) or {}
        # as the Python check: declared ends, not the superseded flat layer
        if k and r.get("from") and r["status"] != "superseded":
            edges.append((k, e))
    want = {e.get("src") for _, e in edges} | {e.get("dst") for _, e in edges}
    kinds = {}
    for line in gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if d.get("id") in want:
            kinds[d["id"]] = O.classify_node(d, nm)
    return onto, edges, kinds


def python_check(onto, edges, kinds):
    rels = {r["id"]: r for r in onto["relations"]}
    bad = set()
    for k, e in edges:
        r = rels[k]
        if not (O._within(kinds.get(e["src"]), r["from"], onto)
                and O._within(kinds.get(e["dst"]), r["to"], onto)):
            bad.add((k, e["src"], e["dst"]))
    return bad


def shacl_check(onto, edges, kinds, ont_ttl, shapes_ttl, census):
    home = {x["id"]: x for x in onto["classes"] + onto["relations"]}

    def iri(kind):
        x = home[kind]
        return URIRef(R.NS[R._lang_of(x, census)] + kind)
    g = rdflib.Graph()
    for nid, k in kinds.items():
        if k:
            g.add((node_iri(nid), RDF.type, iri(k)))
    for k, e in edges:
        g.add((node_iri(e["src"]), iri(k), node_iri(e["dst"])))
    ont = rdflib.Graph().parse(data=ont_ttl, format="turtle")
    shapes = rdflib.Graph().parse(data=shapes_ttl, format="turtle")
    # NO INFERENCE. First run with inference="rdfs" missed half the planted
    # faults: `rdfs:domain st:Clause` let the reasoner CONCLUDE that a word
    # asserting a content is a Clause, and the shape then passed — RDFS
    # domain/range are inference, not constraint, exactly as the export's
    # docstring warns. sh:class walks rdfs:subClassOf in the data graph by
    # itself, so the ontology is mixed in as data and no reasoner is run.
    ok, report, _ = validate(g, shacl_graph=shapes, ont_graph=ont,
                             inference="none", meta_shacl=True)
    # which edges the report names: a focus node that fails a shape
    bad = set()
    SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    for res in report.subjects(RDF.type, SH.ValidationResult):
        focus = report.value(res, SH.focusNode)
        shape = str(report.value(res, SH.sourceShape))
        rid = shape.rsplit("#", 1)[-1]
        side = "Domain" if rid.endswith("Domain") else "Range"
        rid = rid[: -len(side)]
        for k, e in edges:
            end = e["src"] if side == "Domain" else e["dst"]
            if k == rid and node_iri(end) == focus:
                bad.add((k, e["src"], e["dst"]))
    return ok, bad, len(g)


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else "Psa.23"
    onto, edges, kinds = load_passage(prefix)
    census = O.census()
    ont_ttl, shapes_ttl = R.build(onto, census)
    print(f"{prefix}: {len(edges)} edges, {len(kinds)} nodes")

    py = python_check(onto, edges, kinds)
    ok, sh, n = shacl_check(onto, edges, kinds, ont_ttl, shapes_ttl, census)
    print(f"clean     python {len(py)} outside   shacl {len(sh)} outside   "
          f"({n} data triples; conforms={ok})   same: {py == sh}")

    # PLANT FAULTS: the check has to fail where the Python check fails
    planted = []
    for k, e in edges:
        if k == "s" and len(planted) < 2:
            # a subject that is a Content, not a Word or Author
            ct = e["src"]
            planted.append(("s", dict(e, dst=ct)))
        if k == "asserts" and len(planted) < 4 and len(planted) >= 2:
            # an assertion whose source is a word, not a Clause
            wd = next(d for kk, d in ((kk, x["dst"]) for kk, x in edges
                                      if kk == "s")
                      if kinds.get(d) == "Word")
            planted.append(("asserts", dict(e, src=wd)))
    edges2 = edges + planted
    py2 = python_check(onto, edges2, kinds)
    ok2, sh2, _ = shacl_check(onto, edges2, kinds, ont_ttl, shapes_ttl,
                              census)
    print(f"planted {len(planted)}  python {len(py2)} outside   shacl "
          f"{len(sh2)} outside   (conforms={ok2})   same: {py2 == sh2}")
    for x in sorted(py2 ^ sh2):
        print("  differs:", x)
    return 0 if (py == sh and py2 == sh2 and len(py2) == len(planted)) else 1


if __name__ == "__main__":
    sys.exit(main())
