# PROPOSED by DeepSeek from detector non_finite_nonclausal_assertion — not enabled
# tools/fixrules/rules/non_finite_nonclausal_assertion.py
"""Detector for non-finite / non-clausal spans minted as assertions."""

NAME = "non_finite_nonclausal_assertion"
BASIS = "original"
TEST = ("a span with no finite verb is a fragment/continuation, not a new "
        "assertion: flag no-verb asserted clauses unless a verbless S-P, "
        "'and' targets that repeat the preceding verb's argument, infinitive "
        "construct clauses with no finite verb in the verse, participle "
        "clauses with no finite verb in the verse, and PP2CL after 'and' "
        "from a finite clause")

FINITE_MOODS = {
    "qatal",
    "yiqtol",
    "wayyiqtol",
    "weqatal",
    "imperative",
    "cohortative",
    "jussive",
}

ARG_ROLES = {"s", "o", "o2", "io", "pp", "prep_object"}


def _norm(m):
    return (m or "").strip().lower().replace("_", " ")


def _mood(v, c):
    """The clause's verb mood, from the clause or its verb node."""
    m = _norm(c.get("verb_mood"))
    if m:
        return m
    for vid in v.roles(c).get("v", []):
        n = v.node(vid) or {}
        if n.get("mood"):
            return _norm(n["mood"])
    return ""


def _finite(v, c):
    return _mood(v, c) in FINITE_MOODS


def _asserted(v, c):
    """True if an asserts edge ties this clause to its content."""
    cid = v.content(c)
    return any(
        e.get("type") == "asserts" and
        {e.get("src"), e.get("dst")} == {c["id"], cid}
        for e in v.edges
    )


def _nested(v, c):
    """True if this clause is the object of a 'within' edge."""
    return any(
        e.get("type") == "within" and e.get("dst") == c["id"]
        for e in v.edges
    )


def _arg_keys(v, c):
    """The argument slots this clause fills, with PP preposition marker."""
    cid = v.content(c)
    keys = set()
    for e in v.edges:
        if (e.get("clause_role") and e.get("src") == cid and
                e.get("type") in ARG_ROLES):
            marker = None
            if e.get("type") == "pp":
                marker = e.get("prep") or e.get("prep_gloss")
            keys.add((e.get("type"), marker))
    return keys


def detect(v):
    cls = v.clauses()
    any_finite = any(_finite(v, c) for c in cls)

    seen = set()
    findings = []

    def add(at, why):
        if at not in seen:
            seen.add(at)
            findings.append({"at": at, "why": why})

    # 1. PP2CL after 'and' from a finite clause: demote to a gapped PP.
    for e in v.edges:
        if not (e.get("clause_link") and e.get("type") == "and"):
            continue
        src = v.node(e.get("src"))
        tgt = v.node(e.get("dst"))
        if not (src and tgt and src.get("clause") and tgt.get("clause")):
            continue
        if not _finite(v, src):
            continue
        if "PP2CL" not in (tgt.get("rule") or "").upper():
            continue
        if _finite(v, tgt):
            continue
        add(tgt["id"],
            "PP2CL after 'and' from a finite clause is the preceding verb's "
            "gapped PP, not an independent clause")

    # 2. 'and' target that is verbless and only nominal/PP material,
    # matching an argument of the preceding finite clause.
    for e in v.edges:
        if not (e.get("clause_link") and e.get("type") == "and"):
            continue
        src = v.node(e.get("src"))
        tgt = v.node(e.get("dst"))
        if not (src and tgt and src.get("clause") and tgt.get("clause")):
            continue
        if not _finite(v, src):
            continue

        rt = v.roles(tgt)
        if "v" in rt or "p" in rt:
            continue
        material = set(rt) - {"neg", "qualifier"}
        if not material or not material <= ARG_ROLES:
            continue
        if _arg_keys(v, src) & _arg_keys(v, tgt):
            add(tgt["id"],
                f"'and' target has only {sorted(material)} material matching "
                f"an argument of the finite clause before it")

    if not any_finite:
        # 3. Infinitive construct with no finite verb in the verse.
        for c in cls:
            if _mood(v, c) == "infinitive construct" and not _nested(v, c):
                add(c["id"],
                    "infinitive construct with no finite verb in the verse "
                    "is subordinate, not an independent assertion")

        # 4. Participle with no finite verb in the verse: should be a
        # verbless S-P, not a verbal clause with v.
        for c in cls:
            if _mood(v, c) == "participle" and not _nested(v, c):
                if "v" in v.roles(c):
                    add(c["id"],
                        "participle with no finite verb in the verse should "
                        "be a verbless S-P, not a verbal v+o clause")

    # 5. No-verb asserted clause that is not a legitimate verbless S-P.
    for c in cls:
        r = v.roles(c)
        if "v" in r:
            continue
        if not _asserted(v, c):
            continue
        if r.get("p"):
            continue
        add(c["id"],
            "clause has asserts and no verb, but has no S-P predicate")

    yield from findings


def fix(v, f):
    yield from ()


def validate(v, f):
    return []
