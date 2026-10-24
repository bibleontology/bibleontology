"""The sentence layer: the first grouping above the clause, and it was free.

2026-09-05: verses are good as an index for people, but internally the verse
is not the index; every sentence gets an internal id, and the groupings go up
from there all the way to the scroll. And on the id itself: the start of a
sentence is labeled by verse, and a verse can have more than one sentence
identified by it.

MACULA marks 31,224 `<sentence>` elements and the pipeline has never read one.
It also encodes the verse as `<milestone unit="verse">` -- a marker laid over
the text rather than a container of it -- so Clear Bible had already made the
call this project arrived at independently.

## The id

Verse-anchored, with an ordinal only where one is earned:

    96% of verses start exactly one sentence   -> the id IS the verse
     4% start two or more                      -> Gen.1.1#2, and so on
     worst case in the corpus                  -> 1Co 11:22, five

A sentence spanning verses is labelled by the verse it STARTS in, and the verses
it runs through start nothing of their own. Matthew's genealogy is one sentence
of 82 words across Matt 1:2-1:6, so 1:3, 1:4 and 1:5 label nothing.

The ordinal is stored always and dropped by the display layer when it is `#1`:
uniform internally means no code has to guess whether a suffix is present.

## Why it matters, stated honestly

It does NOT widen what the rules can reach. Measured before building: a sentence
window recovers **7 more relations out of 5,224**, because Masoretic verse
divisions follow syntactic accents and already track sentences to within 4%.

What it gives is a **unit that is not a milestone** -- one the reader can be
shown, one that patterns and structure can be computed over, and the first rung
of the ladder up to paragraph, speech and scroll. `tools/patterns.py` and the
`/api/unit` contract both take a ref and do not care what kind of unit it names,
so this is a new query rather than a rewrite.

    python tools/sentences.py
    python tools/sentences.py --spanning     # the ones that cross a verse
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from macula import MAC, _ref                                      # noqa: E402

OUT = ROOT / "out"


def extract():
    """One record per sentence, keyed by the verse it starts in."""
    out = []
    per_start = collections.Counter()
    for f in sorted(glob.glob(str(MAC) + "/**/*.xml", recursive=True)):
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for s in root.iter("sentence"):
            ws = [w for w in s.iter("w")]
            if not ws:
                continue
            refs, seen = [], set()
            for w in ws:
                r = _ref(w.get("ref") or "")
                if r and r not in seen:
                    seen.add(r)
                    refs.append(r)
            if not refs:
                continue
            start = refs[0]
            per_start[start] += 1
            n = per_start[start]
            out.append({
                "id": f"{start}#{n}",
                "ref": start,
                "n": n,
                "verses": refs,
                "spans": len(refs) > 1,
                "words": len(ws),
                # the reading gloss, so a sentence can be recognised without
                # opening it
                "gloss": " ".join((w.get("english") or w.get("gloss") or "")
                                  .strip() for w in ws[:14]).strip(),
            })
    return out, per_start


def main() -> int:
    rows, per_start = extract()

    if "--spanning" in sys.argv:
        sp = [r for r in rows if r["spans"]]
        sp.sort(key=lambda r: -len(r["verses"]))
        print(f"SENTENCES CROSSING A VERSE BOUNDARY  {len(sp):,}")
        for r in sp[:16]:
            print(f"   {r['id']:16}{len(r['verses'])} verses, "
                  f"{r['words']:>3} words   {r['verses'][0]}–{r['verses'][-1]}")
            print(f"      {r['gloss'][:88]}")
        return 0

    dist = collections.Counter(per_start.values())
    span = sum(1 for r in rows if r["spans"])
    verse_to = collections.defaultdict(list)
    for r in rows:
        for v in r["verses"]:
            verse_to[v].append(r["id"])

    path = OUT / "sentences.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_source": "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., "
                       "CC BY 4.0",
            "_note": "One record per sentence. Id is the STARTING verse plus an "
                     "ordinal; a sentence crossing verses labels only its "
                     "first.",
        }) + "\n")
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    (OUT / "sentences-by-verse.json").write_text(
        json.dumps(verse_to), encoding="utf-8")

    print("THE SENTENCE LAYER")
    print(f"  sentences                 {len(rows):>7,}")
    print(f"  verses that start one     {len(per_start):>7,}")
    print(f"  crossing a verse boundary {span:>7,}   "
          f"{100*span//max(len(rows),1)}%")
    print()
    print("  sentences started per verse:")
    for k in sorted(dist):
        print(f"    {k}: {dist[k]:>6,} verses"
              + ("   <- the id IS the verse" if k == 1 else ""))
    print(f"\n  wrote {path}")
    print(f"  wrote {OUT / 'sentences-by-verse.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
