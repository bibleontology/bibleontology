"""WHO AND WHERE FOR EVENTS: the Mac's first round (vocabulary 1.3.0 draft, Doug 2026-10-25: "Approve, Mac
tonight").

529 events, none with a participant or a place. Candidates are mechanical, from what the graph already holds inside
each event's verse span:
  - a participant candidate: every record that is the doer or receiver of a clause in the span (clause-records.jsonl)
  - a place candidate: every place the mentions layer names in the span (mentions.jsonl.gz)
The Mac then answers one narrow question per candidate, with the span's verses in front of it. A planted fault goes
in for a share of events (a person from another event's span, a place from another event), labelled here and never
shown to the model. Divine persons are proposed but always held for Doug's per-record decision.

    python tools/meaning/local_event_links.py export [--plant 0.15]   -> out/grunt/jobs/2b-event-links.jsonl
    python tools/meaning/local_event_links.py report                  after `grunt.py pull`
"""
import collections
import glob
import gzip
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from derive import BOOK  # noqa: E402
from bibleont.refs import parse_ref  # noqa: E402

JOBS, DONE = ROOT / "out" / "grunt" / "jobs", ROOT / "out" / "grunt" / "done"
NAME = "2b-event-links"
OPTIONS = {"temperature": 0, "num_ctx": 6144}
DIVINE = {"god", "holy_ghost", "the_father", "jesus", "spirit", "spirit_of_god"}
MAXV = 8  # verses of the span shown; a longer span shows its first eight

BRIEF_WHO = """You check a Bible knowledge graph against the text. You get an EVENT (its name, a one-line account, and \
the verses that tell it) and ONE person, group or being. Answer one question: does this one take part in THIS event, \
as these verses tell it?

- "doer": acts in the event (builds, strikes, speaks, goes).
- "receiver": is acted on in the event (is struck, is anointed, is given something).
- "present": is there in the event as told, without acting or being acted on.
- "no": is only named in passing (a genealogy, a place name, someone spoken about but not there), or belongs to a \
different happening in these verses.

Judge only from the verses given. Worked examples:
- Event "Death of Abel", Gen 4:8 "Cain rose up against his brother Abel and killed him": Cain -> doer; Abel -> receiver.
- Event "Temple built", 1 Kgs 6:14 "So Solomon built the temple and finished it": Solomon -> doer.
- Event "Temple built", 1 Kgs 6:1 "...in the fourth year of Solomon's reign over Israel ... he began to build": Israel \
-> no (named for the date, not taking part).

Answer with ONLY a JSON object: {"answer": "doer" | "receiver" | "present" | "no", "reason": "<one line quoting \
the verse>"}"""

BRIEF_WHERE = """You check a Bible knowledge graph against the text. You get an EVENT (its name, a one-line account, \
and the verses that tell it) and ONE place. Answer one question: does this event happen at this place, as these \
verses tell it?

- "yes": the event takes place there (or in it, at it, on it).
- "no": the place is only mentioned: where someone came from or is going, a place in a speech, a comparison.

Worked examples:
- Event "Temple built", 2 Chr 3:1 "Solomon began to build the house of the LORD in Jerusalem on Mount Moriah": \
Jerusalem -> yes; Moriah -> yes.
- Event "Flight to Egypt", Matt 2:14 "he got up, took the Child and His mother by night, and withdrew to Egypt": \
Egypt -> yes (they go there and stay); Bethlehem -> no unless the verses place the event there.

Answer with ONLY a JSON object: {"answer": "yes" | "no", "reason": "<one line quoting the verse>"}"""


def bible():
    order, text = [], {}
    for ln in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(ln)
        if "b" in d:
            k = f"{BOOK.get(d['b'], d['b'])}.{d['c']}.{d['v']}"
            order.append(k)
            text[k] = d["t"]
    return order, {k: i for i, k in enumerate(order)}, text


def vid(r):
    p = parse_ref(r)
    return f"{BOOK.get(p.book, p.book)}.{p.start_chapter}.{p.start_verse}"


def items(plant):
    ents = {}
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        for ln in open(f, encoding="utf-8"):
            if ln.strip():
                e = json.loads(ln)
                ents.setdefault(e["id"], e)
    order, pos, text = bible()
    # spans are in the Berean's numbering (the refs are); the clause records and mentions are MACULA's
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    to_mac = {b: m for m, b in moved.items()}
    events = {}
    for e in ents.values():
        if e.get("type") != "event" or not e.get("refs"):
            continue
        try:
            a = pos[vid(e["refs"][0])]
            b = pos[vid(e["refs"][-1])] if len(e["refs"]) > 1 else a
        except Exception:
            continue
        if b < a or b - a > 60:
            b = a
        events[e["id"]] = [order[i] for i in range(a, b + 1)]
    mac_to_ev = collections.defaultdict(set)
    for ev, vs in events.items():
        for v in vs:
            mac_to_ev[to_mac.get(v, v)].add(ev)
    who = collections.defaultdict(set)
    for ln in open(ROOT / "out" / "meaning" / "clause-records.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        for ev in mac_to_ev.get(r["ref"], ()):
            for end in ("subject", "object"):
                rec = (r.get(end) or {}).get("record")
                if rec and (ents.get(rec) or {}).get("type") in ("person", "group", "being"):
                    who[ev].add(rec)
    where = collections.defaultdict(set)
    with gzip.open(ROOT / "out" / "mentions.jsonl.gz", "rt", encoding="utf-8") as f:
        for ln in f:
            d = json.loads(ln)
            rec, occ = d.get("record"), d.get("occurrence", "")
            if rec and (ents.get(rec) or {}).get("type") == "place":
                for ev in mac_to_ev.get(occ.split("#")[0], ()):
                    where[ev].add(rec)
    out, rnd = [], random.Random(11)
    allwho = sorted({x for s in who.values() for x in s})
    allwhere = sorted({x for s in where.values() for x in s})
    for ev, vs in sorted(events.items()):
        e = ents[ev]
        base = {"event": ev, "event_name": e.get("name"), "account": (e.get("desc") or "")[:300],
                "verses": [{"ref": v, "text": text[v]} for v in vs[:MAXV]], "span": len(vs)}
        for rec in sorted(who[ev]):
            out.append({**base, "kind": "who", "cand": rec, "cand_name": ents[rec].get("name"), "planted": None,
                        "divine": rec in DIVINE})
        for rec in sorted(where[ev]):
            out.append({**base, "kind": "where", "cand": rec, "cand_name": ents[rec].get("name"), "planted": None,
                        "divine": False})
        if rnd.random() < plant:  # a person or place from elsewhere: must come back "no"
            pool, kind = (allwho, "who") if rnd.random() < 0.6 else (allwhere, "where")
            others = [x for x in pool if x not in (who[ev] | where[ev])]
            near = " ".join(v["text"] for v in base["verses"]).lower()
            others = [x for x in others if (ents[x].get("name") or "").lower() not in near]
            if others:
                x = rnd.choice(others)
                out.append({**base, "kind": kind, "cand": x, "cand_name": ents[x].get("name"), "planted": "no",
                            "divine": False})
    for i, it in enumerate(out):
        it["key"] = f"{it['event']}|{it['kind']}|{it['cand']}|{i}"
    return out


def messages(it):
    msg = {"event": it["event_name"], "account": it["account"], "verses": it["verses"],
           ("person" if it["kind"] == "who" else "place"): it["cand_name"]}
    return [{"role": "system", "content": BRIEF_WHO if it["kind"] == "who" else BRIEF_WHERE},
            {"role": "user", "content": json.dumps(msg, ensure_ascii=False)}]


def export(plant):
    its = items(plant)
    JOBS.mkdir(parents=True, exist_ok=True)
    with open(JOBS / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "local_event_links"}}) + "\n")
        for it in its:
            f.write(json.dumps({"key": it["key"], "messages": messages(it)}, ensure_ascii=False) + "\n")
    with open(JOBS / f"{NAME}.items.jsonl", "w", encoding="utf-8") as f:
        for it in its:
            f.write(json.dumps({k: v for k, v in it.items() if k != "verses"}, ensure_ascii=False) + "\n")
    c = collections.Counter((i["kind"], bool(i["planted"])) for i in its)
    print(f"{len(its)} calls ({dict(c)}), {len({i['event'] for i in its})} events -> {JOBS / (NAME + '.jsonl')}")


def report():
    its = {json.loads(l)["key"]: json.loads(l) for l in open(JOBS / f"{NAME}.items.jsonl", encoding="utf-8")}
    rows = [json.loads(l) for l in open(DONE / f"{NAME}.jsonl", encoding="utf-8")]
    ans = {}
    for d in rows:
        m = re.search(r'"answer"\s*:\s*"(doer|receiver|present|yes|no)"', d.get("content", ""))
        if m:
            ans[d["key"]] = m[1]
    fake = [k for k in ans if its[k]["planted"]]
    real = [k for k in ans if not its[k]["planted"]]
    print(f"{len(ans)} answered of {len(its)}; planted caught {sum(ans[k] == 'no' for k in fake)} of {len(fake)}")
    print("who:", collections.Counter(ans[k] for k in real if its[k]["kind"] == "who"))
    print("where:", collections.Counter(ans[k] for k in real if its[k]["kind"] == "where"))


if __name__ == "__main__":
    if sys.argv[1] == "export":
        export(float(sys.argv[sys.argv.index("--plant") + 1]) if "--plant" in sys.argv else 0.15)
    else:
        report()
