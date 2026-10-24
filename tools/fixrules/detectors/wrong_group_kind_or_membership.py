# PROPOSED by DeepSeek from detector wrong_group_kind_or_membership — not enabled
# tools/fixrules/rules/wrong_group_kind_or_membership.py
"""Detector for wrongly built group kinds or memberships.

Covers three existing group kinds and one missing-group case:
- Parallel: line non-subject role lists must match; no nonfinite member.
- Conditional: condition must precede its consequence and be a real
  condition, not a question (disjunctive 'im after interrogative he).
- ActionState: action must be a directive with the same verb lemma and
  role list as the state.
- A clause with the function word 'az that has an 'im protasis must be
  inside a Conditional group, not a bare assertion.
"""
import unicodedata

NAME = "wrong_group_kind_or_membership"
BASIS = "original"
TEST = (
    "a Parallel group whose line role lists, excluding subject, differ, or "
    "which has a nonfinite line; a Conditional group whose condition does "
    "not precede its consequence or has question force; an ActionState "
    "group whose action is not a directive or whose action and state differ "
    "in verb lemma or non-subject role list; a clause with 'az preceded by "
    "an 'im protasis but no Conditional group"
)


def _plain(s):
    """Hebrew lemma without combining points."""
    return "".join(ch for ch in (s or "") if not unicodedata.combining(ch))


def _lemma_is(lemma, wanted):
    return _plain(lemma) == _plain(wanted)


def _clause_node(v, ref):
    """Return the Clause node for a member id, if there is one."""
    if isinstance(ref, dict):
        ref = ref.get("id")
    if not isinstance(ref, str):
        return None
    n = v.node(ref)
    if n and n.get("clause"):
        return n
    if "#ct" in ref:
        n = v.node(ref.replace("#ct", "#cl"))
        if n and n.get("clause"):
            return n
    return None


def _roles_for(v, ref):
    """Roles for a clause or content member; empty when unknown."""
    c = _clause_node(v, ref)
    if c:
        return v.roles(c)
    if isinstance(ref, str):
        n = v.node(ref)
        if n and n.get("content"):
            return v.roles(ref)
    return {}


def _role_key(v, ref):
    """Non-subject role list, as a comparable tuple."""
    return tuple(sorted(t for t in _roles_for(v, ref) if t != "s"))


def _order(v, ref):
    """Text order of the clause that `ref` belongs to."""
    c = _clause_node(v, ref)
    if not c:
        return None
    for i, cl in enumerate(v.clauses()):
        if cl["id"] == c["id"]:
            return i
    return None


def _members(v, gid, typ):
    """Members of a group by relation type, whichever direction the edge runs."""
    out = [e["dst"] for e in v.out(gid, typ)]
    if out:
        return out
    return [e["src"] for e in v.into(gid, typ)]


def _verb_lemma(v, ref):
    c = _clause_node(v, ref)
    if c and c.get("verb_lemma"):
        return c["verb_lemma"]
    for nid in _roles_for(v, ref).get("v", []):
        n = v.node(nid)
        if n and n.get("verb"):
            return n.get("lemma")
    return None


def _clause_has_role_lemma(v, clause, lemma):
    for ids in v.roles(clause).values():
        for nid in ids:
            n = v.node(nid)
            if n and _lemma_is(n.get("lemma"), lemma):
                return True
    return False


def _in_conditional_group(v, cid):
    """Whether clause `cid` is already the consequence of a Conditional group."""
    for n in v.nodes.values():
        if n.get("kind") != "Conditional":
            continue
        for cons in _members(v, n["id"], "consequence"):
            c = _clause_node(v, cons)
            if c and c["id"] == cid:
                return True
    return False


def _parallel(v, n):
    gid = n["id"]
    lines = _members(v, gid, "line")
    if len(lines) < 2:
        return

    keys = [(line, _role_key(v, line)) for line in lines]
    first = keys[0][1]
    if any(k != first for _, k in keys):
        detail = "; ".join(f"{line} {list(k)}" for line, k in keys)
        yield {
            "at": gid,
            "why": f"Parallel lines differ in non-subject roles: {detail}",
        }

    for line in lines:
        c = _clause_node(v, line)
        if c is None:
            yield {"at": line, "why": "Parallel member is not a clause"}
        elif c.get("upper_force") == "nonfinite":
            yield {
                "at": c["id"],
                "why": f"Parallel line {c['id']} has nonfinite force",
            }


def _conditional(v, n):
    gid = n["id"]
    conds = _members(v, gid, "condition")
    conseqs = _members(v, gid, "consequence")
    if not conds or not conseqs:
        return

    cond, cons = conds[0], conseqs[0]
    ccond, ccons = _clause_node(v, cond), _clause_node(v, cons)

    if ccond and ccons:
        o1, o2 = _order(v, cond), _order(v, cons)
        if o1 is not None and o2 is not None and o1 >= o2:
            yield {
                "at": gid,
                "why": "Conditional condition does not precede its consequence",
            }

    if ccond and ccond.get("upper_force") == "question":
        yield {
            "at": gid,
            "why": "Conditional condition has question force, so its 'im is disjunctive, not a real condition",
        }


def _action_state(v, n):
    gid = n["id"]
    acts = _members(v, gid, "action")
    states = _members(v, gid, "state")
    if not acts or not states:
        return

    act, st = acts[0], states[0]
    problems = []

    cact = _clause_node(v, act)
    if cact and cact.get("upper_force") != "command":
        problems.append("action is not a directive")

    va = _verb_lemma(v, act)
    vs = _verb_lemma(v, st)
    if va != vs:
        problems.append(f"verb lemma differs: {va} vs {vs}")

    if _role_key(v, act) != _role_key(v, st):
        problems.append("non-subject role lists differ")

    if problems:
        yield {"at": gid, "why": "ActionState " + "; ".join(problems)}


def _then_without_group(v):
    for c in v.clauses():
        if c.get("upper_force") == "nonfinite":
            continue
        if not _clause_has_role_lemma(v, c, "אָז"):
            continue

        cid = c["id"]
        if _in_conditional_group(v, cid):
            continue

        protasis = False
        for e in v.out(cid, "if"):
            o1 = _order(v, e["dst"])
            o2 = _order(v, cid)
            if o1 is not None and o2 is not None and o1 < o2:
                protasis = True
                break

        if protasis:
            yield {
                "at": cid,
                "why": "then-clause has an 'im protasis but no Conditional group",
            }


def detect(v):
    for n in v.nodes.values():
        kind = n.get("kind")
        if kind == "Parallel":
            yield from _parallel(v, n)
        elif kind == "Conditional":
            yield from _conditional(v, n)
        elif kind == "ActionState":
            yield from _action_state(v, n)

    yield from _then_without_group(v)


def fix(v, f):
    return None


def validate(v, f):
    return []
