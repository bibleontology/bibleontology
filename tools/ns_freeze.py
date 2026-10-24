"""Build /ns/shapes and keep each release's dated copy (OWL evaluation Phase
0; approved 2026-10-13: "Version and date" and "Move disjointness").

  - out/ns/shapes.ttl: the closed-world checks, published at /ns/shapes --
    the structure layer's "one of these kinds" lists (out/ns/structure-
    shapes.ttl, from tools/ns_structure.py) and the meaning layer's shapes
    (ontology/meaning/shapes.ttl), where the old disjointness now lives.
  - out/ns/versions/<name>-<date>.ttl: each vocabulary as released, kept
    forever at https://bibleontology.org/ns/<name>/<date>. A release never
    overwrites an earlier date's copy; it fails instead, so a changed file
    must carry a new date (ontology/ns-version.json).
  - Checks meaning.ttl (written by hand) carries the same version and the
    same reasoning policy as the generated two.

    python tools/ns_structure.py && python tools/ns_relation.py && python tools/ns_freeze.py
"""
import sys
from pathlib import Path

import rdflib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from ns_common import DATE, LICENSE, POLICY, RIGHTS, VERSION, VERSIONING  # noqa: E402

NS = ROOT / "out" / "ns"
SOURCES = {"meaning": NS / "meaning.ttl",      # the public copy (tools/ns_meaning.py)
           "structure": NS / "structure.ttl",
           "relation": NS / "relation.ttl",
           # the claim vocabulary (plan 8.1a), written by hand like meaning.ttl
           "claim": ROOT / "ontology" / "claim" / "claim.ttl",
           "shapes": NS / "shapes.ttl",
           # the alignment file (plan 8.1e), from 1.2.0: tools/ns_align.py
           "alignment": NS / "alignment.ttl"}


def main():
    meaning = (ROOT / "ontology" / "meaning" / "meaning.ttl").read_text(encoding="utf-8")
    for must in (POLICY, VERSIONING, f'owl:versionInfo "{VERSION}"', f"/ns/meaning/{DATE}>"):
        if must not in meaning:
            sys.exit(f"meaning.ttl is out of step with ontology/ns-version.json or ns_common.py: missing {must[:60]!r}")
    # the hand-written vocabularies say the licence exactly as the generated
    # ones do, or not at all: one granted and one not would be two answers
    for nm, p in (("meaning.ttl", ROOT / "ontology" / "meaning" / "meaning.ttl"),
                  ("claim.ttl", ROOT / "ontology" / "claim" / "claim.ttl")):
        txt = p.read_text(encoding="utf-8")
        if f'"{RIGHTS}"' not in txt:
            sys.exit(f"{nm}: its dcterms:rights is not {RIGHTS!r} (ns_common.RIGHTS)")
        if bool(LICENSE) != ("creativecommons.org/licenses" in txt):
            sys.exit(f"{nm}: dcterms:license {'missing' if LICENSE else 'present'}, "
                     f"but ontology/ns-version.json says granted={bool(LICENSE)}")
    shapes = rdflib.Graph()
    shapes.parse(NS / "structure-shapes.ttl", format="turtle")
    shapes.parse(ROOT / "ontology" / "meaning" / "shapes.ttl", format="turtle")
    # /ns/claim and its shapes join the family from 1.1.0 (plan 8.1a); the
    # 1.0.0 release, already kept, stays exactly as it was
    with_claim = tuple(int(x) for x in VERSION.split(".")) >= (1, 1, 0)
    # the relations' "one of" shapes join from 1.2.0 (tools/ns_relation.py
    # writes them; where a relation's end allows several classes, a list
    # means either); earlier releases stay exactly as kept
    if tuple(int(x) for x in VERSION.split(".")) >= (1, 2, 0):
        rs = NS / "relation-shapes.ttl"
        if not rs.exists():
            sys.exit("out/ns/relation-shapes.ttl missing: run tools/ns_relation.py first")
        shapes.parse(rs, format="turtle")
    if with_claim:
        shapes.parse(ROOT / "ontology" / "claim" / "shapes.ttl", format="turtle")
        claim = (ROOT / "ontology" / "claim" / "claim.ttl").read_text(encoding="utf-8")
        for must in (f'owl:versionInfo "{VERSION}"', f"/ns/claim/{DATE}>"):
            if must not in claim:
                sys.exit(f"claim.ttl is out of step with ontology/ns-version.json: missing {must!r}")
    head = ("# Bible Ontology -- SHACL shapes, version " + VERSION + " (" + DATE + ").\n"
            "# Closed-world checks for the graph: what the vocabularies at /ns/meaning, /ns/structure\n"
            "# and /ns/relation describe, checked here rather than inferred. Run with inference off.\n"
            "# " + RIGHTS.replace("©", "(c)") + "\n"
            + (f"# Licence: {LICENSE}\n" if LICENSE else ""))
    SOURCES["shapes"].write_text(head + shapes.serialize(format="turtle"), encoding="utf-8")
    if with_claim:
        # the published copy of the claim vocabulary, served at /ns/claim
        (NS / "claim.ttl").write_bytes((ROOT / "ontology" / "claim" / "claim.ttl").read_bytes())
    vdir = NS / "versions"
    vdir.mkdir(parents=True, exist_ok=True)
    for name, src in SOURCES.items():
        if name == "claim" and not with_claim:
            continue                        # /ns/claim begins with 1.1.0
        if name == "alignment":
            if tuple(int(x) for x in VERSION.split(".")) < (1, 2, 0):
                continue                    # /ns/alignment begins with 1.2.0
            if not src.exists():
                sys.exit("out/ns/alignment.ttl missing: run tools/ns_align.py first")
            # its version must be this release's before it is kept forever
            # (the committee's practitioner, P2: a stale 1.1.1 copy sat in
            # out/ns the evening it was built)
            txt = src.read_text(encoding="utf-8")
            for must in (f'owl:versionInfo "{VERSION}"', f"/ns/alignment/{DATE}>"):
                if must not in txt:
                    sys.exit(f"alignment.ttl is out of step with ontology/ns-version.json: missing {must!r}; "
                             "run tools/ns_align.py")
        body = src.read_bytes()
        dst = vdir / f"{name}-{DATE}.ttl"
        if dst.exists() and dst.read_bytes() != body:
            sys.exit(f"{dst.relative_to(ROOT)} exists and differs: a released version is kept as it was. "
                     f"Give this release a new date in ontology/ns-version.json.")
        dst.write_bytes(body)
        print(f"{name}: {dst.relative_to(ROOT)} ({len(body):,} bytes)")
    print(f"shapes: {len(shapes)} triples; version {VERSION}, {DATE}")


if __name__ == "__main__":
    main()
