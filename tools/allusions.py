"""Theme as canonical co-location: which verses quote or echo which.

2026-09-09: the three-coordinate theme space was rejected on the right grounds.
Themes are not determined by word similarity alone; they are determined by
co-location in other parts of the Canon and particularly in the same
narratives, and in the case of a saying, by where it originated. "Compassionate
and gracious" builds on the story of God's forgiveness after the Golden Calf,
and the following verses continue on that theme.

That is right, and the example proves itself. `tools/themespace.py` put Psalm
103:8 in a 3-space whose axes turned out to separate Leviticus from Luke. What
actually gives that verse its theme is that it **quotes Exodus 34:6** -- God's
self-revelation to Moses after the Golden Calf. And the verse before it,
Psalm 103:7, says *"He made known His ways to Moses"*: the psalm names the
narrative and then recites its words.

## The measurement

For every pair of verses sharing at least three content lemmas, score the
**IDF mass they share** -- rare words in common count, common ones do not. Then
drop pairs from the same chapter, which are local repetition rather than
allusion.

Run against Psalm 103:8 it recovers the entire chain scholarship calls the
Grace Formula, from the corpus alone and with no external source:

    Jon 4:2       8 lemmas    36.4    Jonah quoting it back at God
    Joel 2:13     8           36.4
    Exo 34:6      8           36.4    THE SOURCE -- rank 3 of 276 candidates
    Psa 86:15     7           35.0
    Neh 9:17      7           35.0
    Psa 145:8     7           32.5
    Num 14:18     6           21.5

## Why this is the better shape for "theme"

A coordinate space asks *how similar are these two verses*. This asks *does this
verse carry another verse's words*, which is a different and stronger relation:
Psalm 103:8 is not merely near Exodus 34:6 in some space, it is **made of it**.

It is also multi-dimensional in the way that was asked for -- not three numbers but
a graph, where a verse's theme is its neighbourhood, and a chain like the Grace
Formula is a connected component running from Exodus through Numbers, Nehemiah,
Joel, Jonah, Nahum and four psalms.

## What it does not do

It finds **shared wording**, so it will miss an allusion that reworks its source
without repeating it, and it will catch a stock phrase that carries no
dependence. High IDF mass makes the second rare but not impossible. Direction is
not inferred either: the method says Psalm 103:8 and Exodus 34:6 share a
formula, not which came first -- that is a judgement about composition history
this project has no way to make and does not attempt.
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
DEST = ROOT / "out" / "allusions.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

W = re.compile(r"<w\s([^>]*?)/?>", re.S)
A = re.compile(r'([\w:.-]+)="([^"]*)"', re.S)
REF = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)!(\d+)")
FUNC = {"prep", "conj", "art", "ptcl"}

BOOK = {"GEN": "Gen", "EXO": "Exo", "LEV": "Lev", "NUM": "Num", "DEU": "Deu",
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
        "JUD": "Jud", "REV": "Rev"}


def read():
    byv = {}
    # BOTH TESTAMENTS. This scanned only the Hebrew directory, which put a
    # ceiling on it that the editor's own cross-references made visible: of
    # 2,026 parallel-passage notes, 915 are NT-to-NT -- the synoptic parallels
    # above all -- and none were reachable. Hebrew and Greek lemmas never
    # collide, so one index serves both and links stay within a language.
    files = sorted(MAC.glob("*/*.xml"))
    for i, p in enumerate(files):
        if i % 250 == 0:
            print(f"  reading {i}/{len(files)} ...", flush=True)
        cur = collections.defaultdict(list)
        for m in W.finditer(p.read_text(encoding="utf-8")):
            a = dict(A.findall(m.group(1)))
            r = REF.match(a.get("ref", "") or "")
            if r and BOOK.get(r.group(1)):
                cur[(BOOK[r.group(1)], int(r.group(2)), int(r.group(3)))].append(
                    (int(r.group(4)), a))
        for k, ws in cur.items():
            byv[k] = [a for _, a in sorted(ws, key=lambda x: x[0])]
    return byv


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min-shared", type=int, default=3)
    ap.add_argument("--min-idf", type=float, default=14.0,
                    help="shared IDF mass below this is not a link")
    ap.add_argument("--max-df", type=int, default=1200,
                    help="a lemma commoner than this cannot anchor a link")
    ap.add_argument("--top", type=int, default=8, help="links kept per verse")
    ap.add_argument("--passage", default="Psa.103")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    byv = read()
    print(f"verses {len(byv)}")

    lem = {}
    for k, ws in byv.items():
        lem[k] = {x["lemma"] for x in ws
                  if x.get("lemma")
                  and (x.get("class") or x.get("pos")) not in FUNC}

    df = collections.Counter()
    for s in lem.values():
        df.update(s)
    N = len(byv)
    idf = {L: math.log(N / c) for L, c in df.items()}

    # inverted index over lemmas rare enough to anchor a link
    inv = collections.defaultdict(list)
    for k, s in lem.items():
        for L in s:
            if df[L] <= a.max_df:
                inv[L].append(k)
    print(f"anchoring lemmas (df <= {a.max_df}): {len(inv)}")

    def gloss(k):
        return " ".join((x.get("english") or x.get("gloss") or "?")
                        .replace(".", " ") for x in byv[k]).strip()

    links = collections.defaultdict(list)
    keys = list(byv)
    for n, k in enumerate(keys):
        if n % 3000 == 0:
            print(f"  linking {n}/{len(keys)} ...", flush=True)
        cnt = collections.Counter()
        for L in lem[k]:
            if df[L] <= a.max_df:
                for j in inv[L]:
                    if j != k and not (j[0] == k[0] and j[1] == k[1]):
                        cnt[j] += 1
        for j, c in cnt.items():
            if c < a.min_shared:
                continue
            sh = lem[k] & lem[j]
            mass = sum(idf[x] for x in sh)
            if mass >= a.min_idf:
                links[k].append((round(mass, 2), len(sh), j))
        links[k].sort(reverse=True)
        links[k] = links[k][:a.top]

    tot = sum(len(v) for v in links.values())
    print(f"\nverses with at least one link: {sum(1 for v in links.values() if v)}")
    print(f"links kept: {tot}")

    print(f"\n{'=' * 74}\n{a.passage} -- where each verse's words come from\n{'=' * 74}")
    bk, ch = a.passage.split(".")[0], int(a.passage.split(".")[1])
    for v in sorted(x[2] for x in byv if x[0] == bk and x[1] == ch):
        k = (bk, ch, v)
        got = links.get(k) or []
        if not got:
            print(f"  v{v:<3} --")
            continue
        best = ", ".join(f"{j[0]}.{j[1]}.{j[2]} ({m:.0f})" for m, _, j in got[:3])
        print(f"  v{v:<3} {best}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": CREDIT,
            "_note": "Verses linked by shared IDF mass over content lemmas: "
                     "which verses carry another verse's words. Same-chapter "
                     "pairs are excluded as local repetition. Finds shared "
                     "WORDING, so it misses a reworked allusion and does not "
                     "infer direction -- it says two verses share a formula, "
                     "never which came first.",
            "params": {"min_shared": a.min_shared, "min_idf": a.min_idf,
                       "max_df": a.max_df, "top": a.top},
        }, ensure_ascii=False) + "\n")
        for k in sorted(links):
            if not links[k]:
                continue
            f.write(json.dumps({
                "ref": f"{k[0]}.{k[1]}.{k[2]}",
                "links": [{"ref": f"{j[0]}.{j[1]}.{j[2]}",
                           "idf": m, "shared": c} for m, c, j in links[k]],
            }, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
