# PROPOSED by DeepSeek from refine parallel_lines_agree — not enabled
# tools/fixrules/rules/parallel_lines_agree.py
"""WORKED RULE (original language).

1Ki 1:18: a Parallel group makes cl1 a line of cl0, but cl0's subject is
Adonijah (third person) and cl1's verb is second person, and cl1 also has a
negation (לֹא) that cl0 lacks. Two clauses are Parallel only if their
subjects agree in person/number and the second line is the first's roles
minus the subject. This rule detects a bad Parallel group from `line`
edges, drops those line edges, and removes the subject the group carried
onto the second line. It never adds a new clause link: a real conjunction
is already a clause link in the graph, and where none exists this rule must
not invent one.

The rule is general: it reads only the `line` edges, clause roles, verb
person/number and `neg` role. It tests no content words.
"""
from fixrules.framework import add_edge, drop_edge

NAME = "parallel_lines_agree"
BASIS = "original"
TEST = ("a Parallel group is not parallel when its two lines' subjects do "
        "not agree in person/number, or one line has a negation the other "
        "lacks; the bad group is removed, with any subject it carried, and "
        "no new `and` is added")


def _line_edges(v, group):
    return sorted(v.out(group, "line"),
                  key=lambda e: (int(e.get("order", 0) or 0),
                                 e.get("dst", "")))


def _clause_subject(v, cid):
    """Return (person, number, gender) for a clause's subject.

    Prefer the verb's own person/number/gender, because a bad Parallel
    group may have carried a third-person noun onto a second-person line.
    """
    c = v.node(cid) or {}
    if c.get("verb_person"):
        return (c.get("verb_person"), c.get("verb_number"),
                c.get("verb_gender"))
    for sid in (v.roles(cid).get("s") or []):
        n = v.node(sid) or {}
        if n.get("person"):
            return (n.get("person"), n.get("number"), n.get("gender"))
        if n.get("proper") or n.get("pos") == "noun":
            return ("third", n.get("number") or "singular", n.get("gender"))
        if n.get("class") == "pron":
            return (n.get("person"), n.get("number"), n.get("gender"))
    return (None, None, None)


def _part_disagrees(a, b):
    return a is not None and b is not None and a != b


def _carried_subject_edges(v, content_id):
    """`s` roles the parallel group put onto a line's content."""
    return [e for e in v.out(content_id, "s")
            if e.get("inferred") == "carried from the parallel line above"]


def detect(v):
    """Where: a two-line Parallel group whose lines do not agree, or whose
    negation differs."""
    for gid, gnode in v.nodes.items():
        edges = _line_edges(v, gid)
        if not edges or len(edges) != 2:
            continue
        c0, c1 = edges[0]["dst"], edges[1]["dst"]
        n0, n1 = v.node(c0) or {}, v.node(c1) or {}
        if not (n0.get("clause") and n1.get("clause")):
            continue

        s0 = _clause_subject(v, c0)
        s1 = _clause_subject(v, c1)
        bad_subject = (_part_disagrees(s0[0], s1[0]) or
                       _part_disagrees(s0[1], s1[1]))

        r0, r1 = v.roles(c0), v.roles(c1)
        bad_negation = bool(r0.get("neg")) != bool(r1.get("neg"))

        if bad_subject or bad_negation:
            has_and = any(e.get("dst") == c1 for e in v.out(c0, "and"))
            contents = [v.content(n0), v.content(n1)]
            why = []
            if bad_subject:
                why.append(f"subjects differ: {s0} vs {s1}")
            if bad_negation:
                why.append("only one line is negated")
            yield {
                "at": gid,
                "group": gid,
                "lines": [c0, c1],
                "contents": contents,
                "had_and": has_and,
                "why": "; ".join(why),
            }


def fix(v, f):
    """Ungroup the bad Parallel and remove the carried subject.

    This pass never adds an `and` link: if the clauses were truly joined
    by a conjunction, the graph already has that clause link; if it does
    not, adding one would go beyond the text.
    """
    for e in _line_edges(v, f["group"]):
        yield drop_edge(e["src"], e["type"], e["dst"])

    # The second line's content has an `s` role the group carried onto it;
    # that is what would still make the verse say the wrong thing.
    for cid in f["contents"][1:]:
        for e in _carried_subject_edges(v, cid):
            yield drop_edge(e["src"], e["type"], e["dst"])

    # The group's own subject role belongs to the grouping, not the text.
    for e in v.out(f["group"], "s"):
        yield drop_edge(e["src"], e["type"], e["dst"])

    # (Claude, on review.) Whatever held the group — a speech turn's `part`
    # — now holds its lines, in order, or they fall out of the speech.
    for e in v.into(f["group"]):
        if e.get("clause_link"):
            yield drop_edge(e["src"], e["type"], e["dst"])
            for i, c in enumerate(f["lines"]):
                yield add_edge(e["src"], e["type"], c,
                               "a line of a dissolved parallel group",
                               order=(e.get("order") or 0) + i * 0.1)


def validate(v, f):
    """Once fixed: no line edges, no carried subject, no group-only
    subject, and no new `and` link was created by the rule."""
    group, c0, c1 = f["group"], f["lines"][0], f["lines"][1]
    second_content = f["contents"][1]
    problems = []

    if v.out(group, "line"):
        problems.append(f"parallel group {group} still has line edges")
    if not (v.node(c0) or {}).get("clause") or \
            not (v.node(c1) or {}).get("clause"):
        problems.append("a former line is no longer a clause")
    if _carried_subject_edges(v, second_content):
        problems.append("the second line still has the carried subject")
    if v.out(group, "s"):
        problems.append("the dissolved group still has its own subject")
    if any(e.get("clause_link") for e in v.into(group)):
        problems.append("something still holds the dissolved group")

    has_and = any(e.get("dst") == c1 for e in v.out(c0, "and"))
    if has_and != f.get("had_and"):
        problems.append(
            f"`and` link presence changed: was {f.get('had_and')}, "
            f"now {has_and}")

    return problems
