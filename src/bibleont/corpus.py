"""In-memory access to the Bible text, addressable by reference."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .books import BOOK_IDS, BOOK_ORDER, BOOK_TESTAMENT, BOOK_TITLE
from .paths import BSB_JSONL, VERSES_JSONL
from .refs import Ref, VerseId, parse_ref


@dataclass
class Verse:
    id: VerseId
    text: str


class Corpus:
    """The whole Bible held in memory; ~31k verses, a few MB."""

    def __init__(self, verses: dict[VerseId, str], translation: str = "KJV"):
        self._verses = verses
        self.translation = translation
        self._chapters: dict[tuple[str, int], int] = {}
        for vid in verses:
            key = (vid.book, vid.chapter)
            if vid.verse > self._chapters.get(key, 0):
                self._chapters[key] = vid.verse
        self._book_chapters: dict[str, int] = {}
        for book, chapter in self._chapters:
            if chapter > self._book_chapters.get(book, 0):
                self._book_chapters[book] = chapter

    # -- loading ---------------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> "Corpus":
        # THE PUBLIC REPOSITORY HAS NO KJV (2026-10-21, plan 8.3b): its verse
        # file is never published, so where it is absent the Berean is read,
        # which has the same 31,102 verse ids and the same record shape.
        if path is None and not VERSES_JSONL.exists() and BSB_JSONL.exists():
            path = BSB_JSONL
        path = path or VERSES_JSONL
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Run: python -m bibleont.build_corpus"
            )
        verses: dict[VerseId, str] = {}
        translation = "KJV"
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                if "translation" in rec:
                    translation = rec["translation"]
                    continue
                verses[VerseId(rec["b"], rec["c"], rec["v"])] = rec["t"]
        return cls(verses, translation)

    # -- lookup ----------------------------------------------------------
    def __len__(self) -> int:
        return len(self._verses)

    def __contains__(self, vid: VerseId) -> bool:
        return vid in self._verses

    def text(self, vid: VerseId) -> str | None:
        return self._verses.get(vid)

    def chapter_length(self, book: str, chapter: int) -> int:
        return self._chapters.get((book, chapter), 0)

    def book_chapters(self, book: str) -> int:
        return self._book_chapters.get(book, 0)

    def books(self) -> list[dict]:
        return [
            {
                "id": b,
                "title": BOOK_TITLE[b],
                "testament": BOOK_TESTAMENT[b],
                "order": BOOK_ORDER[b],
                "chapters": self.book_chapters(b),
            }
            for b in BOOK_IDS
        ]

    def expand(self, ref: Ref) -> list[VerseId]:
        """All verse ids covered by a reference, in order. Missing ones are skipped."""
        out: list[VerseId] = []
        chapter = ref.start_chapter
        verse = ref.start_verse
        guard = 0
        while (chapter, verse) <= (ref.end_chapter, ref.end_verse):
            guard += 1
            if guard > 10_000:  # pathological range; bail out
                break
            length = self.chapter_length(ref.book, chapter)
            if length == 0:
                # Past the last chapter of the book. Reachable since chapter
                # and book references arrived (2026-08-30): both run to a
                # sentinel end, because where a book stops is a fact about the
                # corpus and `refs` deliberately does not read the corpus.
                # Without this the walk stepped through empty chapters until
                # the 10,000 guard caught it -- correct output, absurdly.
                break
            vid = VerseId(ref.book, chapter, verse)
            if vid in self._verses:
                out.append(vid)
            if verse >= length:
                if chapter >= ref.end_chapter:
                    break
                chapter += 1
                verse = 1
            else:
                verse += 1
        return out

    def verses_for(self, ref_text: str) -> list[Verse]:
        """Resolve a reference string to its verses with text."""
        ref = parse_ref(ref_text)
        return [Verse(vid, self._verses[vid]) for vid in self.expand(ref)]

    def ref_exists(self, ref: Ref) -> bool:
        return bool(self.expand(ref))

    def iter_verses(self):
        for vid in sorted(self._verses, key=lambda v: v.sort_key):
            yield Verse(vid, self._verses[vid])

    def chapter(self, book: str, chapter: int) -> list[Verse]:
        n = self.chapter_length(book, chapter)
        return [
            Verse(VerseId(book, chapter, v), self._verses[VerseId(book, chapter, v)])
            for v in range(1, n + 1)
            if VerseId(book, chapter, v) in self._verses
        ]

    def search(self, needle: str, limit: int = 200) -> list[Verse]:
        low = needle.lower()
        out = []
        for verse in self.iter_verses():
            if low in verse.text.lower():
                out.append(verse)
                if len(out) >= limit:
                    break
        return out


@lru_cache(maxsize=1)
def get_corpus() -> Corpus:
    """Process-wide singleton, loaded on first use."""
    return Corpus.load()
