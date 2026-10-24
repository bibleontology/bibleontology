"""The sentence-level structure of named verses, pinned so it cannot drift.

2026-09-21: work through verse examples one at a time until the node
structures within the sentence level are always constructed correctly, and
move on only when that holds; then bake each into a verse-by-verse regression
suite with a sequence that builds it reliably before going to the next verse.

This is that suite. It is deliberately about ONE VERSE AT A TIME, because the
faults it exists to catch were all found by reading a single verse and asking
why it said what it said — not by any aggregate. Every number in this project
that looked healthy hid one of them:

    97.4% of BSB spans name a lexeme the verse contains   — and 142 chapters
                                                            were showing the
                                                            wrong verse
    3 of 3 edges in Genesis 1:3 have both ends            — and the verse said
                                                            almost nothing
    44.6% of edges bound                                  — measures whether an
                                                            edge has two ends,
                                                            not whether the
                                                            meaning survived

**Bound is not correct, and an aggregate cannot tell the difference.** A named
verse with a hand-checked expectation can.

## The build sequence these expectations assume

Each step depends on the one before it, and none of them can be reached from
above. That is the whole argument for building bottom-up, and it is why two
days of tuning the pattern layer moved nothing:

    1. tools/macula → out/interlinear.jsonl.gz
           words, lemmas, glosses, morphology

    2. tools/placeholders.py
           a. occurrence nodes                     — one per word
           b. clause nodes, parts by MACULA's role — gives the VERB a home,
              and with it the mood that separates a command from a statement
           c. `content` from a speech verb to the
              sibling clause that is what was said
           d. ordered action-state pairs from a
              command + same-lemma wayyiqtol

    3. tools/versify.py     → out/versemap.json
           MACULA reference → the Berean verse carrying the same text

    4. everything above (clausepatterns, propositions, episodes, the app)

Steps 2b–2d are new, and 2b is the one the other two stand on: `content`
needs a clause to point AT, and the pairs need mood on BOTH clauses to know
which is the command.

## Notation

    clauses   "text | mood | lemma"      — mood or lemma may be "-" for none
    roles     "cl0 -s-> god"             — a clause to one of its parts
    links     "cl0 -content-> cl1"       — a clause to another clause
    pairs     "action-state | lemma | action=cl0 | state=cl2"
    edges     "thereNoOne -like-> lord"  — a plain word-level edge

Clause indices are `order` on the clause node, so they follow the text.

    python tests/test_verse_structure.py
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if not ok:
        FAILURES.append(f"{label}: {detail}" if detail else label)


def load(refs):
    """Nodes and edges for just the verses under test."""
    nodes, edges = {}, []
    want = set(refs)
    p = OUT / "placeholder-nodes.jsonl.gz"
    if not p.exists():
        print(f"SKIP - {p.name} not built; run tools/placeholders.py")
        raise SystemExit(0)
    for line in gzip.open(p, "rt", encoding="utf-8"):
        d = json.loads(line)
        if d.get("ref") in want:
            nodes[d["id"]] = d
    for line in gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt",
                          encoding="utf-8"):
        e = json.loads(line)
        if e.get("ref") in want:
            edges.append(e)
    return nodes, edges


def results():
    """-> (spec, {ref: [failures]}), so the suite can be rendered as well as run.

    2026-09-21: a visualization shows the whole suite at once, in reverse
    order of when the verses were taken on. A page that draws the
    verses has to say which of them hold, and a second copy of these checks
    would drift from this one within a day — so the check runs once, here, and
    both the runner and the page read it.
    """
    global FAILURES
    spec = json.loads((Path(__file__).parent / "verses.json")
                      .read_text(encoding="utf-8"))
    refs = [k for k in spec if not k.startswith("_")]
    per = {}
    for ref in refs:
        FAILURES = []
        _run([ref], spec)
        per[ref] = list(FAILURES)
    FAILURES = [f for v in per.values() for f in v]
    return spec, per


def main() -> int:
    spec = json.loads((Path(__file__).parent / "verses.json")
                      .read_text(encoding="utf-8"))
    refs = [k for k in spec if not k.startswith("_")]
    _run(refs, spec)

    if FAILURES:
        print(f"FAILED ({len(FAILURES)})")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    n = len(refs)
    print(f"ok - sentence structure holds for {n} verse"
          f"{'' if n == 1 else 's'}")
    return 0


def _run(refs, spec) -> None:
    nodes, edges = load(refs)

    for ref in refs:
        want = spec[ref]
        mine = {i: n for i, n in nodes.items() if n.get("ref") == ref}
        check(f"{ref} was extracted", bool(mine),
              "no nodes at all — is this reference in the corpus?")
        if not mine:
            continue

        # local name -> node, and clause order -> node
        by_local = {n.get("local"): n for n in mine.values()}
        cl = {n["order"]: n for n in mine.values() if n.get("clause")}

        # ---- clauses, in text order ----------------------------------
        exp = want.get("clauses")
        if exp is not None:
            check(f"{ref} clause count", len(cl) == len(exp),
                  f"expected {len(exp)}, built {len(cl)}")
            for i, row in enumerate(exp):
                text, mood, lemma = [x.strip() for x in row.split("|")]
                n = cl.get(i)
                if not n:
                    check(f"{ref} cl{i} exists", False, f"expected {text!r}")
                    continue
                check(f"{ref} cl{i} text", (n.get("text") or "") == text,
                      f"expected {text!r}, built {n.get('text')!r}")
                check(f"{ref} cl{i} mood",
                      (n.get("verb_mood") or "-") == mood,
                      f"expected {mood}, built {n.get('verb_mood') or '-'}")
                check(f"{ref} cl{i} lemma",
                      (n.get("verb_lemma") or "-") == lemma,
                      f"expected {lemma}, built {n.get('verb_lemma') or '-'}")

        # ---- edges, by the three kinds -------------------------------
        def have(src_local, typ, dst_local, extra=None):
            for e in edges:
                if e.get("ref") != ref or e.get("type") != typ:
                    continue
                s = (e.get("src") or "").split("#")[-1]
                d = (e.get("dst") or "").split("#")[-1]
                if s == src_local and d == dst_local:
                    if extra and not all(e.get(k) for k in extra):
                        continue
                    return True
            return False

        for kind, extra in (("roles", ["clause_role"]),
                            ("links", ["clause_link"]),
                            ("edges", None)):
            for row in want.get(kind) or []:
                src, rest = row.split(" -", 1)
                typ, dst = rest.split("-> ", 1)
                check(f"{ref} {src.strip()} -{typ.strip()}-> {dst.strip()}",
                      have(src.strip(), typ.strip(), dst.strip(), extra))

        # ---- and what must NOT be there ------------------------------
        # Every check above asks whether something exists, so a fix that
        # REMOVES a wrong edge had nothing to pin it: Exodus 8:6's "you may
        # know BECAUSE there is no one like the LORD" could come back and the
        # suite would stay green. `absent` rows use the same notation and
        # must not be built.
        for row in want.get("absent") or []:
            src, rest = row.split(" -", 1)
            typ, dst = rest.split("-> ", 1)
            check(f"{ref} {src.strip()} -{typ.strip()}-> {dst.strip()} "
                  f"is NOT built",
                  not have(src.strip(), typ.strip(), dst.strip(), None))
        for kind in want.get("absent_pairs") or []:
            got = [n["local"] for n in mine.values()
                   if n.get("pair") and n.get("kind") == kind]
            check(f"{ref} mints NO {kind} pair", not got,
                  f"but built {got}")

        # ---- the verb, as a node with its morphology ------------------
        # 2026-09-21, narrowing to one clause, "give thanks to the Lord".
        # It drew as a clause and a prepositional
        # phrase with the verb NOWHERE, because the verb lived as a string
        # attribute and a string cannot be pointed at.
        for row in want.get("verbs") or []:
            local, text, lemma, mood, stem = [x.strip()
                                              for x in row.split("|")]
            n = by_local.get(local)
            check(f"{ref} {local} exists", bool(n))
            if not n:
                continue
            for field, exp_ in (("text", text), ("lemma", lemma),
                                ("mood", mood), ("stem", stem)):
                got = n.get(field) or "-"
                check(f"{ref} {local} {field}", got == exp_,
                      f"expected {exp_!r}, built {got!r}")

        # ---- which preposition, not just that there is one -----------
        # `pp` alone cannot tell "give thanks TO the LORD" from "stood BEFORE
        # the LORD"; the preposition is the relation.
        for row in want.get("preps") or []:
            edge, gloss = [x.strip() for x in row.split("|")]
            src, rest = edge.split(" -", 1)
            typ, dst = rest.split("-> ", 1)
            # SCOPED TO THIS VERSE. `edges` holds every verse under test,
            # and a local name like `ct0` exists in all of them — matching on
            # the suffix alone found Genesis 1:3's ct0 while checking Psalm
            # 107:1 and reported its force as wayyiqtol. The test found a bug
            # in the test.
            ok = any(e.get("ref") == ref
                     and e.get("type") == typ.strip()
                     and (e.get("src") or "").endswith("#" + src.strip())
                     and (e.get("dst") or "").endswith("#" + dst.strip())
                     and e.get("prep_gloss") == gloss
                     for e in edges)
            check(f"{ref} {edge} carries the preposition {gloss!r}", ok)

        # ---- content: the lowest grouping, and the force over it ------
        # 2026-09-21: "thanks to the Lord" is the lowest-level grouping.
        # The predicate with its participants is the bottom of the
        # ladder and the mood is a force applied to it, which is what lets two
        # clauses be recognised as the same act under different force —
        # Genesis 1:3's jussive "let there be light" and wayyiqtol "there was
        # light" share a key exactly.
        for row in want.get("contents") or []:
            local, key, force = [x.strip() for x in row.split("|")]
            n = by_local.get(local)
            check(f"{ref} {local} exists", bool(n))
            if not n:
                continue
            check(f"{ref} {local} key", (n.get("key") or "") == key,
                  f"expected {key!r}, built {n.get('key')!r}")
            got = next((e.get("force") for e in edges
                        if e.get("ref") == ref and e.get("type") == "asserts"
                        and (e.get("dst") or "").endswith("#" + local)), None)
            check(f"{ref} {local} force", got == force,
                  f"expected {force!r}, built {got!r}")

        # ---- groupings, with their head's force ----------------------
        # 2026-09-21: the qualified imperative has a reason and they are
        # grouped together (imperative/basis); an imperative modified as a
        # basis is still an imperative. So the
        # group's force is checked, not only its members: a grouping that
        # loses its head's force cannot fill a slot as what it is.
        for row in want.get("groups") or []:
            bits = [x.strip() for x in row.split("|")]
            kind, force, members = bits[0], bits[1], bits[2:]
            found = None
            for n in mine.values():
                if n.get("pair") and n.get("kind") == kind:
                    found = n
                    break
            check(f"{ref} group {kind}", bool(found))
            if not found:
                continue
            got_f = found.get("force") or "-"
            check(f"{ref} group {kind} force", got_f == force,
                  f"expected {force!r}, built {got_f!r}")
            for m in members:
                pos, local = m.split("=")
                ok = any(e.get("ref") == ref
                         and (e.get("src") or "").endswith("#" + found["local"])
                         and (e.get("dst") or "").endswith("#" + local)
                         and str(e.get("order")) == pos
                         for e in edges)
                check(f"{ref} group {kind} member {pos} is {local}", ok)

        # ---- who is speaking, and WHETHER WE MAY SAY ------------------
        # 2026-09-21: build from the ground up, but do not attribute until
        # the context exists to do so. So both halves
        # are pinned: that Exodus 8:6 names Pharaoh and Moses, and that
        # Genesis 1 names nobody, because only one speaker is ever in view
        # there and the rule must decline rather than guess.
        for row in want.get("speakers") or []:
            local, who = [x.strip() for x in row.split("|")]
            n = by_local.get(local)
            got = next((e.get("dst", "") for e in edges
                        if e.get("ref") == ref and e.get("type") == "speaker"
                        and n and e.get("src") == n.get("id")), "")
            if who == "-":
                check(f"{ref} {local} has NO inferred speaker", not got,
                      f"but got {got}")
            else:
                check(f"{ref} {local} speaker", got.endswith("#" + who),
                      f"expected …#{who}, got {got or 'none'}")

        # ---- ordered pairs -------------------------------------------
        for row in want.get("pairs") or []:
            kind, lemma, act, sta = [x.strip() for x in row.split("|")]
            act, sta = act.split("=")[1], sta.split("=")[1]
            found = False
            for n in mine.values():
                if not n.get("pair") or n.get("kind") != kind:
                    continue
                if n.get("lemma") != lemma:
                    continue
                pid = n["local"]
                # ORDER IS CHECKED, NOT JUST MEMBERSHIP. Order matters
                # with this pattern, so it is more than just a pair.
                # Reversed, a fulfilment becomes an act followed by a command
                # to do it, so a test that only checked membership would pass
                # on the nonsense.
                if have(pid, "action", act, ["order"]) and \
                        have(pid, "state", sta, ["order"]):
                    a = next(e for e in edges if e.get("type") == "action"
                             and (e.get("src") or "").endswith(pid))
                    s_ = next(e for e in edges if e.get("type") == "state"
                              and (e.get("src") or "").endswith(pid))
                    if a.get("order") == 1 and s_.get("order") == 2:
                        found = True
            check(f"{ref} pair {kind} {lemma} {act}->{sta}", found,
                  "missing, or its members are not ordered 1 then 2")


if __name__ == "__main__":
    raise SystemExit(main())
