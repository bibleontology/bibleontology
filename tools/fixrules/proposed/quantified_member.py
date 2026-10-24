# PROPOSED by DeepSeek from refine quantified_member — not enabled
# tools/fixrules/rules/quantified_member.py
"""WORKED RULE (original language), revised after corpus review.

Fault first seen in 2Sa 17:14: the coordinated subject 'Absalom and all
the men of Israel' has as its second member the quantifier word 'all'
(כֹּל). The member should be the quantified noun 'men'; the quantifier
and a following construct complement attach to that noun as qualifiers.

The earlier version re-pointed every quantifier member edge in the verse to
the first quantified noun. Where one verse has several quantifier phrases
('every spring and every valley'), the graph gives the repeated quantifier
ONE word node, so the same node is a member more than once. The revised
detect() pairs each quantifier member slot with a DIFFERENT noun that has a
quantity qualifier edge to that quantifier, ordered by the noun's word
position, falling back to the order of the qualifier edges. If a distinct
noun cannot be assigned per member slot, detect() yields nothing rather
than guessing.
"""
import collections
import re
import unicodedata

from fixrules.framework import add_edge, drop_edge, set_attr

NAME = "quantified_member"
BASIS = "original"
TEST = ("a coordination member that is the quantifier כֹּל takes the noun "
        "its quantity qualifier points from; with several quantifier "
        "members in one composite, each is paired with a different "
        "quantified noun, in word order — never two to the same node")


def _plain(s):
    """Strip Hebrew vowel/cantillation marks so כֹּל and כל compare equal."""
    return "".join(ch for ch in str(s or "") if not unicodedata.combining(ch))


def _ns(s):
    """Normalize a Strong's value to digits, e.g. H0376 -> 376."""
    return re.sub(r"\D", "", str(s or "")).lstrip("0")


def _is_qword(w):
    return _plain(w.get("l")) == "כל" and _ns(w.get("s")) == "3605"


def _is_qnode(n):
    return (not n.get("clause") and not n.get("composite")
            and _plain(n.get("lemma")) == "כל"
            and _ns(n.get("strong")) == "3605")


def _noun(n):
    return bool(n) and n.get("pos") == "noun" \
        and not n.get("clause") and not n.get("composite")


def _node_for_word(v, w):
    """The node for a v.words() entry, preferring an unambiguous match."""
    cands = [n for n in v.nodes.values()
             if not n.get("clause") and not n.get("composite")
             and n.get("pos") == w.get("p")
             and _plain(n.get("lemma")) == _plain(w.get("l"))
             and _ns(n.get("strong")) == _ns(w.get("s"))]
    if len(cands) == 1:
        return cands[0]

    cands = [n for n in v.nodes.values()
             if not n.get("clause") and not n.get("composite")
             and n.get("pos") == w.get("p")
             and (n.get("text") or "").strip() == (w.get("t") or "").strip()]
    return cands[0] if len(cands) == 1 else None


def _has_qual(v, head, dst, rel):
    return any(e.get("dst") == dst and e.get("rel") == rel
               for e in v.out(head, "qualifier"))


def _quantifier_nodes(v):
    return [n for n in v.nodes.values() if _is_qnode(n)]


def _quantifier_word_positions(v, qnodes):
    """Word positions of each quantifier node: node id -> [word indices]."""
    pos = collections.defaultdict(list)
    for i, w in enumerate(v.words()):
        if not _is_qword(w):
            continue
        for n in qnodes:
            if _plain(n.get("lemma")) == _plain(w.get("l")) \
                    and _ns(n.get("strong")) == _ns(w.get("s")):
                pos[n["id"]].append(i)
    return pos


def _word_positions(v):
    """First word position for each node, where it can be determined."""
    pos = collections.defaultdict(list)
    for i, w in enumerate(v.words()):
        n = _node_for_word(v, w)
        if n:
            pos[n["id"]].append(i)
    return pos


def _first_position(pos, nid):
    return pos.get(nid, [None])[0]


def _quantity_heads(v, qid):
    """Nouns with a quantity qualifier edge pointing to quantifier `qid`.

    These are returned in the order the qualifier edges occur in v.edges;
    the caller sorts them by word position.
    """
    heads, seen = [], set()
    for e in v.edges:
        if e.get("type") == "qualifier" and e.get("rel") == "quantity" \
                and e.get("dst") == qid:
            src = e.get("src")
            if src not in seen and _noun(v.node(src)):
                seen.add(src)
                heads.append(src)
    return heads


def _find_tail(v, head, pos):
    """The construct complement for a quantified head, and whether to add it.

    Prefer an existing `of` qualifier from the head; otherwise take the
    immediately following noun word. If ambiguous, return (None, False).
    """
    existing = [e for e in v.out(head, "qualifier")
                if e.get("rel") == "of" and _noun(v.node(e.get("dst")))]
    if len(existing) == 1:
        return existing[0].get("dst"), False
    if existing:
        return None, False

    if pos is None:
        return None, False
    words = v.words()
    if pos + 1 >= len(words):
        return None, False
    w = words[pos + 1]
    if w.get("p") != "noun":
        return None, False
    t = _node_for_word(v, w)
    if t and t["id"] != head and _noun(t):
        return t["id"], True
    return None, False


def _member_edges(v, cid):
    return sorted(v.out(cid, "member"),
                  key=lambda e: (e.get("order") is None, e.get("order", 0)))


def _composite_text(v, cid, members, replacements):
    """Member texts joined by ' and ', in member order, after replacements."""
    final_ids = []
    for i, e in enumerate(members):
        nid = replacements.get(i, e.get("dst"))
        if not (v.node(nid) or {}).get("text"):
            return None
        final_ids.append(nid)
    return " and ".join((v.node(nid) or {}).get("text").strip()
                        for nid in final_ids)


def detect(v):
    """Where: a composite has a quantifier member, and each quantifier
    member slot can be paired with a different quantified noun."""
    qnodes = _quantifier_nodes(v)
    if not qnodes:
        return

    qids = {n["id"] for n in qnodes}
    composites = [n for n in v.nodes.values() if n.get("composite")]
    if not composites:
        return

    qword_pos = _quantifier_word_positions(v, qnodes)
    node_pos = _word_positions(v)

    members_by_cid, q_slot_counts = {}, collections.Counter()
    for cnode in composites:
        ms = _member_edges(v, cnode["id"])
        members_by_cid[cnode["id"]] = ms
        for e in ms:
            if e.get("dst") in qids:
                q_slot_counts[e.get("dst")] += 1

    for cnode in composites:
        cid = cnode["id"]
        members = members_by_cid[cid]

        slots_by_q = collections.defaultdict(list)
        for i, e in enumerate(members):
            if e.get("dst") in qids:
                slots_by_q[e.get("dst")].append({
                    "order": e.get("order"),
                    "index": i,
                })

        if not slots_by_q:
            continue

        pairs, drop_qs, ok = [], [], True
        for qid, slots in slots_by_q.items():
            heads = _quantity_heads(v, qid)

            # Fallback for the old single-phrase success when the graph has
            # no quantity qualifier to use: one quantifier word and one
            # quantifier-member slot in the whole verse.
            if not heads and len(slots) == 1 \
                    and q_slot_counts.get(qid, 0) == 1 \
                    and len(qword_pos.get(qid, [])) == 1:
                wi = qword_pos[qid][0]
                words = v.words()
                if wi + 1 < len(words) and words[wi + 1].get("p") == "noun":
                    h = _node_for_word(v, words[wi + 1])
                    if h and _noun(h):
                        heads = [h["id"]]

            ordered_heads = sorted(
                enumerate(heads),
                key=lambda ih: (
                    _first_position(node_pos, ih[1]) is None,
                    _first_position(node_pos, ih[1])
                    if _first_position(node_pos, ih[1]) is not None
                    else 10 ** 9,
                    ih[0],
                ))
            heads = [h for _, h in ordered_heads]

            if len(heads) != len(slots):
                ok = False
                break

            for slot, hid in zip(slots, heads):
                hp = _first_position(node_pos, hid)
                tail, add_of = _find_tail(v, hid, hp)
                pairs.append({
                    "member": qid,
                    "head": hid,
                    "order": slot["order"],
                    "index": slot["index"],
                    "tail": tail,
                    "add_of": add_of,
                    "add_quantity": not _has_qual(v, hid, qid, "quantity"),
                })
            drop_qs.append(qid)

        if not ok:
            continue

        replacements = {p["index"]: p["head"] for p in pairs}
        new_text = _composite_text(v, cid, members, replacements)
        heads_text = ", ".join(
            (v.node(p["head"]) or {}).get("text") or p["head"]
            for p in pairs)
        yield {
            "at": cid,
            "pairs": pairs,
            "drop_qs": drop_qs,
            "new_text": new_text,
            "why": (f"{cnode.get('text') or cid} has a quantifier as a "
                    f"member; re-pointing to the quantified noun(s): "
                    f"{heads_text}"),
        }


def fix(v, f):
    """Retarget each quantifier member slot to its own quantified noun,
    attach the quantifier and construct complement as qualifiers, and
    rebuild the composite text from the member texts."""
    for qid in f["drop_qs"]:
        yield drop_edge(f["at"], "member", qid)

    for p in f["pairs"]:
        attrs = {}
        if p.get("order") is not None:
            attrs["order"] = p["order"]

        yield add_edge(f["at"], "member", p["head"],
                       "the coordinate names the quantified noun, not the "
                       "quantifier",
                       **attrs)

        if p.get("add_quantity"):
            yield add_edge(p["head"], "qualifier", p["member"],
                           "the quantifier of the coordinated noun phrase",
                           rel="quantity")

        if p.get("tail") and p.get("add_of"):
            yield add_edge(p["head"], "qualifier", p["tail"],
                           "the construct complement of the coordinated "
                           "noun",
                           rel="of")

    cur = (v.node(f["at"]) or {}).get("text")
    if f.get("new_text") and cur != f["new_text"]:
        yield set_attr(f["at"], "text", f["new_text"])


def validate(v, f):
    """Once fixed: no quantifier is still a member, every quantified noun is
    the sole member in its slot, no two slots share a head, the qualifiers
    are present, and the composite text is the joined member texts."""
    problems = []

    for qid in f["drop_qs"]:
        if any(e.get("dst") == qid for e in v.out(f["at"], "member")):
            problems.append(f"the quantifier {qid} is still a member of "
                            f"{f['at']}")

    heads = [p["head"] for p in f["pairs"]]
    if len(heads) != len(set(heads)):
        problems.append("two member slots re-pointed to the same noun")

    for p in f["pairs"]:
        head_edges = [e for e in v.out(f["at"], "member")
                      if e.get("dst") == p["head"]]
        if len(head_edges) != 1:
            problems.append(f"expected one member edge to {p['head']}, "
                            f"have {len(head_edges)}")
        elif p.get("order") is not None and \
                head_edges[0].get("order") != p["order"]:
            problems.append(f"the replacement member for {p['head']} lost "
                            f"its order")

        quantity = [e for e in v.out(p["head"], "qualifier")
                    if e.get("dst") == p["member"]
                    and e.get("rel") == "quantity"]
        if len(quantity) != 1:
            problems.append(f"missing or duplicate quantity qualifier from "
                            f"{p['head']} to {p['member']}")

        if p.get("tail"):
            of = [e for e in v.out(p["head"], "qualifier")
                  if e.get("dst") == p["tail"] and e.get("rel") == "of"]
            if len(of) != 1:
                problems.append(f"missing or duplicate of qualifier from "
                                f"{p['head']} to {p['tail']}")

    if f.get("new_text") and \
            (v.node(f["at"]) or {}).get("text") != f["new_text"]:
        problems.append(f"composite text was not rebuilt as the joined "
                        f"member texts: {(v.node(f['at']) or {}).get('text')}")

    return problems
