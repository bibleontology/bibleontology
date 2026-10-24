"""Persist the higher-level patterns and the group hierarchy as graph layers.

2026-09-14: the patterns (with types, instances, structure, stamps, and
interest indicators) and the group hierarchy are to go into the new graph.

Until now every pattern in this project was computed and thrown away.
`patterns.py` ranks them, `arc.py` finds stage sequences, `shape.py` finds
motifs, and none of it leaves anything behind with an identity. A reader
cannot link to a computation, so nothing in `docs/PATTERNS-IN-THE-APP.md`
could be built. This writes them down.

It also answers the complaint `docs/PATTERN-TYPES.md` opens with: the graph
holds **35,613 pattern nodes and every one is subsentence** -- clause forms
and predicate formulas. The `pattern` kind and the `instance_of` edge already
exist and work; nothing above the clause had ever used them.

## Stable ids, which is the part that matters

    pat:<family>:<12 hex of sha1(family|sorted traits|level)>

**Not a hash of the instances.** Re-stamping one book would then silently
rename every pattern it touches and every saved link would break. Hashing what
DEFINES the pattern -- its family, its traits, the level it was found at --
is stable under re-stamping, and instances changing underneath is correct: a
pattern gaining an instance is the same pattern.

## What each node carries

    family      which of the catalogue's kinds it is
    level       the unit it was found at
    stamps      the trait combination, for `thematic`
    stages      the ordered stages, for `arc`
    instances   how many, and across how many books
    scores      rarity, spread, lift -- the interest indicators, all of them,
                because the five measures disagree informatively and the app
                is to offer the sort order rather than choose one

## The group hierarchy

Sections and books are already nodes; what was missing is the edge between
them. `sec:X part_of book:Y` makes the tree walkable in both directions, which
is what "navigate up or down from a pattern" requires.

    python tools/patternnodes.py            # report
    python tools/patternnodes.py --write    # emit the layers
"""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools"))


def pid(family, traits, level):
    """Stable across re-stamping: keyed on what defines the pattern."""
    key = f"{family}|{'+'.join(sorted(traits))}|{level}"
    return f"pat:{family}:{hashlib.sha1(key.encode()).hexdigest()[:12]}"


def thematic(sec, order, cites, minsup=25, maxk=4, top=600):
    """Trait combinations, ranked by rarity x spread -- the measure that worked."""
    import patterns as P
    units = [([r], sec[r]) for r in order]
    N = len(units)
    base = collections.Counter()
    for _r, ids in units:
        base.update(ids)
    idf = {x: math.log(N / df) for x, df in base.items() if df}
    corr = P.correlations(units, set(base))
    sets = P.closed(P.frequent(units, minsup, maxk))

    out = []
    for s, rows in sets.items():
        if len(s) < 2:
            continue
        exp = N
        for x in s:
            exp *= base[x] / N
        if exp <= 0:
            continue
        lift = len(rows) / exp
        refs = [order[i] for i in rows]
        books = {r.split(".")[0] for r in refs}
        if lift <= 1 or len(books) < 2:
            continue                       # one author's habit, not a pattern
        surprise = P.surprise(s, corr, w=None, idf=idf)
        score = surprise * math.log2(1 + len(books))
        out.append({"family": "thematic", "traits": sorted(s),
                    "form": sorted(s), "refs": refs,
                    "books": sorted(books),
                    "scores": {"score": round(score, 3),
                               "lift": round(lift, 2),
                               "surprise": round(surprise, 4),
                               "spread": len(books),
                               "support": len(rows)},
                    # the FORM is the trait list; the FILL is which
                    # verse in this section shows each trait. That is
                    # what makes a pattern a template rather than a
                    # label.
                    "fill": {r: [[x, cites.get((r, x), "")]
                                 for x in sorted(s)] for r in refs}})
    out.sort(key=lambda d: -d["scores"]["score"])
    return out[:top]


def arcs(sec, order):
    """Ordered stage sequences -- the family-1 patterns, one node per arc kind."""
    import arc as A
    out = []
    for name, stages in A.ARCS.items():
        hits = A.find(stages, sec, order, window=8)
        if not hits:
            continue
        refs = [h[0] for h in hits]
        books = {r.split(".")[0] for r in refs}
        out.append({"family": "arc", "traits": [s for s, _ in stages],
                    "form": [s for s, _ in stages],
                    "fill": {h[0]: [[st, r] for st, r in h[2]]
                             for h in hits},
                    "refs": refs, "books": sorted(books),
                    "arc": name,
                    "spans": [[h[0], h[1]] for h in hits[:200]],
                    "scores": {"support": len(hits), "spread": len(books),
                               "stages": len(stages)}})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--top", type=int, default=600)
    ap.add_argument("--minsup", type=int, default=25)
    a = ap.parse_args()

    src = OUT / "stamps-leveled.jsonl"
    if not src.exists():
        raise SystemExit("run: python tools/stamp.py --levels")
    sec, title = collections.defaultdict(set), {}
    cites = {}              # (section, trait) -> the verse showing it
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        sec[d["ref"]].add(d["id"])
        if d.get("cites"):
            cites.setdefault((d["ref"], d["id"]), d["cites"])
        title[d["ref"]] = d.get("title", "")
    order = sorted(sec, key=lambda r: (r.split(".")[0],
                                       *(int(x) for x in r.split(".")[1:])))
    print(f"{len(order):,} stamped sections", flush=True)

    pats = (thematic(sec, order, cites, a.minsup, top=a.top)
            + arcs(sec, order))
    for p in pats:
        p["id"] = pid(p["family"], p.get("traits", []), "section")
    byfam = collections.Counter(p["family"] for p in pats)
    print(f"patterns: {len(pats):,}   " + ", ".join(
        f"{k} {v}" for k, v in byfam.items()))
    inst = sum(len(p["refs"]) for p in pats)
    print(f"instances: {inst:,}")
    for p in pats[:5]:
        print(f"  {p['id']}  {p['scores'].get('score','-')}  "
              f"{len(p['refs'])} inst / {len(p['books'])} books  "
              + "+".join(p["traits"])[:60])

    if not a.write:
        print("\nnothing written -- pass --write")
        return 0

    # nodes and edges as a layer, in the shape buildgraph already ingests
    np_ = OUT / "pattern-nodes.jsonl.gz"
    ep = OUT / "pattern-edges.jsonl.gz"
    with gzip.open(np_, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_note": "Higher-level patterns from tools/patternnodes.py. Ids "
                     "are keyed on family+traits+level so they survive "
                     "re-stamping; instances change underneath and that is "
                     "correct. Scores are ALL the measures, because they "
                     "disagree informatively -- see docs/PATTERN-TYPES.md."}) + "\n")
        for p in pats:
            # `fill` is per-instance and belongs on the edges, not the node.
            # The node carries the FORM; the edges carry what filled it.
            f.write(json.dumps({k: v for k, v in p.items()
                                if k not in ("refs", "fill")},
                               ensure_ascii=False) + "\n")
    with gzip.open(ep, "wt", encoding="utf-8") as f:
        f.write(json.dumps({"_note": "instance_of: a section implements a "
                                     "pattern. part_of: the group hierarchy."})
                + "\n")
        n = 0
        for p in pats:
            for r in p["refs"]:
                # the edge carries the FILL: how this instance realises the
                # form. 2026-09-14: the structure is key because it
                # becomes a form where instance data can fill in.
                f.write(json.dumps({"src": f"sec:{r}", "type": "instance_of",
                                    "dst": p["id"],
                                    "fill": (p.get("fill") or {}).get(r)},
                                   ensure_ascii=False) + "\n")
                n += 1
        # the group hierarchy: sections already exist as nodes, the edge to
        # their book did not, and "navigate up or down" needs it
        h = 0
        for r in order:
            f.write(json.dumps({"src": f"sec:{r}", "type": "part_of",
                                "dst": f"book:{r.split('.')[0]}"}) + "\n")
            h += 1
    print(f"\n  -> {np_.relative_to(ROOT)}  {len(pats):,} pattern nodes")
    print(f"  -> {ep.relative_to(ROOT)}  {n:,} instance_of + {h:,} part_of")
    print("\nadd to buildgraph.py to merge into the graph "
          "(see the module docstring)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
