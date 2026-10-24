"""Allusion across the testaments, where lemmas cannot reach.

`tools/allusions.py` links verses by shared Hebrew lemmas and so stops at the
Old Testament. Measured against the Berean editor's own parallel-passage notes,
that ceiling is most of the benchmark:

    editor links parsed                     2,026
      entirely within the OT                  747   allusions.py can attempt
      touching the NT                       1,279   INVISIBLE to it

Genesis 1 to John 1, Genesis 3 to Romans 5 -- the links a reader would name
first are exactly the ones a Hebrew-lemma index cannot see, because Hebrew and
Greek share no vocabulary.

## What bridges them here, and why not the alternatives

**MACULA's own English glosses**, which it carries for both testaments. The
gloss is part of the licensed data (CC BY 4.0), it is one vocabulary across the
whole canon, and it needs no third source.

Two better-sounding bridges were rejected on evidence:

- **Strong's numbers in the WEB USFM.** 100% of 645,747 word spans carry one,
  which looked like a free alignment. Measured: H3068 (YHWH) is attached to
  "of" 3,540 times and "a" 6,252 times against ~6,800 real occurrences in the
  Hebrew. The tagger assigns a nearest-Strong's to untranslatable function
  words. Unusable without a filter nobody has built.
- **The Septuagint.** Would be the right instrument and we do not hold it.

## The cost of the bridge, stated plainly

A gloss is a translation choice, so this measures **agreement between two
glossing decisions**, not identity of meaning. Hebrew *chesed* and Greek *eleos*
both gloss as "mercy" and are genuinely related; two unrelated words may both
gloss as "come". So a cross-testament link is weaker evidence than a
same-testament one, and the two are kept in separate files rather than pooled
into one score.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAC = ROOT / "data" / "raw" / "macula"
DEST = ROOT / "out" / "crosslinks.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

W = re.compile(r"<w\s([^>]*?)/?>", re.S)
A = re.compile(r'([\w:.-]+)="([^"]*)"', re.S)
REF = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)")

STOP = set("""the and for that with this from they them their there here who
what when where which will would shall should have has had was were been being
you your his her its our not but all any some such very much many one two his
him she are into upon unto out off over under about after before against among
between through while because since until unless though although whether either
neither nor own too able make made made say said says come came go went give
gave take took know knew see saw let put set thing things""".split())

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
NT = set("Mat Mrk Luk Jhn Act Rom 1Co 2Co Gal Eph Php Col 1Th 2Th 1Ti 2Ti "
         "Tit Phm Heb Jas 1Pe 2Pe 1Jn 2Jn 3Jn Jud Rev".split())


def glosses():
    bags = collections.defaultdict(set)
    files = sorted(MAC.glob("*/*.xml"))
    for i, p in enumerate(files):
        if i % 250 == 0:
            print(f"  reading {i}/{len(files)} ...", flush=True)
        for m in W.finditer(p.read_text(encoding="utf-8")):
            a = dict(A.findall(m.group(1)))
            r = REF.match(a.get("ref", "") or "")
            if not r or not BOOK.get(r.group(1)):
                continue
            g = (a.get("english") or a.get("gloss") or "").lower()
            g = g.replace(".", " ").replace("~", " ")
            ref = f"{BOOK[r.group(1)]}.{int(r.group(2))}.{int(r.group(3))}"
            for w in re.findall(r"[a-z]+", g):
                if len(w) > 3 and w not in STOP:
                    bags[ref].add(w)
    return bags


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min-shared", type=int, default=4)
    ap.add_argument("--min-idf", type=float, default=26.0)
    ap.add_argument("--max-df", type=int, default=600)
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    bags = glosses()
    print(f"verses with glosses: {len(bags):,}")

    df = collections.Counter()
    for s in bags.values():
        df.update(s)
    N = len(bags)
    idf = {w: math.log(N / c) for w, c in df.items()}

    inv = collections.defaultdict(list)
    for ref, s in bags.items():
        for w in s:
            if df[w] <= a.max_df:
                inv[w].append(ref)
    print(f"anchoring glosses (df <= {a.max_df}): {len(inv):,}")

    links = collections.defaultdict(list)
    keys = list(bags)
    for n, ref in enumerate(keys):
        if n % 4000 == 0:
            print(f"  linking {n}/{len(keys)} ...", flush=True)
        bk = ref.split(".")[0]
        side = bk in NT
        cnt = collections.Counter()
        for w in bags[ref]:
            if df[w] <= a.max_df:
                for j in inv[w]:
                    # ONLY across the testaments: same-side links are
                    # tools/allusions.py's job, and it does them on lemmas,
                    # which is stronger evidence than a shared gloss.
                    if (j.split(".")[0] in NT) != side:
                        cnt[j] += 1
        for j, c in cnt.items():
            if c < a.min_shared:
                continue
            sh = bags[ref] & bags[j]
            mass = sum(idf[x] for x in sh)
            if mass >= a.min_idf:
                links[ref].append((round(mass, 2), len(sh), j,
                                   sorted(sh, key=lambda x: -idf[x])[:4]))
        links[ref].sort(reverse=True)
        links[ref] = links[ref][:a.top]

    tot = sum(len(v) for v in links.values())
    print(f"\ncross-testament links: {tot:,} over "
          f"{sum(1 for v in links.values() if v):,} verses")

    print("\nstrongest, as a sanity check:")
    flat = sorted(((m, r, j, sh) for r, v in links.items()
                   for m, c, j, sh in v), reverse=True)[:10]
    for m, r, j, sh in flat:
        print(f"   {r:<12} -> {j:<12} {m:>6.1f}  {sh}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": CREDIT,
            "_note": "Links ACROSS the testaments only, on shared MACULA "
                     "glosses, because Hebrew and Greek share no lemma. Weaker "
                     "evidence than tools/allusions.py, which uses lemmas "
                     "within one testament: a gloss is a translation choice, so "
                     "this measures agreement between two glossing decisions. "
                     "Kept in a separate file for that reason.",
            "params": {"min_shared": a.min_shared, "min_idf": a.min_idf,
                       "max_df": a.max_df},
        }, ensure_ascii=False) + "\n")
        for r in sorted(links):
            if links[r]:
                f.write(json.dumps({
                    "ref": r,
                    "links": [{"ref": j, "idf": m, "shared": c, "words": sh}
                              for m, c, j, sh in links[r]],
                }, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
