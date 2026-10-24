"""Turn downloaded translation files into the project's raw JSON shape.

Until now the repository recorded nothing about where its texts came from.
`data/raw/KJV.json` and `ASV.json` were simply present, and the README called
them "the downloaded public-domain KJV" without saying downloaded from where.
That is a gap worth closing before three more arrive: a corpus whose
provenance is unrecorded cannot be re-derived, and every citation in the graph
rests on it.

## The sources

    KJV  King James Version, 1769           public domain (Crown patent in UK)
    ASV  American Standard Version, 1901    public domain
    YLT  Young's Literal Translation, 1898  ebible.org/Scriptures/engylt_vpl.zip
    WEB  World English Bible                ebible.org/Scriptures/engwebp_vpl.zip
    BSB  Berean Standard Bible              bereanbible.com/bsb.txt

The BSB file states its own terms in its second line: "This text of God's Word
has been dedicated to the public domain." The two eBible texts are listed
Redistributable with copyright "public domain" in that site's own
translations.csv. The KJV remains under perpetual Crown patent **in the United
Kingdom**, which matters for a public site and not for local use.

## Everything must land on the KJV verse scheme

One text is the reference and the rest are aligned to it, with an **empty
string** wherever a translation has no text at a KJV verse id. That convention
already existed -- the ASV file carries sixteen of them -- and it is what makes
"this verse is not in your Bible" representable at all.

Three quirks were found by reporting before writing, which is the whole
argument for doing it in that order:

1. **eBible uses an older USFM code set.** SOL, EZE, JOE, NAH, MAR, JOH, PHI,
   JAM, 1JO, 2JO, 3JO where the current standard says SNG, EZK, JOL, NAM, MRK,
   JHN, PHP, JAS, 1JN, 2JN, 3JN. Eleven books, and unmapped they arrive as
   silently empty rather than as an error.

2. **Book names differ by source.** The existing map came from a source using
   Roman numerals and plural Psalms; the BSB writes "1 Samuel" and "Psalm".
   Normalised rather than aliased one by one, so the next source needs no
   change.

3. **The World English Bible numbers the Romans doxology differently.** It
   places it at Rom 14:24-26 where the KJV has 16:25-27 -- the same text, and
   the only genuine versification difference among the three. Remapped, and
   worth stating plainly because this is the failure mode that would have been
   invisible: without the remap, three verses of Romans would sit under the
   wrong ids and every citation touching them would quietly be wrong.

## What is left absent, and why that is data

After alignment the omissions are real and they sort the five texts by
manuscript family rather than by age of English:

    YLT   0 verses absent   Textus Receptus, like the KJV
    WEB   4 absent
    ASV  16 absent
    BSB  16 absent          the critical-text set exactly

That is the `absent_in` overlay, derived rather than asserted, and it is why
the graph never needs a per-version copy of a relation: two relations in the
whole corpus rest on a verse that any of these translations lacks.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

from .books import BOOK_TITLE, SOURCE_NAME_TO_ID
from .corpus import get_corpus
from .paths import RAW

# Where each text can be fetched. Downloading is deliberately not automatic:
# it is a network fetch into a repository, and it should be a decision.
SOURCES = {
    "YLT": ("https://ebible.org/Scriptures/engylt_vpl.zip",
            "engylt_vpl.txt", "vpl"),
    "WEB": ("https://ebible.org/Scriptures/engwebp_vpl.zip",
            "engwebp_vpl.txt", "vpl"),
    "BSB": ("https://bereanbible.com/bsb.txt", None, "tsv"),
}

TITLES = {
    "YLT": "YLT: Young's Literal Translation (1898)",
    "WEB": "WEB: World English Bible",
    "BSB": "BSB: Berean Standard Bible",
}

_USFM = """GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST
JOB PSA PRO ECC SNG ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP
HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI
TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV""".split()
BY_USFM = dict(zip(_USFM, BOOK_TITLE))
BY_USFM.update({
    "SOL": "Song", "EZE": "Ezek", "JOE": "Joel", "NAH": "Nah",
    "MAR": "Mark", "JOH": "John", "PHI": "Phil", "JAM": "Jas",
    "1JO": "1John", "2JO": "2John", "3JO": "3John",
})

# WEB verse id -> KJV verse id. The Romans doxology and nothing else.
REMAP = {
    "WEB": {"Rom 14:24": "Rom 16:25",
            "Rom 14:25": "Rom 16:26",
            "Rom 14:26": "Rom 16:27"},
}

_ROMAN = {"1": "I", "2": "II", "3": "III"}
_VPL = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)\s+(.*)$")
_TSV = re.compile(r"^(.+?)\s+(\d+):(\d+)\t(.*)$")
_ID_TO_SOURCE = {v: k for k, v in SOURCE_NAME_TO_ID.items()}


def book_id(name: str) -> str | None:
    """A source's book name to this project's id, tolerating conventions."""
    name = " ".join(name.split())
    if name in SOURCE_NAME_TO_ID:
        return SOURCE_NAME_TO_ID[name]
    m = re.match(r"^([123])\s+(.*)$", name)
    if m:
        alt = f"{_ROMAN[m.group(1)]} {m.group(2)}"
        if alt in SOURCE_NAME_TO_ID:
            return SOURCE_NAME_TO_ID[alt]
    for alias, real in (("Psalm", "Psalms"),
                        ("Song of Songs", "Song of Solomon"),
                        ("Revelation", "Revelation of John")):
        if name == alias:
            return SOURCE_NAME_TO_ID.get(real)
    return None


def _read(path: Path, member: str | None, fmt: str) -> dict[str, str]:
    if path.suffix == ".zip":
        text = zipfile.ZipFile(path).read(member).decode("utf-8-sig")
    else:
        text = path.read_text(encoding="utf-8-sig")

    out: dict[str, str] = {}
    unknown: set[str] = set()
    for line in text.splitlines():
        line = line.rstrip()
        if fmt == "vpl":
            m = _VPL.match(line.strip())
            if not m:
                continue
            code, c, v, body = m.groups()
            bid = BY_USFM.get(code)
            if bid is None:
                unknown.add(code)
                continue
        else:
            m = _TSV.match(line)
            if not m:
                continue
            name, c, v, body = m.groups()
            bid = book_id(name)
            if bid is None:
                unknown.add(name.strip())
                continue
        out[f"{bid} {int(c)}:{int(v)}"] = " ".join(body.split())
    if unknown:
        raise SystemExit(f"unmapped books in {path.name}: {sorted(unknown)}")
    return out


def convert(name: str, downloaded: Path) -> tuple[int, list[str]]:
    """Write data/raw/<NAME>.json aligned to the KJV. Returns (kept, absent)."""
    url, member, fmt = SOURCES[name]
    verses = _read(downloaded, member, fmt)

    for src, dst in REMAP.get(name, {}).items():
        if src in verses:
            verses[dst] = verses.pop(src)

    kjv = [str(v.id) for v in get_corpus().iter_verses()]
    stray = sorted(set(verses) - set(kjv))
    if stray:
        raise SystemExit(
            f"{name} has {len(stray)} verse ids outside the KJV scheme, "
            f"first few {stray[:8]}. Add them to REMAP or investigate before "
            f"writing -- an unaligned id silently mis-cites every claim on it.")

    books: dict[str, dict[int, list[dict]]] = {}
    absent: list[str] = []
    for vid in kjv:
        bid, cv = vid.rsplit(" ", 1)
        c, v = (int(x) for x in cv.split(":"))
        text = verses.get(vid, "")
        if not text:
            absent.append(vid)
        books.setdefault(bid, {}).setdefault(c, []).append(
            {"verse": v, "text": text})

    payload = {
        "translation": TITLES[name],
        "source": url,
        "books": [
            {"name": _ID_TO_SOURCE[bid],
             "chapters": [{"chapter": c, "verses": vs}
                          for c, vs in sorted(chapters.items())]}
            for bid, chapters in books.items()
        ],
    }
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return len(kjv) - len(absent), absent


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print("usage: python -m bibleont.acquire <NAME> <downloaded-file>\n")
        print("Sources (download these yourself; they are network fetches "
              "into a repository):")
        for k, (url, _, _) in SOURCES.items():
            print(f"  {k:5}{url}")
        return 2
    name, path = argv[0].upper(), Path(argv[1])
    if name not in SOURCES:
        print(f"unknown translation {name}; known: {sorted(SOURCES)}")
        return 2
    kept, absent = convert(name, path)
    print(f"{name}: {kept} verses on the KJV scheme, {len(absent)} absent")
    if absent:
        print("  " + ", ".join(absent))
    print(f"  wrote {RAW / f'{name}.json'}")
    print("  now run: python -m bibleont.build_corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
