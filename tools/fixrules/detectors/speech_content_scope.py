# PROPOSED by DeepSeek from detector speech_content_scope — not enabled
# tools/fixrules/rules/speech_content_scope.py
"""Detector only: flags content/frame/part edges and Turn nodes that are
structural violations of speech embedding scope.

It never reads a content-word lemma; it uses clause form, edge type, and
the group kind only.
"""

NAME = "speech_content_scope"
BASIS = "original"
TEST = (
    "a content edge may come only from a finite saying/perceiving frame or a "
    "Turn/Communication; a quoted clause is not a new content source; "
    "wayyiqtol/weqatal after a reported run is sequence; non-finite reports "
    "do not mint performed Turns; frame/part edges must involve a Turn/Communication"
)

NONFINITE_MOODS = {"infinitive construct", "infinitive absolute"}
SEQUENCE_MOODS = {"wayyiqtol", "weqatal"}
SPEECH_KINDS = {"turn", "communication"}


def _is_turn(n):
    return isinstance(n, dict) and str(n.get("kind") or "").lower() in SPEECH_KINDS


def _is_clause(n):
    return isinstance(n, dict) and bool(n.get("clause"))


def _mood(n):
    return n.get("verb_mood") if isinstance(n, dict) else None


def _has_frame_edge(v, nid):
    return any(
        e.get("type") == "frame" and (e.get("src") == nid or e.get("dst") == nid)
        for e in v.edges
    )


def detect(v):
    content_edges = [e for e in v.edges if e.get("type") == "content"]
    quoted_dsts = {e["dst"] for e in content_edges}

    for e in content_edges:
        src = e.get("src")
        dst = e.get("dst")
        sn = v.node(src)
        dn = v.node(dst)

        # A weqatal/wayyiqtol after a reported run is sequence, not content.
        if _is_clause(dn) and _mood(dn) in SEQUENCE_MOODS:
            yield {
                "at": dst,
                "why": (
                    f"content edge ends at a {_mood(dn)} clause; "
                    "wayyiqtol/weqatal after a reported run is sequence, not content"
                ),
            }

        # Non-finite reports do not mint performed Turns.
        if _is_clause(sn) and _mood(sn) in NONFINITE_MOODS:
            yield {
                "at": src,
                "why": (
                    f"content edge starts from a non-finite {_mood(sn)} clause; "
                    "infinitive reports do not mint performed Turns"
                ),
            }

        # A quoted clause must not be made the source of another content edge.
        if _is_clause(sn) and src in quoted_dsts and not _has_frame_edge(v, src):
            yield {
                "at": src,
                "why": (
                    "content edge starts from a clause that is already the "
                    "destination of a content edge; quoted clauses at one level "
                    "belong to a Turn/part collection, not a chain"
                ),
            }

        # A content source must be a clause or a Turn/Communication node.
        if sn is not None and not _is_clause(sn) and not _is_turn(sn):
            yield {
                "at": src,
                "why": (
                    "content edge source is neither a clause nor a "
                    "Turn/Communication node"
                ),
            }

    # A part edge must come from the enclosing communication node.
    for e in v.edges:
        if e.get("type") != "part":
            continue
        sn = v.node(e.get("src"))
        if sn is not None and not _is_turn(sn):
            yield {
                "at": e.get("src"),
                "why": "part edge must come from a Turn/Communication node",
            }

    # A frame edge must involve a Turn/Communication at one end.
    for e in v.edges:
        if e.get("type") != "frame":
            continue
        s = v.node(e.get("src"))
        d = v.node(e.get("dst"))
        if s is not None and d is not None and not (_is_turn(s) or _is_turn(d)):
            yield {
                "at": e.get("src"),
                "why": "frame edge does not involve a Turn/Communication node",
            }


def fix(v, f):
    return []


def validate(v, f):
    return []
