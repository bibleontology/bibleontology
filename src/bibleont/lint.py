"""Defects that need a rule, not a judgement.

The supervisor costs about ten cents a review and can afford to look at one
window in eleven. That is fine for the things only judgement can see. It is a
terrible way to catch a node named with a whole verse, which is a string
comparison.

**Everything in this module was first found by reading output, then measured,
then written down.** None of it is speculative: each rule names the real case
that prompted it and the count it had when it was added. A rule that fires on
nothing is deleted rather than kept as insurance.

## Why this is not the gate

`check_extraction` asks whether a batch is *well-formed*: citations resolve,
types exist, quotations match, ids are declared. Everything here is
well-formed by construction and still wrong. `job_1_1 -speaks_of-> evil` is a
valid relation, a real citation and a correctly typed target. It is also the
graph tagging a verse with a word the verse contains, which is a concordance
entry wearing an ontology's clothes.

So this runs *after* the gate and *before* the supervisor: the gate refuses
malformed work for nothing, this refuses shapeless work for nothing, and the
supervisor is left to spend its money on the question neither can answer --
whether the extraction recorded what the passage was saying.

## What a finding means

Not "delete this". Most of these are systemic: they say the prompt is asking
for the wrong shape, and the fix belongs there. A count that falls between
runs is the only evidence that a prompt change worked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Finding:
    rule: str
    subject: str
    detail: str = ""


@dataclass
class Rule:
    name: str
    why: str
    found: list = field(default_factory=list)
    # Whether the rule means anything about a single window.
    #
    # `orphan` does not: inside one window almost everything is unconnected,
    # because its neighbours are in the next window or already in the graph.
    # Running it there would report hundreds of findings that are all false
    # and would teach the worker to avoid making nodes, which is the opposite
    # of what is wanted. Same for near-duplicate ids and speaker-index: all
    # three are statements about the merged whole.
    #
    # The rest are decidable from the batch alone -- an id is a sentence or it
    # is not -- which is what makes them safe to feed back mid-run.
    window_safe: bool = True


# The correct form, for each rule the worker can act on. Written to be pasted
# into a prompt: what was wrong, why it is wrong, and what to do instead.
# The method chosen by hand, and the one measurement we have says it is the one that
# transmits -- the carried-phrase misquotation class went 10 -> 0 when it was
# given worked examples, while the classes described only in prose survived.
FIX = {
    "sentence-as-id":
        "Ids are references, not sentences. A saying gets the reference as its "
        "id and a short label as its name: id `job_9_9`, name \"God makes "
        "the Bear and Orion\" -- never "
        "`he_is_the_maker_of_the_bear_and_orion_of_the_pleiades`.",
    "question-as-id":
        "A question from the text is not an identifier. `doth_job_fear_god_"
        "for_nought` should be id `job_1_9`, name \"Satan asks whether Job "
        "fears God for nothing\".",
    "verse-as-name":
        "A name is a short label a reader would recognise, not the verse. The "
        "verse is already in the corpus under that id; copying it in makes the "
        "node unreadable in every list and menu.",
    "compound-claim":
        "One claim per node. `perfect_and_upright` cannot be shared with "
        "anyone else, so Job and Noah -- whom Ezek 14:14 names together -- "
        "cannot be connected. Emit two edges: `described_as perfect` and "
        "`described_as upright`.",
    "invented-lemma":
        "Tag a node only with a lemma that is in the window's own "
        "original-language block, for a verse the node cites. If the node does "
        "not come from a particular original word -- a claim, a group, a "
        "pattern named across a passage -- omit \"lemma\" entirely. An absent "
        "tag costs nothing; a wrong one asserts the node is grounded in a word "
        "the passage does not contain.",
    "concept-names-a-thing":
        "A concept is an idea the text returns to (adoption, holiness, the "
        "fear of the LORD). A thing is not a concept: a manger, a viper, the "
        "fish of the sea are type `object`, `creature` or `place` -- and where "
        "the passage uses the thing as a picture ('the arm of the mighty'), "
        "type it `image`.",
    "level-skip":
        "A verse does not connect to an idea. It connects to what it SAYS, "
        "and that says something about the idea. Not `job_1_1 -speaks_of-> "
        "evil`, which only records that the word is in the sentence. Instead "
        "the claim itself: `job -described_as-> upright`, cited to Job 1:1. If "
        "you cannot state a claim, do not emit the edge.",
}


# A node id of seven or more words is a sentence, and a sentence is not an
# identifier. The prompt says so, names
# `he_leadeth_me_in_the_...` (Ps 23:3 as an id) as the
# example of what not to do, and that exact id is in the graph. 182 nodes at
# the time this was written, 47 of them from runs made the same day -- so the
# rule is live, not legacy.
ID_WORDS = 7

# A name this long is the verse, copied. Ids are references and names are
# labels a reader would recognise; "There was a man in the land of Uz, whose
# name was Job; and that man was perfect and upright..." is neither.
NAME_CHARS = 100

# A bare verse address used as an entity id -- `2cor_4_1`, `deut_6_10`. The
# suffixed form (`gen_11_3_speech`) is deliberately NOT matched: a speech act
# is a real node and needs a stable key, and where it occurs is the natural
# one. The fault is promoting the verse itself.
_BARE_VERSE = re.compile(r"^[1-3]?[a-z]+_\d+_\d+$")

# The suffixed form, whose NAME is the thing being checked rather than its id.
_KEYED_SPEECH = re.compile(r"^[1-3]?[a-z]+_\d+_\d+_.+$")

# A speech name says who and what kind -- "God's warning to Abimelech",
# "Judah's word to Tamar" -- and fits in a list. Measured on the fresh Genesis,
# Job and Mark batches: 46% were already labelled this way and 54% quoted the
# speech instead, so this threshold splits a habit the extractor already has
# from one it falls back to.
SPEECH_NAME = 45

# Types a metaphor reaches for when a person is said to BE something.
PHYSICAL = {"object", "creature", "place"}

# Edges that assert the thing rather than marking it as a figure.
LITERAL_IS = {"assessed_as", "described_as", "titled", "instance_of", "part_of"}

# Edges asserting that one named individual IS another. `spoken_of_as` is
# excluded deliberately -- it is the type that correctly carries "the Word was
# God", where the corpus does make the statement and the graph should keep it.
NAMED_IS = {"assessed_as", "described_as", "instance_of", "same_as", "titled"}

# Two claims fused into one node cannot be shared. `perfect_and_upright` is
# used by Job alone, and `a_just_man_and_perfect_...` by Noah
# alone, so the graph cannot connect the two men the corpus pairs by name in
# Ezek 14:14.
COMPOUND = re.compile(r"_and_")

_QUESTION = re.compile(
    r"^(doth|dost|hast|hath|whence|wherefore|why|shall|wilt|canst|art|is|are|"
    r"who|what|where|when|how)_")

_STOP = {"the", "of", "and", "a", "in", "to", "is", "that", "his", "her",
         "them", "him", "for", "with", "not", "be", "was", "were", "their"}

# `job_1_1`, `1sam_17_36` -- an id that is only a coordinate. Anything with a
# tail (`job_1_12_speech`) is a named unit and may legitimately reach an idea.
LOCATOR = re.compile(r"^([1-3]?[a-z]+)_(\d+)_(\d+)$")

LEAF = {"concept", "image", "assessment"}


def feedback(found: list, cap: int = 4) -> str:
    """Findings as an instruction the worker can act on, now.

    This is the whole point of a deterministic linter: it answers in
    milliseconds and for nothing, so the worker can be told what it did wrong
    while it is still doing it. An Opus review costs five times a DeepSeek
    retry and arrives, at best, one window in eleven.

    Capped, and one example each. A wall of findings reads as noise and the
    worker starts skimming; three named faults with the correct form is a
    correction it can hold.
    """
    parts = ["", "THE LAST WINDOW WAS CHECKED AND SOME OF IT WAS REFUSED.",
             "These are mechanical faults, found by rule, not opinion.", ""]
    for rule in sorted(found, key=lambda r: -len(r.found))[:cap]:
        if not rule.window_safe or rule.name not in FIX:
            continue
        parts.append(f"  {len(rule.found)}x {rule.name}: {rule.found[0].subject[:70]}")
        parts.append(f"      {FIX[rule.name]}")
        parts.append("")
    if len(parts) <= 4:
        return ""
    parts.append("Do not repeat these in what follows.")
    parts.append("")
    return "\n".join(parts)


def _words(text: str) -> set[str]:
    """Content words, for asking whether a name is already in a verse.

    The length floor was 4 and let `job_1_1 -speaks_of-> man` through: "man"
    is three characters, so the name reduced to nothing and a node with no
    content words cannot be found in anything. Three-letter words carry as
    much here as long ones -- `god`, `man`, `sin`, `law`, `son` are half the
    vocabulary of the corpus. The stopword list, not the length, is what has
    to do the filtering.
    """
    return {w for w in re.findall(r"[a-z]+", (text or "").lower())
            if len(w) > 2 and w not in _STOP}


_REF = re.compile(r"[1-3]?[A-Za-z]+ \d+:\d+$")


def run(entities: dict, relations: list, corpus=None,
        subject: set | None = None) -> list[Rule]:
    """Every rule, against a graph or a single batch.

    `entities` is the LOOKUP -- everything whose type a relation might need,
    which for a single window means the whole graph, because the worker is
    handed the vocabulary and told to reuse it.

    `subject` is what is actually under review: the ids this batch created. It
    exists because merging the graph in for lookup made the entity rules scan
    all 8,475 nodes and report the graph's 340 verse-names to a worker that
    had just written twelve. A correction for someone else's faults is noise,
    and noise is what makes a worker start skimming.
    """
    under = subject if subject is not None else set(entities)
    rules = {
        "sentence-as-id": Rule(
            "sentence-as-id",
            "an id of 7+ words is a sentence; ids are references, names are labels"),
        "question-as-id": Rule(
            "question-as-id",
            "a question from the text used as an identifier -- same fault, "
            "and it reads as a node the graph asserts"),
        "metaphor-taken-literally": Rule(
            "metaphor-taken-literally",
            "a person or being asserted to BE a physical thing, on an edge "
            "that does not mark it as figurative. 'I am the bread of life' is "
            "not a claim about bread",
            window_safe=False),
        "verse-as-node": Rule(
            "verse-as-node",
            "an entity whose id IS a bare verse address: a fragment of a verse "
            "promoted to a thing. The address is already on every relation's "
            "refs, so the node adds nothing and costs a participant that does "
            "not exist"),
        "quote-as-name": Rule(
            "quote-as-name",
            "a speech node named by quoting it. The node is right and the name "
            "is unreadable in a list, a diagram or a search result -- the "
            "quotation belongs in desc"),
        "verse-as-name": Rule(
            "verse-as-name",
            f"a name over {NAME_CHARS} characters is the verse copied into the "
            "graph; the corpus already holds it, keyed by the id"),
        "compound-claim": Rule(
            "compound-claim",
            "two claims fused into one node cannot be shared with anyone else"),
        "invented-relation-type": Rule(
            "invented-relation-type",
            "a relation type that is not in the vocabulary. The merge refuses "
            "it, so the claim is lost entirely -- the work of finding it is "
            "paid for and thrown away"),
        "invented-lemma": Rule(
            "invented-lemma",
            "a node tagged with an original-language word that does not occur "
            "in any verse the node cites. The tag exists to say which word the "
            "node came from; one that names a word the passage does not "
            "contain is worse than none, because it looks like grounding",
            window_safe=False),
        "tagged-not-decomposed": Rule(
            "tagged-not-decomposed",
            "a verse whose every claim is speech-tagging: who spoke, and "
            "which words the saying mentions. The content was never "
            "extracted, so the record says a thing was said and not what was "
            "claimed"),
        "level-skip": Rule(
            "level-skip",
            "a verse locator wired straight to an idea, with no claim between "
            "them -- the meaning layer is missing and this is standing in"),
        "concept-names-a-thing": Rule(
            "concept-names-a-thing",
            "a node typed `concept` whose name is a physical thing -- a "
            "manger, a viper, bronze. `concept` became the catch-all type"),
        "speaker-index": Rule(
            "speaker-index",
            "a passage node that is only spoken and only tags words: who said "
            "which verse, and nothing about what was claimed",
            window_safe=False),
        "orphan": Rule(
            "orphan",
            "a node with no relation at all: paid for, and unreachable",
            window_safe=False),
        "adrift": Rule(
            "adrift",
            "a node the batch created, touched once, and joined to nothing "
            "else in the passage -- usually a fact whose connecting relation "
            "was never extracted",
            window_safe=False),
        "near-duplicate-id": Rule(
            "near-duplicate-id",
            "two ids where one is the other plus a suffix -- usually the same "
            "thing minted twice (`uz` and `uz_land`)",
            window_safe=False),
    }

    out_edges: dict[str, list] = {}
    in_edges: dict[str, list] = {}
    for r in relations:
        out_edges.setdefault(r.src, []).append(r)
        in_edges.setdefault(r.dst, []).append(r)

    for e in (entities[i] for i in under if i in entities):
        if e.id.count("_") >= ID_WORDS - 1:
            rules["sentence-as-id"].found.append(
                Finding("sentence-as-id", e.id, f"{e.id.count('_') + 1} words"))
        if _QUESTION.match(e.id):
            rules["question-as-id"].found.append(
                Finding("question-as-id", e.id))
        # Checked on relations rather than entities; see below.
        if _BARE_VERSE.match(e.id):
            rules["verse-as-node"].found.append(
                Finding("verse-as-node", e.id, e.type))
        elif _KEYED_SPEECH.match(e.id) and len(e.name or "") > SPEECH_NAME:
            rules["quote-as-name"].found.append(
                Finding("quote-as-name", e.id, f"{len(e.name)} chars"))
        if len(e.name or "") > NAME_CHARS:
            rules["verse-as-name"].found.append(
                Finding("verse-as-name", e.id, f"{len(e.name)} chars"))
        if COMPOUND.search(e.id) and e.type in ("assessment", "concept"):
            rules["compound-claim"].found.append(
                Finding("compound-claim", e.id))
        if e.type == "concept":
            kind = _names_a_thing(e.name or "")
            if kind:
                rules["concept-names-a-thing"].found.append(
                    Finding("concept-names-a-thing", e.id,
                            f"'{e.name}' is {kind.split('.')[1]}"))
        if not out_edges.get(e.id) and not in_edges.get(e.id):
            rules["orphan"].found.append(Finding("orphan", e.id, e.type))

    # `uz` beside `uz_land`, `the_sons_of_god` beside `sons_of_god`. Only
    # where BOTH exist and share a type: a person and a place may legitimately
    # share a stem, and that is what the qualified id is for.
    ids = set(entities)
    for i in sorted(under):
        for suffix in ("_land", "_city", "_region", "_place", "_god", "_title"):
            if i.endswith(suffix) and i[: -len(suffix)] in ids:
                a, b = entities[i], entities[i[: -len(suffix)]]
                if a.type == b.type:
                    rules["near-duplicate-id"].found.append(
                        Finding("near-duplicate-id", i,
                                f"also {b.id}, both {a.type}"))
        if i.startswith("the_") and i[4:] in ids:
            rules["near-duplicate-id"].found.append(
                Finding("near-duplicate-id", i, f"also {i[4:]}"))

    # TAGGING IS NOT DECOMPOSING, and this is the concordance failure rebuilt
    # one level up.
    #
    # The graph once held 2,064 relations wiring a verse to a word it
    # contains. That was killed, and the shape came back wearing a speech node
    # instead of a verse node: 865 verses -- 19% of every verse with a claim,
    # 3,658 relations, a quarter of the graph -- whose entire output is who
    # spoke and which words the saying mentions.
    #
    # `speaks_of` is not the fault and must not be flagged on its own: the
    # prompt allows a saying to be ABOUT things, and a text node pointing at a
    # concept is often right. The fault is when that is ALL a verse produced,
    # because then the record is a co-occurrence table with a citation.
    #
    # 1 Corinthians 13:4 is the whole problem in one line. "Love is
    # patient, love is kind" came out (in the older rendering) as `charity_suffereth_long -speaks_of->
    # love`. What the verse CLAIMS -- that charity is longsuffering, that
    # charity is kind -- is absent. And 13:13, whose point is that one of the
    # three is greatest, records only that it mentions all three.
    #
    # 2026-09-02: if this is missed, everything might as well go in a vector
    # db and be done with it.
    # AN INVENTED TYPE IS A CLAIM THROWN AWAY.
    #
    # The prompt says "never invent a relation type; the vocabulary is the
    # trunk and only a person may extend it", and a small model reads that and
    # invents anyway once there is enough to do: zero on a four-verse window,
    # then eight on Psalm 103 and thirteen on Romans 2 -- `crowneth`,
    # `executeth`, `forgiveth`, `accuse`, `bears_witness`.
    #
    # The merge refuses every one, so the cost is total: the claim was found,
    # paid for, and discarded. Caught here it is free and it is fed FORWARD to
    # the next window, which is the only correction that compounds over a book.
    from .schema import load_vocabulary as _lv
    _known = set(_lv().types)
    for r in relations:
        if r.type not in _known:
            rules["invented-relation-type"].found.append(
                Finding("invented-relation-type", f"{r.src} -{r.type}-> {r.dst}",
                        f"{r.type!r} is not in the vocabulary"))

    # The lemma tag is the check on whether the worker read the text or the
    # translation, so a tag naming a word the cited verses do not contain
    # defeats the point of having it. Deterministic: the tagged text either
    # holds that lemma in that verse or it does not. Skipped silently when the
    # tagged text is unavailable, because absence of the corpus is not a
    # finding about the graph.
    _tagged = None
    if any((e.attrs or {}).get("lemma") for e in entities.values()):
        try:
            from .lemmas import load_tagged
            _tagged = load_tagged()
        except Exception:                                        # noqa: BLE001
            _tagged = None
    if _tagged:
        for eid, e in entities.items():
            tags = (e.attrs or {}).get("lemma") or []
            if isinstance(tags, str):
                tags = [tags]
            if not tags:
                continue
            here = {w.lemma for r in (e.refs or [])
                    for w in (_tagged.get(r) or [])}
            if not here:
                continue
            for t in tags:
                if t not in here:
                    rules["invented-lemma"].found.append(
                        Finding("invented-lemma", eid,
                                f"tagged {t}, which is not in "
                                + ", ".join(e.refs or [])))

    TAGGING = {"speaks_of", "asserted_by", "told", "answered", "part_of"}
    _by_verse: dict = {}
    for r in relations:
        for ref in (getattr(r, "refs", None) or []):
            m = _REF.match(str(ref))
            if m:
                _by_verse.setdefault(m.group(0), []).append(r)
                break
    for ref, rs in sorted(_by_verse.items()):
        if not any(x.type == "speaks_of" for x in rs):
            continue
        if all(x.type in TAGGING for x in rs):
            rules["tagged-not-decomposed"].found.append(
                Finding("tagged-not-decomposed", ref,
                        f"{len(rs)} claims, all of them tagging: "
                        + ", ".join(sorted({x.type for x in rs}))))

    # A pure type-pair test, and it needs nothing but the batch. The earlier
    # version asked the corpus whether the target word appeared in the verse,
    # which needed a lookup per edge and found 5,465; this finds 5,925 and is
    # decidable from the ids alone -- because the fault was never "the word is
    # present", it was "the claim is absent".
    for r in relations:
        src, dst = entities.get(r.src), entities.get(r.dst)
        if not src or not dst:
            continue
        if LOCATOR.match(src.id) and dst.type in LEAF:
            rules["level-skip"].found.append(
                Finding("level-skip", f"{r.src} -{r.type}-> {r.dst}",
                        "verse to idea, nothing in between"))

        # A person or being asserted to BE a physical thing, on an edge that
        # does not mark the figure.
        #
        # 2026-09-01, before the gospels are extracted: wait until Jesus'
        # words in Matthew are reached. Taken all literally they would
        # confuse; appreciating that he spoke constantly in metaphors is what
        # makes them read.
        #
        # The danger is narrow and nameable: the COPULA. Marked figures are
        # safe because the text says "is like unto". The unmarked ones say "I
        # am the bread of life", "ye are the salt of the earth", "this is my
        # body" -- and an extractor reads that construction as predication.
        #
        # `likened_to` and `signifies` exist to carry exactly this, so the
        # fault is not the claim but the edge chosen for it. Added while the
        # count is ZERO across Genesis, Job, Mark 1-4, Titus and Philippians,
        # which is the only moment a guard like this is provable rather than a
        # cleanup project. John 6 and Matthew 13 are what it is for.
        # A named individual called by ANOTHER named individual's name.
        #
        # The test set 2026-09-01: a good simple test of the algorithm would
        # be if Matt 16:22-23 were to infer that Peter is Satan -- that would
        # say that the symbolism is being missed.
        #
        # "Get thee behind me, Satan" is a rebuke, not an identification, and
        # nothing in the sentence marks it as figurative. The previous check
        # misses it entirely: it looks for a person asserted to be a physical
        # thing, and Satan is a `being`.
        #
        # The rule is narrower than it looks. Two NAMED individuals joined by
        # an edge that asserts what one IS -- not what one is like, not what
        # one is called in a title formula, but identity or attribution --
        # is nearly always a rebuke, a comparison or a role, and the text
        # marks none of them.
        if (src.type in ("person", "being") and dst.type in ("person", "being")
                and r.type in NAMED_IS and src.id != dst.id):
            rules["metaphor-taken-literally"].found.append(
                Finding("metaphor-taken-literally",
                        f"{r.src} -{r.type}-> {r.dst}",
                        f"one named individual asserted to be another; "
                        f"'Get thee behind me, Satan' is a rebuke"))

        if (src.type in ("person", "being") and dst.type in PHYSICAL
                and r.type in LITERAL_IS):
            rules["metaphor-taken-literally"].found.append(
                Finding("metaphor-taken-literally",
                        f"{r.src} -{r.type}-> {r.dst}",
                        f"a {src.type} asserted to be a {dst.type}; "
                        f"likened_to or signifies carries a figure"))

    for e in (entities[i] for i in under if i in entities):
        if e.type != "text":
            continue
        outs = {r.type for r in out_edges.get(e.id, [])}
        ins = {r.type for r in in_edges.get(e.id, [])}
        if outs and outs <= {"speaks_of"} and ins <= {"told"}:
            rules["speaker-index"].found.append(
                Finding("speaker-index", e.id,
                        f"{len(out_edges.get(e.id, []))} tags, "
                        f"{len(in_edges.get(e.id, []))} spoken-by"))

    return [r for r in rules.values() if r.found]


# A CONCEPT THAT NAMES A THING. Found 2026-09-28, testing the entity store's
# types against the proposed meaning ontology (docs/MEANING-ONTOLOGY.md): of
# 1,388 `concept` records, only 42% of those with a lemma were abstractions
# by WordNet; the rest were things -- "ark", "ashes", "a manger", "livestock",
# "the fish of the sea". The test: the head of the name ("blessings OF the
# breasts" is about blessings) is, in WordNet's usual sense and most of its
# first three, a physical thing. 165 of 1,388 flagged; about 85% right on a
# sample of 40 (misses: "the middle of the night", "sold into Egypt"). Via
# English (PRINCIPLES 44a), so it is a finding, never a rewrite.
_THING = {"noun.artifact", "noun.animal", "noun.plant", "noun.object",
          "noun.substance", "noun.food", "noun.body", "noun.location"}
_HEAD_SKIP = {"the", "a", "an", "his", "her", "my", "your", "their", "its",
              "our", "new", "best", "wild", "ruined", "morning", "boundary",
              "threshing"}
_thing_cache: dict = {}


def _names_a_thing(name: str) -> str | None:
    """The WordNet file of a physical thing, if the name's head is one."""
    if name in _thing_cache:
        return _thing_cache[name]
    out = None
    from .wn import wordnet
    wn = wordnet()            # None, with one warning, where nltk is absent
    if wn is not None:
        n = re.split(r"\b(?:that|which|who|and)\b",
                     name.lower().split(" of ")[0])[0]
        ws = [w for w in re.findall(r"[a-z]+", n) if w not in _HEAD_SKIP]
        h = ws[-1] if ws else None
        ss = wn.synsets(h, pos="n") if h else []
        verbish = h and wn.morphy(h, "v") == h and \
            len(wn.synsets(h, pos="v")) >= len(ss)
        if ss and not verbish:
            lex = [s.lexname() for s in ss[:3]]
            if lex[0] in _THING and \
                    sum(x in _THING for x in lex) >= min(2, len(lex)):
                out = lex[0]
    _thing_cache[name] = out
    return out


def _safe_expand(corpus, ref):
    from .refs import RefError, parse_ref
    try:
        return corpus.expand(parse_ref(ref))
    except (RefError, Exception):                            # noqa: BLE001
        return []


def main(argv: list[str] | None = None) -> int:
    import sys
    from pathlib import Path

    argv = list(sys.argv[1:] if argv is None else argv)
    verbose = "--verbose" in argv
    rest = [a for a in argv if not a.startswith("--")]

    from .corpus import get_corpus
    if rest:
        from .proposals import _rows
        from .schema import Person, Relation, canonical_fields
        d = Path("ontology/proposals") / rest[0]
        if not d.is_dir():
            d = Path("ontology/staging") / rest[0]
        # A worker may emit a key the record does not declare -- `unnamed`
        # arrived at the top level rather than inside `attrs`, and this
        # crashed on a batch the gate had already accepted. The linter must
        # be at least as tolerant as the gate: it exists to report on output,
        # so refusing to read output is the one thing it cannot do.
        #
        # Unknown keys are folded into `attrs` rather than dropped, because a
        # worker inventing a field is itself worth being able to see.
        import dataclasses

        known = {f.name for f in dataclasses.fields(Person)}

        def _entity(row: dict):
            row = canonical_fields(row)
            extra = {k: v for k, v in row.items() if k not in known}
            kept = {k: v for k, v in row.items() if k in known}
            if extra:
                kept.setdefault("attrs", {}).update(extra)
            return Person(**kept)

        rel_known = {f.name for f in dataclasses.fields(Relation)}
        ents = {e["id"]: _entity(e) for e in _rows(d / "entities.jsonl")}
        rels = [Relation(**{k: v for k, v in canonical_fields(r).items()
                            if k in rel_known})
                for r in _rows(d / "relations.jsonl")]
        where = d.name
    else:
        from .schema import load_entities, load_relations
        ents, rels = load_entities(), load_relations()
        where = "the merged graph"

    found = run(ents, rels, get_corpus())
    print(f"  {where}: {len(ents):,} entities, {len(rels):,} relations\n")
    total = 0
    for rule in sorted(found, key=lambda r: -len(r.found)):
        n = len(rule.found)
        total += n
        share = 100 * n / max(len(ents) if "id" in rule.name or "name" in rule.name
                              or rule.name in ("orphan", "compound-claim",
                                               "speaker-index") else len(rels), 1)
        print(f"  {n:>6}  {rule.name:20} {share:5.1f}%  {rule.why}")
        for f in rule.found[:3 if not verbose else 12]:
            print(f"          {f.subject[:74]}"
                  + (f"   ({f.detail})" if f.detail else ""))
        if n > (3 if not verbose else 12):
            print(f"          … {n - (3 if not verbose else 12)} more")
        print()
    print(f"  {total:,} findings across {len(found)} rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
