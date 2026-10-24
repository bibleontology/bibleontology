"""THE GENERICS, CHECKED AGAINST THE TEXT'S OWN WORDS (plan 1.41;
2026-10-18: options 2 and 3 approved, then 2 built out as well).

The resolution pass named 1,515 groups and people the text describes without
a name, one per chapter ("the twelve disciples", Matthew 20). The plan, as
approved (P-2026-10-17-5): "each generic ... is checked against the groups
the text names near it: the same group links to the text's own word ('the
twelve', Matthew 20:17, for Matthew 20:18's 'we'); a part of a group ('one of
his disciples') stays generic and links to the group; otherwise it stays as
it is. Candidates by structure, decided by a judged question (Haiku),
credited as a reading."

  - CANDIDATES BY STRUCTURE: nouns in the generic's chapter, from five verses
    before its first use up to that use, whose gloss is a word of its label
    (the divine words left out).
  - THE QUESTION: same, part_of, or neither, with the candidate named.
    Unresolved is better than wrong: low confidence counts as neither.
  - THE ANSWERS are readings, written to out/sweep/generic-links.jsonl and
    never merged into the layer they read.

    python tools/sweep/generic_check.py candidates            # how many, no calls
    python tools/sweep/generic_check.py run <run> [Book.ch ...]
    python tools/sweep/generic_check.py merge <run>
"""
import collections
import concurrent.futures as cf
import gzip
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import context as C  # noqa: E402
import headless as H  # noqa: E402

OUT = ROOT / "out"
GENERICS = OUT / "sweep" / "runs" / "resolve-1" / "generics.json"
MODEL = "claude-haiku-5-5"
WORKERS = int(os.environ.get("GC_WORKERS", "8"))
CHUNK = 15
STOP = {"the", "a", "an", "of", "from", "to", "in", "on", "into", "for", "with", "by", "and", "his", "her",
        "their", "your", "my", "our", "its", "all", "this", "that", "these", "those", "who", "whom", "which",
        "one", "some", "other", "others", "another", "there", "were", "was", "had", "have", "been", "be", "is"}
DIVINE = {"2316", "430", "433", "410", "3068", "3069", "136", "2962", "3050", "426"}
LOCK = threading.Lock()
state = {"fails": 0, "lost": 0, "stop": None}

TASK = """You are checking people and groups that an earlier reading of the Bible named in its own words,
because the verse did not name them: "the twelve disciples", "a blind man sitting beside the road". For
each, the words of the text nearby that might name the same people are listed as CANDIDATES.

For each generic, decide ONE:
- "same": the generic is the very group or person the text names at that candidate word (the twelve
  disciples of Matthew 20:18 are "the twelve" Jesus took aside in 20:17).
- "part_of": the generic is some of, or one of, the group the text names there ("one of his disciples"
  is part of "his disciples").
- "neither": none of the candidates names them, or the text does not make it plain.

Rules:
- UNRESOLVED IS BETTER THAN WRONG (the owner's rule). Choose "same" or "part_of" only where the verses
  make it plain. A word that merely matches ("men", "people") is not enough: it must be the same people.
- Name the candidate by its id. Keep each `why` to about a dozen words.

Answer with ONLY this JSON object:
{"answers": [{"generic": "<generic id>", "decision": "same|part_of|neither", "candidate": "<candidate id or null>", "confidence": "high|medium|low", "why": "..."}]}

"""


# THE RECHECK'S ADDED RULE (marks by hand, 2026-10-18): Revelation 16:8's
# "the fourth angel" was answered "neither" though "the fourth" (τέταρτος) was
# offered; the Greek has no "angel" there. James 2:2's poor man is πτωχός
# alone. 69 of the 324 "neither" answers had such a candidate.
ADJ_RULE = """- The original often names someone by a describing word or a number ALONE, the noun left implied:
  "the fourth" (Revelation 16:8, where the English adds "angel"), "a poor one" (James 2:2), "a holy one"
  (Daniel 8:13), "the Jews". Such a candidate can be the very person or group: judge it as you would a noun.
"""


def singular(w):
    return w[:-1] if w.endswith("s") and not w.endswith("ss") and len(w) > 3 else w


def content(text):
    return {singular(w) for w in re.findall(r"[a-z]+", (text or "").lower()) if w not in STOP and len(w) > 2}


def load():
    gens = json.loads(GENERICS.read_text(encoding="utf-8"))
    nouns = collections.defaultdict(list)          # ref -> [(id, text, original, heads)]
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("word") and d.get("class") in ("noun", "adj", "num"):
                s = re.sub(r"\D", "", str(d.get("strong") or "")).lstrip("0")
                if s in DIVINE:
                    continue
                nouns[d["ref"]].append((d["id"], d.get("text"), d.get("original"), content(d.get("text"))))
    uses = collections.defaultdict(list)           # generic -> refs where the layer uses it
    with gzip.open(OUT / "sweep-layer.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("type") == "refers_to" and str(d.get("dst", "")).count("#generic:") and d.get("action") != "remove":
                uses[d["dst"]].append(d["ref"])
    return gens, nouns, uses


def head_of(label):
    """The label's head: its last word before the first "of / who / which /
    that / from / in / at / to" or "-ing" word. "the elders of Israel" ->
    elder; "the men who came to David" -> men; "a blind man sitting beside the
    road" -> man. Matching any word of the label let every "Israel" and every
    "David" in (first count, 2026-10-18)."""
    ws = re.findall(r"[a-z]+", (label or "").lower())
    cut = []
    for w in ws:
        if w in ("of", "who", "whom", "which", "that", "from", "in", "at", "to", "with", "on") or \
                (w.endswith("ing") and len(w) > 4):
            break
        cut.append(w)
    keep = [w for w in cut if w not in STOP and len(w) > 2]
    # every word before the cut, not only the last: "the twelve disciples"
    # must keep "twelve", all Matthew 20:17's Greek says (τοὺς δώδεκα)
    return {singular(w) for w in keep} if keep else content(label)


def candidates(g, nouns):
    b, c, v = g["first"].split(".")
    want = head_of(g["label"])
    out = []
    for vv in range(max(1, int(v) - 5), int(v) + 1):
        ref = f"{b}.{c}.{vv}"
        for nid, text, orig, heads in nouns.get(ref, ()):
            if heads & want:
                out.append({"id": nid, "word": text, "original": orig, "verse": ref})
    return out[-6:]                                 # the nearest six


def work(only=None):
    gens, nouns, uses = load()
    items = []
    for g in gens:
        ch = g["first"].rsplit(".", 1)[0]
        if only and ch not in only:
            continue
        cands = candidates(g, nouns)
        if cands:
            items.append((g, cands, sorted(set(uses.get(g["id"], [])))[:3]))
    return items, len(gens)


def prompt(name, batch, bsb):
    gens = []
    for g, cands, used in batch:
        verses = sorted({c["verse"] for c in cands} | set(used) | {g["first"]},
                        key=lambda r: [int(x) if x.isdigit() else 0 for x in r.split(".")[1:]])
        gens.append({"generic": g["id"], "label": g["label"], "first_used": g["first"], "used_in": used,
                     "candidates": cands,
                     "verses": [{"ref": r, "text": bsb(r)[1]} for r in verses]})
    return TASK + json.dumps({"batch": name, "generics": gens}, ensure_ascii=False, separators=(",", ":")) + "\n"


def log(run, msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    print(line, flush=True)
    with LOCK, open(run / "_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def judge(run, name, batch, text):
    out = run / f"G-{name}.json"
    if out.exists() or state["stop"]:
        return
    ids = {g["id"] for g, _c, _u in batch}
    for attempt in range(3):
        if (run / "STOP").exists():
            state["stop"] = "STOP file"
            return
        t0 = time.time()
        res, err = H.call(text, MODEL)
        blob = json.dumps(res or {}) + (err or "")
        if (res is None or res.get("is_error")) and "limit" in blob.lower():
            log(run, f"{name}: usage limit; waiting 10 minutes")
            time.sleep(600)
            continue
        if res is None or res.get("is_error"):
            with LOCK:
                state["fails"] += 1
                bad = state["fails"]
            log(run, f"{name}: call failed")
            if bad >= 5:
                state["stop"] = "5 failed calls in a row"
                log(run, f"STOPPING: {state['stop']}")
                return
            continue
        with LOCK:
            state["fails"] = 0
        u = res.get("usage") or {}
        toks = sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                             "cache_creation_input_tokens"))
        with LOCK, open(run / "_ledger.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"batch": name, "generics": len(batch), "tokens": toks,
                                "seconds": round(time.time() - t0)}) + "\n")
        ans = H.parse(res)
        got = {a.get("generic") for a in (ans or {}).get("answers") or []
               if a.get("decision") in ("same", "part_of", "neither")}
        if ans and len(got & ids) >= 0.9 * len(ids):
            out.write_text(json.dumps(ans, ensure_ascii=False, indent=1), encoding="utf-8")
            log(run, f"{name}: {len(batch)} generics, {len(got & ids)} answered, {toks:,} tokens")
            return
        log(run, f"{name}: answer incomplete ({len(got & ids)} of {len(ids)}), attempt {attempt + 1}")
    with LOCK:
        state["lost"] += 1
    log(run, f"{name}: LOST after 3 attempts")
    if state["lost"] >= 10:
        state["stop"] = "10 batches lost"


def run_cmd(name, only):
    H.stay_awake()
    run = OUT / "sweep" / "runs" / name
    run.mkdir(parents=True, exist_ok=True)
    items, n = work(only)
    bsb = C._bsb()
    batches = [(f"B{i // CHUNK + 1:03d}", items[i:i + CHUNK]) for i in range(0, len(items), CHUNK)]
    log(run, f"start: {len(items)} generics with candidates (of {n}), {len(batches)} batches, {WORKERS} at a time, {MODEL}")
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        futs = [ex.submit(judge, run, nm, b, prompt(nm, b, bsb)) for nm, b in batches]
        for f in futs:
            f.result()
    log(run, f"end: {state['stop'] or 'all batches done'}")


def merge(name):
    run = OUT / "sweep" / "runs" / name
    items, n = work()
    cand_ok = {(g["id"], c["id"]) for g, cs, _u in items for c in cs}
    st = collections.Counter()
    rows = []
    answers = {}
    for p in sorted(run.glob("G-*.json")):
        for a in json.loads(p.read_text(encoding="utf-8")).get("answers") or []:
            answers[a.get("generic")] = a
    # THE RECHECK, where it ran, answers over the first: the "neither"s that had
    # a describing-word candidate, asked again with ADJ_RULE
    redo = OUT / "sweep" / "runs" / f"{name}-recheck"
    for p in sorted(redo.glob("G-*.json")) if redo.exists() else []:
        for a in json.loads(p.read_text(encoding="utf-8")).get("answers") or []:
            if a.get("generic") in answers:
                answers[a["generic"]] = {**a, "rechecked": True}
                st["rechecked"] += 1
    for a in answers.values():
        d, cid = a.get("decision"), a.get("candidate")
        if d in ("same", "part_of") and (a.get("generic"), cid) not in cand_ok:
            st["named a candidate it was not offered (neither)"] += 1
            d = "neither"
        if d in ("same", "part_of") and a.get("confidence") == "low":
            st["low confidence (neither, guess kept)"] += 1
            a["low_guess"], d = d, "neither"
        st[d] += 1
        rows.append({"generic": a.get("generic"), "decision": d, "candidate": cid if d != "neither" else None,
                     **({"low_guess": a["low_guess"], "low_candidate": cid} if a.get("low_guess") else {}),
                     **({"rechecked": True} if a.get("rechecked") else {}),
                     "confidence": a.get("confidence"), "why": a.get("why"),
                     "reading": "generic check", "by": "generic check (Claude Haiku 5.5)"})
    dest = OUT / "sweep" / "generic-links.jsonl"
    dest.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} answers -> {dest.relative_to(ROOT)}:", dict(st))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "candidates"
    if cmd == "candidates":
        items, n = work()
        print(f"{len(items)} of {n} generics have candidates; "
              f"{sum(len(c) for _g, c, _u in items)} candidates")
        for g, cs, used in items[:6]:
            print(" ", g["id"], "|", g["label"], "->", [(c["word"], c["verse"]) for c in cs][:4])
        mat = next((x for x in items if x[0]["id"].startswith("Mat.20#generic:the-twelve")), None)
        print("Matthew 20's twelve:", mat and [(c["word"], c["verse"]) for c in mat[1]])
    elif cmd == "run":
        run_cmd(sys.argv[2], set(sys.argv[3:]) or None)
    elif cmd == "recheck":
        # the "neither" answers that had a describing-word or number candidate,
        # asked again with ADJ_RULE; merged over the first answers
        global TASK
        TASK = TASK.replace("- Name the candidate by its id.", ADJ_RULE + "- Name the candidate by its id.")
        first = {json.loads(x)["generic"]: json.loads(x) for x in
                 (OUT / "sweep" / "generic-links.jsonl").read_text(encoding="utf-8").splitlines()}
        items, _n = work()
        ids = {c["id"] for _g, cs, _u in items for c in cs}
        cls = {}
        with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                if d["id"] in ids:
                    cls[d["id"]] = d.get("class")
        again = [(g, cs, u) for g, cs, u in items if (first.get(g["id"]) or {}).get("decision") == "neither"
                 and any(cls.get(c["id"]) in ("adj", "num") for c in cs)]
        run = OUT / "sweep" / "runs" / sys.argv[2]
        run.mkdir(parents=True, exist_ok=True)
        bsb = C._bsb()
        batches = [(f"R{i // CHUNK + 1:03d}", again[i:i + CHUNK]) for i in range(0, len(again), CHUNK)]
        log(run, f"recheck: {len(again)} 'neither' answers with a describing-word candidate, {len(batches)} batches")
        H.stay_awake()
        with cf.ThreadPoolExecutor(WORKERS) as ex:
            for f in [ex.submit(judge, run, nm, b, prompt(nm, b, bsb)) for nm, b in batches]:
                f.result()
    elif cmd == "merge":
        merge(sys.argv[2])


if __name__ == "__main__":
    main()
