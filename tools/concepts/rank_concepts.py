"""Which concept cards earn a hub, and which travel together (2026-10-09).

The request: a prioritized list of key concepts to give this treatment, from
the underlying metrics; concept clusters and concept relations are to be handled
well too. This could get pretty big, so there is a special treatment path and a
deterministic face lift path.

For every concept card, from the same rules the card itself uses (api_entity):
  uses      the uses of the Hebrew and Greek words the card lists
  books     how many books those words stand in
  edges     the card's relationships in the graph
  themes    the theme pages that point to it
  torrey    the verses Torrey's topic of the same name cites (a benchmark of
            what readers expect, out/torrey-verdicts.json)
A cluster is the concept cards whose words fall in one word family (the
graph's derivation links, _families): love with beloved; righteousness with
righteous, the righteous, justification. A hub covers a cluster.

    python tools/concepts/rank_concepts.py   -> out/concept-ranking.json
"""
from __future__ import annotations

import collections
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

OUT = ROOT / "out" / "concept-ranking.json"


def main():
    d = S.load()
    vo = S._verses_of(d)
    fam = S._families()
    tor = {}
    for r in json.loads((ROOT / "out" / "torrey-verdicts.json").read_text(encoding="utf-8")):
        tor.setdefault(re.sub(r"[^a-z]+", " ", r["topic"].lower()).strip(), r["verses"])
    concepts = [eid for eid, e in d["ents"].items()
                if e.get("type") == "concept" and not str(eid).startswith("theme_")]
    rows = {}
    for i, eid in enumerate(concepts):
        card = S.api_entity(d, {"id": [eid]})
        if not card.get("found"):
            continue
        keys = [w["key"] for w in card.get("words") or [] if w.get("key")]
        verses = set()
        for k in keys:
            verses |= set(vo.get(k, ()))
        books = {v.split(".")[0] for v in verses}
        e = d["ents"][eid]
        names = [e.get("name") or eid] + list(e.get("aka") or [])
        tv = max((tor.get(re.sub(r"[^a-z]+", " ", n.lower()).strip(), 0) for n in names), default=0)
        rows[eid] = {"id": eid, "name": e.get("name") or eid, "words": keys,
                     "uses": len(verses), "books": len(books),
                     "edges": card.get("total_relations") or 0,
                     "themes": len(card.get("mthemes") or []), "torrey": tv}
        if i % 200 == 0:
            print(f"  {i}/{len(concepts)}", flush=True)
    # clusters: concepts joined by a shared word or a word one derivation step away
    parent = {eid: eid for eid in rows}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    by_key = collections.defaultdict(list)
    for eid, r in rows.items():
        for k in r["words"]:
            by_key[k].append(eid)
            for k2, _how in fam.get(k, []):
                by_key[k2].append(eid)
    for k, es in by_key.items():
        for a in es[1:]:
            parent[find(a)] = find(es[0])
    groups = collections.defaultdict(list)
    for eid in rows:
        groups[find(eid)].append(eid)

    def score(r):
        return (math.log1p(r["uses"]) * 2 + math.log1p(r["books"]) + math.log1p(r["edges"])
                + r["themes"] * 0.5 + math.log1p(r["torrey"]))
    for r in rows.values():
        r["score"] = round(score(r), 2)
    clusters = []
    for root, es in groups.items():
        es = sorted(es, key=lambda x: -rows[x]["score"])
        lead = rows[es[0]]
        verses = set()
        for x in es:
            for k in rows[x]["words"]:
                verses |= set(vo.get(k, ()))
        clusters.append({"lead": lead["name"], "lead_id": lead["id"], "score": lead["score"],
                         "uses": len(verses), "members": [{"id": x, "name": rows[x]["name"],
                                                            "score": rows[x]["score"]} for x in es]})
    clusters.sort(key=lambda c: -c["score"])
    OUT.write_text(json.dumps({"_about": __doc__.strip().splitlines()[0], "concepts": sorted(
        rows.values(), key=lambda r: -r["score"]), "clusters": clusters}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"{len(rows)} concept cards, {len(clusters)} clusters, "
          f"{sum(1 for c in clusters if len(c['members']) > 1)} with more than one card")
    for c in clusters[:40]:
        others = ", ".join(m["name"] for m in c["members"][1:6])
        print(f"  {c['score']:5}  {c['lead'][:26]:26} {c['uses']:5} verses  {len(c['members']):3} cards  {others[:70]}")


if __name__ == "__main__":
    main()
