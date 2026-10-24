"""Tier-1 phrase links: verbatim shared wording between verses.

This is the *certain* detector. It reports only wording that actually recurs,
so a link it produces can be checked by reading the two verses side by side.
Cluster matching for reworked sources -- Exod 33-34 behind John 1:14-18, where
nothing is quoted verbatim -- is a separate, weaker tier and is not here.

Two design decisions carry most of the weight, both learned from John 1:

**No stopword filtering.** The obvious way to keep an n-gram index small is to
drop grams made mostly of common words. That deletes the signal: allusion
formulas are built from common words. "In the beginning was the Word" is three
stopwords and one content word, and filtering rejects it.

**Idiomatic senses are suppressed by continuation, not by frequency.** Without
a filter, "in the beginning" matches Genesis 1:1 and also thirteen verses
reading "in the beginning *of* the reign of...", which is a dating formula with
no relation to Genesis. Frequency cannot tell these apart -- they are the same
phrase. What separates them is what the phrase governs. So when one
continuation dominates a phrase's occurrences, that group is treated as a fixed
idiom and the remaining occurrences are linked to each other. On "in the
beginning" this leaves exactly Gen 1:1, John 1:1, John 1:2 and Heb 1:10.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

from .corpus import BOOK_ORDER, VerseId, get_corpus

TOKEN = re.compile(r"[a-z]+")

MIN_N = 3
MAX_N = 12

# Retained in the index. Deliberately loose: idiom suppression runs *after*
# indexing, so a phrase must survive long enough to be split. "In the
# beginning" occurs 17 times and only 4 of those are the absolute sense -- at a
# cap of 15 it is thrown away as common before anything can look at it, which
# is exactly the Genesis 1:1 failure.
INDEX_CAP = 80

# Shown as a link. Applied to what remains after suppression.
LINK_CAP = 8
# Below this length a phrase must be rare to be worth showing; at or above it,
# the shared wording is substantial enough to stand on its own.
SUBSTANTIAL_N = 5
RARE = 5
# Aggregation sees more than display does; convergence is its own evidence.
AGG_RARE = 8

# A short phrase must contain at least one word rarer than this to be shown.
# Without it every verse drags in "with god and the" -- a true recurrence built
# entirely from connective tissue, which tells a reader nothing. Long phrases
# are exempt: at five words the shared wording carries itself.
CONTENT_RANK = 400

# Fraction of occurrences that one continuation must cover before the phrase is
# treated as having a dominant idiomatic sense.
IDIOM_SHARE = 0.6

# Closed-class words: grammar rather than subject matter. Used only to ask
# whether an aggregated match consists of nothing else -- never to remove a word
# from the index, which is the mistake that once deleted "in the beginning".
#
# Closed by design. If a result wants a word added here, that is a reason to
# doubt the result, not to extend the list.
FUNCTION_WORDS = frozenset(
    """
    a an the this that these those
    i me my mine we us our ours you your yours thou thee thy thine ye
    he him his she her hers it its they them their theirs
    who whom whose which what
    am is are was were be been being
    have has had do does did
    shall will should would may might must can could let
    of in on at by for with from to unto into upon over under
    through between among against about after before behind beneath
    beside besides beyond during within without toward towards up down out off
    and or but nor so yet if then than as because while when where why how
    not no nor never neither either both all any some such same own
    there here now again very too also even only just still
    """.split()
)


@dataclass(frozen=True)
class Occurrence:
    verse: VerseId
    start: int  # token offset within the verse
    before: str | None
    after: str | None


@dataclass
class PhraseLink:
    """One phrase and every verse using it."""

    text: str
    occurrences: list[Occurrence]
    suppressed: list[Occurrence] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.text.split())

    @property
    def verses(self) -> list[VerseId]:
        return [o.verse for o in self.occurrences]

    @property
    def books(self) -> list[str]:
        seen: list[str] = []
        for o in self.occurrences:
            if o.verse.book not in seen:
                seen.append(o.verse.book)
        return seen

    @property
    def cross_book(self) -> bool:
        return len(self.books) > 1

    @property
    def cross_testament(self) -> bool:
        from .corpus import BOOK_TESTAMENT

        return len({BOOK_TESTAMENT[b] for b in self.books}) > 1

    def worth_showing(self, aggregating: bool = False) -> bool:
        """Substantial wording, or short wording that is genuinely rare.

        Without this, every verse drags in "there was a man" and "and the
        light" -- true recurrences that tell a reader nothing.

        **The bar is lower when aggregating by source.** Shown alone, a short
        common-word phrase is noise. Converging with two others on the *same*
        verse, it is evidence -- and the temple saying proved it. John 2:19
        reaches Mark 14:58 through "destroy this temple", and Matt 26:61,
        Matt 27:40 and Mark 15:29 through "in three days", and each of those
        was rejected individually: one for having only three words, the other
        for appearing in six verses rather than five. Three separately
        defensible thresholds, together deleting a saying reported five times
        across four books.

        So display keeps the strict test and aggregation relaxes it, letting
        the aggregate score decide instead.
        """
        count = len(self.occurrences)
        if count > LINK_CAP:
            return False
        if self.n >= SUBSTANTIAL_N:
            return True
        if count > (AGG_RARE if aggregating else RARE):
            return False
        if aggregating:
            return True
        rank = _word_rank()
        return any(rank.get(w, 10**6) >= CONTENT_RANK for w in self.text.split())

    def score(self) -> float:
        """Rank by how much wording is shared and how rarely it is shared.

        Length dominates: a seven-word match is a stronger claim than a
        three-word one. Rarity breaks ties. Crossing a book, and especially a
        testament, is worth something because those are the links a reader is
        least likely to already carry.
        """
        s = self.n * 2.0
        s += max(0, 10 - len(self.occurrences))
        if self.cross_book:
            s += 3.0
        if self.cross_testament:
            s += 2.0
        if self.suppressed:
            s += 3.0  # a marked use standing apart from a fixed idiom
        return s


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def token_offsets(text: str) -> list[tuple[int, int]]:
    """Character span of each token, in the same order `tokenize` returns them.

    Matching works in word indices; showing a reader where a match falls needs
    character positions in the original text. Both come from the one regex, so
    index *i* here is always the token *i* there -- deriving the offsets any
    other way would drift the moment the tokenizer changed.
    """
    return [(m.start(), m.end()) for m in TOKEN.finditer(text.lower())]


@lru_cache(maxsize=1)
def _word_rank() -> dict[str, int]:
    """Corpus words ordered by frequency, commonest first."""
    from collections import Counter

    freq = Counter(w for _, ws in _tokenized() for w in ws)
    return {w: i for i, (w, _) in enumerate(freq.most_common())}


@lru_cache(maxsize=1)
def _tokenized() -> list[tuple[VerseId, list[str]]]:
    return [(v.id, tokenize(v.text)) for v in get_corpus().iter_verses()]


@lru_cache(maxsize=1)
def _index() -> dict[str, list[Occurrence]]:
    """Every n-gram occurring in 2..INDEX_CAP verses.

    Indexing n=3..12 at every position would be ~8M entries. Almost all of them
    occur once and cannot be a link, so the index is grown a level at a time and
    an (n+1)-gram is only considered where its n-gram prefix already repeats.
    That is the classic apriori prune and it keeps the table small enough to
    build in seconds.
    """
    verses = _tokenized()

    # Level MIN_N: count every gram, keep the ones that recur.
    counts: dict[str, int] = defaultdict(int)
    for _, words in verses:
        for i in range(len(words) - MIN_N + 1):
            counts[" ".join(words[i : i + MIN_N])] += 1
    live = {g for g, c in counts.items() if c > 1}
    seen = set(live)
    keep: dict[str, int] = {g: counts[g] for g in live if counts[g] <= INDEX_CAP}

    # Levels MIN_N+1..MAX_N: extend only where the shorter gram already repeats.
    for n in range(MIN_N + 1, MAX_N + 1):
        if not live:
            break
        counts = defaultdict(int)
        for _, words in verses:
            for i in range(len(words) - n + 1):
                if " ".join(words[i : i + n - 1]) not in live:
                    continue
                counts[" ".join(words[i : i + n])] += 1
        live = {g for g, c in counts.items() if c > 1}
        seen |= live
        keep.update({g: counts[g] for g in live if counts[g] <= INDEX_CAP})

    # Final pass: collect occurrences, with the neighbouring tokens that
    # _split_idiom needs. A gram that never repeats cannot have a repeating
    # extension, so hitting one ends the scan at that position.
    index: dict[str, list[Occurrence]] = defaultdict(list)
    for vid, words in verses:
        limit = len(words)
        for i in range(limit):
            for n in range(MIN_N, MAX_N + 1):
                if i + n > limit:
                    break
                key = " ".join(words[i : i + n])
                if key not in seen:
                    break
                if key not in keep:
                    continue
                index[key].append(
                    Occurrence(
                        verse=vid,
                        start=i,
                        before=words[i - 1] if i else None,
                        after=words[i + n] if i + n < limit else None,
                    )
                )
    return {k: v for k, v in index.items() if len({o.verse for o in v}) > 1}


def _split_idiom(occs: list[Occurrence]) -> tuple[list[Occurrence], list[Occurrence]]:
    """Separate a dominant fixed sense from the marked uses that stand apart.

    Returns (kept, suppressed). If no continuation dominates, everything is
    kept and nothing is suppressed.
    """
    if len(occs) < 4:
        return occs, []
    by_after: dict[str | None, list[Occurrence]] = defaultdict(list)
    for o in occs:
        by_after[o.after].append(o)
    biggest = max(by_after.values(), key=len)
    if len(biggest) / len(occs) < IDIOM_SHARE:
        return occs, []
    residue = [o for o in occs if o not in biggest]
    if len(residue) < 2:
        return occs, []
    return residue, biggest


def _maximal(links: list[PhraseLink]) -> list[PhraseLink]:
    """Drop phrases wholly contained in a longer phrase over the same verses.

    "in the beginning was" and "in the beginning was the word" are one link,
    and only the longer should be shown.
    """
    links.sort(key=lambda p: -p.n)
    kept: list[PhraseLink] = []
    for link in links:
        covered = set(link.verses)
        padded = f" {link.text} "
        if any(
            padded in f" {longer.text} " and covered <= set(longer.verses)
            for longer in kept
        ):
            continue
        kept.append(link)
    return kept


def _as_verse_id(vid: VerseId | str) -> VerseId | None:
    """Accept "Luke 3:4" as well as the parsed id.

    Occurrences hold VerseId, and a string compares unequal to every one of
    them, so passing one used to return an empty result rather than an error --
    a caller measuring how many announced quotations could be placed got zero
    for all 117 and had no way to tell that from a real answer. **A lookup that
    silently returns nothing for a wrong type is worse than one that raises**,
    because nothing is a plausible answer.
    """
    if isinstance(vid, str):
        from .refs import RefError

        try:
            verses = get_corpus().verses_for(vid)
        except RefError:
            return None
        return verses[0].id if verses else None
    return vid


def links_for_verse(vid: VerseId | str, aggregating: bool = False) -> list[PhraseLink]:
    """Every tier-1 phrase link touching one verse, strongest first."""
    corpus = get_corpus()
    vid = _as_verse_id(vid)
    if vid is None:
        return []
    text = corpus.text(vid)
    if text is None:
        return []
    words = tokenize(text)
    index = _index()
    found: list[PhraseLink] = []
    for i in range(len(words)):
        for n in range(MIN_N, MAX_N + 1):
            if i + n > len(words):
                break
            key = " ".join(words[i : i + n])
            occs = index.get(key)
            if not occs:
                continue
            kept, suppressed = _split_idiom(occs)
            if not any(o.verse == vid for o in kept):
                continue
            others = [o for o in kept if o.verse != vid]
            if not others:
                continue
            link = PhraseLink(text=key, occurrences=kept, suppressed=suppressed)
            if not link.worth_showing(aggregating):
                continue
            found.append(link)
    result = _maximal(found)
    result.sort(key=lambda p: -p.score())
    return result


@dataclass
class SourceLink:
    """One target verse and every phrase this verse shares with it.

    A quotation that survived translation intact shows up as one long run --
    Luke 3:5 and Isaiah 40:4 share eleven consecutive words. A quotation that
    came through the Septuagint does not: Luke 4:18 quotes Isaiah 61:1 and the
    KJV wording drifts, so the match shatters into "hath anointed me to
    preach", "he hath sent me to", "to the captives and", "the brokenhearted
    to". Ranked individually those are four unremarkable short phrases.

    Together they are decisive, and *that* is the signal: four distinct
    fragments landing on one verse is not four weak links, it is one strong
    one. Nothing in the per-phrase view can see it, because the evidence is in
    the coincidence rather than in any single match.
    """

    target: VerseId
    phrases: list[PhraseLink]
    spans: list[tuple[int, int]]  # merged, non-overlapping, in source-verse words

    @property
    def fragments(self) -> int:
        return len(self.spans)

    @property
    def words(self) -> int:
        return sum(end - start for start, end in self.spans)

    def score(self) -> float:
        # Multiple *disjoint* fragments are worth more than their lengths
        # suggest: two verses sharing four separate phrases are related in a
        # way two verses sharing one phrase of the same total length are not.
        #
        # Rarity counts too, and leaving it out lost the best link in the
        # corpus. "Merciful and gracious" occurs in exactly two verses --
        # Exodus 34:6, where it is proclaimed to Moses, and Psalm 103:8, which
        # is quoting it. Three words, one fragment, so it scored 3.0 against a
        # threshold of 4.0 and was dropped, while "and plenteous in" -- twice
        # as common and no longer -- scored the same. Word count alone cannot
        # tell a fingerprint from a turn of phrase.
        #
        # Bounded deliberately: the bonus tops out at +3 for a phrase found
        # nowhere else, so it can rescue a short rare match without letting
        # rarity outrank substantial shared wording.
        #
        # And it is earned by rare *words*, not by a rare sequence. Awarding it
        # on sequence rarity alone added 28% more links and nearly all of them
        # were noise -- "turn aside and", "and see this" -- unusual orderings
        # of ordinary words. One rare word is not enough either: "of the
        # fountain" survives any word-rank bar, because `fountain` is rare and
        # the other two words are furniture. What marks a fingerprint is two
        # rare words carrying the phrase, which is the same content-word test
        # `_has_substance` applies, run against the rank table. That costs 1%
        # more links, and they read like Isaiah 53:6 reaching Psalm 119:176 on
        # "have gone astray".
        rarest = min((len(p.occurrences) for p in self.phrases), default=99)
        bonus = 0.0
        if any(_rare_content(p.text) >= 2 for p in self.phrases):
            bonus = max(0.0, 4.0 - rarest)
        return (self.words * 1.0
                + (self.fragments - 1) * 3.0
                + bonus)


def sources_for_verse(vid: VerseId | str, min_score: float = 4.0) -> list[SourceLink]:
    """Verses this one draws on, aggregated across fragments, strongest first.

    Fragments are counted over *merged* spans of the source verse. The index
    yields every n-gram length, so one quotation surfaces as a fan of nested
    and sliding windows -- Luke 3:4 against Matthew 3:3 produced thirteen
    "fragments" and 136 words for what is a single sixteen-word run. Counting
    those as independent would rank a verbatim copy far above a real
    multi-part allusion, which is the opposite of the point.
    """
    vid = _as_verse_id(vid)
    if vid is None:
        return []
    by_target: dict[VerseId, list[tuple[PhraseLink, int, int]]] = defaultdict(list)
    for link in links_for_verse(vid, aggregating=True):
        here = [o for o in link.occurrences if o.verse == vid]
        there = [o for o in link.occurrences if o.verse != vid]
        for occ in there:
            for mine in here:
                by_target[occ.verse].append((link, mine.start, mine.start + link.n))

    out: list[SourceLink] = []
    for target, items in by_target.items():
        merged: list[tuple[int, int]] = []
        for _, start, end in sorted(items, key=lambda x: (x[1], x[2])):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        # Keep the longest phrase covering each merged span, for display.
        shown: list[PhraseLink] = []
        for span in merged:
            covering = [
                link
                for link, s, e in items
                if s >= span[0] and e <= span[1]
            ]
            if covering:
                shown.append(max(covering, key=lambda p: p.n))
        out.append(SourceLink(target=target, phrases=shown, spans=merged))

    out = [s for s in out if s.score() >= min_score and _has_substance(s)]
    out.sort(key=lambda s: -s.score())
    return out


def _rare_content(text: str) -> int:
    """How many words here are both uncommon and not connective tissue."""
    rank = _word_rank()
    return sum(1 for w in text.split()
               if w not in FUNCTION_WORDS and rank.get(w, 10**6) >= CONTENT_RANK)


def _has_substance(source: SourceLink) -> bool:
    """Does the shared wording contain anything but connective tissue?

    Aggregation drops the content-word test so that weak fragments can
    *contribute* -- the temple saying needs it, since "in three days" carries no
    rare word and is half the evidence. But dropping it outright let wording
    that is purely a way of speaking through as a source in its own right.

    Romans 8:1 is the case. Its second-ranked source was Hebrews 7:16, on "not
    after the" and "but after the": two fragments, so the convergence rule was
    satisfied, and both of them grammar. Four more sources came from "them which
    are in", one apiece, which is a construction rather than a phrase.

    So convergence is not sufficient after all, because **fragments of grammar
    converge on grammar**. The aggregate as a whole has to carry at least one
    word that is not purely structural. Individual fragments still need not,
    which is what the relaxation was for.

    The test is word *class*, not word frequency. Rarity was tried first and
    took "in three days" down with the grammar, because "three" and "days" are
    both common -- common and structural are different things, and only the
    second one means nothing on its own. So the bar is a closed list of
    function words: determiners, prepositions, pronouns, conjunctions,
    auxiliaries, negators. It is finite, it is not tuned, and it cannot grow to
    fit a result.

    This is not the stopword filter that once deleted "in the beginning".
    That removed common words from the index, destroying phrases made of them.
    Nothing is removed here: the phrase is indexed, matched and merged exactly
    as before, and the only question asked at the end is whether the whole
    aggregate is grammar. "In the beginning" keeps `beginning` and survives.
    """
    return any(
        word not in FUNCTION_WORDS
        for phrase in source.phrases
        for word in phrase.text.split()
    )


def links_for_passage(ref_text: str) -> list[tuple[VerseId, list[PhraseLink]]]:
    corpus = get_corpus()
    return [(v.id, links_for_verse(v.id)) for v in corpus.verses_for(ref_text)]


def _fmt(link: PhraseLink, source: VerseId) -> str:
    others = [o.verse for o in link.occurrences if o.verse != source]
    others.sort(key=lambda v: (BOOK_ORDER[v.book], v.chapter, v.verse))
    tag = ""
    if link.cross_testament:
        tag = "  [crosses testaments]"
    elif link.cross_book:
        tag = "  [crosses books]"
    line = f'    "{link.text}"{tag}\n        -> {", ".join(str(v) for v in others)}'
    if link.suppressed:
        idiom = link.suppressed[0].after
        line += f"\n        ({len(link.suppressed)} further uses suppressed as the fixed sense '{link.text} {idiom}')"
    return line


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Tier-1 verbatim phrase links.")
    ap.add_argument("ref", help="verse or passage, e.g. 'John 1:1-18'")
    ap.add_argument("--min-score", type=float, default=0.0)
    ap.add_argument(
        "--sources",
        action="store_true",
        help="group by the verse drawn on, rather than listing phrases",
    )
    args = ap.parse_args(argv)

    corpus = get_corpus()

    if args.sources:
        for vid, _ in links_for_passage(args.ref):
            found = sources_for_verse(vid)
            if not found:
                continue
            print(f"\n{vid}  {corpus.text(vid)}")
            for src in found:
                bits = ", ".join(f'"{p.text}"' for p in src.phrases)
                print(
                    f"    {src.target}  —  {src.fragments} fragment"
                    f"{'' if src.fragments == 1 else 's'}, {src.words} words"
                )
                print(f"        {bits}")
        return 0

    for vid, links in links_for_passage(args.ref):
        links = [x for x in links if x.score() >= args.min_score]
        if not links:
            continue
        print(f"\n{vid}  {corpus.text(vid)}")
        for link in links:
            print(_fmt(link, vid))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
