"""What the Berean text actually calls each word, per lexeme.

2026-09-19, after the pattern card started showing its lexeme and the
other glosses: the gap was to be filled.

The gap is precise. The card could say `declares`, *also read as "oracle",
"says"* — and the reader had just read **"the prophecy of one who hears"** at
Numbers 24:4. `prophecy` was in none of those lists, because they come from
MACULA's glosses and the screen shows the Berean Standard Bible. Two different
English layers, and the card was offering the one the reader cannot see.

## The join was already in the file

The Berean USFM tags its own words with Strong's numbers:

    \\w prophecy|strong="H5002"\\w*

So the words a reader will actually meet are recoverable per lexeme, with
counts, straight from the text being displayed. Nothing is inferred and no
alignment is computed: the translators wrote the tag.

## What this is for, and what it is not

**For:** a card naming a word can name it the way the screen names it, and list
the other ways the same screen will name it elsewhere. 43.5% of occurrences are
glossed something other than their lemma's dominant gloss, so without this a
reader lands on a verse and cannot tell they are in the right place.

**Not for:** replacing MACULA's glosses. Those are a scholarly gloss of the
lexeme; these are one translation's choices in context. Both belong on the
card, labelled, and the difference between them is often the interesting part —
`nᵊʾum` is glossed *declares* and rendered *declares, oracle, prophecy*
depending on who is speaking.

    python tools/bsbwords.py            # counts, and the motivating case
    python tools/bsbwords.py --write
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
SRC = ROOT / "data" / "raw" / "usfm" / "engbsb"
DEST = OUT / "bsb-words.json"

# THE TAG MARKS WHERE A RENDERING STARTS, NOT WHICH WORD TRANSLATES.
#
# Numbers 24:4 in the Berean USFM reads
#
#     \w the|strong="H5002"\w* prophecy \w of|strong="H5869"\w*
#
# so `prophecy` -- the word the reader actually read, and the whole reason for this
# file -- carries NO TAG AT ALL. Only `the` does. Reading tagged words alone
# gives "the" 650 times for H5002 and misses the rendering completely.
#
# So a rendering is the tagged word PLUS any bare words that follow it, up to
# the next tag. That is the format's own logic: one tag opens a run of English
# standing for one word of the original.
WORD = re.compile(
    r'\\w ([^|\\]+)\|[^\\]*?strong="([HG]\d+[a-z]?)"[^\\]*?\\w\*([^\\]*)')
# Footnotes carry their own \w runs in some editions; a note is not the text.
NOTE = re.compile(r"\\f .*?\\f\*", re.S)


def key_of(strong: str) -> str | None:
    """`H5002` -> `h5002`, matching the sense-card keys."""
    if not strong:
        return None
    lang, num = strong[0].lower(), re.sub(r"^0+", "", strong[1:])
    num = re.sub(r"[^0-9]", "", num)
    return f"{lang}{num}" if num else None


def harvest() -> dict:
    per = collections.defaultdict(collections.Counter)
    files = 0
    for f in sorted(SRC.glob("*.usfm")):
        txt = NOTE.sub(" ", f.read_text(encoding="utf-8", errors="replace"))
        files += 1
        for m in WORD.finditer(txt):
            tail = re.sub(r"[^A-Za-z' -]", " ", m.group(3) or "")
            word = re.sub(r"\s+", " ", m.group(1) + " " + tail).strip()
            k = key_of(m.group(2))
            # The tag is on every word including "the" and "of", which are
            # supplied by the translators rather than standing for a lexeme;
            # they are kept, because a reader meets them and the counts make
            # clear which renderings are the real ones.
            if k and word:
                per[k][word.lower()] += 1
    return per, files


# English the translators supply rather than translate. These carry a tag in
# the USFM because every word does, and they tell a reader nothing about which
# lexeme they are looking at.
SUPPLIED = {
    "the", "a", "an", "of", "to", "and", "in", "on", "at", "for", "with",
    "is", "are", "was", "were", "be", "been", "am", "will", "shall", "that",
    "this", "these", "those", "it", "he", "she", "they", "him", "her", "them",
    "his", "hers", "their", "its", "i", "you", "your", "we", "us", "my", "me",
    "not", "but", "or", "as", "so", "then", "there", "who", "whom", "which",
    "all", "from", "by", "up", "out", "into", "upon", "when", "if", "do",
    "did", "has", "have", "had", "s", "o",
}


def disambiguate(per):
    """Drop renderings that plainly belong to a different lexeme.

    The trailing-run rule is right about the format and wrong about the text:
    the Berean USFM leaves some English untagged ENTIRELY, and those words get
    swept up by whichever tag precedes them. `\\w the|strong="H5002"\\w* land`
    in Jeremiah is how `land` -- which is אֶרֶץ -- came to look like a
    rendering of נְאֻם, 21 times.

    So the tagging is NOT a word alignment and must not be read as one. What it
    supports is an association, and an association can be adjudicated: a word
    belongs to the lexeme that claims it most. `land` is claimed overwhelmingly
    by H776 and barely by H5002, so H5002 loses it; `prophecy` is claimed by
    H5002 and almost nothing else, so it stays.

    Supplied English is dropped outright -- every word carries a tag, so "the"
    is the commonest "rendering" of nearly every lexeme in the Bible and means
    nothing.
    """
    # strip leading supplied words: "the prophecy" -> "prophecy"
    clean = collections.defaultdict(collections.Counter)
    for k, c in per.items():
        for phrase, n in c.items():
            parts = [w for w in phrase.split() if w]
            while parts and parts[0] in SUPPLIED:
                parts.pop(0)
            w = " ".join(parts).strip()
            if w and not all(p in SUPPLIED for p in parts):
                clean[k][w] += n
    # who claims each word most
    owner = collections.defaultdict(collections.Counter)
    for k, c in clean.items():
        for w, n in c.items():
            owner[w][k] += n
    out = collections.defaultdict(collections.Counter)
    for k, c in clean.items():
        for w, n in c.items():
            tot = sum(owner[w].values())
            # Keep it if this lexeme accounts for a real share of the word's
            # uses. A fifth is low on purpose: a word legitimately shared by
            # two or three lexemes should survive for all of them, while
            # `land` at 21 against H776's thousands should not.
            if tot and n / tot >= 0.20:
                out[k][w] = n
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--probe", default="h5002")
    a = ap.parse_args()

    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")
    per, files = harvest()
    tot = sum(sum(c.values()) for c in per.values())
    print(f"{files} Berean books, {len(per):,} lexemes, {tot:,} tagged words\n")

    multi = sum(1 for c in per.values() if len(c) > 1)
    print(f"{multi:,} lexemes are rendered more than one way "
          f"({multi/max(len(per),1):.0%})")
    spread = sorted(per.items(), key=lambda kv: -len(kv[1]))[:6]
    print("\nmost variously rendered:")
    for k, c in spread:
        print(f"   {k:<8} {len(c):>4} renderings   "
              + ", ".join(f"{w} ({n})" for w, n in c.most_common(4)))

    probe = per.get(a.probe)
    if probe:
        print(f"\nDoug's case, {a.probe}:")
        for w, n in probe.most_common(8):
            print(f"   {w:<16} {n}")

    per = disambiguate(per)
    probe = per.get(a.probe)
    if probe:
        print(f"\nafter disambiguation, {a.probe}:")
        for w, n in probe.most_common(8):
            print(f"   {w:<16} {n}")

    if not a.write:
        print("\nnothing written -- pass --write")
        return 0
    # Only the renderings worth showing: a long tail of one-offs is mostly
    # supplied words and punctuation artefacts, and a card cannot show 60.
    # A rendering seen ONCE is residual misalignment, not a translation choice:
    # for H5002 the tail reads "areas", "mountain summit", "land would". Twice
    # is the floor, which keeps `oracle` (2) and `prophecy` (6) and drops all
    # of that.
    slim = {k: [[w, n] for w, n in c.most_common(8) if n >= 2]
            for k, c in per.items()}
    slim = {k: v for k, v in slim.items() if v}
    DEST.write_text(json.dumps({
        "_source": "Berean Standard Bible USFM, ebible.org, Public Domain. Its "
                   "own \\w ...|strong=\"...\" word tags.",
        "_note": "How the BEREAN TEXT renders each lexeme, with counts — the "
                 "words a reader actually meets on screen, as distinct from "
                 "MACULA's glosses of the same lexeme. Both belong on a card "
                 "and the difference between them is often the point. Top 8 "
                 "per lexeme. See tools/bsbwords.py.",
        "words": slim}, ensure_ascii=False), encoding="utf-8")
    print(f"\n  -> {DEST.relative_to(ROOT)}  {len(slim):,} lexemes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
