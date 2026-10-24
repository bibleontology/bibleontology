"""The words a book runs on, before anything tries to decompose it.

Proverbs 26 is about fools. The word is in a dozen of its verses, and the
graph had no node for it -- so the worker wrote twenty-six relations pointing
at `fool`, every one refused, an entire chapter's work discarded. Proverbs 10
did the same with `understanding`, `mouth`, `life` and `reproof`.

The prompt was told to declare what it references. It did not hold, and a
second prompt rule would not have held either, because the model is asked to
mint a concept and use it in the same breath and it writes the relation first.

**The fix is to stop asking.** The words a book leans on are knowable before
any of it is read: the tagged text says which lemmas carry it, the graph says
which of those it already holds, and the difference is the gap. Fill the gap
first and no window has to invent anything.

## Why this shrinks rather than handles the problem

Nothing persists between calls -- each window is answered by a model with no
memory of the last one. The one thing that does carry is the run's delta
block, which lists what earlier windows created. So dangling references are
**front-loaded**: the first windows have the least vocabulary and produce the
most, and the rate falls as the delta fills.

Seeding is that delta, computed instead of accumulated, and available to window
one.

## What it will not do

Invent a definition. A seeded node carries the word, its lemma, and the verses
in this book where it occurs -- which is a citation, not a claim. Anything
about what the word *means* is left for a reader, or for the decomposer when it
meets the verse.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter

from .paths import ROOT
from .lemma import BOOKS, forms, load, testament

PROPOSALS = ROOT / "ontology" / "proposals"

# A lemma has to carry this share of a book's verses to count as one of its
# working words. Below it, the word is incidental to the book and a node for
# it should come from reading a verse rather than from counting.
SHARE = 0.012

# A gloss that begins with a pronoun is an inflected verb, not a dictionary
# word: STEPBible gives the commonest surface form, so H0559 comes back as
# "he said" and H8130 as "i hate". Real vocabulary for a node is the thing,
# not one conjugation of it.
_INFLECTED = re.compile(
    '^(he|she|it|they|we|i|you|thou|ye|there|may|let|shall|will|'
    'did|do|does|has|have|had|not|no)[ ]'
)

# Glosses that are grammar rather than vocabulary.
_JUNK = re.compile(r"^(the|a|an|of|and|to|in|is|was|are|were|be|he|she|it|"
                   r"they|you|i|we|his|her|its|their|your|my|our|that|this|"
                   r"which|who|what|not|no|so|then|there|here|will|shall|with|also|"
                   r"upon|unto|before|after|more|very|every|any|much|as|"
                   r"but|or|if|when|now|thus|yet|even|from|by|on|at)$")


# Numerals and counting words. Genesis leans on them heavily -- "seven",
# "two", "hundred", "years" -- because it counts generations, and none of them
# is a concept the graph wants a node for.
_NUMERIC = re.compile(r"^(one|two|three|four|five|six|seven|eight|nine|ten|"
                      r"eleven|twelve|twenty|thirty|forty|fifty|sixty|seventy|"
                      r"eighty|ninety|hundred|thousand|first|second|third|"
                      r"year|years|day|days|time|times|number)s?( s)?$")

# Discourse particles that survive the junk list because they are not single
# function words: "please" is a real gloss of an entreaty particle.
_PARTICLE = re.compile(r"^(these|those|please|behold|now|lo|surely|indeed|"
                       r"also|again|here|thus)$")


def _base(code: str) -> str:
    """H3068G -> H3068. The suffix is STEPBible's homograph disambiguator."""
    return re.sub(r"[A-Za-z]$", "", code) if re.match(r"^[HG]\d+[A-Za-z]$",
                                                      code) else code


def _clean(gloss: str) -> str:
    """A node name from STEPBible's gloss, or "" if it is not usable."""
    g = gloss.strip().lower()
    g = re.sub(r"[\[\]<>{}()]", " ", g)
    g = re.sub(r"^(the|a|an|to|of|and|in|for|is|was)\s+", "", g)
    g = re.sub(r"\s+(of|to|for|in|with|from)$", "", g)
    g = re.sub(r"[^a-z' ]+", " ", g)
    g = " ".join(g.split())
    if not g or len(g) > 28 or _JUNK.match(g) or _INFLECTED.match(g) or g in ('him','her','them','me','us') or _NUMERIC.match(g) or _PARTICLE.match(g):
        return ""
    return g


def gaps(book: str, limit: int = 40) -> list[dict]:
    """Words this book runs on that the graph has no node for."""
    from .schema import load_entities

    ix = load()
    verses, freq = ix["verses"], ix["freq"]
    total_verses = len(verses)
    refs = [r for r in verses if r.rsplit(" ", 1)[0] == book]
    if not refs:
        return []

    here = Counter()
    for r in refs:
        for root in {x[1] for x in verses[r]}:
            here[root] += 1

    ents = load_entities()
    # Match on the BASE code. STEPBible disambiguates homographs with a
    # trailing letter that varies by context -- Proverbs uses H3068G where our
    # yahweh node says H3068 -- so comparing the full code proposes a node for
    # something the graph already holds.
    taken_lemmas = {_base(c) for e in ents.values()
                    for c in (e.attrs or {}).get("lemma", "").split("+") if c}
    taken_names = {n.lower() for e in ents.values() for n in e.names()}

    tbl = forms()
    out = []
    seen_base, seen_names = set(), set()

    # Rank by how much a word BELONGS to this book, not by how often it
    # appears in it. Raw frequency puts `day` and `hand` above `sluggard`,
    # which occurs almost nowhere else in the canon and is exactly the kind of
    # word a worker on Proverbs will reach for and not find. Book share
    # against corpus share -- the same inverse-frequency idea the lemma
    # resolver uses, which should have been applied here from the start.
    import math as _math
    ranked = sorted(
        here.items(),
        key=lambda kv: -(kv[1] / len(refs))
        * _math.log(total_verses / max(freq.get(kv[0], 1), 1)))

    for root, n in ranked:
        if n < len(refs) * SHARE:
            continue
        if _base(root) in taken_lemmas:
            continue
        # Function words carry every book and mean nothing about any of them.
        if freq.get(root, 0) > total_verses * 0.12:
            continue
        form, gloss = tbl.get(root, ["", ""])
        name = _clean(gloss)
        if not name or name in taken_names:
            continue
        where = sorted((r for r in refs if any(x[1] == root for x in verses[r])),
                       key=lambda r: (int(r.rsplit(" ", 1)[1].split(":")[0]),
                                      int(r.rsplit(":", 1)[1])))
        # One base lemma, one node. H7451B and H7451H are both "evil" and
        # would mint two records with the same name -- the very duplication
        # this whole layer exists to prevent.
        if _base(root) in seen_base or name in seen_names:
            continue
        seen_base.add(_base(root)); seen_names.add(name)
        out.append({"lemma": root, "name": name, "word": form,
                    "verses": n, "refs": where[:6]})
        if len(out) >= limit:
            break
    return out


def batch(book: str, limit: int = 40) -> tuple[str, int]:
    """Write the gaps as a proposal batch for the gate to judge."""
    import json as _json

    rows = gaps(book, limit)
    if not rows:
        return "", 0

    kjv = {}
    from .paths import text_path
    with open(text_path(), encoding="utf-8") as fh:
        for line in fh:
            r = _json.loads(line)
            if "b" in r:
                kjv[f"{r['b']} {r['c']}:{r['v']}"] = r["t"]

    name = f"{book.lower()}-vocabulary"
    d = PROPOSALS / name
    d.mkdir(parents=True, exist_ok=True)
    ents = []
    for g in rows:
        first = g["refs"][0]
        ents.append({
            "id": g["name"].replace("'", "").replace(" ", "_"),
            "name": g["name"],
            "type": "concept",
            "gender": "unknown",
            "refs": g["refs"],
            "source": name,
            "attrs": {"lemma": g["lemma"], "lemma_word": g["word"],
                      "lemma_source": "STEPBible TAHOT/TAGNT, CC BY 4.0, "
                                      "www.STEPBible.org"},
            "desc": f"'{kjv.get(first, '').strip()}' ({first}).\n\n"
                    f"{g['lemma']} carries {g['verses']} verses of {book}. "
                    f"Seeded from the book's own vocabulary before extraction, "
                    f"so that a worker meeting the word has somewhere to put "
                    f"it. Nothing is claimed here about what it means.",
        })

    with open(d / "entities.jsonl", "w", encoding="utf-8", newline="") as fh:
        for e in ents:
            fh.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")
    (d / "relations.jsonl").write_text("", encoding="utf-8", newline="")
    (d / "META.json").write_text(json.dumps({
        "producer": "bibleont.seed", "book": book,
        "note": "vocabulary the book runs on that the graph did not hold",
    }, indent=2), encoding="utf-8", newline="")
    return name, len(ents)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    write = "--write" in argv
    rest = [a for a in argv if not a.startswith("--")]
    if not rest:
        print("usage: python -m bibleont.seed <Book> [--write]")
        return 2
    book = rest[0]
    if write:
        name, n = batch(book)
        print(f"  {n} concepts -> ontology/proposals/{name}"
              if n else "  nothing missing")
        if n:
            print(f"  next: python -m bibleont.proposals check {name}")
        return 0
    rows = gaps(book)
    print(f"  {len(rows)} words {book} runs on that the graph has no node for:")
    print(f"  {'lemma':10}{'verses':>7}   name")
    for g in rows:
        print(f"  {g['lemma']:10}{g['verses']:>7}   {g['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
