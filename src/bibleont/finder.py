"""Finding candidates without a model.

The first stage of the work described in `docs/WORKERS.md`. It searches the
corpus for pairs of verses that share a phrase rare enough to be worth a
second look, and hands them on as candidates for something else to judge.

Nothing here makes a decision. That is the point: search is not judgement, and
paying a model to do string matching is both expensive and less reliable than
doing it exactly.

## What it looks for

A run of words appearing in only two or three places in the whole corpus,
where those places are in at least two different books. That is a narrow net
by design.

Common phrasing -- "and it came to pass", "saith the Lord" -- fails the count
test immediately, since it appears hundreds of times. What survives is the
kind of thing that turned out to matter when found by hand: "being fruitful in
every good work" (Col 1:10) is the only place the corpus puts fruit and works
in one phrase, and it joins two vocabularies that Galatians and Ephesians keep
apart.

## Longest wins

If two verses share eight words they also share five overlapping runs of four,
and reporting all of them is noise. Each verse pair is claimed once, by the
longest phrase it shares, because the search runs from long phrases to short
ones and a claimed pair is not revisited.

## Ranking

By rarity of the words involved, not by length. A long phrase of common words
is a formula; a short phrase containing a word used twice in the corpus is a
thread. The score is the summed inverse frequency of the phrase's words, so a
rare word contributes far more than a long run of ordinary ones.

## What is dropped before a human sees it

Pairs the graph already joins, in either direction and at any distance of one
hop. There is no value in proposing a connection that is already drawn, and it
is the largest single source of noise once the graph is dense.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path

from bibleont.paths import ROOT, DATA

MIN_WORDS = 4
MAX_WORDS = 12
MAX_OCCURRENCES = 3

_WORD = re.compile(r"[a-z']+")

# Number words, for detecting formulas. The corpus repeats whole templates
# with only the quantities changing -- "X years old when he began to reign,
# and he reigned Y years", the roster counts of Ezra 2 against Nehemiah 7 --
# and the varying numbers make each instance rare while the sentence itself is
# boilerplate. Masking them exposes the skeleton, which can then be counted.
_NUMBERS = frozenset("""
one two three four five six seven eight nine ten eleven twelve thirteen
fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty
fifty sixty seventy eighty ninety hundred thousand score fourscore threescore
twoscore first second third fourth fifth sixth seventh eighth ninth tenth
eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth
eighteenth nineteenth twentieth thirtieth fortieth fiftieth hundredth
""".split())


def _skeleton(gram: tuple[str, ...]) -> tuple[str, ...]:
    return tuple("#" if w in _NUMBERS else w for w in gram)


def _words(text: str) -> list[str]:
    # The ligature fold matters: the ASV writes "Æneas" and a raw split loses
    # the word entirely. Harmless on the KJV and needed the moment another
    # translation is searched.
    text = text.lower().replace("æ", "ae").replace("œ", "oe")
    return _WORD.findall(text)


@dataclass
class Candidate:
    phrase: str
    a: str
    b: str
    a_text: str
    b_text: str
    occurrences: int
    books: int
    score: float
    # How many of the four neighbouring verse pairs also share a phrase. Zero
    # means the echo stands alone; four means the two passages are running in
    # parallel and the phrase is incidental to that.
    neighbours: int = 0

    def brief(self) -> str:
        return (f'{self.score:7.1f}  "{self.phrase}"\n'
                f'          {self.a:12} {self.a_text}\n'
                f'          {self.b:12} {self.b_text}')


# ---------------------------------------------------------------------------

def load_verses(translation: str = "kjv") -> list[tuple[str, str, str]]:
    """(ref, book, text) for every verse, header line skipped."""
    name = "verses.jsonl" if translation == "kjv" else f"verses.{translation}.jsonl"
    out = []
    for line in (DATA / "bible" / name).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "t" not in r:
            continue
        out.append((f'{r["b"]} {r["c"]}:{r["v"]}', r["b"], r["t"]))
    return out


def _already_joined() -> set[frozenset[str]]:
    """Verse-pairs the graph already brings together on one record.

    A relation or an entity citing both verses means the connection is drawn.
    Cheap to compute and it removes most of what would otherwise be proposed
    back to us.
    """
    joined: set[frozenset[str]] = set()

    def note(refs):
        refs = [str(x) for x in refs]
        for i, x in enumerate(refs):
            for y in refs[i + 1:]:
                if x != y:
                    joined.add(frozenset((x, y)))

    ents = ROOT / "ontology" / "entities" / "entities.jsonl"
    if ents.exists():
        for line in ents.read_text(encoding="utf-8").splitlines():
            if line.strip():
                note(json.loads(line).get("refs", []))
    reldir = ROOT / "ontology" / "relations"
    if reldir.exists():
        for p in reldir.glob("*.jsonl"):
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    note(json.loads(line).get("refs", []))
    return joined


def find(translation: str = "kjv", limit: int = 0) -> list[Candidate]:
    verses = load_verses(translation)
    tokens = [(_words(t), ref, book, t) for ref, book, t in verses]

    freq: Counter[str] = Counter()
    for ws, _, _, _ in tokens:
        freq.update(ws)
    total = sum(freq.values())

    def rarity(w: str) -> float:
        return math.log(total / (1 + freq[w]))

    joined = _already_joined()
    claimed: set[frozenset[str]] = set()
    out: list[Candidate] = []

    # Long phrases first, so each pair is claimed by the longest run it shares
    # and its own sub-phrases never appear again.
    for n in range(MAX_WORDS, MIN_WORDS - 1, -1):
        index: dict[tuple[str, ...], list[int]] = defaultdict(list)
        for i, (ws, _, _, _) in enumerate(tokens):
            for j in range(len(ws) - n + 1):
                index[tuple(ws[j:j + n])].append(i)

        # A phrase is only rare if its skeleton is. Counted per pass, so the
        # comparison is always against grams of the same length.
        skel: Counter[tuple[str, ...]] = Counter()
        for gram, where in index.items():
            skel[_skeleton(gram)] += len(set(where))

        for gram, where in index.items():
            hits = sorted(set(where))
            if not 2 <= len(hits) <= MAX_OCCURRENCES:
                continue
            # Boilerplate with the quantities swapped out: the instance is
            # rare, the sentence is not.
            if any(w in _NUMBERS for w in gram) and skel[_skeleton(gram)] > MAX_OCCURRENCES:
                continue
            books = {tokens[i][2] for i in hits}
            if len(books) < 2:
                continue
            # Report the pair that spans the most distant books; with three
            # occurrences that is a choice, and the first and last in corpus
            # order is the least arbitrary one available.
            a_i, b_i = hits[0], hits[-1]
            if tokens[a_i][2] == tokens[b_i][2]:
                continue
            pair = frozenset((tokens[a_i][1], tokens[b_i][1]))
            if pair in claimed or pair in joined:
                continue
            claimed.add(pair)
            out.append(Candidate(
                phrase=" ".join(gram),
                a=tokens[a_i][1], b=tokens[b_i][1],
                a_text=tokens[a_i][3][:150], b_text=tokens[b_i][3][:150],
                occurrences=len(hits), books=len(books),
                score=round(sum(rarity(w) for w in gram), 1),
                neighbours=_neighbours(tokens, a_i, b_i),
            ))

    # Rank by rarity, but only among echoes that stand alone. A phrase whose
    # neighbours also match is a parallel passage -- Kings against Chronicles,
    # Ezra against Nehemiah, one Synoptic against another -- and those
    # dominate a rarity ranking completely, because retelling a reign shares
    # far more rare wording than any conceptual echo ever will.
    #
    # They are worth having and they are a different question. Kept, sorted
    # below, and separable by a caller.
    out.sort(key=lambda c: (c.neighbours, -c.score))
    return out[:limit] if limit else out


def _shares_phrase(tokens, i: int, j: int, n: int = 4) -> bool:
    if not (0 <= i < len(tokens) and 0 <= j < len(tokens)):
        return False
    a, b = tokens[i][0], tokens[j][0]
    if len(a) < n or len(b) < n:
        return False
    grams = {tuple(a[k:k + n]) for k in range(len(a) - n + 1)}
    return any(tuple(b[k:k + n]) in grams for k in range(len(b) - n + 1))


def _neighbours(tokens, a_i: int, b_i: int) -> int:
    """How many of the surrounding verse pairs also share wording.

    Checked at the same offset on both sides, so it detects two passages
    running together rather than two verses that merely sit near matches.
    """
    return sum(_shares_phrase(tokens, a_i + d, b_i + d) for d in (-2, -1, 1, 2))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    tr = "kjv"
    for a in argv:
        if a.startswith("--translation="):
            tr = a.split("=", 1)[1]
    top = 25
    for a in argv:
        if a.startswith("--top="):
            top = int(a.split("=", 1)[1])

    cands = find(tr)
    out_path = None
    for a in argv:
        if a.startswith("--out="):
            out_path = Path(a.split("=", 1)[1])

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            "".join(json.dumps(asdict(c), ensure_ascii=False) + "\n" for c in cands),
            encoding="utf-8")
        print(f"{len(cands)} candidates -> {out_path}")
        return 0

    for c in cands[:top]:
        print(c.brief())
        print()
    print(f"{len(cands)} candidate pairs in {tr.upper()}; "
          f"phrases of {MIN_WORDS}-{MAX_WORDS} words appearing "
          f"{MAX_OCCURRENCES} times or fewer, in two or more books, "
          f"not already joined by the graph.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
