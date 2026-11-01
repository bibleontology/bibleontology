"""The group card says only what the graph and the verses hold (docs/review/card-panel-appeal/group/designer-notes.md;
rulings GR-A to GR-E; GR-J holds the Jews).

  - THE JEWS ARE HELD: no group face for `jews`, its relations untouched, its page the one it had
  - EVERY ROW IS A PASSAGE: the verses a row prints are verses a relation of the row cites, in canon order within
    books; each line is a relation the group holds; the verse's own words for who acted ("the Pharisees", "some of the
    Pharisees") are a verbatim piece of the verse printed; a row that names the group in no verse says where it is named
  - MEMBERS: a mark "the verse says it" only where one verse holds the person and the group; a quote is a piece of that
    verse; "listed" only under a verse that names the group
  - THE RECORD'S OWN DESCRIPTION is not on the face (GR-A): nothing like "he pronounces woes on them"
  - THE NAME WORD is one a cited verse holds (Colossae: not ἐκκλησία)
  - TITLES AND DESCRIPTIONS: at most 60 and 155 characters, the quote a verbatim piece of the Berean verse, every
    reference a link in the article, no two groups share a title
  - THE PAGE: the JSON-LD names only what the article links, explicit relations only; the index rule (3 own cited verses
    and 100 words) is the page's robots tag
  - the main script's brackets balance

Every check is proved by a planted fault. In process, after the graph loads (~2 minutes).
Run: python tests/test_group_cards.py"""
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
            for i in DIVINE | {"jews"} if i in d["ents"]}


before = divine_snapshot()
cards, pages = {}, {}
for i, e in sorted(d["ents"].items()):
    if e.get("type") == "group" and not e.get("alias_of"):
        c = json.loads(S.answer("/api/entity", f"id={i}"))
        if c.get("found") and c.get("grcard"):
            cards[i] = c
            pg = S.card_page(i)
            if pg:
                pages[i] = pg
check(len(cards) >= 300, f"only {len(cards)} groups carry a face")
check(before == divine_snapshot(), "building the group cards changed a relation on a divine person or on the Jews")
jc = json.loads(S.answer("/api/entity", "id=jews"))
check(jc.get("found") and not jc.get("grcard") and "jews" not in cards, "the Jews (held, GR-J) carry the new face")
check(S.group_card(d, "jews", d["ents"]["jews"]) is None, "group_card builds a face for the Jews")


def vk(vid):
    b, c, v = vid.split(".")
    return (b, int(c), int(v))


def canon(vid):
    b, c, v = vk(vid)
    return (S.ORDER.index(b), c, v)


def card_faults(eid, gc):
    out = []
    rels = d["rels"].get(eid, [])
    pats = S._gr_pats(d, eid)
    for blk in gc["book_blocks"]:
        last = None
        for r in blk["rows"]:
            if last and canon(r["go"]) < last:
                out.append(f"{eid}: rows out of canon order at {r['head']}")
            last = canon(r["go"])
            cited = set()
            for ln in r["lines"]:
                held = [x for x in rels if x["type"] == ln["type"] and x["dir"] == ln["dir"] and x["other"] == ln["id"]]
                if not held:
                    out.append(f"{eid}: a line ({ln['type']} {ln['id']}) that no relation of the group holds")
                for x in held:
                    cited |= {S._img_vid(k) for k in S._img_verses(d, x["refs"])}
            for v in r["verses"]:
                if v["id"] not in cited:
                    out.append(f"{eid}: {v['ref']} is printed but no line of its row cites it")
                for ph in v.get("hl") or []:
                    if ph not in v["text"]:
                        out.append(f"{eid}: the quoted words {ph!r} are not in {v['ref']}")
                    elif not S._gr_find(ph, pats):
                        out.append(f"{eid}: the quoted words {ph!r} do not hold the group's name")
            named = any(S._gr_find(d["verses"][vk(v["id"])], pats) or S._ev_named(d, eid, *vk(v["id"])) for v in r["verses"])
            if r["mark"] == 1 and not named:
                out.append(f"{eid}: {r['head']} says the verse names the group, and no printed verse does")
            if r["mark"] == 2 and named:
                out.append(f"{eid}: {r['head']} is a reader's link though a printed verse names the group")
    for m in gc["members"]:
        if not any(x["type"] == "member_of" and x["dir"] == "in" and x["other"] == m["id"] for x in rels):
            out.append(f"{eid}: member {m['id']} with no member_of relation")
        if m["mark"] == 1:
            t = d["verses"].get(vk(m["go"]), "")
            if m["quote"] not in t:
                out.append(f"{eid}: member {m['id']}'s quote is not in {m['go']}")
            if not S._gr_find(t, pats) or not S._ev_named(d, m["id"], *vk(m["go"])):
                out.append(f"{eid}: {m['id']} marked 'the verse says it' and the verse lacks the person or the group")
        if m["mark"] == 2 and not m["how"]:
            out.append(f"{eid}: {m['id']} marked listed without the heading it is listed under")
    nw = gc["name_word"]
    if nw:
        cited_m = {S.macula_ref(*vk(v)) for blk in gc["book_blocks"] for r in blk["rows"] for ln in r["lines"] for v in ln["vids"]}
        cited_m |= {S.macula_ref(*vk(v)) for m in gc["members"] for v in m["vids"]}
        if not cited_m & set(S._verses_of(d).get(nw["key"]) or ()):
            out.append(f"{eid}: the name word {nw['key']} stands in no verse the group cites")
    if re.search(r"pronounces woes|divided over|party within Israel", json.dumps(gc, ensure_ascii=False)):
        out.append(f"{eid}: the record's own description is on the face (GR-A)")
    return out


def text_faults(eid, gc, head, body):
    out = []
    title, desc = gc["title"], gc["desc"]
    if len(title) > 60:
        out.append(f"{eid}: title over 60 characters")
    if len(desc) > 155:
        out.append(f"{eid}: description over 155 characters")
    m = re.search(r"\(BSB\): “(.+?)”", desc)
    if m:
        sp = S._site_span(d, re.search(r"((?:[1-3] )?[A-Z][a-z]+ \d+:\d+) \(BSB\)", desc).group(1))
        if sp and m.group(1) not in d["verses"].get(sp[:3], ""):
            out.append(f"{eid}: the description's quote is not in its verse")
    links = set(re.findall(r'href="([^"]+)"', body))
    for ref in re.findall(r"\b((?:[1-3] )?[A-Z][a-z]+ \d+:\d+)", desc):
        sp = S._site_span(d, ref)
        if sp and f"/p/{sp[0]}.{sp[1]}.{sp[2]}" not in links:
            out.append(f"{eid}: {ref} in the description is not a link in the article")
    return out


def page_faults(eid, gc, head, body):
    out = []
    links = set(re.findall(r'href="([^"]+)"', body))
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', head, re.S).group(1).replace("<\\/", "</"))
    me = f"{S.SITE}/e/{S._addr(eid)}"
    for node in ld["@graph"]:
        for key, val in node.items():
            if key == "@id" or key == "subjectOf" or key.startswith("bor:"):
                for v in val if isinstance(val, list) else [val]:
                    ids = [v] if isinstance(v, str) else [v.get("@id")] + list(v.get("subjectOf") or [])
                    for u in ids:
                        if isinstance(u, str) and u.startswith(S.SITE + "/") and "#" not in u and u != me:
                            if u[len(S.SITE):] not in links:
                                out.append(f"{eid}: JSON-LD names {u}, not a link in the article")
    implied = {x["addr"] for blk in gc["book_blocks"] for r in blk["rows"] for x in r["lines"] if x["certainty"] != "explicit"}
    explicit = {x["addr"] for blk in gc["book_blocks"] for r in blk["rows"] for x in r["lines"] if x["certainty"] == "explicit"}
    th = ld["@graph"][1]
    for key, val in th.items():
        if key.startswith("bor:"):
            for v in val:
                a = v["@id"].rsplit("/", 1)[-1]
                if a in implied - explicit:
                    out.append(f"{eid}: JSON-LD carries the implied relation to {a}")
    ok = S.gr_indexable(body, gc["counts"]["own"])[2]
    if ("noindex" in head) == ok:
        out.append(f"{eid}: robots tag disagrees with the index rule")
    return out


n_rows = 0
titles = {}
for i, c in cards.items():
    gc = c["grcard"]
    n_rows += gc["counts"]["rows"]
    for f in card_faults(i, gc):
        check(False, f)
    if i in pages:
        head, body, _a = pages[i]
        for f in text_faults(i, gc, head, body) + page_faults(i, gc, head, body):
            check(False, f)
    titles.setdefault(gc["title"], set()).add(i)
for t, ids in titles.items():
    if len(ids) > 1:
        check(False, f"two groups share the title {t!r}: {sorted(ids)}")

# ---- the examples ----------------------------------------------------------------------------------------------------
ph = cards["pharisees"]["grcard"]
check(any(m["id"] == "nicodemus" and m["mark"] == 1 and "Nicodemus" in m["quote"] for m in ph["members"]), "Nicodemus is not 'the verse says it'")
phr = [p for blk in ph["book_blocks"] for r in blk["rows"] for p in r["phrases"]]
check("some Pharisees" in phr or "some of the Pharisees" in phr, "no quantifier phrase ('some Pharisees') is quoted")
check(any(r["near"] for blk in ph["book_blocks"] for r in blk["rows"]), "no pronoun row says where the group is named (Luke 11:54)")
cc = cards["church_at_colosse"]["grcard"]
check(not cc["name_word"] or cc["name_word"]["key"] != "g1577", "Colossae carries the word ἐκκλησία, which no cited verse holds")
check("noindex" in pages["church_at_colosse"][0], "the thin Colossae page is not noindex")
check("noindex" not in pages["pharisees"][0], "the Pharisees page is noindex")
check(ph["title"].startswith("Who Were"), "the Pharisees' title is not the question form (GR-D)")
check(d["cats"]["based_at"]["label"] == "centered on", "the based_at label is British: " + d["cats"]["based_at"]["label"])

# ---- the planted faults ----------------------------------------------------------------------------------------------
def planted(msg, fn, base="pharisees"):
    gc = copy.deepcopy(cards[base]["grcard"])
    fn(gc)
    check(bool(card_faults(base, gc)), "planted: " + msg)


def rowone(gc):
    return gc["book_blocks"][0]["rows"][0]


def g1(gc):
    rowone(gc)["lines"][0]["type"] = "ate"
planted("a line no relation of the group holds", g1)


def g2(gc):
    rowone(gc)["verses"].append({"id": "Gen.1.1", "ref": "Genesis 1:1", "text": "x", "hl": []})
planted("a printed verse its row does not cite", g2)


def g3(gc):
    rowone(gc)["verses"][0]["hl"] = ["the Sadducees"]
planted("quoted words that are not in the verse", g3)


def g4(gc):
    gc["book_blocks"][0]["rows"].reverse()
    gc["book_blocks"][0]["rows"][0]["go"] = "Matt.99.1"
planted("rows out of canon order", g4)


def g5(gc):
    rowone(gc)["mark"] = 2
planted("a row marked a reader's link though a verse names the group", g5)


def g6(gc):
    gc["members"][0]["quote"] = "a Pharisee named Zebulun"
planted("a member's quote that is not in its verse", g6)


def g7(gc):
    gc["members"].append(dict(gc["members"][0], id="moses", mark=3))
planted("a member with no member_of relation", g7)


def g8(gc):
    gc["name_word"] = {"key": "g1577", "lemma": "ἐκκλησία", "lang": "grc", "addr": "w", "n": 1, "translit": "", "gloss": ""}
planted("a name word no cited verse holds", g8)


def g9(gc):
    gc["desc_leak"] = "In the Gospels he pronounces woes on them"
planted("the record's own description on the face", g9)


def plant_text(msg, fn):
    gc = copy.deepcopy(cards["pharisees"]["grcard"])
    head, body, _a = pages["pharisees"]
    gc, body = fn(gc, body)
    check(bool(text_faults("pharisees", gc, head, body)), "planted: " + msg)


plant_text("a title over 60 characters", lambda gc, b: (dict(gc, title="x" * 61), b))
plant_text("a description over 155 characters", lambda gc, b: (dict(gc, desc=gc["desc"] + "x" * 160), b))
plant_text("a quote that is not in its verse", lambda gc, b: (dict(gc, desc=gc["desc"].replace("“", "“Behold ", 1)), b))
plant_text("a reference the article does not link", lambda gc, b: (gc, b.replace('href="/p/Matt.3.7"', 'href="/p/Matt.3.8"')))


def pf(msg, fn):
    gc = copy.deepcopy(cards["pharisees"]["grcard"])
    head, body, _a = pages["pharisees"]
    head, body = fn(head, body)
    check(bool(page_faults("pharisees", gc, head, body)), "planted: " + msg)


pf("JSON-LD naming a verse the article does not link", lambda h, b: (h.replace("/p/Mark.3.6", "/p/Mark.3.99"), b))
pf("a robots tag against the index rule", lambda h, b: (h.replace('<link rel="canonical"', '<meta name="robots" content="noindex, follow">\n<link rel="canonical"'), b))

# the Jews: the guard removed builds a face
saved = S.GR_HELD
S.GR_HELD = frozenset()
try:
    check(S.group_card(d, "jews", d["ents"]["jews"], {}) is not None, "planted: the Jews' face (guard removed)")
finally:
    S.GR_HELD = saved

html = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
main = max(re.findall(r"<script>(.*?)</script>", html, re.S), key=len)
check(js_balance(main) == "OK", "the main script's brackets: " + str(js_balance(main)))
check(js_balance(main.replace("function groupFace(d){", "function groupFace(d){ (", 1)) != "OK", "planted: an unclosed bracket in groupFace")
check("grf ? grf.lead" in main, "the group face is not wired into the card")

bad = [f for f in fails if f.startswith("planted:")]
print(f"{len(cards)} groups, {n_rows} rows, {len(pages)} pages ({time.time() - t0:.0f}s), planted faults caught: "
      f"{planted_n[0] - len(bad)} of {planted_n[0]}, {len(fails) - len(bad)} failures")
for f in fails[:40]:
    print("FAIL", f)
sys.exit(1 if fails else 0)
