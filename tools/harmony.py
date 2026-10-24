"""One event, four witnesses: aligning the gospels into a single account.

2026-09-10, on discovering that verbal linking catches near-verbatim
synoptic parallels at 12 of 12 while missing narrative correspondences that
share no words: this should be a tool to compare and combine the narratives of
the gospels - not the primary function but an interesting one as a
consolidated event view of the Bible is taken.

## Two kinds of parallel, and why both are needed

The distinction this tool rests on was measured, not assumed:

**Verbal parallels** -- `out/allusions.jsonl.gz`, Greek lemmas in common. Caught
12 of 12 hand-picked near-verbatim sayings: *the first shall be last*, *take up
his cross*, *this is my body*. Where the evangelists report the same words, this
finds them.

**Narrative correspondence** -- the Berean editor's own `\\r` notes,
`out/xrefs.jsonl.gz`. Matthew 1:1 and Luke 3:23 are both genealogies of Jesus
and share almost nothing verbally: one runs Abraham to Jesus, the other Jesus to
Adam, with different names through the middle. No wording-based method can link
them and none should pretend to.

Neither alone builds a harmony. **Sayings travel by wording; episodes travel by
narrative.** So both are used, and each link records which kind it is.

## What a harmony node is

A connected component over gospel verses, joined by either kind of link. Its
witnesses are the gospels it touches. A component present in Matthew, Mark and
Luke is a triple tradition; one in Matthew and Luke only is the double
tradition; one gospel alone is unique material.

For each witness the node carries the **frame tuples** from
`out/frames.jsonl.gz` -- agent, predicate, patient -- so the same event can be
read side by side in the terms each evangelist chose.

## What this does not do

**It does not decide what happened.** Where witnesses differ the difference is
shown, not resolved. This project's standing rule, from `docs/PRINCIPLES.md`:
read the corpus without harmonising, and do not split or merge a node to settle
a tension the text leaves open. A harmony here means *laid alongside*, in the
sense of a synopsis, and never *reconciled*.

**Components can over-merge.** Two events joined through a shared stock phrase
land in one component. Component size is reported so that shows.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "harmony.jsonl.gz"
GOSPELS = ("Mat", "Mrk", "Luk", "Jhn")


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


def book(r):
    return str(r).split(".")[0]


class Union:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min-idf", type=float, default=20.0,
                    help="a verbal link weaker than this does not join")
    ap.add_argument("--max-size", type=int, default=60,
                    help="report components larger than this as over-merged")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    u = Union()
    kinds = collections.defaultdict(set)
    verbal = editorial = 0

    for d in load("allusions.jsonl.gz"):
        if book(d["ref"]) not in GOSPELS:
            continue
        for L in d["links"]:
            if book(L["ref"]) in GOSPELS and L["idf"] >= a.min_idf:
                u.join(d["ref"], L["ref"])
                kinds[d["ref"]].add("verbal")
                kinds[L["ref"]].add("verbal")
                verbal += 1

    for r in load("xrefs.jsonl.gz"):
        if book(r["from"]) in GOSPELS and book(r["to"]) in GOSPELS:
            b, c, v1 = r["to"].split(".")
            _, _, v2 = r["to_end"].split(".")
            for v in range(int(v1), min(int(v2), int(v1) + 40) + 1):
                u.join(r["from"], f"{b}.{c}.{v}")
            kinds[r["from"]].add("editorial")
            editorial += 1

    comp = collections.defaultdict(set)
    for x in list(u.p):
        comp[u.find(x)].add(x)

    frames = collections.defaultdict(list)
    for f in load("frames.jsonl.gz"):
        if book(f["ref"]) in GOSPELS:
            frames[f["ref"]].append(f)

    nodes = []
    for root, members in comp.items():
        wit = collections.defaultdict(list)
        for m in members:
            wit[book(m)].append(m)
        nodes.append({
            "id": f"ev{len(nodes):04d}",
            "witnesses": sorted(wit),
            "n_witnesses": len(wit),
            "verses": {k: sorted(v, key=lambda r: (int(r.split('.')[1]),
                                                   int(r.split('.')[2])))
                       for k, v in sorted(wit.items())},
            "size": len(members),
        })
    nodes.sort(key=lambda n: (-n["n_witnesses"], -n["size"]))

    print(f"joins: {verbal:,} verbal, {editorial:,} editorial")
    print(f"components: {len(nodes):,}")
    byw = collections.Counter(n["n_witnesses"] for n in nodes)
    print(f"\n  by number of gospels attesting:")
    for k in sorted(byw, reverse=True):
        label = {4: "all four", 3: "triple tradition",
                 2: "two gospels", 1: "one gospel only"}.get(k, str(k))
        print(f"    {k}  {label:<18} {byw[k]:>5} components")

    big = [n for n in nodes if n["size"] > a.max_size]
    print(f"\n  components larger than {a.max_size} verses "
          f"(likely over-merged): {len(big)}")
    if big:
        print(f"    largest is {big[0]['size']} verses across "
              f"{big[0]['n_witnesses']} gospels")

    print(f"\n{'='*74}\nEVENTS ATTESTED BY ALL FOUR, smallest first\n{'='*74}")
    four = [n for n in nodes if n["n_witnesses"] == 4 and n["size"] <= 24]
    four.sort(key=lambda n: n["size"])
    for n in four[:6]:
        print(f"\n  {n['id']}  {n['size']} verses")
        for g in GOSPELS:
            vs = n["verses"].get(g) or []
            if not vs:
                continue
            tup = []
            for r in vs[:3]:
                for f in frames.get(r, [])[:1]:
                    ag = ", ".join(f.get("agent") or []) or "-"
                    pa = ", ".join(f.get("patient") or []) or "-"
                    tup.append(f"({ag} | {f.get('gloss')} | {pa})")
            print(f"    {g}  {', '.join(vs[:5])}"
                  f"{'  ' + ' '.join(tup) if tup else ''}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_note": "Gospel passages joined into events by VERBAL links "
                     "(shared Greek lemmas, out/allusions.jsonl.gz) and "
                     "NARRATIVE links (the Berean editor's parallel-passage "
                     "notes, out/xrefs.jsonl.gz). Sayings travel by wording, "
                     "episodes travel by narrative, and neither alone builds a "
                     "harmony. Laid alongside, never reconciled: where the "
                     "witnesses differ the difference is shown, not resolved.",
        }, ensure_ascii=False) + "\n")
        for n in nodes:
            f.write(json.dumps(n, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(nodes)} events)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
