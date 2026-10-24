"""Check the proposed meaning ontology: it parses, its examples satisfy its
shapes, and each shape catches the fault it exists for.

    python tools/meaning/check.py

Three tests (PRINCIPLES 48: a rule is trusted on its measurement):
  1. meaning.ttl, examples.ttl and shapes.ttl parse;
  2. the worked examples conform to the shapes;
  3. each fault the shapes guard against, planted in a copy of the
     examples, is caught — a shape that never fires is not a check.
"""
import sys
from pathlib import Path

import pyshacl
import rdflib

HERE = Path(__file__).resolve().parents[2] / "ontology" / "meaning"
EX = "https://bibleontology.org/example/"
BOM = "https://bibleontology.org/ns/meaning#"

FAULTS = {
    "a figurative occurrence with no figure": f"""
        <{EX}occ-X> a <https://bibleontology.org/ns/word#Occurrence> ;
            <https://bibleontology.org/ns/word#ofLexeme> <{EX}or> ;
            <{BOM}usage> <{BOM}Figurative> .""",
    "a read tenor sitting on the figure": f"""
        <{EX}fig-Rev1-16> <{BOM}tenor> "the word of God" .""",
    "a predication with no speaker": f"""
        <{EX}pred-X> a <{BOM}Predication> ; <{BOM}predicationOf> <{EX}jesus> ;
            <{BOM}predicatedCategory> <{EX}cat-man> ; <{BOM}evidence> "Jhn.1.1" .""",
    "a reading with no reader": f"""
        <{EX}reading-X> a <{BOM}ThemeStamp> ; <{BOM}evidence> "Gen.1" .""",
    "two top classes on one individual": f"""
        <{EX}jesus> a <{BOM}Artifact> .""",
    "a subclass membership with no classification": f"""
        <{EX}sower> a <{BOM}Human> .""",
    "a sign whose meaning the text does not state": f"""
        <{EX}occ-Rev1-16> <{BOM}usage> <{BOM}Sign> .""",
    "a contested use with only one side": f"""
        <{EX}occ-Gen1-3> <{BOM}usage> <{BOM}Contested> .""",
    "a use the text settles, marked contested": f"""
        <{EX}occ-Jhn2-19> <{BOM}usage> <{BOM}Contested> .
        <{EX}ur-x> a <{BOM}UsageReading> ; <{BOM}readsUsageOf> <{EX}occ-Jhn2-19> ;
            <{BOM}readsUsage> <{BOM}Literal> ; <{BOM}readsAs> "the Jerusalem temple" ;
            <http://www.w3.org/ns/prov#wasAttributedTo> <{EX}reader-example> ;
            <{BOM}evidence> "Jhn.2.19" .
        <{EX}ur-y> a <{BOM}UsageReading> ; <{BOM}readsUsageOf> <{EX}occ-Jhn2-19> ;
            <{BOM}readsUsage> <{BOM}Figurative> ; <{BOM}readsAs> "his body" ;
            <http://www.w3.org/ns/prov#wasAttributedTo> <{EX}reader-example> ;
            <{BOM}evidence> "Jhn.2.21" .""",
}


def load(*names, extra=None):
    g = rdflib.Graph()
    for n in names:
        g.parse(HERE / n, format="turtle")
    if extra:
        g.parse(data=extra, format="turtle")
    return g


def main():
    onto = load("meaning.ttl")
    shapes = load("shapes.ttl")
    data = load("examples.ttl")
    print(f"parsed: schema {len(onto)} triples, shapes {len(shapes)}, "
          f"examples {len(data)}")
    # NO INFERENCE (the OWL evaluation, 2026-10-13, Phase 0 approved):
    # with RDFS inference on, the schema's own domains and ranges supplied the
    # very classes the shapes test for, so a shape could pass on what the
    # reasoner made up -- the setting tools/shacl_check.py
    # already switches off. The examples must say what they are.
    ok, _, text = pyshacl.validate(data, shacl_graph=shapes, ont_graph=onto,
                                   inference="none", advanced=True)
    print("examples conform:", ok)
    if not ok:
        print(text)
    caught = 0
    for name, ttl in FAULTS.items():
        bad = load("examples.ttl", extra=ttl)
        c, _, _ = pyshacl.validate(bad, shacl_graph=shapes, ont_graph=onto,
                                   inference="none", advanced=True)
        caught += not c
        print(f"  planted fault, {'caught' if not c else 'MISSED'}: {name}")
    print(f"{caught} of {len(FAULTS)} planted faults caught")
    return 0 if ok and caught == len(FAULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
