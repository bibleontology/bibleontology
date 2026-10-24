"""Merge staged extraction batches into the ontology.

Batches are produced independently, so ids are only meaningful inside the batch
that minted them. Two batches can name two different people `azariah`, or name
one person `saul_of_tarsus` and `paul`. Neither is decidable from inside a batch.

So merging is auto-unify-then-audit: records sharing an id are combined, and every
combination is checked for the signatures of a wrong merge. Anything suspicious is
reported for a human decision recorded in ontology/identity.yaml, rather than being
resolved by guesswork.

Usage:
    python -m bibleont.merge --dry-run     # audit only, write nothing
    python -m bibleont.merge               # write ontology/persons + ontology/relations
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

import yaml
from dataclasses import replace
from pathlib import Path

from .paths import ONTOLOGY, PERSONS_DIR, RELATIONS_DIR
from .schema import (
    Person,
    Relation,
    canonical_fields,
    canonicalize,
    load_vocabulary,
    save_entities,
    save_relations,
)
from .check_extraction import check

STAGING = ONTOLOGY / "staging"
IDENTITY = ONTOLOGY / "identity.yaml"


class _DuplicateKeyError(Exception):
    pass


class _StrictLoader(yaml.SafeLoader):
    """A YAML loader that refuses to let one key quietly overwrite another.

    `identity.yaml` opens by saying these decisions are made "by hand, once".
    Plain YAML does not honour that: a second `jehoiachin:` further down the
    same mapping silently discards the first, and the file is long enough that
    nobody sees both. It cost a real decision -- a merge was written near the
    top of `same`, an older entry for the same king sat 80 lines below, and the
    merge simply did not happen. No error, no warning; the graph just kept two
    records for one man and everything downstream agreed with it.

    A silently dropped identity decision is the worst failure this file can
    have, because the whole point of it is to be the one place a question is
    answered. Answering it twice must be an error, not a coin toss.
    """

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise _DuplicateKeyError(
                    f"{key!r} is defined twice in the same block "
                    f"(line {key_node.start_mark.line + 1}). Merge the two "
                    f"entries; YAML would keep only the last and drop the "
                    f"other decision without saying so."
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def load_identity(path: Path | None = None) -> dict:
    path = path or IDENTITY
    if not path.exists():
        return {"same": {}, "distinct": {}}
    raw = yaml.load(path.read_text(encoding="utf-8"), _StrictLoader) or {}
    return {
        "same": raw.get("same") or {},
        "distinct": raw.get("distinct") or {},
        "contested_parentage": raw.get("contested_parentage") or {},
        # Identifications that are the most reasonable reading rather than a
        # settled fact. Merged exactly like `same`, but reported on every run so
        # they stay visible and reversible instead of hardening into assumptions.
        "provisional": raw.get("provisional") or {},
    }


def _batches() -> list[Path]:
    if not STAGING.exists():
        return []
    return sorted(
        d
        for d in STAGING.iterdir()
        if d.is_dir() and not d.name.startswith("_")
        and ((d / "entities.jsonl").exists() or (d / "persons.jsonl").exists())
    )


def _read_batch(batch: Path) -> tuple[list[Person], list[Relation]]:
    import json

    people, relations = [], []
    entity_file = batch / "entities.jsonl"
    if not entity_file.exists():
        entity_file = batch / "persons.jsonl"
    for line in entity_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            people.append(Person(**canonical_fields(json.loads(line))))
    rel_path = batch / "relations.jsonl"
    if rel_path.exists():
        for line in rel_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("//"):
                relations.append(
                    Relation(**canonical_fields(json.loads(line))))
    return people, relations


def _alias_map(identity: dict) -> dict[str, str]:
    """alternate id -> canonical id, with chains followed to their end.

    Aliases accumulate in layers: a spelling merge maps `thamar` to `tamar`, and
    a later identity decision maps `tamar` to `tamar_wife_of_er`. Resolving only
    one hop would leave the Greek spelling stranded as its own person.
    """
    direct: dict[str, str] = {}
    for block in ("same", "provisional"):
        for canonical, alternates in (identity.get(block) or {}).items():
            for alt in alternates or []:
                direct[alt] = canonical

    out: dict[str, str] = {}
    for alt in direct:
        seen = {alt}
        target = direct[alt]
        while target in direct and target not in seen:
            seen.add(target)
            target = direct[target]
        if target in seen and target in direct:
            raise ValueError(
                f"identity.yaml: alias cycle involving {sorted(seen)}"
            )
        out[alt] = target
    return out


def _split_map(identity: dict) -> dict[tuple[str, str], tuple[str, str]]:
    """(batch, colliding id) -> (new id, disambiguation)."""
    out: dict[tuple[str, str], tuple[str, str]] = {}
    for colliding, variants in (identity.get("distinct") or {}).items():
        for variant in variants or []:
            for batch in variant.get("batches", []):
                out[(batch, colliding)] = (
                    variant["id"],
                    variant.get("disambiguation", ""),
                )
    return out


def _merge_people(records: list[Person], canonical: list[Person] | None = None) -> Person:
    """Combine records for one id, preferring the fullest values.

    `canonical` holds the records that already used the surviving id before any
    aliasing. Their spelling of the name wins, so that unifying "Sheth" into
    `seth` displays "Seth" rather than whichever record happened to have the
    longest description.
    """
    pool = canonical or records
    base = max(pool, key=lambda p: len(p.desc or ""))

    # TYPE IS NOT A "FULLEST VALUE" FIELD.
    # ------------------------------------
    # Everything else here prefers the longest, most-populated version, which
    # is right for a description and wrong for a type: a type is a claim about
    # what the thing IS, and the record with the wordiest description has no
    # special authority over it.
    #
    # It went wrong in one direction only. `lion` was a creature until a batch
    # with a longer description called it a concept, and `david -killed-> lion`
    # became invalid; the same for `iron` (a city in Josh 19:38) and `tema`.
    # Eleven errors, every one a concrete thing demoted to an abstraction.
    #
    # That direction is not chance. **`concept` is what the extractor reaches
    # for when it is unsure** -- the same run typed Orion, clay, stones, the
    # grave, a wild ass, wine and the tabernacle as concepts. So where records
    # disagree and one of them says `concept`, the one that commits to
    # something concrete is the one carrying information, and it wins.
    #
    # Two concrete types disagreeing is a different thing entirely -- a person
    # and a place sharing a name -- and is left alone for `_audit_merge` to
    # report, because there the answer is two ids, not a preference.
    # Counted, not just collected. `cattle` was typed `object` once,
    # `creature` once and `concept` twice; the first version of this rule only
    # acted when exactly one concrete type was on offer, so two of them let
    # `concept` back in on description length and `god -made-> cattle` --
    # Genesis 1:25 -- stayed refused.
    #
    # **`concept` does not win against a concrete type, ever.** Where several
    # concrete types disagree that is a real question, and the most-asserted
    # one is taken while `_audit_merge` reports the disagreement for a person.
    # Guessing between `object` and `creature` is a small error that can be
    # corrected; calling cattle an idea refuses the verse outright.
    kinds = Counter(p.type for p in records if p.type)
    if len(kinds) > 1 and "concept" in kinds:
        concrete = {k: n for k, n in kinds.items() if k != "concept"}
        if concrete:
            base = replace(base, type=max(sorted(concrete), key=concrete.get))
    aka: list[str] = []
    refs: list[str] = []
    roles: list[str] = []
    sources: list[str] = []
    for rec in records:
        for name in rec.names():
            if name and name != base.name and name not in aka:
                aka.append(name)
        for ref in rec.refs:
            if ref not in refs:
                refs.append(ref)
        for role in rec.roles:
            if role not in roles:
                roles.append(role)
        for src in (rec.source or "").split(","):
            if src and src not in sources:
                sources.append(src)
    return replace(
        base,
        aka=sorted(aka),
        refs=refs,
        roles=sorted(roles),
        gender=next((r.gender for r in records if r.gender != "unknown"), "unknown"),
        tribe=next((r.tribe for r in records if r.tribe), ""),
        era=next((r.era for r in records if r.era), ""),
        disambiguation=next((r.disambiguation for r in records if r.disambiguation), ""),
        source=",".join(sorted(sources)),
    )


def _audit_merge(
    pid: str, records: list[tuple[str, Person]], decided: set[str]
) -> list[str]:
    """Signatures that records sharing an id are actually different people.

    `decided` holds ids whose identity is settled in identity.yaml. Those are
    skipped: differing wording in a disambiguation note is not evidence of
    anything once a human has ruled on the identity.
    """
    if len(records) < 2 or pid in decided:
        return []
    issues = []

    def conflict(field: str) -> str | None:
        # "unknown" is absence, not disagreement. Batches that only echo an
        # entity to satisfy the standalone checker leave it unset, and treating
        # that as a conflict buries the real ones — the places pass alone added
        # eighteen such lines.
        values = {
            getattr(p, field)
            for _, p in records
            if getattr(p, field) and getattr(p, field) != "unknown"
        }
        return f"{field}: {sorted(values)}" if len(values) > 1 else None

    # A person and a place sharing an id are never the same entity, whatever
    # else agrees. Many biblical names are both, so this is the cross-domain
    # equivalent of two same-named people fused into one record -- and unlike
    # that case there is no parentage signal to catch it.
    types = {p.type for _, p in records}
    if len(types) > 1:
        batches = ", ".join(sorted(b for b, _ in records))
        return [
            f"{pid!r} merged from [{batches}] but they are different KINDS of "
            f"entity ({', '.join(sorted(types))}). These are two things sharing "
            "a name; give one of them a qualified id."
        ]

    # `era` is free-text and batches phrase it differently ("monarchy" vs
    # "united_monarchy"), so it is too noisy to treat as evidence on its own.
    for field in ("tribe", "gender"):
        c = conflict(field)
        if c:
            issues.append(c)

    notes = {p.disambiguation.strip().lower() for _, p in records if p.disambiguation.strip()}
    if len(notes) > 1:
        issues.append(f"disambiguation: {sorted(notes)}")

    if issues:
        batches = ", ".join(sorted(b for b, _ in records))
        return [f"{pid!r} merged from [{batches}] but they disagree on -> {'; '.join(issues)}"]
    return []


def merge(dry_run: bool = False) -> dict:
    vocab = load_vocabulary()
    identity = load_identity()
    aliases = _alias_map(identity)
    splits = _split_map(identity)

    batches = _batches()
    if not batches:
        return {"error": "no batches found in ontology/staging"}

    failed_checks: list[str] = []
    staged: dict[str, list[tuple[str, Person]]] = defaultdict(list)
    canonical_records: dict[str, list[Person]] = defaultdict(list)
    all_relations: list[tuple[str, Relation]] = []

    # Every record in every batch, so a batch is checked against the world it
    # is actually being merged into. Batches reference each other's ids by
    # design -- the farm hands each worker the graph's vocabulary and tells it
    # to reuse those ids -- and checking each one alone reported the reused
    # ones as missing and excluded the batch entire.
    everyone: dict[str, Person] = {}
    for batch in batches:
        try:
            for person in _read_batch(batch)[0]:
                everyone.setdefault(person.id, person)
        except Exception:                                    # noqa: BLE001
            continue                    # a batch too broken to read fails below

    for batch in batches:
        result = check(batch, everyone)
        if not result["ok"]:
            failed_checks.append(
                f"{batch.name}: {len(result['errors'])} errors - excluded from the merge"
            )
            continue
        people, relations = _read_batch(batch)
        name = batch.name

        def resolve(pid: str) -> str:
            pid, _ = splits.get((name, pid), (pid, ""))
            return aliases.get(pid, pid)

        for person in people:
            new_id = resolve(person.id)
            note = splits.get((name, person.id), (None, ""))[1]
            was_canonical = person.id == new_id
            person = replace(
                person,
                id=new_id,
                disambiguation=person.disambiguation or note,
                source=person.source or name,
            )
            staged[new_id].append((name, person))
            if was_canonical:
                canonical_records[new_id].append(person)
        for rel in relations:
            rel = replace(
                rel,
                src=resolve(rel.src),
                dst=resolve(rel.dst),
                source=rel.source or name,
            )
            all_relations.append((name, canonicalize(rel, vocab)))

    # -- audit before committing ----------------------------------------
    decided = set(identity.get("same") or {})
    decided |= {v["id"] for vs in (identity.get("distinct") or {}).values() for v in vs}
    decided |= set(identity.get("contested_parentage") or {})

    warnings: list[str] = []
    for pid, records in sorted(staged.items()):
        warnings.extend(_audit_merge(pid, records, decided))

    people = {
        pid: _merge_people([p for _, p in recs], canonical_records.get(pid))
        for pid, recs in staged.items()
    }

    # collapse duplicate relations, unioning their citations
    combined: dict[tuple[str, str, str], Relation] = {}
    for _, rel in all_relations:
        key = rel.key()
        if key in combined:
            existing = combined[key]
            for ref in rel.refs:
                if ref not in existing.refs:
                    existing.refs.append(ref)
            if rel.certainty == "explicit":
                existing.certainty = "explicit"
            if rel.note and rel.note not in existing.note:
                existing.note = "; ".join(filter(None, [existing.note, rel.note]))
            for src in rel.source.split(","):
                if src and src not in existing.source:
                    existing.source = ",".join(filter(None, [existing.source, src]))
        else:
            combined[key] = replace(rel, refs=list(rel.refs))

    relations = list(combined.values())

    # structural conflation check: one biological father per person
    functional = {n for n, t in vocab.types.items() if t.functional_inverse}
    incoming: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for rel in relations:
        if rel.type in functional:
            incoming[rel.dst][rel.type].add(rel.src)
    contested = identity.get("contested_parentage") or {}
    notes: list[str] = []
    for canonical, alternates in sorted((identity.get("provisional") or {}).items()):
        if canonical in people:
            notes.append(
                f"{canonical!r}: provisional identification, merged with "
                f"{', '.join(sorted(alternates or []))} - reasonable reading, not settled"
            )
    for child, by_type in sorted(incoming.items()):
        for rtype, srcs in by_type.items():
            if len(srcs) <= 1:
                continue
            if child in contested:
                # The text itself disagrees; keeping both parents with the
                # disagreement documented is the honest representation.
                notes.append(f"{child!r}: contested parentage kept - {contested[child]}")
                continue
            warnings.append(
                f"{child!r} has {len(srcs)} distinct {rtype} "
                f"({', '.join(sorted(srcs))}) - two people sharing an id, "
                "or a genuine textual disagreement; record the decision in "
                "ontology/identity.yaml"
            )

    orphans = sorted(
        {p for r in relations for p in (r.src, r.dst)} - set(people)
    )
    for pid in orphans:
        warnings.append(f"relation references {pid!r}, which no batch defines")

    by_source: dict[str, list[Relation]] = defaultdict(list)
    for rel in relations:
        by_source[rel.source.split(",")[0] or "misc"].append(rel)

    summary = {
        "batches": [b.name for b in batches],
        "excluded": failed_checks,
        "people": len(people),
        "relations": len(relations),
        "warnings": warnings,
        "notes": notes,
        "dry_run": dry_run,
        "dropped": _dropped(relations),
    }

    if not dry_run:
        PERSONS_DIR.mkdir(parents=True, exist_ok=True)
        RELATIONS_DIR.mkdir(parents=True, exist_ok=True)
        save_entities(people)
        for existing in RELATIONS_DIR.glob("*.jsonl"):
            existing.unlink()
        for source, rels in by_source.items():
            save_relations(rels, RELATIONS_DIR / f"{source}.jsonl")

    return summary


DERIVED_RELATIONS = {"concept-sort"}


def _dropped(relations: list) -> list[str]:
    """Relations the graph held a moment ago and will not hold after this.

    **Nothing in this pipeline reported what a merge left out, and that is how
    23 relations disappeared without anyone noticing.** A batch can fall out of
    the graph entirely while every number on screen looks healthy, because the
    totals move by thousands in the same breath.

    Compared by relation IDENTITY -- (src, type, dst) -- and not by per-source
    counts, which was the first version and produced false alarms immediately.
    Merging Mark reported seven sources "losing" relations; not one had lost
    anything. The same relation appearing in two batches is attributed to one
    of them, so a new batch winning attribution reads as the old batch
    shrinking. A report that cries loss over bookkeeping is one nobody reads,
    which is the failure it exists to prevent.

    So: what identities did the previous merge write that this one does not,
    and where did they come from. `ontology/relations/` is the previous
    output, one file per source, which makes it a free and exact record.
    """
    if not RELATIONS_DIR.exists():
        return []

    now = {(r.src, r.type, r.dst) for r in relations}
    lost: dict[str, int] = defaultdict(int)
    examples: dict[str, str] = {}
    for f in RELATIONS_DIR.glob("*.jsonl"):
        # Derived after the merge (conceptsort apply), never from a batch:
        # counting it would report the same edges DROPPED on every merge
        if f.stem in DERIVED_RELATIONS:
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = (row.get("src"), row.get("type"), row.get("dst"))
            if key not in now:
                lost[f.stem] += 1
                examples.setdefault(f.stem,
                                    f"{key[0]} -{key[1]}-> {key[2]}")

    out = []
    for source, n in sorted(lost.items(), key=lambda kv: -kv[1]):
        out.append(f"{source}: {n} relation(s) no longer in the graph "
                   f"(e.g. {examples[source]})")
    return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    result = merge(dry_run="--dry-run" in argv)

    if "error" in result:
        print(result["error"])
        return 1
    for line in result["excluded"]:
        print(f"EXCLUDED {line}")
    for line in result.get("notes", []):
        print(f"NOTED    {line}")
    for line in result["warnings"]:
        print(f"REVIEW   {line}")
    # Printed AFTER the reviews and before the totals, because it is the one
    # thing the totals cannot show. A merge that adds 3,000 and quietly stops
    # including 23 reports a healthy gain.
    for line in result.get("dropped", []):
        print(f"DROPPED  {line}")
    print(
        f"\n{len(result['batches'])} batches -> {result['people']} people, "
        f"{result['relations']} relations, {len(result['warnings'])} to review"
        + ("  (dry run, nothing written)" if result["dry_run"] else "")
    )
    if not result["dry_run"]:
        # This rebuild discarded everything derived that was sitting in the
        # output, because that is what a rebuild does. Anything computed rather
        # than authored has to be recomputed now, and the only reliable way to
        # remember is for the tool to say so at the moment it happens.
        print("\nderived values were discarded by the rebuild. Recompute:")
        print("  python -m bibleont.lemma apply")
        print("  python -m bibleont.conceptsort apply")
    return 1 if result["excluded"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
