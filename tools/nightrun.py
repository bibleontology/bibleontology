"""An overnight local-model pass: can a 3b reproduce reasoned judgments?

2026-09-10, overnight: a useful ollama run to kick off, with no great concern
about the results since it is free.

Free, so the bar is only that it answer something worth waking up to. Today
established where our computed floor stops:

    instance_of   FORMULAIC   75 of 114 classes separate at >=3x chance,
                              median 6.4x -- repeated wording, which a lexical
                              measure finds because it IS lexical
    likened_to    FIGURATIVE  abraham -> image_dust_and_ashes. No lexical
    draws_on      DEPENDENT   measure reaches these, four separate failures
                              today proved it

So the run tests the boundary rather than wandering: it asks the model to make
the judgments our floor cannot, on the 710 relations where a human already
made them, and scores the answers.

## Part A -- benchmark, and it is scoreable

For each legacy `draws_on` / `likened_to` relation, the model sees the source
verse and FOUR candidate partners: the true one, plus three distractors drawn
from our own allusion layer's top hits for that verse. Those distractors are
deliberately hard -- they are what the floor ranked highly and would have
offered instead.

A score here means something specific: **how often a free local model picks the
reasoned answer out of the floor's own shortlist.** That is the exact job an
overlay would do.

## Part B -- discovery, and it is not scoreable

Our strongest computed links that the legacy graph has no relation for. The
model labels each: quotation, echo, shared formula, or unrelated. Nothing
validates these by morning; they are a triaged queue for a human, and that is
all they are claimed to be.

## Discipline

Output is an OVERLAY: model-produced, marked as such, never merged into the
computed floor. Written incrementally so a crash keeps what ran, and skipping
work already done so it can resume.
"""
from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import math
import pathlib
import random
import re
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "nightrun.jsonl"
OLLAMA = "http://127.0.0.1:11434/api/generate"

BOOK = {"Gen": "Gen", "Exod": "Exo", "Exo": "Exo", "Lev": "Lev", "Num": "Num",
        "Deut": "Deu", "Deu": "Deu", "Josh": "Jos", "Judg": "Jdg",
        "Ruth": "Rut", "1Sam": "1Sa", "2Sam": "2Sa", "1Kgs": "1Ki",
        "2Kgs": "2Ki", "1Chr": "1Ch", "2Chr": "2Ch", "Job": "Job",
        "Ps": "Psa", "Psa": "Psa", "Prov": "Pro", "Eccl": "Ecc", "Isa": "Isa",
        "Jer": "Jer", "Lam": "Lam", "Ezek": "Ezk", "Dan": "Dan", "Hos": "Hos",
        "Joel": "Jol", "Amos": "Amo", "Jonah": "Jon", "Mic": "Mic",
        "Nah": "Nam", "Hab": "Hab", "Zeph": "Zep", "Hag": "Hag",
        "Zech": "Zec", "Mal": "Mal", "Matt": "Mat", "Mark": "Mrk",
        "Luke": "Luk", "John": "Jhn", "Acts": "Act", "Rom": "Rom",
        "1Cor": "1Co", "2Cor": "2Co", "Gal": "Gal", "Eph": "Eph",
        "Phil": "Php", "Col": "Col", "1Thess": "1Th", "2Thess": "2Th",
        "1Tim": "1Ti", "2Tim": "2Ti", "Titus": "Tit", "Phlm": "Phm",
        "Heb": "Heb", "Jas": "Jas", "1Pet": "1Pe", "2Pet": "2Pe",
        "1John": "1Jn", "2John": "2Jn", "3John": "3Jn", "Jude": "Jud",
        "Rev": "Rev", "Neh": "Neh", "Ezra": "Ezr", "Esth": "Est",
        "Song": "Sng", "Obad": "Oba"}
BACK = {v: k for k, v in BOOK.items()}
RX = re.compile(r"^\s*([1-3]?\s?[A-Za-z]+)\s+(\d+):(\d+)")


def parse(x):
    m = RX.match(str(x))
    if not m:
        return None
    b = BOOK.get(m.group(1).replace(" ", ""))
    return f"{b}.{int(m.group(2))}.{int(m.group(3))}" if b else None


def ask(model, prompt, timeout=240):
    body = json.dumps({"model": model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0, "seed": 11,
                                   "num_ctx": 4096}}).encode()
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["response"].strip()


def load_gz(name):
    rows = []
    p = OUT / name
    if not p.exists():
        return rows
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                if not any(k.startswith("_") for k in d):
                    rows.append(d)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model", default="qwen2.5:3b-instruct-q4_K_M")
    ap.add_argument("--benchmark", type=int, default=400)
    ap.add_argument("--discover", type=int, default=1500)
    a = ap.parse_args()

    text = {}
    for line in (ROOT / "data/bible/verses.bsb.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            if "b" in d:
                text[(d["b"], d["c"], d["v"])] = d["t"]

    def say(ref):
        b, c, v = ref.split(".")
        return text.get((BACK.get(b, b), int(c), int(v)), "")

    link = collections.defaultdict(list)
    for name in ("allusions.jsonl.gz", "crosslinks.jsonl.gz"):
        for d in load_gz(name):
            for L in d["links"]:
                link[d["ref"]].append((L["idf"], L["ref"]))
                link[L["ref"]].append((L["idf"], d["ref"]))
    for r in link:
        link[r].sort(reverse=True)

    rels = []
    for f in sorted(glob.glob(str(ROOT / "ontology/relations/*.jsonl"))):
        for line in pathlib.Path(f).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rels.append(json.loads(line))

    done = set()
    if DEST.exists():
        for line in DEST.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    done.add(json.loads(line)["id"])
                except Exception:
                    pass
    print(f"already done: {len(done):,}")

    rng = random.Random(5)
    fh = DEST.open("a", encoding="utf-8")

    # ---- PART A: benchmark ------------------------------------------------
    # A relation's refs are the verses a human cited for it, so any of them is
    # a defensible answer and so is any verse the same two nodes touch
    # elsewhere. Both go in `ok`; neither may be offered as a distractor.
    touch = collections.defaultdict(set)
    for r in rels:
        got = {parse(x) for x in (r.get("refs") or [])} - {None}
        touch[r["src"]] |= got
        touch[r["dst"]] |= got

    cases = []
    for r in rels:
        if r["type"] not in ("draws_on", "likened_to"):
            continue
        refs = [parse(x) for x in (r.get("refs") or [])]
        refs = [x for x in refs if x and say(x)]
        # TWO refs, NOT one. With one ref the source verse and the answer are
        # the same verse, and the question degenerates to "which of these four
        # lines is the line I just showed you" -- 184 of 400 cases on the
        # 2026-09-10 run, scoring 67% on text identity and measuring nothing.
        if len(refs) < 2:
            continue
        src = refs[0]
        ok = set(refs) | touch.get(r["src"], set()) | touch.get(r["dst"], set())
        alts = [t for _, t in link.get(src, [])[:12] if t not in ok and say(t)]
        if len(alts) < 3:
            continue
        cases.append((r, src, refs, alts[:3]))
    rng.shuffle(cases)
    cases = cases[:a.benchmark]
    print(f"PART A benchmark cases: {len(cases)}")

    hit = seen = 0
    t0 = time.time()
    for i, (r, src, refs, alts) in enumerate(cases):
        cid = f"A:{r['type']}:{r['src']}:{r['dst']}:{src}"
        if cid in done:
            continue
        truth = refs[-1] if len(refs) > 1 else refs[0]
        opts = alts + [truth]
        rng.shuffle(opts)
        letters = "ABCD"
        body = "\n".join(f"{letters[j]}. {o} — {say(o)[:110]}"
                         for j, o in enumerate(opts))
        kind = ("draws on (depends on, develops, or alludes to)"
                if r["type"] == "draws_on" else
                "is likened to (uses as an image or metaphor)")
        p = (f"VERSE: {src} — {say(src)[:150]}\n\nCANDIDATES:\n{body}\n\n"
             f"Which candidate does the verse {kind}?\n"
             f"Answer with one letter only.")
        try:
            ans = ask(a.model, p)
        except Exception as e:
            fh.write(json.dumps({"id": cid, "part": "A",
                                 "error": str(e)[:80]}) + "\n")
            fh.flush()
            continue
        got = next((ch for ch in ans.upper() if ch in letters), "?")
        pick = opts[letters.index(got)] if got in letters else None
        ok = pick == truth
        hit += ok
        seen += 1
        fh.write(json.dumps({"id": cid, "part": "A", "type": r["type"],
                             "src": src, "truth": truth, "pick": pick,
                             "correct": ok,
                             "note": (r.get("note") or "")[:120]},
                            ensure_ascii=False) + "\n")
        fh.flush()
        if seen % 25 == 0:
            el = time.time() - t0
            print(f"  A {seen}/{len(cases)}  {hit}/{seen} = "
                  f"{100*hit/max(seen,1):.0f}%   {el/max(seen,1):.1f}s/case",
                  flush=True)
    print(f"PART A done: {hit}/{seen} = {100*hit/max(seen,1):.1f}%")

    # ---- PART B: discovery ------------------------------------------------
    known = set()
    for r in rels:
        refs = [parse(x) for x in (r.get("refs") or [])]
        for x in refs:
            if x:
                known.add(x)
    flat = sorted(((m, s, t) for s, v in link.items() for m, t in v),
                  reverse=True)
    seenpair = set()
    todo = []
    for m, s, t in flat:
        k = tuple(sorted((s, t)))
        if k in seenpair or s in known or not say(s) or not say(t):
            continue
        seenpair.add(k)
        todo.append((m, s, t))
        if len(todo) >= a.discover:
            break
    print(f"\nPART B discovery candidates: {len(todo)}")

    t0 = time.time()
    for i, (m, s, t) in enumerate(todo):
        cid = f"B:{s}:{t}"
        if cid in done:
            continue
        p = (f"TEXT 1: {s} — {say(s)[:150]}\n"
             f"TEXT 2: {t} — {say(t)[:150]}\n\n"
             f"How are these two related?\n"
             f"A. One quotes the other\n"
             f"B. One echoes the other's wording without quoting\n"
             f"C. Both use a shared stock phrase or formula\n"
             f"D. Not meaningfully related\n\n"
             f"Answer with one letter only.")
        try:
            ans = ask(a.model, p)
        except Exception as e:
            fh.write(json.dumps({"id": cid, "part": "B",
                                 "error": str(e)[:80]}) + "\n")
            fh.flush()
            continue
        got = next((ch for ch in ans.upper() if ch in "ABCD"), "?")
        fh.write(json.dumps({"id": cid, "part": "B", "a": s, "b": t,
                             "idf": m, "label": got},
                            ensure_ascii=False) + "\n")
        fh.flush()
        if (i + 1) % 50 == 0:
            el = time.time() - t0
            print(f"  B {i+1}/{len(todo)}   {el/max(i+1,1):.1f}s/case",
                  flush=True)
    fh.close()
    print(f"\nwrote {DEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
