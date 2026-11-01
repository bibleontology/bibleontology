"""Every question card the site serves takes no side, in its order, its first line, its credit and its page
(the design panel's question card, approved 2026-10-28: docs/review/card-panel-2026-10-28/mockup-free-will.html and
designer-q-notes.md, with the owner's two fixes).

  - the line for the skimmer says the shape and nothing else: "Readers divide here: these are the two pulls, and the
    verses each rests on." where the passed comparison shows the pulls, else "...these are the three readings...",
    the count the card's own; never a summary that takes a side ("Most traditions affirm both")
  - the readings in one order on the app and the page, alphabetical by their names, the same rule on every card
  - each reading's passages in canonical order, five shown first
  - the credit is the card's own: "Held by" is its held_by exactly, until the reader panel has passed the comparison;
    then "Stated by" is the graph's states_reading, only where the reading's held_by names the tradition; a
    document cited under a reading its tradition is not credited with is listed apart (FAULTS #26: Article X under
    free will's third reading, whose held_by lacks the Anglicans)
  - "find your tradition" credits each tradition with exactly the readings the card credits it with
  - the page: its title is the question, its description names the readings the article shows and no verdict, and
    the JSON-LD names the relation vocabulary by the address it answers at (https://bibleontology.org/ns/relation#,
    FAULTS #20), uses only terms schema.org or that vocabulary define, offers every reading as a suggestedAnswer and
    accepts none, and names no verse, tradition or card the page does not link
  - on a phone, one reading at a time with a switcher, never the 3- to 8-column table (the stylesheet's rules)
  - a comparison the panel has not passed (`compare.reviewed` false) is not served: no comparison, no plain names,
    no pulls, credit by held_by; in the preview it is shown and every rule above holds for it

Every check is proved by a planted fault: a check that cannot fail is not a check.

In process, after the graph loads (~1 minute). Run: python tests/test_question_cards.py"""
import copy
import html
import json
import os
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
SHAPE = re.compile(r"Readers divide here: these are the (two pulls|(two|three|four|five|six|seven|eight) readings), "
                   r"and the verses each rests on\.")


# ---- the card ------------------------------------------------------------------------------------------------------
def card_faults(qid, q, raw):
    out = []
    rd = q["readings"]
    m = SHAPE.fullmatch(q.get("shape") or "")
    if not m:
        out.append(f"{qid}: the first line is not the shape alone: {q.get('shape')!r}")
    elif m.group(2) and m.group(2) != S._NUMWORD.get(len(rd)):
        out.append(f"{qid}: the first line counts {m.group(2)} readings; the card has {len(rd)}")
    elif m.group(1) == "two pulls" and not (q.get("compare") or {}).get("pulls"):
        out.append(f"{qid}: the first line names two pulls the card does not show")
    names = [(r.get("name") or r.get("label") or "").lower() for r in rd]
    if sorted(q["order"]) != list(range(1, len(rd) + 1)) or [names[i - 1] for i in q["order"]] != sorted(names):
        out.append(f"{qid}: the readings stand {q['order']}, not alphabetically by name")
    for r in rd:
        ks = [S._passage_key(p) for p in r.get("passages") or []]
        if ks != sorted(ks):
            out.append(f"{qid}: reading {r['index']}'s passages are not in canonical order")
        c = r.get("credit") or {}
        got = [t["name"] for t in c.get("names") or []]
        if q.get("compare"):
            # the graph's documents, only where the reading's held_by names the tradition (FAULTS #26: Article X
            # is cited under free will's third reading, whose held_by lacks the Anglicans); the rest apart
            graph = set(S._stated_by(qid, len(rd)).get(r["index"], {}))
            held = set(raw["readings"][r["index"] - 1].get("held_by") or [])
            if c.get("by") != "stated" or sorted(got) != sorted(graph & held):
                out.append(f"{qid}: reading {r['index']} credits {got}, the graph states {sorted(graph)} and the "
                           f"card holds {sorted(held)}")
            if sorted(t["name"] for t in r.get("cited") or []) != sorted(graph - held):
                out.append(f"{qid}: reading {r['index']} lists {[t['name'] for t in r.get('cited') or []]} apart, "
                           f"not {sorted(graph - held)}")
        elif c.get("by") != "held" or got != list(raw["readings"][r["index"] - 1].get("held_by") or []):
            out.append(f"{qid}: reading {r['index']} credits {got}, the card holds "
                       f"{raw['readings'][r['index'] - 1].get('held_by')}")
    for t in q.get("find") or []:
        want = [i for i in q["order"] if t["name"] in [x["name"] for x in rd[i - 1]["credit"]["names"]]]
        if [w["index"] for w in t["where"]] != want:
            out.append(f"{qid}: find your tradition puts {t['name']} under {[w['index'] for w in t['where']]}, "
                       f"the card under {want}")
    return out


# ---- the page --------------------------------------------------------------------------------------------------------
def parts(head, body):
    title = html.unescape(re.search(r"<title>(.*?)</title>", head).group(1))
    desc = html.unescape(re.search(r'<meta name="description" content="(.*?)">', head).group(1))
    art = html.unescape(re.sub(r"<[^>]+>", " ", body.split("<article", 1)[1] if "<article" in body else ""))
    return title, desc, " ".join(art.split())


VERDICT = re.compile(r"\b(most|all|the best|the right|correct|true reading|majority|consensus|affirm both)\b", re.I)


def page_faults(qid, q, head, body):
    out = []
    title, desc, art = parts(head, body)
    if title != f"{q['question']} · Bible Ontology":
        out.append(f"{qid}: the title is {title!r}")
    if len(desc) > 300:
        out.append(f"{qid}: description {len(desc)} characters")
    for r in q["readings"]:
        s = r["short"].rstrip("…")
        if s not in desc or s not in art:
            out.append(f"{qid}: the description or article lacks the reading {s!r}")
    own_words = desc.replace("none taken", "")
    for r in q["readings"]:                 # a reading's own name may say "all" ("Freed by grace, for all")
        own_words = own_words.replace(r["short"].rstrip("…"), "")
    if VERDICT.search(own_words):
        out.append(f"{qid}: the description takes a side: {desc!r}")
    if q["shape"] not in art:
        out.append(f"{qid}: the article lacks the first line")
    ids = [int(x) for x in re.findall(r'<h2 id="reading-(\d+)"', body)]
    if ids != q["order"]:
        out.append(f"{qid}: the page's readings stand {ids}, the app's {q['order']}")
    return out


def ld_of(head):
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', head, re.S)
    return json.loads(m.group(1).replace("<\\/", "</")) if m else None


TERMS = {"@context", "@graph", "@type", "@id", "url", "name", "description", "publisher", "mainEntity", "mentions",
         "text", "answerCount", "suggestedAnswer", "citation"}
TYPES = {"WebPage", "Organization", "Question", "Answer"}


def ld_faults(qid, q, head, body):
    ld = ld_of(head)
    if ld is None:
        return [f"{qid}: no JSON-LD"]
    out = []
    bor = [c.get("bor") for c in ld.get("@context") or [] if isinstance(c, dict)]
    if bor != ["https://bibleontology.org/ns/relation#"]:
        out.append(f"{qid}: the JSON-LD's vocabulary is {bor}, not https://bibleontology.org/ns/relation#")
    hrefs = set(re.findall(r'href="([^"#?]+)"', body))
    own = f"/questions/{qid}"

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k.startswith("bor:"):
                    if k[4:] not in d["cats"]:
                        out.append(f"{qid}: the JSON-LD uses '{k}', which the relation vocabulary does not define")
                elif k not in TERMS:
                    out.append(f"{qid}: the JSON-LD uses '{k}', which neither vocabulary defines here")
                if k == "@type" and v not in TYPES:
                    out.append(f"{qid}: the JSON-LD types something '{v}'")
                if k == "@id" and isinstance(v, str) and v.startswith(S.SITE):
                    path = v[len(S.SITE):].split("#")[0]
                    if path != own and path not in hrefs:
                        out.append(f"{qid}: the JSON-LD names {path}, which the page does not link")
                if k != "@context":
                    walk(v)
        elif isinstance(x, list):
            for y in x:
                walk(y)
    walk(ld)
    qn = next((x for x in ld.get("@graph") or [] if x.get("@type") == "Question"), {})
    if len(qn.get("suggestedAnswer") or []) != len(q["readings"]) or qn.get("answerCount") != len(q["readings"]):
        out.append(f"{qid}: the JSON-LD offers {len(qn.get('suggestedAnswer') or [])} of {len(q['readings'])} readings")
    return out


RAW = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "ontology" / "questions").glob("*.json")}
CARDS, PAGES = {}, {}
for qid in S._questions():
    q = S.api_question(d, {"id": [qid]})
    CARDS[qid] = q
    PAGES[qid] = S.question_page(qid)
    for f in (card_faults(qid, q, RAW[qid]) + page_faults(qid, q, *PAGES[qid][:2])
              + ld_faults(qid, q, *PAGES[qid][:2])):
        fails.append(f)
check(len(CARDS) >= 10, f"only {len(CARDS)} question cards served")
fw = CARDS["free-will"]
# free will's comparison passed the eleven-reader panel (2026-10-28, docs/review/card-panel-appeal/question-panel/),
# so it is shown: the plain names, in their alphabetical order, and the two pulls
check(fw["order"] == [2, 3, 1] and [r["short"] for r in fw["readings"]][0] == "Healed to cooperate",
      f"free will stands {fw['order']} with {[r['short'] for r in fw['readings']]}")
check(len(fw["readings"][1]["passages"]) > 5 and fw["readings"][1]["shown"] == 5, "free will's reading 2 does not show five first")
check(fw["shape"] == "Readers divide here: these are the two pulls, and the verses each rests on.",
      f"free will's first line: {fw['shape']!r}")
# total depravity and human nature (pair 1) passed the same panel on 2026-10-29 (arbiter method, every seat's own lines
# accepted: docs/review/card-panel-appeal/question-panel/pair1-arbiter.md), so they are shown the same way: the plain
# names in alphabetical order, the pulls line, "Stated by" cut to held_by with the rest listed apart. The expected
# credits are the panel's rulings (the Anabaptists and Anglicans off total depravity's third reading, the Anabaptists
# and Baptists apart on human nature's third), so a change to them is a decision to look at, not a drift.
SHOWN = {
    "total-depravity": {
        "order": [2, 3, 1],
        "stated": {1: ["Catholic", "Eastern Orthodox"],
                   2: ["Anglican", "Baptist / free church", "Lutheran", "Reformed"],
                   3: ["Catholic", "Eastern Orthodox", "Pentecostal / Charismatic", "Wesleyan / Methodist"]},
        "apart": {1: [], 2: ["Pentecostal / Charismatic"], 3: ["Anabaptist", "Anglican"]},
    },
    "human-nature": {
        "order": [4, 1, 2, 3],
        "stated": {1: ["Catholic", "Eastern Orthodox"],
                   2: ["Anglican", "Baptist / free church", "Lutheran", "Pentecostal / Charismatic", "Reformed",
                       "Wesleyan / Methodist"],
                   3: ["Anabaptist"], 4: []},
        "apart": {1: [], 2: [], 3: ["Baptist / free church", "Wesleyan / Methodist"], 4: ["Pentecostal / Charismatic"]},
    },
    # baptism (pair 3): shown once the owner declined the held rider (B-V4.2), 2026-10-29
    "baptism": {
        "order": [3, 2, 1],
        "stated": {1: ["Anglican", "Catholic", "Eastern Orthodox", "Lutheran", "Wesleyan / Methodist"],
                   2: ["Anglican", "Reformed", "Wesleyan / Methodist"],
                   3: ["Anabaptist", "Baptist / free church", "Pentecostal / Charismatic"]},
        "apart": {1: [], 2: [], 3: []},
    },
    # the Lord's Supper (pair 3) passed the same panel on 2026-10-29 (pair3-arbiter.md). Anglican, Wesleyan and Baptist stand under reading 3 and Anabaptist under 4
    # "in part", the reason printed on the card.
    "communion": {
        "order": [4, 1, 2, 3],
        "stated": {1: ["Catholic", "Eastern Orthodox"], 2: ["Lutheran"],
                   3: ["Anglican", "Baptist / free church", "Reformed", "Wesleyan / Methodist"],
                   4: ["Anabaptist", "Baptist / free church", "Pentecostal / Charismatic"]},
        "apart": {1: [], 2: [], 3: [], 4: []},
    },
    # pair 2 (pair2-arbiter.md): the Wesleyan on election's first reading and the Pentecostal on faith and works' third
    # are held for the owner, so they stand apart here until he decides
    "election": {
        "order": [3, 2, 1],
        "stated": {1: ["Eastern Orthodox", "Pentecostal / Charismatic"],
                   2: ["Anglican", "Baptist / free church", "Lutheran", "Reformed"],
                   3: ["Anabaptist", "Catholic", "Pentecostal / Charismatic"]},
        "apart": {1: ["Anabaptist", "Catholic", "Wesleyan / Methodist"], 2: ["Catholic"], 3: ["Lutheran", "Reformed"]},
    },
    "faith-and-works": {
        "order": [1, 3, 2],
        "stated": {1: ["Catholic", "Eastern Orthodox"],
                   2: ["Anglican", "Baptist / free church", "Lutheran", "Pentecostal / Charismatic", "Reformed",
                       "Wesleyan / Methodist"],
                   3: ["Anabaptist", "Wesleyan / Methodist"]},
        "apart": {1: [], 2: [], 3: ["Pentecostal / Charismatic"]},
    },
}
for qid, want in SHOWN.items():
    c = CARDS[qid]
    check(RAW[qid]["compare"].get("reviewed") is True, f"{qid}: its comparison is not marked reviewed")
    check(c.get("compare") and c["order"] == want["order"]
          and [r["short"] for r in c["readings"]] == [x["name"] for x in sorted(RAW[qid]["compare"]["names"],
                                                                               key=lambda x: x["reading"])],
          f"{qid} stands {c.get('order')} with {[r['short'] for r in c['readings']]}, not its plain names in "
          f"{want['order']}")
    check(c["shape"] == "Readers divide here: these are the two pulls, and the verses each rests on.",
          f"{qid}'s first line: {c['shape']!r}")
    for r in c["readings"]:
        check(r["credit"]["by"] == "stated"
              and sorted(t["name"] for t in r["credit"]["names"]) == want["stated"][r["index"]]
              and sorted(t["name"] for t in r.get("cited") or []) == want["apart"][r["index"]],
              f"{qid}: reading {r['index']} credits {[t['name'] for t in r['credit']['names']]} with "
              f"{[t['name'] for t in r.get('cited') or []]} apart")
el = CARDS["election"]
check("Catholic" not in [t["name"] for t in el["readings"][1]["credit"]["names"]],
      "election: unconditional election credited to the Catholics (Trent ch. 12 is cited there as a caveat)")

# the passed comparison, as the preview shows it (free will): plain names, the pulls, "Stated by" from the graph
os.environ["BIBLEONT_SHOW_UNREVIEWED"] = "1"
fwc = S.api_question(d, {"id": ["free-will"]})
fwp = S.question_page("free-will")
del os.environ["BIBLEONT_SHOW_UNREVIEWED"]
for f in card_faults("free-will", fwc, RAW["free-will"]) + page_faults("free-will", fwc, *fwp[:2]) + \
        ld_faults("free-will", fwc, *fwp[:2]):
    fails.append(f"(passed comparison) {f}")
check(fwc.get("compare") and fwc["order"] == [2, 3, 1]
      and fwc["shape"] == "Readers divide here: these are the two pulls, and the verses each rests on."
      and "Anglican" not in [t["name"] for t in fwc["readings"][2]["credit"]["names"]]
      and "Anglican" in [t["name"] for t in fwc["readings"][2].get("cited") or []]
      and "Anglican" not in [t["name"] for t in fwc["compare"]["stated_by"]["3"]],
      f"free will with its comparison: {fwc.get('order')}, {fwc.get('shape')!r}, reading 3 credits "
      f"{[t['name'] for t in fwc['readings'][2]['credit']['names']]}")

# planted: each fault the checks exist for
q0, raw0 = CARDS["free-will"], RAW["free-will"]
# the Anglicans credited under free will's third reading on Article X, which its held_by does not name (FAULTS #26)
bad = copy.deepcopy(fwc); bad["readings"][2]["credit"]["names"].append({"name": "Anglican"})
bad["readings"][2]["cited"] = []
check(any("reading 3" in f for f in card_faults("free-will", bad, raw0)),
      "planted: the Anglicans credited under free will's third reading were not caught")
bad = copy.deepcopy(q0); bad["shape"] = "Most traditions affirm both: God works and the person chooses."
check(card_faults("free-will", bad, raw0), "planted: a first line that takes a side was not caught")
bad = copy.deepcopy(q0); bad["shape"] = bad["shape"].replace("two pulls", "four readings")
check(card_faults("free-will", bad, raw0), "planted: a first line with the wrong count was not caught")
bad = copy.deepcopy(q0); bad["order"] = [1, 2, 3]
check(card_faults("free-will", bad, raw0), "planted: the readings in the card's old order were not caught")
bad = copy.deepcopy(q0); bad["readings"][0]["passages"].reverse()
check(card_faults("free-will", bad, raw0), "planted: passages out of canonical order were not caught")
bad = copy.deepcopy(el); bad["readings"][1]["credit"]["names"].append({"name": "Catholic"})
check(card_faults("election", bad, RAW["election"]), "planted: a credit the card does not hold was not caught")
bad = copy.deepcopy(q0); bad["find"][0]["where"] = []
check(card_faults("free-will", bad, raw0), "planted: a tradition lost from find your tradition was not caught")
h, b = PAGES["free-will"][:2]
check(page_faults("free-will", q0, h.replace("Healed to cooperate", "The right reading"), b),
      "planted: a description that names a reading the page lacks was not caught")
check(page_faults("free-will", q0, h, b.replace('<h2 id="reading-2"', '<h2 id="reading-x"', 1)),
      "planted: the page's readings in another order were not caught")
check(page_faults("free-will", q0, h.replace("and none taken:", "and most traditions affirm both:"), b),
      "planted: a description that takes a side was not caught")
ld = ld_of(h)
bad = copy.deepcopy(ld)
bad["@context"][1]["bor"] = "https://bibleontology.org/ns/"
bad["@graph"][1]["acceptedAnswer"] = bad["@graph"][1]["suggestedAnswer"][0]
bad["@graph"][1]["suggestedAnswer"][0]["citation"] = [{"@id": f"{S.SITE}/p/Obad.1.21"}]
bad["@graph"][1]["suggestedAnswer"][1]["bor:states_reading"] = "x"
h_bad = re.sub(r'<script type="application/ld\+json">.*?</script>',
               lambda m: '<script type="application/ld+json">' + json.dumps(bad) + "</script>", h, flags=re.S)
lf = ld_faults("free-will", q0, h_bad, b)
check(any("ns/relation#" in f for f in lf), "planted: the JSON-LD check did not catch the /ns/ address")
check(any("acceptedAnswer" in f for f in lf), "planted: the JSON-LD check did not catch an accepted answer")
check(any("/p/Obad.1.21" in f for f in lf), "planted: the JSON-LD check did not catch a verse the page does not link")
check(any("states_reading" in f for f in lf), "planted: the JSON-LD check did not catch a term the vocabulary lacks")


# ---- a comparison the panel has not passed stays hidden -------------------------------------------------------------
# (2026-10-28: the next batch's comparisons are drafted with `reviewed` false, total depravity and human nature first,
# docs/review/card-panel-appeal/question-panel/packet-pair1-round1.md). The served card carries no comparison, credits
# by its own held_by ("Held by"), counts its readings rather than naming pulls, and shows no plain name; the preview
# (BIBLEONT_SHOW_UNREVIEWED) shows the comparison, and there it keeps every rule above.
def hidden_faults(qid, q, raw):
    out = []
    c = raw.get("compare") or {}
    if not c or c.get("reviewed"):
        return out
    if q.get("compare"):
        out.append(f"{qid}: its comparison is served before the panel passed it")
    if any((r.get("credit") or {}).get("by") != "held" for r in q["readings"]):
        out.append(f"{qid}: credits 'Stated by' before the panel passed its comparison")
    if "two pulls" in (q.get("shape") or "") or any(r.get("name") for r in q["readings"]):
        out.append(f"{qid}: shows the comparison's pulls or plain names before the panel passed it")
    return out


UNPASSED = sorted(k for k in CARDS if RAW[k].get("compare") and not RAW[k]["compare"].get("reviewed"))
for qid in UNPASSED:
    fails.extend(hidden_faults(qid, CARDS[qid], RAW[qid]))
os.environ["BIBLEONT_SHOW_UNREVIEWED"] = "1"
PREVIEW = {qid: (S.api_question(d, {"id": [qid]}), S.question_page(qid)) for qid in UNPASSED}
del os.environ["BIBLEONT_SHOW_UNREVIEWED"]
for qid, (pq, pp) in PREVIEW.items():
    for f in card_faults(qid, pq, RAW[qid]) + page_faults(qid, pq, *pp[:2]) + ld_faults(qid, pq, *pp[:2]):
        fails.append(f"(preview) {f}")
    check(pq.get("compare") and [r["short"] for r in pq["readings"]]
          == [x["name"] for x in sorted(RAW[qid]["compare"]["names"], key=lambda x: x["reading"])],
          f"{qid}: the preview does not show its comparison with its plain names")
# planted: a comparison not yet passed, served as though it were (free will's, marked unpassed)
raw_unpassed = copy.deepcopy(RAW["free-will"]); raw_unpassed["compare"]["reviewed"] = False
check(len(hidden_faults("free-will", fwc, raw_unpassed)) == 3,
      "planted: a comparison served before the panel passed it was not caught")
# the same for each of pair 1: its comparison served while `reviewed` is false, and a credit its held_by lacks
for qid, extra in (("total-depravity", (3, "Anglican")), ("human-nature", (3, "Wesleyan / Methodist"))):
    raw_unpassed = copy.deepcopy(RAW[qid]); raw_unpassed["compare"]["reviewed"] = False
    check(len(hidden_faults(qid, CARDS[qid], raw_unpassed)) == 3,
          f"planted: {qid}'s comparison served while reviewed is false was not caught")
    bad = copy.deepcopy(CARDS[qid]); bad["readings"][extra[0] - 1]["credit"]["names"].append({"name": extra[1]})
    check(any(f"reading {extra[0]}" in f for f in card_faults(qid, bad, RAW[qid])),
          f"planted: {extra[1]} credited under {qid}'s reading {extra[0]}, which its held_by lacks, was not caught")
    bad = copy.deepcopy(CARDS[qid]); bad["order"] = sorted(bad["order"])
    check(card_faults(qid, bad, RAW[qid]), f"planted: {qid} in the holders' own order was not caught")


# ---- on a phone, one reading at a time -------------------------------------------------------------------------------
def phone_faults(page):
    out = []
    blocks = re.findall(r"@media \(max-width:640px\)\{(.*?)\n\}", page, re.S)
    rules = "".join(b for b in blocks if ".qmap{display:none}" in b)
    for rule, why in ((".qmap{display:none}", "the table is not hidden"),
                      (".qsw{display:block}", "the switcher is not shown"),
                      (".qcards .qrcard:not(.qsel){display:none}", "every reading's card shows at once"),
                      (".qreadings[data-sw] > details.sec:not(.qsel){display:none}", "every reading shows at once")):
        if rule not in rules:
            out.append(f"on a phone {why}")
    if page.count("swHTML(") < 2:
        out.append("the switcher is not drawn for both kinds of card")
    return out


INDEX = (ROOT / "app2" / "static" / "index.html").read_text(encoding="utf-8")
for f in phone_faults(INDEX):
    fails.append(f)
check(phone_faults(INDEX.replace(".qcards .qrcard:not(.qsel){display:none}", "")),
      "planted: every reading's card at once on a phone was not caught")
check(phone_faults(INDEX.replace("  .qsw{display:block}\n", "")), "planted: a hidden switcher was not caught")

print(f"{len(CARDS)} question cards and pages (and free will with its comparison; {len(UNPASSED)} comparisons "
      f"hidden until the panel passes them, checked in the preview: {', '.join(UNPASSED) or 'none'}), 25 planted faults")
for f in fails[:30]:
    print("FAIL", f)
print("ok" if not fails else f"{len(fails)} failures")
sys.exit(1 if fails else 0)
