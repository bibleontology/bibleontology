# PROPOSED by DeepSeek from detector reason_result_connective — not enabled
# tools/fixrules/rules/reason_result_connective.py
"""One detector for reason/result connective errors.

Detect only: it marks places where an explicit reason/result word has no
right link, or where an existing `because` link is self-looped, sourced in a
nonfinite/embedded clause, or sourced in the last clause of an `and` run with
no alt_host.  `fix` and `validate` are intentionally no-ops.
"""
import re

NAME = "reason_result_connective"
BASIS = "original"
TEST = ("a finite clause opening with kî/yaʿan must have an incoming because "
        "edge, unless it is already a recognized content/conditional/"
        "comparative link; a because edge must not self-loop or start from "
        "a nonfinite/embedded clause, or from the last clause of an and-run "
        "without alt_host; a clause opening with lākēn must have an incoming "
        "therefore")

_POINTS = re.compile(r"[\u0591-\u05C7\u05BE]")
_HEBREW = re.compile(r"[\u0590-\u05FF]")


def _norm(s):
    """Strip Hebrew points, dagesh, shin/sin dot and maqqef."""
    return _POINTS.sub("", str(s or "")).strip()


_REASON = {_norm("כִּי"), _norm("יַעַן")}
_THEREFORE = {_norm("לָכֵן")}
_SKIP = {"that", "when_if_though", "if", "though", "as"}


def _first_token(s):
    s = str(s or "").strip()
    if not s:
        return ""
    tok = s.split()[0]
    return re.split(r"[\u05BE]", tok, maxsplit=1)[0]


def _opening_lemma(v, c, clauses):
    """Best effort at the first lemma of a clause.

    Uses only the clause's own Hebrew text, if present, and the first word
    of a first clause in the verse.  This intentionally trades recall for
    precision: a later clause whose first word cannot be assigned is not
    guessed at.
    """
    text = c.get("text") or ""
    if _HEBREW.search(text):
        return _norm(_first_token(text))
    if clauses and clauses[0].get("id") == c.get("id"):
        words = v.words()
        if words:
            return _norm(words[0].get("l") or words[0].get("lemma") or "")
    return ""


def _nonfinite(v, nid):
    n = v.node(nid) or {}
    if n.get("upper_force") == "nonfinite":
        return True
    mood = str(n.get("verb_mood") or n.get("mood") or "")
    return "infinitive" in mood


def _embedded(links, nid):
    """A clause nested in another clause's role."""
    return any(e.get("type") == "within" and e.get("dst") == nid
               for e in links)


def _last_of_and_run(links, nid):
    """The node is the last member of a chain of `and` clause links."""
    incoming = any(e.get("type") == "and" and e.get("dst") == nid
                   and e.get("src") != nid for e in links)
    outgoing = any(e.get("type") == "and" and e.get("src") == nid
                   and e.get("dst") != nid for e in links)
    return incoming and not outgoing


def detect(v):
    clauses = v.clauses()
    links = v.links()

    # Existing `because` edges that point the wrong way or self-loop.
    for e in links:
        if e.get("type") != "because":
            continue
        src = e.get("src")
        dst = e.get("dst")

        if src == dst:
            yield {"at": src, "why": f"because edge self-loops on {src}"}

        if _nonfinite(v, src) or _embedded(links, src):
            yield {"at": src,
                   "why": f"because edge starts from nonfinite/embedded clause {src}"}

        if _last_of_and_run(links, src) and not e.get("alt_host"):
            yield {"at": src,
                   "why": f"because edge starts from last clause of an and-run without alt_host"}

    # Explicit reason/result openers with a missing incoming edge.
    for c in clauses:
        cid = c.get("id")
        opening = _opening_lemma(v, c, clauses)

        if opening in _REASON:
            if _nonfinite(v, cid):
                continue
            if any(v.into(cid, typ) for typ in _SKIP):
                continue
            if not v.into(cid, "because"):
                yield {"at": cid,
                       "why": f"clause opens with {opening} but has no incoming because"}

        elif opening in _THEREFORE:
            if not v.into(cid, "therefore"):
                yield {"at": cid,
                       "why": f"clause opens with {opening} but has no incoming therefore"}


def fix(v, f):
    return []


def validate(v, f):
    return []
