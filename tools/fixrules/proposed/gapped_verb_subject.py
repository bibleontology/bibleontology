# PROPOSED by DeepSeek from Psa.103.1 — not enabled
# tools/fixrules/rules/gapped_verb_subject.py
"""A clause that borrows a verb from an earlier clause also borrows the
host's subject. Where a separate waw stands between the two clauses, make
that an 'and' link; where the host is already a member of a group, put the
gapped clause in the same group.

Built for Psa 103:1: the second line has a gapped verb from the line before
but is otherwise an orphan. The host's implicit 'you' is its subject; the
waw before the object is the clause link; the host is a part of the address,
so the second line must be too.
"""
from fixrules.framework import add_edge

NAME = "gapped_verb_subject"
BASIS = "original"
TEST = ("a clause with a borrowed verb and no subject also carries the "
        "borrowing clause's subject, the waw between them as an 'and' link, "
        "and the host's group membership")


def _positions(v, nid):
    """Word positions in v.words() filled by the node `nid`, if any."""
    n = v.node(nid) or {}
    strong, lemma = n.get("strong"), n.get("lemma")
    if not strong and not lemma:
        return []
    out = []
    for i, w in enumerate(v.words()):
        if strong and lemma:
            if w.get("s") == strong and w.get("l") == lemma:
                out.append(i)
        elif strong and w.get("s") == strong:
            out.append(i)
        elif lemma and w.get("l") == lemma:
            out.append(i)
    return out


def _clause_span(v, clause, exclude=None):
    """Smallest word span covering this clause's own role-filling words.

    The borrowed verb is excluded from the gapped clause's span so it does
    not drag the span back into the host.
    """
    positions = []
    for ids in v.roles(clause).values():
        for nid in ids:
            if nid == exclude:
                continue
            n = v.node(nid) or {}
            if n.get("clause") or n.get("content") or n.get("composite") or n.get("verb"):
                continue
            positions.extend(_positions(v, nid))
    if not positions:
        return None, None
    return min(positions), max(positions)


def detect(v):
    """Where: a clause has a verb role but no verb of its own, no subject,
    and an earlier clause in the verse that supplies that verb and has a
    subject to carry.
    """
    clauses = v.clauses()
    for i, c in enumerate(clauses):
        if c.get("verb_lemma"):
            continue
        content = v.content(c)
        v_ids = [e["dst"] for e in v.edges
                 if e.get("clause_role") and e.get("src") == content
                 and e.get("type") == "v"]
        if not v_ids or v.roles(c).get("s"):
            continue

        verb = v_ids[0]
        host = None
        for h in reversed(clauses[:i]):
            if verb in v.roles(h).get("v", []):
                host = h
                break
        if host is None:
            continue

        subjects = v.roles(host).get("s")
        if not subjects:
            continue

        subject = subjects[0]
        host_id, clause_id = host["id"], c["id"]

        groups = []
        for e in v.into(host_id, "part"):
            group = e["src"]
            already_part = any(
                e2.get("type") == "part" and e2.get("src") == group
                and e2.get("dst") == clause_id for e2 in v.edges)
            if not already_part:
                groups.append(group)

        start1, end1 = _clause_span(v, host)
        start2, _ = _clause_span(v, c, exclude=verb)
        waw_between = False
        if None not in (start1, end1, start2):
            for wi, w in enumerate(v.words()):
                if (end1 < wi < start2 and w.get("p") == "conjunction"
                        and w.get("l") in ("ו", "וְ")):
                    waw_between = True
                    break

        needs_and = waw_between and not any(
            e.get("type") == "and" and e.get("src") == host_id
            and e.get("dst") == clause_id for e in v.edges)

        yield {
            "at": content,
            "why": (f"{c.get('text')} carries a gapped verb from "
                    f"{host.get('text')} but not its subject"),
            "clause": clause_id,
            "content": content,
            "host": host_id,
            "subject": subject,
            "needs_and": needs_and,
            "groups": groups,
        }


def fix(v, f):
    yield add_edge(f["content"], "s", f["subject"],
                   "the same subject as the clause it borrows its verb from")
    if f["needs_and"]:
        yield add_edge(f["host"], "and", f["clause"],
                       "the waw between the two clauses")
    for group in f["groups"]:
        yield add_edge(group, "part", f["clause"],
                       "the same group as the clause it borrows its verb from")


def validate(v, f):
    """Once fixed: the gapped clause has exactly the host's subject; if a
    waw was added, the host has an 'and' link to it; and it is a part of
    each group the host was already in.
    """
    problems = []
    roles = v.roles(f["content"])
    if roles.get("s") != [f["subject"]]:
        problems.append(f"expected one subject {f['subject']}, "
                        f"have {roles.get('s')}")

    if f.get("needs_and"):
        has_and = any(e.get("type") == "and" and e.get("src") == f["host"]
                      and e.get("dst") == f["clause"] for e in v.edges)
        if not has_and:
            problems.append("missing 'and' link from the host to the clause")

    for group in f.get("groups", []):
        in_group = any(e.get("type") == "part" and e.get("src") == group
                       and e.get("dst") == f["clause"] for e in v.edges)
        if not in_group:
            problems.append(f"clause is not part of group {group}")

    return problems
