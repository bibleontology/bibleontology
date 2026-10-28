"""Build the traditions layer from the question cards (2026-10-26).

Reads every ontology/questions/*.json and writes ontology/traditions/nodes.jsonl and edges.jsonl: a node for each
tradition, church body and school of reading, for each distinct document (title and address), and for each question
and reading they speak to; edges from the document to whose it is (`issued_by`), to the question it speaks on
(`speaks_on`) and to each reading whose `sources` cite it (`states_reading`). Every node and every edge carries the
Bible verses of the readings it supports, so nothing in the layer stands without scripture.

The cards stay the one source of truth: edit a card, run this again. Nothing here is edited by hand.
Declared in ontology/schema/traditions.json; checked by bibleont.validate and tests/test_traditions.py.

    python tools/traditions/build.py          # write the layer
    python tools/traditions/build.py --check  # exit 1 if the files on disk differ from a fresh build
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "ontology" / "questions"
OUT = ROOT / "ontology" / "traditions"
SOURCE = "tools/traditions/build.py"

# the nine, in the order the site names them
NINE = ["Catholic", "Eastern Orthodox", "Lutheran", "Reformed", "Anglican", "Wesleyan / Methodist",
        "Baptist / free church", "Pentecostal / Charismatic", "Anabaptist"]
SCHOOL = re.compile(r"^(.*?) \(a school of reading\)$")

# how a document stands, in plain words (shown beside it everywhere)
STANDING = {
    "confession": "a confession of faith",
    "catechism": "a catechism",
    "standard": "adopted as a doctrinal standard",
    "founder": "a founder's work, not the tradition's own statement",
    "scholar": "a scholar's work, not any church's statement",
    # a pastor's or teacher's answer published on a church's own site (2026-10-26: the OCA's question-and-answer
    # pages): the church hosts it, but it is not the church's statement
    "answer": "a teacher's answer on the church's site, not the church's statement",
    # a commission's or an assembly's report or pastoral letter (2026-10-26): received by the body, but not its
    # confession or constitutional standard
    "report": "a report or letter a body received, not its confession",
}

# one body written several ways across the cards is one body (the cards are not edited here)
BODY = {
    "Dutch Mennonite conference at Dordrecht (1632), later adopted by Mennonites in America (1725)":
        "Mennonites of the Dordrecht Confession (1632)",
    "Mennonite (Dordrecht Confession, 1632)": "Mennonites of the Dordrecht Confession (1632)",
    "Dutch Mennonites": "Mennonites of the Dordrecht Confession (1632)",
    "Arminian line before Wesley (Jacobus Arminius)": "The Remonstrants (the Arminian line before Wesley)",
    "Arminian line before Wesley (the Remonstrants)": "The Remonstrants (the Arminian line before Wesley)",
    "Remonstrants (Arminian line)": "The Remonstrants (the Arminian line before Wesley)",
}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def body_name(b: str) -> str:
    b = re.sub(r"(Lutheran Church)[\u2010-\u2015\-\ufffd](Missouri Synod)", "\\1\u2013\\2", b.strip())
    return BODY.get(b, b)


def union(*lists):
    seen, out = set(), []
    for lst in lists:
        for r in lst or []:
            if r and r not in seen:
                seen.add(r)
                out.append(r)
    return out


def build(questions_dir: Path = QUESTIONS, shown_only: bool = False):
    """The layer from every card (what the server gates by "shown"), or, with shown_only, from the shown cards alone:
    what the public data release carries while some cards are held (2026-10-27, three end-times cards held)."""
    nodes: dict[str, dict] = {}
    edges: dict[tuple, dict] = {}
    problems: list[str] = []

    def node(nid, typ, name, refs, attrs):
        n = nodes.setdefault(nid, {"id": nid, "type": typ, "name": name, "refs": [], "source": SOURCE, "attrs": attrs})
        n["refs"] = union(n["refs"], refs)
        return n

    def edge(src, typ, dst, refs, q, note=""):
        e = edges.setdefault((src, typ, dst), {"src": src, "type": typ, "dst": dst, "refs": [], "certainty": "explicit",
                                                "note": note, "questions": [], "source": SOURCE})
        e["refs"] = union(e["refs"], refs)
        if q not in e["questions"]:
            e["questions"].append(q)
        if note and not e["note"]:
            e["note"] = note
        return e

    top_ids: dict[str, str] = {}

    def top(name):
        """the node for a tradition (one of the nine) or a school of reading, with its page address"""
        if name in top_ids:
            return top_ids[name]
        m = SCHOOL.match(name)
        if m:
            label, level = m.group(1), "school"
        elif name in NINE:
            label, level = name, "tradition"
        else:
            problems.append(f"unknown tradition {name!r}: not one of the nine and not a school of reading")
            label, level = name, "tradition"
        nid = f"{level}_{slug(label).replace('-', '_')}"
        top_ids[name] = nid
        nodes.setdefault(nid, {"id": nid, "type": "tradition", "name": label, "refs": [], "source": SOURCE,
                               "attrs": {"level": level, "slug": slug(label),
                                         "order": NINE.index(name) if name in NINE else 100}})
        return nid

    def body(tname, bname):
        tid = top(tname)
        b = body_name(bname)
        bid = f"body_{slug(b).replace('-', '_')}"
        nodes.setdefault(bid, {"id": bid, "type": "tradition", "name": b, "refs": [], "source": SOURCE,
                               "attrs": {"level": "body", "slug": slug(b), "tradition": tid}})
        return bid

    docs: dict[str, dict] = {}
    for path in sorted(questions_dir.glob("*.json")):
        q = json.loads(path.read_text(encoding="utf-8"))
        if shown_only and not q.get("shown"):
            continue
        qid = q["id"]
        fr = q.get("further_reading") or []
        passages = [p["ref"] for p in (q.get("agreed") or {}).get("passages") or []]
        readings = q.get("readings") or []
        for r in readings:
            passages += [p["ref"] for p in r.get("passages") or []]
        passages = union(passages)
        qnode = f"question_{qid.replace('-', '_')}"
        node(qnode, "question", q.get("question") or qid, passages, {"id": qid, "short": q.get("short") or qid})
        rnode = {}
        for i, r in enumerate(readings, 1):
            rid = f"reading_{qid.replace('-', '_')}_{i}"
            rnode[i - 1] = rid
            node(rid, "reading", r.get("label") or f"Reading {i}", [p["ref"] for p in r.get("passages") or []],
                 {"question": qid, "index": i})
        for fi, f in enumerate(fr):
            kind = f.get("kind")
            if kind not in STANDING:
                problems.append(f"{qid}: further_reading[{fi}] has kind {kind!r}, which has no standing label")
                continue
            did = "doc_" + hashlib.sha1(f"{f['title']}|{f['url']}".encode("utf-8")).hexdigest()[:10]
            tid = top(f["tradition"])
            bid = body(f["tradition"], f["body"]) if f.get("body") else None
            d = docs.setdefault(did, {"tid": tid, "bid": bid, "f": f, "checked": True, "refs": [], "qs": []})
            if d["tid"] != tid or d["bid"] != bid:
                problems.append(f"{qid}: {f['title']!r} is given to a different tradition or body than on an earlier card")
            d["checked"] = d["checked"] and bool(f.get("checked", True))
            citing = [i for i, r in enumerate(readings) if fi in (r.get("sources") or [])]
            says = (f.get("says") or "").strip()
            edge(did, "speaks_on", qnode, passages, qid, says)
            d["refs"] = union(d["refs"], passages)
            if qid not in d["qs"]:
                d["qs"].append(qid)
            for i in citing:
                rp = [p["ref"] for p in readings[i].get("passages") or []]
                edge(did, "states_reading", rnode[i], rp, qid)
        # a source index that points nowhere is a card fault, not something to hide
        for i, r in enumerate(readings):
            for s in r.get("sources") or []:
                if not (isinstance(s, int) and 0 <= s < len(fr)):
                    problems.append(f"{qid}: reading {i + 1} cites source {s!r}, and the card has {len(fr)}")

    for did, d in docs.items():
        f = d["f"]
        node(did, "document", f["title"], d["refs"],
             {"tradition": d["tid"], "body": d["bid"], "kind": f["kind"], "standing": STANDING[f["kind"]],
              "title": f["title"], "url": f["url"], "checked": d["checked"]})
        for dst in [d["tid"]] + ([d["bid"]] if d["bid"] else []):
            for q in d["qs"]:
                edge(did, "issued_by", dst, d["refs"], q)
            nodes[dst]["refs"] = union(nodes[dst]["refs"], d["refs"])
        if d["bid"]:
            nodes[nodes[d["bid"]]["attrs"]["tradition"]]["refs"] = union(
                nodes[nodes[d["bid"]]["attrs"]["tradition"]]["refs"], d["refs"])
    # an issued_by edge carries the verses of everything the document is cited for, not of one question
    for (src, typ, dst), e in edges.items():
        if typ == "issued_by":
            e["refs"] = list(docs[src]["refs"])
    return sorted(nodes.values(), key=lambda n: n["id"]), \
        sorted(edges.values(), key=lambda e: (e["src"], e["type"], e["dst"])), problems


def lines(rows) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)


def main() -> int:
    nodes, edges, problems = build()
    if problems:
        print("The cards need attention before the layer can be built:")
        for p in problems:
            print("  -", p)
        return 1
    want = {"nodes.jsonl": lines(nodes), "edges.jsonl": lines(edges)}
    if "--check" in sys.argv:
        stale = [n for n, t in want.items()
                 if not (OUT / n).exists() or (OUT / n).read_text(encoding="utf-8") != t]
        print("traditions layer is " + ("STALE: " + ", ".join(stale) if stale else "current"))
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for n, t in want.items():
        with open(OUT / n, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(t)
    kinds = {}
    for n in nodes:
        k = n["type"] + ("/" + n["attrs"]["level"] if n["type"] == "tradition" else "")
        kinds[k] = kinds.get(k, 0) + 1
    et = {}
    for e in edges:
        et[e["type"]] = et.get(e["type"], 0) + 1
    print(f"{len(nodes)} nodes {kinds}; {len(edges)} edges {et}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
