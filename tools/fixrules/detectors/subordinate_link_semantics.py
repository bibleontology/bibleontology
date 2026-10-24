# PROPOSED by DeepSeek from detector subordinate_link_semantics — not enabled
# tools/fixrules/rules/subordinate_link_semantics.py
"""Subordinate links: explicit subordinators must fix the attachment.

Detection only.  No fix or validation is proposed yet.
"""

NAME = "subordinate_link_semantics"
BASIS = "original"
TEST = (
    "each explicit temporal/purpose/fronted subordinator has the link that "
    "fixes its attachment to the finite clause it belongs to"
)

FINITE_MOODS = {"qatal", "yiqtol", "wayyiqtol", "weqatal",
                "imperative", "cohortative", "jussive"}
PURPOSE_MOODS = {"yiqtol", "cohortative", "jussive"}


def _norm(s):
    """Strip Hebrew points and maqqef so lemma comparisons are exact."""
    out = []
    for ch in (s or ""):
        if "\u0591" <= ch <= "\u05c7":
            continue
        if ch == "\u05be":
            continue
        out.append(ch)
    return "".join(out)


def _first_lemma(v):
    words = v.words()
    if not words:
        return ""
    return _norm((words[0] or {}).get("l") or "")


def _has_incoming(v, cid, type_):
    """Whether a clause_link of `type_` points to this clause."""
    return any(e.get("type") == type_ and e.get("dst") == cid
               for e in v.links())


def _prep_targets(v, preps):
    """Clauses attached by a prepositional role whose preposition is in
    `preps`, by normalized Hebrew lemma."""
    out = set()
    for e in v.edges:
        if e.get("clause_role") and e.get("type") == "pp":
            prep = _norm(e.get("prep") or e.get("prep_gloss") or "")
            if prep in preps and (v.node(e.get("dst")) or {}).get("clause"):
                out.add(e.get("dst"))
    return out


def _finite_verb_in_verse(v):
    return any((c.get("verb_mood") or "") in FINITE_MOODS
               for c in v.clauses())


def detect(v):
    cls = v.clauses()
    if not cls:
        return

    first = _first_lemma(v)
    until_targets = _prep_targets(v, {"עד"})
    as_targets = _prep_targets(v, {"כאשר"})
    b_targets = _prep_targets(v, {"ב"})

    # 1. verse-initial `עד` clause requires an incoming `until_limit`
    if len(cls) >= 2:
        c0 = cls[0]
        if (first == "עד" or c0["id"] in until_targets) and not _has_incoming(
                v, c0["id"], "until_limit"):
            yield {"at": c0["id"],
                   "why": "verse-initial עַד clause has no incoming "
                          "until_limit"}

    # 5. fronted `כִּי` clause requires an incoming `when_if_though`
    if len(cls) >= 2 and first == "כי":
        c0 = cls[0]
        if not _has_incoming(v, c0["id"], "when_if_though"):
            yield {"at": c0["id"],
                   "why": "fronted כִּי clause has no incoming "
                          "when_if_though"}

    # 2. `as` whose target is introduced by `כַּאֲשֶׁר`, but has no
    #    compared act, is a temporal circumstance misread as comparison
    for e in v.links():
        if e.get("type") == "as" and e.get("dst") in as_targets:
            if not e.get("as_said"):
                yield {"at": e["dst"],
                       "why": "כַּאֲשֶׁר clause linked as comparison "
                              "without a foregoing compared act"}

    # 3. weqatal after a nonfinite temporal front must continue that front
    for e in v.links():
        if e.get("type") != "sequence" or e.get("src") not in b_targets:
            continue
        sn = v.node(e.get("src")) or {}
        dn = v.node(e.get("dst")) or {}
        if sn.get("verb_mood") == "infinitive construct" and \
                dn.get("verb_mood") == "weqatal":
            yield {"at": e["dst"],
                   "why": "weqatal after a nonfinite temporal front read "
                          "as sequence, not continuing the front"}

    # 4. a nonfinite infinitive-construct clause with no finite verb in
    #    its verse must not stand as an assertion or Writing part
    if not _finite_verb_in_verse(v):
        for c in cls:
            if c.get("upper_force") == "nonfinite" and \
                    c.get("verb_mood") == "infinitive construct":
                if v.out(c["id"], "asserts") or v.into(c["id"], "part"):
                    yield {"at": c["id"],
                           "why": "nonfinite infinitive construct clause "
                                  "with no finite verb in its verse stands "
                                  "as an assertion/Writing part"}

    # 6. waw + different-person yiqtol/cohortative/jussive after an
    #    imperative is purpose, not plain `and`
    for e in v.links():
        if e.get("type") != "and":
            continue
        src, dst = e.get("src"), e.get("dst")
        sn, dn = v.node(src) or {}, v.node(dst) or {}
        if not (sn.get("clause") and dn.get("clause")):
            continue
        if sn.get("verb_mood") != "imperative":
            continue
        if dn.get("verb_mood") not in PURPOSE_MOODS:
            continue

        sp, dp = sn.get("verb_person"), dn.get("verb_person")
        if not (sp and dp) or sp == dp:
            continue
        if any(e2.get("type") == "purpose" and
               e2.get("src") == src and e2.get("dst") == dst
               for e2 in v.links()):
            continue
        yield {"at": dst,
               "why": f"waw + {dn.get('verb_mood')} in a different person "
                      f"after an imperative should be purpose, not and"}


def fix(v, f):
    yield from ()


def validate(v, f):
    return []
