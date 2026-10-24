# PROPOSED by DeepSeek from refine second_person_subject — not enabled
# tools/fixrules/rules/second_person_subject.py
"""Fix a missing or mismatched subject on a second-person finite verb.

1Ki 1:18: after `parallel_lines_agree` runs, the second-person clause "you
know" (qatal 2ms) has no subject. A second-person Hebrew verb fixes its
subject: the subject is the addressee of the speech turn containing the
clause. This rule adds that addressee when the subject is missing, and
replaces a subject only when every existing subject is a placeholder
(an inferred/carried subject, or a word that cannot be a subject, such as
an adverb or particle).

An explicit nominal or composite subject is left alone. In particular, a
composite whose members include the addressee or a second-person pronoun
already expresses the second-person subject, and must not be overwritten.
"""

import collections

from fixrules.framework import add_edge, drop_edge

NAME = "second_person_subject"
BASIS = "original"
TEST = ("a clause with a second-person verb takes the unique addressee of "
        "its speech turn as its subject when the clause has no subject, or "
        "when all existing subjects are placeholders and none already "
        "expresses the addressee or a second-person pronoun")


def _person(value):
    """Normalize a person value enough to compare verb and noun."""
    p = str(value or "").strip().lower()
    if p in ("1", "p1") or p.startswith("1") or "first" in p:
        return "first"
    if p in ("2", "p2") or p.startswith("2") or "second" in p:
        return "second"
    if p in ("3", "p3") or p.startswith("3") or "third" in p:
        return "third"
    return ""


def _subject_person(n):
    """The syntactic person of the node currently filling subject."""
    if not n:
        return ""
    p = _person(n.get("person"))
    if p:
        return p
    # Participants that are ordinary nouns are third person unless marked.
    if n.get("pos") == "noun" and not n.get("implicit"):
        return "third"
    return ""


def _addressee_for(v, clause_id):
    """Return the unique addressee of the speech turn containing clause_id.

    The addressee edge points from the turn group to the addressee. To know
    whether a turn contains the clause we follow `part` and `line` edges
    forward from the turn (the part edge may be in an earlier verse).
    """
    verses = [v] + list(v.before(len(v.g.refs)))
    edges = []
    for pv in verses:
        edges.extend(pv.edges)

    candidates = [(e.get("src"), e.get("dst")) for e in edges
                  if e.get("type") == "addressee" and e.get("dst")]
    if not candidates:
        return None

    members = collections.defaultdict(list)
    for e in edges:
        if e.get("type") in ("part", "line") and e.get("src") and e.get("dst"):
            members[e["src"]].append(e["dst"])

    def contains(turn):
        seen = set()
        stack = [turn]
        while stack:
            nid = stack.pop()
            if nid == clause_id:
                return True
            if nid in seen:
                continue
            seen.add(nid)
            stack.extend(members.get(nid, []))
        return False

    hits = sorted({dst for turn, dst in candidates if contains(turn)})
    if len(hits) == 1:
        return hits[0]
    return None


def _parts(v, nid):
    """Member nodes of a composite."""
    out = []
    for e in v.edges:
        if e.get("type") == "member":
            if e.get("src") == nid and e.get("dst"):
                out.append(e.get("dst"))
            elif e.get("dst") == nid and e.get("src"):
                out.append(e.get("src"))
    return out


def _member_has_second_or_addressee(v, nid, addressee, seen=None):
    """Whether nid is, contains, or resolves to the addressee/second person."""
    if seen is None:
        seen = set()
    if nid in seen:
        return False
    seen.add(nid)

    n = v.node(nid) or {}
    if nid == addressee:
        return True
    if v.refers(nid) == addressee:
        return True
    if _subject_person(n) == "second":
        return True

    if n.get("composite"):
        for part in _parts(v, nid):
            if _member_has_second_or_addressee(v, part, addressee, seen):
                return True
    return False


def _can_be_subject(n):
    """Whether a node is a real explicit nominal subject."""
    if n.get("composite"):
        return True
    return bool(n.get("proper") or n.get("pos") in ("noun", "pronoun", "adjective"))


def _is_placeholder_subject(v, e, sid):
    """A subject this rule may replace: inferred/carried, or not a real subject."""
    n = v.node(sid) or {}
    if e.get("inferred") or n.get("inferred") or n.get("implicit"):
        return True
    return not _can_be_subject(n)


def detect(v):
    """Where: a second-person verb with a missing or placeholder subject."""
    for c in v.clauses():
        r = v.roles(c)
        if "v" not in r:
            continue

        vnode = v.node(r["v"][0]) or {}
        verb_person = vnode.get("person") or c.get("verb_person")
        if _person(verb_person) != "second":
            continue

        addressee = _addressee_for(v, c["id"])
        if not addressee:
            continue

        s_edges = [e for e in v.edges
                   if e.get("clause_role") and e.get("src") == v.content(c)
                   and e.get("type") == "s"]
        pairs = [(e, e["dst"]) for e in s_edges if e.get("dst")]

        # An existing subject that already expresses the addressee or a
        # second-person pronoun is correct: do not disturb the clause.
        if any(_member_has_second_or_addressee(v, sid, addressee)
               for _, sid in pairs):
            continue

        if not pairs:
            yield {
                "at": v.content(c),
                "clause": c["id"],
                "verb": r["v"][0],
                "old": [],
                "to": addressee,
                "why": (f"{c['text']} has a second-person verb and "
                        "no subject"),
            }
            continue

        # Only replace subjects that are clearly placeholders. An explicit
        # noun subject is left alone even if it is third person.
        if all(_is_placeholder_subject(v, e, sid) for e, sid in pairs):
            yield {
                "at": v.content(c),
                "clause": c["id"],
                "verb": r["v"][0],
                "old": [sid for _, sid in pairs],
                "to": addressee,
                "why": (f"{c['text']} has a second-person verb but only "
                        "placeholder subjects, not the addressee"),
            }


def fix(v, f):
    subjects = v.roles(f["at"]).get("s", [])
    for old in f["old"]:
        if old != f["to"]:
            yield drop_edge(f["at"], "s", old)
    if f["to"] not in subjects:
        yield add_edge(
            f["at"], "s", f["to"],
            "second-person verb subject is the speech turn's addressee",
        )


def validate(v, f):
    """Once fixed: the addressee is the sole subject; no dropped subject remains."""
    subjects = v.roles(f["at"]).get("s", [])
    problems = []

    if subjects != [f["to"]]:
        problems.append(f"expected exactly one subject {f['to']}, "
                        f"have {subjects}")
    for old in f["old"]:
        if old in subjects:
            problems.append(f"wrong subject {old} remains")

    vnode = v.node(f["verb"]) or {}
    verb_person = vnode.get("person") or v.node(f["clause"]).get("verb_person")
    if _person(verb_person) != "second":
        problems.append("the verb is no longer second person")

    if _addressee_for(v, f["clause"]) != f["to"]:
        problems.append(f"the new subject {f['to']} is no longer the "
                        "unique addressee")
    return problems
