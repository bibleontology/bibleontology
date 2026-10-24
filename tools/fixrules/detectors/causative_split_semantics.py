# PROPOSED by DeepSeek from detector causative_split_semantics — not enabled
# tools/fixrules/rules/causative_split_semantics.py
"""Detector for suspected causative-split semantics problems.

Precision is favoured over recall.  Where the brief calls for a semantic
judgement that cannot be made from general features (e.g. "base is
intransitive motion"), the detector fires on the structural footprint the
brief names: roles, hiphil stem, pronominal object, `o2`, and the shape of
the `causes` split.
"""

NAME = "causative_split_semantics"
BASIS = "original"
TEST = ("flags `causes` splits whose effect verb repeats the causative lemma "
        "while its subject is the outer object; hiphil splits where a "
        "pronominal object is also the effect subject and an `o2` is present "
        "as the likely inner subject; hiphil clauses with both object slots "
        "and no split; and splits whose inner event lacks a verb or a subject")


def _verb_node(v, ids):
    if not ids:
        return None, None
    for nid in ids:
        n = v.node(nid)
        if n and (n.get("verb") or n.get("pos") == "verb"):
            return nid, n
    return None, None


def _lemma_or_gloss(n):
    return n.get("lemma") or n.get("text") or n.get("usual") or ""


def _is_pronominal(n):
    if not n:
        return False
    return (n.get("class") == "pron"
            or n.get("pos") == "pronoun"
            or n.get("type") in ("personal", "prs", "pron")
            or n.get("implicit"))


def _is_hiphil(n):
    if not n:
        return False
    return (n.get("stem") or n.get("verb_stem")) == "hiphil"


def detect(v):
    """Yield one dict per suspected defective causative construction."""
    causes = [e for e in v.edges if e.get("type") == "causes"]
    in_split = {e.get("src") for e in causes} | {e.get("dst") for e in causes}

    # Problems inside an existing `causes` split.
    for e in causes:
        a, b = e.get("src"), e.get("dst")
        if not a or not b:
            continue

        outer, inner = a, b
        outer_roles = v.roles(outer)
        inner_roles = v.roles(inner)
        outer_verb_id, outer_verb = _verb_node(v, outer_roles.get("v"))
        inner_verb_id, inner_verb = _verb_node(v, inner_roles.get("v"))

        # A `causes` edge should run from the outer/causing content to the
        # inner/caused content.  If the assumed outer end has no hiphil verb
        # but the other end does, swap.
        if not _is_hiphil(outer_verb):
            a_roles, b_roles = v.roles(a), v.roles(b)
            a_verb_id, a_verb = _verb_node(v, a_roles.get("v"))
            b_verb_id, b_verb = _verb_node(v, b_roles.get("v"))
            if _is_hiphil(b_verb) and not _is_hiphil(a_verb):
                outer, inner = b, a
                outer_roles, inner_roles = b_roles, a_roles
                outer_verb_id, outer_verb = b_verb_id, b_verb
                inner_verb_id, inner_verb = a_verb_id, a_verb

        outer_objs = outer_roles.get("o", [])
        inner_subjs = inner_roles.get("s", [])

        # (1) Effect verb repeats the causative lemma, but the effect
        # subject is the outer object.
        if outer_verb_id and inner_verb_id and outer_objs and inner_subjs:
            key = _lemma_or_gloss(outer_verb)
            if key and key == _lemma_or_gloss(inner_verb):
                if not set(inner_subjs).isdisjoint(outer_objs):
                    yield {
                        "at": inner_verb_id,
                        "why": ("effect verb repeats the causative lemma "
                                "while its subject is the outer object"),
                    }

        # (2) Pronominal `o` plus `o2`, with the pronominal `o` currently
        # filling the effect subject.  The brief says the `o2` should be
        # the effect subject and the pronominal `o` a recipient/pp.
        pron_objs = [nid for nid in outer_roles.get("o", [])
                     if _is_pronominal(v.node(nid))]
        wrong_subjs = [nid for nid in pron_objs if nid in inner_subjs]
        if outer_verb_id and _is_hiphil(outer_verb) and wrong_subjs and \
                outer_roles.get("o2"):
            yield {
                "at": inner,
                "why": ("hiphil causes split has a pronominal object also "
                        "filling the effect subject while an o2 is present"),
            }

        # (4) A split that cannot compose: the caused event lacks a verb
        # or a subject.
        if not inner_verb_id or not inner_subjs:
            yield {
                "at": inner,
                "why": ("causes split cannot compose: inner event lacks "
                        "a verb or a subject"),
            }

    # (3) Hiphil clauses with both object slots but no `causes` split.
    for c in v.clauses():
        cid = v.content(c)
        if cid in in_split:
            continue
        roles = v.roles(cid)
        verb_id, verb = _verb_node(v, roles.get("v"))
        if verb_id and _is_hiphil(verb) and roles.get("o") and roles.get("o2"):
            yield {
                "at": c["id"],
                "why": ("hiphil clause has both an object and a second "
                        "object but no causes split"),
            }


def fix(v, f):
    yield from ()


def validate(v, f):
    return []
