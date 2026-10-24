"""The corpus's central themes, ranked by how much of it they carry.

2026-09-15, correcting a bias that had been running through every ranking
tool in this project: stamps that represent patterns, many of them thematic,
may not need much corroboration, and co-occurrence may be a good signal
rather than a negative; the primary themes are not to be ignored in search of
the outlier.

That is a real correction and it inverts the scoring in `crosslink.py`
(rarity), `nodepat.py` (skew), and `patterns.py` (rarity / surprise /
avoidance). Every one of them was built to surface what is UNUSUAL, which is
the right question for a pattern nobody has noticed and the wrong question for
a theme everybody has. Hours earlier in the same session `people_of_god` at
2,198 of 3,078 sections was called "too broad to find anything" -- but a trait
carried by 71% of the corpus is not a failed discriminator. **It is the corpus
saying what it is about.**

The two questions need opposite scores and this tool asks the second one:

    crosslink.py    what is rare here, and where else is it rare?   OUTLIER
    themespine.py   what is everywhere, and what travels with it?   SPINE

## Co-occurrence read forwards

Lift asks whether two traits appear together MORE than chance, so it
systematically demotes exactly the pairs that define a corpus: `covenant` with
`people_of_god` is the Old Testament's central claim and scores near 1.0
precisely because both are everywhere. Raw co-occurrence keeps it.

So pairs are reported by how much of the corpus holds BOTH, with lift shown
beside it rather than used as the filter -- a reader can see that a pair is
expected and still care that it is the largest thing in the book.

## Corroboration, not derivation

`tools/declaredthemes.py` harvests the places the text summarises itself --
Rom 13:9's "summed up in this word", Heb 8:1's "the main point", Matt 22:40's
"on these two hang all the Law and the Prophets". Those are not a better
register; at 44% precision they are a weaker signal than the stamps. What they
are good for is a CHECK: if the sections holding the text's own summaries carry
the stamps' top themes, the ranking is corroborated by the text rather than
only by itself.

    python tools/themespine.py
    python tools/themespine.py --pairs 30
    python tools/themespine.py --check     # against the declared summaries
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
SRC = OUT / "stamps-leveled.jsonl"

# The lane that answers "what is this passage about". The others answer what
# kind of thing it is (devices), who is in it (character_roles), or what
# happens (event_images) -- all useful, none of them a theme.
LANE = "themes"

NT = {"Matt", "Mark", "Luke", "John", "Acts", "Rom", "1Cor", "2Cor", "Gal",
      "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus",
      "Phlm", "Heb", "Jas", "1Pet", "2Pet", "1John", "2John", "3John",
      "Jude", "Rev"}

# The summary verses that survived reading in tools/declaredthemes.py: the text
# stopping to say "here is the whole of it". 16 of the 41 marker hits verified;
# the other 25 were the same words literally -- six things physically hanging
# (a snake, a millstone, a criminal, the tree), one large sum of money, and the
# Pastorals' "faithful saying" formula introducing church order rather than a
# summary of the whole.
#
# TWO ENTRIES ARE NOT FROM THE HARVEST. Matt 22:37 and John 20:31 were added by
# hand: 22:37 is the commandment that 22:40 says everything hangs on, and John
# 20:31 is the most explicit purpose statement in the New Testament and carries
# no marker lemma at all. Saying so matters because they are 2 of 18 and the
# ratios below are computed on that 18.
DECLARED = {
    "Matt.22.37": "the greatest commandment: love God",
    "Matt.22.40": "on these two hang all the Law and the Prophets",
    "Matt.5.17": "I came not to abolish but to fulfil",
    "Mark.12.31": "no commandment greater than these",
    "Luke.24.44": "everything written about Me must be fulfilled",
    "John.20.31": "these are written that you may believe",
    "Rom.10.4": "Christ is the end of the law",
    "Rom.13.8": "he who loves his neighbour has fulfilled the law",
    "Rom.13.9": "summed up in this one decree",
    "Gal.5.14": "the entire law is fulfilled in a single decree",
    "Eph.1.10": "to bring all things together in Christ",
    "1Cor.15.3": "as of first importance: Christ died for our sins",
    "1Tim.1.15": "Christ Jesus came into the world to save sinners",
    "2Tim.2.11": "if we died with Him, we will also live with Him",
    "Titus.3.8": "those who believe should devote themselves to good works",
    "Heb.8.1": "the point of what we are saying is this",
    "Jas.1.27": "pure and undefiled religion is this",
    "Rev.21.5": "behold, I make all things new",
}


def load():
    """-> ({ref: {theme ids}}, {ref: title}) sections, themes lane only."""
    sec = collections.defaultdict(set)
    title = {}
    allrefs = set()
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        allrefs.add(d["ref"])
        title[d["ref"]] = d.get("title", "")
        if d.get("category") == LANE:
            sec[d["ref"]].add(d["id"])
    return sec, title, allrefs


def key(r):
    b, c, v = r.split(".")
    return (b, int(c), int(v))


def containing(allrefs):
    """-> f(verse ref) -> the section it falls in. Sections are start refs."""
    byb = collections.defaultdict(list)
    for r in allrefs:
        byb[r.split(".")[0]].append(key(r))
    for b in byb:
        byb[b].sort()
    def of(ref):
        b, c, v = key(ref)
        best = None
        for cand in byb.get(b, ()):
            if cand[1:] <= (c, v):
                best = cand
            else:
                break
        return ".".join(str(x) for x in best) if best else None
    return of


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pairs", type=int, default=20)
    ap.add_argument("--check", action="store_true",
                    help="do the text's own summaries carry the top themes?")
    a = ap.parse_args()

    sec, title, allrefs = load()
    n = len(allrefs)
    df = collections.Counter()
    for ids in sec.values():
        df.update(ids)

    if a.check:
        of = containing(allrefs)
        print(f"{len(DECLARED)} verses where the text summarises itself,\n"
              f"and the themes the stamps gave the section each falls in:\n")
        hit = collections.Counter()
        missing = []
        for ref in sorted(DECLARED, key=key):
            s = of(ref)
            ids = sorted(sec.get(s, ()), key=lambda x: -df[x])
            hit.update(ids)
            if not ids:
                missing.append(ref)
            print(f"  {ref:<12} {DECLARED[ref][:52]}")
            print(f"      {str(s):<12} {title.get(s,'')[:30]:<32} "
                  f"{', '.join(ids[:5]) or '-- NO THEME STAMP --'}")
        # THE CONTROL. Every declared summary is in the New Testament, because
        # the markers are Greek technical vocabulary. So enrichment against the
        # WHOLE corpus would partly just be measuring "the NT is about Christ".
        # The honest baseline is NT sections, and the difference between the
        # two columns below is the whole finding.
        ntdf = collections.Counter()
        ntn = 0
        for r, ids in sec.items():
            if r.split(".")[0] in NT:
                ntn += 1
                ntdf.update(ids)
        print(f"\n  themes drawn by the text's own summaries, against two "
              f"baselines\n  ({ntn:,} NT sections of {n:,}):\n")
        print(f"    {'':>7}  {'theme':<24} {'corpus':>7} {'NT':>7}   "
              f"{'x NT':>5}")
        for t, c in hit.most_common(14):
            share = c / len(DECLARED)
            ntshare = ntdf[t] / max(ntn, 1)
            print(f"    {c:>3}/{len(DECLARED):<3} {t:<24} "
                  f"{100*df[t]/n:6.1f}% {100*ntshare:6.1f}%   "
                  f"{share/ntshare if ntshare else 0:5.2f}")
        if missing:
            print(f"\n  !! {len(missing)} summary verses landed in a section "
                  f"with no theme stamp: {', '.join(missing)}")
        return 0

    print(f"{n:,} sections, {len(sec):,} carry a theme stamp "
          f"({100*len(sec)/n:.0f}%), {len(df)} distinct themes\n")
    print("  THE SPINE -- share of the corpus each theme carries\n")
    for t, c in df.most_common():
        bar = "#" * round(40 * c / n)
        print(f"  {100*c/n:5.1f}%  {c:>5}  {t:<22} {bar}")

    print(f"\n  PAIRS that travel together, by share of the corpus "
          f"holding BOTH\n")
    pair = collections.Counter()
    for ids in sec.values():
        for x, y in itertools_pairs(sorted(ids)):
            pair[(x, y)] += 1
    for (x, y), c in pair.most_common(a.pairs):
        # lift is shown, not used to filter: a pair can be entirely expected
        # and still be the largest structure in the corpus.
        exp = df[x] * df[y] / n
        print(f"  {100*c/n:5.1f}%  {c:>5}  lift {c/exp:4.2f}   {x} + {y}")
    return 0


def itertools_pairs(xs):
    for i, x in enumerate(xs):
        for y in xs[i + 1:]:
            yield x, y


if __name__ == "__main__":
    raise SystemExit(main())
