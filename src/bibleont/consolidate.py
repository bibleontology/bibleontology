"""Find entities that are probably one person recorded twice.

The opposite failure from disambiguation. That one is two people wrongly merged;
this is one person wrongly split, and it is the one nothing was looking for.

`propose_aliases` covers part of the ground -- a bare id against a qualified one,
`joseph` against `joseph_husband_of_mary` -- and discriminates by parentage. It
cannot see the case that actually occurs most:

    ahinoam_of_jezreel     "of Jezreel, David's wife"        from the 1sam batch
    ahinoam_jezreelitess   "the Jezreelitess, wife of David" from the 2sam batch

Both qualified, so neither is the bare form; different qualifiers, so no string
rule joins them; and no shared parent, so parentage says nothing. They are
plainly one person and the graph carries her twice, with David married to her
twice.

The signal that finds them is the relations themselves. **Two entities sharing a
name and an identical (relation type, counterpart) edge are almost never two
people.** Two women called Ahinoam who are each the spouse of David is not a
coincidence the text supports; it is a batch boundary.

Nothing here merges anything. Identity decisions are recorded by hand in
`identity.yaml` because they are judgments, and a tool that silently fused
records would be able to destroy the distinctions the disambiguation work exists
to protect. This reports candidates and the evidence for and against each.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .graph import Store
from .schema import name_variants


# An edge held by at most this many entities is rare enough that two sharing it
# are worth comparing even when their names differ entirely.
#
# Raised from 4 once Zidon and Sidon were found. They are both sons of Canaan,
# who has twelve, so the pair was never formed and the spelling test never ran.
# The cap was doing filtering that the spelling test does better: every pair
# found this way must still read as two spellings of one name, so a wider net
# costs candidates to consider rather than candidates to report.
NAMELESS_PAIR_CAP = 30


@dataclass
class Candidate:
    """Two ids that may be one person, with the evidence either way."""

    a: str
    b: str
    name: str
    shared_edges: list[tuple[str, str]] = field(default_factory=list)
    shared_refs: list[str] = field(default_factory=list)
    parents_a: list[str] = field(default_factory=list)
    parents_b: list[str] = field(default_factory=list)

    edge_weights: dict[tuple[str, str], float] = field(default_factory=dict)
    declared_distinct: bool = False
    exact_name: bool = False
    both_unnamed: bool = False
    spelling_variant: bool = False

    @property
    def blocked(self) -> bool:
        """Different recorded parents means different people.

        The same rule `propose_aliases` uses, and it is reliable: parentage is
        the most consistently extracted relation in the graph, and two figures
        with different fathers are not one figure.
        """
        return bool(self.parents_a and self.parents_b) and not (
            set(self.parents_a) & set(self.parents_b)
        )

    def score(self) -> float:
        """Shared edges, weighted by how rare each one is.

        Counting them equally does not work. "Both spouse_of David" is nearly
        conclusive because few people are. "Both mentor_of Jesus" is worth
        almost nothing because twelve are, and it made Peter and Simon the
        Canaanite -- two different apostles who happen to share a name -- look
        like one man. The same for "both located_in Judah", which every town in
        Judah satisfies.
        """
        if self.declared_distinct:
            return 0.0
        return self.raw_score()

    def raw_score(self) -> float:
        """The same arithmetic with the disambiguation veto set aside.

        `score` returns zero the moment either record says it is "distinct
        from" the other, and that veto is the one piece of evidence here which
        never had to cite a verse. It is an extractor's claim, and a wrong one
        silently switches off the check.

        It has been wrong. Uzzah, Ahio and Abinadab were each in the graph
        twice -- once from 2 Samuel 6 and once from 1 Chronicles 13, the same
        episode -- and all six records disclaimed their own twin, so the pair
        scored zero and never appeared. This exists so a sweep can ask what
        the evidence would have said on its own.
        """
        if self.blocked:
            return 0.0
        # Identical surface names carry most of the suspicion. Two entities both
        # named exactly "Ahinoam", both married to David, are one record split
        # in two; Peter and Simon the Canaanite share only the *variant* "Simon"
        # and are two apostles. Without this, rarity weighting buried the split
        # wives, because David has many and the edge is therefore not rare.
        base = 4.0 if self.exact_name else 0.0
        # Two *unnamed* records with the same description are a stronger signal
        # than two named ones, and the ordinary evidence is missing by
        # construction. A role is a description, not a name: "the elder" is not
        # a coincidence the way two men called Simon is, and unnamed figures
        # rarely share edges or verses that could corroborate them.
        #
        # This was found by minting a second "the elder" for 2 John when 3 John
        # already had one whose own note said it covered both letters. Nothing
        # flagged it: the names differed only in capitals, the records shared no
        # edge and no verse, and the score came to zero.
        if self.both_unnamed and self.exact_name:
            base += 4.0
        # Two spellings of one name, sharing an edge. Zidon and Sidon are both
        # "the firstborn of Canaan" in verses that are otherwise word for word,
        # and scored 0.9 -- the shared edge alone, because Canaan has twelve
        # children so the edge is not rare. The near-identical name is the
        # evidence here and was worth nothing.
        if self.spelling_variant and not self.exact_name:
            base += 4.0
        return base + sum(self.edge_weights.values()) + len(self.shared_refs) * 2.0

    def why(self) -> str:
        bits = []
        for key in sorted(self.shared_edges, key=lambda k: -self.edge_weights.get(k, 0)):
            rtype, other = key
            bits.append(f"both {rtype} {other} ({self.edge_weights.get(key, 0):.0f})")
        if self.shared_refs:
            bits.append(f"share {', '.join(self.shared_refs[:3])}")
        return "; ".join(bits) or "name only"


def _declared_distinct(store: Store, pid: str, other: str) -> bool:
    """Did an extractor already rule these two apart, specifically?

    Must check *which* entity the note distinguishes from. A first version
    vetoed on the mere presence of "distinct from", which suppressed the two
    cases that prompted this whole check: `abigail_wife_of_david` reads
    "distinct from Abigail the mother of Amasa", a claim about a third
    Abigail entirely, and both Ahinoams disclaim the one who married Saul.
    Neither says anything about the other.

    So the qualifier of the other id has to appear in the clause. Where it
    does -- socoh_hill saying "distinct from Socoh in the valley" against
    socoh_valley -- the judgment was made deliberately and stands.
    """
    note = (store.people[pid].disambiguation or "").lower()
    if "distinct from" not in note:
        return False
    clause = note.split("distinct from", 1)[1]
    shared = {w for w in _slug_words(store.people[pid].name)}
    qualifiers = [w for w in _slug_words(other) if w not in shared and len(w) > 3]
    return any(w in clause for w in qualifiers)


def _slug_words(text: str) -> list[str]:
    return [w for w in text.lower().replace("-", "_").split("_") if w]


def _spelling_variants(a: str, b: str) -> bool:
    """Do these read as two spellings of one name rather than two names?

    Phalti and Phaltiel, yes. Levi and Simeon, no. A shared prefix is the
    signal that actually separates them -- transliteration differences usually
    fall at the end (Melchisedec/Melchizedek, Eliphalet/Eliphelet,
    Phalti/Phaltiel), because that is where the case endings live.

    **"Usually" was doing too much work.** Genesis 10:15 and 1 Chronicles 1:13
    name Canaan's firstborn, and the older translation spells him Sidon in
    one and Zidon in the other (the BSB has Sidon in both). The same verse,
    one letter apart, and the graph carried two sons. A prefix rule cannot see it, because the drift is in the
    first character.

    So a shared *ending* counts too, on the tighter terms that the names be the
    same length and differ in exactly one place. That admits Zidon/Sidon and
    keeps out anything that merely rhymes.
    """
    for article in ("the ", "a "):
        if a.lower().startswith(article):
            a = a[len(article):]
        if b.lower().startswith(article):
            b = b[len(article):]
    a, b = a.lower().strip(), b.lower().strip()
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) < 4:
        return False
    if longer.startswith(shorter):
        return True
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    if common >= 4 and abs(len(a) - len(b)) <= 3:
        return True
    # Drift at the front: same length, one substitution, and a long tail in
    # common. Zidon/Sidon, Zorobabel/Sorobabel.
    if len(a) == len(b) and len(a) >= 5:
        diffs = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if len(diffs) == 1 and len(a) - diffs[0] - 1 >= 4:
            return True
    return False


def _named_together(store: Store, a: str, b: str) -> bool:
    """Does one verse name both, under both spellings?

    If it does, they are two people. Nehemiah 7:2 -- "I put my brother Hanani in
    charge of Jerusalem, along with Hananiah the commander of the fortress"
    -- names two men whose spellings are close enough to look like variants of one.
    """
    corpus = store.corpus
    names_a = [n for n in store.people[a].names() if len(n) > 3]
    names_b = [n for n in store.people[b].names() if len(n) > 3]
    refs = set(store.people[a].refs) & set(store.people[b].refs)
    for ref in refs:
        try:
            blob = " ".join(v.text for v in corpus.verses_for(ref)).lower()
        except Exception:
            continue
        if any(x.lower() in blob for x in names_a) and any(
            y.lower() in blob for y in names_b
        ):
            return True
    return False


def _directly_related(store: Store, a: str, b: str) -> bool:
    """Two records of one person never have an edge to each other.

    This is what rules out the family cases the rare-edge pairing drags in --
    Hamor and Shechem, James and John, Aquila and Priscilla.
    """
    return any(edge.other == b for edge in store.edges(a))


def _edge_set(store: Store, pid: str) -> set[tuple[str, str]]:
    """(relation type, the other end) for every edge, direction preserved."""
    out: set[tuple[str, str]] = set()
    for edge in store.edges(pid):
        arrow = "->" if edge.outgoing else "<-"
        out.add((f"{arrow}{edge.relation.type}", edge.other))
    return out


def candidates(store: Store | None = None, min_score: float = 5.0) -> list[Candidate]:
    store = store or Store.load()

    by_name: dict[str, list[str]] = defaultdict(list)
    for pid, person in store.people.items():
        for name in person.names():
            for variant in name_variants(name):
                key = variant.lower().strip()
                if len(key) > 2:
                    by_name[key].append(pid)

    # Grouping by name alone misses split records whose *spellings* differ, and
    # those are exactly the ones nobody notices. Phalti (1 Sam 25:44) and
    # Phaltiel (2 Sam 3:15) are one man -- both "the son of Laish", both married
    # to Michal -- and the name index cannot pair them.
    #
    # So also pair anything sharing a rare edge, whatever it is called. A
    # relation held by only a handful of entities is strong enough evidence on
    # its own; the rarity weighting in score() then decides.
    shared: dict[tuple[str, str], set[str]] = defaultdict(set)
    for pid in store.people:
        for key in _edge_set(store, pid):
            shared[key].add(pid)
    for key, holders_of in shared.items():
        if 1 < len(holders_of) <= NAMELESS_PAIR_CAP:
            # Persons only. Groups and places legitimately share relations --
            # neighbouring nations are attacked by the same kings, towns sit in
            # the same region -- and their names are structurally alike ("the
            # tribe of X"), so both the evidence and the spelling test mislead.
            # The split-record problem this path exists for is a person problem.
            for pid in holders_of:
                if store.people[pid].type == "person":
                    by_name[f"EDGEPAIR:{key[0]}:{key[1]}"].append(pid)

    # How many entities hold each (direction+type, counterpart) edge. An edge
    # shared by two entities out of two is evidence; one shared by two out of
    # forty is not.
    holders: dict[tuple[str, str], int] = defaultdict(int)
    for pid in store.people:
        for key in _edge_set(store, pid):
            holders[key] += 1

    parents = store._parents()
    seen: set[tuple[str, str]] = set()
    out: list[Candidate] = []

    for name, ids in by_name.items():
        ids = sorted(set(ids))
        if len(ids) < 2:
            continue
        for i, a in enumerate(ids):
            for b in ids[i + 1 :]:
                if (a, b) in seen:
                    continue
                seen.add((a, b))
                if store.people[a].type != store.people[b].type:
                    continue
                # Two records of one person never point at each other.
                if _directly_related(store, a, b):
                    continue
                # Pairs found only by a shared rare edge must also read as two
                # spellings of one name, or every pair of siblings qualifies.
                if name.startswith("EDGEPAIR:"):
                    if not any(
                        _spelling_variants(x, y)
                        for x in store.people[a].names()
                        for y in store.people[b].names()
                    ):
                        continue
                    if _named_together(store, a, b):
                        continue

                edges_a, edges_b = _edge_set(store, a), _edge_set(store, b)
                shared = sorted(edges_a & edges_b)
                refs_a = set(store.people[a].refs)
                refs_b = set(store.people[b].refs)

                pa = parents.get(a) or {}
                pb = parents.get(b) or {}

                declared = _declared_distinct(store, a, b) or _declared_distinct(
                    store, b, a
                )

                cand = Candidate(
                    a=a,
                    b=b,
                    name=name,
                    shared_edges=shared,
                    shared_refs=sorted(refs_a & refs_b),
                    parents_a=sorted(set(pa.get("f", set())) | set(pa.get("m", set()))),
                    parents_b=sorted(set(pb.get("f", set())) | set(pb.get("m", set()))),
                    edge_weights={
                        key: 10.0 / max(1, holders[key] - 1) for key in shared
                    },
                    declared_distinct=declared,
                    exact_name=store.people[a].name.strip().lower()
                    == store.people[b].name.strip().lower(),
                    both_unnamed=bool(store.people[a].attrs.get("unnamed"))
                    and bool(store.people[b].attrs.get("unnamed")),
                    spelling_variant=any(
                        _spelling_variants(x, y)
                        for x in store.people[a].names()
                        for y in store.people[b].names()
                    ),
                )
                if cand.score() >= min_score:
                    out.append(cand)

    out.sort(key=lambda c: -c.score())
    return out


def cascade_report(store: Store | None = None) -> str:
    """Pairs blocked by parents who are themselves a candidate pair.

    `blocked` treats differing parentage as conclusive, and for two men with
    genuinely different fathers it is. But if the two fathers are one man
    recorded twice, the rule fires on a difference that does not exist, and
    it fires silently -- the pair scores zero and never reaches a report.

    So duplication hides duplication, one generation at a time. Six records
    were found this way: Abinadab of Kirjath-jearim was in the graph twice,
    which made his sons Uzzah and Ahio look like four men rather than two;
    Ahitub was in twice, which did the same to Zadok and then to Ahimaaz
    below him. Merging the parent is what let the children be seen.

    The report is deliberately noisy. Most entries are correct blocks -- two
    kings of the same name really do have different fathers -- and the only
    ones worth reading are those where the two parents share a name.
    """
    store = store or Store.load()
    found = candidates(store, 0.0)
    pairs = {frozenset((c.a, c.b)) for c in found}

    rows = []
    for c in found:
        if not c.blocked:
            continue
        for pa in c.parents_a:
            for pb in c.parents_b:
                if pa != pb and frozenset((pa, pb)) in pairs:
                    rows.append((c, pa, pb))
                    break
            else:
                continue
            break

    rows.sort(key=lambda r: (store.people[r[1]].name != store.people[r[2]].name,
                             -r[0].raw_score()))
    out = [
        f"{len(rows)} pairs are blocked by parents who are themselves a "
        f"candidate pair.",
        "Same-named parents are the ones to read; the rest are usually right.",
        "",
    ]
    for c, pa, pb in rows:
        same = store.people[pa].name == store.people[pb].name
        mark = "  <-- same name" if same else ""
        out.append(f"  {c.a} / {c.b}")
        out.append(f"    blocked by: {pa} vs {pb}{mark}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Entities that may be one person recorded twice."
    )
    ap.add_argument("--min-score", type=float, default=5.0)
    ap.add_argument(
        "--blocked",
        action="store_true",
        help="also show pairs ruled out by differing parentage",
    )
    ap.add_argument(
        "--declared",
        action="store_true",
        help="show only pairs suppressed by a 'distinct from' note, scored "
        "as if the note were absent -- the sweep for notes that are wrong",
    )
    ap.add_argument(
        "--cascade",
        action="store_true",
        help="show pairs ruled out by differing parents where the parents "
        "are themselves a candidate pair -- duplication hiding duplication",
    )
    args = ap.parse_args(argv)

    store = Store.load()

    if args.cascade:
        print(cascade_report(store))
        return 0

    if args.declared:
        vetoed = [
            c
            for c in candidates(store, 0.0)
            if c.declared_distinct and c.raw_score() >= args.min_score
        ]
        vetoed.sort(key=lambda c: -c.raw_score())
        print(
            f"{len(vetoed)} pairs suppressed by a 'distinct from' note that "
            f"would otherwise score {args.min_score:g} or more.\n"
            "Each needs reading: the note may be right.\n"
        )
        for c in vetoed:
            print(f"  {store.people[c.a].name}  (would score {c.raw_score():.0f})")
            print(f"    {c.a:32} {(store.people[c.a].disambiguation or '')[:70]}")
            print(f"    {c.b:32} {(store.people[c.b].disambiguation or '')[:70]}")
            print(f"    evidence: {c.why()}")
            print()
        return 0

    found = candidates(store, args.min_score)

    print(f"{len(found)} candidate pairs\n")
    for c in found:
        a_note = store.people[c.a].disambiguation or ""
        b_note = store.people[c.b].disambiguation or ""
        print(f"  {store.people[c.a].name}  (score {c.score():.0f})")
        print(f"    {c.a:30} {a_note[:64]}")
        print(f"    {c.b:30} {b_note[:64]}")
        print(f"    evidence: {c.why()}")
        print()

    if args.blocked:
        blocked = [c for c in candidates(store, 0.0) if c.blocked and c.shared_edges]
        print(f"\n{len(blocked)} pairs share an edge but have different parents:")
        for c in blocked:
            print(f"  {c.a} / {c.b}  -- {c.why()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
