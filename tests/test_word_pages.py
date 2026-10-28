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
