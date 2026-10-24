"""EVERY CONCEPT CARD AUDITED FOR COMPLETENESS (2026-10-18: an audit of
all concepts for completeness, to show where the likely gaps are with the
verses, so that a prioritized backlog of concept repairs can be built from
this data).

The method is the one "world" proved (plan 8.2b): a card's verses come from
its anchor words, and a card is incomplete where the text uses OTHER words for
the same thing (οἰκουμένη beside κόσμος), where one of its words mostly means
something else (κόσμος "adornment"), or where the verses it cites hold none of
its words. Candidates come from the structure; a judge decides (candidates
then judgment):

  candidates  words whose MACULA gloss shares a word of the card's name or
              aka but are not its anchors, with their verse counts and two
              verses each; the card's anchors with theirs; cited verses that
              hold none of its anchor words
  judge       per card: each candidate add / not; each anchor keep /
              other_sense; what the text likely says of it that these words
              miss; a grade: full / gaps / thin

    python tools/meaning/concept_audit.py prep            -> out/meaning/concept-audit/items.json
    python tools/meaning/concept_audit.py run <run> [N]   -> out/meaning/concept-audit/<run>/A-*.json
    python tools/meaning/concept_audit.py merge <run>...  -> out/meaning/concept-audit/audit.jsonl

A run stops by itself when its ledger passes the token cap in
out/meaning/concept-audit/<run>/BUDGET (one integer), or on a STOP file.
"""
import collections
import concurrent.futures as cf
import gzip
import json
import re
import sys
import threading
import time
from pathlib import Path

import os
ROOT = Path(__file__).resolve().parents[2]
# the same audit over the other kinds of card (objects, images, titles...),
# kept in its own directory: CA_TYPES=object,image CA_DIR=card-audit
OUT = ROOT / "out" / "meaning" / os.environ.get("CA_DIR", "concept-audit")
TYPES = set(os.environ.get("CA_TYPES", "concept").split(","))
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
import context as C  # noqa: E402
import headless as H  # noqa: E402
from concept_anchors import STOP as ESTOP, stem  # noqa: E402

MODELS = {"sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
CHUNK, WORKERS = 6, 8
LOCK = threading.Lock()
state = {"fails": 0, "lost": 0, "stop": None, "tokens": 0}

TASK = """You are auditing concept cards in a Bible knowledge graph for completeness. A card's verses come from its
WORDS: the Hebrew and Greek words tied to it. A card is incomplete when the text uses other words for the same thing,
when one of its words mostly means something else, or when the text speaks of the concept in ways no single word
catches. For each card you get its name, its words (with how many verses each), candidate words (the original's
gloss shares a word with the card's name) with two verses each, and verses the card cites that hold none of its words.

Decide, for each card:
- candidates: for each candidate word, "add" if it names the same thing as the card in most of its uses, else "not".
  A word for a related but different thing is "not" (a word for a SHIELD is not on a card for PROTECTION).
- anchors: for each of the card's words, "keep", or "other_sense" if most of its uses mean something else.
- missing: up to three short notes on what the text says of this concept that the words likely miss (an idiom, a
  phrase, a different word family, a narrative that shows it without naming it). Give a verse reference only if you
  are sure of it. No doctrine: describe where the text speaks of it, not what it means theologically.
- grade: "full" (the words carry it), "gaps" (real verses are missing), or "thin" (most of it is missing).
- confidence: high, medium or low. Unresolved is better than wrong.

Answer with ONLY this JSON object:
{"cards": [{"id": "<card id>", "candidates": {"<key>": "add|not"}, "anchors": {"<key>": "keep|other_sense"},
 "missing": ["..."], "grade": "full|gaps|thin", "confidence": "high|medium|low", "why": "a dozen words"}]}

"""


def prep():
    """Every concept card with its candidates, from the committed data."""
    words_of = collections.defaultdict(set)          # key -> verses
    gloss = collections.defaultdict(collections.Counter)
    lemma = {}
    verse_keys = collections.defaultdict(set)
    occ = collections.defaultdict(list)              # key -> [(verse, rendering)]
    with gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if not d.get("word") or d.get("class") not in ("noun", "verb", "adj"):
                continue
            s = re.sub(r"\D", "", str(d.get("strong") or "")).lstrip("0")
            if not s:
                continue
            k = ("g" if d.get("lang") == "greek" else "h") + s
            words_of[k].add(d["ref"])
            verse_keys[d["ref"]].add(k)
            lemma.setdefault(k, d.get("lemma"))
            occ[k].append((d["ref"], d.get("text")))
            for x in re.findall(r"[A-Za-z]+", d.get("text") or ""):
                if x.lower() not in ESTOP:
                    gloss[k][stem(x)] += 1
    by_stem = collections.defaultdict(list)
    for k, c in gloss.items():
        tot = sum(c.values())
        for st, n in c.items():
            if n >= 2 and n / tot >= 0.15:
                by_stem[st].append((k, n / tot))
    # A CARD AS A READER SEES IT (tools/meaning/membership.py, plan 4.8 step
    # 0(a)): the 2026-10-18/19 audit judged every anchor, 3,114 of them hidden
    # from readers, and none of the root and family words readers are shown, so
    # its "gaps" and "drops" partly described a card nobody saw
    import membership as M
    fp = ROOT / "out" / "word-families.json"
    families = (json.loads(fp.read_text(encoding="utf-8")).get("families") or {}) if fp.exists() else {}
    vsenses = {(r["card"], r["key"]): r["verdict"] for r in
               (json.loads(x) for x in open(ROOT / "ontology" / "verse-senses.jsonl", encoding="utf-8") if x.strip())}
    rix = M.root_index(lemma)
    with gzip.open(ROOT / "out" / "concept-anchors.jsonl.gz", "rt", encoding="utf-8") as f:
        shown = M.anchors(json.loads(x) for x in f if x.strip())
    anchors, card_ws = {}, {}
    for cid, base in shown.items():
        card_ws[cid] = M.words(base, lemma, families, rix, card=cid)
        anchors[cid] = sorted(card_ws[cid])
    ents_by_id = {}
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        e_ = json.loads(line)
        ents_by_id[e_["id"]] = e_
    sys.path.insert(0, str(ROOT / "tools"))
    from export_claims import verses as vlist
    from derive import BOOK
    items = []
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        e = json.loads(line)
        if e.get("type") not in TYPES:
            continue
        an = anchors.get(e["id"], [])
        names = [e["name"]] + (e.get("aka") or [])
        stems = {stem(w) for n in names for w in re.findall(r"[A-Za-z]+", n) if w.lower() not in ESTOP}
        cand = {}
        for st in stems:
            for k, share in by_stem.get(st, []):
                if k not in an and len(words_of[k]) >= 2:
                    cand[k] = max(cand.get(k, 0), share)
        cand = sorted(cand, key=lambda k: -len(words_of[k]))[:6]
        # the entities write "Matt 7:24", the graph "Mat.7.24": mapped, or every
        # cited verse in 40 books looks uncovered (it did, 2026-10-18 and -19:
        # "verses the card cites that hold none of its words" was wrong for
        # Prov, Ps, Titus, Mark, John...)
        cited = sorted({".".join([BOOK.get(v.split(".")[0], v.split(".")[0])] + v.split(".")[1:])
                        for r in e.get("refs") or [] for v in vlist(r)})
        uncovered = [v for v in cited if an and not (verse_keys[v] & set(an))][:3]
        card_verses = M.verses(e["id"], e, card_ws[e["id"]], words_of, occ, vsenses) if an else set()
        items.append({"id": e["id"], "name": e["name"], "aka": e.get("aka") or [],
                      "desc": (e.get("desc") or "")[:300], "cited": len(cited), "verses": len(card_verses),
                      "anchors": [{"key": k, "lemma": lemma.get(k), "gloss": [g for g, _ in gloss[k].most_common(3)],
                                   "verses": len(words_of[k])} for k in an],
                      "candidates": [{"key": k, "lemma": lemma.get(k), "gloss": [g for g, _ in gloss[k].most_common(3)],
                                      "verses": len(words_of[k]), "examples": sorted(words_of[k])[:2]} for k in cand],
                      "uncovered": uncovered})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "items.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(items)} cards ({','.join(sorted(TYPES))}); with candidates {sum(1 for i in items if i['candidates'])}; "
          f"unanchored {sum(1 for i in items if not i['anchors'])}; with uncovered citations "
          f"{sum(1 for i in items if i['uncovered'])} -> {(OUT / 'items.json').relative_to(ROOT)}")


def prompt(batch, bsb):
    cards = []
    for it in batch:
        c = {k: it[k] for k in ("id", "name", "aka", "desc", "anchors")}
        c["candidates"] = [{**{k: x[k] for k in ("key", "lemma", "gloss", "verses")},
                            "examples": [{"ref": r, "text": bsb(r)[1]} for r in x["examples"]]} for x in it["candidates"]]
        c["uncovered_citations"] = [{"ref": r, "text": bsb(r)[1]} for r in it["uncovered"]]
        cards.append(c)
    return TASK + json.dumps({"cards": cards}, ensure_ascii=False, separators=(",", ":")) + "\n"


def log(run, msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    print(line, flush=True)
    with LOCK, open(run / "_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def judge(run, model, name, batch, text):
    out = run / f"A-{name}.json"
    if out.exists() or state["stop"]:
        return
    cap = run / "BUDGET"
    if cap.exists() and state["tokens"] >= int(cap.read_text().strip() or 0):
        state["stop"] = f"token cap {cap.read_text().strip()} reached"
        return
    ids = {it["id"] for it in batch}
    for attempt in range(3):
        if (run / "STOP").exists():
            state["stop"] = "STOP file"
            return
        res, err = H.call(text, model)
        blob = json.dumps(res or {}) + (err or "")
        if (res is None or res.get("is_error")) and "limit" in blob.lower():
            log(run, f"{name}: usage limit; waiting 10 minutes")
            time.sleep(600)
            continue
        if res is None or res.get("is_error"):
            with LOCK:
                state["fails"] += 1
                if state["fails"] >= 5:
                    state["stop"] = "5 failed calls in a row"
            log(run, f"{name}: call failed")
            if state["stop"]:
                return
            continue
        with LOCK:
            state["fails"] = 0
        u = res.get("usage") or {}
        toks = sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                             "cache_creation_input_tokens"))
        with LOCK:
            state["tokens"] += toks
            with open(run / "_ledger.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"batch": name, "cards": len(batch), "tokens": toks,
                                    "out": u.get("output_tokens")}) + "\n")
        ans = H.parse(res)
        got = {a.get("id") for a in (ans or {}).get("cards") or [] if a.get("grade") in ("full", "gaps", "thin")}
        if ans and len(got & ids) >= 0.8 * len(ids):
            out.write_text(json.dumps(ans, ensure_ascii=False, indent=1), encoding="utf-8")
            log(run, f"{name}: {len(batch)} cards, {len(got & ids)} answered, {toks:,} tokens")
            return
        log(run, f"{name}: answer incomplete ({len(got & ids)} of {len(ids)}), attempt {attempt + 1}")
    state["lost"] += 1
    log(run, f"{name}: LOST after 3 attempts")
    if state["lost"] >= 15:
        state["stop"] = "15 batches lost"


def run(name, model_key, limit=None):
    H.stay_awake()
    run_dir = OUT / name
    run_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "tools"))
    from run_record import record
    record(run_dir, MODELS[model_key], TASK, __file__)
    if (run_dir / "_ledger.jsonl").exists():
        state["tokens"] = sum(json.loads(x)["tokens"] for x in (run_dir / "_ledger.jsonl").read_text(encoding="utf-8").splitlines())
    items = json.loads((OUT / "items.json").read_text(encoding="utf-8"))
    # the cards a reader meets most first: most cited, then most verses
    items.sort(key=lambda i: (-i["cited"], -i["verses"]))
    if limit:
        items = items[:int(limit)]
    if os.environ.get("CA_ONLY"):      # a file of card ids: a re-judge of just those
        only = set(json.loads(Path(os.environ["CA_ONLY"]).read_text(encoding="utf-8")))
        items = [i for i in items if i["id"] in only]
    bsb = C._bsb()
    batches = [(f"B{i // CHUNK + 1:04d}", items[i:i + CHUNK]) for i in range(0, len(items), CHUNK)]
    model = MODELS[model_key]
    log(run_dir, f"start: {len(items)} cards, {len(batches)} batches, {WORKERS} at a time, {model}")
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for f in [ex.submit(judge, run_dir, model, nm, b, prompt(b, bsb)) for nm, b in batches]:
            f.result()
    log(run_dir, f"end: {state['stop'] or 'all batches done'}; {state['tokens']:,} tokens")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prep":
        prep()
    elif cmd == "run":
        run(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
