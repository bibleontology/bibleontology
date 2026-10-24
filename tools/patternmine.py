"""From seed episodes to a pattern, and from the pattern to its other participants.

2026-09-14, the whole loop: use the signatures to find the best candidates to
pattern-mine; then use a deterministic algorithm to cycle through the
lower-level patterns and find the best trait combination for the general
pattern; then check for shared lower-level pattern plus similarity across the
whole corpus, to see what other participants the pattern has.

Three stages, each doing the job it is actually good at:

1. **Signatures propose.** `signature.py` ranks the corpus against a seed and
   is cheap, fuzzy and recall-oriented. It put Sodom at rank 5 of 129 against
   the Flood without being told anything.
2. **This searches.** Given the seeds, cycle the trait combinations their
   lower-level units carry and keep the one that is most distinctive.
3. **The corpus answers.** Match that combination everywhere and see who else
   is in the pattern.

## What "best" means, and why it is not frequency

The test, from 2026-09-12: when categorizing animals, "animals with 2 eyes" is
mildly interesting and "marsupials" is really a significant grouping.

An inductive pass over four Genesis judgment episodes returned the five ids
they share, and those five select **9.9% of the corpus** -- two eyes. So the
objective here is not what the seeds share but what the seeds share **and
almost nothing else does**:

    score = how many seeds it covers, then how FEW other passages match

Rarity is the whole point. A combination covering every seed and 300 other
passages has found a genre; one covering every seed and 8 others has found a
pattern. Ties break toward fewer traits, because a rule that needs six
coincidences to fire is fitted to its examples.

## The unit problem, handled explicitly

A seed is an EPISODE -- several sections -- so its trait set is the union of
its parts, and a pattern trait need only appear somewhere inside it. Matching
that against single sections corpus-wide would compare a paragraph to a
chapter and find nothing. So the corpus is searched with **sliding windows of
the seeds' own median size**, which is the only comparison that is fair.

Cosine is NOT used for the corpus sweep. It is biased toward larger nodes --
whole Psalm 32 beats both its halves against Psalm 51 purely because more
units make a denser average -- and window matching here is a set test, which
has no such bias.

    python tools/patternmine.py --seeds Gen.3.1-Gen.3.21,Gen.4.1-Gen.4.17,\\
        Gen.6.1-Gen.9.26,Gen.18.16-Gen.19.30
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import pathlib
import statistics

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
SRC = OUT / "stamps-leveled.jsonl"


def load():
    """-> ({ref: {id}}, {ref: title}, ordered refs)."""
    if not SRC.exists():
        raise SystemExit("run: python tools/stamp.py --levels")
    sec, title = collections.defaultdict(set), {}
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        sec[d["ref"]].add(d["id"])
        title[d["ref"]] = d.get("title", "")
    order = sorted(sec, key=lambda r: (r.split(".")[0],
                                       *(int(x) for x in r.split(".")[1:])))
    return sec, title, order


def seeds(spec, order):
    """-> [[ref...]] the episodes named as START-END."""
    idx = {r: i for i, r in enumerate(order)}
    out = []
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        if a not in idx or b not in idx:
            raise SystemExit(f"not a stamped section: {a if a not in idx else b}")
        out.append(order[idx[a]:idx[b] + 1])
    return out


def windows(order, sec, size):
    """-> [(refs, ids)] every contiguous same-book window of `size` sections."""
    out = []
    for i in range(len(order) - size + 1):
        w = order[i:i + size]
        if len({r.split(".")[0] for r in w}) != 1:      # never cross a book
            continue
        out.append((w, set().union(*(sec[r] for r in w))))
    return out


def mine(sets, wins, maxk=4, need=None):
    """-> [(score...)] trait combinations, most distinctive first.

    `need` is how many seeds a combination must cover; default all of them.
    Candidates are traits carried by at least half the seeds, so one badly
    stamped episode cannot veto a real pattern -- the Flood's missing `curse`
    turned out to be a span boundary, not the text.
    """
    need = need or len(sets)
    freq = collections.Counter()
    for s in sets:
        freq.update(s)
    cand = [i for i, n in freq.items() if n >= max(2, len(sets) / 2)]
    best = []
    for k in range(1, maxk + 1):
        for combo in itertools.combinations(sorted(cand), k):
            c = set(combo)
            cover = sum(1 for s in sets if c <= s)
            if cover < need:
                continue
            hits = [w for w, ids in wins if c <= ids]
            best.append((len(hits), k, cover, combo, hits))
    # fewest corpus matches first, then fewest traits: rarity is the signal,
    # and a shorter rule that is equally rare is the less fitted one.
    best.sort(key=lambda x: (x[0], x[1]))
    return [(len(distinct(h)), k, c, combo, distinct(h)) for _n, k, c, combo, h
            in best]


def distinct(hits):
    """Merge overlapping windows UPWARD into the node they are all pointing at.

    2026-09-14, on the 1Chr run: that is when you move up the graph.

    A sliding sweep reported five separate matches -- 1Chr.19.10, 20.1, 20.4,
    21.1, 21.7 -- which are one David-and-the-census arc seen five times
    through a five-section aperture. The first version of this kept the first
    window and discarded the rest, which is wrong twice: it throws away the
    evidence, and it reports a span smaller than the thing that matched.

    **Overlap is not duplication; it is a unit boundary.** When consecutive
    windows keep matching, the pattern is bigger than the window, and the
    right response is to climb: merge them into the maximal contiguous span,
    which is the participant at its own natural size.
    """
    out = []
    for w in hits:
        if out and set(w) & set(out[-1]):
            merged = out[-1] + [r for r in w if r not in out[-1]]
            out[-1] = merged
        else:
            out.append(list(w))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", required=True,
                    help="episodes as START-END, comma separated")
    ap.add_argument("--maxk", type=int, default=4)
    ap.add_argument("--show", type=int, default=6)
    a = ap.parse_args()

    sec, title, order = load()
    eps = seeds(a.seeds, order)
    sets = [set().union(*(sec[r] for r in e)) for e in eps]
    size = int(statistics.median(len(e) for e in eps))
    wins = windows(order, sec, size)
    print(f"{len(eps)} seeds, median {size} sections, "
          f"{len(sets[0] | sets[-1])}+ traits each")
    for e, s in zip(eps, sets):
        print(f"  {e[0]:<12}..{e[-1]:<12} {len(e)} sec, {len(s)} ids  "
              f"{title[e[0]][:34]}")
    print(f"\nsweeping {len(wins):,} windows of {size} sections\n")

    ranked = mine(sets, wins, a.maxk)
    if not ranked:
        print("no combination covers every seed")
        return 1
    seedrefs = {r for e in eps for r in e}
    print(f"  {'traits':<58}{'corpus':>8}{'new':>6}")
    for n, k, cover, combo, hits in ranked[:a.show]:
        new = [w for w in hits if not (set(w) & seedrefs)]
        print(f"  {'+'.join(combo)[:56]:<58}{n:>8}{len(new):>6}")

    n, k, cover, combo, hits = ranked[0]
    new = [w for w in hits if not (set(w) & seedrefs)]
    print(f"\nbest: {' + '.join(combo)}")
    # Once overlapping windows merge upward, counting MATCHES against merged
    # windows is meaningless -- merging every window collapses each book into
    # one span, and the ratio went over 100%. Coverage is the honest measure:
    # how much of the corpus the matched passages actually occupy.
    covered = len({r for w in hits for r in w})
    print(f"  {n} passages, covering {covered:,} of {len(sec):,} sections "
          f"({100*covered/len(sec):.1f}% of the corpus)")
    print(f"  {len(new)} are outside the seeds -- the other participants:\n")
    seen = set()
    for w in new:
        b = w[0].split(".")[0]
        if (b, w[0]) in seen:
            continue
        seen.add((b, w[0]))
        print(f"    {w[0]:<14}..{w[-1]:<14} {title[w[0]][:44]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
