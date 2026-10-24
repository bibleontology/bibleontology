"""What the corpus says often that no vocabulary of ours can name.

2026-09-15: another pass at the whole Bible, looking only for concepts that
might have been missed. The hyperlinks were surprisingly sparse still, and a
systematic analysis going word by word would show whether justice had been
done.

That is the right instrument and it costs nothing: 13,858 lemmas are already on
disk in `out/interlinear.jsonl.gz`. Every previous attempt to find missing
concepts started from a list somebody wrote — a creedal twenty, a Copilot
twelve, a taxonomy of 858 items — and a list cannot report what it forgot. **A
lexicon can.** Going word by word is the only method here that is not downstream
of somebody's memory.

## The question asked of each lemma

    is this word frequent?        does the corpus say it a lot
    is it spread?                 across how many of the 66 books
    can anything we own find it?  a word family, a theme stamp, any taxonomy id

A lemma that is frequent and spread and reachable by NOTHING is a candidate for
a missing concept. That is a proposal, not a finding — the same 40% prior that
`declaredtypes.py` and `declaredthemes.py` both measured applies, and every
candidate is read before it becomes a register entry.

## Why frequency and spread, and not rarity

The same day: do not ignore the primary themes in search of the
outlier. A word in one book is that book's vocabulary; a word in fifty books
is the canon's. Ranking is `verses x books` for that reason, which is the same
scoring `themespine.py` uses and the opposite of `crosslink.py`'s.

## What is deliberately thrown away

Function words, proper names, and the numbers-and-measures vocabulary. Not
because they are uninteresting but because they are not CONCEPTS, and every
tool in this project that skipped this step drowned: `gradatio.py` returned
6,963 chains led by Ezekiel's temple measurements before a part-of-speech
filter cut it to 229.

The `domain` and `ln` fields on every word would make this far easier and are
NOT READ here or anywhere in this project. They are UBS's semantic-domain
labels and are permission-based. Everything below is derived from lemma, gloss
and part of speech only.

    python tools/lexcoverage.py --top 60
    python tools/lexcoverage.py --covered      # what we DO reach, as a check
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import sys
import unicodedata

# Hebrew and Greek on a cp1252 console. See tools/wordfamily.py.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

NT_IL = {"Mat", "Mrk", "Luk", "Jhn", "Act", "Rom", "1Co", "2Co", "Gal", "Eph",
         "Php", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb", "Jas",
         "1Pe", "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev"}

KEEP_POS = {"noun", "adj", "verb"}

# NARRATIVE SUBSTRATE, hand-curated, and declared as hand-curated.
#
# The first run ranked by verses x books and returned hand, day, house, city,
# year, eye, went up, took, sent. Those are frequent, spread across 35+ books,
# and they are not concepts -- they are what narrative is MADE of. No automatic
# test separates them from concepts: `day` is substrate in Genesis 30 and the
# Day of the LORD in Amos, and only reading tells them apart.
#
# So this list is judgement, not measurement, and it is written down so the
# judgement can be argued with. Every tool in this project that skipped a step
# like this drowned -- gradatio.py returned 6,963 chains led by Ezekiel's
# temple measurements before its part-of-speech filter cut it to 229.
SUBSTRATE = {
    "hand", "day", "house", "city", "year", "name", "eyes", "eye", "head",
    "brothers", "brother", "daughter", "wife", "father", "mother", "servant",
    "took", "sent", "called", "put", "went", "went up", "went out", "got up",
    "return", "see", "saw", "heard", "hear", "spoke", "speak", "know", "eat",
    "land", "inhabitants", "presence", "people", "word", "bear", "die",
    "way", "after", "no", "gave", "give", "stood", "stand", "found", "find",
    "great", "good", "many", "every", "another", "thing", "things", "place",
    "time", "water", "waters", "field", "way", "mouth", "voice", "night",
    "morning", "gold", "silver", "cubits", "measure", "number", "midst",
    "according", "before", "against", "over", "under", "between", "behold",
    "very", "also", "still", "again", "together", "left", "right",
}

# Glosses that mark a word as apparatus rather than concept. A lemma whose
# commonest gloss is one of these is skipped however frequent it is.
STOP_GLOSS = {
    "and", "the", "to", "in", "of", "a", "an", "that", "which", "who", "not",
    "for", "but", "with", "from", "on", "as", "is", "was", "be", "will",
    "this", "these", "he", "she", "it", "they", "we", "you", "i", "his",
    "her", "their", "my", "your", "our", "him", "them", "me", "us", "all",
    "then", "when", "there", "here", "so", "if", "or", "by", "at", "into",
    "up", "out", "do", "did", "have", "has", "had", "said", "say", "says",
    "saying", "one", "two", "three", "son", "sons", "man", "men", "came",
    "come", "went", "go", "made", "make", "now", "also", "were", "are",
}


def nfc(s):
    return unicodedata.normalize("NFC", s)


def load():
    """-> (freq, books, glosses, pos) per lemma, over the whole corpus."""
    freq = collections.Counter()
    books = collections.defaultdict(set)
    gloss = collections.defaultdict(collections.Counter)
    pos = collections.defaultdict(collections.Counter)
    nt = collections.Counter()
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        ref = d.get("ref")
        if not ref:
            continue
        b = ref.split(".")[0]
        for w in d["words"]:
            l = w.get("l")
            if not l:
                continue
            l = nfc(l)
            freq[l] += 1
            books[l].add(b)
            # ORIGINAL CASE, deliberately. The first version lowercased here
            # and then tested the gloss's first letter for a capital to detect
            # proper nouns, so the test could never fire: יהוה, יִשְׂרָאֵל,
            # יְהוּדָה and דָּוִד all came back as missing "concepts".
            if w.get("g"):
                gloss[l][w["g"].strip()] += 1
            if w.get("p"):
                pos[l][w["p"]] += 1
            if b in NT_IL:
                nt[l] += 1
    return freq, books, gloss, pos, nt


def owned():
    """-> ({lemma}, {label}) every lemma any vocabulary of ours can reach.

    Two sources, both already on disk: the word families (explicit lemmas) and
    tools/giftresponse.py's hand-built sets, which are lemma-level vocabulary
    even though they were written for one pattern.
    """
    lem, why = set(), {}
    p = ROOT / "ontology" / "word-families.json"
    if p.exists():
        for f in json.loads(p.read_text(encoding="utf-8"))["families"]:
            for side in ("greek", "hebrew"):
                for l in f.get(side, {}):
                    lem.add(nfc(l))
                    why[nfc(l)] = f["id"]
            for pair in f.get("pairs", []):
                for l in pair:
                    lem.add(nfc(l))
                    why.setdefault(nfc(l), f["id"] + " (pair)")
    try:
        import giftresponse as gr
        for name in ("GIFT", "RESPONSE", "BRIDGE"):
            for l in getattr(gr, name, ()):
                lem.add(nfc(l))
                why.setdefault(nfc(l), "giftresponse." + name)
    except Exception:
        pass
    return lem, why


def is_name(lemma, gl):
    """Proper nouns are not concepts. Greek capitalises them; Hebrew does not,
    so the gloss carries the rest -- a lemma glossed with a capitalised word
    that is not sentence-initial is almost always a name or a place."""
    if lemma[:1].isupper() and lemma[:1].isalpha():
        return True
    top = gl.most_common(1)
    return bool(top and top[0][0][:1].isupper())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--min-books", type=int, default=8)
    ap.add_argument("--min-verses", type=int, default=40)
    ap.add_argument("--covered", action="store_true",
                    help="show what IS reachable, as a sanity check")
    ap.add_argument("--side", choices=("ot", "nt", "both"), default="both")
    a = ap.parse_args()

    freq, books, gloss, pos, nt = load()
    have, why = owned()
    # TYPES and TOKENS say opposite things and both are reported, because
    # either alone misleads. 1% of the lexicon sounds like nothing; the same
    # families touch a large share of the actual words on the page, because a
    # register naturally holds frequent words. Neither number is coverage of
    # MEANING -- see the recall floors in tools/wordfamily.py, where grace
    # misses all seven passages agreed to teach it.
    tok = sum(freq.values())
    tokhave = sum(n for l, n in freq.items() if l in have)
    print(f"{len(freq):,} distinct lemmas, {tok:,} word occurrences.")
    print(f"reachable by a word family or a lemma set: "
          f"{len(have):,} lemmas ({100*len(have)/len(freq):.1f}% of types), "
          f"{tokhave:,} occurrences ({100*tokhave/tok:.1f}% of tokens)\n")

    rows = []
    for l, n in freq.items():
        if n < a.min_verses or len(books[l]) < a.min_books:
            continue
        if not (set(pos[l]) & KEEP_POS):
            continue
        g = gloss[l].most_common(1)
        if not g:
            continue
        low = g[0][0].lower().strip("[](){}. ")
        if low in STOP_GLOSS or low in SUBSTRATE:
            continue
        if is_name(l, gloss[l]):
            continue
        isnt = nt[l] > n / 2
        if a.side == "ot" and isnt:
            continue
        if a.side == "nt" and not isnt:
            continue
        rows.append((n * len(books[l]), n, len(books[l]), l, g[0][0],
                     l in have))

    rows.sort(reverse=True)
    show = [r for r in rows if r[5] == bool(a.covered)]
    # Precise, because the looser claim would be false: the stamps are
    # SECTION-level and several lemmas below sit in stamped sections
    # (`fire_sym`, `nations_as_character`, `priesthood`). What none of them has
    # is a way to ask for the concept itself.
    label = ("REACHABLE at lemma level" if a.covered
             else "REACHED BY NO LEMMA-LEVEL VOCABULARY")
    print(f"{len(show):,} lemmas {label} "
          f"({a.min_verses}+ verses, {a.min_books}+ books)\n")
    print(f"  {'verses':>6} {'books':>5}  {'lemma':<16} gloss")
    for score, n, nb, l, g, _ in show[:a.top]:
        tag = f"  [{why.get(l,'')}]" if a.covered else ""
        print(f"  {n:>6} {nb:>5}  {l:<16} {g[:26]}{tag}")

    if not a.covered:
        print("\n  A CANDIDATE, NOT A FINDING. declaredtypes.py and\n"
              "  declaredthemes.py both measured ~40% precision on a stronger\n"
              "  signal than frequency. Every line above is read before it\n"
              "  becomes a register entry.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
