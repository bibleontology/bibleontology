"""A name appearing once, where no name was expected.

Psalm 103 praises rather than narrates, and one person is named in the body of
it, once: "He made known his ways unto Moses" (Ps 103:7). Three verses later
the psalm is quoting what was proclaimed *to Moses on the mount*. The name is
not decoration; it sets up what follows.

That was put forward as a reader's intuition and it turns out to be arithmetic.
Two conditions, both computable, neither an interpretation:

1. **The name is anomalous.** A chapter of some length, in a book that argues
   or praises rather than narrates, naming exactly one person exactly once.
2. **What follows reaches back.** A verse within a few of the drop shares rare
   wording with a passage where that person is named.

Condition 1 alone is a candidate for a reader. **Both together is a strong
signal**, and the pair confirm each other without either becoming a claim about
meaning: the graph says *this name is unusual here* and *these verses quote
that person's story*, and the reader draws the line.

60 drops found, 23 confirmed by what follows. The one it was built for is
there:

    Psalms 103:7   Moses
      He made known His ways to Moses, His deeds to the people of Israel.
      Psalms 103:8 reaches Exod 34:6 on 'merciful and gracious'

Others it turns up unprompted are the same shape and were not looked for.
Isaiah 6:1 dates a vision by a single name -- "in the year that king Uzziah
died". Hebrews 5:4 says no one takes the priesthood to himself but must be "called
by God, just as Aaron was", and the verses after it reach the Melchisedec
passages, which is the argument of the whole letter. Ezekiel 33:24 quotes
people saying "Abraham was one, and he inherited the land".

## What had to be filtered, and why it was not a special case

**Superscriptions.** "A Psalm of David" is an attribution, not a name-drop, and
counting it buried the signal completely: 87 candidates became 32 once the
attribution was excluded, and Psalm 103 only appeared at all because of it --
the psalm names David in its title and Moses in its body, so it looked like a
two-name chapter and was skipped.

**Eponyms, and this one is not solved.** Jacob dominates what is left -- "the
God of Jacob", "the seed of Jacob" -- because the Psalms and the prophets use
the name for the nation, not the man. The exclusion `prominence.py` uses does
not reach it: that rule drops a person whose name is *also* carried by a place
or a people, and the people here is called Israel. So the rows are left in and
labelled here rather than suppressed by a hand-written exception, on the same
principle as the other leaks in this codebase. A reader skimming the output
should expect roughly half of it to be Jacob.

## What it does not do

It does not say *why* the name was dropped. Psalm 103:7 sets up 103:8, and that
reading is the reader's; what is computable is that the name is unusual and
that the next verse quotes the passage where that name belongs.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .corpus import get_corpus
from .graph import Store

# Books that argue or praise rather than narrate. A single name in a chapter of
# Kings means nothing -- narrative names people constantly.
REFLECTIVE = {"Ps", "Prov", "Eccl", "Song", "Job", "Lam", "Isa", "Jer", "Ezek",
              "Hos", "Joel", "Amos", "Obad", "Mic", "Nah", "Hab", "Zeph",
              "Hag", "Zech", "Mal", "Rom", "1Cor", "2Cor", "Gal", "Eph",
              "Phil", "Col", "Heb", "Jas", "1Pet", "2Pet", "1John", "Jude"}

# The attribution at the head of a psalm names its author, not a figure the
# poem invokes. Leaving it in was the single biggest source of noise.
SUPERSCRIPTION = re.compile(
    r"^(?:To the chief Musician[^.]*\.|"
    r"A (?:Psalm|Song|Prayer|Michtam|Maschil)[^.]*\.|"
    r"[A-Z][^.]{0,60}?of (?:David|Asaph|Solomon|Moses|Heman|Ethan|"
    r"the sons of Korah)[^.]*\.)\s*")

WORD = re.compile(r"[A-Z][a-z']+")


@dataclass
class Drop:
    """One name standing alone in a chapter that does not deal in names."""

    chapter: str
    verse: str
    pretty: str
    name: str
    text: str
    # Verses near the drop that share rare wording with a passage naming the
    # same person. Empty means condition 1 fired and condition 2 did not.
    echoes: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def confirmed(self) -> bool:
        return bool(self.echoes)


def survey(store: Store | None = None, min_verses: int = 8,
           window: int = 3, confirm: bool = True,
           max_share: float = 0.25) -> list[Drop]:
    store = store or Store.load()
    corpus = get_corpus()
    verses = list(corpus.iter_verses())

    people = {p.name for p in store.people.values()
              if p.type == "person" and len(p.name) > 3}
    # Eponyms: the man and the people share a name and the corpus means the
    # people. Same exclusion prominence.py makes, for the same reason.
    elsewhere = {p.name for p in store.people.values() if p.type != "person"}
    people -= elsewhere

    per_ch: dict[str, Counter[str]] = defaultdict(Counter)
    book_chapters: dict[str, set[str]] = defaultdict(set)
    name_chapters: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_chapter_names: dict[str, set[str]] = defaultdict(set)
    where: dict[tuple[str, str], int] = {}
    length: Counter[str] = Counter()
    for i, v in enumerate(verses):
        ch = f"{v.id.book} {v.id.chapter}"
        length[ch] += 1
        book_chapters[v.id.book].add(ch)
        body = SUPERSCRIPTION.sub("", v.text) if v.id.verse == 1 else v.text
        for w in WORD.findall(v.text):
            by_chapter_names[ch].add(w)
        for w in WORD.findall(body):
            if w in people:
                per_ch[ch][w] += 1
                name_chapters[(v.id.book, w)].add(ch)
                where.setdefault((ch, w), i)

    out: list[Drop] = []
    for ch, counts in per_ch.items():
        if ch.split()[0] not in REFLECTIVE:
            continue
        if length[ch] < min_verses or len(counts) != 1:
            continue
        name, n = next(iter(counts.items()))
        if n != 1:
            continue
        # The name must be unusual in the book as well as in the chapter, and
        # the measure has to be a *rate*. A flat cap of three per book filled
        # the list with "Jesus" in the epistles -- where naming him once in a
        # chapter is the ordinary state of the letter, not a marked event --
        # and simultaneously threw out Psalm 103, because Moses appears seven
        # times across a hundred and fifty psalms. Seven of a hundred and fifty
        # is rare; three of four is not.
        book = ch.split()[0]
        share = len(name_chapters[(book, name)]) / len(book_chapters[book])
        if share > max_share:
            continue
        i = where[(ch, name)]
        out.append(Drop(ch, str(verses[i].id), verses[i].id.pretty(), name,
                        verses[i].text))

    if confirm:
        from .phrases import sources_for_verse
        by_ref = {str(v.id): v.text for v in verses}
        for d in out:
            i = where[(d.chapter, d.name)]
            for j in range(i + 1, min(i + 1 + window, len(verses))):
                near = verses[j]
                if f"{near.id.book} {near.id.chapter}" != d.chapter:
                    break
                for s in sources_for_verse(str(near.id))[:4]:
                    target = str(s.target)
                    if target.split(":")[0] == d.chapter:
                        continue  # a link inside the same chapter proves nothing
                    # The passage, not the verse. Psalm 103:8 reaches Exodus
                    # 34:6, which does not contain the word "Moses" -- it says
                    # "before him", and Moses is named at 34:4, 34:5 and 34:8.
                    # Testing the verse alone lost the case this was built for.
                    tgt_ch = target.rsplit(":", 1)[0]
                    if d.name in by_chapter_names.get(tgt_ch, ()):
                        d.echoes.append(
                            (near.id.pretty(), target,
                             "; ".join(p.text for p in s.phrases)))
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Names dropped once into chapters that do not deal in "
                    "names.")
    ap.add_argument("--all", action="store_true",
                    help="candidates too, not only confirmed ones")
    args = ap.parse_args(argv)

    rows = survey()
    strong = [d for d in rows if d.confirmed]
    print(f"{len(rows)} name drops; {len(strong)} confirmed by what follows\n")
    for d in rows:
        if not d.confirmed and not args.all:
            continue
        mark = "**" if d.confirmed else "  "
        print(f"{mark} {d.pretty:14} {d.name}")
        print(f"      {d.text[:120]}")
        for near, target, phrases in d.echoes:
            print(f"      {near} reaches {target} on {phrases[:56]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
