"""Weak cards, found by measurement (BACKLOG "Weak cards", Doug 2026-11-07: "we just need to keep identifying and
shoring up these cards").

A card is weak when the text speaks of its subject far more often than its graph does. For each card of a kind that
names a thing or an idea (concept, object, group, creature, title, covenant, being, image): the Berean verses that
use its name or one of its aliases as a phrase, against the distinct verses its relations cite. Ranked by the gap.

The word-based verse finder (api_entity_verses) cannot measure this: it keeps a card to its anchored words, and gave
"foreign gods" 3 verses where the Berean says "foreign gods" or "other gods" in dozens. The phrase is cruder (a name
like "rock" matches Peter's rock and the rock at Horeb) so the list is candidates, read before anything is built.

    python tools/meaning/weak_cards.py [N]     -> out/weak-cards.json, and the worst N printed
"""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))

KINDS = {"concept", "object", "group", "creature", "title", "covenant", "being", "image"}


def phrases(e):
    names = [e.get("name") or ""] + list(e.get("aka") or [])
    out = set()
    for n in names:
        n = re.sub(r"\s*\(.*?\)\s*", " ", n or "").strip().lower()
        if len(n) >= 4 and not n.startswith("the "):
            out.add(n)
        elif n.startswith("the ") and len(n) > 8:
            out.add(n[4:])
    return out


def main(top=40):
    import server as S
    d = S.load()
    verses = d["verses"]                       # (book, chapter, verse) -> Berean text
    text = {k: " " + v.lower() + " " for k, v in verses.items()}
    rows = []
    for eid, e in d["ents"].items():
        if e.get("type") not in KINDS:
            continue
        ps = phrases(e)
        if not ps:
            continue
        pats = [re.compile(r"\b" + re.escape(p) + r"(?:s|es)?\b") for p in ps]
        hits = [k for k, t in text.items() if any(p.search(t) for p in pats)]
        rels = d["rels"].get(eid, [])
        cited = {r for x in rels for r in (x.get("refs") or [])}
        rows.append({"id": eid, "type": e["type"], "name": e.get("name"), "phrases": sorted(ps),
                     "text_verses": len(hits), "relations": len(rels), "cited_verses": len(cited),
                     "gap": len(hits) - len(cited)})
    rows.sort(key=lambda r: -r["gap"])
    out = ROOT / "out" / "weak-cards.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    kinds = collections.Counter(r["type"] for r in rows if r["text_verses"] >= 10 and r["cited_verses"] * 4 < r["text_verses"])
    print(f"{len(rows)} cards measured; {sum(kinds.values())} whose text names them in 10+ verses and whose relations "
          f"cite under a quarter of those: {dict(kinds)}")
    for r in rows[:top]:
        print(f"{r['gap']:5} {r['text_verses']:5} {r['cited_verses']:4} {r['relations']:4}  {r['type']:8} {r['id']}"
              f"  {r['phrases'][:3]}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
