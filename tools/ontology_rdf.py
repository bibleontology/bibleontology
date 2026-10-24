"""ontology/kinds.json exported as RDFS + SKOS (what the kinds are) and SHACL
(what the check enforces). Plan N.4.

2026-09-25: even without going to OWL, RDFS was to be adopted (RDFS + SHACL
sounds powerful). The JSON stays the source; this is a view of
it for readers who work in the standard tools (Protégé, TopBraid, pySHACL).

NAMESPACES — one per ontology, pathed to mirror the layering (sub-namespaces
accommodate the multiple ontologies):

    https://bibleontology.org/ns/structure#          upper layer
    https://bibleontology.org/ns/lang/hebrew#        language layer, Hebrew
    https://bibleontology.org/ns/lang/greek#         language layer, Greek
    https://bibleontology.org/ns/lang#               language layer, shared
    https://bibleontology.org/ns/words#              lexical layer
    https://bibleontology.org/ns/shapes#             the SHACL checks
    https://bibleontology.org/ns/meta#               our annotations

The path is for people. IRIs are opaque to machines, so a layer's place is
stated as a triple (meta:over), never left to the path. Term IRIs carry no
version: the documents are versioned, the terms are not.

Two semantic differences the export must respect, found by reading the
standards rather than their names:
  * rdfs:domain / rdfs:range are INFERENCE, not constraint — they would
    "explain" a wrong edge instead of failing it. The constraint goes in
    SHACL (sh:class), which is what tools/ontology.py check already does.
  * two rdfs:range statements mean BOTH; our list ends mean EITHER. A list
    end is exported to RDFS as its nearest common superclass, and to SHACL
    as sh:or.

Run:  python tools/ontology_rdf.py      → out/ontology.ttl, out/ontology-shapes.ttl
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ontology as O                                      # noqa: E402

BASE = "https://bibleontology.org/ns/"
NS = {
    "upper": BASE + "structure#",
    "lexical": BASE + "words#",
    "language": BASE + "lang#",
    "hebrew": BASE + "lang/hebrew#",
    "greek": BASE + "lang/greek#",
}
SH_NS = BASE + "shapes#"
META = BASE + "meta#"
PREFIX = {"upper": "st", "lexical": "w", "language": "lang",
          "hebrew": "heb", "greek": "grc"}


def lit(s):
    """A Turtle string literal, long form when it holds a newline or quote."""
    s = str(s)
    if "\n" in s or '"' in s:
        return '"""' + s.replace("\\", "\\\\").replace('"""', '\\"\\"\\"') \
            + '"""'
    return '"' + s.replace("\\", "\\\\") + '"'


def _lang_of(item, census):
    """A language-layer relation belongs to the one language it occurs in,
    or to the shared language namespace if it occurs in both."""
    if item["layer"] != "language":
        return item["layer"]
    langs = {k for k, v in (census.get("by_lang", {}).get(item["id"]) or
                            {}).items() if v and k in ("hebrew", "greek")}
    return langs.pop() if len(langs) == 1 else "language"


def build(onto, census):
    home = {}                                    # kind id -> prefixed name
    for x in onto["classes"] + onto["relations"]:
        home[x["id"]] = f'{PREFIX[_lang_of(x, census)]}:{x["id"]}'

    def ref(kind):
        return home.get(kind, f"st:{kind}")

    def common(ends):
        """Nearest common superclass of a list end, for rdfs:range."""
        if not isinstance(ends, list):
            return ends
        return O.common_kind(ends, onto) if hasattr(O, "common_kind") \
            else "Unit"

    head = [f"@prefix {p}: <{NS[k]}> ." for k, p in PREFIX.items()]
    head += [f"@prefix meta: <{META}> .",
             "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
             "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
             "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
             "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
             "@prefix dcterms: <http://purl.org/dc/terms/> .", ""]
    out = list(head)

    # the ontologies themselves, and how they layer
    out.append(f"<{NS['upper']}> a owl:Ontology ;\n"
               f"  rdfs:label {lit('Bible structure ontology')} ;\n"
               f"  dcterms:source {lit('ontology/kinds.json')} ;\n"
               f"  rdfs:comment {lit(onto.get('_what', ''))} .")
    for k in ("language", "hebrew", "greek", "lexical"):
        over = "upper" if k in ("language", "lexical") else "language"
        out.append(f"<{NS[k]}> a owl:Ontology ;\n"
                   f"  meta:over <{NS[over]}> .")
    # our annotation properties, declared so a reader knows them
    for p, what in (("status", "built | proposed | superseded | withdrawn "
                     "— a fact, checked against the graph"),
                    ("established", "the verse and words that made the kind "
                     "necessary"),
                    ("falsifiedBy", "what would show the kind wrong"),
                    ("withdrawnBecause", "why a kind was reversed; kept so it "
                     "is not re-proposed"),
                    ("layer", "which layer of the model the kind is in"),
                    ("over", "this ontology is a layer over that one"),
                    ("rst", "the Rhetorical Structure Theory relation this "
                     "maps to"),
                    ("rstFit", "exact | close | none"),
                    ("reads", "the relation read as a sentence")):
        out.append(f"meta:{p} a owl:AnnotationProperty ;\n"
                   f"  rdfs:comment {lit(what)} .")
    out.append("")

    rst = ((onto.get("mappings") or {}).get("rst") or {}).get("relations", {})

    def ann(x):
        a = [f"  rdfs:label {lit(x.get('label', x['id']))}",
             f"  meta:status {lit(x['status'])}",
             f"  meta:layer {lit(x['layer'])}"]
        if x.get("definition"):
            a.append(f"  skos:definition {lit(x['definition'])}")
        est = x.get("established")
        if isinstance(est, dict):
            a.append("  meta:established " + lit(
                f'{est.get("ref", "")} {est.get("date", "")}: '
                f'{est.get("quote") or est.get("note") or ""}'.strip()))
        if x.get("falsified_by"):
            a.append(f"  meta:falsifiedBy {lit(x['falsified_by'])}")
        if x.get("withdrawn"):
            a.append(f"  meta:withdrawnBecause {lit(x['withdrawn'])}")
        if x["status"] == "withdrawn":
            a.append("  owl:deprecated true")
        if x.get("reads"):
            a.append(f"  meta:reads {lit(x['reads'])}")
        m = rst.get(x["id"])
        if m:
            if m.get("rst"):
                a.append(f"  meta:rst {lit(m['rst'])}")
            a.append(f"  meta:rstFit {lit(m['fit'])}")
            if m.get("note"):
                a.append(f"  rdfs:comment {lit(m['note'])}")
        return a

    for c in onto["classes"]:
        a = [f"{ref(c['id'])} a rdfs:Class"] + ann(c)
        if c.get("parent"):
            a.append(f"  rdfs:subClassOf {ref(c['parent'])}")
        out.append(" ;\n".join(a) + " .")
    out.append("")
    for r in onto["relations"]:
        a = [f"{ref(r['id'])} a rdf:Property"] + ann(r)
        if r.get("parent"):
            a.append(f"  rdfs:subPropertyOf {ref(r['parent'])}")
        if r.get("from"):
            a.append(f"  rdfs:domain {ref(common(r['from']))}")
        if r.get("to"):
            a.append(f"  rdfs:range {ref(common(r['to']))}")
        out.append(" ;\n".join(a) + " .")
    ttl = "\n".join(out) + "\n"

    # ---- SHACL: the checks tools/ontology.py makes, as shapes -------------
    sh = [f"@prefix sh: <http://www.w3.org/ns/shacl#> .",
          f"@prefix shapes: <{SH_NS}> ."] + head
    for r in onto["relations"]:
        if r["status"] != "built" or not r.get("from") or r.get("abstract"):
            continue
        rid = r["id"]

        def cls_constraint(ends):
            ends = ends if isinstance(ends, list) else [ends]
            if len(ends) == 1:
                return f"sh:class {ref(ends[0])}"
            return "sh:or ( " + " ".join(
                f"[ sh:class {ref(e)} ]" for e in ends) + " )"
        sh.append(
            f"shapes:{rid}Domain a sh:NodeShape ;\n"
            f"  sh:targetSubjectsOf {ref(rid)} ;\n"
            f"  {cls_constraint(r['from'])} ;\n"
            f"  sh:message {lit(f'the source of {rid} must be ' + O._ends(r['from']))} .")
        sh.append(
            f"shapes:{rid}Range a sh:NodeShape ;\n"
            f"  sh:targetObjectsOf {ref(rid)} ;\n"
            f"  {cls_constraint(r['to'])} ;\n"
            f"  sh:message {lit(f'the target of {rid} must be ' + O._ends(r['to']))} .")
    shapes = "\n".join(sh) + "\n"
    return ttl, shapes


def main():
    onto = O.load()
    census = O.census()
    ttl, shapes = build(onto, census)
    (ROOT / "out" / "ontology.ttl").write_text(ttl, encoding="utf-8")
    (ROOT / "out" / "ontology-shapes.ttl").write_text(shapes, encoding="utf-8")
    print(f"out/ontology.ttl         {len(ttl):,} bytes, "
          f"{len(onto['classes'])} classes, {len(onto['relations'])} "
          f"properties")
    print(f"out/ontology-shapes.ttl  {len(shapes):,} bytes, "
          f"{shapes.count('a sh:NodeShape')} shapes")


if __name__ == "__main__":
    main()
