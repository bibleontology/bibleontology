"""Pattern stamping that composes: a node's shape from its children's shapes.

2026-09-10, the reason the pair/collection distinction exists: groups of 2 or
collections keep the pattern stamping simple as it moves up -- focusing only on
the pair or the collection as it climbs the tree, and on the patterns within
the nodes being evaluated one level lower; the patterns with instance values at
the lower level simplify the job on the way up.

That is a **compositional** rule, and it is what makes climbing tractable. At
any node you look at exactly two things:

    1. this node's ARITY -- pair, chain, or collection
    2. the STAMPS of its children, one level down

Never the text, never the whole subtree. A node's stamp is a small string built
from those two facts, so the same machinery works at every height and the work
per node does not grow as the tree does.

## The stamp

    <arity>(<child stamp> x n, <child stamp> x m, ...)

    PAIR(leaf x2)                    two leaves, bound
    CHAIN(leaf x4)                   four leaves, each building on the last
    COLL(leaf x8)                    eight leaves, none bound -- a list
    COLL(PAIR(leaf x2) x3)           three bound pairs, unbound from each other
    PAIR(CHAIN(leaf x3), COLL(leaf x5))

Child stamps are counted, not ordered, so two nodes with the same shape collide
on the same stamp however their children are arranged. That collision is the
point: it is what makes a stamp a PATTERN rather than a description.

## What this does and does not claim

**Arity is measured; the levels are borrowed or missing.** Pair/chain/collection
comes from `tools/grouptree.py`'s tightness scoring, whose weights are asserted
rather than measured -- the one set of numbers in this project that has not
earned its place. Above the chapter there is almost nothing to hang the tree on:
the corpus holds **five** above-chapter marks in total, all of them the Books of
the Psalter. Book-to-scroll here is **canonical, not derived** -- a fact about
how the canon is arranged, taken as given and labelled as such.

So this climbs to the scroll, but the top two storeys are scaffolding rather
than findings, and are printed that way.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

# Canonical, not derived: how the Hebrew canon arranges its books. Taken as
# given the way the 66-book canon is taken as given elsewhere in this project.
SCROLLS = {
    "Torah": "Gen Exo Lev Num Deu",
    "Former Prophets": "Jos Jdg 1Sa 2Sa 1Ki 2Ki",
    "Latter Prophets": "Isa Jer Ezk",
    "The Twelve": "Hos Jol Amo Oba Jon Mic Nam Hab Zep Hag Zec Mal",
    "Poetry": "Psa Job Pro",
    "Megillot": "Rut Sng Ecc Lam Est",
    "Writings": "Dan Ezr Neh 1Ch 2Ch",
}
OF_SCROLL = {b: s for s, bs in SCROLLS.items() for b in bs.split()}


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


def stamp(node):
    """A node's pattern, from its arity and its children's stamps only."""
    kids = node.get("kids") or []
    if not kids:
        return "leaf"
    counts = collections.Counter(stamp(k) for k in kids)
    inner = ", ".join(f"{s} x{n}" if n > 1 else s
                      for s, n in sorted(counts.items(),
                                         key=lambda kv: (-kv[1], kv[0])))
    return f"{node.get('arity', 'COLL')}({inner})"


def arity_of(ties, pair_at):
    if not ties:
        return "UNIT"
    bound = sum(1 for t in ties if t >= pair_at)
    if bound == 0:
        return "COLL"
    if bound == len(ties):
        return "CHAIN"
    return "PAIR"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pair", type=float, default=3.0)
    ap.add_argument("--top", type=int, default=14,
                    help="how many stamps to show per level")
    a = ap.parse_args()

    marks = collections.defaultdict(dict)
    for d in load("structure.jsonl.gz"):
        p = parts(d["ref"])
        if p:
            marks[(p[0], p[1])][p[2]] = d
    sf = {}
    for d in load("sentence-function.jsonl.gz"):
        sf.setdefault(d["ref"], d)

    verses = collections.defaultdict(list)
    seen = set()
    for d in load("sentence-function.jsonl.gz"):
        p = parts(d["ref"])
        if p and d["ref"] not in seen:
            seen.add(d["ref"])
            verses[(p[0], p[1])].append(p[2])

    # ---- level 1: paragraphs inside a chapter --------------------------
    def chapter_node(bk, ch):
        vs = sorted(verses[(bk, ch)])
        if not vs:
            return None
        mk = marks[(bk, ch)]
        runs, cur = [], [vs[0]]
        for v in vs[1:]:
            if v in mk:
                runs.append(cur)
                cur = [v]
            else:
                cur.append(v)
        runs.append(cur)
        kids = [{"kids": [], "verses": r} for r in runs]
        ties = []
        for i in range(1, len(kids)):
            first = f"{bk}.{ch}.{kids[i]['verses'][0]}"
            s = sf.get(first) or {}
            ties.append(3.0 if s.get("direction") == "backward" else 0.0)
        return {"kids": kids, "arity": arity_of(ties, a.pair),
                "id": f"{bk}.{ch}"}

    chapters = {}
    for (bk, ch) in verses:
        n = chapter_node(bk, ch)
        if n:
            chapters[(bk, ch)] = n

    # ---- level 2: chapters inside a book -------------------------------
    books = {}
    for bk in sorted({b for (b, _) in chapters}):
        kids = [chapters[(bk, c)] for c in
                sorted(c for (b, c) in chapters if b == bk)]
        # a chapter binds to the previous one if its first verse attaches back
        ties = []
        for k in kids[1:]:
            first = f"{k['id']}.{k['kids'][0]['verses'][0]}"
            s = sf.get(first) or {}
            ties.append(3.0 if s.get("direction") == "backward" else 0.0)
        books[bk] = {"kids": kids, "arity": arity_of(ties, a.pair), "id": bk}

    # ---- level 3: books inside a scroll (CANONICAL, not derived) -------
    scrolls = {}
    for name, bs in SCROLLS.items():
        kids = [books[b] for b in bs.split() if b in books]
        if not kids:
            continue
        scrolls[name] = {"kids": kids, "arity": "COLL", "id": name,
                         "borrowed": True}

    def report(level, nodes, note=""):
        c = collections.Counter(stamp(n) for n in nodes)
        ar = collections.Counter(n.get("arity") for n in nodes)
        print(f"\n{'='*74}\n{level}   {len(nodes)} nodes{note}\n{'='*74}")
        print(f"  arity: {dict(ar)}")
        print(f"  distinct stamps: {len(c)}   "
              f"most common covers {100*c.most_common(1)[0][1]/len(nodes):.0f}%")
        for s, n in c.most_common(a.top):
            print(f"    {n:>5}  {s[:96]}")

    report("PARAGRAPH GROUPS INSIDE A CHAPTER", list(chapters.values()))
    report("CHAPTERS INSIDE A BOOK", list(books.values()))
    report("BOOKS INSIDE A SCROLL", list(scrolls.values()),
           "   <- CANONICAL, borrowed not derived")

    print(f"\n{'='*74}\nTHE CLIMB, one scroll\n{'='*74}")
    t = scrolls.get("Megillot")
    if t:
        print(f"  Megillot   {stamp(t)[:150]}")
        for b in t["kids"]:
            print(f"    {b['id']:<5} {b['arity']:<6} {len(b['kids'])} chapters"
                  f"   {stamp(b)[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
