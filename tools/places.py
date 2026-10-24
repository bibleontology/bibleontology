"""Places, the dimension the graph has been missing entirely.

2026-09-11, on the legacy audit: close the deterministic gap first.

That audit found 5,229 legacy relations the computed floor does not reproduce,
and **half of them are not a meaning problem at all** — they are deterministic
work nobody had done. The largest single piece is place:

    located_in 402   traveled_to 343   dwelt_at 204   ruled_from 109
    buried_at   65   based_at    48    died_at  40    born_at   16
    reigned_over 60  founded     19    kept_at  19    stationed_at 9
                                                      cast_into  10
                                                      ---------------
                                                            1,334

`tools/peoplexref.py` built the same thing for people a week ago and this was
never done for places. The graph knows who; it has never known where.

## Method, and it is the people method exactly

Proper nouns come from MACULA (CC BY 4.0). Whether a Strong's number names a
**location** comes from STEPBible's Brief Lexicon (CC BY), which documents its
own scheme in its own header:

> Extra for Names is **L=Location**, **P=Person**, LG/PG=Gentilic, T=Title

1,239 Strong's numbers carry a location tag (`N:N--L`, `N:N-M-L`, `N:N-F-L`,
`N:A--L`), against 3,474 tagged as persons.

## The distinction the source itself insists on, and we keep

> Location is only used for places **not named after people** — eg: Israel =
> `N:N-M-P` (for the Person, and nation); Jerusalem = `N:N--L`

So **Israel is not a place here**, and neither is Judah nor Dan. The lexicon
classes them as persons because the nation is named for the man, and it routes
the tribal area through Gentilic instead. That will look like a gap to anyone
expecting "Israel" among the places. It is the source's distinction, stated
where it can be read, and overriding it would be substituting our judgment for
a lexicographer's while still citing them — see `docs/PRINCIPLES.md` on reading
the corpus without harmonising.

Gentilics (`N:N--LG`, 158) are held separately for the same reason: "Jerusalemite"
names a people by their place and is neither cleanly.

## What a row asserts

**The same name, not the same place.** There are two Bethlehems and several
Gilgals. This is an index entry — an invitation to check — exactly as the
people layer is, and for the same reason.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import unicodedata as ud
import xml.etree.ElementTree as ET

import provenance

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAC = ROOT / "data" / "raw" / "macula"
STEP = ROOT / "data" / "raw" / "stepbible"
DEST = ROOT / "out" / "places.jsonl.gz"

REF = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)")
BOOK = {
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
NUM = re.compile(r"^([HG])?0*(\d+)")

# A location tag, and a gentilic tag, kept apart. Anchored at the end so
# "N:N--LG" (gentilic) never matches the location pattern.
IS_PLACE = re.compile(r"N-{1,2}[MF]?-?L$")
IS_GENTILIC = re.compile(r"-LG$|-PG$")


def _key(raw, greek=False):
    m = NUM.match(str(raw).strip())
    if not m:
        return None
    pre = m.group(1) or ("G" if greek else "H")
    # KEEP THE H/G PREFIX. H3478 is Israel and G3478 is Nazareth; stripping it
    # merged them once already, in tools/people.py and tools/peoplexref.py.
    return f"{pre}{int(m.group(2))}"


def skel(s):
    """Consonantal skeleton: drop vowel points and cantillation, normalise.

    The lexicon writes Bethlehem בֵּית לֶ֫חֶם with a metheg MACULA does not
    use. The consonants are what both agree on.
    """
    return re.sub(r"[֑-ׇ]", "",
                  ud.normalize("NFC", s or "")).strip()


def tagged():
    """(place strongs, gentilic strongs, lemma -> strong for places).

    The lemma index exists because **1,577 proper-noun tokens in MACULA carry
    no Strong's number at all** (4.1%), and they are not a random 4%: they are
    the COMPOUND names, written as two words and numbered as neither.

        Bethel 125   Beth- 82   Bethlehem 67   Beer- 34   Kiriath- 19

    A Strong's-only lookup drops every one of them silently. Ruth 1 came back
    with Moab and no Bethlehem, in the chapter that turns on going to and
    returning from Bethlehem, which is how this was caught.

    `tools/peoplexref.py` has the same defect and loses Obed-Edom and
    Abednego the same way. Not fixed here; recorded so it is fixed knowingly.
    """
    place, gent, bylemma = set(), set(), {}
    for f in sorted(STEP.glob("TBES*")):
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                c = line.rstrip("\n").split("\t")
                if len(c) > 5 and re.match(r"^[HG]\d{4}", c[0].strip()):
                    tag = c[5].strip()
                    k = _key(c[0].strip())
                    if not k:
                        continue
                    if IS_GENTILIC.search(tag):
                        gent.add(k)
                    elif IS_PLACE.search(tag):
                        place.add(k)
                        lem = skel(c[3]) if len(c) > 3 else ""
                        # Only multi-word lemmas: a single-word lemma always
                        # carries its number in MACULA, and indexing those
                        # would let a common noun collide with a place.
                        if lem and " " in lem:
                            bylemma.setdefault(lem, k)
    return place, gent, bylemma


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--passage", default="Rut.1")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    places, gentilics, bylemma = tagged()
    recovered = 0
    print(f"strong numbers classed as a LOCATION: {len(places):,}")
    print(f"           ... and as a GENTILIC:     {len(gentilics):,}"
          f"   (held separately, not merged)")
    print(f"compound lemmas indexed for the no-number case: {len(bylemma):,}")

    byverse = collections.defaultdict(set)
    byplace = collections.defaultdict(set)
    name_of = {}

    def label(n):
        c = name_of.get(n)
        return c.most_common(1)[0][0] if c else n

    files = sorted(MAC.rglob("*.xml"))
    for i, f in enumerate(files):
        if i % 250 == 0:
            print(f"  {i}/{len(files)} ...", flush=True)
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        greek = "greek" in str(f).lower()
        for w in root.iter("w"):
            t = (w.get("type") or "").lower()
            c = (w.get("class") or "").lower()
            if not (t == "proper" or c == "name"
                    or (w.get("morph") or "").startswith("Np")):
                continue
            num = _key(w.get("strongnumberx") or w.get("strong") or "",
                       greek=greek)
            if num is None:
                # A compound name, numbered by the lexicon and not by MACULA.
                num = bylemma.get(skel(w.get("lemma") or ""))
                if num:
                    recovered += 1
            if num not in places:
                continue
            m = REF.match(w.get("ref") or "")
            if not m or not BOOK.get(m.group(1)):
                continue
            ref = f"{BOOK[m.group(1)]}.{int(m.group(2))}.{int(m.group(3))}"
            byverse[ref].add(num)
            byplace[num].add(ref)
            # MOST COMMON label, not the first seen. A compound name is two
            # <w> elements and they carry different english values: of the 67
            # tokens whose lemma is bet-lechem, 67 read "Bethlehem" and the
            # rest read "of", "at", "[is]". First-encounter picked Gen 35:19's
            # "[is]" and labelled the town accordingly.
            nm = re.sub("’s$", "", (w.get("english") or w.get("gloss") or "")
                        .strip())
            if nm:
                name_of.setdefault(num, collections.Counter())[nm] += 1

    print(f"\nverses naming a place: {len(byverse):,}")
    print(f"distinct places named: {len(byplace):,}")
    big = sorted(byplace.items(), key=lambda kv: -len(kv[1]))[:10]
    print("  most-referenced:")
    for k, v in big:
        print(f"    {label(k):<16}{len(v):>6} verses")

    print(f"\n{a.passage} -- places named, and what they index to")
    bk, ch = a.passage.split(".")[0], a.passage.split(".")[1]
    for ref in sorted((r for r in byverse if r.startswith(f"{bk}.{ch}.")),
                      key=lambda r: int(r.split(".")[2]))[:10]:
        for num in sorted(byverse[ref]):
            others = sorted(byplace[num] - {ref})
            print(f"  {ref:<12} {label(num):<14} "
                  f"{len(others):>5} other verses  e.g. {others[:3]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({
            **provenance.stamp(__file__,
                               inputs=["data/raw/macula/*/*.xml",
                                       "data/raw/stepbible/TBES*"]),
            "_source": "MACULA (CC BY 4.0) for proper nouns; STEPBible Brief "
                       "Lexicon (CC BY) for whether a Strong's number names a "
                       "location. Both checked in the files' own names.",
            "_note": "Places as an index, not a pattern -- the same shape as "
                     "people-xref. A row asserts THE SAME NAME, not the same "
                     "place: there are two Bethlehems. Israel, Judah and Dan "
                     "are NOT here: the lexicon classes them as persons "
                     "because the nation is named for the man, and that is "
                     "its distinction to make, not ours. Gentilics are held "
                     "out for the same reason.",
        }, ensure_ascii=False) + "\n")
        for ref in sorted(byverse):
            fh.write(json.dumps({
                "ref": ref,
                "places": [{"strong": n, "name": label(n),
                            "occurrences": len(byplace[n])}
                           for n in sorted(byverse[ref])],
            }, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(byverse):,} verses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
