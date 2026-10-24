"""The whole Bible as placeholder nodes — one node per occurrence, no identity claimed.

2026-09-05: start with the placeholder nodes for the whole Bible.

## What a placeholder node is, and what it deliberately is not

**One node per occurrence.** `Gen.1.1#god` and `Gen.1.3#god` are two nodes, not
one, and nothing here says they are the same. That is the whole point of the
word *placeholder*: identity is a claim, and this pass does not make it.

The alternative — merging by surface form — is worse than doing nothing. The
old graph holds **eleven people named Zechariah, ten Shemaiah, eight Joseph**.
A name-to-node rule would collapse all eleven into one and the error would be
invisible, because the result still validates. So each occurrence stands alone
until something with evidence merges it.

**Every node carries the evidence a later identity pass will need**, which is
the useful half:

    lemma      the Hebrew or Greek dictionary form — the strongest signal,
               and the one that survives Abram/Abraham being different English
    strong     Strong's number, a second independent key
    pos/class  what kind of word it is
    proper     is it a proper noun? two witnesses agree on this
    text       the surface English, for reading
    ref        the verse, which is the anchor that survives a rebuild

The last one matters for the change-set design: a delta anchored to a node
id breaks when node ids change, and a delta anchored to verse-plus-lemma does
not.

## What the identity pass will have to work with

    aka             186 person entities in the old graph carry aliases
                    (Abraham <- Abram, Abijah <- Abia/Abijam)
    disambiguation  1,236 carry prose telling two same-named people apart
    lemma           every placeholder here carries one

That is paid-for inference already on disk, and the point of stopping here is
that the merge should USE it rather than re-derive it.

## Output

    out/placeholder-nodes.jsonl.gz    one line per occurrence
    out/placeholder-edges.jsonl.gz    one line per relation
    out/placeholder-summary.json      counts, for the dashboard

    python tools/placeholders.py            # build, whole corpus
    python tools/placeholders.py --sample Gen.1.1

MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0.
"""
from __future__ import annotations

import collections
import gzip
import json
import os
import pathlib
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from macula import MAC, _words, _ref                              # noqa: E402
from graphnodes import resolve, head_word, nid, _pos, _text       # noqa: E402

OUT = ROOT / "out"

_FORCES = None


def _upper_force(lang, form):
    """The meaning-layer force of a verb form, as ontology/kinds.json maps it.

    Read from the ontology rather than written here, so the build and the
    declaration are one mapping. A form the ontology does not list returns
    None — and the closed-world check will say which.
    """
    global _FORCES
    if _FORCES is None:
        _FORCES = json.loads((ROOT / "ontology" / "kinds.json")
                             .read_text(encoding="utf-8"))["forces"]
    return ((_FORCES.get(lang) or {}).get(form or "-") or {}).get("upper")
PROPER = {"proper", "name"}

# Verbs whose complement is the clause that follows them. Named explicitly and
# kept short: this licenses a `content` edge, so a wrong member invents a
# relation rather than merely missing one.
# "דָבַר" WITHOUT the dagesh: MACULA's lemma for the verb "speak". Spelled
# "דָּבַר" here until 2026-09-26, a form the corpus never uses — so the 1,129
# clauses headed by "speak" ("the LORD spoke to Moses") were never
# recognised as speech by any rule that reads this set. Found on BSB 8:19's
# "just as the LORD had said". Not the noun דָּבָר "word" (1,313), which is
# the near-spelling a guess would reach for. Checked since: every hand list
# here against the corpus's own lemma spellings — this was the only miss.
SPEECH = {"אָמַר", "דָבַר", "צָוָה", "קָרָא", "עָנָה", "שָׁאַל", "נָגַד",
          "שָׁבַע"}
# Moods that state a command rather than report an event.
COMMAND = {"jussive", "imperative", "cohortative"}
# Verbs after which כִּי introduces WHAT is known, seen, heard or said — "that"
# — rather than a reason. 447 of 987 `because` edges hung from one of these
# before this set existed (Exodus 8:6, "that you may know THAT there is no
# one like the LORD", was built as "know BECAUSE").
PERCEIVE = {"יָדַע", "רָאָה", "שָׁמַע", "אָמַר", "זָכַר", "נָגַד", "בִּין",
            "שָׁבַע"}
# Greek negatives — MACULA's Greek marks no `type` for them, so by lemma
NEG_GREEK = {"οὐ", "οὐκ", "οὐχ", "οὐχί", "μή", "οὐδέ", "μηδέ", "οὔτε",
             "μήτε", "οὐκέτι", "μηκέτι", "οὐδέποτε", "μηδέποτε"}
# The words a psalm's HEADING names it by: psalm, song, maskil, miktam,
# prayer, praise, shiggaion — and "to the choirmaster" (נָצַח).
PSALM_GENRE = {"מִזְמוֹר", "שִׁיר", "מַשְׂכִּיל", "מִכְתָּם", "תְּפִלָּה",
               "תְּהִלָּה", "שִׁגָּיוֹן", "נָצַח"}
# The names the headings attribute psalms to — a closed list, read off the
# headings themselves. NOT Jeduthun: "for Jeduthun" (39:1, 62:1, 77:1) names
# the director, and the same headings go on "a psalm of David / Asaph".
PSALM_WRITERS = {"דָּוִד", "אָסָף", "קֹרַח", "שְׁלֹמֹה", "מֹשֶׁה", "הֵימָן",
                 "אֵיתָן"}
# How many verses of narrative stay in view. Three is what Exodus 8:6 needs to
# reach Pharaoh in 8:4, and a command answered several verses later is the
# commoner shape than one answered ten verses later.
NARRATIVE_WINDOW = 4

# WHAT A CONJUNCTION SAYS ABOUT THE CLAUSE IT INTRODUCES. 2026-09-21,
# on Psalm 107:1 — "Give thanks to the LORD, for he is good; for his steadfast
# love endures forever." MACULA wraps each subordinate clause in a rule like
# `cjpCLx` that HOLDS the conjunction, and `_bears_roles` skips the wrapper
# because it states no roles of its own, so the conjunction was dropped and
# with it the only thing saying how the clauses relate.
#
# 7,463 clauses are wrapped this way. Unlike the cause in Genesis 1:3, which
# is a reading, these relations are STATED: כִּי is "because" and אִם is "if".
#
#     כִּי 1,175 · אִם 928 · יַעַן 65 · אוֹ 29 · לוּ 22 · פֶּן 5 · עֵקֶב 3
#
# וְ is deliberately typed `and` and nothing more. It is 5,202 of the 7,463 and
# it does everything in Hebrew -- sequence, contrast, consequence -- so
# reading a relation into it would be inventing one, which is the mistake the
# `cause / effect` naming already made once.
#
# KEYED ON NFC, because a pointed Hebrew lemma written here and the same
# lemma in MACULA can differ in BYTES while being identical on screen. כִּי
# arrives as kaf + DAGESH + hiriq and was written above as kaf + hiriq +
# DAGESH; the two render the same, compare unequal, and the lookup silently
# returned nothing for the commonest conjunction in the Bible. Normalising
# both sides is the whole fix, and it is the same fault as everything else
# this week -- a string standing in for an identity.
def _nfc(s):
    return unicodedata.normalize("NFC", s) if s else s


CONNECTIVE = {_nfc(k): v for k, v in {
    "כִּי": "because", "יַעַן": "because", "עֵקֶב": "because",
    "אִם": "if", "לוּ": "if", "לוּלֵא": "unless", "בֵּלֶת": "unless",
    "פֶּן": "lest", "אוֹ": "or", "הֵן": "if", "לָהֵן": "therefore",
    "וְ": "and",
    # "even though" — concession, read as a pair of words (Psa 23:4)
    "גַּם כִּי": "though",
    # "BUT", only where the word is a clause connective and nothing else.
    # 2026-09-26: whether 'but' fits on the list to at least check, or is
    # a more simple contrast — measured: רַק and אַךְ are mostly
    # FOCUS particles on a phrase ("ONLY the high places", 79 and 94), and at
    # clause level they are "but", "only" OR "surely" — Psa 23:6 opens with
    # אַךְ, "SURELY goodness and mercy" — so they stay the adverbs they are,
    # as does אֲבָל (11, "but" or "surely"). אוּלָם (19) and אֶפֶס כִּי (5)
    # mean "but / however" and nothing else; כִּי אִם is "but rather", the
    # correction after a negative ("not X but Y").
    # (typed `contrast`, not "but": the flat layer already has a "but")
    "אוּלָם": "contrast", "אֶפֶס כִּי": "contrast",
    "כִּי אִם": "but_rather",
}.items()}


def _nominal_clause(el):
    """Whether a role's filler is a clause turned into a noun: MACULA's
    CL2NP, reached through single-phrase wrappers (the article's DetNP) —
    "the one who forgives" (Psa 103:3). Nothing but the clause is inside."""
    for _ in range(3):
        if el is None or el.tag != "wg":
            return False
        kids = [x for x in el if x.tag == "wg"]
        if el.get("rule") == "CL2NP":
            return len(kids) == 1 and kids[0].get("class") == "cl"
        others = [x for x in el if x.tag == "w" and
                  x.get("type") != "definite article"]
        if len(kids) != 1 or others:
            return False
        el = kids[0]
    return False


def _member_local(x):
    """A coordination member's node id: an "X of Y" phrase (NPofNP) is named
    by X, its construct head, as the flat layer names it — "slow [of anger]
    and abounding [in loving devotion]" (Psa 103:8) is slow + abounding. By
    its noun it was anger + steadfast love, matched nothing the flat layer
    made, and the role fell back to its first word, "long"."""
    from graphnodes import CONTENT                              # noqa: E402
    # a QUANTIFIED member is named by what it quantifies: "ALL the day and
    # ALL the night" (Exo 10:13) is day + night. Named by "all", the "all"
    # qualified itself and was dropped — 763 quantity qualifiers lost when
    # coordinations began walking each member by its own name (2026-09-26)
    if x is not None and x.tag == "wg" and x.get("rule") == "QuanNP":
        qh = _quant_head(x)
        if qh is not None:
            return _member_local(qh)
    if x is not None and x.tag == "wg" and \
            x.get("rule") in ("NPofNP", "AdjpofNp"):
        first = next((c for c in x if c.tag == "wg" or
                      (c.tag == "w" and _pos(c) in CONTENT)), None)
        if first is not None:
            # through both layers: "ALL the people of the land" (2Ki 11:19)
            # is people, not all
            return _member_local(first) if first.tag == "wg" else nid(first)
    return nid(x)


def _coord_el(el, depth=0):
    """The coordination ELEMENT a role element is — the one _coord_local
    names — through the same wrappers, or None."""
    from graphnodes import COORD, PASSTHROUGH                   # noqa: E402
    if el is None or el.tag != "wg" or depth > 3:
        return None
    rule = el.get("rule") or ""
    if COORD.match(rule):
        return el
    if rule in PASSTHROUGH or rule.startswith("Prep"):
        inner = [c for c in list(el) if c.tag == "wg"]
        if len(inner) == 1:
            return _coord_el(inner[0], depth + 1)
    return None


def _iter_no_cl(el):
    """The words of a phrase, not descending into a clause nested in it."""
    for x in el:
        if x.tag == "w":
            yield x
        elif not (x.tag == "wg" and x.get("class") == "cl"):
            yield from _iter_no_cl(x)


def _is_cl(el):
    return el is not None and el.tag == "wg" and el.get("class") == "cl"


def _in_role(el, parent):
    """Whether a unit is filling a ROLE in a larger clause — the object of
    "know" in "they will know THAT I am the LORD" (Ezk 36:36). Its כִּי is
    "that", however fronted it looks inside the unit: a first version made
    3 of 14 such contents into settings."""
    hops = 0
    while el is not None and hops < 12:
        if el.get("role"):
            return True
        el = parent.get(el)
        hops += 1
    return False


def _fronted_at(kids, conj_i, clause_i):
    """Whether a כִּי clause COMES BEFORE the clause it governs.
    2026-09-26, on Psa 23:4 and the concession measurement: a fronted כִּי is
    a setting — "when", "if" or "though", the Hebrew does not say which —
    and it attaches forward, as a condition does.

    MACULA keeps these flat: Jer 14:12 is `כִּי [they fast] [I will not
    listen] וְ כִּי [they offer] [I will not accept] כִּי [by the sword ...]`.
    Fronted when what directly precedes the כִּי is NOT a clause (the start of
    the unit, or a sentence-opening "and") and a clause follows the כִּי
    clause directly. The last כִּי there is preceded by a
    clause: it trails. Measured before: 0 of 718 `because` edges had their
    reason first — fronted כִּי clauses were dropped, or hung on the clause
    before them ("I will not listen THAT they offer")."""
    # A clause DIRECTLY before the כִּי: it trails ("I will not accept them,
    # for / rather by the sword ..."). With "and" between — וְכִי, "AND when
    # they offer, I will not accept" — the "and" opens a new sentence, and
    # the clause after decides. (A first version skipped the "and" and took
    # the clause before it as the host: Jer 14:12's second כִּי stayed "that".)
    j = conj_i - 1
    if j >= 0 and _is_cl(kids[j]):
        return False
    nxt = kids[clause_i + 1] if clause_i + 1 < len(kids) else None
    if not _is_cl(nxt):
        return False
    # THE CLAUSE IT SETS STANDS ON ITS OWN: one opening with its own
    # conjunction is not that main clause. Rut 3:18, "for the man will not
    # rest UNLESS (כִּי אִם) he has settled it", read "not rest" as setting
    # "he has settled it" — caught while the blind judging was being built.
    first = next(iter(nxt), None)
    return not (first is not None and (
        (first.tag == "w" and first.get("pos") == "conjunction")
        or first.get("class") in ("cjp", "conj")))


def _attrs(w):
    """Everything about one word that a later identity pass could use."""
    if w is None:
        return {}
    a = {"text": _text(w)}
    for src, dst in (("lemma", "lemma"), ("strong", "strong"),
                     ("strongnumberx", "strong"), ("pos", "pos"),
                     ("class", "class"), ("type", "type"),
                     ("gender", "gender"), ("number", "number"),
                     ("person", "person"), ("ref", "word_ref")):
        v = w.get(src)
        if v and dst not in a:
            a[dst] = v
    t = (w.get("type") or "").lower()
    c = (w.get("class") or "").lower()
    a["proper"] = bool(t in PROPER or c in PROPER
                       or (w.get("morph") or "").startswith("Np"))
    return a


def mark_usual(nodes):
    """THE HEBREW WORD'S USUAL RENDERING, beside the one this verse uses.

    2026-09-26, on Psa 23:2 "waters of quiet" (מְנֻחוֹת), quoting the
    word card — "mənûḥāh · most often rendered 'resting place'": going with
    the Hebrew is preferable, as it shows something about the original
    author's intent that is not seen as clearly in the word "quiet".

    A node's `text` is MACULA's `english`: the rendering chosen for this
    occurrence. `usual` is the rendering MACULA's `english` gives this Hebrew
    word most often across the Hebrew Bible — the same count the word card's
    "most often rendered" comes from. Kept on common nouns and adjectives
    where it says more than this verse's word ("resting place" / "quiet",
    "grass" / "green"); names keep their English form.

    WRONG TURN, same day: MACULA's per-word `gloss` column first, read as
    "the Hebrew word's own meaning". It is not reliably the more literal of
    the two — "rest(s)" against "quiet", but "people" against "sons" for
    בְּנֵי (Exo 6:13) — and neither column is the BSB (the English word was in
    the BSB verse 240 times of 400). The rule: do not use the BSB if the
    word was not sourced from it."""
    words = [n for n in nodes
             if n.get("class") in ("noun", "adj") and not n.get("proper")
             and n.get("strong") and n.get("text") and not n.get("verb")]
    count = collections.defaultdict(collections.Counter)
    for n in words:
        count[n["strong"]][n["text"].lower()] += 1
    shown = 0
    for n in words:
        usual = count[n["strong"]].most_common(1)[0][0]
        if _says_more(usual, n["text"]):
            n["usual"] = usual
            shown += 1
    return shown


def _norm_word(s):
    s = (s or "").lower().replace("’", "'")
    for x in ("[s]", "(s)", "(of) ", "'s", "s'"):
        s = s.replace(x, "")
    return " ".join(t[:-1] if t.endswith("s") and len(t) > 3 else t
                    for t in s.split())


def _says_more(g, english):
    """Whether one rendering tells a reader something the other does not.
    Not when they differ only in number or possessive ('Levite[s]' /
    'Levites', 'son' / "son's"), nor when the first is part of the second
    ('places' in 'high places'). Without this test, about half the labels
    shown in a first sample were that kind."""
    a, b = _norm_word(g), _norm_word(english)
    if not a or a == b:
        return False
    return not set(a.split()) <= set(b.split())


def _index(cl):
    """node id -> the word that names it, for every constituent in a clause."""
    out = {}
    for e in cl.iter():
        if e.tag not in ("w", "wg"):
            continue
        i = nid(e)
        if i and i not in out:
            hw = head_word(e)
            if hw is not None:
                out[i] = hw
    return out


def _bears_roles(cl):
    """Does this clause state roles itself, or is it only a container?

    `CLaCL` and `ClCl` are coordinations OF CLAUSES: the container holds no
    subject or verb of its own, only two clauses that do. Taking the outermost
    clause and discarding what is inside therefore yielded NOTHING for those
    verses -- `build()` looks for roles and finds sub-clauses.

    Psalm 103:6 and 103:7 are exactly this, which is why "he made known his
    ways unto Moses" produced no structure at all, and why the pattern harvest
    could not link Moses to the divine-attribute formula in verse 8.
    """
    return any(ch.get("role") for ch in list(cl))


def name_composites(nodes, edges):
    """Give a coordination node the words it stands over.

    **All 38,057 composite nodes carried no text at all** -- 16% of the layer.
    They are minted by `_compose` for a coordination, so they correspond to no
    single word and `_attrs` had nothing to read. Everything downstream then saw
    a node with an id and no name: 63% of the unresolved subjects in the
    figurative-language rules were these, not head selection failing.

    The members are already on `member` edges, so the name is a join of what
    they say. Two members are joined in full and more are abbreviated, matching
    what `_compose` does with ids -- Genesis 25:2 coordinates six sons and the
    point of the node is that it is identifiable, not exhaustive.

    Nested composites are resolved before their parents by looping until
    nothing changes, so a coordination of coordinations is not named "and".
    """
    by_id = {n["id"]: n for n in nodes}
    members = collections.defaultdict(list)
    for e in edges:
        if e.get("type") == "member" and e.get("src") and e.get("dst"):
            members[e["src"]].append(e["dst"])

    named = 0
    for _ in range(4):                       # depth of nesting seen in practice
        progress = 0
        for nid, kids in members.items():
            n = by_id.get(nid)
            if not n or not n.get("composite") or n.get("text"):
                continue
            texts = [by_id.get(k, {}).get("text") for k in kids]
            texts = [t for t in texts if t]
            if len(texts) < len(kids):       # a member is itself unnamed yet
                continue
            n["text"] = (" and ".join(texts) if len(texts) <= 2
                         else f"{texts[0]} and {len(texts)-1} more")
            named += 1
            progress += 1
        if not progress:
            break

    # Most composites are not coordinations at all and carry no `member` edges:
    # 28,201 of them are CONSTRUCT CHAINS, built by a different path. Their
    # `local` id is already made from the head words, so unpacking it recovers
    # a readable name -- `fishOfSea` says what it is. Used only as a fallback,
    # after the members have had their say.
    for n in nodes:
        if not n.get("composite") or n.get("text"):
            continue
        words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", n.get("local", "")).lower()
        words = re.sub(r"\band (\d+) more\b", r"and \1 more", words).strip()
        if words:
            n["text"] = words
            named += 1
    return named


def clauses_by_verse(paths):
    """The outermost clauses that actually state roles, per verse.

    Not simply the top-level ones. A clause-coordination is skipped in favour
    of the clauses inside it, because the container says nothing on its own.
    """
    by = collections.OrderedDict()
    for f in paths:
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        # EVERY clause that states roles, nested or not. Excluding nested ones
        # cost Revelation 14:1 five of its six clauses: its outer clauses are
        # thin wrappers -- an `aux` and a clause filling an object role -- and
        # everything the verse actually says sits inside them.
        #
        # A nested clause's edges are additional facts, not duplicates: the
        # parent mints the child as one node (a summary), and the child states
        # its own subject, verb and object. Both are true.
        usable = [c for c in root.iter("wg")
                  if c.get("class") == "cl" and _bears_roles(c)]
        # EACH WORD'S POSITION IN ITS VERSE, IN DOCUMENT ORDER — the order
        # out/interlinear.jsonl.gz lists them, so a clause's words can be
        # shown in the Hebrew. MACULA's own `!n` numbers SURFACE words, and a
        # prefix or suffix shares its word's number ("and-if" is one), so
        # those numbers ran one off the interlinear and could not be used.
        seen_v = collections.Counter()
        for w in root.iter("w"):
            v = _ref(w.get("ref") or "")
            if v:
                _WPOS[id(w)] = seen_v[v]
                seen_v[v] += 1
            # which stems each verb root occurs in, corpus-wide: a causative
            # (hiphil) wraps an event only where the root has a plain (qal)
            # event to wrap
            if w.get("pos") == "verb" and w.get("stem"):
                _STEMS[_nfc(w.get("lemma"))].add(w.get("stem"))
        # THE CONJUNCTION IS ON THE WRAPPER, NOT THE CLAUSE. A subordinate
        # clause sits inside a `cjpCLx`-style wrapper that holds the word, and
        # the wrapper states no roles so it is skipped above. Carrying the
        # lemma down onto the clause keeps it: `_connective` is read back in
        # build(). Set as an attribute because the clause element is what
        # travels, and pairing it in a side table would break the moment a
        # clause appeared twice.
        parent = {ch: p for p in root.iter() for ch in p}
        # A CONJUNCTION BESIDE THE CLAUSE, not only on a wrapper. Psalm 23:4
        # is "[even though] I walk through the valley ... I will fear no
        # harm, [because] you are with me", and MACULA puts both — גַּם כִּי
        # as a `cjp` group, כִּי as a bare word — as SIBLINGS before their
        # clauses inside a class-less container. Only wrappers were read, so
        # the graph held neither. The plain waw is NOT read this way: every
        # narrative verb's וַ sits there too, and "and then" handles it.
        waw = {_nfc("וְ")}
        for c in usable:
            p = parent.get(c)
            if p is None:
                continue
            # A RELATIVE CLAUSE: MACULA wraps it, with its אֲשֶׁר, in a
            # `relp` unit ("the spoil [which we recovered]", 1Sa 30:22)
            if p.get("class") == "relp":
                c.set("_relative", "1")
            kids = list(p)
            i = kids.index(c)
            prev = kids[i - 1] if i else None
            if prev is None:
                continue
            ws_ = ([prev] if prev.tag == "w" else
                   list(prev.iter("w")) if prev.get("class") in ("cjp",)
                   else [])
            # a `cjp` is a conjunction phrase by MACULA's own class, whatever
            # its words' parts of speech: אוּלָם is tagged an adverb, אֶפֶס a
            # noun, and both are "but" there
            if not ws_ or not (prev.get("class") == "cjp" or all(
                    w.get("pos") in ("conjunction", "particle")
                    or _nfc(w.get("lemma")) == _nfc("אוּלָם") for w in ws_)):
                continue
            lems = [_nfc(w.get("lemma")) for w in ws_]
            core = [l_ for l_ in lems if l_ not in waw]
            pair = {(_nfc("גַּם"), _nfc("כִּי")): "גַּם כִּי",
                    (_nfc("כִּי"), _nfc("אִם")): "כִּי אִם",
                    (_nfc("אֶפֶס"), _nfc("כִּי")): "אֶפֶס כִּי"}.get(tuple(core))
            if pair:
                c.set("_connective", _nfc(pair))
            else:
                conj = next((l_ for l_ in lems if l_ not in waw
                             and l_ in CONNECTIVE), None)
                if conj:
                    c.set("_connective", conj)
                    if conj == _nfc("כִּי") and not _in_role(p, parent) and \
                            _fronted_at(kids, i - 1, i):
                        c.set("_fronted", "1")
                elif lems == [_nfc("וְ")]:
                    # A PLAIN WAW BEFORE A CLAUSE WHOSE VERB DOES NOT CARRY IT.
                    # Skipped above because every wayyiqtol's וַ also sits
                    # here, and "and then" handles those. But a clause whose
                    # verb is NOT a fused-waw form — "and not they could"
                    # (וְלֹא יָכֹלוּ, Exo 8:14), "and not he listened" (8:15) —
                    # was left joined to nothing. First-retrieval fault 5;
                    # 2026-09-26: fix it systemically, and the effect
                    # readings only where the structure marks them.
                    vw_ = next((x for x in list(c) if x.get("role") == "v"),
                               None)
                    hv_ = head_word(vw_) if vw_ is not None else None
                    if hv_ is None or hv_.get("type") not in (
                            "wayyiqtol", "weqatal"):
                        c.set("_connective", _nfc("וְ"))
        for c in usable:
            if c.get("_connective"):
                continue          # already read beside the clause
            p = parent.get(c)
            child = c
            hops = 0
            # up through clause wrappers AND the sentence's class-less top
            # container: "AND behold, the teraphim was in the bed" (1Sa
            # 19:16) has its "and" before the whole unit, up there. Without
            # it the walk found only the "and" AFTER the clause (wrong) — or,
            # once only a conjunction BEFORE counted, nothing: 1,424 clauses
            # lost their link that way before this was added.
            while p is not None and (p.get("class") == "cl" or
                                     (p.tag == "wg" and not p.get("class")))\
                    and not _bears_roles(p):
                hops += 1
                if _tripped(hops, f.name, "connective walk up the tree", 200):
                    break
                # THE CONJUNCTION BEFORE THIS CLAUSE, the nearest one. Exo
                # 4:8 is "and it will be, IF [they do not believe you AND do
                # not heed the first sign], then they will believe the
                # second": the first condition sits in a unit whose only
                # conjunction is the "and" AFTER it, and taking the unit's
                # first conjunction gave it "and" — the אִם above was never
                # reached. DeepSeek's audit found it (Priority 2).
                kids_ = list(p)
                before = kids_[:kids_.index(child)] if child in kids_ else []
                # the nearest conjunction with NO CLAUSE BETWEEN it and this
                # one: in Psa 23:4's flat unit, "[גַּם כִּי] [I walk] [I will
                # not fear]", the search passed over "I walk" and made "I
                # will not fear" a concession too
                cj, blocked = None, False
                for k_ in reversed(before):
                    if k_.get("class") in ("cjp", "conj") or \
                            k_.get("pos") == "conjunction":
                        cj = k_
                        break
                    if _is_cl(k_) and not (k_.get("rule") or "") \
                            .startswith("Intj"):
                        blocked = True
                        break
                if blocked:
                    break
                if cj is None:
                    # a conjunction BEFORE A UNIT belongs to the unit's first
                    # clause only. "[though I walk ...] [I will not fear]" (Psa
                    # 23:4) is one unit after גַּם כִּי: climbing from the second
                    # clause made it a concession too. A clause with a clause
                    # before it in its unit is joined to that one, asyndetic-
                    # ally — stop. An interjection clause ("behold", 1Sa
                    # 19:16) does not count as one.
                    if any(_is_cl(x) and not (x.get("rule") or "")
                           .startswith("Intj") for x in before):
                        break
                    child, p = p, parent.get(p)
                    continue
                if cj is not None:
                    hw = cj if cj.tag == "w" else next(iter(cj.iter("w")), None)
                    # a two-word connective on the wrapper: כִּי אִם is "but
                    # rather", not "because"
                    core_ = [_nfc(x.get("lemma")) for x in
                             ([cj] if cj.tag == "w" else cj.iter("w"))
                             if _nfc(x.get("lemma")) not in waw]
                    pair_ = {(_nfc("גַּם"), _nfc("כִּי")): "גַּם כִּי",
                             (_nfc("כִּי"), _nfc("אִם")): "כִּי אִם",
                             (_nfc("אֶפֶס"), _nfc("כִּי")): "אֶפֶס כִּי"
                             }.get(tuple(core_))
                    if pair_:
                        c.set("_connective", _nfc(pair_))
                        break
                    # a plain "and" whose clause's verb carries it (wayyiqtol,
                    # weqatal) is "and then", handled there — as beside a
                    # clause (the sibling rule above)
                    if hw is not None and _nfc(hw.get("lemma")) in waw and \
                            not core_:
                        vw_ = next((x for x in list(c)
                                    if x.get("role") == "v"), None)
                        hv_ = head_word(vw_) if vw_ is not None else None
                        if hv_ is not None and hv_.get("type") in (
                                "wayyiqtol", "weqatal"):
                            break
                    if hw is not None and hw.get("lemma"):
                        c.set("_connective", hw.get("lemma"))
                        # the WRAPPER's place among its siblings says whether
                        # this כִּי clause comes before the clause it governs
                        gp = parent.get(p)
                        if _nfc(hw.get("lemma")) == _nfc("כִּי") and \
                                gp is not None and not _in_role(p, parent):
                            gk = list(gp)
                            gi = gk.index(p)
                            if _fronted_at(gk, gi, gi):
                                c.set("_fronted", "1")
                    break
        # THE UNIT A SUBORDINATE CONJUNCTION HEADS. In Exo 4:8 the אִם heads
        # [they do not believe AND do not heed]: both clauses are the
        # condition, and the clause it governs is the first one AFTER the
        # unit — not the second condition. Every clause inside a `cjp…`
        # wrapper carries the wrapper's identity, and a forward link skips
        # clauses of its own unit.
        for c in usable:
            a = parent.get(c)
            hops_ = 0
            while a is not None and hops_ < 8:
                if a.get("class") == "cl" and \
                        (a.get("rule") or "").startswith("cjp"):
                    # keyed on the unit's first word, NOT id(): a memory
                    # address differs run to run and broke determinism
                    fw_ = next(a.iter("w"), None)
                    c.set("_scope", f"{fw_.get('ref') if fw_ is not None else ''}"
                                    f"/{_WPOS.get(id(fw_), '')}")
                    break
                a, hops_ = parent.get(a), hops_ + 1
        # WHICH CLAUSE A NESTED CLAUSE SITS INSIDE, AND IN WHICH ROLE.
        # 2026-09-25, on Exodus 7:27: the 'let them go' is part of the
        # refusal clause under the if condition, so it should not be pulled
        # out. It was pulled out because every role-bearing clause
        # was taken as a clause in its own right and the nesting MACULA states
        # was dropped: "to let them go" is the object of "you refuse", inside
        # it. Recorded here, where the parent map exists, and emitted in
        # build() as a `within` edge carrying the role.
        # VOCATIVES. MACULA has no vocative role: "O my soul" (Psa 103:1) is
        # a clause that is only a noun phrase (`Np2CL`), paired with the
        # clause it addresses. The same shape is a TOPIC when the other
        # clause takes it up in the third person ("your rod and your staff
        # — they comfort me", 23:4), so it is a vocative only beside a
        # SECOND-person clause.
        for c in usable:
            p = parent.get(c)
            if p is None:
                continue
            sibs = [s_ for s_ in p if s_.tag == "wg" and s_.get("class") ==
                    "cl"]
            np_ = next((s_ for s_ in sibs if s_.get("rule") == "Np2CL"),
                       None)
            if np_ is None or c is np_:
                continue
            vch = next((ch for ch in c if ch.get("role") == "v"), None)
            hv = (vch if vch is not None and vch.tag == "w" else
                  next(iter(vch.iter("w")), None) if vch is not None
                  else None)
            if hv is not None and hv.get("person") == "second":
                _VOCATIVE[id(c)] = np_
        # how often each root's PLAIN stem (qal) takes an object: a causative
        # wraps an event only where the plain verb is intransitive ("lie
        # down", "go up") — נָחָה "lead" takes an object in qal already, and
        # its hiphil "he leads me" is not "he makes me lead"
        for c in usable:
            vch = next((ch for ch in c if ch.get("role") == "v"), None)
            if vch is None:
                continue
            hv = vch if vch.tag == "w" else next(iter(vch.iter("w")), None)
            if hv is None or hv.get("stem") != "qal":
                continue
            cnt = _QAL_OBJ[_nfc(hv.get("lemma"))]
            cnt[1] += 1
            if any(ch.get("role") in ("o", "o2") for ch in c):
                cnt[0] += 1
        use = set(map(id, usable))
        for c in usable:
            path, p = [], parent.get(c)
            while p is not None and id(p) not in use:
                path.append(p)
                p = parent.get(p)
                if _tripped(len(path), f.name, "nesting walk up the tree",
                            200):
                    p = None
                    break
            if p is None:
                continue
            slot = path[-1] if path else c          # the child OF the parent
            role = slot.get("role") or c.get("role")
            prep = None
            if slot is not c:
                pw = next((w for w in slot.iter("w")
                           if w.get("pos") == "preposition"), None)
                if pw is not None:
                    prep = (pw.get("lemma"), pw.get("gloss"))
            _WITHIN[id(c)] = (p, role, prep)
        for c in usable:
            ws = _words(c)
            if not ws:
                continue
            k = _ref(ws[0].get("ref") or "")
            if k:
                by.setdefault(k, []).append(c)
    return by


# CIRCUIT BREAKERS. 2026-09-25, after a nesting loop never ended and a
# 50-second build ran past 400: recursion detection/circuit breakers are
# needed. Every open-ended loop in the build counts its
# passes against a cap; a loop that trips it stops, the trip is recorded with
# the verse, and the build goes on. A verse that takes longer than
# SLOW_VERSE seconds is recorded too. Both are printed at the end of the build
# and written to the summary, so a runaway is a line in a report — not a
# hang, and not a silently truncated result.
# PRONOUN RESOLUTION BY WALKING THE CHAIN IS OFF. Built 2026-09-25 and
# measured the same hour: 19,716 subjects written, and of 17 sampled Hebrew
# cases 6 were right. Psalm 23:2-3 resolves perfectly ("he makes me lie down"
# -> the LORD), but narrative walks past the real antecedent — "he said" to
# Judah for Hirah (Gen 38:22), "he will do evil" to the LORD for "a man or
# a woman" (Deu 17:2). At ~35% it would put false subjects into the graph,
# so it is PROPOSED: the passage view previews it, dashed; the build keeps
# only the ordered chain it walks. Turn on when a sample says it has earned
# it.
CHAIN_RESOLVE = False
LOOP_CAP = 1000
SLOW_VERSE = 2.0
_BREAKS = []             # (ref, what) for every tripped cap or slow verse


def _tripped(n, ref, what, cap=LOOP_CAP):
    """True, and recorded, once a loop has run `cap` passes."""
    if n < cap:
        return False
    _BREAKS.append((ref, what))
    return True


def _coord_local(el, depth=0):
    """The composite id of a coordination this role element IS, or None.

    Looks through the wrappers a role often sits in — the object marker, the
    article, a preposition before a coordinated noun phrase — to a
    coordination rule, and names it as graphnodes._compose does: the member
    ids joined by "and", or "<first>And<n>More" past three."""
    from graphnodes import COORD, PASSTHROUGH, CONTENT          # noqa: E402
    if el is None or el.tag != "wg" or depth > 3:
        return None
    rule = el.get("rule") or ""
    kids = [c for c in list(el) if c.tag == "wg" or
            (c.tag == "w" and _pos(c) in CONTENT)]
    if COORD.match(rule):
        parts = [_member_local(c) for c in kids]
        parts = [p for p in parts if p]
        if len(parts) < 2:
            return None
        return ("and".join(parts) if len(parts) <= 3
                else f"{parts[0]}And{len(parts) - 1}More")
    if rule in PASSTHROUGH or rule.startswith("Prep"):
        inner = [c for c in list(el) if c.tag == "wg"]
        if len(inner) == 1:
            return _coord_local(inner[0], depth + 1)
    return None


def _drop_so(edges, vstart, ct, vn):
    """Remove the adverbial כֵּן "so" from a content: it has been lifted to the
    clause link it stood for (fulfils, likewise). It probably also
    belongs a level higher."""
    so = _nfc("כֵּן")
    gone = [e for e in edges[vstart:]
            if e.get("src") == ct and e.get("clause_role")
            and e.get("type") in ("adv", "p")
            and _nfc((vn.get(e.get("dst")) or {}).get("lemma")) == so]
    edges[vstart:] = [e for e in edges[vstart:] if e not in gone]
    # and out of the content's KEY, which was written before the lift — the
    # clause still read "adv=so" after the role had gone
    cn = vn.get(ct)
    if gone and cn and cn.get("key"):
        cn["key"] = " ".join(t for t in cn["key"].split()
                             if t not in ("adv=so", "p=so", f"adv={so}",
                                          f"p={so}", "adv=thus", "p=thus"))


# Verbs whose לְ + infinitive is their COMPLEMENT, not a purpose (and the two
# whose use the form does not settle). A word-graph fact, hand-listed until
# that graph exists (plan 2.6), as SPEECH and PERCEIVE are.
_COMPLEMENT_VERBS = {unicodedata.normalize("NFC", x) for x in (
    "יָכֹל", "יָסַף", "כָּלָה", "חָלַל", "אָבָה", "מָאֵן", "בָּקַשׁ", "יָדַע",
    "חָדַל", "מָהַר", "הָיָה", "נָתַן")}


def _quant_head(el, depth=0):
    """The noun phrase a quantifier governs, if this role element is (or
    wraps) a QuanNP — "all [the dust of the earth]" — else None."""
    from graphnodes import PASSTHROUGH                          # noqa: E402
    if el is None or el.tag != "wg" or depth > 3:
        return None
    rule = el.get("rule") or ""
    inner = [c for c in list(el) if c.tag == "wg"]
    if rule == "QuanNP":
        kids = [c for c in list(el) if c.tag in ("wg", "w")]
        return kids[1] if len(kids) > 1 else None
    if (rule in PASSTHROUGH or rule.startswith("Prep")) and len(inner) == 1:
        return _quant_head(inner[0], depth + 1)
    return None


def _pronoun(person, gender, number):
    """The English pronoun a verb's person, gender and number state."""
    pl = number == "plural"
    if person == "first":
        return "we" if pl else "I"
    if person == "second":
        return "you (all)" if pl else "you"
    if pl:
        return "they"
    # HEBREW HAS NO "IT": a masculine verb says he-or-it. 2026-09-25, on
    # "it will become gnats" (Exo 8:12) drawn with the subject "he": the
    # English "he" asserts a person the text does not. Unresolved, the label
    # says both; resolution narrows it ("he" for a named person or God, "it"
    # for a thing).
    return {"feminine": "she/it"}.get(gender, "he/it")


# ---- head and qualifier inside a phrase --------------------------------
# rule -> (index of the head child, index of the dependent child, kind)
# AdjpofNp is an adjective in construct — "slow OF anger", "abounding IN
# loving devotion" (Psa 103:8), 190 in the Hebrew Bible — read as NPofNP is
_QUAL = {"NPofNP": (0, 1, "of"), "AdjpofNp": (0, 1, "of"),
         "NpAdjp": (0, 1, "attribute"),
         "NpPp": (0, 1, "prep"), "QuanNP": (1, 0, "quantity"),
         "NumpNP": (1, 0, "number"), "Nump2NP": (1, 0, "number"),
         "NpNump": (0, 1, "number")}
# phrases whose head is their LAST child: the article, the object marker,
# the preposition come first
_HEAD_LAST = {"DetNP", "OmpNP", "PrepNp", "Det2NP"}
_FUNCTION = {"article", "preposition", "conjunction", "particle"}


def _head_w(el, depth=0):
    """The head WORD of a phrase: through articles, object markers and
    prepositions, to the noun the phrase is about."""
    if el is None or depth > 12:                        # circuit breaker
        return None
    if el.tag == "w":
        return el
    kids = [c for c in el if c.tag in ("w", "wg")]
    if not kids:
        return None
    rule = el.get("rule")
    if rule in _QUAL:
        return _head_w(kids[_QUAL[rule][0]] if len(kids) > 1 else kids[0],
                       depth + 1)
    if rule in _HEAD_LAST:
        return _head_w(kids[-1], depth + 1)
    main = [c for c in kids if not (c.tag == "w"
                                    and c.get("pos") in _FUNCTION)]
    return _head_w((main or kids)[0], depth + 1)


def _qualify(el, head_local, ref, lang, k, known, nodes, edges, minted_lem,
             stats, depth=0):
    """Walk a role's phrase and emit `qualifier` edges, head -> dependent.

    `head_local` is the node the phrase's head already has (the role filler)
    — so the top of the phrase hangs off the node the clause points at, not
    a duplicate. Deeper heads use their own node, minted where there is none.
    """
    if el is None or el.tag != "wg" or depth > 12:      # circuit breaker
        return
    kids = [c for c in el if c.tag in ("w", "wg")]
    rule = el.get("rule")

    def local_of(w):
        if w is None or w.get("pos") in _FUNCTION:
            return None
        l_ = nid(w)
        if l_ and l_ in known:
            return l_
        l_ = f"q{k}_{len(known)}"
        at = _attrs(w)
        at.setdefault("class", w.get("pos") or "x")
        nodes.append({"id": f"{ref}#{l_}", "ref": ref, "local": l_,
                      "lang": lang, **at,
                      **({"w": [_WPOS[id(w)]]} if id(w) in _WPOS else {}),
                      "minted_for": "a qualifier in a phrase"})
        known.add(l_)
        minted_lem[l_] = _nfc(w.get("lemma")) or l_
        stats["qualifier_minted"] += 1
        return l_

    if rule in _QUAL and len(kids) > 1:
        hi, di, kind = _QUAL[rule]
        hloc = head_local or local_of(_head_w(kids[hi]))
        dw = _head_w(kids[di])
        dloc = local_of(dw)
        # A WORD NEVER QUALIFIES ITSELF. A head handed down under the name
        # of its own dependent — the flat layer calls a member "all" for "ALL
        # Israel" (Ezr 8:25) — made "all -quantity-> all" and the edge was
        # dropped. The phrase's own head is used instead.
        if hloc and hloc == dloc and head_local:
            hloc = local_of(_head_w(kids[hi]))
        if hloc and dloc and hloc != dloc:
            # A POSSESSIVE SUFFIX IS "WHOSE", not "of". 2026-09-25: what
            # does secret_arts->of->their mean? בְּלָטֵיהֶם is "secret art" +
            # the suffix "their"; MACULA builds it like "the secret arts of
            # them", which is grammar, not what a reader needs told.
            if kind == "of" and dw is not None and dw.get("pos") == "suffix":
                kind = "whose"
            rec = {"ref": ref, "lang": lang, "type": "qualifier",
                   "src": f"{ref}#{hloc}", "dst": f"{ref}#{dloc}",
                   "rel": kind, "clause_role": True,
                   # THE MENTION IT QUALIFIES: the clause it was read in.
                   # 2026-09-25, on Exo 8:13: dust->of->earth
                   # existed twice — the verse mentions "the dust of the
                   # earth" twice, both mentions share the node `dust`, and
                   # each hung its own "of earth" on it (and the second's
                   # "all" would have shown on the first). A qualifier
                   # belongs to a mention; drawings take only this clause's.
                   "clause_order": k}
            if kind == "prep":
                pw = next((w for w in kids[di].iter("w")
                           if w.get("pos") == "preposition"), None)
                if pw is not None:
                    rec["prep"] = pw.get("lemma")
                    if pw.get("gloss"):
                        rec["prep_gloss"] = pw.get("gloss")
            edges.append(rec)
            stats[f"qualifier_{kind}"] += 1
        _qualify(kids[hi], hloc, ref, lang, k, known, nodes, edges,
                 minted_lem, stats, depth + 1)
        _qualify(kids[di], dloc, ref, lang, k, known, nodes, edges,
                 minted_lem, stats, depth + 1)
        return
    # A COORDINATION IS NO MEMBER'S HEAD. Each member walks its own phrase
    # under its own node — "slow OF ANGER and abounding IN LOVING DEVOTION"
    # (Psa 103:8). Walked as any phrase, the first member "carried" the
    # collection, and "of anger" hung on the collection itself.
    from graphnodes import COORD                                # noqa: E402
    if COORD.match(rule or ""):
        for c in kids:
            if c.tag == "wg" and c.get("class") != "cl":
                ml = _member_local(c)
                _qualify(c, ml if ml in known else None, ref, lang, k, known,
                         nodes, edges, minted_lem, stats, depth + 1)
        return
    for c in kids:
        if c.tag != "wg" or c.get("class") == "cl":
            continue          # a nested clause is `within`, not a qualifier
        # the head-bearing child carries the head's node down; others start
        # afresh
        carries = (rule in _HEAD_LAST and c is kids[-1]) or \
            (rule not in _HEAD_LAST and c is next(
                (x for x in kids if not (x.tag == "w"
                                         and x.get("pos") in _FUNCTION)),
                None))
        _qualify(c, head_local if carries else None, ref, lang, k, known,
                 nodes, edges, minted_lem, stats, depth + 1)


# id(clause element) -> (enclosing clause element, role, (prep lemma, gloss))
_WITHIN = {}
# id(word element) -> its index among the verse's words, in document order
_WPOS = {}
# verb lemma -> the stems it occurs in, across the corpus
_STEMS = collections.defaultdict(set)
# preposition lemma -> its Strong's number, for a preposition made a node
_PREP_STRONG = {}
# id(clause element) -> the Np2CL clause that addresses it ("O my soul")
_VOCATIVE = {}
# verb lemma -> [qal clauses with an object, qal clauses]
_QAL_OBJ = collections.defaultdict(lambda: [0, 0])


def build(paths, lang):
    """Emit (nodes, edges) for every verse these files cover."""
    by = clauses_by_verse(paths)
    nodes, edges = [], []
    carry = prev = None
    stats = collections.Counter()
    # A NARRATIVE WINDOW, BECAUSE A VERSE IS NOT A UNIT OF MEANING.
    # 2026-09-21: it may be necessary to look back a verse, and narratives
    # really need to be taken in order to have context.
    #
    # Two separate layers were blocked on the same thing. Exodus 8:6 has two
    # speeches with no stated speaker, and both participants are NAMED one and
    # two verses earlier — Pharaoh in 8:4, Moses in 8:5 — so the alternation
    # is recoverable and we were attributing both to Moses. And the
    # action-state pairs miss Genesis 1:6 answered by 1:7, *"let there be a
    # firmament"* and *"and it was so"*, because the pair detection could not
    # see out of the verse either.
    #
    # `carry` passes ONE subject across the boundary, which cannot express two
    # alternating participants. This keeps the last few verses' clauses
    # instead. Reset on a BOOK change only: chapter divisions are editorial
    # and land mid-narrative constantly.
    window = collections.deque(maxlen=NARRATIVE_WINDOW)
    # Who does it, to what, and to whom, per clause, as comparable tokens
    # (lemma where MACULA gives one). Kept OFF the clause record so the
    # output does not grow private fields; read by the pair rule, which has to
    # compare a command in one verse with a report in another.
    facts = {}
    perceive = {_nfc(x) for x in PERCEIVE}
    turns = []        # speeches still going at the end of the last verse,
                      # outermost first
    psalm = None      # the Writing unit of the psalm being built
    # THE ORDERED CHAIN. 2026-09-25: at a minimum an ordered chain is
    # needed for pronoun resolution. The last clause built, so each clause
    # links to the one before it across verse boundaries; and a short history
    # of clauses with their subjects, walked back to resolve a pronoun.
    last_clause = None
    history = collections.deque(maxlen=40)
    # the leading text for pronoun resolution: per clause, the referents it
    # names, most recent last (the unique-candidate rule, below)
    ref_hist = collections.deque(maxlen=12)
    resolved = {}     # pronoun node -> the referent it was resolved to
    # FULFILMENT: the commands in the leading text (book-scoped), each with
    # the unit it belongs to and who is to carry it out; and each unit's
    # CONTENT PARENT, so a command chain can be walked up to its top
    cmd_hist = collections.deque(maxlen=40)
    content_parent = {}
    cmd_actor = {}                        # command clause -> its actor
    unit_of = {}                          # command clause -> its group, if any
    unit_effect = {}                      # command group -> its effect clauses
    clause_lemma = {}                     # clause -> its verb's lemma
    last_deed = {}                        # book -> (clause, seq) of latest deed
    heart_owner = {"prev": None}          # whose heart the last clause named
    clause_seq = [0]                      # clauses seen, in order
    acts_run = {"run": None}              # the open run of one agent's acts
    desc_run = {"run": None}              # the open run of "the one who ..."
    divine_ids = set()                    # nodes that are a divine name
    genre = {_nfc(x) for x in PSALM_GENRE}
    writers = {_nfc(x) for x in PSALM_WRITERS}
    divine = {_nfc(x) for x in ("יהוה", "אֱלֹהִים", "אֲדֹנָי", "אֵל")}
    for ref, cls in by.items():
        t_verse = time.time()
        book = ref.split(".")[0]
        if book != prev:
            carry = None          # a subject does not run across a book
            window.clear()
            turns = []            # nor does a speech
            psalm = None          # nor a psalm
            last_clause = None    # nor the ordered chain
            history.clear()
            ref_hist.clear()
        prev = book
        try:
            g = resolve(cls, carry=carry)
            carry = g.get("carry")
        except Exception:                                         # noqa: BLE001
            stats["verse_errors"] += 1
            continue
        words = {}
        for c in cls:
            words.update(_index(c))
        for local in g["nodes"]:
            hw = words.get(local)
            a = _attrs(hw)
            if hw is None:
                # A composite the pass minted rather than a word in the text:
                # the coordination node behind "heavens and earth", or a
                # construct chain. Marked so a consumer reads it as DERIVED
                # rather than as a lexical node whose attributes went missing.
                a = {"composite": True}
                stats["composite"] += 1
            nodes.append({"id": f"{ref}#{local}", "ref": ref, "local": local,
                          "lang": lang, **a})
            stats["nodes"] += 1
            if a.get("proper"):
                stats["proper"] += 1
            if a.get("lemma"):
                stats["with_lemma"] += 1
        # ---- the clause layer ------------------------------------------
        #
        # 2026-09-21, after two days of the pattern work feeling thin: start
        # with the command node 'be light', which has tuple relationships
        # with the command 'be' and the object 'light'; this is the kind of
        # pattern wanted.
        #
        # A clause becomes a NODE and its parts hang off it by MACULA's own
        # role. Two things that were impossible before become possible:
        #
        # **A verb gets somewhere to live.** Until now a verb was an edge
        # LABEL — a string — so everything MACULA knows about it was dropped
        # at the moment the edge was written: 0 of 261,920 edges carried mood,
        # aspect or stem, and `jussive` is the only thing distinguishing "let
        # there be light" from "there was light".
        #
        # **A clause gets somewhere to be pointed at.** `God said` was marked
        # intransitive across 4,892 instances, faithfully — MACULA's `V-S`
        # over *he.said · God* carries no object role, because the thing said
        # is the NEXT CLAUSE. There was no node of the right kind to be its
        # complement.
        known = set(g["nodes"])
        # WHERE THIS VERSE'S EDGES BEGIN. Everything below that looks
        # "at the edges" means THIS verse's edges. Scanning the global
        # accumulator instead made the build quadratic -- 45s became
        # minutes -- and would have grown worse with every book.
        vstart = len(edges)
        cinfo = []
        addr_to = {}          # clause id -> who its psalm address is to
        # each clause's OWN words — without those of clauses nested inside
        # it, whose negation (or anything else) is theirs, not its
        minted_lem = {}               # minted role filler -> its lemma
        inner_w = collections.defaultdict(set)
        for c2 in cls:
            w2 = _WITHIN.get(id(c2))
            if w2:
                inner_w[id(w2[0])] |= {id(x) for x in _words(c2)}
        for k, c in enumerate(cls):
            cid = f"{ref}#cl{k}"
            ce0 = len(edges)        # where this clause's own edges begin
            cw = _words(c)
            vlem = vmood = vstem = vperson = None
            vword = None
            roles = []
            role_els = []          # (role element, its filler's local)
            for ch in list(c):
                role = ch.get("role")
                if not role:
                    continue
                if role == "v":
                    hw = head_word(ch)
                    if hw is not None:
                        vlem = hw.get("lemma")
                        # ONLY A VERB HAS A MOOD, AND THE TWO LANGUAGES KEEP IT
                        # IN DIFFERENT PLACES. Hebrew puts the form in `type`;
                        # Greek puts it in `mood` and uses `type` for nothing
                        # here. Reading `type` from every head gave all 30,462
                        # Greek clauses no mood at all, and gave 100 Hebrew
                        # clauses whose `v` head is not a verb a "mood" of
                        # `adjective`, `proper` or `demonstrative`. Found
                        # 2026-09-24 by the ontology check, which refuses any
                        # force value it has not been told exists.
                        if lang == "greek":
                            vmood = (hw.get("mood")
                                     if hw.get("class") == "verb" else None)
                        else:
                            vmood = (hw.get("type")
                                     if hw.get("pos") == "verb" else None)
                        vstem = hw.get("stem")
                        vperson = hw.get("person")
                        vword = hw
                # WHICH PREPOSITION. 2026-09-21, on "give thanks to the
                # LORD": the role `pp` alone cannot tell *to* the LORD from
                # *before* the LORD or *in* the LORD, and the preposition is
                # the relation. MACULA puts it first inside a `PrepNp`.
                prep = None
                # a PREDICATE can be a prepositional phrase too — "you are
                # WITH me" (Psa 23:4) — and its preposition is the claim
                if role in ("pp", "adv", "p"):
                    # the phrase's OWN preposition — never one inside a clause
                    # nested in the phrase. Psa 103:3 "[he is] the one who
                    # forgives (to) all your iniquity": the search went down
                    # into the participle clause, took its לְ, and the outer
                    # clause got a predicate "to → all".
                    pw = next((w for w in _iter_no_cl(ch)
                               if w.get("pos") == "preposition"), None)
                    if pw is not None:
                        prep = (pw.get("lemma"), pw.get("gloss"))
                        if pw.get("strongnumberx"):
                            _PREP_STRONG[_nfc(pw.get("lemma"))] = \
                                pw.get("strongnumberx")
                # DIFFERENT PREPOSITIONS ARE DIFFERENT RELATIONS. Psa 103:17
                # "the steadfast love of the LORD is FROM everlasting TO
                # everlasting" (מִן ... עַד) was one role, "from: everlasting
                # and everlasting" — "from everlasting to
                # everlasting" was missing altogether; Isa 15:3 "ON its roofs and IN
                # its squares" likewise (DeepSeek). A coordination of
                # prepositional phrases whose prepositions differ (380 in the
                # Hebrew Bible, mostly "from X to Y") is one role PER PHRASE,
                # each with its own preposition. Not "between A and B" (בֵּין
                # ... לְ / בֵּין ... בֵּין, Gen 1:6): that is one relation.
                if role in ("pp", "adv", "p") and ch.tag == "wg" and \
                        lang == "hebrew":
                    mem_pp = [x for x in ch if x.tag == "wg" and
                              (x.get("rule") or "").startswith("Prep")]
                    preps_ = [next((w for w in x if w.tag == "w" and
                                    w.get("pos") == "preposition"), None)
                              for x in mem_pp]
                    lem_ = [_nfc(p.get("lemma")) if p is not None else ""
                            for p in preps_]
                    if len(mem_pp) >= 2 and len(set(lem_)) > 1 and \
                            _nfc("בֵּין") not in lem_ and \
                            all(p is not None for p in preps_):
                        for m_, p_ in zip(mem_pp, preps_):
                            hw_m = next((w for w in m_.iter("w")
                                         if w.get("pos") != "preposition"),
                                        None)
                            if hw_m is None:
                                continue
                            lm_ = nid(m_)
                            if not lm_ or lm_ not in known:
                                lm_ = f"r{k}{role}{len(roles)}"
                                at_m = _attrs(hw_m)
                                at_m.setdefault("class",
                                                hw_m.get("pos") or "x")
                                nodes.append({
                                    "id": f"{ref}#{lm_}", "ref": ref,
                                    "local": lm_, "lang": lang, **at_m,
                                    **({"w": [_WPOS[id(hw_m)]]}
                                       if id(hw_m) in _WPOS else {}),
                                    "minted_for": "one of coordinated phrases "
                                                  "with different prepositions"})
                                known.add(lm_)
                                minted_lem[lm_] = _nfc(hw_m.get("lemma")) \
                                    or lm_
                            roles.append((role, lm_,
                                          (p_.get("lemma"), p_.get("gloss"))))
                            role_els.append((m_, lm_))
                        stats["pp_split_by_preposition"] += 1
                        continue
                # A PHRASE THAT IS A CLAUSE HAS NO ROLE OF ITS OWN.
                # 2026-09-25, on Exo 8:14 (BSB 8:18): 'gnats' was repeated,
                # and it needs to be in one place or the other. "To [bring forth the gnats]" is a preposition
                # wrapping a clause (PrepCL); "just as [the LORD had said]"
                # one wrapping a relative clause (PpRelp). The nested clause
                # is linked to this one (`within`, or `purpose`), and the role
                # minted from its first noun ("to: gnats", "just: LORD") said
                # the same thing twice, wrongly. First-retrieval fault 6.
                if role != "v" and ch.tag == "wg":
                    inner_ = [c for c in list(ch) if c.tag == "wg"]
                    # only a PREPOSITION wrapping a clause: a role whose
                    # filler is itself a clause (Greek `topic`, `tail`) keeps
                    # its role — the ontology check caught the first draft
                    # dropping those whole
                    # ... or a CLAUSE TURNED INTO A NOUN (CL2NP), bare or under
                    # an article: "[he is] THE ONE WHO forgives all your
                    # iniquity" (Psa 103:3, הַסֹּלֵחַ). 2026-09-26: the
                    # nested assertions were not understandable —
                    # the outer clause's word role was a noun from inside
                    # the nested clause, saying it twice.
                    if _nominal_clause(ch) or (
                            len(inner_) == 1 and inner_[0].get("class") in
                            ("cl", "relp") and
                            (ch.get("rule") or "").startswith(("Prep", "Pp"))):
                        stats["role_is_a_clause"] += 1
                        continue
                local = nid(ch)
                # A COORDINATION IS ONE PARTICIPANT. 2026-09-25, on Exo
                # 8:13 (BSB 8:17): livestock was missing and should be in a
                # collection with humans. "On man and on beast" is PPandPP;
                # the flat layer already mints the composite
                # (`humansandanimals`, members by `member`), but the role took
                # the phrase's first content word. The composite's id is made
                # the same way graphnodes._compose makes it, so it is found.
                # A FOCUS PARTICLE WRAPS THE PHRASE IT FOCUSES.
                # 2026-09-26, on Psa 23:6 "SURELY goodness and mercy will
                # follow me": the subject should be a collection that includes
                # both good/goodness and mercy/covenant loyalty. MACULA
                # wraps the subject as אַךְ + [טוֹב וְחֶסֶד] (AdvpNp over
                # NpaNp); the coordination under the wrapper was not seen,
                # the flat layer never made "goodness" or the pair, and the
                # role took "mercy" alone. Now the phrase inside is read — a
                # coordination becomes its collection, minted if need be (11
                # in the Hebrew Bible) — and the particle, which was dropped
                # in all 299 focus-wrapped roles, hangs on the head as its
                # `focus` qualifier: SURELY [goodness and mercy], ONLY [the
                # high places].
                focus_w = None
                if (ch.get("rule") or "").startswith("Advp"):
                    in_ = [x for x in ch if x.tag == "wg"]
                    # the particle only: an adverb or particle by MACULA's own
                    # class. A first version took any first word, and "day"
                    # (הַיּוֹם, "today"), "worthy" and "how" came out as foci.
                    focus_w = next((x for x in ch if x.tag == "w" and (
                        x.get("class") == "adv"
                        or x.get("pos") in ("particle", "adverb"))
                        and _nfc(x.get("lemma")) != _nfc("יוֹם")), None)
                # ANY ROLE WHOSE FILLER IS A COORDINATION IS ITS COLLECTION,
                # minted if the flat layer never made it. 2026-09-26, on
                # Psa 103:8, "slow to anger and abounding in loving devotion"
                # (אֶרֶךְ אַפַּיִם וְרַב־חֶסֶד): very lacking, basically just
                # saying the Lord is slow and skipping reference to anger and
                # 'great of covenant loyalty' altogether. The predicate was
                # "long" alone — the 23:6 fault without a focus particle.
                c_el = _coord_el(in_[0] if focus_w is not None and
                                 len(in_) == 1 else ch) \
                    if role != "v" and ch.tag == "wg" else None
                cf_ = _coord_local(c_el) if c_el is not None else None
                if True:
                    if cf_ and cf_ not in known:
                        from graphnodes import CONTENT as _CONTENT  # noqa
                        mem_ = []
                        for x in c_el:
                            if not (x.tag == "wg" or (x.tag == "w" and
                                                      _pos(x) in _CONTENT)):
                                continue
                            ml_ = _member_local(x)
                            hel_ = x
                            if x.tag == "wg" and \
                                    x.get("rule") in ("NPofNP", "AdjpofNp"):
                                hel_ = next((c for c in x if c.tag == "wg" or
                                             (c.tag == "w" and
                                              _pos(c) in _CONTENT)), x)
                            hx_ = head_word(hel_) if hel_.tag == "wg" \
                                else hel_
                            if not ml_ or hx_ is None:
                                continue
                            if ml_ not in known:
                                at_m = _attrs(hx_)
                                at_m.setdefault("class", hx_.get("pos") or "x")
                                nodes.append({
                                    "id": f"{ref}#{ml_}", "ref": ref,
                                    "local": ml_, "lang": lang, **at_m,
                                    **({"w": [_WPOS[id(hx_)]]}
                                       if id(hx_) in _WPOS else {}),
                                    "minted_for": "a member of a coordination "
                                                  "the flat layer did not make"})
                                known.add(ml_)
                                minted_lem[ml_] = _nfc(hx_.get("lemma")) or ml_
                            mem_.append(ml_)
                        if len(mem_) >= 2:
                            nodes.append({"id": f"{ref}#{cf_}", "ref": ref,
                                          "local": cf_, "lang": lang,
                                          "composite": True,
                                          "minted_for": "a coordination the "
                                                        "flat layer did not "
                                                        "make"})
                            for ml_ in mem_:
                                edges.append({"ref": ref, "lang": lang,
                                              "type": "member",
                                              "src": f"{ref}#{cf_}",
                                              "dst": f"{ref}#{ml_}"})
                            known.add(cf_)
                            stats["coordination_minted"] += 1
                # (each member's own phrase — "slow OF ANGER" — is walked by
                # _qualify, which treats a coordination as no member's head)
                comp_ = cf_ or _coord_local(ch)
                if comp_ and comp_ in known:
                    local = comp_
                    stats["role_to_collection"] += 1
                else:
                    # A QUANTIFIER IS NOT THE HEAD. 2026-09-25, on Exo
                    # 8:13 (BSB 8:17): the subject of 'all' looked wrong.
                    # כָּל־עֲפַר הָאָרֶץ is "all of the dust of the earth": MACULA
                    # tags כָּל a noun, so it was the phrase's first noun and
                    # the role's head — and the verse's two "all"s (the dust,
                    # the land of Egypt) shared one node. The head is the noun
                    # the quantifier governs (QuanNP's second child); "all"
                    # becomes its `quantity` qualifier.
                    qh_ = _quant_head(ch)
                    ql_ = nid(qh_) if qh_ is not None else None
                    if ql_ and ql_ != local and ql_ not in known:
                        # the flat layer named the whole phrase by its
                        # quantifier, so the head never got a node ("in all
                        # the land of Egypt" had only "all"): mint it
                        hw_q = head_word(qh_)
                        if hw_q is not None:
                            at_q = _attrs(hw_q)
                            at_q.setdefault("class", hw_q.get("pos") or "x")
                            nodes.append({
                                "id": f"{ref}#{ql_}", "ref": ref,
                                "local": ql_, "lang": lang, **at_q,
                                **({"w": [_WPOS[id(hw_q)]]}
                                   if id(hw_q) in _WPOS else {}),
                                "minted_for": "the head a quantifier "
                                              "governs"})
                            known.add(ql_)
                            minted_lem[ql_] = _nfc(hw_q.get("lemma")) or ql_
                            stats["role_head_minted"] += 1
                    if ql_ and ql_ in known and ql_ != local:
                        local = ql_
                        stats["role_quantity_to_head"] += 1
                if focus_w is not None and role != "v" and local and \
                        local in known:
                    fl_ = nid(focus_w) or _nfc(focus_w.get("lemma"))
                    if fl_ and fl_ != local:
                        if fl_ not in known:
                            at_f = _attrs(focus_w)
                            at_f.setdefault("class", focus_w.get("pos") or "x")
                            nodes.append({
                                "id": f"{ref}#{fl_}", "ref": ref,
                                "local": fl_, "lang": lang, **at_f,
                                **({"w": [_WPOS[id(focus_w)]]}
                                   if id(focus_w) in _WPOS else {}),
                                "minted_for": "a focus particle"})
                            known.add(fl_)
                        edges.append({"ref": ref, "lang": lang,
                                      "type": "qualifier", "rel": "focus",
                                      "src": f"{ref}#{local}",
                                      "dst": f"{ref}#{fl_}",
                                      "clause_role": True, "clause_order": k})
                        stats["focus_qualifier"] += 1
                if role == "v":
                    # THE VERB IS ITS VERB NODE, never also the word. Where the
                    # word already had a node (an infinitive or participle the
                    # flat layer names — Gen 1:22 לֵאמֹר "saying"), it was
                    # added here as well: 7,653 contents with two `v` edges,
                    # one to a plain Word. Found 2026-09-25 by checking edges
                    # against their relation's declared from → to (plan N.1).
                    continue
                if local and local in known:
                    roles.append((role, local, prep))
                    role_els.append((ch, local))
                else:
                    # A ROLE WHOSE FILLER HAS NO NODE GETS ONE. Psalm
                    # 23:1's missing "not" found the first of these;
                    # counting them found 23,665 — 8% of all role fillers:
                    # 10,882 prepositional phrases (a preposition with a
                    # suffix, "with ME", has no node, so 23:4's "you are with
                    # me" lost its predicate), 7,493 adverbials, 2,462 Greek
                    # copulas. The head word is minted from MACULA's own word
                    # — for a prepositional phrase the word after the
                    # preposition, which stays on the edge. Negatives are
                    # skipped: they have their own `neg` role. A nested
                    # clause in the role is `within`, not a word.
                    kind_ = (ch.get("class") or ch.get("pos") or "?")
                    if ch.tag == "wg" and ch.get("class") == "cl":
                        stats[f"role_dropped:{role}:clause"] += 1
                        continue
                    ws_r = [ch] if ch.tag == "w" else list(ch.iter("w"))
                    hw_r = next((w for w in ws_r
                                 if w.get("pos") != "preposition"
                                 and w.get("type") != "negative"
                                 and _nfc(w.get("lemma")) not in NEG_GREEK),
                                None)
                    if hw_r is None:
                        stats[f"role_dropped:{role}:{kind_}"] += 1
                        continue
                    loc_r = f"r{k}{role}{len(roles)}"
                    at_r = _attrs(hw_r)
                    at_r.setdefault("class", hw_r.get("pos") or "x")
                    nodes.append({"id": f"{ref}#{loc_r}", "ref": ref,
                                  "local": loc_r, "lang": lang,
                                  **at_r,
                                  **({"w": [_WPOS[id(hw_r)]]}
                                     if id(hw_r) in _WPOS else {}),
                                  "minted_for": "a role with no node"})
                    known.add(loc_r)
                    # a pronoun SUFFIX is keyed by its gloss: MACULA gives
                    # every suffix the lemma הוּא whatever its person, so
                    # "you are with ME" (Psa 23:4) keyed as "with HIM"
                    minted_lem[loc_r] = (
                        (hw_r.get("gloss") or "").strip().lower()
                        if hw_r.get("pos") == "suffix"
                        else _nfc(hw_r.get("lemma"))) or loc_r
                    roles.append((role, loc_r, prep))
                    role_els.append((ch, loc_r))
                    stats["role_filler_minted"] += 1
            conn = c.get("_connective")
            crec = {
                "id": cid, "ref": ref, "lang": lang, "local": f"cl{k}",
                "clause": True, "order": k, "rule": c.get("rule"),
                "text": " ".join((w.get("gloss") or "") for w in cw)[:90],
                # WHICH WORDS: 0-based positions in the verse, in document
                # order (the interlinear's order) — what a reader clicking the
                # clause is shown in the Hebrew. A clause was located only by
                # its glosses until 2026-09-25.
                "w": sorted({_WPOS[id(w)] for w in cw if id(w) in _WPOS}),
                **{a: b for a, b in (("verb_lemma", vlem), ("verb_mood", vmood),
                                     ("verb_stem", vstem),
                                     ("verb_person", vperson),
                                     ("connective", conn),
                                     ("fronted", bool(c.get("_fronted"))),
                                     ("relative", bool(c.get("_relative"))),
                                     ("scope", c.get("_scope")),
                                     ("connective_sense",
                                      CONNECTIVE.get(_nfc(conn)))) if b}}
            # KEPT BY REFERENCE, NOT BY SLICING THE TAIL OF `nodes`. The
            # clause list used to be recovered as `nodes[-len(cls):]`, which
            # was true until verb nodes started being appended in the same
            # loop — and then every clause-to-clause edge silently pointed at
            # a VERB instead of a clause. Psalm 107:1's two `because` edges
            # landed on `cl0v`.
            # THE MEANING-LAYER FORCE, from the ontology's own mapping of
            # form to force (ontology/kinds.json → forces), so a Hebrew and a
            # Greek clause meet at "assertion" and the build cannot drift from
            # the declaration. 2026-09-25: the ontology still labelled
            # assertion as proposed, though it was past that.
            crec["upper_force"] = _upper_force(lang, vmood)
            nodes.append(crec)
            cinfo.append(crec)
            # `next`: text order, across verses. An ORDERING link, flagged
            # `order_link` and NOT `clause_link`, so no rule that follows
            # clause relations walks along it and no clause counts as joined
            # because of it — every clause is next to something.
            if last_clause is not None:
                edges.append({"ref": ref, "lang": lang, "type": "next",
                              "src": last_clause, "dst": cid,
                              "order_link": True})
            last_clause = cid
            stats["clauses"] += 1
            if vmood:
                stats["clause_with_mood"] += 1
            # THE VERB IS A NODE, NOT ONLY AN ATTRIBUTE. 2026-09-21,
            # starting from one clause, 'give thanks to the lord'. It rendered as the clause and its prepositional
            # phrase with the verb nowhere on the diagram — because the verb
            # lived as `verb_lemma` on the clause and a string cannot be
            # pointed at.
            #
            # His own model had it as a member from the start: *"a command
            # node 'be light' which has tuple relationships with the command
            # 'be' and the object 'light'."* The command IS one of the parts.
            # Minting it also gives the morphology somewhere fuller to sit
            # than four fields on the parent.
            # ---- CONTENT IS THE LOWEST GROUPING ---------------------------
            #
            # 2026-09-21, after narrowing to one clause and then one word,
            # 'thanks to the lord', and then decisively: 'thanks to the Lord'
            # is the lowest-level grouping.
            #
            # So the bottom of the ladder is the PREDICATE WITH ITS
            # PARTICIPANTS, and the mood is a FORCE APPLIED TO IT rather than
            # part of it. "Give thanks to the LORD" is the imperative force
            # over the content *thanks-to-the-LORD*; "they gave thanks to the
            # LORD" is a report over the same content.
            #
            # That is what makes an action-state pair general instead of a
            # coincidence. Matching lemmas gives 197 command->report pairs in
            # a verse; matching CONTENT gives the 55 that are really the same
            # act, and exposes the deixis shift that proves it — Exodus 4:6's
            # "put hand YOUR in bosom your" answered by "he.put hand HIS in
            # bosom his". One referent, two persons, because the speaker
            # changed. Invisible when matching lemmas.
            #
            # `key` is the comparable signature and deliberately excludes the
            # mood, since two clauses sharing a key differ only in force.
            ctid = f"{ref}#ct{k}"
            sig = []
            if vword is not None:
                vid = f"{cid}v"
                nodes.append({
                    "id": vid, "ref": ref, "lang": lang,
                    "local": f"cl{k}v", "verb": True,
                    "text": _text(vword), "lemma": vlem,
                    "word_ref": vword.get("ref"),
                    **({"w": [_WPOS[id(vword)]]} if id(vword) in _WPOS
                       else {}),
                    **{a: b for a, b in (
                        ("mood", vmood), ("stem", vstem), ("person", vperson),
                        ("gender", vword.get("gender")),
                        ("number", vword.get("number")),
                        ("strong", vword.get("strong")
                         or vword.get("strongnumberx"))) if b}})
                edges.append({"ref": ref, "lang": lang, "type": "v",
                              "src": ctid, "dst": vid, "clause_role": True})
                stats["verb_nodes"] += 1
                stats["clause_role_edges"] += 1
                sig.append(f"v={_nfc(vlem)}")

            for role, local, prep in roles:
                # remembered on the clause so the narrative window can read it
                # back without re-walking the edges
                if role == "s":
                    crec["speaker"] = f"{ref}#{local}"
                rec = {"ref": ref, "lang": lang, "type": role,
                       "src": ctid, "dst": f"{ref}#{local}",
                       "clause_role": True}
                if prep and prep[0]:
                    rec["prep"] = prep[0]
                    if prep[1]:
                        rec["prep_gloss"] = prep[1]
                edges.append(rec)
                stats["clause_role_edges"] += 1
                lem = (g.get("lemmas") or {}).get(local) \
                    if isinstance(g.get("lemmas"), dict) else None
                # a minted filler is keyed by its lemma like any other; keyed
                # by its made-up local id, "you are with me" came out p=r2p1
                part = lem or minted_lem.get(local) or local
                f_ = facts.setdefault(cid, {"stem": vstem})
                if role == "s":
                    f_["subj"] = _nfc(part)
                elif role == "o":
                    f_.setdefault("obj", _nfc(part))
                elif role == "pp" and prep and prep[1] == "to":
                    f_.setdefault("to", _nfc(part))
                sig.append(f"{role}{':' + _nfc(prep[0]) if prep and prep[0] else ''}"
                           f"={part}")

            # ---- HEAD AND QUALIFIER, inside each role's phrase ----------
            # 2026-09-25: assertion 3 lacked green as a modifier on
            # pastures. "He makes me lie down in green pastures" is בִּנְאוֹת
            # דֶּשֶׁא, "in pastures OF GRASS": the role held "pastures" and the
            # rest of its phrase was thrown away. Queue item 4, and the
            # rule from Psalm 107:1 — the primary node in the object is
            # thanks and 'to the Lord' is the qualifier. So each role's
            # phrase is walked down from its head, and each dependent MACULA
            # attaches is a `qualifier` of its head, typed by how:
            #   of         NPofNP    pastures -of-> grass
            #   attribute  NpAdjp    a heart -attribute-> clean
            #   prep       NpPp      the waters -prep: of-> rest
            #   quantity   QuanNP    all -> the earth  (head: the earth)
            #   number     NumpNP / NpNump   seven -> years
            # The content KEY stays the heads: qualifiers hang off them.
            for el_, loc_ in role_els:
                _qualify(el_, loc_, ref, lang, k, known, nodes, edges,
                         minted_lem, stats)

            # NEGATION IS PART OF WHAT A CLAUSE SAYS. 2026-09-25, on
            # Psalm 23:1: the 'not' or 'nothing' was not represented.
            # "I shall not want" (לֹא אֶחְסָר) was held as content `v=חָסֵר` —
            # "I lack" — because MACULA gives לֹא the role `adv` on a bare
            # word, the build made no node for it, and the role edge fell out
            # with nothing to point at. So every negated clause had the same
            # content key as its affirmation. The negative now enters the key
            # BY LEMMA — לֹא "not", אַל "do not" (a prohibition), אַיִן "there
            # is no" are not the same thing — and gets a node, hanging off
            # the content as `neg`. Only the clause's own words: a negative
            # inside a nested clause is that clause's.
            negs = [w for w in cw if id(w) not in inner_w[id(c)]
                    and (w.get("type") == "negative"
                         or _nfc(w.get("lemma")) in NEG_GREEK)]
            polarity = None
            for j, nw in enumerate(negs):
                polarity = "negative"
                nlem = _nfc(nw.get("lemma"))
                sig.append(f"neg={nlem}")
                nloc = f"not{k}" + (f"_{j}" if j else "")
                nodes.append({
                    "id": f"{ref}#{nloc}", "ref": ref, "lang": lang,
                    "local": nloc, "text": (nw.get("gloss") or "not"),
                    "lemma": nw.get("lemma"),
                    "strong": nw.get("strongnumberx") or nw.get("strong"),
                    "pos": nw.get("pos") or "particle", "class": "adv",
                    "type": "negative", "word_ref": nw.get("ref"),
                    **({"w": [_WPOS[id(nw)]]} if id(nw) in _WPOS else {})})
                edges.append({"ref": ref, "lang": lang, "type": "neg",
                              "src": ctid, "dst": f"{ref}#{nloc}",
                              "clause_role": True})
                stats["negations"] += 1

            # ---- A CAUSATIVE WRAPS THE EVENT IT CAUSES ----------------
            # 2026-09-25, on Psalm 23:2: assertion 3 needs to wrap "me
            # lying down in green pastures" with 'He makes me'; there was a
            # layer missing. יַרְבִּיצֵנִי is ONE verb in the causative stem
            # (hiphil) of "lie down": he CAUSES — me to lie down in green
            # pastures. Two events, and the object of the causing is the
            # subject of the caused. So: an INNER content — the object as its
            # subject, the places and manner (pp, adv, p) moved in with it —
            # and the outer content keeps the causer and the verb, with
            # `causes` to the inner. Only where the root ALSO occurs in the
            # plain stem (qal): "strike" (הִכָּה) and "save" (הוֹשִׁיעַ) exist
            # only as hiphil and have no plain event to wrap.
            qo, qn = _QAL_OBJ.get(_nfc(vlem), (0, 0)) if vlem else (0, 0)
            causative = (lang == "hebrew" and vstem == "hiphil" and vlem
                         and "qal" in _STEMS.get(_nfc(vlem), ())
                         # the plain verb is intransitive: seen in qal at
                         # least 3 times, with an object under a third of them
                         and qn >= 3 and qo / qn < 0.33
                         and any(e.get("src") == ctid and e.get("type") == "o"
                                 for e in edges[ce0:]))
            if causative:
                ict = f"{ref}#ct{k}c"
                isig, osig = [f"v={_nfc(vlem)}"], []
                for tok in sig:
                    head_ = tok.split("=", 1)[0].split(":", 1)[0]
                    if head_ == "o":
                        isig.append("s=" + tok.split("=", 1)[1])
                    elif head_ in ("pp", "adv", "p", "o2"):
                        isig.append(tok)
                    else:
                        osig.append(tok)            # v, s, neg stay outside
                osig.append("causes")
                for e in edges[ce0:]:
                    if e.get("src") == ctid and e.get("clause_role") and \
                            e.get("type") in ("o", "pp", "adv", "p", "o2"):
                        e["src"] = ict
                        if e["type"] == "o":
                            e["type"] = "s"          # the caused actor
                            e["from_object"] = True
                if vword is not None:
                    edges.append({"ref": ref, "lang": lang, "type": "v",
                                  "src": ict, "dst": f"{cid}v",
                                  "clause_role": True})
                    # THE CAUSING HAS ITS OWN PREDICATE. 2026-09-25:
                    # assertion 3 still looked like the Lord was lying down —
                    # the outer content pointed at the same verb node, "lie
                    # down", with "he" as its subject. The outer predicate is
                    # MAKES; the verb node, "lie down", is the inner event's.
                    for e in edges[ce0:]:
                        if e.get("src") == ctid and e.get("type") == "v":
                            e["dst"] = f"{cid}vc"
                    nodes.append({"id": f"{cid}vc", "ref": ref, "lang": lang,
                                  "local": f"cl{k}vc", "verb": True,
                                  "causative": True, "text": "makes",
                                  "lemma": vlem, "stem": vstem,
                                  **({"mood": vmood} if vmood else {}),
                                  "gloss": f"makes — causes to "
                                           f"{_text(vword)}"})
                edges.append({"ref": ref, "lang": lang, "type": "causes",
                              "src": ctid, "dst": ict, "clause_role": True})
                nodes.append({
                    "id": ict, "ref": ref, "lang": lang,
                    "local": f"ct{k}c", "content": True, "order": k,
                    "caused": True,
                    # THE EFFECT. 2026-09-25: in the causes node,
                    # 'Me lying down' is called the effect. Named here, not
                    # withheld as at Genesis 1:3, because the stem STATES the
                    # causation — the hiphil is the grammar of "cause to".
                    "role": "effect",
                    "text": " ".join((w.get("gloss") or "") for w in cw)[:90],
                    "key": " ".join(sorted(isig))})
                sig = osig
                stats["causatives_wrapped"] += 1

            nodes.append({
                "id": ctid, "ref": ref, "lang": lang, "local": f"ct{k}",
                "content": True, "order": k,
                "text": " ".join((w.get("gloss") or "") for w in cw)[:90],
                **({"polarity": polarity} if polarity else {}),
                "key": " ".join(sorted(sig))})
            # `asserts`, not `content`: `content` is already the edge from a
            # speech verb to the clause that is what was said, and two
            # different relations under one name is how a vocabulary starts
            # lying. This one is force-over-content.
            edges.append({"ref": ref, "lang": lang, "type": "asserts",
                          "src": cid, "dst": ctid, "force": vmood or "-",
                          "upper": _upper_force(lang, vmood),
                          "clause_role": True})
            stats["content_nodes"] += 1

        # ---- a clause inside another clause's role ---------------------
        # "You refuse [to let them go]" (Exo 7:27): the infinitive clause is
        # the OBJECT of refusing, and MACULA nests it there. `within` runs
        # from the enclosing clause to the one inside it and carries the role
        # it fills, so the refusal reads as one condition with its object,
        # not two pieces of a speech. Relative clauses ("the frogs WHICH HE
        # HAD BROUGHT") land here too, inside the noun phrase's role; what
        # kind of inside it is — object, modifier — is the role's to say.
        kof = {id(c): k for k, c in enumerate(cls)}
        for k, c in enumerate(cls):
            w = _WITHIN.get(id(c))
            if not w or id(w[0]) not in kof:
                continue
            rec = {"ref": ref, "lang": lang, "type": "within",
                   "src": f"{ref}#cl{kof[id(w[0])]}", "dst": f"{ref}#cl{k}",
                   "clause_link": True}
            if w[1]:
                rec["role"] = w[1]
            if w[2] and w[2][0]:
                rec["prep"] = w[2][0]
                if w[2][1]:
                    rec["prep_gloss"] = w[2][1]
            # לְ + INFINITIVE IS PURPOSE. On Exo 8:14: why is "bring
            # forth the gnats" in a `within` relationship? "They did so by
            # their secret arts TO BRING FORTH the gnats" — לְהוֹצִיא is the
            # standard Hebrew purpose construction: what the doing aimed at.
            # (The BSB's "tried to produce" folds it into the verb; the
            # Hebrew verb is plain "did".) So the link is `purpose`, the
            # role kept on the edge.
            vw_ = next((x for x in list(c) if x.get("role") == "v"), None)
            hv_ = head_word(vw_) if vw_ is not None else None
            # ... but only where it IS purpose. Measured over the 4,503 it
            # first caught: after a verb of ability, repetition, beginning,
            # finishing, willing, refusing, seeking, knowing how, the
            # infinitive is WHAT is done, not why ("if you refuse TO LET THEM
            # GO", Exo 7:27 — the suite's own row caught it); לֵאמֹר "saying"
            # only opens a quotation; a verbless main clause or הָיָה ("it
            # was to ...") and נָתַן ("allow" or "give ... to eat") are not
            # settled by form. And only the prepositional role: a subject or
            # predicate clause ("not good for the man to be alone") is not
            # an aim. These are word facts, hand-listed until the word graph
            # holds them (plan 2.6). MEASURED, blind, by two DeepSeek runs
            # that agreed case for case: 10 of 16 right; three misses were a
            # speech or intention verb ("Solomon purposed TO BUILD", "the
            # LORD had said", "warn ... not to sin") — the infinitive is what
            # was said — so speech verbs and "warn" are excluded too (10 of
            # 13 on that sample). The three left explain HOW ("dealt
            # wondrously", "judge ... by bringing down"): meaning, not form.
            wv_ = next((x for x in list(w[0]) if x.get("role") == "v"), None)
            mv_ = head_word(wv_) if wv_ is not None else None
            main_lem = _nfc(mv_.get("lemma")) if mv_ is not None else None
            if lang == "hebrew" and _nfc(rec.get("prep")) == _nfc("לְ") \
                    and hv_ is not None \
                    and hv_.get("type") == "infinitive construct" \
                    and w[1] == "pp" and main_lem \
                    and main_lem not in _COMPLEMENT_VERBS \
                    and main_lem not in {_nfc(x) for x in SPEECH} \
                    and main_lem != _nfc("זָהַר") \
                    and _nfc(hv_.get("lemma")) != _nfc("אָמַר"):
                rec["type"] = "purpose"
                rec["evidence"] = "לְ + infinitive construct"
                stats["purpose_infinitive"] += 1
            # "JUST AS": כְּ (+ אֲשֶׁר) before a clause compares the action to
            # it. 2026-09-25, on Exo 8:15 (BSB 8:19): "just as the LORD
            # had said" seemed sparse, with nothing tying it to the prior;
            # 'just as' is the hook. Where what follows is a SAYING, the text is
            # declaring this action the fulfilment of an earlier word.
            elif _nfc(rec.get("prep")) == _nfc("כְּ") and w[1] == "pp":
                rec["type"] = "as"
                rec["evidence"] = "כְּ / כַּאֲשֶׁר before a clause"
                inner_lem = _nfc(hv_.get("lemma")) if hv_ is not None else ""
                if inner_lem in {_nfc(x) for x in SPEECH}:
                    rec["as_said"] = True
                    stats["as_said"] += 1
                stats["as_link"] += 1
            # "UNTIL": עַד before a clause is a LIMIT on the clause it sits
            # in, not a place inside it. 2026-09-26, on 2Ch 36:20 "they
            # became slaves to him and his sons UNTIL the kingdom of Persia
            # reigned": 'until' is not 'within', but a limit on slavery
            # to Nebuchadnezzar and his sons. DeepSeek's audit found it.
            elif _nfc(rec.get("prep")) == _nfc("עַד") and w[1] == "pp":
                # not "until": the flat layer has an edge of that name (the
                # build's clash check caught it on the first run)
                rec["type"] = "until_limit"
                rec["evidence"] = "עַד before a clause"
                stats["until_link"] += 1
            edges.append(rec)
            stats["clause_within"] += 1

        # ---- what a speech verb said, and ordered action/state pairs -----
        #
        # Both are clause-to-clause relations, and neither was expressible
        # until a clause became a node. 2026-09-21: then
        # God->said->'be light' gets easy.

        # WHAT THE CONJUNCTION SAYS, AS AN EDGE. Psalm 107:1 is "give thanks
        # to the LORD" and then two clauses each introduced by כִּי — the text
        # states its own reason twice and the graph held neither. The edge
        # runs from the clause that GIVES the reason to the one it supports,
        # so `because` points the way it reads.
        # a clause nested inside another is a part of it, never the clause a
        # condition or concession governs
        within_dst = {e["dst"] for e in edges[vstart:]
                      if e.get("type") == "within"}
        for k, n in enumerate(cinfo):
            sense = n.get("connective_sense")
            if not sense:
                continue
            # A CONDITION GOVERNS WHAT FOLLOWS IT. `if` was attached like
            # `because`, to the clause before — and when "if you refuse to let
            # them go" OPENS Exodus 7:27 there is no clause before, so no edge
            # was made and the threat it conditions, "I am about to strike
            # your territory", was left an orphan. A Hebrew protasis precedes
            # its apodosis, so the host is the next clause that is not an
            # infinitive complement ("to let them go") and not another `if`;
            # the clause before, where there is one, is kept as alt_host.
            # A CONCESSION DOES THE SAME: "even though I walk through the
            # valley ..., I will fear no harm" (Psa 23:4) — the concession
            # comes first and qualifies what follows it.
            # A FRONTED כִּי IS A SETTING, not a reason: "(though) they fast, I
            # will not listen" (Jer 14:12), "(when) you pass through the
            # waters, I will be with you". It governs the clause after it —
            # when, if or though; the Hebrew does not say which, so the link
            # does not either. See _fronted_at.
            #
            # MID-VERSE ONLY. A כִּי that OPENS a verse looks fronted too —
            # nothing before it in the verse — but the build reads a verse at
            # a time, and most of those are "FOR this is what the LORD says",
            # the reason for the verse BEFORE. Built for both, a sample of 12
            # was 3 right; mid-verse alone (23) reads right: "even if I give
            # you advice, you will not listen" (Jer 38:15). A verse-opening
            # כִּי stays unlinked, as it was, and is counted. The id is not
            # "setting": the superseded flat layer names edges after verbs,
            # and "I am setting before you" (Deu 11:26) is one.
            if sense == "because" and n.get("fronted") and k == 0:
                stats["fronted_ki_verse_initial_held"] += 1
            fwd = sense in ("if", "though") or \
                (sense == "because" and n.get("fronted") and k > 0)
            ftype = "when_if_though" if sense == "because" else sense
            if fwd:
                # A NARRATIVE "AND THEN" IS NEVER A CONDITION'S CONSEQUENCE.
                # Gen 15:5: "count the stars, IF you are able to count them"
                # — the next clause is the narrator's "and he said to him",
                # outside the quotation, and was taken as the consequence. At
                # a wayyiqtol the search stops, and the condition trails the
                # clause before it.
                stop_ = next((j for j in range(k + 1, len(cinfo))
                              if cinfo[j].get("verb_mood") == "wayyiqtol"),
                             len(cinfo))
                nxt = next((j for j in range(k + 1, stop_)
                            if not (cinfo[j].get("verb_mood") or "")
                            .startswith("infinitive")
                            and cinfo[j].get("connective_sense") != sense
                            and cinfo[j]["id"] not in within_dst
                            # not a clause of the condition's own unit
                            and not (n.get("scope") and
                                     cinfo[j].get("scope") == n.get("scope"))),
                           None)
                if nxt is not None:
                    sense = ftype
                    rec = {"ref": ref, "lang": lang, "type": sense,
                           "src": cinfo[nxt]["id"], "dst": n["id"],
                           "connective": n.get("connective"),
                           "clause_link": True}
                    # a fronted כִּי was placed by the tree itself (nothing
                    # clausal before it in its unit), so the clause before it
                    # is no alternative host
                    if k > 0 and sense != "when_if_though":
                        rec["alt_host"] = [cinfo[k - 1]["id"]]
                        rec["ambiguous"] = True
                        stats["ambiguous_attachment"] += 1
                    edges.append(rec)
                    stats[f"connective_{sense}"] += 1
                    stats[f"{sense}_forward"] += 1
                    stats["connective_edges"] += 1
                    continue
            if k == 0:
                continue
            # attach to the nearest preceding clause that is NOT itself
            # introduced by the same connective, so a run of `for … for …`
            # hangs off the statement both are supporting rather than
            # chaining through each other
            # WHICH CLAUSE IT ATTACHES TO IS NOT ALWAYS STATED.
            # 2026-09-21, on Psalm 107:1: the tricky thing is that the second
            # 'for' actually gives the basis for the declaration that God is
            # good.
            #
            # That reading is available, and MACULA does not
            # settle it: the two כִּי clauses are SIBLINGS under one `ClCl`
            # parent, not nested. So "both ground the imperative" and "the
            # second grounds the first" are both readings, and the earlier
            # version of this line silently chose the first by skipping back
            # past same-connective clauses.
            #
            # THE DEFAULT IS THE NEAREST CLAUSE, which is the held reading:
            # it is the logical reading when thought through.
            # "He is good" is the claim; "his steadfast love endures forever"
            # is how one would know it. A reason attaches to what it is
            # nearest unless something says otherwise, and nothing here does.
            #
            # This is a judgement, not a derivation, and it is made by hand —
            # so the OTHER candidate is kept on the edge rather than thrown
            # away. 162 attachments in the corpus are ambiguous this way, and
            # a layer that reads them the other way has what it needs.
            near = k - 1
            # NOT A RELATIVE CLAUSE. The nearest clause can be a relative
            # clause inside the one it qualifies — "we will not give them any
            # of the spoil [which we recovered], BUT RATHER to each his wife"
            # (1Sa 30:22): the "but" answers the main clause. Found by
            # DeepSeek's blind judging, 3 of 21 contrast / but-rather links
            # (Jdg 18:29, 1Sa 30:22, Num 35:33), none of which Claude had
            # marked. WRONG TURN, same day: skipping EVERY nested clause
            # moved 2,894 links, and a sample of moved "and" was 4 of 8
            # worse — it pulled clauses out of the speech they continue
            # ("who says of Cyrus, 'my shepherd, AND he will fulfil all my
            # desire'", Isa 44:28). Only a relative clause is skipped.
            while near > 0 and cinfo[near].get("relative") and \
                    cinfo[near]["id"] in within_dst:
                near -= 1
            if near != k - 1:
                stats["backward_host_skipped_nested"] += 1
            alts = [cinfo[j]["id"] for j in range(k - 1, -1, -1)
                    if cinfo[j].get("connective_sense") != sense][:1]
            head = near
            # THE EDGE RUNS FROM WHAT IS EXPLAINED TO ITS REASON.
            # 2026-09-21, reading the diagram back as a sentence: looking at
            # just the basics for 107:1, he is not good because we give
            # thanks.
            #
            # Exactly. The first version pointed from the subordinate clause
            # to its host, so the edge read `he.is.good --because--> give
            # thanks` — God is good BECAUSE we thank him, which is the reverse
            # of what the verse says and of what anyone believes. The comment
            # on that line even claimed it "points the way it reads"; it
            # pointed the way it does not.
            #
            # `X --because--> Y` now reads "X because Y", which is how every
            # one of these conjunctions works: *give thanks BECAUSE he is
            # good*, *do this LEST that*, *X IF Y*. The subordinate clause is
            # the destination because it is what the main clause leans on.
            host = cinfo[head]
            etype = sense
            # כִּי AFTER A VERB OF KNOWING, SEEING, HEARING OR SAYING IS "THAT":
            # the clause is what is known, not a reason. The edge still runs
            # host → clause, and now reads "you may know — that there is no
            # one like the LORD".
            if sense == "because" and \
                    _nfc(host.get("verb_lemma") or "") in perceive:
                etype = "that"
            # A VOLITIVE, THEN WAW + JUSSIVE / COHORTATIVE / YIQTOL, IS
            # PURPOSE: "let my people go, that they may serve me" (Exo 7:26).
            # Emitted as plain `and` until now. Two limits, both from the frog
            # plague: the person must change (a command to "you", a result
            # for "them"), and a cohortative after a jussive is excluded —
            # Pharaoh's "that he may remove the frogs, AND I WILL let the
            # people go" (8:4) is a promise, not a purpose.
            if sense == "and" and host.get("verb_mood") in COMMAND and \
                    n.get("verb_mood") in ("jussive", "cohortative",
                                           "yiqtol") and \
                    n.get("verb_person") != host.get("verb_person") and \
                    not (n.get("verb_mood") == "cohortative"
                         and host.get("verb_mood") == "jussive"):
                etype = "purpose"
            rec = {"ref": ref, "lang": lang, "type": etype,
                   "src": host["id"], "dst": n["id"],
                   "connective": n.get("connective"),
                   "clause_link": True}
            if etype != sense:
                stats[f"reclassified_{sense}_as_{etype}"] += 1
            if alts and alts[0] != cinfo[head]["id"]:
                rec["alt_host"] = alts
                rec["ambiguous"] = True
                stats["ambiguous_attachment"] += 1
            edges.append(rec)
            stats[f"connective_{sense}"] += 1
            stats["connective_edges"] += 1

        # THE CONSEQUENCE IS NOT "AND" TO ITS OWN CONDITION. Exo 4:8's "then
        # they will believe the second sign" opens with the apodosis waw, and
        # was joined by "and" to the second condition, beside the "if" that
        # now governs it. DeepSeek: "replace cl2—and→cl3 with cl3—if→cl1".
        scope_of = {c["id"]: c.get("scope") for c in cinfo}
        conds = [(e["src"], e["dst"]) for e in edges[vstart:]
                 if e.get("clause_link") and
                 e.get("type") in ("if", "though", "when_if_though")]
        drop_and = set()
        for host, cond in conds:
            sc = scope_of.get(cond)
            for e in edges[vstart:]:
                if e.get("type") == "and" and e.get("clause_link") and \
                        e.get("dst") == host and (e.get("src") == cond or (
                            sc and scope_of.get(e.get("src")) == sc)):
                    drop_and.add(id(e))
        if drop_and:
            edges[vstart:] = [e for e in edges[vstart:]
                              if id(e) not in drop_and]
            stats["and_into_consequence_dropped"] += len(drop_and)

        for k, n in enumerate(cinfo):
            if n.get("verb_lemma") in SPEECH and k + 1 < len(cinfo):
                # THE THING SAID IS THE NEXT CLAUSE. `[S] said` carried no
                # object across 4,892 instances and that was faithful --
                # MACULA's `V-S` over *he.said · God* has no object role,
                # because the content is the sibling that follows.
                edges.append({"ref": ref, "lang": lang, "type": "content",
                              "src": n["id"], "dst": cinfo[k + 1]["id"],
                              "clause_link": True})
                stats["speech_content"] += 1

        # AN ORDERED PAIR, AND ORDER IS THE CONTENT. Order does matter
        # with this pattern, so it is more than just a pair. A jussive
        # followed by a wayyiqtol OF THE SAME LEMMA is a command reported as
        # having happened. Reversed it would be an act followed by a command
        # to do it, so the members carry positions rather than only names.
        #
        # NOT called cause and effect. Pulling back a first reading: the
        # call that 'and' implies cause and effect was an inference; it might
        # start as a simple pair until inferring such relationships is
        # reliable. Action then state is what is observable; causation
        # is a specialization that attaches to this node later.
        # ---- who is speaking: NOT INFERRED, and here is why -----------
        #
        # 2026-09-21, on Exodus 8:6 having two speeches and no speakers:
        # Pharaoh spoke and Moses responded, and narratives really need
        # to be taken in order to have context. Both true, and the context
        # is genuinely there — 8:4 names Pharaoh and 8:5 names Moses.
        #
        # Alternation inside an established exchange was built, tightened
        # twice, and removed. It kept getting the motivating verse wrong:
        #
        #     Exo 8:4 cl0  he.summoned Pharaoh…   pharaoh   stated
        #     Exo 8:4 cl1  he.said                LORD      inferred   WRONG
        #     Exo 8:6 cl0  he.said                LORD      inferred   WRONG
        #
        # "Pharaoh summoned Moses and Aaron AND SAID" is ONE turn split across
        # two clauses, not two turns. Alternating there is wrong on its own
        # and it also writes a false speaker into the window, which then
        # corrupts every later verse that reads it.
        #
        # The rule needs to know when a NEW TURN begins. Three attempts said
        # nothing in the source marked that.
        #
        # LAYING THE DIALOGUE OUT FOUND IT. The whole dialogue
        # was laid out to be seen. Printed end to end, the elided clauses split
        # cleanly in two:
        #
        #     Exo 8:4 cl0  pharaoh  he.summoned Pharaoh…  --content--> cl1
        #     Exo 8:4 cl1  ???      he.said                 <- INSIDE cl0
        #     Exo 8:6 cl0  ???      he.said                 <- inside nothing
        #     Exo 8:6 cl2  ???      he.said                 <- inside nothing
        #
        # **A speech clause that is the CONTENT of another clause is not a new
        # turn.** It is the same turn continuing, which is precisely what
        # "Pharaoh summoned them AND SAID" is — and the `content` edges
        # already recorded it, so the marker was in the graph the whole time
        # and three heuristics had been reaching past it.
        #
        # With embedded clauses out of the rota, the window before Exodus 8:6
        # holds pharaoh (8:4) and moses (8:5), and alternation gives Pharaoh
        # then Moses.
        embedded = {e["dst"] for e in edges[vstart:]
                    if e.get("type") == "content"}
        named = []                      # who has taken a TURN, oldest first
        for _r, prev_cl in window:
            for pc in prev_cl:
                if pc.get("speaker") and pc.get("verb_lemma") in SPEECH \
                        and not pc.get("embedded"):
                    named.append(pc["speaker"])
        for n in cinfo:
            if n.get("verb_lemma") not in SPEECH:
                continue
            if n["id"] in embedded:
                n["embedded"] = True
                continue
            if n.get("speaker"):
                named.append(n["speaker"])
                continue
            recent = list(dict.fromkeys(reversed(named)))
            if len(recent) < 2:
                continue
            pick = recent[1]
            edges.append({"ref": ref, "lang": lang, "type": "speaker",
                          "src": n["id"], "dst": pick,
                          "inferred": "alternation between the last two "
                                      "speakers to take a turn",
                          "clause_role": True})
            n["speaker"] = pick
            named.append(pick)
            stats["speaker_by_alternation"] += 1

        # ---- who is to do it: the addressee of the command -------------
        #
        # 2026-09-21, on Exodus 8:1: it is an imperative from the LORD
        # to Moses telling him what to say to Aaron. Three levels —
        #
        #     cl0  he.said Yahweh TO MOSES      wayyiqtol
        #       content-> cl1  say TO AARON     imperative
        #            content-> cl2  stretch out your hand…   imperative
        #
        # — and the actor at each level is the addressee of the level above
        # it. Moses is the one who will say it; Aaron is the one who will
        # stretch out his hand. An imperative states no subject in Hebrew
        # because the person being commanded is the person being addressed,
        # and the enclosing speech act names them.
        #
        # This is not an elision heuristic. It reads a `pp: to` that is
        # already recorded and hands it to the clause that has no subject.
        # 318 commands sit inside a speech act with a named addressee; 31
        # state their own subject anyway and are left alone.
        mine_e = edges[vstart:]
        to_of = {}
        for e in mine_e:
            if e.get("type") == "pp" and e.get("prep_gloss") == "to":
                to_of.setdefault(e["src"], e["dst"])
        ct_by_clause = {e["src"]: e["dst"] for e in mine_e
                        if e.get("type") == "asserts"}
        has_subj = {e["src"] for e in mine_e
                    if e.get("type") == "s" and e.get("clause_role")}
        for e in list(mine_e):
            if e.get("type") != "content":
                continue
            who = to_of.get(ct_by_clause.get(e["src"]))
            inner = next((c for c in cinfo if c["id"] == e["dst"]), None)
            if not who or not inner or inner.get("verb_mood") not in COMMAND:
                continue
            ict = ct_by_clause.get(inner["id"])
            if not ict or ict in has_subj:
                continue
            edges.append({"ref": ref, "lang": lang, "type": "s",
                          "src": ict, "dst": who, "clause_role": True,
                          "inferred": "addressee of the enclosing command"})
            has_subj.add(ict)
            if facts.get(e["src"], {}).get("to"):
                facts.setdefault(inner["id"], {})["subj"] = \
                    facts[e["src"]]["to"]
            stats["actor_from_addressee"] += 1

        # A SECOND COMMAND JOINED BY "AND" HAS THE SAME ACTOR. Exodus 8:1:
        # "stretch out your hand … AND bring up the frogs" — Aaron is told to
        # do both, but only the first is the `content` of "say to Aaron", so
        # only the first got its actor, and the second's pair with the
        # magicians' "they brought up the frogs" (8:3) could not be checked.
        # Same mood family, same person, no subject of its own: the actor
        # carries across the `and`.
        subj_of = {}
        for e in edges[vstart:]:
            if e.get("type") == "s" and e.get("clause_role"):
                subj_of.setdefault(e["src"], e["dst"])
        by_id = {c["id"]: c for c in cinfo}
        for e in list(edges[vstart:]):
            if e.get("type") != "and" or not e.get("clause_link"):
                continue
            a_, b_ = by_id.get(e["src"]), by_id.get(e["dst"])
            if not a_ or not b_ or a_.get("verb_mood") not in COMMAND or \
                    b_.get("verb_mood") not in COMMAND or \
                    a_.get("verb_person") != b_.get("verb_person"):
                continue
            act = ct_by_clause.get(a_["id"])
            bct_ = ct_by_clause.get(b_["id"])
            if not bct_ or bct_ in has_subj or act not in subj_of:
                continue
            edges.append({"ref": ref, "lang": lang, "type": "s",
                          "src": bct_, "dst": subj_of[act],
                          "clause_role": True,
                          "inferred": "same actor as the command it is "
                                      "joined to"})
            has_subj.add(bct_)
            subj_of[bct_] = subj_of[act]
            if facts.get(a_["id"], {}).get("subj"):
                facts.setdefault(b_["id"], {})["subj"] = \
                    facts[a_["id"]]["subj"]
            stats["actor_from_coordinate"] += 1

        # ---- and then: the waw inside the verb ------------------------
        #
        # 6,692 orphaned clauses were wayyiqtol, whose "and" is fused into
        # the verb, so the connective pass never saw one: "Moses and Aaron
        # went out from Pharaoh, AND-MOSES-CRIED-OUT to the LORD" (Exo 8:8)
        # left the second an orphan. Its future twin is weqatal: "go to
        # Pharaoh, AND-YOU-SHALL-SAY to him" (7:26).
        #
        # A wayyiqtol continues the NARRATIVE line, so it attaches to the
        # nearest clause before it that is not inside a speech — in 8:6,
        # Moses's "he said" continues Pharaoh's "he said", not Pharaoh's
        # "tomorrow". A weqatal continues whatever it follows, including a
        # command inside a speech. Within the verse only: across verses this
        # is the episode rung, and joining every verse-initial wayyiqtol to
        # the verse before would merge a whole narrative into one group
        # before anything says where it divides.
        #
        # BEFORE THE PAIRS, because the pair rule reads what this carries: a
        # continuing clause of the same person keeps its subject — Hebrew
        # narrative states a change of subject, not a continuation — so
        # "the magicians did the same … and-brought-up the frogs" (8:3) is
        # known to be the magicians' act, and cannot be the state of a
        # command given to Aaron. The carried subject is kept in `facts`
        # for that check ONLY; no subject edge is written from it, since
        # nothing yet validates 9,000 such inferences.
        inside = {e["dst"] for e in edges[vstart:]
                  if e.get("type") == "content"}
        grew, passes = True, 0
        while grew:
            grew = False
            passes += 1
            if _tripped(passes, ref, "inside-a-speech closure", 200):
                break
            for e in edges[vstart:]:
                if e.get("clause_link") and e.get("src") in inside and \
                        e.get("dst") not in inside and \
                        (e.get("dst") or "").startswith(ref + "#cl"):
                    inside.add(e["dst"])
                    grew = True
        linked = {e["dst"] for e in edges[vstart:]
                  if (e.get("clause_link") or e.get("type") == "content")
                  and (e.get("src") or "").startswith(ref + "#cl")}
        # a CONSEQUENCE is related to what precedes it by its condition, not
        # by sequence: Exo 4:8's "then they will believe the second sign"
        # (weqatal) got "then" from the condition before it
        cond_hosts = {e["src"] for e in edges[vstart:]
                      if e.get("clause_link") and
                      e.get("type") in ("if", "though", "when_if_though")}
        for k, c in enumerate(cinfo):
            mood = c.get("verb_mood")
            if k == 0 or mood not in ("wayyiqtol", "weqatal") or \
                    c.get("connective") or c["id"] in linked or \
                    c["id"] in cond_hosts:
                continue
            if mood == "wayyiqtol":
                host = next((cinfo[j] for j in range(k - 1, -1, -1)
                             if cinfo[j]["id"] not in inside), None)
            else:
                host = cinfo[k - 1]
            if host is None:
                continue
            edges.append({"ref": ref, "lang": lang, "type": "then",
                          "src": host["id"], "dst": c["id"],
                          "clause_link": True,
                          "inferred": f"{mood}: the 'and' is inside the verb"})
            stats[f"sequence_{mood}"] += 1
            fh, fc = facts.get(host["id"], {}), facts.setdefault(c["id"], {})
            if fh.get("subj") and not fc.get("subj") and \
                    host.get("verb_person") == c.get("verb_person"):
                fc["subj"] = fh["subj"]
                stats["subject_carried_for_pair_check"] += 1

        # ---- the imperative and what qualifies it -----------------------
        #
        # 2026-09-21, working out Psalm 107:1 from the diagram: the next
        # pair is that the qualified imperative has a reason, and they are
        # grouped together by something similar to the action/state pair in
        # Gen 1:1, but it is not quite action/state: it is
        # imperative/basis.
        #
        # Same family, different specialization. The edges already existed —
        # `cl1 --because--> cl0` twice — but an edge is not a GROUPING, and
        # the grouping is the thing a larger pattern can fill a slot with.
        #
        # Both halves are read, not inferred: the mood says the first member
        # is a command, and כִּי says the others are its reason. A basis can
        # be more than one, which is why members are numbered rather than
        # named `first` and `second`.
        #
        # ONE IMPERATIVE, EXTENDED BY WHAT QUALIFIES IT. 2026-09-25,
        # reading the ontology: there should be one imperative class with
        # either specializations or extendibility. Imperative /
        # basis was a class, and imperative / warning was about to be a
        # second — one class per combination, when a command often carries
        # several at once: "let my people go" (Exo 7:26) has an aim, "that
        # they may serve me", and a warning in the next verse. So the group is
        # the COMMAND, and each qualifier is a typed member: `basis` (a stated
        # reason, כִּי), `aim` (a purpose, a command then waw + jussive in
        # another person). A new qualifier is a new member type, not a new
        # class.
        # ---- the EFFECT of a command --------------------------------------
        #
        # 2026-09-25, on the gnat plague (Exo 8:12, BSB 8:16): 'that it
        # may turn into swarms of gnats throughout the land of Egypt' is the
        # effect of 'Stretch out your staff and strike the dust of the
        # earth' — and it was established earlier that imperatives can have
        # effects. The form: an imperative, then waw + a THIRD-person
        # weqatal — the result the commanded act brings about ("and it will
        # become gnats"), where an aim is waw + jussive (what is intended).
        # All 24 corpus cases read (a closed corpus: an enumeration, not a
        # sample): 12 of 20 non-speech ones are effects. Refined, by
        # choice: a bare וְהָיָה "and it will be" counts only with a
        # 'become INTO' (לְ) complement — it otherwise opens a condition or a
        # time ("and it will be, if anyone comes", Jdg 4:20). 10 of 14 right;
        # known wrong: Num 8:7, 35:2, Jer 50:5, Joel 4:11; lost: Num 16:7,
        # 21:8. The cause is the whole run of commands joined by 'and' before
        # it ("stretch out ... and strike"), so they are all its commands.
        pp_prep = collections.defaultdict(set)
        for e in edges[vstart:]:
            if e.get("clause_role") and e.get("type") == "pp":
                pp_prep[e["src"]].add(_nfc(e.get("prep")))
        effect_of = {}
        for i in range(1, len(cinfo)):
            a, b = cinfo[i - 1], cinfo[i]
            if a.get("verb_mood") != "imperative" or \
                    b.get("verb_mood") != "weqatal" or lang != "hebrew" or \
                    effect_of.get(a["id"]) == b["id"]:
                continue
            vb = next((n for n in reversed(nodes)
                       if n.get("id") == f'{b["id"]}v'), {})
            if vb.get("person") != "third" or \
                    _nfc(vb.get("lemma")) == _nfc("אָמַר"):
                continue
            if _nfc(vb.get("lemma")) == _nfc("הָיָה") and \
                    _nfc("לְ") not in pp_prep.get(ct_by_clause.get(b["id"]),
                                                  set()):
                stats["effect_held_bare_hayah"] += 1
                continue
            effect_of[a["id"]] = b["id"]
            # the waw was read as a plain 'and' (or a narrative 'then'):
            # it is the result of the command
            for e in edges[vstart:]:
                if e.get("clause_link") and e.get("src") == a["id"] and \
                        e.get("dst") == b["id"] and \
                        e.get("type") in ("and", "then"):
                    e["type"] = "result"
                    e["was"] = "and"
                    break
            else:
                edges.append({"ref": ref, "lang": lang, "type": "result",
                              "src": a["id"], "dst": b["id"],
                              "clause_link": True})
            # the link; the group member is counted as imperative_effect below
            stats["result_links"] += 1

        quals = collections.defaultdict(list)
        for e in edges[vstart:]:
            if e.get("clause_link") and e.get("type") in ("because",
                                                         "purpose",
                                                         "result"):
                quals[e["src"]].append(
                    ({"because": "basis", "purpose": "aim",
                      "result": "effect"}[e["type"]], e["dst"],
                     bool(e.get("ambiguous"))))
        by_id_ = {c["id"]: c for c in cinfo}

        def joined(x, y, t):
            return any(e.get("clause_link") and e.get("type") == t
                       and e.get("src") == x and e.get("dst") == y
                       for e in edges[vstart:])

        # A RUN OF COMMANDS IS ONE COLLECTION. 2026-09-25, on Exo 8:12:
        # the second-level (Aaron) imperative content is a collection of 2
        # actions — "stretch out your staff AND strike the dust" is one thing
        # Aaron is told, not a command with another hung off it by 'and'. A
        # run is commands joined by 'and' at one speech level: the walk stops
        # at a command whose CONTENT is the next ("say to Aaron: stretch out"
        # is the LORD's command to Moses, a level up).
        def coordinate(j0, j1):
            return cinfo[j0].get("verb_mood") in COMMAND and \
                cinfo[j1].get("verb_mood") in COMMAND and \
                joined(cinfo[j0]["id"], cinfo[j1]["id"], "and") and \
                not joined(cinfo[j0]["id"], cinfo[j1]["id"], "content")

        for i, a in enumerate(cinfo):
            if a.get("verb_mood") not in COMMAND:
                continue
            q = [(t, by_id_[d], amb) for t, d, amb in quals.get(a["id"], [])
                 if d in by_id_]
            # a command that the next one continues is grouped at the END of
            # its run, where the run's qualifiers (an effect, an aim) attach
            if not q and i + 1 < len(cinfo) and coordinate(i, i + 1):
                continue
            j = i
            while j > 0 and coordinate(j - 1, j):
                j -= 1
            cmds = cinfo[j:i + 1]
            if not q and len(cmds) < 2:
                continue
            gid = f"{ref}#imp{i}"
            nodes.append({
                "id": gid, "ref": ref, "lang": lang, "local": f"imp{i}",
                "pair": True, "kind": "imperative", "ordered": True,
                # A GROUP KEEPS THE FORCE OF ITS HEAD. 2026-09-21:
                # an imperative modified as a basis is still an imperative.
                # Adding a reason qualifies the command; it does
                # not stop it being one. So the group carries its first
                # member's force, and when it fills a slot in something larger
                # it still behaves as a command — the same principle stated
                # for the noun phrase, where the group takes its identity from
                # its primary and the rest qualifies.
                "force": cmds[0].get("verb_mood"), "head": cmds[0]["id"],
                "qualified_by": sorted({t for t, _b, _a in q}),
                "evidence": ("a command, and what the text attaches to it"
                             if q else "commands joined by 'and', said "
                                       "together"),
                **({"commands": len(cmds)} if len(cmds) > 1 else {}),
                # A GROUP INHERITS ITS MEMBERS' UNCERTAINTY. If one of these
                # `because` clauses might instead ground the clause before it,
                # the group is not simply wrong -- it is one of two readings,
                # and it says so rather than presenting itself as settled.
                **({"ambiguous": True} if any(amb for _t, _b, amb in q)
                   else {}),
                "text": " / ".join([x.get("text", "") for x in cmds]
                                   + [b.get("text", "") for _t, b, _a in q])
                        [:90]})
            # the saying's CONTENT is the collection, not its first member
            if len(cmds) > 1:
                for e in edges[vstart:]:
                    if e.get("clause_link") and e.get("type") == "content" \
                            and e.get("dst") == cmds[0]["id"]:
                        e["was"] = e["dst"]
                        e["dst"] = gid
                        stats["content_to_collection"] += 1
                stats["imperatives_coordinated"] += 1
            for n_, cmd in enumerate(cmds, start=1):
                edges.append({"ref": ref, "lang": lang, "type": "command",
                              "src": gid, "dst": cmd["id"], "order": n_,
                              "clause_link": True})
            for n_, (t, b, _a) in enumerate(q, start=len(cmds) + 1):
                edges.append({"ref": ref, "lang": lang, "type": t,
                              "src": gid, "dst": b["id"], "order": n_,
                              "clause_link": True})
                stats[f"imperative_{t}"] += 1
            if q:
                stats["imperatives_qualified"] += 1

        # ---- condition / consequence: the if-then as ONE node ----------
        #
        # 2026-09-25, on Exodus 7:27: the entry point is the if/then.
        # An `if` edge joined the two clauses but nothing stood for the pair,
        # so a speech turn could only point at its loose clauses. Same family
        # as imperative / basis: an ordered pair, the condition first as the
        # text puts it, and the group keeps the force of its head — the
        # consequence, which is the clause that asserts or commands
        # something; the condition only says when.
        for e in list(edges[vstart:]):
            if e.get("type") != "if" or not e.get("clause_link"):
                continue
            cons = next((c for c in cinfo if c["id"] == e["src"]), None)
            cond = next((c for c in cinfo if c["id"] == e["dst"]), None)
            if not cons or not cond:
                continue
            gid = f"{ref}#cnd{cond['order']}"
            nodes.append({
                "id": gid, "ref": ref, "lang": lang,
                "local": f"cnd{cond['order']}", "pair": True,
                "kind": "conditional", "ordered": True,
                "force": cons.get("verb_mood"), "head": cons["id"],
                "evidence": "a clause introduced by 'if', and the clause it "
                            "conditions",
                **({"ambiguous": True} if e.get("ambiguous") else {}),
                "text": f'{cond.get("text", "")} / '
                        f'{cons.get("text", "")}'[:90]})
            edges.append({"ref": ref, "lang": lang, "type": "condition",
                          "src": gid, "dst": cond["id"], "order": 1,
                          "clause_link": True})
            edges.append({"ref": ref, "lang": lang, "type": "consequence",
                          "src": gid, "dst": cons["id"], "order": 2,
                          "clause_link": True})
            stats["conditionals"] += 1

        # A COMMAND MAY BE ANSWERED IN A LATER VERSE. Genesis 1:6 is "let
        # there be a firmament" and 1:7 is "and it was so"; 141 pairs was only
        # what fitted inside single verses.
        # ONE POOL, INDEXED ONCE. The first attempt enumerated the pooled list
        # and then read `cinfo[...]` in the body, so every index past this
        # verse's own clauses ran off the end. Everything below indexes `pool`.
        pool = [c for _r, cl in window for c in cl] + cinfo
        mine = {id(c) for c in cinfo}
        for i, a in enumerate(pool):
            if a.get("verb_mood") not in COMMAND:
                continue
            for j in range(i + 1, len(pool)):
                b = pool[j]
                # the pair is recorded once, by the verse holding its SECOND
                # member; otherwise a command sitting in the window would mint
                # it again on every following verse
                if id(b) not in mine:
                    continue
                if b.get("verb_mood") != "wayyiqtol" or \
                        b.get("verb_lemma") != a.get("verb_lemma"):
                    continue
                # SAME LEMMA IS NOT ENOUGH. The frog plague minted five
                # cross-verse pairs and three were false: the magicians'
                # "they brought up the frogs" (8:3) as the state of God's
                # command to AARON, and "say to Aaron" paired with Pharaoh's
                # "he said" (8:4) and with Moses's "he said to Pharaoh" (8:5).
                # The report must be done by the one commanded — or, for a
                # causative, by what the command acts on: "bring up the
                # frogs" (hiphil) is answered by "the frogs went up" (qal). And
                # a command to speak TO someone is answered only by speaking
                # to that same someone. Where either side's actor is unknown
                # the pair stands, as before; this only removes contradictions.
                fa, fb = facts.get(a["id"], {}), facts.get(b["id"], {})
                if fa.get("subj") and fb.get("subj") and \
                        fa["subj"] != fb["subj"] and \
                        not (fa.get("stem") == "hiphil"
                             and fa.get("obj") == fb["subj"]):
                    stats["pair_rejected_actor"] += 1
                    continue
                if fa.get("to") and fa.get("to") != fb.get("to"):
                    stats["pair_rejected_addressee"] += 1
                    continue
                # the action is the SAYING that issued the command where one
                # precedes it, since that is the act; otherwise the command
                # THE SAYING MUST BE IN THE COMMAND'S OWN VERSE. Searching the
                # whole pool for a speech clause reached back across verses
                # and grabbed an unrelated one: Genesis 1:5 came out as
                # "he.said God / it.was evening", pairing a distant "God said"
                # with an evening that answers nothing. A command is issued by
                # the saying that carries it, which is beside it or nowhere.
                first = next((m for m in range(i)
                              if pool[m].get("verb_lemma") in SPEECH
                              and pool[m]["ref"] == a["ref"]), i)
                pid = f"{ref}#pair{i}_{j}"
                nodes.append({
                    "id": pid, "ref": ref, "lang": lang,
                    "local": f"pair{i}_{j}", "pair": True,
                    "kind": "action-state", "ordered": True,
                    # the head's force, as above
                    "force": pool[first].get("verb_mood"),
                    "head": pool[first]["id"],
                    "evidence": "jussive then wayyiqtol, same lemma",
                    "lemma": a.get("verb_lemma"),
                    # a command answered in a LATER verse, which is the shape
                    # the verse-scoped version could not see at all
                    **({"spans_verses": True}
                       if pool[first]["ref"] != b["ref"] else {}),
                    "text": f'{pool[first].get("text", "")} / '
                            f'{b.get("text", "")}'[:90]})
                edges.append({"ref": ref, "lang": lang, "type": "action",
                              "src": pid, "dst": pool[first]["id"],
                              "order": 1, "clause_link": True})
                edges.append({"ref": ref, "lang": lang, "type": "state",
                              "src": pid, "dst": b["id"],
                              "order": 2, "clause_link": True})
                stats["action_state_pairs"] += 1
                break

        for e in g["edges"]:
            dst = e.get("dst")
            rec = {"ref": ref, "lang": lang, "type": e.get("type"),
                   "src": f"{ref}#{e['src']}" if e.get("src") else None,
                   "dst": (f"{ref}#{dst}" if isinstance(dst, str) else None)}
            if isinstance(dst, dict):
                # a reified construct chain: the target is itself a relation
                rec["dst_relation"] = {
                    "src": f"{ref}#{dst.get('src')}",
                    "type": dst.get("type"),
                    "dst": f"{ref}#{dst.get('dst')}"}
            # This is a WHITELIST, so a new field on an edge is dropped
            # silently unless it is added here. `possessed_by` edges carried
            # `noun` and `agreement` for a whole rebuild before anyone noticed
            # they were being stripped -- the edge arrived, the payload did
            # not, and the rules that read it simply never fired.
            for k in ("negated", "intransitive", "inferred_subject",
                      "attached_to_previous_clause", "agent", "scopes_over",
                      "verb", "unresolved_possessor", "noun", "agreement",
                      "comparison"):
                if e.get(k):
                    rec[k] = e[k]
            edges.append(rec)
            stats["edges"] += 1
            if not rec["src"] and not e.get("agent"):
                stats["unresolved"] += 1
            if e.get("inferred_subject"):
                stats["inferred"] += 1
            if e.get("agent") == "unexpressed":
                stats["agentless"] += 1

        # ---- a parallel line borrows the subject of the one above it ---
        #
        # 2026-09-21, on Psalm 119:105: a good start; add the subject.
        #
        #     cl0   p=lamp   pp:לְ=feet   s=word     "a lamp to my feet, your word"
        #     cl1   p=light  pp:לְ=path             "a light to my path"
        #
        # The second line states no subject because it is the same one: *your
        # word* is a lamp AND a light. This is the defining move of Hebrew
        # poetry, and the elision is what makes the parallel legible — saying
        # it twice would break the line.
        #
        # The test is exact rather than approximate. The second clause's roles
        # must be the first's MINUS the subject, so nothing is carried into a
        # clause that merely looks similar: Genesis 1:25's "God made the
        # animals" and "God saw it was good" both state their subject and are
        # never eligible.
        vparts = {}
        for e in edges[vstart:]:
            if e.get("clause_role") and e.get("type") in ("s", "p", "o", "pp",
                                                          "adv", "v"):
                k = e["type"] + (":" + e["prep"] if e.get("prep") else "")
                vparts.setdefault(e["src"], {})[k] = e["dst"]
        for a, b in zip(cinfo, cinfo[1:]):
            pa = vparts.get(ct_by_clause.get(a["id"])) or {}
            pb = vparts.get(ct_by_clause.get(b["id"])) or {}
            bct = ct_by_clause.get(b["id"])
            if not pa or not pb or not bct or "s" not in pa or "s" in pb:
                continue
            if {k for k in pa if k != "s"} != set(pb):
                continue
            # THE SUBJECT BELONGS TO THE COLLECTION. 2026-09-21: the word
            # is the subject for the collection, or at minimum
            # for both parts of the collection.
            #
            # *Your word* is not the subject of two sentences that happen to
            # agree; it is the subject of ONE statement made in two lines.
            # Putting it on each line separately says the first thing. So the
            # parallel pair becomes a node — the same move as action-state and
            # imperative-basis — and the subject hangs off the group.
            #
            # The per-line edge stays as well, flagged `inferred`, because a
            # reader who opens the second line alone should not find it
            # subjectless. The group is where the claim lives; the line-level
            # copy is a convenience and says so.
            gid = f"{ref}#par{a.get('order', 0)}"
            nodes.append({
                "id": gid, "ref": ref, "lang": lang,
                "local": f"par{a.get('order', 0)}", "pair": True,
                "kind": "parallel", "ordered": True,
                "evidence": "same roles but for the subject, all fillers "
                            "different",
                "text": f'{a.get("text", "")} // {b.get("text", "")}'[:90]})
            edges.append({"ref": ref, "lang": lang, "type": "s",
                          "src": gid, "dst": pa["s"], "clause_link": True})
            for pos, cl_ in ((1, a), (2, b)):
                edges.append({"ref": ref, "lang": lang, "type": "line",
                              "src": gid, "dst": cl_["id"], "order": pos,
                              "clause_link": True})
            edges.append({"ref": ref, "lang": lang, "type": "s",
                          "src": bct, "dst": pa["s"], "clause_role": True,
                          "inferred": "carried from the parallel line above"})
            stats["parallel_pairs"] += 1
            stats["subject_from_parallel"] += 1

        # ---- a speech TURN that runs on across verses -----------------
        #
        # The frog plague's overview showed YHWH's message to Pharaoh (Exo
        # 7:26-7:29) as five unconnected groups: only 7:26 was joined to "he
        # said", and the threat and the whole list of where the frogs will go
        # belonged to no speech at all — because every clause link stops at a
        # verse boundary, and a speech does not.
        #
        # A turn is OPEN at the end of a verse when the verse holds a speech
        # and does not end on a narrative wayyiqtol outside it. The next verse
        # CONTINUES it unless it opens with a narrative wayyiqtol — which is
        # how Hebrew narrative takes the line back ("and the LORD said to
        # Moses", "and Aaron stretched out his hand"). The turn becomes a
        # node, minted in the first verse that continues it: `frame` to the
        # last saying in the verse where it opened (the innermost, so a
        # message inside a message belongs to its own speaker), and `part` to
        # every clause of each continuing verse that nothing else in that
        # verse points at. Within a book.
        #
        # ONLY A NARRATED SAYING OPENS A TURN — "he said" (wayyiqtol), "thus
        # says the LORD" (qatal). The first build let any speech verb with a
        # content edge open one, and a sample showed what that does: a
        # proverb's "he who breathes out truth declares righteousness" opened
        # a 188-verse "turn" through Proverbs, and Deuteronomy's "he shall
        # speak to them all that I command" one of 171. A speech verb inside
        # a law or a saying reports speaking; it does not stage it.
        #
        # TURNS NEST. 2026-09-25, on the frog plague: there are nested
        # speech turns, but the real speech turn is God to Moses; the Moses
        # speech turn is actually a directive from God which Moses does not
        # fulfill in these verses, though it is a speech turn, regardless.
        # The first build kept ONE turn, opened at the last saying — "thus
        # says the LORD" — so the real turn, the LORD to Moses, did not exist.
        #
        #   the LORD said to Moses:                         performed
        #     [go to Pharaoh, and you shall say to him:     commanded
        #       [thus says the LORD:                        commanded (the
        #         [let my people go ... ]]]                  message it carries)
        #
        # The OUTER turn is opened by a narrated saying (wayyiqtol / qatal)
        # that sits inside no speech — which still keeps a proverb's "he who
        # breathes out truth declares" from opening anything. Inside it, any
        # saying whose content continues — a command to speak included — opens
        # the next turn in. Each turn records its MODE: performed, or
        # commanded (a directive, or inside one), since a commanded speech has
        # not happened yet and may be fulfilled later.
        speech_to = {e["src"]: e["dst"] for e in edges[vstart:]
                     if e.get("type") == "content"}

        def speech_of(fid):
            got = {speech_to[fid]}
            grew, passes = True, 0
            while grew:
                grew = False
                passes += 1
                if _tripped(passes, ref, "speech closure", 200):
                    break
                for e in edges[vstart:]:
                    if e.get("clause_link") and e.get("src") in got and \
                            e.get("dst") not in got and \
                            (e.get("dst") or "").startswith(ref + "#cl"):
                        got.add(e["dst"])
                        grew = True
            return got
        top = [c for c in cinfo if c["id"] in speech_to
               and c["id"] not in inside
               and c.get("verb_mood") in ("wayyiqtol", "qatal")]
        # A psalm is a composition of its own: nothing said in one runs on
        # into the next.
        if book == "Psa" and turns and turns[0].get("chapter") != \
                ref.split(".")[1]:
            turns = []
        first = cinfo[0] if cinfo else None
        continuing = bool(turns and first
                          and first.get("verb_mood") != "wayyiqtol")
        if continuing:
            for level, t in enumerate(turns):
                if t["id"] is not None:
                    continue
                t["id"] = f"{ref}#turn{level}"
                fr = t["frame"]
                nodes.append({
                    "id": t["id"], "ref": ref, "lang": lang,
                    "local": f"turn{level}", "pair": True, "kind": "turn",
                    "ordered": True, "spans_verses": True,
                    "mode": t["mode"], "level": level,
                    "force": fr.get("verb_mood"), "head": fr["id"],
                    "evidence": "a speech still open at a verse's end, and "
                                "the next verse does not take the narrative "
                                "line back",
                    "text": f'{fr.get("text", "")} / '
                            f'{first.get("text", "")}'[:90]})
                edges.append({"ref": ref, "lang": lang, "type": "frame",
                              "src": t["id"], "dst": fr["id"],
                              "order": 1, "clause_link": True})
                for rel in ("sender", "addressee"):
                    if t.get(rel):
                        edges.append({"ref": ref, "lang": lang, "type": rel,
                                      "src": t["id"], "dst": t[rel],
                                      "clause_link": True})
                        stats[f"turn_{rel}"] += 1
                t["n"] = 1
                if level:
                    # the inner speech is a PART of the outer one
                    up = turns[level - 1]
                    up["n"] += 1
                    edges.append({"ref": ref, "lang": lang, "type": "part",
                                  "src": up["id"], "dst": t["id"],
                                  "order": up["n"], "clause_link": True})
                stats["speech_turns"] += 1
                stats[f"speech_turns_{t['mode']}"] += 1
            turn = turns[-1]          # a continuing verse speaks INSIDE the
                                      # innermost turn
            pointed = {e["dst"] for e in edges[vstart:]
                       if (e.get("clause_link") or e.get("type") == "content")
                       and (e.get("src") or "").startswith(ref + "#cl")}
            # A PART IS THE HIGHEST UNIT, NOT A LOOSE CLAUSE. On 7:27,
            # it was not clear why it was pulled out (as part 2) under the
            # higher-level turn node. Where a root clause heads a grouping
            # in this verse — the if/then, an imperative with its basis, a
            # parallel pair — the turn points at the grouping.
            # read off this verse's own member edges: scanning all `nodes`
            # for the verse's groups made the build 49s -> 229s
            # The if/then first: "if you refuse, [do this because ...]" is a
            # condition over the whole command, so where a clause heads both,
            # the conditional is the higher unit.
            group_of = {}
            for types in (("condition", "consequence"),
                          ("command", "basis", "aim", "line")):
                for e in edges[vstart:]:
                    if e.get("clause_link") and e.get("type") in types:
                        group_of.setdefault(e["dst"], e["src"])
            done = set()
            for c in cinfo:
                # the narrative takes the line back mid-verse: "'Then run!'
                # Joab told him. SO AHIMAAZ RAN" (2 Sam 18:23) — nothing from
                # the first narrative wayyiqtol on is part of the speech
                if c.get("verb_mood") == "wayyiqtol" and c["id"] not in inside:
                    break
                if c["id"] in pointed:
                    continue
                unit = group_of.get(c["id"], c["id"])
                if unit in done:
                    continue
                done.add(unit)
                turn["n"] += 1
                edges.append({"ref": ref, "lang": lang, "type": "part",
                              "src": turn["id"], "dst": unit,
                              "order": turn["n"], "clause_link": True})
                stats["turn_parts"] += 1
            stats["turn_verses"] += 1
        last = cinfo[-1] if cinfo else None
        closes = bool(last and last.get("verb_mood") == "wayyiqtol"
                      and last["id"] not in inside)
        if closes or not (continuing or top):
            turns = []
        elif top and not continuing:
            # the stack, outermost first: the last top-level saying, then
            # each saying inside the speech of the one before
            n0 = top[-1]

            # WHO TO WHOM, where the text says. 2026-09-25: speech is
            # a communication unit. The sender is the saying's subject
            # (stated, or the speaker inferred for it); the addressee its
            # `pp: to`. A COMMANDED speech in the second person — "and YOU
            # shall say to him" — is sent by whoever the enclosing speech was
            # addressed to: Moses.
            def who(fid):
                ct = ct_by_clause.get(fid)
                s_ = next((e["dst"] for e in edges[vstart:]
                           if e.get("src") == ct and e.get("type") == "s"
                           and e.get("clause_role")), None) or \
                    next((e["dst"] for e in edges[vstart:]
                          if e.get("src") == fid
                          and e.get("type") == "speaker"), None)
                t_ = next((e["dst"] for e in edges[vstart:]
                           if e.get("src") == ct and e.get("type") == "pp"
                           and e.get("prep_gloss") == "to"), None)
                return s_, t_
            s0, a0 = who(n0["id"])
            stack = [{"id": None, "frame": n0, "mode": "performed",
                      "sender": s0, "addressee": a0,
                      "chapter": ref.split(".")[1]}]
            cur = n0
            # VISITED FRAMES ARE NEVER RE-ENTERED. The first version looped
            # forever — a build that takes 50s ran past 400 — because clause
            # links can lead from a saying's speech back to the saying, and
            # the next frame found was one already on the stack.
            visited = {n0["id"]}
            while True:
                # the visited set is the recursion DETECTION; this is the
                # breaker, should a future change defeat it
                if _tripped(len(stack), ref, "speech-turn nesting", 50):
                    break
                within_ = speech_of(cur["id"])
                nxt = next((c for c in cinfo if c["id"] in within_
                            and c["id"] in speech_to
                            and c["id"] not in visited), None)
                if nxt is None:
                    # BY POSITION, as a continuing turn is read: what follows
                    # a saying in its verse is inside its speech until the
                    # narrative takes the line back. BSB 8:20's chain broke
                    # at "(behold, he is going out to the water)", a
                    # participle clause linked to nothing, so "and you shall
                    # say to him: thus says the LORD: ..." — the second
                    # and third levels — was never reached by links.
                    after = False
                    for c in cinfo:
                        if c["id"] == cur["id"]:
                            after = True
                            continue
                        if not after:
                            continue
                        if c.get("verb_mood") == "wayyiqtol" and \
                                c["id"] not in inside:
                            break
                        if c["id"] in speech_to and c["id"] not in visited:
                            nxt = c
                            break
                if nxt is None:
                    break
                mode = ("commanded" if stack[-1]["mode"] == "commanded"
                        or nxt.get("verb_mood") not in ("wayyiqtol",
                                                        "qatal")
                        else "performed")
                s_, a_ = who(nxt["id"])
                # A COMMANDED SAYING IN THE SECOND PERSON IS SPOKEN BY THE ONE
                # COMMANDED: "and YOU shall say to him" (Exo 8:16, BSB 8:20) is
                # Moses's to say. First-retrieval fault 9: the speaker rule
                # (by alternation) had put "the LORD" on it, and the turn read
                # its sender from that. The enclosing addressee wins, and the
                # speaker edge is corrected to match.
                if mode == "commanded" and \
                        nxt.get("verb_person") == "second" and \
                        stack[-1].get("addressee"):
                    s_ = stack[-1]["addressee"]
                    for e in edges[vstart:]:
                        if e.get("type") == "speaker" and \
                                e.get("src") == nxt["id"] and \
                                e.get("dst") != s_:
                            e["dst"] = s_
                            e["corrected"] = ("the addressee of the "
                                              "enclosing command")
                            stats["speaker_corrected_commanded"] += 1
                stack.append({"id": None, "frame": nxt, "mode": mode,
                              "sender": s_, "addressee": a_})
                visited.add(nxt["id"])
                cur = nxt
            turns = stack
            # MINTED WHERE IT OPENS, not only if it runs on. 2026-09-26,
            # on Exo 8:12 (BSB 8:16): there is a clear 'and the LORD said'
            # (imperative) wrapping 'say to Aaron', very similar structurally
            # to the Frog opening which required nested turns; and on 8:16
            # (BSB 8:20), three levels in one verse. The stack was worked out
            # here and minted only in a NEXT verse that continued it, so a
            # speech complete within its verse had no communication unit at
            # all. Now each level is a node here: its frame (the saying), who
            # to whom, the level inside it as a part, and — innermost — what
            # is said, as the highest unit (the collection of commands, not
            # its first command).
            group_here = {}
            for types in (("condition", "consequence"),
                          ("command", "basis", "aim", "effect", "line")):
                for e in edges[vstart:]:
                    if e.get("clause_link") and e.get("type") in types:
                        group_here.setdefault(e["dst"], e["src"])
            for level, t in enumerate(turns):
                t["id"] = f"{ref}#turn{level}"
                fr = t["frame"]
                nodes.append({
                    "id": t["id"], "ref": ref, "lang": lang,
                    "local": f"turn{level}", "pair": True, "kind": "turn",
                    "ordered": True, "mode": t["mode"], "level": level,
                    "force": fr.get("verb_mood"), "head": fr["id"],
                    "evidence": "a narrated saying and what it says",
                    "text": (fr.get("text") or "")[:90]})
                edges.append({"ref": ref, "lang": lang, "type": "frame",
                              "src": t["id"], "dst": fr["id"],
                              "order": 1, "clause_link": True})
                for rel in ("sender", "addressee"):
                    if t.get(rel):
                        edges.append({"ref": ref, "lang": lang, "type": rel,
                                      "src": t["id"], "dst": t[rel],
                                      "clause_link": True})
                        stats[f"turn_{rel}"] += 1
                t["n"] = 1
                if level:
                    up = turns[level - 1]
                    up["n"] += 1
                    edges.append({"ref": ref, "lang": lang, "type": "part",
                                  "src": up["id"], "dst": t["id"],
                                  "order": up["n"], "clause_link": True})
                stats["speech_turns"] += 1
                stats["speech_turns_opened_here"] += 1
                stats[f"speech_turns_{t['mode']}"] += 1
            # what each level itself says (its frame's content, as the
            # highest unit) — the outer speech says "rise early, present
            # yourself" before it gets to "and you shall say to him"
            nested_frames = {t["frame"]["id"] for t in turns}
            for t in turns:
                said = speech_to.get(t["frame"]["id"])
                if not said or said in nested_frames:
                    continue
                unit = group_here.get(said, said)
                t["n"] += 1
                edges.append({"ref": ref, "lang": lang, "type": "part",
                              "src": t["id"], "dst": unit,
                              "order": t["n"], "clause_link": True})
                stats["turn_parts"] += 1
        # (continuing and not closing: the same turns run on)

        # ---- a psalm is a WRITING, and its heading names the writer -------
        #
        # 2026-09-25, on Psalm 23: the assertion that this is a psalm
        # of David needs to inform all nodes in the scroll. The Writing unit
        # (PROPOSED until now) built for the Psalms first, where the unit is
        # the psalm and the heading states its sender: "a psalm of David"
        # (מִזְמוֹר לְדָוִד, 23:1) is its own clause in MACULA.
        #
        # One Writing per psalm, minted at its first verse: `frame` to each
        # heading clause; `sender` to the person the heading names (a proper
        # name, or a construct phrase over one — "the sons of Korah"; never
        # the LORD, never a genre word); `part` to every top-level unit of
        # every verse, so each node of the psalm sits inside it.
        #
        # And the heading INFORMS the psalm's own voice: a first-person
        # singular clause that is not inside a quoted speech, with no subject
        # of its own — "I shall not want", "I will fear no evil" — has the
        # writer as its subject, inferred and saying so. Inside a quotation
        # "I" is whoever is quoted, so those are left alone.
        #
        # לְדָוִד can be read "of", "for" or "about" David; the sender edge
        # carries the preposition and that note. It is read here as authorship.
        if book == "Psa":
            ch_ = ref.split(".")[1]
            if not psalm or psalm["chapter"] != ch_:
                psalm = {"chapter": ch_, "id": f"{ref}#writing",
                         "voice": f"{ref}#psalmist",
                         "sender": None, "n": 0, "frames": 0,
                         "addr": None, "new_addr": None}
                nodes.append({
                    "id": psalm["id"], "ref": ref, "lang": lang,
                    "local": "writing", "pair": True, "kind": "writing",
                    "medium": "writing", "mode": "performed",
                    "ordered": True, "spans_verses": True,
                    "evidence": "a psalm, as a communication from its writer",
                    "text": f"Psalm {ch_}"})
                # THE PSALMIST: THE PSALM'S VOICE, NOT A PERSON.
                # 2026-09-25: this is a psalm that each reader can read, so
                # 'David' needs to be held lightly; whoever is praying this
                # psalm can substitute themselves; better to say the
                # psalmist and let it resolve in the highest-level context to
                # David. The psalm's "I" and "my" point HERE; the voice
                # resolves to David only at the Writing, through the heading.
                nodes.append({
                    "id": psalm["voice"], "ref": ref, "lang": lang,
                    "local": "psalmist", "voice": True,
                    # the Author of a writing, specialized: a psalm's author
                    # voice is the psalmist (a specialization of
                    # scroll author)
                    "author_kind": "psalmist",
                    "text": "the psalmist",
                    "role": "the voice of the psalm — taken up by whoever "
                            "prays it"})
                edges.append({"ref": ref, "lang": lang, "type": "voice",
                              "src": psalm["id"], "dst": psalm["voice"]})
                stats["writings"] += 1
            # this verse's nodes, words included: walk back from the end while
            # the ref holds (a marker taken mid-verse missed the words, which
            # are appended first — and found no heading in any psalm)
            by_node = {}
            for n in reversed(nodes):
                if n.get("ref") != ref:
                    break
                by_node[n["id"]] = n
            heading = set()
            # THE HEADING IS THE RUN OF VERBLESS CLAUSES THAT OPENS THE
            # PSALM. MACULA gives each piece its own clause — "to the
            # choirmaster", "for Jeduthun", "a psalm of David" (Psa 39:1) —
            # and some psalms are headed only "of David" (25:1), with no
            # genre word at all. A first version looked for a genre word and
            # missed 31 psalms; it also took Psalm 147's first line, "it is
            # good to sing PRAISE to our God", for a heading. The run stops
            # at the first clause with a finite verb, or the first that names
            # God — "the LORD is my shepherd" (23:1) is verbless too — and
            # counts only if some clause in it names a genre or a writer.
            if ref.split(".")[2] == "1":
                run, kid = [], {e["dst"] for e in edges[vstart:]
                                if e.get("type") == "within"}
                for k_, c in enumerate(cinfo):
                    lems = {_nfc(w.get("lemma")) for w in _words(cls[k_])}
                    if c["id"] in kid and run:
                        run.append((c, lems))      # inside a heading clause
                        continue
                    # a clause naming a genre or a writer is heading even if
                    # it names God too — "a prayer of Moses, the man of God"
                    # (90:1), "a shiggaion of David, which he sang to the
                    # LORD" (7:1); stopping there lost both writers
                    if c.get("verb_mood") or (
                            lems & divine and not lems & (genre | writers)):
                        break
                    run.append((c, lems))
                if any(lems & (genre | writers) for _c, lems in run):
                    for c, lems in run:
                        heading.add(c["id"])
                        psalm["frames"] += 1
                        edges.append({"ref": ref, "lang": lang,
                                      "type": "frame", "src": psalm["id"],
                                      "dst": c["id"],
                                      "order": psalm["frames"],
                                      "clause_link": True})
                    # the writer: the first heading name in the run. A
                    # composite over it ("the sons of Korah") is preferred
                    # to the bare name.
                    name = next((lm for _c, lems in run for lm in lems
                                 if lm in writers), None)
                    if name:
                        cands = [n for n in by_node.values()
                                 if _nfc(n.get("lemma")) == name
                                 and not n.get("verb")]
                        comp = [n for n in by_node.values()
                                if n.get("composite") and cands and
                                cands[0].get("local", "").lower()
                                in n.get("local", "").lower()]
                        who_n = (comp or cands or [None])[0]
                        if who_n is None:
                            # the name sits inside a construct phrase ("a
                            # shiggaion OF DAVID", 7:1; "the servant of the
                            # LORD, of David", 18:1) and has no node of its
                            # own; mint the occurrence from MACULA's word
                            w_ = next((w for c_, _l in run
                                       for w in _words(
                                           cls[int(c_["id"].rsplit("cl", 1)
                                                   [1])])
                                       if _nfc(w.get("lemma")) == name),
                                      None)
                            if w_ is not None:
                                gl = (w_.get("gloss") or "name").strip()
                                nid_ = f"{ref}#{gl.lower().replace(' ', '')}"
                                who_n = by_node.get(nid_) or {
                                    "id": nid_, "ref": ref, "lang": lang,
                                    "local": gl.lower().replace(" ", ""),
                                    "text": gl, "lemma": w_.get("lemma"),
                                    "strong": w_.get("strongnumberx")
                                    or w_.get("strong"),
                                    "pos": "noun", "class": "noun",
                                    "type": "proper", "proper": True,
                                    "word_ref": w_.get("ref"),
                                    "minted_for": "the psalm's heading"}
                                if nid_ not in by_node:
                                    nodes.append(who_n)
                                    by_node[nid_] = who_n
                        if who_n:
                            psalm["sender"] = who_n["id"]
                            edges.append({
                                "ref": ref, "lang": lang, "type": "sender",
                                "src": psalm["id"], "dst": who_n["id"],
                                "clause_link": True,
                                "stated_by": "the psalm's heading",
                                "prep": _nfc("לְ"),
                                "note": "לְ may be read 'of', 'for' or "
                                        "'about'; taken as authorship"})
                            # the voice resolves to the writer HERE, at the
                            # highest level, and nowhere below it
                            edges.append({
                                "ref": ref, "lang": lang,
                                "type": "resolves_to",
                                "src": psalm["voice"], "dst": who_n["id"],
                                "stated_by": "the psalm's heading",
                                "note": "held lightly: whoever prays the "
                                        "psalm takes up this voice"})
                            stats["writing_sender"] += 1
            # ---- the psalm turns to address someone: "you" -------------
            # 2026-09-25: then there is a flip to directly
            # addressing God as 'you'. Psalm 23:1-4a speaks ABOUT the LORD;
            # 4b-5 speaks TO him — "you are with me; your rod and your staff
            # comfort me; you prepare a table before me". The flip is MARKED:
            # second-person verbs, pronouns and suffixes. A run of clauses so
            # marked, outside any quoted speech, is an ADDRESS — a
            # communication nested in the Writing, from its writer; the
            # addressee is left open, since "you" has no antecedent in the
            # text, only an addressee (previewed, not written).
            in_addr = {}
            psalm["new_addr"] = None      # an address begun in THIS verse
            # the most recent divine name in the psalm, for the default
            for n_ in by_node.values():
                if _nfc(n_.get("lemma")) in divine and not n_.get("verb"):
                    psalm["divine"] = n_["id"]
                    divine_ids.add(n_["id"])
            for k_, c in enumerate(cinfo):
                if c["id"] in heading or c["id"] in inside:
                    continue
                marked = c.get("verb_person") == "second" or any(
                    w.get("person") == "second" for w in _words(cls[k_]))
                if not marked:
                    psalm["addr"] = None           # the run ends
                    continue
                if not psalm.get("addr"):
                    aid = f"{ref}#addr{c['order']}"
                    psalm["addr"] = {"id": aid, "n": 0}
                    nodes.append({
                        "id": aid, "ref": ref, "lang": lang,
                        "local": f"addr{c['order']}", "pair": True,
                        "kind": "address", "medium": "writing",
                        "mode": "performed", "ordered": True,
                        "evidence": "a run of clauses in the second person, "
                                    "outside any quoted speech",
                        "text": c.get("text", "")[:90]})
                    # the psalmist addresses — the voice, not the name
                    edges.append({"ref": ref, "lang": lang,
                                  "type": "sender", "src": aid,
                                  "dst": psalm["voice"],
                                  "clause_link": True})
                    # TO WHOM. 2026-09-25: a general rule of thumb can
                    # be held that second person in psalms refers to God in
                    # Psalms unless overridden. The first few verses of
                    # Psalm 103 are an example of overriding, as the Psalmist
                    # is addressing his soul. A vocative beside the clause overrides; else
                    # the most recent divine name in the psalm.
                    voc = _VOCATIVE.get(id(cls[k_]))
                    to_, why_ = None, None
                    if voc is not None:
                        vw = _head_w(voc)
                        if vw is not None:
                            vl = nid(vw)
                            if not (vl and vl in known):
                                vl = f"voc{c['order']}"
                                at_v = _attrs(vw)
                                at_v.setdefault("class", "noun")
                                nodes.append({
                                    "id": f"{ref}#{vl}", "ref": ref,
                                    "local": vl, "lang": lang, **at_v,
                                    "minted_for": "a vocative"})
                                known.add(vl)
                            to_ = f"{ref}#{vl}"
                            why_ = "the vocative that addresses it"
                            # A VOCATIVE KEEPS ITS "MY". 2026-09-26, on
                            # Psa 103:3: the 'your' resolving to 'soul' is
                            # good, but it would be better if it resolved to
                            # the psalmist's soul. The vocative was minted
                            # from its head word alone and נַפְשִׁי's suffix was
                            # dropped, so the soul had no owner. A first-
                            # person "my" on a vocative in the psalm's own
                            # voice is the psalmist's, as every other "my" is.
                            my_ = any(w.get("pos") == "suffix" and
                                      w.get("person") == "first" and
                                      w.get("number") == "singular"
                                      for w in voc.iter("w"))
                            if my_ and not any(
                                    x.get("type") == "possessor" and
                                    x.get("src") == to_ for x in edges):
                                edges.append({
                                    "ref": ref, "lang": lang,
                                    "type": "possessor", "src": to_,
                                    "dst": psalm["voice"],
                                    "inferred": "the psalmist — the psalm's "
                                                "own voice"})
                                stats["possessor_vocative_psalmist"] += 1
                    if to_ is None and psalm.get("divine"):
                        to_ = psalm["divine"]
                        why_ = ("psalm default: 'you' is God unless a "
                                "vocative names someone else")
                    if to_:
                        edges.append({"ref": ref, "lang": lang,
                                      "type": "addressee", "src": aid,
                                      "dst": to_, "clause_link": True,
                                      "inferred": why_})
                        stats["address_to_" + ("vocative" if voc is not None
                                               else "god")] += 1
                    psalm["addr"]["to"] = to_
                    stats["psalm_addresses"] += 1
                    in_addr[c["id"]] = aid
                    psalm["new_addr"] = aid
                a_ = psalm["addr"]
                a_["n"] += 1
                edges.append({"ref": ref, "lang": lang, "type": "part",
                              "src": a_["id"], "dst": c["id"],
                              "order": a_["n"], "clause_link": True})
                in_addr[c["id"]] = a_["id"]
                if a_.get("to"):
                    addr_to[c["id"]] = a_["to"]
                stats["address_parts"] += 1
            # every top-level unit of the verse is a part of the psalm
            pointed_ = {e["dst"] for e in edges[vstart:]
                        if (e.get("clause_link")
                            or e.get("type") == "content")
                        and (e.get("src") or "").startswith(ref + "#cl")}
            grp_ = {}
            for types in (("condition", "consequence"),
                          ("command", "basis", "aim", "line")):
                for e in edges[vstart:]:
                    if e.get("clause_link") and e.get("type") in types:
                        grp_.setdefault(e["dst"], e["src"])
            done_ = set()
            for c in cinfo:
                if c["id"] in heading:
                    continue
                if c["id"] in in_addr:
                    # an address is ONE part of the psalm, entered once — in
                    # the verse where it begins
                    unit = in_addr[c["id"]]
                    if psalm.get("new_addr") != unit or unit in done_:
                        continue
                elif c["id"] in pointed_:
                    continue
                else:
                    unit = grp_.get(c["id"], c["id"])
                if unit in done_:
                    continue
                done_.add(unit)
                psalm["n"] += 1
                edges.append({"ref": ref, "lang": lang, "type": "part",
                              "src": psalm["id"], "dst": unit,
                              "order": psalm["n"], "clause_link": True})
                stats["writing_parts"] += 1
            # the psalm's own "MY" is its writer's. 2026-09-25: David is
            # explicitly saying that the Lord is David's shepherd
            # and not just a shepherd generically. רֹעִי is "my shepherd", and
            # MACULA marks the suffix first person singular — but the
            # possessor was left unresolved on 800 such nouns in the Psalms.
            # Outside any quoted speech, the psalm's "my" is the PSALMIST's —
            # the psalm's voice, which the heading, at the top, identifies as
            # David: "my shepherd", "my head", "my cup", "my enemies". Every
            # psalm has a voice, headed or not.
            if True:
                clause_of_word = {}
                for e in edges[vstart:]:
                    if e.get("clause_role") and e.get("type") != "speaker":
                        c_ = next((c["id"] for c in cinfo
                                   if ct_by_clause.get(c["id"]) == e["src"]),
                                  None)
                        if c_:
                            clause_of_word.setdefault(e.get("dst"), c_)
                for e in list(edges[vstart:]):
                    if e.get("type") != "possessed_by" or \
                            e.get("agreement") != ["first", "common",
                                                   "singular"]:
                        continue
                    c_ = clause_of_word.get(e.get("src"))
                    if not c_ or c_ in inside or c_ in heading:
                        continue
                    edges.append({"ref": ref, "lang": lang,
                                  "type": "possessor", "src": e["src"],
                                  "dst": psalm["voice"],
                                  "inferred": "the psalmist — the psalm's "
                                              "own voice"})
                    stats["possessor_psalmist"] += 1
            # the psalm's own "I" is the psalmist
            if True:
                vnum = {n["id"][:-1]: n.get("number")
                        for n in by_node.values()
                        if n.get("verb") and not n.get("causative")}
                has_s = {e["src"] for e in edges[vstart:]
                         if e.get("type") == "s" and e.get("clause_role")}
                for c in cinfo:
                    ct = ct_by_clause.get(c["id"])
                    if c["id"] in inside or c["id"] in heading or not ct or \
                            ct in has_s or \
                            c.get("verb_person") != "first" or \
                            vnum.get(c["id"]) not in ("singular", None):
                        continue
                    edges.append({"ref": ref, "lang": lang, "type": "s",
                                  "src": ct, "dst": psalm["voice"],
                                  "clause_role": True,
                                  "inferred": "the psalmist — the psalm's "
                                              "own voice"})
                    stats["subject_psalmist"] += 1
            # ... and so is its "ME". 2026-09-26, on 23:2 "he makes me
            # lie down": resolve "me" to the psalmist. The same voice as "I"
            # and "my", in the object's place — "he leads me", "you are with
            # me" — and in an independent pronoun. A first-person singular
            # pronoun whose clause is outside any quotation and the heading
            # refers to the psalmist; the psalmist resolves to the writer at
            # the Writing, through the heading, as "I" and "my" do. (The
            # pray-er as a second referent was weighed and set above the
            # structure graph: the text does not state it.)
            if True:
                up_ = {}
                for e in edges[vstart:]:
                    if e.get("dst") and e.get("src") and e.get("type") not in (
                            "refers_to", "possessor", "possessed_by", "next"):
                        up_.setdefault(e["dst"], []).append(e["src"])
                clause_of_ct = {v: k for k, v in ct_by_clause.items()}
                for n_ in by_node.values():
                    if n_.get("class") != "pron" or n_.get("verb") or \
                            n_.get("person") != "first" or \
                            n_.get("number") != "singular":
                        continue
                    cls_, seen_, frontier = set(), set(), [n_["id"]]
                    for _ in range(6):             # up to its clause(s)
                        nxt = []
                        for x in frontier:
                            for p in up_.get(x, []):
                                if p in seen_:
                                    continue
                                seen_.add(p)
                                if p in clause_of_ct:
                                    cls_.add(clause_of_ct[p])
                                else:
                                    nxt.append(p)
                        frontier = nxt
                    if not cls_ or cls_ & (inside | heading) or any(
                            x.get("src") == n_["id"] and
                            x.get("type") == "refers_to"
                            for x in edges[vstart:]):
                        continue
                    edges.append({"ref": ref, "lang": lang,
                                  "type": "refers_to", "src": n_["id"],
                                  "dst": psalm["voice"],
                                  "inferred": "the psalmist — the psalm's "
                                              "own voice"})
                    stats["refers_to_psalmist"] += 1

        # ---- a pronoun walks back up the ordered chain -----------------
        #
        # 2026-09-25: could the use of pronoun be enough to establish
        # 'The Lord is my Shepherd' as context for the following collection
        # of nodes? For WHO acts, largely: Psalm 23:2-3 is "he makes me lie
        # down ... he leads me ... he restores ... he guides me" — third
        # masculine singular with no subject — and walking back up the chain
        # the nearest agreeing referent is "the LORD" of 23:1. (Which PICTURE
        # governs — shepherd through v4, host from v5 — is imagery, the
        # meaning graph's; pronouns cannot see it.)
        #
        # The rule: a third-person clause whose content has no subject takes
        # the subject of the nearest earlier clause that agrees in gender and
        # number (where both are known), is at the same speech level (both
        # inside a quoted speech or both outside), and is itself third person
        # — within 12 clauses, in the same book (and psalm). Inferred, and
        # saying so. Not the flat layer's "nearest agreeing clause subject":
        # that ignored speech levels and verse order, and made Pharaoh remove
        # the frogs.
        by_here = {}
        for n in reversed(nodes):
            if n.get("ref") != ref:
                break
            by_here[n["id"]] = n
        subj_id = {}
        for e in edges[vstart:]:
            if e.get("type") == "s" and e.get("clause_role"):
                subj_id.setdefault(e["src"], e["dst"])
        if book == "Psa" and history and \
                history[-1]["ref"].split(".")[1] != ref.split(".")[1]:
            history.clear()                 # a psalm is its own composition
        for c in cinfo:
            ct = ct_by_clause.get(c["id"])
            v = by_here.get(c["id"] + "v") or {}
            gn = (v.get("gender"), v.get("number"))
            lvl = c["id"] in inside
            if CHAIN_RESOLVE and ct and ct not in subj_id and \
                    c.get("verb_person") == "third":
                hops = 0
                for h in reversed(history):
                    hops += 1
                    # the walk's DESIGNED reach, not a runaway: stopping here
                    # is the rule working, so it is not recorded as a
                    # circuit break (the first version did, and reported
                    # 3,092 "breaks" that would have buried a real one)
                    if hops > 12:
                        break
                    if h["lvl"] != lvl or not h.get("s"):
                        continue
                    if h.get("person") in ("first", "second"):
                        continue
                    hg, hn = h.get("gn", (None, None))
                    if (gn[0] and hg and gn[0] != hg and "common" not in
                            (gn[0], hg)) or (gn[1] and hn and gn[1] != hn):
                        continue
                    edges.append({"ref": ref, "lang": lang, "type": "s",
                                  "src": ct, "dst": h["s"],
                                  "clause_role": True,
                                  "inferred": "nearest agreeing referent up "
                                              "the ordered chain"})
                    subj_id[ct] = h["s"]
                    stats["subject_from_chain"] += 1
                    break
            sid = subj_id.get(ct) if ct else None
            sn = (by_here.get(sid) or {}) if sid else {}
            history.append({
                "ref": ref, "lvl": lvl, "s": sid,
                # the clause's person is its VERB's where it has one: "I
                # shall not want" has David as its (inferred) subject, and
                # David is a noun — read as third person, 23:2's "he" would
                # have resolved to David
                "person": c.get("verb_person")
                or (sn.get("person") if sn.get("class") == "pron" else None)
                or ("third" if sid else None),
                # the subject's own gender and number where it has them,
                # else the verb's (an inferred subject agrees with its verb)
                "gn": (sn.get("gender") or gn[0], sn.get("number") or gn[1])})

        # ---- the subject the VERB states ------------------------------
        #
        # 2026-09-25: assertion 3 was still missing 'He makes'; in
        # fact, the following assertions had the same problem of
        # leaving out the subject 'he'. יַרְבִּיצֵנִי carries "he" in the
        # verb — third masculine singular — and no separate word says it, so
        # the clause had no subject at all. The morphology STATES the
        # subject's person, gender and number; that is the text, not an
        # inference. So a finite verb whose content still has no subject
        # gets one: an implicit pronoun node ("he", "she", "they", "I",
        # "you", "we"). WHO it is — the LORD, in Psalm 23:2 — is a further
        # question: pronoun resolution, previewed but not written
        # (CHAIN_RESOLVE).
        has_s_ = {e["src"] for e in edges[vstart:]
                  if e.get("type") == "s" and e.get("clause_role")}
        vnode_ = {}
        for n in reversed(nodes):
            if n.get("ref") != ref:
                break
            if n.get("verb") and not n.get("causative"):
                vnode_[n["id"][:-1]] = n
        # ---- and WHO the pronoun is, only when the text leaves no doubt --
        #
        # 2026-09-25: a resolution rule can be held that if there is
        # only one possible candidate for pronoun resolution in the leading
        # text, it resolves; if there is potential ambiguity, hold
        # off. The nearest-match walk (CHAIN_RESOLVE, ~35%) guessed; this
        # does not. A third-person pronoun resolves only if EXACTLY ONE
        # referent in the leading text (the last 12 clauses, same speech
        # level) agrees with it in gender and number. Predicates are not
        # referents ("the LORD is my shepherd" names one, not two), nor are
        # headings, pronouns, or the psalm's voice. A resolved pronoun's
        # referent stays in the leading text, so "he makes ... he leads ...
        # he restores" chain back to the one LORD.
        #
        # And second person in a psalm: second person in psalms refers
        # to God in Psalms unless overridden — an implicit "you" inside a
        # psalm's address takes that address's addressee (God by default, or
        # the vocative: "Bless the LORD, O MY SOUL", Psa 103:1).
        here_n = {}
        for n in reversed(nodes):
            if n.get("ref") != ref:
                break
            here_n[n["id"]] = n
        frames_ = {e["dst"] for e in edges[vstart:] if e.get("type") ==
                   "frame"}
        if book == "Psa" and ref_hist and \
                ref_hist[-1]["ch"] != ref.split(".")[1]:
            ref_hist.clear()                # a psalm is its own composition
        inner_of = {e["src"]: e["dst"] for e in edges[vstart:]
                    if e.get("type") == "causes"}
        role_by_ct = collections.defaultdict(list)
        for e in edges[vstart:]:
            if e.get("clause_role") and e.get("type") in ("s", "o", "pp",
                                                           "io", "o2"):
                role_by_ct[e["src"]].append(e)

        def agree(g1, n1, g2, n2):
            if g1 and g2 and g1 != g2 and "common" not in (g1, g2):
                return False
            return not (n1 and n2 and n1 != n2)

        for c in cinfo:
            ct = ct_by_clause.get(c["id"])
            v_ = vnode_.get(c["id"]) or {}
            per = v_.get("person")
            num, gen = v_.get("number"), v_.get("gender")
            lvl = c["id"] in inside
            if ct and ct not in has_s_ and per in ("first", "second",
                                                   "third"):
                pron = _pronoun(per, gen, num)
                # the id keeps the first form ("he0", not "heit0"), so ids
                # stay stable while the label says "he/it"
                loc_ = (f"{re.sub(r'[^A-Za-z]', '', pron.split('/')[0])}"
                        f"{c['order']}")
                pid_ = f"{ref}#{loc_}"
                nodes.append({"id": pid_, "ref": ref, "lang": lang,
                              "local": loc_, "text": pron, "class": "pron",
                              "pos": "pronoun", "person": per,
                              **({"gender": gen} if gen else {}),
                              **({"number": num} if num else {}),
                              "implicit": True,
                              "minted_for": "the subject the verb states"})
                edges.append({"ref": ref, "lang": lang, "type": "s",
                              "src": ct, "dst": pid_, "clause_role": True,
                              "implicit": "stated by the verb's person, "
                                          "gender and number"})
                has_s_.add(ct)
                stats["subject_implicit"] += 1
                role_by_ct[ct].append({"type": "s", "dst": pid_})
                # who it is
                pnode = nodes[-1]                 # the pronoun just minted
                eff_cmd = next((a_ for a_, b_ in effect_of.items()
                                if b_ == c["id"]), None)
                eff_obj = None
                if eff_cmd and per == "third":
                    # THE THING STRUCK IS THE THING THAT BECOMES. On
                    # "strike the dust ... and it will become gnats" (Exo
                    # 8:12): the subject is the dust, not "he". An effect's
                    # implicit subject that agrees with its command's OBJECT
                    # is that object — "join them ... and they become one",
                    # "keep my sabbaths ... and they will be a sign".
                    # Structural, so it applies to plurals too.
                    for e in role_by_ct.get(ct_by_clause.get(eff_cmd), []):
                        if e.get("type") != "o":
                            continue
                        on_ = here_n.get(e.get("dst")) or {}
                        if on_ and agree(gen, num, on_.get("gender"),
                                         on_.get("number")):
                            eff_obj = e.get("dst")
                            break
                # THE HEART STANDS FOR ITS OWNER. 2026-09-25, on Exo 8:15
                # (BSB 8:19): is there a way for 'he' to resolve to
                # Pharaoh? — "Pharaoh's heart was hardened, and he would not
                # listen". The clause before names a heart and its owner; an
                # implicit subject agreeing with that owner is the owner.
                # Measured: 70 corpus cases of a heart clause followed by an
                # implicit subject; those listed all right (Exo 7:13, 7:22,
                # 9:7; Gen 42:28 "their hearts sank ... they trembled"); the
                # agreement check excludes Exo 14:5 (Pharaoh's heart ... THEY
                # said).
                ho = heart_owner.get("prev")
                if not eff_obj and ho and per == "third" and \
                        agree(gen, num, ho[1], ho[2]):
                    eff_obj = ho[0]
                    heart_rule = True
                else:
                    heart_rule = False
                if eff_obj and heart_rule:
                    edges.append({"ref": ref, "lang": lang,
                                  "type": "refers_to", "src": pid_,
                                  "dst": eff_obj,
                                  "inferred": "the owner of the heart named "
                                              "in the clause before"})
                    resolved[pid_] = eff_obj
                    if "/" in (pnode.get("text") or ""):
                        pnode["text"] = pnode["text"].split("/")[0]
                    stats["refers_to_heart_owner"] += 1
                elif eff_obj:
                    edges.append({"ref": ref, "lang": lang,
                                  "type": "refers_to", "src": pid_,
                                  "dst": eff_obj,
                                  "inferred": "the object of the command "
                                              "whose effect it is"})
                    resolved[pid_] = eff_obj
                    on_ = here_n.get(eff_obj) or {}
                    if num != "plural" and not on_.get("proper"):
                        pnode["text"] = "it"
                    stats["refers_to_effect_object"] += 1
                elif per == "second" and c["id"] in addr_to and \
                        gen == "feminine" and addr_to[c["id"]] in divine_ids:
                    # A FEMININE "YOU" IS NOT GOD. "Why are you downcast, O my
                    # soul" (Psa 42:12) addresses the soul, נֶפֶשׁ, feminine;
                    # the psalm's default made it God — 14 of them, found
                    # after the divine names were given their gender. Held.
                    stats["refers_to_addressee_held_gender"] += 1
                elif per == "second" and c["id"] in addr_to:
                    edges.append({"ref": ref, "lang": lang,
                                  "type": "refers_to", "src": pid_,
                                  "dst": addr_to[c["id"]],
                                  "inferred": "the addressee of the psalm's "
                                              "address"})
                    resolved[pid_] = addr_to[c["id"]]
                    stats["refers_to_addressee"] += 1
                elif per == "third" and lang == "hebrew" and \
                        num == "plural":
                    # HELD: a plural "they" is not resolved. Measured
                    # 2026-09-25 after the frog plague put "that they may
                    # sacrifice" on the rivers (8:4) and "they piled them
                    # into heaps" on the houses (8:10): a corpus sample of
                    # plural resolutions was 8 of 16 right, against 12 of 16
                    # for singular — and plurals were 2,059 of the 2,921
                    # written. The misses are "they" = people resolved to a
                    # plural THING (fields, water, altars, heavens) or to the
                    # wrong people. Telling them apart is animacy — meaning,
                    # plan 4.3. The choice made: measure, then hold if clearly
                    # worse. It was.
                    stats["refers_to_held_plural"] += 1
                elif per == "third" and lang == "hebrew":
                    # Hebrew only: Greek is step 3 of the order of work, and
                    # its resolutions have not been read
                    cands = {}
                    for h in ref_hist:
                        if h["lvl"] != lvl:
                            continue
                        for key_, (rid, g2, n2) in h["refs"].items():
                            if agree(gen, num, g2, n2):
                                cands[key_] = rid
                    if len(cands) == 1:
                        rid = next(iter(cands.values()))
                        edges.append({"ref": ref, "lang": lang,
                                      "type": "refers_to", "src": pid_,
                                      "dst": rid,
                                      "inferred": "the only agreeing "
                                                  "referent in the leading "
                                                  "text"})
                        resolved[pid_] = rid
                        stats["refers_to_unique"] += 1
                        # resolved to a named person or to God: "he", not
                        # "he/it" (rule 1 only admits names and the divine)
                        if "/" in (pnode.get("text") or ""):
                            pnode["text"] = pnode["text"].split("/")[0]
                    elif cands:
                        stats["refers_to_held_ambiguous"] += 1
                    else:
                        stats["refers_to_held_none"] += 1
            # whose HEART this clause's subject is, for the clause after it
            # (a named owner — "Pharaoh's heart" — or a resolved possessor)
            heart_owner["prev"] = None
            for e in role_by_ct.get(ct, []):
                if e.get("type") != "s":
                    continue
                sn_ = here_n.get(e.get("dst")) or {}
                if _nfc(sn_.get("lemma")) not in (_nfc("לֵב"), _nfc("לֵבָב")):
                    continue
                for q in edges[vstart:]:
                    if q.get("src") != e.get("dst"):
                        continue
                    own = None
                    if q.get("type") == "possessor":
                        own = q.get("dst")
                    elif q.get("type") == "qualifier" and \
                            (here_n.get(q.get("dst")) or {}).get("proper"):
                        own = q.get("dst")
                    if own:
                        on_ = here_n.get(own) or next(
                            (x for x in reversed(nodes)
                             if x.get("id") == own), {})
                        heart_owner["prev"] = (
                            own, on_.get("gender"),
                            on_.get("number") or "singular")
                        break
            # what this clause names, for the pronouns that follow it
            refs_ = {}
            if c["id"] not in frames_:
                for ctx in (ct, inner_of.get(ct)):
                    for e in role_by_ct.get(ctx, []):
                        d = e.get("dst")
                        n_ = here_n.get(d) or {}
                        if n_.get("implicit"):
                            rid = resolved.get(d)
                            if rid:
                                refs_[rid] = (rid, n_.get("gender"),
                                              n_.get("number"))
                            continue
                        if not n_ or n_.get("voice") or \
                                n_.get("class") == "pron" or \
                                n_.get("pos") in ("suffix", "pronoun"):
                            continue
                        if n_.get("class") != "noun" and \
                                not n_.get("proper") and \
                                not n_.get("composite"):
                            continue
                        # a NAME with no recorded number is one person: left
                        # blank it agreed with "they", and "they obey me" (Psa
                        # 18:45) and "they asked him" (Jer 38:27) resolved to
                        # the LORD and to Jeremiah
                        num_ = n_.get("number") or (
                            "singular" if n_.get("proper") else None)
                        # אֱלֹהִים is plural in FORM and, meaning God, takes
                        # singular verbs: left plural it was the candidate
                        # for "they" — "they came to Micah's house" (Jdg
                        # 18:13), "people will fear" (Ecc 3:14) — 5 of 8
                        # misses in a sample of 16
                        # ... and masculine. With no gender recorded it agreed
                        # with "she": "she has prepared her meat" (Pro 9:2,
                        # Wisdom) resolved to the LORD of 8:35 — 49 feminine
                        # pronouns resolved to a divine name, found when the
                        # acts-of-one-agent group put three of them together
                        gen_ = n_.get("gender")
                        if _nfc(n_.get("lemma")) in divine:
                            num_ = "singular"
                            gen_ = gen_ or "masculine"
                        refs_[_nfc(n_.get("lemma")) or d] = (d, gen_, num_)
            # ---- whose: the possessive suffix ----------------------------
            #
            # Psalm 23:3, first retrieval: "he restores MY soul" had its
            # possessor (the psalmist) and "for HIS name's sake" had none —
            # the "he" of the same verse resolved to the LORD, and the "his"
            # beside it was never asked.
            #
            # WRONG TURN, measured: the subject's rule (the one agreeing
            # referent in the leading text and this clause) resolved 1,475
            # and was right on 3 of a sample of 16 — "their eyes" → heart,
            # "their brothers" → instruments, "his servants" → the king
            # (Absalom's), "their waves" → waves. A verb's subject is nearly
            # always a person; a possessive's candidates include every
            # inanimate noun, and telling heart from people is animacy,
            # which is meaning (plan 4.x). So: a third-person possessive
            # resolves to ITS OWN CLAUSE'S SUBJECT, where that subject is
            # known and agrees — "he leads me for his name's sake" — and is
            # held otherwise. Second person inside a psalm's address: the
            # addressee ("YOUR rod and YOUR staff", 23:4).
            subj_ref = None
            for ctx in (ct,):
                for e in role_by_ct.get(ctx, []):
                    if e.get("type") != "s":
                        continue
                    d = e.get("dst")
                    n_ = here_n.get(d) or {}
                    if d in resolved:
                        # the implicit "he" minted just above, in this loop:
                        # not in here_n, which was taken before it existed.
                        # Missing it lost Psalm 23:3's "his name" — the case
                        # this rule was written for.
                        pn = next((x for x in reversed(nodes)
                                   if x.get("id") == d), {})
                        subj_ref = (resolved[d], pn.get("gender"),
                                    pn.get("number"))
                    elif n_ and not n_.get("voice") and \
                            n_.get("class") != "pron" and \
                            n_.get("pos") not in ("suffix", "pronoun"):
                        num_ = n_.get("number") or (
                            "singular" if n_.get("proper") else None)
                        gen_ = n_.get("gender")
                        if _nfc(n_.get("lemma")) in divine:
                            num_ = "singular"
                            gen_ = gen_ or "masculine"
                        subj_ref = (d, gen_, num_)
            quals = collections.defaultdict(list)
            for e in edges[vstart:]:
                if e.get("type") == "qualifier" and e.get("clause_role"):
                    quals[e["src"]].append(e["dst"])
            for ctx in (ct, inner_of.get(ct)):
                for e in role_by_ct.get(ctx, []):
                    # a noun inside the SUBJECT's own phrase cannot take that
                    # subject as its possessor: "HIS choicest young men" went
                    # to "choicest" (Jer 48:15), "right in HIS eyes" to "all"
                    # (Pro 21:2) — 2 of the 5 misses in a sample of 16
                    if e.get("type") == "s" and ctx == ct:
                        continue
                    stack, seen_ = [(e.get("dst"), 0)], set()
                    while stack:
                        noun, depth = stack.pop()
                        if noun in seen_ or depth > 3:
                            continue
                        seen_.add(noun)
                        for q in quals.get(noun, ()):
                            qn = here_n.get(q) or {}
                            if qn.get("pos") != "suffix":
                                stack.append((q, depth + 1))
                                continue
                            qp = qn.get("person")
                            rid = None
                            if qp == "second" and c["id"] in addr_to and \
                                    qn.get("gender") == "feminine" and \
                                    addr_to[c["id"]] in divine_ids:
                                # a feminine "your" is not God's (the soul's,
                                # Zion's), as a feminine "you" is not God
                                stats["possessor_addressee_held_gender"] += 1
                            elif qp == "second" and c["id"] in addr_to:
                                rid = addr_to[c["id"]]
                                stats["possessor_addressee"] += 1
                            elif qp == "second" and \
                                    c.get("verb_person") == "second" and \
                                    subj_ref and subj_ref[0] != noun and \
                                    agree(qn.get("gender"), qn.get("number"),
                                          subj_ref[1], subj_ref[2]):
                                # "STRETCH OUT YOUR STAFF": the "you" addressed
                                # is the command's actor, which the command
                                # structure already knows (Aaron, the one Moses
                                # is to speak to). 2026-09-26: this
                                # should flow out of the imperative
                                # structure. First-retrieval fault 7.
                                rid = subj_ref[0]
                                stats["possessor_command_actor"] += 1
                            elif qp == "third" and lang == "hebrew":
                                if subj_ref and subj_ref[0] != noun and \
                                        agree(qn.get("gender"),
                                              qn.get("number"),
                                              subj_ref[1], subj_ref[2]):
                                    rid = subj_ref[0]
                                    stats["possessor_own_subject"] += 1
                                else:
                                    stats["possessor_held"] += 1
                            if rid:
                                edges.append({
                                    "ref": ref, "lang": lang,
                                    "type": "possessor", "src": noun,
                                    "dst": rid,
                                    "inferred": (
                                        "the addressee of the psalm's address"
                                        if qp == "second" and
                                        c["id"] in addr_to else
                                        "the command's actor"
                                        if qp == "second" else
                                        "its own clause's subject, which "
                                        "agrees")})
            ref_hist.append({"lvl": lvl, "ch": ref.split(".")[1],
                             "refs": refs_})

        # ---- FULFILMENT the text states: "they did so" -----------------
        #
        # 2026-09-25, on Exo 8:13 (BSB 8:17): 'this they did' was
        # meaningless as modelled; it is the fulfillment of both
        # imperatives, and once that is known, 'they' is the
        # fulfillers (Moses and Aaron) and the 'this' is command contents.
        # Plan 1.19. The formula: a narrative wayyiqtol of עָשָׂה 'do' or
        # הָיָה 'be' with כֵּן 'so', not negated, and no NAMED subject (a
        # named one is often someone else doing the same — "the magicians
        # did so", 8:3 — which is imitation, not fulfilment). It fulfils the
        # nearest preceding command in the book (not a cohortative, which is
        # a resolve — "I will gain honor", Exo 14:4), within 40 clauses; if
        # that command is in a collection, the collection. "So" refers to
        # that command unit; the implicit "they" to the ones the command
        # chain was addressed to, walked up through `content`: Aaron (to
        # do it) and Moses (to tell him). All 21 corpus cases read: 13 of
        # the 17 checked right; the misses fulfil a gift, a request or a
        # prophecy (Gen 1:30, Jdg 6:38, 2Ki 7:20) or a reported order
        # (Gen 42:25) — not a command.
        if book != (cmd_hist[-1]["book"] if cmd_hist else book):
            cmd_hist.clear()
        # this verse's nodes AS THEY ARE NOW — here_n was taken before the
        # implicit subjects were minted, and would call "they" named
        vn = {}
        for n in reversed(nodes):
            if n.get("ref") != ref:
                break
            vn[n["id"]] = n
        for e in edges[vstart:]:
            if e.get("clause_link") and e.get("type") == "content":
                content_parent[e["dst"]] = e["src"]
            if e.get("clause_link") and e.get("type") == "command":
                unit_of[e["dst"]] = e["src"]
            if e.get("clause_link") and e.get("type") == "effect":
                unit_effect.setdefault(e["src"], []).append(e["dst"])
        for c in cinfo:
            clause_lemma[c["id"]] = _nfc(c.get("verb_lemma"))
        for ci, c in enumerate(cinfo):
            ct = ct_by_clause.get(c["id"])
            rs = [e for e in edges[vstart:]
                  if e.get("src") == ct and e.get("clause_role")]
            # the actor of a command: its stated or resolved subject
            for e in rs:
                if e.get("type") == "s":
                    d = e.get("dst")
                    n_ = vn.get(d) or {}
                    if n_.get("implicit"):
                        if resolved.get(d):
                            cmd_actor[c["id"]] = resolved[d]
                    elif n_ and not n_.get("voice"):
                        cmd_actor[c["id"]] = d
            lem = {e["type"]: _nfc((vn.get(e["dst"]) or {}).get("lemma"))
                   for e in rs if e.get("type") in ("v", "adv", "p")}
            vlems = {_nfc((vn.get(e["dst"]) or {}).get("lemma"))
                     for e in rs if e.get("type") == "v"}
            clause_seq[0] += 1
            seq_ = clause_seq[0]
            so_formula = (
                lang == "hebrew" and c.get("verb_mood") == "wayyiqtol"
                and _nfc("כֵּן") in (lem.get("adv"), lem.get("p"))
                and vlems & {_nfc("עָשָׂה"), _nfc("הָיָה")}
                and not any(e.get("type") == "neg" for e in rs))
            named_s = any(e.get("type") == "s" and not (
                vn.get(e["dst"]) or {}).get("implicit") for e in rs)
            is_formula = so_formula and not named_s
            # SOMEONE ELSE DID LIKEWISE. "The magicians did so by their secret
            # arts" (Exo 8:14): a named subject nobody commanded, doing the
            # same as the deed just done (Aaron's, 8:13). Linked to that deed
            # as `likewise`, the כֵּן lifted to the link. Only a deed done
            # AFTER the latest command: a named subject with no such deed
            # ("Jeremiah did so", carrying out a request) is left alone.
            if so_formula and named_s:
                ld = last_deed.get(book)
                ncmd = cmd_hist[-1] if cmd_hist else None
                if ld and ld[0] != c["id"] and (
                        ncmd is None or ld[1] > ncmd.get("seq", 0)):
                    edges.append({"ref": ref, "lang": lang,
                                  "type": "likewise", "src": c["id"],
                                  "dst": ld[0], "clause_link": True,
                                  "via": "כֵּן"})
                    _drop_so(edges, vstart, ct, vn)
                    stats["likewise"] += 1
            if is_formula and cmd_hist:
                cmd = cmd_hist[-1]
                unit = unit_of.get(cmd["id"], cmd["id"])
                edges.append({"ref": ref, "lang": lang, "type": "fulfils",
                              "src": c["id"], "dst": unit,
                              "clause_link": True,
                              "evidence": "'did so' / 'it was so' after a "
                                          "command"})
                stats["fulfils"] += 1
                # THE DETAIL OF "THEY DID SO". On BSB 8:17: 'and when
                # Aaron stretched out his hand with his staff and struck the
                # dust of the earth' is not an 'and'; it is a reference to
                # 'this they did' used for cause and effect. The Hebrew has
                # no 'when' — וַיֵּט ... וַיַּךְ ... וַתְּהִי is a plain narrative
                # chain; 'when' is the BSB's reading. The structure gives the
                # same reading by its own evidence: the narrative clauses that
                # follow and repeat a COMMAND's verb (stretch out, strike)
                # ELABORATE the formula and each FULFILS its command; one that
                # repeats the command's EFFECT verb (become / be) fulfils the
                # effect and is the RESULT of the acts before it — the cause
                # and effect of the command, carried into the report.
                cmd_members = [d for d, g in unit_of.items() if g == unit] \
                    or [unit]
                effects = unit_effect.get(unit, [])
                used, last_act = set(), None
                for d in cinfo[ci + 1: ci + 7]:
                    if d.get("verb_mood") != "wayyiqtol":
                        break
                    dl = clause_lemma.get(d["id"])
                    m = next((x for x in cmd_members if x not in used and
                              clause_lemma.get(x) == dl), None)
                    eff = next((x for x in effects
                                if clause_lemma.get(x) == dl), None)
                    if m:
                        used.add(m)
                        edges.append({"ref": ref, "lang": lang,
                                      "type": "elaborates", "src": d["id"],
                                      "dst": c["id"], "clause_link": True})
                        edges.append({"ref": ref, "lang": lang,
                                      "type": "fulfils", "src": d["id"],
                                      "dst": m, "clause_link": True,
                                      "evidence": "the command's verb, "
                                                  "reported"})
                        # the formula's plain 'and' to it WAS the elaboration,
                        # which `elaborates` now says: dropped, not kept twice
                        for e in edges[vstart:]:
                            if e.get("clause_link") and e.get("src") == \
                                    c["id"] and e.get("dst") == d["id"] and \
                                    e.get("type") in ("and", "then"):
                                edges.remove(e)
                                stats["and_became_elaboration"] += 1
                        last_act = d["id"]
                        stats["fulfils_command_member"] += 1
                        # and its unresolved subject is the command's actor —
                        # "he struck" fulfils "strike", whose actor is Aaron:
                        # once the fulfilment is known, so is the doer
                        dct = ct_by_clause.get(d["id"])
                        ds = next((e["dst"] for e in edges[vstart:]
                                   if e.get("src") == dct and
                                   e.get("type") == "s" and
                                   e.get("clause_role")), None)
                        if ds and (vn.get(ds) or {}).get("implicit") and \
                                ds not in resolved and cmd_actor.get(m):
                            edges.append({"ref": ref, "lang": lang,
                                          "type": "refers_to", "src": ds,
                                          "dst": cmd_actor[m],
                                          "inferred": "the actor of the "
                                                      "command it fulfils"})
                            resolved[ds] = cmd_actor[m]
                            stats["refers_to_command_actor"] += 1
                            # a command's actor is a person: "he", not "he/it"
                            if "/" in (vn[ds].get("text") or ""):
                                vn[ds]["text"] = vn[ds]["text"].split("/")[0]
                    elif eff and last_act:
                        edges.append({"ref": ref, "lang": lang,
                                      "type": "fulfils", "src": d["id"],
                                      "dst": eff, "clause_link": True,
                                      "evidence": "the command's effect, "
                                                  "reported"})
                        for e in edges[vstart:]:
                            if e.get("clause_link") and e.get("src") == \
                                    last_act and e.get("dst") == d["id"] and \
                                    e.get("type") in ("and", "then"):
                                e["type"], e["was"] = "result", e["type"]
                                break
                        else:
                            edges.append({"ref": ref, "lang": lang,
                                          "type": "result", "src": last_act,
                                          "dst": d["id"], "clause_link": True})
                        stats["fulfils_effect"] += 1
                    else:
                        break
                # "SO" BELONGS A LEVEL HIGHER. 2026-09-25: כֵּן "so,
                # thus" does not make sense as presented, but it does make
                # sense if it relates to what preceded it; it probably also
                # belongs a level higher. It is not an adverb of the doing;
                # it IS the link to what went before — here, the command
                # fulfilled. So the adverbial role goes, and the link says
                # it came from כֵּן.
                _drop_so(edges, vstart, ct, vn)
                for e in edges[vstart:]:
                    if e.get("type") == "fulfils" and e.get("src") == c["id"] \
                            and e.get("dst") == unit:
                        e["via"] = "כֵּן"
                last_deed[book] = (c["id"], seq_)
                # "they" is the ones the command chain was addressed to
                subj = next((e["dst"] for e in rs if e.get("type") == "s"),
                            None)
                if subj and _nfc("עָשָׂה") in vlems:
                    doers, seen_u, u = [], set(), unit
                    members = [d for d, g in unit_of.items() if g == unit] \
                        or [unit]
                    for m in members:
                        a_ = cmd_actor.get(m)
                        if a_ and a_ not in doers:
                            doers.append(a_)
                    while u in content_parent and u not in seen_u and \
                            len(seen_u) < 6:
                        seen_u.add(u)
                        u = content_parent[u]
                        up = unit_of.get(u, u)
                        a_ = cmd_actor.get(u)
                        if a_ and a_ not in doers and \
                                any(h["id"] == u for h in cmd_hist):
                            doers.insert(0, a_)
                        u = up
                    if len(doers) == 1:
                        rid = doers[0]
                    elif doers:
                        rid = f"{ref}#doers{c['order']}"
                        names = [(next((x for x in reversed(nodes)
                                        if x.get("id") == d), {}).get("text")
                                  or d.split("#")[-1]) for d in doers]
                        nodes.append({"id": rid, "ref": ref, "lang": lang,
                                      "local": f"doers{c['order']}",
                                      "composite": True,
                                      "text": " and ".join(names),
                                      "minted_for": "the ones a fulfilled "
                                                    "command was addressed "
                                                    "to"})
                        for d in doers:
                            edges.append({"ref": ref, "lang": lang,
                                          "type": "member", "src": rid,
                                          "dst": d})
                    else:
                        rid = None
                    if rid:
                        edges.append({"ref": ref, "lang": lang,
                                      "type": "refers_to", "src": subj,
                                      "dst": rid,
                                      "inferred": "the ones the fulfilled "
                                                  "command was addressed to"})
                        resolved[subj] = rid
                        stats["refers_to_fulfillers"] += 1
            if c.get("upper_force") == "directive" and \
                    c.get("verb_mood") != "cohortative":
                cmd_hist.append({"id": c["id"], "book": book, "seq": seq_})
        # ---- "FOR THE SAKE OF": the act's motive --------------------------
        # 2026-09-26, on Psa 23:3 "he guides me in paths of
        # righteousness for his name's sake": the 'for sake of' ləmaʿan link
        # was missing; it is the motivation that links the action to
        # the Lord's name. A reading is not a kind — but here the text MARKS
        # it: לְמַעַן before a noun names what the act is done for ("for the
        # sake of the fifty", Gen 18:24; "for my servant David's sake"). So
        # that prepositional role is the clause's `motive`, the preposition
        # kept on it. (Before a CLAUSE, לְמַעַן is "so that" — a purpose, not
        # this; those stay as they are.)
        for e in edges[vstart:]:
            if e.get("type") == "pp" and e.get("clause_role") and \
                    _nfc(e.get("prep") or "") == _nfc("לְמַעַן"):
                e["type"], e["was"] = "motive", "pp"
                stats["motive"] += 1
        # ---- "AND NOT": an effect, or a failed one ------------------------
        # 2026-09-26, on the gnat plague: the verse 19 example looks
        # like an effect of Pharaoh's heart being hardened. The verse 18
        # example is also an effect, though technically a failed
        # effect, which is a specialization of the pattern. Only where the
        # structure marks it:
        #   the heart hardened, AND NOT he listened — the 'and' into a
        #     negated clause whose subject is the heart's owner (rule 7 of
        #     refers_to) is the heart's RESULT;
        #   they did X TO achieve Y, AND NOT they could — the 'and' into a
        #     negated יָכֹל "be able" from an attempt that has a purpose is
        #     a FAILED RESULT: the purpose not achieved.
        neg_ct = {e["src"] for e in edges[vstart:]
                  if e.get("type") == "neg" and e.get("clause_role")}
        purp_cl = set()
        for e in edges[vstart:]:
            if e.get("type") == "purpose" and e.get("clause_link"):
                purp_cl |= {e["src"], e["dst"]}
        heart_subj = {r_ for r_, t_ in resolved.items()
                      if any(x.get("src") == r_ and x.get("type") ==
                             "refers_to" and "heart" in x.get("inferred", "")
                             for x in edges[vstart:])}
        for e in edges[vstart:]:
            if e.get("type") != "and" or not e.get("clause_link"):
                continue
            d = e.get("dst")
            dct = ct_by_clause.get(d)
            if dct not in neg_ct:
                continue
            # "Could not" with NO complement of its own elides the purpose:
            # "they could not [bring forth the gnats]". With one it states a
            # separate inability — Gen 19:19, "you spared my life, and I am
            # not able TO ESCAPE" — which is not the purpose failing.
            own = any(x.get("src") == d and x.get("clause_link") and
                      x.get("type") in ("within", "content", "purpose")
                      for x in edges[vstart:])
            if clause_lemma.get(d) == _nfc("יָכֹל") and e.get("src") in purp_cl \
                    and not own:
                e["type"], e["was"] = "failed_result", "and"
                e["evidence"] = "an attempt with a purpose, then 'and not " \
                                "able'"
                stats["failed_result"] += 1
            elif any(x.get("src") == dct and x.get("type") == "s" and
                     x.get("dst") in heart_subj for x in edges[vstart:]):
                e["type"], e["was"] = "result", "and"
                e["evidence"] = "the heart hardened, then 'and not'"
                stats["result_heart"] += 1

        # An action-state pair whose STATE is now known to fulfil a specific
        # command is superseded by that fulfilment: the pair was matched by
        # lemma alone and, in the gnat plague, joined the LORD's SAYING
        # ("he said to Moses", 8:12) to Aaron's acts (8:13) — first-retrieval
        # fault 4. The fulfilment names the command itself.
        fulfilled = {e["src"] for e in edges[vstart:]
                     if e.get("type") == "fulfils" and e.get("clause_link")}
        drop = {e["src"] for e in edges[vstart:]
                if e.get("type") == "state" and e.get("dst") in fulfilled}
        if drop:
            edges[vstart:] = [e for e in edges[vstart:]
                              if e.get("src") not in drop]
            nodes[:] = [n for n in nodes if n.get("id") not in drop] \
                if len(drop) else nodes
            stats["pairs_superseded_by_fulfilment"] += len(drop)

        # ---- ACTS OF ONE AGENT ------------------------------------------
        # 2026-09-26, on Psalm 23:2-3: verses 2-3 could be a
        # collection of 4 actions of the Lord with a single subject,
        # structurally fitting a similar pattern surrounded by first-person
        # statements — then built as a new group, acts of one agent.
        # He makes me lie down / he leads me / he restores my soul / he
        # guides me: four clauses, no word joining them, none a narrative
        # "and then", each stating its subject only in its verb, and every
        # one of those subjects resolved to the same referent. The agent sits
        # on the group, as Parallel's subject does (Psa 119:105). A run
        # crosses verses, within a chapter; minted where it reaches two.
        # Measured before building: 207 runs, 189 in the Psalms; its
        # precision is the pronoun rules' — the grouping adds no guess.
        # (The "I" statements around it are the proposed Context kind.)
        inner_ = {e["dst"] for e in edges[vstart:]
                  if e.get("clause_link") and e.get("type") in
                  ("within", "content", "purpose", "as")
                  and "#cl" in (e.get("src") or "")}
        subj_ = {e["src"]: e["dst"] for e in edges[vstart:]
                 if e.get("type") == "s" and e.get("clause_role")}
        refto_ = {e["src"]: e["dst"] for e in edges[vstart:]
                  if e.get("type") == "refers_to"}
        chap_ = (book, ref.split(".")[1])
        for c in cinfo:
            ct = ct_by_clause.get(c["id"])
            agent = refto_.get(subj_.get(ct))
            ok = agent and c["id"] not in inner_ and \
                c.get("verb_mood") not in ("wayyiqtol", None)
            run = acts_run.get("run")
            if ok and run and run["chap"] == chap_ and \
                    run["agent"] == agent:
                last = run["members"][-1]
                joined = any(e.get("clause_link") and
                             {e.get("src"), e.get("dst")} == {last, c["id"]}
                             for e in edges[run["scan"]:])
                if not joined:
                    run["members"].append(c["id"])
                    if not run.get("gid"):
                        gid = f"{ref}#acts{c.get('order', 0)}"
                        run["gid"] = gid
                        nodes.append({
                            "id": gid, "ref": ref, "lang": lang,
                            "local": f"acts{c.get('order', 0)}",
                            "pair": True, "kind": "acts", "ordered": True,
                            "spans_verses": run["ref"] != ref,
                            "evidence": "clauses in a row, joined by no "
                                        "word, each subject resolved to "
                                        "the same agent",
                            "text": "acts of one agent"})
                        edges.append({"ref": ref, "lang": lang, "type": "s",
                                      "src": gid, "dst": agent,
                                      "clause_link": True,
                                      "inferred": "the one agent every act's "
                                                  "subject resolves to"})
                        for k_, m_ in enumerate(run["members"], 1):
                            edges.append({"ref": ref, "lang": lang,
                                          "type": "agent_act", "src": gid,
                                          "dst": m_, "order": k_,
                                          "clause_link": True})
                        stats["agent_acts_groups"] += 1
                        stats["agent_acts_members"] += 2
                    else:
                        edges.append({"ref": ref, "lang": lang,
                                      "type": "agent_act", "src": run["gid"],
                                      "dst": c["id"],
                                      "order": len(run["members"]),
                                      "clause_link": True})
                        stats["agent_acts_members"] += 1
                    run["scan"] = vstart
                    continue
            acts_run["run"] = {"chap": chap_, "agent": agent,
                               "members": [c["id"]], "ref": ref,
                               "scan": vstart} if ok else None

        # ---- A NEGATIVE SHARED BY PARALLEL LINES -------------------------
        # Psa 9:19 (BSB 9:18): "the needy will NOT always be forgotten; [nor]
        # the hope of the afflicted perish forever" — one fronted לֹא governs
        # both lines; the graph asserted the second line's opposite. DeepSeek
        # found it; confirmed by hand. MEASURED FIRST: first line negated, second
        # not, no conjunction, same verb form — 112 pairs in the poetic
        # books, and a sample of 16 was 0 right: asyndetic "not X; Y" is
        # nearly always a CONTRAST ("they did not thirst; he led them
        # through the deserts", Isa 48:21). What marks the shared negative
        # here is that both lines carry the same span, "forever" (נֵצַח /
        # עַד, by Strong's: an earlier try with a hand-typed נֶצַח matched
        # nothing — the corpus spells it נֵצַח). That mark finds exactly one
        # pair in the Hebrew Bible: this verse.
        vnodes_ = {}
        for n_ in reversed(nodes):
            if n_.get("ref") != ref:
                break
            vnodes_[n_["id"]] = n_
        ever_strong = {"5331", "5703", "5769", "8548"}
        negs_ = {e["src"]: e for e in edges[vstart:]
                 if e.get("type") == "neg" and e.get("clause_role")}
        ever_ = collections.defaultdict(set)
        for e in edges[vstart:]:
            if e.get("clause_role") and e.get("type") in ("pp", "adv"):
                s_ = re.sub(r"\D", "", str((vnodes_.get(e["dst"]) or {})
                                           .get("strong") or "")).lstrip("0")
                if s_ in ever_strong:
                    ever_[e["src"]].add(s_)
        paired_ = {(e["src"], e["dst"]) for e in edges[vstart:]
                   if e.get("clause_link")}
        for a_, b_ in zip(cinfo, cinfo[1:]):
            cta, ctb = ct_by_clause.get(a_["id"]), ct_by_clause.get(b_["id"])
            if cta in negs_ and ctb not in negs_ and ever_.get(cta) and \
                    ever_.get(ctb) and not b_.get("connective") and \
                    (a_["id"], b_["id"]) not in paired_ and \
                    (b_["id"], a_["id"]) not in paired_:
                edges.append({"ref": ref, "lang": lang, "type": "neg",
                              "src": ctb, "dst": negs_[cta]["dst"],
                              "clause_role": True,
                              "inferred": "the negative of the parallel line "
                                          "before it — both lines 'forever'"})
                stats["neg_shared_parallel"] += 1

        # ---- A GAPPED VERB: AN OBJECT BORROWS THE VERB BEFORE IT ----------
        # Psa 103:1 "Bless the LORD, O my soul, and all within me, [bless]
        # his holy name" — the second line was a verbless ASSERTION linked to
        # nothing (a spot check; P-2026-09-26-22). An OBJECT cannot
        # stand without a verb, so a clause with an object and no verb has a
        # gapped one: it borrows the verb of the nearest clause before it (in
        # the verse, up to three back) that has a verb AND an object of its
        # own. Measured: 1,032 with any verbed clause before, a sample 11/16
        # ("he gave up their cattle to the hail, and their livestock [he gave
        # up] to lightning", Psa 78:48); misses were a "clause before" that
        # takes no object ("Jether died"), which the object test removes
        # (≈11/13). The broader "second line = first line minus its verb"
        # (Pro 14:19, 602 pairs) was 5-6/16 — real verbless sentences share
        # the shape — and is not built.
        roles_ = collections.defaultdict(set)
        for e in edges[vstart:]:
            if e.get("clause_role"):
                roles_[e["src"]].add(e["type"])
        for k_, b_ in enumerate(cinfo if lang == "hebrew" else []):
            # Hebrew only: measured on Hebrew; Greek structure is step 3
            ctb = ct_by_clause.get(b_["id"])
            if not ctb or "o" not in roles_[ctb] or "v" in roles_[ctb]:
                continue
            host = next((cinfo[j] for j in range(k_ - 1, max(-1, k_ - 4), -1)
                         if {"v", "o"} <= roles_[ct_by_clause.get(
                             cinfo[j]["id"])]), None)
            if host is None:
                continue
            hv = next((e["dst"] for e in edges[vstart:]
                       if e.get("type") == "v" and e.get("clause_role") and
                       e.get("src") == ct_by_clause.get(host["id"])), None)
            if not hv:
                continue
            edges.append({"ref": ref, "lang": lang, "type": "v",
                          "src": ctb, "dst": hv, "clause_role": True,
                          "inferred": "the verb of the line before, gapped"})
            stats["verb_gapped_carried"] += 1

        # ---- A COMPARISON WHOSE ATTACHMENT THE HEBREW LEAVES OPEN ---------
        # Ezk 40:25 "windows to it and to its porches all around; LIKE THESE
        # WINDOWS fifty cubits the length" — MACULA attaches the comparison
        # to the next clause; it was read, by hand and by DeepSeek, with the
        # windows before. The original language could mark what it applies to
        # as indeterminate, and a BSB pass can figure out what it applies to.
        # A כְּ-comparison opening a clause, whose noun repeats a noun of the
        # clause before, could go with either: it is marked `attachment:
        # indeterminate`, and where the Berean text puts the comparison's
        # word in the SAME English sentence as the clause before and not as
        # its own clause (its editors' Strong's tags show which word is
        # which), it moves there as a "like" qualifier of that noun, marked
        # the BSB's reading. Measured on the 46 in the Hebrew Bible: the BSB
        # agrees with MACULA in 12, gives no evidence in 32 (MACULA stands),
        # and moves one — Ezk 40:25.
        if lang == "hebrew":
            quals_ = collections.defaultdict(list)
            for e in edges[vstart:]:
                if e.get("type") == "qualifier":
                    quals_[e["src"]].append(e["dst"])
            rl_ = collections.defaultdict(list)
            for e in edges[vstart:]:
                if e.get("clause_role") and e.get("type") not in (
                        "asserts", "qualifier"):
                    rl_[e["src"]].append(e)
            text_, spans_ = _bsb_verse(ref)
            bounds_ = [m.end() for m in re.finditer(r"[.;:?!]", text_)]
            sent_ = lambda pos: sum(1 for x in bounds_ if x <= pos)

            def st_(i):
                return "h" + re.sub(r"\D", "", str((vnodes_.get(i) or {})
                                                   .get("strong") or "")) \
                    .lstrip("0")

            def words_(rl, skip=None):
                out = set()
                for e in rl:
                    if e is skip:
                        continue
                    out.add(st_(e["dst"]))
                    out.update(st_(q) for q in quals_.get(e["dst"], []))
                return {x for x in out if x != "h"}
            for a_, b_ in zip(cinfo, cinfo[1:]):
                cta, ctb = ct_by_clause.get(a_["id"]), \
                    ct_by_clause.get(b_["id"])
                cmp_ = next((e for e in rl_.get(ctb, []) if e["type"] == "pp"
                             and _nfc(e.get("prep")) == _nfc("כְּ")), None)
                if cmp_ is None:
                    continue
                lem_ = _nfc((vnodes_.get(cmp_["dst"]) or {}).get("lemma"))
                twin = next((e["dst"] for e in rl_.get(cta, [])
                             if lem_ and _nfc((vnodes_.get(e["dst"]) or {})
                                              .get("lemma")) == lem_), None)
                if not twin:
                    continue
                cmp_["attachment"] = "indeterminate — the comparison repeats " \
                                     "a noun of the clause before"
                stats["comparison_indeterminate"] += 1
                occ = [s for s in spans_ if s[2] == st_(cmp_["dst"])]
                wb = words_(rl_.get(ctb, []), cmp_) - {st_(cmp_["dst"])}
                wa = words_(rl_.get(cta, [])) - {st_(cmp_["dst"])}
                sb = {sent_(s[0]) for s in spans_ if s[2] in wb}
                sa = {sent_(s[0]) for s in spans_ if s[2] in wa}
                if len(occ) < 2 or not sb:
                    continue
                cs = sent_(occ[-1][0])
                if cs in sb or not (cs in sa or sent_(occ[0][0]) == cs):
                    continue
                edges[vstart:] = [e for e in edges[vstart:] if e is not cmp_]
                dst_ = cmp_["dst"]
                if dst_ == twin:
                    # the two "windows" share one node (ids are per word
                    # text in a verse until plan 2.5): the compared-with
                    # windows get their own, or the qualifier loops on itself
                    src_n = vnodes_.get(dst_) or {}
                    dst_ = f"{dst_}_like{b_.get('order', 0)}"
                    nodes.append({**{k: v for k, v in src_n.items()
                                     if k not in ("id", "local")},
                                  "id": dst_, "local": dst_.split("#")[1],
                                  "minted_for": "the second of two words "
                                                "sharing a node, compared"})
                edges.append({"ref": ref, "lang": lang, "type": "qualifier",
                              "rel": "like", "src": twin,
                              "dst": dst_, "clause_role": True,
                              "clause_order": a_.get("order"),
                              "reading": "BSB",
                              "inferred": "the BSB places the comparison "
                                          "with the clause before"})
                stats["comparison_moved_by_bsb"] += 1

        # ---- A BARE PARTICIPLE DESCRIBES THE SUBJECT BEFORE IT -----------
        # Isa 15:3: "on its roofs and in its squares all of it wails, GOING
        # DOWN IN WEEPING" — the participle clause stood alone as an
        # assertion. DeepSeek flagged it: it should be a modifier, as it
        # does not stand on its own. Measured: any subjectless, unlinked
        # participle clause after a finite one — 112, a sample 9/16 not
        # independent, of two kinds and with "WHOEVER eats leaven" (the
        # subject of what follows) among the misses. Refined: no subject of
        # its own, no conjunction, not substantival (MACULA glosses those
        # "[one who] ...", "[those who] ..."), after a finite clause, and
        # AGREEING with that clause's subject — 65, a sample 12/16: "they ate
        # the feast, SACRIFICING peace offerings" (2Ch 30:22), "he went out,
        # LEPROUS" (2Ki 5:27), "hear this, O leaders, who LOATHE justice"
        # (Mic 3:9). Misses carry the main statement themselves ("the Root of
        # Jesse will be STANDING as a banner", Isa 11:10).
        linked_in = {e["dst"] for e in edges[vstart:]
                     if e.get("clause_link") and
                     (e.get("src") or "").startswith(ref + "#cl")}
        subj_of = {e["src"]: e["dst"] for e in edges[vstart:]
                   if e.get("type") == "s" and e.get("clause_role")}
        role_types = collections.defaultdict(set)
        for e in edges[vstart:]:
            if e.get("clause_role"):
                role_types[e["src"]].add(e["type"])
        finite = {"qatal", "yiqtol", "wayyiqtol", "weqatal", "imperative",
                  "jussive", "cohortative"}
        for a_, b_ in zip(cinfo, cinfo[1:]):
            ctb = ct_by_clause.get(b_["id"])
            if not (b_.get("verb_mood") or "").startswith("participle") or \
                    "s" in role_types.get(ctb, ()) or b_.get("connective") or \
                    b_["id"] in linked_in or b_["id"] in within_dst or \
                    a_.get("verb_mood") not in finite:
                continue
            gl_ = (b_.get("text") or "")[:16]
            if gl_.startswith("[") and ("who" in gl_ or "one" in gl_):
                continue                    # substantival: "[one who] eats"
            vb_ = vnodes_.get(b_["id"] + "v") or {}
            sa_ = vnodes_.get(subj_of.get(ct_by_clause.get(a_["id"]))) or {}
            n1, n2 = vb_.get("number"), sa_.get("number")
            g1, g2 = vb_.get("gender"), sa_.get("gender")
            if not (n1 and n2 and n1 == n2) or \
                    (g1 and g2 and g1 != g2 and "common" not in (g1, g2)):
                continue
            edges.append({"ref": ref, "lang": lang, "type": "describing",
                          "src": a_["id"], "dst": b_["id"],
                          "clause_link": True,
                          "evidence": "a bare participle agreeing with the "
                                      "subject of the clause before"})
            stats["describing"] += 1
            # no longer a part of the speech or writing on its own: it hangs
            # on the clause it describes
            before_ = len(edges)
            edges[vstart:] = [e for e in edges[vstart:]
                              if not (e.get("type") == "part" and
                                      e.get("dst") == b_["id"])]
            stats["describing_part_dropped"] += before_ - len(edges)

        # ---- "BEWARE" AND WHAT TO BEWARE OF -------------------------------
        # Job 36:21 "take heed; do not turn to iniquity, for this you have
        # chosen": the prohibition was the command of the group and "take
        # heed" floated (DeepSeek). Not separate imperatives, but the
        # latter informs the former. הִשָּׁמֶר (שָׁמַר, niphal) is "beware":
        # like a verb of saying, it has a content — the prohibition after it.
        # Measured: "beware" with a negated clause straight after, 8 in the
        # Hebrew Bible, 7 right ("be careful NOT to drink wine", Jdg 13:4;
        # "take heed; do NOT carry a load", Jer 17:21); the miss, Deu 4:15,
        # is a negated clause already linked as the reason, so a clause with
        # any incoming link but "and" is left alone. Where the prohibition was
        # a command of an Imperative group, "beware" becomes the command.
        in_links = collections.defaultdict(set)
        for e in edges[vstart:]:
            if e.get("clause_link") and \
                    (e.get("src") or "").startswith(ref + "#cl"):
                in_links[e["dst"]].add(e["type"])
        for a_, b_ in zip(cinfo, cinfo[1:]):
            if _nfc(a_.get("verb_lemma") or "") != _nfc("שָׁמַר") or \
                    a_.get("verb_stem") != "niphal" or \
                    ct_by_clause.get(b_["id"]) not in negs_ or \
                    in_links.get(b_["id"], set()) - {"and"}:
                continue
            edges[vstart:] = [e for e in edges[vstart:]
                              if not (e.get("type") == "and" and
                                      e.get("src") == a_["id"] and
                                      e.get("dst") == b_["id"])]
            edges.append({"ref": ref, "lang": lang, "type": "content",
                          "src": a_["id"], "dst": b_["id"],
                          "clause_link": True,
                          "evidence": "beware (שָׁמַר niphal) and the "
                                      "prohibition that says what of"})
            took = False
            for e in edges[vstart:]:
                if e.get("type") == "command" and e.get("dst") == b_["id"]:
                    e["dst"] = a_["id"]
                    took = True
                    stats["beware_took_command"] += 1
            if took:
                # now inside the group, not a part of the speech beside it
                edges[vstart:] = [e for e in edges[vstart:]
                                  if not (e.get("type") == "part" and
                                          e.get("dst") == a_["id"])]
            stats["beware_content"] += 1

        # ---- CONCESSION: the obstacle, what holds anyway, and why ---------
        # 2026-09-26, on Psa 23:4: 'Even though I walk through the
        # valley of the shadow of death' is in effect an obstacle overcome,
        # an overridden motivation. The structure holds what the text marks:
        # the concession (גַּם כִּי), the claim that holds anyway, and — where
        # a כִּי gives it — that claim's ground ("for you are with me"). Where
        # the held claim is NEGATED, the response the concession would have
        # brought is named by the text and denied: "I will NOT FEAR" → denied
        # "fear". That it is an overridden MOTIVATION is the reading over
        # this group, the meaning graph's. Only גַּם כִּי: a fronted כִּי is
        # when / if / though undecided, and a negation does not decide it
        # ("if you meet anyone, do not greet him", 2Ki 4:29).
        neg_ct_ = {e["src"] for e in edges[vstart:]
                   if e.get("type") == "neg" and e.get("clause_role")}
        for e in list(edges[vstart:]):
            if e.get("type") != "though" or not e.get("clause_link"):
                continue
            held, conceded = e["src"], e["dst"]
            ground = next((x["dst"] for x in edges[vstart:]
                           if x.get("type") == "because" and
                           x.get("clause_link") and x.get("src") == held),
                          None)
            c_ord = next((c.get("order", 0) for c in cinfo
                          if c["id"] == conceded), 0)
            gid = f"{ref}#conc{c_ord}"
            grp = {"id": gid, "ref": ref, "lang": lang,
                   "local": gid.split("#")[1], "pair": True,
                   "kind": "concession", "ordered": True,
                   "evidence": "גַּם כִּי: even though ... still",
                   "text": "concession"}
            if ct_by_clause.get(held) in neg_ct_:
                vn_ = next((x for x in reversed(nodes)
                            if x.get("id") == held + "v"), {})
                grp["denied"] = vn_.get("text") or next(
                    (c.get("verb_lemma") for c in cinfo if c["id"] == held),
                    None)
                stats["concession_denied"] += 1
            nodes.append(grp)
            for k_, (typ, m_) in enumerate((("conceded", conceded),
                                            ("holds_anyway", held),
                                            ("its_ground", ground)), 1):
                if m_:
                    edges.append({"ref": ref, "lang": lang, "type": typ,
                                  "src": gid, "dst": m_, "order": k_,
                                  "clause_link": True})
            stats["concession_groups"] += 1

        # ---- AN EXPLICIT "YOU" IN A PSALM'S ADDRESS ----------------------
        # Psa 23:4 "YOU are with me" — אַתָּה, a pronoun word, not a verb's
        # person — was left unresolved: refers_to rule 2 reached only the
        # implicit "you" a verb carries, and a verbless clause has no verb.
        # 353 explicit second-person pronouns in the Psalms were unresolved.
        # Same rule, same guard: the address's addressee, never God for a
        # feminine "you".
        have_ref = {e["src"] for e in edges[vstart:]
                    if e.get("type") == "refers_to"}
        for e in list(edges[vstart:]):
            if not e.get("clause_role") or e.get("type") in ("v", "asserts"):
                continue
            cid_ = e["src"].replace("#ct", "#cl").rstrip("c")
            if cid_ not in addr_to or e["dst"] in have_ref:
                continue
            pn_ = here_n.get(e["dst"]) or {}
            if pn_.get("pos") != "pronoun" or pn_.get("person") != "second":
                continue
            if pn_.get("gender") == "feminine" and \
                    addr_to[cid_] in divine_ids:
                stats["refers_to_addressee_held_gender"] += 1
                continue
            edges.append({"ref": ref, "lang": lang, "type": "refers_to",
                          "src": e["dst"], "dst": addr_to[cid_],
                          "inferred": "the addressee of the psalm's "
                                      "address"})
            have_ref.add(e["dst"])
            stats["refers_to_addressee_explicit"] += 1

        # ---- WITH NO VERB, THE PREPOSITION IS THE PREDICATE --------------
        # 2026-09-26, on Psa 23:4 "you [are] with me": the Hebrew
        # עִמָּד 'with me' should be represented in the graph. It was
        # only a label on the predicate edge, "is · no verb in Hebrew:
        # are.with" — MACULA's gloss glues the supplied "[are]" to it — so
        # the word that carries the whole claim was no node: nothing to click,
        # nothing to count. In a VERBLESS clause whose predicate is a
        # prepositional phrase, the preposition does the verb's work: it
        # becomes the predicate node, and its object hangs off it
        # (`prep_object`). 4,618 clauses: "[is] in", "[belongs] to", "[are]
        # with". Done last, after every rule that reads roles by their filler.
        # With a verb, a preposition stays on its role's edge ("leads me
        # BESIDE waters"): there the verb is the claim.
        hasv_ = {e["src"] for e in edges[vstart:]
                 if e.get("type") == "v" and e.get("clause_role")}
        prep_made_ = set()
        for e in list(edges[vstart:]):
            if e.get("type") != "p" or not e.get("clause_role") or \
                    not e.get("prep") or e["src"] in hasv_:
                continue
            lem_ = _nfc(e["prep"])
            gl_ = " ".join(t for t in (e.get("prep_gloss") or "").split(".")
                           if t and not t.startswith("[")
                           and not t.endswith("]")) or \
                (e.get("prep_gloss") or "").replace(".", " ")
            loc_ = f"prep{(e['src'].split('#ct')[-1])}"
            clause_ord = int(loc_[4:]) if loc_[4:].isdigit() else None
            while f"{ref}#{loc_}" in prep_made_:     # two in one clause
                loc_ += "b"
            prep_made_.add(f"{ref}#{loc_}")
            pid_ = f"{ref}#{loc_}"
            nodes.append({"id": pid_, "ref": ref, "lang": lang,
                          "local": loc_, "text": gl_ or lem_, "lemma": lem_,
                          **({"strong": _PREP_STRONG[lem_]}
                             if lem_ in _PREP_STRONG else {}),
                          "pos": "preposition", "class": "prep",
                          "predicate": True})
            edges.append({"ref": ref, "lang": lang, "type": "prep_object",
                          "src": pid_, "dst": e["dst"], "clause_role": True,
                          "clause_order": clause_ord})
            e["dst"] = pid_
            e.pop("prep", None)
            e.pop("prep_gloss", None)
            stats["preposition_predicates"] += 1

        # ---- "[HE IS] THE ONE WHO FORGIVES": ONE NODE, NOT TWO -----------
        # 2026-09-26, on Psa 103:3: the nested assertions were not
        # understandable. הַסֹּלֵחַ is a participle used as a noun: MACULA
        # wraps it in a verbless frame ("[he is] ...", P2CL) whose only
        # content is the participle clause as its predicate. The frame says
        # nothing of its own, so it is folded into the participle clause —
        # everything that pointed at either points at the one — and the
        # clause is marked a description (`substantival`). 60 in the Hebrew
        # Bible, 29 in the Psalms (the hymns' "who made ..., who does ...").
        # Applied once, at the end of the build (_fold_frames), because a
        # group can reach a frame from a later verse.
        rt_ = collections.defaultdict(set)
        for e in edges[vstart:]:
            if e.get("clause_role") and e.get("type") != "asserts":
                rt_[e["src"]].add(e["type"])
        for e in edges[vstart:]:
            if e.get("type") != "within" or not e.get("clause_link") or \
                    e.get("role") != "p":
                continue
            x_, y_ = e["src"], e["dst"]
            ctx_ = ct_by_clause.get(x_)
            yc_ = next((c for c in cinfo if c["id"] == y_), None)
            if not ctx_ or rt_.get(ctx_) or yc_ is None or \
                    not (yc_.get("verb_mood") or "").startswith("participle"):
                continue
            _FOLD[x_] = y_
            _FOLD_CT.add(ctx_)
            yc_["substantival"] = True
            stats["frame_folded"] += 1
            # ITS SUBJECT. 2026-09-26: psalm 103:3 needs to have a
            # subject node for each of the parts in vs 3-5, or a
            # collection and a common subject; either way the subject
            # node was missing and that was never the intent. The frame was
            # "[HE is] the one who forgives"; folding it dropped the "he".
            # A participle does not carry person, so the subject is minted
            # as every unstated subject is — third person, the participle's
            # gender and number — and resolved (or held) like any other.
            cty_ = ct_by_clause.get(y_)
            vy_ = next((n for n in reversed(nodes)
                        if n.get("id") == y_ + "v"), {})
            if cty_ and not any(e.get("type") == "s" and
                                e.get("src") == cty_ for e in edges[vstart:]):
                sid_ = f"{ref}#he{yc_.get('order', 0)}d"
                g_, n_ = vy_.get("gender") or "masculine", \
                    vy_.get("number") or "singular"
                nodes.append({"id": sid_, "ref": ref, "lang": lang,
                              "local": sid_.split("#")[1], "implicit": True,
                              "person": "third", "gender": g_, "number": n_,
                              "class": "pron", "pos": "pronoun",
                              "text": _pronoun("third", g_, n_),
                              "minted_for": "the unstated subject of "
                                            "'[he is] the one who ...'"})
                edges.append({"ref": ref, "lang": lang, "type": "s",
                              "src": cty_, "dst": sid_, "clause_role": True,
                              "implicit": True})
                yc_["desc_subject"] = sid_
                stats["description_subject_minted"] += 1

        # ---- A RUN OF DESCRIPTIONS IS ONE COLLECTION WITH ONE SUBJECT ------
        # Psa 103:3-5: "who forgives all your iniquity, who heals all your
        # diseases, who redeems your life from the pit, who crowns you ...,
        # who satisfies you with good" — five descriptions of one referent.
        # A collection and a common subject that applies to all.
        # Consecutive substantival ("the one who") clauses, across verses
        # within a chapter, are one group; a folded frame between them does
        # not break the run, any other clause does. The group's subject is
        # the first description's minted "he"; each description keeps its
        # own.
        chap_d = (book, ref.split(".")[1])
        for c in cinfo:
            if c["id"] in _FOLD:
                continue                    # the frame, folded away
            run_d = desc_run.get("run")
            if not c.get("substantival"):
                desc_run["run"] = None
                continue
            if run_d and run_d["chap"] == chap_d:
                run_d["members"].append(c["id"])
                if not run_d.get("gid"):
                    gid = f"{ref}#desc{c.get('order', 0)}"
                    run_d["gid"] = gid
                    nodes.append({"id": gid, "ref": ref, "lang": lang,
                                  "local": gid.split("#")[1], "pair": True,
                                  "kind": "descriptions", "ordered": True,
                                  "spans_verses": run_d["ref"] != ref,
                                  "evidence": "consecutive 'the one who ...' "
                                              "descriptions",
                                  "text": "descriptions of one referent"})
                    if run_d.get("subject"):
                        edges.append({"ref": ref, "lang": lang, "type": "s",
                                      "src": gid, "dst": run_d["subject"],
                                      "clause_link": True,
                                      "inferred": "the one the descriptions "
                                                  "describe"})
                    for k_, m_ in enumerate(run_d["members"], 1):
                        edges.append({"ref": ref, "lang": lang,
                                      "type": "described_as", "src": gid,
                                      "dst": m_, "order": k_,
                                      "clause_link": True})
                    stats["description_groups"] += 1
                else:
                    edges.append({"ref": ref, "lang": lang,
                                  "type": "described_as", "src": run_d["gid"],
                                  "dst": c["id"],
                                  "order": len(run_d["members"]),
                                  "clause_link": True})
            else:
                desc_run["run"] = {"chap": chap_d, "members": [c["id"]],
                                   "ref": ref,
                                   "subject": c.get("desc_subject")}

        # ---- orphans, held AS orphans ---------------------------------
        #
        # 2026-09-21: at some point the orphans are held as orphans; as the
        # graph is built out it might become clear, or there might be so few
        # that an LLM pass is affordable.
        #
        # Exodus 8:1 is the case. "Stretch out your hand … AND bring up the
        # frogs" is a coordinate pair of commands, and the `content` rule
        # takes only the NEXT sibling, so the second half of what Aaron is
        # told to do hangs on nothing.
        #
        # An orphan dropped is an invisible gap; an orphan RECORDED is a
        # known one that can be counted, looked at, and later resolved —
        # either because a rule arrives that attaches it, or because there
        # are few enough to be worth a model's attention. Marking it costs a
        # field and keeps the option.
        #
        # JOINED TO NOTHING, not "pointed at by nothing". Once `if` attached
        # forward, "I am about to strike your territory" (Exo 7:27) became
        # the HEAD of its condition — the source of an edge, the destination
        # of none — and the old test still called it an orphan. A clause that
        # heads a relation is not orphaned; one with no relation in either
        # direction is.
        # BEING IN THE PSALM DOES NOT COUNT. Every clause of a psalm is a
        # part of its Writing, so counting that as "joined" made 1,794
        # clauses of the Psalms look attached when nothing in the psalm
        # relates them to anything — the measure moved and the structure had
        # not. A speech turn's parts still count: being part of a speech ties
        # a clause to the saying that frames it.
        attached = set()
        for e in edges[vstart:]:
            if (e.get("src") or "").endswith("#writing"):
                continue
            if e.get("clause_link") or e.get("type") == "content":
                attached.add(e.get("dst"))
                if (e.get("src") or "").startswith(ref + "#cl"):
                    attached.add(e["src"])
        for c in cinfo[1:]:
            if c["id"] not in attached:
                c["orphan"] = True
                stats["orphan_clauses"] += 1

        # the verse joins the window AFTER its own resolution, so a clause
        # never counts itself as prior context
        window.append((ref, cinfo))
        spent = time.time() - t_verse
        if spent > SLOW_VERSE:
            _BREAKS.append((ref, f"slow verse: {spent:.1f}s"))
    stats["verses"] = len(by)
    _fold_frames(nodes, edges, stats)
    if lang == "hebrew":
        _plugin_rules(nodes, edges, stats, "original")
        _reading_rules(nodes, edges, stats)
        _bsb_fallback(nodes, edges, stats)
        _plugin_rules(nodes, edges, stats, "translation")
    return nodes, edges, stats


def _plugin_rules(nodes, edges, stats, basis):
    """THE APPROVED PLUG-IN RULES (tools/fixrules/rules/). 2026-09-26:
    DeepSeek audits one verse at a time and writes each fix as a rule for a
    released framework, "a detection pass, a fix pass, and a validate pass".
    A rule lands in rules/ only after it is measured and approved by hand.
    Original-language rules run before the readings, so a reading never
    pre-empts them; translation rules run last, after the BSB fallback."""
    sys.path.insert(0, str(ROOT / "tools"))
    from fixrules import framework as F
    rules = [m for m in F.load() if m.BASIS == basis]
    if not rules:
        return
    words = {}
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        r = json.loads(line)
        if r.get("ref"):
            words[r["ref"]] = r["words"]
    refs = sorted({n["ref"] for n in nodes if n.get("ref")})
    bsb = {r: _bsb_verse(r) for r in refs}
    rep = F.run(rules, nodes, edges, "hebrew", bsb=bsb, words=words)
    for name, r in rep.items():
        for k in ("detected", "fixed", "invalid", "rejected"):
            stats[f"rule_{name}_{k}"] = len(r[k])


_BSB_CACHE = {}


def _bsb_verse(macula_ref):
    """(text, spans) of the Berean verse carrying a MACULA verse — loaded
    once; ("", []) when the alignment files are missing."""
    if not _BSB_CACHE:
        try:
            vm = json.load(open(OUT / "versemap.json", encoding="utf-8"))
            _BSB_CACHE["moved"] = vm.get("moved", {})
            v = {}
            for line in gzip.open(OUT / "bsb-align.jsonl.gz", "rt",
                                  encoding="utf-8"):
                r = json.loads(line)
                if r.get("ref") and r.get("text"):
                    v[r["ref"]] = (r["text"], r.get("spans") or [])
            _BSB_CACHE["verses"] = v
        except FileNotFoundError:
            _BSB_CACHE["moved"], _BSB_CACHE["verses"] = {}, {}
    eref = _BSB_CACHE["moved"].get(macula_ref, macula_ref)
    return _BSB_CACHE["verses"].get(eref, ("", []))


def _bsb_fallback(nodes, edges, stats):
    """THE LAST FALLBACK: WHO THE TRANSLATORS SAY A PRONOUN IS.

    2026-09-26: for unresolved personal pronouns, BSB is used as a
    fallback with annotation. Translators resolve pronouns constantly, and
    the Berean text often names the referent where the Hebrew has only "he"
    ("carried by NEBUCHADNEZZAR into exile", 2Ch 36:20). Its editors tagged
    their English with Strong's numbers, so a name they SUPPLIED — tagged to
    no Hebrew word — is visible as theirs.

    Rule: a third-person subject still unresolved after every structure rule
    and every reading takes the one earlier-named person or place (in the
    last 40 clauses of the chapter) whose name the Berean verse supplies
    untagged, whose Hebrew is not in the verse, and which agrees in number.
    Measured: raw (any name in the verse) 8/16; with number agreement and
    the name supplied by the translators, 1,273 fire, a sample 12-13/16
    ("GOLIATH stood and shouted", 1Sa 17:8; "ELIJAH entered a cave", 1Ki
    19:9); misses: a place ("fall at RAMOTH-gilead", 2Ch 18:19), and "he
    spoke by his servant" given to Jeroboam, not the LORD (1Ki 14:18).
    Every edge is marked `reading: "BSB"` — the translation's reading, never
    the structure's, and never over anything the structure or a reading
    resolved.
    """
    try:
        vm = json.load(open(OUT / "versemap.json", encoding="utf-8"))
        moved = vm.get("moved", {})
        bsb = {}
        for line in gzip.open(OUT / "bsb-align.jsonl.gz", "rt",
                              encoding="utf-8"):
            r = json.loads(line)
            if r.get("ref") and r.get("text"):
                bsb[r["ref"]] = (r["text"], r.get("spans") or [])
    except FileNotFoundError:
        stats["bsb_fallback_skipped_no_data"] += 1
        return
    W = {n["id"]: n for n in nodes if n.get("id")}
    subj, ref_of, roles = {}, {}, collections.defaultdict(list)
    for e in edges:
        if e.get("clause_role") and e.get("type") in ("s", "o", "pp", "p"):
            roles[e["src"]].append(e["dst"])
            if e["type"] == "s":
                subj.setdefault(e["src"], e["dst"])
        elif e.get("type") == "refers_to":
            ref_of[e["src"]] = e["dst"]
    verse_strongs = collections.defaultdict(set)
    for n in nodes:
        if n.get("strong") and not n.get("clause"):
            verse_strongs[n["ref"]].add(
                re.sub(r"\D", "", str(n["strong"])).lstrip("0"))

    def strong(i):
        return re.sub(r"\D", "", str(W.get(i, {}).get("strong") or "")) \
            .lstrip("0")

    def supplied(text, spans, name):
        for m in re.finditer(r"\b" + re.escape(name) + r"\b", text):
            if not any(s[0] < m.end() and s[1] > m.start() for s in spans):
                return True
        return False
    cls = [n for n in nodes if n.get("clause")]
    cls.sort(key=lambda x: (x["ref"].split(".")[0],
                            int(x["ref"].split(".")[1]),
                            int(x["ref"].split(".")[2]), x.get("order", 0)))
    window = []
    for c in cls:
        chap = c["ref"].rsplit(".", 1)[0]
        window = [w for w in window if w[0] == chap][-40:]
        ct = c["id"].replace("#cl", "#ct")
        s = subj.get(ct)
        sn = W.get(s, {})
        if s and s not in ref_of and sn.get("person") == "third" and \
                (sn.get("implicit") or sn.get("class") == "pron"):
            text, spans = bsb.get(moved.get(c["ref"], c["ref"]), ("", []))
            cands = {}
            for _, nid in window:
                n = W.get(nid, {})
                name = (n.get("text") or "").strip()
                if not n.get("proper") or len(name) < 3 or \
                        strong(nid) in verse_strongs[c["ref"]]:
                    continue
                if sn.get("number") and \
                        sn["number"] != (n.get("number") or "singular"):
                    continue
                if supplied(text, spans, name):
                    cands[name] = nid
            if len(cands) == 1:
                r = next(iter(cands.values()))
                edges.append({"ref": c["ref"], "lang": "hebrew",
                              "type": "refers_to", "src": s, "dst": r,
                              "reading": "BSB",
                              "inferred": "named by the BSB translation "
                                          "(supplied, not in the Hebrew)"})
                ref_of[s] = r
                stats["reading_BSB"] += 1
        for d in roles.get(ct, []):
            if W.get(d, {}).get("proper"):
                window.append((chap, d))


def _reading_rules(nodes, edges, stats):
    """A SEPARATE PASS OF READINGS, proposed by DeepSeek and measured.

    2026-09-26: see if DeepSeek can come up with some set of rules
    for these examples, applied in a separate pass after the current rule
    set is applied, never overriding already established resolutions.
    The held list (docs/HELD.md) was sent blind with the rules already
    rejected; DeepSeek proposed five (docs/HELD-RULES-deepseek.md). Each was
    measured on the corpus before any was built. This pass only fills a
    subject the structure left unresolved, never changes a resolution, and
    marks every edge `reading` with its rule — these are readings, not
    structure, and they feed the meaning graph (Step 4).

      R1  a pronoun subject of a verbless clause joined by "and" to an
          existential ("there is X") takes X, the existential's own subject
          — Ecc 6:1 "there is an evil ... and it weighs heavily". Fires once
          in the Hebrew Bible; right. Provisional: one case proves little.
      R2  a run of third-person unstated subjects right after a verbless
          clause whose subject is the divine name takes that name — Psa
          103:8-10 "the LORD is compassionate ... he will not always accuse
          ... he has not dealt with us". 48 fires, a sample 14/16; misses:
          "he will be put to death" (1Sa 19:6), "let him go up" (2Ch 36:23).
      R4  a third-person subject quantified "all of it" takes the named
          subject of an earlier clause with the SAME verb — Isa 15:3 "Moab
          wails ... all of it wails". 4 fires, 4 right.
    Not built: R3 (needs a subject the "the one who" descriptions do not
    have), R5 (keyed to one verse's words — overfit).
    """
    W = {n["id"]: n for n in nodes if n.get("id")}
    role, ref_of, qual = collections.defaultdict(dict), {}, \
        collections.defaultdict(list)
    and_in = collections.defaultdict(list)
    words_of = collections.defaultdict(set)     # content -> its words' lemmas
    for e in edges:
        t = e.get("type")
        if e.get("clause_role") and e.get("dst") in W:
            words_of[e["src"]].add(_nfc(W[e["dst"]].get("lemma")))
        if e.get("clause_role") and t in ("s", "v"):
            role[e["src"]].setdefault(t, e["dst"])
        elif t == "refers_to":
            ref_of[e["src"]] = e["dst"]
        elif t == "qualifier":
            qual[e["src"]].append(e)
        if t == "and" and e.get("clause_link"):
            and_in[e["dst"]].append(e["src"])
    cls = [n for n in nodes if n.get("clause")]
    key = lambda x: (x["ref"].split(".")[0], int(x["ref"].split(".")[1]),
                     int(x["ref"].split(".")[2]), x.get("order", 0))
    cls.sort(key=key)
    ctid = lambda c: c["id"].replace("#cl", "#ct")
    yesh = _nfc("יֵשׁ")

    def strong(n):
        return re.sub(r"\D", "", str(W.get(n, {}).get("strong") or "")) \
            .lstrip("0")

    def unres(s):
        n = W.get(s, {})
        return s and s not in ref_of and n.get("person") == "third" and (
            n.get("implicit") or n.get("class") == "pron"
            or n.get("pos") in ("pronoun", "suffix"))

    def agree(a, b):
        x, y = W.get(a, {}), W.get(b, {})
        g1, n1, g2, n2 = x.get("gender"), x.get("number"), y.get("gender"), \
            y.get("number")
        if y.get("proper") and not n2:
            n2 = "singular"
        if n1 and n2 and n1 != n2:
            return False
        return not (g1 and g2 and g1 != g2 and "common" not in (g1, g2)
                    and "both" not in (g1, g2))

    def write(s, r, rule, why):
        edges.append({"ref": W[s]["ref"], "lang": "hebrew",
                      "type": "refers_to", "src": s, "dst": r,
                      "reading": rule, "inferred": why})
        ref_of[s] = r
        stats[f"reading_{rule}"] += 1

    for i, c in enumerate(cls):
        s = role[ctid(c)].get("s")
        if not unres(s):
            continue
        chap = c["ref"].rsplit(".", 1)[0]
        prevs = [p for p in cls[max(0, i - 12):i]
                 if p["ref"].rsplit(".", 1)[0] == chap]
        # R1
        if not c.get("verb_mood"):
            for src in and_in.get(c["id"], []):
                E = W.get(src, {})
                rs = role[src.replace("#cl", "#ct")]
                if not E.get("verb_mood") and rs.get("s") and \
                        yesh in words_of.get(src.replace("#cl", "#ct"), ()) \
                        and agree(s, rs["s"]):
                    write(s, rs["s"], "R1", "reading (DeepSeek R1): the "
                          "subject of the existential 'there is' before it")
                    break
            if s in ref_of:
                continue
        # R2
        if c.get("verb_mood") in ("yiqtol", "qatal", "weqatal", "wayyiqtol"):
            anchor = None
            for p in reversed(prevs):
                ps = role[ctid(p)].get("s")
                if not p.get("verb_mood") and ps and \
                        strong(ps) in ("3068", "3069"):
                    anchor = ps
                    break
                if not (p.get("verb_mood") and ps and
                        W.get(ps, {}).get("person") == "third" and
                        (ps not in ref_of or ref_of.get(ps) and
                         strong(ref_of[ps]) in ("3068", "3069")) and
                        (W.get(ps, {}).get("implicit") or
                         W.get(ps, {}).get("class") == "pron")):
                    break
            if anchor and agree(s, anchor):
                write(s, anchor, "R2", "reading (DeepSeek R2): continues "
                      "the divine name, the subject of the verbless clause "
                      "that opens the run")
                continue
        # R4
        if any(q.get("rel") == "quantity" for q in qual.get(s, [])):
            for p in reversed(prevs):
                ps = role[ctid(p)].get("s")
                if ps and W.get(ps, {}).get("proper") and \
                        _nfc(p.get("verb_lemma")) and \
                        _nfc(p.get("verb_lemma")) == _nfc(c.get("verb_lemma")):
                    write(s, ps, "R4", "reading (DeepSeek R4): 'all of it' "
                          "with the verb of a named subject before it")
                    break

    # R3, GENERALISED: A DESCRIPTION DESCRIBES THE GOD JUST NAMED. DeepSeek
    # proposed it tied to "bless [the LORD]" (a psalm-special rule); widened
    # without the verb: a singular "the one who ..." description's subject
    # takes the divine name (LORD, God) where a clause just before it (up to
    # three back, same chapter, not itself a description) names it as
    # subject, object or prepositional object — "bless the LORD ... WHO
    # forgives" (Psa 103:3), "the LORD our God, the one ENTHRONED on high"
    # (113:5), "sing to God ... who COVERS the sky" (147:8). Measured on all
    # 77 descriptions: 18 fire, 16 right; the misses were plural ("THOSE WHO
    # speak evil against me", Psa 109:20), so singular only. The other
    # descriptions of the same collection inherit its referent (a
    # collection and a common subject that applies to all) — 103:4-5.
    div_ = ("3068", "3069", "430", "410")
    cl_role = collections.defaultdict(list)
    for e in edges:
        if e.get("clause_role") and e.get("type") in ("s", "o", "pp", "p"):
            cl_role[e["src"]].append(e["dst"])
    desc_of = {}                                    # member clause -> group
    for e in edges:
        if e.get("type") == "described_as":
            desc_of[e["dst"]] = e["src"]
    group_ref = {}
    for i, c in enumerate(cls):
        if not c.get("substantival"):
            continue
        s = role[ctid(c)].get("s")
        if not unres(s) or W.get(s, {}).get("number") != "singular":
            continue
        g = desc_of.get(c["id"])
        if g in group_ref:
            write(s, group_ref[g], "R3", "reading (R3, generalised): the "
                  "common referent of the descriptions it belongs to")
            continue
        chap = c["ref"].rsplit(".", 1)[0]
        prev = [p for p in cls[max(0, i - 3):i]
                if p["ref"].rsplit(".", 1)[0] == chap
                and not p.get("substantival")]
        hit = None
        for p in reversed(prev):
            for d in cl_role.get(ctid(p), []):
                d2 = ref_of.get(d, d)
                if strong(d) in div_ or strong(d2) in div_:
                    hit = d2 if strong(d2) in div_ else d
                    break
            if hit:
                break
        if hit:
            write(s, hit, "R3", "reading (R3, generalised): the divine name "
                  "in the clause just before the description")
            if g:
                group_ref[g] = hit

    # THE POSSESSIVE RULE AGAIN, after the readings. On Isa 15:3:
    # there are three references to 'its', which is pretty meaningless if
    # not resolved to Moab. The built rule gives a third-person "his / its"
    # its own clause's subject where that subject is known and agrees; the
    # subjects these readings resolved were not known when it ran. So it runs
    # once more over the clauses a reading touched, and what it writes is a
    # reading too (derived from the reading of the subject).
    # refers_to readings only: a BSB-placed "like" qualifier also carries
    # `reading`, with a noun as its source (the Ezk 40:25 build crashed on it)
    resolved_by = {e["src"]: e for e in edges
                   if e.get("reading") and e.get("type") == "refers_to"}
    possessed = collections.defaultdict(list)       # content -> suffix nodes
    for e in edges:
        if e.get("type") == "qualifier" and e.get("rel") == "whose" and \
                e.get("clause_role"):
            possessed[e.get("clause_order"), W.get(e["src"], {}).get("ref")] \
                .append(e["dst"])
    for c in cls:
        s = role[ctid(c)].get("s")
        if s not in resolved_by:
            continue
        r = ref_of[s]
        for suf in possessed.get((c.get("order"), c["ref"]), []):
            n = W.get(suf, {})
            if suf in ref_of or n.get("person") != "third" or \
                    not agree(suf, r):
                continue
            edges.append({"ref": c["ref"], "lang": "hebrew",
                          "type": "refers_to", "src": suf, "dst": r,
                          "reading": resolved_by[s]["reading"] + "+possessor",
                          "inferred": "reading: its own clause's subject, "
                                      "which a reading resolved"})
            ref_of[suf] = r
            stats["reading_possessor"] += 1




# frame clause -> the participle clause it is folded into; the frame's content
_FOLD = {}
_FOLD_CT = set()


def _fold_frames(nodes, edges, stats):
    """Fold each empty "[he is] the one who ..." frame into its participle
    clause (see the note where frames are found): edges re-pointed, the
    frame's own `within` / `asserts` and its nodes dropped."""
    if not _FOLD:
        return
    keep, seen = [], set()
    for e in edges:
        s, d = e.get("src"), e.get("dst")
        if s in _FOLD_CT or d in _FOLD_CT:
            stats[f"frame_dropped_{e.get('type')}"] += 1
            continue                      # the frame's content and its links
        touched = s in _FOLD or d in _FOLD
        if s in _FOLD:
            e["src"] = _FOLD[s]
        if d in _FOLD:
            e["dst"] = _FOLD[d]
        # only a loop THIS fold made (the frame's `within` / `next` to its
        # clause). A first version dropped every self-loop in the graph —
        # 699 edges for 77 frames, caught by counting what was dropped.
        if touched and e.get("src") == e.get("dst"):
            stats["frame_dropped_self"] += 1
            continue
        if s in _FOLD or d in _FOLD:
            # a link the clause already had, now doubled ("part" twice)
            k_ = (e.get("type"), e.get("src"), e.get("dst"))
            if k_ in seen:
                stats["frame_dropped_duplicate"] += 1
                continue
            seen.add(k_)
        keep.append(e)
    # the clause's own copy of a link the frame also had
    folded_to = set(_FOLD.values())
    own = {}
    final = []
    for e in keep:
        k_ = (e.get("type"), e.get("src"), e.get("dst"))
        if (e.get("src") in folded_to or e.get("dst") in folded_to) and \
                k_ in own:
            stats["frame_dropped_duplicate"] += 1
            continue
        own[k_] = True
        final.append(e)
    keep = final
    stats["frame_edges_dropped"] = len(edges) - len(keep)
    edges[:] = keep
    nodes[:] = [n for n in nodes
                if n.get("id") not in _FOLD and n.get("id") not in _FOLD_CT]
    _FOLD.clear()
    _FOLD_CT.clear()


ARAMAIC = {"Dan": lambda c, v: (c == 2 and v >= 4) or 3 <= c <= 7,
           "Ezr": lambda c, v: ((c == 4 and v >= 8) or c in (5, 6)
                                or (c == 7 and 12 <= v <= 26)),
           "Jer": lambda c, v: c == 10 and v == 11,
           "Gen": lambda c, v: c == 31 and v == 47}


def language_of(ref, lang):
    """hebrew / aramaic / greek for a verse.

    The Aramaic portions live inside the Hebrew files and carry `lang="A"` per
    word; the verse ranges are the standard ones. Genesis 31:47 is two words
    (*Jegar-sahadutha*) and is included because a rule that quietly skips the
    small cases is the rule that quietly skips Jeremiah 10:11 too.
    """
    if lang == "greek":
        return "greek"
    b, c, v = ref.split(".")
    f = ARAMAIC.get(b)
    return "aramaic" if f and f(int(c), int(v)) else "hebrew"


def languages():
    """How often each language-specific test fires. A zero is the alarm.

    The pipeline has three specializations, with Aramaic being the third.
    Written down as a check rather than a comment, because
    the failure mode is silence: Aramaic passives read against Hebrew stems
    returned False and Greek imperatives read against a missing attribute
    returned False, and nothing raised.
    """
    from graphnodes import _passive, _imperative, SPECIALIZATION   # noqa: E402
    out = collections.defaultdict(collections.Counter)
    for lang, pat in (("hebrew", "hebrew/*.xml"), ("greek", "greek/*.xml")):
        for ref, cls in clauses_by_verse(sorted(MAC.glob(pat))).items():
            L = language_of(ref, lang)
            for c in cls:
                out[L]["clauses"] += 1
                if _passive(c):
                    out[L]["passive"] += 1
                if _imperative(c):
                    out[L]["imperative"] += 1
    print("LANGUAGE SPECIALIZATIONS — how often each test fires")
    print("A zero where the grammar has the feature means the specialization")
    print("was never written and is silently returning False.\n")
    print(f"{'':10}{'clauses':>9}{'passive':>9}{'imperative':>12}   reads")
    for L in ("hebrew", "aramaic", "greek"):
        c = out[L]
        spec = SPECIALIZATION.get(L, {})
        print(f"  {L:8}{c['clauses']:>9,}{c['passive']:>9,}"
              f"{c['imperative']:>12,}   "
              f"passive={spec.get('passive','?')} "
              f"imperative={spec.get('imperative','?')}")
        for feat in ("passive", "imperative"):
            if c["clauses"] and not c[feat]:
                print(f"      ! {L} {feat} never fires — check the "
                      f"specialization")
    return 0


def main() -> int:
    if "--languages" in sys.argv:
        return languages()
    if "--sample" in sys.argv:
        ref = sys.argv[sys.argv.index("--sample") + 1]
        bk = ref.split(".")[0]
        paths = [p for p in MAC.rglob("*.xml")]
        n, e, _ = build([p for p in paths
                         if bk.lower()[:3] in p.name.lower()], "?")
        for x in n:
            if x["ref"] == ref:
                print(json.dumps(x, ensure_ascii=False))
        for x in e:
            if x["ref"] == ref:
                print(json.dumps(x, ensure_ascii=False))
        return 0

    # ONE BUILD AT A TIME, AND NEVER A HALF-WRITTEN FILE. 2026-09-24: two
    # builds wrote these files at once, and the graph was corrupt twice
    # (BadGzipFile) before the cause was seen — a build sent to the
    # background after a timeout finished AFTER the foreground one and
    # overwrote it. The lock makes a second build refuse to start; writing to
    # `.tmp` and renaming means a reader sees the old graph or the new one,
    # never a mixture.
    OUT.mkdir(exist_ok=True)
    lock = OUT / "placeholders.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print(f"  another build holds {lock} ({lock.read_text().strip()}).\n"
              f"  If no build is running, it crashed: delete the file.",
              file=sys.stderr)
        return 2
    os.write(fd, f"pid {os.getpid()} since {time.strftime('%H:%M:%S')}"
             .encode())
    os.close(fd)
    try:
        return _build_all()
    finally:
        lock.unlink(missing_ok=True)


def _build_all() -> int:
    t0 = time.time()
    allstats = collections.Counter()
    npath = OUT / "placeholder-nodes.jsonl.gz"
    epath = OUT / "placeholder-edges.jsonl.gz"
    ntmp = npath.with_name(npath.name + ".tmp")
    etmp = epath.with_name(epath.name + ".tmp")
    with gzip.open(ntmp, "wt", encoding="utf-8") as nf, \
            gzip.open(etmp, "wt", encoding="utf-8") as ef:
        head = {"_source": "MACULA Hebrew Linguistic Datasets, available at "
                           "https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek "
                           "Linguistic Datasets, available at "
                           "https://github.com/Clear-Bible/macula-greek/; © Biblica, "
                           "Inc., CC BY 4.0",
                "_note": "One node per OCCURRENCE. No cross-verse identity is "
                         "claimed; merging is a later pass with evidence."}
        nf.write(json.dumps(head) + "\n")
        ef.write(json.dumps(head) + "\n")
        for lang, pat in (("hebrew", "hebrew/*.xml"), ("greek", "greek/*.xml")):
            paths = sorted(MAC.glob(pat))
            print(f"  {lang}: {len(paths)} files …", flush=True)
            nodes, edges, st = build(paths, lang)
            st["composite_named"] = name_composites(nodes, edges)
            if lang == "hebrew":
                st["usual_rendering_shown"] = mark_usual(nodes)
            # A CLAUSE LINK MUST NOT SHARE ITS NAME WITH A FLAT EDGE. The
            # superseded flat layer names edges after verbs and glosses —
            # 16,133 names — and four new links collided on 2026-09-26
            # ("act", "setting", "but", and a stat named "result"). Checks
            # filter by flag and were not fooled; counts and quick analyses
            # were. Said loudly, at the build, where the name is chosen.
            linked_ = {e["type"] for e in edges
                       if e.get("clause_link") or e.get("clause_role")}
            flat_ = {e["type"] for e in edges
                     if not (e.get("clause_link") or e.get("clause_role"))}
            # The first run found 14 older clashes, grandfathered here so a
            # NEW one stands out; renaming them is its own change.
            known_clash = {"aim", "and", "as", "because", "causes", "command",
                           "content", "if", "likewise", "state", "that",
                           "therefore", "though", "within"}
            st["name_clashes_known"] = len((linked_ & flat_) & known_clash)
            clash = sorted((linked_ & flat_) - known_clash)
            st["name_clashes"] = len(clash)
            if clash:
                print(f"    NAME CLASH: {', '.join(clash)} — a clause link "
                      f"or role shares its name with a flat edge",
                      flush=True)
            for x in nodes:
                nf.write(json.dumps(x, ensure_ascii=False) + "\n")
            for x in edges:
                ef.write(json.dumps(x, ensure_ascii=False) + "\n")
            for k, v in st.items():
                allstats[f"{lang}_{k}"] = v
                allstats[k] += v
            print(f"    {st['verses']:,} verses  {st['nodes']:,} nodes  "
                  f"{st['edges']:,} edges", flush=True)
    os.replace(ntmp, npath)
    os.replace(etmp, epath)

    summary = {"built": time.strftime("%Y-%m-%d %H:%M"),
               "seconds": round(time.time() - t0, 1),
               "circuit_breaks": [f"{r}: {w}" for r, w in _BREAKS][:200],
               **dict(allstats)}
    (OUT / "placeholder-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")

    print()
    print(f"  verses          {allstats['verses']:>9,}")
    print(f"  nodes           {allstats['nodes']:>9,}   "
          f"one per occurrence, no identity claimed")
    print(f"    proper nouns  {allstats['proper']:>9,}")
    print(f"    with a lemma  {allstats['with_lemma']:>9,}")
    # THE CLAUSE LAYER, COUNTED SEPARATELY. It is a different kind of node —
    # a thing the text asserts rather than a thing the text mentions — and
    # blending it into the occurrence count would hide both.
    print(f"  clauses         {allstats['clauses']:>9,}   "
          f"a node per assertion, with its verb's mood")
    print(f"    with a mood   {allstats['clause_with_mood']:>9,}   "
          f"{100*allstats['clause_with_mood']//max(allstats['clauses'],1)}%"
          f"; the rest are verbless clauses")
    print(f"    role edges    {allstats['clause_role_edges']:>9,}")
    print(f"  edges           {allstats['edges']:>9,}")
    print(f"    inferred subj {allstats['inferred']:>9,}")
    print(f"    agentless     {allstats['agentless']:>9,}")
    print(f"    unresolved    {allstats['unresolved']:>9,}   "
          f"{100*allstats['unresolved']//max(allstats['edges'],1)}%")
    print(f"  verse errors    {allstats['verse_errors']:>9,}")
    print(f"  circuit breaks  {len(_BREAKS):>9,}"
          + ("   " + "; ".join(f"{r} {w}" for r, w in _BREAKS[:5])
             if _BREAKS else "   none"))
    print()
    print(f"  {npath.name}  {npath.stat().st_size/1e6:.1f} MB")
    print(f"  {epath.name}  {epath.stat().st_size/1e6:.1f} MB")
    print(f"  {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
