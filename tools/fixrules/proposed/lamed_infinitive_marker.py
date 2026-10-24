# PROPOSED by DeepSeek from refine lamed_infinitive_marker — not enabled
# tools/fixrules/rules/lamed_infinitive_marker.py
"""WORKED EXAMPLE (original language) — 2Sa 17:14.

2Sa 17:14 'the LORD had commanded to thwart the counsel of Ahithophel':
the ל before הָפֵר is the infinitive marker, not a preposition with 'the
LORD' as its object. The clause already nests the infinitive under
`content` / `within`; the false `pp:ל` to the subject is what this rule
removes.
"""
import unicodedata

from fixrules.framework import drop_edge

NAME = "lamed_infinitive_marker"
BASIS = "original"
TEST = ("a clause whose content holds a pp:ל to its own subject, and which "
        "nests an infinitive construct clause immediately after that ל, "
        "loses the false pp — the ל is the infinitive marker")


def _bare(s):
    """Remove Hebrew vowel points and marks, leaving only base letters."""
    return "".join(ch for ch in (s or "") if not unicodedata.combining(ch))


def _is_lamed_prep(e):
    return _bare(e.get("prep") or "") == "ל"


def _nested_infinitives(v, c):
    """Infinitive-construct clauses the parent nests via content/within.

    Clause links run clause -> clause, so they leave from the clause node
    `c["id"]`, not from the content node `v.content(c)`.
    """
    out = []
    seen = set()
    for typ in ("content", "within"):
        for e in v.out(c["id"], typ):
            n = v.node(e.get("dst"))
            if (n and n.get("clause") and
                    n.get("verb_mood") == "infinitive construct" and
                    n["id"] not in seen):
                out.append(n)
                seen.add(n["id"])
    return out


def _verb_lemma(v, clause):
    for nid in (v.roles(clause).get("v") or []):
        n = v.node(nid)
        if n and n.get("lemma"):
            return n.get("lemma")
    return None


def _prep_before_infinitive(v, e, verb_lemma):
    """True if the false pp's preposition is immediately before the
    infinitive's verb word in the original word order."""
    need = _bare(e.get("prep") or "")
    vb = _bare(verb_lemma)
    words = v.words()
    for i, w in enumerate(words[:-1]):
        if (w.get("p") or "").lower() not in ("preposition", "prep"):
            continue
        if _bare(w.get("l") or "") != need:
            continue
        nxt = words[i + 1]
        if (nxt.get("p") or "").lower() != "verb":
            continue
        if _bare(nxt.get("l") or "") == vb:
            return True
    return False


def detect(v):
    """Where: a content already has X as subject, also has pp:ל to X, and
    nests an infinitive construct whose verb immediately follows that ל."""
    for c in v.clauses():
        cid = v.content(c)
        s_nodes = set(v.roles(c).get("s") or [])
        if not s_nodes:
            continue

        nested = _nested_infinitives(v, c)
        if not nested:
            continue

        for e in v.out(cid, "pp"):
            if e.get("dst") not in s_nodes:
                continue
            if not _is_lamed_prep(e):
                continue

            for inf in nested:
                vl = _verb_lemma(v, inf)
                if vl and _prep_before_infinitive(v, e, vl):
                    yield {
                        "at": cid,
                        "src": cid,
                        "dst": e["dst"],
                        "clause": c["id"],
                        "nested": inf["id"],
                        "nested_content": v.content(inf),
                        "why": (f"the ל before {vl} is the infinitive "
                                f"marker, not a prepositional phrase to "
                                f"the clause's subject"),
                    }
                    break


def fix(v, f):
    yield drop_edge(f["src"], "pp", f["dst"])


def validate(v, f):
    """Once fixed: the clause no longer has the false pp:ל to its subject,
    the subject remains, and the nested infinitive is still attached with
    its own verb."""
    problems = []

    if any(e.get("dst") == f["dst"] for e in v.out(f["src"], "pp")):
        problems.append("the false prepositional role is still present")

    if f["dst"] not in (v.roles(f["src"]).get("s") or []):
        problems.append("the true subject was removed")

    # The nested-infinitive attachment is a clause link, so check from the
    # clause node, not from the content node.
    attached = (v.out(f["clause"], "content") +
                v.out(f["clause"], "within"))
    if not any(e.get("dst") == f["nested"] for e in attached):
        problems.append("the nested infinitive is no longer attached")

    if not (v.roles(f["nested_content"]).get("v") or []):
        problems.append("the nested infinitive has no verb")

    return problems
