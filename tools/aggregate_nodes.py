"""The declared lists' nodes and links, from ontology/aggregate-hubs.json (A.34).

2026-10-07: a list is one card (two cards for it were confusing), there should
be concept or image nodes for all the members, and what the graph already holds
is reused (the duplicates are consolidated as well). The hub
file names, for every member, the node it opens; this writes:

  ontology/entities/aggregate-hubs.jsonl    the nodes it marks `make` (a member
                                            no node holds) and `make_card` (a
                                            list with no graph card)
  ontology/relations/aggregate-hubs.jsonl   the list's card to each member, at
                                            the member's verse: `draws_on` an
                                            image, `speaks_of` anything else;
                                            plus EXTRA below

A made node's description is its verse, quoted whole from the Berean. A link
already in the graph (same source, type and target) is not made twice, nor
one at a verse outside the chapters the card stands in. A list
whose card cannot carry the link (an object, an event) or whose members the
text does not join to it (`no_links`) gets none; its hub still opens each one.

    python tools/aggregate_nodes.py
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUBS = ROOT / "ontology" / "aggregate-hubs.json"
ENT = ROOT / "ontology" / "entities" / "aggregate-hubs.jsonl"
REL = ROOT / "ontology" / "relations" / "aggregate-hubs.jsonl"
SOURCE = "aggregate-hubs"
LINKS_FROM = {"text", "title", "image", "assessment"}   # speaks_of's sources
SPEAKS_OF_TO = {"concept", "assessment", "place", "being", "object", "title", "image", "person",
                "group", "creature", "observance", "covenant", "text"}   # and its targets (the schema)

# links that are not "the list names this member"
EXTRA = [
    # the armor glosses every piece in the clause that names it (Eph 6:14-17)
    ("the_full_armor_of_god", "speaks_of", "truth", ["Eph 6:14"],
     "'with the belt of truth buckled around your waist' (Eph 6:14)."),
    ("the_full_armor_of_god", "speaks_of", "righteousness", ["Eph 6:14"],
     "'with the breastplate of righteousness arrayed' (Eph 6:14)."),
    ("the_full_armor_of_god", "speaks_of", "faith", ["Eph 6:16"],
     "'take up the shield of faith' (Eph 6:16)."),
    ("the_full_armor_of_god", "speaks_of", "salvation", ["Eph 6:17"],
     "'And take the helmet of salvation' (Eph 6:17)."),
    # the sixth image, beside the five the armor already draws on; its pieces
    # open what they stand for, and the images stay on the card's diagram
    ("the_full_armor_of_god", "draws_on", "image_shoe", ["Eph 6:15"],
     "'with your feet fitted with the readiness of the gospel of peace' (Eph 6:15). The verse "
     "names no sandal; its verb is the Greek one for binding sandals on (as at Mark 6:9)."),
    # the feet are fitted with "the readiness of the gospel of peace"; the
    # piece opens peace (whose card begins at this verse), and this keeps the
    # gospel one step away (the symbol, not the object)
    ("the_full_armor_of_god", "speaks_of", "gospel", ["Eph 6:15"],
     "'and with your feet fitted with the readiness of the gospel of peace' (Eph 6:15)."),
    # the Spiritual Warfare concept "The full armor of God" is merged into the
    # armor's card (tools/themes/theme_nodes.py MERGE), not linked to it
    # the Beatitudes open the Sermon on the Mount; one of them has its own card
    ("matt_5_3_12", "part_of", "sermon_on_the_mount", ["Matt 5:3"],
     "The first sayings of the Sermon on the Mount (Matt 5:3-12)."),
    ("blessed_are_the_merciful", "part_of", "matt_5_3_12", ["Matt 5:7"],
     "'Blessed are the merciful, for they will be shown mercy.' (Matt 5:7)."),
]
NOTE = {}  # a link the list makes that wants its own note: (card, member) -> note


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def main():
    hubs = {k: v for k, v in json.loads(HUBS.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    verse = {}
    for d in rows(ROOT / "data" / "bible" / "verses.bsb.jsonl"):
        if "b" in d:
            verse[f"{d['b']} {d['c']}:{d['v']}"] = d["t"]
    ents = {}
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        if Path(f).name != ENT.name:
            for e in rows(f):
                ents[e["id"]] = e
    have, linked = set(), set()
    for f in glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl")):
        if Path(f).name != REL.name:
            for r in rows(f):
                have.add((r["src"], r["type"], r["dst"]))
                linked.add((r["src"], r["dst"]))

    def quote(ref):
        t = verse[ref].strip().strip("“”‘’ ")
        return f"'{t}' ({ref})."

    new, rels = {}, []
    for aid, h in hubs.items():
        if h.get("make_card"):
            s = h["make_card"]
            new[h["card"]] = {"attrs": {"kind": s["kind"]} if s.get("kind") else {},
                              "desc": s["desc"], "gender": "unknown", "id": h["card"],
                              "name": s["name"], "refs": s["refs"], "source": SOURCE, "type": s["type"]}
        for m in h["members"]:
            if m.get("make"):
                s = m["make"]
                assert m["card"] not in ents, f"{m['card']} is already in the graph"
                new[m["card"]] = {"attrs": {"kind": s["kind"]} if s.get("kind") else {},
                                  "desc": quote(m["ref"]), "gender": "unknown", "id": m["card"],
                                  "name": s["name"], "refs": list(dict.fromkeys([m["ref"]] + s.get("refs", []))),
                                  "source": SOURCE, "type": s["type"]}
    allents = {**ents, **new}
    # the fixed links first, with their quotations; a list's own link then
    # skips anything they already join
    for src, typ, dst, refs, note in EXTRA:
        if (src, typ, dst) not in have:
            rels.append({"certainty": "explicit", "dst": dst, "note": note, "refs": refs,
                         "source": SOURCE, "src": src, "type": typ})
            linked.add((src, dst))
    # a symbol's own links, at its verse: the general image it is built on and
    # what the verse says it is (the breastplate of righteousness is a
    # gateway to righteousness)
    for aid, h in hubs.items():
        for m in h["members"]:
            for ln in m.get("links") or []:
                assert ln["dst"] in allents, ln["dst"]
                if (m["card"], ln["type"], ln["dst"]) not in have:
                    rels.append({"certainty": "explicit", "dst": ln["dst"], "note": quote(m["ref"]),
                                 "refs": [m["ref"]], "source": SOURCE, "src": m["card"], "type": ln["type"]})
    for aid, h in hubs.items():
        card = allents.get(h.get("card"))
        if not card or card["type"] not in LINKS_FROM or h.get("no_links"):
            continue
        seen = set()
        # only in a chapter the card itself stands in: "different gifts, the
        # same Spirit" is 1 Corinthians 12, and does not speak of Romans 12's
        # serving; the hub still opens those members
        chapters = {r.rsplit(":", 1)[0] for r in card.get("refs") or []}
        for m in h["members"]:
            if m["ref"].rsplit(":", 1)[0] not in chapters:
                continue
            dst = allents[m["card"]]
            typ = "draws_on" if dst["type"] == "image" else "speaks_of"
            if dst["type"] not in SPEAKS_OF_TO and typ == "speaks_of":
                continue          # an event card (the letters to the seven churches) takes none

            key = (card["id"], typ, dst["id"])
            # already joined, by any type ("the word of God" is drawn on, at
            # the same verse): the list's link would say it twice
            if key in have or key in seen or (card["id"], dst["id"]) in linked:
                continue
            seen.add(key)
            rels.append({"certainty": "explicit", "dst": dst["id"],
                         "note": NOTE.get((card["id"], dst["id"]), f"Named in the list at {m['ref']}."),
                         "refs": [m["ref"]], "source": SOURCE, "src": card["id"], "type": typ})
    for path, out in ((ENT, sorted(new.values(), key=lambda r: r["id"])), (REL, rels)):
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for r in out:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"{len(new)} nodes ({sum(1 for h in hubs.values() if h.get('make_card'))} list cards), "
          f"{len(rels)} links")


if __name__ == "__main__":
    main()
