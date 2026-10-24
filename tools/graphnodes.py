"""Nodes and edges from a MACULA clause, with elided subjects resolved.

The brief was to keep tuning until the output was what was wanted. This is
the result of that pass. Measured on the
stress set -- the five hardest verses in each language plus the worked cases:

    edges with no resolvable subject   36%  ->  1%

    Gen 1:1-1:5, Jonah 1:1-2, Psalm 23:2, 1 Chr 22:19      all zero
    the one remaining                  Psalm 23:1, "I shall not want"

## And that 1% is overfitting. Read this before scaling.

Run over everything on disk rather than the 14 tuned verses:

    stress set (14 verses)          1% unresolved
    all Hebrew (161 verses)        22%
    all Greek (2,816 verses)       25%

**Tuned to the test set, twenty times worse off it.** The rules are sound --
each decides from something MACULA states -- but the thresholds and the
fallback order were fitted to nine Hebrew verses, and nine verses do not carry
the canon. The stress set did its job in finding structural failures and is the
wrong instrument for estimating coverage.

Greek was 100% unresolved with ZERO nodes until the schema shim below, and it
looked like a logic failure for an hour.

## The whole corpus, measured (2026-09-04)

    Hebrew   23,213 verses   111,223 nodes   103,865 edges   25% unresolved
    Greek     6,867 verses    24,584 nodes    22,553 edges   27% unresolved
                              135,807 nodes   126,418 edges

42 seconds, no model, no cost. The 14-chapter sample predicted 22-25% and the
corpus says 25-27%, so that sample was representative for coverage even though
it was badly unrepresentative for TUNING.

**Known gap: Greek agentless is 0.** `_passive` tests Hebrew stems (niphal,
pual, hophal); Greek marks voice in its own morphology and is not read here, so
Greek agentless passives are counted as unresolved rather than correctly
agentless. The Greek 27% is therefore an overstatement by an unknown amount.

## What the first version got wrong, and it was not a tuning problem

**Node ids came from `gloss`.** MACULA's `gloss` carries the construct relation
and the article inside the word -- *tehom* glosses as "of.the.deep" -- so ids
came out as `theSurfaceOfOfthedeep`. `english` is the clean form. Worse, in
Psalm 23:1 the two columns are OFFSET: *ro'i* is one Hebrew word (participle +
1cs suffix) that MACULA splits, and `gloss` puts "[is].my" on the participle
where `english` correctly puts "shepherd". That produced `isMyOfShepherd`.

**Edges were built by iterating leftover keys**, so whatever survived the loop
became the relation type -- Psalm 23:2 emitted the verb as the target and a
pronoun as the type. Roles are pulled out by name now, once, explicitly.

## Elision is five cases, not one

Each is decided from something MACULA states, so none of it is inference:

    1st person in speech    the speaker, tracked from the framing speech verb
    2nd person in speech    the addressee
    imperative              the addressee, true before we know who they are
    passive, no agent       NOT a failure. "written in the name of the king"
                            leaves the agent unexpressed on purpose, and
                            `agent: unexpressed` is the correct analysis
    3rd person              the nearest preceding clause subject that AGREES

The last is much narrower than the recency-over-all-nouns rule that scored 29%
in August: the candidate set is clause subjects rather than every noun, and
agreement has to match on the features both sides state.

**A verse is a chapter division, not a grammatical unit**, so the subject
carries across verse boundaries and resets at book boundaries. Psalm 23:2
states no subject and wants the one from 23:1.

Every filled subject is labelled with WHY, because an inherited subject is a
weaker claim than a stated one and the graph should not flatten the difference.

## The one that is left, and why it is honest to leave it

Psalm 23:1 "I shall not want" is first person in poetry: no quotation frame, no
narrator, no stated speaker. The psalmist's "I" is a discourse-level referent
and nothing in the clause reaches it. That is the same hole this project has
hit from three directions now, and inventing a filler would hide it.

    MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0
"""

import re
import unicodedata

# --- the three specializations, declared
#
# 2026-09-05: the pipeline has three language specializations, Aramaic being
# the third. And the bug class this exposed is the reason
# to write them down: **a specialization that was never written does not fail,
# it falls through to another language's rules and returns a confident wrong
# answer.** Aramaic passives were read against Hebrew stems and came back
# `False`; Greek imperatives were read against a `type` attribute Greek does
# not have. Neither raised anything.
#
# The shared core is larger than the differences, which is why it went
# unnoticed: MACULA uses ONE set of roles (s/v/o/p/io/pp/adv) across all three,
# and ONE `type` vocabulary across Hebrew and Aramaic. Only the verb's own
# morphology is specialized.
#
#   feature      Hebrew            Aramaic                    Greek
#   passive      stem              stem (no overlap)          voice
#   imperative   type              type                       mood
#   agreement    person/gender/number, shared
#   roles        shared
#
# `tools/placeholders.py --languages` reports how often each test fires per
# language. A zero where there should not be one is the alarm.
SPECIALIZATION = {
    "hebrew": {"passive": "stem", "imperative": "type"},
    "aramaic": {"passive": "stem", "imperative": "type"},
    "greek": {"passive": "voice", "imperative": "mood"},
}

CONTENT = {"noun", "verb", "adjective", "adverb"}
SKIP_WORDS = {"the", "a", "an", "of", "and", "or", "to", "in", "on", "at",
              "is", "was", "were", "be", "been"}


def _pos(w):
    """Part of speech, from whichever attribute this language uses.

    **The two halves of MACULA have different schemas**, which produced zero
    Greek nodes and looked like a logic bug for an hour. Hebrew words carry
    `pos` and `english`; Greek words carry neither -- they have `class` and
    `gloss`. Every lookup here goes through one of these two shims so a schema
    difference cannot masquerade as a rule failure again.
    """
    p = (w.get("pos") or w.get("class") or "").lower()
    # The same schema difference this docstring warns about, caught again in a
    # different place. Hebrew's `pos` spells "adjective" and "adverb" out;
    # Greek's `class` abbreviates them to `adj` and `adv`, which are not in
    # CONTENT -- so a Greek SUBSTANTIVE ADJECTIVE matched neither the noun test
    # nor the content-word fallback and was named by its determiner. Matthew
    # 13:43 came out with "the" as its subject rather than "the righteous".
    return {"pron": "noun", "name": "noun", "num": "noun",
            "adj": "adjective", "adv": "adverb"}.get(p, p)


def _text(w):
    """The readable form: `english` where it exists, else `gloss`.

    Hebrew's `gloss` is the wrong column -- it carries the construct relation
    and the article inside the word -- so `english` is preferred. Greek has no
    `english` at all, and its `gloss` does not have that problem because Greek
    marks case morphologically rather than with prefixes.
    """
    return (w.get("english") or w.get("gloss") or "").strip()


def head_word(e):
    """The content word that names a constituent.

    A phrase is named by its head, not by every word in it. Preferring a noun
    and falling back to any content word keeps "the surface of the deep" from
    being named by its preposition.
    """
    ws = [e] if e.tag == "w" else list(e.iter("w"))
    for w in ws:
        if _pos(w) == "noun" and _text(w):
            return w
    for w in ws:
        if _pos(w) in CONTENT and _text(w):
            return w
    return next((w for w in ws if _text(w)), None)


def nid(e):
    """A node id from the head word."""
    w = head_word(e) if e is not None else None
    if w is None:
        return None
    t = re.sub(r"[^A-Za-z0-9 ]", " ", _text(w))
    parts = [p for p in t.split() if p.lower() not in SKIP_WORDS]
    if not parts:
        parts = [p for p in t.split() if p]
    if not parts:
        return None
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


# MACULA names coordination several ways and matching only the two-way forms
# lost the rest. Genesis 25:2 lists six sons under `Conj6Np`, each with its own
# object marker, and the floor emitted ONE node -- a defect the coverage
# numbers never showed and the edge audit found.
#
#     Conj6Np  Conj13CL  ConjNp      n-way, the commonest
#     NpaNp    CLaCL     NpNpaNp     two-way and the run-on forms
#
# `OmpNP` is the object marker plus its noun phrase: not a relation of its own,
# so it passes straight through to the phrase it marks rather than minting a
# node for the particle.
#
# 2026-09-05: widened again, from the rule vocabulary rather than from guesses.
# A scan of all 1,728 rule names MACULA uses found 25 coordination forms this
# pattern did not match, over 4,015 occurrences -- `PPandPP` (2,047),
# `CLandCL2`, `NumpAndNump`, `VPandVP`, `Conj3Pp` and the rest of the `Conj\d+Pp`
# family. Each one silently kept the first conjunct and dropped the others.
# `Conj-CL` is deliberately NOT matched: it is a clause introduced by a
# conjunction, not two things joined, and reifying it would mint a composite
# for something that has no members.
COORD = re.compile(r"^(Conj\d*(Np|CL|Cl|P|Pp|VP|Adjp|AdjP|Advp|ADV|Nump\d*)|"
                   r"[A-Za-z]+[aA]nd[A-Za-z0-9]*|"
                   r"[A-Za-z]*[aA](Np|CL|Cl|AdjP|Adjp)[A-Za-z]*)$")
PASSTHROUGH = {"OmpNP", "DetNP", "QuanNP"}
# Apposition: "Jonathan, and Abinadab, and Malki-Shua, the sons of Saul". The
# head is the first constituent and the rest re-describe it. 10,076 of these,
# and before this they minted a single node from the whole phrase's gloss --
# which is how 1Chr 10:2 lost two of Saul's three sons.
APPOS = "Np-Appos"


def _compose(parts, made, edges):
    """One node for a coordination, with its members on their own edges.

    Genesis 25:2 coordinates six sons, and joining every member gave a
    50-character id. The composite only needs to be identifiable, not
    exhaustive, because the members are edges.
    """
    parts = [p for p in parts if p]
    if len(parts) < 2:
        return parts[0] if parts else None
    comp = ("and".join(parts) if len(parts) <= 3
            else f"{parts[0]}And{len(parts)-1}More")
    _add(made, comp)
    for p in parts:
        _add(made, p)
        edges.append({"src": comp, "type": "member", "dst": p})
    return comp


def build(cl, made, edges):
    """Emit nodes and edges for one clause, roles pulled out by name."""
    kids = list(cl)

    def mint(e):
        """A node id for a constituent, reifying composites."""
        if e is None:
            return None
        rule = e.get("rule") or "" if e.tag != "w" else ""
        if rule in ("NPofNP",):
            inner = [c for c in list(e) if c.tag != "w" or
                     _pos(c) in CONTENT]
            if len(inner) >= 2:
                h, t = mint(inner[0]), mint(inner[1])
                if h and t:
                    comp = f"{h}Of{t[:1].upper()}{t[1:]}"
                    _add(made, comp)
                    _add(made, h)
                    _add(made, t)
                    edges.append({"src": comp, "type": "references",
                                  "dst": {"src": h, "type": "of", "dst": t}})
                    return comp
        if rule == APPOS:
            inner = [c for c in list(e) if c.tag != "w" or
                     _pos(c) in CONTENT]
            if len(inner) >= 2:
                h = mint(inner[0])
                if h:
                    _add(made, h)
                    for c in inner[1:]:
                        d = mint(c)
                        if d and d != h:
                            _add(made, d)
                            edges.append({"src": h, "type": "apposition",
                                          "dst": d})
                    # the HEAD is what the clause role refers to; the rest
                    # re-describe it and must not displace it
                    return h
        if rule == "NPofNP":
            # "his mother" -- a relational noun possessed by a pronominal
            # SUFFIX. The suffix is not a content word, so it never reached the
            # construct branch above and the whole phrase collapsed into one
            # opaque node: `motherS`, with the possessor nowhere. That is why
            # 2Chr 26:3 can name Jecoliah and still not say whose mother she is,
            # and why `mother_of` recovers nothing while 42% of it is reachable.
            #
            # Recorded ADDITIVELY -- the node id is unchanged and the edge is
            # new -- so nothing downstream shifts, and the possessive now
            # carries the agreement features an antecedent has to match. It is
            # left UNRESOLVED here on purpose: resolving it is a verse-level
            # question, and inventing a filler is the elision mistake.
            suf = next((c for c in list(e)
                        if c.tag == "w" and _pos(c) == "suffix"), None)
            content = [c for c in list(e)
                       if c.tag != "w" or _pos(c) in CONTENT]
            hw = head_word(content[0]) if content else None
            if suf is not None and hw is not None:
                i = nid(e)
                _add(made, i)
                edges.append({
                    "src": i, "type": "possessed_by", "dst": None,
                    "unresolved_possessor": True,
                    "noun": re.sub(r"[^a-z]", "", _text(hw).lower()),
                    "agreement": [suf.get("person"), suf.get("gender"),
                                  suf.get("number")]})
                return i
        if COORD.match(rule):
            parts = [mint(c) for c in list(e)
                     if c.tag != "w" or _pos(c) in CONTENT]
            comp = _compose(parts, made, edges)
            if comp:
                return comp
        i = nid(e)
        _add(made, i)
        return i

    def by_role(*roles):
        return [c for c in kids if c.get("role") in roles]

    verb = next((c for c in kids if c.get("role") == "v"), None)
    verbname = nid(verb) if verb is not None else None
    subj = next((mint(c) for c in by_role("s")), None)
    objs = [mint(c) for c in by_role("o", "o2")]
    ind = [mint(c) for c in by_role("io")]
    preds = [c for c in by_role("p")]
    adjs = [c for c in by_role("pp", "adv")]

    # A negation is a property of the assertion, not a thing in the world.
    # The first version minted `not` as a node and pointed an edge at it,
    # which says the subject stands in a relation TO negation. It does not --
    # the edge itself is denied.
    negated = any(_is_negative(c) for c in kids)
    adjs = [a for a in adjs if not _is_negative(a)]

    def edge(**kw):
        if negated:
            kw["negated"] = True
        made_edges.append(kw)

    made_edges = []
    # Emitted even when the subject is elided, with src None, so the elision
    # pass has something to resolve. Dropping them lost the clause entirely.
    if verbname:
        if objs:
            for o in objs:
                if o:
                    edge(src=subj, type=verbname, dst=o)
        else:
            edge(src=subj, type=verbname, dst=None, intransitive=True)
    for o in ind:
        if o:
            edge(src=subj, type=(verbname or "to") + "To", dst=o)
    # a verbless clause: the predicate is what is said of the subject
    pred_nodes = []
    for p in preds:
        rel, tgt = _prep(p, mint, made, made_edges)
        edge(src=subj, type=rel or "is", dst=tgt)
        if tgt:
            pred_nodes.append(tgt)
    # WHERE THERE IS NO SUBJECT, THE EVENT IS NAMED BY THE PREDICATE.
    #
    # 2026-09-21, on Exodus 8:6: on a graph-first approach 'there is no one'
    # -> 'like' -> 'Lord' should already be bound to the MACULA. It is in MACULA — the clause is tagged
    # `rule="P-PP"`, Predicate plus Prepositional Phrase, over exactly those
    # words — and this function produced two edges hanging off the same
    # `None`:
    #
    #     {"type": "is",   "src": null, "dst": "#thereNoOne"}
    #     {"type": "like", "src": null, "dst": "#lord"}
    #
    # because a P-PP clause has no `s` child and every edge here was anchored
    # on the subject. A verbless clause of that shape HAS no subject
    # constituent; אֵין is the predicate and כַּיהוָה attaches to it. Anchoring
    # the adjunct on the predicate when there is no subject binds the relation
    # the text actually states, and leaves the subject-bearing case untouched.
    host = subj or (pred_nodes[0] if pred_nodes else None)
    # adjuncts scope over the event, so they hang off the subject-verb pair
    for a in adjs:
        rel, tgt = _prep(a, mint, made, made_edges)
        if tgt:
            # Carry the VERB on the adjunct edge. Without it "Moses told Aaron
            # all the words" lifted to `Moses -to-> Aaron`, keeping the
            # preposition and losing the predicate -- so every person-to-person
            # relation in the corpus came out as `to`. The preposition marks
            # the role; the verb is the relation.
            kw = {}
            if _comparative(a):
                # the target is being used AS AN IMAGE here, whatever it is
                # elsewhere in the corpus
                kw["comparison"] = True
            edge(src=host, type=rel or "adjunct", dst=tgt,
                 verb=verbname, scopes_over="event", **kw)
    edges.extend(made_edges)
    return {"verb": verbname, "subject": subj, "negated": negated}


def _agrees(a, b):
    """Do two agreement triples match on the features both of them state?

    Requiring all three to match blocked almost every inheritance, because a
    participle does not inflect for person: Psalm 23:1's predicate is *ro'i*,
    a participle, so the carried subject arrived with person=None and could
    never match 23:2's third-person verbs.

    So: compare only the features present on BOTH sides, and require at least
    one real comparison. Absence is not disagreement -- but absence of every
    feature is not agreement either, or an unmarked form would inherit from
    anything.
    """
    if not a or not b:
        return False
    compared = 0
    for x, y in zip(a, b):
        if x and y:
            if x != y:
                return False
            compared += 1
    return compared > 0


def _imperative(cl):
    """Is this clause headed by an imperative?

    Hebrew and Aramaic put it in `type`; Greek puts it in `mood` and carries
    no `type` at all, so reading only `type` silently missed every Greek
    imperative -- and an imperative's subject is the addressee, which is one
    of the five elision cases.
    """
    for w in cl.iter("w"):
        if w.get("role") == "v" or _pos(w) == "verb":
            return ((w.get("type") or "").startswith("imperative")
                    or (w.get("mood") or "").lower() == "imperative")
    return False


# Hebrew stems that make a verb passive or reflexive, plus the participle
# forms MACULA labels directly.
# Hebrew and Aramaic build passives from the STEM; Greek states a voice.
# Aramaic is a third of the same corpus's grammar and none of its stems are
# Hebrew's: Daniel, Ezra, Jeremiah 10:11 and Genesis 31:47.
PASSIVE_STEMS = {"niphal", "pual", "hophal", "hothpaal",          # Hebrew
                 "peil", "hithpeel", "hithpaal", "ithpeel", "ithpaal"}
GREEK_PASSIVE = {"passive", "middlepassive"}
SPEECH = {"say", "says", "said", "speak", "spoke", "declares", "answered",
          "answer", "commanded", "called", "cried", "replied", "tell"}


def _passive(cl):
    """Is the clause headed by a passive with no expressed agent?

    2026-09-05: the question was what had been done for the Aramaic texts.
    Nothing, and this is where it showed. **Three languages mark voice three ways** and the
    first version read only Hebrew's:

        Hebrew    stem   niphal, pual, hophal, hothpaal
        Aramaic   stem   peil, hithpeel, hithpaal, ithpeel, ithpaal
        Greek     voice  passive, middlepassive  -- and Greek has NO `type`
                         attribute at all, so the participle test never fired

    7,549 Aramaic words sit in Daniel 2:4b-7:28, Ezra 4:8-6:18 and 7:12-26,
    Jeremiah 10:11 and Genesis 31:47. Their ~150 passives were being counted
    as clauses with an unresolvable subject rather than as clauses whose agent
    is deliberately unexpressed -- a different and wrong claim. Greek's 3,331
    passives and middle-passives were the same.

    The rest of the pipeline transfers without change, because MACULA uses one
    shared vocabulary for `type` (qatal, yiqtol, imperative, participle) across
    Hebrew and Aramaic, and one shared set of roles across all three. Only the
    morphology of the verb itself is language-specific.
    """
    for w in cl.iter("w"):
        if w.get("role") == "v" or _pos(w) == "verb":
            if (w.get("stem") or "").lower() in PASSIVE_STEMS:
                return True
            if (w.get("voice") or "").lower() in GREEK_PASSIVE:
                return True
            return "passive" in (w.get("type") or "").lower()
    return False


def _speech_subject(cl, subj):
    """If this clause is a speech act, whose speech is it?

    Jeremiah 34:17 opens "thus says the LORD" and then continues in the first
    person for the rest of the verse. The speaker is stated in the frame, one
    clause earlier, and tracking it turns every following first-person verb
    from unresolved into resolved -- which is this morning's finding about
    quotation spans, applied at clause range instead of span range.
    """
    if not subj:
        return None
    for w in cl.iter("w"):
        if w.get("role") == "v" or _pos(w) == "verb":
            e = _text(w).lower()
            return subj if e in SPEECH else None
    return None


def agreement(cl):
    """(person, gender, number) of the clause's finite verb."""
    for w in cl.iter("w"):
        if w.get("role") == "v" or _pos(w) == "verb":
            return (w.get("person"), w.get("gender"), w.get("number"))
    return (None, None, None)


def resolve(clauses, speaker=None, addressee=None, carry=None):
    """Nodes and edges for a run of clauses, with elided subjects filled in.

    Hebrew drops the subject constantly because the verb carries person,
    gender and number. The elision is not one problem but three, and each has
    its own deterministic answer:

        3rd person   inherit from the nearest preceding clause subject that
                     AGREES. Narrower than the recency-over-all-nouns rule
                     that scored 29% in August: the candidate set is clause
                     subjects, and agreement must match rather than merely be
                     compatible.

        1st person   inside quoted speech the subject IS the speaker. No
                     agreement reasoning is involved and none is needed.

        2nd person   the addressee, same way.

    A verse is a chapter division rather than a grammatical unit, so `carry`
    passes the last stated subject in from the preceding verse -- Psalm 23:2
    states no subject at all and wants the one from 23:1.

    Every filled subject is marked `inferred_subject`, because an inherited
    subject is a weaker claim than a stated one and the graph should not
    flatten the difference.
    """
    made, edges = [], []
    last = carry
    prev_subj = None
    for cl in clauses:
        start = len(edges)
        info = build(cl, made, edges)
        p, g, n = agreement(cl)
        subj = info.get("subject")
        if subj:
            last = (subj, (p, g, n))
            prev_subj = subj
            spk = _speech_subject(cl, subj)
            if spk:
                speaker = spk
            continue

        # A span with no verb AND no subject is not a clause missing its
        # subject -- it is an adjunct phrase. Esther 8:9's "province and
        # province, in its own script" is marked ADV-PP by MACULA and has
        # nothing to elide. Looking for a subject there asks the wrong
        # question; it attaches to the clause before it.
        if not info.get("verb"):
            if prev_subj:
                for e in edges[start:]:
                    if e.get("src") is None:
                        e["src"] = prev_subj
                        e["attached_to_previous_clause"] = True
            continue

        # An agentless passive has no subject to find. "Written in the name of
        # the king", "sealed with the king's ring" -- Hebrew leaves the agent
        # unexpressed on purpose, and the decree being written is the point
        # rather than who held the pen. Recording `unexpressed` is the correct
        # analysis; hunting for an antecedent would invent one.
        if _passive(cl):
            for e in edges[start:]:
                if e.get("src") is None:
                    e["src"] = None
                    e["agent"] = "unexpressed"
            continue

        fill = why = None
        if p == "first" and speaker:
            fill, why = speaker, "speaker of the enclosing speech"
        elif p == "second" and addressee:
            fill, why = addressee, "addressee of the enclosing speech"
        elif _imperative(cl):
            # An imperative's subject is whoever is being addressed, and that
            # is true before we know who they are. A named role-node beats a
            # null: it can be bound when the speech layer supplies a speaker,
            # and it says something true in the meantime.
            fill, why = addressee or "addressee", "subject of an imperative"
        elif last and _agrees(last[1], (p, g, n)):
            fill, why = last[0], "nearest agreeing clause subject"
        if fill:
            for e in edges[start:]:
                if e.get("src") is None:
                    e["src"] = fill
                    e["inferred_subject"] = why
            if fill not in made:
                made.append(fill)
    return {"nodes": made, "edges": edges, "carry": last}


NEGATIVE = {"not", "no", "never", "nothing", "neither", "nor"}


def _is_negative(e):
    ws = [e] if e.tag == "w" else list(e.iter("w"))
    return any(_pos(w) in ("particle", "adverb", "prt", "adv")
               and _text(w).lower() in NEGATIVE
               for w in ws)


# COMPARISON IS MORPHOLOGICALLY MARKED, and the English gloss throws it away.
# "like a lion" and "took her as wife" both gloss as *as*, but Hebrew keeps them
# apart: כְּ and כְּמוֹ compare, לְ predicates a role, בְּ is locative. Counted over
# the first 120 Hebrew files: le- 124, ke- 118, kemo 18, be- 11.
#
# This matters because a figurative use is a property of the OCCURRENCE, not of
# the word. The lion of 1 Peter 5:8 and the lion Daniel was shut in with are the
# same lemma and not the same thing -- which is exactly what the schema's
# `drawn_from` note insists on -- and one node per occurrence is the right
# granularity to record it at.
# Compared BARE, with vowel points and accents stripped. Matching the pointed
# forms directly returned zero: Hebrew niqqud and Greek accents are combining
# marks, and the XML's normalisation form need not equal a source literal's.
# A silent zero that looks like "the corpus has no similes".
COMPARATIVE = {"כ", "כמו", "ως", "ωσπερ", "ωσει", "καθως"}


def _bare(s):
    """Drop combining marks so a lemma compares by its letters."""
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if not unicodedata.combining(c))


def _comparative(e):
    """Is this constituent a SIMILE -- a thing likened to a thing?

    The particle alone is not enough. Hebrew *ka'asher* -- "just as the LORD
    commanded Moses" -- carries the same ke- and compares an ACTION, not an
    entity, and it dominated the first run: lord 93, Moses 18, commanded 11,
    promised 10. Those are not images of anything.

    A simile's object is a noun; a comparative clause has a verb in it. So the
    presence of a verb inside the constituent is the discriminator, and it is
    structural rather than a word list.
    """
    ws = [e] if e.tag == "w" else list(e.iter("w"))
    if any(_pos(w) == "verb" for w in ws):
        return False
    for w in ws:
        if _pos(w) == "preposition" and _bare(w.get("lemma")) in COMPARATIVE:
            return True
    return False


def _prep(e, mint, made, edges):
    """(relation, target) for a prepositional or plain constituent."""
    if e.tag == "w":
        return None, mint(e)
    prep = next((w for w in e.iter("w")
                 if _pos(w) == "preposition"), None)
    rel = None
    if prep is not None:
        rel = re.sub(r"[^a-z]", "", _text(prep).lower()) or None
    # A COORDINATED constituent must be reified, not walked into. Taking the
    # first sub-phrase -- or, where the conjuncts are bare words, the first
    # word -- silently kept one member and dropped the rest. 1Chr 23:21's
    # predicate is `NpaNp` over two bare words, so "the sons of Merari; Mahli,
    # and Mushi" recorded Mahli alone, and every roster in the genealogies lost
    # everyone after the first name. Recursing per conjunct keeps the
    # preposition out of the members' names, which is what the `to -> to` bug
    # of Genesis 25:2 was.
    rule = e.get("rule") or ""
    if COORD.match(rule):
        parts = []
        for c in list(e):
            if c.tag == "w":
                if _pos(c) in CONTENT and c is not prep:
                    parts.append(mint(c))
            else:
                r2, t2 = _prep(c, mint, made, edges)
                rel = rel or r2
                parts.append(t2)
        comp = _compose(parts, made, edges)
        if comp:
            return rel, comp

    # A CONSTRUCT must be reified for the same reason a coordination must: its
    # meaning is the pair, not either half. Walking into it returned the inner
    # phrase and lost the relation the chain states.
    if rule == "NPofNP":
        return rel, mint(e)

    # THE HEAD IS THE BARE NOUN, NOT THE SUB-PHRASE. 2Chr 26:3's predicate is
    # `NpPp` -- "Jecoliah of Jerusalem" -- a head noun with a prepositional
    # modifier hanging off it. Preferring the sub-phrase returned *Jerusalem*
    # and dropped Jecoliah entirely, so the regnal formula recorded a king's
    # mother's name as a city. That formula is most of `mother_of` in Chronicles
    # and Kings, which is why that relation sat at 0% recovery with 40% of its
    # instances reachable.
    direct = [c for c in list(e)
              if c.tag == "w" and c is not prep and _pos(c) in CONTENT]
    if direct:
        return rel, mint(direct[0])

    inner = [c for c in list(e) if c.tag != "w"]
    if inner:
        return rel, mint(inner[0])
    # No sub-phrase: the preposition's object is a bare word beside it. Taking
    # mint(e) here named the phrase by its own preposition and produced the
    # `to -> to` edge in Genesis 25:2 -- a relation pointing at itself.
    rest = [w for w in e.iter("w") if w is not prep]
    if rest:
        return rel, mint(rest[0])
    return rel, None


def _add(made, i):
    if i and i not in made:
        made.append(i)
