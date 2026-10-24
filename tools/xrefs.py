"""Editors' cross-references, as a benchmark our patterns never saw.

2026-09-10: pull all the cross references from the versions downloaded and
build a benchmark; there should be shared patterns in all instances.

That is a good benchmark precisely because **the editors did not consult us**.
A parallel-passage note is one publisher's judgment that two passages belong
together, made for readers and printed in the margin, and it is entirely
independent of anything in `out/`. If our pattern stamps mean something, two
passages an editor links should share a stamp more often than two passages
picked at random.

## What is available, and from where

    BSB    1,324  \\r parallel-passage lines   "(John 1:1-5; Hebrews 11:1-3)"
    WEB      680  inline \\x notes
    WEB-u    726  inline \\x notes
    KJV        0
    ASV        0

BSB's are **section-level**: a heading with a note under it, linking whole
passages. WEB's are **verse-level** footnotes. They answer slightly different
questions and are kept apart rather than pooled.

## The honest limits, stated before any number is produced

**A cross-reference is not a claim of shared structure.** An editor links
Genesis 1 to John 1 because both concern creation and the Word -- a thematic
tie, not a structural one. Our stamps describe shape: pair, chain, collection.
There is no reason in principle why thematically linked passages must share a
shape, and if they do not, that is evidence about what stamps capture rather
than proof they are worthless.

**So the test is directional.** A lift above chance says stamps carry something
an editor also saw. A lift at chance says stamps and editorial linking are about
different things -- which is worth knowing and is not a failure.

**And the sample is not neutral.** BSB places these notes mostly in the gospels
and the Pentateuch, so any result is weighted toward narrative.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
USFM = ROOT / "data" / "raw" / "usfm"
DEST = ROOT / "out" / "xrefs.jsonl.gz"

RLINE = re.compile(r"^\\r\s+(.+)$", re.M)
CHAP = re.compile(r"^\\c\s+(\d+)")
VERSE = re.compile(r"^\\v\s+(\d+)")
FNAME = re.compile(r"^\d*-?([A-Z0-9]{3})")

BOOK = {
    "GEN": "Gen", "EXO": "Exo", "LEV": "Lev", "NUM": "Num", "DEU": "Deu",
    "JOS": "Jos", "JDG": "Jdg", "RUT": "Rut", "1SA": "1Sa", "2SA": "2Sa",
    "1KI": "1Ki", "2KI": "2Ki", "1CH": "1Ch", "2CH": "2Ch", "EZR": "Ezr",
    "NEH": "Neh", "EST": "Est", "JOB": "Job", "PSA": "Psa", "PRO": "Pro",
    "ECC": "Ecc", "SNG": "Sng", "ISA": "Isa", "JER": "Jer", "LAM": "Lam",
    "EZK": "Ezk", "DAN": "Dan", "HOS": "Hos", "JOL": "Jol", "AMO": "Amo",
    "OBA": "Oba", "JON": "Jon", "MIC": "Mic", "NAM": "Nam", "HAB": "Hab",
    "ZEP": "Zep", "HAG": "Hag", "ZEC": "Zec", "MAL": "Mal",
    "MAT": "Mat", "MRK": "Mrk", "LUK": "Luk", "JHN": "Jhn", "ACT": "Act",
    "ROM": "Rom", "1CO": "1Co", "2CO": "2Co", "GAL": "Gal", "EPH": "Eph",
    "PHP": "Php", "COL": "Col", "1TH": "1Th", "2TH": "2Th", "1TI": "1Ti",
    "2TI": "2Ti", "TIT": "Tit", "PHM": "Phm", "HEB": "Heb", "JAS": "Jas",
    "1PE": "1Pe", "2PE": "2Pe", "1JN": "1Jn", "2JN": "2Jn", "3JN": "3Jn",
    "JUD": "Jud", "REV": "Rev",
}

# Spelled-out names as an editor writes them in a margin note.
NAMES = {
    "genesis": "Gen", "exodus": "Exo", "leviticus": "Lev", "numbers": "Num",
    "deuteronomy": "Deu", "joshua": "Jos", "judges": "Jdg", "ruth": "Rut",
    "1 samuel": "1Sa", "2 samuel": "2Sa", "1 kings": "1Ki", "2 kings": "2Ki",
    "1 chronicles": "1Ch", "2 chronicles": "2Ch", "ezra": "Ezr",
    "nehemiah": "Neh", "esther": "Est", "job": "Job", "psalm": "Psa",
    "psalms": "Psa", "proverbs": "Pro", "ecclesiastes": "Ecc",
    "song of solomon": "Sng", "songs": "Sng", "isaiah": "Isa",
    "jeremiah": "Jer", "lamentations": "Lam", "ezekiel": "Ezk",
    "daniel": "Dan", "hosea": "Hos", "joel": "Jol", "amos": "Amo",
    "obadiah": "Oba", "jonah": "Jon", "micah": "Mic", "nahum": "Nam",
    "habakkuk": "Hab", "zephaniah": "Zep", "haggai": "Hag",
    "zechariah": "Zec", "malachi": "Mal", "matthew": "Mat", "mark": "Mrk",
    "luke": "Luk", "john": "Jhn", "acts": "Act", "romans": "Rom",
    "1 corinthians": "1Co", "2 corinthians": "2Co", "galatians": "Gal",
    "ephesians": "Eph", "philippians": "Php", "colossians": "Col",
    "1 thessalonians": "1Th", "2 thessalonians": "2Th", "1 timothy": "1Ti",
    "2 timothy": "2Ti", "titus": "Tit", "philemon": "Phm", "hebrews": "Heb",
    "james": "Jas", "1 peter": "1Pe", "2 peter": "2Pe", "1 john": "1Jn",
    "2 john": "2Jn", "3 john": "3Jn", "jude": "Jud", "revelation": "Rev",
}
CITE = re.compile(
    r"([1-3]?\s?[A-Z][a-z]+(?:\s+of\s+[A-Z][a-z]+)?)\s+(\d+):(\d+)"
    r"(?:\s*[–—-]\s*(?:(\d+):)?(\d+))?")


def parse_cite(s):
    """'John 1:1-5; Hebrews 11:1-3' -> [('Jhn',1,1,5), ('Heb',11,1,3)]"""
    out = []
    for m in CITE.finditer(s):
        raw = re.sub(r"\s+", " ", m.group(1)).strip().lower()
        bk = NAMES.get(raw)
        if not bk:
            continue
        c = int(m.group(2))
        v1 = int(m.group(3))
        v2 = int(m.group(5)) if m.group(5) else v1
        c2 = int(m.group(4)) if m.group(4) else c
        out.append((bk, c, v1, c2, v2))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    rows = []
    unparsed = collections.Counter()
    d = USFM / "engbsb"
    for f in sorted(d.glob("*.usfm")):
        m = FNAME.match(f.name)
        home = BOOK.get(m.group(1)) if m else None
        if not home:
            continue
        ch, verse = 0, 0
        pending = None
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            c = CHAP.match(line)
            if c:
                ch, verse = int(c.group(1)), 0
                continue
            v = VERSE.match(line)
            if v:
                verse = int(v.group(1))
                if pending:
                    for (bk, c1, v1, c2, v2) in pending:
                        rows.append({
                            "from": f"{home}.{ch}.{verse}",
                            "to": f"{bk}.{c1}.{v1}",
                            "to_end": f"{bk}.{c2}.{v2}",
                            "by": "engbsb", "kind": "parallel",
                        })
                    pending = None
                continue
            r = RLINE.match(line)
            if r:
                got = parse_cite(r.group(1))
                if got:
                    pending = got
                else:
                    unparsed[r.group(1)[:40]] += 1

    print(f"BSB parallel-passage links parsed: {len(rows):,}")
    print(f"  notes that would not parse: {sum(unparsed.values())}")
    for s, n in unparsed.most_common(4):
        print(f"     {n:>3}  {s}")

    pairs = {(r["from"].split(".")[0], r["to"].split(".")[0]) for r in rows}
    print(f"\n  distinct book-to-book links: {len(pairs)}")
    src = collections.Counter(r["from"].split(".")[0] for r in rows)
    print(f"  most-linked source books: {dict(src.most_common(6))}")
    tgt = collections.Counter(r["to"].split(".")[0] for r in rows)
    print(f"  most-linked target books: {dict(tgt.most_common(6))}")

    cross = sum(1 for r in rows
                if r["from"].split(".")[0] != r["to"].split(".")[0])
    print(f"\n  links that cross a book: {cross:,} "
          f"({100*cross/max(len(rows),1):.0f}%)")

    print("\n  sample:")
    for r in rows[:6]:
        print(f"     {r['from']:<12} -> {r['to']}..{r['to_end'].split('.')[-1]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": "Berean Standard Bible USFM, ebible.org, Public Domain. "
                       "Its \\\\r parallel-passage notes.",
            "_note": "An editor's judgment that two passages belong together, "
                     "made for readers and independent of anything computed "
                     "here. Held as a BENCHMARK: nothing tunes toward it. A "
                     "cross-reference is a THEMATIC tie and our stamps describe "
                     "SHAPE, so agreement is informative and disagreement is "
                     "evidence about what stamps capture, not proof of failure.",
        }, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(rows)} links)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
