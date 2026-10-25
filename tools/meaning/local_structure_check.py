"""LOCAL PASS: does the verse say what its clause record says? (plan 8.2j, 2026-10-24)

The low-level structure (out/meaning/clause-records.jsonl) records each clause as subject -verb-> object, the ends
resolved to cards. This pass asks the local model one narrow question per record, with the verse and its neighbours:
does the verse say this? And where the record has no doer, who does it according to the text? It is the check Doug
asked for ("have it look at the low level structure"): the structure is read against the text, record by record,
and only what the pass flags goes to a Claude judge.

Planted faults prove it before it is trusted: a share of the records go in a second time with a wrong doer or the
opposite verb, labelled here and never shown to the model. A pass that does not catch them is not used.

Ollama runs on the Mac, reached by tunnel (ssh -N -L 11434:localhost:11434 macmini).

    python tools/meaning/local_structure_check.py run CARD [--model gemma4:26b] [--plant 0.25]
    python tools/meaning/local_structure_check.py run all --plant 0.05    (every clause record, ~40 h on the M2)
    python tools/meaning/local_structure_check.py report CARD
    python tools/meaning/local_structure_check.py export all --plant 0.05   a job for the Mac's own runner
    python tools/meaning/local_structure_check.py import all                (tools/grunt: push, then pull)
      -> out/meaning/local-structure/<card>.jsonl (resumable)
"""
import collections
import glob
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from derive import BOOK  # noqa: E402

OUT = ROOT / "out" / "meaning" / "local-structure"
URL = "http://localhost:11434/api/chat"
ANSWERS = ("yes", "wrong_who", "no")
OPPOSITE = {"built": "destroyed", "build": "destroy", "building": "destroying", "destroyed": "built",
            "destroying": "building", "repair": "abandon", "restored": "abandoned", "filled": "emptied",
            "defiled": "cleansed", "defile": "cleanse", "dedicated": "desecrated", "consecrated": "defiled"}
DECOYS = ("Abraham", "Nebuchadnezzar", "Pontius Pilate", "Goliath")  # the first not named near the verse is used

# v1 asked "does the verse say this?" and caught 21 of 21 planted faults, but named doers for intents and commands.
# v2 and v3 showed the record's mode and asked the model to judge it: the "no" answers doubled, then fell to 30,
# nearly all quarrels with the mode, tense or negation ("you are not the one to build" refused against
# "David -build (not)->"). The mode is read off the verb form and the structure already has it right; a 26B model
# judges it worse. So v4 asks only WHO and WHAT (Doug: "limiting responsibilities of any pass"), and the mode stays
# with the structure, where the evidence cards use it.
BRIEF_V3 = """You check a Bible knowledge graph's low-level structure against the text. You get one verse (with the \
verse before and after) and ONE record the graph made from it: DOER -ACTION-> RECEIVER [MODE]. Answer one question: \
does the verse say this action, in this mode?

How to read the record:
- MODE is how the verse puts the action. "stated": the verse asserts it, in ANY tense: "he built", "he builds" and \
"he will build" / "I will fill this house" are all stated. "promised": a pledge form ("let me", "I shall surely"). \
"commanded": an order. "asked": a question. "wished": "may he". "nonfinite": an infinitive or participle ("to \
build", "building"), often a purpose or intent.
- "(not)" after the action means the record ALREADY says it does not happen: "David -build (not)-> temple" is exactly \
right for "you are not the one to build it".
- DOER and RECEIVER are the graph's names for things, not the verse's words. The verse may call the temple "a house \
for My Name", "the house of the LORD" or "it"; that is still the temple. Only object if the verse means a \
DIFFERENT thing (another house, a different person).

- "yes": the verse says this action, by this doer, to this receiver, in this mode. A doer "unnamed" is fine if the \
action and receiver are right. "David wanted to build a house" fits "unnamed -build-> house [nonfinite]".
- "wrong_who": the action is in the verse, but the doer or the receiver recorded is not the one the verse means.
- "no": the verse does not say this action at all, says the opposite, or says it in a different mode (the record \
says "stated" but the verse only commands, asks, wishes, or intends it). A future is not a different mode.

Then, ONLY if the record's doer is "unnamed": who is the doer of this action, according to this verse and the ones \
around it? For a command, the one commanded; for "to build", the one who would build. Give the name or group as the \
text has it ("Solomon", "the Babylonians", "the people"), or "not stated".

Worked examples:
- Rom 11:3 "they have killed Your prophets and torn down Your altars", record: the Israelites -torn down-> altar \
[stated] -> yes.
- Rom 11:3, record: Elijah -torn down-> altar [stated] -> wrong_who: Elijah is the one speaking; "they" tore them \
down.
- Lev 26:30 "I will destroy your high places, cut down your incense altars", record: God -built-> altar [stated] \
-> no: God says He will cut them down.
- Lev 26:30, record: unnamed -cut down-> altar [stated] -> yes, doer: "the LORD" (He is speaking: "I will").
- 2 Sam 7:5 "Are you the one to build for Me a house?", record: David -build (not)-> house [asked] -> yes: the \
question and the "not" are both in the record.
- Lev 26:30, record: unnamed -cut down-> altar [stated] -> yes: "I will cut down" is a stated future.
- Lev 26:30, record: unnamed -cut down-> altar [nonfinite] -> no: the verse states it, not "to cut down".

Answer with ONLY a JSON object, nothing before or after it: {"answer": "yes" | "wrong_who" | "no", \
"doer": "<name, or not stated, or empty if the doer was named>", "reason": "<one line quoting the verse>"}"""


BRIEF = """You check a Bible knowledge graph's low-level structure against the text. You get one verse (with the \
verse before and after) and ONE record the graph made from it: DOER -ACTION-> RECEIVER. Answer one question: are \
this action, this doer and this receiver in the verse?

Judge ONLY who and what. IGNORE whether it happened: tense, future, negation ("not"), commands, questions, wishes \
and purposes ("to build") all count. "You are not the one to build it" HAS the action build, doer "you", receiver \
"it". DOER and RECEIVER are the graph's names for things, not the verse's words: the temple may be "a house for My \
Name", "the house of the LORD" or "it". "unnamed" means the graph did not name that end; it is never wrong by itself.

- "yes": the action is in the verse, and the doer and receiver are the ones the verse means.
- "wrong_who": the action is there, but the doer or the receiver is a DIFFERENT person or thing than the verse means \
(another house, another person, a part instead of the whole).
- "no": the verse has no such action at all, or the opposite action.

Then, ONLY if the record's doer is "unnamed": who is the doer of this action, according to this verse and the ones \
around it? For a command, the one commanded; for "to build", the one who would build. Give the name or group as the \
text has it ("Solomon", "the Babylonians", "the people"), or "not stated".

Worked examples:
- Rom 11:3 "they have killed Your prophets and torn down Your altars", record: the Israelites -torn down-> altar \
-> yes.
- Rom 11:3, record: Elijah -torn down-> altar -> wrong_who: Elijah is the one speaking; "they" tore them down.
- Lev 26:30 "I will destroy your high places, cut down your incense altars", record: God -built-> altar -> no: \
God says He will cut them down.
- Lev 26:30, record: unnamed -cut down-> altar -> yes, doer: "the LORD" (He is speaking: "I will").
- 2 Sam 7:5 "Are you the one to build for Me a house to dwell in?", record: David -build-> house -> yes (a question \
still has the action, the doer and the receiver).
- 2 Kgs 11:18 "the people of the land went to the temple of Baal and tore it down", record: unnamed -tore down-> \
The Temple -> wrong_who: "it" is the temple of Baal, not the LORD's temple.

Answer with ONLY a JSON object, nothing before or after it: {"answer": "yes" | "wrong_who" | "no", \
"doer": "<name, or not stated, or empty if the doer was named>", "reason": "<one line quoting the verse>"}"""


def entities():
    names = {}
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                names.setdefault(e["id"], e.get("name") or e["id"])
    return names


def texts():
    order, text = [], {}
    for ln in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        if "b" in d:
            k = f"{BOOK.get(d['b'], d['b'])}.{d['c']}.{d['v']}"
            order.append(k)
            text[k] = d["t"]
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    pos = {k: i for i, k in enumerate(order)}

    def ctx(ref):
        k = moved.get(ref, ref)
        i = pos.get(k)
        if i is None:
            return None, None, None
        return (text[order[i - 1]] if i else None, text[k], text[order[i + 1]] if i + 1 < len(order) else None)
    return ctx


def items(card, plant):
    names = entities()
    ctx = texts()
    out = []
    for ln in open(ROOT / "out" / "meaning" / "clause-records.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        s, o = r.get("subject") or {}, r.get("object") or {}
        if card != "all" and card not in (s.get("record"), o.get("record")):
            continue
        before, text, after = ctx(r["ref"])
        it = {"key": r["clause"], "ref": r["ref"], "before": before, "text": text, "after": after,
              "doer": names.get(s.get("record"), s.get("record")) if s.get("record") else "unnamed",
              "action": r["verb_text"] + (" (not)" if r.get("negated") else "") + (" (passive)" if r.get("passive") else ""),
              "receiver": names.get(o.get("record"), o.get("record")) if o.get("record") else "unnamed",
              "mode": r.get("modality") or "stated", "planted": None}
        out.append(it)
    rnd = random.Random(7)
    fakes = []
    for it in rnd.sample(out, int(len(out) * plant)):
        f = dict(it, key=it["key"] + "#planted")
        verb = it["action"].split(" (")[0]
        near = " ".join(x or "" for x in (it["before"], it["text"], it["after"]))
        decoy = next((d for d in DECOYS if d.split()[-1] not in near), None)
        if it["doer"] != "unnamed" and it["doer"] != names.get(card) and decoy:
            f.update(doer=decoy, planted="wrong_who")
        elif verb in OPPOSITE:
            f.update(action=OPPOSITE[verb], planted="no")
        else:
            continue
        fakes.append(f)
    allit = out + fakes
    rnd.shuffle(allit)
    return allit


OPTIONS = {"temperature": 0, "num_ctx": 4096}


def messages(it):
    msg = {k: it[k] for k in ("ref", "before", "text", "after")}
    # v4: who and what only; the mode, "(not)" and "(passive)" stay with the structure
    msg["record"] = f"{it['doer']} -{it['action'].split(' (')[0]}-> {it['receiver']}"
    return [{"role": "system", "content": BRIEF}, {"role": "user", "content": json.dumps(msg, ensure_ascii=False)}]


def parse(raw, secs):
    a = re.search(r'"answer"\s*:\s*"(yes|wrong_who|no)"', raw)
    doer = re.search(r'"doer"\s*:\s*"([^"]*)"', raw)
    reason = re.search(r'"reason"\s*:\s*"(.*)"\s*\}', raw, re.S)
    if not a:
        return {"error": "unparsed: " + raw[:200], "secs": secs}
    return {"answer": a[1], "doer_found": doer[1] if doer else "", "reason": reason[1] if reason else "", "secs": secs}


def ask(model, it):
    body = {"model": model, "stream": False, "think": False, "options": OPTIONS, "messages": messages(it)}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.load(r)
    return parse(d["message"]["content"], round(time.time() - t, 2))


def export(card, model, plant):
    """A job for the Mac's runner (tools/grunt): the model sees only the calls; the items, with what was planted,
    stay here in out/grunt/jobs/<name>.items.jsonl"""
    jobs = ROOT / "out" / "grunt" / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    name = f"structure-{card}"
    its = items(card, plant)
    with open(jobs / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": model, "options": OPTIONS, "pass": "local_structure_check"}}) + "\n")
        for it in its:
            f.write(json.dumps({"key": it["key"], "messages": messages(it)}, ensure_ascii=False) + "\n")
    with open(jobs / f"{name}.items.jsonl", "w", encoding="utf-8") as f:
        for it in its:
            f.write(json.dumps({**it, "model": model}, ensure_ascii=False) + "\n")
    print(f"{len(its)} calls -> {jobs / (name + '.jsonl')}")


def import_(card):
    """The Mac's raw answers joined back to the items, in the shape `run` writes, so `report` and the evidence
    cards read them unchanged"""
    name = f"structure-{card}"
    its = {json.loads(l)["key"]: json.loads(l) for l in open(ROOT / "out" / "grunt" / "jobs" / f"{name}.items.jsonl",
                                                              encoding="utf-8")}
    # pushed under a priority prefix ("1-structure-temple.jsonl"); the runner works in name order
    done = sorted((ROOT / "out" / "grunt" / "done").glob(f"*{name}.jsonl"))[-1]
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(OUT / f"{card}.jsonl", "w", encoding="utf-8") as f:
        for l in open(done, encoding="utf-8"):
            d = json.loads(l)
            r = parse(d["content"], d.get("secs")) if "content" in d else {"error": d.get("error")}
            f.write(json.dumps({**its[d["key"]], **r}, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} of {len(its)} answered -> {OUT / (card + '.jsonl')}")


def run(card, model, plant):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{card}.jsonl"
    done = {json.loads(l)["key"] for l in open(path, encoding="utf-8")} if path.exists() else set()
    todo = [it for it in items(card, plant) if it["key"] not in done]
    with open(path, "a", encoding="utf-8") as f:
        for i, it in enumerate(todo):
            try:
                r = ask(model, it)
            except Exception as e:  # a failed call is recorded, never counted as an answer
                r = {"error": str(e)[:200]}
            f.write(json.dumps({**it, "model": model, **r}, ensure_ascii=False) + "\n")
            f.flush()
            if (i + 1) % 20 == 0:
                print(f"{i + 1}/{len(todo)}", flush=True)
    print(f"done: {path}")


def report(card):
    rows = [json.loads(l) for l in open(OUT / f"{card}.jsonl", encoding="utf-8")]
    ok = [r for r in rows if "answer" in r]
    real = [r for r in ok if not r["planted"]]
    fake = [r for r in ok if r["planted"]]
    print(f"{card}: {len(ok)} answered of {len(rows)} ({len(real)} real records, {len(fake)} planted faults)")
    print(f"  planted faults caught: {sum(r['answer'] != 'yes' for r in fake)} of {len(fake)}"
          f"  ({sum(r['answer'] == r['planted'] for r in fake)} with the exact kind)")
    print(f"  real records: " + ", ".join(f"{k} {v}" for k, v in collections.Counter(r['answer'] for r in real).items()))
    secs = sum(r["secs"] for r in ok)
    print(f"  speed: {len(ok) / secs * 60:.1f} records/min")
    filled = [r for r in real if r["doer"] == "unnamed" and r["doer_found"] and r["doer_found"] != "not stated"]
    print(f"  unnamed doers named by the text: {len(filled)} of {sum(r['doer'] == 'unnamed' for r in real)}")
    for r in sorted(filled, key=lambda r: r["ref"]):
        print(f"    {r['ref']:12} {r['doer_found']} -{r['action']}-> {r['receiver']}")
    print("  real records it says the verse does not support:")
    for r in sorted((r for r in real if r["answer"] != "yes"), key=lambda r: r["ref"]):
        print(f"    {r['ref']:12} [{r['answer']}] {r['doer']} -{r['action']}-> {r['receiver']}  | {r['reason'][:110]}")


if __name__ == "__main__":
    cmd, card = sys.argv[1], sys.argv[2]
    if cmd == "run":
        model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "gemma4:26b"
        plant = float(sys.argv[sys.argv.index("--plant") + 1]) if "--plant" in sys.argv else 0.25
        run(card, model, plant)
    elif cmd == "export":
        model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "gemma4:26b"
        plant = float(sys.argv[sys.argv.index("--plant") + 1]) if "--plant" in sys.argv else 0.25
        export(card, model, plant)
    elif cmd == "import":
        import_(card)
    else:
        report(card)
