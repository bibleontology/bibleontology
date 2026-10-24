"""Where the text declares its own types, instead of us inferring them.

2026-09-15, on the judgement-and-redemption pattern that must reach from
the Fall to the Cross: the link is described somewhere by Paul or perhaps
Hebrews, and need not be made up.

That changes the footing. `crosslink.py` proposes OT<->NT links
from shared rare stamps, which is a model's reading of both sides. But the New
Testament repeatedly says the link outright, and it has a VOCABULARY for it:

    τύπος        pattern, type          Rom 5:14, 1 Cor 10:6, Rom 6:17
    τυπικῶς      typologically          1 Cor 10:11
    ἀντίτυπος    antitype               Heb 9:24, 1 Pet 3:21
    σκιά         shadow                 Col 2:17, Heb 8:5, Heb 10:1
    ὑπόδειγμα    copy, example          Heb 8:5, Heb 9:23
    ἀλληγορέω    speak allegorically    Gal 4:24
    ὑποτύπωσις   pattern                1 Tim 1:16, 2 Tim 1:13

**Romans 5:14 is the link, stated by Paul**: Adam "is a pattern of the One
to come". Nothing has to be inferred and nothing has to be scored.

This is therefore ground truth rather than a proposal, and the right use of it
is to CHECK the inferred links: where crosslink.py agrees with a declared type
it has earned some trust, and where the text declares a type the stamps cannot
see, that is a measured hole in the vocabulary.

## The marker is a net, not a verdict: 30 found, 12 true

2026-09-15, on method: stay true to the word and leverage the stamps, but never
stop with them without verifying.

This tool is the cheapest possible test of that rule, because the harvest
signal is the strongest one available -- not a stamp, not a similarity score,
but the technical vocabulary itself. **It is still only 40% right.**

    30 verses carry a marker word
    12 assert a typological link
    18 are the same word doing something else

The 18 are not noise from a bad threshold. They are the word's other senses:

    moral example   1Th 1:7, 1Ti 4:12, Php 3:17, Tit 2:7, 1Pe 5:3, Jas 5:10
                    -- "be a τύπος to the believers"
    literal shade   Act 5:15 Peter's shadow, Mrk 4:32 birds in the shade,
                    Mat 4:16 / Luk 1:79 "the shadow of death"
    imprint, form   Jhn 20:25 the nail MARKS, Act 23:25 a letter of this FORM,
                    Rom 6:17 the FORM of teaching, Act 7:43 the IMAGES you made

**The discriminator is what occupies the type slot.** Where the type is a
PERSON being imitated, it is moral example; where it is an EVENT or an
INSTITUTION standing for a later one, it is typology. That is a real
regularity and it is still not applied mechanically here -- thirty verses are
cheap to read, and a rule that is 90% right would put three wrong verses into
something this project calls ground truth.

So `VERIFIED` below is hand-checked, one line of reason each. It is the
smallest honest version of the discipline: harvest wide, verify every one,
publish only what survived, and keep the rejects with their reasons so nobody
re-harvests them next year and believes the 30.

## What is here and what is not

The MARKER and the verse are certain -- they are words in the text. The OT
ANTECEDENT often is not in the same verse: 1 Pet 3:21 says "this water",
pointing back to the flood a verse earlier, and Heb 9:24 says "a man-made
copy" without naming the tabernacle in that clause. Extracting the antecedent
is a reading task, and it is left marked rather than guessed.

    python tools/declaredtypes.py            # all 30, verdict on each
    python tools/declaredtypes.py --rejects  # why the 18 were dropped
    python tools/declaredtypes.py --write    # the 12, to out/
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import sys

# Prints Greek. A cp1252 console raises partway through, after the useful
# output, so it reads as a crash rather than a console limitation.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools"))

# The words with which the text says "this stands for that". `παραβολή` and
# `εἰκών` are deliberately excluded: a parable is a told story rather than a
# claimed correspondence between two passages, and εἰκών is mostly "image" in
# the sense of a coin's face or the image of God, not typology.
MARKERS = {
    "τύπος": "type / pattern",
    "τυπικῶς": "typologically",
    "ἀντίτυπος": "antitype",
    "σκιά": "shadow",
    "ὑπόδειγμα": "copy / example",
    "ἀλληγορέω": "allegorically",
    "ὑποτύπωσις": "pattern",
}
BOOK = {"Mat": "Matt", "Mrk": "Mark", "Luk": "Luke", "Jhn": "John",
        "Act": "Acts", "1Co": "1Cor", "2Co": "2Cor", "Php": "Phil",
        "1Th": "1Thess", "2Th": "2Thess", "1Ti": "1Tim", "2Ti": "2Tim",
        "1Pe": "1Pet", "2Pe": "2Pet"}

# Hand-checked against the BSB text of each verse, 2026-09-15. The antecedent
# is what the verse points BACK to; `null` where the verse names the relation
# without naming the earlier thing in that clause.
VERIFIED = {
    # in the text's words, not a gloss: "the Fall-to-Cross link" said more
    # than the verse (2026-10-03)
    "Rom.5.14": ("Adam", "Adam is 'a pattern of the One to come' -- the text's "
                 "own word, τύπος"),
    "1Co.10.6": ("the wilderness generation",
                 "the events happened as types for us"),
    # REVERSED until 2026-10-03 (C-D21): the Greek calls BAPTISM the
    # ἀντίτυπον, answering to the flood's water -- ὃ ... ἀντίτυπον νῦν σῴζει
    # βάπτισμα. Said in the text's words, a reading of the grammar and no
    # position on baptism
    "1Pe.3.21": ("the flood", "baptism is named the antitype (ἀντίτυπον) of the "
                 "flood's water: 'this water symbolizes the baptism that now saves you'"),
    "Gal.4.24": ("Hagar and Sarah", "named as allegory: the two covenants"),
    "Col.2.17": ("festival, new moon, Sabbath",
                 "a shadow of what was coming; the body is Christ"),
    "Heb.8.5": ("the tabernacle", "a copy and shadow of the heavenly"),
    "Heb.9.23": ("the tabernacle and its vessels", "copies of heavenly things"),
    "Heb.9.24": ("the holy place", "a man-made antitype of the true one"),
    "Heb.10.1": ("the law and its sacrifices",
                 "a shadow of the good things to come"),
    # named in the verse after all, "the pattern he had seen": with None the
    # row was titled "Act.7.44 — —" (C-D21)
    "Act.7.44": ("the pattern Moses had seen", "the tabernacle built to the pattern "
                 "Moses was shown -- the heavenly-original sense, Heb 8:5's source"),
    "Heb.4.11": ("the wilderness generation",
                 "their disobedience is the example not to follow"),
    "2Pe.2.6": ("Sodom and Gomorrah",
                 "made an example of what is coming on the ungodly -- "
                 "judgement typology"),
}

# Kept deliberately. A reject list with reasons is what stops the 30 being
# re-harvested and believed next year.
REJECTS = {
    "Mat.4.16": "literal: the shadow of death, an idiom for darkness",
    "Luk.1.79": "literal: the shadow of death",
    "Mrk.4.32": "literal: birds nest in the shade of the mustard plant",
    "Act.5.15": "literal: Peter's shadow falling on the sick",
    "Jhn.20.25": "sense 'imprint': the nail marks in His hands",
    "Act.7.43": "sense 'image': the idols you made to worship",
    "Act.23.25": "sense 'form': he wrote a letter of this form",
    "Rom.6.17": "sense 'form': the form of teaching entrusted to you",
    "Jhn.13.15": "moral example: do as I have done for you",
    "Php.3.17": "moral example: follow my example",
    "1Th.1.7": "moral example: you became an example to believers",
    "2Th.3.9": "moral example: offering ourselves to imitate",
    "1Ti.1.16": "moral example: Paul as an example to future believers",
    "1Ti.4.12": "moral example: set an example for the believers",
    "2Ti.1.13": "sense 'pattern of teaching': hold to sound doctrine",
    "Tit.2.7": "moral example: show yourself a pattern of good works",
    "Jas.5.10": "moral example: the prophets as a model of patience",
    "1Pe.5.3": "moral example: be examples to the flock",
}


def find():
    """-> [(ref, marker, gloss)] every verse that names a type."""
    out = []
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt", encoding="utf-8"):
        d = json.loads(line)
        r = d.get("ref")
        if not r:
            continue
        for w in d["words"]:
            if w.get("l") in MARKERS:
                out.append((r, w["l"], (w.get("g") or "").strip()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rejects", action="store_true",
                    help="the 18 the marker caught and reading dropped")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    from bsbconvert import verses
    bsb = verses("verses.bsb.jsonl")
    got = find()
    bym = collections.Counter(m for _r, m, _g in got)
    refs = sorted({r for r, _m, _g in got}, key=lambda r: (r.split(".")[0],))
    markers = {r: sorted({m for x, m, _g in got if x == r}) for r in refs}

    print(f"{len(got)} marker words in {len(refs)} verses: "
          + ", ".join(f"{m} {n}" for m, n in bym.most_common()))
    kept = [r for r in refs if r in VERIFIED]
    print(f"{len(kept)} verify as typological, {len(refs) - len(kept)} are the "
          f"same words in another sense "
          f"({100 * len(kept) / max(len(refs), 1):.0f}% precision)\n")

    # Anything neither verified nor rejected is unreviewed, and saying so is
    # the point -- a silent default would let a new marker word in unchecked.
    new = [r for r in refs if r not in VERIFIED and r not in REJECTS]
    if new:
        print(f"  !! {len(new)} UNREVIEWED: {', '.join(new)}\n")

    if a.rejects:
        for r in sorted(REJECTS):
            print(f"  {r:<10} {'/'.join(markers.get(r, ['-'])):<12} "
                  f"{REJECTS[r]}")
        return 0

    for ref in sorted(kept):
        ante, why = VERIFIED[ref]
        b, c, v = ref.split(".")
        txt = bsb.get((BOOK.get(b, b), int(c), int(v)), "")
        print(f"  {ref:<10} {'/'.join(markers[ref])}")
        print(f"      {ante or '(not in this verse)'} -- {why}")
        print(f"      {txt[:110]}")

    if a.write:
        p = OUT / "declared-types.jsonl"
        with p.open("w", encoding="utf-8") as f:
            f.write(json.dumps({
                "_note": "Verses where the NT NAMES a typological link, by the "
                         "word it uses AND by reading. Ground truth for "
                         "cross-testament linking: the text's own claim, not "
                         "an inference. 30 verses carry a marker word; these "
                         "12 survived verification. See tools/declaredtypes.py "
                         "for the 18 rejected and why."}) + "\n")
            for ref in sorted(kept):
                ante, why = VERIFIED[ref]
                b, c, v = ref.split(".")
                f.write(json.dumps({
                    "ref": ref, "markers": markers[ref], "antecedent": ante,
                    "reason": why,
                    "text": bsb.get((BOOK.get(b, b), int(c), int(v)), "")},
                    ensure_ascii=False) + "\n")
        print(f"\n  -> {p.relative_to(ROOT)}  {len(kept)} verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
