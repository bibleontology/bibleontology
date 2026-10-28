"""The search's small doors (2026-10-26), each with the fault that would break it.

  1. The words of a verse in any order: "take every thought" finds 2 Cor 10:5
     ("we take captive every thought"); the exact phrase still leads; a single
     word stays with the graph search; the loose rows come after the cards.
  2. The original languages have their own path: H157 / g0026 / G26 open the
     word card (G26 was Genesis 26); Hebrew and Greek script go to word cards
     only, by lemma or by a form as a verse writes it (אָהַבְתָּ, ἠγάπησεν); a
     query that arrives as "???p?" matches nothing.
  3. The words behind the English: at most three rows, after everything else,
     each a word the text renders so in a good share of its uses.
  4. Word cards in the sitemap: every page that passes the threshold is in
     deploy/www/sitemap-words.xml, at the address word_page answers 200 to,
     never a redirecting spelling. Run on a sample of the words (every tenth),
     so it takes about a minute.

Each check is run again with its fault planted (an index that drops a word; G26
read as a reference; a word card left out of the sitemap; a redirecting
address in it), and the test fails if a planted fault is NOT caught.

In process, after the graph loads (~1 minute). Run: python tests/test_search_doors.py"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
sys.path.insert(0, str(ROOT / "tools"))
import server as S  # noqa: E402
import sitemap as SM  # noqa: E402

d = S.load()


def search(q):
    return S.api_search(d, {"q": [q]})["results"]


def passages(rows):
    return [(r["id"], r["chapter"], r["verse"]) for r in rows if r["kind"] == "passage" and r.get("verse")]


def check_verses():
    f = []
    for q in ("take every thought", "thought every captive take", "take every t", "Take, EVERY thought!"):
        if ("2Cor", 10, 5) not in passages(search(q)):
            f.append(f"{q!r} does not find 2 Cor 10:5")
    rows = search("the truth will set you free")
    if passages(rows)[:1] != [("John", 8, 32)]:
        f.append("the exact phrase 'the truth will set you free' does not lead with John 8:32")
    # a word alone stays with the graph search; so does a reference
    for q in ("thought", "captive", "John 3:16", "Gen 1:1"):
        if any(r.get("loose") for r in search(q)):
            f.append(f"{q!r} was given loose verse rows")
    # after the cards
    rows = search("take every thought")
    first = next((i for i, r in enumerate(rows) if r.get("loose")), None)
    if first is None or any(r["kind"] == "entity" for r in rows[first:]):
        f.append("loose verse rows are not after the cards")
    if len([r for r in search("faith works") if r.get("loose")]) > 5:
        f.append("more than five loose verse rows")
    return f


def check_original():
    f = []
    for q, key in (("H157", "h157"), ("h157", "h157"), ("G26", "g26"), ("g0026", "g26"), ("G26a", "g26")):
        rows = search(q)
        if [r["id"] for r in rows] != [key] or rows[0]["kind"] != "sense":
            f.append(f"{q!r} is not the word card {key}: {[(r['kind'], r['id']) for r in rows][:3]}")
    for q, key, first in (("אהב", "h157", True), ("ἀγάπη", "g26", True), ("אָהַבְתָּ", "h157", False),
                          ("ἠγάπησεν", "g25", False), ("ἀγαπῶ", "g25", False)):
        rows = search(q)
        ids = [r["id"] for r in rows]
        if key not in ids or (first and ids[0] != key):
            f.append(f"{q!r} does not reach {key}: {ids[:5]}")
        if any(r["kind"] != "sense" for r in rows):
            f.append(f"{q!r} was matched against more than the word cards")
    if search("???p?") or search("ἀγάπη�"):
        f.append("a query the browser could not encode matched something")
    return f


def check_english():
    f = []
    rows = search("faith without works")
    ids = [r["id"] for r in rows]
    for k in ("g4102", "g2041"):
        if k not in ids:
            f.append(f"'faith without works' does not offer the word behind it: {k}")
    behind = [r for r in rows if "the word behind" in r.get("sub", "")]
    if len(behind) > 3:
        f.append(f"{len(behind)} rows of words behind the English, not three at most")
    if behind and rows[-len(behind):] != behind:
        f.append("the words behind the English are not below everything else")
    for r in behind:
        pct = int(re.search(r"\((\d+)% of its uses\)", r["sub"]).group(1))
        if pct < round(100 * S.RENDER_SHARE):
            f.append(f"{r['id']} is offered at {pct}%")
    return f


# ---- the sitemap, on a sample
keys = sorted(k for k in set(d["lex"]) | set(d["profiles"]) | set(d.get("lemmas") or {}) if re.match(r"^[hg]\d+$", k))
sample = sorted(set(keys[::10]) | {"h157", "g26", "h1254"})
want, thin = set(), 0
for k in sample:
    spelt = k[:1].upper() + k[1:]
    got = S.word_page(spelt)
    if not got:
        continue
    w, v = SM.word_substance(got[1])
    if v >= SM.WORD_MIN_VERSES and w >= SM.WORD_MIN_WORDS and got[2] == spelt:
        want.add(f"/word/{spelt}")
    else:
        thin += 1
listed_all = set(re.findall(r"<loc>" + re.escape(S.SITE) + r"(/word/[^<]+)</loc>",
                            (ROOT / "deploy" / "www" / "sitemap-words.xml").read_text(encoding="utf-8")))


def check_sitemap(listed):
    f = []
    for a in sorted(want - listed)[:5]:
        f.append(f"{a} passes the threshold and is not in sitemap-words.xml")
    for a in sorted(listed):
        m = re.match(r"^/word/([HG]\d+)$", a)
        got = S.word_page(m.group(1)) if m else None
        if not got or got[2] != m.group(1):
            f.append(f"{a} is listed and is not the address word_page answers 200 to")
        elif a in want:
            continue
        else:
            # listed, though not in the sample's passing set: only a fault if it is thin
            w, v = SM.word_substance(got[1])
            if v < SM.WORD_MIN_VERSES or w < SM.WORD_MIN_WORDS:
                f.append(f"{a} is listed and is below the threshold ({v} verses, {w} words)")
        if len(f) > 8:
            break
    return f


fails = []
for name, check in (("verses", check_verses), ("original", check_original), ("english", check_english)):
    got = check()
    fails += [f"{name}: {x}" for x in got]
fails += [f"sitemap: {x}" for x in check_sitemap(listed_all)]
print(f"{len(sample)} words sampled; {len(want)} pass the threshold "
      f"({SM.WORD_MIN_VERSES}+ verses, {SM.WORD_MIN_WORDS}+ words), {thin} do not; "
      f"{len(listed_all)} word cards in sitemap-words.xml")

# ---- the planted faults: each must be CAUGHT
sx = S._search_index(d)
drop = sx["post"].pop("captive")                       # an index that drops a word
try:
    if not check_verses():
        fails.append("planted: an index that drops a word was not caught")
finally:
    sx["post"]["captive"] = drop
real = S._strongs_rows
S._strongs_rows = lambda d_, term: None                # G26 left to the reference parser
try:
    if not [x for x in check_original() if "G26" in x or "g0026" in x or "G26a" in x]:
        fails.append("planted: G26 read as a reference (Genesis 26) was not caught")
finally:
    S._strongs_rows = real
if not check_sitemap(listed_all - {sorted(want)[0]}):  # a passing word card left out
    fails.append("planted: a word card that passes the threshold, missing from the sitemap, was not caught")
if not check_sitemap(listed_all | {"/word/h157"}):     # a redirecting spelling listed
    fails.append("planted: a redirecting address in the sitemap was not caught")
if not check_sitemap(listed_all | {"/word/H00157"}):    # another spelling of a page
    fails.append("planted: a non-canonical spelling in the sitemap was not caught")

for x in fails[:20]:
    print("FAIL", x)
print("ok" if not fails else f"{len(fails)} failures")
sys.exit(1 if fails else 0)
