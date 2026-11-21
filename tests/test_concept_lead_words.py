"""The same-word line's map agrees with the cards (P-2026-11-18-3).

    python -X utf8 tests/test_concept_lead_words.py

ontology/concept-lead-words.json is read from the server's own answers by tools/concept_lead_words.py, because a
card's words come from a derivation too costly to run for every concept on every request. A stale map would put a
card under a word it no longer uses, so this holds it to the cards: every card the servant line names (עֶבֶד's five),
and a sample of 60 others, must lead with the word the map says, and every card a line names must lead with that
word. Both are proven by a planted fault. (That a line never names its own card holds by construction; it is
checked, not planted.)
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

d = S.load()
MAP = json.loads((ROOT / "ontology" / "concept-lead-words.json").read_text(encoding="utf-8"))["cards"]


def live_words(eid):
    r = S.api_entity(d, {"id": [eid]})
    return [w.get("key") for w in ((r.get("ccard") or {}).get("words") or r.get("words") or []) if w.get("key")], r


def faults(cards, sample):
    f = []
    for eid in sample:
        ws, _r = live_words(eid)
        if eid in cards and ws[:1] != cards[eid][:1]:
            f.append(f"{eid}: the map says it leads with {cards[eid][:1]}, the card with {ws[:1]}")
        if eid not in cards and ws:
            f.append(f"{eid}: has words {ws[:2]} and is not in the map")
    return f


def line_faults(eid):
    _ws, r = live_words(eid)
    f = []
    for k, xs in (r.get("same_word") or {}).items():
        if any(x["id"] == eid for x in xs):
            f.append(f"{eid}: its line under {k} names itself")
        for x in xs:
            if (MAP.get(x["id"]) or [None])[0] != k:
                f.append(f"{eid}: names {x['id']} under {k}, which it does not lead")
    return f


def retired_faults(cards):
    """a card merged into another (ontology/aliases.jsonl) answers 301 to it, so on a line it names its own target"""
    return [f"{k}: merged into {d['ents'][k]['alias_of']} and still in the map" for k in cards
            if (d["ents"].get(k) or {}).get("alias_of")]


random.seed(18)
named = [x["id"] for xs in (S.api_entity(d, {"id": ["servant"]}).get("same_word") or {}).values() for x in xs]
sample = sorted(set(named) | set(random.sample(sorted(MAP), min(60, len(MAP)))))
fails = faults(MAP, sample) + line_faults("servant") + line_faults("servants") + retired_faults(MAP)
if not named:
    fails.append("servant's card names no other card under its words (עֶבֶד leads five)")

# planted: a map that moved one card's lead word, and a line that names its own card
bad = dict(MAP)
victim = sample[0]
bad[victim] = ["h0000"] + bad[victim][1:]
planted = {"a stale lead word": bool(faults(bad, [victim]))}
# a merged card left in the map (the 31 of option C were, 2026-11-19)
gone = next((k for k, e in d["ents"].items() if e.get("alias_of") and e.get("type") == "concept"), None)
planted["a merged card left in the map"] = bool(gone) and bool(retired_faults({**MAP, gone: ["h0000"]}))
# a card put under a word it does not lead (blessing under עֶבֶד)
S.same_word(d, "servant", [])                       # load the real map first
S._LEAD_OF[MAP["servant"][0]].append("blessing")
planted["a card under a word it does not lead"] = bool([x for x in line_faults("servant") if "does not lead" in x])
S._LEAD_OF = None
missed = [k for k, v in planted.items() if not v]
for m in missed:
    fails.append(f"planted fault not caught: {m}")
for x in fails:
    print("FAIL", x)
print(f"concept lead words: {len(sample)} cards checked against the map, {len(named)} on servant's line; "
      f"planted faults caught: {len(planted) - len(missed)} of {len(planted)}; {len(fails)} failures")
sys.exit(1 if fails else 0)
