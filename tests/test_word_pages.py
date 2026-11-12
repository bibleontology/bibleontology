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
# the full Greek lexicon (STEP's, fetched): counted in Greek alone, since Strong's Hebrew (8,674 entries, committed)
# passed a count of both in the public copy that had no Greek lexicon (the gate, 2026-11-11)
whole = sum(1 for k in defs if k[:1] == "g") > 3000
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
        # the abridged BDB is withheld until the owner rules on the Online Bible note (2026-10-26): none may leak.
        # Since 2026-11-07 a Hebrew entry is Strong's own dictionary instead (tests/test_strongs_hebrew.py), so the
        # entry must be exactly Strong's, credited as Strong's, and never the BDB's outline
        sh = S.strongs_hebrew()
        for c_, k_ in ((c157, "h157"), (c430, "h430")):
            check((c_.get("definition") or "").startswith(sh[k_]["definition"]) and "1a)" not in (c_.get("definition") or ""),
                  f"{k_}: the Hebrew entry is not Strong's: {(c_.get('definition') or '')[:60]!r}")
            check("Strong's Hebrew Dictionary" in (c_.get("definition_credit") or ""), f"{k_}: not credited as Strong's")
        g26 = S.json.loads(S.answer("/api/sense", S.urlencode({"key": "g26"})))
        check(len(g26.get("definition") or "") > 100 and g26.get("definition_credit"),
              "the Greek entries went with the Hebrew ones")
    # G2411, THE TEMPLE, HEADED AS THE NOUN (2026-10-27 the headword; 2026-11-07 the rest, Doug: "make sure that
    # there isn't still a real or perceived G2411 headword issue"). ἱερόν leads on the card and its page, ἱερός
    # (G2413's adjective, which MACULA files both under) is named beside it, the page says which of Abbott-Smith's
    # senses are the noun's, and STEP's mis-tagged "I Esd.-4 Mac." no longer reads as Esther 1:1-58
    g2411 = S.json.loads(S.answer("/api/sense", S.urlencode({"key": "g2411"})))
    pg = S.word_page("G2411")
    check(g2411.get("lemma") == "ἱερόν" and (g2411.get("lemma_also") or {}).get("form") == "ἱερός",
          f"G2411 is headed {g2411.get('lemma')!r}, beside {(g2411.get('lemma_also') or {}).get('form')!r}")
    check(pg and pg[0].count("<title>ἱερόν ") == 1, "G2411's page is not titled ἱερόν")
    check(pg and "The senses that cite this word" in pg[1], "G2411's page does not say which senses are the noun's")
    # A LETTERED CODE THAT IS ANOTHER WORD KEEPS ITS OWN KEY (2026-11-07, A.48 audit round 1): the Aramaic article
    # (0001b) was counted as H1 "father" (1,314 verses, "O king" among its renderings), "and" (2050b) under H2050, a
    # verb used once, "like" and suffixes under Jetheth (H3509). Variants Strong's merges stay merged
    vo = S._verses_of(d)
    check(len(vo.get("h1", ())) < 1100 and "Dan.2.29" not in vo.get("h1", ()), f"H1 holds {len(vo.get('h1', ()))} verses")
    check(len(vo.get("h2050", ())) < 10 and len(vo.get("h3509", ())) < 10, "H2050 or H3509 still holds a prefix's or suffix's uses")
    check({"h1b", "h2050b", "h3509a"} <= S._SPLIT_CODES, "the article, 'and' or 'like' is not split off")
    check(not {"h1931a", "h7451b", "h859a"} & S._SPLIT_CODES, "a variant Strong's merges (הִיא, רָעָה, אַתֶּם) was split")
    saved = S._SPLIT_CODES
    S._SPLIT_CODES = set()
    try:
        check(S.sense_key("hebrew", "0001b") == "h1", "planted: the collapse (no split codes) was not reproduced")
    finally:
        S._SPLIT_CODES = saved
    check(S.sense_key("hebrew", "0001b") == "h1b", "the Aramaic article still keys as H1")
    # A BASE THE SPLIT-OFF CODE OUTNUMBERS KEEPS NOTHING OF ITS DATA (2026-11-10, audit round 7): Dothan read "and"
    # with the Greek καί beside it, Jetheth "like", light and wailing the article's Septuagint and role rows. H1
    # "father" outnumbers its split-off article and keeps πατήρ
    for k, want_g in (("h1886", "Dothan"), ("h3509", "Jetheth"), ("h3641", "Calneh")):
        c = S.api_sense(d, {"key": [k]})
        check((c.get("gloss") or "").startswith(want_g) and not c.get("lxx"),
              f"{k.upper()} reads {c.get('gloss')!r} with {len(c.get('lxx') or [])} Septuagint rows")
    check(S.api_sense(d, {"key": ["h1"]}).get("lxx"), "H1 father lost its Septuagint rows")
    # A NAME SAYS WHAT IT NAMES AND LINKS TO ITS CARD (Doug, 2026-11-10, on Dothan: "not immediately clear to me that
    # it is a town/place ... the word is not connected to a place (meaning) card"), on the card, the served page and
    # the Navigator, both ways; a word that is not a name says nothing of the kind
    def name_faults():
        f = []
        for k, kind, eid in (("h1886", "a place", "dothan"), ("h3641", "a place", "calneh"),
                             ("g2491", "a man's name", "john_the_baptist")):
            c = S.api_sense(d, {"key": [k]})
            if c.get("name_kind") != kind or eid not in [x["id"] for x in c.get("names") or []]:
                f.append(f"{k.upper()} reads {c.get('name_kind')!r}, names {[x['id'] for x in c.get('names') or []]}")
            pg = S.word_page(k.upper())
            if not pg or f'href="/e/{S._addr(eid)}"' not in pg[1]:
                f.append(f"{k.upper()}'s page does not link {eid}")
        if not any(e["target"] == "dothan" for e in S.api_graph(d, {"id": ["word:h1886"]})["edges"]):
            f.append("the Navigator does not draw Dothan from its word")
        if not any(e["source"] == "word:h1886" for e in S.api_graph(d, {"id": ["dothan"]})["edges"]):
            f.append("the Navigator does not draw Dothan's word from its card")
        if S.api_sense(d, {"key": ["g3485"]}).get("name_kind"):
            f.append("ναός is called a name")
        # the judged links (ontology/word-name-links.json): Meshach is Mishael; Nebat, Jeroboam's father, links to no
        # one (the Mac took him for his son; rejected in the provenance)
        if "mishael_daniels_friend" not in [x["id"] for x in S.names_of_word(d, "h4335")]:
            f.append("Meshach does not link Mishael")
        if S.names_of_word(d, "h5028"):
            f.append(f"Nebat links {[x['id'] for x in S.names_of_word(d, 'h5028')]}")
        return f
    for f in name_faults():
        check(False, f)
    # A VERB USED ONLY IN ITS DERIVED STEMS IS HEADED BY ITS ROOT FORM, AND A NAME'S SEPTUAGINT ROW IS THE NAME
    # (audit round 5): כָּפַר not its Piel כִּפֶּר; Eliam without αξιτοφελ (Ahithophel, the next name in 2 Sam 23:34);
    # Egypt keeps Αἴγυπτος, a row seen more than once
    nf = lambda s: S.unicodedata.normalize("NFC", s or "")  # noqa: E731
    c = S.api_sense(d, {"key": ["h3722"]})
    check(nf(c.get("lemma")) == nf("כָּפַר") and nf((c.get("lemma_also") or {}).get("form")) == nf("כִּפֶּר"),
          f"H3722 is headed {c.get('lemma')!r} beside {(c.get('lemma_also') or {}).get('form')!r}")
    lx = lambda k: [nf(x["word"]) for x in S.lxx_of(d, k)]  # noqa: E731
    check("αξιτοφελ" not in lx("h463") and "ελιαβ" in lx("h463"), f"Eliam's Septuagint rows: {lx('h463')}")
    check(any(w.startswith(nf("αἰγύπτ")) for w in lx("h4714")), f"Egypt lost Αἴγυπτος: {lx('h4714')}")
    saved_k = S.name_kind
    S.name_kind = lambda d_, k: None
    try:   # planted: without the name rule, Ahithophel is Eliam's Greek again
        check("αξιτοφελ" in lx("h463"), "planted: αξιτοφελ under Eliam was not reproduced")
    finally:
        S.name_kind = saved_k
    # SLIPS IN THE FREE LEXICONS (audit round 6): each repair took (its right text is in the entry, its wrong gone);
    # a repair whose wrong text is not in the source would do nothing, silently
    for k, pairs in S.SOURCE_SLIPS.items():
        t = (d["lex"].get(k) or {}).get("definition") or ""
        for wrong, right in pairs:
            check(right in t and wrong not in t, f"{k.upper()}: the slip {wrong!r} -> {right!r} did not take")
    check(S._source_slips("g1715", "ὁμολουεῖν") == "ὁμολογεῖν" and S._source_slips("g26", "ὁμολουεῖν") == "ὁμολουεῖν",
          "a slip repaired on the wrong entry, or not on its own")
    saved_n, saved_c = S._WORD_NAMES, S._CARD_WORDS
    S._WORD_NAMES, S._CARD_WORDS = {"h1886": []}, None
    try:   # planted: the index without Dothan's link (it had no name-map entry), as before 2026-11-10
        check(any("H1886" in f for f in name_faults()), "planted: Dothan without its place card was not caught")
    finally:
        S._WORD_NAMES, S._CARD_WORDS = saved_n, None
    saved = S._clean_split_base
    S._clean_split_base = lambda d, out: None
    try:   # planted: the cleanup off, Dothan reads the merged code's word again
        check(not (S.api_sense(d, {"key": ["h1886"]}).get("gloss") or "").startswith("Dothan") or
              S.api_sense(d, {"key": ["h1886"]}).get("lxx"), "planted: Dothan without the cleanup was not reproduced")
    finally:
        S._clean_split_base = saved
    # A FORM STRONG'S NUMBERS APART SAYS WHERE ITS USES ARE COUNTED (2026-11-07, audit round 1): ἦν, ἐστί, εἶναι
    # and εἶπον said "used 0 times" over UBS senses with 94 verses. And a spelling that is only accentless-equal is
    # not the word: ἦ "surely" is not the article, ὅρος "boundary" is not ὄρος "mountain"
    want = {"g2258": "g1510", "g2076": "g1510", "g1511": "g1510", "g2036": "g3004", "g2400": "g3708", "h1524a": "h1524"}
    for k, to in want.items():
        cu = S.api_sense(d, {"key": [k]}).get("counted_under") or {}
        check(cu.get("key") == to, f"{k.upper()} is not counted under {to.upper()}: {cu}")
    check((S.counted_under(d, "g2076") or {}).get("n", 0) > 800, "ἐστί does not count its ἐστίν")
    for k in ("g2229", "g1488", "g5607", "g8554", "g6383"):
        cu = S.counted_under(d, k)
        check(not cu or cu["key"] == "g1510", f"{k.upper()} is counted under another word's spelling: {cu}")
    pg2258 = S.word_page("G2258")
    check(pg2258 and "used 0 times" not in pg2258[0] and 'href="/word/G1510"' in pg2258[1]
          and "counts its uses under" in pg2258[1], "G2258's page does not say its uses are counted under εἰμί")
    saved = S._FORMS
    S._FORMS = S.collections.defaultdict(S.collections.Counter, {"η": S.collections.Counter({"g3588": 9})})
    try:   # planted: the accentless match without the entry's word, ἦ under the article
        defn = d["lex"]["g2229"]["definition"]
        d["lex"]["g2229"]["definition"] = "ὁ, ἡ, τό, the article"
        check((S.counted_under(d, "g2229") or {}).get("key") == "g3588", "planted: ἦ under the article was not reproduced")
    finally:
        d["lex"]["g2229"]["definition"] = defn
        S._FORMS = saved
    # THE TRANSLITERATION IS THE HEADWORD'S (audit round 1): not an inflected use's (אָמַר "yyōʾmer"), the pausal
    # form's (אֶרֶץ "ʾāreṣ"), Hebrew letters (אָב "אב"), or STEP's Greek ("uhios")
    tr = {"g5207": "huios", "h559": "ʾāmar", "h776": "ʾereṣ", "h1": "ʾāḇ", "h160": "ʾahăḇāh"}
    for k, x in tr.items():
        got = S.api_sense(d, {"key": [k]}).get("translit")
        check(got == x, f"{k.upper()} is transliterated {got!r}, not {x!r}")
    hebrew_x = [k for k in list(vo)[:4000] if k[:1] == "h"
                and re.search(r"[֐-׿]", S._head(d, k, d["lemmas"].get(k), None)[1] or "")]
    check(not hebrew_x, f"Hebrew letters in the transliteration of {hebrew_x[:5]}")
    # THE PULL-QUOTE IS A WHOLE CLAUSE (audit round 1, MISLEADING 6): "of the faculty of speech, Luk.24" (cut at
    # the colon inside Luk.24:19), an unclosed parenthesis under υἱός, "(DCG, ii, 330f.)", ", 7:6, ."
    quotes = {k: (S.lexicon_senses(d, k, vo[k]) or {}).get("quote") for k in vo if k[:1] == "g"}
    quotes = {k: q for k, q in quotes.items() if q}
    def is_torn(q):
        return q.count("(") != q.count(")") or bool(
            re.search(r"\b[1-3]?[A-Z][a-z]{1,3}\.\d+|\d+:\d+|,\s*\.|·|,\s*\d+\s*$|\b(?:MM|WH|DCG)\b", q))
    torn = [k for k, q in quotes.items() if is_torn(q)]
    check(len(quotes) > 800 and not torn, f"{len(torn)} of {len(quotes)} pull-quotes torn: {torn[:5]}")
    check("Luk" not in quotes.get("g3056", "") and "ναός" in S.unicodedata.normalize("NFC", quotes.get("g2411", "")),
          f"G3056 {quotes.get('g3056')!r} / G2411 {quotes.get('g2411')!r}")
    check(S._quote_clean("a measure of length = 600 Greek feet") == "a measure of length = 600 Greek feet",
          "a number the sense states was cut")
    for planted in ("of the faculty of speech, Luk.24", "(a usage mainly due to translation", "peace (DCG, ii, 330f.)"):
        check(is_torn(planted), f"planted: the torn quote {planted!r} was not caught")
    # WHAT THE TEXT DOES WITH אֱלָהּ READS AS ENGLISH (audit round 1, MISLEADING 7): "ables", "sents", "caused
    # todwell", "brought toan end", and τοῦ among its Septuagint words
    rows = {f["with"] for f in S.api_sense(d, {"key": ["h426"]}).get("features") or []}
    check({"is able", "sent", "caused to dwell", "brought to an end"} <= rows and not rows & {"ables", "sents", "τοῦ"},
          f"H426's rows: {sorted(rows)}")
    # ...and every card's role rows in plain English (2026-11-09: "is what will justified", "is what someone obey")
    bad_rows = []
    for k_ in ("g4561", "g1343", "g3341", "g3485", "h157", "g26"):
        for f in S.api_sense(d, {"key": [k_]}).get("features") or []:
            w_ = f["with"].split(" ")
            adjective = len(w_) == 2 and w_[0] == "is"          # "is able", "is diligent": an adjective keeps its "is"
            if f["kind"] in ("subjof", "objof") and (f["says"].startswith("is what")
                                                     or (w_[0].lower() in S._VERB_AUX and not adjective)):
                bad_rows.append((k_, f["says"], f["with"]))
    check(not bad_rows, f"role rows not in plain English: {bad_rows[:5]}")
    check(not [f for k_ in ("g1722", "g2532") for f in S.api_sense(d, {"key": [k_]}).get("features") or []
               if f["kind"] in ("subjof", "objof", "coord")], "a function word (ἐν, καί) still has role rows")
    check(S._verb_plain("someone i rejoice") == "rejoice" and S._verb_plain("will justified") == "justified",
          "the verb cleaner")
    check(S._verb_plain("there would have saved") != "there would have saved", "planted: an auxiliary left on")
    check(S.gloss_repair("put ~ todeath") == "put ~ to death" and S.gloss_repair("a towel") == "a towel",
          "the run-together 'to' is not repaired, or a real to- word was split")
    check(S.gloss_repair("put ~ todeath") != "put ~ todeath", "planted: the unrepaired gloss")
    # ABBOTT-SMITH'S LABEL (c) IS NOT "(with)" (audit round 2): STEP's expansion of his "c." caught the label
    pro = (d["lex"].get("g4396") or {}).get("definition") or ""
    check("__(c)" in pro and "__(with)" not in pro, "G4396's sense label (c) still reads (with)")
    labelled = [k for k, v in d["lex"].items() if "__(b)" in (v.get("definition") or "")
                and re.search(r"__\(b\)(?:(?!__\().)*?__\(with\)", v.get("definition") or "", re.S)]
    check(not labelled, f"{len(labelled)} entries still label a sense (with) after (b): {labelled[:5]}")
    check(re.search(r"__\(b\)(?:(?!__\().)*?__\(with\)", "__(a) x · __(b) y · __(with) of John", re.S),
          "planted: the (with) label was not caught")
    # A FUNCTION WORD KEEPS ITS OWN SMALL WORD (audit round 2): καί printed no "and", ὁ no "the", τίς no "what"
    for k, w in (("g2532", "and"), ("g3588", "the"), ("g5101", "what"), ("g1161", "and"), ("g1722", "in"),
                 ("g1519", "into"), ("g575", "from")):
        top = [r["text"].lower() for r in S.printed_of(d, k, vo[k])["rows"][:3]]
        check(w in top, f"{k.upper()} does not print {w!r} among its top renderings: {top}")
    check(not S._function_word(d, "g3004") and S._function_word(d, "g2532"), "λέγω ('to say') counted as a function word")
    saved_fw = dict(S._FUNCTION_WORDS)
    S._FUNCTION_WORDS["g2532"] = False
    try:   # planted: the small-word rule applied to καί again
        check("and" not in [r["text"].lower() for r in S.printed_of(d, "g2532", vo["g2532"])["rows"][:3]],
              "planted: καί without its exemption still printed 'and'")
    finally:
        S._FUNCTION_WORDS.clear(); S._FUNCTION_WORDS.update(saved_fw)
    # THE WORD AT THE NAVIGATOR'S CENTRE (Doug, 2026-11-08; PRINCIPLES 54): ἀγαπάω's graph is the word, its meaning
    # card and its Hebrew equivalent; a word with no card is not found, not a crash
    g = S.api_graph(d, {"id": ["word:g25"]})
    ids = {n["id"] for n in g.get("nodes") or []}
    check(g.get("center") == "word:g25" and {"love", "word:h157"} <= ids and g.get("policy"),
          f"G25's Navigator graph: {g.get('center')} {sorted(ids)[:8]}")
    check(S.api_graph(d, {"id": ["word:g999999"]}).get("found") is False, "a word with no card did not answer not-found")
    # ...and back: a meaning card's graph carries its original words, under their own legend entry (Doug, 2026-11-09)
    gl = S.api_graph(d, {"id": ["love"]})
    check("word:g26" in {n["id"] for n in gl.get("nodes") or []} and "wording" in (gl.get("categories") or {}),
          "the love card's graph has no way back to ἀγάπη, or no 'Original words' legend entry")
    # EACH FORM WITH ITS PARSING, SUMMING TO THE USES (2026-11-09): ναός's six forms are its 45 uses, ναόν accusative
    pf = S.word_face(d, "g3485").get("parsed") or []
    check(sum(r["n"] for r in pf) == 45 and pf and pf[0]["form"] == "ναόν" and pf[0]["parse"].startswith("accusative"),
          f"ναός's forms: {[(r['form'], r['parse'], r['n']) for r in pf[:3]]}")
    hf = S.word_face(d, "h157").get("parsed") or []
    check(sum(r["n"] for r in hf) == len([1 for r in vo["h157"] for w in d["orig"].get(r, ())
                                           if S.sense_key("hebrew", w.get("s")) == "h157"])
          and not [r for r in hf if any(0x0591 <= ord(ch) <= 0x05AF for ch in r["form"])],
          "אָהֵב's forms do not sum to its uses, or a form kept its cantillation")
    # THE TENS ARE NOT THEIR UNITS: H7970 "thirty" was headed שָׁלֹשׁ "three", as MACULA files it
    for k, head in (("h7970", "שְׁלֹשִׁים"), ("h705", "אַרְבָּעִים"), ("h2572", "חֲמִשִּׁים")):
        c_ = S.api_sense(d, {"key": [k]})
        check(S._pointed(c_.get("lemma")) == S._pointed(head) and (c_.get("lemma_also") or {}).get("source") == "macula",
              f"{k.upper()} is headed {c_.get('lemma')!r}, not {head}")
    tens = S.HEBREW_TENS.pop("h7970")
    try:   # planted: without the list, the unit leads again
        check(S._pointed(S.headwords({"h7970": "שָׁלֹשׁ"}, {}, d["lex"]).get("h7970", {}).get("lemma", "שָׁלֹשׁ"))
              == S._pointed("שָׁלֹשׁ"), "planted: thirty headed by three was not reproduced")
    finally:
        S.HEBREW_TENS["h7970"] = tens
    saved = S._LEMMA_X
    S._LEMMA_X = {("h559", S._pointed("אָמַר")): S.collections.Counter({"yyōʾmer": 3})}
    try:   # planted: an inflected use's transliteration under the headword
        check(S.lemma_translit(d, "h559", "אָמַר", "") == "yyōʾmer", "planted: the inflected transliteration was not reproduced")
    finally:
        S._LEMMA_X = saved
    # in the encoding a keyboard types: STEP's oxia (U+1F79) looked the same and compared unequal
    import unicodedata
    check(unicodedata.normalize("NFC", g2411.get("lemma") or "") == g2411.get("lemma"), "G2411's headword is not NFC")
    check("Est.1:1-58" not in (g2411.get("definition") or "") and "I Esd.–4 Mac." in (g2411.get("definition") or ""),
          "G2411's entry still reads STEP's mis-tag as Esther 1:1-58")

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
