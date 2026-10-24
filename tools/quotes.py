"""Direct speech as spans, tracked across verse boundaries.

The question was whether all quotes within sentences had been identified and
grouped as single nodes. No -- the clause extractor started a new clause at every finite
verb, so "And God said, Let there be light" became two unrelated clauses and
the quoted content lost its speaker.

## Why the closing mark is the whole problem

Both originals mark the OPENING of speech well -- Hebrew *lemor*, the
infinitive "saying" (964), and finite *amar* (4,345); Greek *hoti recitativum*
(1,331) and *legon* (474). **Neither marks where speech ends.** That is not a
gap in the tagging; the languages simply do not punctuate it.

Modern translations do, and that is a third witness rather than a shortcut:
the translators made the judgement, published it, and it can be read. 7,252 BSB
verses carry a quotation mark.

## The number that matters

**1,855 quotations open in one verse and close in another.** Those are exactly
the units a verse-shaped graph cannot hold, and they are why Job 38 -- one
utterance from the whirlwind -- was once 42 separate nodes. A speech node needs
its own span, and the span is not a verse.

The D6 ruling: one speech, one speaker, one hearer. The old graph's 42
nodes are the failure case.

    python tools/quotes.py            # counts and the longest speeches
    python tools/quotes.py --json     # writes out/quotes.jsonl
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bibleont.decompose import _load                              # noqa: E402

OPEN, CLOSE = "“", "”"
REF = re.compile(r"^([1-3]?[A-Za-z]+) (\d+):(\d+)$")


def spans() -> list:
    """Every quotation span, from its opening mark to its closing one.

    Nesting is real -- a speech quoting a speech -- and BSB marks the inner one
    with single quotes, so counting only the double marks keeps the outer span
    whole, which is the one that carries the speaker.
    """
    bsb = _load("verses.bsb.jsonl")
    verses = []
    for ref, txt in bsb.items():
        m = REF.match(ref)
        if m:
            verses.append((m.group(1), int(m.group(2)), int(m.group(3)),
                           ref, txt))
    verses.sort(key=lambda v: (v[0], v[1], v[2]))

    out = []
    open_at = None
    depth = 0
    buf = []
    last_key = None
    for bk, ch, vs, ref, txt in verses:
        key = (bk, ch)
        if key != last_key:
            # a chapter boundary closes any speech left hanging: better to end
            # a span than to run it into unrelated material
            if open_at and buf:
                out.append({"from": open_at, "to": last_ref,
                            "verses": len(buf), "text": " ".join(buf)[:400],
                            "closed": False})
            open_at, depth, buf = None, 0, []
        last_key, last_ref = key, ref

        for part in re.split(f"([{OPEN}{CLOSE}])", txt):
            if part == OPEN:
                if depth == 0:
                    open_at, buf = ref, []
                depth += 1
            elif part == CLOSE:
                depth = max(0, depth - 1)
                if depth == 0 and open_at:
                    out.append({"from": open_at, "to": ref,
                                "verses": _span_len(open_at, ref),
                                "text": " ".join(buf)[:400], "closed": True})
                    open_at, buf = None, []
            elif depth > 0 and part.strip():
                buf.append(part.strip())
    return out


def _span_len(a, b):
    ma, mb = REF.match(a), REF.match(b)
    if not ma or not mb:
        return 1
    if ma.group(1) != mb.group(1) or ma.group(2) != mb.group(2):
        return int(mb.group(3))            # crossed a chapter; approximate
    return int(mb.group(3)) - int(ma.group(3)) + 1


def main() -> int:
    sp = spans()
    multi = [s for s in sp if s["verses"] > 1]
    unclosed = [s for s in sp if not s["closed"]]
    print(f"quotation spans found: {len(sp):,}")
    print(f"  within one verse        {len(sp) - len(multi):>6,}")
    print(f"  crossing verses         {len(multi):>6,}")
    print(f"  never closed in chapter {len(unclosed):>6,}")
    print(f"  longest span            {max(s['verses'] for s in sp):>6} verses")
    print()
    print("the longest speeches in the canon -- each ONE node, not N:")
    for s in sorted(sp, key=lambda x: -x["verses"])[:10]:
        print(f"    {s['from']:12} → {s['to']:12} {s['verses']:>4} verses"
              f"   {s['text'][:38]}")
    print()
    byb = collections.Counter(REF.match(s["from"]).group(1) for s in multi
                              if REF.match(s["from"]))
    print("books with the most multi-verse speeches:")
    print("   ", dict(byb.most_common(8)))
    if "--json" in sys.argv:
        p = ROOT / "out" / "quotes.jsonl"
        with p.open("w", encoding="utf-8") as fh:
            for s in sp:
                fh.write(json.dumps(s, ensure_ascii=False) + "\n")
        print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
