"""Who the corpus talks about most, and whether the graph followed them.

The coverage report answers "which chapters has nothing been extracted from",
and it was answering it well while Esther and Haman had no edge between them.
Esther is named in dozens of verses across seven chapters of her book; every
relation citing her came from two of them. No chapter was uncited, no
validation failed, and the central conflict of the book was simply not there.

So this measures a different thing: **for each person, how much of their span
in the text did the graph actually follow?**

    reach  = chapters where the person is named
    held   = chapters cited by at least one relation touching them
    missed = reach - held

`missed` is the number that matters. A high-reach person with a low `held` is a
figure the graph knows *of* rather than *about* -- it has their parentage and
their first appearance and nothing from the middle of their life. That is a
worse failure than an uncited chapter, because it is invisible: the person
looks present, and the entry looks populated, and the reader has no way to know
which parts of the story were followed.

## What this can and cannot see

**Names, not referents.** A person is counted as named in a chapter when their
name (or an `aka`) appears there as a whole word. Where several people share a
name -- and dozens do -- the chapter is credited to all of them, so their reach
is overstated and their `missed` with it. Those rows are marked `amb`, and the
ranking is meant to be read with that in mind rather than trusted blind.

**It cannot see pronouns.** A chapter that is entirely about a person without
naming them does not count toward reach. This understates the gap for narrative
figures, which are exactly the figures this is for, so the true `missed` is
never smaller than the number printed.

**It does not know what a relation *should* be.** A chapter counts as held if
any relation cites it, whatever that relation says. One thin edge covers a
chapter as fully as ten. This finds silence, not thinness.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from .corpus import get_corpus
from .graph import Store


# A chapter where the person *does* something, as against one that merely says
# their name. The distinction decides how much work a figure actually needs:
# Abraham is named in 82 chapters and acts in about 21, because "the God of
# Abraham" and "the seed of Abraham" run through the whole canon. Reporting 63
# unfollowed chapters for him is true and useless; reporting six is actionable.
#
# The test is subject position -- the name followed by a verb. It is a
# heuristic and it overshoots: 25 against 21 counted by hand for Abraham, since
# "the seed of Abraham he took" reads the same way. Good enough to narrow a
# worklist, not good enough to score against, and the scoring bar the owner
# chose ("every chapter where they act") still needs a person to read the
# candidates.
_ACTED = re.compile(
    r"\s+(?:said|went|took|came|gave|rose|ran|stood|fell|bought|made|saw|sent"
    r"|spake|heard|knew|begat|built|builded|set|laid|put|told|brought|left"
    r"|held|drew|wrote|slew|smote|bare|led|kept|found|hid|dwelt|\w+ed)"
    r"(?![a-z])")


@dataclass
class Reach:
    """One person, how far they run in the text, and how far the graph went."""

    pid: str
    name: str
    verses: int                       # verses naming them anywhere
    reach: set[str] = field(default_factory=set)   # "Esth 2" etc
    held: set[str] = field(default_factory=set)
    shared_name: bool = False         # another person answers to this name
    eponym: bool = False              # a place or people carries the name too
    acting: set[str] = field(default_factory=set)  # chapters where they act

    @property
    def missed(self) -> set[str]:
        return self.reach - self.held

    @property
    def missed_acting(self) -> set[str]:
        """The worklist that matters: chapters they act in and nothing holds."""
        return self.acting - self.held

    @property
    def followed(self) -> float:
        return len(self.held) / len(self.reach) if self.reach else 1.0


def _chapter(ref: str) -> str:
    """'Esth 2:17' -> 'Esth 2'. Ranges and bare chapters both survive."""
    return ref.split(":", 1)[0].strip()


def survey(store: Store | None = None, min_verses: int = 8) -> list[Reach]:
    store = store or Store.load()
    corpus = get_corpus()

    # Every string that could point at a person, and who it could point at.
    # A name held by two people makes both of them ambiguous, which is recorded
    # rather than resolved -- resolving it is the anchor layer's job, not this
    # report's.
    claims: dict[str, list[str]] = defaultdict(list)
    for p in store.people.values():
        if p.type != "person":
            continue
        for label in [p.name] + list(p.aka or []):
            label = label.strip()
            if len(label) > 2 and label[0].isupper():
                claims[label].append(p.pid if hasattr(p, "pid") else p.id)

    # The eponymous ancestors are the loudest false signal here. Dan the man is
    # named in 46 chapters only because Dan the tribe and Dan the city are
    # spelled the same, and the same goes for Ephraim, Moab, Gilead, Canaan and
    # every other father of a people. Their reach is almost entirely their
    # descendants' and their `missed` is close to meaningless, so they are
    # flagged and can be excluded rather than left to head the list.
    elsewhere = {p.name.strip().lower() for p in store.people.values()
                 if p.type != "person"}
    for p in store.people.values():
        if p.type != "person":
            elsewhere.update(a.strip().lower() for a in (p.aka or ()))

    rows = {
        pid: Reach(pid, store.people[pid].name, 0,
                   shared_name=any(len(v) > 1 for k, v in claims.items()
                                   if pid in v),
                   eponym=store.people[pid].name.strip().lower() in elsewhere)
        for names in claims.values() for pid in names
    }

    # One pass over the corpus, tokenizing each verse once and looking the
    # tokens up. The first version compiled a pattern per name and ran all of
    # them against every verse -- around seventy million searches, which did
    # not finish. Whole words either way: "Ur" must not fire inside "Uriah".
    single = {k: v for k, v in claims.items() if " " not in k}
    multi = {k: v for k, v in claims.items() if " " in k}
    word = re.compile(r"[A-Za-z][A-Za-z'-]*")
    for v in corpus.iter_verses():
        ch = f"{v.id.book} {v.id.chapter}"
        hits: set[str] = set()
        acted: set[str] = set()
        for m in word.finditer(v.text):
            for pid in single.get(m.group(0), ()):
                hits.add(pid)
                if _ACTED.match(v.text[m.end():m.end() + 14]):
                    acted.add(pid)
        if multi:
            for label, pids in multi.items():
                # Multi-word names are few, so the scan is cheap, and the
                # first token is a fast reject for nearly all of them.
                if label.split()[0] in v.text and label in v.text:
                    hits.update(pids)
        for pid in hits:
            rows[pid].verses += 1
            rows[pid].reach.add(ch)
        for pid in acted:
            rows[pid].acting.add(ch)

    for rel in store.relations:
        for pid in (rel.src, rel.dst):
            if pid in rows:
                rows[pid].held.update(_chapter(r) for r in rel.refs)

    out = [r for r in rows.values() if r.verses >= min_verses]
    # Rank by how much was left behind, then by how prominent the person is --
    # ten unfollowed chapters of a major figure outrank ten of a minor one.
    out.sort(key=lambda r: (-len(r.missed), -r.verses))
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="People the corpus dwells on, and how far the graph "
                    "followed them.")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--min-verses", type=int, default=8)
    ap.add_argument("--unambiguous", action="store_true",
                    help="only people whose name no one else answers to")
    ap.add_argument("--no-eponyms", action="store_true",
                    help="drop people whose name is also a place or a people")
    ap.add_argument("--acting", action="store_true",
                    help="rank by chapters they act in, not chapters that "
                         "name them")
    ap.add_argument("--who", help="report one person by id")
    args = ap.parse_args(argv)

    rows = survey(min_verses=args.min_verses)

    if args.who:
        hit = [r for r in rows if r.pid == args.who]
        if not hit:
            print(f"no row for {args.who!r} (below --min-verses, or not a "
                  f"person)")
            return 1
        r = hit[0]
        print(f"{r.name} ({r.pid})")
        print(f"  named in {r.verses} verses across {len(r.reach)} chapters")
        print(f"  relations cite {len(r.held)} of them "
              f"({r.followed:.0%} followed)")
        if r.shared_name:
            print("  NOTE another person answers to this name, so the reach "
                  "above is an over-count")
        if r.eponym:
            print("  NOTE a place or a people carries this name too, so most "
                  "of the reach above is probably not about this person")
        print(f"  acts in {len(r.acting)} of them; "
              f"{len(r.missed_acting)} of those uncited")
        if r.missed_acting:
            print("  acts here and nothing records it:")
            print("   ", ", ".join(sorted(r.missed_acting)))
        if r.missed:
            print("  named here and nothing records it:")
            print("   ", ", ".join(sorted(r.missed)))
        return 0

    if args.unambiguous:
        rows = [r for r in rows if not r.shared_name]
    if args.no_eponyms:
        rows = [r for r in rows if not r.eponym]
    print(f"{len(rows)} people named in {args.min_verses}+ verses\n")
    if args.acting:
        rows = [r for r in rows if r.missed_acting]
        rows.sort(key=lambda r: (-len(r.missed_acting), -r.verses))
        print("  todo  acts  held  verses  who")
        for r in rows[: args.limit]:
            flag = ("".join([" amb" if r.shared_name else "",
                             " epon" if r.eponym else ""]))
            print(f"  {len(r.missed_acting):4}  {len(r.acting):4}  "
                  f"{len(r.held):4}  {r.verses:6}  {r.name}{flag}")
        return 0
    print("  missed  held  reach  verses  who")
    for r in rows[: args.limit]:
        flag = ("".join([" amb" if r.shared_name else "",
                         " epon" if r.eponym else ""]))
        print(f"  {len(r.missed):6}  {len(r.held):4}  {len(r.reach):5}  "
              f"{r.verses:6}  {r.name}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
