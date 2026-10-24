"""Node structures with slots, derived from the phrase tree.

2026-09-15, after a day of chips that were trait labels: the early patterns
were all node structures with slots.

That is the object this project has always meant by a pattern, and
`out/patterns.jsonl.gz` has held 12,494 of them since August -- `[S] said to
[X]`, a template whose slots instances fill. What got built earlier today
instead was a **bag of labels**: `image_of_god + temple_presence`. A label has
no slots, so nothing fills it and nothing can be compared, which is why
clicking one produced a list of verse references, and the verdict was that
they are less interesting when all you see is a list of verse references, and
that the pattern is not conceptually there.

This is the same object one level up, over the word-group tree extracted in
`tools/phrases.py`. A node's SHAPE is the sequence of its children's classes;
its SLOTS are what those children actually contain.

## Ranking: constrained slots, not frequency

Frequency finds grammar. The commonest shapes in the corpus are `np [det
noun]` (5,950), `pp [prep np]` (3,247) and `[conj cl]` (7,354), each with
1,500 different fillers per slot -- maximum frequency, maximum variety, no
information. That is exactly the complaint about the Explore view: the
patterns there are on the simple extreme.

**A template is interesting when its slots are CONSTRAINED.** Skew -- how much
the commonest filler dominates its slot -- separates a formula from grammar,
and it inverts the frequency ranking:

    cl [pron s pp]        χάρις ὑμῖν ἀπὸ          the Pauline greeting, 9 books
    advp [pron adv]       πόσῳ μᾶλλον             "how much more"
    cl [ptcl cl o]        Ἀμὴν λέγω ὑμῖν ὅτι      "truly I say to you that"
    cl [cl np verb pron o] ἀποκριθεὶς ὁ Ἰησοῦς εἶπεν αὐτοῖς

The second is worth dwelling on. `a_fortiori` was a stamp -- a model asserting
that a passage argues from lesser to greater, unshowable and uncheckable. Here
it is **derived**: a two-slot template, both slots filled the same way every
time, in five books. Same idea, different epistemic standing.

    python tools/nodepat.py --top 20
    python tools/nodepat.py --min-books 3 --write
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
SRC = OUT / "phrases.jsonl.gz"


def shape_of(node):
    """The part that does NOT vary: the classes of a node's children."""
    return "[" + " ".join((k.get("cls") or k.get("role") or "?")
                          for k in node["kids"]) + "]"


def filler(kid):
    """What a slot actually holds, in the original."""
    if "kids" in kid:
        return " ".join(x.get("t") or "" for x in kid["kids"] if x.get("t"))
    return kid.get("t") or ""


def scan(limit=0, lo=2, hi=5):
    """-> (count, books, per-slot filler counts, refs, examples) per shape.

    `examples` is new, and it exists because the reader was showing phrases the
    text does not contain. 2026-09-16, on a row titled "Having seen that
    he had been outwitted": drilling in showed no such phrase and no reason for
    being there.

    The list built that title from the commonest filler of each slot
    INDEPENDENTLY -- ἰδὼν from 3 instances, ὅτι from 33, ἐνεπαίχθη from 1 --
    and those three never occur together. It is an assembly, and at 28%
    constrained it is an assembly of fillers that mostly do not co-occur, so
    the phrase it advertises may exist nowhere.

    A real instance costs almost nothing to keep and is the only honest title:
    a few whole fillings, each with the verse it came from, so the row says
    something the reader can go and check.
    """
    n = collections.Counter()
    books = collections.defaultdict(set)
    slots = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    refs = collections.defaultdict(list)
    examples = collections.defaultdict(list)

    def walk(node, ref):
        if "kids" not in node:
            return
        if lo <= len(node["kids"]) <= hi:
            s = (node.get("cls") or "?") + " " + shape_of(node)
            n[s] += 1
            books[s].add(ref.split(".")[0])
            if len(refs[s]) < 500:
                refs[s].append(ref)
            whole = []
            for i, k in enumerate(node["kids"]):
                f = filler(k).strip()
                whole.append(f[:40])
                if f:
                    slots[s][i][f[:40]] += 1
            # One ACTUAL filling of this shape, kept with its verse. A nested
            # child can yield an empty string, and requiring every position to
            # be filled threw away every example for shapes like
            # `np [np noun cj noun]`, so a gap is recorded as a gap.
            if len(examples[s]) < 6 and any(whole):
                examples[s].append({"ref": ref,
                                    "fills": [w or "…" for w in whole]})
        for k in node["kids"]:
            walk(k, ref)

    seen = 0
    for line in gzip.open(SRC, "rt", encoding="utf-8"):
        if line.startswith('{"_'):
            continue
        d = json.loads(line)
        seen += 1
        for tr in d.get("trees") or []:
            walk(tr, d["ref"])
        if limit and seen >= limit:
            break
    return seen, n, books, slots, refs, examples


def skew(slot_counts):
    """How much the commonest filler dominates. 1.0 = the same word every time.

    This is what separates a FORMULA from grammar. `np [det noun]` occurs 5,950
    times with 1,498 different nouns -- common and empty. `advp [pron adv]`
    occurs 9 times and is "how much more" every time.
    """
    if not slot_counts:
        return 0.0
    per = [max(c.values()) / sum(c.values()) for c in slot_counts.values()]
    return sum(per) / len(per)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=0, help="verses to scan")
    ap.add_argument("--min-instances", type=int, default=8)
    ap.add_argument("--min-books", type=int, default=2)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    if not SRC.exists():
        raise SystemExit("run: python tools/phrases.py --write")
    seen, n, books, slots, refs, examples = scan(a.limit)
    print(f"{seen:,} verses, {len(n):,} distinct node shapes", flush=True)

    ranked = []
    for s, c in n.items():
        if c < a.min_instances or len(books[s]) < a.min_books:
            continue
        sk = skew(slots[s])
        ranked.append((sk, c, len(books[s]), s))
    # constrained first; a formula outranks grammar however common grammar is
    ranked.sort(key=lambda x: (-x[0], -x[2], -x[1]))
    print(f"{len(ranked):,} pass ({a.min_instances}+ instances, "
          f"{a.min_books}+ books)\n")

    for sk, c, nb, s in ranked[:a.top]:
        print(f"  skew {sk:.2f}  {c:>5}x  {nb:>2} books   {s}")
        for i in sorted(slots[s]):
            tot = sum(slots[s][i].values())
            top = slots[s][i].most_common(2)
            print("      slot %d: %s" % (i, ", ".join(
                f"{w} ({k}/{tot})" for w, k in top))[:96])
        print(f"      e.g. {', '.join(refs[s][:4])}")
        print()

    if not a.write:
        print("nothing written -- pass --write")
        return 0

    p = OUT / "nodepat.jsonl.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., "
                       "CC BY 4.0",
            "_note": "Node structures with slots, from out/phrases.jsonl.gz. "
                     "`shape` is what does not vary; `slots` is what does. "
                     "Ranked by how CONSTRAINED the slots are, because "
                     "frequency finds grammar -- see the module docstring."})
                + "\n")
        for sk, c, nb, s in ranked:
            f.write(json.dumps({
                "shape": s, "instances": c, "books": sorted(books[s]),
                "skew": round(sk, 3),
                "slots": {str(i): slots[s][i].most_common(6)
                          for i in sorted(slots[s])},
                "refs": refs[s][:200],
                # Whole fillings with their verses, so a reader can be shown a
                # phrase that actually occurs rather than one assembled slot by
                # slot from fillers that never co-occur.
                "examples": examples[s]}, ensure_ascii=False) + "\n")
    print(f"  -> {p.relative_to(ROOT)}  {len(ranked):,} templates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
