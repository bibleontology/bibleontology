"""took_place_at candidates for the Mac (P-2026-11-19-3; vocabulary 1.7.0). Doug, 2026-11-19: "make sure the Mac
keeps working".

    python -X utf8 tools/pending/place_pass.py export     # -> out/grunt/jobs/35-took-place-at.jsonl (+ .items.jsonl here)
    python -X utf8 tools/pending/place_pass.py report     # after grunt.py pull: the yes answers, for reading

The event cards' casts name places ("went to", "died at", "was buried at"), but a place in a cast is not where the
event happened: "David was born at Bethlehem" is background on the Goliath card, and "went to" names journey stops.
So each (event, place) pair is one narrow question with its verses: does the text say the event happened there? A
"yes" is a candidate only, read before anything enters the graph (16 sampled, then all by rule only if they hold).
The questions carry the Berean text and names only; the key stays on this PC.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
S = Path(r"<local>")
JOB = ROOT / "out" / "grunt" / "jobs" / "35-took-place-at.jsonl"
KEY = ROOT / "out" / "grunt" / "jobs" / "35-took-place-at.items.jsonl"
DONE = ROOT / "out" / "grunt" / "done" / "35-took-place-at.jsonl"

Q = """You read Bible verses (the Berean Standard Bible) and answer ONE narrow question.

EVENT: {event}
PLACE: {place}
THE VERSES OF THE EVENT'S TELLING THAT NAME THE PLACE:
{verses}

Question: do these verses say that this event happened at this place (at it, in it, or on it)?
- "yes" only if the verses place the event itself there: "the battle was fought at Gilboa", "they came to Moriah and
  he built the altar there".
- "no" if the place is only where someone came from, was born, was buried later, went afterward, or is mentioned in
  passing; or if only part of a longer event happens there and the verses do not make it the event's place.
- Answer "no" when unsure.

Return ONLY one JSON object: {{"answer": "yes" or "no", "why": "the exact words of the verse that decide it"}}.
"""


def export():
    rows = json.load(open(S / "cast_rows.json", encoding="utf-8"))
    E = {}
    for f in (ROOT / "ontology" / "entities").glob("*.jsonl"):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                if "id" in e:
                    E.setdefault(e["id"], e)
    V = {}
    for ln in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        if "b" in r:
            V[f"{r['b']}.{r['c']}.{r['v']}"] = (f"{r['b']} {r['c']}:{r['v']}", r["t"])
    pairs = {}
    for ev, cast in rows.items():
        for row in cast:
            o = row.get("object") or {}
            if (E.get(o.get("id")) or {}).get("type") != "place":
                continue
            p = pairs.setdefault((ev, o["id"]), {"event": ev, "place": o["id"], "gos": [], "rows": []})
            p["gos"] += [c["go"] for c in row["cites"] if c["go"] not in p["gos"]]
            p["rows"].append(row["verb"])
    JOB.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(JOB, "w", encoding="utf-8", newline="\n") as o, open(KEY, "w", encoding="utf-8", newline="\n") as k:
        o.write(json.dumps({"_job": {"model": "gemma4:26b", "options": {"temperature": 0, "num_ctx": 4096,
                                                                         "num_predict": 160}, "recycle_every": 100}}) + "\n")
        for (ev, pl), p in sorted(pairs.items()):
            vs = [V[g] for g in p["gos"][:6] if g in V]
            if not vs:
                continue
            q = Q.format(event=(E.get(ev) or {}).get("name", ev), place=(E.get(pl) or {}).get("name", pl),
                         verses="\n".join(f"  {r}: {t}" for r, t in vs))
            key = f"{ev}|{pl}"
            o.write(json.dumps({"key": key, "messages": [{"role": "user", "content": q}]}, ensure_ascii=False) + "\n")
            k.write(json.dumps({"key": key, **p, "refs": [r for r, _t in vs]}, ensure_ascii=False) + "\n")
            n += 1
    print(n, "questions ->", JOB.relative_to(ROOT))


def report():
    import re
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
    (ROOT / "out" / "took-place-at-yes.json").write_text(json.dumps(yes, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(yes)} yes, {no} no, {bad} unreadable -> out/took-place-at-yes.json")


if __name__ == "__main__":
    {"export": export, "report": report}[sys.argv[1]]()
