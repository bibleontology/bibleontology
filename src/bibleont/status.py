"""What is covered, what is staged, and what is still missing.

Extraction runs get interrupted — session limits, crashes, a batch that never
passes its check. This answers the question that follows: where did it stop, and
what has to be re-run?

Coverage is measured from the citations themselves, not from a list of which
batches were launched, so it stays honest even if a batch half-finished or a
book was covered incidentally by another batch.

Usage:
    python -m bibleont.status
    python -m bibleont.status --missing     # just the book ids still to do
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from .books import BOOK_IDS, BOOK_TESTAMENT, BOOK_TITLE
from .paths import ONTOLOGY
from .refs import RefError, parse_ref
from .schema import load_persons, load_relations

STAGING = ONTOLOGY / "staging"


def coverage() -> dict[str, int]:
    """Relations citing each book, by book id."""
    counts: dict[str, int] = defaultdict(int)
    for rel in load_relations():
        books = set()
        for ref in rel.refs:
            try:
                books.add(parse_ref(ref).book)
            except RefError:
                continue
        for book in books:
            counts[book] += 1
    return counts


def batches() -> list[dict]:
    """Every staged batch and whether it currently passes its own check."""
    from .check_extraction import check

    out = []
    if not STAGING.exists():
        return out
    for d in sorted(STAGING.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        has_persons = (d / "entities.jsonl").exists() or (d / "persons.jsonl").exists()
        has_relations = (d / "relations.jsonl").exists()
        if not (has_persons and has_relations):
            out.append({
                "name": d.name,
                "state": "incomplete",
                "detail": "missing " + ", ".join(
                    n for n, ok in (("persons.jsonl", has_persons),
                                    ("relations.jsonl", has_relations)) if not ok
                ),
                "persons": 0, "relations": 0,
            })
            continue
        result = check(d)
        out.append({
            "name": d.name,
            "state": "passing" if result["ok"] else "failing",
            "detail": (f"{len(result['errors'])} errors"
                       if not result["ok"] else
                       f"{len(result['warnings'])} warnings"),
            "persons": result["persons"],
            "relations": result["relations"],
        })
    return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    counts = coverage()
    missing = [b for b in BOOK_IDS if not counts.get(b)]

    if "--missing" in argv:
        print(" ".join(missing))
        return 0

    people, relations = load_persons(), load_relations()

    print("BATCHES")
    rows = batches()
    if not rows:
        print("  none staged")
    for r in rows:
        mark = {"passing": "ok  ", "failing": "FAIL", "incomplete": "PART"}[r["state"]]
        print(f"  {mark} {r['name']:24} {r['persons']:4}p {r['relations']:4}r  {r['detail']}")
    failing = [r for r in rows if r["state"] != "passing"]
    if failing:
        print(f"\n  {len(failing)} batch(es) not merged. Re-run:")
        for r in failing:
            print(f"    python -m bibleont.check_extraction ontology/staging/{r['name']}")

    print("\nCOVERAGE BY BOOK  (relations citing each book)")
    for testament in ("OT", "NT"):
        ids = [b for b in BOOK_IDS if BOOK_TESTAMENT[b] == testament]
        done = [b for b in ids if counts.get(b)]
        print(f"\n  {testament}: {len(done)}/{len(ids)} books have at least one relation")
        line = []
        for b in ids:
            n = counts.get(b, 0)
            line.append(f"{b}:{n}" if n else f"{b}:-")
        # wrap at a readable width
        buf = "   "
        for item in line:
            if len(buf) + len(item) + 1 > 78:
                print(buf)
                buf = "   "
            buf += " " + item
        if buf.strip():
            print(buf)

    print(f"\nTOTAL  {len(people)} people, {len(relations)} relations, "
          f"{66 - len(missing)}/66 books covered")
    if missing:
        print(f"\nNOT YET EXTRACTED ({len(missing)} books)")
        print("  " + " ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
