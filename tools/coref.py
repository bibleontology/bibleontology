"""Can a word occurrence be tied to the thing it names, across verses?

The gap the audit found, 2026-09-07: the parser's 231,876 nodes are **word
occurrences in one verse**, at exactly 1.00 nodes per id. `Gen.1.1#god` and
`Gen.1.2#god` are different nodes and nothing says they are the same God. The
legacy graph's 8,416 entities are canon-scoped, which is why `father_of` can
exist there and cannot here: it needs an Abraham that outlives the verse.

The aim: join nodes across the board, using the legacy as a check on the
algorithm; work out in which cases a match on words suffices and where rules to
match are needed.

So this measures the cheapest possible rule before proposing any other:

    two word occurrences are the same thing when they carry the same Strong's
    lemma

against the legacy graph as ground truth. A legacy entity names the verses it
appears in, so for each one we can ask which lemmas actually sit under it, and
whether a single lemma accounts for it.

## What the answer decides

**Concentration** -- one lemma covering nearly all of an entity's occurrences --
means lemma identity IS entity identity for that entity, and the join is free.
**Dispersion** means the entity is carried by several words, and a rule is
needed. Those are different problems and the split is expected to fall roughly
along `proper` vs `common`, which is worth confirming rather than assuming.

The reverse error matters just as much and is measured separately: one lemma
serving several distinct entities. Every Zechariah shares a lemma, and joining
on it would merge men the graph has deliberately kept apart.
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

STOPW = {
    "the", "a", "an", "of", "and", "to", "in", "on", "at", "by", "for", "with",
    "from", "his", "her", "their", "its", "this", "that", "these", "those",
    "is", "was", "were", "be", "he", "she", "it", "they", "them", "him", "who",
}

# Only these types NAME something. A `passage` called "Jacob Settles at Shechem"
# and a `text` called "the word of God" are *about* their words rather than
# named by them, so asking whether one lemma accounts for them is meaningless --
# and including them wrecks the reverse-error measurement, which reported 35
# entities sharing Jacob's lemma when 34 of them were passage titles that merely
# contain the word.
REFERRING = {
    "person", "place", "group", "object", "creature", "being", "title",
    "concept", "image", "covenant", "observance",
}


def words(s: str) -> set[str]:
    return set(re.findall(r"[a-z]+", (s or "").lower())) - STOPW


def norm_ref(r: str) -> str:
    m = re.match(r"^\s*(\S+?)[\s.](\d+)[:.](\d+)\s*$", str(r))
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else ""


def load():
    ents = {}
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            ents[e["id"]] = e
    nodes = collections.defaultdict(list)
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            nodes[d["ref"]].append(d)
    return ents, nodes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min-refs", type=int, default=2)
    ap.add_argument("--show", type=int, default=10)
    a = ap.parse_args()

    ents, nodes = load()
    print(f"legacy entities {len(ents)}   parser verses {len(nodes)}\n")

    # entity -> the lemmas found under its name, in the verses it cites
    per_type = collections.defaultdict(lambda: collections.Counter())
    conc_rows = []
    lemma_to_ents = collections.defaultdict(set)
    checked = skipped = 0

    for eid, e in ents.items():
        if e.get("type") not in REFERRING:
            continue
        refs = [norm_ref(x) for x in e.get("refs", [])]
        refs = [r for r in refs if r in nodes]
        nw = words(e.get("name", ""))
        if len(refs) < a.min_refs or not nw:
            skipped += 1
            continue
        lem = collections.Counter()
        prop = collections.Counter()
        hits = 0
        for r in refs:
            for n in nodes[r]:
                if nw & words(n.get("text", "")):
                    key = ("h" if n.get("lang") == "hebrew" else "g") + \
                          str(n.get("strong") or "?")
                    lem[key] += 1
                    prop[bool(n.get("proper"))] += 1
                    hits += 1
        if not hits:
            skipped += 1
            continue
        checked += 1
        top, topn = lem.most_common(1)[0]
        conc = topn / hits
        per_type[e["type"]][round(conc, 1)] += 1
        is_proper = prop[True] >= prop[False]
        conc_rows.append((conc, len(lem), e["type"], eid, e.get("name", ""), top,
                          is_proper))
        lemma_to_ents[top].add((e["type"], eid, is_proper))

    print(f"entities checkable  {checked}   (skipped {skipped}: too few refs, "
          f"no name word, or no lexical hit)\n")

    print("=" * 72)
    print("1. DOES ONE LEMMA ACCOUNT FOR AN ENTITY?")
    print("=" * 72)
    print("concentration = share of an entity's word hits carried by its "
          "commonest lemma\n")
    print(f"{'entity type':14} {'n':>5} {'conc>=0.9':>10} {'>=0.7':>7} "
          f"{'<0.5':>7}  median lemmas")
    for t in sorted(per_type, key=lambda x: -sum(per_type[x].values())):
        rows = [r for r in conc_rows if r[2] == t]
        n = len(rows)
        hi = sum(1 for r in rows if r[0] >= 0.9)
        mid = sum(1 for r in rows if r[0] >= 0.7)
        lo = sum(1 for r in rows if r[0] < 0.5)
        med = sorted(r[1] for r in rows)[n // 2] if n else 0
        print(f"  {t:12} {n:>5} {hi:>10} {mid:>7} {lo:>7}  {med:>6}")

    n = len(conc_rows)
    hi = sum(1 for r in conc_rows if r[0] >= 0.9)
    print(f"\n  overall: {hi} of {n} ({100*hi/max(1,n):.0f}%) are carried by a "
          f"single lemma at >=0.9")

    print()
    print("=" * 72)
    print("2. THE REVERSE ERROR: ONE LEMMA, SEVERAL ENTITIES")
    print("=" * 72)
    print("Joining on lemma would merge these. Every Zechariah shares a lemma.\n")
    shared = {k: v for k, v in lemma_to_ents.items() if len(v) > 1}
    print(f"  lemmas claimed by more than one entity: {len(shared)} "
          f"of {len(lemma_to_ents)}")
    spread = collections.Counter(len(v) for v in lemma_to_ents.values())
    print(f"  entities per lemma: "
          f"{dict(sorted(spread.items())[:8])}{' ...' if len(spread)>8 else ''}")
    worst = sorted(shared.items(), key=lambda kv: -len(kv[1]))[:a.show]
    for lem, es in worst:
        names = sorted(ents[i]["name"] for _, i, _ in es)[:5]
        print(f"    {lem:8} {len(es):>3} entities: {', '.join(n[:16] for n in names)}")

    print()
    print("=" * 72)
    print("4. THE SPLIT THAT DECIDES THE ALGORITHM: proper vs common")
    print("=" * 72)
    print("MACULA tags every word `proper` or not. If lemma identity holds for")
    print("proper nouns and fails for common ones, the rule writes itself.\n")
    for label, want in (("PROPER (names)", True), ("COMMON (kinds)", False)):
        rows = [r for r in conc_rows if r[6] is want]
        if not rows:
            continue
        n = len(rows)
        hi = sum(1 for r in rows if r[0] >= 0.9)
        # reverse error: how many of these lemmas serve >1 entity of this kind?
        lems = collections.Counter(r[5] for r in rows)
        collide = sum(c for l, c in lems.items() if c > 1)
        print(f"  {label:16} entities {n:>4}   "
              f"one lemma at >=0.9  {hi:>4} ({100*hi/n:.0f}%)")
        print(f"  {'':16} lemma shared with another entity of the same kind: "
              f"{collide} ({100*collide/n:.0f}%)")
    print("\n  a proper-noun lemma serving several entities is genuine homonymy")
    print("  (the many Zechariahs); a common-noun lemma serving several is not")
    print("  an error at all -- it is a kind with instances under it.")

    print()
    print("=" * 72)
    print("3. WHERE ONE LEMMA IS NOT ENOUGH (dispersed entities)")
    print("=" * 72)
    for conc, k, t, eid, name, top, proper in sorted(conc_rows)[:a.show]:
        print(f"  conc={conc:.2f} lemmas={k:<3} {t:10} {name[:34]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
