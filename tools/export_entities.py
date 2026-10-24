"""THE RECORDS, TYPED: each record's address, class and name (plan 8.1e, before
the r/semanticweb introduction; 2026-10-20: the three preemptive suggestions
were taken).

The published SHACL shapes say, for example, that the subject of "told" is one
of Person, Being, Group, Concept or Creature. An outsider can only run that if
the published data says which class each record is. The claim export never
did: it names records by address only. This file says it.

  <https://bibleontology.org/e/abraham> a bom:Person ;
      rdfs:label "Abraham" ; bom:legacyType "person" .

A record's class comes from its kind through the meaning vocabulary's own
crosswalk (bom:fromEntityType), where the kind maps to exactly one class. A
kind with no single class (passage, pattern, text, title ...) is given no
rdf:type: its kind is kept verbatim as bom:legacyType, and nothing is guessed.
A record merged into another (ontology/aliases.jsonl) says so with
dcterms:isReplacedBy, as its address redirects.

Typing a divine person as a being is a description, not a derivation: the
reasoning policy forbids deriving anything about them, not saying what kind of
record they are.

    python tools/export_entities.py   -> out/export/entities.ttl.gz
"""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from export_claims import lit  # noqa: E402
from ns_relation import kind_classes  # noqa: E402
from ns_common import export_rights, gz_text  # noqa: E402

SITE = "https://bibleontology.org"
OUT = ROOT / "out" / "export" / "entities.ttl.gz"
# NO LEGACY TYPE FOR THE FOUR DIVINE RECORDS (the committee of 2026-10-21, P11;
# decided 2026-10-21: omit the type for all four): "person" for Jesus beside "being" for
# God, the Father and the Holy Spirit is the old store's label, and published
# it reads as a Christology no edge asserts (PRINCIPLES §4). Their class, a
# personal being, stays: the text has each speak or act.
NO_LEGACY = {"god", "the_father", "jesus", "holy_ghost"}
# A CLASS THIS FILE CANNOT MEET (the code review, 2026-10-22, B2): the shapes
# require a bom:Predication to name what it predicates, who says it and its
# evidence, and this file carries a record's name and class only -- so 410
# records failed four times each against the published shapes. Their kind
# stays (bom:legacyType); the saying's parts are in the claims export
UNSHAPED = {"Predication"}


def main():
    kc = kind_classes()
    alias = {}
    for line in open(ROOT / "ontology" / "aliases.jsonl", encoding="utf-8"):
        if line.strip():
            a = json.loads(line)
            alias[a["id"]] = a["alias_of"]
    lines = ["# Bible Ontology -- the records, typed: each record's address, class and name.",
             "# A record whose kind maps to no single class has no rdf:type; its kind is bom:legacyType.",
             "# Vocabulary: https://bibleontology.org/ns/meaning  Checks: https://bibleontology.org/ns/shapes",
             *export_rights(),
             "",
             "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
             "@prefix dcterms: <http://purl.org/dc/terms/> .",
             f"@prefix bom: <{SITE}/ns/meaning#> .",
             f"@prefix e: <{SITE}/e/> .", ""]
    typed = untyped = merged = 0
    # EVERY RECORD A CLAIM CAN NAME (the code review, 2026-10-22, B2, approved
    # by Doug): entities.jsonl first, then the events, themes, patterns and
    # passages kept in files of their own. Reading entities.jsonl alone left
    # 3,116 records the claims name with no label anywhere in the exports
    files = [ROOT / "ontology" / "entities" / "entities.jsonl"] + sorted(
        p for p in (ROOT / "ontology" / "entities").glob("*.jsonl") if p.name != "entities.jsonl")
    seen_ids = set()
    for line in (ln for p in files for ln in open(p, encoding="utf-8") if ln.strip()):
        r = json.loads(line)
        rid, kind = r["id"], r.get("type")
        if rid in seen_ids:
            continue
        seen_ids.add(rid)
        subj = f"<{SITE}/e/{rid}>"
        parts = []
        cls = kc.get(kind)
        if cls in UNSHAPED:
            cls = None
        if cls:
            parts.append(f"a bom:{cls}")
            typed += 1
        else:
            untyped += 1
        parts.append(f"rdfs:label {lit(r.get('name') or rid)}")
        if kind and rid not in NO_LEGACY:
            parts.append(f"bom:legacyType {lit(kind)}")
        if rid in alias:
            parts.append(f"dcterms:isReplacedBy <{SITE}/e/{alias[rid]}>")
            merged += 1
        lines.append(f"{subj} " + " ;\n    ".join(parts) + " .")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gz_text(OUT) as f:
        f.write("\n".join(lines) + "\n")
    print(f"{typed + untyped:,} records: {typed:,} typed, {untyped:,} with no single class (kind kept), "
          f"{merged} merged into another -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
