"""Groups as a hierarchy: the editions give the skeleton, we work inside it.

2026-09-10, after a night of watching seam detection measure at chance, the
model was changed: orient around the BSB headings first and the number of
paragraph votes second, for all translations. Grouping is then applied to break
up lowest-level paragraphs or to sequence the grouping of paragraphs that the
versions put at the same level.

**The mistake was building our signals as COMPETITORS to the editions.**
`tools/seams.py` runs a precedence ladder where a derived seam beats a BSB
paragraph break, which asks weak signals to do the hardest possible job: find a
boundary anywhere in 31,000 verses. They measured at chance because that is not
a task they can do.

## The skeleton, which needs no new measurement

    level 0   BSB section heading                1,880
    level 1   a break all five editions mark     2,950
    level 2   four agree                         1,716
    level 3   three agree                        3,717
    level 4   two agree                          1,323
    level 5   one edition only                   6,993

A break more editions mark outranks one fewer mark, so the votes ARE the
hierarchy. Nesting follows: a 1-of-5 break opens a child of the 3-of-5 unit it
sits inside.

## What we contribute, and why these two jobs are tractable

**SUBDIVIDE** a leaf paragraph, above the sentence and above a threshold.

**RELATE SIBLINGS** at one level: is a run of same-level units a flat
*collection*, or does it pair up, with some bonds tighter than others?

The second is what the twelve-psalm hand-marking was describing all along --
*"19-20 are tightly bound as are 21-22"*, *"6-7 are bound in one cause and
effect"*, *"((15-(16-17))-18)"*. Every one is a sibling relation, not a seam.
And it is a far easier discrimination: not "is there a boundary at this verse"
across the corpus, but "of these four siblings, which two are most tightly
tied."

Tightness is scored from evidence already measured, strongest first:

    attachment      a unit whose first verse points back by a connective is
                    bound to its predecessor. This is the one signal that ever
                    reproduced a structure marked by hand: Psalm 92's
                    ((((6-7)-8)-9)-10) fell straight out of it.
    shared rare     vocabulary held in common, IDF-weighted, so a shared
                    'steadfast love' counts and a shared 'the' does not.
    same opening    both units opening on one lemma -- the anaphora that binds
                    Psalm 103:20-22.

## What this does not claim

The skeleton is the editors' and is labelled as theirs. Our contribution is the
shape *within* and *between* their units, and every node says which it is.
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
OUT = ROOT / "out"
DEST = OUT / "grouptree.jsonl.gz"


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


def parts(r):
    p = str(r).split(".")
    if len(p) < 3 or not p[1].isdigit() or not p[2].isdigit():
        return None
    return p[0], int(p[1]), int(p[2])


def build(chapter_verses, marks, sf, lem, idf, dev):
    """One chapter -> a tree of units. Level 0 is a heading, 1..5 are vote
    counts descending, and a smaller number binds more strongly."""
    vs = sorted(chapter_verses)
    if not vs:
        return []

    def level(v):
        m = marks.get(v)
        if not m:
            return None
        if m.get("level") == "section":
            return 0
        a = m.get("agree", 0) or 1
        return max(1, 6 - a)          # 5 editors -> 1, 1 editor -> 5

    # cut the chapter into leaf runs, each carrying the level that opened it
    runs, cur, curlev = [], [vs[0]], level(vs[0]) if level(vs[0]) is not None else 0
    for v in vs[1:]:
        L = level(v)
        if L is None:
            cur.append(v)
        else:
            runs.append((curlev, cur))
            cur, curlev = [v], L
    runs.append((curlev, cur))

    # nest: a run of weaker level becomes a child of the last stronger one
    root = {"level": -1, "kids": [], "verses": [], "by": "chapter"}
    stack = [root]
    for lev, verses in runs:
        node = {"level": lev, "verses": verses, "kids": [],
                "by": "heading" if lev == 0 else f"{6-lev} of 5 editors",
                "title": (marks.get(verses[0]) or {}).get("title")}
        while len(stack) > 1 and stack[-1]["level"] >= lev:
            stack.pop()
        stack[-1]["kids"].append(node)
        stack.append(node)
    return root["kids"]


def tightness(a, b, ref, sf, lem, idf, dev):
    """How strongly does unit b bind to unit a, its left sibling?

    `ref` turns a verse number into the key the layers use. The first version
    took the number straight to `sf.get()`, whose keys are strings like
    "Psa.92.7", so ATTACHMENT NEVER FIRED -- the one signal that had ever
    reproduced a structure marked by hand was silently absent from every
    score.
    """
    why, s = [], 0.0
    first = b["verses"][0]
    f = sf.get(ref(first)) or {}
    if f.get("direction") == "backward":
        s += 3.0
        why.append(f"attaches ({f.get('relation') or 'connective'})")
    la = set().union(*[lem.get(ref(v), set()) for v in a["verses"]]) if a["verses"] else set()
    lb = set().union(*[lem.get(ref(v), set()) for v in b["verses"]]) if b["verses"] else set()
    sh = la & lb
    mass = sum(idf.get(x, 0) for x in sh)
    if mass >= 12:
        s += min(mass / 12.0, 2.0)
        top = sorted(sh, key=lambda x: -idf.get(x, 0))[:3]
        why.append("shares " + ", ".join(top))
    oa = [m for m in dev.get(ref(a["verses"][0]), []) if m.get("device") == "anaphora"]
    ob = [m for m in dev.get(ref(first), []) if m.get("device") == "anaphora"]
    if oa and ob and oa[0].get("lemma") == ob[0].get("lemma"):
        s += 1.5
        why.append(f"same opening {oa[0]['lemma']}")
    return round(s, 2), why


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--passage", default="Psa.103")
    ap.add_argument("--pair", type=float, default=3.0,
                    help="sibling tightness at or above this is a PAIR")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    marks = collections.defaultdict(dict)
    for d in load("structure.jsonl.gz"):
        p = parts(d["ref"])
        if p:
            marks[(p[0], p[1])][p[2]] = d
    sf = {}
    for d in load("sentence-function.jsonl.gz"):
        sf.setdefault(d["ref"], d)
    dev = collections.defaultdict(list)
    for d in load("devices.jsonl.gz"):
        dev[d["ref"]] = d["marks"]

    # THE VERSE UNIVERSE COMES FROM THE SENTENCE LAYER, not the cola layer.
    # cola.jsonl.gz is built from the Masoretic accents and is Hebrew-only, so
    # keying off it silently produced an empty tree for every New Testament
    # chapter -- Romans 3 came back blank on the first run.
    verses = collections.defaultdict(list)
    seen = set()
    for d in load("sentence-function.jsonl.gz"):
        p = parts(d["ref"])
        if p and d["ref"] not in seen:
            seen.add(d["ref"])
            verses[(p[0], p[1])].append(p[2])

    lem = {}
    for d in load("cola.jsonl.gz"):
        p = parts(d["ref"])
        if not p:
            continue
        words = set()
        for c in d.get("cola", []):
            for w in re.findall(r"[a-z]+", (c.get("gloss") or "").lower()):
                if len(w) > 3:
                    words.add(w)
        lem[d["ref"]] = words

    df = collections.Counter()
    for s in lem.values():
        df.update(s)
    N = max(len(lem), 1)
    idf = {w: math.log(N / c) for w, c in df.items()}

    print(f"chapters {len(verses)}   marked verses "
          f"{sum(len(m) for m in marks.values()):,}")

    def show(bk, ch):
        key = (bk, ch)
        vv = sorted(verses.get(key) or [])
        if not vv:
            print(f"\n{bk} {ch}: nothing indexed")
            return
        ref = lambda v: f"{bk}.{ch}.{v}"
        mk = {v: marks[key][v] for v in vv if v in marks[key]}
        tree = build(vv, mk, sf, lem, idf, dev)

        def classify(nodes):
            """The second job: is a run of same-level siblings a flat
            COLLECTION, or does it pair up with some bonds tighter than others?

            Scored, not assumed. If no sibling binds above the threshold the run
            is a collection — Proverbs 10's independent couplets are the pure
            case. If some do and some do not, the run is paired and the tie
            scores say which. If every one binds, it is a chain, which is what
            the hand-marking wrote as ((((6-7)-8)-9)-10)."""
            if len(nodes) < 2:
                return None, []
            ties = [tightness(nodes[i - 1], nodes[i], ref, sf, lem, idf, dev)[0]
                    for i in range(1, len(nodes))]
            bound = sum(1 for x in ties if x >= a.pair)
            if bound == 0:
                return "collection", ties
            if bound == len(ties):
                return "chain", ties
            return "paired", ties

        def walk(nodes, ind=0):
            kind, ties = classify(nodes)
            if kind:
                lo = min(ties) if ties else 0
                hi = max(ties) if ties else 0
                print(f"  {'  '*ind}\u2514 {len(nodes)} siblings: {kind.upper()}"
                      f"   ties {lo:.1f}\u2013{hi:.1f}")
            prev = None
            for n in nodes:
                own = n["verses"]
                # a node's SPAN reaches to the end of its last descendant; its
                # own verses are only the run before its first child. The first
                # version printed the own-run as if it were the whole unit, so
                # a 2-of-5 parent looked like it stopped where its children
                # began.
                last = n
                while last["kids"]:
                    last = last["kids"][-1]
                end = last["verses"][-1] if last["verses"] else own[-1]
                span = f"{own[0]}-{end}" if end != own[0] else str(own[0])
                lead = (f"{own[0]}-{own[-1]}" if len(own) > 1 else str(own[0]))
                tie = ""
                if prev is not None:
                    sc, why = tightness(prev, n, ref, sf, lem, idf, dev)
                    tie = (f"   ┐ PAIR {sc}  {'; '.join(why)}"
                           if sc >= a.pair else (f"   · {sc}" if sc > 0 else ""))
                title = f'  «{n["title"]}»' if n.get("title") else ""
                head = f"v{span}" + (f"  (own {lead})" if n["kids"] else "")
                print(f"  {'  '*ind}{head:<22} [{n['by']}]{title}{tie}")
                if n["kids"]:
                    walk(n["kids"], ind + 1)
                prev = n
        bar = "=" * 72
        print(f"\n{bar}\n{bk} {ch}\n{bar}")
        walk(tree)

    bk, ch = a.passage.split(".")[0], int(a.passage.split(".")[1])
    show(bk, ch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
