"""Candidate batches from outside the trunk, and the gate they must pass.

The bottleneck on this graph is judgement, not typing. Finding that Col 1:10
joins fruit to works took a minute of reading and an hour of knowing where to
look; the reading is the cheap half. So the way to scale is not to have
something else do the judging -- it is to have something else do the looking,
at volume, and hand over only what survives a mechanical filter.

That filter already exists. `check_extraction` resolves every citation against
the corpus, checks every relation type against the vocabulary, and refuses a
relation whose cited verses do not name both parties. Measured over one
session of ordinary extraction it rejected five batches out of six on the
first run. A proposal that passes it is not necessarily good, but it is
already about a real verse, about real entities, in a real relation -- which
is most of what makes bad suggestions expensive to read.

## The contract

A proposal is a directory of exactly the same shape as a staging batch:

    ontology/proposals/<name>/
        entities.jsonl
        relations.jsonl
        META.json        who produced it, from what brief, when

Nothing about it is special. That is deliberate: promoting a proposal is a
copy, so there is no second format to keep in step with the first, and a
worker that learns to produce staging batches has learned the only format
this project has.

## What this module adds on top of the gate

Passing is necessary and not sufficient. Three further things are computable
without judgement and all three decide whether a proposal is worth opening:

- **Novelty.** How many of its relations the trunk does not already hold. A
  batch that restates two hundred known facts passes every check and is worth
  nothing.
- **Dangling references.** Relations pointing at ids that exist neither in the
  trunk nor in the batch itself. Mechanically detectable, and the clearest
  signal that a worker was generating rather than reading.
- **Citation reach.** How many distinct books the proposal touches. A batch
  confined to one chapter is doing what a person could have asked for; one
  that joins Habakkuk to Hebrews is doing what the crawler was for.

Ranking by those three is what puts the best proposal on top, and none of it
needs a model.

## What this module refuses to do

It does not promote automatically, at any score. The gate keeps out what is
malformed; it cannot see an edge that is well-formed, well-cited and asserts
something the corpus does not say. That judgement is the whole product, and
it stays with a reader who is accountable for it.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from bibleont.check_extraction import check
from bibleont.paths import ROOT

PROPOSALS = ROOT / "ontology" / "proposals"
STAGING = ROOT / "ontology" / "staging"
# Relations the gate refused individually. Kept rather than dropped: they are
# the only measurement of how often the extractor gets a quotation wrong, and
# the rate is the thing the prompt is being tuned against.
HELD = PROPOSALS / ".held"
REJECTED = PROPOSALS / ".rejected"


# ---------------------------------------------------------------------------
# the trunk, read once
# ---------------------------------------------------------------------------

def _graph_entities() -> dict:
    """Every record the merged graph already holds, for `check`.

    A farm batch reuses ids from the vocabulary it was given, so checking it
    in isolation reports the reused ones as missing. Passing the graph is what
    makes "reuse these ids" and "every id must exist" stop contradicting each
    other.
    """
    try:
        from .schema import load_entities
        return load_entities()
    except Exception:                                        # noqa: BLE001
        return {}


def _trunk() -> tuple[set[str], set[tuple[str, str, str]]]:
    """Ids and relation keys the graph already holds."""
    ids: set[str] = set()
    ents = ROOT / "ontology" / "entities" / "entities.jsonl"
    if ents.exists():
        for line in ents.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ids.add(json.loads(line)["id"])

    keys: set[tuple[str, str, str]] = set()
    reldir = ROOT / "ontology" / "relations"
    if reldir.exists():
        for p in reldir.glob("*.jsonl"):
            for line in p.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                keys.add((r["src"], r["type"], r["dst"]))
    return ids, keys


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


# ---------------------------------------------------------------------------
# the quote check
# ---------------------------------------------------------------------------
#
# Every note in this graph rests its claim on words from a cited verse, and by
# convention it quotes them. That convention turns out to be mechanically
# enforceable, and enforcing it is the single most effective guard available
# against a model that writes fluently and reads carelessly: a fabricated
# citation and a correct quotation cannot both be produced from nothing.
#
# The check is deliberately forgiving about everything that is not the words.
# Case, whitespace, and the ellipsis a writer uses to skip a clause are all
# normalised away, because none of them is where invention happens.

import re as _re

# An apostrophe is a quote mark and also a letter. "David's" is not the start
# of a quotation, and a naive delimiter turns every possessive in the corpus
# into a false report -- 293 of them on the first run over this graph.
#
# So a mark only opens a quotation when no letter precedes it, only closes one
# when no letter follows, and is treated as part of a word whenever letters
# stand on both sides.
_QUOTED = _re.compile(
    r"(?<![A-Za-z])['‘“]"
    r"((?:[^'’”]|(?<=[A-Za-z])['’](?=[A-Za-z])){12,}?)"
    r"['’”](?![A-Za-z])"
)
_TIDY = _re.compile(r"[^a-z0-9 ]+")


def _flatten(text: str) -> str:
    text = text.lower().replace("æ", "ae").replace("œ", "oe")
    return " ".join(_TIDY.sub(" ", text).split())


def _corpus_index() -> dict[str, str]:
    from bibleont.paths import text_path
    idx: dict[str, str] = {}
    path = text_path()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if "t" in r:
            idx[f'{r["b"]} {r["c"]}:{r["v"]}'] = _flatten(r["t"])
    return idx


_RANGE = _re.compile(r"^(.+ \d+):(\d+)\s*-\s*(\d+)$")


def _expand(ref: str) -> list[str]:
    """'Rom 16:3-4' -> ['Rom 16:3', 'Rom 16:4'].

    The corpus is cited both ways in this graph and a checker that reads only
    single verses reports every ranged citation as unresolvable.
    """
    m = _RANGE.match(str(ref).strip())
    if not m:
        return [str(ref)]
    head, first, last = m.group(1), int(m.group(2)), int(m.group(3))
    if last < first or last - first > 40:
        return [str(ref)]
    return [f"{head}:{v}" for v in range(first, last + 1)]


def unquoted(rels: list[dict], idx: dict[str, str] | None = None) -> list[str]:
    """Relations whose note quotes something its cited verses do not say.

    A note with no quotation at all is not reported here -- that is a matter of
    style and the reader can judge it. What is reported is a note that appears
    to quote and does not, which is the failure that matters.
    """
    idx = _corpus_index() if idx is None else idx
    bad: list[str] = []
    for r in rels:
        note = r.get("note") or ""
        spans = _QUOTED.findall(note)
        if not spans:
            continue
        # A citation may be spread over several verses, and a note may quote
        # across a verse boundary, so the haystack is everything it cites --
        # plus, for the same reason, the verses either side are not included:
        # a note that quotes uncited context is citing the wrong verse.
        hay = " ".join(idx.get(v, "")
                       for ref in r.get("refs", []) for v in _expand(ref))
        if not hay:
            bad.append(f'{r.get("src")} -{r.get("type")}-> {r.get("dst")}: '
                       f'no cited verse resolves')
            continue
        for span in spans:
            # An ellipsis means "and then, later in the passage" -- each side
            # has to appear, but not adjacently.
            # Editorial insertions -- "his [Jehoahaz's] brother" -- are the
            # writer supplying a referent the verse leaves to context. They
            # are not part of the quotation and must not be matched against
            # the text.
            span = _re.sub(r"\[[^\]]*\]", " ", span)
            parts = [p for p in _re.split(r"\s*\.\.\.\s*|\s*…\s*", span) if p.strip()]
            for part in parts:
                flat = _flatten(part)
                if len(flat) < 12:
                    continue
                if flat not in hay:
                    bad.append(f'{r.get("src")} -{r.get("type")}-> {r.get("dst")}: '
                               f'quoted "{part.strip()[:70]}" is not in {r.get("refs")}')
    return bad


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# pass one's annotations
# ---------------------------------------------------------------------------
#
# The standing reviewer writes `review.jsonl` beside a proposal: one verdict
# per relation, each naming a check and quoting the words that decided it.
#
# **Annotations never block.** A flagged relation is not removed and not
# refused at promotion; it is sorted to the top of the queue, which is the
# only thing a pass-one reviewer is reliable enough to do. A blocked item is
# invisible and a wrong block is a lost relation; a wrong flag costs a moment.
#
# They also never promote. A batch the reviewer likes is exactly as unapproved
# as one it has not seen.

def _annotations(batch: Path) -> list[dict]:
    p = batch / "review.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


@dataclass
class Assessment:
    name: str
    ok: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    entities: int = 0
    relations: int = 0
    new_entities: int = 0
    new_relations: int = 0
    duplicate_relations: int = 0
    dangling: list[str] = field(default_factory=list)
    misquoted: list[str] = field(default_factory=list)
    flagged: list[dict] = field(default_factory=list)
    unquoted_flags: int = 0
    books: int = 0
    meta: dict = field(default_factory=dict)

    @property
    def worth(self) -> float:
        """A rough ordering, not a verdict.

        New relations are the product. Duplicates and dangling references are
        the cost of reading past them. Reach across books is what a wide,
        cheap pass can find that a person working through a chapter cannot,
        so it is a multiplier rather than an addition.
        """
        if not self.ok:
            return -1.0
        signal = self.new_relations - 0.5 * self.duplicate_relations
        signal -= 2.0 * len(self.dangling)
        # A misquotation is worse than a dangling id. A bad id is a mistake; a
        # quotation the verse does not contain is the one failure that looks
        # exactly like good work until someone opens the Bible.
        signal -= 4.0 * len(self.misquoted)
        return round(max(signal, 0.0) * (1.0 + self.books / 10.0), 1)


def assess(batch: Path, ids: set[str] | None = None,
           keys: set[tuple[str, str, str]] | None = None) -> Assessment:
    """Run the gate, then measure what passing actually got us."""
    if ids is None or keys is None:
        ids, keys = _trunk()

    a = Assessment(name=batch.name)
    meta = batch / "META.json"
    if meta.exists():
        try:
            a.meta = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:
            a.meta = {"unreadable": True}

    result = check(batch, _graph_entities())
    a.ok = bool(result.get("ok"))
    a.errors = list(result.get("errors", []))
    a.warnings = list(result.get("warnings", []))

    ents = _rows(batch / "entities.jsonl")
    rels = _rows(batch / "relations.jsonl")
    a.entities, a.relations = len(ents), len(rels)

    local = {e["id"] for e in ents}
    a.new_entities = len(local - ids)

    books: Counter[str] = Counter()
    for r in rels:
        key = (r.get("src"), r.get("type"), r.get("dst"))
        if key in keys:
            a.duplicate_relations += 1
        else:
            a.new_relations += 1
        for end in (r.get("src"), r.get("dst")):
            if end not in ids and end not in local:
                a.dangling.append(f'{r.get("src")} -{r.get("type")}-> {r.get("dst")} '
                                  f'(unknown id: {end})')
        for ref in r.get("refs", []):
            books[str(ref).split()[0]] += 1
    for e in ents:
        for ref in e.get("refs", []):
            books[str(ref).split()[0]] += 1
    a.books = len(books)
    a.misquoted = unquoted(rels)

    # Pass one's verdicts. They change the order of the queue and nothing
    # else -- not the score, not whether promotion is allowed.
    for v in _annotations(batch):
        if v.get("verdict") != "bad":
            continue
        if not str(v.get("quote", "")).strip():
            a.unquoted_flags += 1
            continue
        a.flagged.append(v)
    return a


def faulty(batch: Path, ids: set[str] | None = None
           ) -> tuple[list[int], dict[int, str], list[str]]:
    """Which individual relations the gate objects to, and why.

    The gate's judgements are already per-relation -- a quotation is in its
    verse or it is not, an id exists or it does not -- but promotion applied
    them per BATCH. That was right when a batch was one chapter of a hundred
    relations. It stopped being right at 4,641: Job passed every structural
    check and was refused whole over 25 notes, holding back 4,616 sound ones,
    and re-running the book to recover them would have cost more than it cost
    to produce and would have landed the same faults at the same rate.

    Measured across every batch on disk, misquotation runs at about 0.5%
    regardless of book or genre. That is the number that makes batch-level
    refusal untenable: it means a large batch is *expected* to contain some,
    so all-or-nothing does not mean "clean or nothing", it means "small or
    nothing".

    This does not soften the gate. The faulty relations are still refused --
    individually, with their reasons, into a file that stays behind. What
    changes is that a bad note costs the note instead of the book.

    Returns the faulty indices, the reason for each, and **the errors that
    could not be pinned on any relation**. That third value is the honest
    part: a malformed entity line, or a check that objects to the batch as a
    whole, has no single row to withhold, and promotion must still refuse.
    Deciding that by pattern-matching the error text -- which is what the
    first version did -- got it wrong the moment a check reported in a shape
    the pattern did not expect.
    """
    if ids is None:
        ids, _ = _trunk()
    rels = _rows(batch / "relations.jsonl")
    local = {e["id"] for e in _rows(batch / "entities.jsonl")}
    key = lambda r: f'{r.get("src")} -{r.get("type")}-> {r.get("dst")}'  # noqa: E731

    why: dict[int, str] = {}
    for i, r in enumerate(rels):
        for end in (r.get("src"), r.get("dst")):
            if end not in ids and end not in local:
                why[i] = f"dangling reference: {end} does not exist"
    # unquoted() reports by relation identity rather than index, so map back
    # through the same rendering it uses.
    for line in unquoted(rels):
        head, _, reason = line.partition(": ")
        for i, r in enumerate(rels):
            if key(r) == head and i not in why:
                why[i] = reason or "quotes what the cited verses do not say"

    # The gate's own errors, which are mostly type violations -- a star typed
    # as an idea, a saying built out of an abstraction. These are the ones
    # that most deserve holding rather than fixing: each is a single relation
    # disagreeing with the vocabulary, and the vocabulary is usually right.
    # Every index for a key, not the last one. A batch can assert the same
    # (src, type, dst) more than once -- Genesis does it 124 times, from
    # different verses -- and a dict comprehension keeps only the final
    # occurrence. Quarantine then held one copy of a faulty relation and
    # promoted the other, and `merge` re-ran the same check and excluded the
    # whole batch, which is the failure quarantine exists to prevent.
    rendered: dict[str, list[int]] = {}
    for i, r in enumerate(rels):
        rendered.setdefault(key(r), []).append(i)
    conflation = _re.compile(
        r"person '(?P<child>[^']+)' is given \d+ different (?P<type>\w+) "
        r"\((?P<parents>[^)]*)\)")
    unmapped: list[str] = []
    for line in check(batch, _graph_entities()).get("errors", []):
        head, _, reason = line.partition(": ")
        hits = rendered.get(head.strip())
        if hits:
            for i in hits:
                if i not in why:
                    why[i] = reason.strip() or "refused by the gate"
            continue

        # A conflation error names a child and several parents rather than one
        # edge, so it read as "not attributable to a single relation" and
        # refused the whole batch -- 6,172 Genesis relations held by one, over
        # Laban being called the son of Nahor (Gen 29:5) as well as of Bethuel
        # (Gen 28:5). Both verses are right; Nahor is his grandfather.
        #
        # It IS attributable: the message names every edge involved. Hold all
        # of them rather than guessing which is the literal generation --
        # the gate cannot know, and picking one silently would be the graph
        # deciding a question about the text on its own authority.
        m = conflation.search(line)
        if m:
            parents = [p.strip() for p in m.group("parents").split(",") if p.strip()]
            hit = False
            for i, r in enumerate(rels):
                if (r.get("dst") == m.group("child")
                        and r.get("type") == m.group("type")
                        and r.get("src") in parents):
                    hit = True
                    if i not in why:
                        why[i] = (f"{r.get('src')} is one of {len(parents)} different "
                                  f"{m.group('type')} given for {m.group('child')} -- "
                                  f"held until the graph says which is meant")
            if hit:
                continue
        unmapped.append(line)
    return sorted(why), why, unmapped


def survey() -> list[Assessment]:
    if not PROPOSALS.exists():
        return []
    ids, keys = _trunk()
    out = []
    for d in sorted(PROPOSALS.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        out.append(assess(d, ids, keys))
    # Flagged first, then by value. Pass one moves things up the queue;
    # it does not decide what they are worth.
    return sorted(out, key=lambda a: (-len(a.flagged), -a.worth))


# ---------------------------------------------------------------------------
# the brief a worker is given
# ---------------------------------------------------------------------------

def spec() -> str:
    """The contract, generated from the schema so it cannot drift from it."""
    from bibleont.schema import load_vocabulary

    vocab = load_vocabulary()
    types = sorted(vocab.types)
    lines = [
        "# What a proposal must be",
        "",
        "Write two JSONL files into `ontology/proposals/<your-batch-name>/`.",
        "Nothing is accepted that does not pass `bibleont.check_extraction`.",
        "",
        "## entities.jsonl -- one JSON object per line",
        "",
        '    {"id": "...", "name": "...", "type": "...", "gender": "unknown",',
        '     "refs": ["Book C:V", ...], "source": "<your-batch-name>"}',
        "",
        "`name` must be a string that actually appears in one of the cited",
        "verses, or the citation check will reject every relation that uses",
        "the record. Add spellings other books use as `aka`.",
        "",
        "## relations.jsonl -- one JSON object per line",
        "",
        '    {"src": "...", "type": "...", "dst": "...",',
        '     "certainty": "explicit|implied|disputed",',
        '     "refs": ["Book C:V", ...], "source": "<your-batch-name>",',
        '     "note": "quote the words the claim rests on"}',
        "",
        "**Both ends must be stated in this batch**, even when the trunk",
        "already holds them. The check reads one batch at a time and cannot",
        "see the rest of the graph.",
        "",
        "**`explicit` means the cited verse names both parties.** If it names",
        "only one, the certainty is `implied` and the note must say what step",
        "is being taken and by whom.",
        "",
        f"## The {len(types)} permitted relation types",
        "",
    ]
    for i in range(0, len(types), 4):
        lines.append("    " + "  ".join(f"{t:<24}" for t in types[i:i + 4]).rstrip())
    lines += [
        "",
        "## What gets a proposal rejected on sight",
        "",
        "- A relation whose `src` or `dst` is an id that exists nowhere.",
        "- A `note` that explains a reading instead of quoting the text.",
        "- A relation the graph already holds, restated.",
        "- Anything asserting what a passage *means* where the corpus only",
        "  says what it *says*. Record the words; leave the conclusion to a",
        "  reader.",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def _render(a: Assessment, verbose: bool = False) -> None:
    mark = "PASS" if a.ok else "FAIL"
    src = a.meta.get("worker") or a.meta.get("source") or "-"
    print(f"{mark:5} {a.worth:7.1f}  {a.name:34} "
          f"{a.new_relations:4} new / {a.relations:4} rels  "
          f"{a.new_entities:3} new ents  {a.books:2} books  [{src}]")
    if a.duplicate_relations:
        print(f"{'':14}{a.duplicate_relations} relation(s) the graph already holds")
    if a.dangling:
        print(f"{'':14}{len(a.dangling)} dangling reference(s)")
        for d in a.dangling[:3] if not verbose else a.dangling:
            print(f"{'':16}{d}")
    if a.flagged:
        print(f"{'':14}{len(a.flagged)} flagged by pass one "
              f"(check {', '.join(sorted({str(v.get('check')) for v in a.flagged}))})")
        for v in (a.flagged[:3] if not verbose else a.flagged):
            print(f"{'':16}{v.get('id','?')}")
            print(f"{'':18}check {v.get('check')}: {str(v.get('why',''))[:96]}")
            print(f'{"":18}quoted "{str(v.get("quote",""))[:80]}"')
    if a.unquoted_flags:
        print(f"{'':14}{a.unquoted_flags} flag(s) with no quote -- ignored, "
              f"a reviewer that does not quote is guessing")
    if a.misquoted:
        print(f"{'':14}{len(a.misquoted)} MISQUOTATION(S) -- note quotes what the verse does not say")
        for m in a.misquoted[:3] if not verbose else a.misquoted:
            print(f"{'':16}{m}")
    if verbose:
        for e in a.errors:
            print(f"{'':14}ERROR   {e}")
        for w in a.warnings:
            print(f"{'':14}WARNING {w}")
    elif a.errors:
        print(f"{'':14}{len(a.errors)} error(s) -- run `check {a.name}` to see them")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "list"

    if cmd == "spec":
        print(spec())
        return 0

    if cmd == "audit":
        # The same check, turned on the trunk. A note that quotes a verse the
        # relation does not cite is usually right about the words and wrong
        # about the reference, which is the quietest way a citation goes bad:
        # the claim is true, the trail to it is broken, and nothing else in
        # the pipeline can see it.
        import pathlib as _pl
        rels = []
        for f in _pl.Path(ROOT / "ontology" / "relations").glob("*.jsonl"):
            rels.extend(_rows(f))
        noted = [r for r in rels if (r.get("note") or "").strip()]
        bad = unquoted(rels)
        for b in bad:
            print(f"  {b}")
        print()
        print(f"{len(rels)} relations, {len(noted)} with notes, "
              f"{len(bad)} quoting words their cited verses do not contain.")
        return 0

    if cmd == "list":
        rows = survey()
        if not rows:
            print(f"nothing proposed. Workers write into {PROPOSALS}")
            return 0
        for a in rows:
            _render(a)
        passing = sum(1 for a in rows if a.ok)
        print(f"\n{len(rows)} proposal(s), {passing} through the gate. "
              f"Ranked by new relations, weighted by reach across books, "
              f"penalised for duplicates and dangling ids.")
        print("Passing the gate is not approval. Read before promoting.")
        return 0

    if cmd in ("check", "promote", "reject") and len(argv) < 2:
        print(f"usage: {cmd} <batch-name>")
        return 2

    if cmd == "check":
        d = PROPOSALS / argv[1]
        if not d.is_dir():
            print(f"no such proposal: {argv[1]}")
            return 1
        _render(assess(d), verbose=True)
        return 0

    if cmd == "promote":
        d = PROPOSALS / argv[1]
        if not d.is_dir():
            print(f"no such proposal: {argv[1]}")
            return 1
        a = assess(d)
        quarantine = "--quarantine" in argv
        if not a.ok and not quarantine:
            print(f"refused: {argv[1]} does not pass the gate "
                  f"({len(a.errors)} error(s)). Nothing was copied.")
            return 1
        if quarantine:
            # Quarantine can only hold faults that belong to a RELATION. A
            # malformed entity line, or a check that objects to the batch as a
            # whole, has no single row to withhold -- so it still refuses, and
            # should. `faulty` reports which those are rather than the caller
            # guessing from the error text.
            _, _, unmapped = faulty(d)
            if unmapped:
                print(f"refused: {argv[1]} has {len(unmapped)} error(s) that "
                      f"cannot be pinned on one relation. Nothing was copied.")
                for e in unmapped[:5]:
                    print(f"    {e[:120]}")
                return 1
        if (a.dangling or a.misquoted or not a.ok) and not quarantine:
            if a.dangling:
                print(f"refused: {argv[1]} has {len(a.dangling)} dangling "
                      f"reference(s). Nothing was copied.")
            if a.misquoted:
                print(f"refused: {argv[1]} has {len(a.misquoted)} note(s) "
                      f"quoting words the cited verses do not contain. "
                      f"Nothing was copied.")
            n = len(a.dangling) + len(a.misquoted)
            print(f"\n{n} of {a.relations} relations are at fault "
                  f"({100 * n / max(a.relations, 1):.1f}%). To hold those back "
                  f"and promote the rest:")
            print(f"    python -m bibleont.proposals promote {argv[1]} --quarantine")
            return 1
        dest = STAGING / argv[1]
        if dest.exists():
            print(f"refused: {dest} already exists. Rename the proposal or "
                  f"merge it by hand.")
            return 1
        dest.mkdir(parents=True)
        held = 0
        for f in ("entities.jsonl", "relations.jsonl"):
            if not (d / f).exists():
                continue
            if quarantine and f == "relations.jsonl":
                bad_idx, why, _ = faulty(d)
                rows = _rows(d / f)
                keep = [r for i, r in enumerate(rows) if i not in why]
                held = len(rows) - len(keep)
                with open(dest / f, "w", encoding="utf-8", newline="") as fh:
                    for r in keep:
                        fh.write(json.dumps(r, ensure_ascii=False,
                                            sort_keys=True) + "\n")
                # The refused ones stay, with their reasons attached, beside
                # the batch they came from. They are evidence about the
                # process -- deleting them would destroy the only record of
                # what the extractor got wrong and how often.
                if held:
                    HELD.mkdir(parents=True, exist_ok=True)
                    with open(HELD / f"{argv[1]}.jsonl", "w",
                              encoding="utf-8", newline="") as fh:
                        for i in bad_idx:
                            fh.write(json.dumps(
                                {**rows[i], "_refused": why[i]},
                                ensure_ascii=False, sort_keys=True) + "\n")
            else:
                shutil.copy2(d / f, dest / f)
        # What was promoted must pass the gate it was filtered against.
        #
        # It did not, once: quarantine held one copy of a relation the batch
        # asserted twice and promoted the other, `merge` re-ran the same check
        # and excluded all 6,104 relations, and the only symptom was a total
        # that did not move. Verifying here turns that into a refusal at the
        # step that caused it, which is where it can be understood.
        if quarantine:
            left = check(dest, _graph_entities())
            if not left.get("ok"):
                shutil.rmtree(dest)
                print(f"refused: quarantine left {len(left.get('errors') or [])} "
                      f"error(s) in {argv[1]}, so the promoted batch would have "
                      f"been excluded at merge. Nothing was copied.")
                for e in (left.get("errors") or [])[:5]:
                    print(f"    {str(e)[:120]}")
                return 1

        shutil.rmtree(d)
        print(f"promoted to {dest}")
        if held:
            print(f"held back {held} relation(s) -> {HELD / (argv[1] + '.jsonl')}")
            print("Those are a measurement of the extractor, not a to-do list:")
            print("fix what produced them, do not edit them into the graph.")
        print("Now run: merge, then validate.")
        return 0

    if cmd == "reject":
        d = PROPOSALS / argv[1]
        if not d.is_dir():
            print(f"no such proposal: {argv[1]}")
            return 1
        why = ""
        if "--why" in argv:
            why = argv[argv.index("--why") + 1]
        REJECTED.mkdir(parents=True, exist_ok=True)
        dest = REJECTED / argv[1]
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(d), str(dest))
        # Kept rather than deleted: a rejected batch is the only record of
        # what a brief actually produced, and briefs are tuned by reading it.
        (dest / "REJECTED.txt").write_text(why + "\n", encoding="utf-8")
        print(f"rejected -> {dest}")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
