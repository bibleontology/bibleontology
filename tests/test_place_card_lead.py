"""A place card leads with what the text tells most there, and a thin one keeps what it has (the place-card layout
review, 2026-11-10).

  - STORY ORDER: the place card's `plcard.story` runs by how much the text tells at the place (each event's mention
    count, the entity's `events[].n`), most first, canon order breaking ties; Bethel's Jeroboam is no longer 16th
  - THE VERSES: /api/entity-verses gives a place its verses (Dothan and Bethel had total 0)
  - THE ORIGINAL WORD: a place's `original` is its own word, counted as its own uses (Dothan's showed the Hebrew
    article: "ha", 35,900 uses, Septuagint τοῦ/ὁ/τῆς)
  - A THIN CARD: Dothan's served page prints both verses that name it (Gen 37:17 and 2 Kgs 6:13)

In process, after the graph loads. Run: python tests/test_place_card_lead.py"""
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


def entity(eid):
    """What /api/entity serves (the place card is added on the route, not by api_entity alone)."""
    return S.json.loads(S.answer("/api/entity", S.urlencode({"id": eid})))

# story order by weight
for pid in ("bethel", "jerusalem"):
    c = entity(pid)
    n = {e["id"]: e.get("n") or 0 for e in c.get("events") or []}
    story = [s["id"] for s in (c.get("plcard") or {}).get("story") or []]
    ns = [n.get(s, 0) for s in story]
    check(story and ns == sorted(ns, reverse=True), f"{pid}: story rows not ordered by mention count: {ns[:8]}")
bethel = [s["id"] for s in (entity("bethel").get("plcard") or {}).get("story") or []]
check("event_jeroboams_idolatry" in bethel[:4], f"Bethel's top four stories lack Jeroboam's idolatry: {bethel[:4]}")

# verses
# Bethel is left out: MACULA gives בֵּית־אֵל no Strong's number (320 names, 1,113 uses unnumbered; HANDOFF), so its
# verses wait for a lemma-text index; its card finds Luz's 7 meanwhile
for pid, least in (("dothan", 2),):
    real = entity(pid).get("id") or pid          # Bethel's record is beth_el; "bethel" is its address
    t = S.api_entity_verses(d, {"id": [real]}).get("total") or 0
    check(t >= least, f"{pid}: entity-verses total {t}, expected at least {least}")

# the original word is the place's own
o = entity("dothan").get("original") or {}
check(o.get("key") == "h1886" and (o.get("uses") or 0) < 10 and o.get("translit") != "ha"
      and not set(o.get("lxx") or []) & {"τοῦ", "ὁ", "τῆς", "τῶν"},
      f"Dothan's original word carries another word's data: {o}")

# a thin card keeps its verses
pg = S.card_page("dothan")
check(pg is not None and "6:13" in pg[1] and "37:17" in pg[1], "Dothan's served page lacks one of its two verses")

print("place cards: story order, verses, original word, thin card" if not fails else f"{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
