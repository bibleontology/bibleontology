"""Ontology data model, vocabulary loading, and JSONL persistence.

Data lives in plain text files under ontology/ so the graph can grow by
appending, be reviewed in diffs, and be merged from parallel extraction runs.

  ontology/schema/relationship_types.yaml   the controlled vocabulary
  ontology/persons/persons.jsonl            one person per line
  ontology/relations/<book>.jsonl           one relation per line
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from .paths import ENTITIES_DIR, PERSONS_DIR, RELATION_TYPES, RELATIONS_DIR

GENDERS = {"m", "f", "unknown"}


# ---------------------------------------------------------------------------
# vocabulary
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RelationType:
    name: str
    label: str
    inverse: str
    category: str
    symmetric: bool = False
    functional_inverse: bool = False
    notes: str = ""
    # How much of two people's relationship this edge accounts for: lifelong
    # and total (parentage, marriage) at 5, a single recorded act at 1. Drives
    # line thickness and the strength filter. Editorial, so it is declared in
    # the vocabulary where it can be reviewed rather than hidden in the app.
    weight: float = 2.0
    # Short noun-phrase header for the type level of the detail tree
    # ("Disciples & mentors"), where the sentence label reads badly as a
    # group name. Falls back to the type name.
    group: str = ""
    # What kinds of entity each end may be. A tuple because several relations
    # take more than one: the text says both "Saul smote the Amalekites" and
    # "the Philistines fought against Israel", and both are the same relation.
    # Defaults to person, which is what every type was before places existed.
    src_types: tuple[str, ...] = ("person",)
    dst_types: tuple[str, ...] = ("person",)

    @property
    def src_type(self) -> str:
        """First permitted source type, for messages and back-compatibility."""
        return self.src_types[0]

    @property
    def dst_type(self) -> str:
        return self.dst_types[0]


@dataclass(frozen=True)
class Vocabulary:
    types: dict[str, RelationType]
    categories: dict[str, dict]
    certainty: dict[str, str]
    # What kind of thing a category's relationships connect a person to.
    # Only `person` is populated today; the rest are declared so that place and
    # event relationships can be added without restructuring the UI.
    domains: dict[str, dict] = field(default_factory=dict)

    def __contains__(self, name: str) -> bool:
        return name in self.types

    def domain_of(self, category: str) -> str:
        return (self.categories.get(category) or {}).get("domain", "person")

    def is_symmetric(self, name: str) -> bool:
        t = self.types.get(name)
        return bool(t and t.symmetric)


def _types_of(spec) -> tuple[str, ...]:
    """`dst_type: place` and `dst_type: [person, group]` are both valid."""
    if isinstance(spec, str):
        return (spec,)
    return tuple(spec)


@lru_cache(maxsize=1)
def load_vocabulary(path: Path | None = None) -> Vocabulary:
    import yaml  # only dependency outside the stdlib

    path = path or RELATION_TYPES
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    types = {}
    for name, spec in (raw.get("types") or {}).items():
        types[name] = RelationType(
            name=name,
            label=spec.get("label", name.replace("_", " ")),
            inverse=spec.get("inverse", ""),
            category=spec.get("category", "other"),
            symmetric=bool(spec.get("symmetric", False)),
            functional_inverse=bool(spec.get("functional_inverse", False)),
            notes=(spec.get("notes") or "").strip(),
            group=(spec.get("group") or "").strip(),
            weight=float(spec.get("weight", 2)),
            src_types=_types_of(spec.get("src_type", "person")),
            dst_types=_types_of(spec.get("dst_type", "person")),
        )
    return Vocabulary(
        types=types,
        categories=raw.get("categories") or {},
        certainty=raw.get("certainty") or {},
        domains=raw.get("domains") or {"person": {"label": "People", "order": 1}},
    )


# ---------------------------------------------------------------------------
# entities
# ---------------------------------------------------------------------------
# `object` is a made or carried thing the text treats as a thing: the ark of the
# covenant, the tabernacle, the brasen serpent. `observance` is a kept practice:
# the passover, the sabbath, the feast of tabernacles. Both are entities on the
# ordinary terms -- the text names them and a verse establishes each claim.
# `creature` is a living thing the text treats as one: the lion David slew, the
# serpent in the garden. `title` is a name the text gives -- "the Lion of the
# tribe of Juda", "the Lamb of God" -- which is a thing the text says and not a
# reading of it, and keeping it separate from the creature is what stops one
# node meaning both Christ and the devil.
ENTITY_TYPES = {"person", "place", "event", "group", "text", "lemma",
                "object", "observance", "creature", "title",
                # A verdict the text pronounces, over and over, in a fixed
                # formula: "did evil in the sight of the LORD". Not a title and
                # not a description -- an assessment the corpus makes 73 times,
                # and the class of kings it sorts them into.
                "assessment",
                # **Not one covenant.** The text keeps them apart itself --
                # Jer 31:32 says the new one is "not according to the covenant
                # that I made with their fathers" -- so a single node would
                # contradict the verse that matters most about them.
                "covenant",
                # A named spiritual being: Gabriel, Michael, Satan. The first
                # extraction pass put angels out of scope, which left the
                # annunciation and the road to Damascus unrecordable -- and
                # those are among the encounters the text is most explicit
                # about.
                "being",
                # A shape several passages share. Nine beatitudes are "Blessed
                # are the X: for they shall Y"; six verses of Genesis 1 are
                # "And God saw that it was good"; Prov 9:10 and Prov 1:7 are
                # the same sentence with wisdom and knowledge swapped.
                #
                # Those are not one node and they are not unrelated, and until
                # now the graph could say only same-or-nothing. A pattern is
                # the third answer, which matters most in the merge queue:
                # "no, but they rhyme" resolves a whole class of question that
                # otherwise needs a person to adjudicate.
                #
                # **This one is ours, not the text's.** Unlike `assessment` --
                # a verdict the corpus itself pronounces -- a pattern is
                # something we noticed. It carries no lemma, because there is
                # no word behind it, and a reader is entitled to know which
                # kind of node they are looking at.
                "pattern"}


@dataclass
class Entity:
    """Anything the graph can hold a relationship to.

    `type` is what distinguishes a person from a place; everything else here is
    common to all of them. Type-specific data goes in `attrs` rather than
    widening this record — a place's region and coordinates, a text's language —
    so that adding a domain does not change the shape every other domain reads.
    """

    id: str
    name: str
    type: str = "person"
    aka: list[str] = field(default_factory=list)
    gender: str = "unknown"
    roles: list[str] = field(default_factory=list)
    tribe: str = ""
    era: str = ""
    desc: str = ""
    refs: list[str] = field(default_factory=list)
    disambiguation: str = ""  # e.g. "son of Kish" for the many Sauls
    source: str = ""  # provenance: which run/agent introduced this record
    attrs: dict = field(default_factory=dict)

    def names(self) -> list[str]:
        return [self.name, *self.aka]


# The graph began as people only and most code still says "person" where it
# means "entity". Kept so that rename churn is not mistaken for behaviour change.
Person = Entity


# Field names the extractor reaches for that mean one we already have.
#
# `akas` cost a Job batch 316 gate errors: 47 entities failed to construct on
# the plural, and 269 sound relations pointing at them then reported "no
# record". Every one of the 47 carried `"akas": []` -- an empty list. Nothing
# was being claimed and nothing could have been wrong.
#
# **A mismatch should cost work in proportion to the information it disagrees
# about.** Refusing an unknown field is right when it carries a claim nobody
# can check; refusing an empty one named the plural of a real field is the
# schema losing thousands of relations to a typo.
#
# This lives here rather than in either reader because it was first written in
# the gate alone, and `merge` -- which reads the same files by the same
# constructor -- then failed on exactly the rows the gate had just accepted.
_FIELD_SYNONYMS = {
    "akas": "aka",
    "aliases": "aka",
    "alias": "aka",
    "description": "desc",
    "references": "refs",
}


# Values that name a grade we already have. Same argument as the field names
# above and the same cost when it is refused: "implicit" cost Genesis 11
# relations, and it is not a different claim from "implied" -- it is the same
# claim spelled the way an English speaker reaches for it first.
#
# Deliberately not a fuzzy match. Each of these is a word that means one of the
# four grades and nothing else; anything genuinely unrecognised is still an
# error, because a certainty nobody can interpret must not silently become
# "explicit".
_VALUE_SYNONYMS = {
    "certainty": {
        "implicit": "implied",
        "inferred": "implied",
        "stated": "explicit",
        "direct": "explicit",
        "contested": "disputed",
        "conjecture": "conjectured",
        "speculative": "conjectured",
    },
}


def canonical_fields(row: dict, note=None) -> dict:
    """Rename known synonyms onto the real field, and the same for their values.

    `note`, if given, is called with a message per rename. Silence would hide
    the rate, and the rate is how far the prompt has drifted from the schema.
    An explicit `aka` beside `akas` is left alone -- that is not a misspelling
    and the constructor should object to it.
    """
    out = {}
    for k, v in row.items():
        target = _FIELD_SYNONYMS.get(k)
        if target is None or target in row:
            out[k] = v
            continue
        if note:
            note(f"field {k!r} read as {target!r}")
        out[target] = v
    for field, table in _VALUE_SYNONYMS.items():
        got = out.get(field)
        if isinstance(got, str) and got.lower() in table:
            if note:
                note(f"{field} {got!r} read as {table[got.lower()]!r}")
            out[field] = table[got.lower()]

    # Anything left that Entity does not declare goes into `attrs`, which is
    # where the record already says such things belong: *"Type-specific data
    # goes in attrs rather than widening this record."*
    #
    # Without this a single unrecognised key fails the whole record and takes
    # every relation pointing at it down with it. `unnamed` did exactly that
    # to Genesis and then to Job, and was stripped by hand the first time --
    # a field the extractor keeps producing and the loader keeps refusing is
    # a loader problem, and the second occurrence is the evidence.
    #
    # It is also not noise. `unnamed` marks people the text DECLINES to name:
    # Job's four messengers, Job's wife, Cain's wife, the man slain by
    # Lamech. Widening Entity for it would invite widening for the next one;
    # keeping it in attrs preserves the distinction without the schema
    # growing a field per observation.
    #
    # `draw.from_batch` has always done this. The loader not doing it is the
    # inconsistency being removed, not a new liberty.
    # Only for ENTITY rows. This function serves both records, and folding
    # unknown keys into `attrs` on a relation immediately broke all 5,194 of
    # Job's -- `Relation` has no `attrs` and never should: a relation is a
    # claim with a citation, and a bag of loose properties on one is a place
    # for assertions to hide from the gate.
    import dataclasses as _dc

    if "src" in out and "dst" in out:
        return out

    known = {f.name for f in _dc.fields(Entity)}
    extra = {k: v for k, v in out.items() if k not in known}
    if extra:
        for k in extra:
            out.pop(k)
            if note:
                note(f"field {k!r} kept in attrs")
        attrs = dict(out.get("attrs") or {})
        attrs.update(extra)
        out["attrs"] = attrs
    return out


@dataclass
class Relation:
    src: str
    type: str
    dst: str
    refs: list[str] = field(default_factory=list)
    certainty: str = "explicit"
    note: str = ""
    source: str = ""
    # WHO CLAIMS THIS, when it is not the scroll.
    #
    # Empty means the narrator states it and the graph records it as the scroll
    # records it. Set, it means this party said so and the graph asserts
    # nothing -- Bildad's argument is held without being endorsed.
    #
    # Settled on 2026-08-30, on a better reason than the first one offered:
    # "God gave" has to be Job's claim, otherwise the whole book breaks down.
    # The book of Job is a dispute about God. Assert Job's
    # theology as fact and Bildad's contradictory claims either make the graph
    # self-contradictory or force it to arbitrate -- and refusing to arbitrate
    # until 42:7 is the book's entire structure. The graph must hold the
    # dispute before the adjudication or there is nothing to adjudicate.
    #
    # A field rather than a node because the alternative is reifying every
    # claim, which doubles the graph and puts one fact in two places. This is
    # how provenance is usually carried -- RDF-star and named graphs do the
    # same thing -- and it stays queryable: what the corpus asserts in its own
    # voice is every relation with `claimed_by` empty.
    #
    # **A claim is never deduplicated across citations**, which is the opposite
    # of the rule for everything else. More citations make an entity record
    # stronger; for a claim they may mean two different claims.
    #
    # 2026-08-30: it is important when Job says different things, because
    # that is part of his development. Job moves from "the LORD gave,
    # and the LORD hath taken away; blessed be the name of the LORD" (1:21),
    # through cursing his birth (ch. 3), through "he destroyeth the perfect and
    # the wicked" (9:22), to "I abhor myself, and repent in dust and ashes"
    # (42:6). He contradicts himself, and the contradiction is the book.
    #
    # Collapse those on (src, type, dst, claimed_by) and a man's arc becomes
    # one flat voice saying a single thing consistently -- the one thing Job
    # never does. The citation is what separates them, so the citation is part
    # of a claim's identity.
    claimed_by: str = ""

    def key(self) -> tuple[str, str, str]:
        return (self.src, self.type, self.dst)


# ---------------------------------------------------------------------------
# id + name helpers
# ---------------------------------------------------------------------------
_ID_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """'Bath-sheba' -> 'bath_sheba'; used to mint stable person ids."""
    norm = unicodedata.normalize("NFKD", name)
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    return _ID_STRIP.sub("_", norm.lower()).strip("_")


def name_variants(name: str) -> set[str]:
    """Surface forms a name may take in KJV text, for corroboration checks."""
    base = name.strip()
    out = {base, base.lower()}
    plain = base.replace("-", "").replace("'", "")
    out |= {plain, plain.lower()}
    hyphen_to_space = base.replace("-", " ")
    out |= {hyphen_to_space, hyphen_to_space.lower()}
    return {v for v in out if v}


# ---------------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------------
def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{i}: invalid JSON: {exc}") from exc
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _clean(d: dict) -> dict:
    """Drop empty optional fields so the files stay readable."""
    return {k: v for k, v in d.items() if v not in ("", [], None)}


def load_entities(directory: Path | None = None) -> dict[str, Entity]:
    """Every entity, keyed by id. Reads the entities directory and, for the
    graph's person-only history, the older persons directory alongside it."""
    dirs = [directory] if directory else [ENTITIES_DIR, PERSONS_DIR]
    out: dict[str, Entity] = {}
    for d in dirs:
        for path in sorted(d.glob("*.jsonl")) if d and d.exists() else []:
            for row in _read_jsonl(path):
                # IGNORE FIELDS THIS SCHEMA DOES NOT KNOW. The entity files
                # gained `name_kjv` after this loader was written, and
                # `Entity(**row)` raised TypeError on every one of them -- so
                # the whole graph refused to load rather than reading the
                # fields it does understand. A reader of a growing data format
                # should skip what it cannot use, not fail.
                known = {k: v for k, v in row.items()
                         if k in Entity.__dataclass_fields__}
                entity = Entity(**known)
                out[entity.id] = entity
    return out


def save_entities(
    entities: dict[str, Entity] | list[Entity], path: Path | None = None
) -> None:
    path = path or (ENTITIES_DIR / "entities.jsonl")
    values = list(entities.values()) if isinstance(entities, dict) else list(entities)
    values.sort(key=lambda e: e.id)
    _write_jsonl(path, [_clean(asdict(e)) for e in values])


# Older names, kept so call sites that only care about people read clearly.
load_persons = load_entities
save_persons = save_entities


def load_relations(directory: Path | None = None) -> list[Relation]:
    directory = directory or RELATIONS_DIR
    out: list[Relation] = []
    for path in sorted(directory.glob("*.jsonl")) if directory.exists() else []:
        for row in _read_jsonl(path):
            # Same forward-compatibility as load_entities: the relation files
            # gained `note_kjv` and this refused every one of them.
            out.append(Relation(**{k: v for k, v in row.items()
                                   if k in Relation.__dataclass_fields__}))
    return out


def save_relations(relations: list[Relation], path: Path) -> None:
    ordered = sorted(relations, key=lambda r: (r.src, r.type, r.dst))
    _write_jsonl(path, [_clean(asdict(r)) for r in ordered])


def canonicalize(relation: Relation, vocab: Vocabulary) -> Relation:
    """Store symmetric relations once, in a fixed direction."""
    if vocab.is_symmetric(relation.type) and relation.dst < relation.src:
        relation.src, relation.dst = relation.dst, relation.src
    return relation
