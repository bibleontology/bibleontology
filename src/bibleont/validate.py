"""Integrity checks for the ontology.

Two jobs. First, ordinary referential integrity: known relation types, resolvable
person ids, well-formed citations. Second — and this is the one that matters when
extraction is delegated to a model — *corroboration*: does the cited verse (or its
immediate neighbours) actually mention the people involved? A relation whose
citation never names either party is the signature of an invented reference, and
gets flagged for review rather than silently trusted.

Usage:  python -m bibleont.validate [--strict]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from .corpus import Corpus
from .paths import BSB_JSONL
from .refs import RefError, parse_ref
from .schema import (
    Person,
    Relation,
    Vocabulary,
    load_persons,
    load_relations,
    load_vocabulary,
    name_variants,
)

ERROR, WARN = "error", "warning"


@dataclass
class Issue:
    level: str
    code: str
    message: str
    subject: str = ""

    def __str__(self) -> str:
        where = f" [{self.subject}]" if self.subject else ""
        return f"{self.level.upper():7} {self.code}{where}: {self.message}"


# How far either side of a cited verse to look when corroborating a name.
CONTEXT_WINDOW = 4


def _contested_ids() -> set[str]:
    """Person ids whose multiple parents are a documented textual disagreement."""
    from .paths import ONTOLOGY

    path = ONTOLOGY / "identity.yaml"
    if not path.exists():
        return set()
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return set(raw.get("contested_parentage") or {})


_HIDDEN = None


def _hidden_names() -> dict[str, list[str]]:
    """Names a record answers to but no card shows: an old KJV title
    (`name_kjv`) and aliases in KJV text (`aka_kjv`), moved out of sight on
    2026-10-02 so no KJV text is displayed -- a copyright precaution. The
    corroboration check still needs them to find a record in its verses (43
    warnings appeared when they left `aka`). Read here, not merged by the
    loader, so no tool that loads and saves records can put them back on
    show."""
    global _HIDDEN
    if _HIDDEN is None:
        import json
        from .paths import ENTITIES_DIR
        _HIDDEN = {}
        for path in sorted(ENTITIES_DIR.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    extra = ([r["name_kjv"]] if r.get("name_kjv") else []) + list(r.get("aka_kjv") or [])
                    if extra:
                        _HIDDEN[r["id"]] = extra
    return _HIDDEN


def _mentions(corpus: Corpus, ref_text: str, names: set[str]) -> bool:
    """True if any name appears in the cited verses or their local context."""
    try:
        ref = parse_ref(ref_text)
    except RefError:
        return False
    vids = corpus.expand(ref)
    if not vids:
        return False
    haystack = []
    first, last = vids[0], vids[-1]
    for v in range(max(1, first.verse - CONTEXT_WINDOW), first.verse):
        t = corpus.text(type(first)(first.book, first.chapter, v))
        if t:
            haystack.append(t)
    haystack.extend(corpus.text(v) or "" for v in vids)
    for v in range(last.verse + 1, last.verse + CONTEXT_WINDOW + 1):
        t = corpus.text(type(last)(last.book, last.chapter, v))
        if t:
            haystack.append(t)
    blob = " ".join(haystack).lower()
    return any(n.lower() in blob for n in names)


@lru_cache(maxsize=1)
def _berean() -> Corpus:
    return Corpus.load(BSB_JSONL)


def validate(
    people: dict[str, Person] | None = None,
    relations: list[Relation] | None = None,
    vocab: Vocabulary | None = None,
    corpus: Corpus | None = None,
) -> list[Issue]:
    from_disk = people is None
    people = load_persons() if people is None else people
    relations = load_relations() if relations is None else relations
    vocab = load_vocabulary() if vocab is None else vocab
    # THE BEREAN, NOT THE KJV (the committee of 2026-10-21, item 3): the text
    # the site shows, and the only one a public copy has. Measured that day:
    # 0 errors on either; warnings 3,532 on the KJV and 3,716 on the Berean
    # (name corroboration, where the Berean spells a name the record does not).
    corpus = _berean() if corpus is None else corpus

    issues: list[Issue] = []
    add = issues.append

    # ONE ID, ONE LINE. The loader keys records by id, so a second line with
    # the same id silently replaces the first -- a record added to
    # entities.jsonl for the angel of Luke 2 already in the-christ.jsonl
    # validated clean (2026-10-13). Read from disk only when it was.
    if from_disk:
        from .paths import ONTOLOGY
        where: dict[str, list[str]] = defaultdict(list)
        for path in sorted((ONTOLOGY / "entities").glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    where[json.loads(line).get("id")].append(path.name)
        for eid, files in where.items():
            if len(files) > 1:
                add(Issue(ERROR, "person.duplicate_id", f"defined {len(files)} times: {', '.join(files)}", eid))

    # -- persons ---------------------------------------------------------
    seen_names: dict[str, list[str]] = defaultdict(list)
    for pid, person in people.items():
        if pid != person.id:
            add(Issue(ERROR, "person.id_mismatch", f"keyed as {pid!r}", person.id))
        if not person.name:
            add(Issue(ERROR, "person.no_name", "person has no name", pid))
        if person.gender not in {"m", "f", "unknown"}:
            add(Issue(WARN, "person.gender", f"unknown gender {person.gender!r}", pid))
        for ref in person.refs:
            try:
                if not corpus.ref_exists(parse_ref(ref)):
                    add(Issue(ERROR, "person.dead_ref", f"{ref} resolves to no verse", pid))
            except RefError as exc:
                add(Issue(ERROR, "person.bad_ref", str(exc), pid))
        for name in person.names():
            seen_names[name.lower()].append(pid)

    for name, ids in seen_names.items():
        if len(ids) > 1:
            unlabeled = [i for i in ids if not people[i].disambiguation]
            if unlabeled:
                add(
                    Issue(
                        WARN,
                        "person.ambiguous_name",
                        f"{name!r} used by {len(ids)} people "
                        f"({', '.join(sorted(ids))}); {len(unlabeled)} lack a "
                        "disambiguation note",
                    )
                )

    # -- relations -------------------------------------------------------
    by_key: dict[tuple, int] = defaultdict(int)
    parents: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    for rel in relations:
        subject = f"{rel.src} -{rel.type}-> {rel.dst}"
        # A CLAIM IS NEVER DEDUPLICATED ACROSS CITATIONS (schema.Relation,
        # claimed_by): Peter's "You are the Christ" and the narrator's "who is
        # called Christ" are two records, and so are Mark's "I am" and Luke's
        # "If I tell you, you will not believe". The check counted them as
        # copies until 2026-10-03; a claim's speaker and citation are part of
        # its identity, so only true copies are flagged
        k = rel.key()
        if rel.claimed_by:
            k = k + (rel.claimed_by, tuple(rel.refs or ()))
        # a STATEMENT is told apart by its verses (plan 2.19): God "spoke to"
        # Moses and God "sent" Moses are two statements, not two copies. The
        # same verb in several verses is already one row (write_statements.py),
        # and the loader keeps no row's verb, so the verses are the key, as
        # they are for a speaker's claims above
        if rel.type == "states":
            k = k + (tuple(rel.refs or ()),)
        by_key[k] += 1

        rtype = vocab.types.get(rel.type)
        if rtype is None:
            add(Issue(ERROR, "rel.unknown_type", f"{rel.type!r} not in vocabulary", subject))
        if rel.src not in people:
            add(Issue(ERROR, "rel.unknown_person", f"src {rel.src!r} not defined", subject))
        if rel.dst not in people:
            add(Issue(ERROR, "rel.unknown_person", f"dst {rel.dst!r} not defined", subject))
        # a speaker's claim names its speaker by id, and that id must be a
        # record: 210 of Eliphaz's verdicts named `eliphaz` after the record
        # had become `eliphaz_the_temanite`, and every card showed "the words
        # of eliphaz", lowercase and linking nowhere (2026-10-13)
        if rel.claimed_by and rel.claimed_by not in people:
            add(Issue(ERROR, "rel.unknown_claimant", f"claimed_by {rel.claimed_by!r} not defined", subject))
        if rel.src == rel.dst:
            add(Issue(ERROR, "rel.self_loop", "relation points at itself", subject))
        if rtype:
            for side, want in (("src", rtype.src_types), ("dst", rtype.dst_types)):
                pid = getattr(rel, side)
                if pid in people and people[pid].type not in want:
                    add(
                        Issue(
                            ERROR,
                            "rel.wrong_entity_type",
                            f"{side} {pid!r} is a {people[pid].type}, but "
                            f"{rel.type} takes {' or '.join(want)} there",
                            subject,
                        )
                    )
        if rel.certainty not in vocab.certainty:
            add(Issue(ERROR, "rel.certainty", f"unknown certainty {rel.certainty!r}", subject))
        if rtype and rtype.symmetric and rel.dst < rel.src:
            add(
                Issue(
                    WARN,
                    "rel.uncanonical",
                    "symmetric relation stored in non-canonical order",
                    subject,
                )
            )
        if not rel.refs:
            add(Issue(ERROR, "rel.no_refs", "relation cites no verse", subject))

        # citations must resolve
        live_refs = []
        for ref in rel.refs:
            try:
                parsed = parse_ref(ref)
            except RefError as exc:
                add(Issue(ERROR, "rel.bad_ref", str(exc), subject))
                continue
            if not corpus.ref_exists(parsed):
                add(Issue(ERROR, "rel.dead_ref", f"{ref} resolves to no verse", subject))
                continue
            live_refs.append(ref)

        # corroboration: at least one citation should name someone involved.
        # Not between two STRUCTURAL records -- a passage, a pattern, an
        # event -- whose names are labels ("Fall (Sin, judgment and mercy):
        # Joshua 7:1"), never words a verse contains. Between those the check
        # can only fire, and did, on every link of the story and role patterns
        # (968 warnings, 2026-09-30), burying the ones that mean something.
        # Nor from a PATTERN to anything: "Speech act: Blessing" or "Message:
        # Do not fear" is a label no verse contains, so the check asks only
        # whether the verse names the other end, and a message spoken in a
        # theme's passage does not name the theme (179 warnings from the
        # messages and speech acts, 2026-09-30). Those edges are grounded
        # by shared verses, which their builders require.
        # And not to a story stage KIND ("Story stage: judgment", a concept
        # node whose name is a label, attrs.kind template_stage_kind): the
        # stages that instance it are grounded by their own verse ranges.
        structural = {"passage", "pattern", "event"}

        def _label(pid):
            p = people[pid]
            return p.type == "pattern" or (p.attrs or {}).get("kind") == "template_stage_kind"
        if live_refs and rel.src in people and rel.dst in people and not (
                people[rel.src].type in structural and people[rel.dst].type in structural) and not (
                _label(rel.src) or _label(rel.dst)):
            names: set[str] = set()
            for pid in (rel.src, rel.dst):
                for n in list(people[pid].names()) + _hidden_names().get(pid, []):
                    names |= name_variants(n)
            if not any(_mentions(corpus, r, names) for r in live_refs):
                add(
                    Issue(
                        WARN,
                        "rel.uncorroborated",
                        "no cited verse (or its context) names either person; "
                        "verify the citation",
                        subject,
                    )
                )

        if rtype and rtype.functional_inverse:
            parents[rel.dst][rel.type].add(rel.src)

    for key, count in by_key.items():
        if count > 1:
            add(
                Issue(
                    WARN,
                    "rel.duplicate",
                    f"{count} copies; merge their citations",
                    f"{key[0]} -{key[1]}-> {key[2]}",
                )
            )

    # Cases already ruled on in identity.yaml are settled; re-reporting them
    # every run would train the reader to ignore this whole class of warning.
    contested = _contested_ids()
    for child, by_type in parents.items():
        for rtype_name, sources in by_type.items():
            if len(sources) > 1 and child not in contested:
                add(
                    Issue(
                        WARN,
                        "rel.multiple_functional",
                        f"has {len(sources)} distinct {rtype_name} "
                        f"({', '.join(sorted(sources))}) - likely two different "
                        "people sharing a name, or a conflated record",
                        child,
                    )
                )

    # One figure keyed to two different KINDS of thing is usually two figures.
    #
    # `image_seed` is keyed to Jesus at Gal 3:16 ("thy seed, which is Christ")
    # and to the word of God at Luke 8:11 ("the seed is the word of God").
    # Both are the text's own explicit keys and both are correctly recorded --
    # and they are not the same seed. Behind them are four different original
    # words: sperma, sporos, Hebrew zera for offspring, and kokkos for the
    # mustard grain. One English node absorbed all four.
    #
    # The discriminator is the TYPE of what is keyed, not the count. Rev 1:20
    # keys one candlestick to seven churches -- one meaning, several
    # referents, and entirely sound. Keying to a person AND a concept is a
    # different situation.
    #
    # A warning, never an error: the corpus really does use one word for
    # several things, and deciding whether that is one node is a reading.
    keyed: dict[str, list[str]] = {}
    for rel in relations:
        if rel.type == "signifies":
            keyed.setdefault(rel.src, []).append(rel.dst)
    for src, dsts in keyed.items():
        kinds = {people[d].type for d in dsts if d in people}
        if len(kinds) > 1:
            add(
                Issue(
                    WARN,
                    "rel.figure_keyed_two_ways",
                    f"is keyed to {len(dsts)} things of different kinds "
                    f"({', '.join(sorted(kinds))}: {', '.join(sorted(dsts))}) "
                    "- one figure standing for unlike things is often two "
                    "figures sharing an English word; check the original",
                    src,
                )
            )

    # THE TRADITIONS LAYER (ontology/traditions/, 2026-10-26): what the traditions have written, each node and
    # edge on the verses of the readings it supports. Read from disk only when the graph was.
    if from_disk:
        from . import traditions
        for level, code, msg, subj in traditions.problems(corpus):
            add(Issue(level, code, msg, subj))

    return issues


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    strict = "--strict" in argv
    quiet = "--quiet" in argv

    issues = validate()
    errors = [i for i in issues if i.level == ERROR]
    warnings = [i for i in issues if i.level == WARN]

    if not quiet:
        for issue in errors + warnings:
            print(issue)

    people, relations = load_persons(), load_relations()
    print(
        f"\n{len(people)} people, {len(relations)} relations, "
        f"{len(errors)} errors, {len(warnings)} warnings"
    )
    if errors:
        return 1
    if strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
