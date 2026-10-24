"""Self-check for a single extraction batch, before it is merged.

Extraction is delegated to cheaper models, so the batch a model produces has to
be checkable on its own, without reference to the rest of the ontology. This
checks exactly that: does the batch cite real verses, and do those verses
actually name the people the relation claims?

The corroboration check is the important one. A model that invents a plausible
reference will almost always cite a verse that names neither party, and that is
mechanically detectable.

Usage:
    python -m bibleont.check_extraction ontology/staging/<batch>
    python -m bibleont.check_extraction ontology/staging/<batch> --json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .corpus import get_corpus
from .refs import RefError, parse_ref
from .schema import (Person, Relation, canonical_fields, load_vocabulary,
                     name_variants)

CONTEXT = 4

# `gen_19_25`, `gen_14_21_speech`, `1sam_17_36` -- the shape the decomposer
# gives a passage node, which is the verse it came from with an optional tail
# saying which part of it.
_ID_VERSE = re.compile(r"^([1-3]?[a-z]+)_(\d+)_(\d+)(?:_|$)")


def _verse_blob(corpus, ref_text: str, context: int) -> str | None:
    try:
        ref = parse_ref(ref_text)
    except RefError:
        return None
    vids = corpus.expand(ref)
    if not vids:
        return None
    parts = [corpus.text(v) or "" for v in vids]
    if context:
        first, last = vids[0], vids[-1]
        cls = type(first)

        # Backwards, ACROSS the chapter break. This used to clamp at verse 1,
        # which meant a chapter's opening verse got no backward context at all
        # -- and a chapter opening is exactly where narrative carries its
        # subject in from what came before.
        #
        # Matthew 5:1 is "And seeing the multitudes, HE went up into a
        # mountain". Jesus is not named in the whole Sermon on the Mount; he is
        # named at Matt 4:23, three verses earlier and one chapter back. Every
        # relation putting Jesus in that chapter was refused as uncited, and
        # every one of them was true.
        v, ch, back = first.verse, first.chapter, context
        while back > 0:
            v -= 1
            if v < 1:
                ch -= 1
                if ch < 1:
                    break
                v = corpus.chapter_length(first.book, ch)
                if not v:
                    break
            parts.append(corpus.text(cls(first.book, ch, v)) or "")
            back -= 1

        # Forwards, likewise -- less important, since a referent is almost
        # always established before the pronoun, but a citation should not
        # behave differently at the end of a chapter than in the middle.
        v, ch, fwd = last.verse, last.chapter, context
        while fwd > 0:
            v += 1
            if v > corpus.chapter_length(last.book, ch):
                ch += 1
                v = 1
                if not corpus.chapter_length(last.book, ch):
                    break
            parts.append(corpus.text(cls(last.book, ch, v)) or "")
            fwd -= 1
    return " ".join(parts).lower()


def check(batch_dir: Path, known: dict | None = None) -> dict:
    """Check one batch. `known` maps id -> entity for records that already
    exist outside it (the merged graph, or the other batches in a merge).

    The module docstring says a batch "has to be checkable on its own, without
    reference to the rest of the ontology". That was true when a batch was a
    self-contained hand-built file. **It stopped being true when the farm
    started handing the worker the graph's vocabulary** and instructing it, in
    those words, to *reuse these ids verbatim* -- which is the whole point of
    the prefix and the reason the cache pays for itself.

    A batch that does as it is told then references ids it does not declare,
    and every one was reported as "has no record in persons.jsonl": 51 of them
    in a three-window Genesis batch, 50 of which were already in the graph.

    So the strictness is kept and its scope is corrected. With no `known` it
    behaves exactly as before, which is right for a batch that really is
    standalone. Given the graph, an id that exists is not missing -- and the
    whole record comes with it, so the type and corroboration checks still
    run rather than being quietly skipped for the ids that came from outside.

    The batch's OWN entities are still checked on their own terms: a record
    here must cite a real verse whatever the graph holds elsewhere.
    """
    corpus = get_corpus()
    vocab = load_vocabulary()
    known = known or {}

    errors: list[str] = []
    warnings: list[str] = []
    persons: dict[str, Person] = {}
    relations: list[Relation] = []

    # A batch names its entity file either way: `entities.jsonl` when it carries
    # a mix of types, `persons.jsonl` from before the graph had more than people.
    persons_path = batch_dir / "entities.jsonl"
    if not persons_path.exists():
        persons_path = batch_dir / "persons.jsonl"
    relations_path = batch_dir / "relations.jsonl"

    for path, kind in ((persons_path, "person"), (relations_path, "relation")):
        if not path.exists():
            errors.append(f"missing required file: {path.name} (entities.jsonl or persons.jsonl)")
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{path.name}:{lineno}: invalid JSON: {exc}")
                continue
            row = canonical_fields(
                row, lambda m, p=path.name, n=lineno: warnings.append(f"{p}:{n}: {m}"))
            try:
                if kind == "person":
                    p = Person(**row)
                    if p.id in persons:
                        errors.append(f"{path.name}:{lineno}: duplicate person id {p.id!r}")
                    persons[p.id] = p
                else:
                    relations.append(Relation(**row))
            except TypeError as exc:
                errors.append(f"{path.name}:{lineno}: bad fields: {exc}")

    # -- persons ---------------------------------------------------------
    for pid, person in persons.items():
        if not person.name:
            errors.append(f"person {pid!r}: missing name")
        if person.gender not in {"m", "f", "unknown"}:
            warnings.append(f"person {pid!r}: gender {person.gender!r} is not m/f/unknown")
        if not person.refs:
            warnings.append(f"person {pid!r}: cites no verse")
        for ref in person.refs:
            if _verse_blob(corpus, ref, 0) is None:
                errors.append(f"person {pid!r}: citation {ref!r} resolves to no verse")

    # -- relations -------------------------------------------------------
    # The batch's own records win over the graph's, because a batch may be
    # revising one. Everything from here reads `lookup` rather than
    # `persons`: a relation's ends may legitimately live outside the batch.
    lookup = dict(known)
    lookup.update(persons)
    for rel in relations:
        tag = f"{rel.src} -{rel.type}-> {rel.dst}"
        if rel.type not in vocab:
            errors.append(f"{tag}: relation type {rel.type!r} is not in the vocabulary")
        if rel.certainty not in vocab.certainty:
            errors.append(f"{tag}: certainty {rel.certainty!r} is not explicit/implied/disputed")
        if rel.src == rel.dst:
            errors.append(f"{tag}: relation points at itself")
        if rel.type in vocab and vocab.is_symmetric(rel.type) and rel.dst < rel.src:
            warnings.append(
                f"{tag}: {rel.type} is symmetric, so it must be stored once with the "
                f"alphabetically smaller id as src - swap to "
                f"{rel.dst} -{rel.type}-> {rel.src}"
            )
        for side in ("src", "dst"):
            pid = getattr(rel, side)
            if pid not in lookup:
                errors.append(f"{tag}: {side} {pid!r} has no record in persons.jsonl")
                continue
            # Now that entities carry a type, a relation can name the wrong kind
            # of thing at either end. Many biblical names belong to both a person
            # and a place -- Haran, Mamre, Shechem, Moab, Gilead, Hebron -- so
            # "buried_at Hebron" pointing at Caleb's descendant rather than the
            # city is a live mistake, and one nothing else would catch.
            meta = vocab.types.get(rel.type)
            if meta is None:
                continue
            want = meta.src_types if side == "src" else meta.dst_types
            got = lookup[pid].type
            if got not in want:
                errors.append(
                    f"{tag}: {side} {pid!r} is a {got}, but {rel.type} takes "
                    f"{' or '.join(want)} there. If a person and a place share "
                    f"this name they need separate ids ({pid}_city or "
                    f"{pid}_of_<father>)."
                )
        if not rel.refs:
            errors.append(f"{tag}: cites no verse")
            continue

        live = []
        for ref in rel.refs:
            if _verse_blob(corpus, ref, 0) is None:
                errors.append(f"{tag}: citation {ref!r} resolves to no verse")
            else:
                live.append(ref)

        # Chapter and book citations are not evidence for the check below, and
        # the danger they pose is the opposite of the obvious one.
        #
        # This check asks whether the cited text names both parties. Ask that
        # of `Gen 14:9` and it is a real question. Ask it of `Job 38-41` --
        # 129 verses -- and almost any pair of names will appear somewhere in
        # it; ask it of `Job` and everything passes. So a container citation
        # does not fail corroboration, it DEFEATS it, and leaving it in the
        # evidence would make citing broadly the cheapest way past the check.
        #
        # They are dropped rather than rejected because they are often the
        # right citation: a speech, a collection or a scroll attribution names
        # a container because the container is the subject. Such a relation
        # simply goes unverified here, which is honest -- the question this
        # check asks does not apply to it.
        from .refs import RefError, parse_ref

        def _is_container(ref: str) -> bool:
            try:
                return parse_ref(str(ref)).is_whole
            except RefError:
                return False

        live = [r for r in live if not _is_container(r)]
        if not live or rel.src not in persons or rel.dst not in persons:
            continue

        # Some of the most important people in the text are never named: the
        # widow of Nain, the woman at the well, the centurion's servant. Their
        # relationships are certain -- the widow's son is the whole point of the
        # passage -- but a name-matching check can never confirm them, and an
        # earlier version of this check forced those records to be deleted.
        # Losing a fact because the tool cannot verify it is worse than
        # recording it with the limit stated, so an entity may declare itself
        # unnamed and is then exempted from the name requirement.
        def is_unnamed(pid: str) -> bool:
            return bool(lookup[pid].attrs.get("unnamed"))

        if is_unnamed(rel.src) and is_unnamed(rel.dst):
            if rel.certainty == "explicit":
                warnings.append(
                    f"{tag}: neither party is named in the text, so no citation can "
                    "corroborate this; mark certainty 'implied'"
                )
            if not rel.note:
                warnings.append(
                    f"{tag}: both parties are unnamed, so the note is the only record "
                    "of how they were identified - add one"
                )
            continue

        # Corroboration asks "does the cited verse NAME this thing". That is a
        # sensible question about a person, a place or a group, and a
        # meaningless one about a concept or a passage: the text is *about*
        # persecution, it does not name it, and `matt_5_11` IS Matthew 5:11 --
        # asking whether the verse names itself is incoherent.
        #
        # Applying it anyway refused true relations at scale the moment
        # narrative started producing passage nodes: every `part_of` into a
        # discourse, and every `speaks_of` from a verse to an idea.
        #
        # Both ends unnameable means there is nothing to corroborate BY NAME.
        # The relation still has to cite a real verse and still has to use a
        # real type; this only stops a name test being run where no name was
        # ever going to appear.
        NAMEABLE = {"person", "place", "group", "being"}
        if (lookup[rel.src].type not in NAMEABLE
                and lookup[rel.dst].type not in NAMEABLE):
            continue

        src_names = {v.lower() for n in lookup[rel.src].names() for v in name_variants(n)}
        dst_names = {v.lower() for n in lookup[rel.dst].names() for v in name_variants(n)}
        if is_unnamed(rel.src):
            src_names = set()
        if is_unnamed(rel.dst):
            dst_names = set()

        # A passage node cited to its own verse corroborates by being it.
        #
        # The rule above already says asking whether a verse names itself is
        # incoherent, but only acted on it when BOTH ends were unnameable. In
        # decomposition output one end is a passage and the other is a person
        # constantly -- `bera_king_of_sodom -told-> gen_14_21_speech`, cited to
        # Gen 14:21 -- and 56 of Genesis's 73 corroboration failures were of
        # exactly that shape. Every one was refused on the grounds that the
        # citation was "almost certainly wrong", which is the one thing it
        # cannot be: the node is named for the verse it cites.
        #
        # This does not excuse the relation. It satisfies the end that cannot
        # be tested, leaving the other end to be found as before -- so a
        # passage linked to a person the verse never mentions still drops to a
        # warning rather than passing silently, and a citation that resolves
        # nowhere is still an error.
        def is_own_verse(pid: str) -> bool:
            if lookup[pid].type != "text":
                return False
            m = _ID_VERSE.match(pid)
            if not m:
                return False
            book, chapter, verse = m.group(1), int(m.group(2)), int(m.group(3))
            for ref in live:
                try:
                    for vid in corpus.expand(parse_ref(ref)):
                        if (str(vid.book).lower() == book
                                and vid.chapter == chapter and vid.verse == verse):
                            return True
                except RefError:
                    continue
            return False

        src_self = is_own_verse(rel.src)
        dst_self = is_own_verse(rel.dst)

        def hits(ref: str, context: int) -> tuple[bool, bool]:
            blob = _verse_blob(corpus, ref, context) or ""
            return (
                src_self or any(n in blob for n in src_names),
                dst_self or any(n in blob for n in dst_names),
            )

        tight = [hits(r, 0) for r in live]
        loose = [hits(r, CONTEXT) for r in live]

        if any(a and b for a, b in tight):
            continue  # both parties named in a cited verse: solid
        if any(a and b for a, b in loose):
            continue  # both named within a few verses: acceptable
        named = any(a or b for a, b in loose)
        one_side_unnamed = is_unnamed(rel.src) or is_unnamed(rel.dst)
        if not named:
            errors.append(
                f"{tag}: none of {live} name either person, even in context - "
                "the citation is almost certainly wrong"
            )
        elif one_side_unnamed:
            # Only one name to find, and it was found. This is as much
            # corroboration as the text allows.
            pass
        elif rel.certainty == "explicit":
            warnings.append(
                f"{tag}: cited verses name only one of the two people; either fix "
                "the citation or mark certainty as 'implied'"
            )

    # -- conflation: one id standing for two different people -------------
    # A person has one biological father. Two different fathers for one id is
    # the single most reliable sign that two same-named people were given the
    # same id, and it is the error that silently corrupts the merged graph.
    functional = {n for n, t in vocab.types.items() if t.functional_inverse}
    incoming: dict[str, dict[str, set[str]]] = {}
    for rel in relations:
        if rel.type in functional:
            incoming.setdefault(rel.dst, {}).setdefault(rel.type, set()).add(rel.src)
    for child, by_type in sorted(incoming.items()):
        for rtype, srcs in by_type.items():
            if len(srcs) > 1:
                names = ", ".join(sorted(srcs))
                errors.append(
                    f"person {child!r} is given {len(srcs)} different {rtype} "
                    f"({names}). Almost always these are two different people who "
                    f"share a name: split them into separate ids (e.g. "
                    f"{child}_son_of_{sorted(srcs)[0]}), set 'disambiguation' on "
                    f"each, and repoint the relations. If the text genuinely "
                    f"disagrees with itself, keep one id and mark the relations "
                    f"certainty 'disputed' with a note."
                )

    # A person record whose name collides with another's, with no note to tell
    # them apart, is the same problem one step earlier.
    by_name: dict[str, list[str]] = {}
    for pid, person in persons.items():
        by_name.setdefault(person.name.strip().lower(), []).append(pid)
    for name, ids in sorted(by_name.items()):
        if len(ids) > 1:
            bare = [i for i in ids if not persons[i].disambiguation.strip()]
            if bare:
                warnings.append(
                    f"name {name!r} is used by {len(ids)} records "
                    f"({', '.join(sorted(ids))}); {len(bare)} have no "
                    "'disambiguation' note saying which person they are"
                )

    return {
        "batch": str(batch_dir),
        "persons": len(persons),
        "relations": len(relations),
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    result = check(Path(args[0]))
    if "--json" in argv:
        print(json.dumps(result, indent=2))
    else:
        for e in result["errors"]:
            print(f"ERROR   {e}")
        for w in result["warnings"]:
            print(f"WARNING {w}")
        print(
            f"\n{result['persons']} people, {result['relations']} relations, "
            f"{len(result['errors'])} errors, {len(result['warnings'])} warnings"
        )
        print("PASS" if result["ok"] else "FAIL - fix the errors above")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
