"""The hidden "suggested" passages, judged (Doug, 2026-11-19, ruling 2 on the event cards: "hide now, judge later").

    python -X utf8 tools/pending/suggested_pass.py export    # -> out/grunt/jobs/36-suggested-passages.jsonl
    python -X utf8 tools/pending/suggested_pass.py report    # after grunt.py pull: the yes answers, for reading

276 passages the Copilot-drafted events listed as "suggested", each marked "shares its subject, but does not speak of
this event" (docs/review/card-conservation/removals.json). Each is one narrow question for the Mac: does this passage
speak of this event (tell it, refer to it, quote it)? A "yes" is a candidate to show again only with a real tie, read
by Claude (and its tie recorded as a relation) before it returns; a "no" stays hidden.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / "out" / "grunt" / "jobs" / "36-suggested-passages.jsonl"
KEY = ROOT / "out" / "grunt" / "jobs" / "36-suggested-passages.items.jsonl"
DONE = ROOT / "out" / "grunt" / "done" / "36-suggested-passages.jsonl"

Q = """You read Bible passages (the Berean Standard Bible) and answer ONE narrow question.

EVENT: {event}, told in {told}
THE EVENT'S OPENING VERSES:
{ev_verses}

A PASSAGE ELSEWHERE:
{p_verses}

Question: does the passage speak of THIS event: tell it, refer to it, or quote words from it?
- "yes" only if the passage is about this very event or quotes words from it.
- "no" if it only shares a subject or a theme (mercy, love, a commandment) with it.
- "no" for a prophecy or promise that a reader may take as foretelling the event: that is a reading, not something
  these verses say. (If the event's own telling quotes the passage, that tie is recorded elsewhere already.)
- Answer "no" when unsure.

Return ONLY one JSON object: {{"answer": "yes" or "no", "why": "the exact words of the passage that decide it"}}.
"""


def verses():
    V, order = {}, []
    for ln in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        if "b" in r:
            k = (r["b"].lower()[:4], r["c"], r["v"])
            V[k] = (f"{r['b']} {r['c']}:{r['v']}", r["t"]); order.append(k)
    return V, order


def span(V, order, fact, n=3):
    m = re.match(r"(\S+) (\d+):(\d+)", fact)
    if not m:
        return []
    k = (m.group(1)[:4], int(m.group(2)), int(m.group(3)))
    if k not in V:
        return []
    i = order.index(k)
    return [V[x] for x in order[i:i + n] if x[0] == k[0]]


def export():
    sys.path.insert(0, str(ROOT / "app2"))
    import server as S
    d = S.load()
    V, order = verses()
    rem = json.loads((ROOT / "docs" / "review" / "card-conservation" / "removals.json").read_text(encoding="utf-8"))["removals"]
    n = 0
    JOB.parent.mkdir(parents=True, exist_ok=True)
    with open(JOB, "w", encoding="utf-8", newline="\n") as o, open(KEY, "w", encoding="utf-8", newline="\n") as k:
        o.write(json.dumps({"_job": {"model": "gemma4:26b", "options": {"temperature": 0, "num_ctx": 4096,
                                                                         "num_predict": 160}, "recycle_every": 100}}) + "\n")
        for r in rem:
            ev = (S.api_entity(d, {"id": [r["card"]]}).get("event") or {})
            tell = ev.get("tellings") or []
            if not tell:
                continue
            first = tell[0].get("first") or ""
            from_ref = re.sub(r"^(\w+)\.(\d+)\.(\d+)$", r"\1 \2:\3", first)
            evv = span(V, order, from_ref.lower(), 4)
            pv = span(V, order, r["fact"], 3)
            if not evv or not pv:
                continue
            q = Q.format(event=ev.get("title") or r["card"], told="; ".join(t.get("label", "") for t in tell),
                         ev_verses="\n".join(f"  {a}: {b}" for a, b in evv),
                         p_verses="\n".join(f"  {a}: {b}" for a, b in pv))
            key = f"{r['card']}|{r['fact']}"
            o.write(json.dumps({"key": key, "messages": [{"role": "user", "content": q}]}, ensure_ascii=False) + "\n")
            k.write(json.dumps({"key": key, "card": r["card"], "fact": r["fact"], "shown_as": r.get("shown_as")},
                               ensure_ascii=False) + "\n")
            n += 1
    print(n, "questions ->", JOB.relative_to(ROOT))


def report():
    key = {json.loads(x)["key"]: json.loads(x) for x in open(KEY, encoding="utf-8")}
    yes, no, bad = [], 0, 0
    for ln in open(DONE, encoding="utf-8"):
        r = json.loads(ln)
        m = re.findall(r"\{[^{}]*\}", r.get("content") or "")
        try:
            a = json.loads(m[-1]) if m else None
        except ValueError:
            a = None
        if not a:
            bad += 1
        elif str(a.get("answer")).lower() == "yes":
            yes.append({**key[r["key"]], "why": a.get("why")})
        else:
            no += 1
    (ROOT / "out" / "suggested-yes.json").write_text(json.dumps(yes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(yes)} yes, {no} no, {bad} unreadable -> out/suggested-yes.json")


if __name__ == "__main__":
    {"export": export, "report": report}[sys.argv[1]]()
