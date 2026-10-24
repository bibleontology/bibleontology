"""Kinship, typed — the bond the text states and the graph never recorded.

2026-09-11: close the deterministic gap first. Place was the larger
half; this is the other.

The legacy graph holds **1,265 kinship relations** — `father_of` 775,
`mother_of` 129, `sibling_of` 94, `spouse_of` 87, and a tail. The computed
floor already SEES both parties in 66% of the `father_of` cases, the highest
of any relation type in the corpus. What it has never done is **type the
bond**: it knows David and Solomon share a verse, not that one fathered the
other.

That is not a meaning problem. The text says it outright.

## Two constructions, and the tree marks both

**Construct chain.** A kinship noun in the CONSTRUCT state between two proper
nouns. lowfat tags the state, so this is read and not guessed:

    Jos 1:1    יְהֹושֻׁעַ   בֵּן(construct)   נוּן      Joshua son of Nun
    Gen 25:19  יִצְחָק      בֵּן(construct)   אַבְרָהָם  Isaac son of Abraham

**The verb.** יָלַד, "fathered", with its arguments already in the frame layer:

    Gen 25:19  אַבְרָהָם  יָלַד  אֵת יִצְחָק     Abraham fathered Isaac

The same verse carries both, which is a useful check: they must agree.

## The ambiguity, and why the obvious handling of it was wrong

בְּנֵי יִשְׂרָאֵל is "the Israelites". The first version therefore dropped every
plural, to avoid reading it as somebody's parentage.

**Measured, that cost 641 genuine ancestries** — sons of Merari, of Kohath, of
Korah — out of 1,781 plural-plus-name cases, and the Chronicles genealogies are
written almost entirely in them. Coverage of the legacy kinship relations was
29%.

Then a discriminator was looked for and **there is none**. The lexicon carries a
gentilic pointer (Edomite → Edom) which marks names used of a group, but
Merari, Kohath and Korah all have gentilics too.

The reason no discriminator exists is that the two are the same claim:
**"sons of Israel" means the descendants of Jacob, and "sons of Merari" means
the descendants of Merari.** Only the scale differs, and the scale is our
judgment rather than the text's. So the plural is kept and typed for what it
actually says — `descendants_of`, not `son_of`. Separating them would be
harmonising a distinction the corpus does not draw.

## What a row asserts

The bond between **two names**, at a verse. Not between two resolved people —
the corpus holds several men called Nathan, and telling them apart is
`tools/namemap.py`'s problem, unchanged by this. Same claim the people and
place layers make, for the same reason.
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
DEST = ROOT / "out" / "kinship.jsonl.gz"

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


def nfc(s):
    return ud.normalize("NFC", s or "")


# lemma -> (relation the FIRST name has to the SECOND). Direction matters and
# is the thing easiest to get backwards: in "Joshua son of Nun", Joshua is the
# CHILD. The relation named here reads first-to-second.
KIN = {nfc(k): v for k, v in {
    "בֵּן": "son_of",
    "בַּת": "daughter_of",
    "אָב": "father_of",
    "אֵם": "mother_of",
    "אָח": "brother_of",
    "אָחוֹת": "sister_of",
    "אִשָּׁה": "wife_of",
}.items()}
GREEK_KIN = {nfc(k): v for k, v in {
    "υἱός": "son_of", "θυγάτηρ": "daughter_of", "πατήρ": "father_of",
    "μήτηρ": "mother_of", "ἀδελφός": "brother_of", "ἀδελφή": "sister_of",
    "γυνή": "wife_of",
}.items()}
BEGET = {nfc("יָלַד"), nfc("γεννάω")}
INVERSE = {"son_of": "father_of", "daughter_of": "father_of",
           "father_of": "son_of", "mother_of": "son_of",
           "brother_of": "brother_of", "sister_of": "sister_of",
           "wife_of": "husband_of"}


# A plural kinship term states DESCENT from the named ancestor rather than
# immediate parentage. Both are true of the text; only one is specific.
PLURAL_REL = {"son_of": "descendants_of", "daughter_of": "descendants_of",
              "brother_of": "kin_of", "sister_of": "kin_of",
              "father_of": "ancestors_of", "mother_of": "ancestors_of",
              "wife_of": "wives_of"}


def rel_kind(rel):
    return "descent" if rel.startswith("descend") else "direct"


def is_proper(w):
    return ((w.get("type") or "").lower() == "proper"
            or (w.get("class") or "").lower() == "name"
            or (w.get("morph") or "").startswith("Np"))


def name_of(w):
    return re.sub("’s$", "", (w.get("english") or w.get("gloss") or "").strip())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    rows = []
    tally = collections.Counter()
    files = sorted(MAC.rglob("*.xml"))
    for i, f in enumerate(files):
        if i % 250 == 0:
            print(f"  {i}/{len(files)} ...", flush=True)
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        greek = "greek" in str(f).lower()
        ws = [w for w in root.iter("w")]
        for j, w in enumerate(ws):
            lem = nfc(w.get("lemma") or "")
            table = GREEK_KIN if greek else KIN
            if lem not in table:
                continue
            # PLURAL IS NOT A DIFFERENT THING, IT IS A DIFFERENT SCALE.
            #
            # The first version dropped every plural, to avoid reading "sons
            # of Israel" as somebody's parentage. That cost 641 genuine
            # ancestries -- sons of Merari, of Kohath, of Korah -- out of
            # 1,781 plural-plus-name cases, and Chronicles is written almost
            # entirely in them.
            #
            # Then a discriminator was looked for and there is none. The
            # lexicon's gentilic pointer (Edomite -> Edom) marks names used
            # of a group, but Merari, Kohath and Korah all have gentilics
            # too. Structurally the two are identical, because they ARE the
            # same claim: "sons of Israel" means the descendants of Jacob,
            # and so does "sons of Merari" of Merari. Only the scale differs,
            # and scale is our judgment, not the text's.
            #
            # So the plural is kept and typed for what it says.
            plural = (w.get("number") or "").lower() == "plural"
            if plural and rel_kind(table[lem]) != "descent":
                tally["plural -> descendants_of"] += 1
            # Hebrew marks the "of" with the construct state. Without it,
            # בֵּן is just "a son" and binds nothing.
            if not greek and (w.get("state") or "").lower() != "construct":
                tally["not construct, dropped"] += 1
                continue
            m = REF.match(w.get("ref") or "")
            if not m or not BOOK.get(m.group(1)):
                continue
            ref = f"{BOOK[m.group(1)]}.{int(m.group(2))}.{int(m.group(3))}"
            # the SECOND name: the nearest proper noun after the kinship term
            second = None
            for k in range(j + 1, min(j + 4, len(ws))):
                if REF.match(ws[k].get("ref") or "") and \
                        (ws[k].get("ref") or "").split("!")[0] != \
                        (w.get("ref") or "").split("!")[0]:
                    break
                if is_proper(ws[k]):
                    second = ws[k]
                    break
            # the FIRST name: the nearest proper noun before it
            first = None
            for k in range(j - 1, max(j - 4, -1), -1):
                if (ws[k].get("ref") or "").split("!")[0] != \
                        (w.get("ref") or "").split("!")[0]:
                    break
                if is_proper(ws[k]):
                    first = ws[k]
                    break
            if second is None:
                tally["no name after the term"] += 1
                continue
            rel = table[lem]
            if plural:
                rel = PLURAL_REL.get(rel, rel)
            if plural and first is None:
                # THE GENEALOGY LIST. "The sons of Mahli: Eleazar and Kish"
                # is בְּנֵי מַחְלִי אֶלְעָזָר וְקִישׁ -- the ancestor comes
                # first and THE CHILDREN FOLLOW HIM. Recording only the
                # ancestor throws away the entire content of Chronicles.
                #
                # Walk forward over names joined by nothing but a conjunction,
                # and stop at the first word that is neither. That keeps
                # "Eleazar and Kish" and refuses "the sons of Israel came to
                # Egypt", where a verb intervenes.
                kids, k = [], ws.index(second) + 1
                while k < len(ws) and len(kids) < 12:
                    x = ws[k]
                    if (x.get("ref") or "").split("!")[0] != \
                            (w.get("ref") or "").split("!")[0]:
                        break
                    cls = (x.get("class") or "").lower()
                    if is_proper(x):
                        kids.append(x)
                    elif cls not in ("cj", "conj", "om", "art"):
                        break
                    k += 1
                for kid in kids:
                    rows.append({"ref": ref, "a": name_of(kid),
                                 "rel": "descendant_of",
                                 "b": name_of(second), "by": "list"})
                tally["descendant_of (from a list)"] += len(kids)
                if not kids:
                    rows.append({"ref": ref, "a": None, "rel": rel,
                                 "b": name_of(second), "by": "construct"})
                    tally[rel] += 1
                continue
            if first is None:
                tally["no name before -- bond half-known"] += 1
                continue
            rows.append({"ref": ref, "a": name_of(first), "rel": rel,
                         "b": name_of(second), "by": "construct"})
            tally[rel] += 1

    # the verbal construction, straight out of the frame layer
    p = ROOT / "out" / "frames.jsonl.gz"
    if p.exists():
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                d = json.loads(line)
                if any(k.startswith("_") for k in d):
                    continue
                if nfc(d.get("lemma") or "") not in BEGET:
                    continue
                ag = (d.get("agent") or []) + \
                     ((d.get("named") or {}).get("agent") or [])
                pa = (d.get("patient") or []) + \
                     ((d.get("named") or {}).get("patient") or [])
                if not ag or not pa:
                    tally["beget verb, a slot empty"] += 1
                    continue
                # NEGATION MATTERS HERE. "she bore him no children" must not
                # become a parentage. polarity was added this morning.
                if d.get("polarity") == "negative":
                    tally["beget verb, NEGATED -- dropped"] += 1
                    continue
                rows.append({"ref": d["ref"], "a": ag[0], "rel": "parent_of",
                             "b": pa[0], "by": "verb"})
                tally["parent_of"] += 1

    print(f"\nkinship statements: {len(rows):,}")
    for k, v in tally.most_common():
        print(f"  {k:<34}{v:>7,}")

    print("\nCHECK -- verses whose bond is not in doubt:")
    want = {"Jos.1.1": ("Joshua", "Nun"), "Gen.25.19": ("Isaac", "Abraham")}
    by = collections.defaultdict(list)
    for r in rows:
        by[r["ref"]].append(r)
    for ref, (x, y) in want.items():
        got = by.get(ref, [])
        ok = any(x.lower() in (r["a"] or "").lower()
                 and y.lower() in (r["b"] or "").lower() for r in got)
        shown = "; ".join(f"{r['a']} {r['rel']} {r['b']}" for r in got[:3])
        print(f"  {'ok ' if ok else 'MISS'} {ref:<12}{shown[:60]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({
            **provenance.stamp(__file__, inputs=["data/raw/macula/*/*.xml",
                                                 "out/frames.jsonl.gz"]),
            "_source": "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., "
                       "CC BY 4.0 -- construct state, number and proper-noun "
                       "marking are all read from it.",
            "_note": "A bond between two NAMES at a verse, not between two "
                     "resolved people. Singular kinship terms only: plurals "
                     "name a people ('sons of Israel'), not a parentage. "
                     "Negated beget-verbs are dropped -- 'she bore him no "
                     "children' is not a parentage.",
        }, ensure_ascii=False) + "\n")
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(rows):,} statements)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
