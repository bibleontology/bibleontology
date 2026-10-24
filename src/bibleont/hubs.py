"""Which nodes are hubs, and why counting connections does not answer it.

The app ranks by degree, and degree puts "the men that had taken strange
wives" fourth in the graph -- above Paul, above Moses, above Abraham. A reader
looking at that list can see immediately that three of the top four belong and
one does not, which is a good sign the measure is wrong rather than the
reader.

## Why the obvious fixes fail

**Weighting by the importance of your neighbours** -- eigenvector centrality,
which is PageRank -- is the natural next idea and it does not work here. Run
over this graph with the vocabulary's own edge weights and 60 iterations of
power method, the roster group stays at rank four.

That is not a bug in the algorithm. **A star centre really is central.** The
group has 115 members, each member's only edge runs back to the group, and
every one of them hands its whole share to it. PageRank is measuring something
true and it is not the thing being asked about.

## What separates them

Triangles: **do your neighbours know each other?**

```
                                        degree  triangles  avg nbr degree
Jesus                                      159        101            6.1
David                                      134        103            6.9
Jerusalem                                  100         83           10.2
Paul                                       105         51            5.3
Moses                                       58         42            9.5
the men that had taken strange wives       115          0            2.1
Judah                                      115          0            1.6
```

The separation is total, not marginal. Both roster-shaped nodes have **zero**
closed triangles among more than a hundred neighbours; every genuine hub has
dozens. Peter, James and John are each tied to Jesus and to one another. The
men of Ezra 10 are tied to the roster and to nothing, including each other.

Average neighbour degree says the same thing more softly -- 2.1 against 6 to
10 -- and is worth carrying because it degrades gracefully where triangles are
sparse.

## Second-degree reach, which is a different question

Reach -- how many nodes are two hops away and not one -- was suggested as an
alternative and is **a sharper filter than triangles for this particular
failure**. The roster drops from rank four to rank 1,042: reach of 33 despite
115 connections, because its members lead nowhere.

It brings its own bias, though, and in the opposite direction. It rewards
being *adjacent to* hubs rather than being one:

```
                        degree   2nd-degree reach
the ark of the covenant      7                326
Jordan                       7                321
Joseph                       9                381
Beth-lehem                  16                423
Moses                       58                352
```

Bethlehem at sixteen connections outranks Moses at fifty-eight, because its
few neighbours are David and Jesus. That is a true fact and a strange thing to
head a list of hubs.

So the two measure different things and neither is the other's improvement:

- **triangles** ask *is my neighbourhood real* -- cohesion
- **reach** asks *does my neighbourhood open out* -- brokerage

A roster fails both, which is why either one fixes the reported problem.
Ranking on both together gives David, Jerusalem, Jesus, Abraham, Moses, Paul,
God, the children of Israel, the Levites, Solomon -- and demotes Bethlehem and
the ark to where a reader would expect them, without excluding them.

## Weighting the two hops by their strengths, which was worth testing

The next proposal was to value a two-hop path by the **product** of the two
edge strengths, using the weights the vocabulary already carries. It is cheap
-- the weighted square of the adjacency matrix -- and it does two things, one
of them wanted.

It rejects the roster harder than anything else tried: **rank 1,107**, a
weighted reach of 346 against Jesus's 5,899.

And it makes the brokerage bias considerably worse. Bethlehem rises from
fourth to **second**, above Jerusalem and David. The tell is further down:

```
                     degree   sum of w1*w2
En-gedi                   3           3195
the tribe of Judah        5           3787
the passover              6           3541
Paul                    105           3237
```

**En-gedi has three edges** -- located in Judah, David dwelt there, Saul went
there -- and outranks Paul. That is not a defect in the arithmetic. Two of its
three neighbours are David and Saul, so every strong path through it lands
somewhere busy, and the sum over reach counts all of it.

So the product does not measure hubness. It measures **how strongly you are
attached to well-connected things**, which is brokerage with the volume turned
up, and summing over reach means a node is rewarded for its neighbours' degree
without paying for its own.

That makes it the wrong tool here and a good one elsewhere. "What is the
strongest two-hop path out of this node" is exactly the question a *related
entities* panel asks, or a **where to look next** suggestion from a page a
reader is already on. Bethlehem to David to everything David touches is a
genuinely strong route, and a reader standing on Bethlehem should be offered
it. They should not be told Bethlehem is the second most important node in
scripture.

**Same measure, opposite verdicts, depending on whether the question is "what
is central" or "where can I go from here".**

### The correction: those tests used the wrong weight

Everything above was computed with the vocabulary's declared *type* weight --
`father_of` is 5.0, `traveled_to` is 1.0 -- and that is **not** what the
application uses. `edgeStrength` in the front end has since the graph view was
built combined type weight with **how many verses name both parties**, and its
own comment records that raw citation count was tried first and rejected,
because extraction records the minimum evidence needed and so Jesus/Peter and
Jesus/Philip both carried four citations while the text spends 43 verses on
one and 10 on the other.

Re-run with the real strength, the product formula behaves:

```
God                     16225   deg  31
Jesus                   15182   deg 159
David                   14560   deg 134
Jerusalem               13577   deg 100
the children of Israel  11993   deg  75
Moses                   11444   deg  58
Beth-lehem               9264   deg  16
Abraham                  8548   deg  43
```

**En-gedi falls from rank 16 to 153.** Its three edges rest on almost nothing:
two verses name it with David, one with Saul, none with Judah. The roster
lands at 1,220. Bethlehem settles at seventh, which is arguable rather than
absurd -- it is where David and Jesus were born and the text does spend real
verses saying so.

So the product formula was never the problem. **Feeding it type weights that
ignore how much the corpus actually says was the problem**, and the fix already
existed in the interface. The `weight` field on `Hub` below still carries raw
type weight and should be read as a tie-break only.

## Adding edges can lower reach, and that is not a bug

Extraction that connects a node to material it was already near will often
**reduce** its reach, because reach counts what is two hops away *and not one*.
Anything promoted from second-degree to first-degree leaves the count.

The Spirit's concept batch is the clean example. Seven new edges took the Holy
Ghost from degree 12 to 19 and from 5 triangles to 10, and its reach fell from
4,557 to 3,263 -- because `born_again`, `baptism` and the resurrection were all
second-degree neighbours through Jesus before, contributing strong products,
and are now first-degree neighbours contributing none.

The score still rose, and sharply, because triangles doubled. But a reader
watching one column will draw the wrong conclusion, and the two columns should
be read together or not at all. **Reach is a measure of what a node opens onto,
so filling in a node's own neighbourhood necessarily shrinks it.**

## Joab, and why triangles-times-reach was not enough

The reader who asked for this measure looked at the top twenty-four and
objected to three names: Absalom, Joab and Judah. All three are honestly
earned under triangles-times-reach -- Joab has **19 closed triangles on 15
edges**, the densest neighbourhood of any figure in David's court. The
objection was not that the arithmetic was wrong. It was that being central to
one story is not the same as being central to scripture, and he was right.

Four things were tried. Three of them failed, and the failures are the useful
part.

**Summing every 2-hop path instead of the best one.** The original proposal was
`sum(w1*w2)` over all paths; what shipped was `sum` over destinations of `max`
over paths. Tested, and it is worse: Joab rises to 17 and **Paul falls to 22**,
below Hebron and Jordan. Summing every path rewards having one spectacularly
connected neighbour, which is precisely the coattail effect being complained
about.

**Counting the disconnected clusters among a node's neighbours.** Structural
diversity in the Burt sense, and it fails on this graph because it tracks
degree: Jesus 82, David 59, Paul 58 -- and Solomon **2**, which is worse than
Joab's 3. It cannot tell a small important neighbourhood from a small one.

**Inverse-frequency weighting by node type, taken literally.** The graph holds
1,597 persons and 64 texts, so a person edge is cheap and a concept edge is
rare, and weighting by `log(N/count)` says so. It works on Joab -- he drops to
29 -- and it introduces a worse problem: `creature` scores 6.46, above `being`,
**because the graph holds four creatures**. That is a fact about what has been
extracted, not about the corpus, and any measure that moves when a batch lands
is measuring the wrong thing. `creature` and `assessment` are pinned to a
baseline for exactly this reason, and the pinning is a standing debt: when
those types are properly extracted the pin should come off.

## The four terms, and the objection each one answers

- **Edges scaled by the rarity of what they reach.** *"The other portions of
  the graph have much less weight due to numbers."* An edge to a text says
  more than another edge to a person, because there are twenty-five times
  fewer texts.
- **Triangles weighted by the strength of the closing leg.** *"If there is a
  triangle does the third leg's strength matter?"* It did not -- triangles
  were counted as booleans. Now a triangle closed by a strong edge counts for
  more than one closed by a passing mention.
- **Reach log-damped per destination.** *"Joab should only be able to ride
  David's coat tails so far."* Compressing each destination's contribution
  caps what one spectacular neighbour can hand you.
- **Distinct narratives, not distinct books.** *"I am not aware of a single
  mention of him in the NT."* Checked, and true: **Joab and Absalom appear in
  zero New Testament verses**, against 5 for Aaron, 10 for Solomon and 18 for
  Isaac. Book count alone does not catch it, because Joab's four books are
  Samuel, Kings and Chronicles -- one story told twice.

Together: Joab falls from 18 to **56**, Absalom to 81, Jonathan to 100.

### The narrative collapse is an editorial call, and should be read as one

Multi-volume works counting once (1 and 2 Samuel are one book) is not
controversial. **Folding Kings and Chronicles into the Samuel narrative is.**
It asserts that the monarchy is a single continuous history, so that being
enormous inside it does not make you enormous in the corpus. It structurally
caps every monarchy figure: Solomon reaches four narratives only by way of
Matthew, Proverbs and the Song.

That is the intended effect and it is still a judgment. A reader who thinks
Chronicles is an independent witness would set it aside, and the constants are
in one place so they can.

## What this is not

It is a measure of **position in the graph**, which is a fact about the
extraction as much as about the corpus. Places are recorded as containers and
the things inside them are not joined to each other; that is a shape this
project chose. Read it as "which nodes sit in a web of mutually-connected
material", and not as "which nodes matter".
"""
from __future__ import annotations

import collections
import math
import re
from dataclasses import dataclass

from .graph import Store
from .schema import load_vocabulary

# Matches `edgeStrength` in the front end. Kept in step deliberately: a hub
# ranking computed on different weights than the graph draws would disagree
# with what the reader sees, which is worse than either being wrong alone.
CERTAINTY = {"explicit": 1.0, "implied": 0.8, "disputed": 0.6}

# Types whose rarity in the graph reflects extraction coverage rather than the
# corpus. Four creatures and four assessments are not evidence that a creature
# edge is precious. Pinned to a borrowed baseline until those types are
# properly extracted, at which point these lines should be deleted.
PINNED = {"creature": "person", "assessment": "object"}

# Volumes of one work. Uncontroversial.
VOLUMES = {
    "1Sam": "Sam", "2Sam": "Sam", "1Kgs": "Kgs", "2Kgs": "Kgs",
    "1Chr": "Chr", "2Chr": "Chr", "1Cor": "Cor", "2Cor": "Cor",
    "1Thess": "Thess", "2Thess": "Thess", "1Tim": "Tim", "2Tim": "Tim",
    "1Pet": "Pet", "2Pet": "Pet",
    "1John": "JohnEp", "2John": "JohnEp", "3John": "JohnEp",
}

# One history, told more than once. This one is a judgment -- see the module
# docstring. It is what stops a figure who is enormous inside the monarchy
# from ranking as though he were enormous in the corpus.
RETELLINGS = {"Chr": "Sam", "Kgs": "Sam"}

_BOOK = re.compile(r"([1-3]?[A-Za-z]+)")


def _narrative(ref: str) -> str | None:
    """The distinct story a citation belongs to, not the book it is printed in."""
    m = _BOOK.match(ref.strip())
    if not m:
        return None
    book = VOLUMES.get(m.group(1), m.group(1))
    return RETELLINGS.get(book, book)


@dataclass
class Hub:
    id: str
    name: str
    type: str
    degree: int
    triangles: int       # closed triangles, counted
    closure: float       # the same triangles, weighted by the closing leg
    cohesion: float      # triangles, normalised by what the degree allows
    reach: float         # 2-hop destinations, log-damped per destination
    strength: float      # summed strength of its own edges
    narratives: int      # distinct stories its citations fall in

    @property
    def score(self) -> float:
        """Closure times reach times narratives.

        Each factor answers a failure the previous version had, and each was
        arrived at by finding a name in the top twenty-four that did not
        belong. The module docstring records the three approaches that were
        tried and discarded; this is what survived.

        **closure** rather than a triangle count, because a triangle closed by
        a strong edge is not the same fact as one closed by a passing mention,
        and counting them as booleans said it was.

        Raw triangles rather than the clustering coefficient, still.
        Normalising by the triangles a degree *could* hold inverts the problem:
        a node with two neighbours who know each other scores a perfect 1.0,
        and the ranking fills with pairs -- Hiram, Haggith, Hushai -- above
        everything. Small and tight is not the same as central.

        **reach** log-damped per destination, so one spectacularly connected
        neighbour cannot hand you its whole address book. Undamped, Joab
        inherits David's 136 edges at full value.

        **narratives** because everything above is local. Joab has more
        triangles than Solomon and appears in zero New Testament verses; no
        measure confined to graph shape can see the difference, and this one is
        not confined to it.
        """
        return self.closure * self.reach * self.narratives


def survey(store: Store | None = None) -> list[Hub]:
    """Rank every node by how it sits in the graph.

    Uses the store's own `interaction` -- verses and chapters naming both
    parties -- so the weights match the ones the graph is drawn with. The
    first call warms a cache and takes about ten seconds; callers should
    hold the result rather than recompute it.
    """
    store = store or Store.load()
    vocab = load_vocabulary()

    # How much an edge is worth for *reaching* a node of a given type. The
    # graph holds 1,597 persons and 64 texts, so a person edge is common and a
    # concept edge is not; inverse frequency says so without anyone choosing
    # numbers. Two types are pinned -- see PINNED.
    counts = collections.Counter(p.type for p in store.people.values())
    total = sum(counts.values()) or 1
    rarity = {t: math.log(total / c) for t, c in counts.items()}
    for pinned, borrow in PINNED.items():
        if pinned in rarity and borrow in rarity:
            rarity[pinned] = rarity[borrow]
    default_rarity = rarity.get("person", 1.0)

    narratives: dict[str, set[str]] = collections.defaultdict(set)
    strength: dict[str, dict[str, float]] = collections.defaultdict(dict)
    for rel in store.relations:
        stories = {n for n in (_narrative(r) for r in rel.refs) if n}
        narratives[rel.src] |= stories
        narratives[rel.dst] |= stories
        if rel.src == rel.dst:
            continue
        rtype = vocab.types.get(rel.type)
        weight = rtype.weight if rtype else 2.0
        shared, chapters = store.interaction(rel.src, rel.dst)
        presence = math.log2(1 + shared + chapters * 0.5)
        value = CERTAINTY.get(rel.certainty, 1.0) * (weight * 0.35
                                                     + presence * 1.1)
        for a, b in ((rel.src, rel.dst), (rel.dst, rel.src)):
            # Scaled by what is at the far end, so the value of an edge
            # depends on where it goes and not only on how well attested it is.
            person = store.people.get(b)
            scaled = value * rarity.get(
                person.type if person else "person", default_rarity)
            strength[a][b] = max(strength[a].get(b, 0.0), scaled)

    out: list[Hub] = []
    for node, edges in strength.items():
        neighbours = list(edges)
        deg = len(neighbours)

        tri = 0
        closure = 0.0
        for i, a in enumerate(neighbours):
            for b in neighbours[i + 1:]:
                leg = strength[a].get(b)
                if leg is not None:
                    tri += 1
                    # The closing leg's strength, which a boolean count threw
                    # away. Two neighbours who merely co-occur close a weaker
                    # triangle than two the corpus keeps together.
                    closure += leg
        # A node with three neighbours can hold at most three triangles; one
        # with a hundred can hold thousands. Without this a tight family
        # outranks Paul.
        # Kept for inspection; the score uses closure. See `score`.
        possible = deg * (deg - 1) / 2 or 1
        cohesion = tri / possible

        best: dict[str, float] = {}
        for m, w1 in edges.items():
            for k, w2 in strength[m].items():
                if k == node or k in edges:
                    continue
                best[k] = max(best.get(k, 0.0), w1 * w2)
        # Damped per destination. Undamped, a single very well-connected
        # neighbour hands over its whole address book at full value, which is
        # how a court officer outranks an apostle.
        reach = sum(math.log2(1 + v) for v in best.values())

        person = store.people.get(node)
        out.append(Hub(
            id=node,
            name=person.name if person else node,
            type=person.type if person else "?",
            degree=deg, triangles=tri, closure=closure, cohesion=cohesion,
            reach=reach, strength=sum(edges.values()),
            narratives=len(narratives.get(node, ()))))
    out.sort(key=lambda h: -h.score)
    return out


def provisional(store: Store | None = None) -> list[str]:
    """Node ids ranked on adjacency alone, in about ten milliseconds.

    `survey` costs ten seconds, nearly all of it in `store.interaction` --
    counting the verses and chapters that name both parties, once per
    relation. Everything else here is set arithmetic and is effectively free.

    That matters because the opening search list is ordered by the ranking, so
    something has to be shown while the real one computes. **Degree is the
    wrong thing to show**, and this module exists because of how wrong: it puts
    a roster of men who married foreign wives fifth in the corpus, which is the
    single result the ranking was built to remove. Showing it for ten seconds
    and then replacing it teaches the reader that the list is arbitrary.

    Triangles times degree, unweighted, gets Jesus, David, Jerusalem, Paul,
    Moses and the children of Israel into the top ten and leaves both rosters
    out, because a star has no closed triangles no matter how it is weighted.
    It is not the real ranking -- there is no rarity weighting, no damping and
    no narrative count, so Joab is still too high -- but it is the same *kind*
    of answer, and the reorder when the real one arrives is a settling rather
    than a reshuffle.
    """
    store = store or Store.load()
    adjacency: dict[str, set[str]] = collections.defaultdict(set)
    for rel in store.relations:
        if rel.src == rel.dst:
            continue
        adjacency[rel.src].add(rel.dst)
        adjacency[rel.dst].add(rel.src)

    scored: list[tuple[float, str]] = []
    for node, nb in adjacency.items():
        neighbours = list(nb)
        tri = sum(1 for i, a in enumerate(neighbours)
                  for b in neighbours[i + 1:] if b in adjacency[a])
        scored.append((tri * len(neighbours), node))
    scored.sort(key=lambda t: -t[0])
    return [node for _, node in scored]


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Which nodes are hubs.")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--by", choices=["score", "degree", "reach", "cohesion",
                                     "closure", "narratives"],
                    default="score")
    args = ap.parse_args(argv)

    rows = survey()
    rows.sort(key=lambda h: -(h.score if args.by == "score"
                              else getattr(h, args.by)))

    print(f"{'':2}{'node':32}{'type':10}{'deg':>5}{'tri':>5}"
          f"{'closure':>9}{'reach':>8}{'narr':>6}")
    for h in rows[:args.top]:
        print(f"  {h.name[:30]:32}{h.type:10}{h.degree:5}{h.triangles:5}"
              f"{h.closure:9.0f}{h.reach:8.0f}{h.narratives:6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
