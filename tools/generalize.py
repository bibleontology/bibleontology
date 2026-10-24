"""Slot triage: what identifies a pattern, what characterises it, what is noise.

2026-09-10, naming the operation the climb was missing: the point is to trim
slots that can be generalized as pattern characteristics, or filtered out of
the pattern as noise, as the climb proceeds.

Three fates for every slot, decided by how it behaves across the instances that
share a shape:

    IDENTITY         constant. It is part of what the pattern IS, and two
                     patterns differing here are different patterns.
    CHARACTERISTIC   varies, but predictably -- a bounded range, a small set of
                     values. It becomes a PROPERTY of one pattern instead of
                     splitting it into many.
    NOISE            varies without structure. Dropped: carrying it would make
                     every instance its own pattern.

## Why this is necessary and not merely tidy

`tools/climb.py` produced **99 distinct stamps** for paragraph groups inside a
chapter, of which the four commonest were `PAIR(leaf x8)`, `PAIR(leaf x11)`,
`PAIR(leaf x12)` and `PAIR(leaf x5)`. Those are one pattern differing in a
count, and the count is a characteristic, not an identity. Stamping each node in
isolation can never see that.

The reason had already been given, arguing about cats: if there were only one
kind of cat in the world, say the lion, cats would not be a classification, but
only the species with males having a mane being a core characteristic.

**A generalisation exists only by comparison.** One lion yields no category. The
mane becomes a characteristic of a species only once there is another cat to
compare it against, and the same is true of a slot: nothing about a single
instance says whether its value identifies, characterises, or is noise.

## The decision rule, and why it is not a threshold to tune

For a slot observed across N instances:

    distinct == 1                       IDENTITY
    numeric, and spread is bounded      CHARACTERISTIC (range carried)
    few values covering most instances  CHARACTERISTIC (set carried)
    otherwise                           NOISE

"Few values covering most instances" is measured by **normalised entropy**: how
evenly the values spread over their own range. A slot taking three values in a
90/5/5 split is characteristic; one taking three in a 34/33/33 split carries a
third of a bit per instance and is not. This is a property of the distribution,
not a knob.

## What it does not do

**It does not name anything.** A generalised pattern is reported as its skeleton
plus its characteristics. Calling one "a paired exhortation" is a reading.

**It cannot rescue a bad grouping.** If the tree beneath is wrong the stamps are
wrong and generalising them makes tidy nonsense. `docs/BACKLOG.md` 1.1b is the
rebuild this waits on.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import re

SLOT = re.compile(r"^(.*?)\bx(\d+)\b(.*)$")


def entropy(counter):
    n = sum(counter.values())
    if n <= 1 or len(counter) <= 1:
        return 0.0
    h = -sum((c / n) * math.log2(c / n) for c in counter.values())
    return h / math.log2(len(counter))


def skeleton(stamp):
    """The stamp with every count blanked, so instances that differ only in
    counts collide."""
    return re.sub(r"\bx\d+\b", "xN", stamp)


def counts(stamp):
    return [int(x) for x in re.findall(r"\bx(\d+)\b", stamp)]


def triage(values):
    """One slot's values across instances -> (fate, detail)."""
    c = collections.Counter(values)
    if len(c) == 1:
        return "IDENTITY", next(iter(c))
    nums = [v for v in values if isinstance(v, int)]
    if len(nums) == len(values):
        lo, hi = min(nums), max(nums)
        spread = hi - lo
        # bounded when the range is small relative to how many instances there
        # are: a count wandering 5..18 over 900 nodes is a characteristic; one
        # taking 900 distinct values is an index, not a pattern
        if len(c) <= max(3, len(values) ** 0.5):
            return "CHARACTERISTIC", {"range": [lo, hi], "distinct": len(c),
                                      "median": sorted(nums)[len(nums) // 2]}
        return "NOISE", {"range": [lo, hi], "distinct": len(c)}
    h = entropy(c)
    if h <= 0.55:
        top = c.most_common(4)
        return "CHARACTERISTIC", {"values": top, "entropy": round(h, 2)}
    return "NOISE", {"distinct": len(c), "entropy": round(h, 2)}


def generalize(stamps):
    """stamps: iterable of stamp strings -> generalised pattern rows."""
    by = collections.defaultdict(list)
    for s in stamps:
        by[skeleton(s)].append(s)
    out = []
    for sk, members in by.items():
        cols = list(zip(*[counts(m) for m in members])) if members else []
        slots = []
        for i, col in enumerate(cols):
            fate, detail = triage(list(col))
            slots.append({"slot": i, "fate": fate, "detail": detail})
        out.append({"skeleton": sk, "instances": len(members), "slots": slots})
    out.sort(key=lambda r: -r["instances"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--demo", action="store_true",
                    help="run against the stamps tools/climb.py produces")
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()

    if not a.demo:
        print("nothing to do -- pass --demo, or import generalize() from here")
        return 0

    import subprocess
    import sys
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    r = subprocess.run([sys.executable, str(root / "tools" / "climb.py")],
                       capture_output=True, text=True, encoding="utf-8")
    raw = []
    section = False
    seen_rule = False
    for line in (r.stdout or "").splitlines():
        if "PARAGRAPH GROUPS" in line:
            section = True
            seen_rule = False
            continue
        if section and line.startswith("======"):
            # the header is FOLLOWED by its own closing rule; only the next
            # one after that ends the section. Breaking on the first rule read
            # zero stamps and reported "could not read".
            if not seen_rule:
                seen_rule = True
                continue
            break
        m = re.match(r"\s+(\d+)\s+(\S.*)$", line)
        if section and m and "(" in m.group(2):
            raw.extend([m.group(2).strip()] * int(m.group(1)))
    if not raw:
        print("could not read stamps from tools/climb.py output")
        return 1

    print(f"stamps read: {len(raw):,}   distinct: {len(set(raw)):,}")
    rows = generalize(raw)
    print(f"after generalisation: {len(rows)} skeletons")
    print(f"  collapse: {len(set(raw)):,} -> {len(rows)}"
          f"  ({len(set(raw))/max(len(rows),1):.0f}x fewer)")

    for r_ in rows[:a.top]:
        print(f"\n  {r_['instances']:>5} instances   {r_['skeleton'][:70]}")
        for s in r_["slots"]:
            print(f"        slot {s['slot']}  {s['fate']:<15} {s['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
