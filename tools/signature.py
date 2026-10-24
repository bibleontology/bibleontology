"""Density signatures: what a node is made of, at whatever level you ask.

2026-09-14, correcting `stamp.py --levels`: the 57 out of 66 at a book level
is not noise, it is book level after all. That 9 books have no sections that
relate to the people of God probably says something about the book, making it
just as meaningful as 9 on and 57 off. But the point is that it is part of a
signature that can be used at many levels. The real signal is density: what
percentage of sections have the toggle on? Every book and every group below
the books, at least down to the section level, has a unique signature which
can be used to look for similarity, and then it is possible to check whether
the patterns hold at the lower levels.

That is right, and `--levels` was throwing the information away. It sorted each
id into corpus/book/section and kept the label, which is a one-bit summary of
a number that was already in hand. **`people_of_god` is not "ubiquitous
therefore useless"** -- it runs from 100% of sections in Titus, Philemon,
Philippians, Obadiah and Nehemiah to **3.8% in Ecclesiastes**, 15.8% in Song
and 24% in Job. That spread is a reading of the corpus: the wisdom and
lament books are about a person before God, not a people. A tier label erases
exactly that.

So the unit here is a **density vector** -- for every id, the fraction of a
node's sections carrying it -- and it is defined identically at every level.
Two nodes are comparable whenever they have children to count.

## What that buys, and the check it comes with

Similarity between signatures proposes that two nodes are alike. That is a
hypothesis, and the corpus can test it: **if two books are similar because
they share a pattern, their sections should pair up too.** Where a book-level
resemblance does not survive the descent, it was an artifact of aggregation --
two books can average alike while agreeing nowhere. `--drill` is that test.

That is the propose/veto asymmetry this project already runs on, one level up:
the signature proposes, the lower level vetoes.

    python tools/signature.py                 # nearest neighbours, all books
    python tools/signature.py --of Rom        # what characterises one book
    python tools/signature.py --drill Ezra,Neh
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "out/stamps-leveled.jsonl"
UNIT = ["scroll"]   # set from --unit; see unitise()


# Books that are ONE work split for scroll length, and books that are one
# book holding many works. 2026-09-14: the book level is not the one to look
# at; the scroll level is. Psalm 1 has as many scrolls as 1 and 2 Chronicles
# combined.
#
# The book-level neighbour list is dominated by the signature rediscovering
# the other half of its own scroll -- 1kgs~2chr 0.951, 1sam~2sam 0.948,
# ezra~neh 0.881. That is a real validation of the method and a bad unit of
# analysis: the strongest result is an artifact of where a scribe ran out of
# hide.
#
# `out/structure.jsonl.gz` carries no scroll level, so this is STATED, not
# derived, and deliberately kept to the uncontroversial cases: the numbered
# continuations, and Psalms, whose psalm divisions are in the text itself.
# The Twelve and Luke-Acts are arguable and are left alone until decided by hand.
SCROLL = {"1sam": "Samuel", "2sam": "Samuel", "1kgs": "Kings", "2kgs": "Kings",
          "1chr": "Chronicles", "2chr": "Chronicles",
          "ezra": "Ezra-Nehemiah", "neh": "Ezra-Nehemiah",
          "1cor": "Corinthians", "2cor": "Corinthians"}


def unitise(book, ref, unit):
    """-> the node this section belongs to, at the requested granularity."""
    if unit == "book":
        return book
    if book == "ps":                      # every psalm is its own scroll
        return f"Ps{ref.split('.')[1]}"
    return SCROLL.get(book, book)


def load():
    """-> (ids, {book: {section: {id}}})."""
    if not SRC.exists():
        raise SystemExit("run: python tools/stamp.py --levels")
    per = collections.defaultdict(lambda: collections.defaultdict(set))
    ids = set()
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        per[unitise(r["book"], r["ref"], UNIT[0])][r["ref"]].add(r["id"])
        ids.add(r["id"])
    return sorted(ids), per


def density(sections, ids):
    """-> {id: fraction of these sections carrying it}. The signature."""
    if not sections:
        return {i: 0.0 for i in ids}
    c = collections.Counter()
    for s in sections.values():
        c.update(s)
    n = len(sections)
    return {i: c[i] / n for i in ids}


def cosine(a, b, ids):
    num = sum(a[i] * b[i] for i in ids)
    da = math.sqrt(sum(a[i] * a[i] for i in ids))
    db = math.sqrt(sum(b[i] * b[i] for i in ids))
    return num / (da * db) if da and db else 0.0


def neighbours(ids, per, k=3):
    sig = {b: density(secs, ids) for b, secs in per.items()}
    books = sorted(sig)
    print(f"{len(books)} books, {len(ids)} ids\n")
    print("nearest by density signature:")
    for b in books:
        near = sorted(((cosine(sig[b], sig[o], ids), o)
                       for o in books if o != b), reverse=True)[:k]
        print(f"  {b:<7} " + "   ".join(f"{o} {s:.3f}" for s, o in near))
    return 0


def profile(book, ids, per, k=14):
    """What this book is made of, and what it is unusually short of."""
    if book.lower() not in per:
        raise SystemExit(f"no stamps for {book}")
    mine = density(per[book.lower()], ids)
    allsec = {}
    for b, secs in per.items():
        allsec.update({(b, r): v for r, v in secs.items()})
    base = density({k2: v for k2, v in allsec.items()}, ids)
    lift = sorted(((mine[i] - base[i], i) for i in ids), reverse=True)
    print(f"{book}: {len(per[book.lower()])} sections\n")
    print(f"  {'id':<28}{'here':>8}{'corpus':>9}{'diff':>9}")
    for d, i in lift[:k]:
        if mine[i] == 0:
            continue
        print(f"  {i:<28}{mine[i]:>7.0%}{base[i]:>9.0%}{d:>+9.0%}")
    print("\n  unusually ABSENT:")
    for d, i in lift[-6:]:
        print(f"  {i:<28}{mine[i]:>7.0%}{base[i]:>9.0%}{d:>+9.0%}")
    return 0


def drill(pair, ids, per):
    """Does a book-level resemblance survive at section level?

    Two books can average alike while agreeing nowhere -- aggregation hides
    disagreement by construction. So the book-level score PROPOSES and this
    vetoes: for every section of A, find its best-matching section in B. If
    the resemblance is real the best matches are strong and mutual; if it was
    an artifact of averaging, they are weak and scattered.
    """
    a, b = [x.strip().lower() for x in pair.split(",")]
    for x in (a, b):
        if x not in per:
            raise SystemExit(f"no stamps for {x}")
    sa, sb = per[a], per[b]
    book = cosine(density(sa, ids), density(sb, ids), ids)
    print(f"{a} vs {b}\n  book-level signature similarity: {book:.3f}\n")

    def jac(x, y):
        return len(x & y) / len(x | y) if (x or y) else 0.0

    best = []
    for ra, va in sa.items():
        m = max(((jac(va, vb), rb) for rb, vb in sb.items()), default=(0, None))
        best.append((m[0], ra, m[1]))
    best.sort(reverse=True)
    scores = [s for s, _r, _o in best]
    strong = sum(1 for s in scores if s >= 0.5)
    print(f"  sections in {a}: {len(sa)}")
    print(f"  mean best-match Jaccard against {b}: "
          f"{sum(scores)/max(len(scores),1):.3f}")
    print(f"  sections with a strong (>=0.50) counterpart: {strong} "
          f"({100*strong/max(len(scores),1):.0f}%)\n")
    print("  strongest pairs:")
    for s, ra, rb in best[:8]:
        print(f"    {s:.2f}  {ra:<12} ~ {rb}")
    print("\n  weakest:")
    for s, ra, rb in best[-4:]:
        print(f"    {s:.2f}  {ra:<12} ~ {rb}")
    return 0


def near(node, ids, per, k=12):
    """The nodes most like this one, at whatever unit is in force."""
    key = next((x for x in per if x.lower() == node.lower()), None)
    if key is None:
        raise SystemExit(f"no node {node}. Try one of: "
                         + ", ".join(sorted(per)[:12]) + " ...")
    sig = {b: density(secs, ids) for b, secs in per.items()}
    rank = sorted(((cosine(sig[key], sig[o], ids), o)
                   for o in per if o != key), reverse=True)[:k]
    print(f"{key}: {len(per[key])} sections\n")
    for s, o in rank:
        shared = sorted(set().union(*per[key].values())
                        & set().union(*per[o].values()))
        print(f"  {s:.3f}  {o:<14} {len(per[o]):>3} sec   "
              + ", ".join(shared[:5]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--of", help="profile one book against the corpus")
    ap.add_argument("--drill", help="BOOK,BOOK -- does the likeness hold lower?")
    ap.add_argument("--unit", choices=("book", "scroll"), default="scroll",
                    help="scroll merges 1/2 splits and makes each psalm a node")
    ap.add_argument("--near", help="the nodes most like this one")
    a = ap.parse_args()
    UNIT[0] = a.unit
    ids, per = load()
    if a.near:
        return near(a.near, ids, per)
    if a.of:
        return profile(a.of, ids, per)
    if a.drill:
        return drill(a.drill, ids, per)
    return neighbours(ids, per)


if __name__ == "__main__":
    raise SystemExit(main())
