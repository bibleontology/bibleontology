"""The place card says what its relations say, and its page promises only what it prints (the design panel's place
card, 2026-10-29: docs/review/card-panel-appeal/place/designer-notes.md; FAULTS #27 and #28).

  - a place with no relation quotes its own verses, never the passage of an event that merely names it (212 thin
    place pages served the same Joshua 13 block; the count is taken over every place page)
  - a relation its verse contradicts is held (`held_beside`): on no card of either end as a fact, printed on the city's
    card beside its verse
  - Jerusalem's story is told from events whose telling holds a relation of the city or of a place inside it, each
    verse placed in a telling that holds it, of the kinds that say something happened (built, kept at, destroyed,
    based at, repaired) -- never from the kings' rosters; a list of names is one row; every actor has a relation with
    its verse behind it
  - every verse that names a place is served by /api/entity-verses (FAULTS #28: Jerusalem's answer was empty over
    some 800 uses): the union of the verses of its name's words, no more, no fewer
  - the served page carries what the app card shows (events, verses, held relations, the name's words, inside it),
    and every verse and name in a place page's title and description is a link in its article

Every check is proved by a planted fault: a check that cannot fail is not a check.

In process, after the graph loads (~1 minute). Run: python tests/test_place_cards.py"""
import copy
import html
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

fails = []
planted_n = [0]


def check(ok, msg):
    if msg.startswith("planted:"):
        planted_n[0] += 1
    if not ok:
        fails.append(msg)


d = S.load()
PLACES = sorted(e for e, x in d["ents"].items() if x["type"] == "place" and not x.get("alias_of"))
STORY_KINDS = {"built", "kept_at", "destroyed", "based_at", "repaired", "built_repaired"}
HELD6 = {("mount_of_olives", "located_in"), ("golgotha", "located_in"), ("stephen", "died_at"),
         ("sennacherib", "traveled_to"), ("annas", "ruled_from"), ("caiaphas", "ruled_from")}


def hrefs(body):
    return set(re.findall(r'href="([^"]+)"', body))


def text_of(body):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)))


# ---- 1. a place with no relation quotes its own verses -----------------------------------------------------------
def shared_block_faults(eid, c, body):
    """Why this page serves a passage that is not the place's own: the first two verses of an event telling that the
    place neither cites nor names (the Joshua 13 block of 212 thin pages), or none of its own verses when it has no
    relation."""
    out = []
    p = c["plcard"]
    own = {v["id"] for v in p["own"]}
    e_ = d["ents"][eid]
    refs_ = list(e_.get("refs") or []) + [x for r in d["rels"].get(eid, []) for x in r.get("refs") or []]
    cited = {f"{k[0]}.{k[1]}.{k[2]}" for r in refs_ for k in S._place_verses(d, r)}
    vs_ = S._verses_of(d)
    for k in S._place_name_keys(d, eid, e_):
        for m_ in vs_.get(k) or ():
            sp_ = S._site_span(d, m_.replace(".", " ", 1).replace(".", ":", 1))
            if sp_:
                cited.add(f"{sp_[0]}.{sp_[1]}.{sp_[2]}")
    for tl in [t for e_ in c.get("events") or [] for t in S._events(d)["events"][e_["id"]]["tellings"][:1]]:
        try:
            fb, fc, fv = S.bsb_ref(d, tl["first"]).split(".")
        except ValueError:
            continue
        v1 = f"/p/{S.MACULA_BACK.get(fb, fb)}.{fc}.{fv}"
        v2 = f"/p/{S.MACULA_BACK.get(fb, fb)}.{fc}.{int(fv) + 1}"
        key1, key2 = v1[3:], v2[3:]
        if f'href="{v1}"' in body and f'href="{v2}"' in body and key1 not in own | cited and key2 not in own | cited:
            out.append(f"{eid}: serves the telling that starts at {key1} though it neither cites nor names it")
    if p["thin"] and not p["own"]:
        out.append(f"{eid}: no relation and no verse of its own quoted")
    for v in p["own"]:
        if v["text"] not in text_of(body) or f'/p/{v["id"]}"' not in body:
            out.append(f"{eid}: its own verse {v['ref']} is not quoted on the page")
    return out


pages, cards = {}, {}
for eid in PLACES:
    r = S.card_page(eid)
    if not r:
        continue
    pages[eid] = r
    cards[eid] = json.loads(S.answer("/api/entity", f"id={eid}"))
n_thin = sum(1 for c in cards.values() if c["plcard"]["thin"])
for eid, (head, body, addr) in pages.items():
    for f in shared_block_faults(eid, cards[eid], body):
        check(False, f)
# the measured claim: no place page serves the Joshua 13 block it does not cite
josh13 = [e for e, (h, b, a) in pages.items()
          if '/p/Josh.13.1"' in b and '/p/Josh.13.2"' in b and not any(r.startswith("Josh 13:") for r in cards[e].get("refs") or [])]
check(not josh13, f"{len(josh13)} place pages still serve the Joshua 13 block: {josh13[:5]}")
m = cards["michmethah"]
check([v["id"] for v in m["plcard"]["own"]] == ["Josh.16.6", "Josh.17.7"], "Michmethath does not quote Josh 16:6 and 17:7")
check(m["plcard"]["thin"] and m["total_relations"] == 0, "Michmethath is not a place with no relation")
# planted: the old page (the telling of the event that names it) comes back
h_, b_, a_ = pages["michmethah"]
planted = b_ + "".join(f'<li><a href="/p/Josh.13.{i}">13:{i}</a> text</li>' for i in range(1, 4))
check(shared_block_faults("michmethah", m, planted), "planted: the shared Joshua 13 block was not caught")
# planted: a thin place that quotes nothing of its own
m2 = copy.deepcopy(m)
m2["plcard"]["own"] = []
check(shared_block_faults("michmethah", m2, b_), "planted: a thin place with no verse of its own was not caught")
# planted: its own verse's text missing from the page
check(shared_block_faults("michmethah", m, b_.replace(m["plcard"]["own"][1]["text"], "")),
      "planted: a quoted verse missing from the page was not caught")


# ---- 2. a held relation is not a fact, and stands beside its verse ---------------------------------------------------
def held_faults(c_jer, others, page):
    out = []
    if len(c_jer["plcard"]["held"]) != 6:
        out.append(f"Jerusalem holds {len(c_jer['plcard']['held'])} relations beside their verses, not 6")
    for h in c_jer["plcard"]["held"]:
        if not h["verses"]:
            out.append(f"{h['stored']}: held with no verse beside it")
    others_ = {o for o, _t in HELD6}
    for g in c_jer["groups"]:
        for it in g["items"]:
            if it["other"] in others_ and it["type"] in {t for _o, t in HELD6}:
                out.append(f"Jerusalem's card shows {it['name']} ({it['type']}) as a fact")
    for oid, oc in others.items():
        for g in oc["groups"]:
            for it in g["items"]:
                if it["other"] == "jerusalem" and (oid, it["type"]) in HELD6:
                    out.append(f"{oc['name']}'s card shows {it['type']} Jerusalem as a fact")
    head, body, addr = page
    conn = body.split("<h2>Connections</h2>", 1)[1] if "<h2>Connections</h2>" in body else ""
    for oid in others_:
        if f'/e/{S._addr(oid)}"' in conn and not any(
                (it["other"] == oid and it["type"] not in {t for _o, t in HELD6}) for g in c_jer["groups"] for it in g["items"]):
            out.append(f"Jerusalem's page links {oid} among its connections")
    sec = body.split("Relations the verses do not support", 1)
    if len(sec) < 2:
        out.append("Jerusalem's page has no section of held relations")
    else:
        part = sec[1]
        for h in c_jer["plcard"]["held"]:
            if h["stored"] not in html.unescape(part):
                out.append(f"the page does not print {h['stored']} beside its verse")
            for v in h["verses"][:1]:
                if v["text"] not in text_of(part):
                    out.append(f"the page does not print the verse {v['ref']} beside {h['stored']}")
    return out


cj = cards["jerusalem"]
oth = {o: json.loads(S.answer("/api/entity", f"id={o}")) for o, _t in HELD6}
for f in held_faults(cj, oth, pages["jerusalem"]):
    check(False, f"held: {f}")
# planted: a held relation printed as fact on the city's card, on the other end's card, and on the page's connections
cj2 = copy.deepcopy(cj)
cj2["groups"][0]["items"].append({"other": "mount_of_olives", "type": "located_in", "name": "Mount of Olives"})
check(held_faults(cj2, oth, pages["jerusalem"]), "planted: a held relation as fact on the city's card was not caught")
oth2 = copy.deepcopy(oth)
oth2["golgotha"]["groups"][0]["items"].append({"other": "jerusalem", "type": "located_in", "name": "Jerusalem"})
check(held_faults(cj, oth2, pages["jerusalem"]), "planted: a held relation as fact on the other end's card was not caught")
hj, bj, aj = pages["jerusalem"]
bj2 = bj.replace("<h2>Connections</h2>", f'<h2>Connections</h2><ul><li>located in <a href="/e/{S._addr("mount_of_olives")}">x</a></li></ul>')
check(held_faults(cj, oth, (hj, bj2, aj)), "planted: a held relation among the page's connections was not caught")
bj3 = bj.replace("Relations the verses do not support", "Other")
check(held_faults(cj, oth, (hj, bj3, aj)), "planted: a page with no held section was not caught")
cj3 = copy.deepcopy(cj)
cj3["plcard"]["held"][0]["verses"] = []
check(held_faults(cj3, oth, pages["jerusalem"]), "planted: a held relation with no verse beside it was not caught")
# the open ruling (P-A): Lam 1:13 stays as it is, with its verse and no label; nothing relabeled or retyped
check(any("Lam" in x["ref"] for s in cj["plcard"]["says"] for x in s["verses"]), "Lam 1:13 is not printed beside its verse")
check(not any(it["other"] == "god" and it["refs"] == ["Lam 1:13"] for g in cj["groups"] for it in g["items"]),
      "Lam 1:13 is still labeled in the groups")
check(any(r["other"] == "god" and r["type"] and "Lam 1:13" in r["refs"] for r in d["rels"]["jerusalem"]),
      "the Lam 1:13 relation was removed from the graph")


# ---- 3. Jerusalem's story: events, not rosters -------------------------------------------------------------------
def backed(row, node_ids):
    """The row's actor has a relation of this kind with a verse the row cites."""
    want = {c["go"] for c in row["cites"]}
    for n in node_ids:
        for r in d["rels"].get(n, []):
            if r["dir"] != "in" or (row.get("via") and n != row["via"]):
                continue
            members = [m["id"] for m in row.get("members") or []] or [row["other"]]
            if r["other"] not in members or (r["type"] != row["kind"] and row["kind"] != "built_repaired"):
                continue
            have = {S._vlabel(*k) for ref in r.get("refs") or [] for k in S._place_verses(d, ref, 400)}
            if not want or want & have or any(w in have for w in want):
                return True
    return False


def story_faults(c):
    out = []
    p = c["plcard"]
    nodes = ["jerusalem"] + [x["id"] for x in p["inside"]]
    evs = S._events(d)["events"]
    if not any(ev["face"] for ev in p["story"]):
        out.append("no event on the face")
    for ev in p["story"]:
        if ev["id"] not in evs:
            out.append(f"{ev['id']} is not an event")
            continue
        n_by = {}
        for r in ev["rows"]:
            if r["kind"] not in STORY_KINDS:
                out.append(f"{ev['name']}: a {r['kind']} row in the story (a roster, not a telling)")
            if not r["cites"]:
                out.append(f"{ev['name']}: a row with no verse")
            elif not backed(r, nodes):
                out.append(f"{ev['name']}: {r['name']} has no relation with its verse behind it")
            for ct in r["cites"]:
                if ev["id"] not in [e_["id"] for e_ in S.events_at(d, ct["go"])]:
                    out.append(f"{ev['name']}: {ct['go']} is in no telling of it")
            if r["kind"] in ("built", "repaired"):
                n_by[(r["kind"], r.get("via"))] = n_by.get((r["kind"], r.get("via")), 0) + 1
        for k, n in n_by.items():
            if n > 3:
                out.append(f"{ev['name']}: {n} names listed one by one ({k[0]})")
        for v in ev["visits"]:
            if not v["cites"]:
                out.append(f"{ev['name']}: {v['name']} went there with no verse")
            elif not backed(v, nodes):
                out.append(f"{ev['name']}: {v['name']} has no relation with its verse behind it")
    names = {ev["id"] for ev in p["story"] if ev["face"]}
    for want in ("event_temple_built", "event_temple_destroyed", "event_capture_of_jerusalem", "event_temple_dedicated"):
        if want not in names:
            out.append(f"{want} is not a story event of the city")
    return out


for f in story_faults(cj):
    check(False, f"story: {f}")
# the story's rows are the relations of the city and of a place inside it; a king's seat is not among them
temple = next(ev for ev in cj["plcard"]["story"] if ev["id"] == "event_temple_built")
check([(r["name"], r["kind"], r["via"]) for r in temple["rows"]] == [("Solomon", "built", "temple")],
      f"Temple built is not Solomon's building of the temple: {temple['rows']}")
check({"2Chr 3:1", "1Kgs 6:2"} <= {c["go"] for c in temple["rows"][0]["cites"]}, "the temple's building does not cite 2 Chr 3:1 and 1 Kgs 6:2")
check(any(ct["go"] == "Luke 2:27" for ev in cj["plcard"]["story"] if ev["id"] == "event_presentation_in_the_temple"
          for v in ev["visits"] for ct in v["cites"]), "Luke 2:27 is not in the presentation")
check(not any(v["cites"] and v["cites"][0]["go"] in ("Luke 2:46",) for ev in cj["plcard"]["story"]
              if ev["id"] == "event_cleansing_of_the_temple" for v in ev["visits"]), "Luke 2:46 sits in the cleansing")
# the first story row with relations (the story runs by mentions since 2026-11-11, so row 2 may have none)
RI = next(i for i, ev in enumerate(cj["plcard"]["story"]) if ev["rows"])
# planted: the story built from a roster of kings
cj4 = copy.deepcopy(cj)
cj4["plcard"]["story"][RI]["rows"].append({"kind": "ruled_from", "other": "david", "name": "David", "via": None,
                                           "cites": [{"ref": "2Sam 5:5", "go": "2Sam 5:5"}], "certainty": "explicit"})
check(story_faults(cj4), "planted: a kings' row in the story was not caught")
# planted: fifty names listed one by one
cj5 = copy.deepcopy(cj)
ev5 = next(ev for ev in cj5["plcard"]["story"] if ev["id"] == "event_wall_rebuilt")
ev5["rows"] = [{"kind": "repaired", "other": f"x{i}", "name": f"x{i}", "via": "wall_of_jerusalem",
                "cites": [{"ref": "Neh 3:1", "go": "Neh 3:1"}], "certainty": "implied"} for i in range(20)]
check(story_faults(cj5), "planted: a roster listed one by one was not caught")
# planted: an actor with no relation behind him, and a verse in no telling of the event
cj6 = copy.deepcopy(cj)
cj6["plcard"]["story"][RI]["rows"][0]["other"] = "pharaoh"
check(story_faults(cj6), "planted: an actor with no relation was not caught")
cj7 = copy.deepcopy(cj)
cj7["plcard"]["story"][RI]["rows"][0]["cites"] = [{"ref": "Gen 1:1", "go": "Gen 1:1"}]
check(story_faults(cj7), "planted: a verse in no telling of the event was not caught")
# planted: a face with no event
cj8 = copy.deepcopy(cj)
for ev in cj8["plcard"]["story"]:
    ev["face"] = False
check(story_faults(cj8), "planted: an empty face was not caught")


# ---- 4. every verse that names it (FAULTS #28) ---------------------------------------------------------------------
def named_faults(eid, v):
    """The verses served for a place are exactly the verses of its name's words."""
    out = []
    e = d["ents"][eid]
    keys = S._place_name_keys(d, eid, e)
    vs = S._verses_of(d)
    want = {x for k in keys for x in vs.get(k) or ()}
    want = {S.bsb_ref(d, x) for x in want}
    got = {it["eref"] for b in v["books"] for it in b["items"]}
    if len(got) > 0 and v["total"] != len({x for x in want}):
        out.append(f"{eid}: serves {v['total']} verses, its name's words stand in {len(want)}")
    if v["total"] <= 0:
        out.append(f"{eid}: serves no verse")
    # the books are capped per book; every verse of the smaller books is present
    for b in v["books"]:
        if b["n"] <= 300:
            for x in want:
                if x.split(".")[0] == b["book"] and x not in {i["eref"] for i in b["items"]}:
                    out.append(f"{eid}: {x} names it and is not served")
                    break
    return out


vj = json.loads(S.answer("/api/entity-verses", "id=jerusalem"))
vm = json.loads(S.answer("/api/entity-verses", "id=michmethah"))
for eid, v in (("jerusalem", vj), ("michmethah", vm)):
    for f in named_faults(eid, v):
        check(False, f"named: {f}")
check(vj["total"] >= 700, f"Jerusalem is named in {vj['total']} verses")
check(sorted(i["eref"] for b in vm["books"] for i in b["items"]) == ["Jos.16.6", "Jos.17.7"], "Michmethath's verses are not Josh 16:6 and 17:7")
nj = {w["strong"]: w for w in cj["plcard"]["names"]}
check(set(nj) == {"H3389", "H3390", "G2414", "G2419"}, f"Jerusalem's name words are {sorted(nj)}")
import unicodedata  # noqa: E402
# Ἰερουσαλήμ apart from Ἱεροσόλυμα is the lexicon's headword; the public copy fetches the lexicon rather than
# carrying it (README; tools/fetch_lexicon.py), so without it the two share MACULA's lemma (2026-11-01, the gate)
# counted in Greek alone: Strong's Hebrew's 8,674 committed entries passed a count of both (the gate, 2026-11-11)
if sum(1 for k, v in d["lex"].items() if k[:1] == "g" and v.get("definition")) > 3000:
    check(unicodedata.normalize("NFC", nj["G2419"]["lemma"] or "").endswith("ήμ"), f"G2419 is shown as {nj['G2419']['lemma']!r}")
    check(nj["G2419"]["lemma"] != nj["G2414"]["lemma"], "G2419 and G2414 carry the same lemma")
else:
    print("skipped: G2419's lemma (the full lexicon is not on this machine: python tools/fetch_lexicon.py)")
# the verse Ezra 4:8 (Aramaic H3390) and Rev 21:2 (G2419) are served
served = {i["eref"] for b in vj["books"] for i in b["items"]}
check("Ezr.4.8" in served and "Rev.21.2" in served and "Jhn.2.13" in served, "Ezra 4:8, Rev 21:2 or John 2:13 is not served for Jerusalem")
# planted: a verse that names it dropped from the answer
vj2 = copy.deepcopy(vj)
for b in vj2["books"]:
    if b["book"] == "Rev":
        b["items"] = [i for i in b["items"] if i["eref"] != "Rev.21.2"]
check(named_faults("jerusalem", vj2), "planted: a verse that names it missing from the answer was not caught")
vm2 = copy.deepcopy(vm)
vm2["books"][0]["items"].pop()
check(named_faults("michmethah", vm2), "planted: Michmethath's second verse missing was not caught")
check(named_faults("jerusalem", {"total": 0, "books": []}), "planted: an empty answer (FAULTS #28) was not caught")


# ---- 5. the page promises what the app card shows ---------------------------------------------------------------------
def page_faults(eid, c, head, body):
    out = []
    p = c["plcard"]
    links = hrefs(body)
    txt = text_of(body)
    for ev in p["story"]:
        if f'/e/{S._addr(ev["id"])}' not in links:
            out.append(f"the event {ev['name']} is not linked")
        for r in ev["rows"] + ev["visits"]:
            for ct in r["cites"]:
                sp = S._site_span(d, ct["go"])
                if f"/p/{sp[0]}.{sp[1]}.{sp[2]}" not in links:
                    out.append(f"{ev['name']}: {ct['go']} is not linked")
            if r.get("other") and f'/e/{S._addr(r["other"])}' not in links:
                out.append(f"{ev['name']}: {r['name']} is not linked")
    for x in p["inside"]:
        if f'/e/{S._addr(x["id"])}' not in links:
            out.append(f"inside it: {x['name']} is not linked")
    for w in p["names"]:
        if f'/word/{w["strong"]}' not in links:
            out.append(f"its name's word {w['strong']} is not linked")
    for v in p["own"]:
        if f'/p/{v["id"]}' not in links or v["text"] not in txt:
            out.append(f"its own verse {v['ref']} is not quoted")
    for h in p["held"]:
        if h["stored"] not in txt:
            out.append(f"the held relation {h['stored']} is not printed")
    for a in p["aka"]:
        sp = S._site_span(d, a["ref"])
        if f"/p/{sp[0]}.{sp[1]}.{sp[2]}" not in links or a["name"] not in txt:
            out.append(f"{a['name']} ({a['ref']}) is not printed with its verse")
    for x in p["events_canon"]:
        if f'/e/{S._addr(x["id"])}' not in links:
            out.append(f"the event {x['name']} that names it is not linked")
    # every verse and name in the title and description is a link in the article
    title = re.search(r"<title>(.*?)</title>", head).group(1)
    desc = html.unescape(re.search(r'name="description" content="(.*?)"', head).group(1))
    for ref in re.findall(r"(?:\d )?[A-Z][a-z]+(?: [a-z]+)? \d+:\d+", html.unescape(title) + " " + desc):
        sp = S._site_span(d, ref)
        if sp and f"/p/{sp[0]}.{sp[1]}.{sp[2]}" not in links:
            out.append(f"{ref} is in the title or description and is not linked in the article")
    return out


for eid in ("jerusalem", "michmethah", "zion", "temple", "beth_lehem", "mount_of_olives", "golgotha"):
    if eid in pages:
        h, b, a = pages[eid]
        for f in page_faults(eid, cards[eid], h, b):
            check(False, f"page {eid}: {f}")
# every place page: title and description verses linked
n_checked = 0
for eid, (h, b, a) in pages.items():
    for f in page_faults(eid, cards[eid], h, b):
        check(False, f"page {eid}: {f}")
    n_checked += 1
hm, bm, am = pages["michmethah"]
hj, bj, aj = pages["jerusalem"]
# planted: each promise broken in a copy of the page
for what, fn, eid_, h0, b0 in [
    ("Josh 17:7 unlinked", lambda b: b.replace('href="/p/Josh.17.7"', 'href="#"'), "michmethah", hm, bm),
    ("the Hebrew word unlinked", lambda b: b.replace('href="/word/H4366"', 'href="#"'), "michmethah", hm, bm),
    ("Temple built unlinked", lambda b: b.replace(f'href="/e/{S._addr("event_temple_built")}"', 'href="#"'), "jerusalem", hj, bj),
    ("2 Chr 3:1 unlinked", lambda b: b.replace('href="/p/2Chr.3.1"', 'href="#"'), "jerusalem", hj, bj),
    ("Zion unlinked", lambda b: b.replace(f'href="/e/{S._addr("zion")}"', 'href="#"'), "jerusalem", hj, bj),
    ("Jebus' verse unlinked", lambda b: b.replace('href="/p/Josh.18.28"', 'href="#"'), "jerusalem", hj, bj),
    ("the held relations not printed", lambda b: b.replace("Mount of Olives located in Jerusalem", "x"), "jerusalem", hj, bj),
    ("G2419 unlinked", lambda b: b.replace('href="/word/G2419"', 'href="#"'), "jerusalem", hj, bj),
    ("an event that names it unlinked", lambda b: b.replace(f'href="/e/{S._addr("event_triumphal_entry")}"', 'href="#"'), "jerusalem", hj, bj),
]:
    check(page_faults(eid_, cards[eid_], h0, fn(b0)), f"planted: the page check did not catch {what}")
# planted: the title names a verse the article does not link
check(page_faults("michmethah", cards["michmethah"], hm.replace("Joshua 16:6", "Genesis 1:1"), bm),
      "planted: a verse of the title not linked in the article was not caught")

# the app card carries the same facts (the data the app draws is the data the page prints)
check(cj["plcard"]["story_rows"] > 0 and cj["plcard"]["face_events"] >= 8, "Jerusalem's card has no story")
check(cj["type"] == "place" and not cj["plcard"]["own"], "Jerusalem quotes verses of its own and has a story")

print(f"{len(PLACES)} places, {len(pages)} pages checked, {n_thin} with no relation, "
      f"{len(josh13)} serving the Joshua 13 block, planted faults caught: {planted_n[0] - sum(f.startswith('planted:') for f in fails)} of {planted_n[0]}, "
      f"{len(fails)} failures")
for f in fails[:25]:
    print("FAIL", f)
sys.exit(1 if fails else 0)
