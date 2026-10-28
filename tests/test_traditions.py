"""The traditions layer (ontology/traditions/, 2026-10-26) holds what the question cards say, and nothing more.

The owner's standing rule is "no node, edge or shown link without Biblical backup", and a card that is not shown
must put nothing on the site. Held by machine:

  - the layer on disk is what tools/traditions/build.py makes from the cards now (a card edited under review and
    not rebuilt fails here, not in the validator)
  - the layer passes bibleont.traditions.problems: every node and edge carries verses that exist, every edge joins
    kinds its relation takes, every document has one tradition and speaks on a question
  - every source a reading cites has its states_reading edge, and that edge carries the reading's own verses
  - no tradition page, list, count or sitemap entry exists for a card that is not shown, and none leaks a question
    that is not shown when another is
  - from a question's sources to a tradition page and from the tradition back to the reading, both ways, every
    address is one the site has
  - the old words ("not part of this site's knowledge graph") are gone from the app and the crawlable page

Proven 2026-10-26 with three faults planted on disk and in the server, each failing here at once and then removed:
an edge with its refs emptied (the checker, the coverage check and the currency check all named it; so did
`python -m bibleont.validate`); a states_reading edge deleted (the coverage check named the source); and every
card treated as shown in _traditions() (a page for a tradition with no card shown, and the other questions named on
a page that should hold one). The first two are also planted in-process below, so a later change cannot loosen
them unseen. NOTE: `python -m bibleont.validate` in a worktree needs PYTHONPATH=src, or it checks the main checkout.

In process, with no server (about five seconds). Run: python tests/test_traditions.py"""
import copy
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app2"))
sys.path.insert(0, str(ROOT / "tools" / "traditions"))
os.environ.pop("BIBLEONT_SHOW_UNREVIEWED", None)

import build as B                                   # noqa: E402
from bibleont import traditions as T                # noqa: E402
import server as S                                  # noqa: E402

fails: list[str] = []


def check(name, ok, detail=""):
    if not ok:
        fails.append(f"{name}: {detail}" if detail else name)


def has(rows, code):
    return any(r[1] == code for r in rows)


# --- the layer is the cards' -------------------------------------------------------------------------------------
nodes, edges, bad = B.build()
check("the cards build without problems", not bad, "; ".join(bad[:3]))
dn, de = T.load_layer()
check("the layer on disk is what the cards make now (run tools/traditions/build.py)",
      B.lines(nodes) == B.lines(dn) and B.lines(edges) == B.lines(de))

# --- it is sound, and the checker sees a fault -------------------------------------------------------------------
from bibleont.validate import _berean               # noqa: E402
corpus = _berean()
probs = T.problems(corpus, dn, de)
check("the layer passes the checker", not probs, str(probs[:2]))
e2 = copy.deepcopy(de)
e2[0]["refs"] = []
check("PLANTED: an edge with no verse is caught", has(T.problems(corpus, dn, e2), "tradition.edge_no_refs"))
e3 = copy.deepcopy(de)
e3[0]["refs"] = ["Genesis 99:99"]
check("PLANTED: an edge on a verse that does not exist is caught",
      has(T.problems(corpus, dn, e3), "tradition.edge_dead_ref"))
n2 = copy.deepcopy(dn)
n2[0]["refs"] = []
check("PLANTED: a node with no verse is caught", has(T.problems(corpus, n2, de), "tradition.node_no_refs"))
check("PLANTED: an edge to a node that is not there is caught",
      has(T.problems(corpus, dn, de + [dict(de[0], dst="nowhere")]), "tradition.unknown_node"))
check("PLANTED: a relation the schema does not declare is caught",
      has(T.problems(corpus, dn, [dict(de[0], type="endorses")] + de[1:]), "tradition.unknown_type"))
check("PLANTED: a document with no tradition is caught",
      has(T.problems(corpus, dn, [x for x in de if x["type"] != "issued_by"]), "tradition.document_owner"))


# --- every source a reading cites has its edge, on the reading's own verses --------------------------------------
def uncovered(cards, layer_edges):
    """(question, reading, source title) for each source a reading cites that has no states_reading edge on that
    reading's verses"""
    have = {(e["src"], e["dst"]): e for e in layer_edges if e["type"] == "states_reading"}
    out = []
    for qid, card in cards.items():
        fr = card.get("further_reading") or []
        for i, r in enumerate(card.get("readings") or [], 1):
            want = [p["ref"] for p in r.get("passages") or []]
            for s in r.get("sources") or []:
                f = fr[s]
                e = have.get((B_doc(f), f"reading_{qid.replace('-', '_')}_{i}"))
                if e is None or sorted(set(e["refs"])) != sorted(set(want)):
                    out.append((qid, i, f["title"]))
    return out


def B_doc(f):
    return S._doc_id(f["title"], f["url"])


cards = {}
for p in sorted((ROOT / "ontology" / "questions").glob("*.json")):
    q = json.loads(p.read_text(encoding="utf-8"))
    cards[q["id"]] = q
miss = uncovered(cards, de)
check("every source a reading cites has its edge on the reading's verses", not miss, str(miss[:3]))
dropped = next(x for x in de if x["type"] == "states_reading")
check("PLANTED: a document cited by a reading with no edge is caught",
      bool(uncovered(cards, [x for x in de if x is not dropped])))
check("the server and the build name a document the same way",
      all(S._doc_id(f["title"], f["url"]) in {n["id"] for n in dn} for c in cards.values()
          for f in c.get("further_reading") or []))


# --- nothing from a card that is not shown -----------------------------------------------------------------------
def reset(shown):
    """serve exactly these question ids as shown (None: as the process would with nothing shown)"""
    S._QUESTIONS = None if shown is None else {k: v for k, v in cards.items() if k in shown}
    S._TRAD_MODEL = None


shown_now = {k for k, v in cards.items() if v.get("shown")}
reset(None)
if not shown_now:
    check("with no card shown there are no traditions", S._traditions() == {})
    check("with no card shown the list answers 404", S.traditions_index_page() is None)
    check("with no card shown About counts none", S._tradition_counts() is None)
    check("with no card shown no tradition page is served",
          all(S.traditions_page(n["attrs"]["slug"]) is None for n in dn
              if n["type"] == "tradition" and n["attrs"]["level"] != "body"))
# a preview shows what the cards hold: the gate, not an absence of data, is what hides them
reset(set(cards))
check("with every card shown the traditions appear", len(S._traditions()) >= 9, str(len(S._traditions())))
# one card shown: its traditions, and only its questions
one = "after-death" if "after-death" in cards else sorted(cards)[0]
reset({one})
ts = S._traditions()
check("one card shown reaches some traditions", bool(ts))
for slug, m in ts.items():
    page = S.traditions_page(slug)
    html = (page[0] + page[1]) if page else ""
    check(f"{slug}: a page for a tradition a shown card reaches", bool(page))
    check(f"{slug}: positions are of the shown card only", {p["id"] for p in m["positions"]} <= {one},
          str({p["id"] for p in m["positions"]}))
    check(f"{slug}: every document speaks on the shown card only",
          all(set(x["questions"]) <= {one} for x in m["docs"]))
    for other in cards:
        if other != one:
            check(f"{slug}: no mention of /questions/{other}", f"/questions/{other}" not in html)
            check(f"{slug}: nor of the question itself", cards[other]["question"] not in html)
reached = {slug for slug in ts}
for n in dn:
    if n["type"] == "tradition" and n["attrs"]["level"] != "body" and n["attrs"]["slug"] not in reached:
        check(f"{n['attrs']['slug']}: a tradition no shown card reaches has no page",
              S.traditions_page(n["attrs"]["slug"]) is None)
idx = S.traditions_index_page()
check("the list names only traditions the shown card reaches",
      bool(idx) and all(f"/traditions/{s}" in idx[1] for s in reached)
      and all(f'href="/traditions/{n["attrs"]["slug"]}"' not in idx[1] for n in dn
              if n["type"] == "tradition" and n["attrs"]["level"] != "body" and n["attrs"]["slug"] not in reached))
check("About counts only the shown card",
      S._tradition_counts()["questions"] == 1, str(S._tradition_counts()))

# --- both ways ---------------------------------------------------------------------------------------------------
reset(set(cards))
ts = S._traditions()
for qid, card in S._questions().items():
    fr, groups = S._fr_enriched(card)
    for f in fr:
        check(f"{qid}: '{f['title'][:40]}' links to a tradition page that exists",
              f.get("tslug") in ts and f.get("tpath") == f"/traditions/{f.get('tslug')}", str(f.get("tslug")))
    for r in card.get("readings") or []:
        for s in r.get("sources") or []:
            check(f"{qid}: a reading's source {s} is a source of the card", 0 <= s < len(fr))
for slug, m in ts.items():
    for p in m["positions"]:
        card = S._questions()[p["id"]]
        for r in p["readings"]:
            check(f"{slug}: reading {r['index']} of {p['id']} exists on the card",
                  1 <= r["index"] <= len(card["readings"]))
            check(f"{slug}: the reading's link is the question's own address",
                  r["path"] == f"/questions/{p['id']}#reading-{r['index']}")
    page = S.traditions_page(slug)
    for p in m["positions"]:
        check(f"{slug}: its page links back to {p['id']}", f'href="/questions/{p["id"]}"' in page[1])

# --- the old words ---------------------------------------------------------------------------------------------
OLD = "not part of this site's knowledge graph"
for f in (ROOT / "app2" / "server.py", ROOT / "app2" / "static" / "index.html"):
    check(f"{f.name}: the old disclaimer is gone", OLD not in f.read_text(encoding="utf-8"))

print(f"{len(dn)} nodes, {len(de)} edges, {len(cards)} cards, {len(fails)} failures")
for f in fails[:12]:
    print("FAIL", f)
sys.exit(1 if fails else 0)
