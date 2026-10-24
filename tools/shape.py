"""Node shape: the sequence of moves a passage makes, independent of subject.

2026-09-14: the best matches were being found from the stamps, but there
should be similarities in the node structure as well; the stamps were intended
to be locating signals.

Everything built today matched on stamps alone -- signatures, seeded mining,
five ranking measures. That treats the stamps as the pattern, and they were
never meant to be. **A stamp says where to look. A shape is what is found.**

## What a shape is

`out/sentence-function.jsonl.gz` types all 31,224 sentences by what they DO,
from evidence and with no subject matter in it at all:

    direction   backward 14,843   free 10,199   sequence 4,975
                forward 776       internal 431
    act         assertion 25,339  command 2,119  question 374  wish 21

A node's shape is that sequence, in order. Psalm 103:1-5 and a passage in
Isaiah can carry entirely different stamps and make the same series of moves;
two judgment oracles can share every stamp and be shaped nothing alike.

## Why sequence and not a bag

Order is most of what a shape is. `question -> assertion -> command` is a
diatribe move; `command -> assertion -> question` is not, and a bag of traits
cannot tell them apart. So shapes are compared as SEQUENCES, by their longest
common subsequence, normalised by the longer of the two.

## The division of labour this restores

    stamps    locate candidates        -- cheap, recall-oriented, about subject
    shape     confirm or reject them   -- about form, and blind to subject

That is the propose/veto asymmetry the project already runs on, applied to
the thing it was actually meant for. A pattern found by both is a pattern in
two independent registers at once.

    python tools/shape.py --of Rom.2.1
    python tools/shape.py --of Gen.6.13 --among judgment_ev,prophetic_word
"""
from __future__ import annotations

import argparse
import collections
import difflib
import gzip
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"


def shapes():
    """-> {section ref: [move...]} the ordered moves inside each section."""
    # section boundaries, from the same structure file the stamping used
    bounds = []
    with gzip.open(OUT / "structure.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d) or d.get("level") != "section":
                continue
            if "engbsb" not in (d.get("by") or []):
                continue
            b, c, v = d["ref"].split(".")
            bounds.append((b, int(c), int(v)))
    bounds.sort()

    per = collections.defaultdict(list)
    with gzip.open(OUT / "sentence-function.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            b, c, v = d["ref"].split(".")
            key = (b, int(c), int(v))
            owner = None
            for t in bounds:
                if t[0] == b and t <= key:
                    owner = t
                elif owner and t > key:
                    break
            if owner is None:
                continue
            # the move itself: what it does, and which way it binds
            # act+direction alone is too coarse: 85% of sentences are
            # assertion/backward, so every narrative section looked identical
            # and whole-shape similarity returned 0.857 for eight unrelated
            # passages. The relation is what separates a move from its
            # neighbour.
            move = "{}/{}/{}".format((d.get("act") or "-")[:3],
                                     (d.get("direction") or "-")[:4],
                                     (d.get("relation") or "-")[:4])
            per[f"{owner[0]}.{owner[1]}.{owner[2]}"].append(move)
    return per


def motifs(seqs, corpus, lo=2, hi=5, minshare=2):
    """Shared move-sequences among candidates, built from the bottom up.

    2026-09-14: look for the existence of shared patterns within the
    candidates, starting at the lower level and working up.

    Comparing whole shapes averages the distinctive part away -- two passages
    that make the same three-move turn in the middle of otherwise different
    material score as unrelated. So this looks for the TURN, not the passage:
    every contiguous run of `lo` moves that several candidates share, then
    every run of `lo+1` built only from those that survived, and upward until
    nothing does.

    Ranked by how much rarer the motif is inside the candidates than in the
    corpus at large, which is the same lift the stamp mining uses, applied to
    sequence rather than to set.
    """
    def grams(seq, n):
        return {tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)}

    alive, out = None, []
    for n in range(lo, hi + 1):
        here = collections.Counter()
        for s in seqs:
            for g in grams(s, n):
                if alive is None or g[:-1] in alive or g[1:] in alive:
                    here[g] += 1
        keep = {g for g, c in here.items() if c >= minshare}
        if not keep:
            break
        base = collections.Counter()
        for s in corpus:
            for g in grams(s, n):
                if g in keep:
                    base[g] += 1
        for g in keep:
            inside = here[g] / len(seqs)
            outside = base[g] / max(len(corpus), 1)
            if outside and inside > outside:
                out.append((inside / outside, n, here[g], g))
        alive = keep
    out.sort(reverse=True)
    return out


def similar(a, b):
    """Longest common subsequence, normalised. Order is most of a shape."""
    if not a or not b:
        return 0.0
    m = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    return 2.0 * sum(x.size for x in m.get_matching_blocks()) / (len(a) + len(b))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--of", required=True, help="section ref, e.g. Rom.2.1")
    ap.add_argument("--among", default="",
                    help="restrict to sections carrying these stamps")
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()

    per = shapes()
    if a.of not in per:
        near = [r for r in per if r.startswith(a.of.split(".")[0] + ".")][:8]
        raise SystemExit(f"no shape for {a.of}. e.g. {', '.join(near)}")

    pool = set(per)
    if a.among:
        want = {x.strip() for x in a.among.split(",")}
        src = OUT / "stamps-leveled.jsonl"
        got = collections.defaultdict(set)
        for line in src.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                got[d["ref"]].add(d["id"])
        pool = {r for r in pool if want <= got.get(r, set())}
        print(f"stamps located {len(pool)} candidates; ranking them by shape\n")

    me = per[a.of]
    print(f"{a.of}  {len(me)} sentences")
    print("  shape: " + " ".join(me[:14]) + (" ..." if len(me) > 14 else ""))

    cand = sorted(pool)
    seqs = [per[r] for r in cand]
    corpus = [per[r] for r in per]
    found = motifs(seqs, corpus)
    print(f"\n  shared motifs among {len(cand)} candidates, "
          f"built up from pairs:")
    seen = set()
    for lift, n, cnt, g in found[:a.top]:
        if g[:2] in seen:
            continue
        seen.add(g[:2])
        where = [r for r in cand
                 if any(tuple(per[r][i:i + n]) == g
                        for i in range(len(per[r]) - n + 1))]
        print(f"    {lift:5.1f}x  n={n}  in {cnt}/{len(cand)}   "
              + " -> ".join(g))
        print(f"            {', '.join(where[:6])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
