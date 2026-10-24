"""Noun classes, so a signature can say what KIND of thing joined two units.

2026-09-08: patterns will work better if every thing fits in a taxonomy of
some sort, which is why the pattern graph ultimately likely incorporates
multiple taxonomies.

Measured the same day, and the number is large: signatures built from raw
lemmas recur **15%** of the time; typed to whatever classes exist, **57%**.
Verbs have 113 classes from `tools/verbclasses.py`. **Nouns have none, and they
are the bulk of every signature** -- a signature reading
`word:בֵּן, word:בַּת` matches another genealogy only if it uses the same two
words, which is the wall that scored Genesis 7 against Exodus 14 at 0.074.

## Why this starts from a better place than the verbs did

`tools/verbclasses.py` had to build its own vectors out of clause participants,
and the matrix came out at 0.62% density -- too sparse to separate meaning from
co-occurrence, which is why *receded* came back nearest to *brought*.

**`tools/senses.py` already did that work for nouns**: 6,097 sparse IDF-weighted
profiles, each with the features that discriminate it, validated by ablation at
13.2x. So this clusters an existing, tested representation rather than deriving
a worse one.

The gloss is added on top at the same weight the verbs needed, because that was
the move that took verb clusters from illegible to legible, and it was proposed
both times.

## The test this has to pass, stated before it ran

If noun classes land and signature recurrence **does not move off 18%**, then
typing is not what patterns were missing, and the 57% was an artefact of
collapsing to five coarse buckets rather than evidence for depth. Recorded
here as a rule of method -- a success criterion written after the fact
is not a test.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import itertools
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "noun-classes.json"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

GLOSS_WEIGHT = 3.0
MAX_CLUSTER = 18
STOP = set(
    "the a an of and to in on at at by for with from he she it they them his "
    "her its this that these those all out up down away back again very one "
    "who whom which what not no nor so then there here".split())


def gwords(s):
    return {w for w in re.findall(r"[a-z]+", (s or "").lower())
            if w not in STOP and len(w) > 2}


def load():
    prof = {}
    with gzip.open(OUT / "sense-profiles.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if not any(k.startswith("_") for k in d):
                prof[d["key"]] = d
    lemma = {}
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            if d.get("lemma") and d.get("strong"):
                k = ("h" if d.get("lang") == "hebrew" else "g") + \
                    str(d["strong"]).lstrip("0")
                lemma.setdefault(k, d["lemma"])
    return prof, lemma


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--threshold", type=float, default=0.22)
    ap.add_argument("--min-obs", type=int, default=5)
    ap.add_argument("--show", type=int, default=16)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    prof, lemma = load()
    keep = sorted(k for k, p in prof.items()
                  if (p.get("observations") or 0) >= a.min_obs and p.get("top"))
    print(f"sense profiles {len(prof)}, with >= {a.min_obs} observations: {len(keep)}")

    # the profile's own features, plus the gloss -- the move that rescued verbs
    vec = {}
    for k in keep:
        d = collections.Counter()
        for f in prof[k]["top"]:
            d[f"f:{f['feature']}"] = float(f["weight"])
        top = max(d.values()) if d else 1.0
        for w in gwords(prof[k].get("gloss")):
            d[f"g:{w}"] = top * GLOSS_WEIGHT / 3.0
        vec[k] = d
    NM = {k: math.sqrt(sum(x * x for x in d.values())) or 1.0
          for k, d in vec.items()}

    # blocking: only compare pairs that share a feature, or this is 18M pairs
    byfeat = collections.defaultdict(list)
    for k in keep:
        for f in vec[k]:
            byfeat[f].append(k)
    cand = set()
    for f, ks in byfeat.items():
        if len(ks) > 400:
            continue
        for x, y in itertools.combinations(sorted(ks), 2):
            cand.add((x, y))
    print(f"candidate pairs sharing a feature: {len(cand)}")

    sims = []
    for x, y in cand:
        dx, dy = vec[x], vec[y]
        if len(dx) > len(dy):
            dx, dy = dy, dx
        s = sum(w * dy.get(f, 0) for f, w in dx.items()) / (NM[x] * NM[y])
        if s >= a.threshold:
            sims.append((-s, x, y))
    sims.sort()

    parent = {k: k for k in keep}

    def find(z):
        while parent[z] != z:
            parent[z] = parent[parent[z]]
            z = parent[z]
        return z

    size = collections.Counter({k: 1 for k in keep})
    for _, x, y in sims:
        rx, ry = find(x), find(y)
        if rx == ry or size[rx] + size[ry] > MAX_CLUSTER:
            continue
        parent[ry] = rx
        size[rx] += size[ry]
    groups = collections.defaultdict(list)
    for k in keep:
        groups[find(k)].append(k)
    clusters = sorted((c for c in groups.values() if len(c) >= 2),
                      key=len, reverse=True)

    inn = sum(len(c) for c in clusters)
    print(f"clusters of 2 or more   {len(clusters)}")
    print(f"nouns inside one        {inn} ({100*inn/max(1,len(keep)):.0f}%)")
    print(f"largest                 {max((len(c) for c in clusters), default=0)}\n")
    for c in clusters[:a.show]:
        gl = sorted({(prof[k].get("gloss") or k)[:15] for k in c})
        print(f"  [{len(c):>2}] " + ", ".join(gl[:8]))

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    DEST.write_text(json.dumps({
        "_source": CREDIT,
        "_note": "Noun classes clustered from tools/senses.py profiles plus the "
                 "MACULA gloss. UNNAMED: naming a class is a ruling.",
        "threshold": a.threshold,
        "clusters": [{"id": i, "keys": c,
                      "lemmas": [lemma.get(k) for k in c],
                      "glosses": sorted({prof[k].get("gloss") for k in c
                                         if prof[k].get("gloss")})}
                     for i, c in enumerate(clusters)],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(clusters)} clusters)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
