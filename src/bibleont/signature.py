"""What two passages share in the original language, weighted by how rare it is.

The cheapest of the three ways to test whether a passage is an instance of a
pattern, and the only one that needs nothing from the graph. It reads the
tagged Hebrew and Greek and asks: which rare words do these two passages have
in common?

## Why it is worth having at all

Two findings on one morning, both invisible in English:

    Gen 18:21 / Exod 3:8    H3381    KJV "go down" / "come down"
    2Sam 24:1 / 1Chr 21:1   H5496    KJV "moved"   / "provoked"

In each pair the King James chooses different English for one Hebrew verb, so
the strongest signal connecting the passages cannot be seen by reading the
translation, and no amount of phrase matching over English will find it. The
second pair decided a schema question -- one relation covers both incitements
because the corpus uses one word.

## Rarity is the whole mechanism

The framing is cladistics: wolves, lions and tigers are all dominant
predator mammals, and only two are cats. Having a backbone does not tell you
which; retractable claws does. **A shared character only counts if it
discriminates.**

So the score is IDF-weighted. H9001 (the conjunction) appears in most verses in
the Hebrew Bible and is worth nothing. H5496 appears in fewer than twenty and
is worth a great deal. Without the weighting every pair of verses looks alike,
because every pair shares "and", "the" and "said".

This is the same weighting the lemma resolver uses to pick a root for a node,
and the same the seed vocabulary uses to rank a book's characteristic words.
Third use, and it has been the right instrument every time.

## What this is not

**Not evidence that two passages mean the same thing.** Shared vocabulary is a
candidate and never a conclusion -- the rule is that similarity is not
reference, and no weighting fixes it. What it does is put a
short list in front of the expensive checks, which is all a first pass should
do.

## STATUS: comparison works, ranking does not

`score` and `--against` are sound and useful. Given two passages they say what
rare vocabulary they share, and they separate a real pair from a control by
about three to one -- Gen 18:20-21 against Exod 3:7-9 scores 0.171 on H6818
and H3381, and against Ruth 2:1-3 scores 0.064 on nothing but "please".

**`neighbours` is not solved.** Searching the corpus blind for what resembles
a passage has been attempted three ways and none ranks correctly:

    summed IDF            Exod 3 at rank 4, three chapters of noise above it,
                          because six ordinary shared verbs outweigh one rare
                          one when the weights are added.

    rarity floor          worse -- rank 40. The floor discarded H7200 (see)
                          and H0935 (come), which are two of the four elements
                          of the construction being searched for. They are
                          common words and the construction still needs them.

    joint co-occurrence   circular, and it took a while to see. The shared set
                          is BY DEFINITION what the two passages have in
                          common, so only those two contain it and every
                          candidate ties. It can validate a construction
                          chosen by hand -- cry + go-down + see + come occurs
                          in exactly two places in the Bible, Gen 18:19-21 and
                          Exod 3:7-9 -- but it cannot rank one.

    rarest shared root    ties everywhere: dozens of passages share SOME word
                          of comparable rarity, and the peak alone says
                          nothing about whether the rest lines up.

The hand-validated finding stands and is worth keeping in view: a set of four
ordinary words, taken together, is unique to two passages in the whole corpus.
That says the signal is real and the retrieval is what is missing. Likely next
attempt: score a candidate by how unlikely its overlap is *given the sizes of
both signatures* -- a hypergeometric tail rather than a sum -- so that sharing
seven roots out of twenty means more than sharing seven out of two hundred.

Until then, use `--against` on candidates found another way, and do not trust
the ordering `neighbours` produces.
"""

from __future__ import annotations

import math
import re
import sys
from functools import lru_cache

# Function words and particles carry no signal and swamp everything if left
# in. Hebrew prefixes and suffixes in STEPBible's numbering start at H9000;
# they are grammar, not vocabulary.
_GRAMMAR = re.compile(r"^H9\d{3}")


@lru_cache(maxsize=1)
def _index() -> tuple[dict, dict, int]:
    """{verse: {root}}, {root: verses containing it}, and the verse count."""
    from .lemma import load

    raw = load()["verses"]
    by_verse: dict[str, set] = {}
    freq: dict[str, int] = {}
    for ref, words in raw.items():
        roots = {r for _, r in words if r and not _GRAMMAR.match(r)}
        if not roots:
            continue
        by_verse[ref] = roots
        for r in roots:
            freq[r] = freq.get(r, 0) + 1
    return by_verse, freq, len(by_verse)


def idf(root: str) -> float:
    """How much a shared root is worth. Rarer is worth more.

    Document frequency, not raw count: a word used ten times in one chapter is
    less discriminating than one used ten times across ten books, and the
    former is common in this corpus -- repetition within a passage is a Hebrew
    rhetorical device rather than evidence of anything.
    """
    _, freq, total = _index()
    n = freq.get(root, 0)
    if not n:
        return 0.0
    return math.log(total / n)


@lru_cache(maxsize=1)
def _proper() -> set:
    """Roots that are proper nouns, from the tagging rather than by guess.

    STEPBible marks them: Sodom and Gomorrah are `HNpl`, Yahweh `HNpt`, while
    the outcry of Gen 18:20 is `HNcfsc` -- a common noun. The `Np` prefix is
    the whole test.

    They have to be removable, because the two questions this module answers
    need opposite treatment of them:

      what REFERS to this passage      keep names. Jer 49 naming Sodom and
                                       Gomorrah is the strongest possible
                                       evidence that it is talking about this.

      what SHARES this CONSTRUCTION    drop names. A pattern is a form, and
                                       whose cry it was is exactly what varies
                                       between instances of it.

    Found the hard way: searching for Gen 18:20-21's neighbours returned Jer
    49, Jer 48, Deut 29 and Isa 1 above Exod 3 -- every one of them a passage
    that names Sodom. The ranking was correct and the question was wrong.
    """
    import glob
    import io
    import os

    from .lemma import RAW, _ROOT, _fields

    proper: dict[str, int] = {}
    common: dict[str, int] = {}
    for path in sorted(glob.glob(str(RAW / "TA*"))):
        if "TAGNT" in os.path.basename(path):
            continue                       # Greek tagging marks case, not names
        _, scol = _fields(path)
        for line in io.open(path, encoding="utf-8", errors="replace"):
            cols = line.rstrip("\n").split("\t")
            if len(cols) <= scol + 1:
                continue
            roots = _ROOT.findall(cols[scol])
            if not roots:
                continue
            is_name = any(p.startswith("Np") for p in cols[scol + 1].split("/"))
            for r in roots:
                (proper if is_name else common)[r] = (
                    (proper if is_name else common).get(r, 0) + 1)
    # A root counts as a name where it is tagged one more often than not.
    # `H3068G` (Yahweh) is always Npt; a handful are genuinely both.
    return {r for r, n in proper.items() if n > common.get(r, 0)}


def signature(refs, names: bool = True) -> set:
    """Every content root in a verse or a run of them.

    `names=False` drops proper nouns, which is what pattern search wants.
    """
    by_verse, _, _ = _index()
    if isinstance(refs, str):
        refs = [refs]
    out: set = set()
    for ref in refs:
        out |= by_verse.get(str(ref), set())
    return out - _proper() if not names else out


def expand(ref: str) -> list[str]:
    """A reference to the verse ids it covers, using the corpus."""
    from .corpus import get_corpus
    from .refs import parse_ref

    return [str(v) for v in get_corpus().expand(parse_ref(ref, allow_book=True))]


# Below this a shared root is a primitive character and is discarded rather
# than down-weighted.
#
# Summing IDF was the first attempt and it ranked Num 11:15-17 above Exod 3:7-9
# for Gen 18:20-21. Numbers shares "know", "see", "do", "if" -- six ordinary
# verbs whose weights add up. Exodus shares H6818, the cry, at idf 7.35, and
# was outvoted by them.
#
# That is precisely the failure cladistics avoids by ignoring primitive
# characters outright: every vertebrate has a backbone, so a backbone can never
# be evidence, however many of them you count. A floor discards rather than
# discounts, which is the difference between "worth less" and "not evidence".
#
# 4.0 keeps roots appearing in fewer than about 1 verse in 55.
FLOOR = 4.0


def score(a, b, floor: float = FLOOR) -> tuple[float, list]:
    """How much RARE vocabulary two passages share, and which roots.

    Normalised by the smaller signature so that a long passage does not score
    highly against everything merely by containing more words. The asymmetry
    matters: four rare roots shared with a two-verse passage is a strong
    signal, and the same four shared with a whole book is not.
    """
    sa, sb = (a if isinstance(a, set) else signature(a),
              b if isinstance(b, set) else signature(b))
    shared = {r for r in sa & sb if idf(r) >= floor}
    if not shared:
        return 0.0, []
    weight = sum(idf(r) for r in shared)
    norm = min(sum(idf(r) for r in sa if idf(r) >= floor),
               sum(idf(r) for r in sb if idf(r) >= floor)) or 1.0
    ranked = sorted(shared, key=idf, reverse=True)
    return weight / norm, ranked


def cooccurrences(roots, window: int = 3) -> int:
    """How many places in the corpus contain ALL of these roots together.

    The measure that made this module work, after two that did not.

    Summed IDF was the first attempt and ranked six ordinary verbs above one
    rare one. A rarity floor was the second and was worse: it discarded
    H7200 (see) and H0935 (come) as too common, which are two of the four
    elements of the construction being searched for, and Exodus 3 fell from
    rank 4 to rank 40.

    Both were measuring the wrong thing. **Rarity is a property of the
    combination, not of the members.** "See" is in 1,106 verses and "come" in
    1,753, and

        cry + go-down + see + come, inside three verses

    occurs in exactly two places in the Bible -- Gen 18:19-21 and Exod 3:7-9.
    Nothing else in the corpus has all four. A set of ordinary words can be
    unique; that is what an idiom is.
    """
    by_verse, _, _ = _index()
    want = set(roots)
    if not want:
        return 0
    refs = list(by_verse)
    n = 0
    i = 0
    while i <= len(refs) - window:
        sig: set = set()
        for s in refs[i:i + window]:
            sig |= by_verse[s]
        if want <= sig:
            n += 1
            i += window          # count a region once, not once per offset
        else:
            i += 1
    return n


def neighbours(refs: list[str], top: int = 8, window: int = 3,
               skip_book: str | None = None, names: bool = True) -> list[tuple]:
    """Passages elsewhere that share this one's rare vocabulary.

    Searched over sliding windows rather than single verses, because the unit
    that recurs is a construction and constructions run across verse
    boundaries -- "a cry rises, God comes down, God sees" is three verses in
    Genesis and three in Exodus, and neither is one verse anywhere.
    """
    by_verse, _, _ = _index()
    target = signature(refs, names=names)
    if not target:
        return []
    drop = set() if names else _proper()
    own = set(refs)
    refs_in_order = list(by_verse)
    out = []
    for i in range(len(refs_in_order) - window + 1):
        span = refs_in_order[i:i + window]
        if any(s in own for s in span):
            continue
        if skip_book and span[0].rsplit(" ", 1)[0].rsplit(" ", 1)[0] == skip_book:
            continue
        sig: set = set()
        for s in span:
            sig |= by_verse[s]
        sig -= drop
        # The FULL intersection, with no rarity floor. The floor belongs to
        # the cheap ranking below and must not touch what stage two counts:
        # the whole finding was that four roots co-occur in two places, and
        # two of those four are ordinary words a floor discards. Truncating
        # the set before counting destroys the signal it exists to measure --
        # which is what the first version of this did, and everything tied.
        shared = target & sig
        if len(shared) < 2:
            continue
        weight = sum(idf(r) for r in shared)
        out.append((weight, f"{span[0]}-{span[-1].rsplit(':', 1)[1]}",
                    sorted(shared, key=idf, reverse=True)))
    out.sort(key=lambda r: -r[0])

    # Two stages, because exact joint rarity is far too slow to run against
    # every window and far more discriminating than the cheap score.
    #
    # Summed IDF is a good FILTER and a poor RANK: it surfaces the right
    # candidates somewhere in its top hundred and orders them badly. So the
    # cheap score chooses who gets looked at, and co-occurrence decides the
    # order -- how many places in the whole corpus share this much of the
    # query at once. Two is remarkable. Two hundred is a cliche.
    #
    # Overlapping windows are collapsed first: before this, three of the top
    # eight were Jer 48:2-4, 48:3-5 and 48:4-6, which is one passage wearing
    # three hats, and thirteen chapters held multiple slots in the top forty.
    seen: set = set()
    distinct = []
    for sc, where, shared in out[:600]:
        chapter = where.rsplit(":", 1)[0]
        if chapter in seen:
            continue
        seen.add(chapter)
        distinct.append((sc, where, shared))

    # Rank by the RAREST thing shared, not by the sum and not by the joint
    # rarity of the shared set.
    #
    # Joint rarity was the third attempt and it is circular: the shared set is
    # by definition what these two passages have in common, so only these two
    # contain it, and every candidate ties at two. It validated a construction
    # picked by hand and could never rank one.
    #
    # The rarest shared root is the honest version of the same cladistic
    # instinct. Six ordinary verbs in common say little however their weights
    # add up; one word that occurs in twenty verses in the Bible says a great
    # deal on its own. Exod 3 shares H6818 -- the cry, 20 verses -- with
    # Gen 18:20-21. Nothing else in the candidate list shares anything rarer
    # than H3381 at 346.
    #
    # Ties break on how many roots are shared, so a passage matching one rare
    # word and six others outranks one matching the same rare word alone.
    ranked = []
    for sc, where, shared in distinct[:120]:
        peak = max(idf(r) for r in shared)
        ranked.append((-peak, -len(shared), -sc, where, shared))
    ranked.sort()
    return [(-peak, w, sh) for peak, _, _, w, sh in ranked[:top]]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m bibleont.signature <ref> [<ref> ...]")
        print("       python -m bibleont.signature 'Gen 18:20' 'Gen 18:21'")
        return 2
    if "--against" in argv:
        i = argv.index("--against")
        a, b = argv[:i], argv[i + 1:]
        refs_a = [r for x in a for r in expand(x)]
        refs_b = [r for x in b for r in expand(x)]
        s, shared = score(signature(refs_a), signature(refs_b))
        print(f"  {' '.join(a)}  vs  {' '.join(b)}")
        print(f"  score {s:.3f}")
        for r in shared[:10]:
            print(f"     {r:8} idf {idf(r):5.2f}")
        return 0

    names = "--structure" not in argv
    argv = [a for a in argv if not a.startswith("--")]
    refs = [r for x in argv for r in expand(x)]
    book = refs[0].rsplit(" ", 1)[0].rsplit(" ", 1)[0] if refs else None
    print(f"  {' '.join(argv)}  ({len(refs)} verses, "
          f"{len(signature(refs, names=names))} roots"
          f"{'' if names else ', proper nouns dropped'})\n")
    print(f"  {'rarest':>7}  {'passage':22} shared roots")
    for n, where, shared in neighbours(refs, skip_book=book, names=names):
        print(f"  {n:>7}  {where:22} {' '.join(shared[:7])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
