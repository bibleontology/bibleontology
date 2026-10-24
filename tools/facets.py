"""Facets over the relation taxonomy: the axes a tree cannot carry.

2026-09-05: the taxonomy should be rich because it will be used extensively in
pattern recognition, and a strict hierarchy is likely to be too restrictive and
end up a graph. Then the counterweight, in the same breath: it is a trade-off,
since filtering on relationship types in the UI wants clean categories, which is
what the hierarchy provides.

Both are true and they do not compete. The tree is not wrong, it is
**insufficient**, so it keeps its job and gains a second layer beside it:

    the CATEGORY is primary     exactly one per relation, no gaps, no overlaps.
                                That is what makes a filter list readable and
                                exhaustive -- you can run down it and know you
                                have seen everything there is.

    the FACETS are additional   partial, overlapping, orthogonal. The pattern
                                engine reads them; the filter UI never has to
                                show them.

Folders and tags. A file lives in one folder and carries many tags, and neither
arrangement undermines the other.

## The constraint that keeps both honest

**The primary category must remain a total function.** The moment a relation
carries two categories "because it is really both", the filter list stops being
trustworthy and the tree is a graph pretending otherwise. Facets are exactly
where "it is really both" goes. `--check` enforces it.

It already found one: **`specializes` carries no category at all** — 115 of 116
typed, one hole. That is a real defect in the filter contract, not a facet
question, and it is reported rather than papered over here.

## Why this is a separate file

`ontology/schema/relationship_types.yaml` is 2,445 lines of abstraction work
that was paid for once, and the UI's filter depends on its `category`. Writing
facets beside it rather than into it means a facet experiment can be deleted
without touching the thing the interface rests on. A facet is cheap to add and
expensive to remove — every reader of one has to handle its absence — so they
get added when a query needs them, not speculatively.

## Absent is not false

Three states, and the difference carries information:

    true / a value   asserted
    false            asserted NEGATIVELY, which is a finding in its own right
    absent           not settled

`signifies` is `transitive: false` because the schema's own note says so: *"A
key is not transitive and must not be walked as though it were."* `father_of`
is `transitive: false` for the reason this project learned the hard way — the
Hebrew *ben* spans generations, so a chain of fathers is not a father. Those
two are read out of work already done rather than invented here. A relation
with no value on an axis has none, per Principle 42: a premature restriction is
a bug.

## The five axes, and what each one is for

    polarity     positive / negative. Cuts straight across kinship, violence
                 and speech, which is what "a brother harms a brother" needs
                 and what no single branch of a tree can express.
    transitive   `ancestor_of` closes, `father_of` does not. Any descent query
                 needs this and the category cannot supply it.
    temporality  point / interval / permanent. `killed` happens, `reigned_over`
                 lasts and can end, `sibling_of` starts and never ends. No
                 pattern over time can be stated without the distinction.
                 The 24 relations that get NO value here are the textual and
                 figurative ones -- `signifies`, `part_of`, `likened_to` --
                 and that silence is correct: they are not events.
    effect       what a relation DOES: creates a bond, terminates one,
                 transfers a thing, confers an office or a name. Orthogonal to
                 which sphere it belongs to.
    symmetric    already on 12 types in the schema; lifted here, along with
                 `functional`, so a pattern query reads every axis from one
                 place instead of two.

    python tools/facets.py            # derive, write, report coverage
    python tools/facets.py --check    # the total-function guarantee
"""
from __future__ import annotations

import collections
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "ontology" / "schema" / "relationship_types.yaml"
FACETS = ROOT / "ontology" / "schema" / "relation_facets.yaml"

NEGATIVE = {
    "accused", "attacked", "betrayed", "cast_into", "conquered",
    "conspired_against", "contrary_to", "cursed", "deceived", "deposed",
    "destroyed", "enemy_of", "fought", "imprisoned", "incited", "killed",
    "persecuted", "put_away", "rebuked",
}
POSITIVE = {
    "adoptive_parent_of", "ally_of", "anointed", "appointed", "baptized",
    "betrothed_to", "blessed", "companion_of", "counselor_of", "friend_of",
    "healed", "mentor_of", "ministered_to", "repaired", "spouse_of",
}

# true where the relation closes under composition; FALSE where the schema or
# this project has established that it must not be walked. Absent elsewhere.
TRANSITIVE = {
    "ancestor_of": True, "located_in": True, "part_of": True,
    "specializes": True,
    # the schema's own note: "A key is not transitive and must not be walked
    # as though it were."
    "signifies": False,
    # the father_of/ancestor_of lesson: Hebrew *ben* spans generations, so a
    # chain of fathers is not a father.
    "father_of": False, "mother_of": False,
    "instance_of": False, "likened_to": False, "drawn_from": False,
}

POINT = {
    "accused", "answered", "anointed", "appeared_to", "appointed", "ate",
    "attacked", "baptized", "besought", "betrayed", "blessed", "born_at",
    "bought", "built", "buried_at", "came_upon", "carried", "cast_into",
    "charged", "commanded_the_making_of", "conquered", "conspired_against",
    "cursed", "deceived", "deposed", "destroyed", "died_at", "explained",
    "fought", "founded", "gave", "healed", "heard", "incited", "instituted",
    "judged", "killed", "led", "made", "named", "observed", "offered",
    "put_away", "quoted", "rebuked", "repaired", "sent", "told", "took",
    "traveled_to", "warned", "wore", "wrote_letter_to", "wrote_to",
}
INTERVAL = {
    "ally_of", "based_at", "betrothed_to", "co_regent_with", "commander_of",
    "companion_of", "concubine_of", "counselor_of", "deity_of", "dwelt_at",
    "enemy_of", "friend_of", "imprisoned", "kept_at", "member_of", "mentor_of",
    "ministered_to", "party_to", "persecuted", "present_with", "prophet_to",
    "reigned_over", "ruled_from", "ruler_of", "servant_of", "spouse_of",
    "stationed_at", "titled",
}
# holds from a moment onward and never ends -- which is why a query over these
# never needs a date range and a query over INTERVAL always does.
PERMANENT = {
    "adoptive_parent_of", "ancestor_of", "descended_from_person", "father_of",
    "half_sibling_of", "mother_of", "predecessor_of", "sibling_of", "uncle_of",
}

EFFECT = {
    "spouse_of": "creates_bond", "betrothed_to": "creates_bond",
    "party_to": "creates_bond", "adoptive_parent_of": "creates_bond",
    "ally_of": "creates_bond", "baptized": "creates_bond",
    "instituted": "creates_bond",

    "killed": "terminates", "destroyed": "terminates",
    "deposed": "terminates", "put_away": "terminates",
    "died_at": "terminates", "conquered": "terminates",
    "supersedes": "terminates",

    "gave": "transfers", "took": "transfers", "bought": "transfers",
    "carried": "transfers", "sent": "transfers",

    "anointed": "confers_office", "appointed": "confers_office",
    "titled": "confers_name", "named": "confers_name",
    "named_with": "confers_name", "self_designated_as": "confers_name",

    "made": "creates_thing", "built": "creates_thing",
    "founded": "creates_thing", "commanded_the_making_of": "creates_thing",

    "healed": "restores", "repaired": "restores",
}

AXES = ["polarity", "transitive", "temporality", "effect", "symmetric",
        "functional"]


def load():
    import yaml
    d = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    return d.get("types") or {}


def facets_for(name, spec):
    f = {}
    if name in NEGATIVE:
        f["polarity"] = "negative"
    elif name in POSITIVE:
        f["polarity"] = "positive"
    if name in TRANSITIVE:
        f["transitive"] = TRANSITIVE[name]
    if name in PERMANENT:
        f["temporality"] = "permanent"
    elif name in INTERVAL:
        f["temporality"] = "interval"
    elif name in POINT:
        f["temporality"] = "point"
    if name in EFFECT:
        f["effect"] = EFFECT[name]
    # already recorded in the schema; lifted so every axis reads from one place
    if spec.get("symmetric"):
        f["symmetric"] = True
    if spec.get("functional_inverse"):
        f["functional"] = True
    return f


def check(types):
    """The primary category is a total function, or the filter list lies."""
    missing = [n for n, s in types.items()
               if isinstance(s, dict) and not s.get("category")]
    doubled = [n for n, s in types.items()
               if isinstance(s, dict) and isinstance(s.get("category"), list)]
    bad = "NO - the filter list would have a gap or an overlap"
    print("PRIMARY CATEGORY - must be exactly one per relation")
    print(f"  relation types          {len(types):>5}")
    print(f"  with no category        {len(missing):>5}   {missing}")
    print(f"  with more than one      {len(doubled):>5}   {doubled}")
    ok = not missing and not doubled
    print(f"  total function:         {'YES' if ok else bad}")
    if missing:
        print("\n  This is a defect in the tree, not a facet question. Every")
        print("  relation needs one category or the UI filter is incomplete.")
    return 0 if ok else 1


def main() -> int:
    types = load()
    if "--check" in sys.argv:
        return check(types)

    out, cover = {}, collections.Counter()
    for name, spec in types.items():
        if not isinstance(spec, dict):
            continue
        f = facets_for(name, spec)
        if f:
            out[name] = f
            for k in f:
                cover[k] += 1

    lines = [
        "# Facets over the relation taxonomy - ADDITIVE, never primary.",
        "#",
        "# The `category` in relationship_types.yaml stays the one primary",
        "# axis: exactly one per relation, which is what makes the UI filter",
        "# list exhaustive and trustworthy. These are orthogonal axes for",
        "# pattern recognition, and they are deliberately PARTIAL.",
        "#",
        "# Absent is not false. A relation with no value on an axis has not",
        "# been settled on it; `transitive: false` is an assertion, and two of",
        "# them (signifies, father_of) come from findings already recorded",
        "# elsewhere rather than from a guess here.",
        "#",
        "# Generated by tools/facets.py. Safe to delete: nothing the UI filter",
        "# depends on lives in this file.",
        "",
        "facets:",
    ]
    for name in sorted(out):
        lines.append(f"  {name}:")
        for k in AXES:
            if k in out[name]:
                v = out[name][k]
                lines.append(
                    f"    {k}: {str(v).lower() if isinstance(v, bool) else v}")
    FACETS.write_text("\n".join(lines) + "\n", encoding="utf-8")

    n = len(types)
    print("FACETS - orthogonal axes, additive over the category that exists")
    print(f"  relation types          {n:>5}")
    print(f"  carrying any facet      {len(out):>5}   {100*len(out)//max(n,1)}%")
    print()
    print("  coverage by axis (partial on purpose):")
    for k in AXES:
        v = cover[k]
        print(f"    {k:14}{v:>5}   {100*v//max(n,1):>3}%")
    print()
    untimed = sorted(t for t in types
                     if t not in out or "temporality" not in out[t])
    print(f"  no temporality ({len(untimed)}) - these are not events:")
    print(f"    {untimed[:12]}")
    print()
    print("  transitivity asserted negatively - the valuable half:")
    for t in sorted(TRANSITIVE):
        if TRANSITIVE[t] is False:
            print(f"    {t}")
    print(f"\n  wrote {FACETS}")
    print("  relationship_types.yaml untouched; the UI filter still reads "
          "`category`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
