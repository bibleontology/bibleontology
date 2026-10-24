"""Lift verse-local edges to claims about things that outlive the verse.

The audit measured the parser reproducing **4.3%** of the legacy graph, and
found the reason: its nodes are word occurrences in one verse, so a `fathered`
edge says *this token and that token are joined by a fathering verb in Gen 10:8*
rather than *Cush is the father of Nimrod*. `tools/referents.py` supplied the
missing identity; this consumes it.

    verse-local edges                261,387
      both ends belong to a referent   2,513   1.0%

One percent looks small and is the honest ceiling of the current referent layer:
it covers 40,428 of 231,876 occurrences, and an edge needs BOTH ends inside it.
The share rises as the referent layer does, and nothing here has to change when
it does.

## What is emitted, and what is deliberately not

A canon-scoped edge carries the verses it was seen in and how often, so a claim
made once in one verse never looks like a claim made nine times across a book.
**The edge type is the verb MACULA found, not an interpretation of it** --
`fathered` stays `fathered` rather than becoming `father_of`, because mapping a
surface verb onto a curated relation type is the reasoning the legacy graph
did, and asserting it here would be claiming the overlay's work as the floor's.

What this gives is the thing the floor could not previously state at all: **a
relation between two things rather than between two words.**
"""
from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "referent-edges.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

# Surface verbs that state a parent-child link. Used ONLY to score against the
# legacy graph's `father_of`, never to relabel an edge.
KINSHIP = {"fathered", "begat", "bore", "bare", "gaveBirth"}


def skeleton(name: str) -> str:
    """A name reduced to its consonants, so two spellings of it match.

    The first scoring run called ten of twenty-two kinship edges disagreements.
    None of them were: they were the KJV's spelling against MACULA's
    transliteration of the same Hebrew --

        ours    enosh  kenan   mahalalel   methushael
        legacy  Enos   Cainan  Mahalaleel  Methusael

    Hebrew names vary in their vowels and not in their consonants, so dropping
    the vowels and normalising the few consonants English writes two ways is
    enough to see that these are one person each. Used ONLY for scoring; nothing
    is merged on it.
    """
    s = re.sub(r"[^a-z]", "", (name or "").lower())
    s = s.replace("sh", "s").replace("ch", "k").replace("ph", "f")
    s = s.replace("c", "k").replace("q", "k").replace("j", "y").replace("w", "v")
    s = re.sub(r"[aeiou]", "", s)
    return re.sub(r"(.)\1+", r"\1", s)


def load_referents():
    node2ref, meta = {}, {}
    with gzip.open(OUT / "referents.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            meta[d["id"]] = d
            for nid in d["nodes"]:
                node2ref[nid] = d["id"]
    return node2ref, meta


def build(node2ref):
    agg = collections.defaultdict(lambda: {"n": 0, "refs": []})
    with gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            if any(k.startswith("_") for k in e):
                continue
            a, b = node2ref.get(e["src"]), node2ref.get(e["dst"])
            if not (a and b) or a == b:
                continue
            k = (a, e["type"], b)
            agg[k]["n"] += 1
            if e["ref"] not in agg[k]["refs"]:
                agg[k]["refs"].append(e["ref"])
    return agg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--show", type=int, default=10)
    a = ap.parse_args()

    node2ref, meta = load_referents()
    agg = build(node2ref)
    print(f"referents {len(meta)}   canon-scoped edges {len(agg)}\n")

    types = collections.Counter(k[1] for k in agg)
    print("edge types:")
    for t, n in types.most_common(12):
        print(f"   {n:6} {t}")

    # --- score the kinship subset against the legacy graph -----------------
    ents, rels = {}, []
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            ents[e["id"]] = e
    for f in sorted(glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            if line.strip():
                rels.append(json.loads(line))

    REFP = re.compile(r"^\s*(\S+?)[\s.](\d+)[:.](\d+)\s*$")

    def nref(r):
        m = REFP.match(str(r))
        return f"{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else ""

    legacy = collections.defaultdict(set)     # verse -> {(parent, child) names}
    for r in rels:
        if r["type"] != "father_of":
            continue
        s, d = ents.get(r["src"]), ents.get(r["dst"])
        if not (s and d):
            continue
        for x in r.get("refs", []):
            v = nref(x)
            if v:
                legacy[v].add((skeleton(s["name"]), skeleton(d["name"])))

    ours = [(k, v) for k, v in agg.items() if k[1] in KINSHIP]
    agree = disagree = unseen = 0
    examples = []
    for (a_id, t, b_id), v in ours:
        an, bn = skeleton(meta[a_id]["name"]), skeleton(meta[b_id]["name"])
        hit = None
        for verse in v["refs"]:
            for (p, c) in legacy.get(verse, ()):
                if an and bn and (an in p or p in an) and (bn in c or c in bn):
                    hit = verse
                    break
            if hit:
                break
        if hit:
            agree += 1
            if len(examples) < a.show:
                examples.append(("agrees", hit, an, bn))
        elif any(verse in legacy for verse in v["refs"]):
            disagree += 1
            if len(examples) < a.show:
                examples.append(("differs", v["refs"][0], an, bn))
        else:
            unseen += 1

    print(f"\nkinship edges emitted: {len(ours)}")
    print(f"  the legacy graph says the same in that verse   {agree}")
    print(f"  it has a father_of there, but a different pair  {disagree}")
    print(f"  it makes no father_of claim in that verse       {unseen}"
          f"   <- new, and the point of the exercise")
    for tag, verse, an, bn in examples:
        print(f"    {tag:8} {verse:12} {an[:18]:20} -> {bn[:20]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0

    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": CREDIT,
            "_note": "Verse-local edges lifted to referents. The type is the "
                     "verb MACULA found, never a curated relation type -- "
                     "mapping one onto the other is the overlay's reasoning.",
        }, ensure_ascii=False) + "\n")
        for (s, t, d), v in sorted(agg.items()):
            f.write(json.dumps({"src": s, "type": t, "dst": d,
                                "n": v["n"], "refs": v["refs"]},
                               ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(agg)} edges)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
