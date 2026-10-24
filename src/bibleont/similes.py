"""Comparisons the text marks as comparisons.

The imagery layer's raw material, found the same way the citation formulas
were: not by deciding what is figurative, but by reading where the corpus says
so itself.

**The marker alone is not enough, and measuring showed it.** 186 verses carry
"even as", "so also" or "even so", and most are comparisons of *manner* rather
than of likeness -- "even as the Lord commanded Moses, so did the daughters of
Zelophehad" (Num 36:10) marks obedience, not a figure. Those are excluded, and
what remains are the markers that assert likeness outright:

```
is/are/was/were like unto     31 verses
is/are like a|an|the          39
likened unto                   5
```

Roughly ninety-five, and they carry both halves of the comparison in the verse
that states it -- which is the rule that keeps this descriptive. A pair is
admissible only when the words on both sides are present in the citation, the
same test the validator applies to a relation's parties.

## What this deliberately does not do

- **It does not create a symbol.** "Lion" is Christ at Rev 5:5 and the devil at
  1 Pet 5:8. A node meaning *lion the symbol* would unite them. What is recorded
  is the pair and its verse; the two readings sit side by side under one word
  and neither claims the other's sense.
- **It does not judge whether a comparison is figurative.** "The guilt offering
  is like the sin offering" (Lev 7:7) is a legal equivalence, and this
  cannot tell it from a metaphor. Both come out; the difference is a reader's.
- **It does not complete a mapping.** Ephesians 5 gives husband->Christ and
  wife->church and says nothing about children. What is stated is taken; the
  rest is left as a gap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .books import BOOK_TESTAMENT
from .corpus import get_corpus

# Only likeness. "Even as" and "so also" are excluded on measurement: they mark
# manner far more often than resemblance, and admitting them buries the figures
# under compliance formulas.
# Each pattern matches the marker and the vehicle only. The tenor is taken from
# the text *before* the marker rather than from a bounded capture: a character
# class that excludes punctuation cannot reach back across a colon, which is
# where Psalm 1:4 keeps its subject -- "Not so the wicked! For they are like
# chaff" in the BSB; the older rendering has a colon and "but are like" --
# and the capture returned "but".
PATTERNS = [
    (re.compile(r"\s(?:is|are|was|were)\s+like unto\s+"
                r"([a-z][\w' ]{2,60}?)\s*[,.;:]", re.I), "like unto"),
    (re.compile(r"\s(?:is|are)\s+like\s+(?:a|an|the)\s+"
                r"([a-z][\w' ]{2,60}?)\s*[,.;:]", re.I), "is like"),
    (re.compile(r"\s(?:is|be|shall be)\s+likened unto\s+"
                r"(?:a|an|the|ten|certain\s+)?([a-z][\w' ]{2,60}?)\s*[,.;:]", re.I),
     "likened unto"),
    # "As for man, his days are as grass"; "all flesh is as grass"; "his heart
    # is as the heart of a lion". **This is the King James Version's dominant
    # simile marker and the first pass missed it entirely**, which cost the
    # whole transience cluster -- dust, grass, flower, shadow, vapour -- since
    # almost none of it uses "like".
    (re.compile(r"\s(?:is|are|was|were)\s+as\s+(?:a|an|the)?\s*"
                r"([a-z][\w' ]{2,60}?)\s*[,.;:]", re.I), "is as"),
    # The appositive simile, set off by commas and followed by what it does:
    # "the devil, AS A ROARING LION, WALKETH ABOUT". No copula, so the patterns
    # above cannot see it -- and this is the form that carries the ground in
    # the open, which is the whole reason for wanting it.
    (re.compile(r",\s+as\s+(?:a|an)\s+([a-z][\w' ]{2,40}?),\s+"
                r"(?P<ground>[a-z][\w' ]{3,50}?)[,.;:]", re.I), "as a"),
]

# What the comparison is *in respect of*, and usually the verse says: "a
# shadow THAT DECLINETH", "chaff WHICH THE WIND DRIVETH AWAY", "a vapour THAT
# APPEARETH" (Jas 4:14).
#
# This is what keeps one word from becoming one symbol. Revelation's lion has
# prevailed and Peter's roaring lion walks about seeking whom he may devour;
# with the ground recorded they are visibly two figures sharing a noun, and
# nothing in the graph has to claim they mean the same. Without it, a reader
# meets a bare pair and supplies the collision themselves.
_GROUND = re.compile(r"\s+(that|which|whose|whereof|when|for)\s+", re.I)

# Openers that swallow the real subject when the sentence begins with a clause.
# The trailing \s+ mattered: a clause that is only "but" -- which is what Psalm
# 1:4 leaves against the marker -- was not stripped, so it survived as a tenor.
_LEAD = re.compile(r"^(?:and|but|for|then|therefore|behold|wherefore|so|now|"
                   r"again|yea|verily|because|that|which|when)(?:\s+|$)", re.I)

# "Who is like unto thee, O Lord?" asserts that nothing is comparable. Reading
# it as a comparison records the exact opposite of what the verse says, so the
# interrogatives are excluded rather than left for a reader to catch.
_RHETORICAL = {"who", "whom", "what", "whose"}

# A pronoun on either side needs an antecedent this cannot see. Dropping the
# pair loses a real comparison; keeping it silently would attach the figure to
# the wrong thing, so they are kept and marked.
_PRONOUNS = {"he", "she", "it", "they", "them", "thee", "thou", "him", "her",
             "us", "we", "ye", "you", "i", "me", "his", "their", "my", "thy"}


@dataclass
class Simile:
    """One stated comparison, with the verse that states it."""

    verse: str
    pretty: str
    marker: str
    tenor: str    # what is being compared
    vehicle: str  # what it is compared to
    ground: str   # the respect in which, where the verse states it
    text: str
    # True when either side is a pronoun whose referent is elsewhere. Kept
    # rather than discarded, because the comparison is real and only the
    # attachment is unresolved.
    unresolved: bool = False

    @property
    def testament(self) -> str:
        return BOOK_TESTAMENT.get(self.verse.split()[0], "?")


def _strip_lead(s: str) -> str:
    while True:
        trimmed = _LEAD.sub("", s.strip())
        if trimmed == s.strip():
            return trimmed
        s = trimmed


def _tidy(s: str) -> str:
    """The nearest clause before the marker that carries a subject.

    Not simply the last one. Psalm 1:4 in the older rendering is "...not so:
    but are like..." -- the clause touching the marker is only "but", and the
    tenor is on the far side of the colon. So clauses are tried from the marker
    backwards and the first with anything left after trimming conjunctions
    wins.
    """
    # ", and" opens a new clause as surely as a semicolon does; without it the
    # tenor of the second comparison in Deut 33:17 swallowed the first one's
    # vehicle.
    for part in reversed(re.split(r"[:;]|,\s+and\s+", s)):
        cleaned = _strip_lead(part.strip().strip(",;:."))
        if cleaned:
            return cleaned
    return ""


def survey(nt_only: bool = False) -> list[Simile]:
    corpus = get_corpus()
    out: list[Simile] = []
    seen: set[tuple[str, str, str]] = set()
    for v in corpus.iter_verses():
        if nt_only and BOOK_TESTAMENT.get(v.id.book) != "NT":
            continue
        for rx, marker in PATTERNS:
            for m in rx.finditer(v.text):
                tenor, vehicle = _tidy(v.text[: m.start()]), _tidy(m.group(1))
                ground = ""
                if "ground" in (rx.groupindex or {}):
                    ground = _tidy(m.group("ground"))
                split = _GROUND.split(vehicle, maxsplit=1)
                if len(split) == 3 and not ground:
                    vehicle, ground = split[0].strip(), f"{split[1]} {split[2]}".strip()
                elif len(split) == 3:
                    vehicle = split[0].strip()
                if not tenor or not vehicle:
                    continue
                # A comparison of a thing to itself is a parsing artefact.
                if tenor.lower() == vehicle.lower():
                    continue
                if tenor.lower().split()[-1] in _RHETORICAL:
                    continue
                key = (str(v.id), tenor.lower(), vehicle.lower())
                if key in seen:
                    continue
                seen.add(key)
                ends = {tenor.lower().split()[-1], vehicle.lower().split()[-1]}
                out.append(Simile(str(v.id), v.id.pretty(), marker,
                                  tenor, vehicle, ground, v.text,
                                  unresolved=bool(ends & _PRONOUNS)))
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Comparisons the text marks itself.")
    ap.add_argument("--nt", action="store_true")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args(argv)

    rows = survey(nt_only=args.nt)
    print(f"{len(rows)} stated comparisons\n")
    for s in rows[: args.limit]:
        flag = " ?" if s.unresolved else "  "
        g = f"  ({s.ground[:34]})" if s.ground else ""
        print(f" {flag}{s.pretty:18} {s.tenor[-30:]:30} -> {s.vehicle[:26]:26}{g}")
    if len(rows) > args.limit:
        print(f"\n  ... {len(rows) - args.limit} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
