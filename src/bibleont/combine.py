"""Gather a book's farm batches into the one batch they always were.

A long farm run restarts. Crashes, budget ceilings, connection resets and a
deliberate `--limit` all end a run early, and each resumption writes its own
proposal directory. Genesis finished as seven of them and Job as seven.

**The gate reads a batch as a closed world, and a fragment is not one.** It
refuses a relation whose endpoints it cannot see, which is right -- a dangling
reference is how a graph acquires nodes nobody defined. But an entity minted
in the first sitting and used in the fourth looks identical to one that was
never declared at all, so all seven Genesis batches were refused, the largest
with 288 errors.

Measured: 2,339 distinct ids are referenced by Genesis relations. Gated
separately, hundreds dangle. Gated together, **five** do -- and those five are
the real defect the gate exists to catch.

So this is not a workaround for a strict gate. The gate was asking the right
question of the wrong unit.

    python -m bibleont.combine Gen
    python -m bibleont.combine Gen --into=gen-full

Writes a new proposal directory and touches none of the originals, so a
combined batch that fails the gate can be thrown away and the parts still
stand exactly as the farm left them.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .paths import ROOT

PROPOSALS = ROOT / "ontology" / "proposals"


def batches(book: str) -> list[Path]:
    """Every farm batch for a book, oldest first.

    Ordered by name, which is the run timestamp, because entity ids are
    minted in creation order and the first sitting to name a thing should be
    the one whose record survives a collision.
    """
    return sorted(PROPOSALS.glob(f"{book.lower()}-farm-*"))


def _rows(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for line in p.open(encoding="utf-8"):
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _rel_key(r: dict) -> tuple:
    """What makes two relation records the same claim.

    Citations are part of it: the same edge asserted from two different verses
    is two pieces of evidence, and collapsing them would quietly discard the
    second. Same edge from the same verse, twice, is the duplication the
    extractor actually produces -- Gen 3:13 arrived five times.
    """
    return (r.get("src"), r.get("type"), r.get("dst"),
            tuple(sorted(str(c) for c in (r.get("citations") or []))))


def combine(book: str, into: str | None = None) -> dict:
    parts = batches(book)
    if not parts:
        raise SystemExit(f"no farm batches for {book}")

    ents: dict = {}
    dup_ents = 0
    for d in parts:
        for e in _rows(d / "entities.jsonl"):
            eid = e.get("id")
            if not eid:
                continue
            if eid in ents:
                dup_ents += 1
                continue
            ents[eid] = e

    rels: dict = {}
    dup_rels = 0
    for d in parts:
        for r in _rows(d / "relations.jsonl"):
            k = _rel_key(r)
            if k in rels:
                dup_rels += 1
                continue
            rels[k] = r

    name = into or f"{book.lower()}-full-{time.strftime('%Y%m%d-%H%M%S')}"
    out = PROPOSALS / name
    out.mkdir(parents=True, exist_ok=True)
    with (out / "entities.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for e in ents.values():
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with (out / "relations.jsonl").open("w", encoding="utf-8", newline="\n") as f:
        for r in rels.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out / "META.json").write_text(json.dumps({
        "produced_by": "bibleont.combine",
        "book": book,
        "from": [d.name for d in parts],
        "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "brief": f"{len(parts)} farm batches for {book}, gathered so the gate "
                 f"sees the closed world the run actually produced",
    }, indent=1), encoding="utf-8")

    return {"name": name, "parts": len(parts), "entities": len(ents),
            "relations": len(rels), "dup_entities": dup_ents,
            "dup_relations": dup_rels}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m bibleont.combine <Book> [--into=NAME]")
        print("       gathers every <book>-farm-* batch into one proposal")
        return 2
    book = argv[0]
    into = None
    for a in argv:
        if a.startswith("--into="):
            into = a.split("=", 1)[1]

    r = combine(book, into)
    print(f"  {r['parts']} batch(es) -> {r['name']}")
    print(f"  {r['entities']:,} entities  ({r['dup_entities']:,} duplicate "
          f"id(s) dropped, first sitting wins)")
    print(f"  {r['relations']:,} relations ({r['dup_relations']:,} exact "
          f"duplicate(s) dropped)")
    print()
    print(f"  next: python -m bibleont.proposals check {r['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
