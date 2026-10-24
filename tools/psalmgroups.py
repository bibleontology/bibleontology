"""The Psalm 103 discipline, applied to every psalm grouped by hand.

2026-09-12: what happens if the discipline used on Psalm 103 is applied to
all the psalms grouped by hand the other day.

## The discipline, as it was derived on Psalm 103

Four steps, in this order, each measured on 2026-09-12:

1. **Anchor units.** Ask MACULA's coreference *"what does this verse lean on?"*
   rather than *"is there a break here?"*. A verse leaning on an earlier verse
   joins its unit; a verse leaning on nothing opens one. On Psalm 103 this put
   9 of 10 units wholly inside one of the four messages read by hand.
2. **Dependent binding.** A verse with no finite verb that opens with a
   preposition governing a participle or infinitive cannot stand alone and
   binds backwards. 86 of 23,213 verses; Psa 103:18 is one.
3. **Boundary rule.** A proper noun as the HEAD of the subject, in a clause with
   a verbal predicate (finite or participle). On Psalm 103 this returned exactly
   [6, 13, 19] -- the three internal message boundaries read by hand, no false
   positives. Corpus-wide it is 1.54x, which is the honest figure.
4. **Compare** against the editors and against the held reading.

## The hand readings are NOT a tuning target

Stated repeatedly and enforced here: nothing in this module was adjusted after
seeing an agreement score, and the rules are the ones already committed for
Psalm 103. Where the discipline disagrees with the hand reading, **the disagreement is the
output** -- it is evidence about what these signals can and cannot see, not a
defect to be tuned away.

## Versification

The hand readings are ENGLISH-versified; MACULA is Hebrew, and most of these
psalms carry a superscription that Hebrew counts as verse 1. The offset is
computed per psalm from the verse counts rather than assumed, and printed, so a
silent misalignment cannot pass for a disagreement.
"""
from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import pathlib
import re
import unicodedata as ud
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
HEB = ROOT / "data/raw/macula/hebrew"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

ENGC = {}
FINITE = {"qatal", "wayyiqtol", "yiqtol", "weqatal", "imperative", "jussive",
          "cohortative", "weyiqtol"}
NONFIN = {"participle", "infinitive construct", "infinitive absolute"}


def nfc(s):
    return ud.normalize("NFC", s or "")


def anchor_verse(tok):
    tok = tok.strip().rstrip(";")
    return int(tok[5:8]) if tok.isdigit() and len(tok) >= 9 else None


def analyse(path):
    """-> dict of per-verse signals for one psalm."""
    root = ET.parse(path).getroot()
    parent = {c: pa for pa in root.iter() for c in pa}
    verses, leans, dep, bound = set(), collections.defaultdict(set), set(), set()

    def vn(w):
        m = re.search(r":(\d+)", w.get("ref") or "")
        return int(m.group(1)) if m else None

    for w in root.iter("w"):
        v = vn(w)
        if v is None:
            continue
        verses.add(v)
        for attr in ("subjref", "participantref"):
            for t in (w.get(attr) or "").split():
                a = anchor_verse(t)
                if a is not None and a < v:
                    leans[v].add(a)

    # dependent verses: no finite verb, opens with a preposition + nonfinite
    for s in root.iter("sentence"):
        ws = list(s.iter("w"))
        if not ws:
            continue
        v = vn(ws[0])
        if v is None:
            continue
        if any(x.get("type") in FINITE for x in ws if x.get("class") == "verb"):
            continue
        if ws[0].get("class") != "prep":
            continue
        if any(x.get("class") == "verb" and x.get("type") in NONFIN for x in ws):
            dep.add(v)

    # boundary rule: proper noun is the subject HEAD, clause has a verbal predicate
    for cl in root.iter("wg"):
        if cl.get("class") != "cl":
            continue
        subj = next((d for d in cl if d.get("role") == "s"), None)
        if subj is None:
            continue
        ws = [subj] if subj.tag == "w" else list(subj.iter("w"))
        if not ws:
            continue
        first = ws[0]
        if not (first.get("type") == "proper" and first.get("class") == "noun"):
            continue
        if not any(x.get("class") == "verb"
                   and (x.get("type") or "").startswith(("participle",))
                   or (x.get("class") == "verb" and x.get("type") in FINITE)
                   for x in cl.iter("w")):
            continue
        v = vn(first)
        if v is not None:
            bound.add(v)
    return {"verses": sorted(verses), "leans": leans, "dep": dep, "bound": bound}


def units(a):
    """Anchor units, CONTIGUOUS. A group is a span, not a set.

    A verse joins the unit in progress when it leans on any verse already in it;
    otherwise it opens a new one. A dependent verse (no finite verb, opening
    preposition) always joins, whatever the pointers say.

    **The first version grouped by anchor id alone**, which let a verse leaning
    on v1 join v1's unit from anywhere in the psalm and produced sets like
    `[1,2,6,8,12,13]`. Psalm 103 hid this because its leaning is local -- every
    pointer there goes back at most five verses. Discovered 2026-09-12 on the
    other ten psalms, and it means the Psalm 103 result was flattered by that
    psalm rather than by the rule.
    """
    out, cur = [], []
    for v in a["verses"]:
        back = {x for x in a["leans"].get(v, ()) if x < v}
        if not cur:
            cur = [v]
            continue
        if v in a["dep"] or (back & set(cur)):
            cur.append(v)
        else:
            out.append(cur)
            cur = [v]
    if cur:
        out.append(cur)
    return out


def english_verse_counts():
    """-> {chapter: n} for Psalms, from the KJV store, to get the real offset."""
    import collections as _c
    out = _c.Counter()
    p = ROOT / "data/bible/verses.jsonl"
    if not p.exists():
        return out
    with open(p, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            # the KJV store uses SBL-style codes: "Ps", not "Psa"
            if d.get("b") in ("Ps", "Psa") and d.get("c"):
                out[int(d["c"])] += 1
    if not out:
        raise SystemExit("english_verse_counts(): read nothing from "
                         "data/bible/verses.jsonl -- refusing to default to an "
                         "offset of 0 and silently misalign every comparison")
    return out


def load_readings():
    out = collections.defaultdict(list)
    p = ROOT / "ontology/readings-held.jsonl"
    with open(p, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                out[d["ref"]].append(d)
    return out


def load_structure():
    out = collections.defaultdict(list)
    with gzip.open(OUT / "structure.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            b, c, v = d["ref"].split(".")
            out[f"{b}.{c}"].append((int(v), d.get("level"), d.get("agree")))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only")
    a = ap.parse_args()

    global ENGC
    ENGC = english_verse_counts()
    readings = load_readings()
    struct = load_structure()
    psalms = sorted({r for r in readings},
                    key=lambda x: int(x.split(".")[1]))
    if a.only:
        psalms = [p for p in psalms if p == a.only]

    tot_h = tot_hit = tot_ed = 0
    for ref in psalms:
        ch = int(ref.split(".")[1])
        path = HEB / f"19-Psa-{ch:03d}-lowfat.xml"
        if not path.exists():
            continue
        an = analyse(path)
        us = units(an)
        heb_max = max(an["verses"])
        # The hand readings are English-versified; infer the offset from counts
        if ch not in ENGC:
            raise SystemExit(f"no English verse count for Psa.{ch}")
        eng_max = ENGC[ch]
        offset = max(0, heb_max - eng_max)
        seams_he = sorted(an["bound"])
        seams_en = [v - offset for v in seams_he if v - offset >= 1]
        ed = sorted({v for v, lvl, ag in struct.get(ref, []) if (ag or 0) >= 2})

        said = [r for r in readings[ref]]
        his_seams = sorted({v for r in said if r["kind"] == "seam"
                            for v in (r.get("verses") or [])})
        his_groups = [tuple(r["verses"]) for r in said
                      if r["kind"] in ("group", "tree") and len(r.get("verses") or []) == 2]

        print(f"\n{'='*72}\n{ref}   Hebrew verses {heb_max}"
              f"   English offset {offset}")
        print(f"  ANCHOR UNITS (English numbering)")
        eng_units = [[v - offset for v in u if v - offset >= 1] for u in us]
        eng_units = [u for u in eng_units if u]
        line = "  ".join("[" + ",".join(str(v) for v in u) + "]" for u in eng_units)
        print(f"    {line}")
        print(f"  BOUNDARY RULE fires at   {seams_en if seams_en else '(none)'}")
        print(f"  EDITORS (agree>=2)       {ed if ed else '(none)'}")
        print(f"  HAND seams               {his_seams if his_seams else '(none)'}")
        if his_groups:
            print(f"  HAND groups              "
                  f"{['-'.join(map(str,g)) for g in his_groups]}")
        # does every hand group sit inside one anchor unit or a run of them?
        ok = bad = 0
        for g in his_groups:
            lo, hi = g
            crossing = [u for u in eng_units
                        if u and u[0] < lo <= u[-1] or (u and u[0] <= hi < u[-1])]
            if crossing:
                bad += 1
            else:
                ok += 1
        if his_groups:
            print(f"  -> his groups respected by anchor units: {ok}/{len(his_groups)}")
            tot_h += len(his_groups); tot_hit += ok
        for r in said:
            if r["kind"] == "note" or r["kind"] == "tree":
                print(f"     note: {r['said'][:96]}")
    if tot_h:
        print(f"\n{'='*72}\nTOTAL: hand-read two-endpoint groups respected by anchor "
              f"units: {tot_hit}/{tot_h} ({100*tot_hit/tot_h:.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
