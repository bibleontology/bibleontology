"""The event card says what its relations and the Berean editors' notes say, and its page promises only what it prints
(the design panel's event card, 2026-10-29: docs/review/card-panel-appeal/event/designer-notes.md).

  - the CAST is relations whose own verse lies inside the event's telling, each with that verse, in the text's order --
    never a count of mentions (David led Pentecost by it); every named actor has a relation with its verse behind it
  - the NEIGHBORS are tellings in the canon's order (two either side), the Berean editors' headings filling the gaps
  - the QUOTATIONS are the Berean editors' own `quotes` notes inside the telling, as pairs (the quoting verse beside the
    quoted one); "quotes" only where the Berean prints quotation marks around the quoted words, otherwise "recalls"
  - the owner's open rulings (E-A, E-B) are not applied: no cast row on the Holy Spirit's `came_upon`, nothing at Acts
    2:36, and no relation on a divine person was created, merged, relabeled or retyped by building the card
  - the served page carries the neighbors, the cast and the quotations the app shows, and every verse in its title and
    description is a link in its article

The second pass (the whole-app walkthrough, 2026-10-30: docs/review/card-panel-appeal/walkthrough-2026-10-30/joint.md):
  - THE LABEL IS IN ITS VERSE: a cast row stands only where one of its subjects is named in a verse it cites inside the
    telling; the others are counted, never printed ("the Gentiles killed Jesus" cited verses that say "the governor's soldiers")
  - the cast is RANKED (plain words of the event's name first, background facts last, then by the verses of the telling that
    name the actor, then by first appearance), six on the face
  - the STORY on the first screen is the whole telling when it is twelve verses or fewer, else the editors' section that
    names the event (else the one with most cast verses), and the editors' OUTLINE covers the telling section by section
  - the DECK under the title is that section's heading, the editors' own words; the page's description starts with it
  - ONE closed drawer holds the machine's work; the page opens on no process note; the strip never breaks a word; the
    main script's brackets balance (this file has no JavaScript parser, so it counts them)

Every check is proved by a planted fault: a check that cannot fail is not a check.

In process, after the graph loads (~1 minute). Run: python tests/test_event_cards.py"""
import bisect
import copy
import html
import json
import re
import sys
import time
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
EVS = S._events(d)["events"]
DIVINE = S.PC_DIVINE | {"holy_ghost"}


def divine_snapshot():
    return {i: json.dumps(sorted(json.dumps(r, sort_keys=True, default=str) for r in d["rels"].get(i, [])))
            for i in DIVINE if i in d["ents"]}


before = divine_snapshot()
t0 = time.time()
cards, pages = {}, {}
for eid in sorted(EVS):
    if d["ents"].get(eid, {}).get("alias_of"):
        continue
    c = json.loads(S.answer("/api/entity", f"id={eid}"))
    if not c.get("found") or not c.get("evcard"):
        continue                              # a parable keeps its own card
    cards[eid] = c
after = divine_snapshot()
check(before == after, "building the event cards changed a relation on God, the Father, Jesus or the Holy Spirit")


def hrefs(body):
    return set(re.findall(r'href="([^"]+)"', body))


def text_of(body):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)))


def vtext_of(go):
    b, c, v = go.split(".")
    return d["verses"].get((b, int(c), int(v))) or ""


def names_of(i):
    """(words that name a record only as written, names that count in any case), from its own record: a second reading of
    S._ev_forms."""
    e = d["ents"].get(i) or {}
    exact, anycase = set(), set()
    for n in [e.get("name")] + list(e.get("aka") or []) + list(e.get("aka_kjv") or []) + [e.get("name_kjv")]:
        n = re.sub(r"['’]s$", "", re.sub(r"^(the|a|an) ", "", (n or "").strip(), flags=re.I))
        if not n:
            continue
        (anycase if " " in n or n[0].islower() or e.get("type") == "group" else exact).add(n)
        exact |= {t for t in re.findall(r"[A-Z][A-Za-z]{2,}", n) if t.lower() not in S._EV_STOP}
    return exact, anycase


def mentions_name(sid, t, b, cc, v):
    exact, anycase = names_of(sid)
    return (sid in S._ev_ids_at(d, b, cc, v)
            or any(re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", t) for w in exact)
            or any(re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", t, re.I) for w in anycase))


def named_in_cites(r):
    """A subject of the row, or the record the mention layer resolved there, is in a verse the row cites."""
    for c in r["cites"]:
        b, cc, v = c["go"].split(".")
        for s in r["subjects"]:
            sid = (d["ents"].get(s["id"]) or {}).get("alias_of") or s["id"]
            if mentions_name(sid, vtext_of(c["go"]), b, int(cc), int(v)):
                return True
    return False


def spans_of(eid):
    return [(b, lo, hi) for b, lo, hi, _t in S._ev_spans(EVS[eid])]


def key_of(go):
    b, c, v = go.split(".")
    return (S.ORDER.index(b), int(c), int(v))


# ---- 1. the cast: relations whose verse lies in the telling, in the text's order ----------------------------------------
def cast_faults(eid, card):
    out = []
    sp = spans_of(eid)
    rows = card["evcard"]["cast"]
    for r in rows:
        keys = [key_of(c["go"]) for c in r["cites"]]
        if not r["cites"]:
            out.append(f"{eid}: a cast row ({r['verb']} {r['object']['name']}) cites no verse")
        for c in r["cites"]:
            b, cc, v = c["go"].split(".")
            if not any(b == s[0] and s[1] <= (int(cc), int(v)) <= s[2] for s in sp):
                out.append(f"{eid}: {c['ref']} lies outside the telling")
            if (b, int(cc), int(v)) in S.EVENT_WITHHELD_VERSES:
                out.append(f"{eid}: {c['ref']} is withheld (ruling E-B) and stands on the card")
        if r["kind"] in S.EVENT_WITHHELD_KINDS:
            out.append(f"{eid}: a {r['kind']} row stands on the card (ruling E-A)")
        if not named_in_cites(r):
            out.append(f"{eid}: no verse {r['verb']} {r['object']['name']} cites names {[s['name'] for s in r['subjects']]}")
        for s in r["subjects"]:
            # a relation of this subject and this object, of this kind, citing a verse inside the telling
            ok = False
            # the relation is stored at both ends; the graph's two ends are not always both kept (the paralytic's
            # healing is at his end only), so either end's record backs the row
            ends = [(rel, "out") for rel in d["rels"].get(s["id"], []) if rel["other"] == r["object"]["id"]] +                    [(rel, "in") for rel in d["rels"].get(r["object"]["id"], []) if rel["other"] == s["id"]]
            for rel, way in ends:
                if rel["type"] != r["kind"] or rel["dir"] != way:
                    continue
                for ref in rel.get("refs") or []:
                    for x in S._ev_cites(d, [ref], [(b, lo, hi, None) for b, lo, hi in sp]):
                        if x["ref"] in {c["ref"] for c in r["cites"]}:
                            ok = True
            if not ok:
                out.append(f"{eid}: {s['name']} {r['verb']} {r['object']['name']} has no relation with its verse in the telling")
    return out


n_rows = 0
for eid, c in cards.items():
    n_rows += len(c["evcard"]["cast"])
    for f in cast_faults(eid, c):
        check(False, f)
check(n_rows > 500, f"only {n_rows} cast rows over {len(cards)} events")

# the cast of Pentecost and the Flight, as the design settled them with the rulings off
pc, fl = cards["event_pentecost"]["evcard"], cards["event_the_flight_to_egypt"]["evcard"]
check([(" and ".join(s["name"] for s in r["subjects"]), r["verb"], r["object"]["name"]) for r in pc["cast"]] ==
      [("God", "raised up", "Jesus"), ("Simon Peter", "told", "Repent and be baptized")],
      f"Pentecost's cast is {[(r['subjects'][0]['name'], r['verb'], r['object']['name']) for r in pc['cast']]}")
check(not any(c["go"] == "Acts.2.36" for r in pc["cast"] for c in r["cites"]), "Acts 2:36 is on Pentecost's card")
check(not any(r["kind"] == "came_upon" for r in pc["cast"]), "a came_upon row is on Pentecost's card")
check("David" not in {s["name"] for r in pc["cast"] for s in r["subjects"]}, "David is in Pentecost's cast (by mention count)")
check([" and ".join(s["name"] for s in r["subjects"]) for r in fl["cast"]] == ["Herod"],
      f"the Flight's cast is {[[s['name'] for s in r['subjects']] for r in fl['cast']]}")

# planted: a cast member with no relation in the telling
c1 = copy.deepcopy(cards["event_pentecost"])
c1["evcard"]["cast"].append({"subjects": [{"id": "david", "name": "David"}], "verb": "told", "kind": "told",
                             "object": {"id": "repent_and_be_baptized", "name": "x", "type": "text"},
                             "cites": [{"ref": "Acts 2:25", "go": "Acts.2.25"}], "claimed_by": None, "certainty": None})
check(cast_faults("event_pentecost", c1), "planted: a cast member with no relation in the telling was not caught")
c2 = copy.deepcopy(cards["event_pentecost"])
c2["evcard"]["cast"][0]["cites"] = [{"ref": "Acts 3:1", "go": "Acts.3.1"}]
check(cast_faults("event_pentecost", c2), "planted: a cast row citing a verse outside the telling was not caught")


# ---- 1b. the cast is ranked, and a row stands only where its verse names who did it -------------------------------------
def actor_n(eid, sid):
    sid = (d["ents"].get(sid) or {}).get("alias_of") or sid
    return sum(1 for b, lo, hi, _t in S._ev_spans(EVS[eid]) for (c, v) in S._ev_bkeys(d, b) if lo <= (c, v) <= hi
               and mentions_name(sid, d["verses"].get((b, c, v)) or "", b, c, v))


def rank_key(eid, r):
    ev = EVS[eid]
    plain = " ".join([ev["title"]] + [a.get("title") or "" for a in ev.get("aliases") or []])
    tw = S._ev_stems(" ".join(w for w in re.findall(r"[A-Za-z][A-Za-z'’]+", plain) if w[0].islower()))
    hit = bool(tw & S._ev_stems(r["verb"] + " " + r["object"]["name"]))
    return (0 if hit else 2 if r["kind"] in S.EVENT_BACKGROUND else 1, -max(actor_n(eid, s["id"]) for s in r["subjects"]),
            min(key_of(c["go"]) for c in r["cites"]))


def rank_faults(eid, card):
    rows = card["evcard"]["cast"]
    ks = [rank_key(eid, r) for r in rows]
    return [f"{eid}: the cast is not ranked ({rows[i]['subjects'][0]['name']} {rows[i]['verb']} before "
            f"{rows[i + 1]['subjects'][0]['name']} {rows[i + 1]['verb']})" for i in range(len(rows) - 1) if ks[i] > ks[i + 1]]


n_rank = 0
for eid, c in cards.items():
    n_rank += len(c["evcard"]["cast"])
    for f in rank_faults(eid, c):
        check(False, f)
check(all(c["evcard"]["cast_face"] == 6 for c in cards.values()), "the face does not show six cast rows")
# planted: the cast in the text's order where the ranking differs (the first event that has such a case)
planted_rank = None
for eid, c in cards.items():
    rows = c["evcard"]["cast"]
    by_text = sorted(rows, key=lambda r: min(key_of(x["go"]) for x in r["cites"]))
    if len(rows) >= 3 and by_text != rows:
        c3 = copy.deepcopy(c)
        c3["evcard"]["cast"] = copy.deepcopy(by_text)
        planted_rank = (eid, c3)
        break
check(planted_rank and rank_faults(*planted_rank), "planted: a cast in the text's order, not ranked, was not caught")
# planted: a background fact (born at) first, on a card that has one
planted_bg = None
for eid, c in cards.items():
    rows = c["evcard"]["cast"]
    bg = [r for r in rows if r["kind"] in S.EVENT_BACKGROUND]
    if bg and len(rows) > len(bg):
        c3 = copy.deepcopy(c)
        c3["evcard"]["cast"] = copy.deepcopy(bg + [r for r in rows if r["kind"] not in S.EVENT_BACKGROUND])
        planted_bg = (eid, c3)
        break
check(planted_bg and rank_faults(*planted_bg), "planted: a background fact (born at, carried) ahead of the story was not caught")
# the label is in its verse: every row left off names no one in its verses; the Gentiles' row, the women at the cross
n_held = sum(c["evcard"]["cast_held"] for c in cards.values())
held_rows = []
for eid in cards:
    ev = EVS[eid]
    _cast, held, _o, _h = S._ev_cast_face(d, eid, ev, d["ents"][eid], S._ev_spans(ev))
    for r in held:
        held_rows.append((eid, r))
        if named_in_cites(r):
            check(False, f"{eid}: {r['subjects'][0]['name']} {r['verb']} {r['object']['name']} is left off though a verse names the actor")
check(len(held_rows) == n_held and n_held > 100, f"{len(held_rows)} held rows, the cards say {n_held}")
cr = cards["event_crucifixion"]
check(not any(r["verb"] == "appeared to" for r in cr["evcard"]["cast"]), "Jesus 'appeared to' Mary is on the Crucifixion's face (Matt 27:56 lists the women)")
check(not any("Nicodemus" in [s["name"] for s in r["subjects"]] or "Joseph of Arimathaea and Nicodemus" in [s["name"] for s in r["subjects"]]
              for r in cr["evcard"]["cast"]), "Joseph of Arimathaea and Nicodemus 'went to Golgotha' is on the Crucifixion's face")
check(not any("Gentiles" in " ".join(s["name"] for s in r["subjects"]) for r in cr["evcard"]["cast"]), "the Gentiles' row is on the Crucifixion's face")
check(any(e == "event_crucifixion" and r["verb"] == "appeared to" for e, r in held_rows), "the Crucifixion's 'appeared to' row was not counted as left off")
# planted: the Gentiles' row, and a held row put back, on the Crucifixion's card
c6a = copy.deepcopy(cr)
c6a["evcard"]["cast"].append({"subjects": [{"id": "gentiles", "name": "the Gentiles"}], "verb": "killed", "kind": "killed",
                              "object": {"id": "jesus", "name": "Jesus", "type": "person"},
                              "cites": [{"ref": "Matthew 27:27", "go": "Matt.27.27"}, {"ref": "Matthew 27:35", "go": "Matt.27.35"}],
                              "claimed_by": None, "certainty": "explicit"})
check(cast_faults("event_crucifixion", c6a), "planted: 'the Gentiles killed Jesus' on verses that do not say so was not caught")
c6b = copy.deepcopy(cr)
c6b["evcard"]["cast"].append(next(copy.deepcopy(r) for e, r in held_rows if e == "event_crucifixion" and r["verb"] == "appeared to"))
check(cast_faults("event_crucifixion", c6b), "planted: a row left off, put back on the face, was not caught")
# the labels: a saying whose quotation mark opens and never closes (the Resurrection's), a record's "The" mid-sentence
def label_faults(eid, card):
    out = []
    for r in card["evcard"]["cast"]:
        nm = r["object"]["name"]
        if len(re.findall("“", nm)) != len(re.findall("”", nm)):
            out.append(f"{eid}: the saying {nm!r} has a quotation mark that opens and never closes")
        if r["object"]["type"] != "text" and nm.startswith("The "):
            out.append(f"{eid}: {nm!r} stands with a capital 'The' in the middle of a cast row")
    return out


for eid, c in cards.items():
    for f in label_faults(eid, c):
        check(False, f)
check(any(r["object"]["name"].startswith("the ") for c in cards.values() for r in c["evcard"]["cast"]),
      "no cast row lowercases a record's leading 'The' (the Penitent Thief, the Temple)")
c6c = copy.deepcopy(cards["event_resurrection"])
c6c["evcard"]["cast"][0]["object"]["name"] = "Jesus said to her, “Mary"
check(label_faults("event_resurrection", c6c), "planted: the garbled saying (an unclosed quotation mark) was not caught")
c6d = copy.deepcopy(cards["event_crucifixion"])
c6d["evcard"]["cast"][0]["object"] = {"id": "penitent_thief_on_the_cross", "name": "The Penitent Thief", "type": "person"}
check(label_faults("event_crucifixion", c6d), "planted: 'The Penitent Thief' capitalized mid-sentence was not caught")
c4 = copy.deepcopy(cards["event_pentecost"])
c4["evcard"]["cast"][0]["cites"].append({"ref": "Acts 2:36", "go": "Acts.2.36"})
check(cast_faults("event_pentecost", c4), "planted: Acts 2:36 on the card was not caught")
c5 = copy.deepcopy(cards["event_pentecost"])
c5["evcard"]["cast"].insert(0, {"subjects": [{"id": "holy_ghost", "name": "Holy Ghost"}], "verb": "came upon", "kind": "came_upon",
                                "object": {"id": "peter", "name": "Simon Peter", "type": "person"},
                                "cites": [{"ref": "Acts 2:4", "go": "Acts.2.4"}], "claimed_by": None, "certainty": "explicit"})
check(cast_faults("event_pentecost", c5), "planted: the Spirit's came_upon on the card was not caught")


# ---- 2. the neighbors: tellings in the canon's order -----------------------------------------------------------------
def strip_faults(eid, card):
    out = []
    st = card["evcard"]["strip"]
    keys = [key_of(x["first"]) for x in st]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        out.append(f"{eid}: the strip is not in canon order: {[x['label'] for x in st]}")
    me = [x for x in st if x["kind"] == "me"]
    if len(me) != 1 or me[0]["id"] != eid:
        out.append(f"{eid}: the strip does not centre on the event")
    for x in st:
        if x["kind"] == "event" and x["id"] not in EVS:
            out.append(f"{eid}: a neighbor {x['id']} is not an event")
        if x["kind"] == "gap":
            b, c, v = x["first"].split(".")
            sec = S._ev_section(d, b, (int(c), int(v)))
            if not sec or sec["title"] != x["name"]:
                out.append(f"{eid}: the gap {x['name']} is not the Berean editors' heading at {x['first']}")
    return out


n_cells = 0
for eid, c in cards.items():
    n_cells += len(c["evcard"]["strip"])
    for f in strip_faults(eid, c):
        check(False, f)
st = cards["event_pentecost"]["evcard"]["strip"]
check([x["name"] for x in st] == ["Ascension", "Matthias Replaces Judas", "Pentecost", "The Fellowship of Believers",
                                  "Healing of the lame man"], f"Pentecost's strip is {[x['name'] for x in st]}")
check([x["kind"] for x in st] == ["event", "gap", "me", "gap", "event"], "Pentecost's two gaps are not named by the editors' headings")
sf = cards["event_the_flight_to_egypt"]["evcard"]["strip"]
check([x["name"] for x in sf][:2] == ["Birth of Jesus", "The Pilgrimage of the Magi"] and len(sf) == 5,
      f"the Flight's strip is {[x['name'] for x in sf]}")
c6 = copy.deepcopy(cards["event_pentecost"])
c6["evcard"]["strip"][0], c6["evcard"]["strip"][4] = c6["evcard"]["strip"][4], c6["evcard"]["strip"][0]
check(strip_faults("event_pentecost", c6), "planted: a neighbor out of canon order was not caught")
c7 = copy.deepcopy(cards["event_pentecost"])
c7["evcard"]["strip"][1]["name"] = "A heading the editors never wrote"
check(strip_faults("event_pentecost", c7), "planted: a gap that is not the editors' heading was not caught")


# ---- 3. the quotations: the Berean editors' own notes, as pairs ------------------------------------------------------
QI = S._quote_index(d)


def quote_faults(eid, card):
    out = []
    for q in card["evcard"]["quotes"]:
        frm = [x["id"] for x in q["from"]]
        to = {x["id"] for x in q["to"]}
        noted = False
        for fid in frm:
            b, c, v = fid.split(".")
            for other, oend, direction in QI.get(S._macula_ref(d, f"{b}.{c}.{v}"), []):
                if direction == "quotes":
                    ks = set(S._vc_keys(d, S.bsb_ref(d, other), S.bsb_ref(d, oend) if oend else None))
                    if ks & to:
                        noted = True
        if not noted:
            out.append(f"{eid}: {q['from_ref']} {q['verb']} {q['to_ref']} is in none of the editors' notes")
        if not all(S._ev_in(S._ev_spans(EVS[eid]), *(lambda b, c, v: (b, int(c), int(v)))(*x.split("."))) for x in frm):
            out.append(f"{eid}: {q['from_ref']} lies outside the telling")
        inside, has = S._ev_marks(" ".join(x["text"] for x in q["from"]))
        grams = {tuple(w[i:i + 4]) for w in [re.findall(r"[a-z0-9']+", " ".join(x["text"] for x in q["to"]).lower())]
                 for i in range(max(1, len(w) - 3))}
        same = any(tuple(inside[i:i + 4]) in grams for i in range(max(1, len(inside) - 3)))
        if q["verb"] == "quotes" and not (has and same):
            out.append(f"{eid}: {q['from_ref']} 'quotes' {q['to_ref']} and the Berean prints no quotation marks around its words")
        if q["verb"] == "recalls" and has and same:
            out.append(f"{eid}: {q['from_ref']} 'recalls' {q['to_ref']} though the Berean quotes it")
    return out


n_pairs = 0
for eid, c in cards.items():
    n_pairs += len(c["evcard"]["quotes"])
    for f in quote_faults(eid, c):
        check(False, f)
check(n_pairs >= 100, f"only {n_pairs} quotation pairs over {len(cards)} events")
vb = {(q["from_ref"], q["to_ref"]): q["verb"] for q in pc["quotes"]}
check(vb == {("Acts 2:17–21", "Joel 2:28–32"): "quotes", ("Acts 2:25–28", "Psalm 16:8–11"): "quotes",
             ("Acts 2:30", "Psalm 132:11"): "recalls", ("Acts 2:34–35", "Psalm 110:1"): "quotes"}, f"Pentecost's pairs are {vb}")
check(all(q["speaker"] and q["speaker"]["id"] == "peter" for q in pc["quotes"]), "Peter is not named for his four pairs")
check(fl["quotes"] and fl["quotes"][0]["verb"] == "quotes" and fl["quotes"][0]["to_ref"] == "Hosea 11:1"
      and not fl["quotes"][0]["speaker"] and fl["quotes"][0]["excerpt"], "the Flight's pair is not Matt 2:15 and Hosea 11:1, unnamed, its sentence")
q1 = copy.deepcopy(cards["event_pentecost"])
q1["evcard"]["quotes"][0]["to"] = [{"id": "Ps.1.1", "ref": "Psalm 1:1", "text": "Blessed is the man"}]
check(quote_faults("event_pentecost", q1), "planted: a quotation not from the editors' notes was not caught")
q2 = copy.deepcopy(cards["event_pentecost"])
q2["evcard"]["quotes"][2]["verb"] = "quotes"
check(quote_faults("event_pentecost", q2), "planted: 'quotes' where the Berean prints no quotation marks was not caught")
q3 = copy.deepcopy(cards["event_pentecost"])
q3["evcard"]["quotes"][0]["verb"] = "recalls"
check(quote_faults("event_pentecost", q3), "planted: 'recalls' for a quoted passage was not caught")
q4 = copy.deepcopy(cards["event_pentecost"])
q4["evcard"]["quotes"][1]["from"] = [{"id": "Acts.3.1", "ref": "Acts 3:1", "text": "x"}]
check(quote_faults("event_pentecost", q4), "planted: a quoting verse outside the telling was not caught")


# ---- 4. the page promises what the app shows -------------------------------------------------------------------------
def page_faults(eid, card, head, body):
    out = []
    p = card["evcard"]
    links, txt = hrefs(body), text_of(body)
    for x in p["strip"]:
        if x["kind"] == "event" and f'/e/{S._addr(x["id"])}' not in links:
            out.append(f"{eid}: the neighbor {x['name']} is not linked")
        if x["kind"] == "gap" and (x["name"] not in txt or f'/p/{x["first"]}' not in links):
            out.append(f"{eid}: the gap {x['name']} is not printed with its verse link")
    for r in p["cast"]:
        for s in r["subjects"]:
            if f'/e/{S._addr(s["id"])}' not in links:
                out.append(f"{eid}: {s['name']} of the cast is not linked")
        if f'/e/{S._addr(r["object"]["id"])}' not in links or r["verb"] not in txt:
            out.append(f"{eid}: {r['verb']} {r['object']['name']} is not printed")
        for c_ in r["cites"]:
            if f'/p/{c_["go"]}' not in links:
                out.append(f"{eid}: the cast verse {c_['ref']} is not linked")
    for q in p["quotes"]:
        if f'/p/{q["to_go"]}' not in links or f'/p/{q["from_go"]}' not in links:
            out.append(f"{eid}: the pair {q['from_ref']} / {q['to_ref']} is not linked")
        for x in q["to"] + q["from"]:
            if f'/p/{x["id"]}' not in links:
                out.append(f"{eid}: {x['ref']} of a pair is not linked")
        if (q["excerpt"] or q["to"][0]["text"]) not in txt:
            out.append(f"{eid}: the text of {q['to_ref']} is not printed")
        if q["verb"] not in txt:
            out.append(f"{eid}: the word {q['verb']} is not printed")
    title = re.search(r"<title>(.*?)</title>", head).group(1)
    desc = html.unescape(re.search(r'name="description" content="(.*?)"', head).group(1))
    for ref in re.findall(r"(?:\d )?[A-Z][a-z]+(?: [a-z]+)? \d+:\d+", html.unescape(title) + " " + desc):
        sp = S._site_span(d, ref)
        if sp and f"/p/{sp[0]}.{sp[1]}.{sp[2]}" not in links:
            out.append(f"{eid}: {ref} is in the title or description and is not linked in the article")
    return out


t1 = time.time()
for eid in cards:
    r = S.card_page(eid)
    if r:
        pages[eid] = r
        for f in page_faults(eid, cards[eid], r[0], r[1]):
            check(False, f)
check(len(pages) == len(cards), f"{len(cards) - len(pages)} event pages are not served")
hp, bp, _ = pages["event_pentecost"]
hf, bf, _ = pages["event_the_flight_to_egypt"]
for what, fn, eid_, h0, b0 in [
    ("the Joel link removed", lambda b: b.replace('href="/p/Joel.2.28"', 'href="#"'), "event_pentecost", hp, bp),
    ("Acts 2:25 unlinked", lambda b: b.replace('href="/p/Acts.2.25"', 'href="#"'), "event_pentecost", hp, bp),
    ("the cast gone", lambda b: re.sub(r"<h2>Who did what.*?</ul>", "", b, flags=re.S), "event_pentecost", hp, bp),
    ("Simon Peter unlinked", lambda b: b.replace('href="/e/peter"', 'href="#"'), "event_pentecost", hp, bp),
    ("the quotations gone", lambda b: re.sub(r"<h2>The Scriptures.*?(?=<h2>Connections|<p><a href=\"/\">)", "", b, flags=re.S),
     "event_pentecost", hp, bp),
    ("a neighbor unlinked", lambda b: b.replace('href="/e/event_ascension"', 'href="#"'), "event_pentecost", hp, bp),
    ("a gap not printed", lambda b: b.replace("Matthias Replaces Judas", "x"), "event_pentecost", hp, bp),
    ("Hosea 11:1 unlinked", lambda b: b.replace('href="/p/Hos.11.1"', 'href="#"'), "event_the_flight_to_egypt", hf, bf),
    ("Herod unlinked", lambda b: b.replace('href="/e/herod_the_great"', 'href="#"'), "event_the_flight_to_egypt", hf, bf),
]:
    check(page_faults(eid_, cards[eid_], h0, fn(b0)), f"planted: the page check did not catch {what}")
check(page_faults("event_pentecost", cards["event_pentecost"], hp, bp.replace('href="/p/Acts.2.4"', 'href="#"')),
      "planted: the description's Acts 2:4 not linked in the article was not caught")
# the served page: what Google sees
check("Acts 2:4" in re.search(r'name="description" content="(.*?)"', hp).group(1), "Pentecost's description does not quote Acts 2:4")
check(len(re.search(r"<title>(.*?) · Bible Ontology", hp).group(1)) <= 60, "Pentecost's title is over 60 characters")
check("application/ld+json" in hp and '"citation"' in hp, "Pentecost's page carries no JSON-LD citation")
cast_html = re.search(r"<h2>Who did what.*?</ul>", bp, flags=re.S).group(0)
quote_html = bp[bp.index("<h2>The Scriptures"):]
check("Acts 2:36" not in cast_html and "Acts.2.36" not in cast_html and "Acts.2.36" not in quote_html,
      "Acts 2:36 is in the cast or the quotations on Pentecost's page")

# ---- 5. the story, the editors' outline and the deck -----------------------------------------------------------------
def sections_of(eid):
    """The first telling's verses grouped under the Berean editors' headings: [(title, [(c, v)])], read straight from the
    headings table (S._headings), not from the card's own walk."""
    b, lo, hi, _t = S._ev_spans(EVS[eid])[0]
    keys, rows = S._headings(d).get(S.TO_MACULA.get(b, b), ([], []))
    out, prev = [], None
    for k in [k for k in S._ev_bkeys(d, b) if lo <= k <= hi]:
        j = bisect.bisect_right(keys, k) - 1
        if out and j == prev:
            out[-1][1].append(k)
        else:
            out.append((rows[j][0] if j >= 0 else None, [k]))
        prev = j
    return out


def heart_of(eid, card):
    """The section the story is taken from: the heading with the most stems of the event's name, ties to the one with more
    cast verses, then the earlier; else the one with the most cast verses; else the first."""
    ev = EVS[eid]
    secs = sections_of(eid)
    b = S._ev_spans(ev)[0][0]
    cast_keys = {(int(c["go"].split(".")[1]), int(c["go"].split(".")[2])) for r in card["evcard"]["cast"] for c in r["cites"]
                 if c["go"].split(".")[0] == b}
    ts = S._ev_stems(" ".join([ev["title"]] + [a.get("title") or "" for a in ev.get("aliases") or []]))
    sc = [len(ts & S._ev_stems(t or "")) for t, _ks in secs]
    cv = [len(set(ks) & cast_keys) for _t, ks in secs]
    named = any(sc)
    pool = [i for i in range(len(secs)) if sc[i] > 0] or list(range(len(secs)))
    return max(pool, key=lambda i: (sc[i] if named else 0, cv[i], -i)), secs


def norm_title(x):
    return re.sub(r"^the ", "", re.sub(r"[^a-z ]", "", (x or "").lower())).strip()


def story_faults(eid, card):
    out = []
    p = card["evcard"]
    op = p["opening"]
    b, lo, hi, _t = S._ev_spans(EVS[eid])[0]
    total = [k for k in S._ev_bkeys(d, b) if lo <= k <= hi]
    shown = [(int(v["id"].split(".")[1]), int(v["id"].split(".")[2])) for v in (op or {}).get("verses") or []]
    if not shown:
        return [f"{eid}: the card tells no story"]
    for v in op["verses"]:
        if v["text"] != vtext_of(v["id"]):
            out.append(f"{eid}: {v['ref']} is not the Berean's words")
    secs = sections_of(eid)
    if len(total) <= S.EVENT_WHOLE_VERSES:
        if shown != total or not op["whole"]:
            out.append(f"{eid}: a telling of {len(total)} verses is not printed whole")
    else:
        if op["whole"]:
            out.append(f"{eid}: a telling of {len(total)} verses is called whole")
        if secs and secs[0][0] is not None:
            i, secs = heart_of(eid, card)
            title, ks = secs[i]
            if op["section"] != title:
                out.append(f"{eid}: the story is from {op['section']!r}, the heart is {title!r}")
            if shown != ks[:S.EVENT_HEART_VERSES]:
                out.append(f"{eid}: the story is not the first {S.EVENT_HEART_VERSES} verses of {title!r}")
            if op["more"] != len(ks) - len(shown):
                out.append(f"{eid}: the story says {op['more']} verses more, {len(ks) - len(shown)} remain in the section")
    return out


def outline_faults(eid, card):
    out = []
    p = card["evcard"]
    secs = sections_of(eid)
    if len(secs) < 2 or any(t is None for t, _k in secs):
        return [f"{eid}: an outline stands on a telling with fewer than two editors' sections"] if p["outline"] and len(secs) < 2 else []
    got = [(x["title"], x["n"]) for x in p["outline"]]
    want = [(t, len(ks)) for t, ks in secs]
    if got != want:
        out.append(f"{eid}: the outline {got[:4]} is not the editors' sections {want[:4]}")
    b = S._ev_spans(EVS[eid])[0][0]
    for x, (_t, ks) in zip(p["outline"], secs):
        if x["go"] != f"{b}.{ks[0][0]}.{ks[0][1]}":
            out.append(f"{eid}: the section {x['title']!r} does not open at its first verse")
        if x["verses"] and [(int(v["id"].split(".")[1]), int(v["id"].split(".")[2])) for v in x["verses"]] != ks:
            out.append(f"{eid}: the verses of {x['title']!r} are not the section's")
    if sum(x["heart"] for x in p["outline"]) != 1:
        out.append(f"{eid}: the outline marks {sum(x['heart'] for x in p['outline'])} sections as the heart")
    return out


def deck_faults(eid, card):
    out = []
    p = card["evcard"]
    k = p["deck"]
    secs = sections_of(eid)
    if k is None:
        return out
    if k["title"] not in [t for t, _k in secs]:
        out.append(f"{eid}: the deck {k['title']!r} is not one of the editors' headings of the telling")
    if norm_title(k["title"]) == norm_title(EVS[eid]["title"]):
        out.append(f"{eid}: the deck only says the title again")
    if p["opening"] and p["opening"]["section"] and k["title"] != p["opening"]["section"]:
        out.append(f"{eid}: the deck {k['title']!r} is not the section the story is from")
    return out


n_long = n_outl = n_deck = 0
for eid, c in cards.items():
    for f in story_faults(eid, c) + outline_faults(eid, c) + deck_faults(eid, c):
        check(False, f)
    n_long += not c["evcard"]["opening"]["whole"]
    n_outl += bool(c["evcard"]["outline"])
    n_deck += bool(c["evcard"]["deck"])
check(n_long > 100 and n_outl > 100 and n_deck > 100, f"story/outline/deck counts look wrong: {n_long}, {n_outl}, {n_deck}")
for eid, heading in [("event_david_defeats_goliath", "David Slays Goliath"), ("event_red_sea_crossing", "Parting the Red Sea"),
                     ("event_crucifixion", "The Crucifixion"), ("event_pentecost", "The Holy Spirit at Pentecost")]:
    op = cards[eid]["evcard"]["opening"]
    check(op["section"] == heading and not op["whole"], f"{eid}: the story is from {op['section']!r}, not {heading!r}")
check(any(v["id"] == "Acts.2.4" for v in cards["event_pentecost"]["evcard"]["opening"]["verses"]), "Acts 2:4 is not in Pentecost's story")
check(cards["event_pentecost"]["evcard"]["deck"]["title"] == "The Holy Spirit at Pentecost", "Pentecost's deck is not the editors' heading")
check(cards["event_crucifixion"]["evcard"]["deck"] is None, "the Crucifixion's deck says its title again")
check(cards["event_the_flight_to_egypt"]["evcard"]["opening"]["whole"], "the Flight (3 verses) is not told whole")
# planted: the heart picked by position, the story from the wrong section, a telling called whole, a section dropped, a deck invented
g = copy.deepcopy(cards["event_david_defeats_goliath"])
g["evcard"]["opening"]["section"] = g["evcard"]["outline"][0]["title"]
check(story_faults("event_david_defeats_goliath", g), "planted: the story taken from the first section, not the heart, was not caught")
g2 = copy.deepcopy(cards["event_david_defeats_goliath"])
g2["evcard"]["opening"]["verses"] = copy.deepcopy(g2["evcard"]["outline"][0]["verses"][:12])
check(story_faults("event_david_defeats_goliath", g2), "planted: the story's verses from another section were not caught")
g3 = copy.deepcopy(cards["event_david_defeats_goliath"])
g3["evcard"]["opening"]["whole"] = True
check(story_faults("event_david_defeats_goliath", g3), "planted: a 58-verse telling called whole was not caught")
g4 = copy.deepcopy(cards["event_david_defeats_goliath"])
g4["evcard"]["outline"].pop(1)
check(outline_faults("event_david_defeats_goliath", g4), "planted: an outline missing a section was not caught")
g5 = copy.deepcopy(cards["event_david_defeats_goliath"])
g5["evcard"]["outline"].reverse()
check(outline_faults("event_david_defeats_goliath", g5), "planted: an outline out of the text's order was not caught")
g6 = copy.deepcopy(cards["event_pentecost"])
g6["evcard"]["deck"] = {"title": "The Birthday of the Church", "go": "Acts.2.1", "ref": "Acts 2:1–13"}
check(deck_faults("event_pentecost", g6), "planted: a deck that is not the editors' heading was not caught")
g7 = copy.deepcopy(cards["event_pentecost"])
g7["evcard"]["deck"] = {"title": "Pentecost", "go": "Acts.2.1", "ref": "Acts 2:1–13"}
check(deck_faults("event_pentecost", g7), "planted: a deck that only says the title again was not caught")
g8 = copy.deepcopy(cards["event_pentecost"])
g8["evcard"]["opening"]["verses"][1]["text"] = "Suddenly there was a wind."
check(story_faults("event_pentecost", g8), "planted: a story verse that is not the Berean's words was not caught")


# ---- 6. the page: no process note, the description from the heading, the outline linked -------------------------------
def page2_faults(eid, card, head, body):
    out = []
    p = card["evcard"]
    art = body[body.index('<article id="ssr"'):]
    if "Every passage is checked" in art or "an event told in" in art:
        out.append(f"{eid}: the page leads with the process note")
    desc = html.unescape(re.search(r'name="description" content="(.*?)"', head).group(1))
    heading = (p["deck"] or {}).get("title") or p["opening"]["section"]
    if heading and not desc.startswith(heading.rstrip(".")):
        out.append(f"{eid}: the description does not begin with the editors' heading {heading!r}: {desc[:80]!r}")
    for x in p["outline"]:
        if f'href="/p/{x["go"]}"' not in art or x["title"] not in text_of(art):
            out.append(f"{eid}: the section {x['title']!r} of the outline is not printed with its verse link")
    return out


for eid in cards:
    h_, b_, _a = pages[eid]
    for f in page2_faults(eid, cards[eid], h_, b_):
        check(False, f)
check(page2_faults("event_pentecost", cards["event_pentecost"], hp, bp.replace('<article id="ssr" class="ssr">',
      '<article id="ssr" class="ssr"><p>The Flight: an event told in Matthew 2:13–15. Every passage is checked against the Berean text.</p>')),
      "planted: the process note leading the page was not caught")
check(page2_faults("event_pentecost", cards["event_pentecost"], hp.replace('content="The Holy Spirit at Pentecost.', 'content="x.'), bp),
      "planted: a description that does not begin with the editors' heading was not caught")
check(page2_faults("event_pentecost", cards["event_pentecost"], hp, bp.replace('href="/p/Acts.2.14"', 'href="#"')),
      "planted: an outline section without its verse link was not caught")


# ---- 7. the drawer's counts and the names it keeps ---------------------------------------------------------------------
def drawer_faults(eid, card):
    out = []
    p = card["evcard"]
    ev = EVS[eid]
    vk = [(b, c, v) for b, lo, hi, _t in S._ev_spans(ev) for (c, v) in S._ev_bkeys(d, b) if lo <= (c, v) <= hi]
    part = {x["id"] for x in ev["participants"]}
    for i in p["names_in"]:
        if i not in part:
            out.append(f"{eid}: {i} is kept in the names and is not a participant")
            continue
        sid = (d["ents"].get(i) or {}).get("alias_of") or i
        if not any(mentions_name(sid, d["verses"].get((b, c, v)) or "", b, c, v) for b, c, v in vk):
            out.append(f"{eid}: {i} is kept in the names and no verse of the telling has it")
    if not (isinstance(p["cast_held"], int) and isinstance(p["cast_outside"], int)):
        out.append(f"{eid}: the drawer's counts are missing")
    return out


for eid, c in cards.items():
    for f in drawer_faults(eid, c):
        check(False, f)
n_names = sum(len(c["evcard"]["names_in"]) for c in cards.values())
n_parts = sum(len(EVS[e]["participants"]) for e in cards)
check(n_names < n_parts, f"every participant is kept in the names ({n_names} of {n_parts})")
dd = copy.deepcopy(cards["event_pentecost"])
dd["evcard"]["names_in"].append("paddan_aram")
check(drawer_faults("event_pentecost", dd), "planted: a name no verse of the telling has, kept in the drawer, was not caught")

# ---- 8. the page's script and style: the strip, the chips, the one drawer, brackets that balance ------------------------
INDEX = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")


def js_balance(js):
    """'OK', or the first bracket, quote or template literal that does not close (no JavaScript parser here)."""
    i, n, stack, prev, prevword = 0, len(js), [], "", ""

    def err(msg, pos):
        return f"{msg} at line {js.count(chr(10), 0, pos) + 1}: {js[max(0, pos - 40):pos + 40]!r}"
    while i < n:
        c = js[i]
        if stack and stack[-1] == ("tpl",):
            if c == "\\":
                i += 2
            elif c == "`":
                stack.pop()
                prev = "`"
                i += 1
            elif c == "$" and js[i + 1:i + 2] == "{":
                stack.append(("${",))
                prev = "{"
                i += 2
            else:
                i += 1
            continue
        if c in " \t\r\n":
            i += 1
        elif js.startswith("//", i):
            j = js.find("\n", i)
            i = n if j < 0 else j
        elif js.startswith("/*", i):
            j = js.find("*/", i + 2)
            if j < 0:
                return err("unterminated comment", i)
            i = j + 2
        elif c in "'\"":
            j = i + 1
            while j < n and js[j] != c:
                if js[j] == "\\":
                    j += 1
                if js[j] == "\n":
                    return err("newline in string", i)
                j += 1
            i, prev = j + 1, "s"
        elif c == "`":
            stack.append(("tpl",))
            i += 1
        elif c == "/" and (prev in ("", "(", ",", "=", ":", "[", "!", "&", "|", "?", "{", "}", ";", "+", "-", "*", "%", "<", ">", "~", "^")
                           or prevword in ("return", "typeof", "case", "in", "of")):
            j, incls = i + 1, False
            while j < n:
                ch = js[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "[":
                    incls = True
                elif ch == "]":
                    incls = False
                elif ch == "/" and not incls:
                    break
                elif ch == "\n":
                    return err("newline in regex", i)
                j += 1
            i = j + 1
            while i < n and js[i].isalpha():
                i += 1
            prev = "r"
        elif c in "([{":
            stack.append(c)
            prev = c
            i += 1
        elif c in ")]}":
            if c == "}" and stack and stack[-1] == ("${",):
                stack.pop()
            elif not stack or stack[-1] != {")": "(", "]": "[", "}": "{"}[c]:
                return err(f"unexpected {c}", i)
            else:
                stack.pop()
            prev = c
            i += 1
        elif c.isalnum() or c in "_$":
            j = i
            while j < n and (js[j].isalnum() or js[j] in "_$"):
                j += 1
            prevword, prev, i = js[i:j], "w", j
        else:
            prev, prevword = c, ""
            i += 1
    return f"unclosed {stack[-1]} ({len(stack)} open)" if stack else "OK"


def script_faults(html_text):
    out = []
    js = max(re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html_text, re.S), key=len)
    bal = js_balance(js)
    if bal != "OK":
        out.append(f"the main script does not balance: {bal}")
    strip = re.search(r"\.pc-seq \.pc-fn\{[^}]*\}", html_text)
    if not strip or "overflow-wrap:normal" not in strip.group(0) or "min-width:min-content" not in strip.group(0) \
            or re.search(r"overflow-wrap:(break-word|anywhere)|word-break:break", strip.group(0)):
        out.append("a strip cell may break a word (.pc-seq .pc-fn)")
    face = html_text[html_text.index("function eventFace(d){"):html_text.index("function placeFace(d){")]
    if "replace(/^\\S+ /" in face:
        out.append("the section chips strip only the first word of the reference ('Samuel 17:1-11', the book's number lost)")
    if "replace(/^.*?\\s(?=\\d+:\\d+)/" not in face:
        out.append("the section chips do not strip the book label")
    if "E.outline" not in face or "E.deck" not in face:
        out.append("the event face does not print the outline or the deck")
    if not re.search(r"return sec\('ev-machine', 'As the graph stores it',.*?, null, false,", html_text, re.S):
        out.append("the event card's one drawer is not closed")
    blk = html_text[html_text.index("function eventBlock(ev, faced, pzcard){"):html_text.index("/* EVENT TEMPLATES (plan A.9)")]
    for what in ("xrefs", "within", "stampP"):
        if "${faced ? '' : " + what + "}" not in blk:
            out.append(f"the event card still prints {what} down the page")
    if "ccf || evf ? '' : minedSection" not in html_text:
        out.append("the machine-mined patterns still print outside the drawer")
    if "|| evf ? '' : templateBlock(d)" not in html_text:
        out.append("the story-pattern reading still prints outside the drawer")
    return out


for f in script_faults(INDEX):
    check(False, f)
for what, old, new in [
    ("an unclosed template literal", 'const tv = v => `<p class="pc-tv">', 'const tv = v => `<p class="pc-tv">`'),
    ("an unclosed bracket", "const vnum = v => v.ref.replace(/^.*:/, '');", "const vnum = v => v.ref.replace(/^.*:/, ''; "),
    ("a strip cell that breaks words", "overflow-wrap:normal;word-break:normal;hyphens:manual", "overflow-wrap:break-word;hyphens:auto"),
    ("the chip that drops the first word", "h.ref.replace(/^.*?\\s(?=\\d+:\\d+)/, '')", "h.ref.replace(/^\\S+ /, '')"),
    ("an open drawer", "</p>${held}${inner}`, null, false,", "</p>${held}${inner}`, null, true,"),
    ("the cross-references down the page", "${faced ? '' : xrefs}", "${xrefs}"),
]:
    alt = INDEX.replace(old, new, 1)
    check(alt != INDEX and script_faults(alt), f"planted: the script check did not catch {what}")


# ---- the numbers the journal quotes ----------------------------------------------------------------------------------
for eid in ("event_pentecost", "event_the_flight_to_egypt"):
    p = cards[eid]["evcard"]
    body = pages[eid][1]
    print(f"{eid}: cast {len(p['cast'])} rows, {sum(len(r['subjects']) for r in p['cast'])} actors, "
          f"{len({c['go'] for r in p['cast'] for c in r['cites']})} verses cited; strip {len(p['strip'])}; "
          f"pairs {len(p['quotes'])}; page {len(text_of(body).split())} words")
print(f"{len(cards)} events, {n_rows} cast rows, {n_cells} strip cells, {n_pairs} pairs, {len(pages)} pages "
      f"({time.time() - t0:.0f}s), planted faults caught: {planted_n[0] - sum(f.startswith('planted:') for f in fails)} of {planted_n[0]}, "
      f"{len(fails)} failures")
for f in fails[:30]:
    print("FAIL", f)
sys.exit(1 if fails else 0)
