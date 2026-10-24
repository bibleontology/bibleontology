"""Group in pairs, mint the pattern each pairing implements, repeat.

2026-09-08, and it is a different algorithm from `tools/grouper.py`: group
signatures are more likely to occur if each grouping is limited to groups of two
or collections of similar patterns, and it should be natural to find patterns at
all levels if the matching is minted anew every time a group is made.

And the model behind it:

> *"every node of greater than one implements a pattern and all patterns fit in
> a pattern graph which might be a taxonomy if that is rich enough or possibly a
> graph holding multiple taxonomies."*

## Why this differs from the grouper that failed

`tools/grouper.py` merged greedily to arbitrary sizes against a **fixed** set of
features, and measured out at barely above chance -- Genesis 0.252 against a
0.177 random baseline. Two things were wrong with it and this version fixes
both.

**Pairs, not runs.** A merge of two units has a signature small enough to recur.
A merge of nine has a signature that occurs once, which is why the earlier
attempt found no repeated structure to lean on.

**The features grow.** Every pairing MINTS the reason it happened -- the shared
lemma, the continued subject, the closed speech -- and that minted signature
becomes a feature the next round can match on. So grouping and patterns lift
each other instead of grouping consuming a frozen list. *"All ships rise
together."*

## What a level looks like

One round takes the current sequence of units and does three things:

1. score every adjacent PAIR
2. take a maximal non-overlapping set of the best pairs, so no unit is merged
   twice in a round and the tree stays binary
3. mint a signature for each merge, and add it to the feature vocabulary

Repeat until nothing scores above the floor. What comes out is a binary tree
whose every internal node carries the pattern it implements, which is the
intended model rather than a byproduct of it.

## What this does not do

It does not name a level, and it does not claim the tree is the right reading.
It says where the text repeats itself and at what scale, which is the only part
that is mechanical.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "grown-groups.json"

# A signature has to be small to recur. These are the facts a pairing can be
# made of, and each is a fact about the JOIN rather than about either side.
MIN_SCORE = 2.0
MAX_ROUNDS = 12


def load(book):
    """Verse units for one book, with the features a pairing can rest on."""
    lem = collections.defaultdict(set)
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            if d.get("lemma") and d.get("class") in ("noun", "adj", "verb"):
                lem[d["ref"]].add(d["lemma"])

    refs = collections.defaultdict(set)
    p = OUT / "referents.jsonl.gz"
    if p.exists():
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                if any(k.startswith("_") for k in d):
                    continue
                for v in d["verses"]:
                    refs[v].add(d["id"])

    subj, ev = {}, collections.defaultdict(list)
    ep = OUT / "events.jsonl.gz"
    if ep.exists():
        with gzip.open(ep, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                if any(k.startswith("_") for k in d):
                    continue
                ev[d["ref"]].append(d)
                s = (d.get("participants") or {}).get("s") or []
                if s:
                    subj.setdefault(d["ref"], s[0])

    seq = []
    for ref in sorted(lem, key=lambda r: _key(r) or ("", 0, 0)):
        k = _key(ref)
        if not k or k[0] != book:
            continue
        seq.append({"id": ref, "c": k[1], "v": k[2], "members": [ref],
                    "lemmas": set(lem[ref]), "refs": set(refs.get(ref, ())),
                    "subject": subj.get(ref),
                    "verbs": {e["lemma"] for e in ev.get(ref, []) if e.get("lemma")},
                    "sig": frozenset(), "level": 0})
    return seq


def _key(ref):
    p = ref.split(".")
    try:
        return (p[0], int(p[1]), int(p[2]))
    except (IndexError, ValueError):
        return None


def signature(a, b):
    """WHY these two joined, as a small set of facts that can recur.

    The signature is the point of the exercise. It is not a score -- it is the
    reason, in a form the next round can match on, so that two pairs which
    joined for the same reason look alike even in different books.
    """
    sig = set()
    shared = a["lemmas"] & b["lemmas"]
    for w in sorted(shared)[:2]:
        sig.add(f"word:{w}")
    if a["refs"] & b["refs"]:
        sig.add("same-referent")
    if a["subject"] and a["subject"] == b["subject"]:
        sig.add(f"subject:{a['subject']}")
    shared_v = a["verbs"] & b["verbs"]
    for w in sorted(shared_v)[:1]:
        sig.add(f"verb:{w}")
    if a["sig"] and a["sig"] == b["sig"]:
        sig.add("mirror")            # two units that joined the same way
    return frozenset(sig)


def score(a, b, sigcount):
    """How strong a pairing is, with a bonus for a REASON already seen.

    The bonus is the whole mechanism: a signature that has
    already justified a merge somewhere else is better evidence than one seen
    once, so the second instance of a form is easier to find than the first.
    """
    s = 0.0
    s += 1.2 * len(a["lemmas"] & b["lemmas"])
    s += 2.0 * len(a["refs"] & b["refs"])
    if a["subject"] and a["subject"] == b["subject"]:
        s += 1.5
    s += 1.0 * len(a["verbs"] & b["verbs"])
    sig = signature(a, b)
    if sig:
        s += 0.8 * sigcount.get(sig, 0)      # seen before, so more likely real
    return s


def merge(a, b, sig):
    return {"id": a["id"], "c": a["c"], "v": a["v"],
            "members": a["members"] + b["members"],
            "lemmas": a["lemmas"] | b["lemmas"],
            "refs": a["refs"] | b["refs"],
            "subject": a["subject"] or b["subject"],
            "verbs": a["verbs"] | b["verbs"],
            "sig": sig, "level": max(a["level"], b["level"]) + 1}


def grow(seq, rounds, floor, log):
    """Pair, mint, repeat. One round never merges a unit twice."""
    sigcount = collections.Counter()
    minted = []
    for rnd in range(rounds):
        pairs = []
        for i in range(len(seq) - 1):
            pairs.append((score(seq[i], seq[i + 1], sigcount), i))
        pairs.sort(reverse=True)
        used, todo = set(), []
        for sc, i in pairs:
            if sc < floor or i in used or i + 1 in used:
                continue
            used.add(i)
            used.add(i + 1)
            todo.append(i)
        if not todo:
            break
        todo.sort()
        out, skip = [], set()
        for i, u in enumerate(seq):
            if i in skip:
                continue
            if i in used and i in todo:
                sig = signature(seq[i], seq[i + 1])
                out.append(merge(seq[i], seq[i + 1], sig))
                sigcount[sig] += 1
                minted.append({"round": rnd, "sig": sorted(sig),
                               "at": seq[i]["id"],
                               "spans": len(seq[i]["members"]) + len(seq[i + 1]["members"])})
                skip.add(i + 1)
            else:
                out.append(u)
        log.append({"round": rnd, "units_before": len(seq),
                    "merges": len(todo), "units_after": len(out)})
        seq = out
    return seq, sigcount, minted


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--book", default="Gen")
    ap.add_argument("--floor", type=float, default=MIN_SCORE)
    ap.add_argument("--rounds", type=int, default=MAX_ROUNDS)
    ap.add_argument("--show", type=int, default=14)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    seq = load(a.book)
    print(f"{a.book}: {len(seq)} verse units")
    log = []
    out, sigcount, minted = grow(seq, a.rounds, a.floor, log)

    print(f"\n{'round':>6} {'units':>7} {'merges':>8} {'->':>3} {'units':>7}")
    for r in log:
        print(f"{r['round']:>6} {r['units_before']:>7} {r['merges']:>8} "
              f"{'':>3} {r['units_after']:>7}")
    print(f"\nfinal units {len(out)}, deepest level {max(u['level'] for u in out)}")

    rec = [s for s, n in sigcount.items() if n > 1]
    print(f"\nsignatures minted {len(sigcount)}, of which RECUR: {len(rec)} "
          f"({100*len(rec)/max(1,len(sigcount)):.0f}%)")
    print("\nthe reasons that recur most:")
    for s, n in sigcount.most_common(a.show):
        print(f"  {n:>4}x  {', '.join(sorted(s))[:66]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    DEST.write_text(json.dumps({
        "book": a.book, "floor": a.floor,
        "units": [{"members": u["members"], "level": u["level"],
                   "sig": sorted(u["sig"])} for u in out],
        "recurring_signatures": [{"sig": sorted(s), "n": n}
                                 for s, n in sigcount.most_common() if n > 1],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {DEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
