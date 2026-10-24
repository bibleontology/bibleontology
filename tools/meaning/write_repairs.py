"""THE RULED CONCEPT REPAIRS, WRITTEN (2026-10-20: the repair writer
approved).

From the decisions' data (out/meaning/repairs.jsonl, tools/meaning/
repair_sheet.py) and the rulings on the two sheets (ontology/provenance/
meaning/concept-repairs-marks-2026-10-20.json and
concept-repairs-d5-marks-2026-10-20.json), one row per card and word:

  named   the word gives the card ONLY these verses, each a reading (both
          passes said the verse speaks of the card). Decision 1's adds, decision
          5's adds, and a dropped word's few verses that did mean the card.
  drop    the word leaves the card.

What is applied, as ruled:
  decision 1  adds, as recommended, EXCEPT an image or title card never takes
              verses because they contain its word (the gold and Israel
              points: "the symbolism is the reading and the tangible is the
              obvious"; Israel "is the descendants of Israel"). Israel's adds go
              to the people (children_of_israel), as ruled; any other image or
              title card's adds are held and counted
  decision 2  every drop; a dropped word's yes verses stay as named verses
  decision 5  the tithe's 10 and justification's 2 adds; young women's 66; the
              women cards' drops; justification's צָדֵק not applied (stays hidden)
Not applied (unmarked): decision 3's phrase-card adds, decision 4's splits.

    python tools/meaning/write_repairs.py   -> ontology/card-repairs.jsonl, a tally

membership.py reads the file, so the server, the audit, the resolver and the
card-words export all see the same repaired card.
"""
import collections
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "ontology" / "card-repairs.jsonl"
MARKS = "ontology/provenance/meaning/concept-repairs-marks-2026-10-20.json"
MARKS5 = "ontology/provenance/meaning/concept-repairs-d5-marks-2026-10-20.json"
# The rulings of 2026-10-20 (decision cards in chat, recorded in MARKS)
REDIRECT = {"israel_title": "children_of_israel"}
NO_WORD_ADDS = ("image", "title")
D5_ADDS = {"the_tithe", "justification", "young_women"}
READER = "the concept audit's two verse passes (Claude Sonnet), both yes; ruled by Doug, 2026-10-20"


def jl(p):
    op = gzip.open if str(p).endswith(".gz") else open
    with op(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main():
    cards = {c["id"]: c for c in jl(ROOT / "out" / "meaning" / "repairs.jsonl")}
    ents = {e["id"]: e for e in jl(ROOT / "ontology" / "entities" / "entities.jsonl")}
    want = {k for c in cards.values() for k in c["adds"]}
    in_verse = collections.defaultdict(set)          # verse -> add words in it
    for d in jl(ROOT / "out" / "placeholder-nodes.jsonl.gz"):
        if d.get("word"):
            s = re.sub(r"\D", "", str(d.get("strong") or "")).lstrip("0")
            k = ("g" if d.get("lang") == "greek" else "h") + s if s else None
            if k in want:
                in_verse[d["ref"]].add(k)

    st, held = collections.Counter(), collections.Counter()
    named = collections.defaultdict(lambda: collections.defaultdict(set))   # card -> key -> verses
    why = {}

    def add(c, decision):
        target = REDIRECT.get(c["id"], c["id"])
        ttype = (ents.get(target) or {}).get("type")
        if target == c["id"] and ttype in NO_WORD_ADDS:
            held[f"{ttype} card: no word-based adds"] += len(c["verses_to_add"])
            st["cards held (image or title)"] += 1
            return
        for v in c["verses_to_add"]:
            ks = in_verse.get(v, set()) & set(c["adds"])
            if not ks:
                held["no add word found in the verse"] += 1
                continue
            for k in ks:
                named[target][k].add(v)
                why[(target, k)] = (decision, c["id"])
        st[f"{decision}: verses added"] += len(c["verses_to_add"])
        if target != c["id"]:
            st[f"redirected: {c['id']} -> {target}"] += len(c["verses_to_add"])

    for c in cards.values():
        if not c["verses_to_add"]:
            continue
        if c["contested"]:
            if c["id"] in D5_ADDS:
                add(c, "decision 5")
            continue
        if c["phrase"]:
            held["phrase card (decision 3, unmarked)"] += len(c["verses_to_add"])
            continue
        add(c, "decision 1")

    drops = []
    for c in cards.values():
        for x in c["drops"]:
            drops.append({"card": c["id"], "key": x["key"], "action": "drop", "decision": "decision 2",
                          "shown_before": x["shown"], "share": x["share"], "uses": x["uses"]})
            st["words dropped"] += 1
            st["words dropped that readers saw"] += bool(x["shown"])
            # the few verses where the word did mean the card stay, as single
            # verses (the sheet's recommendation, approved)
            if x["yes"]:
                named[c["id"]][x["key"]].update(x["yes"])
                why[(c["id"], x["key"])] = ("decision 2 (its yes verses kept)", c["id"])
                st["dropped words kept for their yes verses"] += 1

    rows = []
    for card, ks in sorted(named.items()):
        for k, vs in sorted(ks.items()):
            dec, src = why[(card, k)]
            rows.append({"card": card, "key": k, "action": "named", "verses": sorted(vs), "decision": dec,
                         **({"from_card": src} if src != card else {}), "reader": READER,
                         "ruling": MARKS5 if dec == "decision 5" else MARKS})
    # a word kept for its yes verses is not also dropped
    keep = {(r["card"], r["key"]) for r in rows}
    rows += [{**d, "reader": READER, "ruling": MARKS5 if d["card"] in cards and cards[d["card"]]["contested"] else MARKS}
             for d in drops if (d["card"], d["key"]) not in keep]
    DEST.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    st["named rows"] = sum(r["action"] == "named" for r in rows)
    st["named verses"] = sum(len(r["verses"]) for r in rows if r["action"] == "named")
    st["cards changed"] = len({r["card"] for r in rows})
    print(json.dumps({"applied": dict(st.most_common()), "held": dict(held.most_common())}, ensure_ascii=False, indent=1))
    print(f"-> {DEST.relative_to(ROOT)}: {len(rows):,} rows")


if __name__ == "__main__":
    main()
