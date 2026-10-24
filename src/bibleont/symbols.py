"""Whether a reader's word for a figure reaches the graph's record of it.

The symbol checklist is written in the words a reader arrives with. The graph
is written in the words the corpus uses. Those are not the same vocabulary, and
the gap is invisible from either side alone:

```
reader says     graph holds            because
rainbow         bow_in_the_cloud       Genesis says "my bow in the cloud"
incense         image_incense "odours" the King James says odours
```

A record can be complete, cited and well connected, and still be unreachable
by the only word a reader would type. **That is a search failure that looks
exactly like a coverage gap**, and telling them apart is what this does.

## Both translations, and why

Searching one translation finds the figures that translation names. Searching
two finds the figures *either* names, and the difference between them is a
supply of aliases nobody has to invent: where the King James says odours and
the American Standard says incense, the reader's word is already in the corpus
-- just not in the copy this graph is built on.

That is the same instrument as `divergence.alias_candidates`, pointed at a list
instead of at the concept layer, and it is worth more here because figurative
vocabulary is where translations diverge most.

## The three outcomes

```
held        a record exists and answers to the reader's word
renamed     a record exists and does not -- an alias is missing, not a figure
absent      no record; the figure is genuinely not in the graph
```

**`renamed` is the useful column.** It is cheap to fix, invisible without this,
and every row in it is a reader who searched correctly and got nothing.

## What this does not do

It does not check the gloss. The checklist's third column -- "rainbow: covenant
mercy" -- is the reader's reading, and a row is not made complete by recording
it. Only the figure and its verses are scored here, which is the same rule the
imagery layer already follows.
"""
from __future__ import annotations

import collections
import pathlib
import re
from dataclasses import dataclass, field

from .corpus import Corpus, get_corpus, parse_ref
from .graph import Store
from .paths import VERSES_JSONL

CHECKLIST = pathlib.Path("tests/symbols_200_checklist.txt")
ASV = pathlib.Path("data/bible/verses.asv.jsonl")

# Words that carry no figure and would match everything.
STOP = frozenset("""the a an of and or in on to for with from is are was were
be been by at as it its his her their our your my me him them they we you i
that this these those which who whom what when where how why not no nor all
any some each every other than more most much many one two three both such
same own very now here after before while until because again also even yet
still likewise therefore wherefore behold verily said say""".split())


@dataclass
class Row:
    n: str
    symbol: str
    sense: str
    words: list[str] = field(default_factory=list)
    kjv_verses: int = 0
    asv_verses: int = 0
    records: list[str] = field(default_factory=list)
    reachable: bool = False
    near: list[str] = field(default_factory=list)
    alias_hints: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.reachable:
            return "held"
        if self.near:
            return "renamed"
        return "absent"


def _terms(symbol: str) -> list[str]:
    """The searchable words in a checklist entry.

    "Rod or staff" is two figures; "Sackcloth and ashes" is two; "Ark of the
    Covenant" is one with three words in it. Splitting on the connectives and
    dropping the joining words leaves what can actually be looked for.
    """
    parts = re.split(r"\s*(?:/|,| or | and )\s*", symbol.lower())
    out = []
    for part in parts:
        words = [w for w in re.findall(r"[a-z']+", part) if w not in STOP]
        if words:
            out.append(" ".join(words))
    return out or [symbol.lower()]


def load(path: pathlib.Path | None = None) -> list[Row]:
    text = (path or CHECKLIST).read_text(encoding="utf-8")
    rows: list[Row] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        rows.append(Row(n=parts[0], symbol=parts[1], sense=parts[2],
                        words=_terms(parts[1])))
    return rows


def survey(store: Store | None = None,
           path: pathlib.Path | None = None) -> list[Row]:
    """Score every row, and find the alias where the word has been renamed.

    Three passes. First, which records answer to the reader's word. Second,
    which verses each translation uses the word in. Third -- and this is the
    one worth having -- for a word no record answers to, whether some record
    *cites* a verse the word appears in. If it does, the figure is in the
    graph under another name, and the words that verse uses in the other
    translation are the alias worth adding.
    """
    store = store or Store.load()
    kjv = get_corpus()
    asv = Corpus.load(ASV) if ASV.exists() else None

    # A symbol is not a person. Interpretive and concrete types only.
    WANTED = {"image", "object", "observance", "text", "title", "creature",
              "concept", "covenant", "place"}

    by_word: dict[str, list[str]] = collections.defaultdict(list)
    cites: dict[str, set[str]] = {}
    for pid, person in store.people.items():
        if person.type not in WANTED:
            continue
        cites[pid] = set()
        for ref in person.refs:
            try:
                for v in kjv.expand(parse_ref(ref)):
                    cites[pid].add(str(v))
            except Exception:
                cites[pid].add(ref)
        for name in person.names():
            low = name.lower()
            by_word[low].append(pid)
            for w in re.findall(r"[a-z']{4,}", low):
                if w not in STOP:
                    by_word[w].append(pid)

    # Which verses each translation uses each word in, indexed once. Scanning
    # per symbol would be two hundred passes over thirty-one thousand verses,
    # twice over.
    def index(corpus):
        where: dict[str, set[str]] = collections.defaultdict(set)
        if corpus is None:
            return where
        for verse in corpus.iter_verses():
            vid = str(verse.id)
            for w in set(re.findall(r"[a-z']+", verse.text.lower())):
                where[w].add(vid)
        return where

    kjv_where = index(kjv)
    asv_where = index(asv)
    asv_text = {}
    if asv is not None:
        asv_text = {str(v.id): v.text for v in asv.iter_verses()}

    rows = load(path)
    for row in rows:
        heads = {t.split()[-1] for t in row.words}

        found: list[str] = []
        for term in row.words:
            for key in (term, term.split()[-1]):
                for pid in by_word.get(key, []):
                    if pid not in found:
                        found.append(pid)
        row.records = found[:4]
        row.reachable = bool(found)

        verses = set()
        for h in heads:
            verses |= kjv_where.get(h, set())
            verses |= asv_where.get(h, set())
        row.kjv_verses = sum(len(kjv_where.get(h, ())) for h in heads)
        row.asv_verses = sum(len(asv_where.get(h, ())) for h in heads)

        if row.reachable or not verses:
            continue

        # No record answers to the word, but the word is in the corpus. Does
        # any record cite a verse that uses it? If so the figure is held under
        # another name, and this is a missing alias rather than a missing
        # figure.
        # Sharing one verse proves nothing -- Esther 4 mentions a sceptre, so
        # every saying citing that chapter "overlaps" with sceptre. What marks
        # a record as being *about* the word is that most of its own citations
        # use it. Scored as that share, and only the strong ones are kept.
        scored = []
        for pid, refs in cites.items():
            if not refs:
                continue
            share = len(refs & verses) / len(refs)
            if share >= 0.6:
                scored.append((share, len(refs), pid))
        scored.sort(reverse=True)
        row.near = [pid for _, _, pid in scored[:4]]

        # Where the two translations differ on that verse, the other one's
        # wording is where the reader's word came from -- that is the alias.
        for _, _, pid in scored[:3]:
            for vid in sorted(cites[pid] & verses)[:3]:
                kjv_has = any(vid in kjv_where.get(h, ()) for h in heads)
                asv_has = any(vid in asv_where.get(h, ()) for h in heads)
                if asv_has and not kjv_has:
                    hint = f"{store.people[pid].name!r} += {sorted(heads)[0]}"
                    if hint not in row.alias_hints:
                        row.alias_hints.append(hint)
    return rows


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", choices=["held", "renamed", "absent"])
    ap.add_argument("--top", type=int, default=200)
    args = ap.parse_args(argv)

    rows = survey()
    tally = collections.Counter(r.status for r in rows)
    print(f"{'':10}{'symbol':30}{'KJV':>6}{'ASV':>6}   record")
    shown = 0
    for r in rows:
        if args.only and r.status != args.only:
            continue
        if shown >= args.top:
            break
        shown += 1
        where = ", ".join(r.records[:2]) or ", ".join(r.near[:2])
        if r.alias_hints:
            where += "   ALIAS " + "; ".join(r.alias_hints[:2])
        print(f"{r.status:10}{r.symbol[:28]:30}{r.kjv_verses:6}"
              f"{r.asv_verses:6}   {where}")
    print(f"\n{tally['held']} held, {tally['renamed']} renamed, "
          f"{tally['absent']} absent   ({len(rows)} symbols)")
    print("\nThe gloss is never scored. A row is done when the figure exists "
          "and is cited,\nnot when its meaning is recorded -- that meaning is "
          "the reader's.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
