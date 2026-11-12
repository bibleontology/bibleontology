"""The concept card counts one thing and its page promises only what it shows (the design panel's concept card,
approved 2026-10-28: docs/review/card-panel-appeal/concept/designer-notes.md).

  - every number in a concept page's title and description is in its article, and no count in a hub's title is
    more than the verses that hold one of its words (same-day item 2); the title's transliterations are folded
    as people type them (ASCII)
  - the page's JSON-LD names the relation vocabulary by the address it answers at (FAULTS #20), uses only terms
    schema.org or that vocabulary define, and names no card, verse or word the page does not link
  - the face's known answers: sacrifice's one count (516 verses with its words, 44 books, 16 placed by hand,
    Genesis 8:20 to Revelation 2:20); Ezra's words Aramaic (FAULTS #16); the Day of Atonement once (FAULTS #12);
    mark_13_5_8 in the Berean's words (FAULTS #18); no "Leads to"; the Lord's table row to its question page; the
    three rulings (A: Prov 8:22 on beginning's face, the Berean's "created me" beside MACULA's "possessed"; B: the
    node atonement named "atonement"; C: the LORD through Hosea at Hos 6:6, Jesus at Matt 9:13 and 12:7); "the
    beginning" off beginning's face; beginning and "In the beginning" linked both ways; the theme to its concept
    as "The words for sacrifice", and "The burnt offering" no longer its door

Every check is proved by a planted fault: a check that cannot fail is not a check.

In process, after the graph loads (~1 minute). Run: python tests/test_concept_cards.py"""
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


d = S.load()


# ---- 1. the page: its numbers are in its article --------------------------------------------------------------
def parts(head, body):
    title = html.unescape(re.search(r"<title>(.*?)</title>", head).group(1))
    desc = html.unescape(re.search(r'<meta name="description" content="(.*?)">', head).group(1))
    art = html.unescape(re.sub(r"<[^>]+>", " ", body.split("<article", 1)[1] if "<article" in body else ""))
    return title, desc, " ".join(art.split())


NUM = re.compile(r"\d+(?::\d+)?")


def page_faults(eid, head, body, with_n=None):
    title, desc, art = parts(head, body)
    out = []
    for where, s in (("title", title), ("description", desc)):
        for m in NUM.finditer(s):
            if not re.search(r"(?<![\d:])" + re.escape(m.group(0)) + r"(?![\d])", art):
                out.append(f"{eid}: the {where} says {m.group(0)}, which its article does not")
    if with_n is not None:
        for m in NUM.finditer(title):
            if ":" not in m.group(0) and int(m.group(0)) > with_n:
                out.append(f"{eid}: the title counts {m.group(0)}, more than its {with_n} verses with its words")
    if not re.fullmatch(r"[\x20-\x7e]+", title):
        out.append(f"{eid}: the title is not in the letters people type ({title})")
    if len(desc) > 300:
        out.append(f"{eid}: description {len(desc)} characters")
    return out


def ld_of(head):
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', head, re.S)
    return json.loads(m.group(1).replace("<\\/", "</")) if m else None


SCHEMA_TERMS = {"@context", "@graph", "@type", "@id", "@reverse", "url", "name", "description", "inLanguage",
                "about", "isPartOf", "publisher", "isBasedOn", "breadcrumb", "itemListElement", "position", "item",
                "mentions", "termCode", "alternateName", "subjectOf", "citation", "creator", "license"}
SCHEMA_TYPES = {"WebPage", "Organization", "Dataset", "Book", "BreadcrumbList", "ListItem", "DefinedTerm",
                "CreativeWork"}


def ld_faults(eid, head, body):
    ld = ld_of(head)
    if ld is None:
        return [f"{eid}: no JSON-LD"]
    out = []
    bor = [c.get("bor") for c in ld.get("@context") or [] if isinstance(c, dict)]
    if bor != ["https://bibleontology.org/ns/relation#"]:
        out.append(f"{eid}: the JSON-LD's vocabulary is {bor}, not https://bibleontology.org/ns/relation#")
    hrefs = set(re.findall(r'href="([^"#?]+)"', body))
    own = f"/e/{S._addr(S._card_id(eid))}"

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k.startswith("bor:"):
                    if k[4:] not in d["cats"]:
                        out.append(f"{eid}: the JSON-LD uses '{k}', which the relation vocabulary does not define")
                elif k not in SCHEMA_TERMS:
                    out.append(f"{eid}: the JSON-LD uses '{k}', which neither vocabulary defines")
                if k == "@type" and v not in SCHEMA_TYPES:
                    out.append(f"{eid}: the JSON-LD types something '{v}'")
                if k == "@type" and v == "Dataset" and not 50 <= len(x.get("description") or "") <= 5000:
                    out.append(f"{eid}: the Dataset '{x.get('name')}' has no description of 50 to 5,000 characters "
                               "(Google reports it as an invalid item)")
                if k in ("@id", "item") and isinstance(v, str) and v.startswith(S.SITE):
                    path = v[len(S.SITE):].split("#")[0]
                    if path.startswith(("/e/", "/p/", "/word/")) and path not in hrefs and path != own:
                        out.append(f"{eid}: the JSON-LD names {path}, which the page does not link")
                if k != "@context":
                    walk(v)
        elif isinstance(x, list):
            for y in x:
                walk(y)
    walk(ld)
    return out


hubs = sorted(p.stem for p in (ROOT / "ontology" / "concept-hubs").glob("*.json") if S.concept_hub(p.stem))
plain = sorted(x for x, e in d["ents"].items() if e.get("type") == "concept" and not S.concept_hub(x))
SAMPLE = hubs + ["beginning"] + plain[::max(1, len(plain) // 60)][:60]
pages, with_of = {}, {}
for eid in SAMPLE:
    c = S.api_entity(d, {"id": [eid]})
    if not c.get("ccard"):
        continue
    out = S.card_page(eid)
    if not out:
        continue
    pages[eid] = out
    if c["ccard"]["kind"] == "hub":
        with_of[eid] = c["ccard"]["with"]["n"]
    for f in page_faults(eid, out[0], out[1], with_of.get(eid)) + ld_faults(eid, out[0], out[1]):
        check(False, f)
check("sacrifice" in pages and "beginning" in pages, "sacrifice or beginning has no concept page")
check(len(with_of) >= 20, f"only {len(with_of)} hub pages built")

# planted: a number of the description not in the article; a title count over the verses with words
h, b = pages["sacrifice"][0], pages["sacrifice"][1]
check(any("516" in f for f in page_faults("sacrifice", h, b.replace("516", "five hundred sixteen"), 516)),
      "planted: the page check did not catch 516 missing from the article")
h2 = h.replace("516 Verses", "532 Verses")
check(any("532" in f for f in page_faults("sacrifice", h2, b + "<p>532</p>", 516)),
      "planted: the page check did not catch a title count over the verses with words")
h3 = h.replace("olah", "ʿōlāh", 1).replace("Hebrew, Greek", "Hebrew ʿōlāh, Greek", 1)
check(any("letters people type" in f for f in page_faults("sacrifice", h3, b)),
      "planted: the page check did not catch an unfolded transliteration in the title")
# planted: the JSON-LD at the address that answers 404, an undefined term, and a card the page does not link
ld = ld_of(h)
bad = copy.deepcopy(ld)
bad["@context"][1]["bor"] = "https://bibleontology.org/ns/"
bad["@graph"][1]["subjectOf"][0]["bor:offered_to"] = {"@id": f"{S.SITE}/e/god"}
bad["@graph"][0]["mentions"].append({"@id": f"{S.SITE}/e/melchizedek", "name": "Melchizedek", "attestedIn": "x"})
# and a Dataset with no description, as Search Console found on every concept page (2026-11-05)
for g in bad["@graph"]:
    for ds in g.get("isBasedOn") or []:
        ds.pop("description", None) if ds.get("@type") == "Dataset" else None
h_bad = re.sub(r'<script type="application/ld\+json">.*?</script>',
               lambda m: '<script type="application/ld+json">' + json.dumps(bad) + "</script>", h, flags=re.S)
lf = ld_faults("sacrifice", h_bad, b)
check(any("ns/relation#" in f for f in lf), "planted: the JSON-LD check did not catch the /ns/ address")
check(any("offered_to" in f for f in lf), "planted: the JSON-LD check did not catch a relation not built")
check(any("attestedIn" in f for f in lf), "planted: the JSON-LD check did not catch an undefined term")
check(any("/e/melchizedek" in f for f in lf), "planted: the JSON-LD check did not catch a card the page does not link")
check(any("has no description" in f for f in lf), "planted: the JSON-LD check did not catch a Dataset without a description")


# ---- 2. the face's known answers ------------------------------------------------------------------------------------
def face_faults(sac, beg, rels, ents):
    out = []
    W = sac["with"]
    if (W["n"], W["books"], len(sac["hand"]), W["first"], W["last"]) != (516, 44, 16, "Gen.8.20", "Rev.2.20"):
        out.append(f"sacrifice counts {W['n']} verses with its words in {W['books']} books, {len(sac['hand'])} by "
                   f"hand, {W['first']} to {W['last']}")
    lang = {w["key"]: w["lang"] for w in sac["words"]}
    for k in ("h1684", "h1685", "h5928"):
        if lang.get(k) != "Aramaic":
            out.append(f"{k} (Ezra 6) is labeled {lang.get(k)}")
    if sac["aka"] != ["sacrifices"]:
        out.append(f"sacrifice is also called {sac['aka']} on its face")
    if "leads" in sac:
        out.append("the face carries the hub's Leads to")
    q = [r["question"]["path"] for f in sac["forms"] for r in f["rows"] if r.get("question")]
    lt = [r for f in sac["forms"] for r in f["rows"] if r["label"].startswith("The Lord's table")]
    if not lt or (lt[0].get("question") or {}).get("path") != "/questions/communion":
        out.append(f"the Lord's table row does not open /questions/communion ({q})")
    doa = [r for r in rels.get("sacrifice", []) if r["other"] == "day_of_atonement" and r["type"] == "in_theme"]
    if len(doa) != 1 or "Lev 7:16" in doa[0].get("refs", []):
        out.append(f"the Day of Atonement is on the card {len(doa)} times: {[r.get('refs') for r in doa]}")
    if "sorrow" in (ents["mark_13_5_8"].get("name") or "").lower():
        out.append(f"mark_13_5_8 is named '{ents['mark_13_5_8']['name']}', the KJV's words")
    if ents["atonement"].get("name") != "atonement":
        out.append(f"the node atonement is named '{ents['atonement'].get('name')}' (ruling B)")
    mercy = next((p for p in sac["passages"] if p["id"] == "i_desired_mercy_and_not_sacrifice"), None)
    sp = {s["id"]: s for s in (mercy or {}).get("speakers") or []}
    if not mercy or sp.get("god", {}).get("refs") != ["Hos.6.6"] or (sp.get("god", {}).get("through") or {}).get("id") != "hosea" \
            or sp.get("jesus", {}).get("refs") != ["Matt.9.13", "Matt.12.7"] or set(sp) != {"god", "jesus"}:
        out.append(f"'I desire mercy, not sacrifice' speakers {[(s['id'], s['refs']) for s in sp.values()]} (ruling C)")
    pr = next((p for p in beg["passages"] if "Prov.8.22" in p["refs"]), None)
    rd = (pr or {}).get("renderings") or [{}]
    if not pr or rd[0].get("berean") != "created me" or rd[0].get("macula") != "possessed":
        out.append(f"Prov 8:22 is not on beginning's face with 'created me' beside 'possessed' (ruling A): {rd}")
    if "the beginning" in beg["aka"]:
        out.append("'the beginning' is on beginning's face")
    if (beg.get("phrase") or {}).get("id") != "theme_creation_r2":
        out.append("beginning does not link 'In the beginning' (theme_creation_r2)")
    if [x["id"] for x in (beg.get("first") or {}).get("xref") or []][:1] != ["John.1.1"]:
        out.append("Genesis 1:1 on beginning's face has not the Berean's cross-reference to John 1:1")
    return out


sac = S.api_entity(d, {"id": ["sacrifice"]})["ccard"]
beg = S.api_entity(d, {"id": ["beginning"]})["ccard"]
for f in face_faults(sac, beg, d["rels"], d["ents"]):
    check(False, f"face: {f}")
for what, plant in [
    ("a count by uses", lambda s, b, r, e: s["with"].update(n=532)),
    ("Ezra's word labeled Hebrew", lambda s, b, r, e: [w.update(lang="Hebrew") for w in s["words"] if w["key"] == "h1684"]),
    ("the kinds back as other names", lambda s, b, r, e: s["aka"].extend(["burnt offering", "offering"])),
    ("the Lord's table without its question", lambda s, b, r, e: [x.pop("question", None) for f in s["forms"] for x in f["rows"]]),
    ("the Day of Atonement twice", lambda s, b, r, e: r["sacrifice"].append(
        {"other": "day_of_atonement", "type": "in_theme", "refs": ["Lev 7:16"]})),
    ("the KJV name back", lambda s, b, r, e: e["mark_13_5_8"].update(name="Beginning of sorrows")),
    ("ruling B undone", lambda s, b, r, e: e["atonement"].update(name="reconciliation")),
    ("ruling C undone", lambda s, b, r, e: [x.update(speakers=[{"id": "jesus", "refs": ["Hos.6.6", "Matt.9.13"]}])
                                            for x in s["passages"] if x["id"] == "i_desired_mercy_and_not_sacrifice"]),
    ("ruling A undone", lambda s, b, r, e: b.update(passages=[])),
    ("'the beginning' back", lambda s, b, r, e: b["aka"].append("the beginning")),
]:
    s2, b2 = copy.deepcopy(sac), copy.deepcopy(beg)
    r2 = {"sacrifice": list(d["rels"]["sacrifice"])}
    e2 = {k: dict(d["ents"][k]) for k in ("mark_13_5_8", "atonement")}
    plant(s2, b2, r2, e2)
    check(face_faults(s2, b2, r2, e2), f"planted: the face check did not catch {what}")


# ---- 3. the two-way links -----------------------------------------------------------------------------------------
def link_faults(r2_head, r2_body, theme_body):
    out = []
    if "In the Beginning (Gen 1:1, John 1:1): Meaning and Verses" not in html.unescape(r2_head):
        out.append("theme_creation_r2's page is not titled for the phrase")
    if 'href="/e/beginning"' not in r2_body:
        out.append("theme_creation_r2's page does not link beginning")
    if not re.search(r'<a href="/e/sacrifice">The words for sacrifice</a>', theme_body):
        out.append("the theme Sacrifice does not open the concept as 'The words for sacrifice'")
    if re.search(r'<a href="/e/sacrifice">The burnt offering</a>', theme_body):
        out.append("the theme still reaches the concept through 'The burnt offering'")
    return out


r2h, r2b, _a = S.card_page("theme_creation_r2")
tp = S.theme_page("sacrifice")
th = tp[1] if tp else ""
for f in link_faults(r2h, r2b, th):
    check(False, f"links: {f}")
check(link_faults(r2h, r2b.replace('href="/e/beginning"', 'href="/e/beginnings"'), th),
      "planted: the link check did not catch r2 without beginning")
check(link_faults(r2h, r2b, th.replace("The words for sacrifice", "Sacrifice")),
      "planted: the link check did not catch the theme's door anchored otherwise")

print(f"{len(pages)} concept pages ({len(with_of)} hubs), {len(fails)} failures")
for f in fails[:25]:
    print("FAIL", f)
sys.exit(1 if fails else 0)
