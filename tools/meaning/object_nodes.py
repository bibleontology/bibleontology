"""One node per thing the text follows (plan A.45), from the final chains of 2026-11-07.

docs/review/object-identity/chains-20-2026-11-07.json holds 32 chains: mentions ("Jos.4.20#w5") the passes and
Claude's reading judged one physical thing. Each chain the text treats as a particular thing becomes an object (or
creature) card, its refs every verse that mentions it, linked to the card of its kind by `kind_of`. For the five
test cards (the Jordan stones, the bronze serpent, Joseph's bones, wells, oxen) the people and places the verses
name are added by hand, each quoting its verse, checked here against the Berean's words.

Left out: the law cases of Exodus 21 (an ox that gores is any ox, not one), the Stone of Bohan (already a place
card), and the two Ebal chains, held (Deut 27's chain joins the plastered stones to the altar's stones, which the
text keeps apart).

    python tools/meaning/object_nodes.py   -> ontology/entities/objects-a45.jsonl, ontology/relations/objects-a45.jsonl
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
from object_identity import verses  # noqa: E402

SOURCE = "objects-a45"
BOOK = {"Luk": "Luke", "Mat": "Matt", "Mrk": "Mark", "Jhn": "John", "Gen": "Gen", "Exo": "Exod", "Num": "Num",
        "2Ch": "2Chr", "Jos": "Josh", "2Sa": "2Sam", "1Sa": "1Sam", "2Ki": "2Kgs", "1Ki": "1Kgs", "Deu": "Deut"}
# chain index -> (id, name, type, kind card or None); None drops the chain
NAMES = {
    0: ("stone_at_the_tomb_of_jesus", "the stone at the tomb of Jesus", "object", "stone"),
    1: ("stone_at_the_tomb_of_lazarus", "the stone at the tomb of Lazarus", "object", "stone"),
    2: ("isaacs_well_at_beersheba", "Isaac's well at Beersheba (Shibah)", "object", "well"),
    3: ("the_well_at_haran", "the well where Jacob met Rachel", "object", "well"),
    4: ("rock_in_horeb", None, None, "rock"),                  # an existing card: reused, never a second node
    5: ("the_rock_at_meribah", "the rock at Meribah", "object", "rock"),
    6: ("ox_figures_under_the_sea_rim", "the figures of oxen under the rim of the Sea", "object", None),
    7: None,                                                     # the Stone of Bohan: a place card already
    8: ("the_stone_of_witness_at_shechem", "the stone of witness at Shechem", "object", "stone"),
    9: ("the_wells_of_abraham", None, None, "well"),
    10: ("well_of_springing_water", None, None, "well"),     # "a well of fresh water" (26:19), named Esek (26:20)
    11: ("araunahs_oxen", "Araunah's oxen", "creature", "oxen"),
    12: ("the_stones_at_the_cave_of_makkedah", "the stones at the cave of Makkedah", "object", "stones"),
    13: ("the_cows_that_drew_the_ark", "the two cows that drew the ark", "creature", "cow"),
    14: ("abrahams_well", None, None, "well"),
    15: ("josephs_bones", None, None, "bones"),
    16: ("the_hailstones_at_beth_horon", "the hailstones at Beth-horon", "object", None),
    17: None, 18: None,                                          # Exodus 21: the law's ox, any ox
    19: ("brasen_serpent", None, None, None),
    20: None,                                                    # Ebal, held
    21: ("the_twelve_stones_from_the_jordan", "the twelve stones from the Jordan", "object", "stones"),
    22: None, 23: None,                                          # Exodus 21
    24: ("well_of_nahor", None, None, None),                   # a place card already
    25: ("the_well_at_beer", "the well at Beer", "object", "well"),
    26: ("elishas_oxen", "Elisha's oxen", "creature", "oxen"),
    27: ("the_twelve_bronze_oxen_under_the_sea", "the twelve bronze oxen under the Sea", "object", None),
    28: ("the_twelve_bronze_oxen_under_the_sea", None, None, None),     # the same oxen, 1 Kgs 7: merged into 27
    29: ("sauls_oxen", "the oxen Saul cut in pieces", "creature", "oxen"),
    30: ("the_fiery_serpents", "the fiery serpents", "creature", None),
    31: None,                                                    # Ebal, held
}
# the five test cards' people and places, each with the verse and the words that say it
HAND = [
    ("children_of_israel", "carried", "the_twelve_stones_from_the_jordan", "Jos.4.8", "carried them to the camp"),
    ("the_twelve_stones_from_the_jordan", "located_in", "gilgal", "Jos.4.20", "Gilgal"),
    ("hezekiah", "destroyed", "brasen_serpent", "2Ki.18.4", "demolished the bronze snake called Nehushtan"),
    ("moses", "carried", "josephs_bones", "Exo.13.19", "Moses took the bones of Joseph with him"),
    ("josephs_bones", "located_in", "shechem_city", "Jos.24.32", "were buried at Shechem"),
    ("isaacs_well_at_beersheba", "located_in", "beer_sheba", "Gen.26.33", "Beersheba"),
    ("abrahams_well", "located_in", "beer_sheba", "Gen.21.31", "Beersheba"),
]


def ref(r):
    b, c, v = r.split("#")[0].split(".")
    return f"{BOOK[b]} {c}:{v}"


def main():
    text = verses()
    chains = json.load(open(ROOT / "docs" / "review" / "object-identity" / "chains-20-2026-11-07.json",
                            encoding="utf-8"))["chains"]
    ents, order, reused = {}, [], []
    for i, chain in enumerate(chains):
        spec = NAMES.get(i)
        if spec is None:
            continue
        eid, name, typ, kind = spec
        refs = sorted({ref(m) for m in chain}, key=lambda r: [m.split("#")[0] for m in chain].index(
            next(m.split("#")[0] for m in chain if ref(m) == r)))
        if eid in ents:                                          # a merged chain adds its verses
            ents[eid]["refs"] += [r for r in refs if r not in ents[eid]["refs"]]
            continue
        if name is None:                                         # an existing card: its kind only
            reused.append((eid, kind, chain[0].split("#")[0], refs[0]))
            continue
        ents[eid] = {"attrs": {}, "gender": "unknown", "id": eid, "name": name, "refs": refs, "source": SOURCE,
                     "type": typ, "_kind": kind, "_first": chain[0].split("#")[0]}
        order.append(eid)
    rels = []
    for eid in order:
        e = ents[eid]
        kind = e.pop("_kind")
        first = e.pop("_first")
        if kind:
            rels.append({"certainty": "explicit", "dst": kind, "note": text.get(first, "")[:160], "refs": [e["refs"][0]],
                         "source": SOURCE, "src": eid, "type": "kind_of"})
    for eid, kind, first, r0 in reused:
        if kind:
            rels.append({"certainty": "explicit", "dst": kind, "note": text.get(first, "")[:160], "refs": [r0],
                         "source": SOURCE, "src": eid, "type": "kind_of"})
    for src, typ, dst, r, words in HAND:
        assert words in text.get(r, ""), f"{r} does not say {words!r}: {text.get(r)!r}"
        rels.append({"certainty": "explicit", "dst": dst, "note": words, "refs": [ref(r + "#w0")], "source": SOURCE,
                     "src": src, "type": typ})
    (ROOT / "ontology" / "entities" / f"{SOURCE}.jsonl").write_text(
        "".join(json.dumps(ents[e], ensure_ascii=False) + "\n" for e in order), encoding="utf-8", newline="\n")
    (ROOT / "ontology" / "relations" / f"{SOURCE}.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rels), encoding="utf-8", newline="\n")
    print(f"{len(order)} nodes, {len(rels)} relations ({sum(r['type'] == 'kind_of' for r in rels)} kind_of)")


if __name__ == "__main__":
    main()
