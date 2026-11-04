"""The named gods the text opposes: candidates for their nodes and relations (plan A.44, 2026-11-03).

Doug: "there seems to be a gap for named idols such as Baal"; approved for the tail of the A.40-A.44 bundle. The
graph has no god Baal (its `baal` is a Reubenite) and none of the others, though the Berean names them in about 200
verses. The Mac reads every such verse once and says what the verse itself says is done to, for or about the god.
Nothing is written to the graph: Claude reads the candidates, DeepSeek checks a second time where the divine persons
are not involved, and the nodes and relations are built from what holds.

    python tools/meaning/gods_scan.py build    -> out/grunt/jobs/15-gods-scan.jsonl (+ .key.jsonl)
    python tools/meaning/gods_scan.py report   <- out/grunt/done/15-gods-scan.jsonl
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOBS, DONE = ROOT / "out" / "grunt" / "jobs", ROOT / "out" / "grunt" / "done"
NAME = "15-gods-scan"
# the names as the Berean writes them; a place or a person's name that carries one (Baal-peor the place, Baal-hanan,
# Rimmon the man) is the Mac's to tell apart, by the verse
GODS = ["Baal", "Baals", "Baal of Peor", "Baal-berith", "Baal-zebub", "Asherah", "Asherahs", "Asherah poles",
        "Ashtoreth", "Ashtoreths", "Molech", "Chemosh", "Dagon", "Milcom", "Rimmon", "Nisroch", "Tammuz", "Nehushtan",
        "Artemis", "Zeus", "Hermes", "Bel", "Nebo", "Marduk", "Rephan", "Sakkuth", "Kaiwan", "Succoth-benoth",
        "Nergal", "Ashima", "Nibhaz", "Tartak", "Adrammelech", "Anammelech", "Gad", "Meni", "Queen of Heaven"]
PAT = re.compile(r"\b(" + "|".join(sorted(map(re.escape, GODS), key=len, reverse=True)) + r")\b")
BRIEF = """You read one Bible verse (the Berean Standard Bible), with the verses just before it, and report what it says about a god other than the LORD that it names.

Answer with ONE line of JSON:
{"god": "...", "kind": "...", "acts": [{"who": "...", "did": "...", "to": "..."}], "note": "..."}

- god: the god's name as the verse gives it.
- kind: "god" if the word names the god (or its image, pole or altar); "place" or "person" if it is part of a place or a person's name (Baal-perazim, Baal-hanan; Gad the tribe, Nebo the mountain or town); "none" if neither.
- acts: each thing the verse says is DONE to, for, with or about the god: who did it (as the verse names them; resolve "they", "he" from the verses before), what they did in a few words ("served", "built an altar to", "tore down the altar of", "burned his son to", "fell before", "consulted"), and to what (the god, its altar, its pole, its prophets, its temple). Only what the verse says happened. Commanded, forbidden, warned or threatened is not done: put it in "did" as "was commanded to tear down", "was warned not to serve".
- If the god itself is said to do or not do something ("Dagon had fallen on his face", "there was no voice, no answer"), give "who" as the god.
- note: one short line only if something needs saying (a place and a god in one verse); else "".
- kind "place", "person" or "none": acts is [].
Copy nothing that is not in the verse."""


def verses():
    rows = []
    for l in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if "t" in r:
            rows.append(r)
    return rows


def build():
    rows = verses()
    items = []
    for i, r in enumerate(rows):
        names = sorted(set(PAT.findall(r["t"])))
        if not names:
            continue
        before = [x["t"] for x in rows[max(0, i - 2):i] if x["b"] == r["b"]]
        ref = f"{r['b']} {r['c']}:{r['v']}"
        items.append({"key": ref, "ref": ref, "names": names, "verse": r["t"], "context": before})
    JOBS.mkdir(parents=True, exist_ok=True)
    with open(JOBS / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": {"temperature": 0, "num_ctx": 4096},
                                     "pass": "gods_scan"}}) + "\n")
        for c in items:
            ctx = "".join(f"(before) {x}\n" for x in c["context"])
            f.write(json.dumps({"key": c["key"], "messages": [
                {"role": "system", "content": BRIEF},
                {"role": "user", "content": f"NAMES: {', '.join(c['names'])}\n{ctx}VERSE ({c['ref']}): \"{c['verse']}\""}]},
                ensure_ascii=False) + "\n")
    with open(JOBS / f"{NAME}.key.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for c in items:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{NAME}: {len(items)} verses")


def report():
    keys = {json.loads(l)["key"]: json.loads(l) for l in open(JOBS / f"{NAME}.key.jsonl", encoding="utf-8")}
    kinds, gods, bad, out = {}, {}, 0, []
    for l in open(DONE / f"{NAME}.jsonl", encoding="utf-8"):
        r = json.loads(l)
        try:
            a = json.loads(re.search(r"\{.*\}", r.get("content") or "", re.S).group(0))
        except (AttributeError, ValueError):
            bad += 1
            continue
        kinds[a.get("kind")] = kinds.get(a.get("kind"), 0) + 1
        if a.get("kind") == "god":
            gods[a.get("god")] = gods.get(a.get("god"), 0) + 1
        out.append(dict(keys.get(r["key"], {}), answer=a))
    (ROOT / "out" / "grunt" / f"{NAME}.candidates.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in out), encoding="utf-8")
    print(f"{len(out)} answered, {bad} unreadable; kinds {kinds}")
    print("gods:", dict(sorted(gods.items(), key=lambda kv: -kv[1])))


def ds():
    """DeepSeek's second read of the Mac's acts, as claims, with moved-verse plants. The Mac reads laws and commands
    as done (Lev 20:2-4, Deut 12:3); the re-read brief separates them. Acts naming a divine person are never sent."""
    import random
    sys.path.insert(0, str(ROOT / "tools" / "meaning"))
    import deepseek_judge as dj
    import verse_reread as vr
    div = re.compile(r"\b(LORD|God|Lord|Jesus|Christ|Spirit|Father)\b")
    items, kept = [], 0
    for l in open(ROOT / "out" / "grunt" / f"{NAME}.candidates.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if r["answer"].get("kind") != "god":
            continue
        for k, a in enumerate(r["answer"].get("acts") or []):
            if div.search(json.dumps(a)):
                kept += 1
                continue
            claim = " ".join(str(a.get(x) or "").strip() for x in ("who", "did", "to")).strip()
            items.append({"key": f"{r['ref']}#{k}", "claim": claim, "ref": r["ref"], "verse": r["verse"],
                          "context": r.get("context") or [], "act": a, "god": r["answer"].get("god")})
    rnd = random.Random(20261103)
    pool = list(items)
    rnd.shuffle(pool)
    plants = [dict(a, key=f"P-moved-{i}", claim=b["claim"], planted="not_said")
              for i, (a, b) in enumerate(zip(pool[:16], pool[16:32])) if a["ref"] != b["ref"]]
    allit = items + plants
    rnd.shuffle(allit)
    batches = []
    for bi in range(0, len(allit), dj.BATCH):
        part = allit[bi:bi + dj.BATCH]
        for n, it in enumerate(part, 1):
            it["id"] = f"r{n}"
        batches.append({"batch": f"GODS-{bi // dj.BATCH + 1:02d}", "items": part,
                        "task": vr.DS_BRIEF + "\n\nITEMS (" + str(len(part)) + "):\n\n" + "\n\n".join(vr.ds_text(x) for x in part) + "\n"})
    dj.write_batches(NAME, batches)
    print(f"{NAME}: {len(items)} acts, {len(plants)} planted, {len(batches)} batches; {kept} naming a divine person kept back")


MOOD_BRIEF = """You read Bible verses (the Berean Standard Bible) and say, for each item, in what way the verse speaks of an action. The action is given in plain words; it is taken from the verse.

Answer each item with ONE line of JSON:
{"id": "...", "verdict": "...", "words": "..."}

verdict (how the verse speaks of it):
- "happened": the verse tells it as having happened (or happening) in the story: "the Israelites served the Baals".
- "law": a rule for whoever does it: "anyone who gives his children to Molech must surely be put to death".
- "command": someone is told to do it: "you are to tear down their altars".
- "prohibition": someone is told not to: "you must not set up an Asherah pole".
- "warning": it is threatened or warned against.
- "prophecy": it is foretold, or a judgment announced: "Bel bows down, Nebo stoops".
- "question": it is asked, not told.
- "other": none of these; say which in words.
words: the few words of the verse that show it.

Example:
[r1] ACTION: the people burn up Asherah poles
  VERSE (Deut 12:3): "Tear down their altars, smash their sacred pillars, burn up their Asherah poles..."
{"id": "r1", "verdict": "command", "words": "burn up their Asherah poles"}"""


def mood():
    """One narrow question to DeepSeek: does the verse tell it as done, or as a law, command or prophecy? The Mac's
    acts lose the verse's mood (Lev 20:2, a law, came back as 'gives his children to Molech'), and a re-read of the
    claim cannot see what the claim dropped; DeepSeek called those 'stated' twice. Divine-person acts never sent."""
    sys.path.insert(0, str(ROOT / "tools" / "meaning"))
    import deepseek_judge as dj
    rows = [json.loads(l) for l in open(ROOT / "out" / "grunt" / f"{NAME}.agreement.jsonl", encoding="utf-8")]
    batches = []
    for bi in range(0, len(rows), dj.BATCH):
        part = [dict(r) for r in rows[bi:bi + dj.BATCH]]
        for n, it in enumerate(part, 1):
            it["id"] = f"r{n}"
        text = "\n\n".join(f"[{x['id']}] ACTION: {x['claim']}\n  VERSE ({x['ref']}): \"{x['verse']}\"" for x in part)
        batches.append({"batch": f"GODMOOD-{bi // dj.BATCH + 1:02d}", "items": part,
                        "task": MOOD_BRIEF + "\n\nITEMS (" + str(len(part)) + "):\n\n" + text + "\n"})
    dj.write_batches(NAME + "-mood", batches)
    print(f"{NAME}-mood: {len(rows)} acts, {len(batches)} batches")


if __name__ == "__main__":
    {"build": build, "report": report, "ds": ds, "mood": mood}[sys.argv[1]]()
