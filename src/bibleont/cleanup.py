"""Remove what the current rules forbid, by rule, with no judgement anywhere.

2026-08-31: it has always been the intent that bad relationships solely
referenced by verses that are passed are dropped, and then orphaned nodes are
as well; the cleanup is also a confidence tester.

The policy was never in doubt. What was missing is that it happened silently,
so a correct removal and a bug looked identical from outside, and the only way
to tell them apart was to notice something missing in the app weeks later.

So everything here is rule-driven and every removal is written down with the
rule that caused it. Nothing is decided case by case, because the moment a
cleanup starts making judgements it is editing the graph rather than enforcing
the schema on it.

## The rules

**verse-as-node.** An entity whose id is a bare verse address -- `2cor_4_1`
named "we faint not", `deut_6_10` named with the whole verse. A fragment of a
verse promoted to a thing. The address already rides on every relation's
`refs`, so the node adds nothing and invents a participant that does not
exist. 376 of them, carrying 1,318 relations of which 790 are `speaks_of`.

Deliberately NOT matched: the suffixed form, `gen_11_3_speech`. A speech act
is a real node -- `asserted_by` has to point at something -- and where it
occurs is the natural key. Lumping the two would delete the graph's whole
speech layer to remove its verse fragments.

**orphan.** A node left with no relation at all once the above has run. Not
paid for and not reachable; it exists because something used to point at it.

## What it will not do

It does not touch relations whose endpoints are both real, however poor they
look. `speaks_of` is 4,974 relations of mostly tag-cloud noise and none of it
is removed here, because "this relation is weak" is a judgement and this
module does not make any. Weak relations leave by being superseded when their
book is re-extracted, which is the other half of the 2026-08-31 intent above.

    python -m bibleont.cleanup            report, change nothing
    python -m bibleont.cleanup --apply    remove, recording every reason
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from .paths import ONTOLOGY

STAGING = ONTOLOGY / "staging"
LEDGER = ONTOLOGY / "proposals" / ".held" / "cleanup.jsonl"

# A bare verse address as an entity id. The suffixed form is excluded on
# purpose -- see the module docstring.
BARE_VERSE = re.compile(r"^[1-3]?[a-z]+_\d+_\d+$")


def _rows(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()]


def _write(p: Path, rows: list[dict]) -> None:
    with p.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def plan() -> dict:
    """What the rules would remove, without removing it."""
    ents: dict[str, tuple[Path, dict]] = {}
    rels: list[tuple[Path, dict]] = []
    for d in sorted(STAGING.iterdir()):
        if not d.is_dir():
            continue
        for e in _rows(d / "entities.jsonl"):
            if e.get("id"):
                ents.setdefault(e["id"], (d, e))
        for r in _rows(d / "relations.jsonl"):
            rels.append((d, r))

    verse_nodes = {i for i in ents if BARE_VERSE.match(i)}
    doomed_rel = [(d, r) for d, r in rels
                  if r.get("src") in verse_nodes or r.get("dst") in verse_nodes]

    # Which nodes are left with nothing once those relations go. Computed on
    # what SURVIVES, not on what is removed, because a node can be touched by
    # both a doomed relation and a sound one.
    doomed_ids = {id(r) for _, r in doomed_rel}
    survivors = [(d, r) for d, r in rels if id(r) not in doomed_ids]

    still_used: set[str] = set()
    for _, r in survivors:
        still_used.add(r.get("src"))
        still_used.add(r.get("dst"))

    # Split, because they are two different decisions wearing one word.
    #
    # A node orphaned BY this cleanup is the second half of the rule as
    # stated: the verse node went, so what only it referenced goes too.
    #
    # A node that was ALREADY orphaned was declared and never used by
    # anything, and removing it is a separate cleanup with its own
    # justification. Reporting them together made `abishag` -- a real person
    # with no relations at all -- look like collateral from the verse-node
    # rule, which she is not.
    used_before: set[str] = set()
    for _, r in rels:
        used_before.add(r.get("src"))
        used_before.add(r.get("dst"))

    orphans = sorted(i for i in ents
                     if i not in still_used and i not in verse_nodes)
    already = sorted(i for i in orphans if i not in used_before)
    caused = sorted(i for i in orphans if i in used_before)

    by_batch: dict[str, int] = defaultdict(int)
    for d, _ in doomed_rel:
        by_batch[d.name] += 1

    return {"verse_nodes": sorted(verse_nodes), "relations": doomed_rel,
            "orphans": caused, "already": already,
            "by_batch": dict(by_batch), "ents": ents}


def apply(p: dict) -> int:
    """Remove them, recording every removal with the rule that caused it."""
    verse_nodes = set(p["verse_nodes"])
    orphans = set(p["orphans"])
    doomed = {id(r) for _, r in p["relations"]}

    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    removed = 0
    with LEDGER.open("a", encoding="utf-8", newline="\n") as log:
        for d in sorted(STAGING.iterdir()):
            if not d.is_dir():
                continue

            rf = d / "relations.jsonl"
            rows = _rows(rf)
            keep = []
            for r in rows:
                if id(r) in doomed or r.get("src") in verse_nodes \
                        or r.get("dst") in verse_nodes:
                    r["_removed_by"] = "cleanup/verse-as-node"
                    r["_batch"] = d.name
                    log.write(json.dumps(r, ensure_ascii=False) + "\n")
                    removed += 1
                else:
                    keep.append(r)
            if len(keep) != len(rows):
                _write(rf, keep)

            ef = d / "entities.jsonl"
            rows = _rows(ef)
            keep = []
            for e in rows:
                eid = e.get("id")
                if eid in verse_nodes or eid in orphans:
                    e["_removed_by"] = ("cleanup/verse-as-node"
                                        if eid in verse_nodes
                                        else "cleanup/orphan")
                    e["_batch"] = d.name
                    log.write(json.dumps(e, ensure_ascii=False) + "\n")
                    removed += 1
                else:
                    keep.append(e)
            if len(keep) != len(rows):
                _write(ef, keep)
    return removed


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = plan()

    print(f"  verse-as-node   {len(p['verse_nodes']):>5} entities")
    print(f"  their relations {len(p['relations']):>5}")
    print(f"  orphaned BY it  {len(p['orphans']):>5} entities")
    print(f"  already orphans {len(p['already']):>5} entities  "
          f"(declared and never used -- NOT removed here)")
    print()
    print("  by batch:")
    for b, n in sorted(p["by_batch"].items(), key=lambda kv: -kv[1])[:10]:
        print(f"    {b:<34} {n:>5} relation(s)")

    if p["orphans"]:
        print()
        print("  a sample of what THIS cleanup leaves with nothing:")
        for i in p["orphans"][:8]:
            e = p["ents"][i][1]
            print(f"    {i:<34} {e.get('type', '?')}")

    if "--apply" not in argv:
        print()
        print("  report only. --apply removes them and writes every removal,")
        print(f"  with the rule that caused it, to")
        print(f"  {LEDGER.relative_to(ONTOLOGY.parent)}")
        return 0

    n = apply(p)
    print()
    print(f"  removed {n} record(s); every one logged with its rule")
    print("  next: python -m bibleont.merge && python -m bibleont.lemma apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
