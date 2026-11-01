"""The fallback card says only what the graph holds, and its page promises only what it prints (the site spec,
docs/review/card-panel-appeal/site/spec.md, sections 2 and 3; rulings 2026-10-31).

The fallback card is the face of every card no other face applies to: objects, creatures, titles, covenants,
observances, beings, groups, patterns, the sub-themes, and the concepts, people and events whose own face cannot be
built. Under the name, what the text says of it (one row for each stored relation, explicit or implied, never held,
with its verse), the verses those rows cite, where the text names it, one closed drawer.

  F1  `fbcard` is present exactly when no other face applies
  F2  every row stands on stored relations of the card, not held, each with a verse
  F3  no row's label is a schema inverse
  F4  the verse's own verb wins over the typed one
  F5  merging: one row for one other end and one label, with every chip
  F6  no face string holds a text record's name
  F7  the panel's verses are the Berean's, cited by a row, in canon order, at most three
  F8  the word counts and the book counts each sum to the card's verses
  F9  the drawer's relation count equals total_relations
  F10 no note_kjv anywhere in the face or the page
  F11 no British spelling and no archaic word in what the site says
  F12 ruling F-A: the note is in the drawer; under the name only as a verbatim Berean quotation
  F13 the title is at most 60 characters and the description at most 155; each name of the title and each verse of the
      description is linked in the article; the quotation is a piece of the verse
  F14 no title names a divine person
  F15 the page is the server's copy (`ssr`), complete without /api/

Every check is proved by a planted fault: a check that cannot fail is not a check.
In process, after the graph loads (~1 minute). Run: python tests/test_fallback_card.py"""
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
n_checked = [0]


def check(ok, msg):
    n_checked[0] += 1
    if msg.startswith("planted:"):
        planted_n[0] += 1
    if not ok:
        fails.append(msg)


d = S.load()
SAMPLES = ["fishers_of_men", "theme_judgment_r37", "did_evil_in_the_sight_of_the_lord", "tpl_deliverance", "arc_job",
           "steward_of_josephs_house", "good_assessment", "a_father_of_many_nations", "arc_the_flight_to_egypt", "hazo", "renewal"]
CONTROLS = ["abraham", "jerusalem", "event_pentecost", "image_lion", "the_full_armor_of_god", "lion", "object_staff", "amalekites"]
SAMPLES = [x for x in SAMPLES if x in d["ents"]]
CONTROLS = [x for x in CONTROLS if x in d["ents"]]
BRITISH = re.compile(
    r"\b(?:\w*(?:favour|honour|colour|behaviour|neighbour|labour|saviour|harbour)\w*|centre[sd]?|judgement\w*|defence|"
    r"practis(?:e|es|ed|ing)|fulfil|fulfils|whilst|(?:recogni|organi|reali|bapti|summari)s(?:e|es|ed|ing|ation))\b", re.I)
ARCHAIC = re.compile(r"\b(?:hath|doth|saith|thee|thou|thy|thine|hast|unto|wherefore)\b", re.I)
INV_ONLY = {v["inverse"] for v in d["cats"].values()} - {v["label"] for v in d["cats"].values()}
DIVINE_NAMES = {d["ents"][x]["name"] for x in S.PC_DIVINE if x in d["ents"]}
BOOK_OF = {v: k for k, v in S.TITLE.items()}


def api(eid):
    return json.loads(S.answer("/api/entity", S.urlencode({"id": eid})))


def parts(head):
    t = html.unescape(re.search(r"<title>(.*?) · Bible Ontology</title>", head).group(1))
    m = re.search(r'<meta name="description" content="(.*?)">', head)
    return t, html.unescape(m.group(1)) if m else ""


def key_of(go):
    b, c, v = go.split(".")
    return b, int(c), int(v)


def fb_strings(fb):
    """Every string the face prints in the site's voice (not the Berean's verses, not names)."""
    out = [fb["kind"], fb["deck"]["text"] if fb.get("deck") else ""]
    for r in fb["rows"]:
        out += [r["label"], r.get("said") or ""]
    return out


def face_faults(eid, c, head, body, rels=None):
    """What is wrong with this card's fallback face and page, as a list of F-numbered strings."""
    out = []
    fb = c.get("fbcard")
    e = d["ents"][eid]
    rels = d["rels"].get(eid, []) if rels is None else rels
    if not fb:
        return ["F1: no fbcard"]
    dump = json.dumps(fb, ensure_ascii=False)
    face = json.dumps({k: ([{x: y for x, y in r.items() if x != "note"} for r in fb[k]] if k == "rows" else fb[k])
                        for k in ("kind", "name", "aka", "rows", "also", "words", "deck")}, ensure_ascii=False)
    # F2 rows stand on stored relations, not held, each with a verse
    for row in fb["rows"]:
        if not row["refs"]:
            out.append(f"F2: a row with no verse: {row.get('label')}")
        if row["kind"] == "passages":
            ok = any(r["type"] == "speaks_of" and not r.get("held") for r in rels)
        else:
            ok = any(r["other"] == row["id"] and r["dir"] == row["dir"] and not r.get("held")
                     and r.get("certainty") in ("explicit", "implied") and r.get("refs") for r in rels)
        if not ok:
            out.append(f"F2: a row stands on no stored relation: {row.get('name')} {row['label']}")
    # F3 no inverse label
    for row in fb["rows"]:
        if row["label"] in INV_ONLY:
            out.append(f"F3: the label is a schema inverse: {row['label']}")
    # F4 the verse's own verb wins
    for row in fb["rows"]:
        if row["kind"] == "passages":
            continue
        for k in row["refs"]:
            for r in rels:
                if r["type"] == "states" and r["other"] == row["id"] and r["dir"] == row["dir"] and r.get("label_out") \
                        and k["go"] in {x["go"] for x in (S._fb_ref(d, y) for y in r.get("refs") or []) if x}:
                    if row["label"] != r["label_out"]:
                        out.append(f"F4: {row['name']} at {k['ref']} says {row['label']!r}, the verse says {r['label_out']!r}")
    # F5 merging
    seen = {}
    for row in fb["rows"]:
        if row["kind"] == "passages":
            continue
        kk = (row["dir"], row["id"], row["label"])
        if kk in seen:
            out.append(f"F5: {row['name']} {row['label']} is two rows")
        seen[kk] = 1
    # F6 no text record's name on the face
    for o in {r["other"] for r in rels if (d["ents"].get(r["other"]) or {}).get("type") in S.FB_TEXTUAL}:
        nm = d["ents"][o]["name"]
        if len(nm) > 8 and nm in face:
            out.append(f"F6: a text record's name is on the face: {nm}")
    # F7 the panel
    pv = fb["panel"]["verses"]
    cited = {k["go"] for row in fb["rows"] for k in row["refs"]}
    if len(pv) > 3:
        out.append("F7: more than three verses in the panel")
    for v in pv:
        if v["text"] != d["verses"].get(key_of(v["id"])):
            out.append(f"F7: {v['ref']} is not the Berean's")
        if v["id"] not in cited:
            out.append(f"F7: {v['ref']} is cited by no row")
    order = [(S.ORDER.index(key_of(v["id"])[0]),) + key_of(v["id"])[1:] for v in pv]
    if order != sorted(order):
        out.append("F7: the panel is not in canon order")
    # F8 the counts
    tv = S.api_entity_verses(d, {"id": [eid]})["total"]
    if sum(b["n"] for b in fb["books"]) != tv or fb["total_verses"] != tv:
        out.append(f"F8: the books sum to {sum(b['n'] for b in fb['books'])}, the card has {tv}")
    if fb["counted"] and sum(w["n"] for w in fb["words"]) != tv:
        out.append(f"F8: the words sum to {sum(w['n'] for w in fb['words'])}, the card has {tv}")
    # F9 the drawer's count
    if fb["total_relations"] != sum(len(g["items"]) for g in c["groups"]) or fb["total_relations"] != c["total_relations"]:
        out.append("F9: the drawer's relation count is not total_relations")
    # F10 no note_kjv
    if "note_kjv" in dump or "note_kjv" in body:
        out.append("F10: note_kjv on the face or the page")
    # F11 spelling
    for s in fb_strings(fb):
        if BRITISH.search(s or "") or ARCHAIC.search(s or ""):
            out.append(f"F11: British or archaic wording: {s}")
    # F12 ruling F-A
    dk = fb.get("deck")
    if S.RULING_FA:
        if dk and not dk["verbatim"]:
            out.append("F12: F-A is on and a note that is not a Berean quotation stands under the name")
    elif e.get("desc") and not (dk and dk["text"]):
        out.append("F12: F-A is off and the note does not lead")
    if dk and dk["verbatim"]:
        norm = S._fb_unquote(dk["text"])
        if not any(norm in S._fb_unquote(d["verses"].get(key_of(g), "")) for g in [dk["go"]]):
            out.append("F12: the note stands as a quotation and is not in its verse")
    # F13 the title and the description
    title, desc = parts(head)
    today = f"{(c['name'] or eid)[:1].upper() + (c['name'] or eid)[1:]} in the Bible: every verse and connection"
    if title != today:
        if len(title) > 60:
            out.append(f"F13: the title is {len(title)} characters")
        m = re.match(r"^(.*?) in the Bible: (.*)$", title)
        tail = m.group(2) if m else ""
        if m and not re.match(r"^\d+ verses", tail):    # a person's own title ("Hazo in the Bible") names nobody
            for nm in re.split(r", | and ", tail):
                if f">{html.escape(nm)}</a>" not in body and f">{nm}</a>" not in body:
                    out.append(f"F13: {nm!r} of the title is not linked in the article")
    if len(desc) > 155 and desc != "" and c.get("fbcard", {}).get("rows"):
        out.append(f"F13: the description is {len(desc)} characters")
    for mm in re.finditer(r"\(([1-3]? ?[A-Z][A-Za-z ]+?) (\d+):(\d+)\)", desc):
        b = BOOK_OF.get(mm.group(1))
        if not b or f'href="/p/{b}.{mm.group(2)}.{mm.group(3)}"' not in body:
            out.append(f"F13: the description's verse {mm.group(0)} is not linked in the article")
        q = re.search(r": “(.*)”", desc)
        if q and b:
            quote = q.group(1).replace("…", "").strip()
            t = d["verses"].get((b, int(mm.group(2)), int(mm.group(3)))) or ""
            if quote and quote not in t:
                out.append("F13: the description's quotation is not in its verse")
    # F14 no divine person in the title
    for nm in DIVINE_NAMES:
        if re.search(rf"\b{re.escape(nm)}\b", title.split(" in the Bible:")[-1]) and nm not in (c["name"], ):
            out.append(f"F14: the title names {nm}")
    # F15 the page is the server's copy, complete without the API
    if not body.startswith('<article id="ssr" class="ssr">') or "/api/" in body or "/api/" in head:
        out.append("F15: the page is not the server's copy or reaches for /api/")
    if "<h1>" not in body or "What the text says of it" not in body and fb["rows"]:
        out.append("F15: the article does not print the face")
    return out


# ---- the real cards
cards = {}
for eid in SAMPLES:
    c = api(eid)
    head, body, addr = S.card_page(eid)
    cards[eid] = (c, head, body)
    for f in face_faults(eid, c, head, body):
        check(False, f"{eid}: {f}")
check(len(SAMPLES) == 11, f"{len(SAMPLES)} of 11 sample cards found")

# F1: the fallback is present exactly where no other face applies
for eid in CONTROLS:
    c = api(eid)
    check(not c.get("fbcard"), f"F1: {eid} has another face and an fbcard")
for eid in SAMPLES:
    c = cards[eid][0]
    check(bool(c.get("fbcard")) and not any(c.get(k) for k in S.FB_OTHER_FACES), f"F1: {eid} has an fbcard and another face")
BASE = "did_evil_in_the_sight_of_the_lord"     # 24 relations, rows merged over several verses
base_c, base_h, base_b = cards[BASE]
stub = dict(base_c, ccard={"stub": True})
check(S.fallback_card(d, BASE, d["ents"][BASE], stub) is None, "planted: a stub ccard on a fallback card did not make fbcard vanish")

# the planted faults, each in a copy of the card or the page
STW = "steward_of_josephs_house"                 # a title naming Joseph and Jacob's sons
stw_c, stw_h, stw_b = cards[STW]


def caught(tag, eid, c, head, body, rels=None):
    got = face_faults(eid, c, head, body, rels)
    check(any(g.startswith(tag) for g in got), f"planted: {tag} fault not caught on {eid}: {got[:2]}")


def mut(c, fn):
    c2 = copy.deepcopy(c)
    fn(c2["fbcard"])
    return c2


row0 = next(r for r in base_c["fbcard"]["rows"] if r["kind"] == "act")
# F2: a made-up row; a relation marked held
caught("F2", BASE, mut(base_c, lambda f: f["rows"].append({"kind": "act", "dir": "in", "label": "fed", "id": "daniel", "name": "Daniel",
                                                         "otype": "person", "refs": [{"go": "Dan.6.22", "ref": "Dan 6:22", "chapter": "Daniel 6"}],
                                                         "said": "fed", "n": 1})), base_h, base_b)
held = copy.deepcopy(d["rels"][BASE])
for r in held:
    if r["other"] == row0["id"]:
        r["held"] = True
caught("F2", BASE, base_c, base_h, base_b, held)
# F3: an inverse label
inv = sorted(INV_ONLY)[0]
caught("F3", BASE, mut(base_c, lambda f: f["rows"][0].update(label=inv)), base_h, base_b)
# F4: the verse's own verb wins; a `states` relation on the same other end and verse says "committed", the row says "did"
states = copy.deepcopy(d["rels"][BASE]) + [{"dir": row0["dir"], "type": "states", "other": row0["id"], "certainty": "explicit",
                                            "refs": [row0["refs"][0]["ref"]], "label_out": "committed", "label_in": "committed by"}]
caught("F4", BASE, base_c, base_h, base_b, states)
# F5: the row for the sons of Israel is one row with every verse; split it
check(len(row0["refs"]) >= 4, "F5: the merged row does not carry every verse")
caught("F5", BASE, mut(base_c, lambda f: f["rows"].append(copy.deepcopy(next(r for r in f["rows"] if r["kind"] == "act")))), base_h, base_b)
# F6: a text record's name on the face
fm_c, fm_h, fm_b = cards["fishers_of_men"]
txt = next(d["ents"][r["other"]]["name"] for r in d["rels"]["fishers_of_men"] if d["ents"][r["other"]]["type"] in S.FB_TEXTUAL and len(d["ents"][r["other"]]["name"]) > 8)
caught("F6", "fishers_of_men", mut(fm_c, lambda f: f["also"].append({"id": "x", "addr": "x", "name": txt, "kind": "x"})), fm_h, fm_b)
# F7: an altered verse; an uncited verse
TPL = "tpl_deliverance"
tp_c, tp_h, tp_b = cards[TPL]
check(len(tp_c["fbcard"]["panel"]["verses"]) >= 2, "F7: the pattern's panel has fewer than two verses")
caught("F7", TPL, mut(tp_c, lambda f: f["panel"]["verses"][0].update(text=f["panel"]["verses"][0]["text"] + " x")), tp_h, tp_b)
caught("F7", TPL, mut(tp_c, lambda f: f["panel"]["verses"].append({"id": "Gen.1.1", "ref": "Genesis 1:1", "text": d["verses"][("Gen", 1, 1)]})), tp_h, tp_b)
# F8: drop a book (a card with words and books)
WRD = next((x for x in cards if cards[x][0]["fbcard"]["books"]), None)
check(WRD is not None, "F8: no sample has words and books")
if WRD:
    w_c, w_h, w_b = cards[WRD]
    caught("F8", WRD, mut(w_c, lambda f: f["books"].pop()), w_h, w_b)
# F9: the drawer's count
caught("F9", BASE, mut(base_c, lambda f: f.update(total_relations=f["total_relations"] - 1)), base_h, base_b)
# F10: note_kjv
caught("F10", BASE, mut(base_c, lambda f: f["also"].append({"id": "x", "addr": "x", "name": "x", "kind": "note_kjv"})), base_h, base_b)
# F11: wording
caught("F11", BASE, mut(base_c, lambda f: f["rows"][0].update(label="hath done")), base_h, base_b)
caught("F11", BASE, mut(base_c, lambda f: f.update(kind="Verdict of colour")), base_h, base_b)
# F12: F-A on with a note that is not the Berean's
caught("F12", BASE, mut(base_c, lambda f: f.update(deck={"text": "A verdict of the books of Kings", "verbatim": False, "go": "", "ref": ""})), base_h, base_b)
# F13: a quoted word altered; a name unlinked
t, ds = parts(stw_h)
check(t == "Joseph's steward in the Bible: Joseph and Jacob's sons", f"the steward's title is {t!r}")
check(ds.startswith("Joseph charged Joseph's steward (Genesis 43:16): “Take these men to my house"), f"the steward's description is {ds!r}")
caught("F13", STW, stw_c, stw_h.replace("to my house", "to my hut"), stw_b)
caught("F13", STW, stw_c, stw_h, stw_b.replace(">Joseph</a>", ">Joseph<"))
# F14: God first in the rows (the exclusion lifted)
god_row = {"kind": "act", "dir": "in", "label": "sent", "said": "sent", "id": "god", "addr": "god", "name": "God", "otype": "person",
           "claimed_by": None, "implied": False, "n": 1, "passages": [], "note": "",
           "refs": [{"go": "Gen.43.16", "ref": "Gen 43:16", "chapter": "Genesis 43"}]}
c14 = mut(stw_c, lambda f: f["rows"].insert(0, god_row))
saved = S.PC_DIVINE
S.PC_DIVINE = set()
try:
    p14 = S._fallback_page(d, STW, c14)
finally:
    S.PC_DIVINE = saved
caught("F14", STW, stw_c, stw_h.replace(html.escape(parts(stw_h)[0]), html.escape(p14["title"])), stw_b.replace(">Joseph</a>", ">Joseph</a><a>God</a>"))
check("God" not in S._fallback_page(d, STW, c14)["title"], "F14: the title names God")
# F15: the page reaches for the API
caught("F15", STW, stw_c, stw_h, stw_b.replace("</article>", '<a href="/api/entity?id=x">x</a></article>'))

# shipped examples: one chapter, a sole-chapter line
check(cards["good_assessment"][0]["fbcard"]["sole_chapter"] == "Genesis 1", "good's rows do not all cite Genesis 1")
# F-A at both settings, on a sample with a note
NOTE = next((x for x in SAMPLES if d["ents"][x].get("desc") and not cards[x][0]["fbcard"]["deck"]), None)
check(NOTE is not None, "F12: no sample carries a note")
if NOTE:
    S.RULING_FA = False
    try:
        off = S.fallback_card(d, NOTE, d["ents"][NOTE], cards[NOTE][0])
    finally:
        S.RULING_FA = True
    check(off["deck"] and off["deck"]["text"] and not off["deck"]["verbatim"], "F12: with F-A off the note does not lead under the name")
    check(cards[NOTE][0]["fbcard"]["deck"] is None and cards[NOTE][0]["fbcard"]["note_in_drawer"], "F12: with F-A on, the note is not in the drawer")
# a verbatim note stays under the name with its verse
verb = []
for x, ex in d["ents"].items():
    nd = S._fb_unquote(S._plain(ex.get("desc") or ""))
    if len(nd.split()) < 3 or ex.get("alias_of") or ex["type"] in ("text", "passage", "assessment"):
        continue
    for rf in ex.get("refs") or []:
        k = S._fb_ref(d, rf)
        if k and nd in S._fb_unquote(d["verses"].get(k["key"]) or ""):
            verb.append(x)
            break
n_verb = 0
for x in verb[:12]:
    cx = api(x)
    if cx.get("fbcard"):
        n_verb += 1
        check(bool(cx["fbcard"]["deck"] and cx["fbcard"]["deck"]["verbatim"]), f"F12: {x}'s Berean quotation does not stand under the name")

print(f"{len(SAMPLES)} sample cards, {n_checked[0]} checks, planted faults caught: "
      f"{planted_n[0] - sum(f.startswith('planted:') for f in fails)} of {planted_n[0]}, {len(fails)} failures")
for f in fails[:25]:
    print("FAIL", f)
sys.exit(1 if fails else 0)
