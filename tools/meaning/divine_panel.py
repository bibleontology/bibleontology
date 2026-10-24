"""THE HELD DIVINE ENDS, READ BY THE PANEL OF ELEVEN (2026-10-19, on B4
of the committee sheet: spare tokens used to run these by the committee of 11,
with a governor ensuring that work does not extend into the new session, 6pm
that day).

5,925 words reach God or Jesus only through a pointer chain ("He said to
Moses"), and are held: divine persons are resolved by hand, record by record, never by a
rule. This does not release any of them. It asks the eleven-reader panel
(ontology/provenance/README.md, "The review panel") one question per word:
does it point to that person, as a careful reader of each tradition reads the
text? A question of reference, not of belief. A reader answers only by
objecting ("object" or "unsure", with why); no objection from any seat, in
two independent passes, makes the word a release CANDIDATE for a ruling by hand.

THE GOVERNOR: no call starts after DEADLINE (17:30 Indiana, 21:30 UTC,
2026-10-19; the weekly allowance renews at 18:00), a token cap over both passes,
a STOP file, a stop at the first usage-limit answer (never a wait), and at five
failed calls in a row.

    python tools/meaning/divine_panel.py all        -> out/meaning/divine-panel/{p1,p2}/P-*.json,
                                                       out/meaning/divine-panel/verdicts.jsonl
    python tools/meaning/divine_panel.py merge
"""
import collections
import concurrent.futures as cf
import datetime as dt
import json
import random
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "meaning" / "divine-panel"
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
import context as C  # noqa: E402
import headless as H  # noqa: E402

MODEL = "claude-sonnet-5-5"
DEADLINE = dt.datetime(2026, 10, 19, 21, 30, tzinfo=dt.timezone.utc)
CAP = 24_000_000                       # both passes together
CHUNK, WORKERS = 20, 8
LOCK = threading.Lock()
state = {"tokens": 0, "fails": 0, "stop": None}
NAMES = {"god": "God", "jesus": "Jesus"}

TASK = """You are a review panel of eleven careful readers of the Bible, each from a different tradition, reading
together. The panel:
  lutheran      justification by faith alone; law and gospel; the sacraments
  reformed      election; the perseverance of the saints
  wesleyan      free will; that a believer can fall away
  baptist       believer's baptism; often dispensational
  pentecostal   the gifts of the Spirit
  secular       reads under no confession: does the text say this?
  catholic      Scripture read with the Church's tradition (judging within the 66 books)
  orthodox      Scripture read with the Church's tradition (judging within the 66 books)
  biblical_theological   the Bible as one story; its literary design; the Old Testament heard on its own terms first
  rabbi         the Hebrew Scriptures heard first on their own terms, as their first hearers heard them
  young_african_american_believer   no US political framing; nothing culturally insensitive; true to the text

Each item is ONE word in a verse (a pronoun, or a verb's unstated subject) and a chain showing the word it was
followed back to. A structure built from the Hebrew and Greek says the word points to a person: God or Jesus.

The question is ONLY about reference: in this verse, does this word point to that person, as a careful reader of
your tradition reads the text? It is NOT whether you believe anything about the person, nor what the verse teaches.
A rabbi reading a Gospel narrative can say who "he" refers to in the story without confessing anything.

For each item, list ONLY the seats that would object:
  "object"  this reader reads the word as pointing to someone else (another person, a different divine name, the
            speaker, the people), or the chain is plainly wrong
  "unsure"  this reader's tradition holds the reference open or disputed (e.g. whose spirit, which "he")
Most plain narrative ("the LORD said to Moses ... and he said") draws no objection; then give an empty list.
Do not invent objections. Unresolved is better than wrong, so do not hide a real one either.

Answer with ONLY this JSON object:
{"items": [{"id": "<item id>", "objections": [{"seat": "<seat>", "kind": "object|unsure", "why": "a dozen words"}]}]}

"""


def items():
    out, seen = [], set()
    for line in (ROOT / "out" / "meaning" / "clause-records.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        for side in ("subject", "object"):
            e = r[side]
            if "chain" not in e or e["node"] in seen:
                continue
            seen.add(e["node"])
            person = e["how"].split()[1]                  # "held: god through a referent"
            out.append({"id": e["node"], "ref": r["ref"], "person": person, "verb": r["verb_text"], "side": side,
                        "chain": e["chain"]})
    return out


def text(batch, bsb):
    its = []
    for x in batch:
        refs = []
        for c in x["chain"]:
            if c["ref"] and c["ref"] not in refs:
                refs.append(c["ref"])
        its.append({"id": x["id"], "verse": x["ref"],
                    "texts": {r: bsb(r)[1] for r in sorted(refs)},
                    "word": x["chain"][0]["text"] or "(unstated subject of '" + (x["verb"] or "") + "')",
                    "followed_back_to": [f"{c['text']} ({c['ref']})" for c in x["chain"][1:]],
                    "points_to": NAMES.get(x["person"], x["person"])})
    return TASK + json.dumps({"items": its}, ensure_ascii=False, separators=(",", ":")) + "\n"


def log(msg):
    line = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with LOCK, open(OUT / "_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def governed():
    if state["stop"]:
        return False
    if dt.datetime.now(dt.timezone.utc) >= DEADLINE:
        state["stop"] = "deadline (17:30 Indiana)"
    elif state["tokens"] >= CAP:
        state["stop"] = f"token cap {CAP:,}"
    elif (OUT / "STOP").exists():
        state["stop"] = "STOP file"
    return not state["stop"]


def run(name, seed):
    rd = OUT / name
    rd.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "tools"))
    from run_record import record
    record(rd, MODEL, TASK, __file__)
    its = items()
    random.Random(seed).shuffle(its)                     # each pass sees other neighbours
    bsb = C._bsb()
    batches = [(f"B{i // CHUNK + 1:04d}", its[i:i + CHUNK]) for i in range(0, len(its), CHUNK)]

    def one(nm, b):
        out = rd / f"P-{nm}.json"
        if out.exists():
            return
        for attempt in range(3):
            if not governed():
                return
            res, err = H.call(text(b, bsb), MODEL)
            blob = json.dumps(res or {}) + (err or "")
            if (res is None or res.get("is_error")) and "limit" in blob.lower():
                state["stop"] = "usage limit reached (no waiting)"
                return
            if res is None or res.get("is_error"):
                with LOCK:
                    state["fails"] += 1
                    if state["fails"] >= 5:
                        state["stop"] = "5 failed calls in a row"
                continue
            u = res.get("usage") or {}
            toks = sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                 "cache_creation_input_tokens"))
            with LOCK:
                state["fails"] = 0
                state["tokens"] += toks
                with open(OUT / "_ledger.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"run": name, "batch": nm, "tokens": toks}) + "\n")
            ans = H.parse(res)
            got = {a.get("id") for a in (ans or {}).get("items") or []} & {x["id"] for x in b}
            if len(got) >= 0.9 * len(b):
                out.write_text(json.dumps({"items_shown": [x["id"] for x in b], **ans}, ensure_ascii=False, indent=1),
                               encoding="utf-8")
                return
        log(f"{name} {nm}: not answered")

    log(f"{name}: {len(its)} words, {len(batches)} batches, deadline {DEADLINE:%H:%M}Z, cap {CAP:,}")
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for f in [ex.submit(one, nm, b) for nm, b in batches]:
            f.result()
    log(f"{name}: end ({state['stop'] or 'all batches done'}); {state['tokens']:,} tokens so far")


def merge():
    its = {x["id"]: x for x in items()}

    def load(r):
        a = {}
        for p in (OUT / r).glob("P-*.json"):
            for x in json.loads(p.read_text(encoding="utf-8")).get("items") or []:
                a[x.get("id")] = x.get("objections") or []
        return a
    a1, a2 = load("p1"), load("p2")
    st, rows = collections.Counter(), []
    for i, x in its.items():
        o1, o2 = a1.get(i), a2.get(i)
        if o1 is None or o2 is None:
            v = "not read by both"
        elif not o1 and not o2:
            v = "candidate: no seat objects, both passes"
        elif any(o.get("kind") == "object" for o in o1 + o2):
            v = "objected"
        else:
            v = "held open"
        st[(x["person"], v)] += 1
        rows.append({**x, "pass1": o1, "pass2": o2, "verdict": v})
    (OUT / "verdicts.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    seats = collections.Counter(o.get("seat") for r in rows for o in (r["pass1"] or []) + (r["pass2"] or []))
    log(f"merge: {dict(sorted(st.items()))}; objections by seat {dict(seats.most_common())}")


if __name__ == "__main__":
    if sys.argv[1] == "all":
        H.stay_awake()
        run("p1", 1)
        if governed():
            run("p2", 2)
        merge()
    elif sys.argv[1] == "pilot":
        global_items = items()
        log(f"pilot: {len(global_items)} words in all")
        CHUNK = 20
        rd = OUT / "pilot"
        rd.mkdir(parents=True, exist_ok=True)
        b = random.Random(7).sample(global_items, 20)
        res, err = H.call(text(b, C._bsb()), MODEL)
        u = (res or {}).get("usage") or {}
        print(json.dumps(H.parse(res), ensure_ascii=False, indent=1)[:4000])
        print("tokens", sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                    "cache_creation_input_tokens")))
    else:
        merge()
