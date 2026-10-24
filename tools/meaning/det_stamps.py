"""Deterministic stamps, learned from the Flash corpus run (experiment, P-52).

2026-09-29: an experiment in adding deterministic stamping.

Why: requiring a shared stamp failed as a gate twice (measured 2026-09-29) —
each section chose its stamps from its own slate, so one idea wears two
names in two sections. A rule applies the same way everywhere and can say
which words fired it.

How: a verse carries a stamp (from Flash) when any clause of it carries the
stamp at medium or better. Each stamp's SIGNATURE is the features that
stand out in the verses carrying it — lemmas (by Strong's number, content
words only) and the people, places and concepts the verse mentions (records,
which cross Hebrew and Greek). A feature's weight is its smoothed log lift
(share among the stamp's verses over share among all verses); a verse's
score is the sum over its features; a threshold per stamp is chosen on the
training books for the best F1 against Flash.

Measured by books: trained on one half of the canon, tested on the other,
and the other way round, so no verse is scored by a rule that saw it.

    python tools/meaning/det_stamps.py            -> report
    python tools/meaning/det_stamps.py --apply    -> out/det-stamps.jsonl.gz
                                                     (trained on every book)
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
CONTENT = {"noun", "verb", "adj"}
MIN_A, MIN_LIFT = 5, 2.0            # a feature in 5+ of the stamp's verses, 2x its base rate
MIN_VERSES = 60                     # stamps with fewer medium+ verses are not learned


def rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith('{"_'):
                yield json.loads(line)


def load():
    feats = collections.defaultdict(set)         # verse -> {feature}
    gloss = collections.defaultdict(collections.Counter)
    for n in rows(OUT / "structure-nodes.jsonl.gz"):
        if not n.get("word") or n.get("class") not in CONTENT:
            continue
        d = "".join(c for c in (n.get("strong") or "") if c.isdigit())
        if not d:
            continue
        k = ("g" if n.get("lang") == "greek" else "h") + str(int(d))
        feats[n["id"].split("#")[0]].add(k)
        gloss[k][(n.get("text") or "").lower()] += 1
    for m in rows(OUT / "mentions.jsonl.gz"):
        feats[m["occurrence"].split("#")[0]].add("@" + m["record"])
    labels = collections.defaultdict(set)        # verse -> {stamp}
    for line in gzip.open(OUT / "clause-tags.jsonl.gz", "rt", encoding="utf-8").read().splitlines()[1:]:
        t = json.loads(line)
        if t["kind"] == "stamp" and t["weight"] >= 0.67:
            labels[t["clause"].split("#")[0]].add(re.sub(r"_ev$", "", t["tag"]))
    # a verse the run read: any verse of a stamped section (the run covered
    # 3,007 of 3,009); verses with features are the universe
    return feats, labels, {k: c.most_common(1)[0][0] for k, c in gloss.items()}


def train(verses, feats, labels, stamps):
    N = len(verses)
    df = collections.Counter(f for v in verses for f in feats[v])
    sig = {}
    for s in stamps:
        pos = [v for v in verses if s in labels.get(v, ())]
        if len(pos) < MIN_VERSES // 2:
            continue
        a = collections.Counter(f for v in pos for f in feats[v])
        w = {}
        for f, n in a.items():
            if n < MIN_A:
                continue
            lift = ((n + 1) / (len(pos) + 2)) / ((df[f] + 1) / (N + 2))
            if lift >= MIN_LIFT:
                w[f] = math.log(lift)
        sig[s] = w
    return sig


def score(v, feats, w):
    return sum(w.get(f, 0.0) for f in feats[v])


def threshold(verses, feats, labels, s, w):
    """the score that gives the best F1 against Flash on these verses"""
    sc = sorted(((score(v, feats, w), s in labels.get(v, ())) for v in verses), reverse=True)
    total = sum(y for _x, y in sc)
    best, tp, bt = (0.0, float("inf")), 0, float("inf")
    for i, (x, y) in enumerate(sc, 1):
        tp += y
        if tp == 0:
            continue
        p, r = tp / i, tp / total
        f1 = 2 * p * r / (p + r)
        if f1 > best[0]:
            best = (f1, x)
    return best[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    feats, labels, gloss = load()
    verses = sorted(feats)
    count = collections.Counter(s for v in verses for s in labels.get(v, ()))
    stamps = [s for s, n in count.items() if n >= MIN_VERSES]
    themes = {i["id"] for i in json.loads((ROOT / "ontology" / "interest-taxonomy.json")
                                          .read_text(encoding="utf-8"))["themes"]["items"]}
    books = sorted({v.split(".")[0] for v in verses})
    half = [{b for i, b in enumerate(books) if i % 2 == k} for k in (0, 1)]
    if a.apply:
        sig = train(verses, feats, labels, stamps)
        thr = {s: threshold(verses, feats, labels, s, w) for s, w in sig.items()}
        with gzip.open(OUT / "det-stamps.jsonl.gz", "wt", encoding="utf-8") as f:
            f.write(json.dumps({"_note": "Deterministic stamps (tools/meaning/det_stamps.py): "
                                "each stamp's signature learned from the Flash corpus run, "
                                "applied by rule to every verse. An experiment (P-52)."}) + "\n")
            for v in verses:
                got = []
                for s, w in sig.items():
                    x = score(v, feats, w)
                    if x >= thr[s]:
                        why = sorted((f for f in feats[v] if f in w), key=lambda f: -w[f])[:4]
                        got.append({"stamp": s, "score": round(x, 2), "by": [
                            f[1:] if f[0] == "@" else gloss.get(f, f) for f in why]})
                if got:
                    f.write(json.dumps({"verse": v, "stamps": got}, ensure_ascii=False) + "\n")
        print(f"applied {len(sig)} stamps to {len(verses):,} verses")
        return
    res = collections.defaultdict(lambda: [0, 0, 0])      # stamp -> tp, fp, fn
    sigs = {}
    for k in (0, 1):
        tr = [v for v in verses if v.split(".")[0] in half[k]]
        te = [v for v in verses if v.split(".")[0] not in half[k]]
        sig = train(tr, feats, labels, stamps)
        sigs[k] = sig
        for s, w in sig.items():
            t = threshold(tr, feats, labels, s, w)
            for v in te:
                pred, gold = score(v, feats, w) >= t, s in labels.get(v, ())
                res[s][0] += pred and gold
                res[s][1] += pred and not gold
                res[s][2] += gold and not pred
    rowsout = []
    for s in stamps:
        tp, fp, fn = res[s]
        p = tp / (tp + fp) if tp + fp else 0
        r = tp / (tp + fn) if tp + fn else 0
        f1 = 2 * p * r / (p + r) if p + r else 0
        rowsout.append((s in themes, f1, s, count[s], p, r))
    rowsout.sort(key=lambda x: (not x[0], -x[1]))
    print(f"{len(verses):,} verses, {sum(1 for v in verses if labels.get(v)):,} carry a stamp; "
          f"{len(stamps)} stamps with {MIN_VERSES}+ verses")
    print("held-out books, against Flash (medium+):")
    for th, f1, s, n, p, r in rowsout:
        print(f"  {'T' if th else ' '} {s:32} verses {n:5}  P {p:.2f}  R {r:.2f}  F1 {f1:.2f}")
    allf = [x[1] for x in rowsout]
    print(f"median F1 {sorted(allf)[len(allf) // 2]:.2f}; themes "
          f"{sorted(x[1] for x in rowsout if x[0])[sum(1 for x in rowsout if x[0]) // 2]:.2f}")
    for s in ("sacrifice", "temple_presence", "judgment", "mercy_restoration", "redemption_in_christ"):
        w = sigs[0].get(s) or sigs[1].get(s) or {}
        top = sorted(w, key=lambda f: -w[f])[:12]
        print(f"  {s}: " + ", ".join((f[1:] if f[0] == "@" else gloss.get(f, f)) for f in top))


if __name__ == "__main__":
    main()
