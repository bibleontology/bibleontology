"""Metaphor: X IS Y, where a simile would have said X is LIKE Y.

2026-09-11: the question was whether the audit found places where the image_of
work done in the legacy graph was not matched in the new.

It did not, and the audit actively hid it. `tools/legacyaudit.py` mapped
`likened_to` to the comparison layer and `draws_on` to the allusion layer as a
**stated assumption that was never tested**. Tested against the 507 legacy
relations pointing at an `image_*` node:

    a comparison exists in the verse      98  (23%)
    only an allusion link exists         234  (54%)
    the floor is silent entirely         103  (24%)

The 54% was the worst of it: an allusion link is lexical overlap between two
verses and never says *this verse uses X as an image of Y*.

## Why compare.py structurally cannot find these

It requires a particle — כְּ, ὡς, ὥσπερ. **A metaphor has none.** It simply
asserts the identity:

    "The LORD is my shepherd"            Psa 23:1
    "He is my refuge and my fortress"    Psa 91:2
    "Joseph is a fruitful bough"         Gen 49:22
    "Issachar is a strong ass"           Gen 49:14

## What the tree gives, and it is exact

Biblical Hebrew has no present-tense copula, so these are **verbless clauses**,
and lowfat marks them: `<wg class="cl" rule="S-P">` with `role="s"` on the
subject and `role="p"` on the predicate. 9,238 of them. Greek needs εἰμί and
the same roles apply.

What separates a figure from the rest is **what carries the predicate**:

    wg:pp    2,591   "a psalm OF DAVID"    a superscription, not a figure
    wg:np    2,517   "my shepherd"          FIGURE
    w:noun     951   "a tower"              FIGURE
    w:adj      749   "he is good"           attribution, not a figure
    w:adv/pron/num   deictic or quantitative, never a figure

So: a nominal predicate, never a prepositional or adjectival one.

## What this does NOT claim

**That every X-is-Y is figurative.** "The man is a prophet" predicates a real
category; "the LORD is my shepherd" does not. Nothing structural separates
them, and the source offers no semantic domain this project is permitted to
read. So the layer reports the construction and its two terms, and the
`figurative` judgment is left to a reader or an overlay. Measured against the
legacy image set below, so the reader knows what fraction to expect.

## Sources

MACULA (CC BY 4.0) for the tree, the roles and the classes. UBS semantic-domain
fields (sdbh, lexdomain, coredomain, domain, ln) are permission-based and this
module reads none of them — which is exactly why concreteness is not filtered.
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
DEST = ROOT / "out" / "metaphor.jsonl.gz"

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

# A figure's predicate is NOMINAL. Everything else in that slot is a different
# construction wearing the same clause rule.
PRED_OK_WG = {"np"}
PRED_OK_W = {"noun"}
# A pronoun subject is fine ("HE is my refuge"), a pronoun PREDICATE is not
# ("this is it"). A proper-noun predicate is identity, not figure: "I am the
# LORD" declares who, it does not picture anything.
SKIP_PRED_TYPE = {"proper", "demonstrative", "personal", "interrogative"}


def nfc(s):
    return ud.normalize("NFC", s or "")


def norm_ref(raw):
    m = REF.match(str(raw or ""))
    if not m:
        return None
    b = BOOK.get(m.group(1))
    return f"{b}.{int(m.group(2))}.{int(m.group(3))}" if b else None


def words(node):
    return [w for w in node.iter("w")] if node.tag != "w" else [node]


def lemmas(node, kinds=("noun", "adj", "name", "verb", "pron")):
    out = []
    for w in words(node):
        if (w.get("class") or "").lower() in kinds:
            lab = nfc(w.get("lemma") or "")
            if lab and lab not in out:
                out.append(lab)
    return out


def gloss(node):
    out = []
    for w in words(node):
        g = (w.get("english") or w.get("gloss") or "").strip()
        if g:
            out.append(g)
    return " ".join(out)[:70]


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
        for cl in root.iter("wg"):
            if cl.get("class") != "cl":
                continue
            rule = cl.get("rule") or ""
            # P2CL and its kin are a predicate with NO subject role at all.
            # Psa 91:2 -- "I will say of the LORD, He is my refuge and my
            # fortress" -- puts the refuge and fortress in the predicate and
            # leaves the LORD in a preceding prepositional phrase. The image
            # is fully present; the tenor is not in the clause.
            #
            # Recording the vehicle with `tenor: null` is the same choice
            # compare.py makes for a simile whose tenor is outside its verse,
            # and for the same reason: a guessed tenor is a false record of
            # what a passage is about. See the 2026-09-11 proximity failure.
            has_p = any(ch.get("role") == "p" for ch in cl)
            if not (rule.startswith("S-P") or rule.startswith("P-S")
                    or (has_p and "P" in rule)):
                continue
            tally["verbless clauses with a predicate"] += 1
            subj = pred = None
            for ch in cl:
                if ch.get("role") == "s" and subj is None:
                    subj = ch
                elif ch.get("role") == "p" and pred is None:
                    pred = ch
            if pred is None:
                tally["no predicate role"] += 1
                continue
            # NOMINAL PREDICATE ONLY. A pp predicate is a superscription or a
            # location ("a psalm of David", "the ark is in Kiriath"); an adj
            # predicate attributes a quality ("he is good"). Neither pictures.
            kind = (f"{pred.tag}:{pred.get('class') or '-'}"
                    if pred.tag != "w" else f"w:{pred.get('class') or '-'}")
            ok = ((pred.tag == "wg" and pred.get("class") in PRED_OK_WG)
                  or (pred.tag == "w"
                      and (pred.get("class") or "") in PRED_OK_W))
            if not ok:
                tally[f"predicate is {kind} -- not a figure"] += 1
                continue
            # "I am the LORD" is identity, not picture.
            ptypes = {(w.get("type") or "").lower() for w in words(pred)}
            if ptypes & SKIP_PRED_TYPE:
                tally["predicate is a proper noun or deictic"] += 1
                continue
            ref = None
            for w in (words(subj) if subj is not None else []) + words(pred):
                ref = norm_ref(w.get("ref"))
                if ref:
                    break
            if not ref:
                continue
            tenor = lemmas(subj) if subj is not None else []
            vehicle = lemmas(pred)
            if not vehicle:
                tally["no lemma on the predicate"] += 1
                continue
            rows.append({
                "ref": ref, "rule": rule,
                "tenor": tenor[:4] or None, "vehicle": vehicle[:4],
                "reads": (f"{gloss(subj)} = {gloss(pred)}" if subj is not None
                          else f"(subject not in clause) = {gloss(pred)}"),
            })
            tally["with a tenor" if tenor else "vehicle only, tenor absent"] += 1
            tally["METAPHOR CANDIDATES"] += 1

    print(f"\ncandidates: {len(rows):,}")
    for k, v in tally.most_common(12):
        print(f"  {k:<44}{v:>7,}")

    print("\nCHECK -- figures the legacy graph recorded by hand:")
    # Check words are the ENGLISH GLOSS MACULA uses, not the translation's.
    # The first version looked for "bough" and "ass"; MACULA glosses those
    # as "fruitful" and "donkey", so four real hits read as misses.
    want = {"Psa.23.1": "shepherd", "Gen.49.22": "fruitful",
            "Gen.49.14": "donkey", "Psa.91.2": "refuge", "Pro.18.10": "tower"}
    by = collections.defaultdict(list)
    for r in rows:
        by[r["ref"]].append(r)
    for ref, word in want.items():
        got = by.get(ref, [])
        hit = any(word in r["reads"].lower() for r in got)
        shown = "; ".join(r["reads"] for r in got[:2])
        print(f"  {'ok ' if hit else 'MISS'} {ref:<11}{shown[:66]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            **provenance.stamp(__file__, inputs=["data/raw/macula/*/*.xml"]),
            "_source": "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., "
                       "CC BY 4.0 -- clause rule, roles and classes all read "
                       "from it. UBS semantic-domain fields not read.",
            "_note": "The X-IS-Y construction with a NOMINAL predicate, as "
                     "tenor and vehicle. It does NOT claim every row is "
                     "figurative: 'the man is a prophet' predicates a real "
                     "category and nothing structural separates it from 'the "
                     "LORD is my shepherd'. The construction is computed; the "
                     "figurative judgment is left to a reader or an overlay.",
        }, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(rows):,} candidates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
