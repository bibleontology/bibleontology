"""A passage as a mermaid diagram.

On the hand-built Genesis 1-4 diagrams, the response was that they were easy
to consume, and that their immediate value is that they keep the reviewer in
the loop by showing whether the work is working.

That second point is why this is a module rather than something assembled by
hand each time. **The most valuable finding of 2026-08-30 came from looking at
a picture, not from a measurement.** Every mechanical check called Genesis 1-4
healthy -- 0.0% level-skips, zero validation errors, six suites green -- and
then a person looked at the diagram and said the fall was not in the document.
Gen 3:6 had produced one relation, `adam -spouse_of-> eve`.

The project's written rules already carry this, under what validation cannot
see: *only a person reading the source finds absence*. What a drawing adds is
scale. Nobody reads 16,124 relations; anybody can look at twenty and notice
what is missing.

## Why it must be generated rather than curated

A hand-made diagram shows what its author chose to show. That is exactly the
wrong place for judgement in an instrument meant to catch what its author
missed. This one applies fixed rules and draws what is there.

## Why mermaid

The graph already emits it. A relation is `src -[type]-> dst`, which is a
mermaid edge with no translation layer, so drawing is a formatting pass rather
than a conversion. It is also text, so it diffs, generates server-side, and
degrades to something readable when it fails.

## Filtering is load-bearing, not cosmetic

Dropping `speaks_of` removed 148 of Genesis 4's 185 relations and left the
spine. Genesis 1's raw 223 would be unreadable at any size. Ten to twenty nodes
is the ceiling, and what survives is chosen by rule -- never by taste.

## The honesty requirement

A diagram is more persuasive than a table and therefore more dangerous when it
is wrong. **Absence must look like absence.** A thin chapter draws thin, and
this module says so in the caption rather than composing around the hole -- if
the Genesis page had tidied away its under-extracted chapter 2, the one thing
worth finding would have been the thing hidden.
"""

from __future__ import annotations

import re
import sys
from collections import Counter

# Relations that describe where words are rather than what happened. They are
# the bulk of most passages and none of the signal; see the level-skip work.
NOISE = {"speaks_of"}

# Drawn dotted, because a verdict is a different kind of claim from an act and
# the difference is what makes a passage legible at a glance -- two offerings,
# two verdicts, one accepted.
VERDICT = {"assessed_as", "described_as", "titled", "likened_to"}

# Structural rather than narrative: true, and not what a reader came for.
QUIET = {"part_of", "instance_of", "composed_of", "member_of"}

MAX_EDGES = 24

_ID = re.compile(r"[^a-z0-9_]")


def _safe(node_id: str) -> str:
    """A mermaid-safe node id. Mermaid chokes on punctuation in identifiers."""
    return _ID.sub("_", node_id.lower())[:40] or "n"


# Characters per line inside a box before wrapping. Mermaid sizes the box to
# its longest line, so this is what actually controls box width.
WRAP = 22

# Lines before a label is genuinely too long to draw. Three lines of 22 is 66
# characters, which covers all but the compound assessments -- and those are a
# defect the linter already reports rather than something to design around.
MAX_LINES = 3


def _label(entity, node_id: str) -> str:
    """What to write in the box, WRAPPED rather than cut.

    Truncating was the first version and it was wrong for this tool
    specifically. "one that feared God and eschewed evil" clipped to "one that
    feared God and es..." hides the words a reader opened the diagram to see,
    and an instrument built to reveal what is missing must not manufacture
    absences of its own.

    Mermaid accepts `<br/>` inside a label and sizes the box to its longest
    line, so wrapping costs width rather than meaning. Only a label past three
    lines is shortened, and by then the node itself is the problem: names that
    long are the compound-assessment defect the linter already reports.
    """
    name = (getattr(entity, "name", None) or node_id.replace("_", " ")) if entity else \
        node_id.replace("_", " ")
    # Quotes and pipes both break mermaid's label parsing.
    name = name.replace('"', "'").replace("|", "/").strip()
    if len(name) <= WRAP:
        return name

    lines, current = [], ""
    for word in name.split():
        if current and len(current) + 1 + len(word) > WRAP:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)

    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES]
        lines[-1] = lines[-1].rstrip() + "..."
    return "<br/>".join(lines)


def from_batch(name: str):
    """Entities and relations from an unmerged proposal or staging batch.

    **Added because every diagram drawn today came from the merged graph while
    being described as current.** The fresh Genesis and Job batches sat in
    proposals with zero `asserted_by` relations reaching the merged file, so
    the generator showed yesterday's extraction and said nothing about it.

    For an instrument whose entire purpose is showing what is actually there,
    silently reading the wrong source is the worst defect available to it.
    """
    import dataclasses
    import json as _json
    from pathlib import Path as _Path

    from .paths import ROOT
    from .schema import Entity, Relation, canonical_fields, load_entities

    d = ROOT / "ontology" / "proposals" / name
    if not d.is_dir():
        d = ROOT / "ontology" / "staging" / name
    if not d.is_dir():
        raise SystemExit(f"no batch called {name!r} in proposals or staging")

    known = {f.name for f in dataclasses.fields(Entity)}
    rel_known = {f.name for f in dataclasses.fields(Relation)}
    ents = dict(load_entities())          # the graph, as the fallback lookup
    for line in (d / "entities.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = canonical_fields(_json.loads(line))
        extra = {k: v for k, v in row.items() if k not in known}
        kept = {k: v for k, v in row.items() if k in known}
        if extra:
            kept.setdefault("attrs", {}).update(extra)
        ents[kept["id"]] = Entity(**kept)
    rels = []
    for line in (d / "relations.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = canonical_fields(_json.loads(line))
        rels.append(Relation(**{k: v for k, v in row.items() if k in rel_known}))
    return ents, rels


def relations_for(ref: str, entities=None, relations=None) -> list:
    """Every relation citing anywhere inside this reference."""
    from .corpus import get_corpus
    from .refs import RefError, parse_ref
    from .schema import load_relations

    relations = load_relations() if relations is None else relations
    try:
        want = {str(v) for v in get_corpus().expand(parse_ref(ref, allow_book=True))}
    except RefError:
        return []
    out = []
    for r in relations:
        if any(str(x) in want for x in (r.refs or [])):
            out.append(r)
    return out


def choose(rels: list, entities, limit: int = MAX_EDGES) -> tuple[list, dict]:
    """Which relations to draw, and what was left out.

    Rules, in order, so the result does not depend on who ran it:

      1  drop the noise relations outright
      2  prefer edges between things a reader recognises -- a person, a place,
         an event -- over edges into the concept layer
      3  drop duplicates, which the extractor emits freely
      4  keep verdicts, because they carry the passage's judgement
      5  cap, and report the cap
    """
    solid = {"person", "being", "place", "object", "group", "creature", "event"}

    def kind(node_id: str) -> str:
        e = entities.get(node_id)
        return e.type if e else "?"

    seen = set()
    scored = []
    for r in rels:
        if r.type in NOISE:
            continue
        key = (r.src, r.type, r.dst)
        if key in seen:
            continue
        seen.add(key)
        # Higher is drawn first.
        s = 0
        if kind(r.src) in solid and kind(r.dst) in solid:
            s += 3
        if r.type in VERDICT:
            s += 2
        if r.type in QUIET:
            s -= 2
        scored.append((s, r))
    scored.sort(key=lambda x: -x[0])

    # A CAP PER CATEGORY, and it is the whole difference between a useful
    # drawing and a useless one.
    #
    # Two wrong answers first. With no cap, Genesis 4 drew as a family tree:
    # Adam to Seth, Seth to Enos, Adah to Jabal, twelve kinship edges and one
    # narrative one. The offerings, the verdicts, the curse, the mark and Nod
    # were all cut, because every kinship edge joins two people so the
    # solid-to-solid bonus applied to all of them at once.
    #
    # Capping per TYPE then failed for a subtler reason: kinship is four types
    # -- father_of, mother_of, sibling_of, spouse_of -- so three each handed it
    # twelve slots and the family tree came straight back.
    #
    # Capped by CATEGORY, not by type. Capping types was the second wrong
    # answer: kinship is four types -- father_of, mother_of, sibling_of,
    # spouse_of -- so a cap of three per type handed it twelve slots and the
    # family tree came back. The vocabulary already groups relations, and the
    # group is what a reader perceives as "more of the same".
    from .schema import load_vocabulary

    vocab = load_vocabulary().types

    def group_of(rel_type: str) -> str:
        t = vocab.get(rel_type)
        return getattr(t, "category", None) or rel_type

    per_group = 3
    used: Counter = Counter()
    kept = []
    for _, r in scored:
        if used[group_of(r.type)] >= per_group:
            continue
        used[group_of(r.type)] += 1
        kept.append(r)
        if len(kept) >= limit:
            break
    # If a passage genuinely has few types, fill the remaining room rather than
    # drawing a near-empty diagram out of principle.
    if len(kept) < limit:
        for _, r in scored:
            if r in kept or used[group_of(r.type)] >= per_group * 2:
                continue
            used[group_of(r.type)] += 1
            kept.append(r)
            if len(kept) >= limit:
                break
    dropped = {
        "noise": sum(1 for r in rels if r.type in NOISE),
        "duplicate": len(rels) - len(seen) - sum(1 for r in rels if r.type in NOISE),
        "over_cap": max(0, len(scored) - limit),
    }
    return kept, dropped


def mermaid(ref: str, limit: int = MAX_EDGES, direction: str = "LR",
            batch: str | None = None) -> str:
    """A passage as mermaid source."""
    from .schema import load_entities

    if batch:
        entities, rels_all = from_batch(batch)
        rels = relations_for(ref, entities, rels_all)
    else:
        entities = load_entities()
        rels = relations_for(ref, entities)
    kept, dropped = choose(rels, entities, limit)

    lines = [f"graph {direction}"]
    if not kept:
        lines.append(f'  empty["{ref} — nothing extracted"]')
        return "\n".join(lines)

    drawn: set = set()
    for r in kept:
        for node in (r.src, r.dst):
            if node in drawn:
                continue
            drawn.add(node)
            e = entities.get(node)
            label = _label(e, node)
            shape = (f'(("{label}"))' if e is not None and e.type == "being"
                     else f'{{{{"{label}"}}}}' if e is not None and e.type == "assessment"
                     else f'["{label}"]')
            lines.append(f"  {_safe(node)}{shape}")
    for r in kept:
        arrow = "-.->" if r.type in VERDICT else "-->"
        lines.append(f"  {_safe(r.src)} {arrow}|{r.type.replace('_', ' ')}| {_safe(r.dst)}")
    return "\n".join(lines)


def _msg(text: str) -> str:
    """Make a label safe to sit after the colon in a sequence line.

    On the 50-chapter render a number of diagrams failed with "Syntax error
    in text". Mermaid 10 parses a sequence line as
    `A->>B: message`, and the message runs to end of line -- so anything in it
    that the parser also treats as punctuation ends the statement early and
    the whole diagram fails, not just that line.

    Two offenders, both from quoting scripture into a label:

        ;   a statement separator. 79 across Genesis, the first at Gen 3:16,
            "I will sharply increase your pain in childbirth;"
        :   a second colon, 133 of them, which re-opens the message parse.

    Neither is the extractor's fault. The King James punctuates heavily and
    these are real verse text; the view is what has to cope. Replaced rather
    than stripped, so the label still reads as a sentence -- a semicolon
    becomes a comma because that is what it is doing, and a stray colon
    becomes a dash.

    `<br/>` goes too: it is the class view's line break and is literal text
    inside a sequence message.
    """
    s = (text or "").replace("<br/>", " ")
    s = s.replace(";", ",").replace(":", " -")
    s = s.replace("#", "no.")          # starts an entity code in mermaid
    return " ".join(s.split())


def sequence(ref: str, limit: int = 40, batch: str | None = None) -> str:
    """A passage's dialogue as a mermaid sequence diagram.

    The framing, and it is exact, is sequence diagrams versus class diagrams
    in UML. A class diagram cannot show a protocol and a
    sequence diagram cannot show inheritance; neither derives from the other,
    which is why both are needed here.

    **This vindicates data I had written off.** The 109 `told` edges around
    Job's friends were dismissed as a useless speaker index -- "Bildad said
    verse 8:3" says nothing about Bildad's argument. That judgement was correct
    for a class diagram and wrong as a verdict on the data: 228 told-edges
    collapse to 33 ordered turns, and the exchange between God and the
    adversary in Job 1-2 comes out in exactly the right order. It was never
    useless; it was the wrong projection.

    Order is the whole point. The object-centred view is atemporal and shows
    Job's contradictory claims as two edges on one node, with nothing to say
    that one came after the other or that the distance between them is the
    book. Here the sequence IS the axis, so development is visible.
    """
    import re as _re

    from .corpus import get_corpus
    from .refs import RefError, parse_ref
    from .schema import load_entities, load_relations

    if batch:
        entities, all_rels = from_batch(batch)
    else:
        entities, all_rels = load_entities(), load_relations()
    try:
        want = {str(v) for v in get_corpus().expand(parse_ref(ref, allow_book=True))}
    except RefError:
        return "sequenceDiagram\n  Note over x: unparseable reference"

    def at(r):
        """Where in the passage this relation belongs, for ordering.

        **The LAST cited verse, not the first, and not whichever the list
        happens to start with.** This used to return the first match in
        `refs` order and put Genesis 39 out of sequence in a way a reviewer spotted
        immediately: Potiphar imprisoned Joseph as step one and appointed him
        as step four, which is backwards and is the whole story inverted.

        The cause is a convention the extractor follows deliberately and
        well. Where an act needs setting up, it cites the setup verse AND the
        verse where the act lands -- `potiphar -imprisoned-> joseph` carries
        Gen 39:1, which is where Potiphar is introduced as the man who bought
        him, and Gen 39:20, which is the imprisonment. Its own notes say so
        elsewhere: *"Matthew 10:34 is mid-charge; 10:5 names the speaker."*

        So the earliest citation is routinely the introduction and the latest
        is the moment. Sorting by the earliest sorts by the wrong one every
        time the convention is used, which is exactly where a sequence
        diagram is being asked to do work.

        This is a heuristic and the underlying data is the real fix: Gen 39:1
        does not support `imprisoned` and should not be cited by it. But a
        view has to order what it is given, and given a spread, the act is at
        the end of it.
        """
        found = []
        for x in (r.refs or []):
            if str(x) in want:
                m = _re.match(r"^(.+) (\d+):(\d+)", str(x))
                if m:
                    found.append((int(m.group(2)), int(m.group(3)), str(x)))
        return max(found) if found else None

    # A turn is recorded two ways round and BOTH have to be read.
    #
    #   speaker -told-> speech          the older form
    #   speech -asserted_by-> speaker   the newer one
    #
    # Measured on the Genesis 1-4 batch: told 6, asserted_by 87. The new
    # relation almost entirely displaced the old, and the split between them
    # is arbitrary because nothing ever said how they relate. Reading only
    # `told` made the temptation invisible -- serpent, woman, serpent, the
    # most consequential exchange in Genesis, absent from the dialogue view
    # while sitting in the graph the other way up.
    turns = []
    for r in all_rels:
        if r.type in ("told", "answered"):
            speaker, said = r.src, r.dst
        elif r.type == "asserted_by":
            speaker, said = r.dst, r.src
        else:
            continue
        e = entities.get(speaker)
        if not e or e.type not in ("person", "being", "group"):
            continue
        pos = at(r)
        if pos:
            turns.append((pos, speaker, said, r.type))
    turns.sort(key=lambda t: t[0][:2])

    # ACTIONS, not only speech. This is the correction made on seeing the
    # first version: the Genesis diagrams were focused on speech where action
    # was expected, with connections showing events rather than disconnected
    # verticals (eve-ate-fruit, then adam-ate-fruit).
    #
    # The correction was right. Reading only `told`, `answered` and `asserted_by` turned
    # Genesis 3 into a list of who spoke, when the chapter is a sequence of
    # ACTS -- she took, she ate, she gave, he ate -- and the speech is what
    # surrounds them. A narrative sequence has to carry both, in one order.
    #
    # And a `Note over` is not a connection. Every note is a mark on one
    # lifeline, so a page of them is a column of disconnected ticks with no
    # relationship drawn at all. An arrow between two lifelines is the thing a
    # sequence diagram is FOR.
    for r in all_rels:
        if r.type in NOISE or r.type in QUIET:
            continue
        if r.type in ("told", "answered", "asserted_by"):
            continue                       # already gathered above
        pos = at(r)
        if pos:
            turns.append((pos, r.src, r.dst, r.type))
    turns.sort(key=lambda t: t[0][:2])

    # Dedup before collapsing. The extractor emits the same relation several
    # times -- Gen 3:13 arrived five times in one batch -- and each duplicate
    # would otherwise draw its own arrow.
    seen_turn = set()
    ordered = []
    for pos, src, dst, rtype in turns:
        key = (pos[0], pos[1], src, dst, rtype)
        if key in seen_turn:
            continue
        seen_turn.add(key)
        ordered.append((pos, src, dst, rtype))
    ordered = ordered[:limit]
    if not ordered:
        return f"sequenceDiagram\n  Note over none: nothing extracted for {ref}"

    # Lifelines are the things that ACT or are acted upon more than once.
    # Everything touched only once becomes part of a label instead, because a
    # participant column that receives one arrow costs more width than it earns.
    from collections import Counter as _C

    seen_count: _C = _C()
    for _, src, dst, _t in ordered:
        seen_count[src] += 1
        seen_count[dst] += 1
    who = [n for n, c in seen_count.most_common() if c > 1][:6]
    for _, src, _d, _t in ordered:
        if src not in who and len(who) < 7:
            who.append(src)

    lines = ["sequenceDiagram"]
    for w in who:
        e = entities.get(w)
        lines.append(f"  participant {_safe(w)} as {_msg(_label(e, w))}")

    for (ch, vs, cite), src, dst, rtype in ordered:
        verb = rtype.replace("_", " ")
        if src in who and dst in who:
            lines.append(f"  {_safe(src)}->>{_safe(dst)}: {vs}. {verb}")
        elif src in who:
            e = entities.get(dst)
            lines.append(f"  Note over {_safe(src)}: "
                         f"{vs}. {verb} {_msg(_label(e, dst))}")
    return "\n".join(lines)


def suits_sequence(ref: str, batch: str | None = None) -> tuple[bool, str]:
    """Whether a passage has enough happening to be worth a sequence view.

    The sequence diagram is shown only when events are present, as that is
    what it captures well. That is decidable rather than a judgement. A sequence diagram
    draws ARROWS BETWEEN PARTICIPANTS. Where a passage has few of those it
    degenerates into a column of notes on single lifelines -- disconnected
    verticals, which is exactly the complaint that prompted the rewrite.

    So the view is offered where the passage earns it:

      Genesis 3   she took, she ate, she gave, he ate, God called, God cursed
                  -- events between parties throughout. Sequence.
      Job 3       a lament. One speaker, no acts, nothing to connect. Class.
      Romans      concepts and argument, and Paul is the only actor. Class,
                  and see the note in the journal about what it needs instead.

    The threshold is deliberately low. Three real exchanges is enough to be
    worth drawing in order, and below that the class view says more.
    """
    from .schema import load_entities, load_relations

    if batch:
        entities, rels_all = from_batch(batch)
    else:
        entities, rels_all = load_entities(), load_relations()
    rels = relations_for(ref, entities, rels_all)

    actors = {"person", "being", "group"}

    def kind(i):
        e = entities.get(i)
        return e.type if e else "?"

    events = 0
    seen = set()
    for r in rels:
        if r.type in NOISE or r.type in QUIET:
            continue
        if r.type in ("asserted_by", "told", "answered"):
            continue
        # A comparison is not an act. Job 3 scored three "events" on its first
        # run and all three were false: `job -likened_to-> untimely_birth` is
        # the simile of the stillborn child in Job 3:16, and
        # `kings_and_counsellors -built-> desolate_places` is something Job
        # IMAGINES about the dead. Nothing is built in Job 3.
        if r.type in VERDICT:
            continue
        # And an event inside a quotation is not an event in the passage.
        # Once speech content is extracted properly this will matter far more:
        # a lament or an argument is full of CLAIMED acts, and only narrated
        # ones belong on a sequence. The sequence draws what the narrator says
        # happened.
        if getattr(r, "claimed_by", ""):
            continue
        key = (r.src, r.type, r.dst)
        if key in seen:
            continue
        seen.add(key)
        if kind(r.src) in actors and kind(r.dst) != "?":
            events += 1
    if events >= 3:
        return True, f"{events} events between parties"
    return False, f"only {events} event(s) -- the class view says more"


def caption(ref: str, limit: int = MAX_EDGES, batch: str | None = None) -> str:
    """What the drawing does NOT show, stated rather than implied.

    The reason this exists at all: a diagram that quietly omits is worse than a
    table that visibly does, because it looks complete.
    """
    from .schema import load_entities

    if batch:
        entities, rels_all = from_batch(batch)
        rels = relations_for(ref, entities, rels_all)
    else:
        entities = load_entities()
        rels = relations_for(ref, entities)
    kept, dropped = choose(rels, entities, limit)
    bits = [f"{len(rels)} relations cite {ref}", f"{len(kept)} drawn"]
    if batch:
        bits.append(f"from {batch}")
    if dropped["noise"]:
        bits.append(f"{dropped['noise']} record which words are where")
    if dropped["over_cap"]:
        bits.append(f"{dropped['over_cap']} beyond the cap")
    if not rels:
        return f"Nothing has been extracted for {ref}."
    return " · ".join(bits)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m bibleont.draw <ref> [--limit=N] [--td] "
              "[--sequence] [--batch=NAME]")
        print("       python -m bibleont.draw 'Gen 4'")
        print("       python -m bibleont.draw 'Gen 3' --sequence "
              "--batch=gen-full-20260830-195828")
        print()
        print("--batch reads an UNMERGED proposal or staging batch. Without")
        print("it the trunk graph is drawn, which for a book whose fresh run")
        print("has not been promoted means the diagram is the OLD data while")
        print("looking exactly like the new. That went unnoticed for hours")
        print("once; it is why the flag is documented here.")
        return 2
    limit = MAX_EDGES
    for a in argv:
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
    direction = "TD" if "--td" in argv else "LR"
    batch = None
    for a in argv:
        if a.startswith("--batch="):
            batch = a.split("=", 1)[1]
    ref = " ".join(a for a in argv if not a.startswith("--"))
    if "--sequence" in argv:
        print(sequence(ref, limit, batch))
        return 0
    print(mermaid(ref, limit, direction, batch))
    print()
    print(f"%% {caption(ref, limit, batch)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
