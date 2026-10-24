"""Proper nouns the corpus uses and the graph has no name for.

`coverage` counts chapters and tells you *where* the graph is thin. This names
*what* is missing, which is the difference between "Judges 20 has no citations"
and "the graph has never heard of Zacharias, and the text says it eleven times".

Two kinds of miss come out together, and only a reader can tell them apart:

- **A missing entity.** Caesar appears in 24 verses and is not in the graph.
- **A missing name for an entity that is there.** The graph knew Melchizedek
  and the King James Version spells him Melchisedec, so nine of his eleven
  verses matched nothing -- including every verse of the book that is mostly
  about him. That miss is worse than an absence, because the entity looks
  present while its own text cannot reach it.

The second kind clusters: the New Testament uses Greek-derived spellings for
Old Testament names throughout -- Elias, Esaias, Jonas, Gedeon, Jephthae -- and
finding one is a reason to look for the rest.

## What counts as a proper noun

A word the corpus never writes in lower case. That is the whole test, and it
works because this corpus is consistent about it: `Behold` and `Wherefore` open
sentences constantly but also appear mid-sentence in lower case, while `Nebat`
and `Arnon` never do. Capitalisation alone is useless here -- the King James
Version capitalises after "saying," -- and a stopword list would need to know
which words are names, which is the question being asked.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .books import BOOK_ORDER
from .corpus import get_corpus
from .graph import Store

WORD = re.compile(r"\b([A-Za-z]{3,})\b")


@dataclass
class Gap:
    """A proper noun with no matching name in the graph."""

    word: str
    count: int
    first: str  # pretty reference of the first occurrence
    books: list[str] = field(default_factory=list)

    @property
    def spread(self) -> int:
        return len(self.books)


def _known_words(store: Store) -> set[str]:
    """Every word appearing in any entity name or alias.

    Word-level rather than whole-name, so "the tribe of Judah" contributes
    `judah` and a bare "Judah" in the text is not reported as unknown.
    """
    out: set[str] = set()
    for person in store.people.values():
        for name in person.names():
            for word in WORD.findall(name):
                out.add(word.lower())
    return out


def survey(store: Store | None = None, book: str | None = None) -> list[Gap]:
    store = store or Store.load()
    corpus = get_corpus()
    known = _known_words(store)

    lower: Counter[str] = Counter()
    upper: Counter[str] = Counter()
    first: dict[str, str] = {}
    books: dict[str, set[str]] = {}

    for verse in corpus.iter_verses():
        if book and verse.id.book != book:
            continue
        for match in WORD.finditer(verse.text):
            word = match.group(1)
            key = word.lower()
            if word[0].isupper():
                upper[key] += 1
                first.setdefault(key, verse.id.pretty())
                books.setdefault(key, set()).add(verse.id.book)
            else:
                lower[key] += 1

    gaps = [
        Gap(word=w, count=n, first=first[w],
            books=sorted(books[w], key=lambda b: BOOK_ORDER.get(b, 999)))
        for w, n in upper.items()
        if lower[w] == 0 and w not in known
    ]
    gaps.sort(key=lambda g: (-g.count, g.word))
    return gaps


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Proper nouns the graph has no name for."
    )
    ap.add_argument("--book", help="restrict to one book, by its id (Heb, Lev)")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument(
        "--min-count", type=int, default=1,
        help="ignore words occurring fewer times than this",
    )
    args = ap.parse_args(argv)

    rows = [g for g in survey(book=args.book) if g.count >= args.min_count]
    total = sum(g.count for g in rows)
    print(f"{len(rows)} unmatched proper nouns, {total} occurrences\n")
    for gap in rows[: args.limit]:
        where = gap.first if gap.spread == 1 else f"{gap.first} (+{gap.spread - 1} books)"
        print(f"  {gap.count:5}  {gap.word:20} {where}")
    if len(rows) > args.limit:
        print(f"\n  ... {len(rows) - args.limit} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
