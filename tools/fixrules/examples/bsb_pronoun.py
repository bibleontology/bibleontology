"""WORKED EXAMPLE (translation fallback). Built and measured: 8/16 as first
tried (any name in the verse), 12-13/16 as below.

2Ch 36:20 "he took into exile the remnant": the Hebrew has only "he", and
several earlier names agree with it. The BSB reads "carried by
NEBUCHADNEZZAR into exile", and its editors tagged "Nebuchadnezzar" to no
Hebrew word in the verse, so the name is the translators' supplied reading.
Why the Hebrew cannot decide: more than one earlier person agrees in person,
gender and number. What picks one is the topic, which is meaning, not form.

Rule: a third-person subject that is still unresolved takes the one
earlier-named person or place (in the chapter, up to 40 clauses back) that
meets all of these:
- the BSB verse supplies its name untagged;
- the verse's Hebrew does not contain it;
- it agrees in number.
Misfires: a place ("fall at RAMOTH-gilead", 2Ch 18:19), and "he spoke by
his servant" given to Jeroboam, not the LORD (1Ki 14:18).

(The built pass keeps one 40-clause window running across the chapter.
This example looks back over the verse's own clauses and up to 20 verses
before it, which comes to the same thing for all but the longest
chapters.)
"""
import re

from fixrules.framework import add_edge

NAME = "bsb_pronoun"
BASIS = "translation"
TEST = ("an unresolved third-person subject takes the single earlier-named "
        "person or place whose name the BSB supplies untagged in this verse, "
        "not in the verse's Hebrew, agreeing in number")


def _num(s):
    return re.sub(r"\D", "", str(s or "")).lstrip("0")


def _named(v, clauses):
    """Proper nouns filling roles of these clauses, in order."""
    out = []
    for c in clauses:
        for ids in v.roles(c).values():
            out += [i for i in ids if (v.node(i) or {}).get("proper")]
    return out


def detect(v):
    """Where: an unresolved third-person subject with exactly one candidate
    the BSB supplies."""
    text, spans = v.bsb()
    if not text:
        return
    here = {_num(n.get("strong")) for n in v.nodes.values()
            if n.get("strong") and not n.get("clause")}
    back = []
    for pv in reversed(v.before(20)):
        back += [(pv, i) for i in _named(pv, pv.clauses())]
    for c in v.clauses():
        window = back[-40:]
        s = (v.roles(c).get("s") or [None])[0]
        sn = v.node(s) or {}
        if s and not v.refers(s) and sn.get("person") == "third" and \
                (sn.get("implicit") or sn.get("class") == "pron"):
            cands = {}
            for pv, nid in window:
                n = pv.node(nid) or {}
                name = (n.get("text") or "").strip()
                if len(name) < 3 or _num(n.get("strong")) in here:
                    continue
                if sn.get("number") and \
                        sn["number"] != (n.get("number") or "singular"):
                    continue
                for m in re.finditer(r"\b" + re.escape(name) + r"\b", text):
                    if not any(a < m.end() and b > m.start()
                               for a, b, _ in spans):
                        cands[name] = nid
                        break
            if len(cands) == 1:
                name, nid = next(iter(cands.items()))
                yield {"at": s, "to": nid, "name": name,
                       "why": f"the BSB supplies '{name}' for "
                              f"{sn.get('text')} in {c['text']}"}
        back += [(v, i) for i in _named(v, [c])]


def fix(v, f):
    yield add_edge(f["at"], "refers_to", f["to"],
                   "named by the BSB translation (supplied, not in the "
                   "Hebrew)")


def validate(v, f):
    """Once fixed: the pronoun has exactly one referent, a proper noun that
    agrees with it in number."""
    to = [e["dst"] for e in v.out(f["at"], "refers_to")]
    p, n = v.node(f["at"]) or {}, v.node(f["to"]) or {}
    problems = []
    if to != [f["to"]]:
        problems.append(f"expected one referent {f['to']}, have {to}")
    if not n.get("proper"):
        problems.append("the referent is not a proper noun")
    if p.get("number") and p["number"] != (n.get("number") or "singular"):
        problems.append("number disagrees")
    return problems
