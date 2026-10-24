"""Proposed relations the process has not established, and whether it finds them.

## Three states, not two

A relation in this project can be in one of three conditions, and conflating
the first two is what this module exists to stop.

    EXTRACTED     the process found it, from the verses, unaided. It is in
                  the graph and it carries the graph's authority.

    CANDIDATE     somebody proposed it -- a hand reading, a note from a reader,
                  an idea from the community. Cited, plausible, possibly
                  right. NOT in the graph, because a reader who trusts the
                  graph because it cites verses cannot otherwise tell which
                  records a machine found and which a person decided.

    CORROBORATED  a candidate the process later reached on its own. Then it
                  is in the graph on the process's authority, and the
                  candidate record has become evidence that the method works.

2026-08-31: this corrects an earlier and blunter version that simply
removed hand-written batches. The aim is not to set them aside but to track
whether the process finds them as well, and to evaluate any relationships the
system does not find. Their value is in working backwards from the thought
process. Candidates are also to be crowd-sourced: pulling in an idea from the
community, assessing it rigorously, and incorporating it if it holds up.

So a candidate is not a reject. It is a claim awaiting corroboration, and the
pool is meant to grow from outside.

## The misses are the point

A candidate the process finds is mildly reassuring. **A candidate it never
finds is a measurement of what the method is blind to**, and that is the
diagnostic meant by working backwards from the thought process: a person
made this link from these verses; the extractor read the same verses and did
not. The gap between them is a description of the extractor's limits, written
in specifics rather than in worry.

Two kinds of miss, and they mean different things:

    NO EDGE       both nodes exist in the graph, and nothing connects them.
                  The process saw the participants and did not see the
                  relation. Usually the vocabulary or the prompt.

    NO NODE       the process never minted one of the endpoints at all. A
                  deeper miss: not a link it failed to draw but a thing it
                  failed to notice.

## Why they are not merged, and not deleted

They are excluded from the merge because `ontology/staging/` is what the
merge reads and this is not that. Nothing here is deleted, and any of it may
be right. But a candidate is promoted by being **re-derived**, never by being
copied back -- a record that returns by a file move has proved nothing.

    python -m bibleont.candidates            score every candidate batch
    python -m bibleont.candidates --misses   only what the process did not find
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .paths import ROOT

CANDIDATES = ROOT / "ontology" / "candidates"


def batches() -> list[Path]:
    if not CANDIDATES.is_dir():
        return []
    return sorted(d for d in CANDIDATES.iterdir()
                  if d.is_dir() and (d / "relations.jsonl").exists())


def _rows(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()]


def current_books(graph) -> set[str]:
    """Books that have been through the CURRENT extraction process.

    Without this the scorer is worse than useless. The first run reported
    0/23 corroborated, which reads as a damning verdict on the method and is
    nothing of the kind: every candidate cites Romans, Galatians, Hebrews,
    2 Corinthians, Psalms or Leviticus, and not one of those books has been
    re-extracted. The process was not asked and did not fail.

    `ontology/expectations.yaml` already solved this -- each entry names the
    books it waits on and the suite reports NOT YET separately from failing.
    A score that cannot say "not asked yet" trains its reader to discount it,
    which is how a real regression would later go unnoticed.

    **Read from the farm's own state, not from the graph.** The first attempt
    counted a book as current if any farm-sourced relation cited it, and that
    is wrong in a way that quietly inflates the answer: a Genesis relation
    citing Rom 4:3 marked Romans as extracted. It listed 2Cor, Acts, Heb,
    Isa, Jas, Matt, Num, Ps, Rom and Song as done when the only books the
    farm has finished are Genesis and Job. Cross-references are the point of
    this graph, so almost every book would eventually qualify.

    A book is current only when the farm has covered ALL of its windows.
    Partial books are reported separately -- Mark at 10 of 64 and Exodus at 9
    of 119 can neither corroborate a candidate nor fail to.
    """
    import json as _json

    from .decompose import windows as _windows
    from .farm import STATE_DIR, chapters_of

    done, partial = set(), {}
    for p in sorted(STATE_DIR.glob("*.json")):
        try:
            state = _json.loads(p.read_text(encoding="utf-8"))
            book = state.get("book") or p.stem
            n = len(state.get("done") or {})
            total = sum(len(list(_windows(book, c)))
                        for c in chapters_of(book))
        except Exception:                                    # noqa: BLE001
            continue
        if not total:
            continue
        if n >= total:
            done.add(book)
        elif n:
            partial[book] = (n, total)
    current_books.partial = partial          # for the caller to report
    return done


def _books_of(refs) -> set[str]:
    out = set()
    for x in (refs or []):
        parts = str(x).split()
        if len(parts) >= 2:
            out.add(" ".join(parts[:-1]))
    return out


def score(batch: Path, graph, current: set[str] | None = None) -> dict:
    """How much of one candidate batch the process reached on its own."""
    current = current if current is not None else current_books(graph)
    known = set(graph.people)
    exact, loose = set(), {}
    for r in graph.relations:
        exact.add((r.src, r.type, r.dst))
        loose.setdefault((r.src, r.dst), set()).add(r.type)

    found, differing, no_edge, no_node, not_yet = [], [], [], [], []
    for r in _rows(batch / "relations.jsonl"):
        src, typ, dst = r.get("src"), r.get("type"), r.get("dst")
        refs = ", ".join(str(x) for x in (r.get("refs") or [])[:2])
        waiting = _books_of(r.get("refs")) - current
        if waiting and (src, typ, dst) not in exact:
            not_yet.append((src, typ, dst, sorted(waiting), refs))
            continue
        if (src, typ, dst) in exact:
            found.append((src, typ, dst, refs))
        elif (src, dst) in loose:
            differing.append((src, typ, dst, sorted(loose[(src, dst)]), refs))
        elif src not in known or dst not in known:
            missing = [n for n in (src, dst) if n not in known]
            no_node.append((src, typ, dst, missing, refs))
        else:
            no_edge.append((src, typ, dst, refs))

    due = len(found) + len(differing) + len(no_edge) + len(no_node)
    return {"name": batch.name, "due": due, "found": found,
            "differing": differing, "no_edge": no_edge, "no_node": no_node,
            "not_yet": not_yet}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    only_misses = "--misses" in argv

    from .graph import Store

    bs = batches()
    if not bs:
        print(f"no candidate batches in {CANDIDATES.relative_to(ROOT)}")
        return 0

    graph = Store.load()
    print(f"  scoring {len(bs)} candidate batch(es) against "
          f"{len(graph.relations):,} extracted relations")
    print()

    current = current_books(graph)
    partial = getattr(current_books, "partial", {})
    print(f"  books finished by the current process: "
          f"{', '.join(sorted(current)) or 'none'}")
    if partial:
        print("  part-way: " + ", ".join(
            f"{b} {n}/{tot}" for b, (n, tot) in sorted(partial.items())))
    print()

    tot = agree = waiting = 0
    for b in bs:
        s = score(b, graph, current)
        tot += s["due"]
        agree += len(s["found"])
        waiting += len(s["not_yet"])
        print(f"  {s['name']}")
        if s["due"]:
            print(f"    {len(s['found'])}/{s['due']} corroborated  "
                  f"{len(s['differing'])} different type  "
                  f"{len(s['no_edge'])} no edge  {len(s['no_node'])} no node")
        if s["not_yet"]:
            books = sorted({b for row in s["not_yet"] for b in row[3]})
            print(f"    {len(s['not_yet'])} not yet due -- waiting on "
                  f"{', '.join(books)}")

        if not only_misses:
            for src, typ, dst, refs in s["found"]:
                print(f"      OK       {src} -{typ}-> {dst}   [{refs}]")
        for src, typ, dst, types, refs in s["differing"]:
            print(f"      TYPE     {src} -> {dst}: proposed {typ!r}, "
                  f"graph has {'/'.join(types)}   [{refs}]")
        for src, typ, dst, refs in s["no_edge"]:
            print(f"      NO EDGE  {src} -{typ}-> {dst}   [{refs}]")
        for src, typ, dst, missing, refs in s["no_node"]:
            print(f"      NO NODE  {src} -{typ}-> {dst}   "
                  f"missing: {', '.join(missing)}   [{refs}]")
        print()

    if tot:
        print(f"  {agree}/{tot} DUE candidate relation(s) corroborated "
              f"({100 * agree / tot:.0f}%)")
    else:
        print("  nothing due yet: no candidate cites a book the current "
              "process has finished.")
    if waiting:
        print(f"  {waiting} more waiting on books not yet extracted.")
    print()
    print("  A miss is a measurement of the method, not a record to paste in.")
    print("  A candidate is promoted by being re-derived, never by being moved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
