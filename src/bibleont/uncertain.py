"""Everything the graph is not sure about, in one place, for a later sweep.

2026-09-01, on the supervisor refusing to assert that Jesus is God from
Titus 2:13: even with Jesus and God the graph has to be true to the text, and
the preponderance of evidence over the Bible has to demonstrate the case. The
better approach for now is a way of marking connections as uncertain, with a
later sweep of all uncertain connections. The uncertainty should be at the
sourcing level, though Rahab is a little different because it is a
disambiguation problem on the name match.

**Two uncertainties, two mechanisms, and conflating them is the mistake this
module exists to prevent.**

    SOURCING     Does this verse support this claim? Titus 2:13 -- "the great
                 God and our Saviour Jesus Christ" -- can be read as one
                 person or two, and the Greek permits both. That is a fact
                 about the evidence, and it lives in a relation's `certainty`.

    IDENTITY     Is this the same person? Two women called Rahab, and nothing
                 in the text equating them. That is a fact about the records,
                 and it lives in `identity.yaml` under `provisional`.

Both were already in the schema. Neither was being used: 10 relations of
14,173 are marked `disputed`, 6 `conjectured`, and `provisional` is empty. A
vocabulary of uncertainty nobody reaches for is the same as not having one.

## Why a sweep rather than a resolution

An uncertain claim is not a defect to be fixed at the moment it is found. The
evidence for it is usually spread across books that have not been extracted
yet -- "Jesus Christ is Lord" is asserted elsewhere, and the preponderance
of evidence that is wanted cannot be weighed until the passages carrying it are in the graph.

So the right move is to mark it, leave it, and come back when there is
something to come back with. This lists what is waiting.

## What it deliberately does not do

**It does not score anything.** The question was whether the project is ready for two
numeric scales -- confidence and conceptual similarity -- and the honest
answer is no, for different reasons each. Conceptual similarity is becoming
computable: signature scoring now works within a book. Confidence is not a
measurement at all; it is a judgement about how well evidence supports a
claim, and rendering it as a decimal invites averaging and thresholding that
mean nothing.

This project has been burned repeatedly by numbers that looked real -- a
ledger reporting $12.43 against an empty account, a corroboration check
passing because a node's name was the verse text copied out. A label that says
`disputed` cannot be quietly averaged into something that says otherwise.

    python -m bibleont.uncertain
    python -m bibleont.uncertain --sourcing     only certainty-marked relations
    python -m bibleont.uncertain --identity     only provisional merges
"""

from __future__ import annotations

import json
import sys

from .paths import ONTOLOGY, ROOT

SOFT = ("disputed", "conjectured")


def sourcing() -> list[dict]:
    """Relations whose support is marked as less than settled."""
    from .graph import Store

    s = Store.load()
    out = []
    for r in s.relations:
        if (r.certainty or "").lower() in SOFT:
            out.append({"src": r.src, "type": r.type, "dst": r.dst,
                        "certainty": r.certainty,
                        "refs": [str(x) for x in (r.refs or [])][:3],
                        "note": (r.note or "")[:160]})
    return out


def identity() -> list[dict]:
    """Merges recorded as the most reasonable reading rather than a fact."""
    from .merge import load_identity

    ident = load_identity()
    out = []
    for canonical, alts in (ident.get("provisional") or {}).items():
        out.append({"canonical": canonical, "alternates": list(alts or [])})
    return out


def escalations() -> list[dict]:
    """What the supervisor handed to a person and nobody has ruled on."""
    p = ONTOLOGY / "proposals" / ".supervisor" / "ledger.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for r in d.get("runs", []):
        for e in (r.get("escalations") or []):
            if e.strip():
                out.append({"when": r.get("when", "")[:10],
                            "book": r.get("book", ""), "question": e})
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    only = ("--sourcing" in argv, "--identity" in argv)
    show_all = not any(only)

    if show_all or only[0]:
        rows = sourcing()
        print(f"  SOURCING -- {len(rows)} relation(s) whose support is not settled")
        for r in rows[:25]:
            print(f"    [{r['certainty']}] {r['src']} -{r['type']}-> {r['dst']}"
                  f"   {', '.join(r['refs'])}")
            if r["note"]:
                print(f"        {r['note']}")
        if len(rows) > 25:
            print(f"    ... {len(rows) - 25} more")
        print()

    if show_all or only[1]:
        rows = identity()
        print(f"  IDENTITY -- {len(rows)} provisional merge(s)")
        for r in rows:
            print(f"    {r['canonical']} <- {', '.join(r['alternates'])}")
        if not rows:
            print("    none recorded. Two records that might be one person "
                  "belong here, not in `same`.")
        print()

    if show_all:
        rows = escalations()
        print(f"  ESCALATED -- {len(rows)} question(s) raised for a person")
        seen = set()
        for r in rows:
            key = r["question"][:60]
            if key in seen:
                continue
            seen.add(key)
            print(f"    {r['when']}  {r['book']}")
            print(f"        {r['question'][:200]}")
        print()

    print("  Nothing here is a defect to fix now. The evidence for most of it")
    print("  is in books that have not been extracted, which is the point of")
    print("  marking rather than resolving.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
