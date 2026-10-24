"""The relation vocabulary as RDF, for its namespace: bibleontology.org/ns/relation.

2026-10-11, on publishing the upper ontology: the relation vocabulary was
added next. Built here, not in the server (the
server runs without rdflib and yaml): reads ontology/schema/relationship_types.yaml
and writes out/ns/relation.ttl, which the server serves as Turtle.

Each type becomes a property with its label, the way it reads from the other
side, its category and the kinds it joins; symmetric and functional types say
so in OWL's terms. The types' `notes` are left out: they are guidance to the
extraction tools on how the graph is built, not part of the vocabulary.

    python tools/ns_relation.py
"""
from pathlib import Path
import json
import sys

import rdflib
import yaml
from rdflib import Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from ns_common import header, shapes_head  # noqa: E402

BASE = "https://bibleontology.org/ns/relation"
BOR = Namespace(BASE + "#")
BOM = "https://bibleontology.org/ns/meaning#"
# CATEGORIES THE YAML NAMES BUT DOES NOT LABEL (OWL evaluation Phase 0): the
# published file showed the raw ids "language" and "opposition" beside
# "Kinship"; and `specializes` (a pattern as a narrower form of another) had
# none. Labelled here, for the vocabulary only -- the app's grouping is its own
CAT_FALLBACK = {"language": "Language", "opposition": "What the text sets against it"}
TYPE_CAT_FALLBACK = {"specializes": "Patterns"}


def kind_classes():
    """A record's kind -> its class in the meaning vocabulary
    (bom:fromEntityType), where the kind maps to exactly one class."""
    mg = rdflib.Graph().parse(ROOT / "ontology" / "meaning" / "meaning.ttl", format="turtle")
    pairs = {}
    for c_, k_ in mg.subject_objects(URIRef(BOM + "fromEntityType")):
        pairs.setdefault(str(k_), set()).add(str(c_).rsplit("#", 1)[1])
    return {k_: next(iter(cs)) for k_, cs in pairs.items() if len(cs) == 1}


def shapes(spec=None, kc=None):
    """THE "ONE OF" CHECK (before 1.2.0; the committee's ontology expert): a
    relation whose end allows SEVERAL classes gets no rdfs:domain or range
    (two would mean both), so its list is published as a SHACL shape where a
    list means EITHER, as the structure's shapes already do: "the subject of
    'told' must be one of Person, Being, Group, Concept, Creature". An end
    with a kind no single class stands for is counted and left out, never
    guessed. -> (shapes graph, counts)"""
    spec = spec or yaml.safe_load((ROOT / "ontology/schema/relationship_types.yaml").read_text(encoding="utf-8"))
    kc = kc if kc is not None else kind_classes()
    SH = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    sh = rdflib.Graph()
    sh.bind("sh", SH); sh.bind("bor", BOR); sh.bind("bom", BOM)
    import collections as _co
    n = _co.Counter()
    for tid, t in sorted((spec.get("types") or {}).items()):
        for key, end, target in (("src_type", "subject", SH.targetSubjectsOf), ("dst_type", "object", SH.targetObjectsOf)):
            v = t.get(key)
            kinds = v if isinstance(v, list) else [v] if v else []
            classes = sorted({kc.get(k) for k in kinds} - {None})
            if len(classes) < 2:
                n["one class or none (a domain or range, or nothing)"] += 1
                continue
            if any(kc.get(k) is None for k in kinds):
                n[f"{end}: a kind with no single class (left out)"] += 1
                continue
            s = BOR[f"{tid}_{end}Shape"]
            sh.add((s, RDF.type, SH.NodeShape))
            sh.add((s, target, BOR[tid]))
            sh.add((s, SH.message, Literal(f"The {end} of {tid} must be one of: {', '.join(classes)}")))
            members = []
            for c in classes:
                b = rdflib.BNode()
                sh.add((b, SH["class"], URIRef(BOM + c)))
                members.append(b)
            lst = rdflib.BNode()
            rdflib.collection.Collection(sh, lst, members)
            sh.add((s, SH["or"], lst))
            n[f"{end} shapes"] += 1
    return sh, n


def main():
    spec = yaml.safe_load((ROOT / "ontology/schema/relationship_types.yaml").read_text(encoding="utf-8"))
    # one public definition per type, reviewed by hand (2026-10-14), kept apart
    # from the YAML's private notes
    defs = json.loads((ROOT / "ontology/schema/relation_definitions.json").read_text(encoding="utf-8"))["types"]
    missing = sorted(set(spec.get("types") or {}) - set(defs))
    if missing:
        sys.exit(f"relation types with no public definition: {missing}")
    cats = spec.get("categories") or {}
    g = rdflib.Graph()
    g.bind("bor", BOR); g.bind("owl", OWL); g.bind("dcterms", DCTERMS)
    onto = URIRef(BASE)
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, RDFS.label, Literal("Bible Ontology — relations")))
    g.add((onto, DCTERMS.title, Literal("Bible Ontology — relations")))
    g.add((onto, DCTERMS.creator, Literal("Doug Egge")))
    g.add((onto, DCTERMS.created, Literal("2026-10-11", datatype=XSD.date)))
    g.add((onto, RDFS.comment, Literal(
        "The controlled vocabulary of relations the Bible Ontology graph may assert: each reads "
        "'<source> <label> <target>', and every relation in the graph uses one of these types. "
        "Companion to https://bibleontology.org/ns/meaning.")))
    header(g, onto, BASE, "bor", OWL, DCTERMS, Literal, URIRef, XSD, RDFS)
    for p, lab in (("inverseLabel", "how the relation reads from the target's side"),
                   ("category", "the group a relation belongs to"),
                   ("sourceKind", "the kind of record a relation starts from"),
                   ("targetKind", "the kind of record a relation points to")):
        g.add((BOR[p], RDF.type, OWL.AnnotationProperty))
        g.add((BOR[p], RDFS.label, Literal(lab)))
    # a record's kind -> its class in the meaning vocabulary (bom:fromEntityType)
    KIND_CLASS = kind_classes()
    import collections as _co
    ranged = _co.Counter()
    for tid, t in (spec.get("types") or {}).items():
        p = BOR[tid]
        g.add((p, RDF.type, OWL.ObjectProperty))
        g.add((p, RDFS.isDefinedBy, onto))
        if t.get("label"):
            g.add((p, RDFS.label, Literal(t["label"])))
        if t.get("inverse") and t.get("inverse") != t.get("label"):
            g.add((p, BOR.inverseLabel, Literal(t["inverse"])))
        g.add((p, SKOS.definition, Literal(defs[tid]["definition"])))
        if t.get("category"):
            c = cats.get(t["category"])
            name = c.get("label") if isinstance(c, dict) and c.get("label") \
                else CAT_FALLBACK.get(t["category"], t["category"])
            g.add((p, BOR.category, Literal(name)))
        elif tid in TYPE_CAT_FALLBACK:
            g.add((p, BOR.category, Literal(TYPE_CAT_FALLBACK[tid])))
        if t.get("symmetric") and tid == "possibly_same_as":
            # a reading's symmetry, never an identity (the reasoning policy)
            g.add((p, RDFS.comment, Literal(
                "A reading that two records may be one person, with the case for and against; "
                "never an identity, and never to be mapped to owl:sameAs.")))
        for key, prop, owlp in (("src_type", BOR.sourceKind, RDFS.domain), ("dst_type", BOR.targetKind, RDFS.range)):
            v = t.get(key)
            kinds = v if isinstance(v, list) else [v] if v else []
            for k in kinds:
                g.add((p, prop, Literal(k)))
            # A REAL DOMAIN AND RANGE where every allowed kind is one class of
            # the meaning vocabulary (plan 8.1e item 4; the committee's
            # ontology expert: 0 domains or ranges in /ns/relation). Several
            # classes get none: in RDFS two domains mean BOTH, not either; the
            # kinds stay listed, and the closed-world check enforces them
            classes = {KIND_CLASS.get(k) for k in kinds}
            if kinds and len(classes) == 1 and None not in classes:
                g.add((p, owlp, URIRef(BOM + classes.pop())))
                ranged[owlp] += 1
        if t.get("symmetric"):
            g.add((p, RDF.type, OWL.SymmetricProperty))
        if t.get("functional"):
            g.add((p, RDF.type, OWL.FunctionalProperty))
    out = ROOT / "out" / "ns" / "relation.ttl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(g.serialize(format="turtle"), encoding="utf-8")
    sh, n = shapes(spec, KIND_CLASS)
    (out.parent / "relation-shapes.ttl").write_text(shapes_head("the relations' 'one of' shapes")
                                                     + sh.serialize(format="turtle"), encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {len(spec.get('types') or {})} relation types, {len(g)} triples; "
          f"domains {ranged[RDFS.domain]}, ranges {ranged[RDFS.range]}; "
          f"one-of shapes: {n['subject shapes']} subject, {n['object shapes']} object")


if __name__ == "__main__":
    main()
