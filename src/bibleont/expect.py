"""Things that should be true, checked at the moment they become checkable.

The obvious way to test a graph is to finish it and look. 2026-08-29: there
should be no need to wait for the end of Revelation, and the reason is that
almost every expectation depends on a handful of books rather than on all of
them. "The seed at Gal 3:16 is not the
seed at Luke 8:11" becomes answerable the moment Genesis, Luke and Galatians
are in -- and if it is wrong then, there is still time to fix the thing that
produced it. Discovered after Revelation, it is archaeology.

So every expectation names the books it waits on, and a run sorts them into
three groups:

    DUE, passing     the books are in and it holds
    DUE, failing     the books are in and it does not      <- the only problem
    NOT YET          still waiting on a book

**A failure is a fault in the process, not a record to hand-edit.** Fixing the
record makes the test pass and leaves the cause in place to do it again in the
next book. The point of finding out early is that the prompt, the schema or the
seeding can still be changed.

## What counts as "the book is in"

**The farm has finished it** -- every window of it decomposed. Not "the graph
mentions it", which was the first attempt and was wrong: the graph has cited
Genesis and Hebrews for months from hand extraction, so every expectation came
due at once and "not built yet" was reported as "broken". That is precisely the
confusion this is meant to remove.

`--now` runs everything regardless, for when you want the state of things
rather than the state of the work.
"""

from __future__ import annotations

import sys

from .paths import ROOT

SPEC = ROOT / "ontology" / "expectations.yaml"


def _books_present() -> set[str]:
    """Books the farm has finished, which is not the same as books the graph
    mentions.

    The first version counted a book as present if any relation cited it. That
    made every expectation due immediately, because the graph has cited Genesis
    and Galatians and Hebrews for months from hand extraction -- and it turned
    "this has not been built yet" into "this is broken", which is the exact
    confusion the whole idea was meant to remove.

    A failing expectation should mean something is wrong. Waiting for a book is
    not wrong.
    """
    import json
    state = ROOT / "ontology" / "proposals" / ".farm"
    done = set()
    if not state.is_dir():
        return done
    for path in state.glob("*.json"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        book = raw.get("book")
        if not book:
            continue
        try:
            from .decompose import windows
            from .farm import chapters_of
            total = sum(len(windows(book, c)) for c in chapters_of(book))
        except Exception:                                    # noqa: BLE001
            continue
        if total and len(raw.get("done") or {}) >= total:
            done.add(book)
    return done


def _base(code: str) -> str:
    import re
    return re.sub(r"[A-Za-z]$", "", code) if re.match(
        r"^[HG]\d+[A-Za-z]$", code) else code


def run_check(spec: dict, people, relations) -> tuple[bool, str]:
    kind = spec.get("check")

    if kind == "distinct":
        ids = spec["nodes"]
        missing = [i for i in ids if i not in people]
        if missing:
            return False, f"missing: {', '.join(missing)}"
        if len(set(ids)) != len(ids):
            return False, "the same id listed twice"
        # also fail if one is an alias of another, which is the way this
        # particular mistake actually gets made
        for a in ids:
            names = {n.lower() for n in people[a].names()}
            for b in ids:
                if a != b and people[b].name.lower() in names:
                    return False, f"{b!r} is an alias of {a!r}"
        return True, "separate nodes"

    if kind == "one_kind":
        node = spec["node"]
        if node not in people:
            return False, f"{node} does not exist"
        kinds = {people[r.dst].type for r in relations
                 if r.type == "signifies" and r.src == node
                 and r.dst in people}
        if len(kinds) > 1:
            return False, f"keyed to {', '.join(sorted(kinds))}"
        return True, f"keyed to {', '.join(kinds) or 'nothing'}"

    if kind == "exists":
        return (spec["node"] in people), spec["node"]

    if kind == "lemma_is":
        node = spec["node"]
        if node not in people:
            return False, f"{node} does not exist"
        got = (people[node].attrs or {}).get("lemma", "")
        codes = {_base(c) for c in got.split("+") if c}
        want = _base(spec["lemma"])
        return (want in codes), f"carries {got or 'no lemma'}"

    if kind == "min_edges":
        node = spec["node"]
        n = sum(1 for r in relations if r.src == node or r.dst == node)
        return (n >= spec["n"]), f"{n} edges, wanted {spec['n']}"

    if kind == "pattern_has":
        node = spec["node"]
        n = sum(1 for r in relations
                if r.type == "instance_of" and r.dst == node)
        return (n >= spec["n"]), f"{n} instances, wanted {spec['n']}"

    if kind == "passive":
        # Never the source of an action. Kinship, location and being spoken
        # ABOUT are all fine -- what must not appear is the node doing
        # something, which is the whole claim.
        acted = []
        for n in spec["nodes"]:
            if n not in people:
                continue
            for r in relations:
                if r.src == n and r.type not in (
                        "located_in", "member_of", "part_of", "titled",
                        "composed_of", "instance_of", "ascribed_to"):
                    acted.append(f"{n} -{r.type}-> {r.dst}")
        present = [n for n in spec["nodes"] if n in people]
        if not present:
            return False, "none of these nodes exist yet"
        if acted:
            return False, "; ".join(acted[:3])
        return True, f"{len(present)} present, none of them acts"

    return False, f"unknown check {kind!r}"


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    show_pending = "--all" in argv
    force = "--now" in argv

    try:
        import yaml
    except ImportError:
        print("needs pyyaml:  pip install pyyaml")
        return 1
    from .schema import load_entities, load_relations

    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    people = load_entities()
    relations = load_relations()
    present = _books_present()

    due_pass, due_fail, waiting = [], [], []
    for e in spec["expectations"]:
        need = set(e.get("after") or [])
        missing = [] if force else sorted(need - present)
        if missing:
            waiting.append((e, missing))
            continue
        ok, detail = run_check(e, people, relations)
        (due_pass if ok else due_fail).append((e, detail))

    for e, d in due_fail:
        print(f"FAIL  {e['name']}")
        print(f"      {d}")
        print(f"      {' '.join((e.get('why') or '').split())[:150]}")
    for e, d in due_pass:
        print(f"ok    {e['name']}  ({d})")
    if show_pending:
        for e, m in waiting:
            print(f"...   {e['name']}  waiting on {', '.join(m)}")

    print(f"\n{len(due_pass)} passing, {len(due_fail)} failing, "
          f"{len(waiting)} not yet due"
          + ("" if show_pending else "  (--all to list those)"))
    if due_fail:
        print("\nA failure is a fault in the process. Fix what produced it,")
        print("not the record -- the record will only be produced again.")
    return 1 if due_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
