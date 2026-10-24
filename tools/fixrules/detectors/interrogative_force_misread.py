# PROPOSED by DeepSeek from detector interrogative_force_misread — not enabled
# tools/fixrules/rules/interrogative_force_misread.py
"""Detector for clauses marked Assertion but carrying interrogative force."""

import unicodedata

NAME = "interrogative_force_misread"
BASIS = "original"
TEST = (
    "a clause whose first token after any leading conjunction is "
    "interrogative, or a following or-joined/asyndetic continuation of the "
    "same question with no new interrogative and unchanged subject, but whose "
    "force is still marked Assertion"
)


def _norm(s):
    return "".join(
        ch.lower()
        for ch in unicodedata.normalize("NFC", str(s or ""))
        if ch.isalnum()
    )


_INTERROGATIVE_LEMMAS = {
    "הֲ",
    "מָה",
    "מַה",
    "מִי",
    "מָתַי",
    "מַדּוּעַ",
    "לָמָּה",
    "לָמָה",
    "אֵיךְ",
    "אֵיכָה",
    "אַיֵּה",
    "אֵי",
    "אֵיפֹה",
    "כַּמָּה",
    "כַּמָּה",
    "אָן",
    "אָנָה",
    "עַד־אָן",
}
_INTERROGATIVE_NORM = {
    _norm(x) for x in _INTERROGATIVE_LEMMAS if _norm(x) != "ה"
}


def _is_interrogative_lemma(lemma):
    if not lemma:
        return False
    raw = str(lemma).strip()
    return raw in _INTERROGATIVE_LEMMAS or _norm(raw) in _INTERROGATIVE_NORM


def _is_interrogative_word(w):
    if not w:
        return False
    if str(w.get("g") or "").strip() == "?":
        return True
    return _is_interrogative_lemma(w.get("l") or w.get("lemma"))


def _word_norm(w):
    for key in ("g", "t"):
        n = _norm(w.get(key) or "")
        if n:
            return n
    return ""


def _node_or_member_interrogative(v, nid):
    n = v.node(nid)
    if not n:
        return False
    if _is_interrogative_lemma(n.get("lemma")):
        return True
    if n.get("composite") or n.get("pair"):
        for e in v.out(nid, "member"):
            if _node_or_member_interrogative(v, e.get("dst")):
                return True
    return False


def _interrogative_role(v, c):
    for role, ids in v.roles(c).items():
        for nid in ids:
            if _node_or_member_interrogative(v, nid):
                return role
    return None


def _clause_word_slices(v):
    words = v.words()
    word_norms = [_word_norm(w) for w in words]
    clauses = v.clauses()
    out = {}
    cursor = 0

    for c in clauses:
        target = _norm(c.get("text") or "")
        if not target:
            out[c["id"]] = (None, None)
            continue

        found = None
        for i in range(cursor, len(words)):
            s = ""
            for j in range(i, len(words)):
                s += word_norms[j]
                if s == target:
                    found = (i, j + 1)
                    break
                if len(s) > len(target):
                    break
            if found:
                break

        if found:
            out[c["id"]] = found
            cursor = found[1]
        else:
            out[c["id"]] = (None, None)

    return out


def _first_non_conjunction(words, sl):
    if sl is None or sl[0] is None:
        return None
    start, end = sl
    for w in words[start:end]:
        if w.get("p") == "conjunction":
            continue
        return w
    return None


def _starts_with_interrogative(v, c, slices):
    sl = slices.get(c["id"])
    if not sl or sl[0] is None:
        return None
    w = _first_non_conjunction(v.words(), sl)
    return bool(w and _is_interrogative_word(w))


def _is_assertion(c):
    return str(c.get("upper_force") or "").lower() == "assertion"


def _agreement(n):
    return {
        "person": n.get("person"),
        "gender": n.get("gender"),
        "number": n.get("number"),
    }


def _verb_agreement(c):
    return {
        "person": c.get("verb_person"),
        "gender": c.get("verb_gender"),
        "number": c.get("verb_number"),
    }


def _agreements_match(x, y):
    for k in ("person", "gender", "number"):
        xv = x.get(k)
        yv = y.get(k)
        if xv is not None and str(xv) != "" and yv is not None and str(yv) != "":
            if str(xv) != str(yv):
                return False
    return True


def _same_subject(v, a, b):
    sa = v.roles(a).get("s") or []
    sb = v.roles(b).get("s") or []

    if sa and sb:
        if set(sa) == set(sb):
            return True
        na, nb = v.node(sa[0]), v.node(sb[0])
        return (
            na is not None
            and nb is not None
            and _agreements_match(_agreement(na), _agreement(nb))
        )

    if sa:
        na = v.node(sa[0])
        return na is not None and _agreements_match(
            _agreement(na), _verb_agreement(b)
        )

    if sb:
        nb = v.node(sb[0])
        return nb is not None and _agreements_match(
            _verb_agreement(a), _agreement(nb)
        )

    va, vb = _verb_agreement(a), _verb_agreement(b)
    if not any(va.get(k) is not None for k in va) and not any(
        vb.get(k) is not None for k in vb
    ):
        return False
    return _agreements_match(va, vb)


def _linked_or(v, a, b):
    for e in v.links():
        if e.get("type") == "or" and {e.get("src"), e.get("dst")} == {a, b}:
            return True
    return False


def _adjacent(clauses, a, b):
    for i, c in enumerate(clauses):
        if c["id"] == a and i + 1 < len(clauses) and clauses[i + 1]["id"] == b:
            return True
    return False


def _has_clause_link(v, a, b):
    for e in v.links():
        if {e.get("src"), e.get("dst")} == {a, b}:
            return True
    return False


def detect(v):
    clauses = v.clauses()
    slices = _clause_word_slices(v)
    primaries = {}

    # Primary interrogative clauses misread as assertions.
    for c in clauses:
        if not _is_assertion(c):
            continue

        role = _interrogative_role(v, c)
        if role is not None:
            primaries[c["id"]] = c
            yield {
                "at": c["id"],
                "why": (
                    f"{c.get('text')} is marked Assertion but has an "
                    f"interrogative word filling role {role}"
                ),
            }
            continue

        starts = _starts_with_interrogative(v, c, slices)
        if starts:
            primaries[c["id"]] = c
            w = _first_non_conjunction(v.words(), slices.get(c["id"]))
            yield {
                "at": c["id"],
                "why": (
                    f"{c.get('text')} begins with interrogative "
                    f"{w.get('l')} but is marked Assertion"
                ),
            }

    # Continuations of the same question.
    for p_id, p in primaries.items():
        p_idx = next(
            (i for i, cc in enumerate(clauses) if cc["id"] == p_id), None
        )
        if p_idx is None:
            continue

        chain = [p_id]
        for c in clauses[p_idx + 1:]:
            cid = c["id"]

            if cid in primaries:
                break
            if not _is_assertion(c):
                break
            if not _same_subject(v, p, c):
                break

            starts = _starts_with_interrogative(v, c, slices)
            if starts is None:
                break
            if starts:
                break

            linked = False
            asyndetic = False
            for prev in chain:
                if _linked_or(v, prev, cid):
                    linked = True
                    break
                if _adjacent(clauses, prev, cid) and not _has_clause_link(v, prev, cid):
                    asyndetic = True
                    break

            if not linked and not asyndetic:
                break

            yield {
                "at": cid,
                "why": (
                    f"{c.get('text')} continues the question of "
                    f"{p.get('text')} but is marked Assertion"
                ),
            }
            chain.append(cid)


def fix(v, f):
    return iter(())


def validate(v, f):
    return []
