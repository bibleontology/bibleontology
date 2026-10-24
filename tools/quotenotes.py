"""Old Testament quotations, as the Berean editors marked them.

2026-09-18, after the derived methods missed every quotation in the
temptation narrative: the BSB references could be used for direct quotes; not
ideal, but defensible. And, correcting a conflation immediately after: John 1:1
is not a quote, and it only makes sense to use the references for the quotes,
as the BSB is conservative.

## Two different fields, two different claims

The Berean USFM carries both, and merging them would launder one into the
other:

- `\\r` -- **parallel passages**. 2,026 of them, already harvested to
  `out/xrefs.jsonl.gz`. Matthew 4:1 points to Mark 1 and Luke 4, the synoptic
  parallels. John 1:1 points to Genesis 1:1, which is a statement that the two
  passages belong together and **not** a claim that one quotes the other.
- `\\f ... \\ft <reference>` -- **quotation sources**, which is what this reads.
  Matthew 4:4 to Deuteronomy 8:3, 4:7 to Deuteronomy 6:16, 4:10 to Deuteronomy
  6:13.

It was predicted that the temptation would have three Torah backlinks before
anything was run, and these are they.

## Why this is inherited evidence and is labelled so

An editor marked these for readers. They are not derived here and nothing tunes
toward them, exactly as `out/xrefs.jsonl.gz` is held. The card must say so:
a reader who cannot tell an editor's citation from a computed one has no way to
weigh either.

Their virtue is the reason to use them. Quotation is the one relation where a
conservative human judgement beats anything lexical, because a quotation can
restate its source in different words -- Matthew 4:10 has λατρεύω where the
Septuagint has δουλεύω -- and because the LXX column in MACULA stores INFLECTED
FORMS against the New Testament's LEMMAS, so `αρτον` and `αρτος` never met and
"bread" dropped out of Matthew 4:4 entirely.

## Scope

Quotation is not allusion. John 1:1 echoes Genesis 1:1 and quotes nothing, and
that link has to come from `tools/bridge.py`, which finds it at rank 1 of 1,703
on its own evidence. This file is deliberately narrow.

## Measured

**2026-10-03: 362 -> 592 notes, none lost** (85 more quotations, 145 "points
to"). The book table had no Galatians, Corinthians, Ephesians, Peter ... so
every note naming them was dropped; a reference with an aside ("Psalms 8:2
(see also LXX)", "Exodus 20:13; Deuteronomy 5:17") was not read as one; and
"See X, Y, and Z" notes were not read at all -- now kept as kind "points to",
since some are quotations (Gal 3:8 -> Gen 12:3) and some only refer (Mark
1:44 -> Lev 14). The figures below are the first harvest's.

**362 quotations, 359 of them pointing from the New Testament back into the
Old.** Romans quotes most (73), then Matthew (68) and Hebrews (51); the Psalms
are quoted most (85), then Isaiah (70) and Deuteronomy (59).

Reading only the New Testament end gave 185 and lost the rest, because the
Berean editors note a quotation at BOTH ends and often embed it in a longer
note -- "Or a living soul; cited in 1 Corinthians 15:45".

The test, predicted before anything ran, and corroborated from both
directions:

    Mat 4:4  -> Deu 8:3     and Deu 8:3  says "Cited in Matthew 4:4"
    Mat 4:7  -> Deu 6:16    and Deu 6:16 says "Cited in Matthew 4:7"
    Mat 4:10 -> Deu 6:13    and Deu 6:13 says "Cited in Matthew 4:10"
    Mat 4:6  -> Psa 91:11-12                    (Satan quoting)

For contrast, the derived methods found NONE of these, and the reason is worth
keeping: MACULA's LXX column stores INFLECTED FORMS against the New Testament's
LEMMAS, so Deuteronomy 8:3's `αρτον, αρτου, αρτους, αρτων` never met Matthew's
`αρτος` and **bread dropped out of Matthew 4:4 entirely**. The words that did
match were the ones whose LXX form happens to be nominative singular.

    python tools/quotenotes.py            # counts, and Matthew 4
    python tools/quotenotes.py --write
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
SRC = ROOT / "data" / "raw" / "usfm" / "engbsb"

# \f + \fr 4:4 \ft Deuteronomy 8:3\f*
NOTE = re.compile(r"\\f\s*\+\s*\\fr\s*([0-9]+):([0-9]+)\s*\\ft\s*(.+?)\\f\*",
                  re.S)
IDLINE = re.compile(r"\\id\s+(\w+)")

# A quotation note is a bare reference: "Deuteronomy 8:3", "Psalms 91:11-12".
# Anything with prose in it is a translator's note about wording, not a source.
CITE = re.compile(
    r"^([1-3]?\s*[A-Z][a-z]+)\s+([0-9]+):([0-9]+)"
    r"(?:\s*[-\u2013]\s*(?:([0-9]+):)?([0-9]+))?\s*$")

BOOKS = {
    "Genesis": "Gen", "Exodus": "Exo", "Leviticus": "Lev", "Numbers": "Num",
    "Deuteronomy": "Deu", "Joshua": "Jos", "Judges": "Jdg", "Ruth": "Rut",
    "1 Samuel": "1Sa", "2 Samuel": "2Sa", "1 Kings": "1Ki", "2 Kings": "2Ki",
    "1 Chronicles": "1Ch", "2 Chronicles": "2Ch", "Ezra": "Ezr",
    "Nehemiah": "Neh", "Esther": "Est", "Job": "Job", "Psalm": "Psa",
    "Psalms": "Psa", "Proverbs": "Pro", "Ecclesiastes": "Ecc",
    "Song": "Sng", "Isaiah": "Isa", "Jeremiah": "Jer",
    "Lamentations": "Lam", "Ezekiel": "Ezk", "Daniel": "Dan", "Hosea": "Hos",
    "Joel": "Jol", "Amos": "Amo", "Obadiah": "Oba", "Jonah": "Jon",
    "Micah": "Mic", "Nahum": "Nam", "Habakkuk": "Hab", "Zephaniah": "Zep",
    "Haggai": "Hag", "Zechariah": "Zec", "Malachi": "Mal",
    "Matthew": "Mat", "Mark": "Mrk", "Luke": "Luk", "John": "Jhn",
    "Acts": "Act", "Romans": "Rom", "Hebrews": "Heb", "James": "Jas",
    "Jude": "Jud", "Revelation": "Rev",
    # THE LETTERS WERE MISSING. Until 2026-10-03 this table had Romans and
    # Hebrews and none of the others, so every note naming Galatians, the
    # Corinthian letters, Peter ... was dropped from either end: Lev 18:5's
    # "Cited in Romans 10:5 and Galatians 3:12" kept Romans only (the
    # evaluation's Gal 3:12 -> Lev 18:5, missing)
    "1 Corinthians": "1Co", "2 Corinthians": "2Co", "Galatians": "Gal",
    "Ephesians": "Eph", "Philippians": "Php", "Colossians": "Col",
    "1 Thessalonians": "1Th", "2 Thessalonians": "2Th", "1 Timothy": "1Ti",
    "2 Timothy": "2Ti", "Titus": "Tit", "Philemon": "Phm", "1 Peter": "1Pe",
    "2 Peter": "2Pe", "1 John": "1Jn", "2 John": "2Jn", "3 John": "3Jn",
}

USFM_TO_REF = {
    "GEN": "Gen", "EXO": "Exo", "LEV": "Lev", "NUM": "Num", "DEU": "Deu",
    "JOS": "Jos", "JDG": "Jdg", "RUT": "Rut", "1SA": "1Sa", "2SA": "2Sa",
    "1KI": "1Ki", "2KI": "2Ki", "1CH": "1Ch", "2CH": "2Ch", "EZR": "Ezr",
    "NEH": "Neh", "EST": "Est", "JOB": "Job", "PSA": "Psa", "PRO": "Pro",
    "ECC": "Ecc", "SNG": "Sng", "ISA": "Isa", "JER": "Jer", "LAM": "Lam",
    "EZK": "Ezk", "DAN": "Dan", "HOS": "Hos", "JOL": "Jol", "AMO": "Amo",
    "OBA": "Oba", "JON": "Jon", "MIC": "Mic", "NAM": "Nam", "HAB": "Hab",
    "ZEP": "Zep", "HAG": "Hag", "ZEC": "Zec", "MAL": "Mal", "MAT": "Mat",
    "MRK": "Mrk", "LUK": "Luk", "JHN": "Jhn", "ACT": "Act", "ROM": "Rom",
    "1CO": "1Co", "2CO": "2Co", "GAL": "Gal", "EPH": "Eph", "PHP": "Php",
    "COL": "Col", "1TH": "1Th", "2TH": "2Th", "1TI": "1Ti", "2TI": "2Ti",
    "TIT": "Tit", "PHM": "Phm", "HEB": "Heb", "JAS": "Jas", "1PE": "1Pe",
    "2PE": "2Pe", "1JN": "1Jn", "2JN": "2Jn", "3JN": "3Jn", "JUD": "Jud",
    "REV": "Rev",
}


def parse_cite(text: str):
    """-> (book, chapter, verse, end_verse) or None if this is not a citation.

    Returns None for translator's notes about wording, which share the footnote
    field. Only a bare reference counts, because anything else is a different
    kind of claim and letting it through would inflate the count with prose.
    """
    m = CITE.match(text.strip().rstrip("."))
    if not m:
        return None
    name = re.sub(r"\s+", " ", m.group(1)).strip()
    bk = BOOKS.get(name)
    if not bk:
        return None
    c, v = int(m.group(2)), int(m.group(3))
    end = int(m.group(5)) if m.group(5) else None
    return bk, c, v, end


# "Cited in Hebrews 4:4" -- the SAME relation recorded from the other end. The
# Berean editors mark a quotation on the Old Testament verse as well as on the
# New, and reading only the New Testament end dropped 260 footnotes, including
# every case where the note is embedded in a longer one ("Or a living soul;
# cited in 1 Corinthians 15:45").
CITEDIN = re.compile(r"[Cc]ited in\s+(.+?)(?:\.\s|\.$|;|$)")
# ", and" too: "See Genesis 12:3, Genesis 18:18, and Genesis 22:18" (Gal 3:8)
# left "and Genesis 22:18" as a piece that is not a reference
AND_SPLIT = re.compile(r",\s*(?:and\s+)?|\s+and\s+")


def parse_cited_in(text: str) -> list[tuple]:
    """-> [(book, chapter, verse, end)] for a 'cited in X' note.

    Handles "Cited in Matthew 19:4 and Mark 10:6" and comma-separated lists.
    """
    m = CITEDIN.search(text)
    if not m:
        return []
    out = []
    for piece in AND_SPLIT.split(m.group(1)):
        got = parse_cite(piece.strip())
        if got:
            out.append(got)
    return out


ASIDE = re.compile(r"\s*\([^)]*\)\s*$")


def parse_leading(text: str) -> list[tuple]:
    """The references a note STARTS with, before any prose: "Psalms 8:2 (see
    also LXX)" and "Exodus 20:13; Deuteronomy 5:17" are quotation sources as
    surely as a bare reference -- 83 such notes were dropped -- and the
    "; see also Ezekiel 20:11" after Lev 18:5 is the editors' further pointer,
    not a source. Stops at the first piece that is not a reference."""
    out = []
    for piece in text.strip().rstrip(".").split(";"):
        got = parse_cite(ASIDE.sub("", piece).strip())
        if not got:
            break
        out.append(got)
    return out


def parse_see(text: str) -> list[tuple]:
    """A "See X, Y and Z" note: the editors POINT to passages. Some are
    quotations (Gal 3:8's "all nations will be blessed through you", Gen
    12:3; Mark 14:62, Ps 110:1 and Dan 7:13), some only refer (Mark 1:44,
    "See Leviticus 14:1-32", the leper's offering), so these are kept as their
    own kind, "points to", and never shown as "quotes". Only a note that is
    nothing but references after "See"."""
    t = text.strip().rstrip(".")
    if not t.startswith("See "):
        return []
    pieces = [p.strip() for p in AND_SPLIT.split(t[4:].split(";")[0]) if p.strip()]
    got = [parse_cite(p) for p in pieces]
    return got if got and all(got) else []


def harvest() -> list[dict]:
    rows = []
    for f in sorted(SRC.glob("*.usfm")):
        txt = f.read_text(encoding="utf-8", errors="replace")
        m = IDLINE.search(txt)
        if not m:
            continue
        bk = USFM_TO_REF.get(m.group(1).upper())
        if not bk:
            continue
        for mm in NOTE.finditer(txt):
            c, v, body = mm.group(1), mm.group(2), mm.group(3)
            clean = re.sub(r"\s+", " ", re.sub(r"\\\w+\*?", "", body)).strip()
            here = f"{bk}.{c}.{v}"
            cites = parse_leading(clean)
            if cites:
                for ob, oc, ov, oend in cites:
                    rows.append({"from": here,
                                 "to": f"{ob}.{oc}.{ov}",
                                 "to_end": f"{ob}.{oc}.{oend}" if oend else None,
                                 "source": clean})
                continue
            see = parse_see(clean)
            if see:
                for ob, oc, ov, oend in see:
                    rows.append({"from": here, "to": f"{ob}.{oc}.{ov}",
                                 "to_end": f"{ob}.{oc}.{oend}" if oend else None,
                                 "source": clean, "kind": "points to"})
                continue
            # The same relation recorded from the other end. Normalised to
            # point the same way, so the QUOTING verse is always `from`.
            for ob, oc, ov, oend in parse_cited_in(clean):
                rows.append({"from": f"{ob}.{oc}.{ov}",
                             "to": here,
                             "to_end": None,
                             "source": clean})
    # A quotation can be noted at both ends; keep each pair once.
    seen = set()
    uniq = []
    for r in rows:
        k = (r["from"], r["to"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")
    rows = harvest()
    print(f"{len(rows):,} quotation notes\n")

    byb = collections.Counter(r["from"].split(".")[0] for r in rows)
    tgt = collections.Counter(r["to"].split(".")[0] for r in rows)
    print("most quoting books:      most quoted books:")
    qb = byb.most_common(8)
    qt = tgt.most_common(8)
    for i in range(max(len(qb), len(qt))):
        left = f"  {qb[i][0]:<5}{qb[i][1]:>5}" if i < len(qb) else " " * 12
        right = f"  {qt[i][0]:<5}{qt[i][1]:>5}" if i < len(qt) else ""
        print(f"{left}          {right}")

    print("\nDoug's test -- Matthew 4:1-11:")
    for r in rows:
        b, c, v = r["from"].split(".")
        if b == "Mat" and c == "4" and int(v) <= 11:
            print(f"   {r['from']:<10} -> {r['to']:<10} {r['source']}")

    cross = sum(1 for r in rows
                if r["to"].split(".")[0] not in
                {"Mat", "Mrk", "Luk", "Jhn", "Act", "Rom", "1Co", "2Co",
                 "Gal", "Eph", "Php", "Col", "1Th", "2Th", "1Ti", "2Ti",
                 "Tit", "Phm", "Heb", "Jas", "1Pe", "2Pe", "1Jn", "2Jn",
                 "3Jn", "Jud", "Rev"})
    print(f"\n{cross:,} of {len(rows):,} point from the New Testament back "
          f"into the Old")

    if not a.write:
        print("\nnothing written -- pass --write")
        return 0
    p = OUT / "quotenotes.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_source": "Berean Standard Bible USFM, ebible.org, Public Domain. "
                       "Its footnote citations (\\f ... \\ft), which mark the "
                       "source of a QUOTATION.",
            "_note": "An editor's citation, made for readers and independent "
                     "of anything computed here. INHERITED, not derived, and "
                     "held as a benchmark -- nothing tunes toward it. Distinct "
                     "from out/xrefs.jsonl.gz, which is the \\r "
                     "parallel-passage field and a weaker claim: John 1:1 has "
                     "a parallel note to Genesis 1:1 and quotes nothing. See "
                     "tools/quotenotes.py."}) + "\n")
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n  -> {p.relative_to(ROOT)}  {len(rows):,} citations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
