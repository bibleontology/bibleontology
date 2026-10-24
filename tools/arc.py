"""High-level patterns as ordered stages, with the low-level signals as candidates.

2026-09-14: look more at the higher level pattern types, with the lower being
candidates.

Everything built before this treated a pattern as a SET -- traits that
co-occur somewhere in a span. The patterns that had been wanted for weeks are
not sets, they are **sequences of stages**:

    exodus          bondage -> cry -> deliverance -> covenant
    exile_return    sin -> judgment -> exile -> restoration
    testing         trial -> failure or success -> elevation
    chaos_order     chaos -> divine speech or act -> order

A set test cannot tell those apart from a passage that merely mentions all
four things, and cannot tell `exile -> restoration` from `restoration ->
exile`, which is the difference between a prophecy and a memory.

## How the levels divide

    stamps      mark where a STAGE occurs        -- the candidate signal
    order       is what makes it the pattern     -- the claim
    span        how far apart stages may sit     -- the constraint

That is the division intended all along: the stamps are locating signals. A stamp says *deliverance happens here*; the arc
says *deliverance happened here, after a cry, after bondage, and a covenant
followed* -- which no single stamp and no set of stamps can say.

## Measured weakness: loose stages find coincidence

Run on `exile_return` with a six-section window this returns 161 occurrences,
and the top ones are **1 Chronicles genealogies** -- *The Descendants of Esau*
matching "sin" because it carries one loose stamp, *The Sons of Israel*
matching "exile". Four adjacent sections each carrying one stamp from one
stage set is not a movement, it is four sections.

Two things would fix it and neither is built: stages defined by ids that are
DISTINCTIVE of the stage rather than merely present in it, and a requirement
that the stages be the most salient thing in their sections. Until then treat
occurrence counts as an upper bound and read the spans.

**This is also the argument for not using stamps here at all.** 2026-09-14:
the structural literary pattern may not use traits at all and just looks at
structure. Family 1 has `events` (26,018) and `episodes` (2,652) on disk;
an arc built from predicates and participant roles would say *this person was
bound, cried out, was delivered* rather than *these four sections carry these
four stamps*. That is the version worth building.

## What this does not claim

An arc found here is a claim that the text presents these stages in this
order, not that the author intended the pattern. The stages are stamps, and
the stamps are a finding aid -- the taxonomy says so in its own `_intent`.
Where the arc and the text disagree, the text wins.

    python tools/arc.py --list
    python tools/arc.py --arc exile_return --window 6
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "out/stamps-leveled.jsonl"

# Each stage is a set of stamps ANY of which marks it. VERIFY THEM: the first
# version guessed `lament`, `affliction`, `obedience`, `barrenness` and none
# exists in the corpus, so three of six arcs silently returned zero
# occurrences -- a dead stage makes an arc unmatchable and looks exactly like
# a pattern the text does not contain. Drawn from the ids the
# corpus run actually produced, not from what the taxonomy offers -- a stage
# defined by an unstamped id can never match, and `significant_events` is
# empty, so family 1's own vocabulary is not available.
ARCS = {
    "exodus": [
        ("bondage", {"captivity", "slave_bondservant"}),
        ("cry", {"cry_for_help", "complaint", "prayer"}),
        ("deliverance", {"deliverance", "sea_crossing", "exodus_ev"}),
        ("covenant", {"covenant", "covenant_at_sinai", "covenant_cutting"}),
    ],
    "exile_return": [
        ("sin", {"sin_exile_death", "transgression", "idolatry"}),
        ("judgment", {"judgment", "judgment_ev", "judgment_oracle"}),
        ("exile", {"exile_ev", "captivity", "siege"}),
        ("restoration", {"restoration_vision", "return_from_exile",
                         "mercy_restoration"}),
    ],
    "testing": [
        ("trial", {"testing", "temptation", "affliction"}),
        ("response", {"trial_contest", "temptation", "endurance"}),
        ("elevation", {"exile_to_exaltation", "humiliation_to_vindication",
                       "blessing_ev"}),
    ],
    "chaos_order": [
        ("chaos", {"chaos_waters", "flood", "darkness_sym"}),
        ("act", {"creation", "divine_speech", "theophany"}),
        ("order", {"new_creation", "blessing_commission", "kingdom"}),
    ],
    "promise_fulfilment": [
        ("promise", {"promise_oracle", "promise_faithfulness", "covenant"}),
        ("delay", {"barren_woman_conceives", "temptation",
                   "trial_contest"}),
        ("fulfilment", {"fulfilment", "blessing_ev", "deliverance"}),
    ],
    "death_life": [
        ("death", {"death_produces_life", "sin_exile_death", "sacrifice"}),
        ("reversal", {"resurrection_ev", "new_creation",
                      "humiliation_to_vindication"}),
    ],
}


def load():
    sec, title = collections.defaultdict(set), {}
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        sec[d["ref"]].add(d["id"])
        title[d["ref"]] = d.get("title", "")
    order = sorted(sec, key=lambda r: (r.split(".")[0],
                                       *(int(x) for x in r.split(".")[1:])))
    return sec, title, order


def find(stages, sec, order, window):
    """-> [(start, end, [(stage, ref)])] every in-order run within `window`.

    Greedy and forward-only: from each section that opens stage one, walk
    ahead looking for stage two, then three. A stage may repeat and may be
    skipped over -- what is required is that they OCCUR IN ORDER and close
    enough together to be one movement rather than a coincidence across a book.
    """
    hits = []
    n = len(order)
    for i, r in enumerate(order):
        if not (stages[0][1] & sec[r]):
            continue
        book = r.split(".")[0]
        got = [(stages[0][0], r)]
        j, want = i + 1, 1
        while j < n and want < len(stages) and j - i <= window:
            rj = order[j]
            if rj.split(".")[0] != book:
                break
            if stages[want][1] & sec[rj]:
                got.append((stages[want][0], rj))
                want += 1
            j += 1
        if want == len(stages):
            hits.append((got[0][1], got[-1][1], got))
    # an arc contained in another is the same movement seen from further back
    out = []
    for h in hits:
        if out and h[0] in [x[1] for x in out[-1][2]] + [out[-1][0]]:
            continue
        if out and order.index(h[1]) <= order.index(out[-1][1]):
            continue
        out.append(h)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arc", help="which arc; omit with --list")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--window", type=int, default=8,
                    help="how many sections the whole arc may span")
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    sec, title, order = load()
    if a.list or not a.arc:
        print(f"{len(order):,} sections\n")
        for name, stages in ARCS.items():
            hits = find(stages, sec, order, a.window)
            bk = len({h[0].split(".")[0] for h in hits})
            print(f"  {name:<20} {len(stages)} stages   "
                  f"{len(hits):>4} occurrences in {bk} books   "
                  + " -> ".join(s for s, _ in stages))
        return 0

    if a.arc not in ARCS:
        raise SystemExit(f"unknown arc. try: {', '.join(ARCS)}")
    stages = ARCS[a.arc]
    hits = find(stages, sec, order, a.window)
    print(f"{a.arc}: " + " -> ".join(s for s, _ in stages))
    print(f"  {len(hits)} occurrences, window {a.window} sections\n")
    bk = collections.Counter(h[0].split(".")[0] for h in hits)
    print(f"  books: {', '.join(f'{b}({c})' for b, c in bk.most_common(10))}\n")
    for start, end, got in hits[:a.top]:
        print(f"  {start} .. {end}")
        for stage, r in got:
            print(f"      {stage:<14} {r:<14} {title[r][:44]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
