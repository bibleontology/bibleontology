"""Chapter-level coverage: which passages the graph has never cited.

Existing status reporting is per *book*, and that granularity hid a real hole.
1 Kings looked extracted -- it has 13 covered chapters -- while 1 Kings 10 had
zero citations, so the queen of Sheba was absent and nothing reported it. A book
is not a unit of work; a chapter is.

The report separates two things that look identical in a coverage number:

- a chapter with no citations because **nothing in it was extracted**
- a chapter with no citations because **it holds no relations of these kinds**

Genesis 1 has no person-to-person relation. Exodus 25-30 is construction
specification. Job 3-37 is dialogue. Those are correctly empty, and counting
them as gaps would produce a frightening number that means nothing.

They are told apart by how many entity names the graph already knows appear in
the chapter. That is a triage signal and not proof -- it is blind to figures
identified by title rather than name, which is its own known gap -- so a high
count means "look here", never "this is wrong".
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from .corpus import BOOK_ORDER, get_corpus
from .graph import Store
from .refs import parse_ref

# A chapter naming at least this many known entities is unlikely to be
# legitimately empty. Tuned to be generous: the cost of looking at a chapter
# that turns out to be empty is small, and the cost of skipping a full one is
# the queen of Sheba.
BUSY = 20


@dataclass
class ChapterCoverage:
    book: str
    chapter: int
    verses: int
    cited_verses: int
    known_mentions: int
    distinct_names: int

    @property
    def covered(self) -> bool:
        return self.cited_verses > 0

    @property
    def suspect(self) -> bool:
        """Uncited, but full of people the graph already knows about."""
        return not self.covered and self.known_mentions >= BUSY

    def __str__(self) -> str:
        return f"{self.book} {self.chapter}"


def _cited_verses(store: Store) -> set[str]:
    corpus = get_corpus()
    out: set[str] = set()
    for rel in store.relations:
        for ref in rel.refs:
            try:
                out.update(str(v) for v in corpus.expand(parse_ref(ref)))
            except Exception:
                # A malformed citation is validate's problem, not coverage's.
                continue
    return out


@lru_cache(maxsize=1)
def _name_pattern(store_id: int = 0) -> re.Pattern[str]:
    store = Store.load()
    names: set[str] = set()
    for entity in store.people.values():
        for name in [entity.name, *(getattr(entity, "aliases", None) or [])]:
            name = name.strip()
            # Single words only: multi-word names are mostly disambiguating
            # phrases ("Sheba the son of Bichri") rather than surface forms.
            if len(name) > 3 and " " not in name:
                names.add(name.lower())
    joined = "|".join(sorted(map(re.escape, names), key=len, reverse=True))
    return re.compile(rf"\b({joined})\b", re.I)


def survey(store: Store | None = None) -> list[ChapterCoverage]:
    store = store or Store.load()
    corpus = get_corpus()
    cited = _cited_verses(store)
    pattern = _name_pattern()

    rows: list[ChapterCoverage] = []
    for book in BOOK_ORDER:
        for chapter in range(1, (corpus.book_chapters(book) or 0) + 1):
            verses = corpus.chapter(book, chapter)
            if not verses:
                continue
            hit = sum(1 for v in verses if str(v.id) in cited)
            found = pattern.findall(" ".join(v.text for v in verses))
            rows.append(
                ChapterCoverage(
                    book=book,
                    chapter=chapter,
                    verses=len(verses),
                    cited_verses=hit,
                    known_mentions=len(found),
                    distinct_names=len({f.lower() for f in found}),
                )
            )
    return rows


def worklist(rows: list[ChapterCoverage] | None = None) -> list[ChapterCoverage]:
    """Uncited chapters most likely to be genuine gaps, densest first."""
    rows = rows if rows is not None else survey()
    return sorted(
        (r for r in rows if r.suspect),
        key=lambda r: (-r.known_mentions, r.book, r.chapter),
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Chapter-level citation coverage.")
    ap.add_argument("--book", help="restrict to one book")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument(
        "--all", action="store_true", help="every chapter, not just the worklist"
    )
    args = ap.parse_args(argv)

    rows = survey()
    if args.book:
        rows = [r for r in rows if r.book.lower() == args.book.lower()]

    total = len(rows)
    covered = sum(1 for r in rows if r.covered)
    suspect = [r for r in rows if r.suspect]
    empty = [r for r in rows if not r.covered and r.known_mentions == 0]

    print(f"chapters:            {total}")
    print(f"with any citation:   {covered} ({covered / total:.0%})")
    print(f"uncited but busy:    {len(suspect)}   <- the work list")
    print(f"uncited and nameless:{len(empty):>4}   (likely genuinely empty)")

    if args.all:
        print()
        for r in rows:
            mark = "ok " if r.covered else ("GAP" if r.suspect else " . ")
            print(
                f"  {mark} {r.book:6} {r.chapter:>3}  "
                f"cited {r.cited_verses:>3}/{r.verses:<3}  names {r.known_mentions:>3}"
            )
        return 0

    print(f"\nuncited chapters by known-entity density (top {args.limit}):")
    print(f"  {'mentions':>8} {'distinct':>8}  chapter")
    for r in worklist(rows)[: args.limit]:
        print(f"  {r.known_mentions:>8} {r.distinct_names:>8}  {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
