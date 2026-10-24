"""The unit below the verse, from the Masoretic accents we already hold.

2026-09-09, after the WEB paragraph benchmark turned out to say nothing
about Psalm 103: poetry is where the discipline really matters, with a lot going
on and very rich; then stay with Psalms, and see whether the parts can be
labelled to the point where some rules work.

The question was also whether published scholarship could help, and it can -- but
**the thing that scholarship is built on turned out to be inside our own
licensed data already.** Every literary-structural treatment of Hebrew poetry
works from the *colon*, and the colon boundary is marked by the Masoretic
cantillation accents, which MACULA preserves in each word's `unicode`
attribute. 186 accent marks in a 400-word sample of Psalm 103, including
ETNAHTA, DEHI and GERESH MUQDAM -- the last two belonging specifically to the
poetic accent system of Psalms, Job and Proverbs.

So no external analysis is needed, and none is used. This is Principle 44
again: the division is *in the source*, so it is read from the source.

## What the accents give, and the control that says what they do NOT give

    Psalm 23     6 verses    100% bicolon
    Proverbs 10 32 verses     97% bicolon
    Psalm 103   22 verses     95% bicolon
    Job 38      41 verses     93% bicolon
    Psalm 119  176 verses     85% bicolon
    ---------------------------------------------------
    Genesis 1   31 verses     90% bicolon   <- PROSE CONTROL, and it FAILS

**The control fails and the claim is narrowed accordingly.** Genesis 1 is prose
and splits into two parts just as readily, because the etnahta is the main
divider of *every* Hebrew verse, not a poetic device. What this module
therefore provides is a **sub-verse syntactic unit across the whole Hebrew
Bible** -- which the project did not have at all. In poetry that unit is the
colon; in prose it is the principal syntactic break. It is not a genre
discriminator and must not be used as one.

## Why it is worth having anyway

It makes structure visible that was previously only readable by hand. A reader took
Psalm 103:11-13 as three stacked images, the first two grand in
their imagery and the third shifting to the personal. Split at the accents:

    v11  | as high as the heavens above the earth | so great is his loyal love
    v12  | as far as east is from west            | so far has he removed them
    v13  | as a father has compassion on children | so the LORD has compassion

Three verses, one shape. That is the parallelism the whole tradition of Hebrew
poetics is about, and it is now derivable rather than asserted.

## The accent hierarchy used

Poetic books (Psalms, Job, Proverbs) use a different accent system from the
other twenty-one. The strongest internal dividers there are **ole-weyored** and
**etnahta**; below them sit **revia mugrash** and **dehi**. `--level top` cuts
only at the first two, which yields the bicolon; `--level second` also cuts at
the weaker pair, which yields finer segments in long verses.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
HEB = ROOT / "data" / "raw" / "macula" / "hebrew"
DEST = ROOT / "out" / "cola.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, Clear Bible, CC BY 4.0"

W = re.compile(r"<w\s([^>]*?)/?>", re.S)
A = re.compile(r'([\w:.-]+)="([^"]*)"', re.S)
REF = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)!(\d+)")

OLE = "֫"              # ole, of ole-weyored: strongest internal divider
ETNAHTA = "֑"
REVIA_MUGRASH = "֙"
DEHI = "֭"
REVIA = "֗"
TOP = {OLE, ETNAHTA}
SECOND = TOP | {REVIA_MUGRASH, DEHI, REVIA}

BOOK = {
    "GEN": "Gen", "EXO": "Exo", "LEV": "Lev", "NUM": "Num", "DEU": "Deu",
    "JOS": "Jos", "JDG": "Jdg", "RUT": "Rut", "1SA": "1Sa", "2SA": "2Sa",
    "1KI": "1Ki", "2KI": "2Ki", "1CH": "1Ch", "2CH": "2Ch", "EZR": "Ezr",
    "NEH": "Neh", "EST": "Est", "JOB": "Job", "PSA": "Psa", "PRO": "Pro",
    "ECC": "Ecc", "SNG": "Sng", "ISA": "Isa", "JER": "Jer", "LAM": "Lam",
    "EZK": "Ezk", "DAN": "Dan", "HOS": "Hos", "JOL": "Jol", "AMO": "Amo",
    "OBA": "Oba", "JON": "Jon", "MIC": "Mic", "NAM": "Nam", "HAB": "Hab",
    "ZEP": "Zep", "HAG": "Hag", "ZEC": "Zec", "MAL": "Mal",
}


def accents(word):
    u = unicodedata.normalize("NFD", word.get("unicode") or "")
    return {c for c in u if "֑" <= c <= "֯"}


def read(path):
    byv = collections.defaultdict(list)
    for m in W.finditer(path.read_text(encoding="utf-8")):
        a = dict(A.findall(m.group(1)))
        r = REF.match(a.get("ref", "") or "")
        if r and BOOK.get(r.group(1)):
            key = (BOOK[r.group(1)], int(r.group(2)), int(r.group(3)))
            byv[key].append((int(r.group(4)), a))
    return {k: [a for _, a in sorted(v, key=lambda t: t[0])]
            for k, v in byv.items()}


def split_cola(words, level):
    cola, cur = [], []
    for a in words:
        cur.append(a)
        if accents(a) & level:
            cola.append(cur)
            cur = []
    if cur:
        cola.append(cur)
    return cola


def gloss(ws):
    return " ".join((a.get("english") or a.get("gloss") or "?").replace(".", " ")
                    for a in ws).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--level", choices=("top", "second"), default="top")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    level = TOP if a.level == "top" else SECOND

    files = sorted(HEB.glob("*.xml"))
    print(f"hebrew files {len(files)}   level={a.level}")
    rows, shape = [], collections.Counter()
    for i, p in enumerate(files):
        if i % 200 == 0:
            print(f"  {i}/{len(files)} ...", flush=True)
        for (bk, ch, v), ws in read(p).items():
            cola = split_cola(ws, level)
            shape[len(cola)] += 1
            rows.append({
                "ref": f"{bk}.{ch}.{v}",
                "n": len(cola),
                "cola": [{"words": len(c), "gloss": gloss(c)} for c in cola],
            })

    tot = sum(shape.values())
    print(f"\nverses segmented {tot}")
    print(f"  cola per verse: {dict(sorted(shape.items())[:6])}")
    print(f"  bicolon share:  {100*shape[2]/tot:.1f}%")

    print("\nBY BOOK -- and note the PROSE books score just as high")
    byb = collections.defaultdict(collections.Counter)
    for r in rows:
        byb[r["ref"].split(".")[0]][r["n"]] += 1
    for bk in ("Psa", "Pro", "Job", "Lam", "Gen", "Lev", "1Ki"):
        c = byb.get(bk)
        if not c:
            continue
        n = sum(c.values())
        print(f"  {bk:<5} verses {n:>5}   bicolon {100*c[2]/n:>5.1f}%")
    print("  -> the etnahta divides EVERY Hebrew verse. This is a sub-verse")
    print("     unit for the whole Bible, NOT a poetry detector.")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": CREDIT,
            "_note": "Sub-verse units from the Masoretic cantillation accents "
                     "preserved in MACULA's unicode attribute. Cut at ole and "
                     "etnahta (level=top). In poetry this is the colon; in "
                     "prose it is the main syntactic break. NOT a genre "
                     "discriminator: Genesis 1 scores 90% two-part, as high as "
                     "the Psalms.",
        }, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(rows)} verses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
