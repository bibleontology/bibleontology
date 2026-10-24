"""Per-book state of the graph: how much is there, and how worked it is.

Every number here is computed from the corpus and the graph. **Nothing on this
report is written by hand**, and that is the whole design constraint: a
hand-kept status page is a second thing to maintain, and it starts drifting the
day after it is written. The same rule the About view's figures follow.

## Why there is no single completeness score

Two obvious measures were tried and both mislead, in opposite directions.

**Chapter coverage lies about small books.** A one-chapter epistle reaches
100% the moment one citation lands anywhere in it: 2 John shows full coverage
on thirteen verses and a single relation. Coverage measures breadth of
contact -- whether the graph has touched a chapter at all -- and says nothing
about how much of it was read.

**Density lies about rosters.** Ranked by relations per hundred verses, Ezra
and Nehemiah lead the corpus by a wide margin, because name lists produce many
cheap parentage and membership edges. High density there records a genealogy,
not an understanding.

Both are the same error the project has now met three times: **a count measures
the habit that produced it.** Genesis 22 counted as covered on the strength of
a genealogy appended to its last five verses while the binding of Isaac held
two edges; the Song of Solomon leads the corpus in stated comparisons because
it catalogues a body.

## Two families, reported separately

The measures split in two, because a book can be exhaustively indexed and
barely read, and one set of numbers cannot say both.

**The record** -- who was there and what happened.

  breadth   share of chapters carrying any citation
  density   relations per 100 verses
  depth     of the people who *act* in this book, the share of their acting
            chapters here that any relation follows

**The meaning** -- what the book says, which is what this project is for.
Counted separately because it is nowhere near as numerous and would vanish
inside a combined figure. A node or an edge belongs here when it is a figure,
a saying, a verdict, a covenant or an observance, or when the relation itself
is interpretive (`signifies`, `likened_to`, `assessed_as`, `party_to`). These
are the edges that cannot be read off a list: something has to be understood
before they can be placed.

**Depth is the one to trust in the first family.** It found Abraham unfollowed
in nine chapters and David in seventeen, and no roster can inflate it -- a
list of names produces no acting verbs. Where nobody acts in a book, depth is
`None` rather than 1.0: reporting a perfect score there put 1 John, which has
no nodes and no relations at all, at the top of a depth sort.

## Why the two must not be added together

Raw counts are dominated by books that list people. Joshua carries the largest
node count in the corpus because of the allotment lists and Ezra the highest
density because of the caravan rosters; both sit near the bottom on depth and
**both hold essentially no meaning edges at all**. As bare totals they would
head every column on this page and tell a reader the opposite of the truth.

The second family also fails on its own. Psalms shows the highest meaning
*share* in the corpus at 62% -- on five relations. A share of almost nothing
is not an achievement, which is why the count, the rate per hundred verses and
the share are all shown and none of them is a score.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .corpus import BOOK_ORDER, BOOK_TITLE, get_corpus
from .graph import Store
from . import prominence

_REF = re.compile(r"^((?:[123]\s?)?[A-Za-z]+)\s+(\d+)")


def _book(ref: str) -> str | None:
    m = _REF.match(ref)
    return m.group(1) if m else None


def _chapter(ref: str) -> tuple[str, int] | None:
    m = _REF.match(ref)
    return (m.group(1), int(m.group(2))) if m else None


def _categories() -> dict[str, str]:
    """Relation type -> its declared category, read from the schema."""
    from .schema import load_vocabulary

    return {k: (v.category or "") for k, v in load_vocabulary().types.items()}


# What a roster produces. Who begat whom, who belonged to which tribe, which
# town lay in which territory -- extractable from a list without reading a
# sentence of narrative.
ROSTER_CATEGORIES = frozenset({"kinship", "lineage", "geography", "community"})

# The second family, and the one this project exists for. A relation counts as
# meaning when either end is a figure, a saying, a verdict, a covenant or an
# observance, or when the relation itself is one of the interpretive kinds --
# `signifies`, `likened_to`, `assessed_as`, `party_to`. These are the edges
# that cannot be read off a list: something has to be understood to place them.
MEANING_TYPES = frozenset(
    {"image", "text", "assessment", "covenant", "observance", "title"})
MEANING_CATEGORIES = frozenset({"imagery", "assessment", "covenant"})


@dataclass
class BookStats:
    book: str
    title: str
    chapters: int = 0
    verses: int = 0
    words: int = 0
    nodes: int = 0
    node_types: dict[str, int] = field(default_factory=dict)
    inner: int = 0
    outer: int = 0
    roster: int = 0            # relations in the roster categories
    meaning: int = 0           # relations touching figure, saying, verdict...
    meaning_nodes: int = 0
    categories: dict[str, int] = field(default_factory=dict)
    cited_chapters: int = 0
    # (person, chapter) pairs, not chapters: several people act in one
    # chapter and each is followed or not separately. Genesis has 50 chapters
    # and 300-odd such pairs.
    acting: int = 0
    acting_followed: int = 0
    links: dict[str, int] = field(default_factory=dict)

    @property
    def relations(self) -> int:
        return self.inner + self.outer

    @property
    def breadth(self) -> float:
        return self.cited_chapters / self.chapters if self.chapters else 0.0

    @property
    def density(self) -> float:
        return self.relations / self.verses * 100 if self.verses else 0.0

    @property
    def depth(self) -> float | None:
        """The measure to trust, and None where there is nothing to measure.

        Returning 1.0 for a book nobody acts in reads as a perfect score and
        is not one: it made 1 John, which has no nodes and no relations, sit
        at the top of a depth sort.
        """
        if not self.acting:
            return None
        return self.acting_followed / self.acting

    @property
    def beyond(self) -> float | None:
        """Share of relations that took reading rather than indexing."""
        if not self.relations:
            return None
        return (self.relations - self.roster) / self.relations

    @property
    def meaning_per_100(self) -> float:
        """Interpretive edges per 100 verses -- the second family, reported
        on its own scale because it is nowhere near as numerous as the first
        and would vanish inside a combined figure."""
        return self.meaning / self.verses * 100 if self.verses else 0.0

    @property
    def meaning_share(self) -> float | None:
        if not self.relations:
            return None
        return self.meaning / self.relations

    @property
    def band(self) -> str:
        """A word, from all four measures, so the table can be scanned.

        Deliberately coarse. A finer scale would imply a precision the inputs
        do not have, and the numbers are shown beside it anyway.
        """
        if self.relations == 0:
            return "untouched"
        # A handful of edges is not a worked book however small it is. Two
        # John reached "worked" on thirteen verses and one relation before
        # this line existed.
        if self.relations < 5 or self.nodes < 5:
            return "touched"
        if self.beyond is not None and self.beyond < 0.25:
            return "indexed"
        if self.depth is not None and self.depth < 0.5:
            return "thin"
        if self.breadth < 0.35:
            return "thin"
        if self.breadth >= 0.75 and (self.depth or 0) >= 0.75:
            return "worked"
        return "surveyed"


def survey(store: Store | None = None) -> list[BookStats]:
    store = store or Store.load()
    corpus = get_corpus()

    rows = {b: BookStats(b, BOOK_TITLE.get(b, b)) for b in BOOK_ORDER}

    seen_chapters: dict[str, set[int]] = defaultdict(set)
    for v in corpus.iter_verses():
        r = rows.get(v.id.book)
        if r is None:
            continue
        r.verses += 1
        r.words += len(v.text.split())
        seen_chapters[v.id.book].add(v.id.chapter)
    for b, chs in seen_chapters.items():
        rows[b].chapters = len(chs)

    # A node belongs to every book its own citations name. Entities are not
    # owned by one book -- Moses is in five -- so this counts presence, not
    # possession, and the columns therefore sum to more than the graph.
    for p in store.people.values():
        for ref in p.refs:
            b = _book(ref)
            if b in rows:
                rows[b].nodes += 1
                rows[b].node_types[p.type] = rows[b].node_types.get(p.type, 0) + 1
                if p.type in MEANING_TYPES:
                    rows[b].meaning_nodes += 1

    category = _categories()
    types = {p.id: p.type for p in store.people.values()}
    cited: dict[str, set[int]] = defaultdict(set)
    for rel in store.relations:
        books = {_book(x) for x in rel.refs} - {None}
        cat = category.get(rel.type, "")
        interpretive = (
            cat in MEANING_CATEGORIES
            or types.get(rel.src) in MEANING_TYPES
            or types.get(rel.dst) in MEANING_TYPES
        )
        for b in books:
            if b in rows:
                rows[b].categories[cat] = rows[b].categories.get(cat, 0) + 1
                if cat in ROSTER_CATEGORIES:
                    rows[b].roster += 1
                if interpretive:
                    rows[b].meaning += 1
        for x in rel.refs:
            ch = _chapter(x)
            if ch and ch[0] in rows:
                cited[ch[0]].add(ch[1])
        if len(books) == 1:
            b = next(iter(books))
            if b in rows:
                rows[b].inner += 1
        else:
            for b in books:
                if b in rows:
                    rows[b].outer += 1
                    for other in books:
                        if other != b and other in rows:
                            rows[b].links[other] = rows[b].links.get(other, 0) + 1
    for b, chs in cited.items():
        if b in rows:
            rows[b].cited_chapters = len(chs)

    # Depth, inverted out of the per-person survey: every (person, chapter)
    # where somebody acts, and whether any relation touching them cites it.
    for reach in prominence.survey(store):
        for ch in reach.acting:
            b = ch.rsplit(" ", 1)[0]
            if b not in rows:
                continue
            rows[b].acting += 1
            if ch in reach.held:
                rows[b].acting_followed += 1

    return [rows[b] for b in BOOK_ORDER]


@dataclass
class WorkItem:
    """One prioritised piece of outstanding work, derived not written."""

    book: str
    kind: str          # "untouched" | "no meaning" | "unfollowed" | "dense"
    detail: str
    weight: float

    def __str__(self) -> str:
        return f"{self.book:7} {self.kind:12} {self.detail}"


def worklist(rows: list[BookStats] | None = None, limit: int = 30) \
        -> list[WorkItem]:
    """The to-do list, generated from the same numbers as the table.

    **This is the part that must never be hand-written.** A typed-in list of
    priorities is a second artefact to maintain and it starts drifting the day
    after it is made; the About view's figures and the questions page follow
    the same rule for the same reason.

    Weighting favours size and neglect together: a large book with nothing in
    it outranks a small one, and a book with no interpretive edges at all
    outranks one that merely has few, because the first is a gap in what the
    project is for and the second is a matter of degree.
    """
    rows = rows or survey()
    items: list[WorkItem] = []
    for r in rows:
        if r.verses < 20:
            continue
        if r.relations == 0:
            items.append(WorkItem(
                r.book, "untouched",
                f"{r.verses} verses, nothing cites it", r.verses * 3))
            continue
        if r.meaning == 0:
            items.append(WorkItem(
                r.book, "no meaning",
                f"{r.relations} relations, none interpretive", r.verses * 2))
        elif r.meaning_per_100 < 1.0:
            items.append(WorkItem(
                r.book, "little meaning",
                f"{r.meaning} interpretive edges in {r.verses} verses",
                r.verses))
        if r.depth is not None and r.depth < 0.5 and r.acting >= 10:
            missed = r.acting - r.acting_followed
            items.append(WorkItem(
                r.book, "unfollowed",
                f"{missed} person-chapters nothing records",
                missed * 20))
    items.sort(key=lambda i: -i.weight)
    return items[:limit]


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--sort",
        choices=["order", "depth", "breadth", "density", "meaning",
                 "meaning_per_100", "meaning_share"],
        default="order")
    ap.add_argument("--band", help="show only books in this band")
    ap.add_argument("--work", action="store_true",
                    help="the generated worklist instead of the table")
    args = ap.parse_args(argv)

    rows = survey()
    if args.work:
        for item in worklist(rows):
            print(f"  {item}")
        return 0
    if args.sort != "order":
        rows.sort(key=lambda r: (getattr(r, args.sort) is None,
                                 getattr(r, args.sort) or 0))
    if args.band:
        rows = [r for r in rows if r.band == args.band]

    def pct(x):
        return "   -- " if x is None else f"{x * 100:5.0f}%"

    print("                     THE RECORD                 THE MEANING")
    print(f"{'book':7}{'vs':>6}{'nodes':>7}{'rels':>6}{'brdth':>7}{'dens':>7}"
          f"{'depth':>7}   {'nodes':>6}{'rels':>6}{'/100v':>7}{'share':>7}"
          f"  band")
    for r in rows:
        print(f"{r.book:7}{r.verses:6}{r.nodes:7}{r.relations:6}"
              f"{pct(r.breadth)}{r.density:7.1f}{pct(r.depth)}   "
              f"{r.meaning_nodes:6}{r.meaning:6}{r.meaning_per_100:7.1f}"
              f"{pct(r.meaning_share)}  {r.band}")

    bands = defaultdict(int)
    for r in survey():
        bands[r.band] += 1
    print("\n" + "  ".join(f"{k}: {v}" for k, v in sorted(bands.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
