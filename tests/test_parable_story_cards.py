"""The story cards of the 18 parables hold only what the text says (2026-10-29; the design in
docs/review/card-panel-appeal/parable/the-18/spec.md, the data in ontology/parable-cards.json).

  - each of the 18 parables that have no part-by-part mapping has a story card, a tab per telling, and every item
    (story, setting, meaning, figure) is the Berean's own words, cut by a verse and a phrase of it
  - "What Jesus says it means" is there ONLY as Jesus's own words: every meaning verse lies inside the verses the data
    records as his own speech, outside the story, outside the narrator's setting, and carries no narrator's tag ("Jesus
    said", "he replied"); the block holds the Berean's words and nothing the site wrote; a telling with none says
    "The text gives the story without an explanation." and a held telling shows the story alone
  - a setting is the narrator's words, never inside Jesus's speech, never drawn as a meaning
  - the figures are phrases of their verse; none says what a figure is
  - the served page (what Google sees) carries the same story, setting and meaning, links each verse, and its
    description says what the card answers and quotes only a verse the article links
  - the old "No one in these passages is resolved to a node yet." line is gone from these cards
  - Explore's front door leads with the 22 cards in canon order, each a link, and the machine-stamped parable kinds come
    after them, folded, and not in the Events list; /explore/parables lists the 22 for the server copy

Every check is proved by a planted fault: a check that cannot fail is not a check.
In process, after the graph loads (~1 minute). Run: python tests/test_parable_story_cards.py"""
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
PARS = json.loads((ROOT / "ontology" / "parables.json").read_text(encoding="utf-8"))["events"]
CARDS = json.loads((ROOT / "ontology" / "parable-cards.json").read_text(encoding="utf-8"))["cards"]
MAPPED = {"event_parable_of_the_sower", "event_parable_of_the_weeds", "event_parable_of_the_hidden_treasure",
          "event_parable_of_the_pearl_of_great_price"}
EIGHTEEN = [p["id"] for p in PARS if p["id"] not in MAPPED]
RE_REF = re.compile(r"^(\w+) (\d+):(\d+)(?:-(\d+))?$")
# a narrator's tag: Jesus's own words never carry one
NARR = re.compile(r"\b(Jesus|He|he|they|the expert in the law) (said|replied|answered|told|asked|began|spoke)\b")
SITE_VOICE = "This means that God seeks the lost, and the Church is the flock."


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("’", "'"))


def verses_of(ref):
    m = RE_REF.match(ref)
    b, c, v1 = m.group(1), int(m.group(2)), int(m.group(3))
    return [(b, c, v) for v in range(v1, int(m.group(4) or v1) + 1)]


def vset(refs):
    return {k for r in refs or [] for k in verses_of(r)}


def ivs(it):
    """(verse, start, end) of each verse of an item, cut by `from` and `to`; start -1 when a phrase is missing."""
    ks = verses_of(it["ref"])
    out = []
    for n, k in enumerate(ks):
        t = d["verses"].get(k)
        if t is None:
            return [(k, -1, -1)]
        s, e = 0, len(t)
        if n == 0 and it.get("from"):
            s = t.find(it["from"])
        if n == len(ks) - 1 and it.get("to"):
            i = t.find(it["to"], max(s, 0))
            e = i + len(it["to"]) if i >= 0 else -1
        out.append((k, s, e))
    return out


def telling_verses(ev):
    out = set()
    for tl in ev["tellings"]:
        fb, fc, fv = S.bsb_ref(d, tl["first"]).split(".")
        lb, lc, lv = S.bsb_ref(d, tl["last"]).split(".")
        b = S.MACULA_BACK.get(fb, fb)
        for (kb, kc, kv) in d["verses"]:
            if kb == b and (int(fc), int(fv)) <= (kc, kv) <= (int(lc), int(lv)):
                out.add((kb, kc, kv))
    return out


def plain(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h))


def section(h, cls):
    m = re.search(r'<section class="' + cls + r'[ "].*?</section>', h, re.S)
    return m.group(0) if m else ""


def says_words(h):
    """The words inside the 'what Jesus says' block, without its head, numbers and attribution."""
    s = section(h, "pz-says")
    s = re.sub(r"<h2.*?</h2>|<p class=\"pz-att\">.*?</p>|<a class=\"pz-vn[^>]*>.*?</a>", "", s, flags=re.S)
    return norm(plain(s))


def card_story(eid, sc):
    return S._pc_story(d, sc, S.event_of(d, eid))


def story_faults(eid, sc, st=None):
    """What a story card may not hold, held against the data and the Berean."""
    bad = []
    ev = S.event_of(d, eid)
    st = st or card_story(eid, sc)
    inside = telling_verses(ev)
    if len(st["tabs"]) != len(sc["tabs"]):
        bad.append(f"{eid}: a telling without a tab")
    for tb, tab in zip(sc["tabs"], st["tabs"]):
        who = f"{eid} {tb['b']}"
        jes = vset(tb.get("jesus"))
        story_iv = [x for it in tb.get("story") or [] for x in ivs(it)]
        set_iv = [x for it in tb.get("setting") or [] for x in ivs(it)]
        if not tb.get("story"):
            bad.append(f"{who}: no story")
        for key in ("story", "setting", "meaning"):
            for it in tb.get(key) or []:
                if S._pc_item(d, it) is None or any(s < 0 or e < 0 for _, s, e in ivs(it)):
                    bad.append(f"{who}: {key} {it['ref']} is not the Berean's words")
        for it in tb.get("story") or []:
            if any(k not in inside for k, _, _ in ivs(it)):
                bad.append(f"{who}: story {it['ref']} lies outside the telling")
        for it in tb.get("setting") or []:
            for k, s, e in ivs(it):
                if k in jes:
                    bad.append(f"{who}: setting {it['ref']} is inside Jesus's own speech, not the narrator's")
        for it in tb.get("meaning") or []:
            for k, s, e in ivs(it):
                t = (d["verses"].get(k) or "")[max(s, 0):max(e, 0)]
                if k not in jes:
                    bad.append(f"{who}: meaning {it['ref']} is not Jesus speaking")
                if k not in inside:
                    bad.append(f"{who}: meaning {it['ref']} lies outside the telling")
                if NARR.search(t):
                    bad.append(f"{who}: meaning {it['ref']} carries a narrator's tag: {NARR.search(t).group(0)}")
                for k2, s2, e2 in story_iv:
                    if k2 == k and s < e2 and s2 < e:
                        bad.append(f"{who}: meaning {it['ref']} is inside the story")
                for k2, s2, e2 in set_iv:
                    if k2 == k and s < e2 and s2 < e:
                        bad.append(f"{who}: a setting shown as a meaning: {it['ref']}")
        for f in tb.get("figures") or []:
            m = RE_REF.match(f["ref"])
            vt = d["verses"].get((m.group(1), int(m.group(2)), int(m.group(3)))) or ""
            if not re.search(r"(?<![\w])" + re.escape(f["name"]) + r"(?![\w])", vt, re.I):
                bad.append(f"{who}: figure '{f['name']}' is not a phrase of {f['ref']}")
        # the card as drawn
        h = tab["html"]
        if tb.get("held") and (tab["meaning"] or "pz-says" in section(h, "pz-says")):
            bad.append(f"{who}: a held telling shows a meaning")
        if tab["meaning"]:
            want = norm("".join((it["pre"] if n else "") + "".join(v["t"] for v in it["verses"])
                                for n, it in enumerate(S._pc_item(d, x) for x in tb["meaning"])))
            if says_words(h) != want:
                bad.append(f"{who}: the meaning block holds words that are not Jesus's (the site's voice)")
        elif not tb.get("held"):
            if S.PC_NO_MEANING not in h:
                bad.append(f"{who}: no meaning and no plain line saying so")
            if "pz-says\"" in h or "pz-says pz-long" in h:
                bad.append(f"{who}: a meaning block with no meaning")
        if tb.get("held") and S.PC_NO_MEANING in h:
            bad.append(f"{who}: a held telling claims the text gives no explanation")
        stxt = norm(plain(section(h, "pz-tale")))
        for it in tb.get("story") or []:
            for k, s, e in ivs(it):
                t = (d["verses"].get(k) or "")[max(s, 0):max(e, 0)].strip("“” ")
                if norm(t[:60]) not in stxt:
                    bad.append(f"{who}: story verse {k} is missing from the card")
        for it in tb.get("setting") or []:
            for k, s, e in ivs(it):
                t = (d["verses"].get(k) or "")[max(s, 0):max(e, 0)]
                if norm(t[:40]) not in norm(plain(h)):
                    bad.append(f"{who}: setting {k} is missing from the card")
                if norm(t[:40]) in says_words(h) and len(norm(t[:40])) > 10:
                    bad.append(f"{who}: a setting inside the meaning block")
    return bad


def page_faults(eid, sc, head, body):
    """The served page against the data: the same story, setting and meaning, every verse linked."""
    bad = []
    art = body.split("<article", 1)[1]
    pt = norm(plain(art))
    hrefs = set(re.findall(r'href="([^"]+)"', art))
    for tb in sc["tabs"]:
        for key in ("story", "setting", "meaning"):
            for it in tb.get(key) or []:
                for k, s, e in ivs(it):
                    t = (d["verses"].get(k) or "")[max(s, 0):max(e, 0)].strip("“” ")
                    if norm(t[:50]) not in pt:
                        bad.append(f"{eid}: the served page lacks {key} {k}")
                    if f"/p/{k[0]}.{k[1]}.{k[2]}" not in hrefs:
                        bad.append(f"{eid}: the served page does not link {k}")
        if not tb.get("meaning") and not tb.get("held") and S.PC_NO_MEANING not in art:
            bad.append(f"{eid}: the served page lacks the no-explanation line")
    desc = html.unescape(re.search(r'<meta name="description" content="(.*?)">', head).group(1))
    for v in re.findall(r"\(((?:[1-3] )?[A-Z][a-z]+ \d+:\d+)", desc):
        b, cv = v.rsplit(" ", 1)
        c, vn = cv.split(":")
        if f"/p/{b.replace(' ', '')}.{c}.{vn}" not in hrefs:
            bad.append(f"{eid}: a description verse not linked: {v}")
    if any(tb.get("meaning") for tb in sc["tabs"]) != ("what Jesus says it means" in desc):
        bad.append(f"{eid}: the description does not say what the card answers ({desc[:80]})")
    if re.search(r"No one in these passages", art):
        bad.append(f"{eid}: the empty 'No one ... resolved' line")
    return bad


def eventblock_faults(src):
    """The empty line must not show on a parable card, nor the site's paraphrase of the story above the story."""
    bad = []
    if "(C.length || pzcard ? ''" not in src:
        bad.append("the 'No one in these passages' line is not held back on a parable card")
    if "ev.notes && !pzcard" not in src:
        bad.append("the event's paraphrase of the story still stands above the story")
    if "${pzcard ? '' : sec('ev-who'" not in src:
        bad.append("'Who is in it' still shows on a parable card")
    return bad


def explore_faults(src, kinds, rows_ids):
    bad = []
    if "const evKinds = (events.kinds || []).filter(k => k.id !== 'ev-jesus-parables' && k.id !== 'ev-parables');" not in src:
        bad.append("the stamped parable kinds are still listed in Events")
    if "evKinds.map(k => sec(k.id," not in src or "(events.kinds||[]).map(k => sec(k.id," in src:
        bad.append("Events lists the stamped kinds")
    body = src.split("const pzxSec = () => {", 1)[1].split("const recurs = ", 1)[0]
    i, j = body.find("rows.map(r => pzxRow(r, g))"), body.find("sec('ev-parables'")
    if i < 0 or j < 0 or i > j:
        bad.append("the 22 cards are not drawn before the stamped kinds")
    if "labeled parable-like" not in body or "not the site’s claim" not in body:
        bad.append("the stamped kinds are not said to be a reading pass's labels")
    first = kinds[0] if kinds else {}
    if first.get("id") != "ev-jesus-parables":
        bad.append("the entry does not lead with the parables of Jesus")
    got = [r["id"] for r in first.get("rows") or []]
    for e in rows_ids:
        if e not in got:
            bad.append(f"a parable card missing from the entry: {e}")
    return bad


# ---- the data: 18 parables, each with a card
check(len(EIGHTEEN) == 18, f"{len(EIGHTEEN)} parables without a mapping")
check(set(CARDS) == set(EIGHTEEN), f"cards for {sorted(set(CARDS) ^ set(EIGHTEEN))}")
counts = {}
for eid in EIGHTEEN:
    sc = CARDS[eid]
    f = story_faults(eid, sc)
    check(not f, "; ".join(f))
    pc = S.parable_card(d, eid)
    check(pc and pc.get("story") and pc["story"]["tabs"], f"{eid}: no story on the card")
    if not pc:
        continue
    check(pc["frame"] is None, f"{eid}: the older frame repeats the story")
    st = pc["story"]
    counts[eid] = (len(st["tabs"]), sum(bool(t["meaning"]) for t in st["tabs"]), sum(bool(t["setting"]) for t in st["tabs"]),
                   sum(len(t["story"]) for t in st["tabs"]))
    # the served page
    head, body, _ = S.card_page(S._addr(eid))
    pf = page_faults(eid, sc, head, body)
    check(not pf, "; ".join(pf))
    check(len(body) < 40000, f"{eid}: the article is {len(body)} bytes")
    check(re.search(r"<title>(.*?) · Bible Ontology", head).group(1) == pc["page_title"] and len(pc["page_title"]) <= 60,
          f"{eid}: title rule {pc['page_title']}")
    check("What Jesus Says It Means" not in pc["page_title"], f"{eid}: the title promises an explanation the card maps")
    # the app card: the older empty line is held back
    check(not eventblock_faults(SRC), "; ".join(eventblock_faults(SRC)))
    # nothing says what a figure is
    flat = json.dumps(st, ensure_ascii=False)
    check(not re.search(r"\brepresents?\b|\bsymbolizes?\b|\bstands for\b|\bis God\b|\bis Israel\b|\bthe Church\b", plain(flat)),
          f"{eid}: an interpretation in the card")

# ---- Explore's front door
kinds = S.api_events(d, {})["kinds"]
rows = kinds[0].get("rows") or []
check(len(rows) == 22 and {r["id"] for r in rows} == {p["id"] for p in PARS}, "the entry does not hold the 22")
order = [(S.PC_GOSPELS.index(r["tellings"][0]["b"]), r["tellings"][0]["c"], r["tellings"][0]["v"]) for r in rows]
check(order == sorted(order), "the 22 are not in the order of the canon")
check(all(S._addr(r["id"]) == r["addr"] for r in rows), "a row's address is not its card's")
check(not explore_faults(SRC, kinds, [p["id"] for p in PARS]), "; ".join(explore_faults(SRC, kinds, [p["id"] for p in PARS])))
check(not any(k["id"] == "ev-jesus-parables" for k in kinds[1:]), "the entry is listed twice")
ph = S.explore_page("parables")
check(ph is not None and all(f'href="/e/{r["addr"]}"' in ph[1] for r in rows) and ph[1].count("<li>") == 22,
      "/explore/parables does not list the 22 cards")
check("explore/parables" in (ROOT / "deploy" / "www" / "sitemap-pages.xml").read_text(encoding="utf-8"),
      "/explore/parables is not in the sitemap")

# ---- the planted faults
UF, LS, SAM, JS, MU = ("event_parable_of_the_unforgiving_servant", "event_parable_of_the_lost_sheep", "event_good_samaritan",
                       "event_parable_of_the_good_shepherd", "event_parable_of_the_mustard_seed")


def with_(eid, **chg):
    sc = copy.deepcopy(CARDS[eid])
    sc["tabs"][-1].update(chg)
    return sc


caught("a meaning verse that is a story figure speaking, not Jesus (Matt 18:33)",
       lambda: story_faults(UF, with_(UF, meaning=[{"ref": "Matt 18:33"}])))
caught("a meaning verse that is the narrator (Luke 15:1)",
       lambda: story_faults(LS, with_(LS, meaning=[{"ref": "Luke 15:1"}])))
caught("a meaning that begins in the narrator's tag (John 10:7 without its 'from')",
       lambda: story_faults(JS, with_(JS, meaning=[{"ref": "John 10:7-18"}])))
caught("a setting shown as a meaning", lambda: story_faults(LS, with_(LS, meaning=CARDS[LS]["tabs"][-1]["setting"])))
caught("a setting inside Jesus's own speech", lambda: story_faults(UF, with_(UF, setting=[{"ref": "Matt 18:22"}])))
sc_h = with_(UF, held=True)
built = card_story(UF, CARDS[UF])           # the card as built with the meaning, against a data row marked held
caught("a held row showing a meaning", lambda: story_faults(UF, sc_h, built))
tabs_ = copy.deepcopy(built)
tabs_["tabs"][0]["html"] = tabs_["tabs"][0]["html"].replace(
    '<p class="pz-att">', f'<p class="pz-q">“{SITE_VOICE}”</p><p class="pz-att">', 1)
caught("a meaning written in the site's voice",
       lambda: [x for x in story_faults(UF, CARDS[UF], tabs_) if "site's voice" in x])
tabs2 = copy.deepcopy(card_story(MU, CARDS[MU]))
tabs2["tabs"][0]["html"] = tabs2["tabs"][0]["html"].replace(S.PC_NO_MEANING, "")
caught("a telling with no meaning and no line saying so", lambda: story_faults(MU, CARDS[MU], tabs2))
caught("a figure that is not a phrase of its verse",
       lambda: story_faults(UF, with_(UF, figures=[{"name": "the Church", "ref": "Matt 18:23"}])))
caught("a story verse outside the telling", lambda: story_faults(UF, with_(UF, story=[{"ref": "Matt 5:3"}])))
head, body, _ = S.card_page(S._addr(SAM))
art_story = CARDS[SAM]["tabs"][0]["story"][0]
caught("the served page missing the story",
       lambda: page_faults(SAM, CARDS[SAM], head, body.replace("A man was going down", "").replace("man was going down", "")))
caught("the served page missing the meaning",
       lambda: page_faults(SAM, CARDS[SAM], head, body.replace("Go and do likewise", "")))
caught("the served page without its verse links",
       lambda: page_faults(SAM, CARDS[SAM], head, body.replace('href="/p/Luke.10.30"', 'href="/x"')))
caught("the empty 'No one ... resolved' line back on one of the 18",
       lambda: page_faults(SAM, CARDS[SAM], head, body.replace("</article>", "<p>No one in these passages is resolved to a node yet.</p></article>")))
caught("the empty line back in the app's event block", lambda: eventblock_faults(SRC.replace("(C.length || pzcard ? ''", "(C.length ? ''")))
caught("the paraphrase of the story back above the story", lambda: eventblock_faults(SRC.replace("ev.notes && !pzcard", "ev.notes")))
caught("the description not saying what the card answers",
       lambda: page_faults(LS, CARDS[LS], re.sub(r'(<meta name="description" content=")[^"]*', r"\1Luke 15:3: a story.", S.card_page(S._addr(LS))[0]),
                           S.card_page(S._addr(LS))[1]))
caught("the entry listing the stamped kinds in Events",
       lambda: explore_faults(SRC.replace("const evKinds = (events.kinds || []).filter(k => k.id !== 'ev-jesus-parables' && k.id !== 'ev-parables');",
                                          "const evKinds = (events.kinds || []);"), kinds, [p["id"] for p in PARS]))
caught("the 22 cards not drawn in the entry (only the stamped kinds)",
       lambda: explore_faults(SRC.replace("rows.map(r => pzxRow(r, g))", "rows.map(r => '')"), kinds, [p["id"] for p in PARS]))
_body = SRC.split("const pzxSec = () => {", 1)[1].split("const recurs = ", 1)[0]
caught("the stamped kinds drawn before the 22 cards",
       lambda: explore_faults(SRC.replace(_body, _body.replace("rows.map(r => pzxRow(r, g))", "rows.map(r => '')", 1)
                                          .replace("sec('ev-parables'", "sec('ev-parables' /* rows.map(r => pzxRow(r, g)) */", 1)),
                              kinds, [p["id"] for p in PARS]))
caught("the entry leading with the stamped kinds",
       lambda: explore_faults(SRC, list(reversed(kinds)), [p["id"] for p in PARS]))
caught("a parable card missing from the entry",
       lambda: explore_faults(SRC, [dict(kinds[0], rows=rows[1:])] + kinds[1:], [p["id"] for p in PARS]))

def quote_faults(fn):
    """The outer quotation marks of a block: dropped when they enclose the whole block, kept when a closing mark ends
    some other speech inside it (Matt 21:41: the crowd's answer ends the block with a ” that is not Jesus's)."""
    bad = []
    if fn(["“Truly, truly,", "he said.”"]) != ["Truly, truly,", "he said."]:
        bad.append("an enclosing pair of quotation marks was shown")
    got = fn(["He asked.", "“He will bring them,” they replied. “He will lease it.”"])
    if got != ["He asked.", "“He will bring them,” they replied. “He will lease it.”"]:
        bad.append("a closing mark that ends another speech was dropped")
    if fn(["“A, B ‘c’.", "D, E.”"]) != ["A, B ‘c’.", "D, E."]:
        bad.append("an unmatched outer pair was shown")
    return bad


check(not quote_faults(S._pc_unquote), "; ".join(quote_faults(S._pc_unquote)))
js_tab = next(t for t in S.parable_card(d, "event_parable_of_the_good_shepherd")["story"]["tabs"])["html"]
check("pz-dc" in js_tab and "“Truly" not in section(js_tab, "pz-tale"), "the good shepherd's story shows the enclosing marks")
t21 = S.parable_card(d, "event_parable_of_the_wicked_tenants")["story"]["tabs"][0]["html"]
check("rent out the vineyard to other tenants" in plain(t21) and plain(section(t21, "pz-tale")).rstrip().endswith("”"),
      "the tenants' story lost the crowd's closing mark")
caught("the enclosing marks shown (the old rule)", lambda: quote_faults(
    lambda t: t if not (t and t[0].startswith("“")) else t))
caught("a closing mark that ends another speech dropped (a rule that strips every edge)", lambda: quote_faults(
    lambda t: [x.strip("“”") for x in t]))
caught("'Who is in it' back on a parable card", lambda: eventblock_faults(SRC.replace("${pzcard ? '' : sec('ev-who'", "${sec('ev-who'")))
caught("the card's own title not the h1", lambda: [] if "<h1>${esc(d.parable ? d.parable.title" in SRC.replace(
    "<h1>${esc(d.parable ? d.parable.title", "<h1>${esc(d.label") else ["the h1 is not the parable's own title"])
check("<h1>${esc(d.parable ? d.parable.title" in SRC, "the h1 is not the parable's own title")

print(f"parable story cards: {len(EIGHTEEN)} parables, {sum(v[0] for v in counts.values())} tellings, "
      f"{sum(v[1] for v in counts.values())} with Jesus's words on them, {sum(v[2] for v in counts.values())} with a setting; "
      f"planted and caught: {sum(c for _, c in planted)} of {len(planted)}; {len(fails)} failures")
for f in fails:
    print("FAIL", f)
sys.exit(1 if fails else 0)
