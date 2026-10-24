# PROPOSED by DeepSeek from detector clause_link_source_and_embedding — not enabled
# tools/fixrules/rules/clause_link_source_and_embedding.py
"""Detector for clause-link hosts chosen without respecting embedding.

Only a detector: fix yields nothing, validate returns [].
"""

NAME = "clause_link_source_and_embedding"
BASIS = "original"
TEST = ("an and/sequence/then edge whose source is embedded via within, or a "
        "narrative sequence whose wayyiqtol/weqatal destination has a "
        "nonfinite source, or whose source lies inside a Turn/part")


def _outermost_host(v, nid):
    """Climb out of `within` edges. Return the outermost host id, or None."""
    cur = nid
    seen = {cur}
    while True:
        within = [e for e in v.edges
                  if e.get("type") == "within" and e.get("src") == cur]
        if not within:
            break
        nxt = within[0].get("dst")
        if not nxt or nxt in seen:
            break
        node = v.node(nxt) or {}
        if not node.get("clause"):
            break
        seen.add(nxt)
        cur = nxt
    return cur if cur != nid else None


def _inside_turn_or_part(v, nid):
    """True if the clause is a part of a Turn or Communication node."""
    for e in v.edges:
        if e.get("type") != "part":
            continue
        if nid == e.get("src") or nid == e.get("dst"):
            other = e.get("dst") if e.get("src") == nid else e.get("src")
            parent = v.node(other) or {}
            if parent.get("kind") in ("Turn", "Communication"):
                return True
    return False


def detect(v):
    for e in v.edges:
        if not e.get("clause_link"):
            continue
        if e.get("type") not in ("and", "sequence", "then"):
            continue

        src = e.get("src")
        dst = e.get("dst")
        src_node = v.node(src) or {}
        dst_node = v.node(dst) or {}
        if not src_node.get("clause") or not dst_node.get("clause"):
            continue

        reasons = []
        host = _outermost_host(v, src)

        if host is not None:
            reasons.append(
                f"{e['type']} source {src} is embedded via within; "
                f"outermost host is {host}"
            )

        if (e.get("type") == "sequence" and
                dst_node.get("verb_mood") in ("wayyiqtol", "weqatal")):
            if src_node.get("upper_force") == "nonfinite":
                reasons.append(
                    f"narrative sequence destination {dst} is "
                    f"{dst_node.get('verb_mood')} but source {src} is nonfinite"
                )
            if _inside_turn_or_part(v, src):
                reasons.append(
                    f"narrative sequence source {src} is inside a Turn/part"
                )

        if reasons:
            finding = {
                "at": src,
                "edge_type": e["type"],
                "src": src,
                "dst": dst,
                "why": "; ".join(reasons),
            }
            if host is not None:
                finding["host"] = host
            yield finding


def fix(v, f):
    yield from ()


def validate(v, f):
    return []
