"""The wrong text the Fable audit found still live (docs/review/fable-audit-2026-11-11.md), held as classes.

Each check reads the served page or the card's data the way a reader meets it, and each is proved by a planted fault:

  1. A NAME'S WORD COUNTS ITS OWN USES: a place's "Its name in the original" never carries a merged code's other word
     (Dothan's H1886 printed the Hebrew article's 35,900 uses)
  2. A PASSAGE TOLD AGAIN IS NOT "NO EVIDENCE": an event's suggested passage holding the other side of its told-again
     record carries `told` (the storm's drawer filed Jonah 1 under no evidence while its lead set Jonah's steps beside)
  3. SERVED EVENT PAGES: no "is recounted by" relation; a cut-short telling says how many verses it leaves; the
     Scriptures heading names the tellings where there are several; words the text says are in quotation marks
  4. SERVED PLACE PAGES: at most five visitors inline; no "Every other event" heading with nothing above it; a cited
     range ("2Sam 5:6-9") is in the Verses list
  5. SERVED IMAGE PAGES: a page that lists what the picture stands for never says it "records no key" or "holds no
     explicit key"
  6. DESCRIPTIONS: no doubled full stop inside a closing quote (".”."), no unclosed quotation
  7. NAMES: no "Son And Holy Spirit"; a major theme merged into a concept is named as the theme ("(major theme)")
  8. OBJECT PAGES: no "::", no "1 more cited verses"; the word's verse list says it is the word's

In process, after the graph loads. Run: python tests/test_fable_wrong_text.py"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

fails, plants = [], 0


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg)


def body(eid):
    pg = S.card_page(eid)
    return (pg[0] + pg[1]) if pg else ""


def desc_of(html):
    m = re.search(r'<meta name="description" content="([^"]*)"', html)
    return m.group(1) if m else ""


d = S.load()


# ---- 1. a name's word
def name_faults(names):
    return [f"{w['strong']} prints {w['uses']} uses in {w['verses']} verses" for w in names
            if w["verses"] and w["uses"] > 50 * w["verses"]]


dothan = S.api_entity(d, {"id": ["dothan"]})["plcard"]["names"]
check(not name_faults(dothan), f"Dothan's name: {name_faults(dothan)}")
plants += 1
# the public copy has no full lexicon, so Dothan may carry no name word there: the plant brings its own
plant = dict(dothan[0]) if dothan else {"strong": "H1886", "verses": 2}
check(name_faults([dict(plant, uses=35900)]), "planted: the article's 35,900 uses on Dothan's word not caught")


# ---- 2. told-again passages
def told_faults(eid, book):
    sec = S.event_of(d, eid)["secondary"]
    return [s["label"] for s in sec if s["label"].startswith(book) and "told" not in (s.get("evidence") or [])]


for eid, book in (("event_calming_the_storm", "Jonah"), ("event_feeding_of_the_five_thousand", "2 Kings")):
    check(not told_faults(eid, book), f"{eid}: {told_faults(eid, book)} filed with no evidence")
saved = S._rows
S._rows = lambda p: [] if str(p).endswith("told-again.jsonl") else saved(p)
try:
    plants += 1
    check(told_faults("event_calming_the_storm", "Jonah"), "planted: the storm without its told-again record not caught")
finally:
    S._rows = saved

# ---- 3. served event pages
supper = body("event_last_supper")
check("is recounted by" not in re.sub(r"<script.*?</script>", "", supper, flags=re.S),
      "the Last Supper page prints 'is recounted by'")
check(re.search(r"And \d+ more verses? of this telling", supper), "the Last Supper's cut telling does not say so")
check("quoted and recalled in its 4 tellings" in supper, "the Scriptures heading names one telling over all four")
check(not re.search(r"told <a href=\"/e/the_father_draws_him", supper), "a text object printed without its quotes")
storm = body("event_calming_the_storm")
check("is recounted by" not in re.sub(r"<script.*?</script>", "", storm, flags=re.S), "the storm prints 'is recounted by'")


# ---- 4. served place pages
def place_faults(html):
    f = []
    for li in re.findall(r"Went there or lived there: (.*?)</li>", html):
        if re.sub(r"<details>.*?</details>", "", li, flags=re.S).count('href="/e/') > 5:
            f.append(f"{li.count('href=')} visitors inline")
    if "<h2>Every other event" in html and "<h2>Its story" not in html:
        f.append("'Every other event' with no story above it")
    return f


jer, dot = body("jerusalem"), body("dothan")
check(not place_faults(jer), f"Jerusalem: {place_faults(jer)}")
check(not place_faults(dot), f"Dothan: {place_faults(dot)}")
check("2Sam 5:6-9" in jer, "Jerusalem's Verses drop 2 Sam 5:6-9")
plants += 1
check(place_faults(dot.replace("<h2>Its story, by its relations", "<h2>Every other event whose telling holds")),
      "planted: the old heading not caught")


# ---- 5. served image pages
def image_faults(html):
    text = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    return ("<h2>What it stands for</h2>" in text
            and bool(re.search(r"records no key|holds no explicit key|means in \d+ place", text)))


for eid in ("image_vine", "image_lamp", "image_shepherd"):
    check(not image_faults(body(eid)), f"{eid}: a 'no key' lede above what it stands for")
plants += 1
check(image_faults(body("image_vine").replace("<h2>What it stands for</h2>",
                                              "<h2>What it stands for</h2><p>It records no key for it.</p>")),
      "planted: a no-key lede not caught")


# ---- 6. descriptions
def desc_faults(s):
    f = []
    if re.search(r"\.[”’]\.", s):
        f.append("a doubled full stop")
    if s.count("‘") > s.count("’") or s.count("“") > s.count("”"):
        f.append("an unclosed quotation")
    return f


for eid in ("basin", "ark_of_the_covenant", "event_shipwreck_on_malta", "event_feeding_of_the_five_thousand"):
    ds = desc_of(body(eid))
    check(not desc_faults(ds), f"{eid}'s description: {desc_faults(ds)}: {ds}")
plants += 1
check(desc_faults("Exodus 30:18 (BSB): “...for washing.”."), "planted: a doubled full stop not caught")

# ---- 7. names
check("Son And Holy" not in supper, "'Father, Son And Holy Spirit' on the Last Supper page")
items = [it for g in S.api_entity(d, {"id": ["event_last_supper"]})["groups"] for it in g["items"]
         if it["type"] == "in_theme" and "major theme" in (it.get("label") or "")]
bare = [it["name"] for it in items if "(major theme)" not in it["name"]]
check(items and not bare, f"major themes named as bare concepts: {bare}")


# ---- 8. object pages
def object_faults(html):
    f = []
    if "::</b>" in html:
        f.append("a doubled colon")
    if re.search(r"And 1 more cited verses", html):
        f.append("'1 more cited verses'")
    if "verses that hold its words, in the order" in html:
        f.append("the word's verses called the thing's")
    return f


ark, basin = body("ark_of_the_covenant"), body("basin")
check(not object_faults(ark), f"the ark: {object_faults(ark)}")
check(not object_faults(basin), f"the basin: {object_faults(basin)}")
plants += 1
check(object_faults(ark.replace("Stationed at it:</b>", "Stationed at it::</b>")) or "Stationed at it" not in ark,
      "planted: a doubled colon not caught")

print(f"Fable audit's wrong text: 8 classes checked; {plants} planted faults; {len(fails)} failures")
sys.exit(1 if fails else 0)
