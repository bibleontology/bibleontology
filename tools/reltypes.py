"""A relation taxonomy: the text's verb underneath, the graph's category above.

2026-09-05: the legacy graph categorizes relationship types well while the
new graph has very specific verbs; both are valuable, and for that reason a
relationship type hierarchy/taxonomy is to be built.

The interface/implementation split applied to relations, and both halves earn
their place:

    the VERB is the evidence      *begat*, *bore*, *fathered* — what the text
                                  actually said, never invented, and the thing
                                  that can be checked against the verse
    the CATEGORY is the query     `father_of` — what lets you ask "who descends
                                  from Abraham" without enumerating every
                                  begetting verb in the canon

Losing the verb would flatten *bore* and *begat* into one relation when they
are not one — one is a mother and the other a father. Losing the category
leaves 288 distinct verbs and no way to ask a question.

## The taxonomy already existed and I nearly rebuilt it

The earlier work on the abstractions was good and could be leveraged, and I
had hand-written a category list before looking.
`ontology/schema/relationship_types.yaml` is 2,445 lines holding a complete
two-level hierarchy:

    12 domains      person, place, event, group, text, object, observance,
                    creature, title, assessment, covenant, being
    categories      kinship, political, religious, service, marital,
                    affiliation, lineage, antagonism, encounter, geography,
                    language, community, artifact, deity ...
    116 types       each with label, inverse, category, weight, group,
                    src_type, dst_type, and functional_inverse

So the ONLY new work is verb -> type. Everything above the type is done, and
loading it rather than restating it makes this a bridge between the two graphs
instead of a third vocabulary to reconcile.

**And the father_of note in that schema already said what we rediscovered:**

    "In Hebrew idiom 'son of' can mean any male ancestor (Matt 1:1, 'Jesus
     Christ, the son of David'); use ancestor_of for those."

That is the ancestor rule, with its worked example, written down before this
session started.

## father_of against ancestor_of

The earlier work on father_of vs ancestor_of was not to be lost.

The Hebrew *ben* spans generations — Ezra 5:1 calls Zechariah "son of Iddo"
where Zechariah 1:1 makes Iddo the grandfather — so a patronymic chain is not a
list of fathers. **Position in the chain decides**: the first link is
`father_of` and every later link is `ancestor_of`. Emitting `father_of` for the
whole chain, which the first version did, asserts three fathers for one man.

    python tools/reltypes.py
"""
from __future__ import annotations

import collections
import gzip
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

# verb stem -> the old graph's category. Ordered: the first match wins, so put
# the specific before the general.
TAXONOMY = [
    (("father_of",), "father_of", "parent_of", "kinship"),
    (("ancestor_of",), "ancestor_of", "kinship", "kinship"),
    (("fathered", "begat", "begot"), "father_of", "parent_of", "kinship"),
    (("bore", "birthed"), "mother_of", "parent_of", "kinship"),
    (("married", "took_as_wife"), "spouse_of", "kinship", "kinship"),
    (("brother", "sister"), "sibling_of", "kinship", "kinship"),

    (("said", "spoke", "told", "answered", "cried", "declared", "replied"),
     "told", "speech", "speech"),
    (("commanded", "charged", "ordered"), "charged", "speech", "speech"),
    (("asked", "inquired", "questioned"), "asked", "speech", "speech"),
    (("called", "named"), "named", "speech", "speech"),
    (("blessed",), "blessed", "speech", "speech"),
    (("cursed",), "cursed", "speech", "speech"),
    (("swore", "vowed"), "swore_to", "speech", "speech"),

    (("sent",), "sent", "motion", "motion"),
    (("went", "came", "returned", "journeyed", "fled", "followed"),
     "traveled_to", "motion", "motion"),
    (("brought", "led", "carried"), "brought", "motion", "motion"),

    (("gave", "granted"), "gave", "transfer", "transfer"),
    (("took", "seized", "received"), "took", "transfer", "transfer"),
    (("bought", "sold"), "traded_with", "transfer", "transfer"),

    (("saw", "beheld", "looked"), "saw", "perception", "perception"),
    (("heard", "listened"), "heard", "perception", "perception"),
    (("knew",), "knew", "perception", "perception"),

    (("became", "becameking", "reigned", "ruled"), "ruled_over",
     "authority", "authority"),
    (("judged",), "judged", "authority", "authority"),
    (("anointed",), "anointed", "authority", "authority"),
    (("served", "ministered"), "servant_of", "authority", "authority"),

    (("loved",), "loved", "affect", "affect"),
    (("hated",), "hated", "affect", "affect"),
    (("feared",), "feared", "affect", "affect"),

    (("killed", "slew", "struck", "smote"), "killed", "violence", "violence"),
    (("fought", "warred"), "fought", "violence", "violence"),
    (("pursued",), "pursued", "violence", "violence"),
]

# Bare prepositions that leaked through as relation types. A preposition is a
# ROLE marker, not a relation, and one showing up here means the verb was lost
# upstream -- the same defect that produced `to -> to` in Genesis 25:2.
BARE_PREPOSITION = {"to", "from", "for", "with", "in", "on", "at", "over",
                    "before", "after", "against", "unto", "adjunct"}


SCHEMA = ROOT / "ontology" / "schema" / "relationship_types.yaml"


def schema():
    """The existing hierarchy: type -> (category, domain, label, inverse)."""
    import yaml
    d = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
    cats = d.get("categories") or {}
    out = {}
    for name, spec in (d.get("types") or {}).items():
        if not isinstance(spec, dict):
            continue
        cat = spec.get("category")
        out[name] = {
            "category": cat,
            "domain": (cats.get(cat) or {}).get("domain"),
            "label": spec.get("label"),
            "inverse": spec.get("inverse"),
            "functional": bool(spec.get("functional_inverse")),
            "src_type": spec.get("src_type"),
            "dst_type": spec.get("dst_type"),
        }
    return out


def categorize(verb):
    """(category, parent, top) for a relation verb, or None."""
    v = (verb or "").lower()
    stem = v.split("_")[0]
    for keys, cat, parent, top in TAXONOMY:
        if stem in keys or v in keys:
            return cat, parent, top
    return None


def main() -> int:
    types = schema()
    rows = []
    for line in gzip.open(OUT / "person-relations.jsonl.gz", "rt",
                          encoding="utf-8"):
        rows.append(json.loads(line))

    stats = collections.Counter()
    bytop = collections.Counter()
    uncat = collections.Counter()
    for r in rows:
        n = r.get("count", 1)
        stem = (r["type"] or "").split("_")[0].lower()
        if stem in BARE_PREPOSITION:
            stats["bare_preposition"] += n
            r["category"] = None
            continue
        got = categorize(r["type"])
        if got:
            # the hand list only maps VERB -> TYPE; everything above the type
            # comes from the schema that already exists
            rel = got[0]
            spec = types.get(rel, {})
            r["relation"] = rel
            r["category"] = spec.get("category") or got[1]
            r["domain"] = spec.get("domain") or got[2]
            r["label"] = spec.get("label")
            r["inverse"] = spec.get("inverse")
            if spec.get("functional"):
                r["functional"] = True
            r["in_schema"] = rel in types
            stats["categorized"] += n
            stats["in_schema" if rel in types else "not_in_schema"] += n
            bytop[r["category"]] += n
        else:
            r["category"] = None
            stats["uncategorized"] += n
            uncat[r["type"]] += n

    tot = sum(r.get("count", 1) for r in rows)
    print("RELATION TAXONOMY — the verb kept, a category added")
    print(f"  relation instances     {tot:>7,}")
    print(f"  categorized            {stats['categorized']:>7,}   "
          f"{100*stats['categorized']//max(tot,1)}%")
    print(f"  uncategorized          {stats['uncategorized']:>7,}")
    print(f"  a bare preposition     {stats['bare_preposition']:>7,}   "
          f"the verb was lost upstream")
    print()
    print(f"  the relation is already in the schema {stats['in_schema']:>6,}")
    print(f"  mapped to a type the schema lacks       {stats['not_in_schema']:>6,}")
    print()
    print("  by category (from the existing schema):")
    for k, v in bytop.most_common():
        print(f"    {k:14}{v:>7,}")
    print()
    print("  commonest uncategorized verbs — the taxonomy's next entries:")
    print("   ", [f"{k}({v})" for k, v in uncat.most_common(10)])

    path = OUT / "person-relations-typed.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n  wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
