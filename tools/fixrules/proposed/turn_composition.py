# PROPOSED by DeepSeek from refine turn_composition — not enabled
# tools/fixrules/rules/turn_composition.py
"""Turn composition: remove narration that was collected as speech.

General fault: a finite, waw-initial clause with an explicit subject and
no quoted non-infinitive content is narration, not a turn and not a part of
one.  The rule removes such a clause from a Turn's `part` edges, and
dissolves a Turn whose `frame` is such a clause.

It deliberately does NOT touch groups or nested speech turns: a frame that
is a verb of saying has quoted content, where a narration clause has none.
"""
from fixrules.framework import drop_edge, set_attr

NAME = "turn_composition"
BASIS = "original"
TEST = ("a Turn has a `part` that is a finite, waw-initial clause with an "
        "explicit subject and no quoted non-infinitive content, whose "
        "subject is outside the enclosing speech; or a Turn is framed by "
        "such a narration clause.  Remove the part / dissolve the minted "
        "Turn.  Never touch groups or nested turns framed by a verb of "
        "saying.")

FINITE_MOODS = {"qatal", "yiqtol", "wayyiqtol", "weqatal"}


def _turn_ids(v):
    """Only actual Turn nodes, not every group with frame+part."""
    out = []
    for nid, n in v.nodes.items():
        if str(n.get("kind") or "").lower() == "turn":
            out.append(nid)
    return out


def _single_frame(v, tid):
    frames = v.out(tid, "frame")
    if len(frames) == 1:
        return frames[0]["dst"]
    return None


def _quoted(v, frame):
    """Destinations of `frame`'s content edges that count as speech."""
    out = []
    for e in v.out(frame, "content"):
        n = v.node(e["dst"]) or {}
        if n.get("upper_force") == "nonfinite":
            continue
        if n.get("clause") or n.get("kind") or n.get("pair"):
            out.append(e["dst"])
    return out


def _explicit_subject_ids(v, clause):
    out = []
    for s in v.roles(clause).get("s", []):
        n = v.node(s) or {}
        if not n.get("implicit"):
            out.append(s)
    return out


def _begins_with_waw(c):
    """MACULA marks a clause-initial waw in the clause pattern, e.g.
    W-S-V-O; wayyiqtol/weqatal moods are themselves waw-prefixed."""
    rule = str(c.get("rule") or "")
    if rule:
        first = rule.split("-", 1)[0].strip().upper()
        if first.startswith("W"):
            return True
    return c.get("verb_mood") in ("wayyiqtol", "weqatal")


def _is_narration_clause(v, clause):
    """The fault shape: waw + explicit subject + finite verb, and no quoted
    non-infinitive content (therefore not a verb of saying)."""
    n = v.node(clause) or {}
    if not n.get("clause"):
        return False
    if n.get("verb_mood") not in FINITE_MOODS:
        return False
    if n.get("upper_force") == "nonfinite":
        return False
    if not _begins_with_waw(n):
        return False
    if not _explicit_subject_ids(v, clause):
        return False
    if _quoted(v, clause):
        return False
    return True


def _speech_participants(v, turn, frame):
    """Nodes that are the speaker or addressee of this turn, as far as the
    graph labels them."""
    ids = set()
    for e in v.out(turn, "sender"):
        ids.add(e["dst"])
    roles = v.roles(frame)
    for role in ("s", "o", "pp"):
        ids.update(roles.get(role, []))
    return ids


def _subject_outside_speech(v, clause, turn, frame):
    """The explicit subject of `clause` is not the speaker/addressee of the
    enclosing turn.  If the speech participants cannot be determined, do not
    fire."""
    speech = _speech_participants(v, turn, frame)
    if not speech:
        return False
    subjects = _explicit_subject_ids(v, clause)
    if not subjects:
        return False
    for s in subjects:
        if s in speech or v.refers(s) in speech:
            return False
    return True


def _bad_part(v, turn, frame, part):
    n = v.node(part) or {}

    if n.get("clause"):
        return _is_narration_clause(v, part) and \
            _subject_outside_speech(v, part, turn, frame)

    # A nested turn is only bad if it is itself framed by narration.  A
    # nested turn framed by a verb of saying is legitimate and untouched.
    if str(n.get("kind") or "").lower() == "turn":
        pframe = _single_frame(v, part)
        return bool(pframe and _is_narration_clause(v, pframe))

    # Groups (command-and-effect, parallels, acts of one agent) are by
    # design, never touched here.
    return False


def detect(v):
    """Yield one finding per Turn that needs dissolving, or per Turn with
    narration parts to remove."""
    for turn in _turn_ids(v):
        frame = _single_frame(v, turn)

        # A Turn minted around a narration clause: dissolve it.
        if frame and _is_narration_clause(v, frame):
            yield {
                "at": turn,
                "frame": frame,
                "dissolve": True,
                "bad_parts": [],
                "why": (f"Turn {turn} is framed by narration clause "
                        f"{frame}, not speech"),
            }
            continue

        if not frame or not (v.node(frame) or {}).get("clause"):
            continue

        bad_parts = []
        for e in v.out(turn, "part"):
            part = e["dst"]
            if _bad_part(v, turn, frame, part):
                bad_parts.append(part)

        if bad_parts:
            yield {
                "at": turn,
                "frame": frame,
                "dissolve": False,
                "bad_parts": bad_parts,
                "why": (f"Turn {turn} has narration as part: "
                        f"{bad_parts}"),
            }


def fix(v, f):
    if f.get("dissolve"):
        for e in list(v.out(f["at"])):
            yield drop_edge(e["src"], e["type"], e["dst"])
        yield set_attr(f["at"], "kind", None)
        yield set_attr(f["at"], "pair", False)
        return

    for part in f.get("bad_parts", []):
        yield drop_edge(f["at"], "part", part)


def validate(v, f):
    problems = []
    turn = f["at"]

    if f.get("dissolve"):
        n = v.node(turn) or {}
        if str(n.get("kind") or "").lower() == "turn" or n.get("pair"):
            problems.append("the node is still marked as a Turn/group")
        if v.out(turn):
            problems.append(
                f"the node still has outgoing edges: "
                f"{[e['type'] for e in v.out(turn)]}")
        return problems

    for part in f.get("bad_parts", []):
        if any(e.get("type") == "part" and e.get("dst") == part
               for e in v.out(turn, "part")):
            problems.append(f"{part} is still a part of {turn}")

    return problems
