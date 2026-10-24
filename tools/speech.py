"""How deep inside a told story each verse sits.

2026-09-09: the tricky thing with narrative is that there is a story within
the story. The outer layer is that Jesus talked to the Pharisees and confused
his disciples before helping them understand. On the inner layer Jesus gave a
story where a father welcomed his lost son home, and then gave meaning to it,
explaining that the father is our heavenly Father and we are the sons.

This is a **correctness** problem before it is a modelling one. The father did
not kill the fatted calf in the world; he did so inside a story Jesus told, and
a graph that records the two alike asserts something the text does not. The
project already holds this rule for a different case -- *read the corpus without
harmonizing* -- and this is the same duty one level down.

## Why not MACULA, for once

MACULA has **no speech markup at all**: no `speaker`, no `quote`, no `sp`
element anywhere in the Greek. The `quoted` flag on `out/events.jsonl.gz` is
populated for Mark and essentially nothing else --

    Mrk 57.1%   Mat 0.0%   Luk 0.0%   Jhn 0.0%   Act 0.0%

-- so Luke 15, which is almost entirely direct speech, reports 0 of 68 events
quoted. It cannot carry this.

What can is **quotation depth in the modern translations**, which is an
inversion of this project's usual direction and worth stating plainly: here a
1611 or 1901 text carries *less* information than a modern one. KJV and ASV
punctuate no speech at all (0.0% of verses); BSB marks 17.7% and WEB 22.5%, and
752 verses nest single inside double.

The BSB was authorised as a source where needed.

**Provenance gap, recorded rather than skipped.** `data/macula-manifest.json`
pins a version, a sha256 and a byte count for every MACULA file. The header of
`verses.bsb.jsonl` is `{"translation": "BSB"}` and nothing else -- no source, no
retrieval date, no licence line. Using it as a *source* rather than a display
translation raises the standard it should be held to, and it does not currently
meet MACULA's.

Which WEB edition is on disk, WEBUS or WEBBE? **Measured rather than assumed: it is WEBUS.** 724 American spellings
(savior 41, honor 230, neighbor 162, labor 160) against **zero** British ones
across savior/honour, colour, favour, neighbour and labour. BSB tests the same
way. That the question had to be answered by counting spellings rather than by
reading a header is the provenance gap, restated.

## The one hard case in the punctuation

`’` is both a closing single quote and an apostrophe. *father's* and
*estate.'* end with the same character. The rule used: **a `’` preceded by
a letter is an apostrophe; otherwise it closes a quote.** Anything relying on
this is reported with the disagreement rate between BSB and WEB, because two
independently punctuated texts are the only available check.

## What depth means

    0   narration -- the world the book asserts
    1   direct speech
    2   a story told inside that speech        <- the parable
    3   speech inside the told story
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEST = ROOT / "out" / "speech-depth.jsonl.gz"

OPEN2, CLOSE2 = "“", "”"
OPEN1, CLOSE1 = "‘", "'"
# U+2019 NEVER APPEARS in these files. Single quotes open with U+2018 and
# close with the STRAIGHT apostrophe U+0027, which is also the possessive --
# 1,450 openers against 3,599 apostrophes in BSB. Reading U+2019 as the
# closer, as the first draft did, meant depth only ever incremented and Luke
# 15 ran to 23 levels deep.

# All five translation files share one SBL-style scheme; the PIPELINE layers do
# not. Kept here so the join is explicit rather than assumed.
TO_CANON = {
    "Gen": "Gen", "Exod": "Exo", "Lev": "Lev", "Num": "Num", "Deut": "Deu",
    "Josh": "Jos", "Judg": "Jdg", "Ruth": "Rut", "1Sam": "1Sa", "2Sam": "2Sa",
    "1Kgs": "1Ki", "2Kgs": "2Ki", "1Chr": "1Ch", "2Chr": "2Ch", "Ezra": "Ezr",
    "Neh": "Neh", "Esth": "Est", "Job": "Job", "Ps": "Psa", "Prov": "Pro",
    "Eccl": "Ecc", "Song": "Sng", "Isa": "Isa", "Jer": "Jer", "Lam": "Lam",
    "Ezek": "Ezk", "Dan": "Dan", "Hos": "Hos", "Joel": "Jol", "Amos": "Amo",
    "Obad": "Oba", "Jonah": "Jon", "Mic": "Mic", "Nah": "Nam", "Hab": "Hab",
    "Zeph": "Zep", "Hag": "Hag", "Zech": "Zec", "Mal": "Mal",
    "Matt": "Mat", "Mark": "Mrk", "Luke": "Luk", "John": "Jhn", "Acts": "Act",
    "Rom": "Rom", "1Cor": "1Co", "2Cor": "2Co", "Gal": "Gal", "Eph": "Eph",
    "Phil": "Php", "Col": "Col", "1Thess": "1Th", "2Thess": "2Th",
    "1Tim": "1Ti", "2Tim": "2Ti", "Titus": "Tit", "Phlm": "Phm", "Heb": "Heb",
    "Jas": "Jas", "1Pet": "1Pe", "2Pet": "2Pe", "1John": "1Jn", "2John": "2Jn",
    "3John": "3Jn", "Jude": "Jud", "Rev": "Rev",
}


def load(name):
    rows = {}
    p = ROOT / "data" / "bible" / name
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if "b" in d:
            rows[(d["b"], d["c"], d["v"])] = d["t"]
    return rows


def walk(text, depth):
    """Depth entering the verse -> (depth at each char boundary, depth after).

    Returns the DEEPEST level the verse reaches, not the shallowest. The first
    draft used the minimum and mislabelled the verse that opens a parable:
    Luke 15:11 begins *"Then Jesus said,"* at depth 0, so the minimum is 0 and
    the verse reads as narration when its content is the parable's first line.
    The question a consumer asks is "does this verse contain told-story
    material", and that is the maximum.
    """
    hi = depth
    for i, ch in enumerate(text):
        if ch == OPEN2 or ch == OPEN1:
            depth += 1
        elif ch == CLOSE2:
            depth = max(0, depth - 1)
        elif ch == CLOSE1:
            # THE ONE HARD CASE: apostrophe or closing quote?
            prev = text[i - 1] if i else ""
            if not prev.isalpha():
                depth = max(0, depth - 1)
        hi = max(hi, depth)
    return hi, depth


def depths(rows):
    """Chapter by chapter, because a quotation runs across verse boundaries."""
    out, chapters = {}, collections.defaultdict(list)
    for (b, c, v) in rows:
        chapters[(b, c)].append(v)
    for (b, c), vs in chapters.items():
        d = 0
        for v in sorted(vs):
            t = rows[(b, c, v)]
            hi, d = walk(t, d)
            out[(b, c, v)] = hi
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    bsb, web = load("verses.bsb.jsonl"), load("verses.web.jsonl")
    # BSB IS PRIMARY, and the reason is countable. Open-minus-close for the
    # double quote: BSB +59, WEB +1,466. WEB re-opens a quotation at each
    # paragraph of a continuing speech without closing the previous one, which
    # a depth counter cannot survive. BSB was authorised as a source; WEB is
    # kept only as a second opinion on WHETHER a verse is inside speech.
    db, dw = depths(bsb), depths(web)
    keys = sorted(set(db) & set(dw))
    print(f"verses in both BSB and WEB: {len(keys)}")
    for nm, rows in (("BSB", bsb), ("WEB", web)):
        o = sum(t.count(OPEN2) for t in rows.values())
        c = sum(t.count(CLOSE2) for t in rows.values())
        print(f"  {nm} double quotes: {o} open, {c} close, net {o-c:+d}")

    agree = sum(1 for k in keys if (db[k] > 0) == (dw[k] > 0))
    print(f"\nBSB and WEB agree on INSIDE-SPEECH: {agree} "
          f"({100*agree/len(keys):.1f}%)")
    both = sum(1 for k in keys if db[k] > 0 and dw[k] > 0)
    either = sum(1 for k in keys if db[k] > 0 or dw[k] > 0)
    print(f"  both say inside speech: {both} of {either} "
          f"({100*both/max(either,1):.1f}%)")

    dist = collections.Counter(db[k] for k in keys)
    print("\nDEPTH -- BSB, the deepest level each verse reaches")
    for d in sorted(dist):
        lab = {0: "narration -- the world", 1: "direct speech",
               2: "a story told inside speech", 3: "speech inside that story"}
        print(f"  {d}  {dist[d]:>6}  {100*dist[d]/len(keys):>5.1f}%  "
              f"{lab.get(d, 'deeper')}")

    print("\nLUKE 15 -- the test case")
    for v in (1, 2, 3, 11, 12, 18, 21, 31, 32):
        k = ("Luke", 15, v)
        if k in db:
            print(f"  v{v:<3} BSB={db[k]}  WEB={dw.get(('Luke',15,v))}  "
                  f"{bsb[k][:78]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    n = 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_note": "Quotation depth per verse. 0 narration, 1 direct speech, "
                     "2 a story told inside speech (a parable), 3 deeper. "
                     "Derived from BSB punctuation; KJV and ASV punctuate no "
                     "speech at all and MACULA carries no speech markup. WEB "
                     "is recorded alongside but is not authoritative: it "
                     "re-opens quotations at paragraph breaks (net +1,466 "
                     "unclosed) which a depth counter cannot survive.",
            "_caveat": "A closing single quote and an apostrophe are the same "
                       "character; one is read as an apostrophe when preceded "
                       "by a letter.",
        }, ensure_ascii=False) + "\n")
        for k in keys:
            b, c, v = k
            canon = TO_CANON.get(b)
            if not canon:
                continue
            f.write(json.dumps({
                "ref": f"{canon}.{c}.{v}", "src": f"{b}.{c}.{v}",
                "depth": db[k],
                "bsb": db[k], "web": dw[k],
            }, ensure_ascii=False) + "\n")
            n += 1
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({n} verses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
