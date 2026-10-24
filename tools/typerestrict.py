"""Restrict each node's possible ontological types, from morphology alone.

2026-09-05: before the person relationships are added in again, take a
pass at type restricting all the nodes based on simple deterministic rules,
without accepting this blindly.

Not accepted blindly. The proposed ten-rule set targets the wrong layer.

## Why the proposed rules do not apply here

**They assign part of speech, which MACULA already states.** Deriving "earth is
a noun" from "it follows *the*" solves a problem we do not have, less reliably
than the tagging we already trust. Seven of the ten rules are POS inference.

**They are English word-order rules.** "A word immediately before a noun is an
adjective" — but Hebrew adjectives FOLLOW their noun (*ha-arets ha-gedolah*),
and Greek word order is free because case carries the role. Rule 1 claims to
hold "across English, Hebrew, Greek"; Hebrew's article is a prefix, so there is
no separate determiner word to follow.

**"Subjects are entities" is true and uninformative.** It does not say whether
the entity is a person, a place, or a concept, which is the typing problem we
actually have.

**One rule was right**: a vocative is a definite reference. The data refines it
— *brothers* (98) and *Men* (22) are vocatives addressing a specific GROUP, so
it is not "vocative implies instance" but "vocative implies definite
reference", which for a plural is a group.

## What this does instead

**Restricts** rather than assigns, which is the right word: each
signal removes candidate types, and a node ends with the set that survives.
That composes with the unresolved node — a node typed
`{person, place}` is honest, dispatchable, and narrowable later, where a node
wrongly typed `person` is silently wrong forever.

Every signal is stated in the morphology, not inferred from position:

    lexicon class     N:N-M-P person, N:N--L place, N:N-M-T deity,
                      N:N--PG people-group          5,258 lemmas
    proper            38,591 occurrences (22%)      not a concept
    vocative             565 (0.3%)                 definite reference
    plural            35,667 (20%)                  not a singular instance
    construct + proper 10,693                       a definite description
    pronominal suffix                               a specific possessed thing

    python tools/typing.py

## Result, and it is weak

    noun occurrences      174,736
    narrowed to ONE type   36,442   20%
    still 5 candidates    102,584   58%

**The 58% are common nouns**, where the only rule that fires is "not a named
person or deity", leaving {place, group, object, concept, event}. That is
barely a restriction. The lexicon class covers proper nouns only; for common
nouns the morphology states number and state and nothing ontological. This is
the open-vocabulary wall reached from a new direction, and the honest reading
is that deterministic typing gets 20% and stops.

## Two kinds of unresolved, and they are not the same

The remark that it also implies the node will be split in the future is right, and
it separates this from the person case:

    person-unresolved   {Zechariah-A, Zechariah-B}
                        the candidates ALREADY EXIST as nodes;
                        resolution is an assignment

    type-unresolved     {object, group}
                        the sense-nodes DO NOT exist yet;
                        resolution is a SPLIT that creates them

So a type-unresolved node is a placeholder for a future split rather than a
future label, and edges attached to it must be **redistributed** when it
splits. That is a real cost, and it is the one the change-set design already
absorbs: the split is a pass, and the edges recompute.
"""
from __future__ import annotations

import collections
import gzip
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from macula import MAC, _ref                                      # noqa: E402

OUT = ROOT / "out"
STEP = ROOT / "data" / "raw" / "stepbible"

# A seed vocabulary over the lexicon's own English glosses. The suggestion
# was that possible types or definitions for each word can be sourced from an
# external source — right, and I had stopped a step early. The Hebrew entries are
# short gloss chains ("crib, manger, feeding trough"; "reed, papyrus"), so a
# few hundred English type-words classify a third of them.
#
# **Loose on purpose.** Loose is fine at this stage, so as not to
# get stuck: the relationship work will help get unstuck. These are
# CANDIDATES fed into a restriction, not assignments, so a wrong seed widens
# the set rather than committing an error.
SEED = {
    "object": "vessel garment cloth stone wood tool weapon sword bow altar "
              "table door gate wall house tent chariot ship rod staff cup "
              "bowl basket crib manger trough ring chain pillar beam board "
              "plate net".split(),
    "plant": "tree plant vine grain wheat barley reed papyrus flower herb "
             "grass thorn fruit olive fig palm cedar".split(),
    "animal": "animal beast bird cattle sheep goat ox lion bear wolf serpent "
              "fish locust dove eagle horse donkey camel".split(),
    "place": "city town village land country region mountain hill valley "
             "river sea desert wilderness field border road way".split(),
    "person": "man woman king priest prophet servant slave son daughter "
              "father mother brother sister child elder judge".split(),
    "concept": "destruction love hatred fear joy sorrow wisdom folly "
               "righteousness sin guilt truth peace war justice glory "
               "strength faithfulness".split(),
    "body": "hand foot head eye ear mouth heart soul flesh bone blood arm "
            "face tongue".split(),
}
SEEDWORD = {w: t for t, ws in SEED.items() for w in ws}

# Anything concrete can be used as an image, and Thursday's measurement found
# 48 words the old graph typed BOTH ways. The decision was to mark uncertainty
# around thing or image_of. So `object` is almost never the honest answer on
# its own -- it is {object, image_of} until an occurrence decides.
CONCRETE = {"object", "plant", "animal", "place", "body"}

ALL = {"person", "place", "deity", "group", "object", "concept", "event",
       "plant", "animal", "body", "image_of"}
LEXCLASS = {"P": "person", "L": "place", "T": "deity",
            "PG": "group", "LG": "group"}


def lexicon():
    """Strong number -> the class the lexicon states for it."""
    out = {}
    for f in sorted(STEP.glob("TBES*")):
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                c = line.rstrip("\n").split("\t")
                if len(c) > 5 and re.match(r"^[HG]\d{4}", c[0].strip()):
                    m = re.match(r"^N:N-?([MF]?)-?(P|L|T|PG|LG|TG)?G?$",
                                 c[5].strip())
                    if m and m.group(2):
                        out.setdefault(re.sub(r"[^0-9]", "", c[0].strip()),
                                       LEXCLASS.get(m.group(2)))
    return {k: v for k, v in out.items() if v}


def lex_types():
    """Candidate types from the lexicon's English gloss, via the seed words."""
    out = {}
    for f in sorted(STEP.glob("TBESH*")):
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                c = line.rstrip("\n").split("\t")
                if (len(c) > 7 and re.match(r"^H\d{4}", c[0].strip())
                        and c[5].strip().startswith("H:N")):
                    txt = ((c[6] or "") + " "
                           + re.sub(r"<[^>]*>", " ", c[7])[:120]).lower()
                    got = {SEEDWORD[x] for x in re.findall(r"[a-z]+", txt)
                           if x in SEEDWORD}
                    if got:
                        out.setdefault(re.sub(r"[^0-9]", "", c[0].strip()),
                                       got)
    return out


LEXTYPES = {}


def restrict(w, lex):
    """The types this word could still be, and what ruled the others out."""
    cand, why = set(ALL), []
    num = re.sub(r"[^0-9]", "",
                 w.get("strongnumberx") or w.get("strong") or "")
    proper = (w.get("type") or "").lower() == "proper" or \
             (w.get("class") or "").lower() == "name"

    known = lex.get(num)
    if known and proper:
        cand &= {known}
        why.append(f"lexicon says {known}")

    if proper:
        cand -= {"concept", "event"}
        why.append("proper noun: not a concept")
    # NO restriction for a common noun. The first version removed person and
    # deity, conflating "not a NAMED person" with "not a person" -- but king,
    # servant, priest and man are common nouns denoting people, and *elohim*
    # and *theos* are common nouns denoting God. That rule emptied 18,635
    # candidate sets when the lexicon then suggested `person`.

    if (w.get("number") or "").lower() == "plural" and "group" in cand:
        cand -= {"object"}
        why.append("plural: a collection rather than one object")

    if (w.get("case") or "").lower() == "vocative":
        cand -= {"concept", "event", "object"}
        why.append("vocative: a definite reference, addressed")

    # types the lexicon's own gloss suggests, as candidates
    if not proper:
        sug = LEXTYPES.get(num)
        if sug:
            # Narrow only if something survives. An intersection that empties
            # asserts the node can be NOTHING, which is false and worse than
            # leaving it wide -- 18,635 nodes came out with zero candidates
            # before this guard. Loose is acceptable; empty is an error.
            keep = cand & (set(sug) | {"image_of"})
            if keep:
                cand = keep
                why.append("lexicon gloss suggests "
                           + "/".join(sorted(sug)))
            else:
                cand |= set(sug)
                why.append("lexicon gloss disagrees with the morphology; "
                           "widened rather than emptied")

    # a concrete thing can always be used as an image; that stays open until
    # an occurrence decides it
    if cand & CONCRETE:
        cand |= {"image_of"}
        why.append("concrete: could be the thing or an image of it")
    elif len(cand) > 1:
        cand -= {"image_of"}

    return cand, why


def main() -> int:
    lex = lexicon()
    LEXTYPES.update(lex_types())
    stats = collections.Counter()
    sizes = collections.Counter()
    out = []
    for f in sorted(MAC.rglob("*.xml")):
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for w in root.iter("w"):
            if (w.get("class") or w.get("pos")) != "noun":
                continue
            cand, why = restrict(w, lex)
            stats["nouns"] += 1
            sizes[len(cand)] += 1
            if len(cand) == 1:
                stats["resolved"] += 1
            out.append({"ref": _ref(w.get("ref") or ""),
                        "text": (w.get("english") or w.get("gloss") or "")
                        .strip(),
                        "types": sorted(cand), "why": why})
    path = OUT / "node-types.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("TYPE RESTRICTION — narrowing, not assigning")
    print(f"  noun occurrences        {stats['nouns']:>8,}")
    print(f"  narrowed to ONE type    {stats['resolved']:>8,}   "
          f"{100*stats['resolved']//max(stats['nouns'],1)}%")
    print()
    print("  candidates remaining, by count:")
    for k in sorted(sizes):
        print(f"    {k} type(s){'':4}{sizes[k]:>8,}  "
              f"{100*sizes[k]//max(stats['nouns'],1):>3}%")
    print(f"\n  wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
