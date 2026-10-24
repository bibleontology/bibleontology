"""What the concept cards show today, section by section (2026-10-09).

The requirement: with the facelift, not much substance may be lost over what
exists today. Before the face-lift is built, the
inventory of every section a concept card's answer (api_entity) carries, and
how many of the cards have something in it -- the list the new template must
carry, move, or retire by name. tests will check it card by card.

    python tools/concepts/inventory.py   -> out/concept-inventory.json
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

SKIP = {"found", "id", "name", "addr", "type", "label", "total_relations", "types"}


def filled(v):
    if v is None or v is False:
        return False
    if isinstance(v, (list, dict, str)):
        return len(v) > 0
    if isinstance(v, (int, float)):
        return v != 0
    return True


def main():
    d = S.load()
    ids = [eid for eid, e in d["ents"].items()
           if e.get("type") == "concept" and not str(eid).startswith("theme_")]
    have = collections.Counter()
    sizes = collections.defaultdict(list)
    richest = []
    rel_kinds = collections.Counter()
    for eid in ids:
        c = S.api_entity(d, {"id": [eid]})
        if not c.get("found"):
            continue
        n_secs = 0
        for k, v in c.items():
            if k in SKIP or not filled(v):
                continue
            have[k] += 1
            n_secs += 1
            if isinstance(v, (list, dict)):
                sizes[k].append(len(v))
        for g in c.get("groups") or []:
            rel_kinds[g.get("label") or g.get("kind") or str(g)[:30]] += 1
        richest.append((n_secs, eid, c.get("name")))
    rows = [{"section": k, "cards": n, "share": round(n / len(ids), 3),
             "median_size": sorted(sizes[k])[len(sizes[k]) // 2] if sizes[k] else None,
             "max_size": max(sizes[k]) if sizes[k] else None} for k, n in have.most_common()]
    richest.sort(reverse=True)
    out = {"_about": __doc__.strip().splitlines()[0], "cards": len(ids), "sections": rows,
           "relation_groups": rel_kinds.most_common(), "richest": [[n, e, nm] for n, e, nm in richest[:15]]}
    (ROOT / "out" / "concept-inventory.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(ids)} concept cards")
    for r in rows:
        print(f"  {r['section']:18} on {r['cards']:5} cards ({r['share']:.0%})  median {r['median_size']}  max {r['max_size']}")
    print("relation groups:", rel_kinds.most_common(12))
    print("richest:", [(n, nm) for n, _e, nm in richest[:10]])


if __name__ == "__main__":
    main()
