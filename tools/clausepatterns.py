"""Patterns inside a sentence: a template, its slots, and what fills them.

2026-09-05: start harvesting patterns so as to build out the discipline at the
micro-level before expanding up, and then the scoping that matters: for now the
patterns are the simple ones that exist within a sentence, as opposed to the
rich ones to come.

So nothing here crosses a sentence boundary. The point is to establish what a
pattern IS, and how one is measured, on the easy cases — before the same
machinery is pointed at speeches, scenes and scrolls where the shapes are
harder and the mistakes are more expensive.

## A pattern is a template plus what fills its slots

The second half is what makes it more than a frequency count, and it is
directly the "coordinates and radius" wanted for pattern slots: **a
slot's observed fillers are its extent.** `[S] said to [X]` is not just 1,531
occurrences; it is 266 distinct things that can stand in that slot, and knowing
which they are is the useful part.

Four shapes, all already in the graph:

    clause        the verb is fixed          [S] begat [O]
    adjunct       verb + preposition fixed   [S] went to [X]
    construct     the head noun is fixed     sons of [X]
    coordination  neither is fixed           [X] and [Y]

**Structural edges are excluded.** `possessed_by` (11,359) and `apposition`
(4,398) are how the graph is wired, not what the text says, and left in they
dominate the list and mean nothing.

## Classified by measurement, never by naming

Naming a pattern is interpretation and belongs in an overlay. Three computed
numbers separate genuinely different things without anyone deciding what a
pattern means:

    reach         how many books it occurs in
    productivity  distinct fillers per instance
    skew          the top filler's share of the slot

    PRODUCTIVE  many fillers, many books. `[S] said to [X]` spans 32 books with
                266 fillers and tops out at 18% -- the text uses it generatively.
    FORMULA     one filler dominates. "Thus says the LORD" is this shape: the
                corpus repeats it rather than composing with it.
    LOCAL       confined to a book or two. Not a failure and not dropped --
                a book with its own idiom is a finding, and Judges repeating
                "they did not drive them out" is exactly that.

## The threshold declared itself

    >= 2 instances   9,639 templates covering 88% of clause instances
    >= 5 instances   3,262 templates covering 75%
    >=25 instances     536 templates covering 54%

Five is where the tail stops being coincidence, so five is the floor. Nothing
was tuned to make a number look better.

    python tools/patterns.py                # harvest, classify, write
    python tools/patterns.py --top          # what the corpus repeats most
    python tools/patterns.py --pattern <key>
    python tools/patterns.py --validate     # does a pattern survive the split?
"""
from __future__ import annotations

import collections
import gzip
import hashlib
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

MIN_INSTANCES = 5
REFS_KEPT = 60
# How the graph is wired, not what the text says. Left in, `possessed_by` alone
# would be the single commonest "pattern" in the Bible.
STRUCTURAL = {"member", "references", "apposition", "possessed_by"}
# An anchor that is a function word yields a template about grammar rather than
# about anything said. Same lesson the contrast harvest learned.
STOP_ANCHOR = {"be", "is", "was", "were", "are", "am", "to", "of", "and", "the",
               "a", "in", "on", "at", "for", "with", "adjunct", "as", "by",
               "from", "not", "it", "this", "that",
               # A CASE MARKER IS NOT A RELATION. 2026-09-20, on the
               # function-word list: most of the patterns were just triples with
               # the relationship fixed on a common word.
               #
               # אֵת is the Hebrew accusative particle. It marks that a noun is
               # the direct object and carries no meaning of its own, which
               # MACULA says out loud by glossing it "(et)" rather than
               # translating it. It nonetheless anchored two templates over
               # 176 instances -- `[S] et [O]`, `[S] et [X]` -- and those say
               # only "a verb here had an object", which is true of most
               # clauses in the Bible.
               #
               # It is worse than an empty template: it outranked the entries
               # on the same list that mean something, because a case marker
               # is by definition frequent.
               "et"}


def slug(s):
    """Normalise a gloss for use inside a template.

    IT USED TO DELETE THE SPACES. `re.sub(r"[^a-z0-9]", "", ...)` removes every
    non-alphanumeric character, and MACULA glosses a word with a phrase often
    enough that the template then claimed a word the text cannot contain:

        according to  -> accordingto     463 instances
        just as       -> justas          179
        because of    -> becauseof       129
        in place      -> inplace          84

    Measured by tools/templateaudit.py, which tests every literal word in every
    template against the glosses AND the Berean text of the verses that
    template itself cites. These were found in neither.

    Identical to the `_slug` bug in tools/senses.py, which welded
    "for edification" into "foredification" on the word cards. Collapsing to a
    single space keeps the token readable and still deterministic.
    """
    return re.sub(r"\s+", " ",
                  re.sub(r"[^a-z0-9]+", " ", (s or "").lower())).strip()


# MULTI-WORD PREPOSITIONS THAT THE EDGE VOCABULARY SPELLS AS ONE TOKEN.
#
# The graph's edge `type` is an identifier -- `accordingto`, `becauseof` --
# and this builder used it directly as a template word, so the template claimed
# a word the text cannot contain. Found by tools/templateaudit.py, which tests
# every literal word against the glosses AND the Berean text of the verses the
# template itself cites; these appeared in neither.
#
# Extracted from the edge vocabulary rather than recalled: 16,129 distinct edge
# types, of which these are every one that splits into two English function
# words. 1,544 instances affected. `downward` and `hereby` split cleanly too
# and are deliberately absent, being ordinary words.
UNWELD = {
    "accordingto": "according to", "justas": "just as",
    "becauseof": "because of", "outof": "out of", "someof": "some of",
    "morethan": "more than", "belongsto": "belongs to",
    "insteadof": "instead of", "belongedto": "belonged to",
    "belongto": "belong to", "nextto": "next to",
    "togetherwith": "together with", "ratherthan": "rather than",
    "suchas": "such as", "awayfrom": "away from", "evento": "even to",
    "dueto": "due to", "apartfrom": "apart from", "evenas": "even as",
    "inplace": "in place", "sothat": "so that", "asfaras": "as far as",
}


def spaced(s):
    """`gaveBirth` -> `gave birth`, and `Blessed [are]` -> `blessed`.

    Two jobs. The word boundary the builder encodes as a capital has to survive
    into a template, because templates are read by people.

    **And square brackets have to go.** MACULA's contextual English supplies
    words the Greek does not have, marked in brackets, and it supplies them
    inconsistently: the same μακάριος is glossed `Blessed [are]` at Matthew 5:3
    and `Blessed` at 5:5. That split the beatitudes across two templates and
    **cost a Tier 1 case in `docs/GROUPING-TESTS.md`** -- nine identical verses
    that no run-detector could see as a run.

    Stripping supplied English recovers it as `Mat 5:3-11 "is blessed"`, and
    takes consecutive-run collections from 117 to 134 across the canon. What is
    in brackets is the translator's, not the text's, and a pattern over the text
    must not be keyed on it.
    """
    s = re.sub(r"\s*\[[^\]]*\]", "", s or "")
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    # The capital is the only word boundary this could recover, and the edge
    # vocabulary does not use one -- `accordingto` has nothing to split on.
    return UNWELD.get(s, s)


# The words English can put where Hebrew puts a construct. A replacement has to
# be one of these: anything else means the head was only part of the phrase.
CONNECTORS = {"of", "the", "to", "from", "in", "by", "for", "with", "on",
              "over", "at", "into", "upon", "against", "before", "among"}


def connectors(rows):
    """Let the translation say which word joins a construct chain.

    2026-09-15 and again on 2026-09-16: the first pattern should say
    'declares the [X]' not 'declares of [X]', as it is obvious in the first
    reference; and the test was meant to be on the BSB.

    Both points hold. The builder renders EVERY construct as `of`,
    because that is what a construct usually means; Hebrew marks the relation
    with no word at all, so the English has to supply one and `of` is the
    common case. It is not the only case, and the Berean text already knows
    which -- נְאֻם־יְהוָה is not "declares of the LORD", it is **"declares the
    LORD"**.

    The earlier audit missed this by asking whether "of" appeared ANYWHERE in
    the verse, which a long verse almost always satisfies. The question that
    settles it is what the translation puts BETWEEN the two words:

        template            instances   BSB puts after the head word
        king of [X]               666   "of" 50/50
        descendants of [X]        309   "of" 15/15
        word of [X]               244   "of" 32/34
        declares of [X]           364   "the" 41/41    <-- alone in the corpus

    So the connector is read off the translation rather than assumed, and only
    replaced when the evidence is overwhelming: at least 8 readings and at
    least 80% agreeing on a word that is not "of". Everything else is left
    exactly as it was -- this corrects a wrong word, it does not re-translate
    the corpus.
    """
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        sys.path.insert(0, str(ROOT))
        from bsbconvert import verses as _v
        from app2.server import MACULA_BACK
        bsb = _v("verses.bsb.jsonl")
    except Exception as exc:                      # no Berean text on disk
        print(f"  connectors: skipped ({exc})")
        return

    def english(ref):
        try:
            mb, c, v = ref.split(".")
            return bsb.get((MACULA_BACK.get(mb, mb), int(c), int(v))) or ""
        except (ValueError, TypeError):
            return ""

    changed = 0
    for r in rows:
        m = re.fullmatch(r"([a-z][a-z ]*) of \[X\]", r["template"])
        if not m:
            continue
        head = m.group(1)
        seen = collections.Counter()
        for ref in r["refs"][:40]:
            for mm in re.finditer(r"\b" + re.escape(head) + r"\b\s+(\w+)",
                                  english(ref), re.I):
                seen[mm.group(1).lower()] += 1
        if not seen:
            continue
        word, n = seen.most_common(1)[0]
        total = sum(seen.values())
        # ONLY A CONNECTOR MAY REPLACE A CONNECTOR. The first version accepted
        # whatever word followed the head, and where the head was only PART of
        # the English phrase that word was the rest of the noun: "fierce of
        # [X]" became "fierce anger [X]", "scarlet of [X]" became "scarlet yarn
        # [X]" -- losing the genitive instead of correcting it. An incomplete
        # head is a different defect and is left alone rather than papered over.
        if word in CONNECTORS and word != "of" and n >= 8 and n / total >= 0.8:
            r["template"] = f"{head} {word} [X]"
            r["key"] = key_of(r["template"])
            r["connector_from_bsb"] = [word, n, total]
            changed += 1
    print(f"  connectors: {changed} template(s) re-joined from the Berean text")


def key_of(template):
    return hashlib.md5(template.encode()).hexdigest()[:10]


# ---------------------------------------------------------------------------
# ANCHORS ARE KEYED ON THE WORD, NOT ON WHAT A TRANSLATOR CALLED IT.
#
# 2026-09-18, after asking to see tangible verse-level examples of why a
# pattern failed to match across parallel passages: the gloss keying is fixed
# first.
#
# `2Sa 10:10` and `1Ch 19:11` are word-for-word identical and parse to
# identical trees, and they produced different templates:
#
#     2Sa 10:10   [S] placed [O]    [S] placed in [X]    [S] engage [O]
#     1Ch 19:11   [S] put [O]       [S] put in [X]       [S] against [O]
#
# Every differing word is the SAME WORD -- נָתַן is Strong 5414 in both, glossed
# "placed" in Samuel and "put" in Chronicles; קרא is 7122, glossed "engage" and
# "against". The templates were built from the ENGLISH GLOSS, so one Hebrew
# verb made two patterns whenever the translators chose differently. `[S] put
# [O]` had 384 instances and `[S] placed [O]` had 36; they are one pattern.
#
# The scale of it, measured over the corpus: across 10,373 Strong's numbers the
# median word carries 2 distinct glosses and the mean 5.6. נָתַן carries 210
# over 2,009 uses, עָשָׂה 198, λέγω 183. 273 frequent words carry ten or more, so
# `[S] said` was split across *said / saying / he said / says / I say*. Every
# instance count this file reported was an undercount.
#
# So the anchor is resolved to its Strong's number through the verse's own
# interlinear, and the template is labelled with that number's COMMONEST gloss.
# 89.8% of template-producing anchors resolve; the rest are multi-word anchors
# ("said to", "i say to") where the template spans more than one word, and they
# keep the old behaviour rather than being guessed at.
#
# WHAT THIS DELIBERATELY LOSES: aspect that only the English carried. *said*,
# *saying* and *says* are one Strong's number and now one template. That is
# defensible because a template is a TYPE and the instance still carries its
# own words -- but it is a real loss, and if aspect turns out to matter the fix
# is morphology from MACULA, not the gloss. Verb nodes carry a `type` field
# ("infinitive construct") but only 2.2% of anchors appear as nodes, so that
# route is not available today.
#
# MEASURED, 2026-09-18, rebuilding the whole layer:
#
#     templates  12,492 -> 6,920   (-5,572; 45% were the same pattern twice)
#     instances 145,448 -> 158,457 (+13,009)
#
#     [S] said        2,859 -> 4,891
#     son of [X]      1,047 -> 2,497
#     [S] give [O]      512 -> 1,950
#     [S] placed [O]     36 -> merged into [S] give [O]
#     [S] engage [O]      3 -> merged into [S] call [O]
#
# `[S] put [O]` survives at 620 rather than merging into `give`, which is the
# check that this keys on the WORD and not on the English: those are שׂים 7760,
# a different verb that English also renders "put".
#
# Regression set -- the 38 verse pairs with identical lemma sequences across
# Samuel/Kings/Chronicles:
#
#     before  mean jaccard 0.86, exact 26/38
#     after   mean jaccard 0.96, exact 35/38
#
# The three that still disagree: `2Sa 23:37`/`1Ch 11:39`, where MACULA wraps a
# participial phrase in a `cl` in Chronicles and not in Samuel, so the parse
# genuinely differs and this layer cannot fix it; and two pairs with identical
# trees that each lose one template, which is an edge-extraction difference
# upstream of here and is recorded in BACKLOG.
#
# SLOT FILLERS ARE NOT CANONICALISED, only anchors. A filler is the part that
# varies and is shown to the reader as it stands; canonicalising it would hide
# the text behind a lexicon entry. That means filler counts remain fragmented
# by gloss, which affects skew, and is recorded in BACKLOG rather than fixed
# here.

GLOSS_STRONG: dict = {}
STRONG_GLOSS: dict = {}
# The anchor's part of speech, read off the corpus.
LEMMA_POS: dict = {}

# A FUNCTION WORD IS NOT SOMETHING SAID, AND THE ENGLISH LIST COULD NOT SEE IT.
#
# `STOP_ANCHOR` states the rule already -- "an anchor that is a function word
# yields a template about grammar rather than about anything said" -- but it
# tests the English, so `behold`, `no` and `what` sailed through it.
#
# 2026-09-19, on `[S] is behold` standing second in the list: it reads like a
# stand-alone command, as in Genesis 6:13, "Now behold, I will
# destroy both them and the earth." The parse agrees:
# הִנֵּה is a PARTICLE and the thing filling [S] is a pronominal SUFFIX, so the
# template reads a presentative particle with a pronoun stuck to it as though
# it were a subject and a predicate.
#
# 40 of 5,744 templates are anchored this way -- 1% -- but they rank high,
# because one filler dominating a slot is exactly what the ranking rewards and
# a particle takes few fillers.
#
# THEY ARE NOT DROPPED: this should be its own list. Which is the standing
# rule -- rank, do not exclude -- and right here for a second reason:
# "behold" IS a thing the text does, repeatedly and deliberately, and a reader
# interested in how Hebrew points at something would want exactly this list.
# It is only wrong when it sits among the fixed phrases pretending to be a
# predication. So the part of speech is recorded and the app files them
# separately.
FUNCTION_POS = {"particle", "ptcl", "suffix", "pronoun", "conjunction",
                "preposition"}
# lemma -> Strong's number, so a pattern can carry the key that opens the same
# word card the reader opens. 2026-09-19: clicking it should show the same thing
# as clicking in the reader.
LEMMA_STRONG: dict = {}


def load_lexicon():
    """Fill GLOSS_STRONG (per verse) and STRONG_GLOSS (corpus-wide).

    KEYED ON THE LEMMA, NOT THE STRONG'S NUMBER, and the first version of this
    got it wrong. Hebrew and Greek share a number namespace here: **5207 is
    both Greek υἱός, "son", and Hebrew נִיחֹחַ, "pleasing"**, so taking the
    commonest gloss for 5207 gave "son" on 367 occurrences against "pleasing"
    on 43 — and the offering formula rendered in the reader as *"aroma to
    son"*, which is what exposed it.

    It is not a corner case. **4,443 of 10,373 numbers carry more than one
    lemma (42.8%), covering 406,808 word occurrences.** Keying on the number
    silently rewrote the minority word wherever two languages shared a number.

    The lemma is the word and cannot collide, so that is the key. `strong` is
    still stored, for callers that have a number and no lemma.
    """
    freq = collections.defaultdict(collections.Counter)
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        ref = d.get("ref")
        if not ref:
            continue
        per = GLOSS_STRONG.setdefault(ref, {})
        for w in d.get("words") or []:
            g = slug(w.get("g"))
            lem = w.get("l")
            if not g or not lem:
                continue
            # First gloss wins within a verse: a repeated gloss in one verse is
            # nearly always the same word, and where it is not, the anchor is
            # ambiguous anyway.
            per.setdefault(g, lem)
            freq[lem][g] += 1
            if w.get("s"):
                LEMMA_STRONG.setdefault(lem, w["s"])
            # KEYED ON THE SENSE, NOT THE LEXEME. מוּל is a verb where it
            # means "circumcise" and a preposition where it means "in front
            # of", and taking the lemma's corpus-wide majority filed
            # `[S] circumcised` under prepositions. The gloss names which
            # sense is in play, so the pair decides.
            if w.get("p"):
                LEMMA_POS.setdefault((lem, g),
                                     collections.Counter())[w["p"]] += 1
    for lem, c in freq.items():
        STRONG_GLOSS[lem] = c.most_common(1)[0][0]
    # Kept whole, not just the winner: the card shows the range so a reader who
    # lands on a different English still recognises the word.
    _GLOSS_COUNTS.update(freq)
    return len(GLOSS_STRONG), len(STRONG_GLOSS)


def anchor_word(ref, w):
    """The template's word for an anchor: its lexeme's commonest gloss.

    Falls back to `w` unchanged when the anchor cannot be resolved to a single
    word of the verse, so an unresolvable anchor behaves exactly as before.
    """
    if not w:
        return w
    s = (GLOSS_STRONG.get(ref) or {}).get(w)
    if not s:
        return w
    return STRONG_GLOSS.get(s, w)


def anchor_lemma(ref, w):
    """The ORIGINAL word behind an anchor, or None if it cannot be resolved.

    2026-09-19, after tracing `declares the [X]` by hand to Numbers 24:4
    and finding the word there is *prophecy*: prophecy and declares are the
    same word, so how can pattern matching do this justice and bring as much
    insight as the good old fashioned word navigation?

    Word navigation worked because it shows the ORIGINAL word, which is the
    stable identity. A template shows one English rendering, which is a choice,
    and the corpus makes a different choice 43.5% of the time — so the label on
    a card routinely does not appear in the verse the card sends you to.

    Worse, three different Englishes are in play for one Hebrew word at Numbers
    24:4: MACULA's dominant gloss is *declares* (what the card says), MACULA's
    gloss at that verse is *oracle* (what the interlinear strip says), and the
    Berean text reads *prophecy* (what the reader actually reads). Nothing on
    screen said those were one word.

    So the lemma travels with the pattern. It is what the card can show beside
    the English to make the two readings resolve to one thing.
    """
    return (GLOSS_STRONG.get(ref) or {}).get(w)


def _anchor_gloss(template):
    """The template's own anchor word, which names the sense in play."""
    t = re.sub(r"\[[A-Z]\]", " ", template or "")
    t = re.sub(r"(is|of|to|the|a|in|on|at|for|with)", " ", t)
    words = [w for w in t.split() if w]
    return words[0] if words else None


def _anchor_pos(lemmas, gloss=None):
    """The part of speech of the anchor IN THIS SENSE, or None.

    A lexeme can be two kinds of word and the gloss says which is meant, so
    the lookup is by (lemma, gloss). Falling back to the lexeme's overall
    majority would refile every verb whose lemma is more often a preposition.
    """
    if not lemmas:
        return None
    lem = lemmas.most_common(1)[0][0]
    if gloss:
        c = LEMMA_POS.get((lem, slug(gloss)))
        if c:
            return c.most_common(1)[0][0]
    merged = collections.Counter()
    for (l_, _g), c in LEMMA_POS.items():
        if l_ == lem:
            merged.update(c)
    return merged.most_common(1)[0][0] if merged else None


def _run_lemmas(ref, text):
    """Split an English run into (gloss, lemma) by this verse's own glosses.

    Greek edges fuse the verb and its preposition into one camel-cased type:
    `heSaidTo` spaces out to "he said to", which is not a gloss of anything,
    so an all-or-nothing lookup returned None and **38% of New Testament
    templates could not be named by their lexeme** against 5% of the Hebrew.
    Every miss was λέγω -- `[S] said to [O]`, `[S] i say to [O]`,
    `[S] he says to [O]` -- the commonest verb in the Gospels.

    The longest prefix that IS a gloss here wins, and the remainder is walked
    the same way, so "he said to" resolves as λέγω + πρός rather than as
    nothing. Unresolvable words are skipped rather than guessed at.
    """
    per = GLOSS_STRONG.get(ref) or {}
    words = [w for w in (text or "").split() if w]
    out, i = [], 0
    while i < len(words):
        for n in range(len(words) - i, 0, -1):
            cand = slug(" ".join(words[i:i + n]))
            lem = per.get(cand)
            if lem:
                out.append((" ".join(words[i:i + n]), lem))
                i += n
                break
        else:
            i += 1
    return out


def _fixed_positions(p):
    """Each fixed position of a template, named by its lexeme.

    One entry per word of the ORIGINAL. `share` is how often that lexeme is
    the one standing there, which says whether the position is genuinely
    fixed in the language or only in the English: a position holding one
    lexeme at 100% is a formula, and one holding three at 40/35/25 is a
    rendering that happens to coincide.
    """
    out = []
    for i in sorted(p["fixed"]):
        c = p["fixed"][i]
        n = sum(c.values())
        if not n:
            continue
        lem, top = c.most_common(1)[0]
        g = p["fixed_gloss"].get(i)
        out.append({"lemma": lem,
                    "key": _lemma_key(collections.Counter({lem: 1})),
                    "gloss": g.most_common(1)[0][0] if g else None,
                    "share": round(top / n, 3),
                    "lexemes": len(c)})
    return out


def _is_suffix(lemma, gloss):
    """Is this anchor bound morphology rather than a word?"""
    if not lemma:
        return False
    c = LEMMA_POS.get((lemma, slug(gloss))) if gloss else None
    if not c:
        c = collections.Counter()
        for (l_, _g), cc in LEMMA_POS.items():
            if l_ == lemma:
                c.update(cc)
    return bool(c) and c.most_common(1)[0][0] == "suffix"


def _is_function(lemma, gloss):
    """Is this lexeme, in THIS sense, a function word rather than a content one?

    Keyed on the pair for the reason `_anchor_pos` is: מוּל is a verb where it
    means "circumcise" and a preposition where it means "in front of", so the
    lexeme alone would refile the verb.
    """
    if not lemma:
        return False
    c = LEMMA_POS.get((lemma, slug(gloss))) if gloss else None
    if not c:
        return False
    return c.most_common(1)[0][0] in FUNCTION_POS


def _lemma_key(lemmas):
    """`h5002` for the anchor's lemma -- the sense card's own key."""
    if not lemmas:
        return None
    s = LEMMA_STRONG.get(lemmas.most_common(1)[0][0])
    if not s:
        return None
    import re as _re
    n = _re.sub(r"^0+", "", _re.sub(r"[^0-9]", "", s))
    if not n:
        return None
    # Hebrew and Greek share the number namespace, so the language prefix is
    # what makes the key unique -- the same collision that rendered the
    # offering formula as "aroma to son" before the lemma keying landed.
    return ("h" if any("֐" <= c <= "׿"
                       for c in lemmas.most_common(1)[0][0]) else "g") + n


def _also(lemmas):
    """Every English the corpus gives this anchor, beyond the one in the title.

    Ordered by how often each is used, so the card can say "declares · also
    read as oracle, says" and a reader landing on *oracle* knows they are in
    the right verse. Built from the gloss counts already loaded, so it costs
    nothing and cannot drift from them.
    """
    if not lemmas:
        return []
    lem = lemmas.most_common(1)[0][0]
    counts = _GLOSS_COUNTS.get(lem)
    if not counts:
        return []
    top = counts.most_common(1)[0][0]
    return [g for g, _ in counts.most_common(6) if g != top]


_GLOSS_COUNTS: dict = {}


def load():
    nodes = {}
    for line in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if "id" in d:
            nodes[d["id"]] = d
    byref = collections.defaultdict(list)
    for line in gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt",
                          encoding="utf-8"):
        e = json.loads(line)
        if "ref" in e:
            byref[e["ref"]].append(e)
    return nodes, byref


def harvest(nodes, byref):
    """template -> {instances, fillers per slot, books, refs}."""
    # `refs` keeps a readable sample for the file; `all_refs` keeps every one,
    # because the UI has to answer "which patterns does THIS verse use?" for any
    # verse, not only for the first sixty a pattern happened to appear in.
    pat = collections.defaultdict(lambda: {
        "n": 0, "books": set(), "refs": [], "all_refs": set(),
        "lemmas": collections.Counter(),
        # WHICH VERSES EACH FILLER CAME FROM. 2026-09-19: on the declares page,
        # group the verses under the 'What fills each slot' lists and allow the
        # user to navigate through all the examples. The card could say [X] is "lord" 336 times and
        # then showed one undifferentiated list of verses, so a reader could
        # not get from the filler to its own instances.
        "slot_refs": collections.defaultdict(
            lambda: collections.defaultdict(list)),
        "slots": collections.defaultdict(collections.Counter),
        # position -> lexemes (and glosses) seen filling that FIXED position.
        # A fixed position is fixed in the original, not in the English: the
        # same lexeme can be written several ways across instances.
        "fixed": collections.defaultdict(collections.Counter),
        "fixed_gloss": collections.defaultdict(collections.Counter)})

    def word(nid):
        """What fills a slot, keyed on the lexeme rather than the gloss.

        2026-09-18: the slot fillers are fixed too. The anchor fix left
        this half fragmented -- `men` and `people` are both עַם 5971 and were
        counted as two distinct fillers of the same slot.

        That is not cosmetic. `productivity` is distinct fillers per instance
        and `skew` is the top filler's share, and those two numbers are what
        sort a FORMULA from a PRODUCTIVE pattern and therefore what orders the
        Explore lists. Splitting one word into several inflates the filler
        count and depresses the top filler's share, so a formula the corpus
        repeats verbatim reads as though the text were composing with it.

        Nodes carry `lemma` directly, so unlike the anchors this needs no
        gloss lookup. It must be the LEMMA and not the Strong's number:
        Hebrew and Greek share a number namespace here, so keying on the
        number rendered the offering formula as "aroma to son". The rest are composite nodes --
        `heavensandearth` is a coordination with no single lexeme -- and they
        keep their text.

        MEASURED. It does NOT change which templates fire, and it should not:
        the 38 identical-text pairs stay at 0.96 and parallel agreement stays
        at 0.37 / 0.21 / 0.15. The whole effect is in the ranking:

            formula      2,775 -> 2,926   (+151)
            productive   3,595 -> 3,459   (-136)
            local          550 ->   530    (-20)

            248 templates (3.6%) changed kind
            mean skew            +0.018
            mean distinct fillers -0.8

        **151 patterns the corpus repeats verbatim were being reported as
        productive** -- `forced labor of [X]`, `scroll of [X]`, `sand of [X]` --
        because one word counted as several fillers made the slot look open.
        """
        n = nodes.get(nid) or {}
        lem = n.get("lemma")
        # A SUFFIX HAS NO DOMINANT MEANING, and canonicalising it to one was
        # wrong 87% of the time. 2026-09-19, on `[S] is behold` reading
        # "his" where Genesis 6:13 plainly says *I*: the construction was
        # nonsensical.
        #
        # Every Hebrew pronominal suffix carries the lemma הוּא -- 46,940
        # occurrences, 45,530 of them tagged `suffix` -- so the lexeme's
        # commonest gloss is a single word, "his", covering 13% of them. The
        # other 87% are your, you, my, him, them, their, me, it, her. The
        # canonicalisation that stopped `men` and `people` fragmenting into two
        # fillers of one lexeme rewrote every suffix in the corpus into the
        # same one.
        #
        # It was not confined to the behold card: **987 of 6,913 templates
        # (14.3%) have a slot majority-filled by a pronoun gloss**, and the
        # reader was told `[S] answered [O]` takes "his" 117 times and `[S] i
        # say to [O]` takes "you" 143 times -- one of those is right by
        # accident.
        #
        # The node already holds what the verse says in place, so a suffix or
        # pronoun keeps it. Nothing is guessed and nothing is looked up: the
        # whole fix is to stop overwriting a word that is only ever resolved
        # locally.
        if n.get("pos") in ("suffix", "pronoun"):
            return spaced(n.get("text") or n.get("local"))
        if lem and lem in STRONG_GLOSS:
            return STRONG_GLOSS[lem]
        return spaced(n.get("text") or n.get("local"))

    def add(t, ref, slots, lemma=None, fixed=None):
        """`fixed` is the ORIGINAL words behind the template's fixed part.

        2026-09-21: the right way is by the lexeme.

        The template is written in English and the English is the lexeme's
        DOMINANT gloss, which the verse need not use. Measured over the
        browsable layer, only **43.1% of 164,696 instances sit in a verse
        that contains their own template's words**; `[S] got up [O]` has 230
        instances and none of them. So a count of fixed positions taken from
        the template string counts English words, and three separate attempts
        to recover the original count afterwards all failed -- the last one by
        trying to align the label against verses that do not contain it.

        It cannot be recovered later. It is known HERE, where the template is
        assembled out of specific edges and nodes, and was being thrown away.
        Each entry is one original word: its gloss as written into the
        template, and the lexeme it stands for. "is" and "of" are not in the
        list, because neither is a word of the Hebrew -- the first is how a
        verbless clause is written out and the second is what a construct
        chain means.
        """
        p = pat[t]
        p["n"] += 1
        p["books"].add(ref.split(".")[0])
        p["all_refs"].add(ref)
        if len(p["refs"]) < REFS_KEPT:
            p["refs"].append(ref)
        if lemma:
            p["lemmas"][lemma] += 1
        for i, (g, lm) in enumerate(fixed or []):
            if lm:
                p["fixed"][i][lm] += 1
            # THE POSITION'S GLOSS IS THE CANONICAL ONE, not this verse's.
            # The lemma has to be resolved from what the verse says, since
            # the verse usually does not contain the canonical form -- but
            # the template is WRITTEN in the canonical form, so a label built
            # from these positions only lines up with the template if they
            # agree. Taking it back from the lexeme guarantees that.
            cg = STRONG_GLOSS.get(lm) if lm else None
            if cg or g:
                p["fixed_gloss"][i][cg or g] += 1
        for k, v in slots.items():
            if v:
                p["slots"][k][v] += 1
                # UNCAPPED. 2026-09-19: under lord it states '298
                # more'; that is made clickable to extend the list as it is
                # elsewhere. It could not be: the references were not there
                # to extend to. A count that names what is missing and cannot
                # produce it is the same fault as the list headers that
                # advertised rows the server never sent.
                # A filler can occur twice in one verse -- "declares the
                # LORD" does at 1 Samuel 2:30 -- and the same reference listed
                # twice reads as a bug to anyone scanning it.
                rs = p["slot_refs"][k][v]
                if not rs or rs[-1] != ref:
                    rs.append(ref)

    together = {}
    for ref, edges in byref.items():
        members = collections.defaultdict(list)
        for e in edges:
            if e.get("type") == "member" and e.get("src") and e.get("dst"):
                members[e["src"]].append(e["dst"])

        def predicate(nid):
            """A coordination read as ONE predicate, in a stable order.

            Psalm 103:8 has "compassionate and gracious"; Joel 2:13 has
            "gracious and compassionate". Same formula, reversed, and they
            never match unless the members are sorted.
            """
            kids = members.get(nid)
            if kids:
                return " and ".join(sorted(word(k) for k in kids if word(k)))
            return word(nid)

        # PREDICATION. `is` was stop-listed as a function word, which threw away
        # the whole class: the Hebrew Bible states attributes with a verbless
        # clause, so "the LORD is merciful and gracious" was invisible while
        # `[S] blessed [O]` was not. For a copula the anchor is the PREDICATE
        # and the subject is the slot -- the reverse of every other shape here.
        for e in edges:
            if e.get("type") not in ("is",) or not e.get("dst"):
                continue
            # A PRONOUN IS NOT CANONICALISED EITHER, for the reason a suffix is
            # not: הוּא is the lexeme behind both, its commonest gloss is "his",
            # and running the free pronoun through the lexicon produced the
            # template `his [S]` where the text says *he*. The demonstratives
            # are on the same path and must survive it -- `these [S]` is the
            # toledot formula, "these are the generations of" -- so the rule is
            # to keep what the verse says, not to drop the class.
            pred = predicate(e["dst"])
            if (nodes.get(e["dst"]) or {}).get("pos") not in ("pronoun",
                                                              "suffix"):
                pred = anchor_word(ref, pred)
            if not pred or pred in STOP_ANCHOR:
                continue
            # THE NODE KNOWS ITS OWN LEMMA; DO NOT REVERSE-RESOLVE THE GLOSS.
            # `anchor_lemma` takes the template's English back to a lexeme by
            # looking that English up in the verse, and the template's English
            # is the lexeme's DOMINANT gloss, which the verse need not use.
            # Genesis 22:1 glosses הִנֵּה as *here*, so looking up "behold"
            # found nothing and the instance resolved to no lemma at all.
            #
            # That is worse than a missing label. It split one Hebrew
            # construction in two: instances whose gloss happened to match
            # became `behold [S]` and instances whose gloss did not stayed
            # `[S] is behold` -- a division on lookup failure rather than on
            # anything in the text, which then reported a majority lemma of
            # ὁράω for a template that is 78 parts Hebrew and 2 parts Greek.
            dn = nodes.get(e["dst"]) or {}
            # A SUFFIX CANNOT BE AN ANCHOR. It is bound morphology -- it has no
            # standing as a word -- and the same dominant-gloss fault that made
            # every filler "his" made four templates whose ANCHOR is "his":
            # `[S] his` over 34 instances, `[S] his to [X]`, `his [S]`,
            # `[S] his like [X]`. Naming a template after a pronominal ending
            # is not a shape the text has.
            if dn.get("pos") == "suffix":
                continue
            lem = dn.get("lemma") or anchor_lemma(ref, predicate(e["dst"]))
            # A PARTICLE POINTS; IT DOES NOT PREDICATE. 2026-09-19:
            # the construction was nonsensical.
            #
            # הִנְנִי is הִנֵּה plus a suffix -- "behold me" -- and the copula
            # branch wrote it out as `[S] is behold`, which puts the slot in
            # front of the anchor and inserts an English verb the Hebrew has
            # no room for. A verbless clause really does need the "is": "the
            # LORD is merciful" states an attribute and the reversal is
            # correct there. A presentative states nothing about its
            # complement; it holds it up. So where the predicate is a function
            # word the anchor leads and no copula is written, which is the
            # order the Hebrew has.
            fn = (dn.get("pos") in FUNCTION_POS if dn.get("pos")
                  else _is_function(lem, pred))
            tm = f"{pred} [S]" if fn else f"[S] is {pred}"
            # ONE original word: the predicate. The "is" is ours.
            add(tm, ref, {"S": word(e.get("src"))}, lem, [(pred, lem)])
            if fn:
                # Not a member of any compound predication: "behold and
                # gracious" is not a thing the text says, and letting a
                # presentative into `together` would build families out of it.
                continue
            # A formula is often a SEQUENCE of predications about one subject:
            # Psalm 103:8 says the LORD is "compassionate and gracious" AND
            # "abounding and slow" in one breath. Those two templates share no
            # member, so only co-occurrence on the same subject finds the
            # compound -- and it is exact rather than inferred.
            together.setdefault((ref, word(e.get("src"))), set()).add(tm)

        for e in edges:
            if e.get("type") in STRUCTURAL or e.get("dst_relation"):
                continue
            raw = spaced(e.get("verb") or e.get("type"))
            verb = anchor_word(ref, raw)
            if not verb or verb in STOP_ANCHOR:
                continue
            # A SUFFIX CANNOT BE AN ANCHOR HERE EITHER. The copula branch
            # rejects one by node; this branch names its anchor from the edge,
            # so the lexeme has to be resolved and asked. `[S] his` over 34
            # instances, and three more shapes, are a pronominal ending given
            # the billing of a verb.
            if _is_suffix(anchor_lemma(ref, raw), verb):
                continue
            src, dst = e.get("src"), e.get("dst")
            if e.get("scopes_over"):
                prep = anchor_word(ref, spaced(e.get("type")))
                if not prep or prep in ("adjunct",):
                    continue
                # DO NOT SAY IT TWICE. `verb` falls back to the edge type when
                # the edge carries no verb, and `prep` IS the edge type -- so
                # for a bare prepositional edge both were the same word and the
                # template read "[S] accordingto accordingto [X]". 1,506
                # instances across the corpus, found by tools/templateaudit.py.
                # RESOLVE FROM THE EDGE'S OWN ENGLISH, NOT THE CANONICAL ONE.
                # `raw` is what this verse says; `verb` is the lexeme's
                # dominant gloss, which the verse uses only 43% of the time.
                # Looking the canonical form up in the verse dropped `went up`
                # to a 0.43 share on עָלָה because Genesis 8:20 reads "offered
                # up" -- resolving the label against verses that do not
                # contain it, which is the whole fault this field exists to
                # fix.
                vlem = anchor_lemma(ref, raw)
                rawprep = spaced(e.get("type"))
                if verb == prep:
                    tm = f"[S] {prep} [X]"
                    fx = _run_lemmas(ref, rawprep)
                else:
                    tm = f"[S] {verb} {prep} [X]"
                    fx = _run_lemmas(ref, f"{raw} {rawprep}"
                                     if raw != rawprep else raw)
                add(tm, ref, {"S": word(src), "X": word(dst)}, vlem, fx)
            elif isinstance(dst, str):
                vlem = anchor_lemma(ref, raw)
                add(f"[S] {verb} [O]", ref, {"S": word(src), "O": word(dst)},
                    vlem, _run_lemmas(ref, raw))
            else:
                vlem = anchor_lemma(ref, raw)
                add(f"[S] {verb}", ref, {"S": word(src)}, vlem,
                    _run_lemmas(ref, raw))

        # the construct chain: the head noun is the anchor, the dependent the slot
        for e in edges:
            rel = e.get("dst_relation")
            if not rel or (rel.get("type") or "").lower() != "of":
                continue
            head = anchor_word(ref, spaced((rel.get("src") or "").split("#")[-1]))
            if not head or head in STOP_ANCHOR:
                continue
            # ONE original word: the head noun. The "of" is the construct
            # relation, which Hebrew expresses by juxtaposition and has no
            # word for.
            hlem = anchor_lemma(ref, spaced((rel.get("src") or "")
                                            .split("#")[-1]))
            add(f"{head} of [X]", ref, {"X": word(rel.get("dst"))}, hlem,
                [(head, hlem)])

    cooc = collections.Counter()
    for tms in together.values():
        tl = sorted(tms)
        for i, a in enumerate(tl):
            for b in tl[i + 1:]:
                cooc[(a, b)] += 1
    return pat, cooc


# Canonical order, so "first attested" means first in the story rather than
# first encountered while walking files.
CANON = ["Gen","Exo","Lev","Num","Deu","Jos","Jdg","Rut","1Sa","2Sa","1Ki",
         "2Ki","1Ch","2Ch","Ezr","Neh","Est","Job","Psa","Pro","Ecc","Sng",
         "Isa","Jer","Lam","Ezk","Dan","Hos","Jol","Amo","Oba","Jon","Mic",
         "Nam","Hab","Zep","Hag","Zec","Mal","Mat","Mrk","Luk","Jhn","Act",
         "Rom","1Co","2Co","Gal","Eph","Php","Col","1Th","2Th","1Ti","2Ti",
         "Tit","Phm","Heb","Jas","1Pe","2Pe","1Jn","2Jn","3Jn","Jud","Rev"]
CANON_IX = {b: i for i, b in enumerate(CANON)}


def canon_key(ref):
    b, _, rest = ref.partition(".")
    c, _, v = rest.partition(".")
    try:
        return (CANON_IX.get(b, 99), int(c), int(v))
    except ValueError:
        return (99, 0, 0)


def anchor_members(template):
    """The words a predication template is built from.

    "compassionate and gracious" and "abounding and slow" are two templates of
    one family: they share nothing, but "abounding and slow" and "great and
    slow" share *slow*. Matching whole strings keeps them apart; matching
    MEMBERS finds the family, which is what was meant by order and complexity
    in a collection mattering less than similarity within a slot.
    """
    if not template.startswith("[S] is "):
        return set()
    return {w for w in template[7:].split(" and ") if w and w not in STOP_ANCHOR}


def families(rows, cooc):
    """Templates sharing an anchor member, so a formula's variants find each other."""
    by_member = collections.defaultdict(list)
    for r in rows:
        for m in anchor_members(r["template"]):
            by_member[m].append(r["key"])
    bykey = {r["template"]: r["key"] for r in rows}
    spoken = collections.defaultdict(collections.Counter)
    for (a, b), n in cooc.items():
        ka, kb = bykey.get(a), bykey.get(b)
        if ka and kb:
            spoken[ka][kb] += n
            spoken[kb][ka] += n
    for r in rows:
        rel = collections.Counter()
        for m in anchor_members(r["template"]):
            for k in by_member[m]:
                if k != r["key"]:
                    rel[k] += 1          # shares a word
        for k, n in spoken.get(r["key"], {}).items():
            rel[k] += n * 2              # said in the same breath: stronger
        if rel:
            r["related"] = [{"key": k, "weight": n} for k, n in rel.most_common(8)]


def base_rates(pat):
    """How often each word fills ANY slot, corpus-wide.

    The question: many patterns are shown but they feel pretty open ended --
    `___ bless ___` is any tuple with bless -- so should there be some
    threshold to clear before a pattern is shown?

    A count threshold is the wrong instrument -- `[S] blessed [O]`
    is frequent AND open-ended. What separates a pattern from a verb with
    objects is **surprise**: is the slot filled more narrowly than that filler's
    own corpus frequency would predict?

        tent of [meeting]     "meeting" is rare everywhere else   -> high lift
        [S] blessed [him]     "him" is everywhere                 -> lift ~1

    So the gate is lift, not frequency, and it is computed rather than chosen.
    """
    tot = collections.Counter()
    for p in pat.values():
        for c in p["slots"].values():
            tot.update(c)
    n = sum(tot.values()) or 1
    return {w: c / n for w, c in tot.items()}, n


def classify(p, rates=None):
    """Three measured numbers, no naming. See the module docstring."""
    reach = len(p["books"])
    slots = {k: dict(c.most_common(6)) for k, c in p["slots"].items()}
    open_slot = max(p["slots"].items(), key=lambda kv: sum(kv[1].values()),
                    default=(None, collections.Counter()))
    counts = open_slot[1]
    total = sum(counts.values())
    distinct = len(counts)
    top, topn = counts.most_common(1)[0] if counts else ("", 0)
    skew = topn / total if total else 0.0
    # lift: how much more this slot prefers its top filler than the corpus at
    # large does. 1.0 means the slot is filled exactly as chance would fill it.
    lift = 0.0
    if rates and top and total:
        base = rates.get(top, 0.0)
        lift = (skew / base) if base else 0.0
    productivity = distinct / p["n"] if p["n"] else 0.0
    if total and skew >= 0.5:
        kind = "formula"
    elif reach <= 2:
        kind = "local"
    else:
        kind = "productive"
    # A template clears the bar when its slot is filled surprisingly, or when
    # it is a local habit worth noticing. Everything else is a verb with
    # objects and is harvested but not surfaced by default.
    # Lift alone is degenerate: a filler that occurs nowhere else scores
    # infinity, so `[S] hecomes / gadfly` tied with the real formulae. Surprise
    # needs a volume floor beside it -- the top filler has to actually recur.
    distinctive = bool(lift >= 8 and topn >= 5) or kind == "local"
    return {"reach": reach, "distinct_fillers": distinct,
            "productivity": round(productivity, 3), "skew": round(skew, 3),
            "lift": round(lift, 1), "distinctive": distinctive,
            "top_filler": top, "kind": kind, "slots": slots}


def held_out(book):
    return int(hashlib.md5(book.encode()).hexdigest(), 16) % 2 == 1


def validate(pat):
    """A pattern harvested on one half should recur in the other.

    The same book split the relation work uses, and it answers the question a
    frequency count cannot: is this a pattern of the language, or a habit of
    one author? A template seen only on the derive side is LOCAL whatever its
    count says.
    """
    both = derive_only = heldout_only = 0
    for t, p in pat.items():
        if p["n"] < MIN_INSTANCES:
            continue
        d = any(not held_out(b) for b in p["books"])
        h = any(held_out(b) for b in p["books"])
        both += d and h
        derive_only += d and not h
        heldout_only += h and not d
    tot = both + derive_only + heldout_only
    print("SPLIT CHECK — does a pattern occur on both sides?")
    print(f"  patterns at {MIN_INSTANCES}+ instances   {tot:>7,}")
    print(f"  in both halves                {both:>7,}   {100*both//max(tot,1)}%")
    print(f"  derive books only             {derive_only:>7,}")
    print(f"  held-out books only           {heldout_only:>7,}")
    print()
    print("  One-sided patterns are not failures. They are the corpus having")
    print("  local habits, and they are labelled `local` rather than dropped.")
    return 0


def main() -> int:
    nv, ns = load_lexicon()
    print(f"  lexicon: {nv:,} verses, {ns:,} lexemes with a canonical gloss",
          flush=True)
    nodes, byref = load()
    pat, cooc = harvest(nodes, byref)
    # A count floor is right for open-ended verb templates and WRONG for
    # formulae. "[S] is abounding and slow" occurs three times -- Numbers,
    # Psalms, Nahum -- and is a famous formula; a verb with 500 objects is not.
    # So reach gates the rare ones: twice in two different books is not
    # coincidence, twice in one book might be.
    kept = {t: p for t, p in pat.items()
            if p["n"] >= MIN_INSTANCES
            or (p["n"] >= 2 and len(p["books"]) >= 2)}

    if "--validate" in sys.argv:
        return validate(pat)

    rates, _ = base_rates(kept)
    rows = []
    for t, p in kept.items():
        c = classify(p, rates)
        refs = sorted(p["all_refs"], key=canon_key)
        # `_src` is the template as HARVESTED. connectors() may rewrite
        # `template` from the Berean text, and everything keyed on the original
        # string -- the co-occurrence map, `kept` -- must still resolve.
        rows.append({"_src": t, "key": key_of(t), "template": t,
                     "instances": p["n"],
                     "books": sorted(p["books"], key=lambda b: CANON_IX.get(b, 99)),
                     "refs": refs[:REFS_KEPT],
                     # where the shape is first attested, in canonical order.
                     # "minted in Exodus" becomes a fact you can read off.
                     "first": refs[0] if refs else None,
                     # THE ORIGINAL WORD, and every English the corpus gives
                     # it. A template is one rendering of a lexeme and the
                     # corpus renders it otherwise 43.5% of the time, so a card
                     # showing only the template names a word the reader will
                     # not find in the verse it links to. `declares the [X]`
                     # is נְאֻם, which the Berean text reads as "prophecy" at
                     # Numbers 24:4 and MACULA glosses "oracle" there.
                     "lemma": (p["lemmas"].most_common(1)[0][0]
                               if p["lemmas"] else None),
                     # The key that opens the reader's own word card, so the
                     # anchor on a pattern is the SAME object a reader clicks
                     # in a verse rather than a lookalike.
                     "lemma_key": _lemma_key(p["lemmas"]),
                     # What KIND of word anchors this: a verb and a noun make
                     # a template about something said, a particle makes one
                     # about grammar. Recorded rather than filtered on, so the
                     # app can file them apart instead of losing them.
                     "anchor_pos": _anchor_pos(
                         p["lemmas"], _anchor_gloss(t)),
                     # EVERY lexeme seen at this anchor, not just the
                     # commonest. Where a template holds both testaments the
                     # minority lemma IS the other language's word -- הִנֵּה
                     # 250 times and ὁράω twice for `[S] is behold` -- and
                     # keeping only the winner threw away the better half of
                     # the bridge: the word actually standing in those verses,
                     # rather than the one the Septuagint column predicts.
                     "lemmas": [[l, c] for l, c in p["lemmas"].most_common(6)],
                     # THE FIXED PART, POSITION BY POSITION, IN THE ORIGINAL.
                     # 2026-09-21: the right way is by the lexeme.
                     #
                     # `fixed_orig` is the count the ranking formula needs and
                     # the template string cannot give: "went out" is two
                     # English words and ONE Hebrew verb, and no segmentation
                     # of the English distinguishes that from a genuine
                     # two-word run. Assembled here, where the words are in
                     # hand, rather than reconstructed later from a label that
                     # 57% of instances do not contain.
                     #
                     # Each position also carries its lexeme and how dominant
                     # that lexeme is, so a template can be named by the word
                     # instead of by one of its renderings.
                     "fixed": _fixed_positions(p),
                     "fixed_orig": len(p["fixed"]),
                     "slot_refs": {k: {w: rs for w, rs in v.items()}
                                   for k, v in p["slot_refs"].items()},
                     "also": _also(p["lemmas"]),
                     **c})
    # AFTER families(), which indexes the co-occurrence map by the template
    # string: renaming first raised KeyError: 'declares the [X]'.
    families(rows, cooc)
    connectors(rows)
    rows.sort(key=lambda r: -r["instances"])

    if "--pattern" in sys.argv:
        want = sys.argv[sys.argv.index("--pattern") + 1]
        for r in rows:
            if r["key"] == want or r["template"] == want:
                print(f"{r['template']}   {r['instances']:,} instances "
                      f"· {r['kind']} · {r['reach']} books")
                for slot, fills in r["slots"].items():
                    print(f"  slot [{slot}]: " +
                          ", ".join(f"{k} ({v})" for k, v in fills.items()))
                print(f"  {', '.join(r['refs'][:12])}")
                return 0
        print("no such pattern")
        return 1

    if "--top" in sys.argv:
        for r in rows[:30]:
            print(f"  {r['instances']:>6,}x  {r['template']:32}"
                  f"{r['kind']:11}{r['reach']:>3} books  "
                  f"{r['distinct_fillers']:>4} fillers  top {r['top_filler'][:16]}")
        return 0

    byref_index = collections.defaultdict(list)
    for r in rows:
        for ref in kept[r.get("_src", r["template"])]["all_refs"]:
            byref_index[ref].append(r["key"])

    path = OUT / "patterns.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_source": "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., "
                       "CC BY 4.0",
            "_note": "Within-sentence templates only. Classified by reach, "
                     "productivity and skew -- never named.",
        }) + "\n")
        for r in rows:
            # `_src` is the harvest-time key, used only while building.
            fh.write(json.dumps({k: v for k, v in r.items() if k != "_src"},
                                ensure_ascii=False) + "\n")
    (OUT / "patterns-by-ref.json").write_text(
        json.dumps(byref_index), encoding="utf-8")

    kinds = collections.Counter(r["kind"] for r in rows)
    dist = sum(1 for r in rows if r["distinctive"])
    print("WITHIN-SENTENCE PATTERNS")
    print(f"  templates seen              {len(pat):>7,}")
    print(f"  kept at {MIN_INSTANCES}+ instances       {len(rows):>7,}")
    print(f"  instances covered           "
          f"{sum(r['instances'] for r in rows):>7,}")
    print()
    for k, n in kinds.most_common():
        print(f"    {k:12}{n:>6,}")
    print()
    print(f"  clearing the surprise gate  {dist:>6,}   "
          f"{100*dist//max(len(rows),1)}%  -- shown by default")
    print("  the rest are harvested and browsable, but a verb with objects is")
    print("  not a pattern and should not be presented as one.")
    print()
    print("  most surprising:")
    for r in sorted(rows, key=lambda r: -r["lift"])[:10]:
        print(f"   lift {r['lift']:>7.1f}  {r['template']:28}"
              f"{r['instances']:>5}x  top {r['top_filler'][:18]}")
    print()
    print("  the commonest, with what fills the open slot:")
    for r in rows[:12]:
        print(f"   {r['instances']:>6,}x  {r['template']:30}{r['kind']:11}"
              f"{r['reach']:>3} bk  {r['distinct_fillers']:>4} fillers")
    print(f"\n  wrote {path}")
    print(f"  wrote {OUT / 'patterns-by-ref.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
