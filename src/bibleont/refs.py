"""Parsing and formatting of scripture references.

Supported forms (all case-insensitive, whitespace tolerant):

    Gen 5:3
    Genesis 5:3
    Gen 5:3-5            (verse range inside one chapter)
    Gen 5:3-6:2          (cross-chapter range)
    1Sam 16:13
    1 Samuel 16:13
    Gen 5:3,5; 1Sam 16:13    (multiple, via parse_refs)
    Job 1                (a whole chapter)
    Job 38-41            (a run of chapters)
    Job                  (a whole book -- only with allow_book=True)

## Why a verse was the only address for so long

Until 2026-08-30 this module accepted a verse and a verse range and nothing
else. `Job 1` did not parse. Neither did `Job 38-41` or `Job`.

That looked like a parser limitation and was in fact a modelling one, because
**a citation is how anything in this graph says where it lives**. If the
smallest thing you can name is a verse, then a verse is the largest container
anything can hang from, and every structure bigger than one verse -- a speech,
an argument, a collection, a scroll -- has nowhere to attach. Measured on the
day it was fixed: 5,925 relations wired a verse straight to an idea with no
claim between them, no relation anywhere cited a scroll, and God's speech from
the whirlwind (Job 38-41) could not be referred to at all.

## Bare book names are opt-in, deliberately

Seventeen books are ordinary English words -- Acts, James, Job, John, Jude,
Judges, Lamentations, Luke, Mark, Matthew, Numbers, Philemon, Proverbs,
Psalms, Revelation, Romans, Titus. If `parse_ref("Mark")` succeeded by
default, a model that emitted the *person* Mark as a citation would silently
be given the whole gospel, and prose containing "Numbers" would parse as
scripture.

A book name followed by a digit is unambiguous and always parses. A bare book
name is only a reference where the caller says it is one, which is why
`allow_book` exists and defaults to False.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .books import BOOK_ORDER, BOOK_TITLE, resolve_book


class RefError(ValueError):
    """Raised when a reference string cannot be parsed."""


@dataclass(frozen=True, order=True)
class VerseId:
    """A single verse address."""

    book: str
    chapter: int
    verse: int

    def __str__(self) -> str:  # "Gen 5:3"
        return f"{self.book} {self.chapter}:{self.verse}"

    @property
    def sort_key(self) -> tuple[int, int, int]:
        return (BOOK_ORDER.get(self.book, 999), self.chapter, self.verse)

    def pretty(self) -> str:  # "Genesis 5:3"
        return f"{BOOK_TITLE.get(self.book, self.book)} {self.chapter}:{self.verse}"


# Granularity: what the writer actually named, which is not recoverable from
# the range alone. "Job 1" and "Job 1:1-22" cover the same verses and are not
# the same citation -- one names a chapter, the other names every verse in it,
# and a reader shown "Job 1:1-22" where the source said "Job 1" has been told
# something the source did not say.
VERSE, CHAPTER, BOOK = "verse", "chapter", "book"

# Stands in for "to the end", because the end is a fact about the corpus and
# this module does not read the corpus -- keeping it free of that dependency
# is why it can be imported by anything. `Corpus.expand` walks by chapter
# length and stops at the real end, so the sentinel never survives contact
# with a verse list. It is read in exactly one place.
LAST = 10 ** 6


@dataclass(frozen=True)
class Ref:
    """A contiguous reference: a verse, a range, a chapter, or a whole book."""

    book: str
    start_chapter: int
    start_verse: int
    end_chapter: int
    end_verse: int
    # Defaulted so that every existing construction and every existing test
    # keeps its current meaning.
    granularity: str = VERSE

    def __str__(self) -> str:
        if self.granularity == BOOK:
            return self.book
        if self.granularity == CHAPTER:
            if self.start_chapter == self.end_chapter:
                return f"{self.book} {self.start_chapter}"
            return f"{self.book} {self.start_chapter}-{self.end_chapter}"
        if (self.start_chapter, self.start_verse) == (self.end_chapter, self.end_verse):
            return f"{self.book} {self.start_chapter}:{self.start_verse}"
        if self.start_chapter == self.end_chapter:
            return f"{self.book} {self.start_chapter}:{self.start_verse}-{self.end_verse}"
        return (
            f"{self.book} {self.start_chapter}:{self.start_verse}"
            f"-{self.end_chapter}:{self.end_verse}"
        )

    def pretty(self) -> str:
        """The same, with the book spelled out: 'Job 38-41'."""
        return str(self).replace(self.book, BOOK_TITLE.get(self.book, self.book), 1)

    @property
    def is_whole(self) -> bool:
        """Names a container rather than a verse or a span of them.

        The distinction the corroboration check needs: "does this verse name
        both ends" is a fair question of `Gen 14:9` and an unfair one of
        `Job 38-41`, where the subject may be four chapters away from the
        words that establish it.
        """
        return self.granularity in (CHAPTER, BOOK)

    @property
    def sort_key(self) -> tuple[int, int, int]:
        return (BOOK_ORDER.get(self.book, 999), self.start_chapter, self.start_verse)


# Book name: letters, plus an optional leading numeral in any of the common
# styles (1, I, First). Chapter:verse follows.
_REF_RE = re.compile(
    r"""^\s*
    (?P<book>(?:[1-3]|I{1,3}|First|Second|Third)?\s*[A-Za-z][A-Za-z.\s]*?)
    \s+
    (?P<c1>\d+)\s*:\s*(?P<v1>\d+)
    (?:\s*[-–]\s*(?:(?P<c2>\d+)\s*:\s*)?(?P<v2>\d+))?
    \s*$""",
    re.VERBOSE,
)

_ORDINAL_WORDS = {"first": "1", "second": "2", "third": "3"}


def _normalize_book_token(token: str) -> str:
    token = token.strip().rstrip(".")
    low = token.lower()
    for word, digit in _ORDINAL_WORDS.items():
        if low.startswith(word + " "):
            return digit + token[len(word) :].strip()
    return token


# A chapter or a run of them, with no colon anywhere. Kept as its own pattern
# rather than loosening the one above, because a single relaxed regex reads
# "Gen 38-41" as chapter 38 verse 41 -- the numbers fit both shapes and only
# the absence of a colon tells them apart. Two strict patterns say which is
# meant; one loose pattern guesses.
_CHAPTER_RE = re.compile(
    r"""^\s*
    (?P<book>(?:[1-3]|I{1,3}|First|Second|Third)?\s*[A-Za-z][A-Za-z.\s]*?)
    \s+
    (?P<c1>\d+)
    (?:\s*[-–]\s*(?P<c2>\d+))?
    \s*$""",
    re.VERBOSE,
)

_BOOK_RE = re.compile(
    r"""^\s*
    (?P<book>(?:[1-3]|I{1,3}|First|Second|Third)?\s*[A-Za-z][A-Za-z.\s]*?)
    \s*$""",
    re.VERBOSE,
)


def parse_ref(text: str, allow_book: bool = False) -> Ref:
    """Parse a single reference. Raises RefError on failure.

    `allow_book` admits a bare book name. Off by default: seventeen books are
    ordinary English words, so accepting them everywhere would turn the person
    Mark into the gospel and the word "Numbers" into the fourth book of the
    Pentateuch. Callers that know they are reading a citation -- a scroll
    attribution, a hand-written expectation -- pass True.
    """
    m = _REF_RE.match(text)
    if m:
        book = resolve_book(_normalize_book_token(m.group("book")))
        if book is None:
            raise RefError(f"unknown book in reference: {text!r}")
        c1, v1 = int(m.group("c1")), int(m.group("v1"))
        if m.group("v2") is None:
            c2, v2 = c1, v1
        else:
            c2 = int(m.group("c2")) if m.group("c2") else c1
            v2 = int(m.group("v2"))
        if (c2, v2) < (c1, v1):
            raise RefError(f"reference range runs backwards: {text!r}")
        return Ref(book, c1, v1, c2, v2)

    m = _CHAPTER_RE.match(text)
    if m:
        book = resolve_book(_normalize_book_token(m.group("book")))
        if book is None:
            raise RefError(f"unknown book in reference: {text!r}")
        c1 = int(m.group("c1"))
        c2 = int(m.group("c2")) if m.group("c2") else c1
        if c2 < c1:
            raise RefError(f"reference range runs backwards: {text!r}")
        return Ref(book, c1, 1, c2, LAST, CHAPTER)

    if allow_book:
        m = _BOOK_RE.match(text)
        if m:
            book = resolve_book(_normalize_book_token(m.group("book")))
            if book is not None:
                return Ref(book, 1, 1, LAST, LAST, BOOK)

    raise RefError(f"unparseable reference: {text!r}")


def parse_refs(text: str) -> list[Ref]:
    """Parse a semicolon/comma separated list of references.

    Bare numbers after a comma continue the previous book and chapter,
    so "Gen 5:3, 5" yields Gen 5:3 and Gen 5:5.
    """
    out: list[Ref] = []
    last: Ref | None = None
    for chunk in re.split(r"[;]", text):
        for i, piece in enumerate(re.split(r",", chunk)):
            piece = piece.strip()
            if not piece:
                continue
            if i > 0 and last is not None and re.fullmatch(r"\d+(?:\s*[-–]\s*\d+)?", piece):
                nums = [int(n) for n in re.split(r"[-–]", piece)]
                v1 = nums[0]
                v2 = nums[-1]
                ref = Ref(last.book, last.end_chapter, v1, last.end_chapter, v2)
            else:
                ref = parse_ref(piece)
            out.append(ref)
            last = ref
    return out
