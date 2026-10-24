"""THE CONCEPT AUDIT'S "OTHER SENSE" FLAGS, RE-JUDGED ON THE VERSES (2026-10-19).

Phase 1 of the audit (concept_audit.py) flagged 1,062 of a card's own words, on
614 cards, as mostly meaning something else. Too many to trust: "anger" was
told to drop אַף, which is mostly anger. A judge reading a word's gloss is not
evidence. So each flag is re-asked on the text: up to 20 of the word's verses,
spread over its uses, each judged "does the word mean <the card> here?", by two
models. The share both say yes to is the measurement; a word is a drop
candidate only where it is low on both.

    python tools/meaning/concept_senses.py run <run> <sonnet|haiku>   -> out/meaning/concept-audit/<run>/S-*.json
    python tools/meaning/concept_senses.py merge <run1> <run2>        -> out/meaning/concept-audit/senses.jsonl

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
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
import concept_audit as A  # noqa: E402
import context as C  # noqa: E402
import headless as H  # noqa: E402

OUT = A.OUT
PER_WORD = 20
TASK = """You are checking one Hebrew or Greek word against a concept card in a Bible knowledge graph. The card is
named below; the word is one of the card's words. For each verse, answer whether the word, AS USED IN THIS VERSE,
means the card's concept:
  "yes"    the word here means the concept (or a plain instance of it)
  "no"     the word here means something else (a different sense: "nose" not "anger", "adornment" not "world")
  "unsure" it could be read either way
Read the Berean text. Judge the sense of the word only, not what the verse teaches. Unresolved is better than wrong.

Several flags may be given; answer each, each against its own card.

Answer with ONLY this JSON object:
{"flags": [{"flag": "<flag id>", "verses": {"<ref>": "yes|no|unsure"}}]}

"""
# 4 flags a call: one flag a call spent ~11,600 tokens, mostly fixed overhead
# (pilot of 8, 2026-10-19)
PER_CALL = 4


def flags():
    bl = [json.loads(x) for x in (OUT / "backlog.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    ents = {}
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        e = json.loads(line)
        ents[e["id"]] = e
    verses_of, lemma = collections.defaultdict(set), {}
    with gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if d.get("word") and d.get("class") in ("noun", "verb", "adj"):
                s = re.sub(r"\D", "", str(d.get("strong") or "")).lstrip("0")
                if s:
                    k = ("g" if d.get("lang") == "greek" else "h") + s
                    verses_of[k].add(d["ref"])
                    lemma.setdefault(k, d.get("lemma"))
    out = []
    for r in bl:
        e = ents.get(r["id"]) or {}
        for k in r.get("other_sense") or []:
            pool = sorted(verses_of.get(k) or [])
            if len(pool) > PER_WORD:                 # spread over all its uses
                step = len(pool) / PER_WORD
                pool = [pool[int(i * step)] for i in range(PER_WORD)]
            if pool:
                out.append({"flag": f"{r['id']}~{k}", "card": r["id"], "name": e.get("name") or r.get("name"),
                            "desc": (e.get("desc") or "")[:240], "key": k, "lemma": lemma.get(k),
                            "uses": len(verses_of.get(k) or []), "pool": pool, "cited": r.get("cited") or 0})
    out.sort(key=lambda x: -x["cited"])          # the cards a reader meets most first
    return out


def run(name, model_key):
    H.stay_awake()
    run_dir = OUT / name
    run_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "tools"))
    from run_record import record
    record(run_dir, A.MODELS[model_key], TASK, __file__)
    A.state["tokens"] = sum(json.loads(x)["tokens"] for x in (run_dir / "_ledger.jsonl").read_text(encoding="utf-8").splitlines()) \
        if (run_dir / "_ledger.jsonl").exists() else 0
    fl = flags()
    (run_dir / "items.json").write_text(json.dumps(fl, ensure_ascii=False, indent=1), encoding="utf-8")
    bsb = C._bsb()
    model = A.MODELS[model_key]

    def text(b):
        return TASK + json.dumps({"flags": [{"flag": x["flag"], "card": x["name"], "card_description": x["desc"],
                                             "word": {"key": x["key"], "lemma": x["lemma"]},
                                             "verses": [{"ref": r, "text": bsb(r)[1]} for r in x["pool"]]} for x in b]},
                                 ensure_ascii=False, separators=(",", ":")) + "\n"

    def fname(x):
        return run_dir / f"S-{x['flag'].replace('~', '__')}.json"

    def one(b):
        b = [x for x in b if not fname(x).exists()]
        if not b or A.state["stop"]:
            return
        cap = run_dir / "BUDGET"
        if cap.exists() and A.state["tokens"] >= int(cap.read_text().strip() or 0):
            A.state["stop"] = "token cap reached"
            return
        for attempt in range(3):
            if (run_dir / "STOP").exists():
                A.state["stop"] = "STOP file"
                return
            res, err = H.call(text(b), model)
            blob = json.dumps(res or {}) + (err or "")
            if (res is None or res.get("is_error")) and "limit" in blob.lower():
                A.log(run_dir, f"{b[0]['flag']}: usage limit; waiting 10 minutes")
                time.sleep(600)
                continue
            if res is None or res.get("is_error"):
                with A.LOCK:
                    A.state["fails"] += 1
                    if A.state["fails"] >= 5:
                        A.state["stop"] = "5 failed calls in a row"
                if A.state["stop"]:
                    return
                continue
            with A.LOCK:
                A.state["fails"] = 0
            u = res.get("usage") or {}
            toks = sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                 "cache_creation_input_tokens"))
            with A.LOCK:
                A.state["tokens"] += toks
                with open(run_dir / "_ledger.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"flags": [x["flag"] for x in b], "tokens": toks}) + "\n")
            ans = H.parse(res) or {}
            by_flag = {a.get("flag"): a.get("verses") or {} for a in ans.get("flags") or [] if isinstance(a, dict)}
            if not by_flag and "verses" in ans:          # one flag answered in the single form
                by_flag = {ans.get("flag"): ans.get("verses") or {}}
            done = 0
            for x in b:
                v = by_flag.get(x["flag"]) or {}
                got = set(v) & set(x["pool"])
                if len(got) >= 0.8 * len(x["pool"]):
                    fname(x).write_text(json.dumps({"flag": x["flag"], "verses": v}, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
                    done += 1
            A.log(run_dir, f"{b[0]['flag']}+{len(b) - 1}: {done} of {len(b)} flags answered, {toks:,} tokens")
            b = [x for x in b if not fname(x).exists()]
            if not b:
                return
        A.log(run_dir, f"{b[0]['flag']}+{len(b) - 1}: LOST")

    A.log(run_dir, f"start: {len(fl)} flags, {sum(len(x['pool']) for x in fl):,} verses, {A.WORKERS} at a time, {model}")
    batches = [fl[i:i + PER_CALL] for i in range(0, len(fl), PER_CALL)]
    with cf.ThreadPoolExecutor(A.WORKERS) as ex:
        for f in [ex.submit(one, b) for b in batches]:
            f.result()
    A.log(run_dir, f"end: {A.state['stop'] or 'all flags done'}; {A.state['tokens']:,} tokens")


def merge(r1, r2):
    """Per flag: the share of its verses BOTH judges say mean the card. A word
    is a drop candidate under 30%, kept at 60% or more, mixed between (a word
    with two senses is split by verse, not dropped)."""
    its = json.loads((OUT / r1 / "items.json").read_text(encoding="utf-8"))

    def load(run):
        return {p.stem[2:].replace("__", "~"): json.loads(p.read_text(encoding="utf-8")).get("verses") or {}
                for p in (OUT / run).glob("S-*.json")}
    a1, a2 = load(r1), load(r2)
    rows, st, agree, both_n = [], collections.Counter(), 0, 0
    for x in its:
        v1, v2 = a1.get(x["flag"]), a2.get(x["flag"])
        if v1 is None or v2 is None:
            st["not judged by both"] += 1
            continue
        both = [r for r in x["pool"] if r in v1 and r in v2]
        both_n += len(both)
        agree += sum(1 for r in both if v1[r] == v2[r])
        yes = [r for r in both if v1[r] == "yes" and v2[r] == "yes"]
        no = [r for r in both if v1[r] == "no" and v2[r] == "no"]
        share = len(yes) / max(1, len(both))
        verdict = "drop candidate" if share < 0.3 else "keep" if share >= 0.6 else "mixed: split by verse"
        st[verdict] += 1
        rows.append({**{k: x[k] for k in ("flag", "card", "name", "key", "lemma", "uses")},
                     "judged": len(both), "yes": len(yes), "no": len(no), "share_yes": round(share, 2),
                     "verdict": verdict, "yes_verses": yes, "no_verses": no})
    rows.sort(key=lambda r: (r["share_yes"], -r["uses"]))
    (OUT / "senses.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(its)} flags; judges agree on {agree:,} of {both_n:,} verses ({100 * agree / max(1, both_n):.1f}%); "
          f"{dict(st.most_common())} -> {(OUT / 'senses.jsonl').relative_to(ROOT)}")


if __name__ == "__main__":
    {"run": run, "merge": merge}[sys.argv[1]](*sys.argv[2:])
