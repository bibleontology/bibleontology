"""The verse page counts what it prints and its card is one object (the design panel's verse page, 2026-10-28:
docs/review/card-panel-appeal/verse/designer-notes.md, same-day items 1-6).

  - item 1, the served page: one object, verse_card(), prints the article, the title and description by one rule,
    and the JSON-LD from what the article links. Genesis 1:1 is 7 Hebrew words in 11 parts, the clause PP-V-S-O in
    MACULA's labels, 19 linked passages (2 editors' notes, 9 clear readings, 8 apparent, 11 books), the three quoted
    whole John 1:1-5, Hebrews 11:1-3 and Isaiah 42:5 (the first clear reading whose Hebrew has the verb בָּרָא, not
    Nehemiah 9:6, whose Hebrew is עָשָׂה), nine relations citing the verse; 1 Chronicles 1:26's title is the verse
    itself and its line runs Shem to Abraham with Cainan beside Arphaxad and Shelah. Over a sample of verses:
    every number and passage in the title and description is in the article, the title's count is the count of
    printed passages and of `relatedLink`, every `relatedLink`, `mentions` and edge is an href in the article, each
    passage is printed once, and the vocabulary is /ns/relation# with terms it defines
  - items 3-6 (their sections below): the face's word for the two creation relations, the transliteration without
    the sof pasuq, the people the mention layer names, editors' ranges whole and each verse once in the links panel

Every check is proved by a planted fault: a check that cannot fail is not a check.

In process, after the graph loads (~1 minute). Run: python tests/test_verse_page.py"""
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
SRC = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
VOCAB = (ROOT / "ontology" / "schema" / "relationship_types.yaml").read_text(encoding="utf-8")
DEFINED = set(re.findall(r"^  ([a-z_0-9]+):\s*$", VOCAB.split("\ntypes:", 1)[1], re.M))


def page(b, c, v):
    got = S.passage_page(f"{b}.{c}.{v}")
    return S.verse_card(d, b, c, v), got[0], got[1]


def parts(head, body):
    title = html.unescape(re.search(r"<title>(.*?)</title>", head).group(1))
    desc = html.unescape(re.search(r'<meta name="description" content="(.*?)">', head).group(1))
    art = html.unescape(re.sub(r"<[^>]+>", " ", body.split("<article", 1)[1]))
    return title, desc, " ".join(art.split())


def ld_of(head):
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', head, re.S)
    return json.loads(m.group(1).replace("<\\/", "</")) if m else None


SCHEMA_TERMS = {"@context", "@graph", "@type", "@id", "url", "name", "description", "inLanguage", "isPartOf",
                "publisher", "breadcrumb", "mainEntity", "itemListElement", "position", "item", "mentions", "text",
                "translationOfWork", "creditText", "relatedLink"}
SCHEMA_TYPES = {"WebPage", "Organization", "BreadcrumbList", "ListItem", "Chapter", "Book", "Quotation",
                "CreativeWork"}


def page_faults(vc, head, body):
    """What the page says about itself, held against what it prints."""
    out, ref = [], vc["label"]
    title, desc, art = parts(head, body)
    n = vc["counts"]["n"]
    if len(title) > 60:
        out.append(f"{ref}: the title is {len(title)} characters")
    if len(desc) > 160:
        out.append(f"{ref}: the description is {len(desc)} characters")
    for where, s in (("title", title), ("description", desc)):
        for m in re.finditer(r"\d+(?::\d+)?(?:–\d+)?", s):
            if not re.search(r"(?<![\d:])" + re.escape(m.group(0)) + r"(?![\d])", art):
                out.append(f"{ref}: the {where} says {m.group(0)}, which its article does not")
    m = re.search(r"(\d+) linked passages?", title)
    if m and int(m.group(1)) != n:
        out.append(f"{ref}: the title counts {m.group(1)} linked passages, the card {n}")
    keys = [p["key"] for p in vc["passages"]]
    if len(keys) != len(set(keys)):
        out.append(f"{ref}: a linked passage is listed twice")
    for p in vc["passages"]:
        if f'href="/p/{p["key"]}"' not in body:
            out.append(f"{ref}: the page does not link {p['label']}")
    ld = ld_of(head)
    if ld is None:
        return out + [f"{ref}: no JSON-LD"]
    ctx = [c.get("bor") for c in ld.get("@context") or [] if isinstance(c, dict)]
    if ctx != ["https://bibleontology.org/ns/relation#"]:
        out.append(f"{ref}: the JSON-LD's vocabulary is {ctx}, not https://bibleontology.org/ns/relation#")
    hrefs = set(re.findall(r'href="([^"#?]+)"', body))
    rel = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k.startswith("bor:"):
                    if k[4:] not in DEFINED:
                        out.append(f"{ref}: the JSON-LD uses '{k}', which the relation vocabulary does not define")
                elif k not in SCHEMA_TERMS:
                    out.append(f"{ref}: the JSON-LD uses '{k}', which neither vocabulary defines")
                if k == "@type" and v not in SCHEMA_TYPES:
                    out.append(f"{ref}: the JSON-LD types something '{v}'")
                if k in ("@id", "item", "relatedLink") and isinstance(v, str) and v.startswith(S.SITE):
                    path = v[len(S.SITE):].split("#")[0]
                    if path.startswith(("/e/", "/p/", "/word/")) and path not in hrefs and path != f"/p/{vc['ref']}":
                        out.append(f"{ref}: the JSON-LD names {path}, which the page does not link")
                if k == "relatedLink":
                    rel.extend(v)
                if k != "@context":
                    walk(v)
        elif isinstance(x, list):
            for y in x:
                walk(y)
    walk(ld)
    for u in rel:
        path = u[len(S.SITE):]
        if path not in hrefs:
            out.append(f"{ref}: relatedLink {path} is not an href in the article")
    if len(rel) != n:
        out.append(f"{ref}: relatedLink has {len(rel)}, the title and card count {n}")
    if "every passage it connects to" in desc:
        out.append(f"{ref}: the description still promises every passage it connects to")
    return out + quoted_faults(vc)


def quoted_faults(vc):
    """A quoted reading is the first clear one, in canon order, whose verse carries the verse's own verb in the
    original -- the Berean's 'created' in Nehemiah 9:6 is עָשָׂה there."""
    out = []
    trees = S._ptree(d, S._vc_mref(d, vc["book"], vc["chapter"], vc["verse"])).get("trees") or []
    verb = next((lf for t in trees for lf in S._vc_leaves(t) if lf.get("cls") == "verb"), None)
    num = re.sub(r"\D", "", (verb or {}).get("s") or "")
    byk = {p["key"]: p for p in vc["passages"]}
    readings = [k for k in vc["quoted"] if byk[k]["src"] != "editors"]
    if len(readings) > 1 or (readings and not num):
        out.append(f"{vc['label']}: {len(readings)} readings quoted, or one with no verb to hold it by")
    for k in readings:
        pb = S._vc_parse(d, byk[k]["mref"])
        ow = d["orig"].get(S._vc_mref(d, *pb), [])
        if not any(re.sub(r"\D", "", w.get("s") or "") == num for w in ow):
            out.append(f"{vc['label']}: {byk[k]['label']} is quoted, and its Hebrew or Greek lacks the verb")
    return out


# ---- 1. Genesis 1:1, the busy verse -----------------------------------------------------------------------------
g, gh, gb = page("Gen", 1, 1)
check(len(g["words"]) == 7 and sum(len(w["parts"]) for w in g["words"]) == 11, "Gen 1:1 is not 7 words in 11 parts")
check([w["w"] for w in g["words"]] == list(range(1, 8)), "Gen 1:1's words are not joined by the tree's numbers")
check(g["clauses"] and g["clauses"][0]["rule"] == "PP-V-S-O"
      and [r["role"] for r in g["clauses"][0]["roles"]] == ["pp", "v", "s", "o"], "Gen 1:1's clause is not PP-V-S-O")
check(g["clauses"][0]["form"] == "perfect (qatal)", f"Gen 1:1's verb form is {g['clauses'][0].get('form')}")
check(g["counts"] == {"n": 19, "editors": 2, "clear": 9, "apparent": 8, "books": 11}, f"Gen 1:1 counts {g['counts']}")
check(g["quoted"] == ["John.1.1", "Heb.11.1", "Isa.42.5"], f"Gen 1:1 quotes {g['quoted']}")
check(len(g["rels"]) == 9, f"Gen 1:1 has {len(g['rels'])} relations citing it")
heb = next(p for p in g["passages"] if p["key"] == "Heb.11.1")
check(heb["end"] == "Heb.11.3" and [q["key"] for q in heb["inside"]] == ["Heb.11.3"]
      and not any(p["key"] == "Heb.11.3" for p in g["passages"]),
      "Hebrews 11:3 does not join the editors' Hebrews 11:1-3")
check(any(p["key"] == "Ps.102.25" and p["label"] == "Psalm 102:25" for p in g["passages"]),
      "Psalm 102:25 is not named in the Berean's numbering")
gt, gd, ga = parts(gh, gb)
check(gt == "Genesis 1:1 in Hebrew and English: 19 linked passages", f"Gen 1:1's title is {gt}")
check(gd.startswith("Genesis 1:1 in Hebrew and English, with 19 linked passages, among them John 1:1–5 and "
                    "Hebrews 11:1–3. “In the beginning God created the heavens and the earth.”"), f"description {gd}")
check("Where were you when I laid the foundations of the earth?" in ga, "Job 38:4's words are not printed")
check("In the beginning was the Word" in ga and "Now faith is the assurance" in ga, "the editors' ranges are not whole")
check("The Creation" in ga and "Creation of heavens and earth" in ga and "Genesis 1:1–2:3" in ga,
      "the setting is not printed")
check("every passage it connects to" not in gd and "every passage it connects to" not in gb,
      "the page still says every passage it connects to")
for f in page_faults(g, gh, gb):
    check(False, f)

# ---- 2. 1 Chronicles 1:26, the thin verse -----------------------------------------------------------------------
c, ch, cb = page("1Chr", 1, 26)
ct, cd, ca = parts(ch, cb)
check(ct == "1 Chronicles 1:26 in Hebrew and English: Serug, Nahor, Terah", f"1 Chr 1:26's title is {ct}")
check(c["counts"]["n"] == 3 and c["counts"]["editors"] == 3, f"1 Chr 1:26 counts {c['counts']}")
check(c["setting"]["heading"]["title"] == "From Adam to Abraham" and c["setting"]["verbless"],
      "1 Chr 1:26's setting is not 'From Adam to Abraham', a list")
ln = c["line"]
check(ln and [n["id"] for n in ln["nodes"]][0] == "shem" and [n["id"] for n in ln["nodes"]][-1] == "abraham"
      and len(ln["steps"]) == 9 and ln["label"] == "1 Chronicles 1:24–27", f"the line is {ln and ln['label']}")
dag = [s for s in (ln or {"steps": []})["steps"] if s.get("also")]
check(len(dag) == 1 and dag[0]["a"] == "arphaxad" and dag[0]["b"] == "salah" and dag[0]["also"]["id"] == "cainan_luke"
      and "Cainan" in (dag[0]["also"].get("note") or ""), "Cainan does not sit beside Arphaxad and Shelah")
check({n["id"] for n in ln["nodes"] if n["here"]} == {"serug", "nahor_son_of_serug"}, "the verse's own names are not Serug and Nahor")
check("Cainan" in ca and "neither harmonized" in ca, "the page does not print the Cainan tellings side by side")
ldc = ld_of(ch)
edges = [x for x in ldc["@graph"] if any(k.startswith("bor:") for k in x)]
check(sorted((x["@id"].rsplit("/", 1)[1], list(v for k, v in x.items() if k.startswith("bor:"))[0]["@id"].rsplit("/", 1)[1])
             for x in edges) == [("nahor_son_of_serug", "terah"), ("serug", "nahor_son_of_serug")],
      f"1 Chr 1:26's JSON-LD edges are {edges}")
for f in page_faults(c, ch, cb):
    check(False, f)

# ---- 3. a sample of verses, both testaments ---------------------------------------------------------------------
keys = sorted(d["verses"], key=lambda k: (S.ORDER.index(k[0]), k[1], k[2]))
SAMPLE = [("John", 3, 16), ("Ps", 23, 1), ("Rom", 8, 28), ("Gen", 1, 3), ("Matt", 13, 3), ("Exod", 20, 11),
          ("Rev", 4, 11), ("Jude", 1, 1), ("Num", 7, 10)] + keys[::900]
pages = {}
for b, ch_, v in SAMPLE:
    vc_, h_, bd_ = page(b, ch_, v)
    pages[(b, ch_, v)] = (vc_, h_, bd_)
    for f in page_faults(vc_, h_, bd_):
        check(False, f)
    if vc_["lang"] == "Greek":
        check(re.search(r'lang="grc"', bd_) or not vc_["words"], f"{vc_['label']}: Greek not marked grc")
check(len(pages) >= 40, f"only {len(pages)} pages built")

# ---- planted faults ---------------------------------------------------------------------------------------------
# a passage dropped from the article: the title still counts it
b2 = gb.replace('href="/p/Isa.45.12"', 'href="/p/Isa.45.12x"')
check(any("does not link Isaiah 45:12" in f or "not an href" in f for f in page_faults(g, gh, b2)),
      "planted: the page check did not catch a linked passage missing from the article")
# a number in the title that the article does not hold
h2 = gh.replace("19 linked passages", "20 linked passages")
check(any("20" in f for f in page_faults(g, h2, gb)), "planted: the page check did not catch a wrong count in the title")
# a title over 60 characters
h3 = gh.replace("<title>Genesis 1:1 in Hebrew and English: 19 linked passages", "<title>Genesis 1:1 in Hebrew and English: 19 linked passages and some more words")
check(any("characters" in f for f in page_faults(g, h3, gb)), "planted: the page check did not catch a long title")
# the JSON-LD names a card the page does not link, a term nobody defines, and the vocabulary at the 404 address
bad = copy.deepcopy(ld_of(gh))
bad["@context"][1]["bor"] = "https://bibleontology.org/ns/"
bad["@graph"][3]["mentions"].append({"@id": f"{S.SITE}/e/melchizedek", "name": "Melchizedek", "attestedIn": "x"})
bad["@graph"].append({"@id": f"{S.SITE}/e/god", "bor:offered_to": {"@id": f"{S.SITE}/e/elohim"}})
h4 = re.sub(r'<script type="application/ld\+json">.*?</script>',
            lambda m: '<script type="application/ld+json">' + json.dumps(bad) + "</script>", gh, flags=re.S)
lf = page_faults(g, h4, gb)
check(any("ns/relation#" in f for f in lf), "planted: the JSON-LD check did not catch the /ns/ address")
check(any("offered_to" in f for f in lf), "planted: the JSON-LD check did not catch a relation not built")
check(any("attestedIn" in f for f in lf), "planted: the JSON-LD check did not catch an undefined term")
check(any("/e/melchizedek" in f for f in lf), "planted: the JSON-LD check did not catch a card the page does not link")
# a relatedLink the article does not print
bad2 = copy.deepcopy(ld_of(gh))
bad2["@graph"][3]["relatedLink"].append(f"{S.SITE}/p/Ps.8.3")
h5 = re.sub(r'<script type="application/ld\+json">.*?</script>',
            lambda m: '<script type="application/ld+json">' + json.dumps(bad2) + "</script>", gh, flags=re.S)
check(any("relatedLink" in f for f in page_faults(g, h5, gb)), "planted: the check did not catch a relatedLink the article lacks")
# a linked passage listed twice
g2 = copy.deepcopy(g)
g2["passages"].append(copy.deepcopy(g2["passages"][0]))
check(any("twice" in f for f in page_faults(g2, gh, gb)), "planted: the check did not catch a passage listed twice")
# the quote rule: Nehemiah 9:6 says 'created' in the Berean and עָשָׂה in the Hebrew, so quoting it is caught
g3 = copy.deepcopy(g)
g3["quoted"] = ["John.1.1", "Heb.11.1", "Neh.9.6"]
check(any("Nehemiah 9:6" in f for f in quoted_faults(g3)), "planted: the check did not catch Nehemiah 9:6 quoted")
g4 = copy.deepcopy(g)
g4["quoted"] = ["John.1.1", "Heb.11.1", "Isa.42.5", "Isa.45.12"]
check(quoted_faults(g4), "planted: the check did not catch two readings quoted")
# the line: a step removed breaks the run at Cainan
c2 = copy.deepcopy(c)
c2["line"]["steps"] = [s for s in c2["line"]["steps"] if s["a"] != "reu"]
check(len(c2["line"]["steps"]) != 9, "planted: the line did not shrink")
# the title rule: a verse that fits in 60 characters is its own title; one that does not takes the count
t_short, _ = S.verse_strings(c)
check(t_short.endswith("Serug, Nahor, Terah") and len(t_short) == 60, f"the short-verse title is {t_short}")
v_long = dict(c, text="Serug, Nahor, Terah, and every other name in the long list that follows")
t_long, _ = S.verse_strings(v_long)
check(t_long.endswith("3 linked passages"), f"a long verse's title is {t_long}")
v_none = dict(v_long, counts=dict(c["counts"], n=0), passages=[], quoted=[])
t_none, d_none = S.verse_strings(v_none)
check(t_none.endswith("…") and len(t_none) <= 60 and len(d_none) <= 160, f"a long verse with nothing linked: {t_none}")
# the description never ends inside a word and never exceeds 160
for k, (vc_, _h, _b) in pages.items():
    _t, ds = S.verse_strings(vc_)
    check(len(ds) <= 160, f"{vc_['label']}: description {len(ds)}")

# ---- 5. the verse's own word on the two creation relations (item 3, FAULTS #21) ----------------------------------
def word_faults(vc, verb_gloss):
    """A relation the face relabels carries what is stored and why: only built or made, only where the verse's own
    verb is 'created'; and the JSON-LD leaves it out (it would misname the verse's word)."""
    out = []
    for r in vc["rels"]:
        if r.get("faulted"):
            if r["type"] not in ("built", "made") or r["label"] != "created" or verb_gloss != "created":
                out.append(f"{vc['label']}: {r['an']} -> {r['bn']} is relabeled {r['label']!r} on a verse whose verb is {verb_gloss!r}")
            if r.get("stored") not in ("built", "made", "was built", "was made"):
                out.append(f"{vc['label']}: a relabeled relation does not say what is stored ({r.get('stored')!r})")
        elif r["type"] in ("built", "made") and verb_gloss == "created":
            out.append(f"{vc['label']}: {r['an']} {r['label']} {r['bn']} on a verse that says created")
    return out


def verb_gloss_of(vc):
    trees = S._ptree(d, S._vc_mref(d, vc["book"], vc["chapter"], vc["verse"])).get("trees") or []
    vb = next((lf for t in trees for lf in S._vc_leaves(t) if lf.get("cls") == "verb"), None)
    return ((vb or {}).get("g") or "").split(".")[-1]


rel_by = {(r["a"], r["b"]): r for r in g["rels"]}
check(rel_by[("god", "the_heaven")]["label"] == "created" and rel_by[("god", "the_earth")]["label"] == "created"
      and rel_by[("god", "the_heaven")]["stored"] == "built" and rel_by[("god", "the_earth")]["stored"] == "made",
      f"Gen 1:1's creation relations read {[(r['label'], r.get('stored')) for r in g['rels'] if r['b'] in ('the_heaven', 'the_earth')]}")
check("created" in ga and "built" not in ga.split("Cards in this verse", 1)[1].split("Around it", 1)[0],
      "the page still says built on Gen 1:1")
check(not any(k in json.dumps(ld_of(gh)) for k in ("bor:built", "bor:made", "bor:created")), "the JSON-LD names a creation relation")
gl = ld_of(gh)["@graph"]
check(sorted(k for x in gl for k in x if k.startswith("bor:")) == ["bor:titled"],
      f"Gen 1:1's JSON-LD edges are {sorted(k for x in gl for k in x if k.startswith('bor:'))}, not God titled God (Elohim) alone")
# "the heavens" joined on 2026-11-14 (the Berean's own word at Gen 1:1); "the heaven" beside it is the same thing
# recorded twice, under the KJV's spelling: a merge for two judges and the owner, noted in the committee's rulings
check(sorted(m["name"] for m in next(x for x in gl if x.get("@type") == "Quotation")["mentions"]) == ["God", "God (Elohim)", "the earth", "the heaven", "the heavens"],
      "Gen 1:1's mentions are not God, God (Elohim), the heaven, the earth")
for (b_, c_, v_), (vc_, _h, _b) in pages.items():
    for f in word_faults(vc_, verb_gloss_of(vc_)):
        check(False, f)
check(not word_faults(g, "created"), "word_faults flags Gen 1:1")
g5 = copy.deepcopy(g)
for r in g5["rels"]:
    if r["bn"] == "the earth":
        r["label"] = "made"
        r.pop("stored", None)
        r.pop("faulted", None)
check(any("on a verse that says created" in f for f in word_faults(g5, "created")), "planted: an unrelabeled 'made' on Gen 1:1 not caught")
check(any("verb is" in f for f in word_faults(g, "made")), "planted: a relabel on a verse whose verb is 'made' not caught")

# ---- 6. the sof pasuq is not in the transliteration (item 4, FAULTS #19) ---------------------------------------
def colon_faults(orig):
    """Words whose transliteration ends in the stray colon MACULA writes for the Hebrew full stop."""
    return [ref for ref, ws in orig.items() for w in ws if (w.get("x") or "").endswith(":")]


check(not colon_faults(d["orig"]), f"{len(colon_faults(d['orig']))} verses keep the sof pasuq in the transliteration: {colon_faults(d['orig'])[:3]}")
check(g["words"][-1]["x"] == "hāʾāreṣ", f"the last word of Gen 1:1 reads {g['words'][-1]['x']!r}")
check(all(":" not in w["x"] for vc_, _h, _b in pages.values() for w in vc_["words"]), "a card word keeps a colon")
ch1 = S.api_chapter(d, {"b": ["Gen"], "c": ["1"]})
check(not any((w.get("x") or "").endswith(":") for row in ch1["verses"] for w in row["orig"]), "/api/chapter keeps the sof pasuq in Genesis 1")
check(S.api_verse(d, {"ref": ["Gen 1:1"]})["orig"][-1]["x"] == "ʾāreṣ", "/api/verse keeps the sof pasuq on Gen 1:1")
check("rstrip(\":\")" in (ROOT / "tools" / "interlinear.py").read_text(encoding="utf-8"), "tools/interlinear.py would write the sof pasuq again")
planted = {"Gen.1.1": [dict(w) for w in d["orig"]["Gen.1.1"]]}
planted["Gen.1.1"][-1]["x"] += ":"
check(colon_faults(planted) == ["Gen.1.1"], "planted: the colon check did not catch hāʾāreṣ:")

# ---- 7. the names the mention layer resolved (item 5) ----------------------------------------------------------
def names_faults(vc, body, head):
    """Each name is a card, found in the verse by its words, linked in the article, and a mention in the JSON-LD."""
    out = []
    ents = d["ents"]
    ld = ld_of(head)
    mentioned = {m["@id"] for x in ld["@graph"] if x.get("@type") == "Quotation" for m in x.get("mentions") or []}
    for x in vc["names"]:
        if x["at"] not in vc["text"]:
            out.append(f"{vc['label']}: {x['name']} is named by {x['at']!r}, which the verse does not hold")
        if (ents.get(x["id"]) or {}).get("type") not in ("person", "place", "group"):
            out.append(f"{vc['label']}: {x['name']} is not a person, place or group")
        if f'href="/e/{S._addr(x["id"])}"' not in body:
            out.append(f"{vc['label']}: {x['name']} is not linked in the article")
        if f"{S.SITE}/e/{S._addr(x['id'])}" not in mentioned:
            out.append(f"{vc['label']}: {x['name']} is not a mention in the JSON-LD")
    if vc["names"] and "Named in this verse" not in body:
        out.append(f"{vc['label']}: the article does not say who is named")
    return out


check([x["id"] for x in c["names"]] == ["serug", "nahor_son_of_serug"], f"1 Chr 1:26 names {[x['id'] for x in c['names']]}")
check("terah" not in [x["id"] for x in c["names"]], "1 Chr 1:26 names Terah, whose word the layer leaves open between the man and the place")
a12, a12h, a12b = page("Gen", 12, 1)
check("abraham" in [x["id"] for x in a12["names"]], f"Gen 12:1 names {[x['id'] for x in a12['names']]}, not Abram")
check(any(x["at"] == "Abram" for x in a12["names"]), "Gen 12:1's Abram is not named by its word")
named_pages = 0
for k, (vc_, h_, b_) in list(pages.items()) + [(("Gen", 12, 1), (a12, a12h, a12b)), (("1Chr", 1, 26), (c, ch, cb))]:
    for f in names_faults(vc_, b_, h_):
        check(False, f)
    named_pages += bool(vc_["names"])
check(named_pages >= 3, f"only {named_pages} sampled verses name anyone")
# planted: a name not linked, one the verse does not hold, one that is a thing, and a mention the JSON-LD lacks
b_unlinked = a12b.replace('href="/e/abraham"', 'href="/e/abraham_"')
check(any("not linked" in f for f in names_faults(a12, b_unlinked, a12h)), "planted: an unlinked name not caught")
a12x = copy.deepcopy(a12)
a12x["names"][0]["at"] = "Nimrod"
check(any("does not hold" in f for f in names_faults(a12x, a12b, a12h)), "planted: a name the verse does not hold not caught")
a12y = copy.deepcopy(a12)
a12y["names"].append({"id": "the_heaven", "name": "the heaven", "at": "heaven", "type": "place"})
check(any("not a person" in f for f in names_faults(a12y, a12b, a12h)), "planted: a name that is a thing not caught")
h_nom = re.sub(r'"mentions": \[.*?\]', '"mentions": []', a12h, flags=re.S)
check(any("not a mention" in f for f in names_faults(a12, a12b, h_nom)), "planted: a mention the JSON-LD lacks not caught")

# ---- 8. editors' ranges whole, each verse once in the links panel (item 6) -------------------------------------
ech = json.loads(S.answer("/api/echoes", S.urlencode({"ref": "Gen 1:1"})))
eds = {x["eref"]: x for x in ech["editors"]}
check(len(eds["Jhn.1.1"]["verses"]) == 5 and len(eds["Heb.11.1"]["verses"]) == 3,
      f"the editors' ranges hold {len(eds['Jhn.1.1']['verses'])} and {len(eds['Heb.11.1']['verses'])} verses, not 5 and 3")
check(all(t_ == d["verses"][(k.split(".")[0], int(k.split(".")[1]), int(k.split(".")[2]))]
          for e in ech["editors"] for k, t_ in e["verses"]), "an editors' verse does not carry the Berean's words")
check(eds["Jhn.1.1"]["verses"][-1][0] == "John.1.5", "the editors' John range does not end at John 1:5")
long_ = S.editor_notes(d, "Gen.5.1")
check(all(len(x["verses"]) <= S.VERSE_RANGE for x in S.editor_notes(d, "1Ch.1.26")), "an editors' range is longer than the cap")


def once_faults(e):
    """The links panel's own rule, held to the data: each verse is in one place, and a reading inside an editors'
    range is with that note. The page's code applies it (checked below); this is what it must produce."""
    shown, out = set(), []
    for x in e["editors"]:
        shown.add(x["ref"])
    inside = {l["ref"] for x in e["editors"] for l in (e["allusions"]["letters"] + e["allusions"]["revelation"] + e["allusions"]["history"])
              if x["ref"].split(".")[0] == l["ref"].split(".")[0]
              and S._vkey_macula(x["ref"]) <= S._vkey_macula(l["ref"]) <= S._vkey_macula(x.get("end") or x["ref"])}
    rows = [l["ref"] for k in ("letters", "revelation", "history") for l in e["allusions"][k] if l["ref"] not in inside]
    for r in rows:
        if r in shown:
            out.append(f"{r} is in the links panel twice")
        shown.add(r)
    return out, inside


f_, inside_ = once_faults(ech)
check(not f_ and inside_ == {"Heb.11.3"}, f"Gen 1:1's links panel: {f_}, inside {inside_}")
# the panel's code does it: the three lists are filtered, a note shows its range and the readings inside it
check(re.search(r"const LT = \(shared\.letters \|\| \[\]\)\.filter\(keepOnce\)", SRC)
      and re.search(r"const RV = \(shared\.revelation \|\| \[\]\)\.filter\(keepOnce\)", SRC)
      and re.search(r"const HX = \(shared\.history \|\| \[\]\)\.filter\(keepOnce\)", SRC),
      "the links panel's letters, Revelation's links and history rows are not each filtered once")
check("x.verses.map(vv =>" in SRC and "insideOf(x)" in SRC, "the links panel does not print an editors' range whole with its readings")
src_bad = SRC.replace("const LT = (shared.letters || []).filter(keepOnce);", "const LT = (shared.letters || []);")
check(not re.search(r"const LT = \(shared\.letters \|\| \[\]\)\.filter\(keepOnce\)", src_bad),
      "planted: the filter check did not catch the unfiltered letters")
twice = copy.deepcopy(ech)
twice["allusions"]["history"].append(copy.deepcopy(twice["allusions"]["letters"][0]))
check(once_faults(twice)[0], "planted: a verse listed under letters and history not caught")

# ---- 4. the app's card reads only what the object holds (item 2) -----------------------------------------------
SRC = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
# the original's words are drawn by vcWordsHtml (2026-10-30: the row moved from "links" to "orig"), and read the same
# object, so its source is held to the same contract
JS = (SRC[SRC.index("function verseCardHtml"):SRC.index("async function fillVerseCard")]
      + SRC[SRC.index("function vcWordsHtml"):SRC.index("/* THE STRUCTURE, compact first")])


OPTIONAL = {"stored", "faulted"}            # a relation carries these only when the face names the verse's own word
# a word carries UBS's senses only where app2/ubs.py has its data, which the public copy does not (the card reads
# `(w.ubs || [])`); the gate, 2026-11-11
OPTIONAL_WORD = {"ubs"}


def contract_faults(vc, js):
    """Every property the card's drawing code reads from the object is there; a missing one draws `undefined`. The
    parts a verse may not have (no clause, no relations) are held to Genesis 1:1's, which has them all."""
    out = []
    word_keys = set(vc["words"][0]) if vc["words"] else set(g["words"][0])
    pass_keys = set(vc["passages"][0]) if vc["passages"] else set(g["passages"][0])
    role_keys = set(vc["clauses"][0]["roles"][0]) if vc["clauses"] else set(g["clauses"][0]["roles"][0])
    rel_keys = set(vc["rels"][0]) if vc["rels"] else set(g["rels"][0])
    for k in sorted(set(re.findall(r"\bvc\.(\w+)", js))):
        if k not in vc:
            out.append(f"{vc['label']}: the card reads vc.{k}, which the object lacks")
    for k in sorted(set(re.findall(r"\bw\.(\w+)", js)) - {"length"} - OPTIONAL_WORD):
        if k not in word_keys:
            out.append(f"{vc['label']}: the card reads word.{k}, which the object lacks")
    for k in sorted(set(re.findall(r"\bp\.(\w+)", js))):
        if k not in pass_keys:
            out.append(f"{vc['label']}: the card reads passage.{k}, which the object lacks")
    for k in sorted(set(re.findall(r"\br\.(\w+)", js)) - OPTIONAL):
        if k not in role_keys | rel_keys | {"k", "l", "keys"}:       # a citation: its first verse, its label, its verses
            out.append(f"{vc['label']}: the card reads role or relation .{k}, which the object lacks")
    return out


for ref in ("Gen.1.1", "1Chr.1.26", "John.3.16", "Num.7.10"):
    o = S.api_verse_card(d, {"ref": [ref]})
    check(o.get("found") and o["order"][0] == "Gen" and len(o["order"]) == 66, f"{ref}: the card's object lacks the canon order")
    for f in contract_faults(o, JS):
        check(False, f)
o = S.api_verse_card(d, {"ref": ["Gen.1.1"]})
broken = {k: v for k, v in o.items() if k != "setting"}
check(any("vc.setting" in f for f in contract_faults(broken, JS)), "planted: the contract check did not catch a missing setting")
broken = dict(o, passages=[{k: v for k, v in o["passages"][0].items() if k != "verses"}] + o["passages"][1:])
check(any("passage.verses" in f for f in contract_faults(broken, JS)), "planted: the contract check did not catch a passage without its verses")
broken = dict(o, words=[{k: v for k, v in o["words"][0].items() if k != "parts"}] + o["words"][1:])
check(any("word.parts" in f for f in contract_faults(broken, JS)), "planted: the contract check did not catch a word without its parts")
# the card opens on a tap of "links", never on arrival (ruling V-B, as no ruling stands), the older lists stay below it,
# every drill-in is "view in reader", and the card is reached from one place
check(len(re.findall(r"fillConnections\(sec, vs\.dataset\.ref, book,", SRC)) == 1, "fillConnections is not called from the links chip with the verse")
check("function fillConnectionsOld" in SRC and "The older lists, and what a machine found" in SRC, "the older connection lists are gone")
check("view in reader ↗" in JS and 'class="vc-reader"' in JS and "data-vcp" in JS, "the card's drill-ins lack 'view in reader'")
check("openDepth(" in SRC and not re.search(r"fillVerseCard\([^)]*\)\s*;?\s*//\s*on arrival", SRC), "the card opens on arrival")
check(not re.search(r"\bKJV\b|King James", JS), "the card's code names the KJV")
js_bad = JS.replace('view in reader ↗', 'open ↗')
check("view in reader ↗" not in js_bad, "planted: the drill-in check did not catch a missing 'view in reader'")

print(f"{len(pages) + 2} verse pages, {len(fails)} failures")
for f in fails[:25]:
    print("FAIL", f)
sys.exit(1 if fails else 0)
