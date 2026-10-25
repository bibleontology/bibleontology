"""DO THE CARDS SAY WHAT THE GRAPH NOW HOLDS? (plan 8.2h, 2026-10-24)

Doug: "looking to get serious volume done for the rest of the weekend to really shore up the model and cards to
match". After the image audit narrowed 66 image cards to the verses where the figure is used, a card's description
can cite a verse the card no longer carries, or name a thing it has no relation to. This is the mechanical half of
that check, no model: every verse a description cites, against the card's verses and its relations' verses.

    python tools/meaning/card_desc_check.py [CARD ...] [--port 8012]   (default: every image card with a ruling)
      -> out/meaning/card-desc-check.json, a tally
"""
import collections
import glob
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from export_claims import verses as vlist  # noqa: E402
from derive import BOOK  # noqa: E402

PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8012
# "(Genesis 1:2)", "(Ps 34:15)", "(1 Corinthians 6:19-20)", "(7:23)" after a full one
CITE = re.compile(r"\(((?:[1-3] )?[A-Z][a-z]+\.? \d+:\d+(?:[-–]\d+)?(?:[;,] ?(?:\d+:)?\d+(?:[-–]\d+)?)*)\)")


# a description cites in the Berean's numbering, and the server lists a card's verses in the Berean's numbering too
# (it shows Malachi 4), so the two compare as they are. (A first cut mapped citations to MACULA's numbering, 2026-10-24,
# which is right for the rulings file and wrong here.)
def mac(ref):
    try:
        return {BOOK.get(b, b) + "." + rest for b, rest in (v.split(".", 1) for v in vlist(ref))}
    except Exception:
        return set()


def main(cards):
    ents = {}
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                ents.setdefault(e["id"], e)
    rel_verses = collections.defaultdict(set)
    for f in glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                r = json.loads(ln)
                for ref in r.get("refs") or []:
                    for end in (r["src"], r["dst"]):
                        rel_verses[end] |= mac(ref)
    if not cards:
        rp = [json.loads(l) for l in open(ROOT / "ontology" / "card-repairs.jsonl", encoding="utf-8") if l.strip()]
        cards = sorted({r["card"] for r in rp if (ents.get(r["card"]) or {}).get("type") == "image"})
    out, tally = {}, collections.Counter()
    for c in cards:
        with urllib.request.urlopen(f"http://localhost:{PORT}/api/entity-verses?id={c}", timeout=120) as r:
            d = json.load(r)
        on = {it["eref"] for b in d.get("books") or [] for it in b.get("items") or []}
        desc = (ents.get(c) or {}).get("desc") or ""
        cited = []
        for m in CITE.finditer(desc):
            for part in re.split(r"[;,] ?", m.group(1)):
                cited.append(part)
        missing = []
        for ref in cited:
            vs = mac(ref)
            if vs and not (vs & on) and not (vs & rel_verses[c]):
                missing.append(ref)
        out[c] = {"verses": len(on), "cited": cited, "cited_not_on_card_or_relations": missing,
                  "desc_words": len(desc.split())}
        tally["cards"] += 1
        tally["with a stray citation"] += bool(missing)
        tally["citing nothing"] += not cited
    (ROOT / "out" / "meaning" / "card-desc-check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                                   encoding="utf-8")
    print(dict(tally))
    for c, v in sorted(out.items(), key=lambda x: -len(x[1]["cited_not_on_card_or_relations"]))[:15]:
        if v["cited_not_on_card_or_relations"]:
            print(f"  {c:32} {v['verses']:>4} verses; cites, but holds neither by verse nor relation: "
                  f"{', '.join(v['cited_not_on_card_or_relations'])}")


if __name__ == "__main__":
    main([a for a in sys.argv[1:] if not a.startswith("--") and not a.isdigit()])
