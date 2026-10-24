"""Whether the graph leans, measured rather than asserted.

`tests/controversies_checklist.txt` lists contested doctrines and, for each,
the verses **each side actually cites** -- not a summary of the argument. This
scores it against the graph as built.

## The failure it is looking for

A corpus its readers argue about gives a graph two ways to fail. It can
**adjudicate** -- state a conclusion one side rejects -- or it can be
**lopsided**, holding one side's verses thoroughly and the other's barely, so
that a reader searching in good faith finds a stacked deck.

The second is the more likely failure and much the harder to notice, because
it looks exactly like ordinary incompleteness. Nobody decides to under-cite
one side; it happens because the verses one tradition leans on are the ones a
particular extraction pass happened to cover. **That is what this measures.**

It cannot measure the first. Adjudication lives in the wording of a note, and
no count will find it -- a person has to read the edge. So a clean report here
is not a clean bill of health, and the module says so rather than letting the
number imply it.

## What the score means

For each side, the fraction of its cited verses that some relation in the
graph also cites. Then:

```
A   both sides reachable      each side at or above the floor
B   lopsided                  one side well covered, the other far behind
C   neither                   both below the floor -- a gap, not a lean
```

**B is the finding, and its direction is the finding within the finding.** A
row scoring B tells you which tradition's reader is currently better served,
which is the thing that cannot be seen from inside a single extraction batch.

`C` is honest. A doctrine nobody has extracted for yet leans nowhere, and
filling it in is ordinary work. `B` is a defect, and the fix is not to remove
the covered side but to reach the other one.

## What a verse being "cited" does and does not mean

It means some relation in the graph names that verse. It does not mean the
graph says anything useful about it, and it certainly does not mean the graph
represents the argument the verse is used in. A reader arriving at John 14:28
finds the verse reachable; whether what they find there helps them is a
separate question this does not attempt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .corpus import get_corpus, parse_ref
from .graph import Store

CHECKLIST = Path("tests/controversies_checklist.txt")

# Below this, a side is not meaningfully reachable. Chosen so that one stray
# citation does not read as coverage of a ten-verse position.
FLOOR = 0.34
# A gap this wide between two covered sides is a lean rather than noise.
LEAN = 0.30


@dataclass
class Row:
    id: str
    question: str
    a_refs: list[str]
    b_refs: list[str]
    note: str
    a_hit: list[str] = field(default_factory=list)
    b_hit: list[str] = field(default_factory=list)

    @property
    def a_share(self) -> float:
        return len(self.a_hit) / len(self.a_refs) if self.a_refs else 0.0

    @property
    def b_share(self) -> float:
        return len(self.b_hit) / len(self.b_refs) if self.b_refs else 0.0

    @property
    def score(self) -> str:
        a, b = self.a_share, self.b_share
        if a < FLOOR and b < FLOOR:
            return "C"
        if a >= FLOOR and b >= FLOOR and abs(a - b) < LEAN:
            return "A"
        return "B"

    @property
    def lean(self) -> str:
        """Which side a reader is currently better served on."""
        if self.score != "B":
            return ""
        return "first" if self.a_share > self.b_share else "second"


def _cited(store: Store) -> set[str]:
    """Every verse any relation names, ranges expanded."""
    corpus = get_corpus()
    seen: set[str] = set()
    for rel in store.relations:
        for ref in rel.refs:
            try:
                for v in corpus.expand(parse_ref(ref)):
                    seen.add(str(v))
            except Exception:
                continue
    return seen


def _split(refs: str) -> list[str]:
    return [r.strip() for r in refs.split(",") if r.strip()]


def load(path: Path | None = None) -> list[Row]:
    text = (path or CHECKLIST).read_text(encoding="utf-8")
    rows: list[Row] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            continue
        rows.append(Row(id=parts[0], question=parts[1],
                        a_refs=_split(parts[2]), b_refs=_split(parts[3]),
                        note=parts[4] if len(parts) > 4 else ""))
    return rows


def survey(store: Store | None = None,
           path: Path | None = None) -> list[Row]:
    store = store or Store.load()
    corpus = get_corpus()
    cited = _cited(store)

    def hits(refs: list[str]) -> list[str]:
        out = []
        for ref in refs:
            try:
                verses = {str(v) for v in corpus.expand(parse_ref(ref))}
            except Exception:
                continue
            if verses & cited:
                out.append(ref)
        return out

    rows = load(path)
    for row in rows:
        row.a_hit = hits(row.a_refs)
        row.b_hit = hits(row.b_refs)
    return rows


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", choices=["A", "B", "C"],
                    help="show just one score")
    args = ap.parse_args(argv)

    rows = survey()
    tally = {"A": 0, "B": 0, "C": 0}
    print(f"{'':2}{'doctrine':24}{'first':>12}{'second':>12}  lean")
    for r in rows:
        tally[r.score] += 1
        if args.only and r.score != args.only:
            continue
        a = f"{len(r.a_hit)}/{len(r.a_refs)}"
        b = f"{len(r.b_hit)}/{len(r.b_refs)}"
        print(f"{r.score} {r.id[:22]:24}{a:>12}{b:>12}  {r.lean}")

    total = sum(tally.values()) or 1
    print(f"\n{tally['A']} both sides, {tally['B']} lopsided, "
          f"{tally['C']} neither   ({total} doctrines)")
    if tally["B"]:
        print("\nLopsided rows are the finding. The fix is to reach the "
              "thinner side, never to thin the other.")
    print("\nThis cannot see adjudication -- a note that states a conclusion "
          "one side rejects counts as coverage here. Read the edges.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
