"""P-2026-11-19-2's pilot, on DeepSeek (Doug, 2026-11-21: "keep tokens low but make sure DeepSeek is working"; the Mac
bench showed the Mac is not the finder). The pairs of cards that share two or more claims with no relation either
way ("Also spoken of with"), concept-concept left out, written in the zero-relation pass's card format so its brief
builder, runner and mechanical check are reused as they are: each pair is a "card" (one end) with one candidate (the
other end) and the shared claims' verses.

    python -X utf8 tools/pending/pairs_export.py   -> <scratch>/pairs_cand.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "pairs" / "pairs_cand.json"
d = S.load()
seen, cards = set(), []
for k, e in sorted(d["ents"].items()):
    if e.get("type") not in S.BRIDGE_KINDS or e.get("alias_of"):
        continue
    b = S.graph_bridges(d, k)
    for it in (b or {}).get("items", []):
        o = it.get("id")
        pair = tuple(sorted((k, o)))
        if not o or pair in seen or len(it.get("via") or []) < 2:
            continue
        if e.get("type") == "concept" and it.get("type") == "concept":
            continue
        seen.add(pair)
        verses, refs = [], set()
        for v in it["via"]:
            if v.get("ref") and v["ref"] not in refs:
                refs.add(v["ref"]); verses.append({"ref": v["ref"], "text": v.get("text") or ""})
        cards.append({"id": k, "type": e["type"], "name": e.get("name", k), "verses": verses[:6],
                      "candidates": [{"id": o, "type": it.get("type"), "name": it.get("name", o)}]})
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(cards), "pairs ->", OUT)
