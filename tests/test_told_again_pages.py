"""A story told again leads, on the served pages and in the card's data (the told-again layout review, 2026-11-10).

ontology/told-again.jsonl holds 117 pairs of stories whose steps match (Matthew's storm and Jonah's), each with its steps
quoted from both texts (`beats`), where they differ (`differs`) and the telling detail (`distinctive`). The served card
page printed none of the steps, and the group page headed most pairs by verse range with no link to either card.

  - THE CARD'S DATA: /api/entity's relation item for each told-again pair carries `pairs` (the beats, this card's story
    first), `differs` and `distinctive`, from either end (the later story's card and the earlier one's)
  - THE SERVED CARD PAGE: a section printing every step from both texts, both cards linked (/e/...), and where they
    differ; the page's <title> or description names the other story
  - THE GROUP PAGE (/explore/told-again): every pair whose two events exist links both cards

In process, after the graph loads. Run: python tests/test_told_again_pages.py"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg)


d = S.load()
rows = [json.loads(x) for x in (ROOT / "ontology" / "told-again.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()]
both = [r for r in rows if r.get("later_event") in d["ents"] and r.get("earlier_event") in d["ents"]
        and r["later_event"] != r["earlier_event"]]
check(len(both) >= 100, f"only {len(both)} told-again pairs with both events")
storm = next(r for r in rows if r.get("later_event") == "event_calming_the_storm"
             and r.get("earlier_event") == "event_jonah_thrown_overboard_swallowed")


def items(eid):
    return [i for g in S.api_entity(d, {"id": [eid]}).get("groups") or [] for i in g.get("items") or []]


# the card's data, from both ends; this card's story first in each pair
for eid, other, mine in (("event_calming_the_storm", "event_jonah_thrown_overboard_swallowed", 0),
                         ("event_jonah_thrown_overboard_swallowed", "event_calming_the_storm", 1)):
    it = next((i for i in items(eid) if i.get("other") == other and i.get("pairs")), None)
    check(it is not None, f"{eid}: no relation item to {other} carrying its pairs")
    if it:
        check(len(it["pairs"]) == len(storm["beats"]), f"{eid}: {len(it['pairs'])} pairs, the record has "
                                                        f"{len(storm['beats'])}")
        first = it["pairs"][0]
        check(json.dumps(first, ensure_ascii=False).find(storm["beats"][0][mine][1]) <
              json.dumps(first, ensure_ascii=False).find(storm["beats"][0][1 - mine][1]),
              f"{eid}: this card's story is not first in its pairs")
        check(it.get("differs") == storm["differs"] and it.get("distinctive") == storm["distinctive"],
              f"{eid}: differs or distinctive missing from the relation item")

# the served card page
pg = S.card_page("event_calming_the_storm")
check(pg is not None, "no served page for event_calming_the_storm")
if pg:
    head, body = pg[0], pg[1]
    for (a_ref, a_txt), (b_ref, b_txt) in storm["beats"]:
        check(a_txt in body and b_txt in body, f"the storm's page lacks the step {a_txt!r} / {b_txt!r}")
    check('href="/e/event_jonah_thrown_overboard_swallowed"' in body, "the storm's page does not link Jonah's card")
    check(storm["differs"][:60] in __import__("html").unescape(body), "the storm's page does not say where they differ")
    check("Jonah" in re.sub(r"<link[^>]*>", "", head), "the storm's title and description never name Jonah")

# the group page links both cards of every pair
gp = S.explore_page("told-again")
check(gp is not None, "no /explore/told-again page")
if gp:
    unlinked = [r["id"] for r in both if f'href="/e/{S._addr(r["later_event"])}"' not in gp[1]
                or f'href="/e/{S._addr(r["earlier_event"])}"' not in gp[1]]
    check(not unlinked, f"{len(unlinked)} pairs on the group page do not link both cards (e.g. ids {unlinked[:5]})")

print(f"told again: {len(both)} pairs, the storm's card and page, the group page" if not fails
      else f"{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
