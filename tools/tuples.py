"""Subject-verb-object tuples from grammar alone, with the typing deferred.

2026-09-04: try to use determinism to find the lowest-level tuple patterns
even if the nodes are not classified yet. They should follow the rules of
grammar; even the relationship type might be abstract, but the structure
would be captured.

**The verb is the relation, and the text supplies it.** Nothing here decides
whether `H1254` should become `made` or `formed` or `created` -- it records that
`elohim` stands in the `H1254` relation to `hashamayim`, and leaves the mapping
to a vocabulary as a separate, later, deferrable step. That removes the
judgement call that the extraction currently spends a reasoning model on, and
it removes the invented-relation-type failure entirely, because no type is
invented.

## What each language marks, and neither requires inference

**Greek marks case.** `N-NSM` is nominative and therefore the subject; `N-ASM`
is accusative and therefore the object. The tagged text states both.

**Hebrew marks the definite direct object** with the particle את, H0853 --
10,946 occurrences, glossed `<obj.>`, doing exactly one job. Hebrew has no
nominative marking, but narrative is verb-first, so the canonical shape is

    VERB  SUBJECT  <obj.>  OBJECT

and Genesis 1:1 is exactly that: `he created` `God` `<obj.>` `the heavens`.

## What this is not

It is not meaning. A tuple says a grammatical relation holds, not what the
passage is arguing -- the test for any addition is whether it helps someone
understand what a passage is saying, and a tuple alone does not. What it is is
a **floor**: a deterministic, free, complete lower layer that the meaning layer
can be built on and checked against, rather than re-derived from the text every
time by a model.

    python tools/tuples.py                # counts and samples
    python tools/tuples.py --json         # writes out/tuples.jsonl
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from markers import corpus, base                                 # noqa: E402

# Hebrew morph segments: the verb is any segment whose body starts with V, and
# a noun is Nc (common) or Np (proper). Particles, prefixes and suffixes are
# separated by "/" in the tag, so a compound like HC/Vqw3ms holds both a
# conjunction and a verb.
def _seg(morph, kind):
    for s in morph.split("/"):
        b = s.lstrip("H")
        if b.startswith(kind):
            return b
    return None


# Hebrew conjugations that do NOT open a clause: infinitive absolute,
# participle, infinitive construct, passive participle. These are structures
# INSIDE a clause -- the cheat sheet puts them at step 6 -- and letting them
# start one is what made Gen 1:2's "[was] hovering" a clause of its own while
# tools/acts.py, using the same distinction, correctly refused it a speech act.
NONFINITE = set("arcs")


def is_finite(w):
    """Hebrew: a verb opens a clause only if it is finite."""
    v = _seg(w[5], "V")
    return bool(v) and len(v) > 2 and v[2] not in NONFINITE


def clauses(ws, prefield=True):
    """Split a verse into clauses at each finite verb, pre-field included.

    The complaint: it was pulling from all over, and the view should be able
    to tell where the phrases are; follow the rules taught in sixth grade.

    Sixth-grade grammar: one clause has one subject, one verb, one object, and
    you do not reach across a conjunction to collect them. The first version
    looked ahead six words for an object marker and cheerfully crossed clause
    boundaries, which is why Judges 9:27 came out with a subject from one
    clause and an object from another.

    ## Why the clause cannot start at the verb

    It did, and that silently discarded every fronted subject. Genesis 1:2 is
    the case: *we-ha-arets hayetah tohu* -- "and the earth was formless". The
    subject stands BEFORE the verb, so a span beginning at the verb never saw
    it and took *tohu* ("formlessness") as the subject instead.

    This is not an edge case. Hebrew narrative is verb-first, so **subject-first
    is the MARKED order** -- it is how the language signals that a clause is not
    advancing the narrative. Dropping the pre-field therefore lost the subject
    precisely in the clauses that are doing something other than telling the
    story, which is the material this project cares most about.

    The fix is conservative on purpose. For the verse's FIRST finite verb, the
    words before it belong to no earlier clause and are unambiguously its own.
    For later verbs the material after the previous verb is genuinely ambiguous
    -- post-field of the one, or pre-field of the next -- and it is not guessed
    at here.
    """
    starts = [i for i, w in enumerate(ws) if is_finite(w)]
    if not starts:
        return []
    out = []
    for n, i in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(ws)
        begin = 0 if (prefield and n == 0) else i
        out.append((begin, end, i))
    return out


# Prose accents by rank, strongest first. The Masoretic system is hierarchical
# by design -- each disjunctive divides the domain of the one above it -- so it
# is a parse tree that was written down a thousand years ago and that this
# project had been using only to count poetry lines.
#
# NOT valid for Psalms, Proverbs and Job, which use a different inventory.
ACCENT = {"׃": (0, "sof-pasuq"), "֑": (1, "etnachta"),
          "֒": (2, "segolta"), "֓": (2, "shalshelet"),
          "֔": (3, "zaqef-qatan"), "֕": (3, "zaqef-gadol"),
          "֖": (4, "tipcha"), "֭": (4, "dehi"), "֮": (4, "zinor")}
POETIC_BOOKS = {"Psa", "Pro", "Job"}


def accent(w):
    """The strongest disjunctive accent on this word, or None."""
    best = None
    for ch in (w[6] or ""):
        if ch in ACCENT:
            r = ACCENT[ch]
            if best is None or r[0] < best[0]:
                best = r
    return best


def predication(ws, lo, hi):
    """Does this span stand as a clause on its own?

    A clause needs a predicate, and Hebrew offers three shapes: a finite verb,
    a participle or infinitive doing predicate duty, or a VERBLESS clause --
    a noun phrase with something predicated of it, normally a prepositional
    phrase.

    A span holding only a noun phrase is a fragment: a subject still waiting
    for its predicate. Refusing to cut one off is what separates Gen 1:2's
    "and darkness | over the face of the deep" -- a real verbless clause --
    from "and the Spirit of God", a subject whose predicate sits across a
    zaqef-qatan.
    """
    verb = nonfin = False
    for k in range(lo, hi + 1):
        v = _seg(ws[k][5], "V")
        if v and len(v) > 2:
            if v[2] in NONFINITE:
                nonfin = True
            else:
                verb = True
    if verb or nonfin:
        return True
    # A verbless clause needs a BARE subject and something predicated of it,
    # and the operand ladder is what distinguishes them. Testing word by word
    # counted the noun INSIDE a prepositional phrase as a subject, so Jonah
    # 1:3's "from before the presence of the LORD" -- one prepositional
    # phrase, no subject at all -- passed as a clause and rendered as
    # "from·before·Yahweh [is] —".
    ops = operands(ws[lo:hi + 1])
    bare = any(o["kind"] in ("phrase", "group") for o in ops)
    pp = any(o["kind"] == "prep" for o in ops)
    return bare and pp


def clauses_by_accent(ws, book=None):
    """Clause boundaries from the Masoretes' own division of the verse.

    Gen 1:2 worked through by hand matched the accents exactly:
    the etnachta marks the sentence break, and the ranked disjunctives below
    it divide the clauses. Critically it finds clauses a verb-based splitter
    **cannot** -- Gen 1:2's second clause has no verb at all, and is 4 of the
    verse's 14 words.

    Falls back to the verb-based splitter for the three poetic books, whose
    accent system is different and not encoded here.
    """
    if book in POETIC_BOOKS or not ws:
        return clauses(ws)

    def descend(lo, hi):
        marks = [(k, accent(ws[k])) for k in range(lo, hi)]
        marks = [(k, r) for k, r in marks if r and r[0] <= 4]
        if not marks:
            return [(lo, hi)]
        k, _ = min(marks, key=lambda x: (x[1][0], x[0]))
        if not predication(ws, lo, k) or not predication(ws, k + 1, hi):
            return [(lo, hi)]          # a cut that orphans a fragment is wrong
        return descend(lo, k) + descend(k + 1, hi)

    out = []
    for lo, hi in descend(0, len(ws) - 1):
        # None, not a fallback index. A verbless clause has NO verb, and
        # substituting its first word made "darkness" render as the verb of
        # Gen 1:2's second clause. A missing thing must be represented as
        # missing; the caller decides what to do about it.
        vi = next((k for k in range(lo, hi + 1) if is_finite(ws[k])), None)
        out.append((lo, hi + 1, vi))
    return out


def constituent(span, k):
    """The whole tightly-bound phrase starting at k, not just the one word.

    The principle: find the most tightly bound part of the sentence first
    before anything else; the subject and object are not necessarily a single
    word.

    Right, and Hebrew states it. The construct chain (smichut) is marked in the
    morphology: a noun tagged `...c` is in the CONSTRUCT state and binds to what
    follows; a noun tagged `...a` is ABSOLUTE and closes the chain. So

        [the] appointed feasts of   Yahweh
        Ncmpc                       Np

    is one object, and taking `feasts` alone loses the half that says whose.

    Parse order matters here and it is the ordinary one: morphology first, then
    constituents, then clause roles. Assigning roles to bare words skips the
    middle step and produces subjects that are half a phrase.
    """
    out = [span[k]]
    i = k
    while i < len(span) - 1:
        # A pronominal suffix closes the phrase, because the suffix is what the
        # noun is bound to and it binds tighter than anything following. Gen
        # 24:9 is the case: `hand/his` is HNcbsc/Sp3ms -- "his hand", complete
        # -- and without this the chain ran on through `under` (HNcmsc, a noun
        # in construct, since Hebrew *tachat* is literally "the underside of")
        # to produce "his hand under the thigh of Abraham" as one object.
        if "/Sp" in span[i][5]:
            break
        tag = _seg(span[i][5], "N") or ""
        if not tag.endswith("c"):          # absolute state closes the chain
            break
        nxt = _seg(span[i + 1][5], "N")
        if not nxt:
            break
        # A prefixed preposition or conjunction opens a new phrase and cannot
        # be absorbed. Without this the chain ate straight through Gen 24:9 --
        # "hand his UNDER the thigh of Abraham" became one object, because
        # `HR/Ncmsc` carries a noun segment and looked like a continuation.
        if re.match(r"H[RC]/", span[i + 1][5]):
            break
        out.append(span[i + 1])
        i += 1
    return out


def has_prep(morph):
    """Does a preposition govern this word?

    The segment is not always `R/`. Hebrew fuses the preposition with the
    definite article -- *ba-* is *be* + *ha* -- and STEPBible tags that `Rd`,
    so Genesis 1:18's "over the day" is `HRd/Ncmsa`. Matching `R/` literally
    missed every fused form, which meant locatives kept being offered as
    subjects even after the guard was added. The test is a segment that STARTS
    with R and precedes the noun, not one that equals it.
    """
    for s in (morph or "").split("/"):
        b = s.lstrip("H")
        if b.startswith("R"):
            return True
        if b.startswith("N") or b.startswith("V"):
            return False
    return False


def operands(span):
    """Resolve a clause into operands, innermost binding first.

    2026-09-04: as in math, solve inside the parens before outside them; one
    might even end up grouping subjects, (Sodom&Gomorrah) assessed_as wicked.

    That is right, and the evidence is worse than the example. Coordination used
    to be detected as a by-product of finding two object markers, which meant
    it was only ever visible for definite direct objects. Genesis 19:24 rains
    *gophrith wa-esh* -- "brimstone and fire" -- with no marker on either,
    and the clause reported no object at all. Genesis 14:8 coordinates five
    kings as one subject and only the first was kept.

    ## The ladder

    These are precedence levels, not passes, because they nest both ways: a
    coordinated member can be a construct chain ("the God of Abraham and the
    God of Isaac") and a chain's tail can be coordinated ("the God of Abraham
    and Isaac"). Mutually recursive structures need innermost-first
    evaluation, which is what arithmetic does with parentheses.

        1  pronominal suffix   closes tightest        hand-his
        2  construct chain     noun binds to noun     king-of-Sodom
        3  coordination        waw joins peers        <Sodom + Gomorrah>
        4  preposition         governs the group      on <Sodom + Gomorrah>

    Role assignment is level 5 and happens outside this function, operating on
    whole operands rather than on loose words. That is the point: a role is
    borne by a group, so the group has to exist first.

    Returns operands in order, each a dict with its word indices, its kind, and
    -- for a coordination -- the members it joins, so the pairing is recorded
    and the halves stay derivable. That is the D1 veto applied one level
    down.
    """
    out = []
    i = 0
    while i < len(span):
        m = span[i][5] or ""
        prep = has_prep(m)
        start = i
        if re.fullmatch(r"H?R", m.strip()):        # standalone preposition
            i += 1
            if i >= len(span):
                out.append({"i": [start], "kind": "prep", "members": []})
                break
            m = span[i][5] or ""
        if not _seg(m, "N"):
            out.append({"i": [start], "kind": "word", "members": []})
            i = start + 1
            continue
        # level 1-2: the construct chain, suffix-terminated
        first = constituent(span, i)
        members = [list(range(i, i + len(first)))]
        chains = [_links(span, i, len(first))]
        i += len(first)
        # level 3: coordination -- a waw-prefixed noun of the same state is a
        # peer, not a new phrase. The rule, and the tag states it.
        # The waw does not have to sit on the noun. Hebrew coordinates
        #     et X   we-et Y      the marker carries it   (Gen 1:1)
        #     al X   we-al Y      the preposition does    (Gen 19:24)
        #     X      we-Y         the noun does           (Gen 14:8)
        # and all three join peers. Requiring it on the noun found the third
        # only, which is why "the heavens" and "the earth" stayed apart in the
        # single most-cited verse in the corpus.
        head_state = (_seg(span[members[0][0]][5], "N") or "")[-1:]
        while i < len(span):
            mm = span[i][5] or ""
            j = i
            if mm.startswith("HC/") and not _seg(mm, "N"):
                body = mm[3:]
                if not (body.startswith("To") or body.startswith("R")):
                    break
                j = i + 1                      # waw rode the marker/preposition
                if j >= len(span):
                    break
                mm = span[j][5] or ""
            elif not (mm.startswith("HC/") and _seg(mm, "N")):
                break
            if not _seg(mm, "N") or (_seg(mm, "N") or "")[-1:] != head_state:
                break
            nxt = constituent(span, j)
            members.append(list(range(j, j + len(nxt))))
            chains.append(_links(span, j, len(nxt)))
            i = j + len(nxt)
        idx = [k for grp in members for k in grp]
        if prep:
            idx = [start] + [k for k in idx if k != start]
        # A coordinated prepositional phrase is still a prepositional phrase.
        # Letting coordination override the kind offered "over the day and
        # over the night" as a subject -- a group, correctly built, and a
        # locative, which is never a subject. The two facts are independent
        # and the record keeps both.
        out.append({"i": sorted(set(idx)),
                    "kind": ("prep" if prep else
                             "group" if len(members) > 1 else "phrase"),
                    "coordinated": len(members) > 1,
                    "members": members,
                    "chains": chains})
    return out


def _links(span, k, n):
    """Split a construct chain into its links, head first.

    On Gen 1:2's second clause, the breakdown of the first sentence missed a
    grouping step. It did. `al-penei tehom` was
    absorbed into one flat operand, so `penei` and `tehom` came out as two
    strings in a list with nothing saying how they relate.

    **Coordination and construct were being stored in the same shape and they
    are opposite relations.** `heavens + earth` are peers, interchangeable and
    equal. `surface-of -> deep` is head and dependent: one is a part of the
    other, and the order is not reversible. Flattening both into "members"
    loses the distinction entirely.

    It also breaks the D2 ruling -- if it is mentioned it is a thing and
    relates somehow -- because `tehom`, the deep, is a referent in its own
    right and was not retrievable from the chain. D1 was honoured for
    coordination and D2 was not honoured for construct, from the same code.

    Each link is a word plus whatever binds tighter than the chain: a
    pronominal suffix is fused into the host tag by STEPBible, so a link is
    one word here. The head is first and every later link is its dependent.
    """
    return [{"i": [k + m],
             "state": (_seg(span[k + m][5], "N") or "")[-1:],
             "role": "head" if m == 0 else "of"}
            for m in range(n)]


def _bare_noun(span, lo, hi):
    """The first noun in [lo, hi) that is NOT inside a prepositional phrase.

    A preposition governs a whole phrase, not one word, so skipping only the
    prefixed word is not enough. Psalm 23:2 is *bin'ot deshe*, "in pastures of
    grass": the preposition sits on *pastures* and *grass* is the second half
    of the construct chain, so a one-word guard left `grass` looking bare and
    made it the subject. The whole of Psalm 23 came out with locatives as
    subjects, and the equation view is what made that visible -- the chip view
    showed the same words correctly coloured and hid the structure.

    A noun in a prepositional phrase is a modifier: where, when, by what
    means. It is never the subject.
    """
    k = lo
    while k < hi:
        m = span[k][5] or ""
        # Prefixed: HR/Ncmpc, the preposition rides on the noun.
        if has_prep(m) and _seg(m, "N"):
            k += max(1, len(constituent(span, k)))
            continue
        # Standalone: the preposition is its own word (Hebrew *al*, *el*,
        # *tachat*), tagged HR with nothing after it. Psalm 23:2 is this case
        # -- "he leads me BESIDE waters of rest" -- and requiring the slash
        # missed every one of them.
        if re.fullmatch(r"H?R", m.strip()):
            k += 1
            if k < hi and _seg(span[k][5], "N"):
                k += max(1, len(constituent(span, k)))
            continue
        if _seg(m, "N"):
            return k
        k += 1
    return None


def _phrase(ws):
    return " ".join(w[3].strip() for w in ws)


# Step 6, the waw-connector. The Hebrew cheat sheet separates it from the
# verb -- "And [lifted Moses his staff]" -- and it is a connector between
# clauses rather than part of the action. The tag carries it as its own segment
# (Hc/Vqw3ms), and the gloss as a "and/ " prefix, so both come apart cleanly.
_WAW = re.compile(r"^(and|then|so|but|now)\s*/\s*", re.I)

# Step 4b, the directional object: what the action is AIMED at, which Hebrew
# distinguishes from what it merely happens near. These are the prepositions of
# motion and address; everything else stays a plain modifier.
DIRECTIONAL = {"H0413",   # el -- to, toward
               "H5704",   # ad -- as far as, until
               "H5921",   # al -- upon, against
               "H3212",   # (motion verbs take these)
               "H4480"}   # min -- from, out of
# Some Hebrew prepositions are grammatically NOUNS in construct, so the
# morphology calls them Ncmsc and the modifier pass misses them. Gen 24:9 loses
# "under the thigh of Abraham" for exactly this reason.
NOUN_PREPS = {"H8478",    # tachat -- under
              "H6440",    # lifne -- before, in the presence of
              "H8432",    # tavek -- in the midst of
              "H0310",    # achar -- after
              "H0996"}    # ben -- between


# Step 6: how one clause hangs off the last one. The compound/complex sheet.
#
# **Hebrew is paratactic** -- it chains with waw and has few subordinators, and
# expresses much of what English subordinates through verb form and context
# instead. **Greek is hypotactic** -- it subordinates richly, with conjunctions,
# participles and infinitives all carrying logical weight.
#
# That asymmetry is a prediction the corpus can check, not a stylistic remark.
H_LINK = {
    "H3588": ("reason", "ki -- because, that"),
    "H0834": ("relative", "asher -- which, who"),
    "H4616": ("purpose", "lemaan -- so that"),
    "H0518": ("condition", "im -- if"),
    "H3651": ("result", "ken -- so, thus"),
    "H6440": ("time", "lifne -- before"),
    "H0310": ("time", "achar -- after"),
}
G_LINK = {
    "G3754": ("reason", "hoti -- because, that"),
    "G1063": ("reason", "gar -- for"),
    "G2443": ("purpose", "hina -- so that"),
    "G1437": ("condition", "ean -- if"),
    "G1487": ("condition", "ei -- if"),
    "G3752": ("time", "hotan -- when"),
    "G3753": ("time", "hote -- when"),
    "G5613": ("comparison", "hos -- as"),
    "G3739": ("relative", "hos -- who, which"),
    "G3767": ("inference", "oun -- therefore"),
    "G0235": ("adversative", "alla -- but"),
    "G1161": ("coordinate", "de -- and, but"),
    "G2532": ("coordinate", "kai -- and"),
}


def link_of(span, greek=False):
    """What joins this clause to the one before it, from its opening words."""
    table = G_LINK if greek else H_LINK
    for w in span[:3]:
        hit = table.get(base(w[4]))
        if hit:
            return {"kind": hit[0], "marker": hit[1],
                    "word": w[3].strip()}
    if not greek and re.match(r"H[cC]/", span[0][5] or ""):
        # the waw itself: coordination, and in Hebrew it does most of the work
        return {"kind": "coordinate", "marker": "waw -- and, then, so, but",
                "word": "and"}
    return None


def unwaw(gloss):
    """Split a waw-connector off the front of a gloss."""
    m = _WAW.match(gloss)
    return (m.group(1).lower(), _WAW.sub("", gloss)) if m else (None, gloss)


def modifiers(span, used):
    """Step 5: the details, separated out rather than merged into the object.

    The cheat sheet, in order: verb, subject, core, objects, MODIFIERS,
    extra structures. Step 5 was missing here, and its absence is what made
    Gen 24:9 wrong -- "under the thigh of Abraham" is a place modifier, and
    with nowhere to put it, it either swallowed the object or vanished.

    Hebrew marks these too. A prepositional prefix or particle (HR) opens a
    phrase; an adverb (HD) modifies the verb; an adjective (HAa) modifies the
    noun before it. Typing them by what they answer -- where, when, how --
    needs a lexicon of prepositions and is left undone rather than guessed.
    """
    out = []
    i = 0
    while i < len(span):
        if i in used:
            i += 1
            continue
        m = span[i][5]
        if re.match(r"H[R]", m) or "/R" in m or re.match(r"HR/", m):
            phrase = constituent(span, i) if _seg(m, "N") else [span[i]]
            j = i + len(phrase)
            # a preposition standing alone governs the noun phrase after it
            if len(phrase) == 1 and j < len(span) and _seg(span[j][5], "N"):
                phrase = phrase + constituent(span, j)
            out.append({"kind": "prepositional", "text": _phrase(phrase)})
            i += len(phrase)
            continue
        # A non-finite verb inside this clause: participle, infinitive
        # construct or absolute, passive participle. These are step 6 --
        # structures INSIDE a clause -- so they no longer open one, and until
        # now that left all 17,506 of them attached to nothing at all. They
        # belong to the clause they sit in, which is what this records.
        #
        # The kind is kept rather than flattened, because the three do
        # different work: an infinitive construct after a preposition is
        # usually purpose or time ("in order to", "when"), and a participle is
        # usually attendant circumstance. Typing them as `grounds` or
        # `purpose` needs the governing preposition and is a separate step.
        v = _seg(m, "V")
        if v and len(v) > 2 and v[2] in NONFINITE:
            out.append({"kind": {"r": "participle", "s": "passive participle",
                                 "c": "infinitive construct",
                                 "a": "infinitive absolute"}[v[2]],
                        "text": span[i][3].strip()})
            i += 1
            continue
        if _seg(m, "D"):
            out.append({"kind": "adverb", "text": span[i][3].strip()})
        elif _seg(m, "Aa"):
            out.append({"kind": "adjective", "text": span[i][3].strip()})
        i += 1
    return out


def hebrew(rows):
    """The six steps, in order, over one clause.

    The procedure: verb, subject, core, objects, modifiers, extra
    structures. Steps 1-4 were here; step 5 is now, and step 6 -- dependent
    clauses, appositives, compounds -- is not, which is why a clause is still
    cut at the next finite verb rather than parsed as subordinate or not.
    """
    by = collections.defaultdict(list)
    for r in rows:
        if r[4].startswith("H"):
            by[r[0]].append(r)
    out = []
    for ref, ws in by.items():
        for begin, end, vi in clauses(ws):
            w = ws[vi]
            span = ws[begin:end]
            vpos = vi - begin
            # The object marker, and the noun it governs, inside this clause.
            # The rule: decompose at the sentence unit level until the
            # whole base structure is had. An earlier version emitted only when a
            # definite direct object was marked, which silently dropped every
            # intransitive clause -- "and he went", "and he wept" -- and left
            # 27% of Hebrew words outside any decomposition, verbs included.
            # A clause with no object is still a clause.
            # EVERY object marker in the clause, not just the first. Genesis
            # 1:1 is the case: `et ha-shamayim we-et ha-arets` marks two
            # objects, and taking `next(...)` kept "the heavens" and silently
            # dropped "and the earth" -- 1,685 object constituents across the
            # Hebrew canon, in 1,158 clauses.
            #
            # The parts are kept separate rather than merged into one phrase.
            # The D1 veto is the reason: certain concepts will be grouped
            # together often, and the combination works as a concept from which
            # the individual concepts can be derived. Derivable requires the
            # parts to still be there, and `coordinated` records that they were
            # stated as one thing.
            marks = [k for k in range(vpos + 1, len(span))
                     if base(span[k][4]) == "H0853"]
            objs = []
            for k in marks:
                if k + 1 < len(span) and _seg(span[k + 1][5], "N"):
                    objs.append((k, constituent(span, k + 1)))
            j = marks[0] if marks else None
            obj = objs[0][1] if objs else None
            limit = j if j is not None else len(span)
            # The pre-field first: a noun standing BEFORE the verb is fronted,
            # and fronting is how Hebrew marks a clause as the subject's rather
            # than the narrative's. Only if there is nothing there does the
            # ordinary verb-first order apply and the subject follow the verb.
            # A prefixed preposition disqualifies the whole phrase it governs,
            # not just the word carrying it. Gen 1:1 opens with *bereshit*,
            # `HR/Ncfsa` -- "in [the] beginning" -- a time adverbial rather
            # than the subject. But skipping only that word is not enough:
            # Ps 23:2 is *bin'ot deshe*, "in pastures of grass", where the
            # preposition sits on *pastures* and *grass* is the second half of
            # the construct chain. Guarding one word left `grass` looking
            # unprefixed, and the whole of Psalm 23 came out with locatives as
            # subjects.
            si = _bare_noun(span, 0, vpos)
            fronted = si is not None
            if si is None:
                si = _bare_noun(span, vpos + 1, limit)
            subj = constituent(span, si) if si is not None else None
            used = {vpos} | set(marks)
            for k, o in objs:
                used |= set(range(k + 1, k + 1 + len(o)))
            if si is not None:
                used |= set(range(si, si + len(subj)))
            out.append({"ref": ref, "lang": "H", "fronted": fronted,
                        "s": [base(x[4]) for x in subj] if subj else None,
                        "s_gloss": _phrase(subj) if subj else None,
                        "v": base(w[4]), "v_gloss": w[3].strip(),
                        "o": [base(x[4]) for x in obj] if obj else None,
                        "o_gloss": _phrase(obj) if obj else None,
                        # every marked object, in order; `o` above is the first
                        "objects": [{"lemmas": [base(x[4]) for x in o],
                                     "gloss": _phrase(o)} for _, o in objs],
                        "coordinated": len(objs) > 1,
                        "mods": modifiers(span, used),
                        "clause": _phrase(span)})
    return out


NOM = re.compile(r"^N-N|^P-N|^A-N")      # nominative: subject
ACC = re.compile(r"^N-A|^P-A|^A-A")      # accusative: direct object
DAT = re.compile(r"^N-D|^P-D|^A-D")      # dative: beneficiary / indirect
# Finite moods open a clause: Indicative, iMperative, Subjunctive, Optative.
# Participles (P) and iNfinitives (N) do NOT -- the Greek sheet puts them in
# step 6 as extra structures, and letting them start clauses is what fragmented
# verses in the first version.
FINITE = re.compile(r"^V-\w*?[IMSO]-|^V-\w*?[IMSO]$")
PARTIC = re.compile(r"^V-\w*?P-")
INFIN = re.compile(r"^V-\w*?N$|^V-\w*?N-")
# Greek connectives, which mark clause seams as reliably as the verbs do.
CONNECT = {"G2532", "G1161", "G1063", "G0235", "G3767", "G1161", "G3754"}


def greek(rows):
    """The six steps in Greek logic: verb, subject (often implied), core,
    objects by case, modifiers, extra structures.

    The Greek cheat sheet corrected two things. **The subject is often
    inside the verb** -- `V-PAI-3S` already says "he" -- so a clause with no
    nominative is not missing data, and the first version skipped those.
    And **participles and infinitives are step 6, not step 1**: letting
    `V-PAP-NSM` open a clause is what made verses fragment and produced
    "Jesus composed account" for Acts 1:1, where the subject is Luke.
    """
    by = collections.defaultdict(list)
    for r in rows:
        if r[4].startswith("G"):
            by[r[0]].append(r)
    out = []
    for ref, ws in by.items():
        starts = [i for i, w in enumerate(ws) if FINITE.match(w[5] or "")]
        if not starts:
            continue
        for n, i in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(ws)
            span = ws[i:end]
            v = span[0]
            s = next((w for w in span if NOM.match(w[5] or "")), None)
            o = next((w for w in span if ACC.match(w[5] or "")), None)
            d = next((w for w in span if DAT.match(w[5] or "")), None)
            # A clause with no object is still a clause. Hebrew was fixed for
            # this and Greek was not, which is the whole of the gap between
            # Hebrew's 98% word coverage and Greek's 80%: every intransitive
            # and every copular clause -- "he wept", "he is the light" -- was
            # dropped on the floor, verb included.
            person = ""
            m = re.search(r"-(\d)([SP])$", v[5] or "")
            if m:
                person = {"1S": "I", "2S": "you", "3S": "he/she",
                          "1P": "we", "2P": "you (pl)",
                          "3P": "they"}.get(m.group(1) + m.group(2), "")
            out.append({
                "ref": ref, "lang": "G",
                "s": base(s[4]) if s else None,
                "s_gloss": s[3].strip() if s else (person or None),
                "s_implied": s is None,
                "v": base(v[4]), "v_gloss": v[3].strip(),
                "o": [base(o[4])] if o else None,
                "o_gloss": o[3].strip() if o else None,
                "indirect": d[3].strip() if d else None,
                "mods": ([{"kind": "participle", "text": w[3].strip()}
                          for w in span if PARTIC.match(w[5] or "")]
                         + [{"kind": "infinitive", "text": w[3].strip()}
                            for w in span if INFIN.match(w[5] or "")]),
                "clause": _phrase(span)})
    return out


def main() -> int:
    rows = corpus()
    heb = hebrew(rows)
    grk = greek(rows)
    all_ = heb + grk
    full = [t for t in all_ if t["s"]]
    print(f"tuples from grammar alone, no typing, no model:")
    print(f"  Hebrew  {len(heb):>7,}   ({sum(1 for t in heb if t['s']):,} with a subject)")
    print(f"  Greek   {len(grk):>7,}   ({sum(1 for t in grk if t['s']):,} with a subject)")
    print(f"  total   {len(all_):>7,}   {len(full):,} complete triples")
    print(f"  verses covered: {len({t['ref'] for t in all_}):,}")
    print()

    print("the commonest verbs, which are the relation types the text supplies:")
    c = collections.Counter((t["v"], t["v_gloss"][:22]) for t in all_)
    for (lem, gl), n in c.most_common(12):
        print(f"    {lem:9} {gl:24}{n:>6,}")
    print()
    fr = [t for t in heb if t.get("fronted")]
    print(f"  clauses whose subject stands BEFORE the verb: {len(fr):,}")
    print("    Hebrew is verb-first, so subject-first is the MARKED order and")
    print("    signals a clause that is not advancing the narrative.")
    print()

    print("samples — an objectless clause is still a clause, so o may be empty:")
    for t in [x for x in full if x["ref"].startswith("Gen.1")][:5]:
        print(f"    {t['ref']:12} {str(t['s_gloss'])[:16]:18}"
              f"-{t['v_gloss'][:16]:18}-> {str(t['o_gloss'] or '—')[:22]}")
    for t in [x for x in full if x["lang"] == "G"][:4]:
        print(f"    {t['ref']:12} {str(t['s_gloss'])[:16]:18}"
              f"-{t['v_gloss'][:16]:18}-> {str(t['o_gloss'] or '—')[:22]}")

    if "--json" in sys.argv:
        p = ROOT / "out" / "tuples.jsonl"
        with p.open("w", encoding="utf-8") as fh:
            for t in all_:
                fh.write(json.dumps(t, ensure_ascii=False) + "\n")
        print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
