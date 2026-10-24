"""The alignment file says only what is so (plan 8.1e; tools/ns_align.py).

  - every one of ours is a term the 1.2.0 vocabularies define;
  - every target is in ontology/align/targets.json, checked against its
    specification (a target nobody checked is how a mapping to a term that
    does not exist gets published);
  - only closeMatch, broadMatch, narrowMatch, relatedMatch; no exactMatch;
  - no pair mapped twice, and no pair mapped both broader and narrower;
  - the published copy is what the generator writes now, and it parses;
  - planted: an unchecked target, a term of ours that does not exist, and an
    exact match are each caught.

    python tests/test_alignment.py          (preflight runs it so)
"""
import json
import sys
import tempfile
from pathlib import Path

import rdflib
from rdflib import URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ns_align as A  # noqa: E402
import ns_common as NC  # noqa: E402
import vocab_inventory as V  # noqa: E402


def problems(rows, unmapped, ours_defined, checked):
    bad = []
    seen = {}
    for m in rows:
        if m["match"] not in A.SKOSM:
            bad.append(f"{m['ours']} -> {m['theirs']}: '{m['match']}' is not one of {sorted(A.SKOSM)}")
        if m["ours_iri"] not in ours_defined:
            bad.append(f"{m['ours']} is not a term of the vocabularies")
        if m["theirs"] not in checked:
            bad.append(f"{m['theirs']} was never checked against its specification (ontology/align/targets.json)")
        if not (m.get("why") or "").strip():
            bad.append(f"{m['ours']} -> {m['theirs']}: no reason given")
        key = (m["ours"], m["theirs"])
        if key in seen:
            bad.append(f"{m['ours']} -> {m['theirs']} mapped twice ({seen[key]}, {m['match']})")
        seen[key] = m["match"]
    for c, u, _w in unmapped:
        if u not in ours_defined:
            bad.append(f"unmapped {c} is not a term of the vocabularies")
    return bad


def main():
    fails = []
    gen, _ = V.generated()
    graphs = {n: rdflib.Graph().parse(data=gen[n].decode("utf-8"), format="turtle")
              for n in ("structure", "relation", "meaning", "claim")}
    ours_defined = {str(s) for g in graphs.values() for s in g.subjects()
                    if isinstance(s, URIRef) and any(str(s).startswith(b) for b in A.OURS.values())}
    checked = set(json.loads(A.TARGETS.read_text(encoding="utf-8"))["targets"])
    pre, rows, unmapped = A.load()
    raw = A.SRC.read_text(encoding="utf-8")
    if "match: exact" in raw:
        fails.append("an exact match: the policy is none (skos:exactMatch is transitive)")
    bad = problems(rows, unmapped, ours_defined, checked)
    fails += bad
    # the published copy is the generator's output now, and it parses
    released = tuple(int(x) for x in NC.VERSION.split(".")) >= (1, 2, 0)
    pub = ROOT / "out" / "ns" if released else ROOT / "docs" / "review" / "alignment"
    with tempfile.TemporaryDirectory() as tmp:
        A.main(graphs, tmp)
        for f in ("alignment.ttl", "alignment.html"):
            now = (Path(tmp) / f).read_text(encoding="utf-8")
            if not (pub / f).exists() or (pub / f).read_text(encoding="utf-8") != now:
                fails.append(f"{(pub / f).relative_to(ROOT)} is not what tools/ns_align.py writes now")
        g = rdflib.Graph().parse(Path(tmp) / "alignment.ttl")
        n = sum(1 for _s, p, _o in g if str(p).startswith("http://www.w3.org/2004/02/skos/core#"))
        if n != len(rows):
            fails.append(f"the Turtle holds {n} mappings, the source {len(rows)}")
    # PLANTED
    planted = [dict(rows[0], theirs="schema:NoSuchTerm", theirs_iri="https://schema.org/NoSuchTerm"),
               dict(rows[0], ours="bom:NoSuchClass", ours_iri=A.OURS["meaning"] + "NoSuchClass",
                    theirs="foaf:Agent")]
    caught = problems(rows + planted, unmapped, ours_defined, checked)
    if not any("NoSuchTerm" in b for b in caught) or not any("NoSuchClass" in b for b in caught):
        fails.append("planted: an unchecked target or an undefined term of ours was not caught")
    if "match: exact" not in raw.replace("match: close", "match: exact", 1):
        fails.append("planted: the exact-match check cannot fire")
    print(f"alignment: {len(rows)} mappings to {len({m['theirs'] for m in rows})} checked targets; "
          f"{len(bad)} problems; planted faults caught; {len(fails)} failures")
    for f in fails:
        print("FAIL " + f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
