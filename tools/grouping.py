"""The grouping program: operations, composed methods, and loops to a fixed point.

2026-09-04: the sequence of operations is to be refined until every sentence
is completely grouped. It is like a program: each operation is a function or
sub-method, sequences of operations are grouped into methods used later within
the sequence, and in other cases there are loops until a condition is met.

That is the right model, and it makes the missing piece obvious: **a loop needs
a termination condition.** "Completely grouped" was a description; here it is a
predicate, so the loop has something to test and progress has something to be
measured against.

## The three parts

    OPERATION   one function over one clause. Places words. Idempotent, so
                running it twice changes nothing the second time.
    METHOD      a named sequence of operations, reusable inside the program
                and callable again later at a different level.
    LOOP        run a method until it stops placing words -- a fixed point,
                not a fixed number of iterations.

Every operation reports what it placed, which is what makes the loop
terminable and the sequence auditable. An operation that cannot say what it
placed cannot be part of a program that claims to finish.

## The termination condition

A verse is COMPLETE when every one of its tagged words belongs to something:
a verb, an operand, or an explicit attachment. Measured at the start:

    Hebrew verses                          23,261
    completely grouped                      1,349    5%
    words still unplaced                  111,516

5% is the honest baseline. The residue is not noise -- it sorts into closed
classes, and each class is one operation still to write:

    prepositions      23,019    absorb into the phrase they govern
    conjunctions      21,277    clause linking
    object markers     8,709    absorb into the object they mark
    adjectives         8,941    attach by agreement
    common nouns       7,439    real content, currently missed
    non-finite verbs   5,635    attach to the clause they modify
    relative asher     4,861    subordination
    pronouns           3,473    verbless clauses -- the Psalm 23:1 case

## Why operations must be idempotent

The loop re-runs a method until nothing changes. An operation that places a
word differently on the second pass never converges, and one that places a
word twice makes the count lie. Idempotence is what lets the fixed point exist
at all, and it is checked rather than assumed -- `--verify` runs every
operation twice and fails if the second run places anything.

    python tools/grouping.py             # completeness, and what is left
    python tools/grouping.py --verify    # idempotence check on every operation
    python tools/grouping.py --trace Gen.1.1    # one verse, operation by operation
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from markers import corpus, base                                  # noqa: E402
from tuples import (clauses, operands, constituent, has_prep,     # noqa: E402
                    _seg, is_finite)


class State:
    """One clause being grouped. Operations place words into it.

    `owner[i]` is the id of whatever claimed word i. A word with no owner is
    unplaced, and the count of those is what the loop drives to zero.
    """

    def __init__(self, span, vpos):
        self.span = span
        self.vpos = vpos
        self.owner = [None] * len(span)
        self.units = {}            # id -> {kind, i, members, role}
        self.log = []

    def place(self, kind, idx, members=None, role=None, by=""):
        idx = [k for k in idx if 0 <= k < len(self.span)]
        free = [k for k in idx if self.owner[k] is None]
        if not free:
            return None
        uid = f"u{len(self.units)}"
        self.units[uid] = {"kind": kind, "i": sorted(free),
                           "members": members or [], "role": role, "by": by}
        for k in free:
            self.owner[k] = uid
        self.log.append((by, kind, [self.span[k][3].strip() for k in free]))
        return uid

    def unplaced(self):
        return [k for k in range(len(self.span)) if self.owner[k] is None]

    def gloss(self, idx):
        return " ".join(self.span[k][3].strip() for k in idx)


# ----------------------------------------------------------- operations

def op_verb(st):
    """The finite verb heads the clause."""
    st.place("verb", [st.vpos], by="verb")


def op_operands(st):
    """The precedence ladder: suffix, construct chain, coordination, preposition.

    This is `tuples.operands` used as an operation rather than a pass, so the
    same code serves both the old caller and the program.
    """
    for op in operands(st.span):
        if op["kind"] in ("phrase", "group", "prep"):
            st.place(op["kind"], op["i"], op.get("members"), by="operands")


def op_particles(st):
    """Absorb a particle into the word it marks.

    The object marker, the article and the negative are not units of their own
    -- each exists to mark the thing beside it. Left loose they were 19,095
    unplaced words that no later operation would ever claim, because nothing
    else is looking for them.

    Direction matters and differs: the object marker and the article look
    FORWARD to what they mark; the negative looks forward to the verb it
    negates. A suffix would look backward, but STEPBible already fuses those
    into the host word's tag.
    """
    for k in st.unplaced():
        b = (st.span[k][5] or "").lstrip("H").split("/")[0]
        if not (b.startswith("To") or b.startswith("Td") or b.startswith("Tn")):
            continue
        nxt = next((j for j in range(k + 1, len(st.span))), None)
        if nxt is not None and st.owner[nxt] is not None:
            uid = st.owner[nxt]
            st.units[uid]["i"] = sorted(st.units[uid]["i"] + [k])
            st.owner[k] = uid
            st.log.append(("particles", "absorbed",
                           [st.span[k][3].strip()]))


def op_adjectives(st):
    """An attributive adjective joins the noun it follows.

    Hebrew marks agreement, so this is checkable rather than positional: the
    adjective and its noun share gender and number. `Aamsa` after `Ncmsa` is
    the same shape and belongs to it; a mismatch means the adjective is
    predicative and stands alone.
    """
    for k in st.unplaced():
        a = _seg(st.span[k][5], "A")
        if not a or len(a) < 4 or k == 0:
            continue
        prev = st.owner[k - 1]
        if prev is None:
            continue
        host = st.units[prev]
        if host["kind"] not in ("phrase", "group", "prep"):
            continue
        n = _seg(st.span[k - 1][5], "N")
        if not n or len(n) < 4:
            continue
        if a[2:4] != n[2:4]:          # gender and number must agree
            continue
        host["i"] = sorted(host["i"] + [k])
        st.owner[k] = prev
        st.log.append(("adjectives", "attached", [st.span[k][3].strip()]))


def op_nonfinite(st):
    """A participle or infinitive is a structure inside the clause."""
    for k in st.unplaced():
        v = _seg(st.span[k][5], "V")
        if v and len(v) > 2 and v[2] in "arcs":
            st.place("nonfinite", [k], by="nonfinite")


def op_connectors(st):
    """A conjunction that joins clauses rather than words.

    By the time this runs, every coordinating waw that joined two operands has
    already been absorbed by the ladder. What is left is the clause-level waw,
    and it is a connector rather than a member -- so it is placed as one and
    stops being counted as a gap.
    """
    for k in st.unplaced():
        b = (st.span[k][5] or "").lstrip("H").split("/")[0]
        if b.startswith("C") or b.startswith("Tc") or b.startswith("Tr"):
            st.place("connector", [k], by="connectors")


def op_leftover_nouns(st):
    """Any noun the ladder did not reach still forms a phrase.

    A safety net, and one that earns its place: 7,439 common nouns were
    unplaced, which is real content rather than function words. Where they
    come from is a defect in the ladder; until that is found they are at
    least recorded rather than silently dropped.
    """
    for k in st.unplaced():
        if _seg(st.span[k][5], "N"):
            st.place("phrase", [k for k in constituent_idx(st, k)],
                     by="leftover-nouns")


def constituent_idx(st, k):
    ws = constituent(st.span, k)
    return list(range(k, k + len(ws)))


# ------------------------------------------------------------- methods

METHOD_CLAUSE = [
    ("verb", op_verb),
    ("operands", op_operands),
    ("particles", op_particles),
    ("adjectives", op_adjectives),
    ("nonfinite", op_nonfinite),
    ("leftover-nouns", op_leftover_nouns),
    ("connectors", op_connectors),
]


def run_clause(span, vpos, method=METHOD_CLAUSE, loop=True, max_iter=6):
    """Apply a method to one clause, repeating until it stops placing words.

    The loop is a fixed point, not a fixed count: it exits when an iteration
    places nothing. `max_iter` is a guard against a non-idempotent operation,
    not the termination condition -- hitting it is a bug, and `--verify`
    exists to catch that case directly.
    """
    st = State(span, vpos)
    for _ in range(max_iter if loop else 1):
        before = len(st.unplaced())
        for _, fn in method:
            fn(st)
        if len(st.unplaced()) == before:
            break
    return st


def completeness(limit=None):
    """The termination condition, measured over the corpus."""
    rows = [r for r in corpus() if r[4].startswith("H")]
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault(r[0], []).append(r)
    refs = list(by)[:limit] if limit else list(by)

    done = total = placed = words = 0
    residue = collections.Counter()
    by_op = collections.Counter()
    for ref in refs:
        ws = by[ref]
        total += 1
        left = set(range(len(ws)))
        for begin, end, vi in clauses(ws):
            st = run_clause(ws[begin:end], vi - begin)
            for k in range(len(st.span)):
                if st.owner[k] is not None:
                    left.discard(begin + k)
            for by_name, _, glosses in st.log:
                by_op[by_name] += len(glosses)
        words += len(ws)
        placed += len(ws) - len(left)
        if not left:
            done += 1
        for k in left:
            b = (ws[k][5] or "").lstrip("H").split("/")[0]
            residue[b[:2] or "?"] += 1
    return {"verses": total, "complete": done, "words": words,
            "placed": placed, "residue": residue, "by_op": by_op}


def verify():
    """Every operation must be idempotent, or the loop cannot converge."""
    rows = [r for r in corpus() if r[4].startswith("H")]
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault(r[0], []).append(r)
    bad = []
    for ref in list(by)[:2000]:
        ws = by[ref]
        for begin, end, vi in clauses(ws):
            span, vpos = ws[begin:end], vi - begin
            st = run_clause(span, vpos)
            n = len(st.log)
            for _, fn in METHOD_CLAUSE:
                fn(st)
            if len(st.log) != n:
                bad.append((ref, st.log[n:][:2]))
    return bad


def main() -> int:
    if "--verify" in sys.argv:
        bad = verify()
        print(f"idempotence check over 2,000 verses: "
              f"{'PASS' if not bad else 'FAIL'}")
        for ref, extra in bad[:5]:
            print(f"   {ref} placed again: {extra}")
        return 1 if bad else 0

    if "--trace" in sys.argv:
        ref = sys.argv[sys.argv.index("--trace") + 1]
        rows = [r for r in corpus() if r[0] == ref]
        print(f"{ref} — {len(rows)} words, operation by operation\n")
        for begin, end, vi in clauses(rows):
            st = run_clause(rows[begin:end], vi - begin)
            print(f"  clause: {st.gloss(range(len(st.span)))[:70]}")
            for by_name, kind, glosses in st.log:
                print(f"     {by_name:16}{kind:12}{' | '.join(glosses)[:44]}")
            u = st.unplaced()
            print(f"     {'UNPLACED':16}{'':12}"
                  f"{st.gloss(u)[:44] if u else '— none, clause complete'}\n")
        return 0

    r = completeness()
    print("THE TERMINATION CONDITION — a verse is complete when every tagged")
    print("word belongs to a verb, an operand, or an explicit attachment.\n")
    print(f"  Hebrew verses            {r['verses']:>8,}")
    print(f"  completely grouped       {r['complete']:>8,}   "
          f"{100*r['complete']//r['verses']}%     was 5% before this program")
    print(f"  words placed             {r['placed']:>8,}   "
          f"{100*r['placed']//r['words']}% of {r['words']:,}")
    print(f"  words unplaced           {r['words']-r['placed']:>8,}")
    print()
    print("placed by operation:")
    for k, v in r["by_op"].most_common():
        print(f"   {k:18}{v:>9,}")
    print()
    print("what is still unplaced — each class is one operation still to write:")
    for k, v in r["residue"].most_common(12):
        print(f"   {k:6}{v:>9,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
