"""The I AM card's data against the graph (2026-10-31): every place the original has the words is placed, and the
face's fixture is today's data.

    python -X utf8 tests/test_iam_card.py
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

d = S.load()
fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


def faults(c):
    f = []
    if c["unplaced"]:
        f.append("the original has the words where ontology/iam-card.json places nothing: " + ", ".join(c["unplaced"]))
    for g in c["groups"]:
        for i in g["items"]:
            if not i["words"]:
                f.append(f"{i['ref']}: placed, but the original does not have the words there")
            if not i["text"]:
                f.append(f"{i['ref']}: no verse text")
    seen = [i["go"] for g in c["groups"] for i in g["items"]]
    if len(seen) != len(set(seen)):
        f.append("a verse placed twice")
    for p in c["pairs"]:
        for s in ("a", "b"):
            if len(p[s]["words"]) < 2:
                f.append(f"pair: {p[s]['ref']} lacks the paired words in the original")
    return f


c = S.iam_card(d, "i_am")
check(c is not None, "no I AM card")
for x in faults(c):
    check(False, x)
found = S._iam_found(d)
check(c["total"] == len(found), f"{c['total']} placed, {len(found)} found")
fx = json.loads((ROOT / "tests" / "fixtures" / "iam_card.json").read_text(encoding="utf-8"))
check(fx == json.loads(json.dumps(c, ensure_ascii=False)),
      "tests/fixtures/iam_card.json is stale: rebuild it from S.iam_card(d, 'i_am')")
check(S.iam_card(d, "i_am_he") is None, "another card answers as I AM")

# planted: the check must catch each
planted = 0
for what, plant in [
    ("an unplaced verse", lambda x: x.update(unplaced=["Jhn.8.58"])),
    ("a verse without the words", lambda x: x["groups"][0]["items"][0].update(words=[])),
    ("a verse placed twice", lambda x: x["groups"][1]["items"].append(x["groups"][1]["items"][0])),
]:
    planted += 1
    c2 = copy.deepcopy(c)
    plant(c2)
    check(bool(faults(c2)), f"planted: the check did not catch {what}")

for m in fails:
    print("FAIL", m)
print(f"I AM card: {c['total']} places in {len(c['groups'])} groups, {len(c['pairs'])} pair; planted faults caught: "
      f"{planted - sum(1 for m in fails if m.startswith('planted'))} of {planted}; {len(fails)} failures")
sys.exit(1 if fails else 0)
