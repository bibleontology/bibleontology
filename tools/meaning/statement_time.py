"""THE TIME OF A HELD STATEMENT (plan 2.19a; approved on the refreshed 1.2.0
inventory, 2026-10-20: approved with the recommendations).

A verb statement whose verb's form does not say the thing happened (a Hebrew
yiqtol or weqatal, a Greek future, subjunctive or optative;
resolve_records.time_of) is held. Each of its clauses is read here, in its
verse with the verse before, by two judges blind to each other:

  happened      the verse says this happened, or that it is so (a past, a
                present, a habit, a general truth)
  promised      the speaker says they themselves will do it
  foretold      said of the future, of someone other than the speaker
  commanded     a command or instruction ("you shall")
  wished        a wish or prayer ("may he")
  dependent     the purpose, condition, time or expected result of another
                clause ("so that", "if", "until", "when")
  unsure

Only where both judges give the same answer is it applied (write_statements.py
reads the merged file); anything else stays held.

    python tools/meaning/statement_time.py run <run> <haiku|sonnet>  -> out/meaning/statement-time/<run>/T-*.json
    python tools/meaning/statement_time.py merge <run1> <run2>       -> ontology/provenance/meaning/statement-time-2026-10-20.jsonl

Stops on a STOP file, or when its ledger passes the cap in <run>/BUDGET.
"""
import collections
import concurrent.futures as cf
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
sys.path.insert(0, str(ROOT / "tools"))
import concept_audit as A  # noqa: E402
import context as C  # noqa: E402
import headless as H  # noqa: E402

OUT = ROOT / "out" / "meaning" / "statement-time"
DEST = ROOT / "ontology" / "provenance" / "meaning" / "statement-time-2026-10-20.jsonl"
ANSWERS = ("happened", "promised", "foretold", "commanded", "wished", "dependent", "unsure")
PER_CALL = 8
TASK = """You are reading statements lifted from single clauses of the Bible. For each item you are given the verse
(Berean Standard Bible) and the verse before it, who is speaking if the clause is inside someone's speech, the
statement in plain words: SUBJECT - VERB - OBJECT, and the verb in the original (Hebrew or Greek) with its form. The
verb's form does not settle whether the statement says this HAPPENED: a Hebrew perfect can tell the future as done
(the prophetic perfect) or perform what it says; a participle or infinitive has no time of its own. The original
decides over the English where they differ. Read the verse and answer, for the clause the statement comes from:
  "happened"   the verse says this happened, or that it is so: a past event, a present fact, a habit, a general truth
  "promised"   the speaker says they themselves will do it (a promise, a resolve: "I will ...")
  "foretold"   said of the future about someone other than the speaker (a prediction: "you will ...", "he will ...")
  "commanded"  a command or instruction ("you shall ...", "you must ...")
  "wished"     a wish or a prayer ("may he ...", "let it ...")
  "dependent"  the clause is the purpose, condition, time or expected result of another clause ("so that", "if",
               "until", "when", "lest")
  "unsure"     it could be read more than one way
Judge the grammar and sense of this one clause in its verse, not what the passage teaches. Unsure is better than wrong.

Answer with ONLY this JSON object:
{"items": [{"id": "<item id>", "answer": "happened|promised|foretold|commanded|wished|dependent|unsure"}]}

"""


def items():
    # the clauses already judged (an earlier run's merged answers) are not
    # asked again; the second sitting's holds added new ones (2026-10-20)
    done = set()
    if DEST.exists():
        done = {json.loads(x)["clause"] for x in DEST.read_text(encoding="utf-8").splitlines() if x.strip()}
    recs = {}
    for line in open(ROOT / "out" / "meaning" / "clause-records.jsonl", encoding="utf-8"):
        c = json.loads(line)
        recs[c["clause"]] = c
    names = {}
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        e = json.loads(line)
        names[e["id"]] = e.get("name") or e["id"]
    out = []
    for line in open(ROOT / "ontology" / "relations" / "verb-statements.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if "reading of its time" not in str(r.get("held") or ""):
            continue
        for cl in r["clauses"]:
            if cl in done:
                continue
            c = recs.get(cl) or {}
            form = ", ".join(str(v) for v in (c.get("stem"), c.get("mood"), c.get("tense"),
                                              f"{c['person']} person" if c.get("person") else None) if v)
            out.append({"id": cl, "subject": names.get(r["src"], r["src"]), "verb": r.get("label_plain") or r["label"],
                        "object": names.get(r["dst"], r["dst"]),
                        "original": f"{c.get('verb') or ''} ({form})".strip(),
                        "speaker": names.get(r["claimed_by"]) if r.get("claimed_by") else None})
    seen, uniq = set(), []
    for x in out:                       # a clause judged once
        if x["id"] not in seen:
            seen.add(x["id"])
            uniq.append(x)
    return uniq


def run(name, model_key):
    H.stay_awake()
    run_dir = OUT / name
    run_dir.mkdir(parents=True, exist_ok=True)
    from run_record import record
    model = A.MODELS[model_key]
    record(run_dir, model, TASK, __file__)
    A.state["tokens"] = sum(json.loads(x)["tokens"] for x in (run_dir / "_ledger.jsonl").read_text(encoding="utf-8").splitlines()) \
        if (run_dir / "_ledger.jsonl").exists() else 0
    its = items()
    (run_dir / "items.json").write_text(json.dumps(its, ensure_ascii=False, indent=1), encoding="utf-8")
    bsb = C._bsb()

    def ctx(cl):
        ref = cl.split("#")[0]
        b, c, v = ref.split(".")
        title, text = bsb(ref)
        before = bsb(f"{b}.{c}.{int(v) - 1}")[1] if int(v) > 1 else ""
        return title, text, before

    def text(b):
        rows = []
        for x in b:
            title, t, before = ctx(x["id"])
            rows.append({"id": x["id"], "verse": title, "text": t, "verse_before": before,
                         "speaker": x["speaker"] or "the narrator",
                         "statement": f"{x['subject']} - {x['verb']} - {x['object']}",
                         "verb_in_the_original": x.get("original")})
        return TASK + json.dumps({"items": rows}, ensure_ascii=False, separators=(",", ":")) + "\n"

    def fname(x):
        return run_dir / f"T-{x['id'].replace('#', '__')}.json"

    def one(b):
        b = [x for x in b if not fname(x).exists()]
        if not b or A.state["stop"]:
            return
        cap = run_dir / "BUDGET"
        if cap.exists() and A.state["tokens"] >= int(cap.read_text().strip() or 0):
            A.state["stop"] = "token cap reached"
            return
        for _attempt in range(3):
            if (run_dir / "STOP").exists():
                A.state["stop"] = "STOP file"
                return
            res, err = H.call(text(b), model)
            blob = json.dumps(res or {}) + (err or "")
            if (res is None or res.get("is_error")) and "limit" in blob.lower():
                A.log(run_dir, f"{b[0]['id']}: usage limit; waiting 10 minutes")
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
                    f.write(json.dumps({"items": [x["id"] for x in b], "tokens": toks}) + "\n")
            ans = {a.get("id"): a.get("answer") for a in (H.parse(res) or {}).get("items") or [] if isinstance(a, dict)}
            done = 0
            for x in b:
                if ans.get(x["id"]) in ANSWERS:
                    fname(x).write_text(json.dumps({"id": x["id"], "answer": ans[x["id"]]}), encoding="utf-8")
                    done += 1
            A.log(run_dir, f"{b[0]['id']}+{len(b) - 1}: {done} of {len(b)} answered, {toks:,} tokens")
            b = [x for x in b if not fname(x).exists()]
            if not b:
                return
        A.log(run_dir, f"{b[0]['id']}+{len(b) - 1}: LOST")

    A.log(run_dir, f"start: {len(its)} clauses, {A.WORKERS} at a time, {model}")
    batches = [its[i:i + PER_CALL] for i in range(0, len(its), PER_CALL)]
    with cf.ThreadPoolExecutor(A.WORKERS) as ex:
        for f in [ex.submit(one, b) for b in batches]:
            f.result()
    A.log(run_dir, f"end: {A.state['stop'] or 'all clauses done'}; {A.state['tokens']:,} tokens")


def merge(r1, r2):
    """Per clause: the answer both judges gave, or none (stays held)."""
    def load(run):
        return {json.loads(p.read_text(encoding="utf-8"))["id"]: json.loads(p.read_text(encoding="utf-8"))["answer"]
                for p in (OUT / run).glob("T-*.json")}
    a1, a2 = load(r1), load(r2)
    rec = {r: json.loads((OUT / r / "run.json").read_text(encoding="utf-8")) if (OUT / r / "run.json").exists() else {}
           for r in (r1, r2)}
    st, rows = collections.Counter(), []
    for cl in sorted(set(a1) | set(a2)):
        x, y = a1.get(cl), a2.get(cl)
        agreed = x if x == y and x not in (None, "unsure") else None
        st[agreed or ("not judged by both" if x is None or y is None else "the judges differ or are unsure")] += 1
        rows.append({"clause": cl, "answer": agreed, "judges": {r1: x, r2: y},
                     "runs": [r1, r2], "models": [str((rec[r] or {}).get("model") or r) for r in (r1, r2)]})
    # ADDED TO, never replaced: a later pair of runs judges only clauses no
    # earlier pair did, so earlier answers stay as they were
    DEST.parent.mkdir(parents=True, exist_ok=True)
    kept = []
    if DEST.exists():
        new = {r["clause"] for r in rows}
        kept = [json.loads(x) for x in DEST.read_text(encoding="utf-8").splitlines()
                if x.strip() and json.loads(x)["clause"] not in new]
    DEST.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept + rows), encoding="utf-8")
    both = [c for c in a1 if c in a2]
    agree = sum(a1[c] == a2[c] for c in both)
    print(f"{len(rows)} clauses; the judges agree on {agree} of {len(both)}; {dict(st.most_common())} "
          f"-> {DEST.relative_to(ROOT)}")


if __name__ == "__main__":
    {"run": run, "merge": merge}[sys.argv[1]](*sys.argv[2:])
