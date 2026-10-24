"""Confidence testing: sample the graph, judge it, keep the score.

The validator proves consistency -- every citation resolves, every type exists,
nobody has two fathers by accident. It cannot see a relation that was never
recorded, a plausible-but-wrong choice of type, or a person missed entirely.
An absence passes every mechanical test there is.

So a sample gets read and judged, and the point is a **baseline that can be
compared after the next extraction round**, not a one-off verdict. A single
number would be useless; the output names which batches are weak.

Three roles, and only one of them needs a reader:

- `sample` builds a stratified selection with the evidence attached -- the
  claim, the cited verse, and the verses either side of it, which is what a
  judge needs and is otherwise tedious to assemble.
- `completeness` runs mechanically. For a sampled chapter it lists the proper
  nouns the graph has no name for, which is the entity-completeness dimension
  with no judgment required.
- `score` aggregates verdicts by dimension and by batch and diffs against the
  stored baseline.

Sampling is **stratified and seeded**, not random. The strata are where
systematic failure hides: every batch is represented, because one agent with
one misunderstanding produced all of it, and the batches known to be careful
are kept in as controls. Without a control there is no way to tell a bad batch
from a bad judge.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .corpus import get_corpus
from .graph import Store
from .paths import ROOT

BASELINE = ROOT / "docs" / "audit-baseline.json"

# Batches to over-sample, and why. The early work used cheaper models and is the
# known risk; the Samuel batches were careful and ride along as controls.
WEIGHT = {
    "josh-judg-ruth": 3,
    "gospels-recall": 3,
    "judges-recall": 3,
    "1chr": 2,
    "1sam": 2,   # control
    "2sam": 2,   # control
}
CONTROLS = {"1sam", "2sam"}

VERDICTS = ("supported", "wrong_type", "unsupported", "contradicted")


@dataclass
class Item:
    """One relation, with everything a judge needs to rule on it."""

    batch: str
    claim: str
    type: str
    certainty: str
    refs: list[str]
    note: str = ""
    verses: list[str] = field(default_factory=list)
    context: list[str] = field(default_factory=list)
    verdict: str = ""      # filled in by the judge
    comment: str = ""


def sample(size: int = 30, seed: int = 3, store: Store | None = None) -> list[Item]:
    s = store or Store.load()
    corpus = get_corpus()

    by_batch: dict[str, list] = {}
    for rel in s.relations:
        by_batch.setdefault(rel.source, []).append(rel)

    rng = random.Random(seed)
    picked = []
    for batch, rows in sorted(by_batch.items()):
        k = min(WEIGHT.get(batch, 1), len(rows))
        picked += rng.sample(rows, k)
    rng.shuffle(picked)
    picked = picked[:size]

    out: list[Item] = []
    for rel in picked:
        verses, context = [], []
        for ref in rel.refs[:2]:
            try:
                found = corpus.verses_for(ref)
            except Exception:
                continue
            for v in found[:2]:
                verses.append(f"{v.id.pretty()}  {v.text}")
                # The verse either side, because a pronoun three words in is
                # often the only thing naming the party.
                for offset in (-1, 1):
                    n = v.id.verse + offset
                    if n < 1:
                        continue
                    try:
                        near = corpus.verses_for(f"{v.id.book} {v.id.chapter}:{n}")
                    except Exception:
                        continue
                    for w in near[:1]:
                        context.append(f"{w.id.pretty()}  {w.text}")
        out.append(
            Item(
                batch=rel.source,
                claim=s.describe(rel),
                type=rel.type,
                certainty=rel.certainty,
                refs=list(rel.refs),
                note=rel.note or "",
                verses=verses,
                context=context,
            )
        )
    return out


def completeness(book: str, chapter: int, store: Store | None = None) -> dict:
    """Entity completeness for one chapter, with no judgment required.

    Names the chapter uses that the graph has no name for. This is the
    Oreb-and-Zeeb class -- a figure named in the text and absent from the
    graph -- and it is the one dimension a machine can score honestly.
    """
    from .gaps import survey

    s = store or Store.load()
    rows = [g for g in survey(s, book=book) if g.first.startswith(f"{book} ")
            or f" {chapter}:" in g.first]
    return {
        "book": book,
        "chapter": chapter,
        "unmatched": [{"word": g.word, "count": g.count, "first": g.first} for g in rows],
    }


def score(items: list[Item]) -> dict:
    """Aggregate verdicts by dimension and by batch."""
    judged = [i for i in items if i.verdict]
    by_batch: dict[str, dict[str, int]] = {}
    totals: dict[str, int] = {v: 0 for v in VERDICTS}
    for i in judged:
        totals[i.verdict] = totals.get(i.verdict, 0) + 1
        # A relation merged from several batches carries all their names, so
        # credit each one. Keying on the compound string instead put almost
        # every item in a batch of its own and left the control at one item,
        # which is no control at all.
        for b in i.batch.split(","):
            slot = by_batch.setdefault(b.strip(), {v: 0 for v in VERDICTS})
            slot[i.verdict] = slot.get(i.verdict, 0) + 1

    n = len(judged)
    supported = totals.get("supported", 0)
    control = [i for i in judged
               if CONTROLS & {b.strip() for b in i.batch.split(",")}]
    control_ok = sum(1 for i in control if i.verdict == "supported")
    return {
        "judged": n,
        "precision": round(supported / n, 3) if n else None,
        "totals": totals,
        "by_batch": by_batch,
        # If the controls score no better than the rest, the judge is the
        # problem rather than the batches.
        "control": {"judged": len(control), "supported": control_ok},
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Sample the graph and score a judgment.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sample", help="write a stratified sample for judging")
    p.add_argument("--size", type=int, default=30)
    p.add_argument("--seed", type=int, default=3)
    p.add_argument("--out", default="audit-sample.json")

    p = sub.add_parser("score", help="aggregate a judged sample")
    p.add_argument("file")
    p.add_argument("--save-baseline", action="store_true")

    args = ap.parse_args(argv)

    if args.cmd == "sample":
        items = sample(args.size, args.seed)
        Path(args.out).write_text(
            json.dumps([asdict(i) for i in items], indent=1), encoding="utf-8"
        )
        print(f"{len(items)} items -> {args.out}")
        for i, item in enumerate(items, 1):
            print(f"\n--- {i}. [{item.batch}] {item.claim}  ({item.type}, {item.certainty})")
            for v in item.verses:
                print(f"      {v[:150]}")
        return 0

    raw = json.loads(Path(args.file).read_text(encoding="utf-8"))
    items = [Item(**r) for r in raw]
    result = score(items)
    print(json.dumps(result, indent=1))
    if result["judged"] < len(items):
        print(f"\n  {len(items) - result['judged']} of {len(items)} still unjudged")
    if args.save_baseline:
        BASELINE.write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(f"\nbaseline written to {BASELINE}")
    elif BASELINE.exists():
        old = json.loads(BASELINE.read_text(encoding="utf-8"))
        if old.get("precision") is not None and result["precision"] is not None:
            print(f"\nprecision {old['precision']} -> {result['precision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
