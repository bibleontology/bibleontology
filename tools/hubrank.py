"""Freeze the hub ranking so the reader can use it without paying for it.

2026-09-16, on the People list in the new reader: the old app's node explorer
had a good weighted formula, still served on port 8000.

That formula is `src/bibleont/hubs.py`, which the old app serves at
`/api/hubs`. Its score is

    closure  x  reach  x  narratives

    closure     weighted triangle closure -- is my neighbourhood REAL
    reach       damped two-hop reach      -- does it OPEN OUT
    narratives  distinct stories its citations fall in

and the three together answer a question neither degree nor raw frequency can.
That module's own record of the alternatives is worth reading before anyone
proposes a simpler measure: degree alone puts a roster of eighty-four men
fourth in the corpus, and two-hop reach alone puts Bethlehem above Moses,
because Bethlehem's few neighbours are David and Jesus -- true, and a strange
thing to head a list of hubs.

## Why this file exists at all

`survey()` takes about ten seconds cold, which the old app absorbed with a
two-stage paint. The new reader builds its Explore page on every load and
should not pay that, so the ranking is computed once here and written to
`out/hubs.json` for the reader to read.

That also makes the ranking a FILE rather than a behaviour -- inspectable,
diffable, and obviously stale if the graph changes without it being rerun.

    python tools/hubrank.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    from bibleont.hubs import survey

    print("  ranking hubs (closure x reach x narratives) …", flush=True)
    rows = survey()
    rows.sort(key=lambda h: -h.score)
    out = [{"id": h.id, "name": h.name, "type": h.type, "degree": h.degree,
            "triangles": h.triangles, "closure": round(h.closure, 2),
            "reach": round(h.reach, 2), "narratives": h.narratives,
            "score": round(h.score, 2)} for h in rows]
    p = OUT / "hubs.json"
    p.write_text(json.dumps(
        {"_note": "Nodes ranked by closure x reach x narratives -- see "
                  "src/bibleont/hubs.py and tools/hubrank.py. Rerun when the "
                  "graph changes.",
         "hubs": out}, ensure_ascii=False), encoding="utf-8")
    print(f"  {len(out):,} nodes -> {p.relative_to(ROOT)}\n")
    print(f"  {'node':30}{'type':10}{'deg':>5}{'closure':>10}"
          f"{'reach':>9}{'narr':>6}")
    for h in out[:15]:
        print(f"  {h['name'][:28]:30}{h['type']:10}{h['degree']:5}"
              f"{h['closure']:10.0f}{h['reach']:9.0f}{h['narratives']:6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
