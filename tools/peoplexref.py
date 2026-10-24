"""People are an index, not a pattern.

2026-09-09: people are their own category; no pattern is needed, only a clear
cross reference.

This corrects a measurement made an hour earlier. Having found that Psalm 103:8
quotes Exodus 34:6, I asked whether a **shared proper noun** made such a link
less likely to be coincidental, and measured it as a bonus on top of lexical
overlap:

    links sharing a proper noun     13,127   mean IDF 16.9
    links sharing none              18,470   mean IDF 15.4

A 10% difference, so the answer looked like "barely". **That was the wrong
question.** A person's name is not weak evidence of a pattern; it is an exact
reference that needs no pattern at all. "Moses" in Psalm 103:7 points at every
verse naming Moses, the way an index entry does. Scoring it as one more feature
in a weighted sum both understates it and mixes two different kinds of claim.

So people come out of `tools/allusions.py`'s vocabulary and live here instead,
as their own edge type.

## What a link here does and does not assert

It asserts **the same name**, not the same person. The corpus holds many men
called Zechariah, and separating them is the distinct and much harder problem
`tools/namemap.py` exists for. A row here is an invitation to check, which is
what a concordance has always been.

## Sources

Proper nouns come from MACULA (CC BY 4.0). Whether a given Strong's number
*names a person* rather than a place comes from STEPBible's Brief Lexicon,
which is CC BY -- checked in the file's own name, not assumed. It supplies a
classification ("this word names a person") and never an identification ("this
is which person"), which is the weaker and safer of the two.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAC = ROOT / "data" / "raw" / "macula"
STEP = ROOT / "data" / "raw" / "stepbible"
DEST = ROOT / "out" / "people-xref.jsonl.gz"

REF = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)")
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


def _key(s, greek=None):
    """H1234 / G1234 kept apart. MACULA's Hebrew files carry bare numbers, so
    the language is taken from the file when the string does not say."""
    s = str(s).strip()
    m = re.match(r"^([HG])?0*(\d+)", s)
    if not m:
        return ""
    pre = m.group(1)
    if not pre:
        pre = "G" if greek else "H"
    return f"{pre}{int(m.group(2))}"


def person_strongs():
    """Strong's numbers the lexicon classes as naming a person."""
    out = set()
    for f in sorted(STEP.glob("TBES*")):
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                c = line.rstrip("\n").split("\t")
                if len(c) > 5 and re.match(r"^[HG]\d{4}", c[0].strip()):
                    if re.search(r"N-[MF]-P$", c[5].strip()):
                        # KEEP THE H/G PREFIX. Stripping it collides the two
                        # numbering systems: H3478 is Israel and G3478 is
                        # Nazareth, and the first run merged them into one
                        # "person" with 2,243 occurrences named Nazareth.
                        # tools/people.py normalises the same way and has the
                        # same defect.
                        out.add(_key(c[0].strip()))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--passage", default="Psa.103")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    persons = person_strongs()
    print(f"strong numbers classed as a person: {len(persons)}")

    byverse = collections.defaultdict(set)
    byname = collections.defaultdict(set)
    name_of = {}
    files = sorted(MAC.rglob("*.xml"))
    for i, f in enumerate(files):
        if i % 250 == 0:
            print(f"  {i}/{len(files)} ...", flush=True)
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for w in root.iter("w"):
            t = (w.get("type") or "").lower()
            c = (w.get("class") or "").lower()
            if not (t == "proper" or c == "name"
                    or (w.get("morph") or "").startswith("Np")):
                continue
            raw = w.get("strongnumberx") or w.get("strong") or ""
            num = _key(raw, greek=("greek" in str(f).lower()))
            if num not in persons:
                continue
            m = REF.match(w.get("ref") or "")
            if not m or not BOOK.get(m.group(1)):
                continue
            ref = f"{BOOK[m.group(1)]}.{int(m.group(2))}.{int(m.group(3))}"
            byverse[ref].add(num)
            byname[num].add(ref)
            nm = re.sub("’s$", "", (w.get("english") or w.get("gloss") or "")
                        .strip())
            if nm and num not in name_of:
                name_of[num] = nm

    print(f"\nverses naming a person: {len(byverse)}")
    print(f"distinct persons named:  {len(byname)}")
    big = sorted(byname.items(), key=lambda kv: -len(kv[1]))[:8]
    print("  most-referenced:",
          {name_of.get(k, k): len(v) for k, v in big})

    print(f"\n{a.passage} -- people named, and what they index to")
    bk, ch = a.passage.split(".")[0], a.passage.split(".")[1]
    for ref in sorted((r for r in byverse if r.startswith(f"{bk}.{ch}.")),
                      key=lambda r: int(r.split(".")[2])):
        for num in sorted(byverse[ref]):
            others = sorted(byname[num] - {ref})
            print(f"  {ref:<12} {name_of.get(num, num):<10} "
                  f"{len(others)} other verses  e.g. {others[:4]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_source": "MACULA (CC BY 4.0) for proper nouns; STEPBible Brief "
                       "Lexicon (CC BY) for whether a Strong's number names a "
                       "person rather than a place.",
            "_note": "People as an index, not a pattern (Doug, 2026-09-09). A "
                     "link asserts THE SAME NAME, not the same person -- the "
                     "corpus holds many men called Zechariah, and separating "
                     "them is tools/namemap.py's problem. Deliberately kept "
                     "out of tools/allusions.py, where a name would be scored "
                     "as one weak feature among many.",
        }, ensure_ascii=False) + "\n")
        for ref in sorted(byverse):
            fh.write(json.dumps({
                "ref": ref,
                "people": [{"strong": n, "name": name_of.get(n, n),
                            "occurrences": len(byname[n])}
                           for n in sorted(byverse[ref])],
            }, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(byverse)} verses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
