"""Turn a proposed grouping into a staged batch the ordinary merge can take.

2026-09-01: the plan was to complete Genesis and Job grouping and merge it in
-- and then, before any of it landed, to visualize the groupings before
merging in. So this writes a batch and stops. `merge` is a separate command
run by a person who has looked.

## A passage stores a span, and membership is computed

The obvious design gives every claim an edge to the passage holding it. It is
wrong twice over. Genesis alone would take about 4,700 such edges, which is as
many as the book's entire claim set -- doubling the graph to record something
already implied. And every one of them goes stale the moment a seam moves,
because the edge names a passage rather than a position.

**So a passage carries `refs` -- its verse span -- and nothing else, and a
claim belongs to the passage whose span contains the verse it cites.** That is
the rule that anything mechanically derivable from what you already
hold is produced on demand, because storing it doubles the surface that can go
stale and creates a second source of truth that will eventually disagree with
the first. Re-grouping a book then orphans nothing; it changes spans, and
membership follows.

What IS stored is what cannot be derived:

    passage      id, name, the span it covers, and the evidence for its seam
    part_of      passage inside passage. The nesting is a judgement and no
                 arithmetic recovers it from spans alone -- 1-12 containing
                 1-5 and 6-12 is a choice, not a consequence.
    pattern      a repeated form, and instance_of from each member

`addressed_to` is NOT stored. 2026-09-02: it can and should be derived from a
single scroll assertion unless there is dialog -- so it is one fact at
the scroll rather than 31 copies across passages, and it descends.

## What this layer is, and is not

2026-09-02: a passage is more the overlay than the core meaning. The
claims are the meaning; this layer organises them so a reader can find their
way. Widening `part_of` to take a passage lets the overlay have a shape -- it
does not make the overlay into content, and nothing here should ever be the
thing a reader is asked to believe.

## The seam evidence is kept on the node

`because` quotes the words that mark the seam, and it goes into `desc` rather
than being dropped. It is the only thing standing between a reader and taking
a boundary on trust, and this project's whole argument is that it does not ask
for trust. A passage whose evidence quotes nothing is still written -- the
review page flags it -- because silently dropping it would be the graph
deciding what a reader may doubt.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from .paths import ROOT

PROPOSALS = ROOT / "ontology" / "proposals"
STAGING = ROOT / "ontology" / "staging"


def _span_refs(book: str, ch: int, lo: int, hi: int) -> list[str]:
    """A passage's citation. One ref for one verse, else first and last.

    Deliberately not every verse in between. A forty-verse passage citing
    forty refs makes the citation lists useless everywhere they are displayed,
    and the span is recoverable from its ends.
    """
    return [f"{book} {ch}:{lo}"] if lo == hi else [f"{book} {ch}:{lo}",
                                                   f"{book} {ch}:{hi}"]


def build(book: str) -> dict:
    src = PROPOSALS / f"{book.lower()}-groups"
    # Chapter files only. level*.json is the climb and 014-deep.json
    # is a side-by-side run; neither is a chapter.
    files = sorted(x for x in src.glob("*.json") if x.stem.isdigit())
    if not files:
        raise SystemExit(f"no grouping at {src} -- run `group {book} --book` first")

    ents: list[dict] = []
    rels: list[dict] = []
    source = f"{book.lower()}-groups"
    seen: set[str] = set()
    skipped: list[str] = []

    for f in files:
        ch = int(f.stem)
        d = json.loads(f.read_text(encoding="utf-8"))
        by_id = {str(p.get("id")): p for p in (d.get("passages") or [])}

        for p in d.get("passages") or []:
            pid = str(p.get("id") or "").strip()
            vs = p.get("verses") or []
            if not pid or len(vs) != 2 or not all(isinstance(x, int) for x in vs):
                skipped.append(f"{book} {ch}: {pid or '(no id)'} has no usable span")
                continue
            if pid in seen:
                skipped.append(f"{book} {ch}: {pid} declared twice")
                continue
            seen.add(pid)
            because = (p.get("because") or "").strip()
            ents.append({
                "id": pid,
                "name": (p.get("name") or pid)[:80],
                "type": "passage",
                "refs": _span_refs(book, ch, vs[0], vs[1]),
                "desc": because[:400],
                "source": source,
                "attrs": {"seam_evidence_quotes": bool(re.search(r"[\"'“‘]", because))},
            })
            parent = (p.get("part_of") or "").strip()
            if parent:
                if parent in by_id:
                    rels.append({"src": pid, "type": "part_of", "dst": parent,
                                 "certainty": "explicit",
                                 "refs": _span_refs(book, ch, vs[0], vs[1]),
                                 "note": because[:200], "source": source})
                else:
                    # A dangling parent is dropped and SAID. Mark 16 produced
                    # one, naming a passage it never declared.
                    skipped.append(f"{book} {ch}: {pid} part_of {parent!r} "
                                   "which was never declared")
            # ADDRESSEE IS DERIVED FROM THE SCROLL, NOT STORED PER PASSAGE.
            #
            # 2026-09-02: addressed_to is intuitive and is something that
            # needs to be known, but it can and should be derived from a
            # single scroll assertion unless there is dialog.
            #
            # Storing it per passage was the wrong shape twice
            # over. It is 31 copies of one fact across Genesis and Job, and
            # every one goes stale the moment a seam moves -- which is
            # the rule that anything derivable is computed rather than stored.
            #
            # It also matches what was measured: 53% of Genesis's turns, 78%
            # of Job's and 93% of Mark's never state who they are addressed
            # to. A fact that absent has to descend from above or it does not
            # exist, and descending is exactly what a scroll-level assertion
            # does for free.
            #
            # So the grouping pass's `addressed_to` is kept in the proposal
            # for review and deliberately NOT staged. Dialogue is the
            # exception the rule names, and dialogue is where a passage
            # genuinely differs from its scroll -- that case needs its own
            # treatment and does not exist yet.

        for q in d.get("patterns") or []:
            qid = str(q.get("id") or "").strip()
            insts = [str(x) for x in (q.get("instances") or []) if str(x) in by_id]
            # A pattern needs two instances to be a pattern. One passage with
            # an interesting shape is a passage -- the vocabulary says so and
            # the grouping prompt says so; this is where it is enforced.
            if not qid or len(insts) < 2:
                skipped.append(f"{book} {ch}: pattern {qid or '(no id)'} has "
                               f"{len(insts)} resolvable instances, needs 2")
                continue
            if qid not in seen:
                seen.add(qid)
                ents.append({"id": qid, "name": (q.get("name") or qid)[:80],
                             "type": "pattern",
                             "refs": sorted({r for i in insts
                                             for r in _span_refs(
                                                 book, ch, *(by_id[i]["verses"]))}),
                             "desc": (q.get("because") or "")[:400],
                             "source": source})
            for i in insts:
                rels.append({"src": i, "type": "instance_of", "dst": qid,
                             "certainty": "explicit",
                             "refs": _span_refs(book, ch, *by_id[i]["verses"]),
                             "note": (q.get("because") or "")[:200],
                             "source": source})

    return {"entities": ents, "relations": rels, "skipped": skipped}


def write(book: str, out: dict) -> Path:
    d = STAGING / f"{book.lower()}-groups"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "entities.jsonl").open("w", encoding="utf-8") as fh:
        for e in out["entities"]:
            fh.write(json.dumps(e, sort_keys=True) + "\n")
    with (d / "relations.jsonl").open("w", encoding="utf-8") as fh:
        for r in out["relations"]:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    return d


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    rest = [a for a in argv if not a.startswith("--")]
    if not rest:
        print("usage: python -m bibleont.stage_groups <Book> [--write]")
        return 2
    book = rest[0]
    out = build(book)
    ents, rels = out["entities"], out["relations"]
    import collections
    et = collections.Counter(e["type"] for e in ents)
    rt = collections.Counter(r["type"] for r in rels)
    print(f"{book}: {len(ents)} entities, {len(rels)} relations")
    for t, n in et.most_common():
        print(f"    {t:12}{n:>5}")
    for t, n in rt.most_common():
        print(f"    {t:12}{n:>5}  (relation)")
    noq = sum(1 for e in ents
              if e["type"] == "passage" and not e["attrs"]["seam_evidence_quotes"])
    print(f"  passages whose seam evidence quotes nothing: {noq}")
    if out["skipped"]:
        print(f"  SKIPPED {len(out['skipped'])}:")
        for s in out["skipped"][:12]:
            print(f"    {s}")
    if "--write" in argv:
        print(f"  wrote {write(book, out)}")
    else:
        print("  (dry run -- pass --write to stage)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
