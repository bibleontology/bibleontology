"""Every event the narrative reports, from the grammar that marks it.

The next step: identify all events. The gap is real and this
session measured it: an event boundary could not be tested because there is no
event layer, and the legacy graph holds **32** `event` entities for the whole
canon. Act-type transitions were tried as a proxy and gave 0.85-1.49 -- nothing.

**But the languages mark their own narrative, and MACULA carries the marking.**

## What counts as an event, and why it is not "a verb"

Hebrew's `morph` encodes the conjugation in its third position, and the
**wayyiqtol** -- the waw-consecutive imperfect -- is the form that carries
narrative forward. `Vqw3ms` is *and he said*; `Vqp3ms` is *he created*, a
perfect, which reports a state of affairs rather than advancing the story.
Genesis 1 has 45 wayyiqtols and they are its spine.

Greek marks the same thing differently: the **aorist indicative** is the
narrative tense, against the imperfect's ongoing action and the present's
discourse.

So an event here is a **finite verb in the narrative form**, with whatever
participants its clause names. That is a grammatical fact, not a reading, which
is the whole point -- interpretation is kept for decision by hand, and this
layer must be able to say *the text reports something happening here* without
saying what kind of thing it was.

## What is deliberately excluded

- **Speech content.** A wayyiqtol inside a quotation is an event in the story
  someone is telling, not in the story being told. Both are recorded, and the
  `quoted` flag separates them, because conflating them is what made act-type
  transitions useless.
- **Statives and modals.** A perfect, a participle, an imperative and a jussive
  all say something other than *and then this happened*.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
MAC = ROOT / "data" / "raw" / "macula"
DEST = OUT / "events.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

# Hebrew morph, position 3: the conjugation. `w` is the wayyiqtol.
HEB_NARRATIVE = "w"
# What the other codes are, kept so the exclusion is legible rather than magic.
HEB_CONJ = {"p": "perfect", "i": "imperfect", "w": "wayyiqtol", "j": "jussive",
            "v": "imperative", "r": "participle", "c": "inf construct",
            "a": "inf absolute", "h": "cohortative"}

REF = re.compile(r"^(\w+)\s+(\d+):(\d+)")
BOOK3 = {}


def verse_of(ref: str) -> str | None:
    """`GEN 1:1!3` -> `Gen.1.1`, matching the rest of the pipeline."""
    m = REF.match(str(ref or ""))
    if not m:
        return None
    b = m.group(1)
    b = BOOK3.get(b) or (b[0].upper() + b[1:3].lower())
    return f"{b}.{int(m.group(2))}.{int(m.group(3))}"


def hebrew_conj(morph: str) -> str | None:
    """The conjugation letter of a Hebrew verb, or None if it is not one."""
    if not morph or morph[0] != "V" or len(morph) < 3:
        return None
    return morph[2]


def scan(paths, lang):
    """One record per narrative verb, with the participants its clause names."""
    rows = []
    counts = collections.Counter()
    for p in paths:
        try:
            root = ET.parse(p).getroot()
        except ET.ParseError:
            continue
        # a word's enclosing clause, so participants can be read off it
        for cl in root.iter("wg"):
            if cl.get("class") != "cl":
                continue
            ws = [w for w in cl.iter("w")]
            if not ws:
                continue
            # participants: the head noun of each role-bearing child
            parts = collections.defaultdict(list)
            for kid in cl:
                role = kid.get("role")
                if not role or role == "v":
                    continue
                for w in ([kid] if kid.tag == "w" else kid.iter("w")):
                    if w.get("class") in ("noun", "adj") and w.get("lemma"):
                        parts[role].append(w.get("lemma"))
                        break
            for w in ws:
                if w.get("class") != "verb":
                    continue
                if lang == "hebrew":
                    c = hebrew_conj(w.get("morph", ""))
                    counts[HEB_CONJ.get(c, c or "?")] += 1
                    if c != HEB_NARRATIVE:
                        continue
                else:
                    counts[f"{w.get('tense')}/{w.get('mood')}"] += 1
                    if not (w.get("tense") == "aorist"
                            and w.get("mood") == "indicative"):
                        continue
                ref = verse_of(w.get("ref"))
                if not ref:
                    continue
                rows.append({
                    "ref": ref, "lang": lang,
                    "lemma": w.get("lemma"),
                    "gloss": (w.get("english") or w.get("gloss") or "").strip(),
                    "person": w.get("person"), "number": w.get("number"),
                    "gender": w.get("gender"),
                    "participants": {k: v[:3] for k, v in parts.items()},
                })
    return rows, counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--show", type=int, default=10)
    a = ap.parse_args()

    # quoted spans, so an event inside speech can be told from one in narration
    RXQ = re.compile(r"^\s*(\S+?)\s+(\d+):(\d+)\s*$")
    BK = {"Gen": "Gen", "Job": "Job", "Mark": "Mrk", "Titus": "Tit"}
    quoted = set()
    qp = OUT / "quotes.jsonl"
    if qp.exists():
        for line in qp.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            q = json.loads(line)
            f_, t_ = RXQ.match(str(q.get("from", ""))), RXQ.match(str(q.get("to", "")))
            if not (f_ and t_):
                continue
            b = BK.get(f_.group(1), f_.group(1))
            c1, v1, c2, v2 = (int(f_.group(2)), int(f_.group(3)),
                              int(t_.group(2)), int(t_.group(3)))
            if c1 == c2:
                for v in range(v1, v2 + 1):
                    quoted.add(f"{b}.{c1}.{v}")

    allrows, allcounts = [], collections.Counter()
    for lang, pat in (("hebrew", "hebrew/*.xml"), ("greek", "greek/*.xml")):
        paths = sorted(MAC.glob(pat))
        print(f"  {lang}: {len(paths)} files …", flush=True)
        rows, counts = scan(paths, lang)
        for r in rows:
            r["quoted"] = r["ref"] in quoted
        allrows += rows
        allcounts.update(counts)
        print(f"    {len(rows):,} narrative events")

    print(f"\nevents {len(allrows):,} over "
          f"{len({r['ref'] for r in allrows}):,} verses")
    print(f"  inside a quotation {sum(1 for r in allrows if r['quoted']):,}")
    withp = sum(1 for r in allrows if r["participants"])
    print(f"  naming a participant {withp:,} "
          f"({100*withp/max(1,len(allrows)):.0f}%)")
    print("\nverb forms seen (the exclusions are the point):")
    for k, n in allcounts.most_common(10):
        mark = "  <- kept" if k in ("wayyiqtol", "aorist/indicative") else ""
        print(f"   {n:>7,} {str(k):20}{mark}")

    print("\nexamples:")
    for r in allrows[:a.show]:
        ps = " ".join(f"{k}={','.join(v)}" for k, v in r["participants"].items())
        print(f"   {r['ref']:12} {str(r['gloss'])[:22]:24} {ps[:44]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({"_source": CREDIT,
                            "_note": "Narrative events: Hebrew wayyiqtol and "
                                     "Greek aorist indicative, with the "
                                     "participants their clause names."},
                           ensure_ascii=False) + "\n")
        for r in allrows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(allrows)} events)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
