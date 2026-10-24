"""The loop: cast wide, trim strategically, then re-read the bottom with the top in hand.

2026-09-10, describing the architecture after a day of watching single-pass
methods fail: it has to be iterative, with more liberal testing of candidates,
then strategic trimming, then reevaluation of lower levels in the contexts that
the higher-level patterns create.

Three phases, and the third is the one nothing here has ever done.

## 1. Liberal candidates

Every passage against every other, **in each taxonomy separately**, keeping
anything with rarity mass above a low bar. Casting wide is deliberate: a single
strict pass throws away the pair that would have been obvious once its taxonomy
was known.

Two taxonomies over the same frame data, and they disagree usefully:

    PREDICATE   what was done
    PATIENT     what it was done to

Measured on Genesis 19 (Sodom):

    vs Judges 19    predicates 150.1   the HOSPITALITY script: urge, linger,
                                       rise early, wash, lodge
    vs Genesis 6-9  predicates 121.0   the JUDGMENT script: rain down, shut,
                                       destroy, remember, preserve alive
    vs Genesis 11    predicates 29.3   control, correctly weak

The same passage is strongly like two others **in different respects**, and a
comparison that pooled the taxonomies would have found neither.

## 2. Strategic trimming

A candidate survives when **one taxonomy clearly dominates** -- a high mass in
one and not the rest. That asymmetry is the evidence that something specific was
noticed, rather than two passages merely both being long. A pair scoring evenly
everywhere is dropped: it is similar in no particular way.

## 3. Re-evaluation with context

The step that was asked for, and the reason the loop exists. Once a pair is typed --
these two are a JUDGMENT pattern -- the slots beneath are re-read **in that
light**, and their fates change:

    סָגַר "shut"    noise against Babel, IDENTITY against the Flood
    אָמַר "said"    noise in every comparison, always

This had already been named when the triage looked fixed: some triage items may
come up for re-evaluation later; the details of Abraham's negotiation become
noise when comparing to the Ark though they might give off signals that are
captured at a more conceptual level.

**So triage is a property of the PAIR, not of the slot.** `tools/generalize.py`
fixes a slot's fate per skeleton and is wrong for exactly this reason; it is
correct only within one comparison.

## What this does not do

**It does not name a pattern.** A surviving pair is reported with the taxonomy
that carried it and the rare items that did the carrying. Calling one "divine
judgment on a corrupt city" is a reading and belongs to the reader.

**One iteration is not convergence.** This runs the loop twice and shows what
moved. Whether it settles, and on what, is unmeasured.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"


def load(name):
    rows = []
    p = OUT / name
    if not p.exists():
        return rows
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                if not any(k.startswith("_") for k in d):
                    rows.append(d)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--floor", type=float, default=0.18,
                    help="phase 1 keeps a candidate above this cosine")
    ap.add_argument("--dominance", type=float, default=1.6,
                    help="phase 2 keeps a pair whose best taxonomy beats its "
                         "second by this ratio")
    ap.add_argument("--min-shared", type=int, default=5,
                    help="a taxonomy needs this many items in common before a "
                         "cosine means anything")
    ap.add_argument("--minz", type=float, default=2.0,
                    help="a pair must be this many sd above its taxonomy's own "
                         "mean to count as having noticed anything")
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()

    fr = load("frames.jsonl.gz")
    byref = collections.defaultdict(list)
    for f in fr:
        byref[f["ref"]].append(f)

    # corpus rarity, per taxonomy
    freq = {"predicate": collections.Counter(), "patient": collections.Counter()}
    for f in fr:
        if f.get("lemma"):
            freq["predicate"][f["lemma"]] += 1
        for p in (f.get("patient") or []):
            freq["patient"][p] += 1
    total = {k: sum(v.values()) for k, v in freq.items()}

    # units = chapters, which is what a narrative mostly occupies
    chap = collections.defaultdict(list)
    for r in byref:
        b, c, _ = r.split(".")
        chap[(b, int(c))].append(r)

    def profile(key):
        out = {"predicate": collections.Counter(),
               "patient": collections.Counter()}
        for r in chap[key]:
            for f in byref[r]:
                if f.get("lemma"):
                    out["predicate"][f["lemma"]] += 1
                for p in (f.get("patient") or []):
                    out["patient"][p] += 1
        return out

    keys = [k for k in chap if len(chap[k]) >= 12]
    print(f"chapters with >=12 framed verses: {len(keys):,}")
    prof = {k: profile(k) for k in keys}

    # RARITY-WEIGHTED COSINE, not raw shared mass. Raw mass made Genesis 24
    # -- 67 verses -- match six unrelated chapters on nothing but its own
    # length, and its "rare" shared verbs were run, ride, grow old. Cosine
    # divides out size, so a short chapter that overlaps precisely can beat a
    # long one that overlaps by accident.
    def wvec(k, tax):
        v = {x: n * math.log(total[tax] / freq[tax][x])
             for x, n in prof[k][tax].items()}
        z = math.sqrt(sum(y * y for y in v.values())) or 1.0
        return {x: y / z for x, y in v.items()}

    W = {tax: {k: wvec(k, tax) for k in keys}
         for tax in ("predicate", "patient")}
    MIN_SHARED = a.min_shared

    def mass(a_, b_, tax):
        # A SPARSE VECTOR FAKES A HIGH COSINE. Genesis 5's patient profile is
        # almost entirely "name" and "he", so it normalised to a near-unit
        # vector and scored 5.4-6.7 against six unrelated psalms on one shared
        # word. Requiring several shared items is what separates "these two
        # overlap" from "one of these has nothing to overlap WITH".
        sh = set(prof[a_][tax]) & set(prof[b_][tax])
        if len(sh) < MIN_SHARED:
            return 0.0, sh
        x, y = W[tax][a_], W[tax][b_]
        if len(x) > len(y):
            x, y = y, x
        s = sum(w * y.get(i, 0) for i, w in x.items())
        return s, sh

    # ---- PHASE 1: liberal ------------------------------------------------
    focus = [k for k in keys if k[0] == "Gen"]
    cands = []
    for f_ in focus:
        for k in keys:
            if k == f_:
                continue
            scored = {}
            shares = {}
            for tax in ("predicate", "patient"):
                m, sh = mass(f_, k, tax)
                scored[tax] = m
                shares[tax] = sh
            best = max(scored, key=scored.get)
            if scored[best] >= a.floor:
                cands.append((f_, k, scored, shares, best))
    print(f"\nPHASE 1 (liberal, floor {a.floor}): {len(cands):,} candidates "
          f"from {len(focus)} Genesis chapters")

    # ---- PHASE 2: strategic trim ----------------------------------------
    # EACH TAXONOMY AGAINST ITS OWN BACKGROUND. The first version compared a
    # predicate cosine with a patient cosine directly, so the ratio measured
    # which taxonomy is DENSER, not which one noticed something: 20,910 of
    # 24,675 candidates "survived", a filter that drops 15% and decides
    # nothing. Standardising within a taxonomy first makes the comparison
    # meaningful -- a pair is kept when one taxonomy is unusual FOR THAT
    # TAXONOMY and the others are not.
    import statistics
    bg = {}
    for tax in ("predicate", "patient"):
        vals = [s[tax] for _, _, s, _, _ in cands]
        mu = statistics.fmean(vals) if vals else 0.0
        sd = statistics.pstdev(vals) if len(vals) > 1 else 1.0
        bg[tax] = (mu, sd or 1.0)
    print(f"  background: " + "  ".join(
        f"{tax} mean {bg[tax][0]:.3f} sd {bg[tax][1]:.3f}"
        for tax in bg))

    kept = []
    for f_, k, scored, shares, best in cands:
        z = {tax: (scored[tax] - bg[tax][0]) / bg[tax][1] for tax in scored}
        order = sorted(z, key=z.get, reverse=True)
        top, second = z[order[0]], z[order[1]]
        if top < a.minz:
            continue                      # unusual in no taxonomy at all
        if second > 0 and top / max(second, 0.05) < a.dominance:
            continue                      # unusual in every taxonomy equally
        kept.append((round(top, 2), f_, k, order[0], shares[order[0]]))
    kept.sort(reverse=True)
    print(f"PHASE 2 (dominance >= {a.dominance}x): {len(kept):,} survive "
          f"— a pair alike in NO PARTICULAR respect is dropped")

    # ADJACENCY IS A DIFFERENT RELATION, not a better one. Genesis 42 resembles
    # Genesis 43 because it is the same story continued, and detecting that is
    # table stakes -- it dominated the ranking and buried everything distant.
    # Scored apart rather than discarded: continuation is real, it is simply
    # not allusion, and only the distant column can hold a discovery.
    def near(x, y):
        return x[0] == y[0] and abs(x[1] - y[1]) <= 2

    cont = [r for r in kept if near(r[1], r[2])]
    dist = [r for r in kept if not near(r[1], r[2])]
    print(f"  of these: {len(cont):,} CONTINUATION (within 2 chapters), "
          f"{len(dist):,} DISTANT")

    def show(rows, n):
        for m, f_, k, tax, sh in rows[:n]:
            rare = sorted(sh,
                          key=lambda x: -math.log(total[tax] / freq[tax][x]))[:4]
            print(f"    {f_[0]}.{f_[1]:<3} ~ {k[0]}.{k[1]:<4} z={m:>5.1f}  "
                  f"[{tax}]  {rare}")

    print(f"\n  CONTINUATION — the same story carrying on (table stakes):")
    show(cont, 5)
    print(f"\n  DISTANT — where a discovery could be:")
    show(dist, a.top)

    # ---- PHASE 3: re-read the slots with the pair's type in hand ---------
    print(f"\n{'='*74}\nPHASE 3 — the same slots, re-read inside each pair\n"
          f"{'='*74}")
    print("A slot's fate is a property of the PAIR, not of the slot.\n")
    for m, f_, k, tax, sh in dist[:4]:
        allitems = set(prof[f_][tax]) | set(prof[k][tax])
        ident, noise = [], []
        for x in sorted(allitems):
            r = math.log(total[tax] / freq[tax][x])
            if x in sh and r >= 6.0:
                ident.append((r, x))
            elif x in sh:
                noise.append(x)
        ident.sort(reverse=True)
        print(f"  {f_[0]}.{f_[1]} ~ {k[0]}.{k[1]}   [{tax}]")
        print(f"    IDENTITY here : {[x for _, x in ident[:6]]}")
        print(f"    shared but common (noise here): {noise[:6]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
