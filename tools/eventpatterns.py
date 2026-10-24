"""Find recurring narrative shapes without naming one first.

The ask: do the deliverance pattern, but also discover unnamed patterns with
the approach. That is the harder and the right ask. Seeding
`deliverance` tests only whether the pipeline can find a thing already named;
letting shapes fall out tests whether the method sees anything at all, and it is
falsifiable in a way the seeded version is not.

## What a pattern is here

`tools/events.py` gives 26,018 events, each a narrative verb with the
participants its clause names. A **shape** is a run of consecutive events
reduced to their verbs -- *rose, took, went* -- with the fillers thrown away. A
shape is a **pattern** when the same run recurs with DIFFERENT fillers in
DIFFERENT books.

That distinction is the whole thing. *said, said, said* recurs everywhere and is
a habit of the language. *sinned, sent, cried, delivered* recurring in Judges
with a different agent each time is a pattern, and the difference between them
is measurable rather than a matter of taste.

## The gates, taken from `tools/patterns.py` which established them

- **reach** -- distinct books. A shape confined to one book is that book's
  style, and Genesis 5's genealogy is the honest example of a real one-book
  form; it is reported separately rather than mixed in.
- **productivity** -- distinct agents filling the subject slot. A run that
  always has the same agent is one story told once, not a form.
- **skew** -- the share taken by the commonest agent. High skew means one story
  dominating a shape that looked productive.
- **lift** -- how much likelier this run is than its verbs occurring
  independently. Without it, common verbs manufacture shapes by arithmetic.

## What it does not do

It does not name a pattern, and it does not decide that two shapes are the same
shape at a deeper level -- *rose, went* and *arose, departed* are separate here.
Naming and merging are readings, kept for decision by hand.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "event-patterns.json"

# Verbs so common that a run of them is grammar rather than narrative shape.
# Measured: `said` alone heads 1 event in 6, and every top shape without this
# was some arrangement of speech verbs.
SPEECHY = {"אָמַר", "דָּבַר", "עָנָה", "קָרָא", "λέγω", "λαλέω",
           "ἀποκρίνομαι", "φημί", "εἶπον"}


def load_events():
    rows = []
    with gzip.open(OUT / "events.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if not any(k.startswith("_") for k in d):
                rows.append(d)
    return rows


def key(ref):
    p = ref.split(".")
    try:
        return (p[0], int(p[1]), int(p[2]))
    except (IndexError, ValueError):
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, default=3, help="events per shape")
    ap.add_argument("--min-count", type=int, default=4)
    ap.add_argument("--min-books", type=int, default=2)
    ap.add_argument("--min-agents", type=int, default=3)
    ap.add_argument("--max-skew", type=float, default=0.6)
    ap.add_argument("--show", type=int, default=25)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    ev = load_events()
    ev = [e for e in ev if not e.get("quoted")]
    ev.sort(key=lambda e: (key(e["ref"]) or ("", 0, 0)))
    print(f"narrative events (unquoted): {len(ev)}")

    # runs of N consecutive events inside one chapter
    shapes = collections.defaultdict(lambda: {"n": 0, "books": set(),
                                              "agents": collections.Counter(),
                                              "where": []})
    unigram = collections.Counter()
    total_runs = 0
    for i in range(len(ev) - a.n + 1):
        win = ev[i:i + a.n]
        ks = [key(e["ref"]) for e in win]
        if any(k is None for k in ks):
            continue
        if len({(k[0], k[1]) for k in ks}) != 1:      # one chapter
            continue
        verbs = tuple(e["lemma"] for e in win)
        if any(v is None for v in verbs):
            continue
        if all(v in SPEECHY for v in verbs):
            continue
        total_runs += 1
        for v in verbs:
            unigram[v] += 1
        agent = None
        for e in win:
            s = (e.get("participants") or {}).get("s")
            if s:
                agent = s[0]
                break
        rec = shapes[verbs]
        rec["n"] += 1
        rec["books"].add(ks[0][0])
        if agent:
            rec["agents"][agent] += 1
        if len(rec["where"]) < 6:
            rec["where"].append(win[0]["ref"])

    print(f"runs of {a.n}: {total_runs}, distinct shapes: {len(shapes)}")

    rows = []
    for verbs, rec in shapes.items():
        if rec["n"] < a.min_count or len(rec["books"]) < a.min_books:
            continue
        ags = rec["agents"]
        if len(ags) < a.min_agents:
            continue
        skew = ags.most_common(1)[0][1] / max(1, sum(ags.values()))
        if skew > a.max_skew:
            continue
        expected = total_runs
        for v in verbs:
            expected *= unigram[v] / max(1, total_runs * a.n)
        lift = rec["n"] / max(expected, 1e-9)
        rows.append({"verbs": list(verbs), "count": rec["n"],
                     "books": sorted(rec["books"]),
                     "agents": len(ags), "skew": round(skew, 2),
                     "lift": round(lift, 1),
                     "top_agents": [x for x, _ in ags.most_common(4)],
                     "where": rec["where"]})
    rows.sort(key=lambda r: (-len(r["books"]), -r["agents"], -r["lift"]))

    print(f"shapes passing every gate: {len(rows)}\n")
    gl = {}
    for e in ev:
        gl.setdefault(e["lemma"], e.get("gloss") or e["lemma"])
    print(f"  {'shape':46} {'n':>4} {'bks':>4} {'agt':>4} {'skew':>5} {'lift':>6}")
    for r in rows[:a.show]:
        sh = " > ".join(gl.get(v, v)[:12] for v in r["verbs"])
        print(f"  {sh[:44]:46} {r['count']:>4} {len(r['books']):>4} "
              f"{r['agents']:>4} {r['skew']:>5.2f} {r['lift']:>6.1f}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    DEST.write_text(json.dumps(
        {"_note": "Recurring narrative shapes, discovered rather than named. "
                  "A shape is a run of consecutive narrative verbs; it is kept "
                  "when it recurs across books with several different agents.",
         "n": a.n, "gates": {"min_count": a.min_count,
                             "min_books": a.min_books,
                             "min_agents": a.min_agents,
                             "max_skew": a.max_skew},
         "shapes": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(rows)} shapes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
