"""Verses that announce they are quoting something.

The phrase layer finds shared wording. It cannot tell a quotation from a
formula, and no weighting fixes that -- six ranking schemes and three cap
relaxations established it, because both are the same words in two places and
every property computable from the content belongs to formulas too.

What separates them is whether the later writer was *pointing at* the earlier
one, and that is intent. It is not in the counts.

But it is sometimes in the text. "As it is written", "to fulfill what was spoken
through the prophet Isaiah", "David saith" -- these are the corpus
declaring the relationship in so many words. That declaration is a fact about
the text, checkable by anyone, and needs no inference at all.

So this module reads the declarations and stops there. It does **not** decide
what is being quoted. Where the phrase layer independently places a source, the
two agree and the link can be shown as asserted rather than merely shared. Where
it cannot, the honest output is "this verse says it is quoting something, and we
have not placed it" -- which is a gap worth showing a reader and a worklist worth
having, and is a great deal more useful than a guess.

Two things this deliberately does not do:

- **Name a source the text does not name.** Most announcements say only "it is
  written". Roughly one in six names a prophet. Where no name is given, none is
  recorded, however obvious the source may seem.
- **Treat "thus saith the LORD" as a citation.** It occurs in 124 Old Testament
  verses and announces prophetic speech, not a written source. Reading it as a
  citation formula would swamp the real ones several times over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .books import BOOK_TESTAMENT
from .corpus import get_corpus


# How strong a claim the formula makes. Kept separate from the pattern because
# a reader is owed the difference: "as it is written" asserts a written source,
# while "spoken by the prophet" asserts a speaker who may or may not be being
# quoted from a book.
WRITTEN = "written"  # names a written source
SPOKEN = "spoken"  # attributes to a speaker
FULFILLED = "fulfilled"  # claims an earlier saying is being answered


@dataclass(frozen=True)
class Formula:
    pattern: re.Pattern
    kind: str
    label: str


def _p(rx: str) -> re.Pattern:
    return re.compile(rx, re.I)


# Ordered longest-claim-first only for readability; every formula is tested and
# a verse may match several.
FORMULAS: list[Formula] = [
    Formula(_p(r"\bas it is written\b"), WRITTEN, "as it is written"),
    Formula(_p(r"\bit is written\b"), WRITTEN, "it is written"),
    Formula(_p(r"\bwhich was written\b"), WRITTEN, "which was written"),
    Formula(_p(r"\bthe scriptures?\s+(saith|say|said)\b"), WRITTEN, "the scripture saith"),
    Formula(_p(r"\baccording to the scriptures?\b"), WRITTEN, "according to the scriptures"),
    # "the book of life" is not a citation of anything. Four verses -- Phil 4:3
    # and three in Revelation -- and without the exclusion they are the only
    # false positives this list produces.
    Formula(_p(r"\bin the book of\b(?!\s+life\b)"), WRITTEN, "in the book of"),
    Formula(_p(r"\bthe law\s+(saith|said)\b"), WRITTEN, "the law saith"),
    Formula(_p(r"\bwritten in the (law|prophets?|psalms?)\b"), WRITTEN, "written in"),
    Formula(_p(r"\bthat which was spoken\b"), SPOKEN, "that which was spoken"),
    Formula(_p(r"\bwhich was spoken by\b"), SPOKEN, "which was spoken by"),
    Formula(_p(r"\bspoken by the (prophet|prophets)\b"), SPOKEN, "spoken by the prophet"),
    # Hebrews 7:14 -- "a tribe as to which Moses said nothing about
    # priests" -- is a denial that a source says something, which is the
    # opposite of a citation and would be recorded as one without the guard.
    Formula(_p(r"\b(moses|david|esaias|isaiah|elias|daniel|joel)\s+"
               r"(saith|said|spake|wrote)\b(?!\s+nothing\b)"),
            SPOKEN, "named speaker"),
    # "Ye have heard that it was said" -- the Sermon on the Mount's way of
    # citing the law, six times in Matthew 5. It names no book and no speaker,
    # attributing only to "them of old time", so it is a SPOKEN claim: the text
    # says it is quoting, and declines to say from where.
    Formula(_p(r"\bye have heard that it (was|hath been) said\b"), SPOKEN,
            "ye have heard that it was said"),
    Formula(_p(r"\bit hath been said\b"), SPOKEN, "it hath been said"),
    Formula(_p(r"\b(might|should)\s+be\s+fulfilled\b"), FULFILLED, "might be fulfilled"),
    Formula(_p(r"\bwas fulfilled which\b"), FULFILLED, "was fulfilled which"),
]


# Names the text uses for a source, and the book they point at. Only where the
# identification is the text's own and not a scholarly one: "Esaias" is the KJV
# spelling of Isaiah, and "the book of Psalms" is the book of Psalms.
#
# `david` is deliberately absent. Acts 2:25 has "David speaketh concerning him",
# and the quotation is from a psalm -- but the text attributes it to the man,
# not to the book, and the graph should record the man. Collapsing him into
# "Psalms" would be an editorial identification wearing the text's clothes.
#
# Values are canonical book codes, not display titles, so they compare directly
# against `VerseId.book` -- the first version stored "Isaiah" and compared it to
# "Isa", which reported that the text and the wording disagreed in all thirteen
# cases when they in fact agree in most.
NAMED_SOURCE: dict[str, str] = {
    "esaias": "Isa",
    "isaiah": "Isa",
    "jeremy": "Jer",
    "jeremias": "Jer",
    "jeremiah": "Jer",
    "joel": "Joel",
    "osee": "Hos",
    "daniel": "Dan",
    "malachi": "Mal",
    "jonas": "Jonah",
}

_NAME_RX = _p(r"\b(" + "|".join(NAMED_SOURCE) + r")\b")

# Attributions the text makes to a person or a body of writing rather than to a
# book. Recorded as stated, and not resolved to a book.
_SPEAKER_RX = _p(r"\b(moses|david|elias|the prophets?|the law|the psalms?)\b")


@dataclass
class Announcement:
    """A verse stating that it is quoting or fulfilling something."""

    verse: str  # canonical verse id
    pretty: str
    text: str
    book: str = ""
    chapter: int = 0
    number: int = 0
    kinds: set[str] = field(default_factory=set)
    labels: list[str] = field(default_factory=list)
    named_books: list[str] = field(default_factory=list)
    named_speakers: list[str] = field(default_factory=list)

    @property
    def names_a_source(self) -> bool:
        return bool(self.named_books or self.named_speakers)

    def why(self) -> str:
        bits = ", ".join(self.labels)
        if self.named_books:
            bits += f" -> {', '.join(self.named_books)}"
        elif self.named_speakers:
            bits += f" -> {', '.join(self.named_speakers)} (not resolved to a book)"
        return bits


def announcements(nt_only: bool = False) -> list[Announcement]:
    """Every verse carrying a citation formula.

    The Old Testament quotes itself -- Chronicles retells Kings, Daniel reads
    Jeremiah -- so it is included by default. `nt_only` is for measuring against
    the New Testament quotation lists, which is the only place a published
    ground truth exists to check against.
    """
    corpus = get_corpus()
    out: list[Announcement] = []
    for v in corpus.iter_verses():
        if nt_only and BOOK_TESTAMENT.get(v.id.book) != "NT":
            continue
        hits = [f for f in FORMULAS if f.pattern.search(v.text)]
        if not hits:
            continue
        ann = Announcement(
            verse=str(v.id),
            pretty=v.id.pretty(),
            text=v.text,
            book=v.id.book,
            chapter=v.id.chapter,
            number=v.id.verse,
            kinds={f.kind for f in hits},
            labels=[f.label for f in hits],
        )
        seen: set[str] = set()
        for m in _NAME_RX.finditer(v.text):
            book = NAMED_SOURCE[m.group(1).lower()]
            if book not in seen:
                seen.add(book)
                ann.named_books.append(book)
        for m in _SPEAKER_RX.finditer(v.text):
            who = m.group(1).lower()
            if who not in ann.named_speakers:
                ann.named_speakers.append(who)
        out.append(ann)
    return out


# How many verses after the formula the quotation may run.
#
# Not a tuned number: the formula routinely ends with "saying," and the quoted
# words begin at the next verse. Matthew 4:14 is the whole of "to fulfill what was
# spoken through the prophet Isaiah:" -- there is no
# quotation in it at all, and looking only at the announcing verse finds nothing
# because there is nothing there to find. Acts 2:16 is the same, with Joel
# running on through verse 21.
QUOTE_WINDOW = 3


def placements(ann: Announcement, min_score: float = 4.0):
    """Where the shared wording puts the quotation this verse announces.

    Searches the announcing verse and the verses immediately after it, because
    the formula and the quoted words are usually not in the same verse.
    Verse division is later than the text and lands wherever it lands; it is
    not a boundary the quotation respects.
    """
    from .phrases import sources_for_verse

    corpus = get_corpus()
    out = []
    seen: set[str] = set()
    book, chapter, verse = ann.book, ann.chapter, ann.number
    last = corpus.chapter_length(book, chapter) or verse
    blocked = _formula_words(ann.text)
    for offset in range(QUOTE_WINDOW):
        n = verse + offset
        if n > last:
            break
        for src in sources_for_verse(f"{book} {chapter}:{n}", min_score=min_score):
            key = str(src.target)
            if key in seen:
                continue
            # On the announcing verse only, the quoted words come *after* the
            # formula -- "...spoken through the prophet Isaiah: He took up our
            # infirmities" (Matt 8:17). A match beginning before the formula ends is a
            # match on the announcement, not on anything quoted.
            #
            # Acts 2:16 is the whole verse: "this is what was spoken by the
            # prophet Joel" in the BSB, and in the older rendering it opens
            # "this is that which". It reaches Exodus 16:23 through "this is
            # that which" -- two verses introducing quotations in the same
            # words, the phrase layer confusing formula with content in exactly
            # the way this module exists to prevent.
            if offset == 0 and blocked is not None and all(
                span[0] < blocked for span in src.spans
            ):
                continue
            seen.add(key)
            out.append((offset, src))
    return out


def _formula_words(text: str) -> int | None:
    """Word index where the last citation formula ends.

    None when the formula runs to the end of the verse, because then there is
    no quoted text here to distinguish and every match has to be kept -- the
    alternative is discarding the verse's placements entirely on the strength
    of a rule that had nothing to work with.
    """
    from .phrases import tokenize

    end = 0
    for f in FORMULAS:
        for m in f.pattern.finditer(text):
            end = max(end, len(tokenize(text[: m.end()])))
    if not end or end >= len(tokenize(text)):
        return None
    return end


@dataclass
class Agreement:
    """How the named source and the matched wording compare.

    One shape for every state. The first version returned a differently shaped
    tuple per state -- a bare list here, a pair there -- and reading the wrong
    element raised rather than answering, which is at least loud, but only
    because the types happened to differ.
    """

    state: str  # confirmed | contested | elsewhere | absent | unnamed
    placed: object = None  # the named book's best placement, where there is one
    rival: object = None  # what outranks or replaces it
    siblings: list = field(default_factory=list)  # same-testament co-quotations

    def __iter__(self):
        """Kept so `state, _ = agreement(a)` still reads naturally."""
        return iter((self.state, self))


def agreement(ann: Announcement, min_score: float = 4.0) -> Agreement:
    """How the named source and the matched wording compare.

    Returns one of `confirmed`, `outranked`, `absent`, or `unnamed`, with the
    placement it refers to.

    **Deliberately not a boolean.** A first version returned True when the named
    book appeared anywhere in the list, and reported Matthew 27:9 as confirmed:
    it names Jeremiah, and some verse of Jeremiah does turn up far down the
    ranking. But the strongest real placement is Zechariah 11:13, and Matthew
    attributing to Jeremiah a passage that reads like Zechariah is a known and
    much-discussed difficulty in the text.

    A checkmark there would be the tool taking a side in a dispute it does not
    understand, and taking the side that makes the tool look better. Naming the
    state instead lets the reader see the disagreement, which is the more
    interesting fact and the one the graph exists to surface.
    """
    ranked = [src for _off, src in placements(ann, min_score)]

    if not ann.named_books:
        # **"Unnamed" was throwing away the more useful half.** A verse can
        # announce a quotation without saying whose, and the wording often
        # places it anyway: Romans 8:36 says only "as it is written" and lands
        # on Psalm 44:22 at seventeen points; the antitheses of Matthew 5 say
        # "ye have heard that it was said" and land on the commandments they
        # are answering -- 5:21 on Exodus 20:13, 5:27 on Exodus 20:14, 5:43 on
        # Leviticus 19:18.
        #
        # One instrument says *this is a quotation* and declines to name the
        # source; the other says *of this*. Reporting only the first and
        # discarding the second wasted the agreement between them, which is
        # the whole reason the two are computed separately.
        here = BOOK_TESTAMENT.get(ann.book)
        across = [s for s in ranked if BOOK_TESTAMENT.get(s.target.book) != here]
        if across:
            return Agreement("unnamed", rival=across[0],
                             siblings=[s for s in ranked if s not in across])
        return Agreement("unnamed", siblings=ranked)

    # Only verses in the other testament are candidates to be the source. A New
    # Testament verse announcing a quotation is not quoting another gospel.
    #
    # Without this the states are almost all "outranked", and every one of them
    # is spurious: Luke 3:4 is outranked by Matthew 3:3, Romans 10:16 by John
    # 12:38, John 12:39 by Matthew 13:15. Those are **sibling quotations** --
    # two writers drawing on the same passage -- and they score high precisely
    # because both reproduce it. Reading them as rivals to the named source
    # inverts what they actually show, which is corroboration.
    here = BOOK_TESTAMENT.get(ann.book)
    sources = [s for s in ranked if BOOK_TESTAMENT.get(s.target.book) != here]
    siblings = [s for s in ranked if s.target.book != ann.book and s not in sources]

    named = [s for s in sources if s.target.book in ann.named_books]
    if not named:
        # Nothing from the named book -- but if something else placed, saying
        # only "absent" would throw away the interesting half. Matthew 27:9
        # names Jeremiah and the wording lands squarely on Zechariah 11:13,
        # which is a real and much-discussed difficulty in the text. "We found
        # nothing" and "we found something, in a different book" are not the
        # same report and must not collapse into one.
        if sources:
            return Agreement("elsewhere", rival=sources[0], siblings=siblings)
        return Agreement("absent", siblings=siblings)
    if sources[0] is named[0]:
        return Agreement("confirmed", placed=named[0], siblings=siblings)
    # A different book of the same testament outscores the one the text names.
    return Agreement("contested", placed=named[0], rival=sources[0],
                     siblings=siblings)


def unplaced(nt_only: bool = True, min_score: float = 4.0) -> list[Announcement]:
    """Announced quotations the phrase layer cannot place.

    The worklist. Each one is a verse that says it is quoting something, where
    no shared wording is strong enough to say what -- which is exactly the class
    the translation of two languages into one destroys, and exactly what a
    reader is most likely to notice missing.
    """
    from .phrases import sources_for_verse

    return [
        a
        for a in announcements(nt_only=nt_only)
        if not sources_for_verse(a.verse, min_score=min_score)
    ]


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Verses that announce a quotation.")
    ap.add_argument("--nt", action="store_true", help="New Testament only")
    ap.add_argument("--unplaced", action="store_true",
                    help="only those the phrase layer cannot place")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args(argv)

    rows = unplaced(nt_only=True) if args.unplaced else announcements(nt_only=args.nt)

    named = sum(1 for a in rows if a.names_a_source)
    print(f"{len(rows)} announcements, {named} naming a source\n")
    for a in rows[: args.limit]:
        print(f"  {a.pretty:22} {a.why()}")
        print(f"    {a.text[:100]}")
    if len(rows) > args.limit:
        print(f"\n  ... {len(rows) - args.limit} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
