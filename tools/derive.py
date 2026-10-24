"""Deterministic derivation of the legacy graph's simple relations.

2026-09-05: keep pushing on the simple relationships in the legacy graph and
develop deterministic functions to derive them, focusing on simple concept to
simple concept first and then building up, being careful not to overfit.

The legacy graph holds 15,023 relations that were **reasoned out** — read by a
model, verse by verse, at real cost. The new graph holds 143,319 clause edges
that were **computed** from syntax for free. The question this tool asks is the
only one that matters about that pair:

    how much of what was reasoned out can be recomputed?

Whatever a function can recompute never has to be paid for again. Whatever it
cannot is where the reasoning actually earned its money, and that residue is
the thing worth keeping as a change set.

## Simple concept to simple concept

That scoping is the right cut. Of the 15,023, **5,224 join two simple
entities** — person, place, group, object, creature, event, title, covenant,
observance. The other 9,799 have a `text` or `passage` at one end, which is the
verse-contains-word shape the project already knows is an index rather than a
claim. Those are out of scope here by construction, not by convenience.

## The four-gate funnel, because one number hides the answer

A single recall figure tells you nothing about what to fix. Every legacy
relation is scored through four gates instead, and they fail for unrelated
reasons:

    1. verse parsed     is the ref in the structural data at all?   coverage
    2. both ends named  are BOTH entities spelled out in that verse?
                                                              REACHABILITY
    3. pair on an edge  does a clause edge join them?    parsing / elision
    4. type agrees      does the verb map to this relation?    vocabulary

**Gate 2 is the ceiling and most of the loss.** A relation the legacy graph
inferred across a passage, or one where the text names an end by description --
1Sam 17:50 calls Goliath *the Philistine* -- cannot be reached by any rule over
a single verse. Scoring those as rule failures measures the wrong thing, so
every per-type line also reports recovery **against gate 2** rather than against
the total.

Held-out, after the coordination and apposition work of 2026-09-05:

    1. verse parsed   92%      3. pair on an edge  15%
    2. both ends named 27%     4. type agrees       8%   (30% of reachable)

    father_of         48% reachable, 38% recovered -- 79% of its ceiling

## Not overfitting: the split, and the rule that governs rules

The lesson is already on the board. Tuning against 14 verses took node
extraction from 36% to 1% on those verses and left 22-25% everywhere else. The
number moved and the method did not.

So two guards, and the second is the one that actually bites:

**The books are split.** An md5 of the book code decides: even is DERIVE, odd
is HELDOUT. Deterministic, unpickable, and it spreads across genre rather than
handing me the narrative books to tune on. Every figure below is reported
twice, and **the gap between the two columns is the finding** — not the
left-hand number.

**No rule may name a proper noun.** A rule keyed to Abraham is not a function,
it is a memory of Abraham, and it will report a high score for having memorised
the answer. `--audit-rules` checks the rule tables against the entity list and
fails if any rule matches a name in the corpus.

## The join, stated honestly

Endpoints are matched **by name**, not by resolved identity, so this measures
*relation derivation with identity supplied* — not end-to-end. An earlier
version restricted the name lookup to each entity's own `refs` and collapsed
gate 3 to 0-1%, which looked like a structural failure and was not: a legacy
entity's `refs` are a representative attestation rather than an occurrence
index, so `cain` lists Gen 4:1 alone while the killing he is party to is at
Gen 4:8.

    python tools/derive.py                 # the funnel, derive vs held-out
    python tools/derive.py --audit-rules   # no rule names a proper noun
    python tools/derive.py --misses father_of
"""
from __future__ import annotations

import collections
import glob
import gzip
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

# The legacy graph and MACULA abbreviate books differently, and the last time
# that went unnoticed a scoring pass returned 0 of 15,022 and looked exactly
# like a coverage problem. The map is explicit and `_check_books` fails loudly
# rather than letting a silent zero pass for a finding.
BOOK = {
    "Gen": "Gen", "Exod": "Exo", "Lev": "Lev", "Num": "Num", "Deut": "Deu",
    "Josh": "Jos", "Judg": "Jdg", "Ruth": "Rut", "1Sam": "1Sa", "2Sam": "2Sa",
    "1Kgs": "1Ki", "2Kgs": "2Ki", "1Chr": "1Ch", "2Chr": "2Ch", "Ezra": "Ezr",
    "Neh": "Neh", "Esth": "Est", "Job": "Job", "Ps": "Psa", "Prov": "Pro",
    "Eccl": "Ecc", "Song": "Sng", "Isa": "Isa", "Jer": "Jer", "Lam": "Lam",
    "Ezek": "Ezk", "Dan": "Dan", "Hos": "Hos", "Joel": "Jol", "Amos": "Amo",
    "Obad": "Oba", "Jonah": "Jon", "Mic": "Mic", "Nah": "Nam", "Hab": "Hab",
    "Zeph": "Zep", "Hag": "Hag", "Zech": "Zec", "Mal": "Mal",
    "Matt": "Mat", "Mark": "Mrk", "Luke": "Luk", "John": "Jhn", "Acts": "Act",
    "Rom": "Rom", "1Cor": "1Co", "2Cor": "2Co", "Gal": "Gal", "Eph": "Eph",
    "Phil": "Php", "Col": "Col", "1Thess": "1Th", "2Thess": "2Th",
    "1Tim": "1Ti", "2Tim": "2Ti", "Titus": "Tit", "Phlm": "Phm", "Heb": "Heb",
    "Jas": "Jas", "1Pet": "1Pe", "2Pet": "2Pe", "1John": "1Jn", "2John": "2Jn",
    "3John": "3Jn", "Jude": "Jud", "Rev": "Rev",
}
REF = re.compile(r"^([0-9]?[A-Za-z]+)\s+(\d+):(\d+)")

SIMPLE = {"person", "place", "group", "object", "creature", "being", "event",
          "title", "observance", "covenant"}

# ---------------------------------------------------------------- the rules
#
# Every entry is a VERB STEM or a PREPOSITION. Not one names a person, a place
# or a book -- `--audit-rules` enforces it, because a rule that names Abraham
# scores well by remembering rather than by working.

# A transitive clause: subject -verb-> object becomes src -relation-> dst.
DIRECT = {
    "killed": "killed", "slew": "killed", "smote": "killed", "struck": "killed",
    "gave": "gave", "give": "gave", "granted": "gave",
    "took": "took", "take": "took", "seized": "took",
    "sent": "sent", "send": "sent",
    "made": "made", "make": "made", "built": "built",
    "led": "led", "brought": "led", "carried": "carried",
    "blessed": "blessed", "cursed": "cursed",
    "charged": "charged", "commanded": "charged",
    "anointed": "anointed", "appointed": "appointed",
    "healed": "healed", "buried": "buried_at",
    "conquered": "conquered", "defeated": "conquered",
    "repaired": "repaired", "loved": "loved", "hated": "hated",
    "saw": "saw", "heard": "heard", "asked": "besought",
    "besought": "besought", "entreated": "besought",
    "rebuked": "rebuked", "deceived": "deceived", "betrayed": "betrayed",
    "wrote": "wrote_to", "baptized": "baptized",
    # `--suggest` found this one, 11 occurrences in the derive books. `called`
    # is NOT a verb that determines its type -- the same scan shows it under
    # traveled_to (4) and mother_of (3), which is the annotator reading past
    # the verb to what the clause means. `named` is the literal reading and
    # the plurality, so it is what a floor rule may claim.
    "called": "named",
}

# A verb whose relation lands on a PREPOSITIONAL adjunct rather than the
# object: "went to X", "dwelt at X". (verb stem, preposition) -> relation.
ADJUNCT = {
    ("went", "to"): "traveled_to", ("came", "to"): "traveled_to",
    ("returned", "to"): "traveled_to", ("journeyed", "to"): "traveled_to",
    ("fled", "to"): "traveled_to", ("wentUp", "to"): "traveled_to",
    ("wentDown", "to"): "traveled_to", ("wentOut", "to"): "traveled_to",
    ("brought", "to"): "traveled_to", ("came", "into"): "traveled_to",
    ("dwelt", "in"): "dwelt_at", ("dwelt", "at"): "dwelt_at",
    ("settled", "in"): "dwelt_at", ("settled", "at"): "dwelt_at",
    ("lived", "in"): "dwelt_at", ("sojourned", "in"): "dwelt_at",
    ("buried", "in"): "buried_at", ("buried", "at"): "buried_at",
    ("died", "in"): "died_at", ("died", "at"): "died_at",
    ("born", "in"): "born_at", ("born", "at"): "born_at",
    ("reigned", "over"): "reigned_over", ("ruled", "over"): "reigned_over",
    ("reigned", "in"): "ruled_from", ("ruled", "in"): "ruled_from",
    # from `--suggest`: the accession formula is `becameKing`, not `reigned`,
    # and the preposition alone separates ruling a people from ruling from a
    # city. 11 and 9 occurrences in the derive books, and the table had neither.
    ("becameKing", "over"): "reigned_over",
    ("becameKing", "in"): "ruled_from",
    ("went", "adjunct"): "traveled_to",
    ("said", "to"): "told", ("spoke", "to"): "told", ("says", "to"): "told",
    ("told", "to"): "told", ("answered", "to"): "answered",
    ("sent", "to"): "sent", ("gave", "to"): "gave",
    ("fought", "against"): "fought", ("roseUp", "against"): "fought",
    ("warred", "against"): "fought",
}

# Begetting is its own family, because the text states it in three shapes and
# only one of them is a plain transitive clause.
BEGET_M = {"fathered", "begat", "begot", "begets"}
BEGET_F = {"bore", "bare", "birthed"}
# Words that stand in for the child until a naming clause supplies the name.
CHILD = {"son", "sons", "daughter", "daughters", "child", "children"}
PRONOUN = {"him", "her", "them", "he", "she", "they", "it", "his", "hers",
           "their", "me", "you", "us", "thee", "thou", "ye", "himself",
           "herself", "themselves", "who", "whom", "which", "that"}


def ref(s):
    """'1Chr 27:33' -> '1Ch.27.33'; None when the book is unknown."""
    m = REF.match((s or "").strip())
    if not m:
        return None
    b = BOOK.get(m.group(1))
    return f"{b}.{int(m.group(2))}.{int(m.group(3))}" if b else None


def held_out(book):
    """Odd md5 -> held out. Deterministic and unpickable by me."""
    return int(hashlib.md5(book.encode()).hexdigest(), 16) % 2 == 1


def slug(name):
    """Spelling-normalised form, because the two graphs transliterate apart.

    The legacy graph spells names the KJV's way and MACULA spells them its own,
    so a third of legacy person names have no exact match in the node
    vocabulary: Ahijah/Ahiah, Elijah/Eliah, Urijah/Uriah, Alphaeus/Alpheus,
    Aeneas/Eneas. That is not an absence, it is an orthography, and leaving it
    unhandled understates every gate below it.

    **The aggressive version of this was a trap and is worth recording.** A
    normaliser that also collapsed vowel runs and mapped ch/ph/sh matched far
    more -- and merged Esau with Joshua with Jesse with Asa, and Judah with
    Adah. It would have raised the score by destroying the measurement, which
    is the exact failure this project keeps meeting: a confident wrong answer
    that no count-based check can see.

    What survives is only what cannot collide: intervocalic j->i, ae->e,
    doubled letters collapsed. Across 1,612 named people that produces 13
    merges and every one is a real spelling pair. `--audit-names` prints them,
    so the cost of this function stays visible rather than assumed.
    """
    s = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    s = re.sub(r"(?<=[aeiou])j(?=[aeiou])", "i", s)
    s = s.replace("ae", "e")
    return re.sub(r"(.)\1+", r"\1", s)


# ------------------------------------------------------------------- inputs

def legacy():
    ents = {}
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            ents[e["id"]] = e
    rows = []
    for f in sorted(glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl"))):
        for line in pathlib.Path(f).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return ents, rows


def structure():
    """verse -> [edge]."""
    byverse = collections.defaultdict(list)
    for line in gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt",
                          encoding="utf-8"):
        e = json.loads(line)
        if "_source" in e:
            continue
        byverse[e["ref"]].append(e)
    return byverse


def _check_books(rows, byverse):
    """A silent zero is the failure mode; refuse to report one as a finding."""
    seen, mapped, landed = set(), 0, 0
    for r in rows:
        for x in r.get("refs", []):
            m = REF.match(x.strip())
            if m:
                seen.add(m.group(1))
            v = ref(x)
            if v:
                mapped += 1
                if v in byverse:
                    landed += 1
    bad = sorted(b for b in seen if b not in BOOK)
    print("BOOK MAP SELF-CHECK")
    print(f"  legacy book codes seen     {len(seen):>7}")
    print(f"  unmapped                   {len(bad):>7}   {bad}")
    print(f"  refs mapped                {mapped:>7,}")
    print(f"  landing on a parsed verse  {landed:>7,}   "
          f"{100*landed//max(mapped,1)}%")
    if bad or landed < mapped // 4:
        print("\n  ABORT: the map is wrong. Any score below would be an "
              "artefact of the abbreviations, not a measurement.")
        return False
    print()
    return True


# ---------------------------------------------------------------- the derive

def _members(edges):
    """Coordination group node -> its member nodes."""
    g = collections.defaultdict(list)
    for e in edges:
        if e.get("type") == "member" and e.get("src") and e.get("dst"):
            g[e["src"]].append(e["dst"])
    return g


def _slugs(edges):
    """Every node spelled out in this verse, construct chains included."""
    out = set()
    for e in edges:
        for k in ("src", "dst"):
            if isinstance(e.get(k), str):
                out.add(slug(e[k].split("#")[-1]))
        r = e.get("dst_relation") or {}
        for k in ("src", "dst"):
            if isinstance(r.get(k), str):
                out.add(slug(r[k].split("#")[-1]))
    return out


def _names(edges):
    """A naming clause supplies the name a child word stands in for."""
    out = []
    for e in edges:
        if (e.get("type") or "").lower() in ("called", "named") and e.get("dst"):
            out.append(e["dst"])
    return out


def _expand(node, groups):
    return groups.get(node, [node]) if node else []


def _roster(edges, groups, got):
    """The genealogical roster, which is a verbless clause and not an event.

    1Chr 23:21 -- "The sons of Merari; Mahli, and Mushi" -- comes out of the
    parse as a construct chain standing as the subject of a verbless clause:

        sonsOfMerari  references  (sons -of-> merari)
        sonsOfMerari  is          mahli

    So the relation is carried by the CONSTRUCT plus the copula, with no verb
    anywhere in it. Every rule above this one looks for a verb and therefore
    could not see a single line of the roster literature -- 1 Chronicles 1-9,
    Genesis 10 and 36, Numbers 26 -- which is where most of the corpus's
    paternity is actually stated. The shape is general: a kin term in construct
    with a name, predicated of one or more other names.
    """
    for e in edges:
        rel = e.get("dst_relation")
        if not rel or (rel.get("type") or "").lower() != "of":
            continue
        noun = slug((rel.get("src") or "").split("#")[-1])
        if noun not in RELATIONAL:
            continue
        parent = rel.get("dst")
        if not parent or slug(parent.split("#")[-1]) in PRONOUN:
            continue
        # The copula is not always spelled `is`. 1Chr 2:7 -- "the sons of
        # Carmi; Achar" -- links with `in`, and requiring `is` reached only 196
        # of the 807 kin-construct chains in the parse. What actually
        # identifies the child link is the ABSENCE of an event: a verbless
        # clause has no verb and scopes over nothing, so any edge off the
        # construct that is not an event adjunct is the predicate.
        for f in edges:
            if f.get("src") != e.get("src") or f is e:
                continue
            if f.get("scopes_over") or f.get("verb"):
                continue
            kids = [c for c in _expand(f.get("dst"), groups)
                    if c and c != parent]
            for child in kids:
                _relate(noun, parent, child, got)
            # BUILDING UP: a roster states siblinghood without saying the word.
            # "The sons of Jesse; Eliab, and Abinadab, and Shammah" names three
            # brothers, and every rule up to here only read it as three
            # fatherhoods. This is composition over what was just derived
            # rather than a new reading of the text, which is why it needs no
            # new vocabulary and cannot disagree with the verse.
            if RELATIONAL.get(noun, ("", ""))[1] == "to_head" and len(kids) > 1:
                for i, a in enumerate(kids):
                    for b in kids[i + 1:]:
                        got.add((a, "sibling_of", b))
                        got.add((b, "sibling_of", a))


# A RELATIONAL NOUN in construct states a relation with no verb at all: "the
# sons of Merari", "Joab the brother of Abishai", "Doeg the servant of Saul".
# The kin case was written first and the rest of the table is the same shape --
# which is why servant_of, sibling_of, spouse_of and companion_of all sat at 0%
# recovery with reachability to spare.
#
# Orientation matters and is not guessable from the noun's meaning alone:
#
#   to_head     the construct's object is the SOURCE   "the sons of X" -> X ..> head
#   from_head   the head is the source                 "Y the servant of X" -> Y ..> X
#   symmetric   either direction is the same claim     "Y the brother of X"
RELATIONAL = {
    "son": ("father_of", "to_head"), "sons": ("father_of", "to_head"),
    "child": ("father_of", "to_head"), "children": ("father_of", "to_head"),
    "daughter": ("father_of", "to_head"),
    "daughters": ("father_of", "to_head"),
    "father": ("father_of", "from_head"),
    "mother": ("mother_of", "from_head"),
    "brother": ("sibling_of", "symmetric"),
    "brothers": ("sibling_of", "symmetric"),
    "brethren": ("sibling_of", "symmetric"),
    "sister": ("sibling_of", "symmetric"),
    "wife": ("spouse_of", "symmetric"), "wives": ("spouse_of", "symmetric"),
    "husband": ("spouse_of", "symmetric"),
    "servant": ("servant_of", "from_head"),
    "servants": ("servant_of", "from_head"),
    "companion": ("companion_of", "symmetric"),
    "friend": ("companion_of", "symmetric"),
    "counselor": ("counselor_of", "from_head"),
    "counsellor": ("counselor_of", "from_head"),
}


_GENDER = None


def gender_of(node):
    """Grammatical gender for a name, pooled across all its occurrences.

    MACULA marks gender on only about a fifth of proper-noun occurrences --
    Abraham is masculine on 28 of 122, Sarah feminine on 2 of 27, Merari never
    -- but where it is marked it is right. So pool by spelling and use it when
    any occurrence states it, unanimously; conflicting marks decide nothing.
    """
    global _GENDER
    if _GENDER is None:
        seen = collections.defaultdict(set)
        for line in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt",
                              encoding="utf-8"):
            n = json.loads(line)
            if n.get("proper") and n.get("gender") in ("masculine", "feminine"):
                seen[slug(n.get("local"))].add(n["gender"])
        _GENDER = {k: v.pop() for k, v in seen.items() if len(v) == 1}
    return _GENDER.get(slug((node or "").split("#")[-1]))


def _relate(rel_noun, parent, head, got, idiom=False):
    """Emit the relation a construct states, in the right direction.

    `idiom=True` marks the PATRONYMIC -- "Jehiel the son of Hachmoni" -- where
    Hebrew usage makes the named party the father, and the graph may say so.

    Everything else descent-shaped defers. "The sons of X" says nothing about
    which parent X is, and reading it as fatherhood produced 34 of the 405
    disagreements the first precision run found: Genesis 35:23-26 lists "the
    sons of Leah", "the sons of Bilhah", "the sons of Zilpah", and the rule
    called every one of those women a father.

    The fix is not to guess gender, it is to **claim less**. Where the
    morphology settles it, say father or mother; where it does not, say
    `parent_of` -- true, weaker, and refinable later. That is the unresolved
    node applied to a relation, and Principle 42's asymmetry again: a claim
    that is too weak can be sharpened, and one that is wrong has to be found
    first.
    """
    spec = RELATIONAL.get(rel_noun)
    if not spec or not parent or not head or parent == head:
        return
    name, orient = spec
    if orient == "to_head":
        if name == "father_of":
            g = gender_of(parent)
            if g == "feminine":
                # the idiom is not absolute: "Joab the son of Zeruiah" is a
                # MATRONYMIC, and Zeruiah is David's sister. Where the
                # morphology says feminine it overrides the default in both
                # the idiom and the roster case.
                name = "mother_of"
            elif g != "masculine" and not idiom:
                name = "parent_of"
        got.add((parent, name, head))
    elif orient == "from_head":
        got.add((head, name, parent))
    else:
        got.add((head, name, parent))
        got.add((parent, name, head))


_GENTILIC = None


def gentilics():
    """Node ids MACULA types as a gentilic -- a people-group word.

    `member_of` was the second largest simple type at 311 held-out relations
    and recovered NOTHING, because none of the day's rules had a shape for
    "Saul a Benjamite". It turns out not to need one: MACULA marks the
    gentilic in the morphology (`type="gentilic"`, 1,785 words), and the
    apposition edges added earlier today already point straight at them --
    `abram -> hebrew`, `ephron -> hittite`, `laban -> aramean`.

    So the rule is a join between two things that already existed, which is
    the same shape as the roster and possessive wins: the structure was there
    and nothing was reading it.
    """
    global _GENTILIC
    if _GENTILIC is None:
        _GENTILIC = set()
        for line in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt",
                              encoding="utf-8"):
            d = json.loads(line)
            if (d.get("type") or "").lower() == "gentilic":
                _GENTILIC.add(d["id"])
    return _GENTILIC


def _gentilic_membership(edges, got):
    """"Uriah the Hittite" -- apposition to a gentilic states membership."""
    gent = gentilics()
    for e in edges:
        if e.get("type") != "apposition":
            continue
        src, dst = e.get("src"), e.get("dst")
        if src and isinstance(dst, str) and dst in gent and src != dst:
            got.add((src, "member_of", dst))


def _rel_noun(n):
    """RELATIONAL lookup tolerant of the possessive 's the gloss carries."""
    n = slug(n)
    if n in RELATIONAL:
        return n
    return n[:-1] if n.endswith("s") and n[:-1] in RELATIONAL else None


def _possessors(edges):
    """Resolve "his"/"her" inside a phrase to the nearest clause subject.

    The node builder now records a possessive suffix rather than swallowing it,
    but deliberately leaves the possessor unresolved, because resolving it is a
    verse-level question. This is that pass, and it is the SAME rule the elision
    work settled on in August -- the nearest preceding clause subject, never the
    nearest noun -- for the same reason: a candidate set of clause subjects is
    narrow enough to be right, and a candidate set of every noun is not.

    Returns node -> (possessor node, relational noun).
    """
    out, subjects = {}, []
    for e in edges:
        if e.get("type") == "possessed_by" and e.get("unresolved_possessor"):
            noun = _rel_noun(e.get("noun") or "")
            cand = [s for s in subjects
                    if slug(s.split("#")[-1]) not in PRONOUN]
            if noun and cand:
                out[e["src"]] = (cand[-1], noun)
            continue
        s = e.get("src")
        if s and not e.get("scopes_over"):
            subjects.append(s)
    return out


def _possessive_relations(edges, got):
    """The two shapes a possessed relational noun states a relation in.

    Both were unreachable an hour ago and are the last of the day's blocked
    `father_of` and `mother_of` misses:

        "Ammizabad HIS son"                 1Chr 27:6
          ammizabad -apposition-> son, son possessed by 3ms -> Benaiah
          => father_of(Benaiah, Ammizabad)

        "HIS mother's name was Jecoliah"    2Chr 26:3, and the whole regnal
          nameOfMotherS references (name of motherS)   formula in Kings and
          nameOfMotherS -of-> jecoliah                 Chronicles
          motherS possessed by 3ms -> Uzziah
          => mother_of(Jecoliah, Uzziah)

    The second is worth noticing as a shape: **a naming clause about a relation
    states the relation.** "The name of X's mother is Y" asserts motherhood
    without a verb and without ever putting the two people in one clause.
    """
    poss = _possessors(edges)
    if not poss:
        return

    # "Ammizabad his son"
    for e in edges:
        if e.get("type") != "apposition":
            continue
        head, tgt = e.get("src"), e.get("dst")
        if head and isinstance(tgt, str) and tgt in poss:
            owner, noun = poss[tgt]
            if owner != head:
                # "Ammizabad HIS son" is the patronymic with a pronoun for the
                # father, so the same idiom applies
                _relate(noun, owner, head, got, idiom=True)

    # "his mother's name was Jecoliah"
    for e in edges:
        rel = e.get("dst_relation")
        if not rel or (rel.get("type") or "").lower() != "of":
            continue
        if slug((rel.get("src") or "").split("#")[-1]) != "name":
            continue
        inner = rel.get("dst")
        if inner not in poss:
            continue
        owner, noun = poss[inner]
        for f in edges:
            if f.get("src") != e.get("src") or f is e:
                continue
            if f.get("scopes_over") or f.get("verb"):
                continue
            named = f.get("dst")
            if isinstance(named, str) and named != owner:
                _relate(noun, owner, named, got)


def _appositive_patronymic(edges, got):
    """"Jehiel the son of Hachmoni" -- paternity carried by apposition.

    After the roster rule landed, this was the single commonest remaining shape
    in the `father_of` misses: "Ahio the son of Abinadab", "Elhanan the son of
    Jair", "Joram the son of Toi". It is not a clause at all -- no verb, no
    copula, just a name re-described by a construct chain -- and it only became
    derivable when the node builder started emitting apposition edges instead
    of collapsing the whole phrase into one node.

    Deliberately NOT handled: "Ammizabad his son", where the construct's parent
    is a pronoun. That needs an antecedent from outside the phrase, and
    inventing one here would be the same mistake as filling an elided subject
    with a guess.
    """
    for e in edges:
        if e.get("type") != "apposition":
            continue
        head, tgt = e.get("src"), e.get("dst")
        if not head or not isinstance(tgt, str):
            continue
        for f in edges:
            if f.get("src") != tgt:
                continue
            rel = f.get("dst_relation")
            if not rel or (rel.get("type") or "").lower() != "of":
                continue
            noun = slug((rel.get("src") or "").split("#")[-1])
            if noun not in RELATIONAL:
                continue
            parent = rel.get("dst")
            if parent and parent != head and \
                    slug(parent.split("#")[-1]) not in PRONOUN:
                # the patronymic is idiom: "X the son of Y" names the father
                _relate(noun, parent, head, got, idiom=True)


def derived(edges):
    """Every relation the rules can compute from one verse's clause edges.

    Returns a set of (src_node, relation, dst_node). Nothing here consults the
    legacy graph -- that comparison happens afterwards, so the rules cannot
    quietly read the answer.
    """
    groups = _members(edges)
    named = _names(edges)
    people_order = [e["dst"] for e in edges if e.get("dst")]
    got = set()
    _roster(edges, groups, got)
    _appositive_patronymic(edges, got)
    _possessive_relations(edges, got)
    _gentilic_membership(edges, got)

    for e in edges:
        verb = (e.get("verb") or e.get("type") or "")
        stem = verb.split("_")[0]
        src, dst = e.get("src"), e.get("dst")

        # --- begetting, the three shapes -------------------------------
        if stem in BEGET_M or stem in BEGET_F:
            rel = "father_of" if stem in BEGET_M else "mother_of"
            kids = []
            if dst and not e.get("scopes_over"):
                kids = _expand(dst, groups)
            # "she bore a son" -- the child word is a placeholder, and the
            # naming clause in the same verse supplies who it was.
            kids = [k for k in kids
                    if slug(k.split("#")[-1]) not in CHILD] or \
                   [n for n in named
                    if slug(n.split("#")[-1]) not in CHILD and
                    slug(n.split("#")[-1]) != "name"]
            for k in kids:
                if src and k != src:
                    got.add((src, rel, k))
            continue

        # "X bore Y TO Z" -- the adjunct names the other parent. General, and
        # it is how the text states paternity in the birth notices.
        if e.get("scopes_over") and (e.get("verb") or "") in BEGET_F \
                and (e.get("type") or "").lower() == "to" and dst:
            for m in (mm for ee in edges if (ee.get("verb") or "") in BEGET_F
                      or (ee.get("type") or "") in BEGET_F
                      for mm in _expand(ee.get("dst"), groups)):
                if slug(m.split("#")[-1]) not in CHILD and m != dst:
                    got.add((dst, "father_of", m))
            for n in named:
                if slug(n.split("#")[-1]) not in ("name",) | CHILD:
                    got.add((dst, "father_of", n))
            continue

        # --- a verb landing on a prepositional adjunct -----------------
        if e.get("scopes_over"):
            rel = ADJUNCT.get((e.get("verb") or "", (e.get("type") or "").lower()))
            if rel and src and dst:
                for s in _expand(src, groups):
                    for d in _expand(dst, groups):
                        if s != d:
                            got.add((s, rel, d))
            continue

        # --- a plain transitive clause ---------------------------------
        rel = DIRECT.get(stem)
        if rel and src and dst:
            for s in _expand(src, groups):
                for d in _expand(dst, groups):
                    if s == d:
                        continue
                    # a pronoun object carries no identity of its own; the
                    # nearest earlier non-subject node in the verse is what it
                    # stands for, which is the only resolution the clause
                    # structure licenses without leaving the verse.
                    if slug(d.split("#")[-1]) in PRONOUN:
                        prior = [p for p in people_order
                                 if p != s and
                                 slug(p.split("#")[-1]) not in PRONOUN]
                        if not prior:
                            continue
                        d = prior[-1]
                    got.add((s, rel, d))

    # A COORDINATION DISTRIBUTES, wherever it ends up. The verb rules expand
    # groups inline, but the apposition, roster and possessive rules added
    # later did not, so "the Philistines killed Jonathan, and Abinadab, and
    # Malki-Shua" reached only whichever member a given rule happened to hold.
    # Doing it once at the end covers every rule and cannot be forgotten by the
    # next one.
    #
    # **Only coordination.** A composite's members each genuinely participate
    # in whatever the composite does. A CONSTRUCT does not work that way -- the
    # sons of Saul are not Saul -- and expanding one would turn "killed the
    # sons of Saul" into killing Saul. Measured on the legacy relations, the
    # unreachable pairs split 144 coordination / 243 construct / 680 merely
    # sharing a node, and only the first third is safe to take.
    for a, rel, b in list(got):
        for s in _expand(a, groups):
            for d in _expand(b, groups):
                if s != d:
                    got.add((s, rel, d))
    return got


# ------------------------------------------------------------------- scoring

def surface(e):
    """Every spelling the legacy graph offers for an entity."""
    out = {slug(e["name"])}
    for a in e.get("aka", []) or []:
        out.add(slug(a))
    # `enoch_son_of_cain` -- the id is disambiguated, the name inside it is not
    out.add(slug(e["id"].split("_son_of_")[0].split("_of_")[0]))
    return {s for s in out if s}


def induce(ents, rows, byverse):
    """Learn the name mapping from GRAPH PLACEMENT, not from string similarity.

    2026-09-05: do the aliases in the existing graph help? If not, graph
    placement should help build a mapping. The aliases help a
    little -- 186 of 1,681 people carry one, lifting name reach from 70% to
    72% -- and placement is the better instrument, because it does not care how
    a name is spelled at all.

    The argument: where a rule derives a relation of the RIGHT TYPE at the
    right verse, and one endpoint already matches the legacy relation by name,
    the other endpoint is standing in the position the legacy graph says the
    other entity occupies. Two things in the same position in the same clause
    of the same verse are the same thing. That is evidence of identity from
    structure, and it is exactly how a person reads an unfamiliar spelling.

    **Induced on the DERIVE books only and applied to HELD OUT.** Learning a
    mapping from agreement and then scoring agreement with it would be
    circular, and the split is what stops that: the mapping never sees the
    books it is scored on.

    A proposal is accepted only with at least two independent verses behind it
    and no rival carrying comparable support -- a single co-occurrence is a
    coincidence, and a contested one is a guess.
    """
    prop = collections.defaultdict(collections.Counter)
    cache = {}
    for r in rows:
        s, d = ents.get(r["src"]), ents.get(r["dst"])
        if not s or not d or s["type"] not in SIMPLE or d["type"] not in SIMPLE:
            continue
        book = (REF.match(r["refs"][0].strip()).group(1)
                if r.get("refs") and REF.match(r["refs"][0].strip()) else "")
        if held_out(book):
            continue
        sn, dn = surface(s), surface(d)
        for x in r.get("refs", []):
            v = ref(x)
            if not v or v not in byverse:
                continue
            if v not in cache:
                cache[v] = derived(byverse[v])
            # THE POSITION MUST HAVE EXACTLY ONE FILLER. The first version of
            # this proposed `dedan -> sheba`, `haran -> abram`, `abida ->
            # ephah` -- all siblings, none aliases. In "the sons of X: A, B,
            # C" every child occupies the SAME position, so a match on the
            # parent identifies nothing about which child is which. Placement
            # is evidence of identity only where the slot is single-valued;
            # where it is a list, it is evidence of being in the same list.
            # Count the fillers BEFORE discarding the one that already
            # matched, or a two-name roster looks single-valued: "sons of
            # Jokshan; Sheba, and Dedan" with `jokshan father_of dedan` leaves
            # Sheba alone in the slot and proposes dedan -> sheba. The slot
            # held two names, so it is evidence of nothing.
            fwd, rev = set(), set()
            for (a, rel, b) in cache[v]:
                if rel != r["type"]:
                    continue
                sa, sb = slug(a.split("#")[-1]), slug(b.split("#")[-1])
                if sa in sn and sb:
                    fwd.add(sb)
                elif sb in dn and sa:
                    rev.add(sa)
            if len(fwd) == 1 and not (fwd & dn):
                prop[slug(d["name"])][next(iter(fwd))] += 1
            if len(rev) == 1 and not (rev & sn):
                prop[slug(s["name"])][next(iter(rev))] += 1

    out, contested = {}, 0
    for key, cands in prop.items():
        top = cands.most_common(2)
        if top[0][1] < 2:
            continue
        if len(top) > 1 and top[1][1] * 2 > top[0][1]:
            contested += 1
            continue
        out[key] = top[0][0]
    return out, len(prop), contested


def score(ents, rows, byverse, want=None, alias=None):
    """Score each legacy relation through the three gates.

    **The endpoints are matched by NAME, not by resolved identity.** An earlier
    version restricted the name lookup to the entity's own `refs`, which
    collapsed gate 2 to 0-1% and looked like a structural failure. It was not:
    a legacy entity's `refs` are a representative attestation, not an
    occurrence index -- `cain` lists Gen 4:1 alone, while the killing it is
    party to is at Gen 4:8. The lookup was empty nearly everywhere and the
    rules never got a chance to be wrong.

    Matching by name asks the question this tool is actually for: *does the
    verse contain an edge joining a node spelled like the source to a node
    spelled like the target, carrying the right relation?* That is relation
    derivation with identity supplied, which is the honest description of it.
    Same-name collisions inside a single verse are counted rather than hidden.
    """
    gate = collections.Counter()
    per = collections.defaultdict(collections.Counter)
    misses = collections.defaultdict(list)
    weaker = 0
    cache = {}

    for r in rows:
        s, d = ents.get(r["src"]), ents.get(r["dst"])
        if not s or not d:
            continue
        if s["type"] not in SIMPLE or d["type"] not in SIMPLE:
            continue
        typ = r["type"]
        if want and typ != want:
            continue
        book = (REF.match(r["refs"][0].strip()).group(1)
                if r.get("refs") and REF.match(r["refs"][0].strip()) else "")
        half = "heldout" if held_out(book) else "derive"
        gate[(half, "total")] += 1
        per[typ][(half, "total")] += 1

        sn, dn = surface(s), surface(d)
        if alias:
            sn = sn | {alias[x] for x in sn if x in alias}
            dn = dn | {alias[x] for x in dn if x in alias}
        hit_verse = hit_both = hit_pair = hit_type = False
        for x in r.get("refs", []):
            v = ref(x)
            if not v or v not in byverse:
                continue
            hit_verse = True
            edges = byverse[v]
            # Gate 1.5, and it is the one that separates two completely
            # different failures: BOTH endpoints spelled out in this verse, or
            # not. When they are not, no rule over this verse can ever produce
            # the relation -- the legacy graph inferred it across a passage, or
            # the text names one of them by description ("the Philistine" for
            # Goliath in 1Sam 17:50). That is not a rule to write.
            here = _slugs(edges)
            if (sn & here) and (dn & here):
                hit_both = True
            if v not in cache:
                cache[v] = derived(edges)
            for (a, rel, b) in cache[v]:
                sa, sb = slug(a.split("#")[-1]), slug(b.split("#")[-1])
                if sa in sn and sb in dn:
                    hit_pair = True
                    if rel == typ:
                        hit_type = True
                    elif rel == "parent_of" and typ in ("father_of",
                                                        "mother_of"):
                        # a deliberate under-claim where gender is unstated:
                        # true, and less specific than the legacy type. Counted
                        # as recovered and reported separately, because a
                        # weaker true answer is not the same as an exact one.
                        hit_type = True
                        weaker += 1
                elif sa in dn and sb in sn:
                    hit_pair = True
            if not hit_pair:
                # the pair may sit on an edge whose verb no rule maps -- that
                # is gate 3 failing, not gate 2, and the difference is the
                # whole point of separating them
                for e in edges:
                    a, b = e.get("src"), e.get("dst")
                    if not a or not isinstance(b, str):
                        continue
                    sa, sb = slug(a.split("#")[-1]), slug(b.split("#")[-1])
                    if (sa in sn and sb in dn) or (sa in dn and sb in sn):
                        hit_pair = True

        for k, ok in (("verse", hit_verse), ("both", hit_both),
                      ("pair", hit_pair), ("type", hit_type)):
            if ok:
                gate[(half, k)] += 1
                per[typ][(half, k)] += 1
        if not hit_type and len(misses[typ]) < 10:
            stage = ("no verse" if not hit_verse else
                     "not both named" if not hit_both else
                     "no pair" if not hit_pair else "wrong type")
            misses[typ].append((r["src"], typ, r["dst"],
                                r["refs"][0] if r.get("refs") else "", stage))
    return gate, per, misses, weaker


def suggest(ents, rows, byverse):
    """What the DERIVE books say the missing rules are.

    Hand-guessing the verb vocabulary is how `traveled_to` ended up at 1%: the
    table had ("went", "to") and the text says `wentUp`, `cameInto`, `broughtTo`
    and forty other things. The COORD fix earlier today worked because the rule
    names were SCANNED rather than guessed, and this is the same move applied to
    the relation vocabulary.

    Where a legacy relation's two endpoints sit on one clause edge and the type
    does not agree, the edge's (verb, preposition) is what that relation looks
    like in the text. Tallied over the derive books only, the frequent ones are
    the missing table entries -- and because held-out never contributes a
    suggestion, adding them and re-scoring stays an honest test rather than a
    fit.

    Reported, never written. A suggestion with two occurrences is noise, and
    deciding which are real is the judgement the table exists to record.
    """
    want = collections.defaultdict(collections.Counter)
    cache = {}
    for r in rows:
        s, d = ents.get(r["src"]), ents.get(r["dst"])
        if not s or not d or s["type"] not in SIMPLE or d["type"] not in SIMPLE:
            continue
        book = (REF.match(r["refs"][0].strip()).group(1)
                if r.get("refs") and REF.match(r["refs"][0].strip()) else "")
        if held_out(book):
            continue
        sn, dn = surface(s), surface(d)
        for x in r.get("refs", []):
            v = ref(x)
            if not v or v not in byverse:
                continue
            if v not in cache:
                cache[v] = derived(byverse[v])
            if any(rel == r["type"] and slug(a.split("#")[-1]) in sn and
                   slug(b.split("#")[-1]) in dn for a, rel, b in cache[v]):
                continue                      # already derived; nothing to add
            for e in byverse[v]:
                a, b = e.get("src"), e.get("dst")
                if not a or not isinstance(b, str):
                    continue
                sa, sb = slug(a.split("#")[-1]), slug(b.split("#")[-1])
                if not (sa in sn and sb in dn):
                    continue
                verb = e.get("verb") or e.get("type") or ""
                prep = (e.get("type") or "").lower() if e.get("verb") else ""
                want[r["type"]][(verb, prep)] += 1

    print("SUGGESTED RULES - from the DERIVE books only, never written")
    print("  (verb, preposition) seen joining the two endpoints where the")
    print("  relation is NOT currently derived. Held-out contributes nothing,")
    print("  so adding these and re-scoring is still a fair test.\n")
    for typ in sorted(want, key=lambda t: -sum(want[t].values())):
        top = [(k, n) for k, n in want[typ].most_common(6) if n >= 3]
        if not top:
            continue
        print(f"  {typ}")
        for (verb, prep), n in top:
            known = (verb, prep) in ADJUNCT if prep else verb in DIRECT
            mark = "already mapped ->" if known else "MISSING"
            print(f"    {n:>4}x  {verb:18}{prep:10}{mark}")
    return 0


def precision(ents, rows, byverse):
    """How often the rules are WRONG, which recall cannot tell you.

    Every number in the funnel is recall: of what the legacy graph holds, how
    much do we recompute? A rule that fires constantly and wrongly scores well
    on that and is worse than no rule, because a confident wrong answer is the
    failure this project keeps meeting.

    The check: where the rules derive a relation between two entities that the
    legacy graph ALSO relates, compare the types. Legacy is incomplete, so a
    derived relation it does not hold is not thereby wrong and is counted
    separately as unverifiable -- but a pair it *does* hold, typed differently,
    is a real disagreement.

    The specific worry that prompted this: the roster rule reads "the sons of
    X" as `father_of`, and *b'nei yisrael* -- "the sons of Israel" -- means the
    nation, not the children of the man. If that misfires it manufactures
    fatherhood for every tribe in the corpus.
    """
    known = collections.defaultdict(set)
    for r in rows:
        s, d = ents.get(r["src"]), ents.get(r["dst"])
        if s and d:
            known[(slug(s["name"]), slug(d["name"]))].add(r["type"])

    agree, disagree, unverifiable = 0, collections.Counter(), 0
    weak = 0
    examples = collections.defaultdict(list)
    for v, edges in byverse.items():
        for a, rel, b in derived(edges):
            key = (slug(a.split("#")[-1]), slug(b.split("#")[-1]))
            types = known.get(key)
            if not types:
                unverifiable += 1
                continue
            if rel in types:
                agree += 1
            elif rel == "parent_of" and (types & {"father_of", "mother_of"}):
                # true, and deliberately less specific. Not a disagreement --
                # counting it as one would punish the very under-claiming that
                # fixed the Leah-and-Bilhah errors.
                weak += 1
            else:
                disagree[(rel, tuple(sorted(types))[0])] += 1
                if len(examples[rel]) < 4:
                    examples[rel].append((key[0], rel, key[1],
                                          sorted(types)[0], v))
    total = agree + weak + sum(disagree.values())
    print("PRECISION - where the legacy graph relates the same pair too")
    print(f"  derived relations checkable   {total:>7,}")
    print(f"    same type                   {agree:>7,}   "
          f"{100*agree//max(total,1)}%")
    print(f"    weaker but true (parent_of) {weak:>7,}   "
          f"{100*weak//max(total,1)}%")
    print(f"    NOT WRONG, combined         {agree+weak:>7,}   "
          f"{100*(agree+weak)//max(total,1)}%")
    print(f"    legacy types the pair       {sum(disagree.values()):>7,}   "
          f"differently -- see below")
    print()
    print("  'Differently' is NOT the same as wrong, and the split matters:")
    print("    told -> besought/anointed/prophet_to   the text says 'said to'")
    print("      and the annotator read WHAT was said. Ours is literally true;")
    print("      theirs is an interpretation. The fact/expression boundary.")
    print("    told -> killed/attacked   an artefact of comparing by PAIR: the")
    print("      verse holds both events, legacy recorded one and we the")
    print("      other, so legacy's incompleteness reads as our disagreement.")
    print("    father_of -> mother_of    a REAL error -- matronymics like")
    print("      'Joab the son of Zeruiah', where MACULA marks no gender.")
    print(f"  not in the legacy graph at all{unverifiable:>7,}   "
          f"unverifiable, not wrong")
    print()
    print("  commonest disagreements (ours -> theirs):")
    for (ours, theirs), n in disagree.most_common(10):
        print(f"    {ours:16}-> {theirs:18}{n:>6}")
    print()
    for rel, rows_ in list(examples.items())[:4]:
        for e in rows_[:2]:
            print(f"    {e[0][:16]:18}we say {e[1][:14]:16}"
                  f"they say {e[3][:16]:18}{e[4]}")
    return 0


def audit_rules(ents):
    """A rule that names a proper noun is a memory, not a function.

    The check cuts both ways, and the first time it ran it caught the legacy
    graph rather than the rules: `us` is an entity there, a `group` resting on
    one verse of Titus 2:14 -- "gave himself for us". A bare pronoun is not an
    entity, and that collision is a defect to annotate on the old graph, not a
    rule to delete from this one. So the two cases are reported apart, and
    only real memorisation fails.
    """
    names = {}
    for e in ents.values():
        if e["type"] in ("person", "place", "group"):
            names.setdefault(slug(e["name"]), e)
    words = set(DIRECT) | {a for a, _ in ADJUNCT} | {b for _, b in ADJUNCT} \
        | BEGET_M | BEGET_F | CHILD
    collide = sorted(w for w in words if slug(w) in names)
    legacy_bad = sorted(w for w in PRONOUN if slug(w) in names)

    print("RULE AUDIT - no rule may name a person, place or group")
    print(f"  rule words (verbs, prepositions, kin terms) {len(words):>5}")
    print(f"  matching an entity name                     "
          f"{len(collide):>5}   {collide}")
    print()
    print("  separately: legacy entities that are bare pronouns")
    for w in legacy_bad:
        e = names[slug(w)]
        print(f"    {e['id']:12} {e['type']:8} {len(e.get('refs', [])):>3} ref"
              f"  {(e.get('desc') or '')[:46]}")
    if legacy_bad:
        print("    ^ a defect in the OLD graph to annotate, not a rule here")
    ok = not collide
    print()
    print("  clean - every rule is a verb, a preposition or a kin term"
          if ok else "  FAIL - a rule above memorises rather than computes")
    return 0 if ok else 1


def audit_names(ents):
    """What the spelling normaliser costs, printed rather than assumed."""
    per = [e for e in ents.values()
           if e["type"] == "person" and not (e.get("attrs") or {}).get("unnamed")]
    g = collections.defaultdict(set)
    for e in per:
        g[slug(e["name"])].add(e["name"])
    coll = {k: v for k, v in g.items() if len(v) > 1}
    print("NAME NORMALISER - every merge it makes")
    print(f"  named person entities   {len(per):>5}")
    print(f"  distinct keys           {len(g):>5}")
    print(f"  keys merging spellings  {len(coll):>5}")
    for k, v in sorted(coll.items()):
        print(f"    {k:16}{sorted(v)}")
    print("\n  Each of these should be one person spelled two ways. Any pair")
    print("  that is two different people is a false merge and a defect.")
    return 0


def main() -> int:
    ents, rows = legacy()
    if "--audit-rules" in sys.argv:
        return audit_rules(ents)
    if "--audit-names" in sys.argv:
        return audit_names(ents)
    if "--suggest" in sys.argv:
        return suggest(ents, rows, structure())
    if "--precision" in sys.argv:
        return precision(ents, rows, structure())

    byverse = structure()
    if not _check_books(rows, byverse):
        return 1

    want = None
    if "--misses" in sys.argv:
        want = sys.argv[sys.argv.index("--misses") + 1]

    alias = None
    if "--no-placement" not in sys.argv:
        alias, proposed, contested = induce(ents, rows, byverse)
        print("NAME MAPPING FROM GRAPH PLACEMENT")
        print(f"  legacy names with a proposal   {proposed:>5}")
        print(f"  accepted (>=2 verses, no rival){len(alias):>5}")
        print(f"  rejected as contested          {contested:>5}")
        print("  induced on the DERIVE books only, applied to HELD OUT, so")
        print("  the lift below cannot be circular.")
        ex = list(alias.items())[:8]
        print(f"  e.g. {ex}")
        print()

    gate, per, misses, weaker = score(ents, rows, byverse, want, alias)

    def row(label, key):
        d, h = gate[("derive", key)], gate[("heldout", key)]
        dt, ht = gate[("derive", "total")], gate[("heldout", "total")]
        pd, ph = 100 * d // max(dt, 1), 100 * h // max(ht, 1)
        flag = "  <-- gap" if abs(pd - ph) >= 10 else ""
        print(f"  {label:22}{d:>6} {pd:>3}%   {h:>6} {ph:>3}%{flag}")

    print("DERIVING THE LEGACY RELATIONS - simple entity to simple entity")
    print(f"  {'':22}{'DERIVE':>10}   {'HELD OUT':>10}")
    row("relations in scope", "total")
    row("1. verse is parsed", "verse")
    row("2. both ends named", "both")
    row("3. pair on an edge", "pair")
    row("4. type agrees", "type")
    if weaker:
        print(f"     of which parent_of, gender unstated  {weaker:>5}   true but less specific")
    print()
    print("  The gap column is the finding. A large one means the rules")
    print("  learned the derive books rather than the language.")
    print()
    hb, hv = gate[("heldout", "both")], gate[("heldout", "verse")]
    print(f"  The ceiling is gate 2, not gate 4. Of the {hv:,} held-out")
    print(f"  relations whose verse parses, only {hb:,} have BOTH endpoints")
    print("  spelled out in that verse. The rest were inferred across a")
    print("  passage or name one end by description; no rule over a single")
    print("  verse can reach them, and counting them as rule failures would")
    print("  be measuring the wrong thing.")
    print(f"  Against that ceiling, gate 4 stands at "
          f"{100*gate[('heldout','type')]//max(hb,1)}%.")
    print()

    print("  by relation type (held-out only, >=20 instances):")
    print(f"    {'type':22}{'n':>5}{'verse':>7}{'both':>7}{'pair':>7}"
          f"{'type':>7}{'of max':>8}")
    order = sorted(per, key=lambda t: -per[t][("heldout", "total")])
    for t in order:
        n = per[t][("heldout", "total")]
        if n < 20:
            continue
        v, b, p, y = (per[t][("heldout", k)]
                      for k in ("verse", "both", "pair", "type"))
        print(f"    {t:22}{n:>5}{100*v//n:>6}%{100*b//n:>6}%{100*p//n:>6}%"
              f"{100*y//n:>6}%{100*y//max(b,1):>7}%")

    if want:
        print(f"\n  misses for {want}:")
        for m in misses.get(want, []):
            print(f"    {m[0][:18]:20}-{m[1][:14]:16}-> {m[2][:18]:20}"
                  f"{m[3]:12} {m[4]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
