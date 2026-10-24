"""Where the text says two names are one person.

Abram/Abraham, Saul/Paul, Simon/Peter, Hadassah/Esther, Hananiah/Shadrach.
A missing alias is quiet in a way that matters twice over: search for the name
a reader knows returns nothing, and the prominence report undercounts the
person's reach, because reach is measured on the names the graph holds.

Neither the validator nor the consolidation check can find these. The
consolidator looks for two records that should be one; an alias is one record
that should answer to two names, and nothing about it looks wrong.

So this is found the same way the citation formulas were: not by deciding who
is whom, but by reading the places where the corpus says so itself.

    thy name shall be called          Gen 17:5, Gen 32:28
    called his name                   Gen 41:45
    which/who is called               John 11:16, Acts 13:9
    surnamed                          Mark 3:16
    that is                           Esth 2:7
    the same is                       Ezra 10:23

## What this is not

**It is not a merge proposal.** A verse saying "Thomas, which is called
Didymus" establishes an alias. Two accounts of one event using two names --
Matthew at Matt 9:9 and Levi at Mark 2:14 -- establish nothing, however
strongly the tradition reads them together, and no formula in the corpus joins
them. Those stay apart, and the fact that they stay apart is the point.

**It cannot resolve which person.** "Called his name Joseph" tells you a name
was given, not which Joseph in the graph received it. The report pairs the
names and leaves the identification to a reader, which is why it prints the
verse.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .corpus import get_corpus
from .graph import Store

NAME = r"[A-Z][A-Za-z']+(?:-[A-Za-z]+)?"

# Each pattern yields (old, new) or (new,) with the old name taken from earlier
# in the verse. Ordered most specific first; a verse can match several and
# every distinct pair is kept.
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # The renaming proper, and the first pass missed every canonical case --
    # Abram, Sarai, Jacob -- because the KJV builds it four ways and I had
    # encoded one. What they share is "not called X ... but Y", with the
    # negation, the auxiliary and the intervening words all moving around:
    #
    #   Neither shall thy name any more be called Abram, but thy name
    #     shall be Abraham                                        (Gen 17:5)
    #   Thy name shall be called no more Jacob, but Israel       (Gen 32:28)
    #   Thy name shall not be called any more Jacob, but Israel
    #     shall be thy name                                      (Gen 35:10)
    #
    # So the optional parts are all made optional rather than enumerated, and
    # the "but" is what anchors it.
    (re.compile(r"name\s+(?:any more\s+|no more\s+)?(?:shall\s+|shalt\s+)?"
                r"(?:not\s+)?(?:be\s+)?call(?:ed)?\s+"
                r"(?:no more\s+|any more\s+)?(" + NAME + r")\b"
                r"[^.;:]{0,30}?,?\s+but\s+"
                r"(?:(?:thy|his|her) name shall be\s+)?(" + NAME + r")"),
     "rename"),
    # "thou shalt not call her name Sarai, but Sarah shall her name be."
    # The same statement with the possessive ahead of the name instead of
    # behind it, which the pattern above cannot reach.
    (re.compile(r"call\s+(?:his|her|their|thy)\s+name\s+(" + NAME + r")"
                r"\b[^.;:]{0,30}?,?\s+but\s+(" + NAME + r")"), "rename"),
    # "turned his name to Jehoiakim" (2Kgs 23:34), "changed his name to
    # Zedekiah" (2Kgs 24:17). The old name is the subject several clauses
    # back -- Eliakim, Mattaniah -- and the nearest preceding proper noun is
    # the wrong one in both verses, so only the new name is captured and the
    # row is flagged for a reader.
    (re.compile(r"(?:turned|changed)\s+(?:his|her|their)\s+name\s+(?:un)?to\s+"
                r"(" + NAME + r")"), "rename"),
    # "he called his name Israel"; "Pharaoh called Joseph's name Zaphnath-
    # paaneah". The naming formulas: most are birth names and not aliases at
    # all, which is why the report separates them out.
    (re.compile(r"called\s+(?:his|her|their|the child's)\s+name\s+("
                + NAME + r")"), "named"),
    (re.compile(r"called\s+(" + NAME + r")'s name\s+(" + NAME + r")"),
     "rename"),
    # "Thomas, which is called Didymus"; "Saul, (who also is called Paul,)";
    # "Simon, whom he surnamed Peter".
    (re.compile(r"(" + NAME + r"),?\s*\(?(?:which|who|whose surname)"
                r"(?:\s+also)?\s+is(?:\s+also)?\s+called\s+(" + NAME + r")"),
     "alias"),
    (re.compile(r"(" + NAME + r"),?\s+(?:whom he |he )?surnamed\s+("
                + NAME + r")"), "alias"),
    (re.compile(r"(" + NAME + r"),?\s+surname was\s+(" + NAME + r")"),
     "alias"),
    # "Hadassah, that is, Esther"; "Kelaiah, (the same is Kelita)".
    (re.compile(r"(" + NAME + r"),\s+that is,?\s+(" + NAME + r")"), "alias"),
    (re.compile(r"(" + NAME + r"),?\s*\(?the same is\s+(" + NAME + r")"),
     "alias"),
    # Daniel 1:7 renames four men in one verse and does it in a shorthand
    # nothing else in the corpus uses: after the first name is given
    # ("the name of Belteshazzar"), the rest follow as "to Hananiah, of
    # Shadrach", and so on for Mishael and Azariah (the BSB reads "To Daniel
    # he gave the name Belteshazzar; to Hananiah, Shadrach"). The bare "to X, of Y" is far too loose to
    # run unguarded, so both forms are gated on the verse announcing itself.
    (re.compile(r"(?:unto|to)\s+(" + NAME + r")\s+the name of\s+("
                + NAME + r")"), "alias"),
    (re.compile(r"(?:and\s+)?to\s+(" + NAME + r"),\s+of\s+(" + NAME + r")"),
     "alias"),
]

# The two Daniel 1:7 patterns above only run on a verse that says it is doing
# this. Without the gate, "and to Aaron, of the tribe of Levi" reads as a
# renaming.
_GATED = {-1, -2}
_GATE = re.compile(r"gave\s+names|the name of", re.I)

# "Called" is a busy word. These are the readings that are not naming at all,
# and admitting them buries the real aliases: a summons, a vocation, a title
# applied rather than a name given.
_NOT_A_NAME = re.compile(
    r"called (?:to|unto|for|upon|out|after|him|them|his servants|the name of "
    r"the Lord)", re.I)


@dataclass
class Alias:
    """One place the text puts two names on one person."""

    verse: str
    pretty: str
    kind: str        # alias | rename | named
    left: str
    right: str
    text: str
    # True when the left capture is the object of "of" -- "the land of Canaan"
    # followed by "that is, Beth-el", where the name joined to Beth-el is Luz and Canaan is
    # a modifier three words away from it. Walking back to the previous proper
    # noun fixes Genesis 35:6 and breaks Luke 2:4, where the subject is the
    # phrase "the city of David" and not a name at all. So it is flagged
    # rather than guessed.
    left_qualified: bool = False


_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _proper_nouns() -> set[str]:
    """Words the corpus never writes in lower case.

    The same test `gaps.py` uses, for the same reason. Without it Mark 7:34 --
    "Ephphatha, that is, Be opened" -- reads as an alias, because the formula
    that joins two names is also the formula that glosses a foreign word, and
    "Be" is capitalised there like any other sentence opener. A word that
    appears in lower case anywhere in the corpus is not a name.
    """
    corpus = get_corpus()
    lower: set[str] = set()
    upper: set[str] = set()
    for v in corpus.iter_verses():
        for w in _WORD.findall(v.text):
            (upper if w[0].isupper() else lower).add(w.lower())
    return {w for w in upper if w not in lower}


# "a city of Samaria", then "which is called Sychar", is containment, not naming --
# Sychar is one city among many in Samaria. "the city of David, which is called
# Bethlehem" is naming. The article carries the whole distinction, so it is
# what gets tested.
_INDEFINITE = re.compile(r"\ba (?:city|town|place|village) of\s*$", re.I)

# The left capture sitting in an "of" phrase, where it modifies the real
# subject instead of being it.
_OF = re.compile(r"\bof\s+$", re.I)


def survey() -> list[Alias]:
    corpus = get_corpus()
    proper = _proper_nouns()
    out: list[Alias] = []
    seen: set[tuple[str, str, str]] = set()
    for v in corpus.iter_verses():
        for idx, (rx, kind) in enumerate(PATTERNS):
            if idx - len(PATTERNS) in _GATED and not _GATE.search(v.text):
                continue
            for m in rx.finditer(v.text):
                groups = [g for g in m.groups() if g]
                if len(groups) == 2:
                    left, right = groups
                elif kind == "rename" and len(groups) == 1:
                    # "thy name shall be called Abraham" -- the old name is the
                    # subject somewhere earlier in the verse, and this cannot
                    # see it. Kept, with the left side blank, because a reader
                    # checking Genesis 17 wants the row.
                    left, right = "", groups[0]
                else:
                    continue
                if left == right:
                    continue
                if kind == "named" and _NOT_A_NAME.search(v.text):
                    continue
                # Both sides have to be names. Multi-word right sides are
                # tested word by word, so "Be opened" fails on both.
                if any(w.lower() not in proper
                       for side in (left, right) if side
                       for w in _WORD.findall(side)):
                    continue
                if left and _INDEFINITE.search(v.text[: m.start(1)]):
                    continue
                key = (str(v.id), left, right)
                if key in seen:
                    continue
                seen.add(key)
                out.append(Alias(str(v.id), v.id.pretty(), kind, left, right,
                                 v.text,
                                 left_qualified=bool(
                                     left and _OF.search(v.text[: m.start(1)]))))
    return out


def audit(store: Store | None = None) -> list[tuple[Alias, str]]:
    """Pair each stated alias with what the graph does about it."""
    store = store or Store.load()
    holds: dict[str, set[str]] = {}
    for p in store.people.values():
        labels = {p.name.strip()} | {a.strip() for a in (p.aka or ())}
        for label in labels:
            holds.setdefault(label, set()).update(labels)

    rows = []
    for a in survey():
        if a.kind == "named":
            continue
        if not a.left:
            # "changed his name to Zedekiah" -- the old name is clauses away
            # and the nearest proper noun is the wrong one. All that can be
            # checked is whether the new name reached the graph at all, which
            # is still worth checking: it is the name the rest of the corpus
            # will use from here on.
            rows.append((a, "new name is held" if a.right in holds else
                         "absent: " + a.right + " (the old name is elsewhere "
                         "in the verse -- check by hand)"))
            continue
        if a.right in holds.get(a.left, ()):
            verdict = "held"
        elif a.left_qualified:
            verdict = ("check by hand: '" + a.left + "' is the object of "
                       "'of' here, so the name joined to '" + a.right
                       + "' is elsewhere in the verse")
        elif a.left not in holds and a.right not in holds:
            verdict = "neither name is in the graph"
        elif a.left not in holds:
            verdict = "absent: " + a.left + " (the graph has " + a.right + ")"
        elif a.right not in holds:
            verdict = "absent: " + a.right + " (the graph has " + a.left + ")"
        else:
            # Both strings exist on records that are not linked. That is not
            # proof of a split: Colossians 4:11's Jesus is not Jesus Christ,
            # and the graph is right to keep them apart. The report says what
            # it saw and asks rather than asserts.
            verdict = ("unlinked: both names are in the graph on separate "
                       "records -- one person, or two sharing a name?")
        rows.append((a, verdict))
    return rows


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Names the text joins, and whether the graph joined them.")
    ap.add_argument("--all", action="store_true",
                    help="every match, including birth names")
    ap.add_argument("--held", action="store_true",
                    help="include the ones already carried")
    args = ap.parse_args(argv)

    if args.all:
        rows = survey()
        print(str(len(rows)) + " statements of naming\n")
        for a in rows:
            print(" " + a.pretty.ljust(14) + a.kind.ljust(7)
                  + (a.left + " = " + a.right if a.left else "-> " + a.right))
        return 0

    rows = audit()
    bad = [r for r in rows if r[1] != "held"]
    print(str(len(rows)) + " stated aliases; " + str(len(rows) - len(bad))
          + " held, " + str(len(bad)) + " not\n")
    for a, verdict in rows:
        if verdict == "held" and not args.held:
            continue
        print(" " + a.pretty.ljust(14) + verdict)
        print("   " + a.text[:150])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
