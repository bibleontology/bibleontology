"""The claim export conforms to its shapes, and each shape catches its fault.

Plan 8.1a: out/export/claims.trig.gz (tools/export_claims.py) is what the
public repository will carry, so it is checked the way the vocabularies are:
ontology/claim/shapes.ttl, closed-world, inference off, and a planted fault
per rule that must be caught (a check that never fires is not a check).

    python tests/test_claims.py
"""
import gzip
import sys
from pathlib import Path

import pyshacl
import rdflib

ROOT = Path(__file__).resolve().parents[1]
C = "https://bibleontology.org/ns/claim#"
SITE = "https://bibleontology.org"


def main():
    ds = rdflib.Dataset()
    with gzip.open(ROOT / "out" / "export" / "claims.trig.gz", "rt", encoding="utf-8") as f:
        ds.parse(data=f.read(), format="trig")
    g = rdflib.Graph()
    for t in ds.default_graph:
        g.add(t)
    shapes = rdflib.Graph().parse(ROOT / "ontology" / "claim" / "shapes.ttl")
    ok, _, text = pyshacl.validate(g, shacl_graph=shapes, inference="none")
    claims = len(set(g.subjects(rdflib.RDF.type, rdflib.URIRef(C + "Claim"))))
    fails = 0
    if not ok:
        print("FAIL the export does not conform:\n" + text[:1200])
        fails += 1
    # one claim, five ways wrong
    base = (f"@prefix claim: <{C}> . @prefix e: <{SITE}/e/> . @prefix p: <{SITE}/p/> . "
            f"@prefix bor: <{SITE}/ns/relation#> . ")
    good = ("<x:c> a claim:Claim ; claim:subject e:job ; claim:relation bor:described_as ; claim:object e:x ; "
            "claim:verse p:Job.15.6 ; claim:certainty claim:explicit ; claim:voice claim:narrator . ")
    planted = {
        "no verse": good.replace("claim:verse p:Job.15.6 ; ", ""),
        "a verse that is not a page": good.replace("p:Job.15.6", "<https://example.org/Job15>"),
        "two certainties": good.replace("claim:certainty claim:explicit", "claim:certainty claim:explicit, claim:implied"),
        "a certainty off the scale": good.replace("claim:explicit", "claim:probable"),
        "a relation from elsewhere": good.replace("bor:described_as", "<https://example.org/rel>"),
        # the statement shape (the committee's ontology expert, second sitting)
        "a verb statement with a force off the scheme": good.replace(
            "claim:voice claim:narrator . ",
            'claim:voice claim:narrator ; claim:verbLabel "loved" ; claim:negated false ; '
            "claim:modality claim:modality_probably . "),
        "a clause addressed in MACULA's book codes": good.replace(
            "claim:voice claim:narrator . ",
            'claim:voice claim:narrator ; claim:verbLabel "loved" ; claim:negated false ; '
            "claim:modality claim:modality_stated ; claim:clause <https://bibleontology.org/structure/Jhn.3.16#cl0> . "),
    }
    gg = rdflib.Graph().parse(data=base + good, format="turtle")
    if not pyshacl.validate(gg, shacl_graph=shapes, inference="none")[0]:
        print("FAIL the well-formed claim was refused")
        fails += 1
    caught = 0
    for name, ttl in planted.items():
        bad = rdflib.Graph().parse(data=base + ttl, format="turtle")
        if pyshacl.validate(bad, shacl_graph=shapes, inference="none")[0]:
            print(f"FAIL planted fault not caught: {name}")
            fails += 1
        else:
            caught += 1
    # NO CLAIM NAMES A RETIRED RECORD (the code review, 2026-10-22, B1): an id
    # ontology/aliases.jsonl replaces must not be a claim's subject, object or
    # claimant, or one person is counted twice (Bashemath had two fathers)
    import json
    retired = {SITE + "/e/" + json.loads(x)["id"]
               for x in open(ROOT / "ontology" / "aliases.jsonl", encoding="utf-8") if x.strip()}

    def named_retired(graph):
        return sorted({str(o) for p in ("subject", "object", "claimedBy")
                       for o in graph.objects(None, rdflib.URIRef(C + p)) if str(o) in retired})
    hit = named_retired(g)
    if hit:
        print(f"FAIL claims name {len(hit)} retired records, e.g. {hit[:3]}")
        fails += 1
    bad = rdflib.Graph().parse(data=base + good.replace("e:job", "e:elon_the_hittite"), format="turtle")
    planted["a retired record named"] = None
    if named_retired(bad):
        caught += 1
    else:
        print("FAIL planted fault not caught: a retired record named")
        fails += 1
    print(f"{claims:,} claims conform: {ok}; planted faults caught: {caught} of {len(planted)}; {fails} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
