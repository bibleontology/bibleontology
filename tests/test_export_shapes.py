"""The published shapes pass on the published data (the code review, 2026-10-22).

A semantic-web reader's first move is to load the exports and run the shapes
the exports name ("Checks: .../ns/shapes"). On 2026-10-22 that failed 2,828
times, because the entities export left out 3,116 records the claims name
and typed 410 records with a class whose shape the file could not meet. This
checks, in the published files:

  1. Every record a claim names (subject, object, claimant) has a label in
     entities.ttl.gz.
  2. out/ns/shapes.ttl and relation-shapes.ttl report no violation over the
     claims (default graph), the entities and the meaning vocabulary.

Planted: a claim naming a record with no label, and a record typed
bom:Predication with nothing a predication needs, must each be caught.

    python tests/test_export_shapes.py
"""
import gzip
import sys
from pathlib import Path

import pyshacl
import rdflib

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://bibleontology.org"
C = rdflib.Namespace(SITE + "/ns/claim#")
SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")


def load():
    ds = rdflib.Dataset()
    with gzip.open(ROOT / "out" / "export" / "claims.trig.gz", "rt", encoding="utf-8") as f:
        ds.parse(data=f.read(), format="trig")
    g = rdflib.Graph()
    for t in ds.default_graph:
        g.add(t)
    with gzip.open(ROOT / "out" / "export" / "entities.ttl.gz", "rt", encoding="utf-8") as f:
        g.parse(data=f.read(), format="turtle")
    g.parse(ROOT / "out" / "ns" / "meaning.ttl")
    return g


def unlabelled(g):
    named = {o for p in (C.subject, C.object, C.claimedBy) for o in g.objects(None, p)
             if str(o).startswith(SITE + "/e/")}
    return sorted(str(x) for x in named if g.value(x, rdflib.RDFS.label) is None)


def violations(g, shapes):
    _, rg, _ = pyshacl.validate(g, shacl_graph=shapes, inference="none")
    return list(rg.subjects(rdflib.RDF.type, SH.ValidationResult))


def main():
    g = load()
    shapes = rdflib.Graph().parse(ROOT / "out" / "ns" / "shapes.ttl").parse(ROOT / "out" / "ns" / "relation-shapes.ttl")
    fails = []
    u = unlabelled(g)
    if u:
        fails.append(f"{len(u)} records named in claims have no label in entities.ttl.gz, e.g. {u[:3]}")
    v = violations(g, shapes)
    if v:
        fails.append(f"the published shapes report {len(v)} violations on the published data")
    # PLANTED, each on a copy
    caught = 0
    g1 = rdflib.Graph() + g
    c = rdflib.URIRef(SITE + "/claim/planted")
    g1.add((c, C.subject, rdflib.URIRef(SITE + "/e/no_such_record_planted")))
    if unlabelled(g1):
        caught += 1
    else:
        fails.append("planted: a claim naming an unlabelled record was not caught")
    g2 = rdflib.Graph() + g
    g2.add((rdflib.URIRef(SITE + "/e/planted_predication"), rdflib.RDF.type,
            rdflib.URIRef(SITE + "/ns/meaning#Predication")))
    if violations(g2, shapes):
        caught += 1
    else:
        fails.append("planted: a bare bom:Predication was not caught")
    for f in fails:
        print("FAIL " + f)
    print(f"export shapes: {len(u)} unlabelled records named, {len(v)} violations; "
          f"planted faults caught: {caught} of 2; {len(fails)} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
