"""Templates: a pattern is defined by what does NOT vary.

The question was how a pattern can be surfaced when it never recurs elsewhere in the
corpus, the case having been named in an earlier session:

  "if the beatitudes were the only verses in the Bible in that form I would
   still want to capture that pattern as it is important for the collection."

The answer is a second, independent source of significance: **repetition inside
the node**, not across the corpus. The beatitudes are unique corpus-wide and
repeat eight times internally.

## Three signatures, and why the first two failed

Getting this right took three attempts and the failures are the finding.

**1. `(stance, polarity, form)` per clause.** Median 0.78 across 18,317
ten-verse windows -- a measure that fires on everything -- and it ranked the two
most formulaic passages in the Bible BELOW its own median (beatitudes 0.75,
Psalm 136 0.70). Most narrative clauses are `(report, positive, indicative)`, so
genealogies scored 0.92 trivially. **It measured "is this narrative", not "is
this formulaic".**

**2. Clause `rule` sequences, and then PAIRS of them.** Single rules
discriminated (genealogy 0.86, free argument 0.24) but still put the beatitudes
at 0.42. Pairing rules made it far worse -- 0.06 -- because pairing inflates the
signature space until nothing repeats.

**3. Constituent shape.** Looking at what MACULA actually gives for Matthew 5:3
settled it:

    cl  rule=None                     the whole beatitude: VERBLESS,
      np   role=s                     "makarioi" IS the predicate
      wg   rule=sub-CL role=adv       hoti ...
        cl rule=P-VC-S / S-V / S-V-O  VARIES between beatitudes

**The inner clause varies by design; the outer frame does not.** So the
signature is the frame -- does the clause have a finite verb, what roles its
direct children fill, and which subordinator heads any adverbial sub-clause:

    ("V" | "VERBLESS",  sorted child roles,  subordinator lemma)

Measured on passages chosen before running:

    Psa 136      refrain        0.78   VERBLESS  p/s              x25
    Gen 1:3-13   creation       0.74   V         s/v              x13
    Mat 5:3-12   BEATITUDES     0.64   V         adv/p/s  hoti     x8
    Gen 5:6-20   genealogy      0.60   V         o/v              x10
    Psa 119:1-24                0.57
    1Co 13:1-8   love           0.52   V         o/v               x8
    Rom 3:1-12   argument       0.23
    Mat 5:21-32  antitheses     0.21
    Rom 9:1-12   argument       0.06

**All eight beatitudes under one signature**, and Psalm 136's refrain at 25
repeats of the first. Range 0.06 to 0.78, so unlike attempt 1 it can express
failure.

## The generalisation

**A template is defined by what does not vary, and the level at which that
invariance lives is the level of the pattern.** The first two signatures
measured the fill rather than the frame, which is the same level-boundness
recorded on 2026-09-12 from the other direction: a section-level trait is
invisible at verse level, and a frame-level template is invisible to a
fill-level signature.
"""
from __future__ import annotations

import argparse
import collections
import glob
import pathlib
import re
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAC = ROOT / "data/raw/macula"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

FINITE = {"indicative", "imperative", "subjunctive", "optative",
          "qatal", "wayyiqtol", "yiqtol", "weqatal", "jussive", "cohortative"}


def _first(s):
    p = (s or "").split()
    return p[0] if p else ""


def shapes(path, chapter=None, lo=None, hi=None):
    """Constituent-shape signature for every TOP-LEVEL clause in range."""
    root = ET.parse(path).getroot()
    parent = {c: p for p in root.iter() for c in p}
    out = []
    for cl in root.iter("wg"):
        if cl.get("class") != "cl":
            continue
        n = parent.get(cl)
        nested = False
        while n is not None:
            if n.get("class") == "cl":
                nested = True
                break
            n = parent.get(n)
        if nested:
            continue
        ws = list(cl.iter("w"))
        if not ws:
            continue
        m = re.search(r"(\d+):(\d+)", ws[0].get("ref") or "")
        if not m:
            continue
        c, v = int(m.group(1)), int(m.group(2))
        if chapter is not None and not (c == chapter and lo <= v <= hi):
            continue
        finite = any((x.get("class") == "verb" and _first(x.get("type")) in FINITE)
                     or (x.get("mood") in FINITE) for x in ws)
        roles = tuple(sorted({d.get("role") for d in cl if d.get("role")}))
        sub = None
        for d in cl:
            if d.get("rule") == "sub-CL" or d.get("role") == "adv":
                w0 = next((x for x in d.iter("w")), None)
                if w0 is not None:
                    sub = w0.get("lemma")
                break
        out.append(((c, v), ("V" if finite else "VERBLESS"), roles, sub))
    return out


def repetition(sigs):
    """-> (share repeated, n, most common signature and its count)."""
    seq = [s[1:] for s in sigs]
    if len(seq) < 4:
        return None
    c = collections.Counter(seq)
    return (sum(n - 1 for n in c.values()) / len(seq), len(seq),
            c.most_common(1)[0])


PROBES = [
    ("Mat 5:3-12  BEATITUDES", "greek/01-matthew.xml", 5, 3, 12, 0.55),
    ("Psa 136     refrain", "hebrew/19-Psa-136-lowfat.xml", 136, 1, 26, 0.70),
    ("Gen 5:6-20  genealogy", "hebrew/01-Gen-005-lowfat.xml", 5, 6, 20, 0.50),
    ("Rom 9:1-12  free argument", "greek/06-romans.xml", 9, 1, 12, None),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()
    print("CONSTITUENT-SHAPE TEMPLATES\n")
    print(f"  {'passage':<28}{'rep':>6}{'n':>5}   dominant frame")
    print("  " + "-" * 70)
    ok = True
    for name, rel, ch, lo, hi, floor in PROBES:
        r = repetition(shapes(MAC / rel, ch, lo, hi))
        if r is None:
            print(f"  {name:<28} too few clauses")
            continue
        ratio, n, (top, k) = r
        print(f"  {name:<28}{ratio:>6.2f}{n:>5}   {top[0]:<8} "
              f"{'/'.join(top[1]) or '-':<10} {top[2] or '-':<6} x{k}")
        if floor is not None and ratio < floor:
            ok = False
            print(f"       FAIL: expected >= {floor}")
    if a.test:
        print(f"\n  {'PASS' if ok else 'FAIL'}  "
              f"(free argument should sit far below the formulaic passages)")
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
