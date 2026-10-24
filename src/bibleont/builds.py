"""Which build of the worker's instructions each book was extracted under.

2026-09-02: the work is iterative; the books are worked through knowing
another pass will be needed, with a close track of the revision of the farm
for each build so the right books can be targeted.

So the question this answers is **"which books need re-running"**, and it has
to be answerable from disk rather than from anyone's memory, because the
instructions changed twice in a single evening and the corpus is now mixed:
Genesis, Job, Mark and Titus were extracted before the case library existed;
Exodus is running after it.

## Why a hash and not a version number

A version number someone must remember to bump is a number that goes stale
without saying so. `prefix.revision()` hashes the rules themselves, so it
cannot drift from what actually ran -- it IS the text. The vocabulary block is
deliberately excluded, because it grows on every merge and hashing it would
give every batch its own revision and the field would carry no information.

## What a revision does NOT tell you

That a book is on the current revision does not mean it is good, and being on
an old one does not mean it is bad. It means the instructions differed. What
makes a re-run worth paying for is a measured gap -- `tagged-not-decomposed`
on the old books against the new ones, say -- and this module deliberately
reports the revision beside those counts rather than instead of them, so the
decision stays a measurement rather than a tidiness urge.
"""

from __future__ import annotations

import collections
import json
import re
import sys

from .paths import ROOT

PROPOSALS = ROOT / "ontology" / "proposals"
TAGGING = {"speaks_of", "asserted_by", "told", "answered", "part_of"}


def batches() -> list[dict]:
    """Every proposal batch on disk, with the revision that produced it."""
    out = []
    for d in sorted(PROPOSALS.glob("*")):
        meta = d / "META.json"
        if not meta.is_dir() and meta.exists():
            try:
                m = json.loads(meta.read_text(encoding="utf-8"))
            except Exception:                                    # noqa: BLE001
                continue
            out.append({"batch": d.name, "book": m.get("book"),
                        "when": m.get("when", ""),
                        # Absent means it predates the field, which is itself
                        # the answer: those are the oldest builds.
                        "revision": m.get("rules_revision") or "(pre-versioning)",
                        "verses": len(m.get("verses") or []),
                        "path": d})
    return out


def quality(d) -> tuple[int, int]:
    """(relations, verses whose every claim is tagging) for one batch.

    The second is the measure the case library was written against, so it is
    the one that says whether a re-run under a newer revision would buy
    anything.
    """
    f = d / "relations.jsonl"
    if not f.exists():
        return 0, 0
    per: dict = collections.defaultdict(list)
    n = 0
    with f.open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            n += 1
            for ref in (r.get("refs") or []):
                if re.match(r"[1-3]?[A-Za-z]+ \d+:\d+$", str(ref)):
                    per[str(ref)].append(r)
                    break
    tagged = sum(1 for rs in per.values()
                 if rs and all(x["type"] in TAGGING for x in rs)
                 and any(x["type"] == "speaks_of" for x in rs))
    return n, tagged


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    rows = batches()
    if not rows:
        print("no batches with metadata")
        return 0

    by_book: dict = collections.defaultdict(lambda: collections.Counter())
    stats: dict = collections.defaultdict(lambda: [0, 0])
    for b in rows:
        by_book[b["book"]][b["revision"]] += 1
        if "--quick" not in argv:
            n, tagged = quality(b["path"])
            stats[b["book"]][0] += n
            stats[b["book"]][1] += tagged

    from .prefix import revision
    cur = revision()
    print(f"current rules revision: {cur}\n")
    print(f"{'book':8}{'batches':>9}{'relations':>11}{'tagging-only':>14}  revisions")
    for book in sorted(by_book, key=lambda x: str(x)):
        revs = by_book[book]
        n, tagged = stats[book]
        mark = "" if cur in revs else "  <-- re-run candidate"
        shown = ", ".join(("older build" if r.startswith("(pre") else r[:12])
                          + (f" x{c}" if c > 1 else "")
                          for r, c in revs.most_common(3))
        print(f"{str(book):8}{sum(revs.values()):>9}{n:>11}{tagged:>14}  {shown}{mark}")
    print("\nA book on an older build is not necessarily worse. Re-run where the")
    print("tagging-only count says a re-run would buy something.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
