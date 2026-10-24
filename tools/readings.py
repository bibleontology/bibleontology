"""A reader's hand-readings of twelve psalms: HELD, NOT APPLIED.

2026-09-10, correcting a first version that stored these as overlays to be
applied to the grouping: personal markings are not to be applied as overlays,
because the aim is to see what the algorithm surfaces; they are held for later
as a potential benchmark, which for now is not something to try to hit.

**Nothing reads this file.** It is not an input to any pipeline, it does not
correct a computed grouping, and no weight anywhere is tuned toward it. If
`tools/grouptree.py` divides a psalm differently, the difference stands.

## Why holding them unused is the whole value

They are worth something precisely as an **untouched** comparison: a check run
once, late, against an algorithm that never saw them. Consulted during
development they become training data and there is nothing left to test with.

This project has made the fitted-measurement mistake twice and recorded both --
a 57% recurrence figure produced by deleting word terms rather than typing them,
and a 1.02x pattern-fit test guaranteed by construction. Both looked like
findings. Holding this file aside is how it does not happen a third time.

## Why they are stored at all

Because they cannot be regenerated. Everything else in `out/` is derived from
the corpus; this is a reading, made over one long session, and it existed only
in a chat transcript until 2026-09-10, and a session's context is summarised
and then lost.

## Anchoring

Every judgment anchors on **verse references**, never on a group -- a group has
no stable identity across a rebuild, while `Psa.103.9` means the same thing
whatever the grouping says about it. `tools/patterns.py` follows the same rule
with its content-hashed `key_of()`: identity from content, never from position.

## Kinds

    seam      a division the reader placed at a verse
    group     a span the reader called one unit
    tree      a nested structure, in the reader's own bracket notation
    note      a judgment in prose no current layer can represent

`tree` and `note` are deliberately unparsed. `((15-(16-17))-18)` and "v3 binds
more closely with 2 than 4 by tone" are real readings we have no vocabulary
for, and recording them whole is better than dropping them or pretending to
score them.

See `docs/READINGS.md` for what this is and is not.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
STORE = ROOT / "ontology" / "readings-held.jsonl"

# --------------------------------------------------------------------------
# A reader's reading, 2026-09-09 and 2026-09-10, transcribed from the reader's
# own words. Verse numbers are ENGLISH (BSB), as the reader was reading them.
# --------------------------------------------------------------------------
SEED = [
    {"ref": "Psa.1", "kind": "seam", "verses": [4],
     "said": "agreed with BSB on the major breaks"},
    {"ref": "Psa.1", "kind": "seam", "verses": [3], "weight": "minor",
     "said": "a secondary break before verse 3 as it really is its own rich "
             "picture which ties beautifully to the prophets"},
    {"ref": "Psa.1", "kind": "group", "verses": [1, 3],
     "said": "BSB is exactly right that 1-3 is the larger group and has to be "
             "because of the pronoun"},
    {"ref": "Psa.1", "kind": "note",
     "said": "4-6 is one big group, but 6 ties to 5 closely as 6 applies to 5, "
             "and the 5-6 group is the consequence of 4"},

    {"ref": "Psa.23", "kind": "seam", "verses": [5],
     "said": "the major seam in the right place after v4"},
    {"ref": "Psa.23", "kind": "seam", "verses": [4], "weight": "minor",
     "said": "a minor seam before v4 as it stirs things up a bit. 'Even though' "
             "is answering the expected challenge to the theme"},

    {"ref": "Psa.145", "kind": "note",
     "said": "goes back and forth between talking about the Lord and those who "
             "worship him; I put seams on those transitions"},

    {"ref": "Psa.62", "kind": "group", "verses": [3, 4],
     "said": "3-4 is a group that goes negative so I put a break after 4"},
    {"ref": "Psa.62", "kind": "group", "verses": [5, 7],
     "said": "5-7 is a personal testament"},
    {"ref": "Psa.62", "kind": "group", "verses": [8, 10],
     "said": "seams around 8-10 as it is an exhortation"},

    {"ref": "Psa.63", "kind": "seam", "verses": [1], "weight": "mid-verse",
     "said": "the first break really should be in the middle of verse 1 after "
             "the word 'Judah' that sets the context for the imagery in the "
             "remainder of 1"},
    {"ref": "Psa.63", "kind": "seam", "verses": [11], "weight": "minor",
     "said": "sub-divide 9-11 before 11 as it is the 'but' case"},
    {"ref": "Psa.63", "kind": "group", "verses": [6, 7],
     "said": "6-7 is the tightly bound pair within 5-8 as 7 builds on 6"},
    {"ref": "Psa.63", "kind": "note",
     "said": "2, 3, and 4 each build on 1, arguably in larger surrounding circles"},

    {"ref": "Psa.65", "kind": "seam", "verses": [1], "weight": "mid-verse",
     "said": "same v1 break, but this time the intro sets context for the "
             "whole psalm"},
    {"ref": "Psa.65", "kind": "group", "verses": [5, 13],
     "said": "5-13 really all go together, with 12-13 breaking the 'you' "
             "reference mold and shifting to the pastures' reaction"},
    {"ref": "Psa.65", "kind": "note",
     "said": "not sure it was necessary to partition off 3, but it is distinct "
             "in its tone and binds more closely with 2 than 4; I would group "
             "1-2 first"},

    {"ref": "Psa.88", "kind": "seam", "verses": [1], "weight": "mid-verse",
     "said": "break in v1"},
    {"ref": "Psa.88", "kind": "group", "verses": [3, 8],
     "said": "3-8 are one lament that builds on 1b-2"},
    {"ref": "Psa.88", "kind": "seam", "verses": [6], "weight": "minor",
     "said": "agreed with the minor split before 6 as the focus shifts to 'You'"},
    {"ref": "Psa.88", "kind": "group", "verses": [9, 12],
     "said": "9 starts the shift and groups with 10-12, which is a list of "
             "4 tight questions"},
    {"ref": "Psa.88", "kind": "seam", "verses": [13],
     "said": "12 to 13 is another break with the tone becoming intense"},
    {"ref": "Psa.88", "kind": "tree", "verses": [15, 18],
     "said": "((15-(16-17))-18)"},

    {"ref": "Psa.92", "kind": "group", "verses": [1, 3],
     "said": "1b-3 is one sentence"},
    {"ref": "Psa.92", "kind": "seam", "verses": [6],
     "said": "the real break is before 6"},
    {"ref": "Psa.92", "kind": "tree", "verses": [6, 10],
     "said": "((((6-7)-8)-9)-10) -- each verse seems to expand on the section"},
    {"ref": "Psa.92", "kind": "group", "verses": [12, 15],
     "said": "12-15 build on one thought, though the quote is its own sub unit"},
    {"ref": "Psa.92", "kind": "seam", "verses": [14], "weight": "minor",
     "said": "a minor seam between 13 and 14"},
    {"ref": "Psa.92", "kind": "note",
     "said": "the first half of 4 looks forward and the second half sets the "
             "stage for 5"},

    {"ref": "Psa.143", "kind": "group", "verses": [7, 12],
     "said": "the address to God is 7-12"},
    {"ref": "Psa.143", "kind": "tree", "verses": [1, 12],
     "said": "((1b-2)-3)-(4-(5-(6-((7-9)-(10(11-12))))))  -- a buildup to the prayer"},
    {"ref": "Psa.143", "kind": "note",
     "said": "a change of tone in v10, but 11-12 shift back; 6 sets the stage "
             "for the prayer"},

    {"ref": "Psa.17", "kind": "tree", "verses": [8, 14],
     "said": "((8-9)-(10-14)), and 15 stands in contrast to it"},
    {"ref": "Psa.17", "kind": "note",
     "said": "the 'they' in verses 10-14 references the wicked in v9, which is "
             "tightly bound to 8"},

    {"ref": "Psa.38", "kind": "group", "verses": [1, 2],
     "said": "the 1-2 bind is apparent"},
    {"ref": "Psa.38", "kind": "group", "verses": [4, 8],
     "said": "4-8 gives the reason for 3"},
    {"ref": "Psa.38", "kind": "group", "verses": [6, 7],
     "said": "6-7 are bound in one cause and effect"},
    {"ref": "Psa.38", "kind": "seam", "verses": [9],
     "said": "there is a shift in 9"},
    {"ref": "Psa.38", "kind": "tree", "verses": [12, 14],
     "said": "(12-(13-14)) -- 13-14 contrasts 12"},
    {"ref": "Psa.38", "kind": "tree", "verses": [15, 17], "said": "(15-(16-17))"},
    {"ref": "Psa.38", "kind": "group", "verses": [19, 20],
     "said": "19-20 are tightly bound"},
    {"ref": "Psa.38", "kind": "group", "verses": [21, 22],
     "said": "21-22 are tightly bound"},

    {"ref": "Psa.103", "kind": "note",
     "said": "psalm 103 is difficult; I see more seams than I have emphasised "
             "because I focused on the major ones"},
]


def load_store():
    if not STORE.exists():
        return []
    return [json.loads(x) for x in
            STORE.read_text(encoding="utf-8").splitlines() if x.strip()]


def seed():
    rows = []
    for i, s in enumerate(SEED):
        rows.append({
            "id": f"doug-{i:03d}",
            "source": "Doug, by hand",
            "recorded": "2026-09-10",
            "versification": "english",
            **s,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", action="store_true",
                    help="write the hand-reading of twelve psalms to the store")
    ap.add_argument("--compare", action="store_true",
                    help="ONE-SHOT check against the current grouping. Named "
                         "compare, not apply: it changes nothing. Run it once, "
                         "on a grouping built without reference to it; running "
                         "it repeatedly while tuning is fitting, whatever it "
                         "is called.")
    a = ap.parse_args()

    if a.seed:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        rows = seed()
        STORE.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8")
        by = collections.Counter(r["kind"] for r in rows)
        ch = sorted({r["ref"] for r in rows})
        print(f"wrote {STORE.relative_to(ROOT)}  ({len(rows)} overlays)")
        print(f"  kinds: {dict(by)}")
        print(f"  passages: {', '.join(ch)}")
        return 0

    rows = load_store()
    if not rows:
        print("nothing stored — run with --seed")
        return 0
    print(f"held readings: {len(rows)}")
    print(f"  by kind: {dict(collections.Counter(r['kind'] for r in rows))}")

    if not a.compare:
        for r in rows[:6]:
            print(f"  {r['id']}  {r['ref']:<9} {r['kind']:<6} "
                  f"{r.get('verses') or ''}  {r['said'][:52]}")
        print("  ...")
        return 0

    # Re-application: does the current structure honour each judgment?
    seams = set()
    p = OUT / "seams.jsonl.gz"
    if p.exists():
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    if d.get("ref"):
                        seams.add(d["ref"])

    ok = orphan = skipped = 0
    print("\nAPPLYING TO THE CURRENT GROUPING")
    for r in rows:
        if r["kind"] in ("note", "tree"):
            skipped += 1
            continue
        vs = r.get("verses") or []
        if r["kind"] == "seam":
            hit = any(f"{r['ref']}.{v}" in seams for v in vs)
            if hit:
                ok += 1
            else:
                orphan += 1
                print(f"  ORPHAN  {r['id']}  {r['ref']} seam at {vs}"
                      f"   — {r['said'][:46]}")
        else:
            # a group holds if no seam falls strictly inside its span
            lo, hi = vs[0], vs[-1]
            inside = [v for v in range(lo + 1, hi + 1)
                      if f"{r['ref']}.{v}" in seams]
            if inside:
                orphan += 1
                print(f"  SPLIT   {r['id']}  {r['ref']} group {lo}-{hi}"
                      f" cut at {inside}   — {r['said'][:40]}")
            else:
                ok += 1
    print(f"\n  held {ok}   did not hold {orphan}   "
          f"not machine-checkable {skipped}")
    print("  'did not hold' is information, not failure: it says where the "
          "computed grouping and the reader disagree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
