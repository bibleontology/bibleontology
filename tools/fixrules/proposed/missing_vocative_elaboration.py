# PROPOSED by DeepSeek from Psa.103.1 — not enabled
# tools/fixrules/rules/missing_vocative_elaboration.py
"""A second vocative coordinated by waw, whose words fall in no clause,
is the same addressee stated more fully.

Psa 103:1 "O my soul, and all that is within me": the graph holds 'soul'
as the addressee ('you -> soul'); 'all that is within me' is not in any
node or role. The rule adds the missing noun phrase and joins it to the
first vocative as an elaboration, with its quantity and possessor.
"""
from fixrules.framework import add_edge, add_node

NAME = "missing_vocative_elaboration"
BASIS = "original"
TEST = ("a waw after a held, addressed noun is followed by an unheld noun "
        "phrase with a suffix; the second noun is added and joined to the "
        "first as its elaboration")


def _word_node(v, w):
    """The graph node for a word-list entry, matched by Strong's and text."""
    for nid, n in v.nodes.items():
        if n.get("strong") == w.get("s") and n.get("text") == w.get("t"):
            return nid
    return None


def _held(v, nid):
    """True if a node is already used by any non-order edge in the verse."""
    return any((e.get("src") == nid or e.get("dst") == nid)
               for e in v.edges if e.get("type") != "next")


def _possessor(v, nid):
    return next((e.get("dst") for e in v.edges
                 if e.get("type") == "possessor" and e.get("src") == nid),
                None)


def _addressed(v, nid):
    """True if a second-person/implicit pronoun resolves to this noun."""
    for e in v.edges:
        if e.get("type") == "refers_to" and e.get("dst") == nid:
            src = v.node(e.get("src")) or {}
            if src.get("implicit") or src.get("person") == "second":
                return True
    return False


def detect(v):
    """Where: waw after an addressed noun, followed by an unheld noun
    phrase whose head is a noun with a suffix."""
    words = v.words()
    for i, w in enumerate(words):
        if w.get("p") != "conjunction":
            continue

        # The first vocative is the nearest addressed, held noun before the waw.
        first_nid = None
        for j in range(i - 1, -1, -1):
            if words[j].get("p") == "noun":
                nid = _word_node(v, words[j])
                if nid and _held(v, nid) and _addressed(v, nid):
                    first_nid = nid
                    break
        if not first_nid:
            continue

        # After the waw: optional pre-head quantity noun, then the head noun
        # and its suffix.
        j = i + 1
        qty_nid = None
        if j + 2 < len(words):
            a, b, c = words[j], words[j + 1], words[j + 2]
            if (a.get("p") == "noun" and b.get("p") == "noun"
                    and c.get("p") == "suffix"):
                qty_nid = _word_node(v, a)
                if qty_nid is None:
                    continue
                head_idx = j + 1
        if qty_nid is None:
            if (j + 1 < len(words) and words[j].get("p") == "noun"
                    and words[j + 1].get("p") == "suffix"):
                head_idx = j
            else:
                continue

        head_nid = _word_node(v, words[head_idx])
        if not head_nid or _held(v, head_nid):
            continue
        if qty_nid and _held(v, qty_nid):
            continue

        head = v.node(head_nid) or {}
        local = f"{head_nid.split('#')[-1]}_voc"
        phrase = " ".join(wd.get("t", "")
                          for wd in words[j:head_idx + 1]).strip()
        yield {
            "at": head_nid,
            "local": local,
            "first_nid": first_nid,
            "head_nid": head_nid,
            "qty_nid": qty_nid,
            "possessor": _possessor(v, first_nid),
            "phrase": phrase or head.get("text") or "inward parts",
            "why": f"{phrase or 'the second vocative'} is the addressee "
                   f"restated, but its words fall in no clause",
        }


def fix(v, f):
    head = v.node(f["head_nid"]) or {}
    new = f"{v.ref}#{f['local']}"

    yield add_node(
        f["local"],
        f["why"],
        text=f.get("phrase") or head.get("text") or "inward parts",
        lemma=head.get("lemma"),
        strong=head.get("strong"),
        pos=head.get("pos") or "noun",
        proper=bool(head.get("proper")),
        **{"class": head.get("class") or "common"},   # (Claude: reserved word)
    )

    if f.get("qty_nid"):
        yield add_edge(new, "qualifier", f["qty_nid"],
                       "quantity of the second vocative", rel="quantity")

    if f.get("possessor"):
        yield add_edge(new, "possessor", f["possessor"],
                       "possessive suffix on the second vocative")

    yield add_edge(new, "elaborates", f["first_nid"],
                   "second vocative restates the first")


def validate(v, f):
    """Once fixed: the new noun exists, is a noun, elaborates the first
    vocative, and carries its quantity and possessor when detected."""
    new = f"{v.ref}#{f['local']}"
    node = v.node(new)
    problems = []

    if not node:
        return ["the new vocative node was not created"]
    if node.get("pos") != "noun":
        problems.append("the new node is not marked as a noun")

    elab = [e["dst"] for e in v.out(new, "elaborates")]
    if elab != [f["first_nid"]]:
        problems.append(f"expected elaboration to {f['first_nid']}, got {elab}")

    if f.get("qty_nid"):
        qty = [e["dst"] for e in v.out(new, "qualifier")]
        if qty != [f["qty_nid"]]:
            problems.append(f"expected quantity {f['qty_nid']}, got {qty}")

    if f.get("possessor"):
        poss = [e["dst"] for e in v.out(new, "possessor")]
        if poss != [f["possessor"]]:
            problems.append(f"expected possessor {f['possessor']}, got {poss}")

    if not _addressed(v, f["first_nid"]):
        problems.append("the first vocative is no longer addressed")

    return problems
