"""The relation vocabulary's "one of" shapes hold on the graph (before 1.2.0).

tools/ns_relation.py publishes, for every relation whose end allows several
classes, a SHACL shape where a list means either ("the subject of 'told' must be
one of Animal, Concept, Group, PersonalBeing"). This builds the graph as those
shapes see it -- every record typed by its kind's class, every relation the
store holds -- validates it, and plants two faults that must be caught.

    python tests/test_relation_shapes.py          (preflight runs it so)
"""
import json
import sys
from pathlib import Path

import pyshacl
import rdflib
from rdflib import RDF, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ns_relation as R  # noqa: E402

E = "https://bibleontology.org/e/"
BOM = R.BOM
BOR = R.BOR


def data(kc):
    """The records' classes from the PUBLISHED file (out/export/entities.ttl.gz,
    tools/export_entities.py), as an outsider would run the shapes, and the
    relations from the store."""
    import gzip
    types = {}
    g = rdflib.Graph()
    g.parse(data=gzip.open(ROOT / "out" / "export" / "entities.ttl.gz", "rt", encoding="utf-8").read(), format="turtle")
    LEG = URIRef(BOM + "legacyType")
    for s, k in g.subject_objects(LEG):
        types[str(s)[len(E):]] = str(k)
    # the four divine records publish no legacy type (P11): their kind is read
    # from the store, so their relations are still checked
    sys.path.insert(0, str(ROOT / "tools"))
    from export_entities import NO_LEGACY
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip() and json.loads(line)["id"] in NO_LEGACY:
            types[json.loads(line)["id"]] = json.loads(line).get("type")
    # a class the entities file leaves off because it cannot carry what that
    # class's shape needs (export_entities.UNSHAPED, 2026-10-22: Predication)
    # is still the record's class in the store, so its relations are checked
    # against it, as the four divine records' are
    from export_entities import UNSHAPED
    for s, k in list(g.subject_objects(LEG)):
        if kc.get(str(k)) in UNSHAPED:
            g.add((s, RDF.type, URIRef(BOM + kc[str(k)])))
    g.remove((None, LEG, None))
    g.remove((None, rdflib.RDFS.label, None))
    n = 0
    for p in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
        for line in open(p, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("held") or r["src"] not in types or r["dst"] not in types:
                continue
            g.add((URIRef(E + r["src"]), BOR[r["type"]], URIRef(E + r["dst"])))
            n += 1
    return g, types, n


def main():
    kc = R.kind_classes()
    sh, counts = R.shapes(kc=kc)
    g, types, n = data(kc)
    fails = []
    # THE PUBLISHED FILE MUST BE THE STORE'S (the stale-ties lesson, 2026-10-20):
    # every record in the store is in it, with the kind it has now
    store = {json.loads(x)["id"]: json.loads(x).get("type") for x in
             (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()}
    stale = [i for i, k in store.items() if types.get(i) != k]
    if stale:
        fails.append(f"out/export/entities.ttl.gz is behind the store ({len(stale)} records, e.g. {stale[:3]}): "
                     "python tools/export_entities.py")
    ok, _, text = pyshacl.validate(g, shacl_graph=sh, inference="none")
    if not ok:
        fails.append("the graph does not conform:\n" + text[:1500])
    # PLANTED: a place as the subject of 'told' (one of Person, Being, ...),
    # and a person as the object of 'in_theme'-like one-of ends
    shaped = [s for s in sh.subjects(RDF.type, rdflib.URIRef("http://www.w3.org/ns/shacl#NodeShape"))]
    told = BOR["told"]
    place = next(i for i, t in types.items() if t == "place" and kc.get("place"))
    person = next(i for i, t in types.items() if t == "person")
    g2 = rdflib.Graph() + g
    g2.add((URIRef(E + place), told, URIRef(E + person)))
    if pyshacl.validate(g2, shacl_graph=sh, inference="none")[0]:
        fails.append("planted: a place telling a person was not caught")
    # a record whose class is not in the list, on an object shape
    obj = next((s for s in shaped if str(s).endswith("_objectShape")), None)
    if obj is not None:
        prop = sh.value(obj, rdflib.URIRef("http://www.w3.org/ns/shacl#targetObjectsOf"))
        listed = set()
        for b in rdflib.collection.Collection(sh, sh.value(obj, rdflib.URIRef("http://www.w3.org/ns/shacl#or"))):
            listed.add(str(sh.value(b, rdflib.URIRef("http://www.w3.org/ns/shacl#class"))).rsplit("#", 1)[1])
        wrong = next((k for k, c in kc.items() if c not in listed and any(t == k for t in types.values())), None)
        if wrong:
            rec = next(i for i, t in types.items() if t == wrong)
            g3 = rdflib.Graph() + g
            g3.add((URIRef(E + person), prop, URIRef(E + rec)))
            if pyshacl.validate(g3, shacl_graph=sh, inference="none")[0]:
                fails.append(f"planted: a {wrong} as the object of {str(prop).rsplit('#', 1)[1]} was not caught")
    print(f"relation shapes: {counts['subject shapes']} subject and {counts['object shapes']} object 'one of' shapes; "
          f"{n:,} relations conform: {ok}; planted faults among the checks; {len(fails)} failures")
    for f in fails:
        print("FAIL " + f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
