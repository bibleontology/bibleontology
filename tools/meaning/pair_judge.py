"""Flash judges whether two matched verses say the same thing (P-52 follow-on).

2026-09-29, chosen then: run the 60-pair Flash test. The
structure proposes matches; on the blind hand grades of 60 that pass the
checklist, 22% were a clear yes and 32% no, and the scores of the two
overlap (10-16 both). Candidates, then judgment: a focused question per
pair, blind, with each verse's section heading and the verses either side.

The worker sees only the Berean text (public domain). The hand grades are the
answer key and are never in the brief.

Tested on those 60: Flash caught 18 of the 19 nos; shown only where it said
same or partly, 1 wrong in 26 (measured 2026-09-29). The run was approved.

    python tools/meaning/pair_judge.py --test   -> out/pair-judge/test.json + tally
    python tools/meaning/pair_judge.py --run    -> out/pair-judge/run/<n>.json (resumable)
                                                   then out/pair-judgments.jsonl.gz
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "pair-judge"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
from bibleont import delegate  # noqa: E402

MIN_SCORE, WORKERS, BUDGET = 10.0, 8, 7.0

PER_CALL = 10
HEAD = """Below are pairs of Bible verses (Berean Standard Bible, public domain). Each verse is shown with the heading of the section it stands in and, in brackets, the verse before and after it, so you can read it in context.

A search matched each pair because the two verses share a verb and its object. Many such matches are accidents: the same words used about different things. Your task is to judge, for EACH pair, whether the two verses SAY THE SAME THING:

  same    - the same claim, command, promise, warning, law, prayer, refrain or scene, said again (in other words or the same ones); a reader of one would want to be shown the other
  partly  - the same theme or subject, or one part of what the other says, but not the same statement
  no      - the shared words are used about different things; a reader of one gains nothing from the other

Judge the meaning in context, not the shared words. Give a confidence for each: high, medium or low. Your answers are scored: 3 points for a correct high answer, 2 for a correct medium and 1 for a correct low; you lose 10 points for a wrong high answer and 3 for a wrong medium, and nothing for a wrong low one.

Return ONLY this JSON:
{"judgments": [{"pair": "<id>", "verdict": "<same|partly|no>", "confidence": "<high|medium|low>", "reason": "<one short sentence>"}]}

"""


def verse_block(x):
    ctx = lambda s: f" [{s}]" if s else ""   # noqa: E731
    return (f"  ({x['head']})\n  {ctx(x['before'])}\n  {x['ref']}: {x['text']}\n  {ctx(x['after'])}"
            if x.get("head") else f"  {ctx(x['before'])}\n  {x['ref']}: {x['text']}\n  {ctx(x['after'])}")


def brief(items):
    body = "\n".join(f"PAIR {it['id']}\n A:\n{verse_block(it['a'])}\n B:\n{verse_block(it['b'])}\n"
                     for it in items)
    return HEAD + body


def parse(answer):
    m = re.search(r'\{\s*"judgments"', answer or "")
    if not m:
        return []
    try:
        return json.JSONDecoder().raw_decode(answer[m.start():])[0].get("judgments", [])
    except json.JSONDecodeError:
        # a malformed answer (an unescaped quote in a reason ended the first
        # full run at call 3,784): keep each judgment that reads on its own
        out = []
        for x in re.finditer(r'\{[^{}]*"pair"[^{}]*\}', answer):
            try:
                out.append(json.loads(x.group(0)))
            except json.JSONDecodeError:
                pass
        return out


def candidates():
    """Every 'says the same thing' verse pair the reader could show: a clause
    pair of 10+ that passes the trimming checklist, best clause pair per
    verse pair, in canon-stable order."""
    verdict = {}
    for l in gzip.open(ROOT / "out" / "trim.jsonl.gz", "rt", encoding="utf-8"):
        t = json.loads(l)
        if "from" in t:
            verdict[(t["from"], t["to"])] = t["verdict"]
    best = {}
    for l in gzip.open(ROOT / "out" / "aligned.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(l)
        if r.get("tier") != "same" or r["score"] < MIN_SCORE:
            continue
        if verdict.get((r["from"], r["to"])) != "keep":
            continue
        k = tuple(sorted((r["from"].split("#")[0], r["to"].split("#")[0])))
        if k[0] != k[1] and (k not in best or r["score"] > best[k]):
            best[k] = r["score"]
    return sorted(best)


def run():
    from det_pairs_review import bsb
    from event_profiles import OSIS, MAC
    back = dict(zip(MAC, OSIS))
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8")).get("moved") or {}

    def verse(v):
        e = moved.get(v, v)
        b, c, n = e.split(".")
        txt, head = bsb(back.get(b, b))
        c, n = int(c), int(n)
        return {"ref": f"{back.get(b, b)} {c}:{n}", "text": txt.get((c, n), ""),
                "head": head.get((c, n), ""), "before": txt.get((c, n - 1), ""),
                "after": txt.get((c, n + 1), "")}

    pairs = candidates()
    dest = OUT / "run"
    dest.mkdir(parents=True, exist_ok=True)
    batches = [pairs[i:i + PER_CALL] for i in range(0, len(pairs), PER_CALL)]
    todo = [i for i in range(len(batches)) if not (dest / f"{i}.json").exists()]
    print(f"{len(pairs):,} pairs, {len(batches):,} calls, {len(todo):,} to do", flush=True)
    lock, state = threading.Lock(), {"cost": 0.0, "done": 0, "fail_run": 0, "stop": ""}

    def one(i):
        if state["stop"]:
            return
        items = []
        for j, (a, b) in enumerate(batches[i]):
            items.append({"id": f"q{j}", "a": verse(a), "b": verse(b)})
        r = delegate.run(brief(items), 1, label=f"pair-judge {i}", blind=True,
                         timeout=180, check_balance=False)
        got = {j.get("pair"): j for j in parse(r.get("answer"))}
        out = []
        for j, (a, b) in enumerate(batches[i]):
            g = got.get(f"q{j}")
            if g and g.get("verdict") in ("same", "partly", "no"):
                out.append({"a": a, "b": b, "verdict": g["verdict"],
                            "confidence": g.get("confidence"), "reason": g.get("reason", "")})
        with lock:
            state["cost"] += r.get("cost") or 0
            if r.get("refused") or (r.get("stopped") and "cap" in (r.get("stopped") or "")):
                state["stop"] = r.get("refused") or r["stopped"]
            if len(out) >= len(batches[i]) - 1:        # one missing is retried on resume
                (dest / f"{i}.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
                state["fail_run"] = 0
            else:
                state["fail_run"] += 1
                print(f"  call {i}: {len(out)} of {len(batches[i])} judged "
                      f"({r.get('stopped') or 'unreadable'})", flush=True)
                if state["fail_run"] >= 8:
                    state["stop"] = "8 failed calls in a row"
            state["done"] += 1
            if state["cost"] >= BUDGET:
                state["stop"] = f"budget ${BUDGET:.2f} reached"
            if state["done"] % 250 == 0:
                print(f"  {state['done']:,}/{len(todo):,} calls · ${state['cost']:.2f}", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(one, todo))
    print(f"done: {state['done']:,} calls, ${state['cost']:.2f}, {(time.time() - t0) / 60:.0f} min"
          + (f"; STOPPED: {state['stop']}" if state["stop"] else ""), flush=True)
    collect(dest)


def collect(dest):
    rows, tally = [], collections.Counter()
    for f in sorted(dest.glob("*.json")):
        for r in json.loads(f.read_text(encoding="utf-8")):
            rows.append(r)
            tally[r["verdict"]] += 1
    with gzip.open(ROOT / "out" / "pair-judgments.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"_note": "Whether two matched verses say the same thing: DeepSeek "
                             "Flash, blind, with each verse's context (tools/meaning/pair_judge.py). "
                             "A reading, shown as one.",
                             "_reader": "DeepSeek Flash (pair judgment, unreviewed)"}) + "\n")
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows):,} judgments: " + ", ".join(f"{k} {v:,}" for k, v in tally.most_common()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--count", action="store_true")
    a = ap.parse_args()
    if a.count:
        print(f"{len(candidates()):,} pairs")
        return
    if a.run:
        run()
        return
    if not a.test:
        raise SystemExit("--test, --run or --count")
    page = (ROOT / "docs" / "review" / "det-pairs-test.html").read_text(encoding="utf-8")
    items = json.loads(re.search(r"const DATA=(\[.*?\]);\n", page, re.S).group(1))
    OUT.mkdir(parents=True, exist_ok=True)
    groups = [items[i:i + PER_CALL] for i in range(0, len(items), PER_CALL)]

    def one(g):
        r = delegate.run(brief(g), 1, label=f"pair-judge test {g[0]['id']}", blind=True,
                         timeout=180, check_balance=False)
        return r
    with ThreadPoolExecutor(3) as ex:
        results = list(ex.map(one, groups))
    got, cost = {}, 0.0
    for r in results:
        cost += r.get("cost") or 0
        if r.get("refused") or r.get("stopped"):
            print("stopped:", r.get("refused") or r.get("stopped"))
        for j in parse(r.get("answer")):
            got[j.get("pair")] = j
    (OUT / "test.json").write_text(json.dumps(got, ensure_ascii=False, indent=1), encoding="utf-8")
    key = json.loads((ROOT / "docs" / "review" / "det-pairs-grades.json").read_text(encoding="utf-8"))["grades"]
    norm = {"same": "yes", "yes": "yes", "partly": "partly", "no": "no"}
    conf = {}
    for it in items:
        j = got.get(it["id"]) or {}
        k = (key.get(it["id"]), norm.get(j.get("verdict"), "-"), j.get("confidence", "-"))
        conf[k] = conf.get(k, 0) + 1
    print(f"{len(got)} of {len(items)} judged; ${cost:.4f}")
    print("Doug  | Flash  | confidence | n")
    for k in sorted(conf):
        print(f"{k[0]:6} | {k[1]:6} | {k[2]:6} | {conf[k]}")


if __name__ == "__main__":
    main()
