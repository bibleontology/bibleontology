"""THE EXPORTS, DESCRIBED (the committee of 2026-10-21, ontology seat finding
3, before the public repository: "one void:Dataset / dcat:Dataset node per
export, and one for the graph").

A reader of the files, or Google's Dataset Search, should not have to find the
terms in a comment. This writes out/export/void.ttl: the graph as one dataset,
each export file as a subset with its own distribution, and on each
  - dcterms:license once the graph's licence is granted (ns-version.json,
    graph_license; tools/ns_common.py), and dcterms:rights always, in words;
  - dcterms:source: MACULA in its attribution's own words, STEP Bible as it
    asks to be credited, and the Berean;
  - void:vocabulary: the four namespaces the files use.

    python tools/export_void.py      -> out/export/void.ttl
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from export_claims import lit  # noqa: E402
from ns_common import GRAPH_LICENSE  # noqa: E402

SITE = "https://bibleontology.org"
OUT = ROOT / "out" / "export" / "void.ttl"
RIGHTS = ("© 2026 Doug Egge. Licensed under CC BY 4.0: share and adapt, with credit to Bible Ontology by "
          "Doug Egge (bibleontology.org)." if GRAPH_LICENSE else
          "© 2026 Doug Egge. All rights reserved until the public repository is published, when CC BY 4.0 "
          "is granted.")
NS = {"claim": f"{SITE}/ns/claim#", "bor": f"{SITE}/ns/relation#", "bom": f"{SITE}/ns/meaning#",
      "bos": f"{SITE}/ns/structure#", "prov": "http://www.w3.org/ns/prov#", "dqv": "http://www.w3.org/ns/dqv#"}
# each file with the vocabularies it actually uses (the committee, 2026-10-22)
FILES = [
    ("claims-rdf12.trig.gz", "Claims (RDF 1.2)", "Every relation as a claim with its verses, certainty and voice: "
     "each a triple term, and only the narrator's outright statements also asserted.", "application/trig",
     ("claim", "bor", "prov")),
    ("claims.trig.gz", "Claims (RDF 1.1)", "The same claims, each voice's plain triples in its own named graph.",
     "application/trig", ("claim", "bor", "prov")),
    ("entities.ttl.gz", "Records, typed", "Each record's address and name, and its class where one maps.",
     "text/turtle", ("bom",)),
    ("ties.trig.gz", "Navigator ties", "How strongly records are tied, with each tie's measure and each "
     "centre's floor.", "application/trig", ("bom", "dqv")),
    ("card-words.trig.gz", "Card words", "The words on each card with their strength, and which are shown by "
     "default.", "application/trig", ("bom", "dqv")),
]
IANA = "https://www.iana.org/assignments/media-types/"
# the public repository's address, once it exists (ns-version.json "repository",
# set on cut day): each distribution then names where to download it
import json  # noqa: E402
_REPO = json.loads((ROOT / "ontology" / "ns-version.json").read_text(encoding="utf-8")).get("repository")
_DATA = json.loads((ROOT / "ontology" / "ns-version.json").read_text(encoding="utf-8"))["data"]
SOURCES = [
    ("https://github.com/Clear-Bible/macula-hebrew/",
     "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/"),
    ("https://github.com/Clear-Bible/macula-greek/",
     "MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/"),
    ("https://www.STEPBible.org", "STEP Bible"),
    ("https://bereanbible.com", "The Berean Standard Bible (public domain)"),
]


def main():
    g = f"<{SITE}/dataset>"
    out = ["# Bible Ontology: the published exports, described (VoID and DCAT).",
           "# Written by tools/export_void.py; the terms follow ontology/ns-version.json, graph_license.", "",
           "@prefix void: <http://rdfs.org/ns/void#> .",
           "@prefix dcat: <http://www.w3.org/ns/dcat#> .",
           "@prefix dcterms: <http://purl.org/dc/terms/> .",
           "@prefix foaf: <http://xmlns.com/foaf/0.1/> .",
           "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .", ""]
    for uri, label in SOURCES:
        out.append(f"<{uri}> dcterms:title {lit(label)} .")
    out.append("")

    def common(vocabs):
        p = [f"dcterms:rights {lit(RIGHTS)}",
             "dcterms:creator [ a foaf:Person ; foaf:name \"Doug Egge\" ]",
             "dcterms:publisher [ a foaf:Person ; foaf:name \"Doug Egge\" ]",
             "dcterms:source " + ", ".join(f"<{u}>" for u, _ in SOURCES),
             "void:vocabulary " + ", ".join(f"<{NS[v]}>" for v in vocabs)]
        if GRAPH_LICENSE:
            p.insert(0, f"dcterms:license <{GRAPH_LICENSE}>")
        return p

    head = [f"a void:Dataset, dcat:Dataset", f"dcterms:title \"Bible Ontology\"",
            "dcterms:description " + lit("A knowledge graph of what the text of the Bible says: its people, "
                                         "places, events and claims, each relation resting on its verses and "
                                         "credited to the voice that makes it."),
            # THE DATA'S OWN VERSION, not the vocabularies' (ns-version.json "data")
            f"foaf:homepage <{SITE}/>", f"dcterms:modified \"{_DATA['date']}\"^^xsd:date",
            f"dcat:version {lit(_DATA['version'])}", f"void:uriSpace \"{SITE}/e/\""] + common(NS)
    head += ["void:subset " + ", ".join(f"<{SITE}/dataset/{f.split('.')[0]}>" for f, *_ in FILES)]
    out.append(g + " " + " ;\n    ".join(head) + " .\n")
    for f, title, desc, mt, vocabs in FILES:
        d = f"<{SITE}/dataset/{f.split('.')[0]}>"
        url = f"{_REPO.rstrip('/')}/raw/main/out/export/{f}" if _REPO else None
        dist = (f"dcat:distribution [ a dcat:Distribution ; dcterms:title {lit(f)} ; "
                f"dcat:mediaType <{IANA}{mt}> ; dcat:compressFormat <{IANA}application/gzip>"
                + (f" ; dcat:downloadURL <{url}>" if url else "") + " ]")
        parts = ["a void:Dataset, dcat:Dataset", f"dcterms:title {lit(title)}", f"dcterms:description {lit(desc)}",
                 f"dcterms:isPartOf {g}"] + common(vocabs) + ([f"void:dataDump <{url}>"] if url else []) + [dist]
        out.append(d + " " + " ;\n    ".join(parts) + " .\n")
    OUT.write_text("\n".join(out), encoding="utf-8", newline="\n")
    print(f"{len(FILES)} exports described, licence {'granted' if GRAPH_LICENSE else 'not yet granted'} "
          f"-> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
