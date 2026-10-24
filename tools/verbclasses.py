"""Verb classes from the corpus, positioned by what they sit beside and against.

The question: can the verbs be put in a vector and grouped that way, or an LLM
help once there is a manageable group of clusters? Then, decisively: include
the glossary in the equation if that helps. It helped more than
anything else tried.

## The three attempts, because the failures are the argument

**Participants only.** Two verbs are similar when they take similar subjects and
objects. Measured: 519 verbs, matrix density 0.62%, median 15 features. The
nearest neighbours of *receded* came back as *brought*, *floated*, *sent out* --
**Exodus 14's cast list**, not a class of verbs. Topical association, not sense.

**Wider context.** All content lemmas in the verse rather than only the clause's
participants. Density 0.62% -> 1.86%, and the clusters were still incoherent:
*He gave, We saw, allowed, answered, became full* in one group.

**Plus the glossary.** MACULA's English gloss of the verb itself, weighted
above context because it is direct evidence rather than circumstantial. This is
the same move that took `tools/senses.py` from 8.0x to 13.2x on ablation, and
it was proposed both times. The clusters became legible immediately:

    left off, came to rest, had peace, rested, stopped
    has delivered, plundered, rescued, taken away
    asked, searched, sought
    buried, died, judged, avenged

**The second of those is the deliverance verb class**, which is what the whole
line of work needed and could not previously see -- Genesis 7 and Exodus 14
share no verb, but *delivered* and *rescued* are one class.

## Positioning the clusters against each other

The idea: the list together and in opposition should give the looser relationships,
help position the clusters relative to each other and help bring visibility
to opposites.

So each pair of clusters gets two numbers, and they are different kinds of thing:

- **together** -- how often their verbs occur in the same chapter, above what
  their sizes predict. Loose association: what tends to happen alongside what.
- **against** -- how often their verbs appear on opposite sides of a contrast,
  from `tools/contrast.py`'s 1,071 pairs. Opposition is not weak similarity, it
  is its own relation, and the earlier deity work made the same distinction for
  identity.

## What this is for, and what it is not

It is a **proposal**. The clusters have no names and this file will not give
them any: naming a class is a ruling. What it does is reduce 1,555 verbs to
roughly a hundred groups small enough for a person -- or a model, cheaply and
once -- to name and correct.
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
DEST = OUT / "verb-classes.json"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

GLOSS_WEIGHT = 3.0     # direct evidence outranks circumstantial context
MAX_CLUSTER = 16       # a class of 30 verbs is a failure to separate
STOP = set(
    "the a an of and to in on at by for with from he she it they them him his "
    "her i you we us my your be is was were are am has have had did do does "
    "not no so then there that this these those all out up down away back "
    "again very".split())


def gloss_words(s):
    return {w for w in re.findall(r"[a-z]+", (s or "").lower())
            if w not in STOP and len(w) > 2}


def load():
    ev = []
    with gzip.open(OUT / "events.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if not any(k.startswith("_") for k in d):
                ev.append(d)
    ctx = collections.defaultdict(set)
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            if d.get("lemma") and d.get("class") in ("noun", "adj"):
                ctx[d["ref"]].add(d["lemma"])
    return ev, ctx


def contrast_pairs():
    """Verb pairs the text sets against each other, from tools/contrast.py.

    **Keyed by English gloss, not by lemma**, which is why the first join
    returned zero: that file records `{"a": "listen", "b": "spoke"}` because it
    reads MACULA's contextual English column. So the match here is on the gloss
    words a cluster carries, and only rows whose `slot` is the verb are used --
    a contrast between two adjuncts says nothing about the verbs around them.
    """
    p = OUT / "contrast-pairs.jsonl.gz"
    out = collections.Counter()
    if not p.exists():
        return out
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            if d.get("slot") != "verb":
                continue
            a, b = d.get("a"), d.get("b")
            if a and b:
                out[(str(a).lower(), str(b).lower())] += d.get("count", 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--threshold", type=float, default=0.22)
    ap.add_argument("--min-events", type=int, default=4)
    ap.add_argument("--show", type=int, default=18)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    ev, ctx = load()
    prof = collections.defaultdict(collections.Counter)
    gloss = collections.defaultdict(collections.Counter)
    n = collections.Counter()
    label, chapters = {}, collections.defaultdict(set)
    for e in ev:
        v = e.get("lemma")
        if not v:
            continue
        n[v] += 1
        label.setdefault(v, e.get("gloss") or v)
        prof[v].update(ctx.get(e["ref"], ()))
        gloss[v].update(gloss_words(e.get("gloss")))
        p = e["ref"].split(".")
        if len(p) == 3:
            chapters[v].add((p[0], p[1]))

    keep = sorted(v for v in prof if n[v] >= a.min_events)
    comb = {}
    for v in keep:
        d = collections.Counter({f"c:{f}": c for f, c in prof[v].items()})
        for w, c in gloss[v].items():
            d[f"g:{w}"] = c * GLOSS_WEIGHT
        comb[v] = d
    df = collections.Counter()
    for v in keep:
        df.update(comb[v])
    N = len(keep)
    V = {v: {f: (1 + math.log(c)) * math.log(N / (1 + df[f]))
             for f, c in comb[v].items()} for v in keep}
    NM = {v: math.sqrt(sum(x * x for x in d.values())) for v, d in V.items()}

    sims = []
    for x, y in itertools.combinations(keep, 2):
        dx, dy = V[x], V[y]
        if len(dx) > len(dy):
            dx, dy = dy, dx
        s = sum(w * dy.get(f, 0) for f, w in dx.items()) / max(1e-9, NM[x] * NM[y])
        if s >= a.threshold:
            sims.append((-s, x, y))
    sims.sort()

    parent = {v: v for v in keep}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    size = collections.Counter({v: 1 for v in keep})
    for _, x, y in sims:
        rx, ry = find(x), find(y)
        if rx == ry or size[rx] + size[ry] > MAX_CLUSTER:
            continue
        parent[ry] = rx
        size[rx] += size[ry]
    groups = collections.defaultdict(list)
    for v in keep:
        groups[find(v)].append(v)
    clusters = [sorted(c, key=lambda v: -n[v])
                for c in groups.values() if len(c) >= 2]
    clusters.sort(key=len, reverse=True)

    inn = sum(len(c) for c in clusters)
    print(f"event verbs (>= {a.min_events} events)  {len(keep)}")
    print(f"clusters of 2 or more                {len(clusters)}")
    print(f"verbs inside one                     {inn} "
          f"({100*inn/max(1,len(keep)):.0f}%)")
    print(f"largest                              "
          f"{max((len(c) for c in clusters), default=0)}\n")
    for c in clusters[:a.show]:
        print(f"  [{len(c):>2}] " + ", ".join(
            sorted({label.get(v, v)[:14] for v in c})[:8]))

    # ---- position the clusters against each other -----------------------
    cid = {v: i for i, c in enumerate(clusters) for v in c}
    together = collections.Counter()
    for x, y in itertools.combinations(range(len(clusters)), 2):
        shared = len({ch for v in clusters[x] for ch in chapters[v]} &
                     {ch for v in clusters[y] for ch in chapters[v]})
        if shared:
            together[(x, y)] = shared
    # gloss word -> the clusters that use it, so an English-keyed contrast can
    # reach a cluster of Hebrew and Greek lemmas
    by_gloss = collections.defaultdict(set)
    for i, c in enumerate(clusters):
        for v in c:
            for w in gloss_words(label.get(v, "")):
                by_gloss[w].add(i)
    against = collections.Counter()
    for (p, q), c in contrast_pairs().items():
        for i in by_gloss.get(p, ()):
            for j in by_gloss.get(q, ()):
                if i != j:
                    against[tuple(sorted((i, j)))] += c

    print(f"\ncluster pairs sharing a chapter: {len(together)}")
    print(f"cluster pairs set in contrast:   {len(against)}")
    for (i, j), c in together.most_common(6):
        li = ", ".join(sorted({label.get(v, v)[:10] for v in clusters[i]})[:3])
        lj = ", ".join(sorted({label.get(v, v)[:10] for v in clusters[j]})[:3])
        print(f"    together x{c:<4} [{li}] ~ [{lj}]")
    for (i, j), c in against.most_common(6):
        li = ", ".join(sorted({label.get(v, v)[:10] for v in clusters[i]})[:3])
        lj = ", ".join(sorted({label.get(v, v)[:10] for v in clusters[j]})[:3])
        print(f"    AGAINST  x{c:<4} [{li}] vs [{lj}]")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    DEST.write_text(json.dumps({
        "_source": CREDIT,
        "_note": "Verb classes proposed from context plus MACULA gloss. "
                 "UNNAMED on purpose: naming a class is a ruling.",
        "threshold": a.threshold, "gloss_weight": GLOSS_WEIGHT,
        "clusters": [{"id": i, "verbs": c,
                      "glosses": sorted({label.get(v, v) for v in c}),
                      "events": sum(n[v] for v in c)}
                     for i, c in enumerate(clusters)],
        "together": [{"a": i, "b": j, "chapters": c}
                     for (i, j), c in together.most_common(400)],
        "against": [{"a": i, "b": j, "contrasts": c}
                    for (i, j), c in against.most_common(200)],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(clusters)} clusters)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
