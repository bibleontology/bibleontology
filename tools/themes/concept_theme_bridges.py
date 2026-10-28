"""The concept-theme bridges as relations in the graph: concept -in_theme-> theme node, each backed by the verses the
theme cites that also use the concept's word.

Doug, 2026-10-25: "a lot of these concept cards are closely tied to themes and when the relationship is particularly
close there should be a strong bridge to the theme", then "they probably should be tied in the graph as well". The
pairs are ontology/concept-theme-bridges.json (by hand). in_theme is the approved kind: "a concept ... is a core
concept of a major theme". A pair the graph already ties is left alone (judgment: theme_judgment -aspect_of->
judgment, approved 2026-09-29). A pair whose theme cites no verse with the concept's word gets no relation and is
reported: nothing without scripture.

    python tools/themes/concept_theme_bridges.py            dry run
    python tools/themes/concept_theme_bridges.py --write    ontology/relations/concept-theme-bridges.jsonl
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "ontology" / "relations" / "concept-theme-bridges.jsonl"


def label(vid):
    b, c, v = vid.split(".")
    return f"{b} {c}:{v}"


def hub_verses(eid):
    p = ROOT / "out" / "concept-hubs" / f"{eid}.json"
    if not p.exists():
        return set()
    out = set()

    def walk(o):
        if isinstance(o, dict):
            for k in ("verses", "eg"):
                if isinstance(o.get(k), list):
                    out.update(x for x in o[k] if isinstance(x, str))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(json.loads(p.read_text(encoding="utf-8")))
    return out


def main():
    bridges = json.loads((ROOT / "ontology" / "concept-theme-bridges.json").read_text(encoding="utf-8"))["bridges"]
    tm = json.loads((ROOT / "out" / "theme-map.json").read_text(encoding="utf-8"))
    themes = {t["id"]: t for t in tm["themes"]}
    have = set()
    for f in (ROOT / "ontology" / "relations").glob("*.jsonl"):
        if f == OUT:
            continue
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                r = json.loads(ln)
                have.add((r.get("src"), r.get("dst")))
                have.add((r.get("dst"), r.get("src")))
    nodes = set()
    for f in (ROOT / "ontology" / "entities").glob("*.jsonl"):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                nodes.add(json.loads(ln)["id"])
    rows = []
    for eid, tids in bridges.items():
        mine = hub_verses(eid)
        for tid in tids:
            node = f"theme_{tid}"
            # a theme the map merged into an existing card has no node of its own: its node IS the card (covenant,
            # kingdom, sacrifice), so card and theme are already one node
            if node not in nodes and eid in {n["id"] for n in (themes.get(tid) or {}).get("nodes") or []}:
                print(f"  {eid:10} -> theme {tid:18} the theme's node is this card itself; already one node")
                continue
            if (eid, node) in have:
                print(f"  {eid:10} -> {node:24} already tied in the graph; left alone")
                continue
            t = themes.get(tid)
            cited = [r["id"] for c in (t or {}).get("concepts", []) for p in c["passages"] for r in p["refs"] if r.get("id")]
            both = [v for v in dict.fromkeys(cited) if v in mine]
            if not both:
                print(f"  {eid:10} -> {node:24} NO verse the theme cites uses the word: no relation")
                continue
            rows.append({"certainty": "implied", "dst": node,
                         "note": f"'{eid}' is a core concept of the major theme {t['title']}: the theme's own title names "
                                 f"it, and {len(both)} of the verses the theme cites use the word (Doug, 2026-10-25: "
                                 f"'when the relationship is particularly close there should be a strong bridge to "
                                 f"the theme'; 'they probably should be tied in the graph as well')",
                         "refs": [label(v) for v in both[:6]], "source": "concept-theme-bridges", "src": eid,
                         "type": "in_theme"})
            print(f"  {eid:10} -> {node:24} {len(both)} shared verses, cites {', '.join(label(v) for v in both[:3])}")
    if "--write" in sys.argv:
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        print(f"{len(rows)} relations -> {OUT}")
    else:
        print(f"{len(rows)} relations (dry run; --write to write)")


if __name__ == "__main__":
    main()
