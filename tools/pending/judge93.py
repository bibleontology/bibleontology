"""DeepSeek judges 93 items (Doug, 2026-11-20: "have DeepSeek judge the 93 items"): the 70 took_place_at pairs the Mac
and DeepSeek both said yes to, now asked the stricter question both missed (a stop or a part of a longer event is
not the event's place), and job 38's 23 flags (the Mac said no or unclear: do the verses say this relation?).

    python -X utf8 tools/pending/judge93.py build     -> out/judge93/{place,flag}-NNN.txt
    bash tools/pending/judge93_run.sh                 blind, think, off-peak, resumable
    python -X utf8 tools/pending/judge93.py report    -> out/judge93/verdicts.json
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out" / "judge93"

PLACE = """You judge entries of a Bible knowledge graph against the Berean Standard Bible. Each entry says an EVENT
took place at a PLACE. Answer one question per entry: is this place where the event itself happened?
- "yes" when the event as a whole happens there: the binding of Isaac at Moriah ("go to the land of Moriah ... offer him
  there"); Saul's death on Mount Gilboa.
- "part" when only one stop, scene or section of a longer event is there: one city on a journey of many cities; one
  gate of a wall rebuilt section by section; a birth inside a longer family story.
- "no" when the place is only where someone came from, went afterward, was born or buried, or is mentioned in passing.
Return ONLY a JSON array, one object per entry, in order:
[{"n": 1, "answer": "yes" or "part" or "no", "why": "a few words"}]
"""

FLAG = """You check entries of a Bible knowledge graph against the Berean Standard Bible. Each entry is one relation,
SUBJECT -- relation -- OBJECT, with the verses it cites. Answer one question per entry: do these verses say this?
- "yes": the verses state it (a pronoun whose referent the verses make clear counts).
- "implied": the verses clearly imply it without stating it.
- "no": the verses do not say it, or say something else.
Return ONLY a JSON array, one object per entry, in order:
[{"n": 1, "answer": "yes" or "implied" or "no", "why": "the exact words that decide it"}]
"""


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    items = []
    agreed = json.load(open(ROOT / "out" / "second-pass" / "agreed.json", encoding="utf-8"))["agreed"]
    q = {json.loads(l)["key"]: json.loads(l) for l in list(open(ROOT / "out/grunt/jobs/35-took-place-at.jsonl",
                                                                 encoding="utf-8"))[1:]}
    for a in agreed:
        body = q[a["key"]]["messages"][0]["content"].split("Question:")[0].split("ONE narrow question.")[-1].strip()
        items.append(("place", a["key"], body))
    key = {json.loads(l)["key"]: json.loads(l) for l in open(ROOT / "out/grunt/jobs/38-relation-recheck-new.key.jsonl",
                                                             encoding="utf-8")}
    for ln in open(ROOT / "out/grunt/done/38-relation-recheck-new.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        m = re.findall(r"\{[^{}]*\}", r.get("content") or "")
        try:
            ans = json.loads(m[-1])["answer"] if m else "unclear"
        except (ValueError, KeyError):
            ans = "unclear"
        if ans in ("no", "unclear"):
            k = key[r["key"]]
            body = k["text"] + "\n" + "\n".join(f"  {v['ref']}: {v['text']}" for v in k["verses"])
            items.append(("flag", r["key"], body))
    index = {}
    for kind, head in (("place", PLACE), ("flag", FLAG)):
        its = [i for i in items if i[0] == kind]
        for b in range(0, len(its), 8):
            chunk = its[b:b + 8]
            name = f"{kind}-{b // 8:03d}"
            text = head + "\n" + "\n\n".join(f"=== ENTRY {i + 1} ===\n{body}" for i, (_k, _key, body) in enumerate(chunk))
            (OUT / f"{name}.txt").write_text(text, encoding="utf-8", newline="\n")
            index[name] = [key_ for _k, key_, _b in chunk]
    json.dump(index, open(OUT / "index.json", "w", encoding="utf-8"), indent=1)
    print(sum(len(v) for v in index.values()), "items in", len(index), "batches")


def report():
    index = json.load(open(OUT / "index.json", encoding="utf-8"))
    out, missing = [], 0
    for name, keys in index.items():
        a = OUT / f"{name}.answer.txt"
        got = {}
        if a.exists():
            m = re.search(r"^\[.*\]", a.read_text(encoding="utf-8"), re.S | re.M)
            try:
                got = {x["n"]: x for x in json.loads(m.group(0))} if m else {}
            except ValueError:
                pass
        for i, k in enumerate(keys):
            x = got.get(i + 1)
            if not x:
                missing += 1
            else:
                out.append({"kind": name.split("-")[0], "key": k, "answer": x.get("answer"), "why": x.get("why")})
    json.dump(out, open(OUT / "verdicts.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    import collections
    print(collections.Counter((o["kind"], o["answer"]) for o in out), "unanswered", missing)


if __name__ == "__main__":
    {"build": build, "report": report}[sys.argv[1]]()
