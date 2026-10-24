# PROPOSED by DeepSeek from detector volitive_directive_force — not enabled
# tools/fixrules/rules/volitive_directive_force.py
"""Detector for volitive clauses whose force is not directive.

Detect only: fix yields no changes, validate returns no problems.
"""
import re

NAME = "volitive_directive_force"
BASIS = "original"
TEST = ("a clause whose Hebrew form is volitive -- imperative, cohortative, "
        "second-person prohibition, or a second-person weqatal continuing an "
        "imperative -- must carry directive force; a second-person verb tagged "
        "jussive is directive")

_SUBORD = {
    "within", "when_if_though", "because", "if", "content", "purpose",
    "until_limit", "though", "conceded", "lest", "unless", "as",
}

_PERSON = {
    "first": {"first", "1st", "1"},
    "second": {"second", "2nd", "2"},
    "third": {"third", "3rd", "3"},
}

_NEG_LEMMAS = {"אַל", "אל", "לֹא", "לא", "לוא"}


def _mood(c):
    return str(c.get("verb_mood") or "").strip().lower()


def _is_person(c, target):
    p = str(c.get("verb_person") or c.get("person") or "").strip().lower()
    return p in _PERSON.get(target, set())


def _norm_lemma(s):
    # Strip Hebrew maqqef so "אַל־" and "אַל" compare equal.
    return re.sub(r"\u05BE", "", str(s or "")).strip()


def _has_neg(v, c):
    """True if this clause's content has a negative particle AL or LO."""
    for nid in (v.roles(c).get("neg") or []):
        node = v.node(nid) or {}
        if _norm_lemma(node.get("lemma")) in _NEG_LEMMAS:
            return True
    return False


def _verb_surface(v, c):
    """Best available Hebrew form for the verb of c."""
    for nid in (v.roles(c).get("v") or []):
        node = v.node(nid) or {}
        if node.get("lemma"):
            return str(node["lemma"])
    return str(c.get("verb_lemma") or "")


def _ends_cohortative_he(v, c):
    """A 1st-person yiqtol whose visible Hebrew form ends in -ah."""
    surf = _verb_surface(v, c)
    return surf.endswith("ָה") or surf.endswith("הָ") or \
        bool(re.search(r"\u05B8\u05D4$", surf))


def _simple_volitive(v, c):
    """Volitive by the clause's own verb form, apart from weqatal runs."""
    mood = _mood(c)
    if mood == "imperative" or mood == "cohortative":
        return True
    if mood == "yiqtol" and _is_person(c, "second") and _has_neg(v, c):
        return True
    if mood == "yiqtol" and _is_person(c, "first") and \
            _ends_cohortative_he(v, c):
        return True
    return False


def _simple_why(v, c):
    mood = _mood(c)
    label = c.get("upper_force") or "none"
    if mood == "imperative":
        return f"imperative is directive, but the clause is labeled {label}"
    if mood == "cohortative":
        return f"cohortative is directive, but the clause is labeled {label}"
    if mood == "yiqtol" and _is_person(c, "second") and _has_neg(v, c):
        return ("second-person yiqtol under AL/LO is a prohibition, "
                f"but the clause is labeled {label}")
    if mood == "yiqtol" and _is_person(c, "first"):
        return ("first-person yiqtol with cohortative -ah is directive, "
                f"but the clause is labeled {label}")
    return f"volitive form should be directive, but the clause is labeled {label}"


def _is_subordinate(v, c):
    """A clause is subordinate if it is nonfinite or has a subordinate link."""
    if c.get("upper_force") == "nonfinite":
        return True
    cid = c["id"]
    for e in v.edges:
        if e.get("clause_link") and e.get("type") in _SUBORD and \
                (e.get("src") == cid or e.get("dst") == cid):
            return True
    return False


def _has_clause_link(v, src, dst, typ):
    return any(e.get("type") == typ and e.get("src") == src and
               e.get("dst") == dst for e in v.edges)


def _weqatal_after_imperative(v, c, clauses, i):
    """Return (imperative_clause, separated_by_subordinate) or None."""
    if _mood(c) != "weqatal" or not _is_person(c, "second"):
        return None

    seen_subordinate = False
    start = max(0, i - 4)
    for p in reversed(clauses[start:i]):
        if _mood(p) == "imperative":
            return p, seen_subordinate
        if _is_subordinate(v, p):
            seen_subordinate = True
            continue
        return None
    return None


def detect(v):
    """Yield each volitive clause whose force or link is wrong."""
    clauses = v.clauses()

    for i, c in enumerate(clauses):
        mood = _mood(c)

        # 2nd-person jussive is not third-person volition: it is directive.
        if mood == "jussive" and _is_person(c, "second"):
            yield {
                "at": c["id"],
                "why": "second-person verb is tagged jussive; it is directive",
            }
            continue

        # A 2nd-person weqatal after an imperative continues the command.
        after = _weqatal_after_imperative(v, c, clauses, i)
        if after:
            prev, separated = after
            bad_link = _has_clause_link(v, prev["id"], c["id"], "sequence")
            if c.get("upper_force") != "command" or bad_link:
                why = "second-person weqatal continues the preceding imperative"
                if separated:
                    why += " (subordinate clause between)"
                if c.get("upper_force") != "command":
                    why += f", but the clause is labeled {c.get('upper_force') or 'none'}, not command"
                if bad_link:
                    why += ", and it is linked as sequence, not and"
                yield {"at": c["id"], "prev": prev["id"], "why": why}
            continue

        # Standalone volitive forms: imperative, cohortative, prohibition,
        # 1st-person yiqtol with cohortative -ah.
        if _simple_volitive(v, c) and c.get("upper_force") != "command":
            yield {"at": c["id"], "why": _simple_why(v, c)}


def fix(v, f):
    return iter(())


def validate(v, f):
    return []
