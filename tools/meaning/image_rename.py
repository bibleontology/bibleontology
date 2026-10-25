"""IMAGE CARDS NAMED BY THEIR FIGURE (2026-10-25). Doug, on the release guide's first row: the image card for the
parable of the two houses was called "house", like the object card, and the two read alike; then "I like the name
change a lot ... If you are asking for my approval on these name changes I give it".

92 image cards shared their name with another card. The rule, from what the cards hold:
  - a card of a few verses, or one named saying, takes the text's own phrase ("the two houses", "a city on a hill");
  - a broad card (dozens or hundreds of verses) takes "<word>, as a figure": a phrase from one verse would make
    a card of every figurative "light" read as "I am the light of the world";
  - twins (two image cards for one figure) keep their names: renaming them apart would hide a duplicate that the
    twin-cards proposal (P-2026-10-24-1) is to settle.
Names drafted by a Claude Sonnet reader from each card's description and figure verses
(out/meaning/image-audit/rename-output.json); the tiers applied here.

    python tools/meaning/image_rename.py            dry run
    python tools/meaning/image_rename.py --write    rename in ontology/entities/entities.jsonl, with a record
"""
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENTS = ROOT / "ontology" / "entities" / "entities.jsonl"
RECORD = ROOT / "ontology" / "provenance" / "meaning" / "image-renames-2026-10-25.json"
SAYINGS = {"image_two_houses": "the two houses", "image_city_on_a_hill": "a city on a hill",
           "image_narrow_gate": "the narrow gate", "image_good_tree": "the good tree"}
TWINS = {"bucklers", "image_shield", "clay", "image_clay", "feet", "image_feet", "image_chaff", "image_stubble",
         "image_gin", "image_trap", "table", "image_table", "image_adder", "viper", "image_gold", "image_defence"}
# a drafted phrase that is already another card's name ("a well of fresh water")
OVERRIDE = {"image_well": "well, as a figure"}
SMALL = 8


def main():
    drafts = json.loads((ROOT / "out" / "meaning" / "image-audit" / "rename-output.json").read_text(encoding="utf-8"))
    verses = collections.defaultdict(set)
    for ln in open(ROOT / "ontology" / "card-repairs.jsonl", encoding="utf-8"):
        if ln.strip():
            r = json.loads(ln)
            if r["action"] == "named":
                verses[r["card"]] |= set(r["verses"])
    plan = {}
    for d in drafts:
        c = d["id"]
        if c in TWINS:
            continue
        if c in OVERRIDE:
            new, why = OVERRIDE[c], "the drafted phrase is another card's name"
        elif c in SAYINGS:
            new, why = SAYINGS[c], "a named saying"
        elif len(verses[c]) <= SMALL:
            new, why = d["new"], f"{len(verses[c])} verses: the text's own phrase ({d['reason']})"
        else:
            new, why = f"{d['old']}, as a figure", f"{len(verses[c])} verses: a broad figure"
        plan[c] = {"old": d["old"], "new": new, "why": why}
    # read as bytes: read_text() turns CRLF into LF, so the line ending is never seen and every line of this
    # CRLF file was rewritten (2026-10-25: 8,378 lines in the diff for 76 renames)
    raw = ENTS.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.split(nl)
    taken = collections.Counter()
    for ln in lines:
        if ln.strip():
            e = json.loads(ln)
            if e["id"] not in plan:
                taken[(e.get("name") or "").strip().lower()] += 1
    clash = [p["new"] for p in plan.values() if taken[p["new"].strip().lower()]]
    dup = [n for n, k in collections.Counter(p["new"].lower() for p in plan.values()).items() if k > 1]
    print(f"{len(plan)} renames ({len(TWINS)} twins held); still clashing: {clash}; duplicated: {dup}")
    for c, p in list(plan.items())[:10]:
        print(f"  {c:28} {p['old']!r} -> {p['new']!r}")
    if not WRITE:
        return
    if clash or dup:
        sys.exit("refused: a new name would still clash")
    done = set()
    for i, ln in enumerate(lines):
        if ln.strip():
            e = json.loads(ln)
            if e["id"] in plan:
                assert e.get("name") == plan[e["id"]]["old"], (e["id"], e.get("name"))
                e["name"] = plan[e["id"]]["new"]
                lines[i] = json.dumps(e, ensure_ascii=False)
                done.add(e["id"])
    missing = set(plan) - done
    assert not missing, missing
    ENTS.write_text(nl.join(lines), encoding="utf-8", newline="")
    RECORD.write_text(json.dumps({"approved_by": "Doug, 2026-10-25: \"If you are asking for my approval on these name "
                                                 "changes I give it\"", "rule": __doc__.split("\n\n")[1],
                                  "renames": plan, "twins_held": sorted(TWINS)}, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
    print(f"renamed {len(done)} -> {RECORD.relative_to(ROOT)}")


WRITE = "--write" in sys.argv
if __name__ == "__main__":
    main()
