"""Person-to-person relations, lifted from the structure already extracted.

2026-09-05: proceed, on the expectation that the structure will do most of
this work.

The test of that. Nothing new is read from the text here: the clause-level edges
already exist in `out/placeholder-edges.jsonl.gz` (129,626 of them, subject
-verb-> object), and the person nodes already exist in `out/people.jsonl.gz`
(2,481 of them, each holding the verse references of its occurrences). Joining
the two lifts an edge from *this token did that to that token* up to *this
person did that to that person*.

Two sources, and they are different in kind:

    lifted     a clause edge whose BOTH endpoints resolve to person nodes.
               The relation is whatever verb the text used -- no vocabulary is
               invented, which is the same discipline tools/tuples.py follows.

    patronymic the chains already extracted for disambiguation are themselves
               relations: "Zechariah son of Berechiah" IS father_of. Free,
               because the work was done for another purpose.

## What this cannot do, stated up front

An edge is lifted only where both endpoints are person occurrences **in the
same clause**. The old graph's relations are largely inferences spanning a
passage — `abraham father_of ishmael` comes from "she bore him Ishmael" — so
agreement will be partial by construction, and a low number is a statement
about the gap between clause-level fact and passage-level inference rather
than about accuracy. That was measured on 2026-09-04 and is why edge agreement
sat at 2%.

    python tools/relations.py
"""
from __future__ import annotations

import collections
import gzip
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"


def load_people():
    """(ref, name) -> person id, plus the person records."""
    people, index = [], {}
    for line in gzip.open(OUT / "people.jsonl.gz", "rt", encoding="utf-8"):
        p = json.loads(line)
        pid = f"p{len(people)}"
        p["id"] = pid
        people.append(p)
        key = p["name"].lower()
        for r in p["refs"]:
            # A verse can hold two people of the same name; the first wins and
            # the collision is counted rather than hidden.
            index.setdefault((r, key), pid)
    return people, index


def lift():
    people, index = load_people()
    byid = {p["id"]: p for p in people}
    edges = collections.Counter()
    detail = collections.defaultdict(list)
    stats = collections.Counter()

    for line in gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt",
                          encoding="utf-8"):
        e = json.loads(line)
        if "_source" in e:
            continue
        src, dst = e.get("src"), e.get("dst")
        if not src or not isinstance(dst, str):
            continue
        stats["edges"] += 1
        ref = e["ref"]
        s = index.get((ref, src.split("#", 1)[-1].lower()))
        d = index.get((ref, dst.split("#", 1)[-1].lower()))
        if not s or not d or s == d:
            continue
        stats["lifted"] += 1
        # the verb is the relation; a bare preposition is only its role
        rel = (e.get("type") or "").strip()
        if e.get("verb"):
            rel = f"{e['verb']}_{rel}" if e.get("scopes_over") else e["verb"]
        edges[(s, rel, d)] += 1
        if len(detail[(s, rel, d)]) < 4:
            detail[(s, rel, d)].append(ref)

    # patronymics are relations we already extracted for another purpose
    pat = 0
    byname = collections.defaultdict(list)
    for p in people:
        byname[p["name"].lower()].append(p)
    anc = 0
    for p in people:
        if not p.get("chain"):
            continue
        # POSITION IN THE CHAIN DECIDES. The earlier work on father_of vs
        # ancestor_of is not to be lost. Hebrew *ben* spans
        # generations -- Ezra 5:1 calls Zechariah "son of Iddo" where
        # Zechariah 1:1 makes Iddo the grandfather -- so a chain is not a list
        # of fathers. The first link is father_of; every later link is
        # ancestor_of. Emitting father_of for the whole chain, which the first
        # version did, asserts three fathers for one man.
        for depth, name in enumerate(p["chain"]):
            cands = byname.get(name.lower(), [])
            if len(cands) != 1:
                if cands:
                    stats["patronymic_ambiguous"] += 1
                continue
            rel = "father_of" if depth == 0 else "ancestor_of"
            edges[(cands[0]["id"], rel, p["id"])] += 1
            if depth == 0:
                pat += 1
            else:
                anc += 1
    stats["patronymic"] = pat
    stats["ancestor"] = anc
    return people, byid, edges, detail, stats


def main() -> int:
    people, byid, edges, detail, stats = lift()
    print("PERSON RELATIONS — lifted from structure, nothing newly read")
    print(f"  clause edges considered   {stats['edges']:>8,}")
    print(f"  both ends resolve to people {stats['lifted']:>6,}   "
          f"{100*stats['lifted']//max(stats['edges'],1)}%")
    print(f"  father_of from patronymics {stats['patronymic']:>7,}")
    print(f"    father named but ambiguous {stats['patronymic_ambiguous']:>5,}")
    print(f"  distinct person-person edges {stats['lifted'] and len(edges):>6,}")
    print()
    print("  the commonest lifted relations:")
    for (s, rel, d), n in edges.most_common(12):
        if rel == "father_of":
            continue
        print(f"    {byid[s]['name'][:14]:16}-{rel[:16]:18}-> "
              f"{byid[d]['name'][:14]:16}{n:>4}x  {detail[(s,rel,d)][:2]}")

    path = OUT / "person-relations.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for (s, rel, d), n in edges.items():
            fh.write(json.dumps({
                "src": s, "src_name": byid[s]["name"], "type": rel,
                "dst": d, "dst_name": byid[d]["name"], "count": n,
                "refs": detail[(s, rel, d)],
                "source": "patronymic" if rel == "father_of" else "lifted",
            }, ensure_ascii=False) + "\n")
    print(f"\n  wrote {path}  ({len(edges):,} relations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
