"""The structure layer as RDF, for its namespace: bibleontology.org/ns/structure.

2026-10-11: structure was added next -- the third part of the upper
ontology (with /ns/meaning and /ns/relation). Reads ontology/kinds.json and
writes out/ns/structure.ttl, which the server serves as Turtle.

Published: each class (with its parent, layer, status and definition) and each
relation (with its domain and range, layer, status, definition and how it
reads). Left out: the passage log, each term's history ("was", "established")
and the matching rules -- they record how the ontology was built, not what it
says.

PHASE 0 OF THE OWL EVALUATION (docs/review/OWL-EVALUATION.md;
every item approved 2026-10-13):
  - ONE RANGE, ONE DOMAIN. Twenty relations listed several kinds as their
    range, and RDFS reads several range triples as ALL AT ONCE: a subject in
    Psalm 23:2 was entailed to be an Author, a Composite and a Word together
    (a known trap of RDFS ranges, which the N.4 entry had already decided
    against). Now the one kind they all are (their least common superclass,
    tools/ontology.py's common_kind), and the full list as a SHACL `sh:or` in
    out/ns/shapes.ttl, where a list means EITHER.
  - WITHDRAWN AND SUPERSEDED TERMS ARE MARKED owl:deprecated, their addresses
    kept.
  - The layer kinds.json calls "Meaning" is published as "Upper
    (language-independent)": the sibling ontology is /ns/meaning, and every
    structure term read as belonging to it.
  - The version block and the reasoning policy (tools/ns_common.py).

    python tools/ns_structure.py
"""
from pathlib import Path
import json
import re
import sys

import rdflib
from rdflib import BNode, Literal, Namespace, URIRef
from rdflib.collection import Collection
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS, XSD

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from ns_common import header, shapes_head  # noqa: E402

BASE = "https://bibleontology.org/ns/structure"
BOS = Namespace(BASE + "#")
SH = Namespace("http://www.w3.org/ns/shacl#")
LAYER_LABEL = {"Meaning": "Upper (language-independent)"}


def public(text):
    """A definition as published: the sentences that credit who decided it
    (those that name the owner as the source) are build history, kept in
    kinds.json; the ontology's creator is named once, in its header."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(p for p in parts if not re.search(r"\bDoug\b", p)).strip()


def kinds_of(v):
    return [c for c in (v if isinstance(v, list) else [v] if v else [])
            if isinstance(c, str) and c.isidentifier()]


def main():
    k = json.loads((ROOT / "ontology/kinds.json").read_text(encoding="utf-8"))
    parent = {c["id"]: c.get("parent") for c in k.get("classes") or []}

    def lineage(c):
        out = []
        while c and c not in out:
            out.append(c)
            c = parent.get(c)
        return out

    def common(cs):
        chains = [lineage(c) for c in cs]
        if not chains:
            return None
        shared = set(chains[0]).intersection(*chains[1:])
        return next((c for c in chains[0] if c in shared), None)

    g = rdflib.Graph()
    sh = rdflib.Graph()
    for p, ns in (("bos", BOS), ("owl", OWL), ("dcterms", DCTERMS), ("skos", SKOS)):
        g.bind(p, ns)
    sh.bind("sh", SH); sh.bind("bos", BOS)
    onto = URIRef(BASE)
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, RDFS.label, Literal("Bible Ontology — structure")))
    g.add((onto, DCTERMS.title, Literal("Bible Ontology — structure")))
    g.add((onto, DCTERMS.creator, Literal("Doug Egge")))
    g.add((onto, DCTERMS.created, Literal("2026-10-11", datatype=XSD.date)))
    g.add((onto, RDFS.comment, Literal(
        "How the text is built: clauses, what they assert and with what force, and how they group "
        "into turns, scenes and larger units. Shares ids with the meaning layer "
        "(https://bibleontology.org/ns/meaning) and never merges with it; the relations between "
        "records are at https://bibleontology.org/ns/relation. Where a relation joins one of several "
        "kinds, its domain or range here is the kind they all are, and the shapes at "
        "https://bibleontology.org/ns/shapes list which ones.")))
    header(g, onto, BASE, "bos", OWL, DCTERMS, Literal, URIRef, XSD, RDFS)
    for p, lab in (("layer", "the layer a term belongs to"),
                   ("status", "built, proposed, deferred (built before, not by the current builder; "
                              "kept for re-entry), withdrawn or superseded, as the term stands"),
                   ("reads", "how a relation reads as a sentence")):
        g.add((BOS[p], RDF.type, OWL.AnnotationProperty))
        g.add((BOS[p], RDFS.label, Literal(lab)))
    layers = {l["id"]: l.get("label") or l["id"] for l in k.get("layers") or []}

    def common_props(s, x):
        g.add((s, RDFS.isDefinedBy, onto))
        if x.get("label"):
            g.add((s, RDFS.label, Literal(x["label"])))
        if x.get("definition"):
            g.add((s, SKOS.definition, Literal(public(x["definition"]))))
        if x.get("layer"):
            lab = layers.get(x["layer"], x["layer"])
            g.add((s, BOS.layer, Literal(LAYER_LABEL.get(lab, lab))))
        if x.get("status"):
            g.add((s, BOS.status, Literal(x["status"])))
            if x["status"] in ("withdrawn", "superseded"):
                g.add((s, OWL.deprecated, Literal(True)))

    for c in k.get("classes") or []:
        s = BOS[c["id"]]
        g.add((s, RDF.type, OWL.Class))
        if c.get("parent"):
            g.add((s, RDFS.subClassOf, BOS[c["parent"]]))
        common_props(s, c)
    multi = 0
    for r in k.get("relations") or []:
        s = BOS[r["id"]]
        g.add((s, RDF.type, OWL.ObjectProperty))
        for key, prop, target in (("from", RDFS.domain, SH.targetSubjectsOf),
                                  ("to", RDFS.range, SH.targetObjectsOf)):
            cs = kinds_of(r.get(key))
            if len(cs) == 1:
                g.add((s, prop, BOS[cs[0]]))
            elif len(cs) > 1:
                multi += 1
                lcs = common(cs)
                if lcs:
                    g.add((s, prop, BOS[lcs]))
                # the full list, where a list means EITHER
                shape = BOS[f"{r['id']}_{'subject' if key == 'from' else 'object'}Shape"]
                sh.add((shape, RDF.type, SH.NodeShape))
                sh.add((shape, target, s))
                head = BNode()
                Collection(sh, head, [_cls(sh, BOS[c]) for c in cs])
                sh.add((shape, SH["or"], head))
                sh.add((shape, SH.message, Literal(
                    f"{'Subject' if key == 'from' else 'Object'} of {r['id']} must be one of: {', '.join(cs)}")))
        if r.get("reads"):
            g.add((s, BOS.reads, Literal(r["reads"])))
        # UNDER ITS PARENT (plan 8.1b): a query for bos:clause_link finds
        # `when`, `purpose`, `content` ..., as a query for a prepositional
        # family finds its types. Unwritten until 2026-10-17, so the published
        # clause links did not say they were clause links.
        if r.get("parent"):
            g.add((s, RDFS.subPropertyOf, BOS[r["parent"]]))
        common_props(s, r)
    # MARKS (1.2.0): a value on a clause or on a link, not a link of its own
    # ("presented", a clause a 'behold' introduces; "indirect", reported speech)
    rel_ids = {r["id"] for r in k.get("relations") or []}
    for a in k.get("attributes") or []:
        s = BOS[a["id"]]
        g.add((s, RDF.type, OWL.DatatypeProperty))
        g.add((s, RDFS.range, XSD.boolean))
        if a.get("on") and a["on"] not in rel_ids:
            g.add((s, RDFS.domain, BOS[a["on"]]))
        elif a.get("on"):
            # a mark on a link: the link is a statement, so no class domain
            g.add((s, RDFS.comment, Literal(f"Marks a {a['on']} link.")))
        common_props(s, a)
    # WHAT IT DOES NOT ATTEMPT (1.2.0): published, so a gap reads as a decision
    for x in (k.get("scope") or {}).get("excludes") or []:
        g.add((onto, SKOS.scopeNote, Literal(public(x))))
    prep(g, onto, rel_ids, common_props)
    # A SUB-PROPERTY INHERITS ITS PARENT'S DOMAIN AND RANGE (plan 8.1b). If the
    # parent's is narrower, a reasoner types the child's ends as the parent's
    # classes: on 2026-10-18 `content`, `fulfils`, `part`, `item` and
    # `imperative_qualifier` reached a Unit under parents whose range was
    # Clause, so a speech's content would have been entailed a clause when it
    # is a group. Refused here, before anything is written.
    def supers(c):
        out_, todo = set(), [c]
        while todo:
            x = todo.pop()
            if x not in out_:
                out_.add(x)
                todo += list(g.objects(x, RDFS.subClassOf))
        return out_
    escapes = []
    for child, par in g.subject_objects(RDFS.subPropertyOf):
        for prop in (RDFS.domain, RDFS.range):
            pc, cc = g.value(par, prop), g.value(child, prop)
            if pc is not None and (cc is None or pc not in supers(cc)):
                escapes.append(f"{child.split('#')[-1]} {prop.split('#')[-1]} {cc and cc.split('#')[-1]} "
                               f"is not within its parent {par.split('#')[-1]}'s {pc.split('#')[-1]}")
    if escapes:
        raise SystemExit("not written: a sub-property escapes its parent\n  " + "\n  ".join(escapes))
    out = ROOT / "out" / "ns" / "structure.ttl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(g.serialize(format="turtle"), encoding="utf-8")
    (ROOT / "out" / "ns" / "structure-shapes.ttl").write_text(shapes_head("the structure's shapes")
                                                              + sh.serialize(format="turtle"), encoding="utf-8")
    print(f"{out.relative_to(ROOT)}: {len(k.get('classes') or [])} classes, "
          f"{len(k.get('relations') or [])} relations, {len(g)} triples; "
          f"{multi} multi-kind domains/ranges -> one kind + a shape")


# A PREPOSITIONAL TYPE THAT SHARES A CLAUSE LINK'S NAME is the same term, so
# one query finds it at both levels: `means` (2026-10-17, plan 1.35:
# the same name as the prepositional type), and `purpose` (2026-10-17:
# shared like means), and `partitive`, a person who is one of a group
# (2026-10-18: partitive chosen). Any other collision with a structure term is
# refused, never merged by accident: a different meaning needs a different
# address (the prepositional `basis` became `rests_on`, the same day).
SHARED = {"means", "purpose", "partitive"}


def prep(g, onto, taken, common_props):
    """The prepositional relations (plan 2.13): what a phrase adds to the
    action or noun it attaches to. Two levels, families over types, each type
    a sub-property of its family (2026-10-17: families plus types). From
    ontology/schema/prep_relations.json."""
    p = json.loads((ROOT / "ontology/schema/prep_relations.json").read_text(encoding="utf-8"))
    top = BOS["prep_relation"]
    g.add((top, RDF.type, OWL.ObjectProperty))
    common_props(top, {"label": "prepositional relation", "layer": "lexical", "status": "built",
                       "definition": "What a prepositional phrase adds to the action or noun it "
                                     "attaches to, read from the original-language trees: named by "
                                     "a rule where the preposition and its object settle it, "
                                     "otherwise a credited reading. A type is named only where it is "
                                     "sure; where only the family is sure, the family is named."})
    clash = []
    for fam, f in p["families"].items():
        fs = BOS[fam]
        g.add((fs, RDF.type, OWL.ObjectProperty))
        g.add((fs, RDFS.subPropertyOf, top))
        common_props(fs, {"label": fam.replace("_", " "), "layer": "lexical", "status": "built",
                          "definition": f["means"][0].upper() + f["means"][1:] + "."})
        for t, d in f["types"].items():
            if t in taken and t not in SHARED:
                clash.append(t)
                continue
            ts = BOS[t]
            g.add((ts, RDFS.subPropertyOf, fs))
            if t in SHARED:
                continue        # its own entry carries the label and definition
            g.add((ts, RDF.type, OWL.ObjectProperty))
            common_props(ts, {"label": t, "layer": "lexical", "status": "built",
                              "definition": d[0].upper() + d[1:] + "."})
    if clash:
        print(f"  HELD, a name already used by a structure term with another meaning: "
              f"{', '.join(clash)} (needs its own name, or a ruling that it is the same term)")


def _cls(g, c):
    b = BNode()
    g.add((b, SH["class"], c))
    return b


if __name__ == "__main__":
    main()
