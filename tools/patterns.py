"""Every pattern in the corpus, ranked by how specific and how rare it is.

`patternmine.py` answers *what do these four passages share*. This asks the
unsupervised question: **what patterns are in the corpus at all**, with nothing
seeded and nothing known in advance.

## Why this cannot be brute force

264 trait ids give 187 million four-trait combinations and 1.5 billion at five.
So it is built as frequent-itemset mining: a combination can only be frequent
if every one of its subsets is frequent, which means candidates are grown from
confirmed ones and the search never visits the vast majority of that space.
`--minsup` is what makes it finish.

## Ranking: complexity times distinctiveness

A combination of the two was asked for, and they pull in opposite directions.

    complexity      how many traits must coincide -- k
    distinctiveness how little of the corpus matches -- log2(N / support)

    score = k * log2(N / support)

A single trait in 5% of the corpus scores 4.3. Four traits that coincide in
eight passages score 34. That is the intended shape: **coincidence is the
signal**, and a long rule that fires rarely is the thing worth reading.

### The two failure modes it guards against

**A pattern must repeat.** A combination matching one passage is not a
pattern, it is a description of that passage, and it would score highest of
all. `--minsup` is the floor.

It is also what makes the search finish, and the two purposes pull together
rather than apart. At minsup 3 with k up to 5 the level-3 join never
terminates; at 25 it runs in five seconds. Since 25 of 3,078 units is 0.8% of
the corpus, the floor is not costing distinctiveness -- everything above it is
already rare.

**Subsets that add nothing are dropped.** If `a+b+c` and `a+b+c+d` match the
same passages, the shorter one has learned nothing that the longer does not
say better, and the longer is reported alone. These are *closed* itemsets, and
without the filter the top 100 fills with near-duplicates of one pattern.

## The unit

Sections by default. `--window N` merges N contiguous sections first, because
a pattern that spans an arc -- judgment announced, then executed, then its
aftermath -- cannot be seen through a one-section aperture. Overlapping matches
are merged upward into the span they point at, which is the rule of
2026-09-14: repeated overlap is a unit boundary, not duplication.

    python tools/patterns.py --top 100
    python tools/patterns.py --window 3 --minsup 4 --top 100
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "out/stamps-leveled.jsonl"


def books(sec, order, floor=0.25):
    """-> [(refs, ids)] one unit per book, ids unioned from its sections.

    2026-09-14: do not go low at first; wait for evidence from above.

    Mining 3,078 sections directly is going low immediately, and it shows: at
    that granularity the top of the ranking filled with four common role
    stamps landing in one section by chance. 66 books is a search small enough
    to be exhaustive, and a pattern that does not distinguish books is not
    worth hunting for inside them. The book level proposes; `drill()` asks the
    sections whether the proposal survives.

    Presence cannot be the test up here. A book is the union of its sections,
    so nearly every book "has" nearly every trait -- `people_of_god` is
    book-level in 57 of 66 -- and with everything frequent the join never
    finishes. **Density is what a book-level trait means**: the trait belongs
    to the book when a real share of its sections carry it, which is the same
    measure `signature.py` uses and it makes the book vectors sparse enough to
    search exhaustively.
    """
    per = collections.defaultdict(list)
    for r in order:
        per[r.split(".")[0]].append(r)
    out = []
    for rs in per.values():
        c = collections.Counter()
        for r in rs:
            c.update(sec[r])
        # A fraction alone is meaningless in a small book. Obadiah has one
        # section, Nahum three, Jude four -- so at a 25% floor a single
        # stamped section makes the trait "characteristic of the book", every
        # tiny book carries everything, and they all match each other at
        # billions-fold lift while NO section below them carries the pattern
        # at all. Requiring at least three sections makes a density a density.
        out.append((rs, {x for x, n in c.items()
                         if n >= max(3, floor * len(rs))}))
    return out


def correlations(units, items):
    """-> {(a,b): phi} how much each pair of traits travels together anyway.

    2026-09-14: calculate a correlation between all stamps, then match
    connections against stamps and assign a score of something like
    1-correlation, and look for the highest combined totals.

    This is the fix for lift's central defect here. Lift asks how surprising a
    co-occurrence is **under independence**, and these traits are nowhere near
    independent -- `judgment_oracle`, `woe_pronouncement` and `prophetic_word`
    travel together as a matter of register, so every four-subset of the
    prophets scored astronomically and Micah appeared in 60 of the first
    hundred patterns.

    Correlation measures what lift assumed away. Scoring a combination by
    `sum(1 - phi)` over its pairs asks a better question: **do these traits
    normally avoid each other?** A quartet of prophetic vocabulary scores near
    zero however rare the quartet is, because those traits always co-occur. A
    combination that crosses registers -- a legal formula inside a lament, a
    genealogy inside an apocalypse -- scores high, and that is the thing a
    reader would call a pattern rather than a genre.

    phi is the correlation of two binary variables, which is what a stamp is.
    """
    n = len(units)
    has = {x: set() for x in items}
    for i, (_refs, ids) in enumerate(units):
        for x in ids:
            if x in has:
                has[x].add(i)
    out = {}
    for a, b in itertools.combinations(sorted(items), 2):
        A, B = has[a], has[b]
        n11 = len(A & B)
        n10, n01 = len(A) - n11, len(B) - n11
        n00 = n - n11 - n10 - n01
        den = math.sqrt(len(A) * (n - len(A)) * len(B) * (n - len(B)))
        out[(a, b)] = ((n11 * n00 - n10 * n01) / den) if den else 0.0
    return out


def weights(corr, items):
    """-> {trait: total connection weight} its summed |phi| to everything else.

    2026-09-14: add a denominator of total connection weight.

    Some traits are hubs. `judgment` and `people_of_god` correlate with almost
    everything, so any combination containing one inherits that connectivity
    and looks well-connected without having earned it. A trait's total |phi|
    across the corpus is what it brings to any combination regardless of which
    one, and dividing by it asks the sharper question: **are these peripheral
    traits that nonetheless met?**

    It also removes the size bias that `sum(1 - phi)` carried -- the numerator
    grows with the number of pairs and the denominator grows with the number
    of traits, so a combination no longer wins by being long.

    **Measured caveat, and it is about the data rather than the measure.** In
    this corpus low connection weight mostly means a badly stamped trait. The
    top result under this score is `bridegroom + builder + guest + host +
    firstborn ...` landing in *The Gates of the Inner Court* -- the
    `character_roles` over-stamping already known from Gen 1:24 being given
    `bridegroom + builder + fisherman`. Those traits are peripheral because
    they are noise, and dividing by a small denominator amplifies them. The
    ranking is sound; the stamps under it are not yet.
    """
    w = collections.defaultdict(float)
    for (a, b), v in corr.items():
        w[a] += abs(v)
        w[b] += abs(v)
    return {x: w.get(x, 0.0) for x in items}


def rarity(base, n):
    """-> {trait: log(N/df)} how much a stamp says by being uncommon.

    2026-09-14: the stamp categories are not all equal, and the rarer the
    stronger the signal.

    Every measure before this counted traits equally, so `people_of_god` in
    thousands of sections weighed the same as `beast_from_sea` in four. That
    is why the prophetic register kept winning: its vocabulary is everywhere,
    and a pattern built from ubiquitous traits was scored as generously as one
    built from traits that barely occur.

    Inverse document frequency is the standard answer and it is the right one
    here: a trait in 1% of the corpus carries log(100) of evidence and one in
    60% carries almost none. Weighting each pair's surprise by how rare its
    two traits are makes a coincidence of rare stamps outrank a coincidence of
    common ones, however tight the correlation.
    """
    return {x: math.log(n / df) for x, df in base.items() if df}


def surprise(combo, corr, mean=False, w=None, idf=None):
    """Sum of (1 - phi) over every pair. High = traits that normally avoid.

    The SUM is the "combined totals" asked for and it is a genuine combination
    of the two criteria -- more traits means more pairs (complexity) and each pair
    contributes its own independence (distinctiveness). Measured on the book
    level, though, it correlates **0.987 with trait count**: the mean term
    spans only 0.705 to 0.872, so size dominates and the correlation barely
    discriminates.

    The cause is the unit, not the measure. 66 books is too few observations
    to estimate phi between 264 traits -- most pairs come out small and alike.
    `mean=True` divides the size out, and the measure is worth much more at
    section level, where 3,078 observations can actually separate traits that
    avoid each other from traits that merely co-occur rarely.
    """
    pairs = list(itertools.combinations(sorted(combo), 2))
    if idf is not None:
        # each pair's surprise, weighted by how much its two traits say
        return sum((1.0 - corr.get((x, y), 0.0))
                   * (idf.get(x, 0.0) + idf.get(y, 0.0)) / 2
                   for x, y in pairs) / max(len(pairs), 1)
    tot = sum(1.0 - corr.get(p, 0.0) for p in pairs)
    if w is not None:
        den = sum(w.get(x, 0.0) for x in combo)
        return tot / den if den else 0.0
    return tot / len(pairs) if mean and pairs else tot


def drill(sec, refs, combo):
    """-> the sections inside these books that carry the whole combination."""
    return [r for r in refs if set(combo) <= sec[r]]


def load(window, floor=0.25):
    """-> (units, title) where a unit is (refs, {id})."""
    if not SRC.exists():
        raise SystemExit("run: python tools/stamp.py --levels")
    sec, title = collections.defaultdict(set), {}
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        sec[d["ref"]].add(d["id"])
        title[d["ref"]] = d.get("title", "")
    order = sorted(sec, key=lambda r: (r.split(".")[0],
                                       *(int(x) for x in r.split(".")[1:])))
    if window == 0:                     # book level -- start here
        return books(sec, order, floor), title, sec
    if window <= 1:
        return [([r], sec[r]) for r in order], title, sec
    out = []
    for i in range(len(order) - window + 1):
        w = order[i:i + window]
        if len({r.split(".")[0] for r in w}) != 1:
            continue
        out.append((w, set().union(*(sec[r] for r in w))))
    return out, title, sec


def frequent(units, minsup, maxk):
    """Apriori: {tuple: set(unit indices)} for every itemset above minsup.

    The first version generated candidates by trying every frequent item
    against every frequent itemset and then checking all k subsets for
    frequency. That is |itemsets| x |items| x k set lookups per level and it
    did not finish.

    This joins instead: two (k-1)-itemsets sharing their first k-2 items
    produce one candidate, and its support is the INTERSECTION of theirs --
    which is both the pruning rule and the counting step at once, so the units
    are never rescanned. Keeping itemsets as sorted tuples makes the shared
    prefix a slice comparison.
    """
    post = collections.defaultdict(set)
    for i, (_refs, ids) in enumerate(units):
        for x in ids:
            post[x].add(i)
    cur = {(x,): v for x, v in post.items() if len(v) >= minsup}
    out = dict(cur)
    k = 1
    while cur and k < maxk:
        keys = sorted(cur)
        nxt = {}
        for i, a in enumerate(keys):
            pre = a[:-1]
            for b in keys[i + 1:]:
                if b[:-1] != pre:              # sorted, so prefixes are runs
                    break
                cand = a + (b[-1],)
                sup = cur[a] & cur[b]
                if len(sup) >= minsup:
                    nxt[cand] = sup
        out.update(nxt)
        cur = nxt
        k += 1
    return out


def closed(sets):
    """Drop an itemset if a strict superset matches exactly the same units."""
    by_sup = collections.defaultdict(list)
    for s, rows in sets.items():
        by_sup[frozenset(rows)].append(set(s))
    out = {}
    for rows, group in by_sup.items():
        # Among itemsets with IDENTICAL support, keep ONE -- the largest.
        #
        # The subset test alone is not enough when --maxk truncates the
        # search: a real 5-trait pattern is never built, so all five of its
        # 4-subsets survive as mutually non-nested and the ranking reports the
        # same pattern five times. Identical support means identical pattern
        # however the traits are sliced, so the union of the group is the
        # honest description of it.
        merged = set().union(*group)
        out[tuple(sorted(merged))] = sorted(rows)
    return out


def merge(units, rows):
    """Overlapping matches climb into the span they point at."""
    spans = [units[i][0] for i in sorted(rows)]
    out = []
    for w in spans:
        if out and set(w) & set(out[-1]):
            out[-1] = out[-1] + [r for r in w if r not in out[-1]]
        else:
            out.append(list(w))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--window", type=int, default=0,
                    help="0 = books (start high), 1 = sections, N = N-section "
                         "windows")
    ap.add_argument("--minsup", type=int, default=4)
    ap.add_argument("--maxk", type=int, default=4)
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--score",
                    choices=("rarity", "peripheral", "surprise",
                             "avoidance", "lift"),
                    default="rarity",
                    help="surprise = sum(1-phi) over pairs; lift assumes the "
                         "traits are independent, and they are not")
    ap.add_argument("--spread", action="store_true", default=True,
                    help="multiply by log2(1+books): a pattern the corpus "
                         "returns to beats one author's habit")
    ap.add_argument("--overlap", type=float, default=0.5,
                    help="skip a pattern when this share of its books is "
                         "already covered by one already listed")
    ap.add_argument("--realised", action="store_true", default=True,
                    help="require at least one section to carry the whole thing")
    ap.add_argument("--floor", type=float, default=0.25,
                    help="book level: share of sections that must "
                         "carry a trait for the book to have it")
    a = ap.parse_args()

    units, title, sec = load(a.window, a.floor)
    N = len(units)
    print(f"{N:,} units of {a.window} section(s), minsup {a.minsup}, "
          f"traits up to {a.maxk}", flush=True)

    sets = frequent(units, a.minsup, a.maxk)
    print(f"frequent itemsets: {len(sets):,}", flush=True)
    sets = closed(sets)
    print(f"closed: {len(sets):,}\n", flush=True)

    # Rarity alone cannot rank, and does not mean what we want.
    #
    # Every pattern sitting at the minsup floor scores identically -- the first
    # version returned thousands of ties at 27.8 and ordered them arbitrarily.
    # Worse, it rewarded rarity however it arose: `bridegroom + builder +
    # fisherman + gatekeeper` matched 25 sections including "The Sixth Day",
    # which is four common role stamps landing together by chance.
    #
    # LIFT is the measure actually wanted: how much more often these traits
    # coincide than independence predicts. Four traits each in 10% of the
    # corpus should co-occur in 0.01% of it; when they co-occur in 1%, that is
    # a hundredfold coincidence and it is the thing worth reading. Chance
    # co-occurrence scores ~1 and disappears.
    base = collections.Counter()
    for _refs, ids in units:
        base.update(ids)
    a_score = a.score
    corr = (correlations(units, set(base))
            if a.score in ("surprise", "avoidance", "peripheral", "rarity")
            else {})
    W = weights(corr, set(base)) if a.score == "peripheral" else {}
    IDF = rarity(base, N) if a.score == "rarity" else {}
    ranked = []
    for s, rows in sets.items():
        if len(s) < 2:
            continue
        expected = N
        for x in s:
            expected *= base[x] / N
        if expected <= 0:
            continue
        lift = len(rows) / expected
        if lift <= 1:
            continue                  # no more than chance predicts
        passages = merge(units, rows)
        # 2026-09-14: spread across the corpus raises interest.
        #
        # A combination confined to two books is that author's habit; the same
        # combination in thirteen is a pattern the corpus keeps returning to.
        # Nothing in the earlier measures knew the difference. log2 rather
        # than the count itself, so breadth matters most where it is scarce --
        # two books to four is a real change, twenty to twenty-two is not.
        nbooks = len({w[0].split(".")[0] for w in passages})
        breadth = math.log2(1 + nbooks)
        if a_score == "lift":
            score = len(s) * math.log2(lift)
        else:
            # The measure asked for: the traits' own correlations, not independence.
            score = surprise(s, corr, a_score == "avoidance",
                             W if a_score == "peripheral" else None,
                             IDF if a_score == "rarity" else None)
            if a.spread:
                score *= breadth
        ranked.append((score, len(s), len(passages), sorted(s), passages,
                       len(rows), lift))
    ranked.sort(key=lambda x: (-x[0], -x[6]))

    # 2026-09-14: list both the node structure characteristics as primary and
    # the common stamps shared across the instances.
    #
    # The structure is what makes it a pattern -- how many nodes, how big they
    # are, how far they spread. A combination appearing 30 times inside one
    # book is a habit of that author; the same combination across 12 books is
    # a pattern in the corpus. The stamps say what it is ABOUT, and are
    # reported second because two patterns can share stamps and differ
    # entirely in shape.
    # Two filters that turn a ranking into a reading list.
    #
    # REALISED: a book-level combination that no single section carries is a
    # fact about vocabulary, not a pattern anyone can be shown. 31 of the
    # first hundred were of that kind.
    #
    # DIVERSE: lift over independent traits rewards large correlated trait
    # sets, and the prophetic books all share prophetic vocabulary, so every
    # four-subset of them scores astronomically. Micah appeared in 60 of the
    # first hundred and Isaiah in 56 -- one genre reported a hundred ways. A
    # pattern is skipped when most of its books are already spoken for, so the
    # list moves on instead of restating.
    shown, seen_books = [], []
    for row in ranked:
        bset = {w[0].split(".")[0] for w in row[4]}
        if a.realised and not drill(sec, [r for w in row[4] for r in w], row[3]):
            continue
        if any(len(bset & prev) / len(bset) > a.overlap for prev in seen_books):
            continue
        shown.append(row)
        seen_books.append(bset)
        if len(shown) >= a.top:
            break

    for n, (score, k, np_, combo, passages, sup, lift) in enumerate(shown, 1):
        sizes = sorted(len(w) for w in passages)
        books = collections.Counter(w[0].split(".")[0] for w in passages)
        spread = ", ".join(f"{b}({c})" for b, c in books.most_common(6))
        print(f"\n{n:>4}. score {score:.1f}   lift {lift:.0f}x")
        print(f"      STRUCTURE  {np_} nodes, {sizes[0]}-{sizes[-1]} sections "
              f"(median {sizes[len(sizes)//2]}), {len(books)} books")
        print(f"      SPREAD     {spread}"
              + ("" if len(books) <= 6 else f" +{len(books)-6} more"))
        print(f"      STAMPS     {' + '.join(combo)}")
        if a.window == 0:
            # evidence from above, tested below: where inside those books
            # does the whole combination actually land together?
            inside = drill(sec, [r for w in passages for r in w], combo)
            print(f"      BELOW      {len(inside)} sections carry all of it")
            for r in inside[:3]:
                print(f"      e.g.       {r:<26} {title[r][:40]}")
        else:
            for w in passages[:3]:
                where = f"{w[0]}..{w[-1]}" if len(w) > 1 else w[0]
                print(f"      e.g.       {where:<26} {title[w[0]][:40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
