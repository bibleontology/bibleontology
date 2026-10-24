# PROPOSED by DeepSeek from detector pronoun_suffix_resolution — not enabled
# tools/fixrules/rules/pronoun_suffix_resolution.py
"""Detector for pronoun / possessive-suffix resolution faults (original language).

This is a detect-only rule.  It reports places where an existing
`refers_to` / `whose` / `possessor` resolution breaks the leading-text,
same-content, addressee or voice rules, and also reports a relative
pronoun whose unique same-NP antecedent is left unresolved.
"""

import collections
import re

NAME = "pronoun_suffix_resolution"
BASIS = "original"
TEST = ("pronouns, possessive suffixes and inferred pronominals resolve only "
        "to a strictly earlier, non-coreferent, agreeing referent; 1cs "
        "suffixes in one voice go to one speaker; 2nd-person suffixes go to "
        "the addressee; a unique relative-pronoun antecedent in the same NP "
        "is resolved")

RES_TYPES = {"refers_to", "possessor", "whose"}
SUFFIX_TYPES = {"possessor", "whose"}
REL_LEMMAS = {"אֲשֶׁר", "אשׁר", "שֶׁ", "ש"}
REL_STRONGS = {"834", "7945"}


def _person(n):
    p = str(n.get("person") or "").strip().lower()
    if p in ("1", "1st", "first"):
        return "first"
    if p in ("2", "2nd", "second"):
        return "second"
    if p in ("3", "3rd", "third"):
        return "third"
    return p


def _number(n):
    num = str(n.get("number") or "").strip().lower()
    if num in ("sg", "sing", "singular", "1"):
        return "singular"
    if num in ("pl", "plural", "2"):
        return "plural"
    return num


def _is_first_sg(n):
    return _person(n) == "first" and _number(n) == "singular"


def _is_second(n):
    return _person(n) == "second"


def _strongs(n):
    s = re.sub(r"\D", "", str(n.get("strong") or ""))
    return s.lstrip("0")


def _is_pronoun_word(n):
    return (n.get("class") == "pron" or
            n.get("pos") in ("pronoun", "pron", "prn"))


def _is_nominal(n):
    if not n:
        return False
    return (n.get("pos") in ("noun", "adjective") or
            bool(n.get("proper")) or
            n.get("class") == "noun")


def _disp(v, nid):
    n = v.g.nodes.get(nid) or {}
    return n.get("text") or nid


def _node_positions(v, nid):
    """Word positions of node `nid` within this verse, if determinable."""
    n = v.g.nodes.get(nid) or {}
    if n.get("ref") != v.ref:
        return None

    text = n.get("text")
    lemma = n.get("lemma")
    out = []
    for i, w in enumerate(v.words()):
        if (text is not None and w.get("t") == text) or \
                (lemma is not None and w.get("l") == lemma):
            out.append(i)
    return out or None


def _strictly_prior(v, src, dst):
    """True if dst is textually before src; False if it is clearly not."""
    if src == dst:
        return False

    sref = src.rsplit("#", 1)[0]
    dref = dst.rsplit("#", 1)[0]
    pos = v.g._pos
    if sref not in pos or dref not in pos:
        return None

    si, di = pos[sref], pos[dref]
    if di < si:
        return True
    if di > si:
        return False

    sp = _node_positions(v, src)
    dp = _node_positions(v, dst)
    if not sp or not dp:
        return None

    if len(sp) == 1 and len(dp) == 1:
        return dp[0] < sp[0]

    # With duplicate words (one node per word text per verse), only flag the
    # clear case that no occurrence of the target precedes any source word.
    if any(d < s for s in sp for d in dp):
        return True
    if all(d >= s for s in sp for d in dp):
        return False
    return None


def _content_fillers(v):
    """content-id -> set of node ids that fill it, expanded through `member`."""
    member = collections.defaultdict(set)
    for e in v.edges:
        if e.get("type") == "member":
            member[e.get("src")].add(e.get("dst"))
            member[e.get("dst")].add(e.get("src"))

    def expand(nid):
        seen = set()
        stack = [nid]
        while stack:
            x = stack.pop()
            if x in seen:
                continue
            seen.add(x)
            stack.extend(member.get(x, set()) - seen)
        return seen

    out = collections.defaultdict(set)
    for e in v.edges:
        if e.get("clause_role") and e.get("src") and e.get("dst"):
            for x in expand(e.get("dst")):
                out[e["src"]].add(x)
    return out


def _same_content(v, fillers, src, dst):
    for cid, ids in fillers.items():
        if src in ids and dst in ids:
            return True
    return False


def _addressees(v):
    out = set()
    for e in v.edges:
        if e.get("type") == "addressee":
            if e.get("dst"):
                out.add(e["dst"])
            if e.get("src"):
                out.add(e["src"])
    return out


def _clauses_for_word(v, word_id):
    out = []
    for e in v.edges:
        if e.get("clause_role") and e.get("dst") == word_id and e.get("src"):
            cid = e.get("src")
            if "#ct" in cid and not cid.endswith("c"):
                out.append(cid.replace("#ct", "#cl", 1))
    return out


def _voice_key(v, src):
    """Return (container, speaker) for a word inside a communication part."""
    for clause_id in _clauses_for_word(v, src):
        for e in v.edges:
            if e.get("type") not in ("part", "frame"):
                continue
            container = None
            if e.get("dst") == clause_id:
                container = e.get("src")
            elif e.get("src") == clause_id:
                container = e.get("dst")
            if not container:
                continue

            speaker = None
            for se in v.edges:
                if se.get("type") == "sender":
                    if se.get("src") == container:
                        speaker = se.get("dst")
                        break
                    if se.get("dst") == container:
                        speaker = se.get("src")
                        break
            return (container, speaker)
    return None


def _relative_pronouns(v):
    out = []
    for nid, n in v.nodes.items():
        if not _is_pronoun_word(n):
            continue
        if n.get("type") == "relative" or \
                n.get("lemma") in REL_LEMMAS or \
                _strongs(n) in REL_STRONGS:
            out.append(nid)
    return out


def _as_content(nid):
    if "#ct" in nid:
        return nid
    if "#cl" in nid:
        return nid.replace("#cl", "#ct", 1)
    return nid


def _missing_relative(v, nid):
    """If `nid` is an unresolved relative pronoun with one clear same-NP
    antecedent, return a detection for it."""
    for e_role in v.edges:
        if not (e_role.get("clause_role") and e_role.get("dst") == nid and
                e_role.get("src")):
            continue
        cid = e_role["src"]
        if "#ct" in cid and cid.endswith("c"):
            continue
        inner_clause = cid.replace("#ct", "#cl", 1)

        for e in v.edges:
            if e.get("type") != "within":
                continue
            if e.get("dst") != inner_clause and e.get("src") != inner_clause:
                continue

            outer = e.get("src") if e.get("dst") == inner_clause else e.get("dst")
            if not outer:
                continue
            outer_content = _as_content(outer)
            if not outer_content:
                continue

            role = e.get("role") or e.get("rel")
            if not role:
                continue

            cands = v.roles(outer_content).get(role, [])
            cands = [c for c in cands
                     if c != nid and _is_nominal(v.g.nodes.get(c))]
            if len(cands) == 1:
                return {
                    "at": nid,
                    "why": (f"relative pronoun {_disp(v, nid)} has one "
                            f"same-NP antecedent {_disp(v, cands[0])} and is "
                            f"unresolved"),
                }
    return None


def detect(v):
    problems_by_edge = []
    reported = set()
    voice_groups = collections.defaultdict(list)
    fillers = _content_fillers(v)
    addressees = _addressees(v)

    # 1. Existing resolution edges.
    for e in v.edges:
        etype = e.get("type")
        if etype not in RES_TYPES:
            continue
        src = e.get("src")
        dst = e.get("dst")
        if not src or not dst:
            continue

        sn = v.g.nodes.get(src) or {}
        dn = v.g.nodes.get(dst) or {}
        issues = []

        prior = _strictly_prior(v, src, dst)
        if prior is False:
            issues.append(f"target {_disp(v, dst)} is not strictly prior "
                          f"to {_disp(v, src)}")

        if _same_content(v, fillers, src, dst):
            issues.append(f"target {_disp(v, dst)} is inside the same "
                          f"content as {_disp(v, src)}")

        if (etype in SUFFIX_TYPES and _is_second(sn) and addressees and
                dst not in addressees):
            issues.append(f"second-person target {_disp(v, dst)} is not "
                          f"the addressee")

        if issues:
            yield {"at": src, "why": "; ".join(issues)}
            reported.add(src)

        if etype in SUFFIX_TYPES and _is_first_sg(sn):
            key = _voice_key(v, src)
            if key is not None:
                voice_groups[key].append((src, dst))

    # 2. 1cs suffixes in one communication voice must share one speaker.
    for (container, speaker), items in voice_groups.items():
        if speaker is not None:
            for src, dst in items:
                if dst != speaker and src not in reported:
                    yield {
                        "at": src,
                        "why": (f"first-person singular suffix targets "
                                f"{_disp(v, dst)}, not the voice's speaker "
                                f"{_disp(v, speaker)}"),
                    }
                    reported.add(src)
        else:
            targets = {dst for _, dst in items}
            if len(targets) > 1:
                baseline = items[0][1]
                for src, dst in items:
                    if dst != baseline and src not in reported:
                        yield {
                            "at": src,
                            "why": (f"first-person singular suffixes in one "
                                    f"voice split across {_disp(v, baseline)} "
                                    f"and {_disp(v, dst)}"),
                        }
                        reported.add(src)

    # 3. Unresolved relative pronoun with a unique same-NP antecedent.
    for nid in _relative_pronouns(v):
        if v.refers(nid):
            continue
        finding = _missing_relative(v, nid)
        if finding is not None:
            yield finding


def fix(v, f):
    # Detect-only pass requested: no changes are proposed.
    return iter(())


def validate(v, f):
    return []
