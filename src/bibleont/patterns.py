"""Verses that share a shape rather than a wording.

The phrase layer finds verses that reuse words. This finds verses that reuse a
**construction** -- the same moves in the same order, with different vocabulary
in the slots. Those are different things and the second is much harder.

## The case this was built from

Joshua 1:9 and Isaiah 41:10 are the same sentence three times over:

    be not afraid          |  fear thou not
    neither be dismayed    |  be not dismayed
    for the Lord thy God   |  for I am with thee
    is with thee

Two negated imperatives about fear, then a reason introduced by *for*, and the
reason is presence. **Nothing in the phrase layer connects them**: they share
"be not" and "for", which are function words, and nothing else.

Run as a shape, the corpus gives **ten** of them -- eight more than the two the
reader had noticed, including Deuteronomy 31:6 spoken by Moses to Israel and
1 Chronicles 28:20 spoken by David to Solomon, which is the same charge handed
down twice more.

## A second construction, and why it was looked for

The same reader observed that the five verses he had offered were all on his
own memory list, and suggested that **the verses people love may be loved
partly for their shape**. That is testable, and it holds.

Measured across the three hundred most-quoted references against the whole
corpus:

```
not X, but Y                        6.7%  vs  2.4%   2.78x
imperative + for/because            3.5%  vs  1.8%   1.94x
first-person divine "I will"        7.7%  vs  4.9%   1.56x
conditional if/then                 3.0%  vs  2.0%   1.49x
universal all/every/whosoever      24.1%  vs 18.3%   1.32x
second-person address              36.1%  vs 29.4%   1.23x
comparison as/like                  4.0%  vs  3.8%   1.04x
"shall"                            19.7%  vs 19.5%   1.01x
```

The bottom two are the control and they matter. **The verses people memorise
are not simply the promises or the figurative ones** -- those features do not
distinguish them at all. They are disproportionately the ones that *correct
something*: name a thing you might have assumed, and replace it.

## What it cannot do, which is the more useful half

The same reader pointed at four New Testament verses as the same message:
Philippians 4:6-7, 1 Peter 5:7, John 14:27. **This detector finds none of
them**, and it is right not to:

- **Phil 4:6** replaces the second negation with a positive instruction --
  "but in every thing by prayer" -- and puts the promise in the next verse.
- **1 Pet 5:7** compresses the whole thing into a participle and a clause:
  "Cast all your anxiety on Him, because He cares for you." The fear word is
  gone; only the causal clause survives.
- **John 14:27** inverts the order, giving the promise first and the negation
  last.

So the finding is not that pattern detection works. It is that **pattern
detection works exactly as far as the form is stable, and the New Testament
varies the form deliberately.** A detector tuned until it caught all five would
catch several hundred verses that mean nothing like them.

That is the same lesson the phrase layer learned about normalising thou and ye,
and the comparison counter learned about the Sermon on the Mount: an instrument
that finds one kind of thing should say which kind, and a reader who wants the
other kind is better served by being told so than by a widened net.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .corpus import get_corpus

# Negated imperatives about fear. Deliberately literal: every one of these is
# a form the KJV actually uses, and no stemming is applied, because the shape
# being detected is a construction and not a word.
FEAR_NEGATION = re.compile(
    r"\b(fear not|fear thou not|fear ye not|be not afraid|neither be afraid|"
    r"be not dismayed|neither be thou dismayed|nor be dismayed|"
    r"be not terrified|let not your heart be troubled|"
    r"be careful for nothing|take.{0,12}no thought)\b", re.I)

# The pivot. This is the word doing the structural work, and it is why the
# construction is findable at all.
REASON = re.compile(r"\b(for|because)\b", re.I)

# What the reason offers. Presence is one promise among several the corpus
# gives, and it is the one Joshua 1:9 and Isaiah 41:10 share.
PRESENCE = re.compile(
    r"\b(i am with (?:thee|you)|i will be with (?:thee|you)|"
    r"will be with (?:thee|you)|is with (?:thee|you)|"
    r"doth go with (?:thee|you)|am with (?:thee|you)|"
    r"i am thy god|the lord thy god is with)\b", re.I)


# "Not X, but Y." The construction that most distinguishes the verses people
# quote from the verses they do not -- see `antithesis` below.
ANTITHESIS = re.compile(r"\bnot\b.{0,60}\bbut\b", re.I)


@dataclass
class Shape:
    """One verse matching a construction, with the parts it matched on."""

    ref: str
    text: str
    negation: str
    reason: str = ""
    promise: str = ""
    parts: list[str] = field(default_factory=list)


def fear_not_for_presence(min_parts: int = 3) -> list[Shape]:
    """Verses that negate fear and then promise presence as the reason.

    Three parts required by default: the negation, a `for` after it, and a
    presence clause. Dropping to two widens it to forty-six verses whose
    reasons are anything at all -- an enemy delivered, a city taken, a child
    promised -- which is a different and much looser question.
    """
    out: list[Shape] = []
    for verse in get_corpus().iter_verses():
        neg = FEAR_NEGATION.search(verse.text)
        if not neg:
            continue
        rest = verse.text[neg.end():]
        why = REASON.search(rest)
        pres = PRESENCE.search(verse.text)
        parts = ["negation"]
        if why:
            parts.append("reason")
        if pres:
            parts.append("presence")
        if len(parts) < min_parts:
            continue
        out.append(Shape(
            ref=str(verse.id), text=verse.text, negation=neg.group(0),
            reason=why.group(0) if why else "",
            promise=pres.group(0) if pres else "", parts=parts))
    return out


def antithesis(refs: list[str] | None = None) -> list[Shape]:
    """Verses built on "not X, but Y".

    **The strongest structural signal separating quoted verses from the rest.**
    Measured against the 300-verse famous list: 6.7% of those verses carry this
    construction against 2.4% of the corpus, a lift of 2.78 -- higher than
    imperative-plus-reason (1.94), first-person divine speech (1.56) or
    conditional promise (1.49), and far above comparison (1.04) and the word
    "shall" (1.01), which do not distinguish them at all.

    That last pair is the useful control. The verses people memorise are not
    simply the promises or the figurative ones. They are disproportionately
    the ones that **correct something** -- that name a thing you might have
    assumed and replace it.

    Twenty-seven of the famous three hundred are built this way, and the list
    reads like the reason the hypothesis was worth testing: not by might nor by
    power but by My Spirit; man shall not live on bread alone but on every
    word; the Son of Man did not come to be served but to serve; do not be
    conformed but be transformed; our struggle is not against flesh and
    blood; I no longer live, but Christ lives in me; God has not given us a
    spirit of fear, but of power.
    """
    corpus = get_corpus()
    wanted = set(refs) if refs else None
    out: list[Shape] = []
    for verse in corpus.iter_verses():
        if wanted is not None and str(verse.id) not in wanted:
            continue
        m = ANTITHESIS.search(verse.text)
        if m:
            out.append(Shape(ref=str(verse.id), text=verse.text,
                             negation=m.group(0)[:40], parts=["antithesis"]))
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--parts", type=int, default=3,
                    help="how many of negation/reason/presence to require")
    ap.add_argument("--antithesis", action="store_true",
                    help="verses built on 'not X, but Y' instead")
    args = ap.parse_args(argv)

    if args.antithesis:
        rows = antithesis()
        print(f"{len(rows)} verses built on 'not X, but Y'")
        print()
        for r in rows[:40]:
            print(f"  {r.ref:12} {r.text[:112]}")
        return 0

    rows = fear_not_for_presence(args.parts)
    print(f"{len(rows)} verses matching the shape "
          f"(at least {args.parts} parts)\n")
    for r in rows:
        print(f"  {r.ref:12} {r.negation!r} + {r.reason!r} + {r.promise!r}")
        print(f"               {r.text[:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
