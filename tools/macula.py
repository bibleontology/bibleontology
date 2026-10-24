"""MACULA syntax trees as the floor's base, with our layers kept on top.

2026-09-04: do not blindly assume that it does the job; use it as a base and
distill the extra value derived from it, taking the best of both.

## What MACULA is

Clear Bible's [macula-hebrew] and [macula-greek] (Clear Bible is Biblica's;
the data is (c) Biblica, Inc.): manually curated syntax trees over the whole
Hebrew Bible and Greek New Testament, **CC BY 4.0** with no non-commercial
clause and no share-alike. Attribution required as "MACULA Hebrew Linguistic
Datasets, available at https://github.com/Clear-Bible/macula-hebrew/" and
"MACULA Greek Linguistic Datasets, available at
https://github.com/Clear-Bible/macula-greek/" (tools/macula_credit.py).

It marks, per word and per constituent, exactly the things this project spent
2026-09-04 deriving:

    role="s" / "v" / "o" / "p"     subject, verb, object, predicate
    class="cl" rule="S-V-O"        clause and its constituent order
    rule="S-P"                     a VERBLESS clause
    rule="NpaNp"                   coordination -- NP and NP
    rule="NPofNP"                  a construct chain
    class="np" / "pp"              phrase types

Genesis 1:2 carries `role="s"` on *ha-arets*, the fronted subject that took an
afternoon to recover here. The derivation was still worth doing: it is why the
failure modes have names -- fronted subjects, fused prepositions, verbless
clauses, distributives -- and why MACULA can be evaluated rather than assumed.

## What it does NOT have, and why the project still exists

No speech acts, no assertion status, no assessor, no coordination-as-a-
collection-node, no pattern layer. MACULA answers "what is the grammatical
structure"; it does not answer "what is being claimed, by whom, and is it
being asserted or merely entertained". Those stay ours, and they are the
layers that carry meaning.

**So MACULA is a better floor, not a replacement for the building.**

## Attribution

MACULA Hebrew and Greek Linguistic Datasets, Clear Bible, CC BY 4.0.
Read from disk under `data/raw/macula/`; not redistributed by this project.

    python tools/macula.py                 # what is loaded, and coverage
    python tools/macula.py --compare       # MACULA against our derivation
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAC = ROOT / "data" / "raw" / "macula"
sys.path.insert(0, str(ROOT / "tools"))

# MACULA ids are "GEN 1:2"; ours are "Gen.1.2" internally and "Gen 1:2" in the
# English-facing layer. One table, both directions, so a mismatch is a missing
# key rather than a silently wrong join.
BOOK = {"GEN": "Gen", "EXO": "Exo", "LEV": "Lev", "NUM": "Num", "DEU": "Deu",
        "JOS": "Jos", "JDG": "Jdg", "RUT": "Rut", "1SA": "1Sa", "2SA": "2Sa",
        "1KI": "1Ki", "2KI": "2Ki", "1CH": "1Ch", "2CH": "2Ch", "EZR": "Ezr",
        "NEH": "Neh", "EST": "Est", "JOB": "Job", "PSA": "Psa", "PRO": "Pro",
        "ECC": "Ecc", "SNG": "Sng", "ISA": "Isa", "JER": "Jer", "LAM": "Lam",
        "EZK": "Ezk", "DAN": "Dan", "HOS": "Hos", "JOL": "Jol", "AMO": "Amo",
        "OBA": "Oba", "JON": "Jon", "MIC": "Mic", "NAM": "Nam", "HAB": "Hab",
        "ZEP": "Zep", "HAG": "Hag", "ZEC": "Zec", "MAL": "Mal",
        "MAT": "Mat", "MRK": "Mrk", "LUK": "Luk", "JHN": "Jhn", "ACT": "Act",
        "ROM": "Rom", "1CO": "1Co", "2CO": "2Co", "GAL": "Gal", "EPH": "Eph",
        "PHP": "Php", "COL": "Col", "1TH": "1Th", "2TH": "2Th", "1TI": "1Ti",
        "2TI": "2Ti", "TIT": "Tit", "PHM": "Phm", "HEB": "Heb", "JAS": "Jas",
        "1PE": "1Pe", "2PE": "2Pe", "1JN": "1Jn", "2JN": "2Jn", "3JN": "3Jn",
        "JUD": "Jud", "REV": "Rev"}
REF = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)")

# Constituent rules that name a relation rather than just an order. These are
# the ones the ontology cares about, because each is a different edge.
RELATION = {"NpaNp": "coordinate", "NPofNP": "construct", "DetNP": "definite",
            "PrepNp": "prepositional", "ADJP": "attributive",
            "NpAnp": "coordinate", "CLaCL": "coordinate"}


def _ref(s):
    m = REF.match(s or "")
    if not m:
        return None
    b = BOOK.get(m.group(1))
    return f"{b}.{int(m.group(2))}.{int(m.group(3))}" if b else None


def _words(e):
    return [w for w in e.iter("w")]


def _gloss(e):
    return " ".join((w.get("gloss") or w.get("english") or "").replace(".", " ")
                    for w in _words(e)).strip()


def _constituents(cl):
    """Direct children of a clause, each with its role and its relation."""
    out = []
    for ch in list(cl):
        if ch.tag == "w":
            out.append({"role": ch.get("role") or "-", "rel": None,
                        "gloss": (ch.get("gloss") or ch.get("english") or ""
                                  ).replace(".", " ").strip(),
                        "n": 1, "lemmas": [ch.get("lemma") or ""]})
        else:
            rule = ch.get("rule") or ""
            out.append({"role": ch.get("role") or "-",
                        "rel": RELATION.get(rule, rule or None),
                        "gloss": _gloss(ch), "n": len(_words(ch)),
                        "lemmas": [w.get("lemma") or "" for w in _words(ch)],
                        "class": ch.get("class")})
    return out


def load(paths=None):
    """Every clause MACULA marks, keyed by our verse reference.

    A clause can span verses and a verse can hold several clauses, so the key
    is the verse of the clause's FIRST word -- the same convention the rest of
    this project uses for a window.
    """
    files = list(paths or sorted(MAC.rglob("*.xml")))
    out = collections.defaultdict(list)
    for f in files:
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for cl in root.iter("wg"):
            if cl.get("class") != "cl":
                continue
            ws = _words(cl)
            if not ws:
                continue
            ref = _ref(ws[0].get("ref") or "")
            if not ref:
                continue
            out[ref].append({
                "rule": cl.get("rule") or "",
                "verbless": "V" not in (cl.get("rule") or "").split("-"),
                "n": len(ws),
                "parts": _constituents(cl),
                "gloss": _gloss(cl)})
    return out


ROLE = {"s": "subject", "v": "verb", "o": "object", "p": "predicate",
        "io": "indirect", "adv": "adverbial", "pp": "prepositional",
        "cmpl": "complement", "-": None}


def tree(e, depth=0):
    """One constituent as a nested dict, keeping MACULA's own nesting.

    The notation was hard to read; parens and indentation, or JSON with
    standard pretty printing, would show the sentence broken down in one clean
    statement.

    Right, and it fixes the data rather than only the display. MACULA's XML is
    a TREE and the first reader here flattened it to one level -- which threw
    away the nesting that makes "the surface of the waters" a phrase inside a
    prepositional phrase inside a clause. A symbol notation (dots, circled
    pluses, angle brackets) then had to encode depth in punctuation, which is
    exactly the thing indentation does better and for free.

    So: nested dicts, one key per thing worth knowing, and `json.dumps(...,
    indent=2)` is the pretty printer.
    """
    if e.tag == "w":
        out = {"word": (e.get("gloss") or e.get("english") or "").replace(
            ".", " ").strip()}
        for src, dst in (("lemma", "lemma"), ("pos", "pos"),
                         ("state", "state"), ("type", "type")):
            if e.get(src):
                out[dst] = e.get(src)
        if ROLE.get(e.get("role")):
            out["role"] = ROLE[e.get("role")]
        return out

    rule = e.get("rule") or ""
    out = {}
    if ROLE.get(e.get("role")):
        out["role"] = ROLE[e.get("role")]
    if e.get("class") == "cl":
        out["clause"] = rule or "?"
        out["verbless"] = "V" not in rule.split("-")
    else:
        out["phrase"] = e.get("class") or "?"
        if RELATION.get(rule):
            out["relation"] = RELATION[rule]
        elif rule:
            out["rule"] = rule
    out["text"] = _gloss(e)
    kids = [tree(c, depth + 1) for c in list(e)]
    if kids:
        out["parts"] = kids
    return out


def compact(e):
    """The same tree, shaped the way a data structure should read.

    The verbose form is one object per word and five lines each, which buries
    the structure it exists to show. This makes the ROLE the key -- because
    that is what it is -- collapses a leaf phrase to a string, and expands only
    where there is genuine structure to expand:

        {"clause": "S-V-O",
         "subject": "the earth",
         "verb": "it was",
         "object": {"coordinate": ["formlessness", "emptiness"]}}

    A construct chain becomes {"construct": {"head": ..., "of": ...}} rather
    than a dot-joined string, so "the deep" stays a retrievable thing --
    decision D2 -- instead of being punctuation inside a phrase.
    """
    if e.tag == "w":
        return (e.get("gloss") or e.get("english") or "").replace(
            ".", " ").strip()

    rule = e.get("rule") or ""
    rel = RELATION.get(rule)
    kids = [c for c in list(e)]
    content = [c for c in kids
               if not (c.tag == "w" and c.get("pos") in ("conjunction",)
                       and (c.get("gloss") or "") in ("and", "or"))]

    if e.get("class") == "cl":
        out = {"clause": rule or "?"}
        if "V" not in rule.split("-"):
            out["verbless"] = True
        for c in kids:
            r = ROLE.get(c.get("role"))
            v = compact(c)
            if r:
                out[r] = v
            elif isinstance(v, str) and v:
                out.setdefault("also", []).append(v)
            elif isinstance(v, dict):
                out.setdefault("also", []).append(v)
        return out

    if rel == "coordinate":
        return {"coordinate": [compact(c) for c in content]}
    if rel == "construct":
        parts = [compact(c) for c in content]
        return {"construct": {"head": parts[0],
                              "of": parts[1] if len(parts) == 2
                              else parts[1:]}}
    if rel == "prepositional":
        prep = next((compact(c) for c in kids if c.tag == "w"), "")
        rest = [compact(c) for c in kids[1:]]
        # Hebrew fuses the preposition onto the word, so a PP can have no
        # child beyond the one that carries it. Gen 1:1 is *bereshit*, one
        # word, and taking only non-word children produced {"in": []}.
        rest = [x for x in rest if x]
        if not rest:
            return _gloss(e)
        return {prep or "prep": rest[0] if len(rest) == 1 else rest}
    # A wrapper with no class, rule or role of its own carries no information
    # -- it is the sentence's outer bracket. Returning it as a "phrase" whose
    # text is the entire verse buried the clauses one level down for nothing.
    inner = [compact(c) for c in kids if c.tag != "w"]
    if not e.get("class") and not rule and inner:
        return inner[0] if len(inner) == 1 else inner
    txt = _gloss(e)
    if inner and any(isinstance(x, dict) for x in inner):
        # A wrapper holding exactly one structured child, with no word of its
        # own, adds a level of indentation and no information. Esther 8:9 was
        # six levels deep on nothing but these.
        own_words = [c for c in kids if c.tag == "w"]
        if len(inner) == 1 and not own_words:
            return inner[0]
        return {"phrase": txt, "parts": inner}
    return txt


# Participants are IN the event; adjuncts are predicates OF it. MACULA marks
# the difference on the constituent, so the split needs no inference.
PARTICIPANT = {"s": "agent", "v": None, "o": "theme", "io": "recipient",
               "o2": "theme2", "p": "is", "vc": "complement",
               "topic": "topic"}
ADJUNCT = {"pp", "adv"}


def event(cl):
    """A clause as a reified event, with adjuncts scoping over the whole tuple.

    On Genesis 1:1: the preposition sits outside the SVO tuple and modifies it,
    since subject, verb and object are more tightly bound than the preposition:
    (God->created->(h, e))->occurred_in->the_beginning

    That is Davidsonian event semantics, and for a GRAPH it is not a stylistic
    preference — it is what makes adjuncts representable at all:

        ∃e. created(e) ∧ agent(e, God) ∧ theme(e, ⟨heavens, earth⟩)
                       ∧ in(e, beginning)

    A flat `PP-V-S-O` is a four-place thing with no edge representation.
    Reified, the SVO core becomes a node and every adjunct is one more edge off
    it — so *when*, *where* and *how* can be added without changing anyone's
    arity. It is the same move RDF makes for n-ary relations.

    The participant/adjunct split is read from MACULA rather than guessed:
    `s`/`o`/`io` are in the event, `pp`/`adv` are about it.

    **What is deliberately not done here**: naming the adjunct relation.
    "In the beginning" is temporal and "in the land" is spatial, and Hebrew's
    prefixed prepositions do not distinguish them — *bet* alone covers in,
    with, by and against. Greek does mark it, through preposition plus case.
    So the preposition stays as the key, and typing it is a later step with a
    known cost, rather than a guess made here.
    """
    # `agent` and `theme` are THEMATIC roles and a copula has neither. The
    # first version emitted Gen 1:2 as agent="the earth", theme=⟨formlessness,
    # emptiness⟩ -- but the earth does nothing to formlessness, it is
    # described as it. Where the verb is *hayah* the grammatical labels are
    # used instead, because they are what the text supports.
    #
    # This is the open-vocabulary wall again in a new place: knowing that
    # *bara* takes an agent and *hayah* does not is lexical knowledge, and
    # only the copula is a closed enough class to decide here. Every other
    # stative verb still gets thematic labels it may not deserve, and that is
    # a known over-claim rather than a solved problem.
    copula = any(w.get("lemma") in ("הָיָה",) and w.get("role") == "v"
                 for w in cl.iter("w"))
    names = dict(PARTICIPANT)
    if copula or "V" not in (cl.get("rule") or "").split("-"):
        names.update({"s": "subject", "o": "is", "p": "is"})

    core, adj = {}, []
    for ch in list(cl):
        r = ch.get("role")
        v = compact(ch)
        if r == "v":
            core["did"] = v
        elif r in names:
            core[names[r]] = v
        elif r in ADJUNCT:
            adj.append((r, v))
        elif isinstance(v, (str, dict)) and v:
            adj.append(("also", v))
    # There can be no event without a verb, and calling one an event was wrong. A verbless clause asserts that a
    # STATE holds -- "darkness over the surface of the deep" -- and nothing
    # occurs in it. The distinction is not cosmetic: an event has a time and
    # can be sequenced, a state has an interval and cannot.
    rule = cl.get("rule") or ""
    verbless = "V" not in rule.split("-")
    out = {("state" if verbless else "event"): core or None}
    for r, v in adj:
        # A prepositional adjunct arrives as {preposition: value}; lifting it
        # to the outer level is what puts it OUTSIDE the tuple, which is the
        # whole point.
        if isinstance(v, dict) and len(v) == 1 and r == "pp":
            k, val = next(iter(v.items()))
            out.setdefault(k, val)
        else:
            out.setdefault(r if r != "also" else "and", v)
    return out


def nodes(cl, mint=None):
    """The clause as nodes and edges, with composite phrases reified.

    **STATUS: NOT WORKING. Do not build on this yet.**

    It is correct on simple narrative -- Gen 1:1 and 1:2 come out clean -- and
    that was misleading. Psalm 23 produces garbage:

        Psa 23:1  src="isMyOfShepherd"          a node minted from "[is] my
                                                shepherd"; ident() strips
                                                articles but not copulas or
                                                possessives
        Psa 23:2  {src: None, type: "he",       the VERB became the target and
                   dst: "makesMeLieDown"}       a pronoun became the relation

    Measured on the stress set: 24 of 84 edges have no source (28%), and that
    figure UNDERSTATES the problem because some of the 72% that do have a
    source are wrong. There is a coverage number here and no correctness
    number, which is the same trap the completeness metric fell into earlier
    the same day.

    Two things are needed before this is trustworthy, and neither is a tweak:
    a node identity that is not a mangled gloss, and edge construction that
    distinguishes the predicate from its arguments instead of reading whatever
    key happens to be left over.

    On Gen 1:2: deep and surface are simple nodes;
    surfaceOfDeep->references->(surface->partOf->deep);
    darkness->locatedOver->surfaceOfDeep

    That is the construct chain reified, which is the same move as reifying
    the clause, one level down. "The surface of the deep" is a THING you can
    point at -- distinct from `surface` and from `deep` -- and it exists
    because a relation holds between them. So the composite gets a node and
    the node references the relation that constitutes it.

    Why it matters for a graph: without it, `darkness over surface of deep`
    is either a 3-place edge or a lossy binary one. With it, every edge is
    binary and nothing is lost.

    **What is NOT typed here, and it is the same wall as everywhere else.**
    The proposal wrote `partOf`, which is right for *penei tehom*. But the Hebrew
    construct is one form covering many relations:

        the surface OF the deep     part-whole
        the word OF the LORD        source
        the month OF Sivan          identity / apposition
        a man OF valour             attribute

    The morphology marks the construct state and says nothing about which. So
    the edge is emitted as `of` -- structure captured, type deferred -- which
    is the standing rule: the relationship type might be abstract but the
    structure is captured.
    """
    made, edges = [], []

    def ident(txt, proper=False):
        """A node id from a gloss.

        MACULA's gloss carries the relation and the article inside the word --
        *tehom* glosses as "of.the.deep" -- so minting naively produced
        `theSurfaceOfOfthedeep`. The leading `of` belongs to the construct
        edge, not to the node, and the article is a property rather than part
        of the name.
        """
        t = re.sub(r"[^a-z0-9 ]", " ", (txt or "").lower())
        w = [x for x in t.split() if x]
        while w and w[0] in ("of", "the", "a", "an", "and", "et"):
            w.pop(0)
        if not w:
            return "?"
        head = w[0].capitalize() if proper else w[0]
        return "".join([head] + [x.capitalize() for x in w[1:]])

    def emit(v):
        """Return a node id for a value, minting composites as needed."""
        if isinstance(v, str):
            nid = ident(v)
            if nid not in made:
                made.append(nid)
            return nid
        if not isinstance(v, dict):
            return None
        if "construct" in v:
            head = emit(v["construct"]["head"])
            of = v["construct"]["of"]
            tail = emit(of if isinstance(of, (str, dict)) else of[0])
            nid = f"{head}Of{(tail or '')[:1].upper()}{(tail or '')[1:]}"
            if nid not in made:
                made.append(nid)
            # the composite references the relation that constitutes it
            edges.append({"src": nid, "type": "references",
                          "dst": {"src": head, "type": "of", "dst": tail}})
            return nid
        if "coordinate" in v:
            parts = [emit(x) for x in v["coordinate"]]
            nid = "and".join(p for p in parts if p)
            if nid not in made:
                made.append(nid)
            for p in parts:
                if p:
                    edges.append({"src": nid, "type": "member", "dst": p})
            return nid
        # a prepositional wrapper: {preposition: value}
        if len(v) == 1:
            k, val = next(iter(v.items()))
            inner = emit(val)
            return {"prep": k, "node": inner}
        return None

    e = event(cl)
    core = e.get("state") or e.get("event") or {}
    subj = core.get("subject") or core.get("agent")
    src = emit(subj) if subj else None
    for k, v in core.items():
        if k in ("subject", "agent", "did"):
            continue
        got = emit(v)
        if isinstance(got, dict):                 # predicate is a PP
            edges.append({"src": src, "type": got["prep"], "dst": got["node"]})
        elif got:
            edges.append({"src": src, "type": core.get("did") or k,
                          "dst": got})
    for k, v in e.items():
        if k in ("state", "event"):
            continue
        got = emit(v)
        if isinstance(got, dict):
            edges.append({"src": src, "type": got["prep"], "dst": got["node"]})
        elif got:
            edges.append({"src": src, "type": k, "dst": got})
    return {"nodes": made, "edges": edges,
            "note": "construct relations emitted as `of`; part-whole vs "
                    "source vs identity is not marked in the morphology"}


def _agreement(cl):
    """(person, gender, number) of the clause's finite verb, or None."""
    for w in cl.iter("w"):
        if w.get("role") == "v" or w.get("pos") == "verb":
            p, g, n = w.get("person"), w.get("gender"), w.get("number")
            if p or n:
                return (p, g, n)
    return None


def verse_nodes(clauses, carry=None):
    """`carry` is the last stated subject from the PRECEDING verse.

    A verse is a chapter-division, not a grammatical unit, and a subject runs
    straight through one. Psalm 23:2 is the case: "in pastures of grass he
    makes me lie down" states no subject at all, and the one it wants --
    Yahweh -- was stated in 23:1. Resetting at the verse boundary threw that
    away and left four of the verse's six edges with no source.
    """
    """Nodes and edges for a verse, carrying the subject across a clause chain.

    Two failures showed up when `nodes()` was run over the stress set:

        26 of 73 edges had NO SOURCE   a clause whose subject is elided
        14 clauses emitted NO EDGE     subject + verb and nothing else

    **Elision.** Hebrew drops the subject constantly because the verb carries
    person, gender and number. MACULA's own resolution does not cover it --
    `subjref` is 7% of Hebrew words and `referent` is 0% -- so it is resolved
    here, but narrowly: an elided subject inherits from **the nearest
    preceding clause subject that agrees**. That is much tighter than the
    recency-over-all-nouns rule that scored 29% in August, because the
    candidate set is clause subjects rather than every noun, and agreement
    has to match rather than merely being compatible.

    Marked `inferred` wherever it fires, because an inherited subject is a
    different kind of claim from a stated one and the graph should not
    pretend otherwise.

    **Intransitives.** "And there was light" is subject and verb with no
    object, and the first version emitted nothing at all. A unary predication
    is still a fact -- light came to be -- so it becomes an edge with no
    target rather than no edge.
    """
    out_nodes, out_edges = [], []
    last = carry                     # (id, agreement) of the last stated subject
    for cl in clauses:
        g = nodes(cl)
        agree = _agreement(cl)
        stated = any(e.get("src") for e in g["edges"])
        subj = next((e["src"] for e in g["edges"] if e.get("src")), None)
        if subj:
            last = (subj, agree)
        elif last and agree and last[1] and agree[0] == last[1][0] \
                and agree[2] == last[1][2]:
            subj = last[0]
            for e in g["edges"]:
                if not e.get("src"):
                    e["src"] = subj
                    e["inferred_subject"] = True
        for n in g["nodes"]:
            if n not in out_nodes:
                out_nodes.append(n)
        # a clause with a subject and a verb and nothing else still asserts
        e0 = event(cl)
        core = e0.get("event") or e0.get("state") or {}
        if not g["edges"] and core.get("did"):
            s = next((v for k, v in core.items()
                      if k in ("subject", "agent") and isinstance(v, str)),
                     None)
            sid = None
            if s:
                sid = re.sub(r"[^A-Za-z0-9]", "", s.split()[-1]).lower()
                if sid and sid not in out_nodes:
                    out_nodes.append(sid)
            elif last:
                sid = last[0]
            if sid:
                out_edges.append({"src": sid, "type": core["did"],
                                  "dst": None, "intransitive": True,
                                  **({"inferred_subject": True}
                                     if not s else {})})
        out_edges.extend(g["edges"])
    return {"nodes": out_nodes, "edges": out_edges, "carry": last}


def stack(cl, act=None, status=None):
    """The clause as a stack of nodes, each level wrapping the one below.

    The point is structure more than wording: the event is a node and the
    event with its preposition is a higher-level node.

    Sharper than adjuncts-as-edges, and it fixes a real defect: with adjuncts
    as sibling keys, a clause with two of them cannot say which scopes over
    which. Nesting states it.

    **And it unifies four things this project built separately.** An adjunct,
    a negation, an attribution and a speech act are the same move — an
    operator that takes a proposition and yields a new node one level up:

        level 1   event            (God, created, ⟨heavens, earth⟩)
        level 2   + adjunct        (that) in (the beginning)
        level 3   + speech act     (that) asserted
        level 4   + attribution    (that) attributed to God

    Each level is addressable, which is the point. "What happened" is level 1;
    "God's creating-in-the-beginning" is level 2; "the claim that it happened"
    is level 3. Those are different referents and a flat structure conflates
    them.

    It is also the same containment the upper layers already use — clause
    inside speech inside passage inside pattern. The clause is not a special
    case; it is the bottom of one structure.
    """
    base = event(cl)
    core = {"level": 1, "event": base.get("event")}
    if base.get("verbless"):
        core["verbless"] = True
    # KNOWN ASSUMPTION: the levels stack in TEXT order, nearest constituent
    # innermost. For adjuncts that is usually right and it is what MACULA's
    # constituent order supports. It is NOT right in general -- a negation
    # scopes over everything regardless of where it sits, and a modal or a
    # frequency adverb can outscope a locative that precedes it. Recording the
    # assumption rather than presenting the order as derived, because the
    # difference only shows up on the sentences that matter most.
    node, lvl = core, 1
    for k, v in base.items():
        if k in ("event", "verbless"):
            continue
        lvl += 1
        node = {"level": lvl, "modifier": k, "value": v, "of": node}
    if act:
        lvl += 1
        node = {"level": lvl, "act": act, "of": node}
    if status:
        lvl += 1
        node = {"level": lvl, "status": status, "of": node}
    return node


def sentence(ref, data=None, ours=None):
    """A whole verse as one nested structure, ready for pretty printing."""
    files = sorted(MAC.rglob("*.xml"))
    for f in files:
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for s in root.iter("sentence"):
            ws = _words(s)
            if not ws or _ref(ws[0].get("ref") or "") != ref:
                continue
            out = {"ref": ref, "words": len(ws),
                   "source": "MACULA, Clear Bible, CC BY 4.0"}
            if ours:
                out["ours"] = ours
            out["parts"] = [tree(c) for c in list(s) if c.tag == "wg"]
            return out
    return None


EXTRACT = ROOT / "data" / "macula-clauses.jsonl.gz"


def extract():
    """Write the fields we use, committed, so the repo rebuilds without the source.

    A copy in the repo is needed despite the duplication. The insurance argument is real -- a checksum proves a file
    drifted but cannot give back the one you lost, and a rebuildable graph is
    only rebuildable while its inputs exist.

    But the raw XML is 49 MB for the stress chapters alone and roughly 1.5 GB
    for the corpus, which is not what git is for. **This commits the
    EXTRACT instead: 9% of the raw size, ~1% gzipped**, holding exactly the
    fields the pipeline reads.

    That is not duplication. It is our derived artifact, which the build needs
    anyway, and CC BY 4.0 explicitly permits the derivative with attribution.
    It also makes an upgrade reviewable the right way: regenerate, and read the
    git diff, rather than trusting a hash to tell you nothing changed.
    """
    import gzip
    data = load()
    n = 0
    with gzip.open(EXTRACT, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"_source": "MACULA Hebrew Linguistic Datasets, available at "
                                        "https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek "
                                        "Linguistic Datasets, available at "
                                        "https://github.com/Clear-Bible/macula-greek/; © Biblica, "
                                        "Inc., CC BY 4.0",
                             "_url": "https://github.com/Clear-Bible",
                             "_note": "Derived extract; SDBH fields excluded "
                                      "as they are permission-based, not "
                                      "openly licensed."}) + "\n")
        for ref in sorted(data):
            for c in data[ref]:
                fh.write(json.dumps({"ref": ref, **c}, ensure_ascii=False)
                         + "\n")
                n += 1
    mb = EXTRACT.stat().st_size / 1e6
    print(f"wrote {EXTRACT}  ({n:,} clauses, {mb:.2f} MB gzipped)")
    return 0


def show(ref):
    """One verse, pretty-printed, MACULA structure with our layers merged.

    Parens and indentation, or JSON with standard pretty printing, show the
    sentence broken down in one clean statement.
    """
    for f in sorted(MAC.rglob("*.xml")):
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for s in root.iter("sentence"):
            ws = _words(s)
            if not ws or _ref(ws[0].get("ref") or "") != ref:
                continue
            parts = [compact(c) for c in list(s) if c.tag == "wg"]
            body = parts[0] if len(parts) == 1 else parts
            out = {"ref": ref, "structure": "MACULA, CC BY 4.0",
                   "clauses": body if isinstance(body, list) else [body]}
            _ours(ref, out)
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0
    print(f"{ref} not loaded — is its chapter in data/raw/macula?")
    return 1


def _ours(ref, out):
    """Attach the layers MACULA has no concept of, labelled as ours."""
    try:
        from markers import corpus                                # noqa: E402
        from acts import act_of, status_of, quoted_verses, eng, _mood
    except ImportError:
        return
    ws = [r for r in corpus() if r[0] == ref]
    if not ws:
        return
    quoted = eng(ref) in quoted_verses()
    acts, prev = [], 0
    for i, w in enumerate(ws):
        if not _mood(w):
            continue
        pre = ws[prev:i]
        a = act_of(w, pre)
        prev = i + 1
        if a:
            acts.append({"verb": w[3].strip(), "act": a,
                         "status": ("attributed" if a == "command" and quoted
                                    else status_of(w, pre, quoted))})
    if acts:
        out["ours"] = {"note": "not in MACULA — derived here from verb mood "
                               "and quotation spans",
                       "speech_acts": acts,
                       "inside_a_quotation": quoted}


def main() -> int:
    if "--extract" in sys.argv:
        return extract()
    if "--sentence" in sys.argv:
        i = sys.argv.index("--sentence")
        if i + 1 >= len(sys.argv):
            print("--sentence needs a reference, e.g. Gen.1.2")
            return 1
        return show(sys.argv[i + 1])
    data = load()
    print("MACULA Hebrew and Greek Linguistic Datasets, Clear Bible, CC BY 4.0")
    print("https://github.com/Clear-Bible/macula-hebrew  /  macula-greek")
    print()
    print(f"verses loaded from disk: {len(data):,}")
    print(f"clauses:                 {sum(len(v) for v in data.values()):,}")
    vl = sum(1 for v in data.values() for c in v if c["verbless"])
    print(f"  of which verbless:     {vl:,}")
    rules = collections.Counter(c["rule"] for v in data.values() for c in v)
    print()
    print("the commonest clause rules — the constituent order, stated:")
    for k, n in rules.most_common(10):
        print(f"   {k:16}{n:>6,}")
    rels = collections.Counter(p["rel"] for v in data.values() for c in v
                               for p in c["parts"] if p["rel"])
    print()
    print("relations named on constituents:")
    for k, n in rels.most_common(8):
        print(f"   {k:16}{n:>6,}")

    if "--compare" in sys.argv:
        compare(data)
    return 0


def compare(data):
    """MACULA against our derivation, clause for clause, on the stress set."""
    from markers import corpus                                   # noqa: E402
    from tuples import clauses_by_accent                         # noqa: E402
    rows = [r for r in corpus()]
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault(r[0], []).append(r)

    print()
    print("OURS AGAINST MACULA — clause counts on the stress set")
    print(f"{'verse':13}{'words':>6}{'ours':>6}{'macula':>8}{'verbless':>10}"
          f"   agreement")
    tests = ["Gen.1.1", "Gen.1.2", "Est.8.9", "Est.3.12", "Jer.34.17",
             "1Ch.22.19", "Jos.8.33", "Jon.1.1", "Psa.23.1"]
    for ref in tests:
        ws = by.get(ref)
        m = data.get(ref)
        if not ws or not m:
            print(f"  {ref:11}{'—':>6}   not loaded")
            continue
        ours = clauses_by_accent(ws, ref.split(".")[0])
        vl = sum(1 for c in m if c["verbless"])
        agree = "same" if len(ours) == len(m) else (
            f"ours {'+' if len(ours) > len(m) else '−'}"
            f"{abs(len(ours)-len(m))}")
        print(f"  {ref:11}{len(ws):>6}{len(ours):>6}{len(m):>8}{vl:>10}"
              f"   {agree}")


if __name__ == "__main__":
    raise SystemExit(main())
