"""The object card and the minor kinds (object, creature, being, covenant, observance, title) say only what the graph holds
(docs/review/card-panel-appeal/object/designer-notes.md; rulings OB-A to OB-H).

  - EVERY ROW IS A RELATION THE CARD HOLDS, with a verse it cites; the mark is computed from the relation's certainty
    ("the text says it" only on an explicit one); the lede names only explicit rows; a row whose explicit person, group
    or place at the other end no cited verse names is HELD, never stated (the ark "carried by Moses" and "by David")
  - THE DIVINE: God, the Father and the Holy Spirit have no object card, nor has a title with a divine holder (OB-H);
    building the cards changes no relation on God, the Father, Jesus or the Holy Spirit
  - THE DATA FIXES: the Levites cite Deut 31:25; the ark's "ark of shittim wood" and "oracle" are gone; the rainbow
    is the Berean's word (OB-A); the renamed addresses (OB-F) answer for the Berean's spelling and no href carries the
    King James spelling
  - TITLES AND DESCRIPTIONS: at most 60 and 155 characters; the quote is a verbatim piece of the Berean verse it names;
    every reference in either is a link in the article; no two cards share a title
  - THE PAGE: the JSON-LD names only what the article links and only explicit relations; the index rule (own verses or a
    covenant's or observance's telling, and 100 words) is the page's robots tag
  - the main script's brackets balance (this file has no JavaScript parser, so it counts them)

Every check is proved by a planted fault: a check that cannot fail is not a check.

In process, after the graph loads (~2 minutes). Run: python tests/test_object_cards.py"""
import copy
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


_src = (ROOT / "tests" / "test_event_cards.py").read_text(encoding="utf-8")
exec(re.search(r"def js_balance\(js\):.*?\n\n\n", _src, re.S).group(0))

d = S.load()
t0 = time.time()
DIVINE = S.OB_DIVINE


def divine_snapshot():
    return {i: json.dumps(sorted(json.dumps(r, sort_keys=True, default=str) for r in d["rels"].get(i, [])))
            for i in DIVINE if i in d["ents"]}


before = divine_snapshot()
cards, pages = {}, {}
for i, e in sorted(d["ents"].items()):
    if e.get("type") in S.OB_KINDS and not e.get("alias_of"):
        c = json.loads(S.answer("/api/entity", f"id={i}"))
        if c.get("found") and c.get("obcard"):
            cards[i] = c
            pg = S.card_page(i)
            if pg:
                pages[i] = pg
check(len(cards) >= 440, f"only {len(cards)} object-family cards carry a face")
check(before == divine_snapshot(), "building the object cards changed a relation on God, the Father, Jesus or the Holy Spirit")
DISPLAY = {"object", "creature", "being", "covenant", "observance", "title"}
check(all(d["ents"][i]["type"] in DISPLAY for i in cards), "a card of another kind carries an object face")


def vkey(vid):
    b, c, v = vid.split(".")
    return (b, int(c), int(v))


def card_faults(eid, oc):
    """The faults of one card's data; empty when it is the graph's."""
    out = []
    rels = d["rels"].get(eid, [])
    for b in oc["boxes"]:
        for x in b["rows"]:
            held = [r for r in rels if r["type"] == x["type"] and r["dir"] == x["dir"] and r["other"] == x["id"]]
            if not held:
                out.append(f"{eid}: a row ({x['type']} {x['id']}) that no relation of the card holds")
                continue
            cited = set()
            for r in held:
                cited |= {S._img_vid(k) for k in S._img_verses(d, r["refs"])}
            if not {v["id"] for v in x["vs"]} <= cited:
                out.append(f"{eid}: a row prints a verse its relation does not cite ({x['id']})")
            expl = any(r.get("certainty") == "explicit" for r in held)
            if x["mark"] == 1 and not expl:
                out.append(f"{eid}: {x['id']} marked 'the text says it' on an implied relation")
            if x["mark"] == 2 and expl:
                out.append(f"{eid}: {x['id']} marked implied on an explicit relation")
            ot = d["ents"][x["id"]].get("type")
            if (x["mark"] == 1 and ot in ("person", "group", "place", "creature", "being", "title") and x["id"] not in DIVINE
                    and not x["named"]):
                out.append(f"{eid}: {x['id']} stated though no cited verse names it")
            if x["type"] == "signifies":
                out.append(f"{eid}: a signifies reading stands in a box, not the fold")
    for g in oc["lede"]:
        for n in g["names"]:
            if not any(x["id"] == n["id"] and x["mark"] == 1 for b in oc["boxes"] for x in b["rows"]):
                out.append(f"{eid}: the lede names {n['id']}, which is no explicit row")
    for x in oc["reads"]:
        if x["type"] != "signifies":
            out.append(f"{eid}: a non-reading in the fold of readings")
    return out


def text_faults(eid, oc, head, body):
    out = []
    title, desc = oc["title"], oc["desc"]
    if len(title) > 60:
        out.append(f"{eid}: title over 60 characters ({len(title)})")
    if len(desc) > 155:
        out.append(f"{eid}: description over 155 characters ({len(desc)})")
    m = re.search(r"\(BSB\): “(.+?)”", desc)
    if m:
        ref = desc.split(" (BSB)")[0]
        sp = S._site_span(d, ref)
        if sp and m.group(1) not in d["verses"].get(sp[:3], ""):
            out.append(f"{eid}: the description's quote is not in {ref}")
    links = set(re.findall(r'href="([^"]+)"', body))
    for ref in re.findall(r"\b((?:[1-3] )?[A-Z][a-z]+ \d+:\d+)", desc):
        sp = S._site_span(d, ref)
        if sp and f"/p/{sp[0]}.{sp[1]}.{sp[2]}" not in links:
            out.append(f"{eid}: {ref} in the description is not a link in the article")
    return out


def page_faults(eid, oc, head, body):
    out = []
    links = set(re.findall(r'href="([^"]+)"', body))
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', head, re.S).group(1).replace("<\\/", "</"))
    for node in ld["@graph"]:
        for key, val in list(node.items()):
            if key in ("@id", "subjectOf") or key.startswith("bor:"):
                vals = val if isinstance(val, list) else [val]
                for v in vals:
                    ids = [v] if isinstance(v, str) else [v.get("@id")] + (v.get("subjectOf") or [])
                    for u in ids:
                        if isinstance(u, str) and u.startswith(S.SITE + "/") and "#" not in u and u != f"{S.SITE}/e/{S._addr(eid)}":
                            if u[len(S.SITE):] not in links:
                                out.append(f"{eid}: JSON-LD names {u}, not a link in the article")
    explicit = {x["addr"] for b in oc["boxes"] for x in b["rows"] if x["mark"] == 1}
    implied = {x["addr"] for b in oc["boxes"] for x in b["rows"] if x["mark"] == 2}
    for node in ld["@graph"][2:]:
        a = node["@id"].rsplit("/", 1)[-1]
        if a in implied - explicit:
            out.append(f"{eid}: JSON-LD carries the implied relation to {a}")
    robots = "noindex" in head
    ok = S.ob_indexable(body, oc, len(re.findall(r"Where the text names it", body)) and
                        len(re.findall(r"<p><a href=\"/p/[^\"]+\">", body.split("Where the text names it")[-1])))[2]
    if robots == ok:
        out.append(f"{eid}: robots tag disagrees with the index rule")
    kjv = re.findall(r'href="[^"]*(?:cesar|laver|fowl|favou?red|shittim)[^"]*"', body, re.I)
    if kjv:
        out.append(f"{eid}: a King James spelling in an href: {kjv[0]}")
    return out


n_rows = n_held = 0
titles = {}
for i, c in cards.items():
    oc = c["obcard"]
    n_rows += sum(len(b["rows"]) for b in oc["boxes"])
    n_held += len(oc["held"])
    for f in card_faults(i, oc):
        check(False, f)
    if i in pages:
        head, body, _a = pages[i]
        for f in text_faults(i, oc, head, body) + page_faults(i, oc, head, body):
            check(False, f)
    titles.setdefault(oc["title"], set()).add(i)
for t, ids in titles.items():
    if len(ids) > 1:
        check(False, f"two cards share the title {t!r}: {sorted(ids)}")

# ---- the divine and the held ------------------------------------------------------------------------------------------
for i in ("god", "the_father", "holy_ghost", "jesus"):
    check(i not in cards, f"{i} carries an object face")
divine_titles = [i for i, e in d["ents"].items() if e.get("type") == "title" and any(
    r["other"] in DIVINE and r["type"] in ("titled", "self_designated_as") for r in d["rels"].get(i, []))]
check(len(divine_titles) >= 30 and not [i for i in divine_titles if i in cards],
      "a title with a divine holder carries a face (OB-H) or the list of them is gone")

# ---- the data fixes ---------------------------------------------------------------------------------------------------
ark = cards["ark_of_the_covenant"]["obcard"]
face_ids = {x["id"] for b in ark["boxes"] for x in b["rows"]}
held_ids = {h["id"] for h in ark["held"]}
check({"moses", "david"} <= held_ids and not ({"moses", "david"} & face_ids), "the ark's Moses and David rows are not held")
lev = [r for r in d["rels"]["ark_of_the_covenant"] if r["other"] == "levites" and r["type"] == "carried"][0]
check("Deut 31:25" in lev["refs"] and "Deut 31:26" not in lev["refs"], "the Levites do not cite Deut 31:25")
e_ark = d["ents"]["ark_of_the_covenant"]
check("ark of shittim wood" not in e_ark["aka"] and "oracle" not in e_ark["desc"], "the ark keeps King James wording")
check(d["ents"]["bow_in_the_cloud"]["name"] == "the rainbow in the clouds" and "My rainbow" in d["verses"][("Gen", 9, 13)],
      "the rainbow is not the Berean's word (OB-A)")
check(S._addr("bow_in_the_cloud") == "rainbow_in_the_clouds", "the rainbow has no Berean address")
for old, new in (("cesar", "caesar"), ("cesar_augustus", "caesar_augustus"), ("tiberius_cesar", "tiberius_caesar"),
                 ("the_laver", "basin"), ("sure_covenant_under_nehemiah", "binding_agreement_under_nehemiah")):
    check(S._addr(old) == new and S._card_id(new) == old, f"{old} is not answered at {new}")
check("Yom Kippur" in d["ents"]["day_of_atonement"]["aka"], "the Day of Atonement lacks its searched name (OB-E)")
pg = pages["day_of_atonement"][1]
check("/p/Lev.16.30" in pg or "/p/Lev.16.1" in pg, "the Day of Atonement page prints no part of Leviticus 16")
check(cards["covenant_with_noah"]["obcard"]["passage"]["n"] >= 10, "Noah's covenant does not print its telling")
check(any(b["key"] == "sign" and b["rows"] for b in cards["covenant_with_noah"]["obcard"]["boxes"]), "Noah's covenant has no sign")
check(any(b["key"] == "sign" and b["empty"] for b in cards["covenant_at_sinai"]["obcard"]["boxes"]),
      "Sinai's empty Sign box does not say so")
check(cards["the_high_priest"]["obcard"]["boxes"][0]["rows"], "the high priest's holder is missing")
hubs = [i for i, c in cards.items() if c["obcard"]["hub"]]
check("ark_of_the_covenant" in hubs and "the_altar_of_incense" in hubs, "the tabernacle furnishings lack their hub link")

# ---- the planted faults -----------------------------------------------------------------------------------------------
def planted(msg, fn, base="ark_of_the_covenant"):
    oc = copy.deepcopy(cards[base]["obcard"])
    fn(oc)
    check(bool(card_faults(base, oc)), "planted: " + msg)


def plant_text(msg, fn, base="ark_of_the_covenant"):
    oc = copy.deepcopy(cards[base]["obcard"])
    head, body, _a = pages[base]
    oc, body = fn(oc, body)
    check(bool(text_faults(base, oc, head, body)), "planted: " + msg)


def first_row(oc):
    return next(x for b in oc["boxes"] for x in b["rows"] if x["mark"] == 1)


def f1(oc):
    first_row(oc)["mark"] = 2
planted("an explicit row marked implied", f1)


def f2(oc):
    for b in oc["boxes"]:
        for x in b["rows"]:
            if x["mark"] == 2:
                x["mark"] = 1
planted("an implied row marked 'the text says it'", f2)


def f3(oc):
    first_row(oc)["type"] = "party_to"
planted("a row no relation of the card holds", f3)


def f4(oc):
    first_row(oc)["vs"].append({"id": "Gen.1.1", "ref": "Genesis 1:1", "text": "x"})
planted("a row printing a verse its relation does not cite", f4)


def f5(oc):
    first_row(oc)["named"] = False
planted("a stated row whose verses do not name it", f5)


def f6(oc):
    oc["lede"].append({"label": "Made by", "names": [{"id": "moses", "addr": "moses", "name": "Moses", "go": "", "ref": ""}], "more": 0})
planted("a lede naming an id that is no explicit row", f6)


def f7(oc):
    oc["reads"].append(dict(first_row(oc), type="made"))
planted("a non-reading in the fold of readings", f7)


def f8(oc):
    oc["boxes"][0]["rows"].append(dict(first_row(oc), type="signifies"))
planted("a signifies reading in a box", f8)

plant_text("a title over 60 characters", lambda oc, b: (dict(oc, title="x" * 61), b))
plant_text("a description over 155 characters", lambda oc, b: (dict(oc, desc=oc["desc"] + "x" * 160), b))
plant_text("a quote that is not in its verse", lambda oc, b: (dict(oc, desc=oc["desc"].replace("“", "“Behold ", 1)), b))
plant_text("a reference in the description that the article does not link",
           lambda oc, b: (oc, b.replace('href="/p/Exod.25.10"', 'href="/p/Exod.25.11"')))


def pf(msg, fn, base="ark_of_the_covenant"):
    oc = copy.deepcopy(cards[base]["obcard"])
    head, body, _a = pages[base]
    head, body = fn(head, body)
    check(bool(page_faults(base, oc, head, body)), "planted: " + msg)


pf("JSON-LD naming a verse the article does not link", lambda h, b: (h.replace("/p/Exod.37.1", "/p/Exod.99.1"), b))
pf("a robots tag against the index rule", lambda h, b: (h.replace('<link rel="canonical"', '<meta name="robots" content="noindex, follow">\n<link rel="canonical"'), b))
pf("a King James spelling in an href", lambda h, b: (h, b.replace("</article>", '<a href="/e/cesar_augustus">x</a></article>')))
pf("JSON-LD carrying a card the article does not link", lambda h, b: (h, b.replace('href="/e/bezalel"', 'href="/e/zzz"')))

# a face for a divine being (the guard removed)
saved = S.OB_DIVINE
S.OB_DIVINE = frozenset()
try:
    check(S.object_card(d, "the_father", d["ents"]["the_father"]) is not None, "planted: a divine being's face (guard removed)")
finally:
    S.OB_DIVINE = saved
check(S.object_card(d, "the_father", d["ents"]["the_father"]) is None, "the Father carries an object face")

# the unnamed explicit row goes to the held list
e2 = copy.deepcopy(d["ents"]["passover"])
check(any("Josiah" in h["stored"] for h in cards["passover"]["obcard"]["held"]), "Josiah's keeping, which no cited verse names, is not held")

# the script
html = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
main = max(re.findall(r"<script>(.*?)</script>", html, re.S), key=len)
check(js_balance(main) == "OK", "the main script's brackets: " + str(js_balance(main)))
check(js_balance(main.replace("function objectFace(d){", "function objectFace(d){ (", 1)) != "OK", "planted: an unclosed bracket in objectFace")
check("function objectFace" in main and "obf ? obf.lead" in main, "the object face is not wired into the card")

print(f"{len(cards)} cards, {n_rows} rows, {n_held} held, {len(pages)} pages ({time.time() - t0:.0f}s), "
      f"planted faults caught: {planted_n[0] - len([f for f in fails if f.startswith('planted:')])} of {planted_n[0]}, "
      f"{len([f for f in fails if not f.startswith('planted:')])} failures")
for f in fails[:40]:
    print("FAIL", f)
sys.exit(1 if fails else 0)
