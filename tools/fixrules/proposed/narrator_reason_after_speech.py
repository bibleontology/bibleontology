# PROPOSED by DeepSeek from refine narrator_reason_after_speech — not enabled
# tools/fixrules/rules/narrator_reason_after_speech.py
"""Narrator reason after a speech (original).

2Sa 17:14: "...and the LORD had ordained to thwart Ahithophel's good
counsel" follows a quoted speech, has waw + explicit noun subject + qatal,
and is wrongly minted as a speech turn. It is a false speech turn because
the only clause content it frames is an infinitive construct (purpose), not
a finite quotation.
"""
from fixrules.framework import add_edge, drop_edge

NAME = "narrator_reason_after_speech"
BASIS = "original"
TEST = (
    "A qatal clause with an explicit noun subject that follows a speech "
    "and is joined to that speech by 'and', but is framed as a turn whose "
    "only clause content is an infinitive verb, is removed from that "
    "non-speech turn and given a 'because' link from the preceding "
    "speech's frame, provided the clause is not itself part of any quoted "
    "turn and its subject is not that speech's speaker or addressee."
)

INFINITIVE_MOODS = {"infinitive construct", "infinitive absolute"}
TURN_EDGE_TYPES = ("frame", "part", "sender", "addressee", "head")


def _explicit_noun(n):
    return bool(n) and not n.get("implicit") and (
        n.get("pos") == "noun" or n.get("composite"))


def _expand(v, ids):
    out = set(ids or [])
    for nid in list(out):
        for e in v.out(nid, "member") or []:
            if e.get("dst"):
                out.add(e["dst"])
    return out


def _mentions(v, nid, candidates):
    if not candidates:
        return False
    return bool(_expand(v, {nid}) & _expand(v, set(candidates)))


def _speaker_or_addressee(v, groups, frames):
    """The speech's stated speaker/addressee ids, falling back to the frame's
    subject when no sender/addressee edge names one."""
    ids = set()
    for gid in groups:
        for edge_type in ("sender", "addressee"):
            for e in v.out(gid, edge_type) or []:
                if e.get("dst"):
                    ids.add(e["dst"])
    if ids:
        return ids
    for fid in frames:
        r = v.roles(v.node(fid)) or {}
        ids.update(r.get("s", []))
    return ids


def _inside_any_turn(v, clause_id):
    """True if this clause is already the quoted content of a turn."""
    return any(e.get("type") == "part" and e.get("dst") == clause_id
               for e in v.into(clause_id, "part"))


def _is_nonfinite_clause(v, nid):
    n = v.node(nid) or {}
    if not n.get("clause"):
        return False
    mood = n.get("verb_mood")
    if mood in INFINITIVE_MOODS:
        return True
    return mood is None and n.get("upper_force") == "nonfinite"


def _framed_content(v, frame_id, turns):
    """Clause ids this frame/turn frames: direct content and turn parts."""
    ids = set()
    for e in v.out(frame_id, "content") or []:
        if (v.node(e.get("dst")) or {}).get("clause"):
            ids.add(e["dst"])
    for tid in turns:
        for e in v.out(tid, "part") or []:
            if (v.node(e.get("dst")) or {}).get("clause"):
                ids.add(e["dst"])
    # The frame itself is not the turn's content.
    ids.discard(frame_id)
    return ids


def _only_infinitive_content(v, frame_id, turns):
    """True if this turn has clause content, and all of it is nonfinite."""
    ids = _framed_content(v, frame_id, turns)
    return bool(ids) and all(_is_nonfinite_clause(v, nid) for nid in ids)


def _previous_speech(v, clauses, k):
    """(frame, quote, turns) for the nearest quoted speech before clauses[k]."""
    for j in range(k - 1, -1, -1):
        q = clauses[j]
        frames = [e["src"] for e in v.into(q["id"], "content")
                  if (v.node(e.get("src")) or {}).get("clause")]
        turns = [e["src"] for e in v.into(q["id"], "part")]
        if frames and turns:
            return frames[0], q["id"], turns
    return None


def detect(v):
    """Where: the narrator's qatal reason clause after a speech, wrongly a turn."""
    clauses = v.clauses()
    for k in range(1, len(clauses)):
        c = clauses[k]

        if c.get("verb_mood") != "qatal":
            continue

        subject_ids = (v.roles(c) or {}).get("s") or []
        if len(subject_ids) != 1:
            continue
        subject_id = subject_ids[0]
        if not _explicit_noun(v.node(subject_id)):
            continue

        # A clause inside a quotation is speech, never the narrator.
        if _inside_any_turn(v, c["id"]):
            continue

        # It must follow and be joined to the preceding speech.
        speech = _previous_speech(v, clauses, k)
        if not speech:
            continue
        frame_id, quote_id, groups = speech
        and_srcs = [e["src"] for e in v.into(c["id"], "and")
                    if e.get("type") == "and"]
        if not any(s in (frame_id, quote_id) for s in and_srcs):
            continue

        # It is minted as a turn frame, but its clause content is not a
        # finite quotation; it is only an infinitive clause.
        turns = [e["src"] for e in v.into(c["id"], "frame")]
        if not turns:
            continue
        if not _only_infinitive_content(v, c["id"], turns):
            continue

        # The narrator is not the same actor as the preceding speech's
        # speaker or addressee.
        if _mentions(v, subject_id,
                     _speaker_or_addressee(v, groups, [frame_id])):
            continue

        yield {
            "at": c["id"],
            "to": frame_id,
            "turns": turns,
            "why": (f"{c.get('text', c['id'])} is the narrator's reason "
                    f"for the preceding speech, not a speech turn"),
        }


def fix(v, f):
    """Dissolve the minted non-speech turn and link the narrator's reason."""
    seen = set()
    for tid in f["turns"]:
        for e in v.edges:
            if e.get("type") not in TURN_EDGE_TYPES:
                continue
            if e.get("src") != tid and e.get("dst") != tid:
                continue
            key = (e.get("src"), e.get("type"), e.get("dst"))
            if key in seen:
                continue
            seen.add(key)
            yield drop_edge(*key)

    yield add_edge(
        f["to"],
        "because",
        f["at"],
        "the narrator gives the reason for the preceding speech",
    )


def validate(v, f):
    """After the fix: exactly one because-link from the frame, and no turn
    edges left around the minted turn node."""
    problems = []

    becauses = [e.get("src") for e in v.into(f["at"], "because")]
    if becauses != [f["to"]]:
        problems.append(
            f"expected exactly one because from {f['to']}, got {becauses}"
        )

    for tid in f["turns"]:
        for e in v.edges:
            if e.get("type") in TURN_EDGE_TYPES and (
                e.get("src") == tid or e.get("dst") == tid
            ):
                problems.append(
                    f"turn {tid} still has a {e.get('type')} edge"
                )

    return problems
