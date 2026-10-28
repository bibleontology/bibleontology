"""Who does it? Reference resolution of unnamed clause subjects, by the Mac's local model (plan 2.17 step 1, 8.2o).

Doug, 2026-10-25: "this is part of the reason why I wanted to do the pronoun/reference resolution at the clause level
first", and on the Mac: "want it to be constantly providing value around the clock". On the whole-graph structure
check the Mac's strongest answer was never its verdict on a record (about 40% of its flags genuine after three
askings) but naming who an unnamed doer is: 4,114 of 5,047. So this pass asks only that, of every clause whose
subject the graph left unnamed, and nothing else.

It scores itself: a share of subjects the graph has ALREADY resolved through a referent go in with the name hidden
(planted), and the answer is compared with the record by name, so every batch carries its own accuracy. What it
returns is a CANDIDATE: a name as the text has it, mapped to a record here, never written into the graph without a
judge (and, for God, Jesus or the Spirit, Doug's rule: the clause or the sentences just before name him, and the
original agrees).

    python tools/meaning/local_resolve.py export      the job, Genesis first, then the Gospels and Acts
    python tools/meaning/local_resolve.py report      after `grunt.py pull`: the planted score and the candidates
"""
import collections
import glob
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
from local_structure_check import BOOK, OPTIONS, berean_words, in_verse  # noqa: E402

NAME = "2e-resolve-subjects"
JOBS = ROOT / "out" / "grunt" / "jobs"
OUT = ROOT / "out" / "meaning" / "local-resolve"
PLANT = 0.05
FIRST = ["Gen", "Mat", "Mrk", "Luk", "Jhn", "Act"]  # Genesis first (Doug, /ops: Gen 1 is the most visited)

BRIEF = """You read one Bible verse, with the verses before it, and answer ONE question about one action in it: WHO \
does this action? The verse is from the Berean Standard Bible.

You get the verse, the verses before and after, and the ACTION (a word from the verse). Find who performs it, \
reading back through the verses before when the verse says only "he", "she", "they", "we", "I", "you" or nothing.

Answer with the name or group exactly as the text gives it ("Abraham", "the Israelites", "the LORD", "Jesus", \
"the disciples", "Pharaoh's daughter"). Then say how you know:
- "this verse": the verse itself names them.
- "nearby": the verse says "he"/"they"/nothing, and a verse shown names them.
- "speaker": the action is the speaker's own ("I will") or the one addressed ("you shall"), and the text names that \
speaker or hearer.
- "general": not one person but anyone of a kind ("whoever digs a pit", "a man"): give the words.
- "not stated": the text shown does not say who.
Never guess beyond the text shown. If two people could be meant, answer "not stated".

Worked examples:
- Acts 9:4 "He fell to the ground and heard a voice say to him, 'Saul, Saul, why do you persecute Me?'" (9:3 "As \
Saul drew near to Damascus"), ACTION "fell" -> {"who": "Saul", "how": "nearby", "words": "As Saul drew near"}
- Gen 22:3 "So Abraham got up early the next morning and saddled his donkey", ACTION "saddled" -> {"who": \
"Abraham", "how": "this verse", "words": "Abraham got up early"}
- Gen 4:8 "Cain rose up against his brother Abel and killed him", ACTION "killed" -> {"who": "Cain", "how": "this \
verse", "words": "Cain rose up"}
- Exod 20:13 "You shall not murder.", ACTION "murder" (20:1 "And God spoke all these words", to Israel) -> {"who": \
"Israel", "how": "speaker", "words": "And God spoke all these words"}
- Prov 26:27 "He who digs a pit will fall into it", ACTION "fall" -> {"who": "he who digs a pit", "how": "general", \
"words": "He who digs a pit"}
- Ps 12:2 "They speak falsehood to one another", with no one named before -> {"who": "", "how": "not stated", \
"words": ""}

Answer with ONLY a JSON object, nothing before or after it: {"who": "...", "how": "this verse" | "nearby" | \
"speaker" | "general" | "not stated", "words": "<the words that name them, quoted from the text shown>"}"""


def names():
    out, alias = {}, collections.defaultdict(set)
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                out.setdefault(e["id"], e.get("name") or e["id"])
                for a in [e.get("name")] + list(e.get("aka") or []) + list(e.get("aliases") or []):
                    if isinstance(a, str) and a:
                        alias[norm(a)].add(e["id"])
    return out, alias


def norm(s):
    s = re.sub(r"^(the|a|an)\s+", "", (s or "").lower().strip())
    return re.sub(r"[^a-z0-9 ]", "", s).strip()


def context(k_before=3):
    order, text = [], {}
    for ln in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        if "b" in d:
            k = f"{BOOK.get(d['b'], d['b'])}.{d['c']}.{d['v']}"
            order.append(k)
            text[k] = d["t"]
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    pos = {k: i for i, k in enumerate(order)}

    def ctx(ref):  # ref in MACULA's numbering; the text read in the Berean's
        k = moved.get(ref, ref)
        i = pos.get(k)
        if i is None:
            return None
        before = [f"{order[j]} {text[order[j]]}" for j in range(max(0, i - k_before), i)]
        after = f"{order[i + 1]} {text[order[i + 1]]}" if i + 1 < len(order) else ""
        return {"ref": k, "before": before, "text": text[k], "after": after}
    return ctx


def export():
    ents, _ = names()
    ctx = context()
    bw = berean_words()
    rnd = random.Random(25)
    asks, plants = [], []
    for ln in open(ROOT / "out" / "meaning" / "clause-records.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        s = r.get("subject") or {}
        c = ctx(r["ref"])
        if not c:
            continue
        action = in_verse(bw.get(r.get("verb_key"), []), c["text"]) or r.get("verb_text")
        if not action:
            continue
        it = {"key": r["clause"], "ref": r["ref"], "action": action, **c}
        if s.get("how") == "unnamed":
            asks.append(it)
        elif (s.get("how") or "").startswith("referent") and s.get("record") and rnd.random() < PLANT * 3:
            plants.append({**it, "key": r["clause"] + "#planted", "answer": s["record"],
                           "answer_name": ents.get(s["record"], s["record"])})
    plants = rnd.sample(plants, min(len(plants), int(len(asks) * PLANT)))
    rank = {b: i for i, b in enumerate(FIRST)}
    allit = asks + plants
    allit.sort(key=lambda x: (rank.get(x["ref"].split(".")[0], len(FIRST)), rnd.random()))
    JOBS.mkdir(parents=True, exist_ok=True)
    with open(JOBS / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f, \
            open(JOBS / f"{NAME}.items.jsonl", "w", encoding="utf-8") as g:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "who does it"}}) + "\n")
        for it in allit:
            msg = {"verse": f"{it['ref']} {it['text']}", "before": it["before"], "after": it["after"],
                   "ACTION": it["action"]}
            f.write(json.dumps({"key": it["key"], "messages": [
                {"role": "system", "content": BRIEF},
                {"role": "user", "content": json.dumps(msg, ensure_ascii=False)}]}, ensure_ascii=False) + "\n")
            g.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{len(asks)} unnamed subjects asked, {len(plants)} planted (name hidden) -> {JOBS / (NAME + '.jsonl')}")


def parse(raw):
    who = re.search(r'"who"\s*:\s*"([^"]*)"', raw or "")
    how = re.search(r'"how"\s*:\s*"([^"]*)"', raw or "")
    words = re.search(r'"words"\s*:\s*"([^"]*)"', raw or "")
    if not how:
        return None
    return {"who": who[1] if who else "", "how": how[1], "words": words[1] if words else ""}


def report():
    ents, alias = names()
    its = {json.loads(l)["key"]: json.loads(l) for l in open(JOBS / f"{NAME}.items.jsonl", encoding="utf-8")}
    done = sorted((ROOT / "out" / "grunt" / "done").glob(f"*{NAME}.jsonl"))
    if not done:
        print("nothing pulled yet")
        return
    rows = []
    for ln in open(done[-1], encoding="utf-8"):
        d = json.loads(ln)
        p = parse(d.get("content"))
        if p and d["key"] in its:
            it = its[d["key"]]
            p["ids"] = sorted(alias.get(norm(p["who"]), ()))
            rows.append({**it, **p})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "answers.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    plant = [r for r in rows if "answer" in r]
    real = [r for r in rows if "answer" not in r]
    hit = [r for r in plant if r["answer"] in r["ids"] or norm(r["who"]) == norm(r["answer_name"])]
    named = [r for r in plant if r["how"] not in ("not stated", "general")]
    print(f"{len(rows)} answered ({len(plant)} planted, {len(real)} real)")
    if plant:
        print(f"planted: named {len(named)} of {len(plant)}; the right one {len(hit)} "
              f"({len(hit) / max(len(named), 1):.0%} of those it named)")
        for r in [r for r in named if r not in hit][:10]:
            print(f"   missed {r['ref']:12} {r['action']:14} said {r['who']!r:28} record {r['answer_name']!r}")
    c = collections.Counter(r["how"] for r in real)
    mapped = [r for r in real if len(r["ids"]) == 1]
    print("real, how:", dict(c), f"| mapped to exactly one record: {len(mapped)}")


if __name__ == "__main__":
    {"export": export, "report": report}[sys.argv[1]]()
