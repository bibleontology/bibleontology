"""Extend an existing pattern to the units it already had, book-wide.

The problem this fixes, measured 2026-09-06: **130 of 132 patterns cannot leave
their chapter.** Patterns were minted inside chapter-scoped extraction windows,
so a pattern could only ever see the instances in the window that made it. The
toledot node was minted in the Gen 25 window and never saw the nine other
"these are the generations of" headings in Genesis -- *even though the grouper
had already built passage units for ten of the eleven*.

So this is not detection. **The units exist and the formula is already named;
only the `instance_of` edge is missing.** That makes the whole job deterministic
and free -- no model is called, and no node is ever minted.

## How the formula is derived, and why it is not invented

A pattern's formula comes from **the pattern's own confirmed members**: the
longest word n-gram every member's text shares. Nothing is guessed and nothing
is hand-written, so a pattern the workers never made cannot appear here.

The naive version of that fails, and it fails loudly enough to be worth keeping
in the code. Two members of "Jacob's fear that mischief will befall Benjamin"
share only `and he said`, which matches 89 verses of Genesis; a scan on it
returns half the book. Three gates stop that:

1. **Self-validation against the node's own words.** Among the shared n-grams,
   prefer one whose words appear in the pattern's *name or description*. This is
   what separates "Blessing to be fruitful" (whose members are days five and six,
   so they share the day refrain incidentally) from the day-refrain pattern
   itself. The node already says what it is about; believe it.
2. **Length**, at least MIN_WORDS -- `and he said` is not a form.
3. **Rarity**, at most MAX_SHARE of the book's verses. A formula that matches 4%
   of Genesis is connective tissue, not a shape. Note this is a *ceiling on the
   phrase*, never a ceiling on the pattern: Genesis 5's genealogy legitimately
   has ten members and passes easily.

## And position, which is the gate that does the real work

A formula sits somewhere in its unit. `these are the generations of` opens the
block; `and there was evening, and there was morning` closes it. Where it sits is
read off the confirmed members and required of every candidate, so a heading
formula can never pick up a unit that merely mentions the words halfway through.

## What it will not do

- mint a passage, a pattern, or any other node
- link a unit whose start verse an existing member already covers
- touch a pattern whose members are `text` nodes rather than units -- those are
  the 14 leftovers of the superseded `-farm-` runs, and extending them would
  spread the older shape rather than retire it
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_REL = ROOT / "ontology" / "relations" / "formulae-extended.jsonl"

MIN_WORDS = 4        # `and he said` is not a form
MAX_SHARE = 0.01     # a phrase in >1% of a book's verses is connective tissue
MIN_MEMBERS = 2      # a formula needs two witnesses to be derived at all

# Vouching has to run on contentful words only. Measured: with `and` allowed to
# vouch, "Blessing to be fruitful" -- whose description says *"Be fruitful, and
# multiply"* -- was vouched for the eight-word day refrain by the `and`, and the
# refrain won on length. Every day of creation was then proposed as an instance
# of the blessing. Function words vouch for everything, which is to say nothing.
STOP = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at", "by",
    "for", "with", "from", "as", "that", "this", "these", "those", "it", "its",
    "is", "was", "were", "be", "been", "are", "am", "he", "she", "they", "them",
    "his", "her", "their", "him", "i", "we", "us", "you", "ye", "thy", "thee",
    "thou", "shall", "will", "not", "unto", "into", "upon", "which", "who",
    "all", "any", "so", "then", "when", "there", "here", "one", "up", "out",
}

REF = re.compile(r"^(\S+)\s+(\d+):(\d+)$")


def words(s: str) -> list[str]:
    return re.findall(r"[a-z]+", s.lower())


def load():
    verses = {}
    for line in (ROOT / "data" / "bible" / "verses.jsonl").read_text(
            encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if "b" in d:
            verses[(d["b"], d["c"], d["v"])] = d["t"]

    ents = {}
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            ents[e["id"]] = e

    rels = []
    for f in sorted(glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            if line.strip():
                rels.append(json.loads(line))
    return verses, ents, rels


def verses_of(e: dict) -> list[tuple]:
    """Every verse a node's refs touch. Two refs in one chapter is a span."""
    pts = []
    for x in e.get("refs", []):
        m = REF.match(str(x).strip())
        if m:
            pts.append((m.group(1), int(m.group(2)), int(m.group(3))))
    if len(pts) == 2 and pts[0][:2] == pts[1][:2] and pts[0][2] <= pts[1][2]:
        b, c = pts[0][:2]
        return [(b, c, v) for v in range(pts[0][2], pts[1][2] + 1)]
    return sorted(set(pts))


def shared_ngrams(texts: list[str], lo: int, hi: int = 14) -> set[tuple]:
    """Every word n-gram present in all of them."""
    common = None
    for t in texts:
        w = words(t)
        g = {tuple(w[i:i + n]) for n in range(lo, hi + 1)
             for i in range(len(w) - n + 1)}
        common = g if common is None else (common & g)
        if not common:
            return set()
    return common or set()


def pick_formula(cands: set[tuple], node_words: set[str]) -> tuple | None:
    """Longest n-gram, preferring ones the node's own name/desc vouches for.

    The preference is the gate that matters. "Blessing to be fruitful" holds days
    five and six, so its members share the day refrain -- but the node says
    *fruitful*, and only one candidate contains that word.
    """
    if not cands:
        return None
    vouched = [g for g in cands if (node_words & set(g)) - STOP]
    return max(vouched or list(cands), key=lambda g: (len(g), g))


# A KJV heading is routinely introduced by a narrative connective -- *"NOW these
# are the generations of Ishmael"*, *"AND these are the generations of Isaac"* --
# so these are stepped over before asking whether the formula heads the verse.
# Without that the toledot pattern matches nothing at all.
OPENERS = {"and", "now", "so", "then", "but", "also", "moreover", "therefore"}


def _heads(formula: str, verse: str) -> bool:
    """Does the formula begin the verse, once a leading connective is stepped over?"""
    w = words(verse)
    i = 0
    while i < len(w) and w[i] in OPENERS:
        i += 1
    return " ".join(w[i:]).startswith(formula)


def position_of(formula: str, unit: list[tuple], verses: dict) -> str | None:
    """Does the formula open the unit, close it, or sit inside it?

    "Opens" is strict: the formula must begin the unit's first verse, not merely
    appear somewhere in it. Measured -- without that, *"the people of the land"*
    linked Joseph accusing his brothers of spying (Gen 42:6) to Abraham bowing at
    Machpelah, because the phrase occurs mid-verse in both. A heading formula
    heads its verse; that is what makes it a heading.
    """
    if not unit:
        return None
    hits = [i for i, k in enumerate(unit)
            if formula in " ".join(words(verses.get(k, "")))]
    if not hits:
        return None
    if hits[0] == 0 and _heads(formula, verses.get(unit[0], "")):
        return "opens"
    if hits[-1] == len(unit) - 1:
        return "closes"
    return "inside"


def analyse(verses, ents, rels):
    inst = collections.defaultdict(list)
    for r in rels:
        if r["type"] == "instance_of":
            inst[r["dst"]].append(r["src"])

    # every verse of the book, once, lowercased for scanning
    book_text = collections.defaultdict(dict)
    for (b, c, v), t in verses.items():
        book_text[b][(c, v)] = " ".join(words(t))

    # existing units, indexed by the verse they start at
    units_by_start = collections.defaultdict(dict)
    unit_span = {}
    for k, e in ents.items():
        if e.get("type") != "passage":
            continue
        vs = verses_of(e)
        if not vs:
            continue
        unit_span[k] = vs
        units_by_start[vs[0][0]].setdefault(vs[0][1:], []).append(k)

    out = []
    for pid, p in ents.items():
        if p.get("type") != "pattern":
            continue
        members = inst.get(pid, [])
        units = [(m, verses_of(ents[m])) for m in members if m in ents]
        # only units. `text`-membered patterns are the superseded runs.
        units = [(m, vs) for m, vs in units
                 if ents[m].get("type") == "passage" and vs]
        if len(units) < MIN_MEMBERS:
            continue
        book = units[0][1][0][0]
        if any(vs[0][0] != book for _, vs in units):
            continue

        texts = [" ".join(verses.get(k, "") for k in vs) for _, vs in units]
        node_words = set(words(f"{p.get('name','')} {p.get('desc','')}"))
        g = pick_formula(shared_ngrams(texts, MIN_WORDS), node_words)
        if not g:
            continue
        formula = " ".join(g)

        share = sum(1 for t in book_text[book].values() if formula in t) \
            / max(1, len(book_text[book]))
        if share > MAX_SHARE:
            continue

        # where the formula sits, agreed by every confirmed member
        places = {position_of(formula, vs, verses) for _, vs in units}
        places.discard(None)
        if len(places) != 1:
            continue
        place = places.pop()
        # A formula that neither opens nor closes its unit is not a structural
        # marker at this gate strength -- it is a phrase that happens to occur.
        # Measured: `inside` produced 11 of 25 proposals and every one was
        # wrong, e.g. "in the land of canaan and" matching Lot's choice of the
        # plain. The known cost of dropping it is the Matthew 6 piety triad,
        # whose marker *"they have their reward"* sits mid-member by design --
        # so this is a bound to revisit when Matthew is extracted, not a claim
        # that interior formulae do not exist.
        if place == "inside":
            continue

        # A pattern's instances must not overlap each other -- the same rule the
        # passage tree keeps for siblings. Genesis 1 holds three units over day
        # six (1:24-25, 1:24-31, 1:26-31); the pattern already has 1:24-31, and
        # without this the refrain would also pick up 1:26-31 and give the
        # pattern seven members for six days.
        covered = {k for _, vs in units for k in vs}
        found = []
        for _, ids in sorted(units_by_start[book].items()):
            for uid in ids:
                vs = unit_span[uid]
                if set(vs) & covered:
                    continue
                if position_of(formula, vs, verses) == place:
                    found.append(uid)
                    covered |= set(vs)
                    break
        if found:
            out.append(dict(pid=pid, name=p["name"], book=book, formula=formula,
                            place=place, have=len(units), add=sorted(found),
                            share=share))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="write the edges (default is a dry run)")
    ap.add_argument("--pattern", help="restrict to one pattern id")
    a = ap.parse_args()

    verses, ents, rels = load()
    res = analyse(verses, ents, rels)
    if a.pattern:
        res = [r for r in res if r["pid"] == a.pattern]

    total = sum(len(r["add"]) for r in res)
    print(f"patterns extended   {len(res)}")
    print(f"edges proposed      {total}")
    print(f"nodes minted        0        model calls 0\n")
    for r in sorted(res, key=lambda r: -len(r["add"])):
        print(f'+{len(r["add"]):3} (has {r["have"]:2})  {r["name"][:44]:46} '
              f'{r["place"]:7} "{r["formula"][:46]}"')
        for uid in r["add"]:
            e = ents[uid]
            print(f'          {str(e.get("refs"))[:26]:28} {e["name"][:46]}')

    if not a.apply:
        print("\ndry run -- pass --apply to write")
        return 0

    lines = []
    for r in res:
        for uid in r["add"]:
            lines.append(json.dumps({
                "src": uid, "dst": r["pid"], "type": "instance_of",
                "certainty": "explicit",
                "refs": ents[uid].get("refs", []),
                "note": f'The formula "{r["formula"]}" {r["place"]} this unit, '
                        f'as it does in the {r["have"]} units already recorded.',
                "source": "formulae-extended",
            }, ensure_ascii=False))
    OUT_REL.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {len(lines)} edges to {OUT_REL.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
