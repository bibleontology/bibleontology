"""Does one rule set fit every writing style? Measured, per style.

2026-09-09, on the sentence layer: all writing styles must be accounted for,
but the rules might be adapted to the style that they apply to.

`tools/sentfunc.py` applies **one connective table** to narrative, law, poetry,
prophecy, gospel, epistle and apocalypse alike. That is the assumption this
module tries to break, and there is prior reason to think it will: five signals
have already been measured **inverting sign by genre** rather than merely
weakening, and lexical cohesion read **0.0 at every seam** of Psalm 103 while
being the strongest signal available in Pauline argument.

## How style is assigned, and why not with `genre.py`

`src/bibleont/genre.py` computes a seven-dimension style vector and would be
the right instrument -- except that it reads `data/raw/stepbible`, which this
project dropped from the pipeline on 2026-09-08. Those files are still on local
disk and are gitignored, so nothing was ever distributed, but the module would
fail for anyone who cloned the repository. **Flagged rather than used.**

So style here is the **canonical division**, which is coarse, standard, and
carries no licence question at all. Its weakness is real and stated: it is
assigned by book, so Exodus's law and Exodus's narrative get one label, and
poetry embedded in prophecy is counted as prophecy.

To keep that from being an unchecked assumption, each style is reported
alongside a **measured** narrative rate -- events per sentence, from
`out/events.jsonl.gz`, which is wayyiqtol and aorist indicative counted from
MACULA. If the labels are arbitrary, that column will not separate them.

## What would falsify the premise

If every style shows the same direction mix and the same relation mix within a
few points, then one rule set does fit, the suspicion is wrong, and this
module should say so plainly rather than manufacture a difference.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

# Canonical divisions. Coarse by construction; see the docstring.
STYLES = {
    "law": "Gen Exo Lev Num Deu",
    "narrative": "Jos Jdg Rut 1Sa 2Sa 1Ki 2Ki 1Ch 2Ch Ezr Neh Est",
    "poetry": "Job Psa Pro Ecc Sng",
    "prophecy": "Isa Jer Lam Ezk Dan Hos Jol Amo Oba Jon Mic Nam Hab Zep Hag "
                "Zec Mal",
    "gospel": "Mat Mrk Luk Jhn Act",
    "epistle": "Rom 1Co 2Co Gal Eph Php Col 1Th 2Th 1Ti 2Ti Tit Phm Heb Jas "
               "1Pe 2Pe 1Jn 2Jn 3Jn Jud",
    "apocalyptic": "Rev",
}
OF = {b: s for s, bs in STYLES.items() for b in bs.split()}
ORDER = list(STYLES)


def book(ref):
    return str(ref or "").split(".")[0]


def load(name):
    rows = []
    with gzip.open(OUT / name, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if not any(k.startswith("_") for k in d):
                rows.append(d)
    return rows


def pct(part, whole):
    return 100.0 * part / whole if whole else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min-opener", type=int, default=40,
                    help="openers rarer than this are not reported per style")
    a = ap.parse_args()

    sents = load("sentence-function.jsonl.gz")
    events = collections.Counter(book(e.get("ref")) for e in load("events.jsonl.gz"))

    per = collections.defaultdict(list)
    unknown = collections.Counter()
    for s in sents:
        b = book(s["ref"])
        st = OF.get(b)
        if st:
            per[st].append(s)
        else:
            unknown[b] += 1
    if unknown:
        print(f"unlabelled books: {dict(unknown.most_common(8))}\n")

    # --- 1. does the label separate anything measurable? -------------------
    print("STYLE SIZE, and a MEASURED check that the labels are not arbitrary")
    print(f"  {'style':<12} {'sentences':>9} {'events/sent':>12}")
    for st in ORDER:
        rows = per[st]
        ev = sum(events[b] for b in STYLES[st].split())
        print(f"  {st:<12} {len(rows):>9} {ev / len(rows):>12.2f}"
              if rows else f"  {st:<12} {'0':>9}")

    # --- 2. the direction mix, per style ----------------------------------
    print("\nDIRECTION -- what a sentence needs from its neighbours")
    print(f"  {'style':<12} " + "".join(f"{k:>11}" for k in
                                        ("backward", "internal", "forward", "free")))
    dirs = {}
    for st in ORDER:
        rows = per[st]
        if not rows:
            continue
        c = collections.Counter(r["direction"] for r in rows)
        dirs[st] = {k: pct(c[k], len(rows)) for k in
                    ("backward", "internal", "forward", "free")}
        print(f"  {st:<12} " + "".join(f"{dirs[st][k]:>10.1f}%" for k in
                                       ("backward", "internal", "forward", "free")))

    # --- 3. the relation mix, per style -----------------------------------
    rels = ("expansion", "contingency", "temporal", "comparison")
    print("\nRELATION -- and how often NO connective is found at all")
    print(f"  {'style':<12} " + "".join(f"{k:>13}" for k in rels) + f"{'none':>9}")
    for st in ORDER:
        rows = per[st]
        if not rows:
            continue
        c = collections.Counter(r["relation"] for r in rows)
        print(f"  {st:<12} " + "".join(f"{pct(c[k], len(rows)):>12.1f}%"
                                       for k in rels)
              + f"{pct(c[None], len(rows)):>8.1f}%")

    # --- 4. the point: does one WORD mean one thing everywhere? ------------
    # A rule set is style-independent only if its individual triggers are.
    print("\nSAME OPENER, DIFFERENT STYLE -- share of that style's sentences")
    print("  (a word whose rate swings by style is a rule needing adaptation)")
    opens = collections.Counter(s["opens"] for s in sents if s["opens"])
    watch = [w for w, n in opens.most_common(40) if n >= a.min_opener][:14]
    print(f"  {'opener':<10} " + "".join(f"{s[:6]:>8}" for s in ORDER) + "   swing")
    swings = []
    for w in watch:
        row = []
        for st in ORDER:
            rows = per[st]
            row.append(pct(sum(1 for r in rows if r["opens"] == w), len(rows))
                       if rows else 0.0)
        lo, hi = min(row), max(row)
        swings.append((hi - lo, w, row))
    for sw, w, row in sorted(swings, reverse=True):
        print(f"  {w:<10} " + "".join(f"{v:>7.1f}%" for v in row)
              + f"  {sw:>6.1f}pt")

    # --- 5. the verdict, stated as a number rather than an impression -----
    print("\nVERDICT")
    if len(dirs) > 1:
        spread = {k: max(d[k] for d in dirs.values()) - min(d[k] for d in dirs.values())
                  for k in ("backward", "internal", "forward", "free")}
        worst = max(spread, key=lambda k: spread[k])
        print(f"  widest direction spread: {worst} varies {spread[worst]:.1f} points "
              f"across styles")
        top = max(dirs, key=lambda s: dirs[s]["free"])
        bot = min(dirs, key=lambda s: dirs[s]["free"])
        print(f"  most connective-free style: {top} ({dirs[top]['free']:.1f}% free)")
        print(f"  least:                      {bot} ({dirs[bot]['free']:.1f}% free)")
        print(f"  ratio {dirs[top]['free'] / max(dirs[bot]['free'], 1e-9):.2f}x")
        if spread[worst] < 5:
            print("\n  -> one rule set FITS. The premise is not supported and no "
                  "per-style adaptation is justified.")
        else:
            print("\n  -> the same rules do NOT behave alike across styles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
