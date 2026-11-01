"""The parable card holds only what the text and the graph say (the design panel's parable card, 2026-10-29:
docs/review/card-panel-appeal/parable/designer-notes.md and mapping-agreed.md).

  - the 22 parable events each have one address, the event's id without event_ (the pearl's parable_of_the_pearl),
    tools/card_slugs.py keeps them, and every older record answers there (the node, the event id, the weeds'
    former address)
  - the sower: 13 "is" marks (12 hearers and Luke 8:11), none from a ground image; 15 answered_in rows, 12 of them
    in its place / 3 the same word, a mark never over another; each mark's words a verbatim part of the Berean's
    verse; the key "The seed is the word of God" (Luke 8:11) and Matthew's own note that it does not say what the seed is
  - scoped by the telling's verses: the seed's key in Galatians 3:16 (the seed is Christ) is on no parable's card
  - a mapping is drawn only for a parable with an explained relation: the net has answered_in rows and no explained
    relation, so it shows none; the pearl and the treasure say the text records no explanation, and nothing else does
  - the owner's rulings of 2026-10-29: the three divine-persons rows are in (they carry `decided`), a held row and an
    undecided one at a divine person are not drawn, and ANS-W05, ANS-S08 and EXP03 stay out
  - the site's voice: no "great price" and no "tares" on the pearl's or the weeds' page, the card or the card data
  - the title (60 or fewer) and description by the rule; every verse in the description, the key and the JSON-LD an
    href in the article; the pearl's steps and frame each a part of the verse, each Greek word in MACULA's
  - the phone: the story and the explanation each carry a label by name and the key line says which is which, and
    the columns appear from 700 px with their headings

Every check is proved by a planted fault: a check that cannot fail is not a check.
In process, after the graph loads (~1 minute). Run: python tests/test_parable_card.py"""
import copy
import html
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
sys.path.insert(0, str(ROOT / "tools"))
import server as S  # noqa: E402
import card_slugs  # noqa: E402

fails = []
planted = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


def caught(name, fn):
    """A planted fault: `fn` must report at least one fault."""
    got = fn()
    planted.append((name, bool(got)))
    if not got:
        fails.append(f"planted fault NOT caught: {name}")


d = S.load()
SRC = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
EVENTS = [x["id"] for x in json.loads((ROOT / "ontology" / "parables.json").read_text(encoding="utf-8"))["events"]]
SLUGS = json.loads((ROOT / "out" / "card-slugs.json").read_text(encoding="utf-8"))
GROUNDS = {"image_way", "image_stony_ground", "image_thorn", "image_good_ground", "image_the_path_in_the_sower"}
KJV = re.compile(r"great price|\btares\b", re.I)
BSB = {k: v for k, v in d["verses"].items()}


def marks(pc):
    return [(b, l, k, m) for b, ls in pc["lanes"].items() for l in ls for k in l["keys"] for m in k["marks"]]


def card_faults(pc, rows):
    """What a card may not hold, held against the rows the graph has."""
    bad = []
    for b, l, k, m in marks(pc):
        r = m["row"]
        if m["kind"] == "is" and (r["src"] in GROUNDS or m["objs"][0] in GROUNDS):
            bad.append(f"an 'is' mark from a ground image: {r['src']}")
        want = r.get("src") and next((x for x in rows if x["src"] == r["src"] and x["dst"] == r["dst"]), None)
        if not want:
            bad.append(f"a mark with no relation behind it: {r['src']} {r['dst']}")
    return bad


def shown_faults(pc, eid):
    """A mapping shown on a parable with no explained relation."""
    ex = [r for r in d["rels"].get(eid, []) if r["type"] == "explained" and r["dir"] == "in"]
    return ["a mapping without an explained relation"] if (marks(pc) or pc["hero"]) and not ex else []


def held_faults(pc, rows):
    """A row held, or at a divine person without the owner's decision, drawn on a card."""
    bad = []
    for b, l, k, m in marks(pc):
        r = m["row"]
        for x in rows:
            if x["src"] == r["src"] and x["dst"] == r["dst"] and (
                    x.get("held") or ({x["src"], x["dst"]} & S.PC_DIVINE and not x.get("decided"))):
                bad.append(f"drawn: {x['src']} {x['dst']}")
    return bad


def forbidden(text):
    return KJV.findall(text)


def page_faults(head, body):
    """The page's description, key and JSON-LD held against what the article links."""
    bad = []
    desc = html.unescape(re.search(r'<meta name="description" content="(.*?)">', head).group(1))
    art = body.split("<article", 1)[1]
    hrefs = set(re.findall(r'href="([^"]+)"', art))
    for v in re.findall(r"\(((?:[1-3] )?[A-Z][a-z]+ \d+:\d+)\)", desc):
        b, cv = v.rsplit(" ", 1)
        c, vn = cv.split(":")
        if f"/p/{b.replace(' ', '')}.{c}.{vn}" not in hrefs:
            bad.append(f"a description verse not linked: {v}")
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', head, re.S)
    if not m:
        return bad + ["no JSON-LD"]
    ld = json.loads(m.group(1).replace("<\\/", "</"))
    ids = []
    for node in ld["@graph"]:
        ids += node.get("citation") or []
        for k in ("bor:told", "bor:explained", "bor:recounts"):
            ids += [x["@id"] for x in (node.get("@reverse") or {}).get(k, [])]
        sg = node.get("bor:signifies")
        if sg:
            ids.append(sg["bor:signifies"]["@id"])
            ids += [x["@id"] for x in sg.get("subjectOf", [])]
    for i in ids:
        if i.replace("https://bibleontology.org", "") not in hrefs:
            bad.append(f"a JSON-LD id the article does not link: {i}")
    return bad


def phone_faults(src):
    bad = []
    for need in ("The story · ", "Jesus explains · ", "What Jesus says it means", "Each pair: <b>the story</b> (shaded)",
                 "@media (min-width:700px)"):
        if need not in src:
            bad.append(f"missing: {need}")
    css = src.split("/* THE PARABLE CARD (parableBlock)", 1)[1].split(".evheads{", 1)[0]
    if ".pz-cols{display:none}" not in css or "(min-width:700px){\n  .pz-cols{display:grid" not in css:
        bad.append("the column headings do not appear only from 700 px")
    return bad


# ---- the 22: one address each, the older records answer there
check(len(EVENTS) == 22, f"22 parable events, got {len(EVENTS)}")
for e in EVENTS:
    want = {"event_parable_of_the_pearl_of_great_price": "parable_of_the_pearl",
            "event_good_samaritan": "parable_of_the_good_samaritan", "event_prodigal_son": "parable_of_the_prodigal_son",
            "event_rich_man_and_lazarus": "rich_man_and_lazarus"}.get(e, e[len("event_"):])
    check(SLUGS.get(e) == want, f"{e}: address {SLUGS.get(e)} not {want}")
    check(card_slugs.parable_address(e) == want, f"card_slugs.parable_address({e})")
check("parable_of_the_tares" not in SLUGS, "the weeds' folded node keeps an address of its own")
check(set(EVENTS) <= card_slugs.all_ids(), "an event id missing from the entity files card_slugs reads")
old = {"parable_of_the_sower": "parable_of_the_sower", "event_parable_of_the_sower": "parable_of_the_sower",
       "parable_of_the_tares": "parable_of_the_weeds", "parable_of_the_weeds_in_the_field": "parable_of_the_weeds",
       "the_pearl_of_great_price": "parable_of_the_pearl", "event_parable_of_the_pearl_of_great_price": "parable_of_the_pearl",
       "the_hireling_flees": "parable_of_the_good_shepherd", "the_door_of_the_sheepfold": "parable_of_the_good_shepherd",
       "the_lost_piece_of_silver": "parable_of_the_lost_coin", "the_treasure_hid_in_a_field": "parable_of_the_hidden_treasure",
       "parable_of_the_unmerciful_servant": "parable_of_the_unforgiving_servant",
       "parable_of_the_lost_sheep": "parable_of_the_lost_sheep", "rich_man_and_lazarus": "rich_man_and_lazarus"}
for o, new in old.items():
    got = S.card_page(o)
    check(got is not None and got[2] == new, f"/e/{o} should answer at {new}, got {got and got[2]}")

# ---- the sower
sower = S.parable_card(d, "event_parable_of_the_sower")
rows = d["meaning_rows"]
mk = marks(sower)
check(sower["title"] == "The Parable of the Sower", f"sower title {sower['title']}")
check(sower["page_title"] == "Parable of the Sower (Matthew 13): What Jesus Says It Means", f"page title {sower['page_title']}")
check(sower["description"].startswith("Jesus explains it himself: “The seed is the word of God” (Luke 8:11)."), sower["description"])
check(sower["hero"] and sower["hero"]["after"] == "the word of God" and sower["hero"]["ref"] == "Luke 8:11", "the sower's key")
check("Matthew does not say what the seed is" in sower["hero_other"]["Matt"]["text"], "Matthew's note on the seed")
check(sower["hero_other"]["Mark"]["ref"] == "Mark 4:14", "Mark's own line on the seed")
check(sum(m["kind"] == "is" for *_, m in mk) == 13, f"13 'is' marks, got {sum(m['kind'] == 'is' for *_, m in mk)}")
srows = [r for r in rows if r["type"] == "answered_in" and r.get("story") and S._pc_key(r["story"][0])[0] in ("Matt", "Mark", "Luke")
         and S._pc_key(r["refs"][0])[1] in (4, 8, 13) and S._pc_key(r["refs"][0])[2] < 24
         and r["src"] in ("image_fowls_of_the_air", "image_sun", "image_root", "image_thorn", "image_fruit", "image_seed", "image_sower")]
check(len(srows) == 15, f"15 answered_in rows on the sower, got {len(srows)}")
check(sum(r["answer_kind"] == "in_its_place" for r in srows) == 12 and sum(r["answer_kind"] == "same_word" for r in srows) == 3,
      "12 in its place and 3 the same word")
check(sower["overlaps"] == [], f"marks overlap: {sower['overlaps']}")
check(not card_faults(sower, rows), card_faults(sower, rows))
for b, l, k, m in mk:
    check(k["text"][m["s"]:m["e"]] in BSB[S._pc_key(k["ref"])], f"mark not a part of {k['ref']}")
    check(m["label"] and m["kind"] in S.PC_KIND_LABEL, "a mark without a label in words")
check(not any(m["meaning"] and m["meaning"]["id"] == "jesus" for *_, m in mk), "Galatians 3:16's key on the sower")
check({r["dst"] for r in rows if r["src"] == "image_seed"} >= {"jesus", "word_of_god"}, "the seed's rows (Gal 3:16 and Luke 8:11) are both in the graph")
check(all(r["src"] not in GROUNDS for r in rows if r["type"] == "signifies"), "a signifies row from a ground image")

# ---- the weeds
weeds = S.parable_card(d, "event_parable_of_the_weeds")
check(weeds["description"] == "Jesus explains it himself: “The field is the world” (Matt 13:38). The story in Matthew, its images and his key, each with a verse.",
      weeds["description"])
check(weeds["page_title"] == "Parable of the Weeds (Matthew 13): What Jesus Says It Means", weeds["page_title"])
wm = marks(weeds)
check(sum(m["kind"] == "is" for *_, m in wm) == 7, f"weeds: 7 'is' marks, got {sum(m['kind'] == 'is' for *_, m in wm)}")
check(any(m["kind"] == "as_so" for *_, m in wm), "the text's own 'as ... so' at Matt 13:40")
check(any(m["meaning"] and m["meaning"]["id"] == "the_son_of_man" and m["meaning"]["link"] for *_, m in wm), "the Son of Man (decided) shown and linked")
check(not any(m["meaning"] and m["meaning"]["link"] for *_, m in wm if m["meaning"] and m["meaning"]["id"] in S.PC_NO_LINK), "a meaning with no card of its own is linked")
check(any(m["kind"] == "in_its_place" and "Son of Man will send out" in k["text"][m["s"]:m["e"]] for _, _, k, m in wm), "ANS-W04 (Matt 13:41) shown")

# ---- the unexplained
for e in ("event_parable_of_the_pearl_of_great_price", "event_parable_of_the_hidden_treasure", "event_parable_of_the_net"):
    pc = S.parable_card(d, e)
    check(pc["lanes"] == {} and not pc["explained"], f"{e} shows a mapping with no explained relation")
check(S.parable_card(d, "event_parable_of_the_pearl_of_great_price")["negative"] == "The text records no explanation of this parable.", "the pearl's line")
check(S.parable_card(d, "event_parable_of_the_hidden_treasure")["negative"], "the treasure's line")
for e in EVENTS:
    pc = S.parable_card(d, e)
    check(pc is not None and pc["overlaps"] == [], f"{e}: a card")
    check(not shown_faults(pc, e), f"{e}: a mapping with no explained relation")
    if e not in ("event_parable_of_the_pearl_of_great_price", "event_parable_of_the_hidden_treasure"):
        check(pc["negative"] is None, f"{e} says the text records no explanation, and has not been checked")
    check(len(pc["page_title"]) <= 60, f"{e}: title {len(pc['page_title'])} characters")
    check(len(pc["description"]) <= 300, f"{e}: description {len(pc['description'])} characters")
net_rows = [r for r in rows if r["type"] == "answered_in" and r["src"].startswith("story_matt_13_48")]
check(len(net_rows) == 2, "the net's two answered_in rows are in the graph, undrawn")
pearl = S.parable_card(d, "event_parable_of_the_pearl_of_great_price")
check(pearl["title"] == "The Parable of the Pearl" and pearl["page_title"] == "Parable of the Pearl (Matthew 13:45–46)", pearl["page_title"])
check(pearl["frame"]["bold"] == "is like" and pearl["frame"]["likened_to"]["word"] == "ἐμπόρῳ", "the pearl's frame")
check(pearl["basis"]["ref"] == "Matt 13:53" and not pearl["basis"]["inside"], "the pearl's basis, after its telling")
for s in pearl["steps"]:
    k = S._pc_key(s["ref"])
    check(s["text"] in BSB[k], f"step not a part of {s['ref']}")
    toks = d["orig"].get(S._vc_mref(d, *k), [])
    check(any(w.get("t", "").strip("·.,;") == s["word"] and re.match(r"^0*%s$" % s["strong"][1:], str(w.get("s") or "")) for w in toks),
          f"step word {s['word']} not MACULA's {s['strong']} at {s['ref']}")
lk = pearl["frame"]["likened_to"]
check(any(w.get("t") == lk["word"] for w in d["orig"].get(S._vc_mref(d, *S._pc_key(lk["ref"])), [])), "the frame's word")

# ---- the owner's rulings of 2026-10-29
ents = d["ents"]
for gone in ("story_matt_13_30_gather_the_wheat", "expl_matt_13_43_righteous_shine", "expl_luke_8_13_no_root", "the_world_kosmos"):
    check(gone not in ents, f"{gone} is held out")
check(not [r for r in d["rels"].get("event_parable_of_the_net", []) if r["type"] == "explained"], "EXP03 stays out")
decided = [r for r in rows if r.get("decided")]
check({(r["src"], r["dst"]) for r in decided} == {("image_one_who_sows_the_good_seed", "the_son_of_man"),
                                                  ("story_matt_13_30_tell_the_harvesters", "expl_matt_13_41_son_of_man_sends_angels")},
      "the two decided rows")
held = {"src": "story_matt_13_30_gather_the_wheat", "dst": "expl_matt_13_43_righteous_shine", "type": "answered_in", "held": True,
        "refs": ["Matt 13:43"], "story": ["Matt 13:30"], "answer_kind": "in_its_place", "story_clause": "gather the wheat into my barn (Matt 13:30)"}
undecided = {"src": "image_one_who_sows_the_good_seed", "dst": "the_son_of_man", "type": "signifies", "refs": ["Matt 13:37"],
             "story": ["Matt 13:24"], "mark": "The One who sows the good seed is", "verb": "is"}
check(not S._pc_shown(held) and not S._pc_shown(undecided) and S._pc_shown(dict(undecided, decided="the owner")), "the held/decided rule")
check(not held_faults(sower, rows) and not held_faults(weeds, rows), "a held or undecided row is drawn")

# ---- the site's voice
for pid in ("parable_of_the_pearl", "parable_of_the_weeds", "parable_of_the_sower"):
    head, body, _ = S.card_page(pid)
    check(not forbidden(html.unescape(head + body)), f"{pid}'s page says {forbidden(head + body)}")
    pc = S.parable_card(d, "event_" + (pid if pid != "parable_of_the_pearl" else "parable_of_the_pearl_of_great_price"))
    check(not forbidden(json.dumps(pc, ensure_ascii=False)), f"{pid}'s card says {forbidden(json.dumps(pc, ensure_ascii=False))}")
for i in ("event_parable_of_the_pearl_of_great_price", "event_parable_of_the_weeds", "the_pearl_of_great_price", "parable_of_the_tares"):
    e = ents[i]
    shown = " ".join([e["name"], e.get("desc") or "", " ".join(e.get("aka") or [])])
    check(not forbidden(shown), f"{i}: {forbidden(shown)} in what is shown")

# ---- the page
for pid in ("parable_of_the_sower", "parable_of_the_weeds", "parable_of_the_pearl"):
    head, body, _ = S.card_page(pid)
    check(not page_faults(head, body), f"{pid}: {page_faults(head, body)}")
    check(len(body) < 40000, f"{pid}: the article is {len(body)} bytes")
sh, sb, _ = S.card_page("parable_of_the_sower")
check("<table>" in sb and sb.count("<tr>") >= 20, "the sower's table")
ph, pb, _ = S.card_page("parable_of_the_pearl")
check("<table>" not in pb and "The text records no explanation of this parable." in pb, "the pearl has no table and says so")
check(not phone_faults(SRC), phone_faults(SRC))

# ---- the planted faults
bad_rows = [dict(r, src="image_the_path_in_the_sower") if r["type"] == "signifies" and r["src"] == "image_seed_sown_along_the_path" else r
            for r in rows]
bad_card = S.parable_card(d, "event_parable_of_the_sower", rows=bad_rows)
caught("an 'is' mark from a ground image", lambda: card_faults(bad_card, bad_rows))
net = S.parable_card(d, "event_parable_of_the_net")
caught("a mapping shown on a parable with no explained relation",
       lambda: shown_faults(dict(net, lanes=sower["lanes"], hero=sower["hero"]), "event_parable_of_the_net"))
# a held row and an undecided divine-persons row, drawn because the rule was switched off: the check sees them
w04 = next(r for r in rows if r["dst"] == "expl_matt_13_41_son_of_man_sends_angels")
w01 = next(r for r in rows if r["dst"] == "the_son_of_man")
planted_rows = [dict(r, held=True) if r is w04 else dict(r, decided=None) if r is w01 else r for r in rows]
keep = S._pc_shown
S._pc_shown = lambda r: True
try:
    leaky = S.parable_card(d, "event_parable_of_the_weeds", rows=planted_rows)
finally:
    S._pc_shown = keep
caught("a held divine-persons row shown (ANS-W04 held, SIG-W01 undecided)", lambda: held_faults(leaky, planted_rows))
caught("KJV 'great price' in the site's voice", lambda: forbidden("The parable of the pearl of great price"))
caught("'tares' in the site's voice", lambda: forbidden("also called the parable of the tares"))
caught("the story and explanation unlabeled on a phone", lambda: phone_faults(SRC.replace("Jesus explains · ", "")))
caught("the columns not held to 700 px", lambda: phone_faults(SRC.replace(".pz-cols{display:none}", ".pz-cols{display:grid}")))
caught("a description verse with no link", lambda: page_faults(sh, sb.replace('href="/p/Luke.8.11"', 'href="/p/x"')))
caught("a JSON-LD id the article does not link", lambda: page_faults(sh, sb.replace('href="/e/word_of_god"', 'href="/e/x"')))
caught("marks laid over one another", lambda: S.parable_card(d, "event_parable_of_the_sower", rows=rows + [
    dict(next(r for r in rows if r["src"] == "image_seed_sown_on_rocky_ground" and r["refs"] == ["Matt 13:20"]),
         mark="seed sown on rocky ground is the one", verb="is")])["overlaps"])

print(f"parable cards: {len(EVENTS)} events, sower {len(mk)} marks ({sum(m['kind'] == 'is' for *_, m in mk)} 'is'), "
      f"weeds {len(wm)} marks; planted and caught: {sum(c for _, c in planted)} of {len(planted)}; {len(fails)} failures")
for f in fails:
    print("FAIL", f)
sys.exit(1 if fails else 0)
