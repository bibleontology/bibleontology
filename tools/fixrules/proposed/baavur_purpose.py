# PROPOSED by DeepSeek from 2Sa.17.14 — not enabled
# tools/fixrules/rules/baavur_purpose.py
"""Replace a `within` link that swallows a purpose infinitive.

2Sa 17:14: "the LORD had purposed to thwart ... in order to bring disaster
on Absalom". The infinitive construct after לְבַעֲבוּר / בַּעֲבוּר states the
purpose of the clause that governs it; the graph linked it only as `within`.
"""
from fixrules.framework import add_edge, drop_edge

NAME = "baavur_purpose"
BASIS = "original"
TEST = ("an infinitive construct clause introduced by בַּעֲבוּר / לְבַעֲבוּר, "
        "currently linked only by `within` from its governing clause, takes "
        "a `purpose` clause link instead")


def _is_baavur(w):
    s = str(w.get("s") or "")
    return w.get("l") == "עָבוּר" or s in ("H5668", "5668")


def _infinitive_clauses(v):
    cands = {}
    for c in v.clauses():
        if c.get("verb_mood") == "infinitive construct" and c.get("verb_lemma"):
            cands.setdefault(c["verb_lemma"], []).append(c)
    return cands


def _governing(v, target_id):
    """The single clause that currently holds `target_id` as `within`."""
    incoming = [e for e in v.into(target_id, "within")
                if e.get("clause_link") and
                (v.node(e.get("src")) or {}).get("clause")]
    if len(incoming) != 1:
        return None
    return incoming[0]["src"]


def detect(v):
    words = v.words()
    if not words:
        return
    by_verb = _infinitive_clauses(v)
    for i, w in enumerate(words):
        if not _is_baavur(w):
            continue
        # The infinitive verb usually follows the purpose marker closely.
        for j in range(i + 1, min(len(words), i + 7)):
            wv = words[j]
            if wv.get("p") != "verb" or wv.get("l") not in by_verb:
                continue
            cands = by_verb[wv["l"]]
            if len(cands) != 1:
                continue
            target = cands[0]
            target_id = target["id"]
            gov = _governing(v, target_id)
            if not gov:
                continue
            if target.get("order", 0) <= (v.node(gov) or {}).get("order", -1):
                continue
            if any(e.get("type") == "purpose" and e.get("src") == gov and
                   e.get("dst") == target_id for e in v.edges):
                continue
            gov_text = (v.node(gov) or {}).get("text", gov)
            yield {"at": target_id, "gov": gov,
                   "why": f"the infinitive construct after בַּעֲבוּר states "
                          f"the purpose of {gov_text}"}
            # One finding per marker.
            break


def fix(v, f):
    yield drop_edge(f["gov"], "within", f["at"])
    yield add_edge(f["gov"], "purpose", f["at"],
                   "the infinitive with בַּעֲבוּר states the purpose of the "
                   "clause that governs it",
                   clause_link=True)


def validate(v, f):
    gov, goal = f["gov"], f["at"]
    problems = []

    purpose_dsts = [e["dst"] for e in v.out(gov, "purpose")]
    if purpose_dsts != [goal]:
        problems.append(f"expected one purpose edge {gov}->{goal}, have "
                        f"{purpose_dsts}")

    old_within = [e for e in v.into(goal, "within") if e.get("src") == gov]
    if old_within:
        problems.append("the old `within` link is still present")

    target = v.node(goal) or {}
    if target.get("verb_mood") != "infinitive construct":
        problems.append("the target is no longer an infinitive construct")

    return problems
