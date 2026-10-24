"""CANDIDATE RELATIONS FROM THE CLAUSES, JUDGED (plan 2.17, step 2).

Each clause whose subject and object both resolve to records
(out/meaning/clause-records.jsonl, tools/meaning/resolve_records.py) is a
candidate statement "<subject> <verb> <object>". A judge reads the verse and
says whether the verse states it, as resolved: "yes", "no" (a wrong record at
one end, a negated or hypothetical clause, a different sense), or "unsure".
Two judges, kept only where both say yes. Nothing is shown until then.

    python tools/meaning/lift_relations.py run <run> <model> [--love]   -> out/meaning/lift/<run>/L-*.json
    python tools/meaning/lift_relations.py merge <run1> <run2>          -> out/meaning/lift/relations.jsonl
    python tools/meaning/lift_relations.py senses <run> <model>          -> out/meaning/lift/<run>/F-*.json (verb sense
                                                                           and family, candidates for the schema)
"""
import collections
import concurrent.futures as cf
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "meaning" / "lift"
sys.path.insert(0, str(ROOT / "tools" / "sweep"))
import context as C  # noqa: E402
import headless as H  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
from run_record import record  # noqa: E402  (every judged run keeps its model, commit and prompt)

MODELS = {"sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}
# MACULA spells the Hebrew lemma אָהֵב (the first pilot used אָהַב and found no
# Old Testament love at all, 2026-10-19); both kept
LOVE = {"ἀγαπάω", "φιλέω", "אָהֵב", "אָהַב", "אהב"}


def family(lemma, rendering):
    """A relation's family comes from the word's SENSE in the verse, not its
    lemma: φιλέω is "love" in John 21 and "kiss" in Mark 14:44, and the first
    pilot filed Judas's kiss as love (2026-10-19). The builder's verbs carry no
    sense field, so the verse's own rendering decides (a translation fallback,
    and recorded as one)."""
    r = (rendering or "").lower()
    if lemma in LOVE:
        return ("love", "rendering") if "lov" in r else (None, f"rendered {rendering!r}, not love")
    return None, "no family yet"
CHUNK, WORKERS = 25, 8
state = {"fails": 0, "stop": None, "tokens": 0}

TASK = """You are checking statements drawn from the grammar of Bible verses. Each item gives a verse (the Berean
text), and a statement built from one of its clauses: SUBJECT, VERB, OBJECT, where subject and object have been
matched to named people, places or concepts. Answer whether the verse states this, as matched:
  "yes"     the verse says the subject does this to the object (or did, or will)
  "no"      a wrong person or thing at either end, or the clause is negated, a question, a command, a wish, or
            hypothetical, or the verb means something else here
  "unsure"  it could be read either way
Judge only what the verse states; take no doctrinal position. Unresolved is better than wrong.

Answer with ONLY this JSON object:
{"answers": [{"id": "<item id>", "decision": "yes|no|unsure", "why": "a dozen words"}]}

"""


def items(love_only=False):
    rows = [json.loads(x) for x in (ROOT / "out" / "meaning" / "clause-records.jsonl").read_text(encoding="utf-8").splitlines()]
    ents = {}
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        e = json.loads(line)
        ents[e["id"]] = e.get("name")
    out = []
    for r in rows:
        s, o = r["subject"]["record"], r["object"]["record"]
        fam, fam_how = family(r["verb"], r["verb_text"])
        if not (s and o) or (love_only and fam != "love"):
            continue
        # the gate (plan 2.18): a command, question, promise, negated or
        # passive clause is not judged as a statement; kept in clause-records
        # with its modality and reason
        if r.get("gate"):
            continue
        out.append({"id": f"{r['clause']}", "ref": r["ref"], "verb": r["verb"], "verb_text": r["verb_text"],
                    "family": fam, "family_from": fam_how,
                    "subject": s, "subject_name": ents.get(s, s), "object": o, "object_name": ents.get(o, o),
                    "how": [r["subject"]["how"], r["object"]["how"]]})
    return out


def key(x):
    return (x["id"], x["subject"], x["object"])


def judged(runs):
    """{(clause, subject, object): decision} from earlier runs: a statement
    already judged is not paid for again when resolution changes elsewhere."""
    out = {}
    for r in runs:
        its = {x["id"]: x for x in json.loads((OUT / r / "items.json").read_text(encoding="utf-8"))}
        for i, d in answers(r).items():
            if i in its:
                out[key(its[i])] = d
    return out


def run(name, model, love_only=False, new_only=None):
    H.stay_awake()
    rd = OUT / name
    rd.mkdir(parents=True, exist_ok=True)
    record(rd, MODELS[model], TASK, __file__)
    its = items(love_only)
    if new_only:                       # only statements the named runs never judged
        done = judged(new_only)
        its = [x for x in its if key(x) not in done]
    (rd / "items.json").write_text(json.dumps(its, ensure_ascii=False, indent=1), encoding="utf-8")
    bsb = C._bsb()
    batches = [(f"B{i // CHUNK + 1:04d}", its[i:i + CHUNK]) for i in range(0, len(its), CHUNK)]

    def one(nm, b):
        out = rd / f"L-{nm}.json"
        if out.exists() or state["stop"] or (rd / "STOP").exists():
            return
        text = TASK + json.dumps({"items": [{"id": x["id"], "verse": x["ref"], "text": bsb(x["ref"])[1],
                                             "statement": f"{x['subject_name']} — {x['verb_text']} ({x['verb']}) — {x['object_name']}"}
                                            for x in b]}, ensure_ascii=False, separators=(",", ":")) + "\n"
        for attempt in range(3):
            res, err = H.call(text, MODELS[model])
            blob = json.dumps(res or {}) + (err or "")
            if (res is None or res.get("is_error")) and "limit" in blob.lower():
                time.sleep(600)
                continue
            if res is None or res.get("is_error"):
                state["fails"] += 1
                if state["fails"] >= 5:
                    state["stop"] = "5 failed calls"
                    return
                continue
            state["fails"] = 0
            u = res.get("usage") or {}
            state["tokens"] += sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                             "cache_creation_input_tokens"))
            ans = H.parse(res)
            got = {a.get("id") for a in (ans or {}).get("answers") or []} & {x["id"] for x in b}
            if len(got) >= 0.9 * len(b):
                out.write_text(json.dumps(ans, ensure_ascii=False, indent=1), encoding="utf-8")
                return
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for f in [ex.submit(one, nm, b) for nm, b in batches]:
            f.result()
    print(f"{name}: {len(its)} candidates, {len(batches)} batches, {state['tokens']:,} tokens; {state['stop'] or 'done'}")


SENSE_TASK = """Each item is a statement drawn from a Bible verse: SUBJECT, VERB, OBJECT, with the verse (the Berean
text) and the verb's Hebrew or Greek lemma. Say what the verb does IN THIS VERSE:
  "sense"   two or three plain English words for the verb's meaning here ("love", "kiss", "give birth to",
            "strike down", "send away")
  "family"  one or two words for the broad kind of act it is, as you would group verbs ("affection", "speech",
            "motion", "violence", "giving", "perception", "worship", "making", ...). Use the same word for the
            same kind every time.
These are candidates for grouping, not rulings. Take no doctrinal position.

Answer with ONLY this JSON object:
{"answers": [{"id": "<item id>", "sense": "...", "family": "..."}]}

"""


def senses(name, model):
    """Plan 2.17, evidence for the predication decision (2026-10-19): what
    verb families emerge from the relations both judges kept. Candidates only;
    nothing is filed by them."""
    H.stay_awake()
    rd = OUT / name
    rd.mkdir(parents=True, exist_ok=True)
    record(rd, MODELS[model], SENSE_TASK, __file__)
    its = [json.loads(x) for x in (OUT / "relations.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    bsb = C._bsb()
    cap = int((rd / "BUDGET").read_text().strip()) if (rd / "BUDGET").exists() else None
    batches = [(f"B{i // 40 + 1:04d}", its[i:i + 40]) for i in range(0, len(its), 40)]

    def one(nm, b):
        out = rd / f"F-{nm}.json"
        if out.exists() or state["stop"] or (rd / "STOP").exists():
            return
        if cap and state["tokens"] >= cap:
            state["stop"] = "token cap reached"
            return
        text = SENSE_TASK + json.dumps({"items": [{"id": x["id"], "verse": x["ref"], "text": bsb(x["ref"])[1],
                                                   "statement": f"{x['subject_name']} — {x['verb_text']} — {x['object_name']}",
                                                   "lemma": x["verb"]} for x in b]},
                                       ensure_ascii=False, separators=(",", ":")) + "\n"
        for attempt in range(3):
            if (rd / "STOP").exists():
                return
            res, err = H.call(text, MODELS[model])
            blob = json.dumps(res or {}) + (err or "")
            if (res is None or res.get("is_error")) and "limit" in blob.lower():
                time.sleep(600)
                continue
            if res is None or res.get("is_error"):
                state["fails"] += 1
                if state["fails"] >= 5:
                    state["stop"] = "5 failed calls"
                    return
                continue
            state["fails"] = 0
            u = res.get("usage") or {}
            state["tokens"] += sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                             "cache_creation_input_tokens"))
            ans = H.parse(res)
            got = {a.get("id") for a in (ans or {}).get("answers") or []} & {x["id"] for x in b}
            if len(got) >= 0.9 * len(b):
                out.write_text(json.dumps(ans, ensure_ascii=False, indent=1), encoding="utf-8")
                return
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for f in [ex.submit(one, nm, b) for nm, b in batches]:
            f.result()
    fam = collections.Counter()
    for p in rd.glob("F-*.json"):
        for a in json.loads(p.read_text(encoding="utf-8")).get("answers") or []:
            fam[(a.get("family") or "").lower()] += 1
    print(f"{name}: {len(its)} relations, {state['tokens']:,} tokens; {state['stop'] or 'done'}; "
          f"{len(fam)} families, top: {fam.most_common(25)}")


ENDS_TASK = """Each item is a statement drawn from a Bible verse (SUBJECT, VERB, OBJECT) in which ONE end has been matched
to a card in a Bible knowledge graph: a CONCEPT card (an idea or kind of thing: "world", "grace", "ground") or an
IMAGE card (a figure the text uses: the house built on the rock in Jesus' parable). Say whether that card fits the
word at that end, in this verse:
  "fits"         concept card: the verse speaks of the concept itself ("God so loved the world"); image card: the
                 word is that figure, as the text uses it
  "particular"   the word is a particular person or thing in the story, not the concept ("the house" Solomon built
                 is the temple; "the lamb" each household ate; "the ground" of one field)
  "other_sense"  the card is the wrong sense of the word here (a card for "husband" where the word means "a man")
  "unsure"       it could be read either way
Read the Berean text. Take no doctrinal position. Unresolved is better than wrong.

Answer with ONLY this JSON object:
{"answers": [{"id": "<item id>", "decision": "fits|particular|other_sense|unsure", "why": "a dozen words"}]}

"""


def end_items():
    """Every card or image end of a statement both judges kept."""
    ents = {}
    for line in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        e = json.loads(line)
        ents[e["id"]] = e
    out = []
    for line in (OUT / "relations.jsonl").read_text(encoding="utf-8").splitlines():
        x = json.loads(line)
        for side, i in (("subject", 0), ("object", 1)):
            # BY WHAT THE END REACHED, not how (the scholar, 2026-10-19: 295 card
            # ends reached through a pronoun were labelled "referent" and skipped)
            if (ents.get(x[side]) or {}).get("type") not in ("person", "place", "group", "being", None) \
                    or x["how"][i].split()[0] in ("card", "image"):
                e = ents.get(x[side]) or {}
                out.append({"id": f"{x['id']}|{side}", "ref": x["ref"], "rel": key(x), "side": side,
                            "card": x[side], "kind": "image" if x["how"][i].startswith("image") else "concept",
                            "card_name": e.get("name"), "card_desc": (e.get("desc") or "")[:200],
                            "statement": f"{x['subject_name']} — {x['verb_text']} — {x['object_name']}"})
    return out


def ends(name, model):
    """Plan 2.17 (2026-10-19: the rule for weak card ends was agreed, provided the
    image handling is respected): the structure decides what
    it can (an image's own verses, a demonstrative, a possessor, "all"); a
    judge decides the rest, "the concept itself, or a particular one?"."""
    H.stay_awake()
    rd = OUT / name
    rd.mkdir(parents=True, exist_ok=True)
    record(rd, MODELS[model], ENDS_TASK, __file__)
    its = end_items()
    (rd / "items.json").write_text(json.dumps(its, ensure_ascii=False, indent=1), encoding="utf-8")
    bsb = C._bsb()
    batches = [(f"B{i // CHUNK + 1:04d}", its[i:i + CHUNK]) for i in range(0, len(its), CHUNK)]

    def one(nm, b):
        out = rd / f"E-{nm}.json"
        if out.exists() or state["stop"] or (rd / "STOP").exists():
            return
        text = ENDS_TASK + json.dumps({"items": [{"id": x["id"], "verse": x["ref"], "text": bsb(x["ref"])[1],
                                                  "statement": x["statement"], "end": x["side"],
                                                  "card": {"kind": x["kind"], "name": x["card_name"],
                                                           "description": x["card_desc"]}} for x in b]},
                                      ensure_ascii=False, separators=(",", ":")) + "\n"
        for attempt in range(3):
            res, err = H.call(text, MODELS[model])
            blob = json.dumps(res or {}) + (err or "")
            if (res is None or res.get("is_error")) and "limit" in blob.lower():
                time.sleep(600)
                continue
            if res is None or res.get("is_error"):
                state["fails"] += 1
                if state["fails"] >= 5:
                    state["stop"] = "5 failed calls"
                    return
                continue
            state["fails"] = 0
            u = res.get("usage") or {}
            state["tokens"] += sum(u.get(k) or 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                             "cache_creation_input_tokens"))
            ans = H.parse(res)
            got = {a.get("id") for a in (ans or {}).get("answers") or []} & {x["id"] for x in b}
            if len(got) >= 0.9 * len(b):
                out.write_text(json.dumps(ans, ensure_ascii=False, indent=1), encoding="utf-8")
                return
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for f in [ex.submit(one, nm, b) for nm, b in batches]:
            f.result()
    print(f"{name}: {len(its)} ends, {len(batches)} batches, {state['tokens']:,} tokens; {state['stop'] or 'done'}")


def ends_merge(r1, r2):
    """relations.jsonl -> relations-final.jsonl: a statement keeps a card or
    image end only where both judges say it fits; the rest are dropped, with
    their end's verdicts kept in the provenance."""
    def load(r):
        a = {}
        for p in (OUT / r).glob("E-*.json"):
            for x in json.loads(p.read_text(encoding="utf-8")).get("answers") or []:
                a[x.get("id")] = x.get("decision")
        return a
    a1, a2 = load(r1), load(r2)
    its = json.loads((OUT / r1 / "items.json").read_text(encoding="utf-8"))
    st, bad = collections.Counter(), set()
    for x in its:
        d1, d2 = a1.get(x["id"]), a2.get(x["id"])
        st[f"{x['kind']}: {d1} / {d2}"] += 1
        if not (d1 == "fits" and d2 == "fits"):
            bad.add(tuple(x["rel"]))
    rel = [json.loads(l) for l in (OUT / "relations.jsonl").read_text(encoding="utf-8").splitlines()]
    keep = [x for x in rel if key(x) not in bad]
    (OUT / "relations-final.jsonl").write_text("".join(json.dumps(k, ensure_ascii=False) + "\n" for k in keep),
                                               encoding="utf-8")
    print(f"{len(its)} ends: {dict(st.most_common(12))}")
    print(f"{len(rel)} relations -> {len(keep)} kept ({len(rel) - len(keep)} dropped on an end) -> relations-final.jsonl")


def answers(name):
    a = {}
    for p in (OUT / name).glob("L-*.json"):
        for x in json.loads(p.read_text(encoding="utf-8")).get("answers") or []:
            a[x.get("id")] = x.get("decision")
    return a


def merge(r1, r2):
    """r1, r2: one judge's runs each, comma-separated (all-sonnet,delta-sonnet).
    The candidates are the CURRENT resolution's, each matched to its answers
    by clause and ends, so a statement whose ends changed is never kept on a
    judgment of the old one."""
    its = items()
    a1, a2 = judged(r1.split(",")), judged(r2.split(","))
    st, keep = collections.Counter(), []
    for x in its:
        d1, d2 = a1.get(key(x)), a2.get(key(x))
        st[f"{d1} / {d2}"] += 1
        if d1 == "yes" and d2 == "yes":
            keep.append({**x, "reading": "lifted from the clause", "by": f"two judges ({r1}; {r2})"})
    (OUT / "relations.jsonl").write_text("".join(json.dumps(k, ensure_ascii=False) + "\n" for k in keep), encoding="utf-8")
    print(f"{len(its)} candidates: {dict(st.most_common(8))}; kept {len(keep)}")
    print("by verb:", collections.Counter(k["verb"] for k in keep).most_common(10))


if __name__ == "__main__":
    if sys.argv[1] == "run":
        nw = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--new-only=")), None)
        run(sys.argv[2], sys.argv[3], "--love" in sys.argv, nw)
    elif sys.argv[1] == "senses":
        senses(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "ends":
        ends(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "ends-merge":
        ends_merge(sys.argv[2], sys.argv[3])
    else:
        merge(sys.argv[2], sys.argv[3])
