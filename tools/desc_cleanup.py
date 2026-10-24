"""Descriptions that talk about the build, rewritten to talk about the text.

2026-10-01, after the UI committee found 670 of 5,635 descriptions
speaking of "the corpus", "the graph", "this record", extraction or the King
James (two clutter items to clean up: 670 descriptions and 'no
scripture behind them' wording). Love's card opened: "'the greatest of these
is love' (1Cor 13:13) -- the corpus ranking its own terms, which it almost
never does ... This record holds no definition."

The rewrite is drafted by a worker (DeepSeek, the entity store is released to
it) in batches, and every draft is checked here before it can be applied:
each scripture reference and each quotation in the old text must survive into
the new, nothing about the build may remain, and the new text may not be
longer. A draft that fails is left out and listed, and the old text stays.

    python tools/desc_cleanup.py select          # list what would be rewritten
    python tools/desc_cleanup.py draft [--n N]   # send batches, keep drafts
    python tools/desc_cleanup.py check           # verify drafts, report
    python tools/desc_cleanup.py apply           # write passing drafts
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTS = ROOT / "ontology" / "entities" / "entities.jsonl"
WORK = ROOT / "out" / "desc-cleanup"
sys.path.insert(0, str(ROOT / "src"))

# what a description must not say once rewritten: the build, not the text
BUILD = re.compile(r"(?i)\bthe corpus\b|\bthe graph\b|\bthis (record|node|entry)\b|"
                   r"\bthe record\b|\bextract|\bKing James\b|\bKJV\b|\bthe store\b|"
                   r"\bnodes?\b|\bthe ontology\b|\bpipeline\b")
# not "edge": the text has the edge of the sea and of the sword
REF = re.compile(r"\b(?:[1-3] ?)?[A-Z][a-z]+\.? \d+:\d+(?:[–-]\d+)?")
# a quotation opens after a space, a bracket or a dash and closes before one
# (an apostrophe inside "Moses's" or "it's" is neither)
QUOTE = re.compile(r"(?:^|(?<=[\s(—]))[‘'“\"]([^‘“\"’”*\n]{12,}?)[’'”\"](?=[\s.,;:)—?!]|$)")
BATCH = 12

BRIEF = """You are editing short descriptions shown on cards in a Bible study app.
Each description below was written in a voice that talks about the database
("the corpus", "the graph", "this record", "this node", extraction, the King James
wording) instead of about the Bible text. Rewrite each one so that it speaks only
about what the text says.

Rules, all required:
1. Keep every scripture reference exactly as written (for example "1Cor 13:13").
2. Keep every quotation of scripture word for word, in its quotation marks.
3. Remove every mention of the corpus, the graph, the record, nodes, edges,
   extraction, the pipeline, the ontology, and of the King James Version or how it
   words things. If a sentence only says something about the database or the
   King James wording, drop the sentence.
4. "The corpus does X" about the Bible itself becomes "the text does X" or
   "Scripture does X" only where the claim is about what the text says.
5. Add nothing: no new claims, no new verses, no doctrine, no application.
6. Plain prose: no asterisks, no markdown, use an em dash (—) not "--".
7. Never longer than the original; shorter is better. Keep paragraph breaks
   only where the original had them.

Return ONLY a JSON object mapping each id to its new description, nothing else.

Descriptions:
"""


def entities():
    return [json.loads(l) for l in ENTS.read_text(encoding="utf-8").splitlines() if l.strip()]


def select():
    return [e for e in entities() if e.get("desc") and BUILD.search(e["desc"])]


def draft(n=None, workers=6):
    from bibleont import delegate
    todo = select()
    WORK.mkdir(parents=True, exist_ok=True)
    done = {p.stem for p in WORK.glob("b*.json")}

    def one(ix_b):
        i, b = ix_b
        task = BRIEF + json.dumps({e["id"]: e["desc"] for e in b}, ensure_ascii=False, indent=1)
        res = delegate.run(task, level=2, label=f"desc-cleanup b{i:03d}", blind=True,
                           effort="off", timeout=300, check_balance=False)
        ans = (res.get("answer") or "").strip()
        m = re.search(r"\{.*\}", ans, re.S)
        try:
            got = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            got = {}
        (WORK / f"b{i:03d}.json").write_text(json.dumps(
            {"ids": [e["id"] for e in b], "drafts": got, "stopped": res.get("stopped"),
             "refused": res.get("refused"), "cost": res.get("cost")},
            ensure_ascii=False, indent=1), encoding="utf-8")
        return i, len(got), res.get("cost") or 0, res.get("stopped") or res.get("refused")

    order = [(i, todo[j:j + BATCH]) for i, j in enumerate(range(0, len(todo), BATCH))
             if f"b{i:03d}" not in done][: n or None]
    total = 0.0
    with cf.ThreadPoolExecutor(workers) as ex:
        for i, k, cost, stop in ex.map(one, order):
            total += cost
            print(f"b{i:03d}: {k} drafts, ${cost:.4f}{'  STOP: ' + str(stop) if stop else ''}")
            if stop:
                print("stopping at the first failed call")
                break
    print(f"spent ${total:.4f}")


RETRY = """Your earlier rewrite of each description below was rejected, for the reason
given beside it. Rewrite each again, following the same rules:
keep every scripture reference and every quotation of scripture word for word;
remove every mention of the corpus, the graph, the record, nodes, extraction,
the pipeline, the ontology, workers, seeding, and the King James Version or its
wording (where a reference is labelled "KJV", keep the reference and drop only
the label); add nothing; plain prose with em dashes; never longer.
If a description is ONLY about how the database was built, return just its
quoted scripture with its reference, or "" if it has none.

Return ONLY a JSON object mapping each id to its new description.

"""


def retry(workers=4):
    """A second pass on the drafts that failed, each sent with its reason."""
    from bibleont import delegate
    ents = {e["id"]: e for e in entities()}
    _ok, bad = check(verbose=False)
    ids = sorted(bad)
    batches = [ids[i:i + 8] for i in range(0, len(ids), 8)]

    def one(ix_b):
        i, b = ix_b
        task = RETRY + json.dumps({x: {"description": ents[x]["desc"], "rejected because": bad[x]}
                                   for x in b}, ensure_ascii=False, indent=1)
        res = delegate.run(task, level=2, label=f"desc-cleanup r{i:03d}", blind=True,
                           effort="off", timeout=300, check_balance=False)
        m = re.search(r"\{.*\}", (res.get("answer") or ""), re.S)
        try:
            got = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            got = {}
        (WORK / f"r{i:03d}.json").write_text(json.dumps(
            {"ids": b, "drafts": got, "stopped": res.get("stopped")}, ensure_ascii=False,
            indent=1), encoding="utf-8")
        return i, len(got), res.get("cost") or 0
    with cf.ThreadPoolExecutor(workers) as ex:
        for i, k, cost in ex.map(one, enumerate(batches)):
            print(f"r{i:03d}: {k} drafts, ${cost:.4f}")


def verify(old, new, hand=False):
    """Why a draft may not replace the old text, or None. A draft written by
    hand (m*.json) was read against its old text when it was written, and drops
    some quotations on purpose (a KJV/ASV comparison, the index's own phrases),
    so only the build talk, the marks and the length are checked for it."""
    if not isinstance(new, str):
        return "empty"
    if not new.strip():
        # emptied: right only for a description with no scripture in it
        return None if not REF.search(old) and not QUOTE.search(old) else "empty"
    # scripture's own words may say "record" ('This is the record of the
    # genealogy', Matt 1:1): only what is outside quotation marks is checked
    bare = QUOTE.sub("", new)
    if BUILD.search(bare):
        return "still talks about the build: " + BUILD.search(bare).group(0)
    if "**" in new or " -- " in new:
        return "markup left"
    if len(new) > len(old) + 10:
        return f"longer ({len(new)} > {len(old)})"
    if hand:
        return None
    sentences = re.split(r"(?<=[.!?])\s+|\n+", old)
    for r in REF.findall(old):
        if r.replace(" ", "") not in new.replace(" ", ""):
            # a reference may go with a sentence that was only about the build
            # ("TO CHECK WHEN STRONG'S LANDS: Romans 3:25 ...")
            home = next((s for s in sentences if r in s), "")
            if BUILD.search(home) or re.search(r"\bTO CHECK\b|Strong's", home):
                continue
            return "lost reference " + r
    for q in QUOTE.findall(old):
        q = q.strip()
        if BUILD.search(q):          # a quoted phrase that was itself build talk
            continue
        if q[:40] not in new:
            return "lost quotation: " + q[:50]
    return None


def check(verbose=True):
    ents = {e["id"]: e for e in entities()}
    ok, bad = {}, {}
    # first drafts, then the second pass: a passing draft is never replaced
    # by a failing one
    for p in sorted(WORK.glob("b*.json")) + sorted(WORK.glob("r*.json")) \
            + sorted(WORK.glob("m*.json")):       # m: written by hand
        b = json.loads(p.read_text(encoding="utf-8"))
        for i in b["ids"]:
            if i in ok or i not in ents:
                continue
            new = (b.get("drafts") or {}).get(i)
            if isinstance(new, dict):      # the second pass echoes the shape it was sent
                new = new.get("description", new.get("new"))
            if isinstance(new, str):       # the marks, mechanically: no judgement in it
                new = re.sub(r"\*\*(.+?)\*\*", r"\1", new)
                new = re.sub(r"(^|[^*\w])\*([^*\n]+?)\*(?![*\w])", r"\1\2", new)
                new = new.replace(" -- ", " — ").replace("--", "—")
            why = verify(ents[i]["desc"], new, hand=p.name.startswith("m")) \
                if new is not None else "no draft"
            if why:
                bad[i] = why
            else:
                ok[i] = new
                bad.pop(i, None)
    if verbose:
        print(f"selected {len(select())}, drafted {len(ok) + len(bad)}, pass {len(ok)}, fail {len(bad)}")
        import collections
        print(collections.Counter(w.split(":")[0].split(" (")[0] for w in bad.values()).most_common())
    return ok, bad


def apply():
    ok, bad = check(verbose=True)
    lines = ENTS.read_text(encoding="utf-8").splitlines()
    out = []
    for l in lines:
        if l.strip():
            e = json.loads(l)
            if e["id"] in ok:
                e["desc"] = ok[e["id"]]
                l = json.dumps(e, ensure_ascii=False, sort_keys=True)
        out.append(l)
    ENTS.write_text("\n".join(out) + "\n", encoding="utf-8")
    (WORK / "failed.json").write_text(json.dumps(bad, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"applied {len(ok)}; {len(bad)} kept as they were (out/desc-cleanup/failed.json)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["select", "draft", "retry", "check", "apply"])
    ap.add_argument("--n", type=int)
    a = ap.parse_args()
    if a.cmd == "select":
        s = select()
        print(len(s))
        for e in s[:8]:
            print(" ", e["id"], "|", BUILD.search(e["desc"]).group(0))
    elif a.cmd == "draft":
        draft(a.n)
    elif a.cmd == "retry":
        retry()
    elif a.cmd == "check":
        check()
    else:
        apply()
