"""A word's card and its crawlable page state what the data holds, in order,
with nothing of the KJV in them (2026-10-26).

The word cards are what a search engine reads. They were a lemma and a dozen
verses (490 words) listed book by book in alphabetical order, with the lexicon
entry cut off mid-outline ("... 1a5b)"), the word headed by a participle's
sense ("to love: friend"), no sum of how the Berean renders it, and a
cognate in the Aramaic that did not share the word's consonants. This holds
each of those, and every check is proved by a planted fault: a check that
cannot fail is not a check.

  - verses in canonical order, every use up to WORD_VERSES, then a count of the rest
  - the renderings sum to the uses they were counted over, and are at most the card's own count
  - no KJV/AV rendering in a lexicon entry (the cut itself, and every entry the server holds)
  - the headline sense is the word's main one (never "to love: friend")
  - an Aramaic cognate is shown only when its consonants are the word's own
  - the page holds what the card holds, and every word it links has a page

In process, after the graph loads (~1 minute). Run: python tests/test_word_pages.py"""
import copy
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
sys.path.insert(0, str(ROOT / "src"))
import server as S  # noqa: E402
from bibleont import lemma  # noqa: E402

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


# ---- the checks, each a function so that it can be shown to fail ------------
def verse_keys(body):
    """The canonical keys of the verses a page lists under its verse heading."""
    part = body.split("Its verses, in canonical order", 1)
    if len(part) < 2:
        return []
    return [(S._CANON.get(b, 999), int(c), int(v))
            for b, c, v in re.findall(r'<li><a href="/p/([^."]+)\.(\d+)\.(\d+)">', part[1])]


def out_of_order(body):
    ks = verse_keys(body)
    return [i for i in range(1, len(ks)) if ks[i] < ks[i - 1]]


def renderings_fault(c):
    """Why a card's renderings do not add up, or ''."""
    r = c.get("renderings") or {}
    rows = r.get("rows") or []
    if sum(x["n"] for x in rows) != r.get("total"):
        return f"renderings sum to {sum(x['n'] for x in rows)}, not the stated {r.get('total')}"
    if r.get("total", 0) > (c.get("observations") or 0):
        return f"{r['total']} renderings counted for {c.get('observations')} uses"
    for x in rows:
        if x["refs"] != sorted(x["refs"], key=S._vkey_macula):
            return f"the verses of '{x['gloss']}' are not in canonical order"
    return ""


def kjv_in_entry(c):
    return bool(lemma._KJV.search(c.get("definition") or ""))


# ---- the checks work: planted faults -------------------------------------------
d = S.load()
good = S.word_page("H157")
check(good is not None, "H157 has no page")
body = good[1]
check(not out_of_order(body), "H157's verses are out of canonical order")
check(len(verse_keys(body)) >= 150, f"H157 lists {len(verse_keys(body))} verses")
items = re.findall(r'(<li><a href="/p/[^"]+">.*?</li>)', body.split("Its verses, in canonical order", 1)[1])
planted = body.replace(items[0] + items[1], items[1] + items[0], 1)
check(out_of_order(planted) == [1], "planted fault (two verses swapped) not found")
planted = body.replace(items[3], items[-1], 1)
check(out_of_order(planted), "planted fault (a late verse early) not found")

c157 = S.json.loads(S.answer("/api/sense", S.urlencode({"key": "h157"})))
check(renderings_fault(c157) == "", "H157: " + renderings_fault(c157))
bad = copy.deepcopy(c157)
bad["renderings"]["rows"][0]["n"] += 1
check(renderings_fault(bad), "planted fault (a rendering count raised by one) not found")
bad = copy.deepcopy(c157)
bad["renderings"]["total"] = bad["observations"] + 5
check(renderings_fault(bad), "planted fault (more renderings than uses) not found")
bad = copy.deepcopy(c157)
bad["renderings"]["rows"][0]["refs"].reverse()
check(renderings_fault(bad), "planted fault (a rendering's verses reversed) not found")

check(not kjv_in_entry(c157), "H157's lexicon entry names the KJV")
bad = copy.deepcopy(c157)
# (the Hebrew entries may be withheld, HEBREW_DEFINITIONS_SHOWN: the fault is planted into whatever is there)
bad["definition"] = (bad.get("definition") or "to love") + " · also called Jeiel (KJV: Jehiel)"
check(kjv_in_entry(bad), "planted fault (a KJV rendering in a definition) not found")
check(lemma.scrub_translation("also called Jeiel (Ketiv: Jeuel; KJV: Jehiel) at 1Ch.9.35")
      == "also called Jeiel at 1Ch.9.35", "the cut of a KJV parenthesis")
check(lemma.scrub_translation("a road (AV, the street) here") == "a road here", "the cut of an AV parenthesis")
check(lemma.scrub_translation("also called in KJV: Dodavah; a man") == "", "an entry naming the KJV outside a parenthesis is withheld")
check(lemma.scrub_translation("(RV, the open street)") == "(RV, the open street)", "the RV is left alone")
check(lemma.headline_gloss("to love: friend") == "to love", "headline of a colon gloss")
check(lemma.headline_gloss("God") == "God", "headline of a plain gloss")

# ---- what the server holds -------------------------------------------------------
defs = {k: v["definition"] for k, v in d["lex"].items() if v.get("definition")}
check(not [k for k, t in defs.items() if lemma._KJV.search(t)],
      "lexicon entries naming the KJV: " + ", ".join([k for k, t in defs.items() if lemma._KJV.search(t)][:8]))
colon = [k for k, v in d["lex"].items() if ":" in (v.get("gloss") or "")]
check(not colon, f"{len(colon)} headline glosses still hold a colon: {colon[:6]}")
whole = len(defs) > 5000
print(f"{len(defs):,} lexicon entries held" + ("" if whole else " (the committed extract only: the full lexicon is not on this machine)"))
if whole:
    check(c157.get("short") == "to love", f"H157 is headed {c157.get('short')!r}")
    c430 = S.json.loads(S.answer("/api/sense", S.urlencode({"key": "h430"})))
    check(c430.get("short") == "God", f"H430 is headed {c430.get('short')!r}")
    if S.HEBREW_DEFINITIONS_SHOWN:
        check(len(c157["definition"] or "") > 500 and not c157["definition"].endswith("1a5b)"),
              "H157's lexicon entry is cut off")
        check(c430.get("definition_credit"), "an entry with no credit")
    else:
        # withheld until the owner rules on the Online Bible note (2026-10-26): none may leak
        check(not c157.get("definition") and not c430.get("definition"), "a withheld Hebrew entry is shown")
        g26 = S.json.loads(S.answer("/api/sense", S.urlencode({"key": "g26"})))
        check(len(g26.get("definition") or "") > 100 and g26.get("definition_credit"),
              "the Greek entries went with the Hebrew ones")

# ---- the Aramaic cognate is the word's own consonants ------------------------------
check(S._equivalents(d, "h157")["aramaic"] is None, "H157 is offered the Aramaic יהב")
wrong = 0
for k in d["lemmas"]:
    if k.startswith("h"):
        a = S._equivalents(d, k).get("aramaic")
        if a and S._consonants(d["lemmas"][k]) != S._consonants(a["t"]):
            wrong += 1
check(not wrong, f"{wrong} Aramaic cognates do not share the word's consonants")

# ---- the card's face (the design panel, 2026-10-28) ------------------------------------
# One count per card; what the Berean prints sums to the uses; every relation's
# verse holds the word; a relative's count and headword are its own card's; the
# lexicon line and the printed English are the known answers the panel counted
# by hand. Each check is shown to fail on a planted fault.
def face_faults(c, key):
    """Why a card's face disagrees with itself, or []."""
    F, out = c.get("face") or {}, []
    if not F:
        return ["no face"]
    if F["uses"] != c.get("observations"):
        out.append(f"{F['uses']} uses on the face, {c.get('observations')} in the header")
    if F["uses"] != sum(b[1] for b in F["books"]):
        out.append("the strip does not sum to the uses")
    if F["verses"] != (c.get("occurrences") or {}).get("total"):
        out.append(f"{F['verses']} verses on the face, {(c.get('occurrences') or {}).get('total')} in the list")
    P = F["printed"]
    if sum(r["n"] for r in P["rows"]) + P["none"] + P["unaligned"] != F["uses"]:
        out.append("what the Berean prints does not sum to the uses")
    mine = {r["ref"] for r in S.occurrences(d, key, cap=10 ** 9)[0]}
    off = [r for f in c.get("features") or [] for r in f["refs"] if r not in mine]
    if off:
        out.append(f"relations cite verses without the word: {off[:3]}")
    for k in F.get("recurring") or []:
        if len(S._verses_of(d).get(k["key"], ())) > len(d["orig"]) / 20:
            out.append(f"{k['lemma']} recurs everywhere and is listed as recurring here")
    return out


FACE = {k: S.json.loads(S.answer("/api/sense", S.urlencode({"key": k})))
        for k in ("g2411", "g3485", "g2417", "h1004", "h1964", "h157")}
for k, c in FACE.items():
    for f in face_faults(c, k):
        fails.append(f"{k}: {f}")
g2411 = FACE["g2411"]
check(g2411["face"]["uses"] == 71 and g2411["face"]["verses"] == 67, "G2411: not 71 uses in 67 verses")
pr = {r["text"]: r["n"] for r in g2411["face"]["printed"]["rows"]}
if whole:       # which number owns ἱερόν's "temple courts" is the lexicon's headword (2026-11-01: 21 in the public copy)
    check(pr.get("temple courts", 0) >= 30, f"G2411: the Berean's \"temple courts\" counted {pr.get('temple courts')}")
if whole:       # the lexicon lines need the full lexicon, which the public copy does not carry
    check("as distinct from" in ((g2411["face"]["lexicon"] or {}).get("quote") or ""),
          "G2411: the lexicon line is not the distinction")
    check("temple building proper" in ((FACE["g3485"]["face"]["lexicon"] or {}).get("quote") or ""),
          "G3485: the lexicon line is not the building proper")
fam = {x["key"]: x for x in FACE["g2417"].get("family") or []}
nfc = lambda s: S.unicodedata.normalize("NFC", s or "")  # noqa: E731  (the lexicon's accents are composed differently)
check(fam.get("g2411", {}).get("uses") == 71, f"G2417's family gives G2411 as {fam.get('g2411')}")
if whole:       # the lemma ἱερόν (not the adjective's ἱερός) is the lexicon's headword
    check(nfc(fam.get("g2411", {}).get("lemma")) == nfc("ἱερόν"), f"G2417's family gives G2411 as {fam.get('g2411')}")
check([r for f in g2411["features"] for r in f["refs"] if r == "Luk.2.37"] and
      not [r for f in g2411["features"] for r in f["refs"] if r == "Luk.2.36"], "G2411: Anna's verse is not Luke 2:37")
# planted: each fault the checks exist for
bad = copy.deepcopy(g2411); bad["observations"] += 1
check(face_faults(bad, "g2411"), "planted fault (a second count in the header) not found")
bad = copy.deepcopy(g2411); bad["face"]["printed"]["rows"][0]["n"] += 1
check(face_faults(bad, "g2411"), "planted fault (a printed count raised by one) not found")
bad = copy.deepcopy(g2411); bad["features"][0]["refs"] = ["Luk.2.36"]
check(face_faults(bad, "g2411"), "planted fault (a relation a verse early) not found")
bad = copy.deepcopy(g2411); bad["face"]["recurring"] = [{"key": "g846", "lemma": "αὐτός"}]
check(face_faults(bad, "g2411"), "planted fault (αὐτός listed as recurring) not found")
print(f"{len(FACE)} card faces checked")


# ---- the Septuagint's chi and xi (FAULTS #17, 2026-10-28) ------------------------------
# MACULA's Septuagint column swaps χ and ξ in some forms, both ways; a card prints the form corrected only where the
# corrected form is a Greek word the evidence names, never blindly: ψυξή must come out ψυχή, ἔξω must stay ἔξω.
def lxx_faults():
    out = []
    said = lambda k: [S.unicodedata.normalize("NFC", x["word"]) for x in S.lxx_of(d, k)]  # noqa: E731  (oxia as tonos)
    if not said("h5315") or any("ξ" in w for w in said("h5315")) or "ψυχή" not in said("h5315"):
        out.append(f"h5315 prints {said('h5315')}, not ψυχή")
    if not said("h7225") or not said("h7225")[0].startswith("ἀρχ"):
        out.append(f"h7225 prints {said('h7225')}, not ἀρχὴ first")
    if not said("h2351") or said("h2351")[0] != "ἔξω":
        out.append(f"h2351 (outside) prints {said('h2351')}, not ἔξω")
    if not said("h3004") or said("h3004")[2] != "ξηρά":
        out.append(f"h3004 (dry land) prints {said('h3004')}, not ξηρά")
    for k, w in (("h2351", "ἔξω"), ("h3004", "ξηρά"), ("h1", "ἔξω"), ("h1", "ξηρά"), ("h5315", "ἔχω")):
        if S._lxx_spell(d, k, w) != w:
            out.append(f"{w} under {k}, a word as written, was printed {S._lxx_spell(d, k, w)}")
    # the person card's name line, by the same rule: Serug's σερουξ is σερουχ, Arphaxad's αρφαχαδ is αρφαξαδ
    # (Enoch's card stands on the Greek Ἐνώχ, g1802, and has no Septuagint line)
    for eid, want in (("serug", "σερουχ"), ("arphaxad", "αρφαξαδ")):
        pe = [S.unicodedata.normalize("NFC", x)
              for x in (S.api_entity(d, {"id": [eid]}).get("original") or {}).get("lxx") or []]
        if want not in pe:
            out.append(f"{eid}'s person card prints the Septuagint's name as {pe}, not {want}")
    if whole and not said("h3722")[0].startswith("ἐξιλάσ"):
        out.append(f"h3722 prints {said('h3722')}, not ἐξιλάσεται")
    for k in ("h5315", "h7225", "h3722", "h2351", "h3004", "h1004", "h4480", "h3808"):
        for x in S.lxx_of(d, k):
            if x.get("raw") and x["raw"].translate(S._CHI_XI) != x["word"]:
                out.append(f"{k}: {x['raw']} printed {x['word']}, more than χ and ξ changed")
    return out


for f in lxx_faults():
    fails.append(f"Septuagint χ/ξ: {f}")
psy = S.json.loads(S.answer("/api/sense", S.urlencode({"key": "h5315"})))
check([S.unicodedata.normalize("NFC", x["word"]) for x in psy["lxx"]][:1] == ["ψυχή"] and psy["equiv"]["greek"][0].get("key") == "g5590"
      and S.unicodedata.normalize("NFC", psy["lxx"][0].get("raw") or "") == "ψυξή", f"/api/sense h5315: lxx {psy['lxx'][:1]}, equiv {psy['equiv']['greek'][:1]}")
# planted: the column printed as written (the fault), and a blind fold (the fault the rule guards against)
real = S._lxx_fix
S._lxx_fix = lambda raw, ok: raw if ok(raw) else None
planted = lxx_faults()
check(any("ψυχή" in f for f in planted), "planted fault (ψυξή printed as written) not found")
check(any("serug" in f for f in planted), "planted fault (Serug's name line as written, σερουξ) not found")
S._lxx_fix = lambda raw, ok: raw.translate(S._CHI_XI)
check(any("ἔξω" in f and "printed ἔχω" in f for f in lxx_faults()), "planted fault (ἔξω folded to ἔχω) not found")
S._lxx_fix = real
check(not lxx_faults(), "the χ/ξ rule did not come back")
print("Septuagint χ/ξ: ψυξή printed ψυχή, ἔξω kept, Serug σερουχ on his card, 3 planted faults caught")

# ---- every verse, one tap under the strip (the owner, 2026-10-28) ----------------------
# A page of 150 from /api/word-verses: together the pages are the card's verses, once each and in order (no list
# stops at 150); each mark is the Berean's English for the word as the face counts it, so the marks and the "no
# separate word" notes add up to the uses the face prints.
def verse_list_faults(key, pages, F):
    out = []
    refs = [r["ref"] for p in pages for r in p["rows"]]
    if refs != sorted(S._verses_of(d).get(key, ()), key=S._vkey_macula):
        out.append(f"{key}: the pages hold {len(refs)} verses, not the card's {F['verses']} in order")
    if pages and pages[0]["pages"] != -(-F["verses"] // pages[0]["per"]):
        out.append(f"{key}: {pages[0]['pages']} pages for {F['verses']} verses")
    printed = {r["text"].lower() for r in F["printed"]["rows"]}
    marked = none = 0
    for p in pages:
        for r in p["rows"]:
            for s, e in r["marks"]:
                if not 0 <= s < e <= len(r["text"]) or r["text"][s:e].lower() not in printed:
                    out.append(f"{key} {r['ref']}: marks '{r['text'][s:e]}', not a rendering the face counts")
            marked += len(r["marks"])
            none += r["none"]
    want = F["uses"] - F["printed"]["unaligned"]
    if marked + none != want:
        out.append(f"{key}: {marked} marked and {none} unprinted, not the face's {want} aligned uses")
    return out


VPAGES = {}
for k in ("g2411", "h1004", "h5315"):
    first = S.json.loads(S.answer("/api/word-verses", S.urlencode({"key": k, "page": 0})))
    VPAGES[k] = [first] + [S.json.loads(S.answer("/api/word-verses", S.urlencode({"key": k, "page": i})))
                           for i in range(1, first["pages"])]
    F_ = FACE[k]["face"] if k in FACE else S.json.loads(S.answer("/api/sense", S.urlencode({"key": k})))["face"]
    for f in verse_list_faults(k, VPAGES[k], F_):
        fails.append(f)
check(len(VPAGES["h1004"]) > 1 and all(len(p["rows"]) == 150 for p in VPAGES["h1004"][:-1]),
      f"h1004: pages of {[len(p['rows']) for p in VPAGES['h1004']]}, not 150 each")
check(VPAGES["g2411"][0]["rows"][0]["ref"] == "Mat.4.5" and VPAGES["g2411"][0]["rows"][0]["forms"]
      and "temple" in [VPAGES["g2411"][0]["rows"][0]["text"][s:e] for s, e in VPAGES["g2411"][0]["rows"][0]["marks"]],
      "G2411: Matthew 4:5 does not open the list with its form and \"temple\" marked")
# planted: a verse dropped from a page, a mark a word off, a "no separate word" lost
bad = copy.deepcopy(VPAGES["h1004"]); bad[3]["rows"].pop(7)
check(verse_list_faults("h1004", bad, FACE["h1004"]["face"]), "planted fault (a verse dropped from page 4) not found")
bad = copy.deepcopy(VPAGES["g2411"]); r_ = next(r for r in bad[0]["rows"] if r["marks"])
r_["marks"][0] = [r_["marks"][0][0] + 4, r_["marks"][0][1] + 4]
check(verse_list_faults("g2411", bad, FACE["g2411"]["face"]), "planted fault (a mark four letters off) not found")
bad = copy.deepcopy(VPAGES["g2411"]); next(r for r in bad[0]["rows"] if r["none"])["none"] = 0
check(verse_list_faults("g2411", bad, FACE["g2411"]["face"]), "planted fault (an unprinted use lost) not found")
print(f"every verse: {sum(len(p['rows']) for v in VPAGES.values() for p in v)} verses on "
      f"{sum(len(v) for v in VPAGES.values())} pages, 3 planted faults caught")

# ---- the pages -----------------------------------------------------------------------
words = {"H157": 2500, "G26": 1800, "H430": 2500, "G25": 1800}      # a floor of words, from the measured pages
sample = list(words) + ["H3052", "H2942", "G5547", "G2424", "H3068", "H6376", "H6213"]
once = next((k for k in sorted(d["lex"]) if re.match(r"^h\d+$", k) and S._uses(d, k) == 1
             and d["occ"].get(k)), None)
if once:
    sample.append(once.upper())
pages = links = 0
for spelt in sample:
    got = S.word_page(spelt)
    if not got:
        fails.append(f"{spelt} has no page")
        continue
    pages += 1
    head, pg, addr = got
    text = re.sub(r"<[^>]+>", " ", pg)
    c = S.json.loads(S.answer("/api/sense", S.urlencode({"key": spelt.lower()})))
    check(not out_of_order(pg), f"{spelt}: verses out of canonical order")
    check(renderings_fault(c) == "", f"{spelt}: {renderings_fault(c)}")
    check(not kjv_in_entry(c), f"{spelt}: the entry names the KJV")
    check(not re.search(r"\b(KJV|AV)\b", text), f"{spelt}: the page names the KJV")
    # a Hebrew word used once holds little but its entry: with the Hebrew entries withheld its page is thinner, and
    # the sitemap leaves such pages out by its own threshold
    floor = words.get(spelt, 150 if (S.HEBREW_DEFINITIONS_SHOWN or not spelt.startswith("H")) else 100)
    check(len(text.split()) >= floor, f"{spelt}: only {len(text.split())} words")
    check("application/ld+json" in head and '"DefinedTerm"' in head, f"{spelt}: no DefinedTerm")
    check(f"used {S.json.loads(S.answer('/api/sense', S.urlencode({'key': spelt.lower()})))['observations']:,} time" in head
          or "used 1 time" in head, f"{spelt}: the title does not say how often it occurs")
    n_uses = len(verse_keys(pg))
    n_verses = len({r["ref"] for r in S.occurrences(d, spelt.lower(), cap=10 ** 9)[0]})
    if n_verses <= S.WORD_VERSES:
        check(n_uses >= n_verses - 3, f"{spelt}: lists {n_uses} of {n_verses} verses")      # a verse the site lacks is not linked
    else:
        check(n_uses == S.WORD_VERSES, f"{spelt}: lists {n_uses}, not {S.WORD_VERSES}, of {n_verses}")
        check("more, every one in" in pg, f"{spelt}: does not say how many more")
    for href in set(re.findall(r'href="(/word/[HG]\d+)"', pg)):
        links += 1
        if href != f"/word/{addr}" and S.word_page(href[6:]) is None:
            fails.append(f"{spelt}: links {href}, which has no page")
check(pages == len(sample), f"{pages} of {len(sample)} sampled words have a page")

print(f"{pages} word pages checked; {links} links to other words")
for f in fails[:25]:
    print("FAIL", f)
print("ok" if not fails else f"{len(fails)} failures")
sys.exit(1 if fails else 0)
