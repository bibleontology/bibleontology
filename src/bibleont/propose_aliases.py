"""Propose identity.yaml entries for ids that look like the same person.

The recurring drift between batches is a bare id in one and a qualified id in
another — `zadok` from a batch that did not disambiguate, `zadok_son_of_ahitub`
from one that did. Left alone they are two people in the graph.

This finds those pairs and, crucially, checks the *evidence* before proposing a
merge: same display name, and parentage that agrees rather than conflicts. A
bare `joel` and a `joel_son_of_samuel` with different fathers are two men and are
reported as such, not merged.

Nothing is written. The output is a YAML block to paste into identity.yaml after
reading it, because merging two people who are not the same is the one mistake
this project cannot detect afterwards.

Usage:
    python -m bibleont.propose_aliases
"""

from __future__ import annotations

import sys
from collections import defaultdict

from .schema import load_persons, load_relations, slugify


def analyse() -> tuple[list[dict], list[dict], list[dict]]:
    people = load_persons()
    relations = load_relations()

    parents: dict[str, set[str]] = defaultdict(set)
    children: dict[str, set[str]] = defaultdict(set)
    degree: dict[str, int] = defaultdict(int)
    for rel in relations:
        degree[rel.src] += 1
        degree[rel.dst] += 1
        if rel.type in ("father_of", "mother_of"):
            parents[rel.dst].add(rel.src)
            children[rel.src].add(rel.dst)

    same: list[dict] = []
    conflicting: list[dict] = []
    undecided: list[dict] = []

    for short in sorted(people):
        for long in sorted(people):
            if long == short or not long.startswith(short + "_"):
                continue
            a, b = people[short], people[long]
            # Compare every name each record carries, not just the display one:
            # after a spelling merge one side may show "Thamar" and the other
            # "Tamar" while both list the alternate in `aka`.
            names_a = {n.strip().lower() for n in a.names()}
            names_b = {n.strip().lower() for n in b.names()}
            # The id counts as a name too. After a spelling merge the surviving
            # record can display "Thamar" under the id `tamar`, which still
            # matches a record named "Tamar".
            id_match = any(slugify(n) == short for n in b.names())
            if not (names_a & names_b) and not id_match:
                continue  # different names that merely share an id prefix

            pa, pb = parents.get(short, set()), parents.get(long, set())
            ca, cb = children.get(short, set()), children.get(long, set())
            suffix = long[len(short) + 1 :]

            # Two records that are parent to the same child are the same person —
            # a child has one mother and one father. This catches pairs neither
            # of which has a recorded parent of its own, such as Tamar and
            # Tamar-wife-of-Er, both mother of Pharez.
            shared_child = ca & cb

            # "..._son_of_ahitub" only tells us something if the BARE id's own
            # recorded parent is the one named. Matching the qualified id's
            # suffix against its own parent is trivially true and proves nothing
            # about whether the two are the same man.
            names_parent = bool(pa) and any(
                p in suffix or p.rsplit("_son_of_", 1)[0] in suffix for p in pa
            )
            shared = pa & pb
            conflict = bool(pa and pb and not shared)

            entry = {
                "short": short,
                "long": long,
                "name": a.name,
                "short_parents": sorted(pa),
                "long_parents": sorted(pb),
                "short_degree": degree.get(short, 0),
                "long_degree": degree.get(long, 0),
                "short_refs": a.refs[:2],
                "long_refs": b.refs[:2],
                "short_disambig": a.disambiguation,
                "long_disambig": b.disambiguation,
                "evidence": (
                    "same parent" if shared
                    else "parent of the same child" if shared_child
                    else "qualifier names the parent" if names_parent
                    else "no parent recorded on one side" if not (pa and pb)
                    else "parents differ"
                ),
            }
            if conflict:
                conflicting.append(entry)
            elif shared or shared_child or names_parent:
                same.append(entry)
            else:
                # A shared name and nothing else. This is where the genuinely
                # different people hide — Nathan the prophet beside Nathan son of
                # David, an Edomite Saul beside the king. No merge is proposed.
                entry["evidence"] = "no evidence either way"
                undecided.append(entry)

    return same, conflicting, undecided


def main(argv: list[str] | None = None) -> int:
    same, conflicting, undecided = analyse()

    if conflicting:
        print("# DIFFERENT PEOPLE - do not merge; they have different parents.")
        print("# Give the bare id a qualifier of its own instead.\n")
        for e in conflicting:
            print(f"#   {e['name']}: {e['short']} (parent {e['short_parents']}) "
                  f"vs {e['long']} (parent {e['long_parents']})")
        print()

    if undecided:
        print("# NO EVIDENCE EITHER WAY - a shared name and nothing more. NOT")
        print("# proposed as merges: this is exactly where different people hide")
        print("# (Nathan the prophet vs Nathan son of David). Decide by reading")
        print("# the cited verses, then write the answer into identity.yaml by hand.\n")
        for e in undecided:
            print(f"#   {e['name']}: {e['short']} {e['short_refs']} "
                  f"(parents={e['short_parents'] or 'none'}) vs "
                  f"{e['long']} {e['long_refs']} (parents={e['long_parents'] or 'none'})")
        print()

    # One bare id cannot be two people. If several qualified ids claim the same
    # short id, the evidence is self-contradictory and none of them can stand.
    claims: dict[str, list[dict]] = defaultdict(list)
    for e in same:
        claims[e["short"]].append(e)
    contested = {s: es for s, es in claims.items() if len(es) > 1}
    if contested:
        print("# CONTRADICTORY - more than one person claims the same bare id, so")
        print("# the bare id is probably a third person. Not proposed.\n")
        for short, es in contested.items():
            print(f"#   {short} is claimed by " + ", ".join(e["long"] for e in es))
        print()
        same = [e for e in same if e["short"] not in contested]

    if not same:
        print("# No same-person candidates with supporting evidence.")
        return 0

    print("# SAME PERSON - the parentage agrees, or the qualifier names the")
    print("# recorded parent. Paste under `same:` in ontology/identity.yaml.\n")
    for e in same:
        print(f"  # {e['name']}: {e['evidence']}")
        print(f"  #   {e['short']:34} parents={e['short_parents']} "
              f"deg={e['short_degree']} {e['short_refs']}")
        print(f"  #   {e['long']:34} parents={e['long_parents']} "
              f"deg={e['long_degree']} {e['long_refs']}")
        # Keep the more specific id as canonical: it carries the disambiguation.
        print(f"  {e['long']}: [{e['short']}]\n")
    print(
        f"# {len(same)} proposed, {len(conflicting)} rejected as different people, "
        f"{len(undecided)} undecided."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
