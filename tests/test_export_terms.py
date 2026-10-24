"""The exports say one thing about their terms (plan 8.3; the committee of
2026-10-21, ontology seat finding 3).

The graph's licence is one switch (ontology/ns-version.json, graph_license).
Every export's header, the VoID/DCAT description and the switch must agree:
granted, every dataset carries dcterms:license and every header says CC BY
4.0; not yet, none does and none says it is granted. Every header carries
MACULA's credit in MACULA's own words. Planted: a header with the old
"intended once the copyright filing is received" sentence, and a description
whose licence disagrees with the switch.

    python tests/test_export_terms.py
"""
import gzip
import sys
from pathlib import Path

import rdflib
from rdflib import RDF, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ns_common as N  # noqa: E402

EXPORTS = ["claims-rdf12.trig.gz", "claims.trig.gz", "entities.ttl.gz", "ties.trig.gz", "card-words.trig.gz"]
LICENSE = URIRef("http://purl.org/dc/terms/license")
VOID = URIRef("http://rdfs.org/ns/void#Dataset")
STALE = "intended once the copyright filing is received"


def header(p: Path) -> str:
    out = []
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#"):
                break
            out.append(line)
    return "".join(out)


def header_faults(name: str, h: str) -> list[str]:
    # the claims carry WordNet's verb classes, so its notice too
    want = N.export_rights(wordnet=name.startswith("claims"))
    bad = [f"{name}: header lacks {w!r}" for w in want if w not in h]
    if STALE in h:
        bad.append(f"{name}: header still says the licence is {STALE!r}")
    return bad


def void_faults(g: rdflib.Graph) -> list[str]:
    bad = []
    sets = list(g.subjects(RDF.type, VOID))
    if len(sets) != len(EXPORTS) + 1:
        bad.append(f"void.ttl describes {len(sets)} datasets, not {len(EXPORTS) + 1}")
    for s in sets:
        has = set(g.objects(s, LICENSE))
        if N.GRAPH_LICENSE and has != {URIRef(N.GRAPH_LICENSE)}:
            bad.append(f"{s}: licence {has or 'missing'}, but the switch grants {N.GRAPH_LICENSE}")
        if not N.GRAPH_LICENSE and has:
            bad.append(f"{s}: says {has} before the licence is granted")
    return bad


def main():
    fails = []
    for name in EXPORTS:
        fails += header_faults(name, header(ROOT / "out" / "export" / name))
    g = rdflib.Graph()
    g.parse(ROOT / "out" / "export" / "void.ttl", format="turtle")
    fails += void_faults(g)
    # PLANTED: the old sentence in a header; a licence the switch did not grant
    planted = 0
    if header_faults("planted", "".join(x + "\n" for x in N.export_rights()) + f"# {STALE}\n"):
        planted += 1
    g2 = rdflib.Graph() + g
    s = next(iter(g2.subjects(RDF.type, VOID)))
    if N.GRAPH_LICENSE:
        g2.remove((s, LICENSE, None))
    else:
        g2.add((s, LICENSE, URIRef("https://creativecommons.org/licenses/by/4.0/")))
    if void_faults(g2):
        planted += 1
    if planted != 2:
        fails.append(f"planted faults caught: {planted} of 2")
    print(f"export terms: {len(EXPORTS)} headers and their description agree with the switch "
          f"(licence {'granted' if N.GRAPH_LICENSE else 'not yet granted'}); planted faults caught: {planted} of 2; "
          f"{len(fails)} failures")
    for f in fails:
        print("FAIL " + f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
