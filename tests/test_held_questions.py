"""Six question cards stay off the site until the owner rules on them. The owner, 2026-10-29: "I told you to hold them
indefinitely until I rule - I am not wanting them on the site right now", and "do what you need to to not turn them on
by accident or put them in the sitemap.xml".

A card is off when its file says `"shown": false`; everything the site serves reads the cards through
`server._questions()`, which keeps only the shown ones (outside the owner's preview, BIBLEONT_SHOW_UNREVIEWED=1). So
this holds, for each held card:
  - its file says `"shown": false` (a draft, a comparison or a `reviewed` flag never turns it on);
  - the site does not serve it: no question page, no entry in /api/questions, no link from any shown question's page
    or any tradition's page, and a HEAD for it answers 404 as its GET does;
  - no sitemap in deploy/www names it;
  - the live unit never sets BIBLEONT_SHOW_UNREVIEWED (the preview switch that shows every card).
Taking a card off HELD is the owner's ruling and nothing else: the line that removes it says when he ruled.

Each check is proven by a planted fault. Run: python -X utf8 tests/test_held_questions.py (~1 minute, loads the graph).
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.pop("BIBLEONT_SHOW_UNREVIEWED", None)
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app2"))
import server as S  # noqa: E402

HELD = ["after-death", "end-times", "hell", "millennium", "rapture", "tithing"]

FAILS = []


def check(ok, msg):
    if not ok:
        FAILS.append(msg)
    return ok


def held_links(text):
    if isinstance(text, (tuple, list)):  # a page builder that returns (html, ...) alongside its page
        text = " ".join(t for t in text if isinstance(t, str))
    return sorted(set(re.findall(r"/questions/(" + "|".join(map(re.escape, HELD)) + r")(?![\w-])", text or "")))


def faults(files, served, sitemaps, unit):
    """every way a held card could reach the site, given the cards on disk, what the server serves, the sitemaps and
    the live unit; returns the list of what is wrong"""
    out = []
    for q in HELD:
        if (q in files or not IN_COPY) and files.get(q, {}).get("shown") is not False:
            out.append(f"{q}: its file does not say \"shown\": false")
        if q in served["questions"]:
            out.append(f"{q}: the server holds it as a shown question")
        if served["pages"].get(q):
            out.append(f"{q}: the server serves its question page")
        if not served["head404"].get(q):
            out.append(f"{q}: a HEAD for /questions/{q} answers 200 (GET answers 404)")
    for where, text in list(served["linking"].items()) + list(sitemaps.items()):
        for q in held_links(text):
            out.append(f"{where} names /questions/{q}")
    if re.search(r"BIBLEONT_SHOW_UNREVIEWED", unit):
        out.append("the live unit sets BIBLEONT_SHOW_UNREVIEWED, which shows every held card")
    return out


files = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "ontology" / "questions").glob("*.json")}
# THE PUBLIC COPY carries no held card's file at all (tools/export_public.py leaves them out), so there an absent file
# is held; here, in the private repository, every one must be on disk (2026-11-01: the gate's KeyError on 'hell').
# Known by the journal, which the copy never carries, so that deleting all six files here cannot pass as the copy
IN_COPY = not (ROOT / "docs" / "JOURNAL.md").exists()
if IN_COPY:
    print("in the public copy: no held card's file is here, which is how the copy holds them")
for q in HELD:
    check(q in files or IN_COPY, f"{q}: no ontology/questions/{q}.json (a held card was renamed or removed: say so to the owner)")

shown = S._questions()
d = S.load()
linking = {"/api/questions": json.dumps(S.api_questions(d, {}), ensure_ascii=False)}
for qid in shown:
    linking[f"/questions/{qid}"] = S.question_page(qid) or ""
    linking[f"/api/question?id={qid}"] = json.dumps(S.api_question(d, {"id": qid}), ensure_ascii=False, default=str)
for slug in S._traditions():
    linking[f"/traditions/{slug}"] = S.traditions_page(slug) or ""
served = {"questions": set(shown), "pages": {q: S.question_page(q) for q in HELD}, "linking": linking,
          "head404": {q: S.head_unshown(f"/questions/{q}") for q in HELD}}
for qid in shown:  # and a shown card's HEAD still answers 200
    check(not S.head_unshown(f"/questions/{qid}"), f"{qid}: shown, but a HEAD for it answers 404")
sitemaps = {f"deploy/www/{p.name}": p.read_text(encoding="utf-8") for p in (ROOT / "deploy" / "www").glob("sitemap*.xml")}
unit = (ROOT / "deploy" / "bibleontology.service").read_text(encoding="utf-8")

check(len(sitemaps) >= 2, "no sitemaps found in deploy/www")
check(len(linking) > 10, f"only {len(linking)} served pages checked")
for f in faults(files, served, sitemaps, unit):
    check(False, f)

# planted faults: each must be caught
planted = 0
caught = 0


def plant(name, **over):
    global planted, caught
    planted += 1
    args = {"files": files, "served": served, "sitemaps": sitemaps, "unit": unit}
    args.update(over)
    if faults(**args):
        caught += 1
    else:
        FAILS.append(f"planted fault not caught: {name}")


plant("hell turned on in its file", files={**files, "hell": {**files.get("hell", {"shown": False}), "shown": True}})
plant("rapture's shown flag removed", files={**files, "rapture": {k: v for k, v in files.get("rapture", {"shown": False}).items() if k != "shown"}})
plant("the server holding tithing as shown", served={**served, "questions": served["questions"] | {"tithing"}})
plant("a page served for millennium", served={**served, "pages": {**served["pages"], "millennium": "<html>"}})
plant("a shown question's page linking to end-times",
      served={**served, "linking": {**linking, "/questions/free-will": '<a href="/questions/end-times">'}})
plant("a tradition's page linking to after-death",
      served={**served, "linking": {**linking, "/traditions/catholic": '<a href="/questions/after-death#reading-1">'}})
plant("hell in the pages sitemap", sitemaps={**sitemaps, "deploy/www/sitemap-pages.xml":
                                             "<url><loc>https://bibleontology.org/questions/hell</loc></url>"})
plant("a HEAD for hell answering 200", served={**served, "head404": {**served["head404"], "hell": False}})
plant("the preview switch in the live unit", unit=unit + "\nEnvironment=BIBLEONT_SHOW_UNREVIEWED=1\n")

for f in FAILS:
    print("FAIL", f)
print(f"held questions: {len(HELD)} held ({', '.join(HELD)}), {len(shown)} shown; {len(linking)} served pages and "
      f"{len(sitemaps)} sitemaps checked; planted faults caught: {caught} of {planted}; {len(FAILS)} failures")
sys.exit(1 if FAILS else 0)
