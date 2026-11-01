"""The image card, its sketch layer, and the armor of God and fruit of the Spirit showcases say only what the graph holds
(docs/review/card-panel-appeal/image/designer-notes.md, image/sketches/sketch-style.md, armor/spec.md, fruit/spec.md;
rulings IM-A..F, SK-A, SK-B, AR-A, AR-B, FR-A).

  - THE FACE IS THE GRAPH'S: every line of every row is a relation the card holds, with a verse it cites; "Means" stands
    only on an explicit `signifies`; a mark says "the text says it" only where an explicit `signifies` or `likened_to` is
    in the row, "a reader's link" only where an implied one is; `draws_on`, `drawn_from` and `speaks_of` make neither;
    rows are in canon order and every verse of a row is a verse a relation of the row cites
  - THE DATA FIXES: Revelation 22:16 is held out of the vine, the saying cites John 15:4, the butler's dream is the chief
    cupbearer's, and the three King-James-worded addresses answer 301 to Berean-worded ones
  - TITLES AND DESCRIPTIONS: the quote in a description is a verbatim piece of the verse it names (the BSB); every reference
    in a title or description is a link in the article; "Means" appears in a class-S title and in no class-N one
  - THE PAGE: the JSON-LD names only what the article links, explicit relations only; no King James word in the article or
    in an href; the index rule (3 verse links and 100 words, else noindex, follow) is the sitemap's too
  - THE SKETCHES: every mapped key has a symbol; no firm exclusion (the dove, the smoking firepot, God's hand or arm or
    eyes, a pledge) is mapped; the three animals never get a sketch on a card keyed to a divine person, nor does any
    divine-keyed card outside the ruled objects; every shape is stroke only by attribute; no `.sk *` page rule
  - THE SHOWCASES: the armor's six pieces are the hub's members, each drawn from the library, labeled in the verse's own
    words, linked to its card, and `image_feet` is not linked; the fruit's nine are in the text's order around one fruit;
    the humility relation and the Ephesians 5:9 citation are gone; no relation on a divine person is created or changed
  - the main script's brackets balance (this file has no JavaScript parser, so it counts them)

Every check is proved by a planted fault: a check that cannot fail is not a check.

In process, after the graph loads (~1 minute). Run: python tests/test_image_cards.py"""
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


# the bracket counter the event-card test holds the page's script to
_src = (ROOT / "tests" / "test_event_cards.py").read_text(encoding="utf-8")
exec(re.search(r"def js_balance\(js\):.*?\n\n\n", _src, re.S).group(0))

d = S.load()
t0 = time.time()
DIVINE = S.PC_DIVINE | {"holy_ghost"}


def divine_snapshot():
    return {i: json.dumps(sorted(json.dumps(r, sort_keys=True, default=str) for r in d["rels"].get(i, [])))
            for i in DIVINE if i in d["ents"]}


before = divine_snapshot()
IMAGES = sorted(i for i, e in d["ents"].items() if e.get("type") == "image" and not e.get("alias_of"))
cards = {}
for i in IMAGES:
    c = json.loads(S.answer("/api/entity", f"id={i}"))
    if c.get("found") and c.get("imgcard"):
        cards[i] = c
check(len(cards) >= 250, f"only {len(cards)} image cards carry a face")
check(before == divine_snapshot(), "building the image cards changed a relation on God, the Father, Jesus or the Holy Spirit")


# ---- 1. the face is the graph's: every line a relation, "Means" only on an explicit signifies, marks computed ------------
def face_faults(eid, ic):
    out = []
    rels = d["rels"].get(eid, [])
    last = (-1, 0, 0)
    for r in ic["rows"]:
        keyed = [ln for ln in r["lines"] if ln["type"] in S.IMG_KEY_TYPES]
        if r["mark"] == 1 and not any(ln["explicit"] for ln in keyed):
            out.append(f"{eid}: {r['head']} marked 'the text says it' with no explicit signifies or likened_to in the row")
        if r["mark"] == 2 and (not keyed or any(ln["explicit"] for ln in keyed)):
            out.append(f"{eid}: {r['head']} marked 'a reader's link' without an implied key line (or beside an explicit one)")
        if r["mark"] == 3 and keyed:
            out.append(f"{eid}: {r['head']} marked 'the word only' with a key line in it")
        for ln in r["lines"]:
            if ln["label"] == "Means" and not (ln["type"] == "signifies" and ln["explicit"]):
                out.append(f"{eid}: 'Means' on a line that is not an explicit signifies ({ln['type']})")
            if ln["type"] not in S.IMG_KEY_TYPES and ln["mark"] != 3:
                out.append(f"{eid}: a {ln['type']} line makes a mark")
            held = [x for x in rels if x["type"] == ln["type"] and x["other"] == ln["id"] and x["dir"] == ln["dir"]]
            if not held:
                out.append(f"{eid}: a line ({ln['type']} {ln['id']}) that no relation of the card holds")
            elif not any(set(ln["vids"]) <= {S._img_vid(k) for k in S._img_verses(d, x["refs"])} for x in held):
                out.append(f"{eid}: a line's verses are not the verses its relation cites ({ln['id']})")
        first = tuple(int(x) if x.isdigit() else S.ORDER.index(x) for x in
                      (lambda p: (p[0], p[1], p[2]))(r["go"].split(".")))
        first = (S.ORDER.index(r["go"].split(".")[0]), int(r["go"].split(".")[1]), int(r["go"].split(".")[2]))
        if first < last:
            out.append(f"{eid}: the rows are not in canon order at {r['head']}")
        last = first
    # the lede says "means" only of explicit signifies, and names no key a relation does not hold
    for k in ic["lede"]["keys"]:
        if not any(r["type"] == "signifies" and r["other"] == k["id"] and r.get("certainty") == "explicit" for r in rels):
            out.append(f"{eid}: the lede says it means {k['id']} with no explicit signifies")
    if ic["lede"]["cls"] == "N" and "Means" in ic["title"]:
        out.append(f"{eid}: a class N title says 'means'")
    if ic["lede"]["cls"] == "S" and "means" not in ic["title"]:
        out.append(f"{eid}: a class S title does not say what the text says it means")
    return out


n_rows = n_lines = 0
for i, c in cards.items():
    ic = c["imgcard"]
    n_rows += len(ic["rows"])
    n_lines += sum(len(r["lines"]) for r in ic["rows"])
    for f in face_faults(i, ic):
        check(False, f)
vine = cards["image_vine"]["imgcard"]
bad = copy.deepcopy(vine)
bad["rows"][0]["lines"][0]["label"] = "Means"          # Genesis 40:9's draws_on made to say "means"
check(face_faults("image_vine", bad), "planted: 'Means' on a draws_on line was not caught")
bad = copy.deepcopy(vine)
bad["rows"][0]["mark"] = 1                              # a word-only row made to say "the text says it"
check(face_faults("image_vine", bad), "planted: a word-only row marked 'the text says it' was not caught")
bad = copy.deepcopy(vine)
bad["rows"][0]["lines"].append(dict(bad["rows"][0]["lines"][0], id="the_made_up_node"))
check(face_faults("image_vine", bad), "planted: a line no relation holds was not caught")
bad = copy.deepcopy(vine)
bad["rows"][0], bad["rows"][-1] = bad["rows"][-1], bad["rows"][0]
check(face_faults("image_vine", bad), "planted: rows out of canon order were not caught")

# ---- 2. the data fixes --------------------------------------------------------------------------------------------------
vine_ids = {ln["id"] for r in vine["rows"] for ln in r["lines"]}
check("the_root_and_offspring_of_david" not in vine_ids, "Revelation 22:16 is still on the vine (IM-A)")
check(not any(v["id"] == "Rev.22.16" for r in vine["rows"] for v in r["verses"]), "Revelation 22:16 is printed on the vine")
saying = [r for r in d["rels"]["the_branch_cannot_bear_fruit_of_itself"]
          if r["type"] == "draws_on" and r["other"] == "image_vine"]
check(saying and "John 15:4" in saying[0]["refs"], "the saying's relation to the vine does not cite John 15:4 (IM-F)")
check(d["ents"]["dream_of_the_butler"]["name"] == "the chief cupbearer's dream", "the butler's dream is not renamed (IM-B)")
for old in ("dream_of_the_butler", "he_shall_shake_off_his_unripe_grape_as_the_vine", "the_branch_cannot_bear_fruit_of_itself"):
    new = S._addr(old)
    check(new != old and not re.search(r"butler|shake_off|cannot_bear|unripe_grape_as|fruit_of_itself", new),
          f"{old} still has a King James address ({new}) (IM-C)")
    check(S._card_id(new) == old, f"the address {new} does not name {old}")
    got = S.card_page(old)
    check(got is not None and got[2] == new, f"/e/{old} does not answer with {new}'s page, so the caller cannot send a 301")
check("whole armor of God" not in json.dumps(d["ents"]["the_full_armor_of_god"].get("aka") or []),
      "the armor card still has the King James aka")
check("humility" not in {r["other"] for r in d["rels"]["fruit_of_the_spirit"]}, "the humility relation at Galatians 5:23 is back")
check(not any(r["type"] == "draws_on" and r["other"] == "holy_ghost" and any("Eph 5:9" in x for x in r["refs"])
              for r in d["rels"]["fruit_of_the_spirit"]), "Ephesians 5:9 is cited on the fruit's draws_on holy_ghost (FR-A)")
check("the same phrase" not in (d["ents"]["fruit_of_the_spirit"].get("desc") or ""), "the fruit's description still says 'the same phrase'")
check("stitched from Isaiah" not in (d["ents"]["the_full_armor_of_god"].get("desc") or ""), "the armor's description still says 'stitched from Isaiah' (AR-B)")

# ---- 3. titles and descriptions ---------------------------------------------------------------------------------------
BSB = {}
for line in (ROOT / "data" / "bible" / "verses.bsb.jsonl").read_text(encoding="utf-8").splitlines():
    r = json.loads(line)
    if "b" in r:
        BSB[(r["b"], r["c"], r["v"])] = r["t"]


def desc_faults(ic):
    out = []
    m = re.match(r"^(.+?) (\d+):(\d+) \(BSB\): “(.+?)”( |$)", ic["desc"] or "")
    if ic["desc"] and not m:
        return [f"description does not open with 'Book c:v (BSB): “quote”': {ic['desc'][:70]}"]
    if m:
        book = {"Psalm": "Ps"}.get(m.group(1)) or S.TITLE_BACK.get(m.group(1)) or m.group(1)
        verse = d["verses"].get((book, int(m.group(2)), int(m.group(3)))) or ""
        if m.group(4) not in verse:
            out.append(f"the description's quote is not in {m.group(1)} {m.group(2)}:{m.group(3)}: {m.group(4)[:50]}")
    return out


n_desc = 0
for i, c in cards.items():
    ic = c["imgcard"]
    if ic["desc"]:
        n_desc += 1
    for f in desc_faults(ic):
        check(False, f"{i}: {f}")
bad = dict(vine, desc=vine["desc"].replace("true vine", "false vine"))
check(desc_faults(bad), "planted: a description quote that is not in its verse was not caught")
check(vine["desc"].startswith("John 15:1 (BSB): “I am the true vine"), f"the vine's description: {vine['desc'][:60]}")
check(vine["title"] == "Vine in the Bible: what the text says it means", f"the vine's title: {vine['title']}")
bg = cards["image_bridegroom"]["imgcard"]
check("imagery" in bg["title"] and "Means" not in bg["desc"], f"the bridegroom's title or description: {bg['title']} / {bg['desc'][:60]}")

# ---- 4. the page: links, JSON-LD, King James words, the index rule ------------------------------------------------------
SAMPLE = ["image_vine", "image_seed", "image_bridegroom", "image_belt_of_truth", "image_sun", "image_water", "image_lamp"] + IMAGES[::9]
SAMPLE = [x for x in dict.fromkeys(SAMPLE) if x in cards]
KJV_WORDS = re.compile(r"\b(butler|tares|ye|thou|thee|thy|hath|unto|canst)\b", re.I)
# the three addresses ruling IM-C renames; other cards' ids are not this file's business
OLD_ADDR = re.compile(r"dream_of_the_butler|he_shall_shake_off|the_branch_cannot_bear|cannot_bear_fruit_of_itself")
pages, n_idx, n_noidx = {}, 0, 0


def ld_faults(head, body):
    out = []
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', head, re.S)
    if not m:
        return ["no JSON-LD"]
    ld = json.loads(m.group(1).replace("<\\/", "</"))
    linked = set(re.findall(r'href="([^"]+)"', body))
    page_id = [n for n in ld["@graph"] if n.get("@type") == "WebPage"][0]["@id"]
    for node in ld["@graph"]:
        for x in ([node] + [y for v in node.values() if isinstance(v, list) for y in v if isinstance(y, dict)]):
            ident = x.get("@id", "")
            if ident.startswith(S.SITE + "/e/") and "#" not in ident and ident[len(S.SITE):] not in linked and ident != page_id:
                out.append(f"JSON-LD names {ident}, which the article does not link")
            for u in x.get("subjectOf", []) if isinstance(x.get("subjectOf"), list) else []:
                if u[len(S.SITE):] not in linked:
                    out.append(f"JSON-LD cites {u}, which the article does not link")
    return out


def page_faults(eid, head, body):
    out = []
    hrefs = set(re.findall(r'href="([^"]+)"', body))
    text = re.sub(r"<[^>]+>", " ", body)
    for h in hrefs:
        if OLD_ADDR.search(h):
            out.append(f"a King James address in an href: {h}")
    # the verses are the Berean's own; the card's prose is what is checked
    prose = re.sub(r"<p><a href=\"/p/[^>]*>.*?</p>", " ", body, flags=re.S)
    prose = re.sub(r"<[^>]+>", " ", prose)
    for w in KJV_WORDS.findall(prose):
        out.append(f"a King James word in the card's prose: {w}")
    title = re.search(r"<title>(.*?) · Bible Ontology</title>", head).group(1)
    desc = re.search(r'name="description" content="(.*?)"', head).group(1)
    from html import unescape
    for ref in re.findall(r"\b((?:[1-3] )?[A-Z][a-z]+ \d+:\d+)", unescape(title + " " + desc)):
        b, cv = ref.rsplit(" ", 1)
        code = S.TITLE_BACK.get(b) or ("Ps" if b == "Psalm" else b)
        c_, v_ = cv.split(":")
        if f'href="/p/{code}.{c_}.{v_}"' not in body:
            out.append(f"{ref} is in the title or description and is not a link in the article")
    out += ld_faults(head, body)
    return out


for i in SAMPLE:
    got = S.card_page(i)
    check(got is not None, f"{i}: no page")
    if not got:
        continue
    head, body, addr = got
    pages[i] = (head, body, addr)
    links, words, ok = S.image_indexable(body)
    noidx = 'content="noindex, follow"' in head
    check(noidx == (not ok), f"{i}: the robots tag ({'noindex' if noidx else 'index'}) is not the index rule's ({links} links, {words} words)")
    n_idx += not noidx
    n_noidx += noidx
    for f in page_faults(i, head, body):
        check(False, f"{i}: {f}")
    check("sk-page-sprite" not in body or (cards.get(i, {}).get("sketch") is not None), f"{i}: a sketch sprite on a card with no sketch")
h, b, _a = pages["image_vine"]
check(not page_faults("image_vine", h, b), "the vine's page has faults: " + "; ".join(page_faults("image_vine", h, b)[:2]))
# planted faults on the page
check(page_faults("x", h, b.replace("</article>", '<p>the <a href="/e/dream_of_the_butler">dream</a> of the tares</p></article>', 1)),
      "planted: a King James word in the prose and an address was not caught")
check(ld_faults(h.replace('"@graph": [', '"@graph": [{"@id": "https://bibleontology.org/e/nowhere_at_all", "subjectOf": []}, ', 1), b),
      "planted: a JSON-LD @id the article does not link was not caught")
check(ld_faults(h, b.replace('href="/p/Hos.10.1"', 'href="/p/Hos.10.2"')), "planted: a JSON-LD verse the article does not link was not caught")
ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', h, re.S).group(1).replace("<\\/", "</"))
sig = [n for n in ld["@graph"] if n.get("@type") == "DefinedTerm"][0].get("bor:signifies") or []
check({x["@id"].rsplit("/", 1)[1] for x in sig} == {"children_of_israel", "jesus"}, f"the vine's bor:signifies: {sig}")
# the index rule: a thin page is not asked for
check(not S.image_indexable("<p>" + "word " * 200 + '<a href="/p/Gen.1.1">x</a><a href="/p/Gen.1.2">y</a></p>')[2],
      "planted: a page with two verse links was called indexable")
check(not S.image_indexable("<p>short " + "".join(f'<a href="/p/Gen.1.{k}">x</a>' for k in range(1, 6)) + "</p>")[2],
      "planted: a page with few words was called indexable")
check(S.image_indexable("<p>" + "word " * 120 + "".join(f'<a href="/p/Gen.1.{k}">x</a>' for k in range(1, 4)) + "</p>")[2],
      "the index rule refuses a page with 3 verse links and 100 words")
SM = (ROOT / "tools" / "sitemap.py").read_text(encoding="utf-8")
check("image_indexable" in SM, "tools/sitemap.py does not apply the image index rule")

# ---- 5. a verse the card prints keeps its marks (Mark 16:9-20, John 7:53-8:11) ----------------------------------------------
tail = [v for c in cards.values() for r in c["imgcard"]["rows"] for v in r["verses"]
        if re.match(r"Mark\.16\.(9|1\d|20)$|John\.7\.53$|John\.8\.([1-9]|1[01])$", v["id"])]
check(all(v.get("vmarks") and v["vmarks"].get("ms") for v in tail), "a verse of the longer ending prints on an image card without its dagger")
check("†" in S._marked_hl("Mark", 16, 18, "they will pick up snakes with their hands", ("snakes",)),
      "the served page's verse printer drops the dagger at Mark 16:18")
check("<mark" in S._marked_hl("John", 15, 1, "I am the true vine", ("vine",)), "the served page's verse printer drops the highlight")
check("†" not in S._marked_hl("John", 15, 1, "I am the true vine", ("vine",)), "planted: a dagger on John 15:1")  # a dagger where there is none

# ---- 6. the sketch library ----------------------------------------------------------------------------------------------
SVG = (ROOT / "app2" / "static" / "sketches.svg").read_text(encoding="utf-8")
MAP = json.loads((ROOT / "ontology" / "image-sketches.json").read_text(encoding="utf-8"))
SYMS = set(re.findall(r'<symbol id="sk-([a-z]+)"', SVG))
NEVER = {"image_dove", "image_smoking_furnace", "image_hand_of_god", "image_mighty_hand", "image_eyes", "image_of_god",
         "image_arm", "image_earnest"}
FIGURE_KEYS = {"dove", "hand", "arm", "eyes", "eye", "figure", "person", "man", "woman", "face", "halo", "lamb", "lion", "serpent"}


def map_faults(m, syms):
    out = []
    for cid, key in m.items():
        if key not in syms:
            out.append(f"{cid} maps to {key}, which has no symbol")
        if d["ents"].get(cid, {}).get("type") != "image":
            out.append(f"{cid} is not an image card")
        if cid in NEVER:
            out.append(f"{cid} is a firm exclusion and is mapped")
        if key in FIGURE_KEYS:
            out.append(f"{cid} maps to a key that draws a figure or an animal ({key})")
    return out


check(not map_faults(MAP, SYMS), "the sketch map: " + "; ".join(map_faults(MAP, SYMS)[:3]))
check(map_faults({**MAP, "image_dove": "vine"}, SYMS), "planted: the dove mapped was not caught")
check(map_faults({**MAP, "image_vine": "no_such_key"}, SYMS), "planted: a key with no symbol was not caught")
check(len(SYMS) >= 30, f"only {len(SYMS)} sketch symbols")


def svg_faults(svg):
    out = []
    for m in re.finditer(r'<symbol id="(sk-[a-z]+)"(.*?)</symbol>', svg, re.S):
        sid, inner = m.group(1), m.group(2)
        if 'fill="none"' not in inner.split(">")[0]:
            out.append(f"{sid}: the symbol has no fill=none")
        g = re.search(r"<g ([^>]*)>", inner)
        if not g or not all(a in g.group(1) for a in ('fill="none"', 'stroke="currentColor"', 'stroke-width="1.6"', 'stroke-linecap="round"', 'filter="url(#sk-rough)"')):
            out.append(f"{sid}: the group does not carry the stroke and the filter")
        for s in re.finditer(r"<(path|circle|ellipse|rect|line|polyline|polygon)\b([^>]*)>", inner):
            if 'fill="none"' not in s.group(2) or "vector-effect" not in s.group(2):
                out.append(f"{sid}: a {s.group(1)} without fill=none and vector-effect")
    if not re.search(r'<filter id="sk-rough"', svg):
        out.append("no shared filter")
    return out


check(not svg_faults(SVG), "the sprite: " + "; ".join(svg_faults(SVG)[:3]))
check(svg_faults(SVG.replace('fill="none" vector-effect', "vector-effect", 1)), "planted: a shape with no fill=none was not caught")
check(svg_faults(SVG.replace('stroke-width="1.6"', 'stroke-width="2"', 1)), "planted: a group with another pen was not caught")
INDEX = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
check(not re.search(r"\.sk\s+\*|\.sk\s*>\s*\*|\.sk\s+path", INDEX), "a page rule reaches into a sketch (.sk *)")
check(re.search(r"\.sk\s+\*", INDEX.replace("</style>", ".sk *{fill:currentColor}</style>", 1)), "planted: the .sk * rule was not caught")

# SK-A: the animals never, the ruled objects yes, anything else keyed to a divine person no -- computed on each request
check(S.image_sketch(d, "image_vine") == "vine" and S.image_sketch(d, "image_seed") == "seed", "the vine and the seed lost their sketch (SK-A)")
saved = S._IMG_SKETCHES
try:
    S._IMG_SKETCHES = {**MAP, "image_lamb": "lamb", "image_lion": "lion", "image_serpent": "serpent", "image_dove": "bird"}
    check(all(S.image_sketch(d, x) is None for x in ("image_lamb", "image_lion", "image_serpent")),
          "a sketch was attached to the lamb, the lion or the serpent (SK-A)")
    check(S.image_sketch(d, "image_dove") is None, "a sketch was attached to the dove")
    # a relation added later to an unruled card cannot slip a drawing onto it
    d["rels"].setdefault("image_sun", []).append({"dir": "out", "type": "signifies", "other": "jesus", "refs": ["Mal 4:2"], "certainty": "implied"})
    check(S.image_sketch(d, "image_sun") is None, "a card that gained a divine key kept its sketch")
    d["rels"]["image_sun"].pop()
    check(S.image_sketch(d, "image_sun") == "sun", "the sun lost its sketch")
    S.SK_DIVINE_OK, ok_saved = frozenset(), S.SK_DIVINE_OK
    check(S.image_sketch(d, "image_vine") is None, "planted: the vine without SK-A kept its sketch")
    S.SK_DIVINE_OK = ok_saved
finally:
    S._IMG_SKETCHES = saved
check(sum(1 for c in cards.values() if c.get("sketch")) >= 60, "fewer than 60 image cards carry a sketch")
check(all(c.get("sketch") in SYMS for c in cards.values() if c.get("sketch")), "a card's sketch has no symbol")
check("sketch" in cards["image_vine"] and cards["image_vine"]["sketch"] == "vine", "the vine card has no sketch key")
# the first-screen rule, as far as a test with no browser can hold it: the drawing floats beside the title, 72 px on a phone,
# and a card with none draws nothing
check(re.search(r"\.sk-float\{float:right", INDEX) and re.search(r"\.sk\{width:72px; height:72px", INDEX), "the sketch is not the floated 72 px drawing")
check("imSketch(d.sketch)" in INDEX and re.search(r"const imSketch = \(key, cls\) => key\s*\?\s*`<svg", INDEX) and "`<svg" in INDEX.split("const imSketch")[1].split("\n")[1] and ": ''" in INDEX.split("const imSketch")[1].split(";")[0],
      "imageFace does not draw nothing when the card has no sketch")

# ---- 7. the showcases ---------------------------------------------------------------------------------------------------
arm = json.loads(S.answer("/api/entity", "id=the_full_armor_of_god")).get("showcase")
fru = json.loads(S.answer("/api/entity", "id=fruit_of_the_spirit")).get("showcase")
check(arm and fru, "a showcase card has no showcase")


def show_faults(arm, fru):
    out = []
    hub = S.hub_for(d, "the_full_armor_of_god")
    if [p["card"] for p in sorted(arm["pieces"], key=lambda p: p["n"])] != [m["card"] for m in hub["members"]]:
        out.append("the armor's pieces are not the hub's members in the text's order")
    if len(arm["pieces"]) != 6 or not all(p["sketch"] for p in arm["pieces"]):
        out.append("the armor does not draw six pieces")
    if "image_feet" in arm["art"] or "image_feet" in json.dumps(arm["rows"]):
        out.append("the armor links image_feet (Job 29:15)")
    saying = d["rels"]["the_full_armor_of_god"]
    for p in arm["pieces"]:
        if not any(r["type"] == "draws_on" and r["other"] == p["card"] and r["dir"] == "out" for r in saying):
            out.append(f"{p['card']} is a piece with no draws_on from the saying")
        text = " ".join(" ".join(s["t"] for s in ln) for ln in p["text"]["lines"])
        if re.sub(r"\s+", " ", text) not in d["verses"][S._site_span(d, p["ref"])[:3]]:
            out.append(f"the label '{text}' is not in {p['ref']}")
        if f'href="/e/{p["addr"]}"' not in arm["art"]:
            out.append(f"{p['card']} is not a link in the picture")
    sw = [p for p in arm["pieces"] if p["card"] == "image_sword_of_the_spirit"]
    if not sw or "word" not in " ".join(s["t"] for ln in sw[0]["text"]["lines"] for s in ln if s["b"]):
        out.append("the sword's 'which is the word of God' is not in bold")
    if sum(1 for r in arm["rows"] if r["pair"]["which"]) != 1:
        out.append("more than the sword is said to be something")
    for sc, nm in ((arm, "armor"), (fru, "fruit")):
        if re.search(r"image_(dove|hand|halo)|holy_ghost|data-ent=\"(god|jesus|the_holy_spirit)\"", sc["art"]):
            out.append(f"a divine person on the {nm}'s picture")
    if len(fru["ring"]) != 9 or [q["label"] for q in fru["ring"]] != [m["label"] for m in S.hub_for(d, "fruit_of_the_spirit")["members"]]:
        out.append("the fruit's nine are not the hub's members in the text's order")
    elif not (fru["ring"][0]["anchor"] == "middle" and fru["ring"][0]["y"] < fru["center"]["y"] - 80):
        out.append("the ring does not start at the top")
    if not all(abs((q["x"] - 180) ** 2 + (q["y"] - 152) ** 2 - 100 ** 2) < 1500 for q in fru["ring"]):
        out.append("the ring is not on its circle")
    if fru["center"]["sketch"] != "fruit" or 'href="#sk-fruit"' not in fru["art"]:
        out.append("the fruit is not drawn at the center")
    ct = fru["contrast"]
    if not ct or ct["mark"] != 2 or len(ct["left"]["items"]) != 15:
        out.append("the contrast with the acts of the flesh is not a reader's link between two lists")
    if not all(t["word"] for t in fru["tiles"]):
        out.append("a quality tile has no Greek word")
    if {t["label"]: t["cname"] for t in fru["tiles"]}.get("faithfulness") != "faith":
        out.append("faithfulness does not open the card for faith")
    if arm["art"].count("<use ") < 6 or fru["art"].count("<use ") < 1:
        out.append("a showcase picture draws too few sketches")
    return out


if arm and fru:
    check(not show_faults(arm, fru), "the showcases: " + "; ".join(show_faults(arm, fru)[:3]))
    bad = copy.deepcopy(arm)
    bad["pieces"][2]["card"] = "image_feet"
    bad["pieces"][2]["addr"] = "image_feet"
    check(show_faults(bad, fru), "planted: image_feet in the armor was not caught")
    bad = copy.deepcopy(arm)
    bad["art"] = bad["art"].replace("</svg>", '<a href="/e/holy_ghost" data-ent="holy_ghost"></a></svg>')
    check(show_faults(bad, fru), "planted: a divine person on the armor was not caught")
    bad = copy.deepcopy(arm)
    bad["pieces"][0]["text"]["lines"][0][0]["t"] = "the girdle"
    check(show_faults(bad, fru), "planted: a label that is not in its verse was not caught")
    bad = copy.deepcopy(fru)
    bad["ring"].reverse()
    check(show_faults(arm, bad), "planted: the fruit's nine out of the text's order were not caught")
    bad = copy.deepcopy(fru)
    bad["contrast"]["mark"] = 1
    check(show_faults(arm, bad), "planted: a contrast marked 'the text says it' without an explicit relation was not caught")
    bad = copy.deepcopy(fru)
    bad["tiles"][8]["word"] = None
    check(show_faults(arm, bad), "planted: a quality with no Greek word was not caught")
    # the pages
    for eid, sc in (("the_full_armor_of_god", arm), ("fruit_of_the_spirit", fru)):
        got = S.card_page(eid)
        check(got is not None, f"{eid}: no page")
        if got:
            head, body, _a = got
            check("noindex" not in head, f"{eid}: a showcase page is noindexed")
            for m in sc.get("moves", []):
                check(f'href="/p/{m["go"]}"' in body, f"{eid}: the verb '{m['words']}' is not linked")
            check("image_feet" not in body and "holy_ghost" not in body, f"{eid}: a page that links image_feet or the Holy Spirit")
    check(arm["desc"].startswith("“Put on the full armor of God”") and arm["desc"].endswith("and four more."), f"the armor's description: {arm['desc']}")
    check(fru["desc"].startswith("“But the fruit of the Spirit is love") and fru["desc"].endswith("self-control” (Galatians 5:22–23, BSB)"),
          f"the fruit's description: {fru['desc'][:90]}")

# ---- 8. the page's script: brackets that balance --------------------------------------------------------------------------
scripts = re.findall(r"<script>(.*?)</script>", INDEX, re.S)
main = max(scripts, key=len)
check(js_balance(main) == "OK", f"the main script does not balance: {js_balance(main)}")
for what, old, new in [("an unclosed template literal", "const imMk = n => `<span class=\"im-mk m${n}\" aria-hidden=\"true\"></span>`;",
                        "const imMk = n => `<span class=\"im-mk m${n}\" aria-hidden=\"true\"></span>;"),
                       ("an unclosed bracket", "function imageWire(d){\n  const pane = $('#paneinner');", "function imageWire(d){\n  const pane = ($('#paneinner';")]:
    alt = main.replace(old, new, 1)
    check(alt != main and js_balance(alt) != "OK", f"planted: the script check did not catch {what}")
for needle in ("function imageFace(d){", "function imageWire(d){", "function showcaseFace(d){", "function sketchesReady(){",
               "imageFace(d).html", "d.showcase", "vtext(v.text, v.vmarks, fmt)", "pcLacks(v.id)", "/sketches.svg"):
    check(needle in INDEX, f"missing in the page code: {needle}")
for needle in ("IMG_KEY_TYPES", "def image_sketch(", "def image_card(", "def _image_card_page(", "def showcase_card(", "def image_indexable("):
    check(needle in (ROOT / "app2" / "server.py").read_text(encoding="utf-8"), f"missing in the server: {needle}")

print(f"{len(cards)} image cards, {n_rows} rows, {n_lines} lines, {n_desc} descriptions, {len(SAMPLE)} pages "
      f"({n_idx} indexed, {n_noidx} noindex), {len(MAP)} sketched cards of {len(SYMS)} symbols ({time.time() - t0:.0f}s), "
      f"planted faults caught: {planted_n[0] - sum(f.startswith('planted:') for f in fails)} of {planted_n[0]}, {len(fails)} failures")
for f in fails[:30]:
    print("FAIL", f)
sys.exit(1 if fails else 0)
