"""The event card leads with what only the graph knows (2026-11-01).

    python -X utf8 tests/test_event_lead.py

Doug: "see if we buried the lead by making the graph findings an afterthought". Both seats found the temptation's
echoes of Israel's wilderness on the fourth screen, below a closed drawer (docs/review/card-panel-appeal/event/
temptation-lead-2026-11-01/). This holds: echoes that passed the story-echo standard come before the passage, the
quoted Scriptures before the cast, each echo marked a reading; Matt 4:7 and 4:10 are two quotations, not one; the
angels of Mark 1:13 "ministered to", never "taught". Each check is proven by a planted fault.
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

S.load()
HTML = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
fails = []


def order_faults(src):
    m = re.search(r"lead: `\$\{told\}(.*?)`,", src)
    if not m:
        return ["the event face's lead line is not found"]
    seq = re.findall(r"\$\{(\w+)\}", m.group(1))
    f = []
    if not seq or seq[0] != "echo":
        f.append(f"the echoes do not lead: {seq}")
    for a, b in (("open", "cast"), ("pairs", "cast"), ("cast", "strip")):
        if a in seq and b in seq and seq.index(a) > seq.index(b):
            f.append(f"{a} comes after {b}")
    if "a reading the graph marks implied" not in src:
        f.append("the echoes are not marked a reading")
    return f


def card_faults(c):
    f = []
    q = [(x["from_ref"], x["to_ref"]) for x in c["evcard"]["quotes"]]
    if ("Matthew 4:7", "Deuteronomy 6:16") not in q or ("Matthew 4:10", "Deuteronomy 6:13") not in q:
        f.append(f"Matt 4:7 and 4:10 are not two quotations: {q}")
    if any(x["verb"] == "taught" for x in c["evcard"]["cast"]):
        f.append("the cast says the angels taught")
    if not any(i["type"] == "re_enacts" and i.get("pairs") for g in c["groups"] for i in g["items"]):
        f.append("the echoes carry no paired words")
    return f


c = json.loads(S.answer("/api/entity", urlencode({"id": "event_jesus_temptation"})))
fails += order_faults(HTML) + card_faults(c)
planted = [
    ("the strip leading", order_faults(HTML.replace("lead: `${told}${echo}${open}", "lead: `${told}${strip}${echo}${open}"))),
    ("the cast before the quotations", order_faults(HTML.replace("${pairs}${cast}", "${cast}${pairs}"))),
    ("the reading mark removed", order_faults(HTML.replace("a reading the graph marks implied", "the graph says"))),
    ("the two quotations joined", card_faults(dict(c, evcard=dict(c["evcard"], quotes=[
        {"from_ref": "Matthew 4:7–10", "to_ref": "Deuteronomy 6:13–16"}])))),
    ("taught", card_faults(dict(c, evcard=dict(c["evcard"], cast=[{"verb": "taught"}])))),
]
caught = sum(1 for _, f in planted if f)
for name, f in planted:
    if not f:
        fails.append(f"planted fault not caught: {name}")
for m in fails:
    print("FAIL", m)
print(f"event lead: the temptation's face checked; planted faults caught: {caught} of {len(planted)}; {len(fails)} failures")
sys.exit(1 if fails else 0)
