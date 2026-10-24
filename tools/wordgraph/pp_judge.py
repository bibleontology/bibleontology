"""THE JUDGED PASS OVER PREPOSITIONAL PHRASES (plan 2.13, second step;
2026-10-17: start the job).

The 70,936 phrases no certain rule could name (prep_phrases.py) go to a small
model a passage at a time, with the verse in English and each phrase's
original words, preposition, object and attachment. It chooses ONE relation
from a closed list, or "none". Unresolved is better than wrong
(2026-10-16), and the instructions say so. The answers are readings, kept in
out/ only; the list's names are provisional until they are ruled on by hand.

The machinery is the sweep's (tools/sweep/headless.py): the Claude Code CLI in
print mode, no tools, the display held awake, breakers on failed calls and
lost chunks, waits at a usage limit.

    python tools/wordgraph/pp_judge.py <run> [Book.chapter ...]   (default: the whole Bible)
    python tools/wordgraph/pp_judge.py <run> --ids <file.json>    (only these phrase ids)
"""
import collections
import concurrent.futures as cf
import gzip
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
import context as C  # noqa: E402
import headless as H  # noqa: E402

SRC = ROOT / "out" / "wordgraph" / "prep-phrases.jsonl.gz"
MODEL = "claude-haiku-5-5"
WORKERS = int(os.environ.get("PP_WORKERS", "16"))
CHUNK = 60                     # phrases per call
REJUDGE_CHUNK = 40             # a re-judge's phrases per call, across a book's chapters
LOCK = threading.Lock()
state = {"fails": 0, "lost": 0, "stop": None}

RELATIONS = {
    "place": "where something is or happens (in the house, on the mountain, among the people)",
    "direction": "toward or into a place or person, as the goal of a movement (went to Egypt, came into the house)",
    "source": "from, out of: where something or someone comes from, or is separated from",
    "recipient": "the one to whom something is given, said, shown or done (said to him, gave to them)",
    "beneficiary": "for whose sake or good something is done (for you, on behalf of the people)",
    "possession": "belonging to someone (the field belonging to Boaz, a psalm of David as authorship)",
    "means": "the thing used to do it, or the means by which it is done (with a sword, by the hand of)",
    "manner": "how it is done (with all your heart, in righteousness, with joy)",
    "agent": "by whom something is done, with a passive verb (was spoken by the prophet)",
    "time": "when, or for how long (in the morning, after three days, until evening)",
    "purpose": "the aim of the act (for an offering, for a witness)",
    "cause": "because of what (because of their sin)",
    "reference": "about, concerning, with regard to (spoke about him)",
    "opposition": "against (fought against Israel, sinned against the LORD)",
    "authority": "over: rule or charge over someone (king over Israel)",
    "presence": "before, in the presence of (stood before the LORD)",
    "partitive": "some of, one of (one of the mountains, some of the people)",
    "extent": "as far as, up to, a limit in space or amount (as far as Dan)",
    "comparison": "than, like, as (better than, like a lion)",
    "accompaniment": "together with someone (went with him)",
    "none": "no relation above fits plainly, or the text leaves it open",
}

TASK = """You are reading prepositional phrases in the Bible, in the original Hebrew or Greek, to say what each
phrase adds to its clause. A rule has already found each phrase, its preposition, its object and what it
attaches to. For each phrase, choose ONE relation from RELATIONS, or "none".

Rules:
- UNRESOLVED IS BETTER THAN WRONG (the owner's rule). Choose a relation only where the verse makes it plain.
  If two relations are open, choose "none" and say which two in `why`.
- Decide from the original's preposition and the sense of the verse, not from the English word alone: the
  same English "to" can be direction, recipient or purpose.
- A phrase that attaches to a noun says something about that noun (possession, partitive, place, source...).
- Answer every phrase once, by its id. Keep each `why` to about a dozen words.

Answer with ONLY this JSON object:
{"answers": [{"id": "<phrase id>", "relation": "<one of RELATIONS>", "confidence": "high|medium|low", "why": "..."}]}

"""


# THE TWO-LEVEL SCHEMA (PP_SCHEMA=2; 2026-10-18: options 2 and
# 3 approved, the re-judge offered as 2.13's optional step). Families over types, as
# ruled 2026-10-17 and approved on the 1.2.0 sheet: the judge names a TYPE
# where it is sure, else the FAMILY, else none. The first run's 20 names stay
# above, so it can be reproduced.
SCHEMA = os.environ.get("PP_SCHEMA", "1")
if SCHEMA == "2":
    _pr = json.loads((ROOT / "ontology" / "schema" / "prep_relations.json").read_text(encoding="utf-8"))
    RELATIONS = {}
    for _fam, _f in _pr["families"].items():
        RELATIONS[_fam] = f"FAMILY: {_f['means']} (name it when you know the family but not which of its types)"
        for _t, _d in _f["types"].items():
            RELATIONS[_t] = f"{_fam} / {_d}"
    RELATIONS["none"] = "no relation above fits plainly, or the text leaves it open"
    TASK = TASK.replace(
        "For each phrase, choose ONE relation from RELATIONS, or \"none\".",
        "For each phrase, choose ONE name from RELATIONS, or \"none\". RELATIONS has two levels: six FAMILIES, "
        "each with its TYPES (a type's description begins with its family). Name the TYPE where the verse makes "
        "it plain; where you are sure of the family but not the type, name the FAMILY; otherwise \"none\".").replace(
        "- A phrase that attaches to a noun",
        "- `sphere` (in Christ, in the Spirit) is a reading of where something is said to be true, defined only by the\n"
        "  grammar: use it only where no other type fits, and say so in `why`.\n"
        "- `authority` is by whose authority an act is done (in the name of the LORD); `dominion` is rule over\n"
        "  someone (king over Israel). `target` is the one something comes or falls upon, with nothing handed over;\n"
        "  `recipient` is the one something is given, said or shown to.\n"
        "- A phrase that attaches to a noun")


def chunks(only=None, ids=None):
    """A chapter's open phrases, CHUNK at a time. With `ids` (a re-judge of
    named phrases), a book's listed phrases REJUDGE_CHUNK at a time across its
    chapters: 10,848 phrases in 1,031 chapters would otherwise be ~1,031
    small calls, each paying the instructions in full."""
    by_ch = collections.defaultdict(list)
    with gzip.open(SRC, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            d = json.loads(line)
            b, c, _v = d["ref"].split(".")
            if only and f"{b}.{c}" not in only:
                continue
            for p in d["pp"]:
                if ids is not None:
                    if p["id"] in ids:
                        by_ch[(b, 0)].append((d["ref"], p))
                elif not p["relation"]:
                    by_ch[(b, int(c))].append((d["ref"], p))
    size = REJUDGE_CHUNK if ids is not None else CHUNK
    for (b, c), items in by_ch.items():
        for i in range(0, len(items), size):
            yield (f"{b}.r{i // size + 1}" if ids is not None else f"{b}.{c}.{i // size + 1}"), items[i:i + size]


def prompt(name, items, bsb):
    verses = {}
    for ref, _p in items:
        if ref not in verses:
            verses[ref] = bsb(ref)[1]
    phrases = [{"id": p["id"], "verse": ref, "original": p["text"], "word_by_word": p["gloss"],
                "preposition": f"{p['prep']['l']} ({p['prep']['g']})",
                "object": (p["object"] or {}).get("g"), "attaches_to": p["attaches"]} for ref, p in items]
    return TASK + json.dumps({"passage": name, "RELATIONS": RELATIONS,
                              "verses": [{"ref": r, "text": t} for r, t in verses.items()],
                              "phrases": phrases}, ensure_ascii=False, separators=(",", ":")) + "\n"


def log(run, msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    print(line, flush=True)
    with LOCK, open(run / "_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def judge(run, name, items, text):
    out = run / f"J-{name}.json"
    if out.exists() or state["stop"]:
        return
    ids = {p["id"] for _r, p in items}
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
        toks = sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        with LOCK, open(run / "_ledger.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"chunk": name, "phrases": len(items), "tokens": toks, "seconds": round(time.time() - t0),
                                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}) + "\n")
        ans = H.parse(res)
        got = {a.get("id") for a in (ans or {}).get("answers") or [] if a.get("relation") in RELATIONS}
        if ans and len(got & ids) >= 0.9 * len(ids):
            out.write_text(json.dumps(ans, ensure_ascii=False, indent=1), encoding="utf-8")
            log(run, f"{name}: {len(items)} phrases, {len(got & ids)} answered, {toks:,} tokens")
            return
        log(run, f"{name}: answer incomplete ({len(got & ids)} of {len(ids)}), attempt {attempt + 1}")
    with LOCK:
        state["lost"] += 1
    log(run, f"{name}: LOST after 3 attempts")
    if state["lost"] >= 20:
        state["stop"] = "20 chunks lost"
        log(run, f"STOPPING: {state['stop']}")


def main():
    H.stay_awake()
    run = ROOT / "out" / "sweep" / "runs" / sys.argv[1]
    run.mkdir(parents=True, exist_ok=True)
    args = sys.argv[2:]
    ids = None
    if args and args[0] == "--ids":
        # a re-judge of the listed phrases only (2026-10-18: the 10,848
        # judged under the wrong verse before the refiling)
        ids = set(json.loads(Path(args[1]).read_text(encoding="utf-8")))
        args = args[2:]
    only = set(args) or None
    bsb = C._bsb()
    work = list(chunks(only, ids))
    if ids is not None and not only:
        found = sum(len(i) for _n, i in work)
        if found != len(ids):
            raise SystemExit(f"{len(ids) - found} listed phrases are not in {SRC.name}: wrong list or stale file")
    log(run, f"start: {len(work)} chunks, {sum(len(i) for _n, i in work):,} phrases, {WORKERS} at a time, {MODEL}")
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        futs = [ex.submit(judge, run, n, items, prompt(n, items, bsb)) for n, items in work]
        for f in futs:
            f.result()
    log(run, f"end: {state['stop'] or 'all chunks done'}")


if __name__ == "__main__":
    main()
