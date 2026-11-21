"""Does the verse say it? Every "Who did what" row on the event cards, checked against the verses it cites
(2026-11-11; Doug: "just keep it utilized with the goal of continual improvement").

The Fable card reviews of 2026-11-10 found relations the cited verse does not say: "Julius imprisoned Paul" on the
verse where Julius treats him with consideration, "Naboth died at Jezreel" where he is stoned outside the city, five
Last Supper messages. Each was one verse not saying one claim. The event cards' "Who did what" rows (1,581 on 428
events) are claims of exactly that shape, each printed with its verses, so each gets one narrow question: does the
verse say this? Nothing is written by this pass. Claude reads every "not_said" and holds what the verse does not
support; a row on God, the Father, Jesus or the Holy Spirit goes to Doug. The Mac alone (DeepSeek budget 0).

    python tools/meaning/cast_check.py build   -> out/orchestra-intake/26-cast-check/
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app2"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))

NAME = "26-cast-check"
OPTIONS = {"temperature": 0, "num_ctx": 4096}
SEED = 20261111

BRIEF = """You check one claim against the Bible verses it cites (the Berean Standard Bible). The claim is
SUBJECT - ACT - OBJECT, as a card prints it. Say whether the verses say it.

Answer with ONE line of JSON:
{"id": "...", "verdict": "...", "words": "...", "why": "..."}

verdict:
- "stated": the verses say the subject does this act to the object, in these words or plainly equivalent ones.
- "implied": the verses do not say it outright, but a plain reader would take it from them (the story shows it).
- "not_said": the verses do not say it: a different act ("treated with consideration" is not "imprisoned"), a
  different place or person, the act is only planned or denied, or the verse is about something else.
- "unclear": you cannot tell from the verses given.

words: the verses' words that say it, copied exactly ("" if not_said).
why: one short reason.

Worked examples (not from the items):
- CLAIM Joab - killed - Abner. VERSES 2 Sam 3:27: "...Joab stabbed him in the stomach, and he died..." -> stated.
- CLAIM Julius - imprisoned - Paul. VERSES Acts 27:1: "Paul and some other prisoners were handed over to a
  centurion named Julius"; Acts 27:3: "Julius treated Paul with consideration" -> not_said (he guarded a prisoner
  handed to him; he did not imprison him).
- CLAIM Naboth - died at - Jezreel. VERSES 1 Kgs 21:13: "they took him outside the city and stoned him to death" ->
  not_said (outside the city).
"""


def build():
    import server as S
    from object_identity import verses
    text = verses()
    d = S.load()
    items = []
    for eid, e in sorted(d["ents"].items()):
        if e.get("type") != "event":
            continue
        try:
            c = S.api_entity(d, {"id": [eid]})
        except Exception:
            continue
        for r in ((c.get("evcard") or {}).get("cast") or []):
            subj = " and ".join(s["name"] for s in r["subjects"])
            obj = r["object"]["name"]
            # every verse of a cited range (up to six), not only its first: "Luke 19:5–9" is Zacchaeus's whole meal
            vs, seen = [], set()
            for ci in r["cites"][:3]:
                for k in S._place_verses(d, ci["ref"], 6):
                    t = d["verses"].get(k)
                    if t and k not in seen and len(vs) < 8:
                        seen.add(k)
                        vs.append(f"{S._vlabel(*k)}: {t}")
            if not vs:
                continue
            items.append({"key": f"{eid}|{'+'.join(s['id'] for s in r['subjects'])}|{r['verb']}|{r['object']['id']}",
                          "id": f"c{len(items) + 1}", "event": eid,
                          "subjects": [s["id"] for s in r["subjects"]], "object": r["object"]["id"], "verb": r["verb"],
                          "cites": [ci["ref"] for ci in r["cites"]],
                          "claim": f"CLAIM {subj} - {r['verb']} - {obj}.", "verse": "\n".join(vs), "context": []})
    random.Random(SEED).shuffle(items)
    out = ROOT / "out" / "orchestra-intake" / NAME
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "cast_check"}}) + "\n")
        for it in items:
            f.write(json.dumps({"key": it["key"], "messages": [
                {"role": "system", "content": BRIEF},
                {"role": "user", "content": f"id: {it['id']}\n{it['claim']}\nVERSES:\n{it['verse']}"}]},
                ensure_ascii=False) + "\n")
    spec = {"pass": NAME, "mac_job": f"{NAME}.jsonl", "priority": 30, "flag": {"verdict_in": []},
            "deepseek": {"budget_usd": 0}, "allowed_fields": ["id", "claim", "verse", "context"]}
    (out / f"{NAME}.pass.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "brief.md").write_text(BRIEF, encoding="utf-8", newline="\n")
    with open(out / "items.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{len(items)} cast rows -> {out}")


# THE SECOND READ (27-cast-reread, 2026-11-11): 26 called 442 of 1,633 rows not said, and a sample showed the model,
# not the rows, wrong in many: "Abraham - told - Stay here with the donkey" read as Abraham telling the donkey, "Isaac -
# told - Isaac at Gen 22:7" as Abraham telling Isaac. "told" with a speech as its object means the subject said those
# words. And one cited verse can leave out what the scene beside it says (Jonathan killed at 1 Sam 31:2; Gilboa at
# 31:1). So: the non-divine not_said rows only (a row on God, the Father, Jesus or the Holy Spirit goes to Doug by
# hand), "told" a speech worded as "said", and three verses either side of each cited verse
REREAD = "27-cast-reread"
DIVINE = {"god", "jesus", "the_father", "holy_ghost", "spirit_of_the_lord_in_the_hebrew_bible", "holy_spirit"}
REREAD_BRIEF = """You check one claim against the Bible passage it comes from (the Berean Standard Bible). The claim is
SUBJECT - ACT - OBJECT, as a card prints it. The verses it cites are marked >>; the verses around them are the scene.
Say whether the passage says it.

Answer with ONE line of JSON:
{"id": "...", "verdict": "...", "words": "...", "why": "..."}

verdict:
- "stated": the passage says the subject does this act to the object, in these words or plainly equivalent ones.
- "implied": the passage does not say it outright, but a plain reader would take it from the scene.
- "not_said": the passage does not say it: a different act ("treated with consideration" is not "imprisoned"), a
  different place or person, the act is only planned or denied, or the passage is about something else.
- "unclear": you cannot tell from the passage given.

How to read the claim:
- "SUBJECT - said - WORDS" means the subject spoke those words (or the words named). It does not say who heard
  them. Check only that this subject says them in the passage.
- A place in the claim may be named in a verse beside the cited one: the scene counts.
- A group as subject ("the two angels") is said when the passage has them, or one of them for them, do it.

words: the passage's words that say it, copied exactly ("" if not_said).
why: one short reason.

Worked examples (not from the items):
- CLAIM Ruth - said - "Where you go, I will go". PASSAGE >> Ruth 1:16: "But Ruth replied: 'Do not urge me to leave
  you... For where you go, I will go...'" -> stated (she said these words; that she said them to Naomi does not
  matter).
- CLAIM Saul - died at - Mount Gilboa. PASSAGE 1 Sam 31:1: "...many fell slain on Mount Gilboa"; >> 31:4: "...Saul
  took his own sword and fell on it" -> stated (the scene is Mount Gilboa).
- CLAIM Julius - imprisoned - Paul. PASSAGE >> Acts 27:1: "Paul and some other prisoners were handed over to a
  centurion named Julius"; Acts 27:3: "Julius treated Paul with consideration" -> not_said (he guarded a prisoner
  handed to him; he did not imprison him).
"""


def reread():
    import server as S
    d = S.load()
    base = ROOT / "out" / "orchestra-intake" / NAME
    items = {json.loads(x)["key"]: json.loads(x) for x in open(base / "items.jsonl", encoding="utf-8")}
    got = {}
    for x in open(ROOT / "out" / "grunt" / "done" / f"{NAME}.jsonl", encoding="utf-8"):
        r = json.loads(x)
        try:
            got[r["key"]] = json.loads(r["content"])
        except ValueError:
            continue
    rows, divine = [], 0
    for k, v in got.items():
        it = items.get(k)
        if not it or v.get("verdict") != "not_said":
            continue
        if DIVINE & set(it["subjects"] + [it["object"]]):
            divine += 1
            continue
        oe = d["ents"].get(it["object"]) or {}
        subj, _, rest = it["claim"][len("CLAIM "):].partition(" - ")
        verb, _, obj = rest.partition(" - ")
        if it["verb"] == "told" and oe.get("type") not in ("person", "group", "place"):
            claim = f"CLAIM {subj} - said - {obj}"
        else:
            claim = it["claim"]
        # the cited verses, marked, and three either side in the same chapter (at most 14)
        cited, keys = [], []
        for ref in it["cites"][:3]:
            cited += [k_ for k_ in S._place_verses(d, ref, 6) if k_ in d["verses"]]
        for (b, c, v_) in cited:
            for n in range(v_ - 3, v_ + 4):
                if (b, c, n) in d["verses"] and (b, c, n) not in keys:
                    keys.append((b, c, n))
        books = list(dict.fromkeys(t[0] for t in keys))     # the cited books in the order cited
        keys = sorted(keys, key=lambda t: (books.index(t[0]), t[1], t[2]))[:14]
        lines = [f"{'>> ' if k_ in cited else ''}{S._vlabel(*k_)}: {d['verses'][k_]}" for k_ in keys]
        if lines:
            rows.append(dict(it, claim=claim, verse="\n".join(lines), first=v))
    random.Random(SEED).shuffle(rows)
    out = ROOT / "out" / "orchestra-intake" / REREAD
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{REREAD}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": dict(OPTIONS, num_ctx=6144),
                                     "pass": "cast_reread"}}) + "\n")
        for it in rows:
            f.write(json.dumps({"key": it["key"], "messages": [
                {"role": "system", "content": REREAD_BRIEF},
                {"role": "user", "content": f"id: {it['id']}\n{it['claim']}\nPASSAGE:\n{it['verse']}"}]},
                ensure_ascii=False) + "\n")
    spec = {"pass": REREAD, "mac_job": f"{REREAD}.jsonl", "priority": 30, "flag": {"verdict_in": []},
            "deepseek": {"budget_usd": 0}, "allowed_fields": ["id", "claim", "verse", "context"]}
    (out / f"{REREAD}.pass.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out / "brief.md").write_text(REREAD_BRIEF, encoding="utf-8", newline="\n")
    with open(out / "items.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in rows:
            f.write(json.dumps({k: it[k] for k in ("key", "id", "event", "subjects", "object", "verb", "cites",
                                                   "claim", "verse", "first")}, ensure_ascii=False) + "\n")
    print(f"{len(rows)} not-said rows to read again ({divine} on a divine person left for Doug) -> {out}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["build"]:
        build()
    elif sys.argv[1:2] == ["reread"]:
        reread()
    else:
        print(__doc__)
