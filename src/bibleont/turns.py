"""Dialogue turns, found from the markers the corpus states outright.

## Why this exists

2026-08-31, on seeing 728 speech nodes renamed to "<Speaker> at <verse>":
speakers should be tied only to the highest-level node in their dialog turn,
and that really requires grouping. The node can be succinct because the graph
below contains the structure. Speech tied to verses will not age well.

The graph currently keys speech to verses, and a verse is not a unit of
speech. It is the unit the EXTRACTION WINDOW uses -- twelve at a time -- so the
node boundary is a property of the tooling rather than of the discourse.
Nothing in the text says Zophar stopped talking at the end of verse 10.

    Job 11    one speech by Zophar, verses 1-20      13 nodes
    Job 38    God answering out of the whirlwind     42 nodes
    Gen 24    the servant's mission                  57 nodes

## Why it needs no model

`group.py` asks a model where a book's passages and movements are, because
narrative structure is not marked. **A dialogue turn is marked**, and the King
James marks it in a form a regex can find: *"Then answered Eliphaz the
Temanite, and said"*, *"But Job answered and said"*.

Run over Job, twenty-seven markers reproduce the book's structure exactly --
the prologue exchanges, three cycles of Eliphaz-Job-Bildad-Job-Zophar-Job, the
third cycle stopping after Bildad because **Zophar has no third speech**,
Elihu, and the voice from the whirlwind. That is not an approximation of the
scholarly outline; it is the same outline, and it cost nothing.

So the split is by evidence, not by ambition:

    MARKED      dialogue turns. Deterministic, free, exact. Here.
    UNMARKED    passages and movements. Needs a wider reading. `group.py`.

## What it must not do

**A turn is a span, not a claim about content.** This module says Zophar spoke
from 11:1 to 11:20 and nothing whatever about what he said. The claims inside
belong to the extraction and hang beneath the turn; keeping those two apart is
what lets the turn node be succinct, which was the point of the 2026-08-31 decision.

It also does not merge speeches. Two consecutive turns by the same speaker are
two turns -- Job 40:3 and Job 42:1 are separate replies with God speaking
between them, and flattening them would erase the exchange.

## What it gets wrong, stated rather than hidden

**The start of a turn is marked and the end is not.** So a turn runs from its
marker to the verse before the next one, and where narrative sits between two
speeches the turn absorbs it. In Job that is three of twenty-nine: Satan's
reply at 1:9 runs over the messengers, his reply at 2:4 runs into chapter 3,
and Job's last speech runs over the five verses introducing Elihu.

The dialogue cycles -- the bulk of the book and the part that matters -- are
exact. The over-extension is predictable, always at the end, and always into
narrative rather than into another speech, so a later pass can trim it with
the text in view. `group.py` is where that belongs; guessing here would make
the span a fact about this module rather than about the book.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from .paths import ROOT

# A turn opens where a NAMED speaker is said to speak. Both word orders occur,
# and the corpus favours a different one per genre:
#
#     Job's cycles      "Then answered Eliphaz the Temanite, and said"
#     Genesis, Mark     "And the LORD said unto Abram"
#
# **The name is what makes this usable.** A first version required only the
# verb, which caught "he said" and "she said" -- and a pronoun continues a
# turn rather than opening one, so Genesis came back with a single turn
# running from 9:8 to 16:12 and Mark's speakers were "he", "she", "He".
#
# Measured, the cost of demanding a name is almost nothing: 98% of Genesis's
# speech markers name their speaker and 99% of Mark's.
# THE SMALL CAPS ARE NOT IN OUR KJV FILE, so the two most specific branches
# here were dead code against our own data. Measured 2026-09-09:
#
#     verses.jsonl   LORD 6      Lord 7,719     <- distinction LOST
#     verses.bsb     LORD 6,490  Lord 1,106
#     verses.web     LORD 6,576  Lord 1,139
#
# The real KJV prints YHWH as "LORD" and Adonai as "Lord"; whatever conversion
# produced our file flattened both to "Lord". So `the LORD` never matched and
# "the Lord said" fell through to the generic `[A-Z][a-z]+` branch, yielding
# the speaker "Lord" -- or, with the preceding conjunction, "And the Lord".
#
# Matching both cases restores the branch. It does NOT recover the distinction:
# in this file "the Lord" may be YHWH or Adonai and the string cannot say which.
# The ruling of 2026-09-09 is that the KJV file is demoted to verse numbering
# and any layer needing the divine name's IDENTITY resolves it from MACULA's
# lemma at that verse, which distinguishes them at source.
_NAME = (r"(?:the LORD God|the LORD|the Lord God|the Lord|God|Jesus|"
         r"[A-Z][a-z]+(?: the [A-Z][a-z]+)?)")
_VERB = r"(?:answered|spake|said|saith)"

_FORWARD = _NAME + r"\s+" + _VERB + r"\b"        # <Name> said / answered
_INVERTED = r"\b(?:answered|spake)\s+" + _NAME   # Then answered <Name>

_ANSWERED = re.compile(_FORWARD + r"|" + _INVERTED)

# Who is speaking, from the same sentence. Deliberately crude; trailing
# connectives are stripped below rather than encoded here.
_WHO = re.compile(
    r"(" + _NAME + r")\s+" + _VERB
    + r"|"
    + r"(?:answered|spake)\s+(" + _NAME + r")"
)

_TRAILING = re.compile(r"[,;:]?\s*(and|unto|to|out of|again)\s*$", re.I)

# The generic branch of _NAME carries an optional " the <Word>" tail so that
# "Bildad the Shuhite" survives intact. It also swallows a preceding
# conjunction: "And the Lord said" matches from "And", one word earlier than
# "the Lord", and Python's leftmost rule prefers it. Measured before the fix:
# "And the Lord" 267 attributions against "the Lord" 73, i.e. the same speaker
# split across two strings with the larger share under the wrong one.
_LEADING = re.compile(r"^(?:and|but|so|then|now|for|therefore|yet)\s+", re.I)


@dataclass
class Turn:
    book: str
    speaker: str          # as the text names them, cleaned
    start: tuple          # (chapter, verse)
    end: tuple            # (chapter, verse), inclusive
    marker: str           # the verse text that opened it

    @property
    def ref(self) -> str:
        c1, v1 = self.start
        c2, v2 = self.end
        if (c1, v1) == (c2, v2):
            return f"{self.book} {c1}:{v1}"
        if c1 == c2:
            return f"{self.book} {c1}:{v1}-{v2}"
        return f"{self.book} {c1}:{v1}-{c2}:{v2}"

    @property
    def id(self) -> str:
        c1, v1 = self.start
        who = re.sub(r"[^a-z0-9]+", "_", self.speaker.lower()).strip("_")
        return f"{self.book.lower()}_{c1}_{v1}_turn_{who}"[:80]

    @property
    def verses(self) -> int:
        # Only meaningful within a chapter; across chapters it under-counts,
        # which is fine because it is used for reporting rather than logic.
        if self.start[0] == self.end[0]:
            return self.end[1] - self.start[1] + 1
        return -1


def _verses(book: str) -> dict:
    out = {}
    from .paths import text_path
    path = text_path()
    for line in path.open(encoding="utf-8"):
        d = json.loads(line)
        if d.get("b") == book:
            out[(d["c"], d["v"])] = d["t"]
    return out


def _speaker(text: str) -> str:
    m = _WHO.search(text)
    if not m:
        return "?"
    who = (m.group(1) or m.group(2) or "").strip()
    # "Bildad the Shuhite, and" -> "Bildad the Shuhite"
    # "And the Lord"           -> "the Lord"
    while True:
        stripped = _LEADING.sub("", _TRAILING.sub("", who)).strip()
        if stripped == who:
            break
        who = stripped
    return who or "?"


def _speech_verses(book: str) -> set:
    """Verses the extraction identified as speech, from the graph.

    The START of a turn is marked in the text and exact. The END is not
    marked at all, so a turn naively runs to wherever the next one begins and
    swallows any narrative in between -- which put Satan's three-verse speech
    at Job 1:9-2:1, absorbing the messengers and the loss of Job's children.

    The graph already knows better. Every `*_speech` node carries the verses
    the extraction judged to be speech, so the last such verse inside a span
    is where the speaking stops. This uses the extraction to bound the turn
    and the text to open it, which is each source doing what it is good at.

    TRIED AND REVERTED, and left here with the reason because the idea is
    tempting enough to be had twice.

    It is wrong in both directions. The speech verses inside a span are not
    only the SPEAKER'S: Satan's turn at Job 1:9 runs to the next marker at
    2:2, and the messengers speak at 1:15-19 inside it, so bounding on "last
    speech verse" moved his three-verse speech to 1:9-21 rather than 1:9-11.
    And it inherits the extraction's gaps: Job 3 is extracted only through
    verse 12, so Job's lament -- 3:2-26 -- came back as 3:2-12, a turn
    truncated by how far a batch happened to get.

    A turn is a fact about the text. Bounding it with a derived artefact makes
    it a fact about the pipeline, which is the whole complaint that started
    this module. Off by default.
    """
    try:
        from .graph import Store
    except Exception:                                        # noqa: BLE001
        return set()
    out = set()
    prefix = book.lower() + "_"
    for e in Store.load().people.values():
        if not e.id.startswith(prefix) or "speech" not in e.id:
            continue
        for r in (e.refs or []):
            m = re.match(r"^\S+\s+(\d+):(\d+)", str(r))
            if m:
                out.add((int(m.group(1)), int(m.group(2))))
    return out


def graph_speakers(book: str) -> dict:
    """(chapter, verse) -> speaker id, from what the extraction recorded.

    **The text marks WHERE a turn opens; the graph knows WHO opened it.**
    Each source is used for the thing it is reliable about.

    A regex cannot tell a grammatical subject from a noun in a relative
    clause, and Mark 3:22 shows it exactly: "the scribes ... from Jerusalem"
    (BSB: "who had come down from Jerusalem") yields the speaker *Jerusalem*. No amount of pattern
    tightening fixes that, because the information needed is syntactic and a
    marker is not.

    The extraction already resolved it -- `asserted_by` on a speech node names
    the speaker, and `told` / `answered` name it from the other side.
    Measured: the graph supplies the speaker for 91% of Genesis's turns. Mark
    manages 7% only because Mark is ten windows of sixty-four extracted, so
    that number rises on its own as the book is finished rather than needing
    anything built.
    """
    try:
        from .graph import Store
        s = Store.load()
    except Exception:                                        # noqa: BLE001
        return {}
    said_by = {}
    for r in s.relations:
        if r.type == "asserted_by":
            said_by.setdefault(r.src, r.dst)
        elif r.type in ("told", "answered"):
            said_by.setdefault(r.dst, r.src)

    out = {}
    for e in s.people.values():
        if "speech" not in e.id:
            continue
        who = said_by.get(e.id)
        if not who:
            continue
        person = s.people.get(who)
        for x in (e.refs or []):
            m = re.match(r"^(\S+)\s+(\d+):(\d+)", str(x))
            if m and m.group(1) == book:
                out.setdefault((int(m.group(2)), int(m.group(3))),
                               person.name if person else who)
    return out


def find(book: str, bound: bool = False) -> list[Turn]:
    """Every dialogue turn in a book, in order."""
    verses = _verses(book)
    speech = _speech_verses(book) if bound else set()
    from_graph = graph_speakers(book)
    keys = sorted(verses)
    starts = []
    for k in keys:
        text = verses[k]
        if _ANSWERED.search(text):
            starts.append((k, _speaker(text), text))

    turns = []
    for i, (k, who, text) in enumerate(starts):
        # A turn runs to the verse before the next one opens, or to the end of
        # the book. Not to the end of the chapter: God's answer from the
        # whirlwind runs from 38:1 into chapter 40, and a chapter boundary is
        # no more a unit of speech than a verse is.
        end = keys[-1]
        if i + 1 < len(starts):
            nxt = starts[i + 1][0]
            before = [x for x in keys if x < nxt]
            end = before[-1] if before else k

        # Pull the end back to the last verse the extraction called speech.
        # Never past the opening verse, and never used when the book has not
        # been extracted -- an unbounded turn is honest, a wrongly-bounded one
        # is not.
        if speech:
            inside = [x for x in keys if k <= x <= end and x in speech]
            if inside:
                end = max(inside)

        # The graph wins where it has an answer; the marker is the fallback.
        turns.append(Turn(book=book, speaker=from_graph.get(k, who),
                          start=k, end=end, marker=text))
    return turns


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m bibleont.turns <Book> [<Book> ...]")
        print("       the dialogue turns a book marks in its own text")
        return 2

    for book in argv:
        if book.startswith("--"):
            continue
        ts = find(book)
        print(f"  {book}: {len(ts)} turn(s)")
        for t in ts:
            span = f"{t.verses} verses" if t.verses > 0 else "spans chapters"
            print(f"    {t.ref:<20} {t.speaker:<32} {span}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
