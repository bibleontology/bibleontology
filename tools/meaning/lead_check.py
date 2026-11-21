"""THE BURIED PASS: which facts on a card should a reader meet first? (Mac mini, gemma4:26b; 2026-11-12.)

Doug, 2026-11-12: *"I think that completeness tends to be an issue or sometimes we bury things on the cards"*. The gap
pass (local_gap_check.py) asks what a card lacks. This asks what it has but may hide: one card per call, its lines in
a SHUFFLED order (so the card's own order cannot lead the model), and one question: which three lines does a reader
most need first, to understand who this is or what happened -- the facts the Bible itself makes central, not the most
frequent or the most detailed.

The Mac only picks; nothing it answers reaches a card. Afterwards (report), Claude compares each pick with what the
LIVE card shows first (the server's own card page): a central fact that the page shows far down, or folds away, is
a buried fact, and a candidate for the card's lead.

What the model sees: the card's name, what else it is called, and its lines (the gap pass's own, the strongest 40),
numbered in random order. No verse text, no note, nothing from docs/. Divine persons are in, as flags for Doug only.

Cards: people, groups and beings with at least MIN_LINES lines (fewer leave nothing to bury), and every event with as
many. Validation is not planted here: the report checks the picks for well-known cards (David, Moses, Peter, the
Exodus) by eye first, and the run is judged on them before anything else is read.

    python tools/meaning/lead_check.py export     -> out/grunt/jobs/29-lead-check.jsonl (+ .key.jsonl)
    python tools/grunt/grunt.py push out/grunt/jobs/29-lead-check.jsonl
    python tools/grunt/grunt.py pull
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
import local_gap_check as G  # noqa: E402

NAME = "29-lead-check"
MIN_LINES = 6
OPTIONS = {"temperature": 0, "num_ctx": 6144}
SEED = 29

BRIEF = """You read what a Bible reference card records about one person, group, being or event. Each numbered line is
one fact the card holds, with the verses it rests on. The lines are in RANDOM order.

Choose the THREE lines a reader most needs to meet first, to understand who this is or what happened: the facts the
Bible itself makes central to this person or event. Not the line with the most verses, not the most detailed one, not
a minor family link when something defining is listed. If the card lacks the defining fact altogether, still choose
the three most important lines it has, and say what is missing in "missing".

Answer with JSON only, no other text:
{"top": [n, n, n], "why": "one short sentence", "missing": "the defining fact the card lacks, or empty"}"""


def messages(it):
    msg = {"name": it["name"], "also_called": it.get("also_called") or [], "kind": it["kind"],
           "lines": [f"{i + 1}. {t}" for i, t in enumerate(it["shuffled"])]}
    return [{"role": "system", "content": BRIEF}, {"role": "user", "content": json.dumps(msg, ensure_ascii=False)}]


def export():
    persons, events, _people = G.all_cards()
    rnd = random.Random(SEED)
    its = []
    for c in persons + events:
        shown = G.shown_lines(c)
        if len(shown) < MIN_LINES:
            continue
        order = list(range(len(shown)))
        rnd.shuffle(order)
        its.append({"key": f"l{len(its):04d}", "id": c["id"], "kind": c["kind"], "name": c["name"],
                    "also_called": c.get("also_called"), "lines": shown, "order": order,
                    "shuffled": [shown[i] for i in order]})
    G.JOBS.mkdir(parents=True, exist_ok=True)
    with open(G.JOBS / f"{NAME}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "lead_check"}}) + "\n")
        for it in its:
            f.write(json.dumps({"key": it["key"], "messages": messages(it)}, ensure_ascii=False) + "\n")
    with open(G.JOBS / f"{NAME}.key.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in its:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"{len(its)} cards ({sum(1 for i in its if i['kind'] == 'person')} people, "
          f"{sum(1 for i in its if i['kind'] == 'event')} events) with >= {MIN_LINES} lines -> {G.JOBS / (NAME + '.jsonl')}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["export"]:
        export()
    else:
        print(__doc__)
