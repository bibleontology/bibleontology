"""THE BLIND SECOND READER's input, for an image evidence pack (plan 8.2h, as for
temple, plan 8.2e: 183 of 196 agreed).

From out/meaning/image-audit/packs/<image>.json: every verse the gatherer did not
call literal, and 40 of its literal ones (a fixed seed, so a rerun asks the same),
each with its Berean text and nothing of the gatherer's answer. Then, once the
blind reader has answered, the agreement.

    python tools/meaning/blind_input.py make  image_lion   -> packs/image_lion.blind-input.json
    python tools/meaning/blind_input.py agree image_lion   (reads packs/image_lion.blind.json)
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / "out" / "meaning" / "image-audit" / "packs"


def make(image):
    pack = json.loads((PACKS / f"{image}.json").read_text(encoding="utf-8"))
    vs = pack["verses"]
    lit = [v for v in vs if v.get("sense") == "literal"]
    rest = [v for v in vs if v.get("sense") != "literal"]
    rng = random.Random(f"blind:{image}")
    sample = rest + rng.sample(lit, min(40, len(lit)))
    rng.shuffle(sample)
    items = [{"ref": v["ref"], "bsb_ref": v.get("bsb_ref"), "text": v.get("text")} for v in sample]
    out = {"image": image, "literal": pack.get("literal"), "n": len(items), "verses": items}
    (PACKS / f"{image}.blind-input.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{image}: {len(items)} verses ({len(rest)} non-literal, {len(items) - len(rest)} literal)")


def agree(image):
    pack = json.loads((PACKS / f"{image}.json").read_text(encoding="utf-8"))
    first = {v["ref"]: v.get("sense") for v in pack["verses"]}
    blind = json.loads((PACKS / f"{image}.blind.json").read_text(encoding="utf-8"))
    rows = blind["verses"] if isinstance(blind, dict) else blind
    same, diff = 0, []
    for b in rows:
        a = first.get(b["ref"])
        if a == b.get("sense"):
            same += 1
        else:
            diff.append({"ref": b["ref"], "first": a, "blind": b.get("sense"), "blind_reason": b.get("reason")})
    # WHERE THE VERSE GOES is what a ruling decides; "figure" and "figure_keyed"
    # both go on the image card (the vine: 14 of 22 differences were only that)
    place = {"literal": "literal card", "figure": "image card", "figure_keyed": "image card", "both": "both cards"}
    placed = [d for d in diff if place.get(d["first"], "neither") != place.get(d["blind"], "neither")]
    out = {"image": image, "asked": len(rows), "agree": same, "agree_on_card": len(rows) - len(placed),
           "disagree": diff, "disagree_on_card": placed}
    (PACKS / f"{image}.agreement.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{image}: {same} of {len(rows)} agree on the sense, {len(rows) - len(placed)} on the card; "
          f"{len(placed)} to rule")


if __name__ == "__main__":
    {"make": make, "agree": agree}[sys.argv[1]](sys.argv[2])
