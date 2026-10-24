"""Align ENGLISH verse numbers to MACULA's, by content rather than by rule.

Found 2026-09-08 while building the coverage panel, which reported more parsed
verses in Psalms than the Psalms contain. **The Hebrew and English Bibles number
verses differently**, and in the chapters where they disagree the app was
attaching MACULA's structure to the wrong KJV verse -- silently, in the reader's
view.

The ruling, the same day, makes the fix much smaller: verses are an indexing
convention and grouping was never directed to be based on them. The fix should
not affect the grouping or relationships, except for sourcing documentation
with relationships, where the verse numbers of the KJV were to be used because
readers will go by the verse numbers in all of the modern translations.

So the pipeline's internal joins are MACULA-to-MACULA and were never wrong. The
only place the mismatch bites is where an **English verse is turned into a
MACULA reference for display**, which is one function with three call sites.

And it is ENGLISH versification, not the King James's. The KJV is not treated
as special, and is not the default English version, since the Berean is far
more readable. Checked: **all five translations on
disk -- KJV, ASV, BSB, WEB, YLT -- share identical versification, 0 differing
verse sets across all 1,189 chapters.** So this map is Hebrew-to-English and
holds whichever translation is displayed.

## Why a rule does not work, and content does

The obvious model is "MACULA counts the superscription as verse 1, so add one".
It is wrong. The offsets come in **paired opposites in adjacent chapters**:

    Exod 7  +4   then  Exod 8  -4
    Lev  5  +7   then  Lev  6  -7
    Gen 31  -1   then  Gen 32  +1

That is not a verse-numbering difference, it is the two traditions putting a
**chapter boundary** in different places, and no per-chapter constant derived
from verse counts can express it.

So the offset is found by **aligning the text with itself**: for each candidate
shift, score how well the KJV's content words overlap MACULA's own English
glosses for the verse it would land on, and keep the best. Tested against seven
chapters with known answers, including four controls that must come back zero:

    Ps 3    +1      Ps 23    0
    Gen 32  +1      Gen 1    0
    Jonah 2 +1      Exod 7   0
                    Lev 5    0

Exodus 7 is the useful control: its *last* verse number differs by four, and its
body aligns at zero, because the boundary moved rather than the numbering.

## What this does not fix

A chapter whose offset **changes partway through** -- where one tradition splits
a verse the other keeps whole -- gets the dominant offset and is wrong for the
remainder. Those are reported by the checker rather than hidden.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEST = ROOT / "out" / "verse-map.json"

STOP = set(
    "the a an of and to in on at by for with from he she it they them his her "
    "is was were be that this all shall unto thou thy thee my me not so then "
    "there which who when out up into upon before after".split())


def words(s):
    return {w for w in re.findall(r"[a-z]+", (s or "").lower())
            if w not in STOP and len(w) > 2}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--span", type=int, default=4, help="offsets to try, +/-")
    ap.add_argument("--min-score", type=float, default=0.06,
                    help="below this the chapter has too little overlap to judge")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    sys.path.insert(0, str(ROOT / "app2"))
    import server                                              # noqa: E402
    d = server.load()

    gloss = collections.defaultdict(set)
    for n in d["nodes"].values():
        r = n.get("ref")
        if r:
            gloss[r] |= words(n.get("text"))

    chapters = collections.defaultdict(list)
    for (b, c, v) in d["verses"]:
        chapters[(b, c)].append(v)

    out, shifted, weak, ties = {}, 0, 0, 0
    for (b, c), vs in sorted(chapters.items()):
        mb = server.TO_MACULA.get(b, b)
        vs.sort()
        scores = {}
        for off in range(-a.span, a.span + 1):
            tot = n = 0
            for v in vs:
                kw = words(d["verses"][(b, c, v)])
                mw = gloss.get(f"{mb}.{c}.{v + off}")
                if kw and mw:
                    tot += len(kw & mw) / len(kw | mw)
                    n += 1
            if n >= max(3, len(vs) // 3):
                scores[off] = tot / n
        if not scores:
            continue
        best = max(scores, key=lambda k: scores[k])
        top = scores[best]
        if top < a.min_score:
            weak += 1
            continue
        runner = max((s for o, s in scores.items() if o != best), default=0.0)
        if runner and top - runner < 0.02:
            ties += 1
        if best:
            shifted += 1
            out[f"{b}.{c}"] = best

    print(f"chapters examined       {len(chapters)}")
    print(f"  needing a shift       {shifted}")
    print(f"  too little overlap    {weak}")
    print(f"  best barely beat 2nd  {ties}   <- least trustworthy")
    print()
    byoff = collections.Counter(out.values())
    print("offsets found:", dict(sorted(byoff.items())))
    print()
    for k, v in sorted(out.items())[:14]:
        print(f"   {k:12} {v:+d}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    DEST.write_text(json.dumps({
        "_note": "KJV chapter -> the offset to add to a KJV verse number to "
                 "reach MACULA's. Derived by content alignment, not by rule: "
                 "the two traditions move CHAPTER BOUNDARIES, not just "
                 "superscriptions, so no constant from verse counts works.",
        "offsets": out,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(out)} chapters)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
