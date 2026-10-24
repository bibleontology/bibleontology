"""The old graph laid over the new one: its established, sourced relations, by type.

2026-09-28: in general, established and sourced relationships/nodes in the
old graph are treated as overlays in the new graph if the graph is unable to
surface them; the old graph holds a lot more hand work, valuable once the
foundation is built with the deterministic App2 approach; and, choosing how
(plan 6.13, step 1): by type, without speaks_of.

KEPT — the kinds of fact the deterministic layer cannot reach on its own:

    identity and titles   deity_of, distinguished_from, named_with,
                          self_designated_as, spoken_of_as, assumed_form_of,
                          titled, signifies, instance_of
    kinship               father_of, mother_of, sibling_of, half_sibling_of,
                          uncle_of, adoptive_parent_of, ancestor_of,
                          descended_from_person, spouse_of, betrothed_to,
                          concubine_of, put_away
    assessments           assessed_as
    typology              draws_on, drawn_from, likened_to, token_of
    part-of, membership   part_of, member_of, composed_of

LEFT OUT — speaks_of (the type found to record which words are where:
measured at 75% of 16,124 relations), asserted_by and told (speech the new
graph surfaces itself), and the narrative actions (gave, killed, traveled_to
...) which the new graph's clauses carry. Widening is decided by hand.

The Trinity is not modelled either way (a standing decision): identity relations are
carried as the old graph asserted them, each with its verses, both
`spoken_of_as` and `distinguished_from`, neither resolved. No weights here:
how much partial credit a relation earns is decided where it is used
(plan 6.13, steps 3 and 4).

    python tools/overlay.py     -> out/overlay-relations.jsonl
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
GROUPS = {
    "identity": {"deity_of", "distinguished_from", "named_with", "self_designated_as",
                 "spoken_of_as", "assumed_form_of", "titled", "signifies", "instance_of"},
    "kinship": {"father_of", "mother_of", "sibling_of", "half_sibling_of", "uncle_of",
                "adoptive_parent_of", "ancestor_of", "descended_from_person", "spouse_of",
                "betrothed_to", "concubine_of", "put_away"},
    "assessment": {"assessed_as"},
    "typology": {"draws_on", "drawn_from", "likened_to", "token_of"},
    "membership": {"part_of", "member_of", "composed_of"},
}
GROUP_OF = {t: g for g, ts in GROUPS.items() for t in ts}
CERTAIN = {"explicit", "implied"}          # disputed / conjectured stay out


def main() -> None:
    kept, left = [], collections.Counter()
    for f in sorted((ROOT / "ontology" / "relations").glob("*.jsonl")):
        for line in f.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            t = r.get("type")
            if t not in GROUP_OF or not r.get("refs") or r.get("certainty") not in CERTAIN:
                left[t if t not in GROUP_OF else f"{t} (unsourced or uncertain)"] += 1
                continue
            kept.append({"src": r.get("src"), "dst": r.get("dst"), "type": t,
                         "group": GROUP_OF[t], "certainty": r.get("certainty"),
                         "refs": r.get("refs"), "note": r.get("note"),
                         "from": f"old graph, {f.name}"})
    with (OUT / "overlay-relations.jsonl").open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"_note": "The old graph's established, sourced relations kept "
                             "as an OVERLAY on the new graph, by type (tools/overlay.py; "
                             "plan 6.13 step 1). Credited to the old graph; never merged "
                             "into the computed layer; no weights.",
                             "_groups": {g: sorted(ts) for g, ts in GROUPS.items()}}) + "\n")
        for r in kept:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    by = collections.Counter(r["group"] for r in kept)
    print(f"{len(kept):,} relations kept: " + ", ".join(f"{g} {n:,}" for g, n in by.most_common()))
    print(f"{sum(left.values()):,} left out; largest: " +
          ", ".join(f"{t} {n:,}" for t, n in left.most_common(8)))


if __name__ == "__main__":
    main()
