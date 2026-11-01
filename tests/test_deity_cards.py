"""The four divine-person cards carry their shared header, and no other card does (2026-10-31).

    python -X utf8 tests/test_deity_cards.py

Each header holds its name, its sketch verbatim (app2/deity_sketches.py: a thing the text names, never a person)
and the verse the sketch is drawn from, quoted from the graph's own text with its link.
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402
from deity_sketches import SKETCHES  # noqa: E402

d = S.load()
fails = []


def faults(eid, c):
    f = []
    if eid not in S.DEITY_PLATES:
        return ["a header on a card that is not one of the four"] if c.get("deityplate") else []
    name, sk, ref = S.DEITY_PLATES[eid]
    p = c.get("deityplate") or {}
    h = p.get("html") or ""
    r = S._sc_ref(d, ref)
    if not h:
        return [f"{eid}: no header"]
    if SKETCHES[sk] not in h:
        f.append(f"{eid}: the sketch {sk} is not carried verbatim")
    if f">{name}</h1>" not in h:
        f.append(f"{eid}: the name {name} is not its heading")
    # the four share the person card's face (2026-11-01: God, the Father and the Holy Spirit to match Jesus), and a
    # being's first drawer never calls whom he leads and is with his family
    pc = c.get("pcard") or {}
    if not pc or c.get("fbcard"):
        f.append(f"{eid}: not on the person card's face")
    if c.get("type") != "person" and any(x["title"] in ("Family and kin", "Where he went") for x in pc.get("drawers") or []):
        f.append(f"{eid}: a being's drawer is titled as a man's (Family and kin, Where he went)")
    if not r or f'href="/p/{r[1]}"' not in h or S._esc(d["verses"][r[0]]) not in h:
        f.append(f"{eid}: the verse {ref} is not quoted with its link")
    return f


seen = 0
for eid in list(S.DEITY_PLATES) + ["moses", "i_am", "abraham", "spirit_of_god"]:
    if eid not in d["ents"]:
        fails.append(f"{eid}: no such record")
        continue
    c = json.loads(S.answer("/api/entity", urlencode({"id": eid})))
    fails += faults(eid, c)
    seen += 1
# planted: the check must catch each
planted = 0
c0 = json.loads(S.answer("/api/entity", urlencode({"id": "god"})))
for what, bad in [("a dropped sketch", dict(c0, deityplate={"html": c0["deityplate"]["html"].replace(SKETCHES["rock"], "")})),
                  ("a missing header", dict(c0, deityplate=None)),
                  ("the fallback face", dict(c0, pcard=None, fbcard={"rows": []})),
                  ("a family drawer on God", dict(c0, pcard=dict(c0["pcard"], drawers=[{"key": "family", "title": "Family and kin"}])))]:
    planted += 1
    if not faults("god", bad):
        fails.append(f"planted: the check did not catch {what}")
planted += 1
if not faults("moses", dict(c0)):
    fails.append("planted: the check did not catch a header on another card")
for m in fails:
    print("FAIL", m)
print(f"deity cards: {len(S.DEITY_PLATES)} headers, {seen} cards checked; planted faults caught: "
      f"{planted - sum(1 for m in fails if m.startswith('planted'))} of {planted}; {len(fails)} failures")
sys.exit(1 if fails else 0)
