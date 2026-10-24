"""Where the text summarises itself, so the theme list is not imported.

2026-09-15, correcting the approach mid-build: let Paul, Jesus, Hebrews and John
say what those themes are first, then go back looking for the evidence.

`ontology/major-themes.json` had just been written from a theologians' list --
creedal, defensible, and **not derived from this corpus**. The objection is the
same one that has governed everything good in this project: the register should
be evidence before it is a target. On the typology pattern a few hours
earlier: the link is described somewhere by Paul or perhaps Hebrews, and need
not be made up.

And the summaries are MARKED, which makes them harvestable rather than chosen:

    ἀνακεφαλαιόω   "summed up in this word"      Rom 13:9, Eph 1:10
    κεφάλαιον      "the main point is this"      Heb 8:1
    πιστὸς ὁ λόγος "this is a faithful saying"   5x in the Pastorals
    κρεμάννυμι     "on these two hang ALL"       Matt 22:40
    μυστήριον      "the mystery now revealed"    Eph 3, Col 1, Rom 16
    θρησκεία       "pure religion is THIS"       Jas 1:27
    τέλος + νόμος  "Christ is the end of the law" Rom 10:4, 1 Tim 1:5

Every one of these is the author stopping to say *here is the whole of it*.
That is a different object from a theme a model detected, and a better
foundation for a register than anything a list can supply.

## The method, which is now established

`tools/declaredtypes.py` measured it the same day: the New Testament's own
typology vocabulary -- the strongest signal available anywhere in this project
-- returned 30 verses of which **12 were typology and 18 were the same words in
another sense.** 40% precision from ground truth.

So a marker harvest is a NET. The rule: stay true to the word and leverage the
stamps, but never stop with them without verifying.
Every candidate here is read before it enters the register, and the rejects are
kept with their reasons.

## What this cannot reach

The Old Testament has the same move -- Mic 6:8 "what does the LORD require of
you", Eccl 12:13 "the conclusion of the matter", Deut 10:12 -- but it marks it
with ordinary words rather than a technical vocabulary, so no lemma catches it.
Those come in as a named candidate list, flagged as such, because a hand list
that admits it is one is honest and a lemma set that silently misses them is
not.

    python tools/declaredthemes.py              # the harvest, unverified
    python tools/declaredthemes.py --ot         # the named OT candidates
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import sys

# Prints Greek. See tools/declaredtypes.py.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools"))

# Single lemmas that flag a summary. Each is rare enough to read every hit.
SOLO = {
    "ἀνακεφαλαιόω": "sums up",
    "κεφάλαιον": "the main point",
    "θρησκεία": "religion is this",
    "κρεμάννυμι": "everything hangs on",
}

# Summaries marked by a PAIR of lemmas in one verse. `τέλος` alone is 40+
# ordinary uses of "end"; `τέλος` with `νόμος` is Romans 10:4.
PAIRS = {
    ("πιστός", "λόγος"): "a faithful saying",
    ("τέλος", "νόμος"): "the end / goal of the law",
    ("πληρόω", "νόμος"): "the fulfilment of the law",
    ("ὅλος", "νόμος"): "the whole law",
    ("μέγας", "ἐντολή"): "the greatest commandment",
    ("πρῶτος", "παραδίδωμι"): "of first importance",
}

# `μυστήριον` is 28x and genuinely mixed -- some are "the mystery of lawlessness"
# and "I tell you a mystery" rather than a summary of the whole. Kept separate
# so its lower yield does not hide inside the others' numbers.
WATCH = {"μυστήριον": "the mystery now disclosed"}

# Old Testament summaries, named rather than harvested. See the docstring: the
# OT marks this move with ordinary vocabulary and no lemma set will find it.
OT_CANDIDATES = {
    "Deut.6.4": "Hear, O Israel -- the Shema, which Jesus then quotes as first",
    "Deut.10.12": "what does the LORD your God require of you",
    "Eccl.12.13": "the conclusion of the matter, when all has been heard",
    "Mic.6.8": "He has shown you what is good, and what the LORD requires",
    "Ps.15.1": "who may dwell on your holy hill -- the answer is a list",
    "Isa.1.16": "cease to do evil, learn to do good -- the demand condensed",
    "Prov.1.7": "the fear of the LORD is the beginning of knowledge",
    "Prov.9.10": "the fear of the LORD is the beginning of wisdom",
    "Hab.2.4": "the righteous shall live by his faith -- cited 3x in the NT",
    "Lev.19.18": "love your neighbour as yourself -- cited as the whole law",
}

BOOK = {"Mat": "Matt", "Mrk": "Mark", "Luk": "Luke", "Jhn": "John",
        "Act": "Acts", "1Co": "1Cor", "2Co": "2Cor", "Php": "Phil",
        "1Th": "1Thess", "2Th": "2Thess", "1Ti": "1Tim", "2Ti": "2Tim",
        "1Pe": "1Pet", "2Pe": "2Pet", "1Jn": "1John", "2Jn": "2John",
        "3Jn": "3John", "Jas": "Jas", "Tit": "Titus", "Rev": "Rev"}


def harvest(watch=False):
    """-> {ref: [why, ...]} every verse that marks itself as a summary."""
    want = dict(SOLO)
    if watch:
        want.update(WATCH)
    hits = collections.defaultdict(list)
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt", encoding="utf-8"):
        d = json.loads(line)
        ref = d.get("ref")
        if not ref:
            continue
        lem = {w.get("l") for w in d["words"] if w.get("l")}
        for l, why in want.items():
            if l in lem:
                hits[ref].append(why)
        for (a, b), why in PAIRS.items():
            if a in lem and b in lem:
                hits[ref].append(why)
    return hits


def bsbtext(bsb, ref):
    b, c, v = ref.split(".")
    return bsb.get((BOOK.get(b, b), int(c), int(v)), "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--watch", action="store_true",
                    help="include μυστήριον, which is mixed")
    ap.add_argument("--ot", action="store_true",
                    help="the named OT candidates instead")
    a = ap.parse_args()

    from bsbconvert import verses
    bsb = verses("verses.bsb.jsonl")

    if a.ot:
        print(f"{len(OT_CANDIDATES)} named OT summary candidates "
              f"(hand-listed -- no lemma set reaches these)\n")
        for ref in sorted(OT_CANDIDATES, key=lambda r: r.split(".")[0]):
            print(f"  {ref:<12} {OT_CANDIDATES[ref]}")
            print(f"      {bsbtext(bsb, ref)[:110]}")
        return 0

    hits = harvest(a.watch)
    bywhy = collections.Counter(w for ws in hits.values() for w in ws)
    print(f"{len(hits)} verses mark themselves as a summary "
          f"-- UNVERIFIED harvest\n")
    for w, n in bywhy.most_common():
        print(f"  {n:>3}  {w}")
    print()
    for ref in sorted(hits, key=lambda r: (r.split(".")[0],
                                           *(int(x) for x in r.split(".")[1:]))):
        print(f"  {ref:<12} {'; '.join(sorted(set(hits[ref])))}")
        print(f"      {bsbtext(bsb, ref)[:112]}")
    print("\n  NOT a register yet. declaredtypes.py scored 40% on a stronger\n"
          "  signal than this one; every line above is read before it counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
