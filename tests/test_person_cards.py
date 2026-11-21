"""The person card says what its relations say, in the Berean's words, and its page promises only what it shows
(the design panel's person card, approved 2026-10-28: docs/review/card-panel-appeal/person/designer-notes.md).

  - a verdict, title or likeness on a person card is named in the words of a verse it cites, as the Berean prints
    them (same-day item 4: "counted for righteousness" sat over Gen 15:6, which reads "credited to him as
    righteousness"); the ones not yet relabeled are listed, and the list may only shrink
  - every name and every verse in a person page's title and description is a link in its article (item 1)
  - the page's JSON-LD names the relation vocabulary by the address it answers at (FAULTS #20: /ns/ is 404), uses
    only terms schema.org or that vocabulary define, and names no person or verse the page does not link
  - the face's known answers: the kin with their verses and mothers (item 3), Abraham's and Terah's ranges, strip,
    ages and family, the two rulings, Terah's name counted without the camp Tarah and no Septuagint form without a
    Greek letter (item 5), the hand-paired passages (item 6)

Every check is proved by a planted fault: a check that cannot fail is not a check.

In process, after the graph loads (~1 minute). Run: python tests/test_person_cards.py"""
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


def check(ok, msg):
    if not ok:
        fails.append(msg)


# ---- 1. labels in the Berean's words ---------------------------------------------------------------------------
LABELED = ("described_as", "titled", "likened_to")
# a figure node is named for its figure, not quoted ("wine, as a figure")
FIGURE = re.compile(r"(, as a figure|\(as an image\))$")
# NOT YET IN THE BEREAN'S WORDS (2026-10-28): each would be a relabel, or a ruling that the label is the graph's
# summary and not a quotation. The list may only shrink; a new one fails.
KNOWN = {
    ("abiathar", "the_high_priest"), ("abraham", "going_to_fathers_in_peace"),
    ("bashemath_daughter_of_elon", "a_grief_of_mind"), ("benjamin", "image_wolf"), ("dan", "image_lion"),
    ("elihu_son_of_barachel", "has_yet_to_speak_on_gods_behalf"), ("esau", "faint"), ("isaac", "dim_eyes"),
    ("isaac", "isaacs_wealth"), ("jacob", "a_stench_to_the_inhabitants_of_the_land"), ("jacob", "in_good_health"),
    ("jacob", "prince"), ("jeremiah", "image_drunken_man"), ("jesus", "image_serpent"), ("jesus", "the_christ"),
    ("job", "infants"), ("job", "accepted_of_the_lord"), ("job", "condemned_by_his_own_mouth"),
    ("job", "lived_an_hundred_and_forty_years"), ("job", "one_who_knew_not_wonderful_things"),
    ("job", "one_who_uttered_that_which_he_understood_not"),
    ("job", "self_abhorring_and_repenting_in_dust_and_ashes"), ("job", "image_eyes"), ("job", "image_garment"),
    ("job", "image_owl"), ("judah", "comforted"), ("judith", "a_grief_of_mind"),
    ("rahab_of_jericho", "justified_by_works"), ("woman_person", "woman_title"),
}
# the four relabeled 2026-10-28: these must pass
FIXED = {("abraham", "counted_for_righteousness"), ("abraham", "full_of_years"),
         ("abraham", "ninety_and_nine_years_old"), ("abraham", "image_covering_of_the_eyes")}


def _norm(s):
    s = (s or "").lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"[^a-z0-9' -]+", " ", s).replace("-", " ")


def label_faults(d):
    """(person, target, name) for every labeled target not in any verse it cites."""
    out = []
    for eid, e in d["ents"].items():
        if e.get("type") != "person":
            continue
        for r in d["rels"].get(eid, []):
            if r["dir"] != "out" or r["type"] not in LABELED or r.get("certainty") != "explicit":
                continue
            name = (d["ents"].get(r["other"]) or {}).get("name") or r["other"]
            if FIGURE.search(name):
                continue
            texts = []
            for ref in r.get("refs") or []:
                sp = S._site_span(d, ref)
                if sp:
                    texts += [d["verses"].get((sp[0], c, v)) or "" for c, v in
                              [(sp[1], v) for v in range(sp[2], (sp[4] if sp[3] == sp[1] else sp[2]) + 1)]]
            if not any(" " + _norm(name).strip() + " " in " " + _norm(t) + " " for t in texts):
                out.append((eid, r["other"], name))
    return out


def unexpected(found):
    return [f for f in found if (f[0], f[1]) not in KNOWN]


d = S.load()
found = label_faults(d)
for f in unexpected(found):
    check(False, f"{f[0]}: '{f[2]}' ({f[1]}) is in none of the verses it cites, as the Berean prints them")
for f in found:
    check((f[0], f[1]) not in FIXED, f"{f[0]}: relabeled '{f[1]}' is again not in its verse")
# planted: the KJV's "counted for righteousness" back on the node
_was = d["ents"]["counted_for_righteousness"]["name"]
d["ents"]["counted_for_righteousness"]["name"] = "counted for righteousness"
planted = label_faults(d)
check(any(f[1] == "counted_for_righteousness" for f in unexpected(planted)),
      "planted: the label check did not catch 'counted for righteousness' over Gen 15:6")
d["ents"]["counted_for_righteousness"]["name"] = _was


# ---- 2. the page: every name and verse in the title and description is a link --------------------------------
NOT_NAMES = {"Family", "Tree", "Age", "Years", "Father", "Mother", "Son", "Daughter", "Child", "Wife", "Husband",
             "Spouse", "Bible", "Lived", "He", "She", "They", "In", "The", "Genesis"}
VERSE = re.compile(r"\b((?:[1-3] ?)?[A-Z][a-z]+) (\d+):(\d+)(?:[–-](\d+))?")


def page_parts(head, body):
    title = html.unescape(re.search(r"<title>(.*?) · Bible Ontology</title>", head).group(1))
    desc = html.unescape(re.search(r'<meta name="description" content="(.*?)">', head).group(1))
    return title, desc


def page_faults(eid, head, body):
    """Why a person page's title or description names something its article does not link, or []."""
    e = d["ents"][S._card_id(eid)]
    own = {w for n in [e["name"]] + list(e.get("aka") or []) for w in n.split(" ")}   # the page's own subject
    own |= {w.capitalize() for w in own}   # "a messenger" is titled "A messenger": the subject's own word, capitalized
    art = body.split('<article', 1)[1] if '<article' in body else ""
    anchors = [html.unescape(re.sub(r"<[^>]+>", "", t)) for t in re.findall(r"<a [^>]*>(.*?)</a>", art)]
    hrefs = set(re.findall(r'href="([^"]+)"', art))
    out = []
    title, desc = page_parts(head, body)
    for where, s in (("title", title), ("description", desc)):
        s_wo = VERSE.sub(" ", s)
        for run in re.findall(r"\b[A-Z][\w'’-]*(?: [A-Z][\w'’-]*)*", s_wo):
            for w in [run] if run not in NOT_NAMES else []:
                parts = [p for p in w.split(" ") if p not in NOT_NAMES]
                w = " ".join(parts)
                if not w or all(p in own for p in parts):
                    continue
                if not any(re.search(r"(?<![\w])" + re.escape(w) + r"(?![\w])", a) for a in anchors):
                    out.append(f"{eid}: the {where} names '{w}', which the page does not link")
        for m in VERSE.finditer(s):
            b = S.TITLE_BACK.get(m.group(1), m.group(1).replace(" ", ""))
            for v in range(int(m.group(3)), int(m.group(4) or m.group(3)) + 1):
                if f"/p/{b}.{m.group(2)}.{v}" not in hrefs:
                    out.append(f"{eid}: the {where} cites {b} {m.group(2)}:{v}, which the page does not link")
    return out


def ld_of(head):
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', head, re.S)
    return json.loads(m.group(1).replace("<\\/", "</")) if m else None


SCHEMA_TERMS = {"@context", "@graph", "@type", "@id", "url", "name", "description", "mainEntity", "publisher",
                "mainEntityOfPage", "alternateName", "parent", "spouse", "children", "sibling", "homeLocation",
                "deathPlace", "birthPlace", "additionalType", "subjectOf"}
SCHEMA_TYPES = {"WebPage", "Person", "Organization", "Role", "Place"}


def ld_faults(eid, head, body):
    """Why the JSON-LD points at nothing, uses a term no vocabulary defines, or names what the page does not."""
    ld = ld_of(head)
    if ld is None:
        return [f"{eid}: no JSON-LD"]
    out = []
    ctx = ld.get("@context") or []
    bor = [c.get("bor") for c in ctx if isinstance(c, dict)]
    if bor != ["https://bibleontology.org/ns/relation#"]:
        out.append(f"{eid}: the JSON-LD's vocabulary is {bor}, not https://bibleontology.org/ns/relation#")
    hrefs = set(re.findall(r'href="([^"#?]+)"', body))
    rel_types = set(d["cats"])

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k not in SCHEMA_TERMS:
                    out.append(f"{eid}: the JSON-LD uses '{k}', which neither vocabulary defines")
                if k == "@type" and v not in SCHEMA_TYPES:
                    out.append(f"{eid}: the JSON-LD types something '{v}'")
                if k == "additionalType" and not (v.startswith("bor:") and v[4:] in rel_types):
                    out.append(f"{eid}: additionalType '{v}' is not a term of the relation vocabulary")
                if k == "@id" and isinstance(v, str) and v.startswith(S.SITE) and k != "@context":
                    path = v[len(S.SITE):].split("#")[0]
                    if path.startswith(("/e/", "/p/")) and path not in hrefs and path != f"/e/{S._addr(S._card_id(eid))}":
                        out.append(f"{eid}: the JSON-LD names {path}, which the page does not link")
                if k != "@context":
                    walk(v)
        elif isinstance(x, list):
            for y in x:
                walk(y)
    walk(ld)
    return out


SAMPLE = ["abraham", "terah", "keturah", "boaz", "eve", "tamar", "isaac", "david", "nahor_son_of_terah"]
persons = sorted(x for x, e in d["ents"].items() if e.get("type") == "person")
SAMPLE += persons[::max(1, len(persons) // 120)][:120]
pages = {}
for eid in SAMPLE:
    out = S.card_page(eid)
    if not out:
        continue
    pages[eid] = out
    head, body = out[0], out[1]
    title, desc = page_parts(head, body)
    check("every verse" not in title.lower() and "every verse" not in desc.lower(),
          f"{eid}: the title or description says 'every verse'")
    check(len(desc) <= 300, f"{eid}: description {len(desc)} characters")
    # a page built from the person's relations (the who line as its first paragraph); one with no family recorded
    # keeps its record's own description, which is not built from links
    if 'class="ssr-who"' in body:
        check(len(desc) <= 160, f"{eid}: description {len(desc)} characters, over 160")
        for f in page_faults(eid, head, body):
            check(False, f)
    if ld_of(head) is not None:
        for f in ld_faults(eid, head, body):
            check(False, f)
check(ld_of(pages["abraham"][0]) is not None and ld_of(pages["terah"][0]) is not None,
      "Abraham's or Terah's page has no JSON-LD")

# planted: a name of the description unlinked in the article (every link to Lot taken out)
h, b = pages["terah"][0], pages["terah"][1]
b2 = re.sub(r'<a href="/e/lot">([^<]*)</a>', r"\1", b)
check(any("'Lot'" in f for f in page_faults("terah", h, b2)),
      "planted: the page check did not catch Lot unlinked")
# planted: a verse of the description unlinked
b3 = b.replace('href="/p/Gen.11.32"', 'href="/p/Gen.11.33x"')
check(any("Gen 11:32" in f for f in page_faults("terah", h, b3)),
      "planted: the page check did not catch Gen 11:32 unlinked")
# planted: the JSON-LD at the address that answers 404, and a person the page does not link
ld = ld_of(h)
bad = copy.deepcopy(ld)
bad["@context"][1]["bor"] = "https://bibleontology.org/ns/"
bad["@graph"][1]["children"].append({"@type": "Role", "children": {"@id": f"{S.SITE}/e/milcah#person"},
                                     "attestedIn": [f"{S.SITE}/p/Gen.11.29"]})
h_bad = re.sub(r'<script type="application/ld\+json">.*?</script>',
               lambda m: '<script type="application/ld+json">' + json.dumps(bad) + "</script>", h, flags=re.S)
lf = ld_faults("terah", h_bad, b)
check(any("ns/relation#" in f for f in lf), "planted: the JSON-LD check did not catch the /ns/ address")
check(any("attestedIn" in f for f in lf), "planted: the JSON-LD check did not catch an undefined term")
check(any("/e/milcah" in f for f in lf), "planted: the JSON-LD check did not catch a person the page does not link")


# ---- 3. the face's known answers ----------------------------------------------------------------------------------
def face_faults(a, t):
    """Why Abraham's (a) or Terah's (t) card is not the approved card, or []."""
    out = []
    pa, pt = a["pcard"], t["pcard"]
    kin = {(k["rel"], k["id"]): k for k in a["kin"]}
    if not all(k.get("refs") for k in a["kin"]):
        out.append("a kin entry without its verses")
    for son in ("zimran", "jokshan", "medan", "midian", "ishbak", "shuah_person"):
        if (kin.get(("father of", son)) or {}).get("mother", {}).get("id") != "keturah":
            out.append(f"{son} is not under Keturah (mother_of from her card)")
    if (kin.get(("father of", "isaac")) or {}).get("mother", {}).get("id") != "sarah":
        out.append("Isaac is not under Sarah")
    sis = kin.get(("brother of", "sarah")) or {}
    if sis.get("claimed_by") != "abraham":
        out.append("Sarah as Abraham's sister is not marked as his words (ruling A)")
    if not any(k["id"] == "sarah" and k.get("claimed_by") == "abraham" for k in t["kin"]):
        out.append("Sarah as Terah's daughter is not marked as Abraham's words (ruling A)")
    # ruling B, as ruled again 2026-11-14 (R-16): Abraham's verdict is the text's own words, "credited to him as
    # righteousness" (Gen 15:6, quoted Rom 4:3, Gal 3:6, Jas 2:23), not the site's "justified by faith"
    jf = [r for r in S.load()["rels"]["abraham"] if r["other"] == "counted_for_righteousness" and r["type"] == "described_as"]
    if [r["refs"] for r in jf] != [["Gen 15:6", "Rom 4:3", "Gal 3:6", "Jas 2:23"]]:
        out.append(f"'credited to him as righteousness' cites {[r['refs'] for r in jf]}, not Gen 15:6, Rom 4:3, Gal 3:6, Jas 2:23 (ruling B)")
    if any(r["other"] == "justified_by_faith" and r["type"] == "described_as" for r in S.load()["rels"]["abraham"]):
        out.append("Abraham is still 'described as justified by faith', the site's paraphrase (ruling B)")
    R = pa["range"] or {}
    if (R.get("b"), R.get("c1"), R.get("v1"), R.get("c2"), R.get("v2")) != ("Gen", 11, 26, 25, 10):
        out.append(f"Abraham's range is {R}")
    if [s["c"] for s in pa["strip"] or []] != list(range(11, 26)):
        out.append("Abraham's strip is not Genesis 11-25")
    if [x["age"] for x in pa["ages"]] != [75, 86, 99, 100, 175]:
        out.append(f"Abraham's ages are {[x['age'] for x in pa['ages']]}")
    evs = {e["id"]: e for e in pa["events"]}
    beats = [evs[b]["order"] for b in pa["beats"]]
    if len(pa["beats"]) != 7 or beats != sorted(beats):
        out.append("the seven events are not seven, in the text's order")
    if (evs.get("event_the_destruction_of_sodom_and_gomorrah") or {}).get("within") != "event_destruction_of_sodom":
        out.append("the Sodom record inside the other is not listed under it")
    if (pa["opening"] or {}).get("event", {}).get("id") != "event_call_of_abram":
        out.append("Abraham's story does not open with the call of Abram")
    if [w["name"] for w in pa["family"]["wives"]] != ["Sarah", "Hagar", "Keturah"]:
        out.append("Abraham's wives are not Sarah, Hagar, Keturah in the text's order")
    if not any(n["id"] == "lot" and n["under"] == "haran" for n in pa["family"]["named"]):
        out.append("Lot is not placed as Haran's son")
    pair = pa["pair"] or {}
    cols = {c["title"]: [r["other"] for r in c["rels"]] for c in pair.get("passages") or []}
    if list(cols) != ["Romans 4:2–5", "Galatians 3:6–9", "James 2:21–24"]:
        out.append(f"the paired passages are {list(cols)}")
    elif "counted_for_righteousness" not in cols["Romans 4:2–5"] or "justified_by_works" not in cols["James 2:21–24"]:
        out.append("a verdict is missing under its passage")
    if any("’’" in x or not re.search(r"[Ͱ-Ͽἀ-῿]", x) for x in (a.get("original") or {}).get("lxx") or []):
        out.append(f"a Septuagint form with no Greek letter: {(a.get('original') or {}).get('lxx')}")
    nm = {w["key"]: w for w in pt["names"]}
    tw = nm.get("h8646") or {}
    if tw.get("verses") != 9 or [(o["id"], o["n"]) for o in tw.get("others") or []] != [("tarah", 2)]:
        out.append(f"Terah's name is counted {tw.get('verses')} verses, others {tw.get('others')}")
    if [v["id"] for v in (pt["quote"] or {}).get("verses") or []] != ["Gen.11.26", "Gen.11.27", "Gen.11.31", "Gen.11.32"]:
        out.append("Terah's quoted verses are not Gen 11:26-27, 31-32")
    if ((pt["quote"] or {}).get("next") or {}).get("id") != "event_call_of_abram":
        out.append("Terah's card does not link the next event, the call of Abram")
    if pt["strip"] is not None:
        out.append("Terah, with no events, has a strip")
    return out


a = S.api_entity(d, {"id": ["abraham"]})
t = S.api_entity(d, {"id": ["terah"]})
for f in face_faults(a, t):
    check(False, f"face: {f}")
# planted: each known answer broken in a copy
for what, plant in [
    ("Keturah's sons in one row", lambda a, t: [k.pop("mother", None) for k in a["kin"] if k["id"] == "zimran"]),
    ("ruling A undone", lambda a, t: [k.pop("claimed_by", None) for k in a["kin"] if k["id"] == "sarah"]),
    ("events by count", lambda a, t: a["pcard"]["beats"].reverse()),
    ("the camp counted", lambda a, t: [w.update(verses=11, others=[]) for w in t["pcard"]["names"]]),
    ("the junk Septuagint form", lambda a, t: a["original"]["lxx"].append("’’")),
]:
    a2, t2 = copy.deepcopy(a), copy.deepcopy(t)
    plant(a2, t2)
    check(face_faults(a2, t2), f"planted: the face check did not catch {what}")

print(f"{len(found)} labels outside their verses ({len(found) - len(unexpected(found))} known), "
      f"{len(pages)} person pages, {len(fails)} failures")
for f in fails[:20]:
    print("FAIL", f)
if "--labels" in sys.argv:
    for f in found:
        print("LABEL", f)
sys.exit(1 if fails else 0)
