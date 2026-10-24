"""WORKED EXAMPLE (original language). Built and measured: 11/16, ~11/13
once clauses without an object were excluded.

Psa 103:1 "Bless the LORD, O my soul, and all within me, [bless] his holy
name": the second line has an object and no verb. An object cannot stand
without a verb, so the verb is gapped. The second line borrows the verb of
the nearest clause before it, up to three clauses back in the verse, that
has both a verb and an object. Also Psa 78:48, "he gave up their cattle to
the hail, and their livestock [he gave up] to lightning".

Why it is not a one-off: it names no word. It reads only roles (o, v) and
clause order. Where it would go wrong: when the clause before takes no
object ("Jether died"), which is why the verb it borrows must have an
object too.
"""
from fixrules.framework import add_edge

NAME = "gapped_verb"
BASIS = "original"
TEST = ("a clause with an object and no verb takes the verb of the nearest "
        "clause before it (in the verse, up to three back) that has both a "
        "verb and an object")


def detect(v):
    """Where: a clause with an object and no verb, and a host before it."""
    cls = v.clauses()
    for k, c in enumerate(cls):
        r = v.roles(c)
        if "o" not in r or "v" in r:
            continue
        for j in range(k - 1, max(-1, k - 4), -1):
            h = v.roles(cls[j])
            if "v" in h and "o" in h:
                yield {"at": v.content(c), "host": v.content(cls[j]),
                       "verb": h["v"][0],
                       "why": f"{c['text']} has an object and no verb"}
                break


def fix(v, f):
    yield add_edge(f["at"], "v", f["verb"],
                   "the verb of the line before, gapped")


def validate(v, f):
    """Once fixed: the clause has exactly one verb, the host's, and still
    its object. The host keeps its own verb."""
    r, h = v.roles(f["at"]), v.roles(f["host"])
    problems = []
    if r.get("v") != [f["verb"]]:
        problems.append(f"expected the one verb {f['verb']}, have {r.get('v')}")
    if not r.get("o"):
        problems.append("the object is gone")
    if f["verb"] not in h.get("v", []):
        problems.append("the host lost its verb")
    return problems
