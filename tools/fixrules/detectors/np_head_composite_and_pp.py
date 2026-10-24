# PROPOSED by DeepSeek from detector np_head_composite_and_pp — not enabled
# tools/fixrules/rules/np_head_composite_and_pp.py
"""Detector for misattached NP heads, coordinated lists, and PP objects.

This pass only reports; `fix` yields no changes and `validate` returns no
problems.
"""

NAME = "np_head_composite_and_pp"
BASIS = "original"
TEST = (
    "a clause argument role (s, o, o2, io, p, pp) must point to the phrase "
    "head or Composite, not to a member of a Composite, a qualifier "
    "dependent, or a preposition as a pp object"
)

_ARGUMENT_ROLES = ("s", "o", "o2", "io", "p", "pp")


def _composite_of(v, nid):
    """Composite(s) that `nid` is a member of, regardless of edge direction."""
    found = []
    for e in v.edges:
        if e.get("type") != "member":
            continue
        other = None
        if e.get("src") == nid:
            other = e.get("dst")
        elif e.get("dst") == nid:
            other = e.get("src")
        if other and (v.node(other) or {}).get("composite"):
            found.append(other)
    return found


def detect(v):
    role_counts = {}
    for c0 in v.clauses():
        for ids in v.roles(c0).values():
            for nid in ids:
                role_counts[nid] = role_counts.get(nid, 0) + 1

    for c in v.clauses():
        cid = v.content(c)
        roles = v.roles(cid)
        label = c.get("text") or cid

        for role in _ARGUMENT_ROLES:
            for target in roles.get(role, []):
                node = v.node(target) or {}

                # A pp role must point to the object, never the preposition.
                if role == "pp" and node.get("pos") == "preposition":
                    yield {
                        "at": cid,
                        "role": role,
                        "target": target,
                        "why": (
                            f"{role} of {label} points to {target}, which is "
                            "the preposition; the pp role should point to the "
                            "preposition's object"
                        ),
                    }
                    continue

                # Shared word nodes can legitimately occur in more than one
                # role; do not judge those, since the graph does not yet
                # distinguish occurrences.
                if role_counts.get(target, 0) > 1:
                    continue

                # Coordinated words must not fill a clause role directly.
                composites = _composite_of(v, target)
                unused_composites = [
                    comp for comp in composites if comp not in role_counts
                ]
                if unused_composites:
                    yield {
                        "at": cid,
                        "role": role,
                        "target": target,
                        "why": (
                            f"{role} of {label} points to {target}, a member "
                            f"of Composite {unused_composites[0]}; the role "
                            "should point to the Composite"
                        ),
                    }
                    continue

                # A construct dependent must not fill a clause role directly.
                for qual in v.out(target, "qualifier"):
                    head = qual.get("dst")
                    if head not in role_counts:
                        yield {
                            "at": cid,
                            "role": role,
                            "target": target,
                            "why": (
                                f"{role} of {label} points to {target}, a "
                                f"qualifier dependent of {head}; the role "
                                "should point to the phrase head"
                            ),
                        }
                        break


def fix(v, f):
    yield from ()


def validate(v, f):
    return []
