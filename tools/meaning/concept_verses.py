"""PHASE 2 OF THE CONCEPT AUDIT: THE VERSES (2026-10-18: to know where the
likely gaps are with the verses, for a prioritized backlog of concept
repairs; tools/meaning/concept_audit.py is phase 1).

For every card where phase 1 said to ADD words, the verses those words carry
that the card does not (up to 40 a card, spread over books), each read by a
judge against the card: does this verse speak of the concept? The answer is
a concrete list of verses a repair would add.

    python tools/meaning/concept_verses.py run <run> <phase1-run>  -> out/meaning/concept-audit/<run>/V-*.json
    python tools/meaning/concept_verses.py merge <run> <phase1-run>  -> out/meaning/concept-audit/backlog.jsonl

Stops on a STOP file, or when its ledger passes the cap in <run>/BUDGET.
"""
import collections
import concurrent.futures as cf
import gzip
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "meaning" / "concept-audit"
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
import concept_audit as A  # noqa: E402
import context as C  # noqa: E402
import headless as H  # noqa: E402

OUT = A.OUT          # follows CA_DIR, so the other kinds' audit keeps its own files

import os
# up to 150 verses a card overnight 2026-10-18 (use the budget well);
# the docstring's 40 is the default for a light run
PER_CARD = int(os.environ.get("CV_PER_CARD", "40"))
TASK = """You are deciding which verses belong on a concept card in a Bible knowledge graph. The card names a concept;
each verse below uses a Hebrew or Greek word that usually expresses it. For each verse, answer:
  "yes"    the verse speaks of this concept (the word is used in that sense here)
  "no"     the word means something else here, or the verse is not about the concept
  "unsure" it could be read either way
Read the Berean text. Unresolved is better than wrong. Take no doctrinal position: judge only whether the verse
speaks of the concept, not what it teaches about it.

Answer with ONLY this JSON object:
{"card": "<card id>", "verses": {"<ref>": "yes|no|unsure"}}

"""


def phase1(run):
    ans = {}
    for p in sorted((OUT / run).glob("A-*.json")):
        for c in json.loads(p.read_text(encoding="utf-8")).get("cards") or []:
            ans[c.get("id")] = c
    return ans


def work(p1run):
    items = {i["id"]: i for i in json.loads((OUT / "items.json").read_text(encoding="utf-8"))}
    answers = phase1(p1run)
    verses_of = collections.defaultdict(set)
    with gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("word") and d.get("class") in ("noun", "verb", "adj"):
                s = re.sub(r"\D", "", str(d.get("strong") or "")).lstrip("0")
                if s:
                    verses_of[("g" if d.get("lang") == "greek" else "h") + s].add(d["ref"])
    # CV_SKIP_RUNS=verses-1: leave out verses an earlier run already judged, so a
    # second sample of a large pool covers new verses (2026-10-19)
    skip = collections.defaultdict(set)
    for r in filter(None, os.environ.get("CV_SKIP_RUNS", "").split(",")):
        for p in (OUT / r).glob("V-*.json"):
            skip[p.stem[2:]] |= set(json.loads(p.read_text(encoding="utf-8")).get("verses") or {})
    out = []
    for cid, a in answers.items():
        it = items.get(cid)
        if not it:
            continue
        adds = [k for k, v in (a.get("candidates") or {}).items() if v == "add"]
        if not adds:
            continue
        have = set().union(set(), *[verses_of[x["key"]] for x in it["anchors"]])
        pool = sorted({v for k in adds for v in verses_of[k]} - have - skip.get(cid, set()))
        if len(pool) > PER_CARD:                       # spread over the whole pool
            step = len(pool) / PER_CARD
            pool = [pool[int(i * step)] for i in range(PER_CARD)]
        if pool:
            out.append({"id": cid, "name": it["name"], "adds": adds, "pool": pool, "grade": a.get("grade"),
                        "cited": it["cited"], "verses": it["verses"]})
    out.sort(key=lambda x: (-x["cited"], -x["verses"]))
    return out


def run(name, p1run):
    H.stay_awake()
    run_dir = OUT / name
    run_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "tools"))
    from run_record import record
    record(run_dir, A.MODELS["sonnet"], TASK, __file__)
    A.state["tokens"] = sum(json.loads(x)["tokens"] for x in (run_dir / "_ledger.jsonl").read_text(encoding="utf-8").splitlines()) \
        if (run_dir / "_ledger.jsonl").exists() else 0
    cards = work(p1run)
    bsb = C._bsb()

    def text(c):
        return TASK + json.dumps({"card": c["id"], "name": c["name"],
                                  "verses": [{"ref": r, "text": bsb(r)[1]} for r in c["pool"]]},
                                 ensure_ascii=False, separators=(",", ":")) + "\n"

    def one(c):
        out = run_dir / f"V-{c['id']}.json"
        if out.exists() or A.state["stop"]:
            return
        cap = run_dir / "BUDGET"
        if cap.exists() and A.state["tokens"] >= int(cap.read_text().strip() or 0):
            A.state["stop"] = "token cap reached"
            return
        for attempt in range(3):
            if (run_dir / "STOP").exists():
                A.state["stop"] = "STOP file"
                return
            res, err = H.call(text(c), A.MODELS["sonnet"])
            blob = json.dumps(res or {}) + (err or "")
            if (res is None or res.get("is_error")) and "limit" in blob.lower():
                A.log(run_dir, f"{c['id']}: usage limit; waiting 10 minutes")
                time.sleep(600)
                continue
            if res is None or res.get("is_error"):
                A.state["fails"] += 1
                if A.state["fails"] >= 5:
                    A.state["stop"] = "5 failed calls in a row"
                    return
                continue
            A.state["fails"] = 0
            u = res.get("usage") or {}
            toks = sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                 "cache_creation_input_tokens"))
            with A.LOCK:
                A.state["tokens"] += toks
                with open(run_dir / "_ledger.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"card": c["id"], "verses": len(c["pool"]), "tokens": toks}) + "\n")
            ans = H.parse(res)
            got = set(((ans or {}).get("verses") or {}).keys()) & set(c["pool"])
            if len(got) >= 0.8 * len(c["pool"]):
                out.write_text(json.dumps(ans, ensure_ascii=False, indent=1), encoding="utf-8")
                A.log(run_dir, f"{c['id']}: {len(got)} of {len(c['pool'])} verses, {toks:,} tokens")
                return
        A.log(run_dir, f"{c['id']}: LOST")

    A.log(run_dir, f"start: {len(cards)} cards, {sum(len(c['pool']) for c in cards):,} verses, {A.WORKERS} at a time")
    with cf.ThreadPoolExecutor(A.WORKERS) as ex:
        for f in [ex.submit(one, c) for c in cards]:
            f.result()
    A.log(run_dir, f"end: {A.state['stop'] or 'all cards done'}; {A.state['tokens']:,} tokens")


def _verdicts(x):
    """A judge's verdicts as {key: verdict}: a few phase-1 answers gave a list
    (2026-10-19, the first merge failed on one) -- a list of keys, or of
    {key: verdict} objects."""
    if isinstance(x, dict):
        return x
    out = {}
    for y in x or []:
        if isinstance(y, dict):
            out.update({k: v for k, v in y.items() if isinstance(v, str)})
        elif isinstance(y, str):
            out[y] = "listed"
    return out


def merge(name, p1run, second=None):
    """One line per card: its grade, the words to add or drop, the notes, and
    the verses phase 2 said yes to, in BOTH passes where a second ran;
    ordered for a backlog."""
    items = {i["id"]: i for i in json.loads((OUT / "items.json").read_text(encoding="utf-8"))}
    p1 = phase1(p1run)

    def load(run):
        v = {}
        for p in (OUT / run).glob("V-*.json"):
            v[p.stem[2:]] = json.loads(p.read_text(encoding="utf-8")).get("verses") or {}
        return v
    v1 = load(name)
    v2 = load(second) if second else None
    rows, agree, judged_both = [], 0, 0
    for cid, a in p1.items():
        it = items.get(cid) or {}
        a1, a2 = v1.get(cid) or {}, (v2 or {}).get(cid) or {}
        if v2 is not None:
            both = set(a1) & set(a2)
            judged_both += len(both)
            agree += sum(1 for r in both if a1[r] == a2[r])
            yes = sorted(r for r in both if a1[r] == "yes" and a2[r] == "yes")
        else:
            yes = sorted(r for r, x in a1.items() if x == "yes")
        rows.append({"id": cid, "name": it.get("name"), "grade": a.get("grade"), "confidence": a.get("confidence"),
                     "cited": it.get("cited"), "verses_now": it.get("verses"),
                     "add_words": [k for k, x in _verdicts(a.get("candidates")).items() if x == "add"],
                     "other_sense": [k for k, x in _verdicts(a.get("anchors")).items() if x == "other_sense"],
                     "verses_to_add": yes, "judged_verses": len(a1),
                     "missing": a.get("missing") or [], "why": a.get("why")})
    if v2 is not None:
        print(f"the two passes agree on {agree:,} of {judged_both:,} verses ({100 * agree / max(1, judged_both):.1f}%)")
    order = {"thin": 0, "gaps": 1, "full": 2}
    rows.sort(key=lambda r: (order.get(r["grade"], 3), -len(r["verses_to_add"]), -(r["cited"] or 0)))
    # CV_BACKLOG names the file, so a merge of a second sample does not
    # overwrite the first backlog
    dest = OUT / os.environ.get("CV_BACKLOG", "backlog.jsonl")
    dest.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} cards; grades {collections.Counter(r['grade'] for r in rows)}; "
          f"verses to add {sum(len(r['verses_to_add']) for r in rows):,} on {sum(1 for r in rows if r['verses_to_add'])} cards; "
          f"words to drop on {sum(1 for r in rows if r['other_sense'])} cards -> {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    {"run": run, "merge": merge}[sys.argv[1]](*sys.argv[2:])
