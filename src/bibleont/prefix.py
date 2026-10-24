"""The stable half of a worker prompt, built so the provider can cache it.

DeepSeek prices a cached input token about thirty times below an uncached one,
and it caches by *prefix* -- the longest identical head of the request. So the
economics of a batch run are decided by what is put first and whether it stays
byte-identical across calls.

Measured on this graph, for a run over the Psalms:

    concepts, images, beings, covenants, titles     219 nodes    3,356 tokens
    texts and sayings                               376 nodes    7,713 tokens
    persons and places cited anywhere in Psalms       6 nodes       116 tokens
                                                   ---------------------------
                                                    601 nodes   11,187 tokens

At the off-peak flash rate that block costs $0.000078 a call once it is warm,
against roughly $0.00165 of output per verse -- **under five per cent of the
cost of the answer it informs.** Which settles a design question that looked
like a trade-off and is not one: there is no reason to look candidates up per
verse and inject them, because a lookup result lands in the *variable* part of
the prompt where tokens cost thirty times more. Handing the worker the whole
relevant vocabulary up front is cheaper than handing it a shortlist, and it
recalls better.

## Why not the whole graph, then

Cost is not the reason. All 3,016 nodes is about 57,000 tokens, $0.0004 a
call, a quarter of the output cost -- affordable.

**Attention is the reason.** Asking a model to read 1,608 person names before
deciding whether "the LORD is my shepherd" mentions a shepherd is a worse
prompt, not a cheaper one. So the block is scoped by genre, which is the same
routing that decides the extraction mode.

## Ordering

Everything here is emitted most-stable-first: task rules, then the relation
vocabulary, then the entity vocabulary. A book run changes only the last
section, so switching from Psalms to Proverbs still shares the head.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from .paths import ROOT
from .schema import Entity, load_entities, load_vocabulary

# ---------------------------------------------------------------------------
# genre routing -- what mode a book is read in
# ---------------------------------------------------------------------------

NARRATIVE = ('Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr '
             '2Chr Ezra Neh Esth Jonah Matt Mark Luke John Acts').split()
WISDOM = 'Job Ps Prov Eccl Song'.split()
PROPHET = ('Isa Jer Lam Ezek Dan Hos Joel Amos Obad Mic Nah Hab Zeph Hag '
           'Zech Mal').split()
EPISTLE = ('Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus '
           'Phlm Heb Jas 1Pet 2Pet 1John 2John 3John Jude Rev').split()

GENRE: dict[str, str] = {}
for _books, _g in ((NARRATIVE, 'narrative'), (WISDOM, 'wisdom'),
                   (PROPHET, 'prophet'), (EPISTLE, 'epistle')):
    for _b in _books:
        GENRE[_b] = _g

# Which entity types belong in the block, per genre. Narrative runs coarse and
# needs actors and places; wisdom runs on concepts and images and barely
# mentions anyone.
SCOPE = {
    # PERSON AND PLACE BELONG HERE, and their absence was minting duplicates.
    #
    # Wisdom was scoped to the abstract on the reasoning that a psalm is about
    # ideas and barely mentions anyone. Mostly true and wrong where it counts:
    # Psalm 103:7 names Moses, who is already in the graph with eight refs and
    # was invisible to the worker reading that verse -- so a second `moses`
    # gets minted in good faith, which is how this graph acquired duplicates
    # six times before.
    #
    # It costs almost nothing because `named_in` already filters concrete
    # types to what the book's text actually names: 118 people and 65 places
    # across the whole of Psalms, against 1,681 and 746 in the graph. The
    # filter was always there; the type was not in scope for it to apply to.
    'wisdom':    ('concept', 'image', 'being', 'covenant', 'title',
                  'assessment', 'observance', 'text', 'person', 'place'),
    'prophet':   ('concept', 'image', 'being', 'covenant', 'title',
                  'assessment', 'observance', 'text', 'group', 'place'),
    'epistle':   ('concept', 'image', 'being', 'covenant', 'title',
                  'assessment', 'observance', 'text', 'group'),
    # Narrative now runs in concept mode like everything else, so it needs the
    # conceptual vocabulary as well as the actors. Without `concept` and
    # `image` here a worker on Genesis 1 would have no node for light, or the
    # deep, or the image of the firmament, and would mint all of them.
    'narrative': ('person', 'place', 'group', 'being', 'object', 'title',
                  'covenant', 'observance', 'creature', 'concept', 'image',
                  'text', 'assessment'),
}


def revision() -> str:
    """Which build of the worker's instructions produced a batch.

    2026-09-02, on working through the books knowing a second pass is
    coming: keep close track of the revision of the farm for each build so the
    right books can easily be targeted.

    That is the whole requirement. Extraction is now iterative -- the rules
    changed twice in one evening, and Exodus is running on a build that
    Genesis, Job, Mark and Titus were not -- so the corpus will be mixed for a
    long time, and the question "which books need re-running" has to be
    answerable from disk rather than from memory.

    **Hashed from the instructions, not version-numbered by hand.** A number
    someone has to remember to increment is a number that goes stale silently,
    and this project has already been bitten by exactly that: a measured
    claim outlived the thing it measured. The hash
    cannot drift, because it IS the text.

    Only the rules are hashed, not the vocabulary block. The vocabulary grows
    every time a book merges, so hashing it would mark every batch as its own
    revision and the field would carry no information at all.
    """
    import hashlib
    return hashlib.sha256(CONCEPT_RULES.encode("utf-8")).hexdigest()[:12]


def genre_of(book: str) -> str:
    return GENRE.get(book, 'narrative')


def mode_of(book: str) -> str:
    """Which worker reads this book. Since 2026-08-29: the same one, always.

    Narrative used to run coarse -- actors, events and places against a closed
    vocabulary, with concepts only inside direct speech and narrator
    commentary. That existed to stop narrative filling the graph with
    English-keyed concept slop.

    **The lemma layer removed the reason.** A concept pulled out of a narrative
    verse is now anchored to a Hebrew or Greek word from a citable source, so
    it is not slop, and the split was costing more than it saved: two prompts
    to keep correct, every fix landing twice, and the half seeing less traffic
    rotting quietly.

    The reason given: stick with what is being refined.

    `COARSE_RULES` is kept, unused, because the argument for it may come back
    if concept mode over the histories turns out to produce more than anyone
    can read.
    """
    return 'concept'


# ---------------------------------------------------------------------------
# the rules, which are the most stable thing in the prompt
# ---------------------------------------------------------------------------

CONCEPT_RULES = """\
You are decomposing one verse of the King James Bible into a graph.

You are not summarising it and not interpreting it. You are recording what the
verse says, in nodes and edges, so that a reader can find their way back to the
words. Every claim you make is checked against the verse text mechanically, and
a claim quoting words the verse does not contain is discarded.

WHAT A NODE IS

  concept   an idea the corpus names: wisdom, humility, the fear of the LORD
  image     a thing standing for something else: a refuge, a shepherd, oil
  text      a saying worth holding as a unit: "the LORD is my shepherd"
  being     God, the Holy Ghost, an angel
  person    a named human
  place     a named location

A VERSE IS NOT A PARTICIPANT

This is the rule that matters most, and the one most often broken. In the last
full run of Genesis, **2,064 of 6,644 relations broke it** -- roughly a third
of everything produced.

A verse is WHERE something was written down. It is not a thing that acts, and
it is not a thing ideas belong to. So a verse never connects to an idea.

Take Job 1:1 -- "There was a man in the land of Uz, whose name was Job; and
that man was perfect and upright, and one that feared God, and eschewed evil."

  WRONG                                RIGHT
  job_1_1 -speaks_of-> man             job -dwelt_at----> uz
  job_1_1 -speaks_of-> evil            job -described_as-> perfect
  job_1_1 -speaks_of-> perfect         job -described_as-> upright
  job_1_1 -speaks_of-> upright         job -described_as-> the_fear_of_the_lord
  job_1_1 -speaks_of-> the_fear_of_the_lord

Both cite Job 1:1. The left column says which words are in the sentence, which
a search for those words already tells anyone. The right column says what is
true of Job, and connects him to Uz and to nodes that other verses also reach.
The left is a concordance entry. The right is a graph.

Note the one edge that survives translation into the right column unchanged:
`the_fear_of_the_lord` is worth recording because the verse says "one that
feared God" and does NOT contain that phrase. You identified something. The
other four only repeated words already on the page.

**The test, before you write any edge: could someone find this by searching
for the word?** If yes, you have added nothing. Ask instead what the verse
SAYS -- who did what, who is what, who claims what -- and record that.

If a verse states nothing you can put in that form, emit no edge for it. An
empty answer is correct and costs nothing. A tag cloud costs a reader's trust.

SAY "NOTHING HERE". NEVER SAY NOTHING.

An empty answer and a failed one are the same bytes, and nobody downstream can
tell them apart. So when a verse genuinely holds nothing of this kind, **say
that it does**, with a question under the fixed key `nothing-recorded` naming
the verses and one clause of why:

  {"key": "nothing-recorded", "kind": "reading",
   "asks": "Gen 5:12-14 is genealogy only -- nothing recorded",
   "nodes": [], "refs": ["Gen 5:12", "Gen 5:13", "Gen 5:14"]}

Of 1,189 chapters in this corpus, 403 carry a citation. Stated alone that reads
as 66% failure; triaged, 133 are probably real gaps and 103 are probably
genuinely empty. Those are three different numbers telling three different
stories, and only the first is a work list. The cheapest way to have the right
number is for you to say which one this was.

TAGGING IS NOT DECOMPOSING, AND IT IS THE SAME FAULT ONE LEVEL UP

The rule above killed `verse -speaks_of-> idea`. The shape came back wearing a
speech node instead of a verse node, and it is now a quarter of this graph:
**865 verses whose every relation is who spoke and which words the saying
mentions.** Nothing about what was claimed.

  1 Cor 13:4 is "Love is patient, love is kind."

  WRONG                                    RIGHT
  love_is_patient                          love -described_as-> patience
    -speaks_of-> love                      love -described_as-> kindness

The left says the verse is about love, which a search for "love" already
tells anyone. The right says what the verse CLAIMS. Same test as before: could
someone find this by searching for the word?

**`speaks_of` is not forbidden and is often right** -- a saying can be about
something. The fault is when it is ALL a verse produced. If everything you
emit for a verse is `speaks_of`, `asserted_by` and `told`, you have recorded
that a thing was said and not what was said, and the verse is wasted.

BEFORE YOU EMIT ANYTHING: WHY IS THIS NODE STRUCTURE HERE, AND WHAT IS IT
TRYING TO DO?

Doug, 2026-09-02. Ask it of the STRUCTURE you are about to write, never of the
verse -- asking it of the verse invites a summary of the verse, which is how a
tag cloud gets made. Asked of the structure, it forces the thing you emit to
justify its own existence.

    love_is_patient -speaks_of-> love
        what is it trying to do?  Record that the word love is nearby.
        Nothing. Delete it.

    love -described_as-> patience
        what is it trying to do?  Say what love IS, so that every other
        verse making a claim about love meets this one.

If the honest answer is "record that these words occur together", you have
written a concordance entry. If the answer names something the text is doing
-- asserting, ruling, grounding, excepting, conditioning -- write it.

A NODE STRUCTURE DOES WORK. SAY WHAT WORK.

Most verses make one of a small number of moves, and naming the move is what
makes a claim reusable somewhere else in the corpus:

  DESCRIBES    X is Y.  `described_as` (shown "is described as")
               "The LORD is merciful and gracious, slow to anger" (Ps 103:8)
               god -described_as-> merciful ... -described_as-> slow_to_anger
               NOT: this saying speaks_of mercy.
               A DEED the text evaluates is `assessed_as` (shown "did"):
               "Ahab did evil in the sight of the LORD" (1 Kgs 16:30).
               An age, a state or a trait is never a deed: "Abraham was
               seventy-five years old" is described_as, not "did".

  RULES        a decision or verdict, usually following an assessment
               "I will destroy man whom I have created" (Gen 6:7)

  GROUNDS      the reason a claim or ruling is given.  `grounds`
               **Record this even when no connective marks it.** Genesis 6:5
               states the wickedness and 6:7 states the destruction, with no
               "therefore" between them -- and the whole passage is that one
               grounds the other. Paul writes the connective and gets this
               right; narrative and poetry do not, and get it wrong.

  EXCEPTS      the one carved out of a ruling
               "Noah, however, found favor in the eyes of the LORD" (Gen 6:8)

  CONDITIONS   terms on which something holds.  `conditional_on`
               "If I find in Sodom fifty righteous ... I will spare"

  UNFOLDS      a statement and then its expansion. Ps 103:7 says his ways were
               made known to Moses; 103:8-12 is WHAT was made known. Record
               the statement as a claim and the expansion as claims, and use
               `grounds` where the second explains the first.

Measured on Psalm 103 before this rule existed: 95 relations, 41 of them
`speaks_of`, **zero `grounds`**, and eight of twenty-two verses producing
nothing but tagging -- including 103:7, which is the hinge of the psalm.

CASES: FIND THE TRIGGER, COPY THE SHAPE

Each case below starts with a TRIGGER you can check without judgement -- a
word at the front of the verse, a formula, a punctuation mark. When a trigger
fires, emit the shape shown. **Copy the shape. Do not invent a relation type;
every type used below is in the vocabulary and yours must be too.**

CASE 1 -- TRIGGER: the verse opens For / Because / Wherefore / Seeing that
  It is giving the reason for what came just before.

  Ps 103:13  "As a father has compassion on his children, so the LORD has
             compassion on those who fear Him."
  Ps 103:14  "FOR He knows our frame; He is mindful that we are dust."

      ps_103_14_claim -grounds-> ps_103_13_claim     refs: both verses
      god -likened_to-> image_father                 claimed_by: the_psalmist

  The `grounds` edge runs from the REASON to the CLAIM IT SUPPORTS, and both
  ends are claims. Not a concept to a claim. Not a claim to a concept.

CASE 2 -- TRIGGER: the verse opens Therefore / So then
  A consequence of what came before. Same shape, reversed:

      rom_5_1_claim -grounds-> rom_4_25_claim   <- WRONG, backwards
      rom_4_25_claim -grounds-> rom_5_1_claim   <- the earlier grounds the later

CASE 3 -- TRIGGER: the verse opens If / Except, or contains "if ... then"
  Terms. Gen 18:26 "If I find in Sodom fifty righteous ... then I will spare"

      gen_18_26_sparing -conditional_on-> fifty_righteous

CASE 4 -- TRIGGER: "X is Y", "X was Y", a predicate on a named subject
  An assessment, and it is the most under-recorded shape in this graph.

  Ps 103:8  "The LORD is merciful and gracious, slow to anger"

      god -described_as-> merciful           claimed_by: the_psalmist
      god -described_as-> gracious           claimed_by: the_psalmist
      god -described_as-> slow_to_anger      claimed_by: the_psalmist

  THREE edges, one per predicate. Not one edge to a fused
  `merciful_and_gracious`, which no other verse can ever meet.

CASE 5 -- TRIGGER: said / saith / spake / answered
  Record the speech act AND decompose what was said, with `claimed_by`.

  Job 1:21  "the LORD gave, and the LORD hath taken away"

      job -told-> job_1_21_speech
      god -gave-> jobs_possessions          claimed_by: job
      god -took-> jobs_possessions          claimed_by: job

  The speech node alone is unfinished work.

CASE 6 -- TRIGGER: a question mark
  A question is NOT a claim. Paul asks "That God is unjust to inflict His
  wrath on us?" (Rom 3:5) and answers "Certainly not!" (3:6). Recording the question
  as a claim makes the graph assert the opposite of the argument.

      DO NOT emit: god -described_as-> unrighteous
      Emit the question as a node if it is answered, and the ANSWER as the
      claim.

CASE 7 -- TRIGGER: "God forbid" / "Nay"
  The proposition just raised is being DENIED. Whatever precedes it is not
  the author's position. If you recorded it as a claim, you have inverted the
  text.

CASE 8 -- NO TRIGGER, and this one needs judgement. Say so.
  Gen 6:5 states the wickedness; Gen 6:7 states the destruction; nothing joins
  them and the whole passage is that one grounds the other.

      man -described_as-> wicked
      gen_6_7_ruling -grounds-> gen_6_5_assessment    certainty: implied

  Mark it `implied`, not `explicit`. A join you made is not a join the text
  made.

AN EVENT IS A NODE

Some things that happen are worth a node of their own, because later text
points back at them. The type exists and was never used once in 8,475 records,
because nothing here told you it was available.

  death_of_abel         [event]   Gen 4:8
  the_flood             [event]   Gen 7:17-24
  the_binding_of_isaac  [event]   Gen 22:1-19

Make one when EITHER is true:

  the event has one participant and so cannot be an edge
      "and he died" (Gen 5:5) is a fact about Adam and about nothing else.
      As an edge it has no second end; as a node it can be dated, placed,
      and counted with the seven others in that chapter.

  the event is referred to later
      "the blood of Abel" (Heb 12:24) needs something to point AT. A
      relation between Cain and Abel is not a thing a later writer can cite.

Do NOT make one for every action. `cain -killed-> abel` is already a
complete record of who did what; the event node earns its place only when the
text treats the happening itself as a subject. If nothing points at it and it
has two participants, the edge is enough.

Cite it like anything else, and let existing relations reach it:

  death_of_abel -instance_of-> pattern_and_he_died
  death_of_abel -part_of-> the_story_of_cain_and_abel

WHO SAYS IT: asserted_by

The corpus reports many things it does not endorse, and a graph that cannot
tell the difference asserts them all in its own voice.

Job's three friends argue for thirty-five chapters that his children died for
their sin. The book overturns them: "ye have not spoken of me the thing that
is right" (Job 42:7). If Bildad's claims are recorded as plain edges, the
graph asserts the theology the book exists to refute.

  WRONG                                  RIGHT
  job -sinned-> ...                      job_8_4_claim -asserted_by-> bildad
  (the graph now says Job sinned)        (the graph says Bildad said it)

So: when the text puts words in a speaker's mouth, the claim is a node and
`asserted_by` names the speaker. When the narrator states it, no speaker is
named and the claim stands as the scroll's.

The same rule holds Sarah's denial (Gen 18:15) and the census, where 2Sam 24:1
says the LORD moved David and 1Chr 21:1 says Satan provoked him. Two scrolls,
two claims, and the graph asserts neither.

WHO CAUSED IT: incited

When the text says one party moved another to act, that is a relation and not
a flourish. It was missing entirely, and the two most argued-over verses in
the historical books both turn on it:

  2Sam 24:1  the LORD ... moved David ... to say, Go, number Israel
  1Chr 21:1  Satan ... provoked David to number Israel

  god       -incited-> david        cited 2Sam 24:1
  the_devil -incited-> david        cited 1Chr 21:1

The King James says "moved" in one and "provoked" in the other, and the Hebrew
is the same verb in the same form both times. Use `incited` for both. Record
what the person then does as its own edge -- the incitement and the act are
two relations, not one.

WHAT WAS SAID, NOT ONLY THAT IT WAS SAID

**A speech node with nothing but `asserted_by` is unfinished work.** Naming the
speaker and stopping records that a person opened their mouth. The content is
the reason the verse is in the Bible.

Measured before this rule existed: of 33 speech nodes across Genesis 1-4, all
33 had `asserted_by` and two had anything else. Job 3 -- twenty-six verses of
Job cursing the day of his birth -- produced "Job spoke verse 3, then verse 4,
then verse 5", and not one thing he said.

WRONG                                RIGHT
job_1_21 -asserted_by-> job          job_1_21 -asserted_by-> job
(and nothing else)                   god -gave-> jobs_possessions
                                       claimed_by: job
                                     god -took-> jobs_possessions
                                       claimed_by: job

Job 1:21 is "the LORD gave, and the LORD hath taken away". Both verbs exist in
your vocabulary. Use them.

A QUOTATION SITS INSIDE THE NARRATIVE, AND THAT IS LOAD-BEARING

Every quotation is reported by a narrator, so a verse with speech in it holds
TWO facts and they are of different kinds:

  job -told-> job_1_21_speech          the narrator's fact. Asserted flatly.
  god -gave-> jobs_possessions         Job's claim. Asserted by nobody.
    claimed_by: job

**The scroll vouches for the fact of the saying, never for its content.** Emit
both. Dropping the first loses who reported it; dropping the second loses what
was said.

The containment is not bookkeeping. Job 1:21 means what it means BECAUSE it
comes after the losses, and Job 9:22 -- "he destroyeth the perfect and the
wicked" -- means what it means because the friends have spoken by then. The
same man says both. Keep every claim tied to the verse it was made at, and
never merge two claims by one speaker because they look alike: Job changes his
mind across the book, and that change is the book.

USE `claimed_by` FOR EVERY WORD INSIDE A QUOTATION

Extract the content of a speech exactly as you would narration -- the same
relations, the same care -- and add `claimed_by` naming the speaker. The graph
then holds what was said WITHOUT asserting it.

This is not a formality. Job's friends argue for thirty-five chapters that his
children died for their sin, and the book overturns them: "ye have not spoken
of me the thing that is right" (Job 42:7). Their claims must be recordable as
THEIRS. A plain edge would make the graph assert the theology the book exists
to refute.

  bildad -asserted_by...        job_8_4_claim -asserted_by-> bildad
                                jobs_children -sinned_against-> god
                                  claimed_by: bildad

Leave `claimed_by` empty when the NARRATOR states a FACT. "Job had seven sons
and three daughters" is the scroll reporting, and it is recorded flatly.

AN ASSESSMENT ALWAYS HAS SOMEONE MAKING IT

`assessed_as` and `described_as` are judgements, and a judgement is always somebody's. Three cases,
and collapsing them into an empty field loses the difference between "nobody
assessed this" and "the scroll assessed this":

  the text NAMES the assessor     use that name, even in narration
  a character assesses in speech  use the speaker
  the narrator assesses           use `narrator`

The first case is the one most easily missed, because it looks like plain
narration and is not. "Ahab did evil IN THE SIGHT OF THE LORD" does not lack an
assessor -- it names one. The narrator is reporting God's judgement, and "in
the sight of" / "in the eyes of" / "before the LORD" says whose it is.

  ahab -assessed_as-> evil                     claimed_by: god
  job -assessed_as-> sinned_not                claimed_by: narrator

"In all this Job sinned not" (Job 1:22) is the scroll's own verdict on the
chapter, not a neutral report, and recording it as the narrator's is what makes
it comparable with the friends' opposite verdict later.

Watch the nesting. Job 15:15 -- "the heavens are not clean in his sight" -- has
the formula, but ELIPHAZ is speaking, so `claimed_by` is eliphaz. The formula
names whose sight it is; the claim still belongs to whoever made it.

POETRY IS NOT A DIFFERENT JOB

A chapter with no story in it still has claims in it, and they are extracted
the same way. Job 3 is a lament, and it asserts a great deal:

  job -cursed-> the_day_of_his_birth        Job 3:1, and this is NARRATION
  job_3_3_wish -asserted_by-> job           "let the day perish"
  job_3_11_question -asserted_by-> job      "why died I not from the womb"

Note the first. Job 3:1 -- "After this opened Job his mouth, and cursed his
day" -- is the narrator, not Job, and `cursed` is in your vocabulary. It was
extracted as a tag on the verse, because the chapter around it is poetry and
the whole window drifted into tagging.

**Do not let the character of a chapter change how you read a verse in it.**

WHY A CLAIM IS MADE: grounds

Where the text gives a reason for a claim, record it. Gen 18:17-19:

  "Shall I hide from Abraham what I am about to do?"        <- the claim
  "For I have chosen him, so that he will command..."       <- the ground

  gen_18_19_election -grounds-> gen_18_17_disclosure

That is the only place in the Torah where God states a reason for choosing
Abraham, and as five `speaks_of` tags it disappears entirely. `grounds` is for
argument -- not `draws_on`, which is allusion, and not `part_of`, which is
containment.

TERMS: conditional_on

"If I find in Sodom fifty righteous within the city, then I will spare all the
place for their sakes" (Gen 18:26), and five more times down to ten.

  gen_18_26_sparing -conditional_on-> fifty_righteous

A bargain with no terms is not a bargain. The same form runs through the
blessings and curses of Deuteronomy and through most prophetic warning, which
is conditional by construction.

HOW TO NAME A NODE

Four kinds, and the id convention differs because the kinds differ.

  word      a single idea the corpus names: wisdom, instruction, refuge
            id = the word.            wisdom, instruction, image_refuge

  phrase    a settled multi-word name: "the fear of the LORD", "the Son of man"
            id = the phrase, underscored, WITHOUT leading articles
            the_fear_of_the_lord, the_son_of_man
            Then say what words it is built from with composed_of.

  passage   a saying or a verse held as a unit
            id = THE REFERENCE.       prov_1_20, ps_23_5, prov_10_1_12
            name = a short modern-English label a reader would recognise:
            "Wisdom crying in the streets", "You anoint my head with oil"

  observed  a pattern you noticed rather than a phrase the text uses.
            Rare. Raise a question before minting one.

**A SENTENCE IS NOT AN IDENTIFIER.** Do not write ids like
`he_guides_me_in_the_paths_of_righteousness_for_the_sake_of_his_name`. That was
produced in the same batch as `prov_1_20`, which is correct, and the two
conventions in one batch is the thing this rule exists to stop. The reference
is stable and short; the label carries the words and can be rewritten later
without breaking a single relation.

CONCEPT OR IMAGE, AND WHICH RELATION GOES WITH WHICH

A **concept** is an idea named directly: wisdom, instruction, justice, equity.
An **image** is a thing from the world standing for something else: a way, a
path, a net, a whirlwind, a grave, a pit, fruit, a shepherd.

If you could photograph it and the verse does not mean the photograph, it is
an image. "Let us swallow them up alive as the grave" (Prov 1:12) is a grave
standing for destruction -- `image`, not `concept`.

**A THIRD ANSWER: IT IS JUST THE THING ITSELF.**

Not every noun is an idea or a figure. Job 9:9 says God "maketh Arcturus,
Orion, and Pleiades" -- those are *stars*, meant literally, and typing them
`concept` says Genesis-style creation acted on an abstraction. Each of these
was typed `concept` and each is wrong:

    Orion, Pleiades, Arcturus     object      real stars, made by God
    clay, stones                  object      substances handled and shaped
    the grave                     place       where Job asks to be hidden
    the wild ass                  creature    an animal, in a real desert

**A plural is not more abstract than a singular.** "Oxen", "flocks", "herds",
"camels", "menservants", "garments", "corn" are as concrete as one ox. Genesis
counts a man's wealth in them, and every one of these was typed `concept`:

    oxen, flocks, herds, camels     creature    livestock, counted and driven
    menservants, womenservants      group       people, bought and given
    garments, savoury meat, corn    object      worn, cooked, bought
    Shebah                          place       the well Isaac's servants dug

If you can put a number in front of it, it is not an idea.

Ask which of three things it is, not which of two:

    is it an idea?                       -> concept   (wisdom, justice)
    is it a thing standing for another?  -> image     (a net, a shepherd)
    is it simply the thing?              -> object, place, creature, person

`Sheol` is an image in "let us swallow them alive like Sheol" (Prov 1:12) and
a place in "hide me in Sheol" (Job 14:13). **The same word takes its type from the verse, every
time.** If the verse means the thing, it is the thing.

The relation follows the type, and the vocabulary enforces it:

    text --speaks_of--> anything        what the saying is about
    text --draws_on--> image            a figure the saying is built from

`draws_on` a concept is refused: a saying is built out of figures, not out of
ideas. `speaks_of` will take any kind of subject -- so it is never the reason
to call a star an idea.

TWO IMAGES POINTING AT ONE THING ARE NOT RELATED TO EACH OTHER

Symbols converge on purpose -- that is what a symbol is for -- and a rich
corpus points many images at one referent. Convergence is evidence about the
referent and about nothing else.

    the seed signifies the word of God      Luke 8:11, the sower
    the sword signifies the word of God     Eph 6:17, the armour
    THEREFORE the seed relates to the sword          <- NO. No passage says so.

**A signifies C and B signifies C says nothing whatever about A and B.** Never
emit an edge between two images because they share a referent. Point each at
the referent and stop; a reader following both arrives at the same place, which
is the true finding.

WHERE THE LITERAL AND THE FIGURATIVE READING ARE BOTH LIVE, RECORD BOTH

Often the text settles it. It marks the figure ("is like unto", "which things
are an allegory"), or the types make it plain, since a person is not literally
a door.

**But a large class is genuinely contested**, and centuries of careful readers
have differed on exactly which passages those are. "This is my body" (Mark
14:22) is the obvious one: whole traditions read it differently, each with
reasons, and the disagreement is about the text rather than about anyone's
competence.

    MARKED      the text says it is a figure          record it as a figure
    TYPED       the reading is impossible literally   record it as a figure
    CONTESTED   competent readers differ              record BOTH, and say so

**The failure is not literalism or figurativism. It is having a default.**
Resolving toward the literal asserts what the text may not claim; resolving
toward the figurative explains away what it may mean plainly. Both are a
machine settling a question the source leaves open, and both are invisible
afterwards because the output looks equally confident either way.

WHEN A WRITER SETS A WORD AGAINST ITS OWN NEGATION, SAY SO

Nothing else in this system can see it, so if you pass it by it is lost.

    Titus 3:8   "These things are good and PROFITABLE unto men."
    Titus 3:9   "...for they are UNPROFITABLE and vain."

Every measure here works on shared vocabulary, and the Greek is G5624 against
G0512 -- the same root with an alpha-privative, which makes a different word.
Those two verses score **0.000** against each other. The corollary is worth
holding: **the more deliberately the opposition is built, the lower it scores**,
because every term has been swapped for its opposite. Perfect antithesis is
invisible.

So where a passage sets a thing against its negation, emit `contrary_to`
between the two nodes and quote both verses. This is how Hebrew poetry is built
and how Paul's arguments turn, so it is not a rare case.

A phrase of several words can be one concept. "The fear of the LORD" is a
settled phrase and is a node; so is "the beginning of wisdom". Do not break a
settled phrase into its words and stop -- record the phrase AS a node, then say
what words it is built from.

COMPOSITION IS LEXICAL, NOT SEMANTIC

  composed_of   this phrase is built from this term. Nothing more.

"The fear of the LORD" is composed_of "fear" and composed_of "the LORD". That
is a fact about the words. It is NOT a claim that the fear of the LORD is a
kind of fear -- the corpus calls it clean, a treasure, and a fountain of life,
and calls none of those things of being afraid. Never emit a semantic edge
(is_a, likened_to, contrary_to) to justify a composition. If you believe there
is a semantic relation, raise it as a question instead.

A ROLE IS NOT A PERSON. AN UNNAMED PERSON STILL IS ONE.

Two different things look alike here, and getting them the same way round is
worth more than any other typing decision you will make.

**A role** is a KIND of person, true of anybody who fits: "my son", "thy
father", "sinners", "the wicked", "a friend". Proverbs is built out of these
and almost none is anybody in particular. Type them `concept`.

**An unnamed person** is one particular human the story is following, who
happens to be identified by office or relation rather than by name: the chief
butler, the chief baker, the steward of Joseph's house, Potiphar's wife, Lot's
wife. Type them `person` and set `"unnamed": true`.

**A body of people** -- more than one, acting or spoken of together -- is a
`group`, and that includes humankind itself and its divisions.

The test is not whether a name is given. It is whether the text is following
ONE OF THEM.

    the chief butler   dreams, is restored, forgets Joseph, remembers him two
                       years later -- one man, across four chapters   person
    a friend           whoever the proverb is about                   concept
    Joseph's brethren  ten men who go down to Egypt together          group
    man                "So God created man in his own image" -- the
                       humankind he created, not the idea of humanity  group
    male and female    "male and female created he them"               group

`man` typed as a concept made Genesis 1:27 unrecordable: God cannot be said to
have *made* an abstraction. **When the verse says something was created, what
was created is a thing or a people, never an idea.**

Getting this wrong is expensive in a way that is easy to miss: a `concept`
cannot be imprisoned, cannot speak and cannot be present with anyone, so
**every true thing the chapter says about him is refused**, and the refusals
land on the relations rather than on the node that caused them.

Then, for genuine roles: **do not use person relations on them.**
`father_of`, `told`, `warned`, `killed` and the rest require a human at
the end the vocabulary says so. A concept cannot father anyone.

Say what the verse says instead, with the saying as the subject:

  WRONG   father --father_of--> my_son
          father --warned--> my_son
  RIGHT   my_son_hear_the_instruction_of_thy_father --speaks_of--> father
          my_son_hear_the_instruction_of_thy_father --speaks_of--> instruction

If a verse genuinely has a named person doing something -- Solomon, David,
Agur, Lemuel -- then the person relations apply and the id is in the vocabulary
below.

"SON OF" DOES NOT ALWAYS MEAN SON

Hebrew usage lets a man be called the son of any ancestor, and the corpus does
it constantly. Genesis calls Laban "the son of Nahor" (Gen 29:5) and also "son
of Bethuel" (Gen 28:5) -- Bethuel is his father, Nahor his grandfather, and
both verses are correct.

Recorded as two `father_of` edges it becomes a claim that Laban had two
fathers, which is the graph's most reliable signal that one id is standing for
two different people. A true idiom is turned into a false conflation.

  **`father_of`**    only where the text means the immediate generation
  **`ancestor_of`**  where a generation may be skipped -- true on either
                     reading, so it is the safe form when you are not sure

If the same person is already given a different father anywhere you can see,
that is the case this rule is about: use `ancestor_of` for the longer-range
one, and say in the note which verse gives which.

POINTING AT PART OF A SET SAYS THE PART IS SPECIAL

Choosing a narrow target rather than a general one is itself a claim. "X led
these two tribes" tells a reader that those two are distinctive -- otherwise
why name them rather than the nation? -- and if X led all twelve, the narrow
edge is false in a way the verb alone never reveals. That happened here, and
correcting the relation type was the visible half of the fix; the invisible
half was that a correctly-typed edge at the wrong altitude still misleads.

**Before scoping a relation to part of a set, ask whether it holds of the
whole set.** If it does, the general edge is the true one. If it genuinely
holds of only that part, say why in the note, because a reader who is not told
will supply their own reason.

A LETTER IS ONE ACT, NOT ONE ACT PER PARAGRAPH

Some passages REPORT something that happened. Others ARE the thing happening,
addressed to whoever is reading. They look identical to a search and only the
first is an event this graph can hold.

  "When Cephas came to Antioch, however, I opposed him to his face" (Gal 2:11)
      two named parties, a place, a time -- a rebuke that happened. Record it.

  1 Corinthians 5, a chapter condemning a man in Corinth
      also a rebuke, explicit and sustained -- but with an author, an audience
      and no reported outcome. There is nothing to say about whether it landed.

So: **extract the participants, not the audience.** The man in Corinth is a
record, tied to the congregation he belonged to. The congregation does not
acquire an edge for having been written to about him -- do that and every
addressee becomes a hub by volume of correspondence.

And do not turn each imperative into its own speech-act from writer to
recipient. That multiplies edges without adding facts and buries the handful of
narrated encounters that are real. Record what the letter CLAIMS, with
`claimed_by` naming the writer, exactly as you would for any other speech.

THE KJV IS THE TEXT. THE OTHERS ARE A CHECK.

Node names and ids follow the King James wording, always. The other four
translations are shown so that you can *notice* a divergence, not so that you
have to choose between them.

  Prov 1:27  KJV "whirlwind", others "storm", "hurricane"  -> image_whirlwind
  Prov 1:31  KJV "devices", YLT "counsels", WEB "schemes"  -> devices
  Prov 1:32  KJV "turning away", ASV "backsliding"         -> turning_away

Do not raise a question merely because the translations differ; they differ
constantly and the KJV settles it. Say what you noticed in the relation's
`note` instead, where it is evidence a reader can weigh.

**One exception worth a question**: where the divergence is not a synonym but a
different concept, and the graph holds both. Ps 34:8 is "trusteth in him" in
the KJV and "taketh refuge in him" in three others; `trust` and `refuge` are
both nodes and they are not the same idea. That is a real question. "Storm" for
"whirlwind" is not.

PERSONIFICATION IS NOT A BEING

Wisdom crying in the streets (Prov 1:20-33), speaking in the first person and
promising to pour out her spirit, is a figure of speech that the corpus
sustains for a chapter. Whether she is more than that is a live question --
it runs to John 1 and it is not yours to settle.

So: do not give a personified abstraction the `being` type, which would let it
take `told`, `quoted` and the rest. Record the speech as text nodes, have them
`speaks_of` the concept, and raise a question. Keep a personified node separate
from the plain concept and from any existing image; a later merge is cheap and
a wrong merge is not.

LOOK FOR THE RECORD BEFORE MINTING ONE, AND LOOK BY NAME

You have no memory of the window you did an hour ago, so you will re-mint
things far more often than a person would. **The check is not on the id. It is
on the name and its variants.** Five ids were created in one session for things
the graph already held:

    works_of_the_flesh   against   the_works_of_the_flesh
    beth_lehem           against   bethlehem
    children_of_israel   against   israel_people

Not one of those was an id collision -- an id lookup finds none of them, and
reading the names in the vocabulary below finds all of them. A duplicate passes
every mechanical check and quietly halves the connectivity of what it copies,
because half the edges point at one and half at the other.

**A name that is a ROLE is a strong prior that the record already exists.** The
multitude, the disciples, the scribes, the chief priests, the elders -- these
persist across the whole book while individuals come and go, and no verse ever
says "the same crowd as last chapter". Every per-window copy looks like new
content while you are writing it. Search the vocabulary for the role before
minting one.

A proper name is a *weak* prior, and that is the opposite of the intuition:
the corpus reuses personal names freely, so finding `simon` in the vocabulary
is not evidence that this Simon is that one.

EVERY ID YOU USE MUST EXIST

A relation may only name an id that is **either** in the vocabulary below
**or** in your own `entities` list in this same reply. There is no third
option. An id that is in neither is a dangling reference: the gate refuses the
relation, and the work of finding it is thrown away.

If a verse is about `understanding` and no such node is listed below, that is
not a reason to skip it and not a reason to point at it and hope. **Create the
entity, then use it.** One Proverbs batch emitted thirty-one relations naming
concepts it never declared -- understanding, mouth, life, reproof -- and every
one was discarded, having cost exactly as much to produce as a good one.

Before you finish, read your own relations and check that each `src` and `dst`
appears either above or in your entities list.

THE SAME WORDS ARE NOT THE SAME EVENT

In poetry and teaching, a repeated phrase is usually one thing. "The fear of
the LORD" in Prov 9:10 and in Ps 111:10 is one concept and one node.

**In narrative it is usually not.** When Kings says Manasseh "did evil in the
sight of the LORD" and says it again of Amon, those are two reigns, two
verdicts, two events that happen to be described in identical words. One node
would merge two kings into one fact and lose which of them the text was
judging.

So in narrative: **same wording, separate nodes**, and connect them with a
pattern if the form recurs.

The exception is a genuine reference back. When a later passage points at an
earlier event -- "the God of Abraham, Isaac and Jacob", "as he sware unto thy
fathers", Hebrews recalling the wilderness -- the later text is talking about
the earlier event and should reach the existing node rather than mint a new
one. The test is whether the passage is **reporting** the event again or
**referring** to it: a report is its own occurrence, a reference is a pointer.

If you cannot tell which, raise a question. Getting this wrong in the merging
direction cannot be undone.

WHEN SEVERAL VERSES SHARE A SHAPE

Sometimes a passage repeats a form. "Blessed are the X: for they shall Y", nine
times. "And God saw that it was good", six times. Those verses are NOT one node
-- they say different things -- and they are not unrelated either.

  pattern       a shape several passages share
  instance_of   this passage is one instance of it

Make a pattern node only when **you can see at least two instances in the
verses in front of you**, and name it for the shape rather than for any one
verse: `blessed_are_the_x_for_they_shall_y`, not `blessed_are_the_meek`.

Two limits that matter:

**A pattern is ours, not the text's.** It records that we grouped these. It is
not a claim that the writer intended a form. If the corpus itself marks the
series -- an acrostic, a numbered oracle, a refrain the text calls a refrain --
say so in the note, because then the shape is the text's and worth more.

**Group by form, not by meaning.** Two verses sharing a shape may be about
entirely different things. Saying they rhyme is not saying they agree.

WHEN TWO THINGS MIGHT BE THE SAME

Do not decide. Split, and raise a question.

If "wisdom" in "the beginning of wisdom" reads as a quality, and "wisdom" in
"wisdom's instruction" reads as someone who acts, those are two nodes and one
question. Splitting wrongly is repaired by a later merge; merging wrongly
destroys the distinction and cannot be recovered. Always split.

Give every question a `key`: a short stable slug naming the QUESTION, not this
verse. The same question from forty verses must produce the same key forty
times, so a person answers it once. Use the key `wisdom-actor-vs-quality`, not
`ps-23-wisdom`.

WHEN NO RELATION TYPE FITS

Use the closest one in the vocabulary and raise a question with the wording you
wanted. Never invent a relation type. The vocabulary is the trunk and only a
person may extend it.

WHERE THE TEXT HAS NO NARRATOR, SOMEONE IS STILL SPEAKING

A psalm is one person addressing God or the reader. Nothing in it says "and
David said", because the whole thing is the saying. **The absence of a speech
marker is not the absence of a speaker.**

    WRONG   god -described_as-> refuge              ['Ps 46:1']
    RIGHT   ps_46_1_claim -asserted_by-> the_psalmist
            ps_46_1_claim -speaks_of-> refuge      ['Ps 46:1']

Get this wrong and the psalmist's words become the graph's own assertions.
Measured before this rule existed: Job carried 838 attributed speech nodes
because its speeches are marked, and the Psalms carried 3 attributions across
83 relations because they are not.

**The same rule for praise and for lament, and this is the part to hold on
to.** "The LORD is my shepherd" (Ps 23:1) and "Thou hast laid me in the lowest
pit" (Ps 88:6) are the same kind of sentence. Attributing the second and not
the first would record a preference rather than the text.

A lament that never resolves stays unresolved. Psalm 88 ends "lover and friend
hast thou put far from me, and mine acquaintance into darkness" and stops.
Supplying hope the psalm withholds is editing it.

Where a superscription names the speaker, use that name. Where it does not,
`the_psalmist` is the speaker and the node says so rather than leaving it
open.

**This reaches past the Psalms.** Ecclesiastes is the Preacher's, through the
despair and the conclusion alike. The Song is its two voices. Lamentations has
a speaker. Any book that is somebody talking, without a narrator to say so,
gets the same treatment.

A FORM TAKEN AND LATER SET ASIDE: assumed_form_of

Where the text narrates someone TAKING a form rather than simply appearing,
the form is its own node and points at the one who took it.

    WRONG   jesus -described_as-> in_the_form_of_a_servant
    RIGHT   jesus_incarnate -assumed_form_of-> jesus     ['Phil 2:7']

The subject is the FORM and the object is the one who assumed it. Never the
other way round: the arrow runs from the temporary to the permanent, because
the form is set aside afterwards.

Use it only where the taking is narrated. "The LORD appeared to Abraham...
and saw three men standing nearby" (Gen 18:1-2) narrates it. "The angel of the
LORD appeared in a flame" (Exod 3:2) does not quite -- the text moves between
the angel and God without equating them, so that is `conjectured` and the note
must say why.

If a passage merely compares one thing to another -- "made like unto the Son of
God" (Heb 7:3) -- that is `likened_to`, not this. The writer chose a word that
stops short of identifying them and so must you.

A VERSE IS NOT A NODE. A SPEECH IS, AND IT NEEDS A LABEL NOT A QUOTE

Two different mistakes, and only the first is fatal.

**1. Never mint a node whose id is a bare verse address.**

    WRONG   2cor_4_1        name: "we faint not"
    WRONG   deut_6_10       name: "When the Lord thy God shall have brought..."

That is a fragment of a verse promoted to a thing. Every relation touching it
records where words are rather than what happened, and the verse address is
already carried by `refs` on every relation -- so the node adds nothing that
was not already there and costs the graph a participant that does not exist.
**Verse locations are derived from citations. They are never entities.**

If the verse says something worth recording, record the CLAIM between the
parties it names, and cite the verse.

**2. A speech act IS a node, because `asserted_by` must point at something.**
Key it to where it occurs, and then NAME IT LIKE A THING, not by quoting it.

    WRONG   gen_11_3_speech         name: "Come, let us make bricks and bake
                                           them thoroughly. So they used brick
                                           instead of stone"
    RIGHT   gen_11_3_speech         name: "the builders' proposal"
                                    desc: "Come, let us make bricks..."

The name is what a reader sees in a list, a diagram and a search result, so a
name that runs to two hundred characters is unreadable everywhere it appears.
The quotation belongs in `desc`, where nothing is lost.

You already do this about half the time, and the good half shows the pattern:
`gen_20_3_god_speech` is named *God's warning to Abimelech*;
`gen_38_11_judah_speech` is *Judah's word to Tamar*. Do that every time.

A good speech name says WHO and WHAT KIND -- a warning, a refusal, an oath, a
complaint, a promise -- in under about forty characters.

WHEN THE SUBJECT IS A PRONOUN, CITE THE VERSE THAT NAMES HIM TOO

A relation is refused if the verses it cites do not NAME both parties. That
rule stops invented citations and it is not going away, so a narrative that
runs on pronouns has to be cited with it in mind.

Mark's first pass lost six correct relations to this, every one of them the
same shape:

    Mark 1:30   "they tell him of her"           -- neither Jesus nor Simon
    Mark 1:35   "he went out ... and there prayed"  -- nobody named at all
    Mark 2:3    "a paralytic was brought to Him, carried by four men"

The relations were right. Jesus did heal Simon's mother-in-law; he did go out
and pray. The citations named nobody, so the gate refused all three.

    WRONG   jesus -healed-> peters_wife_mother        ["Mark 1:31"]
    RIGHT   jesus -healed-> simons_wifes_mother       ["Mark 1:29", "Mark 1:31"]

Mark 1:29 names Jesus, Simon and the house; 1:31 is where the healing happens.
Cite BOTH -- the verse that names the participant and the verse where the act
occurs.

This is the same convention already used for speech, where the attribution
verse and the content verse are both cited. Extend it to any act whose subject
is carried by a pronoun from an earlier verse, which in narrative is most of
them.

Note the second fault in that example too: the verse says **Simon**, not
Peter. Name the person the way THIS passage names him.

QUOTE FROM THE KING JAMES, FROM THIS VERSE, UNBROKEN

Three ways this goes wrong, all three found in one book:

**1. Quoting a different translation.** The other renderings are shown so you
can NOTICE where they differ. They are never the thing you quote.

  Job 33:16  KJV  "sealeth their instruction"
             BSB  "terrifies them with warnings"   <- quoted, and refused
  Job 39:19  KJV  "clothed his neck with thunder"
             BSB  "adorn his neck with a mane"     <- quoted, and refused

**2. Tidying the words on the way out.** This is the commonest of the three and
the hardest to notice, because the result is always *true* -- it says what the
verse says. It is simply not what the verse says it with. Every one of these
was refused:

    verse                                        quoted                        edit
    "The fountains ALSO of the deep"             "the fountains of the deep"   dropped a word
    "there shall be twenty FOUND there"          "twenty BE found there"       added a word
    "they called Rebekah, AND said unto her"     "And they said unto her"      dropped the middle
    "the nakedness of the land YE ARE COME"      "Ye are come to see the..."   reordered
    "maketh Arcturus, Orion, and Pleiades"       "maketh Orion"                skipped a word

**A quotation is a copy, not a rendering.** The words between your quotation
marks must appear in the verse in that order, with nothing removed from the
middle and nothing put in. If the phrasing is awkward, quote a shorter run of
it, or use `...` between two runs you have each copied exactly -- but do not
smooth it.

**3. Quoting a verse other than the one the relation cites.** "they that know
him not" is in Job 24:1. It was quoted on ten relations citing 24:2 through
24:11, none of which contains it. **A note must quote the verse THIS relation
cites** -- if the evidence is in a neighbouring verse, cite that verse too, or
write the note without quotation marks.

  **Most often it is off by exactly one.** The speech formula sits in the verse
  before the speech, and the quotation is taken from where the eye is rather
  than from where the relation points:

    Gen 11:6  "And the LORD said"          <- the formula lives HERE
    Gen 11:7  "Go to, let us go down"      <- quoted "And the Lord said", refused

    Job 9:4   "He is wise in heart"        <- quoted on a relation citing 9:5
    Job 9:35  "Then would I speak"         <- quoted on a relation citing 9:34

  Before you write a quotation, read the number on the relation and find the
  words in THAT line. One verse either side is not close enough.

QUOTATION MARKS MEAN THE EXACT WORDS

Inside quotation marks, copy the King James **letter for letter**. Do not
modernise, do not shorten, do not smooth.

  Prov 10:27 says "prolongeth days".
  WRONG   "prolongs life"        modernised, and both words changed
  RIGHT   "prolongeth days"

This is checked mechanically against the verse and a note that fails is
discarded whatever else is right about it. It is also the single most damaging
thing you can produce: this graph's whole claim is that a reader can check any
citation against the book in front of them, and a quotation that is not in the
book breaks that for every other record too.

If you want to say it in your own words, say it **without** quotation marks.

A NODE MUST COME FROM THE VERSE'S WORDS, NOT YOUR PARAPHRASE

Prov 10:9 is "He that walketh uprightly walketh surely: but he that perverteth
his ways shall be known." A relation between `uprightness` and `perversity`
citing that verse fails, because neither noun is in it -- they are your
summary of two participles. Name what the verse says.

SYMMETRIC RELATIONS ARE STORED ONE WAY ROUND

`contrary_to` and the other symmetric types carry no direction, so they are
stored once, with the **alphabetically smaller id as `src`**. Emit
`foolish_son -contrary_to-> wise_son`, never the reverse; the pair
`righteousness` / `treasures_of_wickedness` likewise.

CERTAINTY

  explicit    the verse states it in words
  implied     the verse entails it but does not say it
  conjectured you are reading it in

Default to explicit only when you can quote the words. If the join is yours
rather than the text's, say implied, and say so in the note.

OUTPUT

Strict JSON, no prose around it:

{
  "entities": [
    {"id": "...", "name": "...",
     "type": "concept|image|text|pattern|being|person|place|group",
     "aka": [], "refs": ["Ps 23:1"], "existing": false,
     "lemma": ["H7462"],
     "desc": "one or two sentences, quoting the verse"}
  ],
  "relations": [
    {"src": "...", "type": "...", "dst": "...", "certainty": "explicit",
     "refs": ["Ps 23:1"], "note": "quote the words that support this"}
  ],
  "questions": [
    {"key": "stable-slug", "kind": "merge|vocabulary|reading",
     "asks": "the question in one sentence",
     "nodes": ["id_a", "id_b"], "refs": ["Ps 23:1"]}
  ]
}

Set "existing": true and reuse the id verbatim when the node is already in the
vocabulary below. Do not restate its name, aka or desc -- id alone is enough.
Mint a new id only when nothing in the vocabulary is the same thing.

THE ORIGINAL WORDS ARE THE TEXT. THE ENGLISH IS A RENDERING OF IT.

Every window gives you the original words in order as gloss{lemma}. That block
is the text. The English translations above it are four attempts at it, and
where they and the original disagree, the original wins.

You may put the lemma a node came from in "lemma" when it is obvious from the
block -- one original word, one node, "lemma": ["H8414"]. Do not spend
reasoning on it, do not guess, and omit it entirely for any node that does not
come from one particular word. Lemma assignment is done deterministically
after the run; this field is a convenience, not a task.

**Do not mint a node from an English phrase that the original does not
carry as a unit.** Genesis 1:2 is the case. The KJV reads "without form and
void", and the original reads formlessness{H8414} and/ emptiness{H0922} --
two Hebrew nouns. The English is one adjectival phrase and the text is two
things, so it is two nodes, one lemma each. A `without_form_and_void` node
names a translator's phrasing and nothing in the text.

The same test, run the other way: where several English words render one
original word, that is one node, not several.
"""

COARSE_RULES = """\
You are recording what happened in one verse of the King James Bible.

This is narrative. It is about actors, what they did, and where. It is not
about concepts, and you must not create any. Nodes may be coarse: "went up to
Jerusalem" needs a place and a movement, not a theory of ascent.

Two exceptions, and only two:

  1. Someone is speaking. What is said inside the quotation may carry concepts.
     Record the speech act and mark the span, but do not decompose it here.
  2. The writer steps outside the story to assess -- "and he did that which was
     evil in the sight of the LORD". That is the writer's verdict and is worth
     an edge.

You may use ONLY the relation types listed below and may create only person,
place, group, object, title and creature nodes. If a verse seems to need a
concept, raise a question instead of creating one.

Output the same strict JSON shape as the decomposer, with an empty "entities"
list for anything already in the vocabulary.
"""


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

def _entity_line(e: Entity) -> str:
    bits = [e.id, e.name]
    if e.aka:
        bits.append("aka " + "; ".join(e.aka[:4]))
    if e.disambiguation:
        bits.append(e.disambiguation[:150].replace("\n", " "))
    return "  " + " | ".join(bits)


def _relation_lines(vocab) -> list[str]:
    """Each type with the types it connects.

    The first version of this gave the worker a name, a label and a note, and
    left out the signature. On the first real run it produced five sound
    relations and the gate refused every one of them: `speaks_of` is declared
    concept -> concept, and they pointed at a person, a being and an image.
    The worker was not guessing, it was uninformed -- the constraint it was
    being judged against was the one fact about each type it had not been
    given.
    """
    out = []
    for name in sorted(vocab.types):
        t = vocab.types[name]
        label = getattr(t, "label", "") or ""
        # src_types, not src_type: the singular property returns only the
        # first of several and would tell the worker `draws_on` is
        # title -> creature, which is one of the eight kinds it accepts.
        src = "|".join(getattr(t, "src_types", ()) or ("any",))
        dst = "|".join(getattr(t, "dst_types", ()) or ("any",))
        note = " ".join((getattr(t, "notes", "") or "").split())
        out.append(f"  {name}  --  {label}")
        out.append(f"      {src} -> {dst}")
        if note:
            out.append(f"      {note[:150]}")
    return out


@dataclass
class Prefix:
    book: str
    genre: str
    mode: str
    text: str
    nodes: int

    @property
    def tokens(self) -> int:
        return len(self.text) // 4

    def cost_per_call(self, rate_hit: float = 0.007) -> float:
        return self.tokens * rate_hit / 1e6


KINSHIP = {"father_of", "mother_of", "sibling_of", "half_sibling_of",
           "spouse_of", "concubine_of", "uncle_of", "cousin_of", "descended_from_person",
           "ancestor_of", "adoptive_parent_of", "betrothed_to"}

_ROSTER: set[str] | None = None


def roster_only() -> set[str]:
    """Persons the graph holds for their parentage and nothing else.

    733 of 1,608 people -- 46% -- carry only kinship edges or none at all.
    They are the men of the Chronicles registers and the returning families of
    Ezra: correctly recorded, genealogically complete, and of no use whatever
    to a worker deciding what a verse says.

    They are also expensive in exactly the wrong places. They are 428 of the
    entities in the 1 Chronicles prefix and 238 in Genesis -- a quarter to a
    third of the prompt, spent on names the worker must read past.

    So they come out of the listing. But they are NOT hidden, because a worker
    that cannot find Jahath in its vocabulary will mint a second Jahath in good
    faith, which is how this graph acquired duplicates six times. One sentence
    replaces four hundred rows and says the thing the rows were there to say.
    """
    global _ROSTER
    if _ROSTER is not None:
        return _ROSTER
    import collections
    import json as _json
    types: dict[str, set[str]] = collections.defaultdict(set)
    for path in (ONTOLOGY_RELATIONS := (ROOT / "ontology" / "relations")).glob(
            "*.jsonl"):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                r = _json.loads(line)
                types[r["src"]].add(r["type"])
                types[r["dst"]].add(r["type"])
    ents = load_entities()
    _ROSTER = {i for i, e in ents.items()
               if e.type == "person"
               and (not types.get(i) or types[i] <= KINSHIP)}
    return _ROSTER


ROSTER_NOTE = """\
NOT LISTED: {n} further people appear in this graph whose only recorded
relations are parentage -- the registers of Chronicles, the returning families
of Ezra, the begats of Genesis. They are already recorded and the genealogy is
not the work here.

So: **never create a person node for a name that appears in a genealogical
list** -- a run of "X begat Y", "the sons of X", "the children of X", or a
register of families and numbers. If such a name is all a verse contains, emit
no entities and no relations for it and say so in a question. If one of them
acts in the story -- speaks, travels, builds, is killed -- then it is no longer
genealogy and the verse is worth recording; name the person and let the gate
resolve the id.
"""


def _flat(text: str) -> str:
    import re as _re
    return " " + " ".join(_re.findall(r"[a-z]+", text.lower())) + " "


def _text_of(book: str) -> str:
    """One book's text, lowercased and flattened to single-spaced words."""
    import json as _json
    from .paths import text_path
    parts = []
    path = text_path()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            r = _json.loads(line)
            if r.get("b") == book:
                parts.append(r["t"])
    return _flat(" ".join(parts))


_FREQ: dict[str, int] = {}

# An aka must contain a word rarer than this to count as evidence that the
# entity is on the page. Chosen against the corpus, not by feel: "son" appears
# in 1,799 verses, "word" in 675, "man" in 2,426 -- all far too common to mean
# anything. "Christ" is in 532, "Jehovah" and "Emmanuel" far fewer. The gap
# between "word" and "Christ" is where the line goes.
_AKA_RARITY = 600

# A single-word primary name must be at least this rare to count as evidence.
# `Solomon` is in 274 verses and `David` 968, both far under; `on` and `put`
# are in thousands and are English, not the city and the nation.
_NAME_RARITY = 2000


def _freq() -> dict[str, int]:
    """Verses containing each word, computed once."""
    if _FREQ:
        return _FREQ
    import json as _json
    import re as _re
    from .paths import text_path
    path = text_path()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            r = _json.loads(line)
            if "b" in r:
                for w in set(_re.findall(r"[a-z]+", r["t"].lower())):
                    _FREQ[w] = _FREQ.get(w, 0) + 1
    return _FREQ


def named_in(e: Entity, text: str) -> bool:
    """Does any of this entity's names actually occur in this book's text?

    The narrative scope cannot be "entities already cited from this book".
    That is how a duplicate gets minted: Abraham is named in 1 Kings and no
    relation cites 1 Kings for him, so he is absent from the prompt and the
    worker mints a second `abraham` in good faith. It has happened six times
    in this project and never once because two ids collided -- always because
    a name was not on the page.

    So the test is the text. **As a phrase, not as a bag of words.** The first
    version of this asked whether every word of a name appeared somewhere in
    the book, on the reasoning that over-matching was the safe direction. It
    is not, for multi-word names built from common ones: `jesus` carries the
    aka "the Son" and "the Word", and 1 Kings contains "the", "son" and
    "word", so Jesus was admitted to a prompt about Solomon's temple. A spare
    row is cheap; a spare row inviting a worker to attach Kings to Jesus is
    not. `holy_ghost` arrived by the same route through "the Spirit".
    Phrase matching alone did not fix it, because 1 Kings genuinely contains
    "the son" (of Nebat) and "the Spirit" (of the LORD, 22:24). Those aka are
    real English phrases that denote Jesus only in a New Testament context.

    So the primary name always counts -- it is what the entity is called --
    and an aka counts only when it carries a word distinctive enough to mean
    something on its own. That admits "Christ" and "Emmanuel" and refuses "the
    Son" and "the Word", which is the cut wanted.
    """
    import re as _re
    freq = _freq()

    needle = _flat(e.name).strip()
    if needle and f" {needle} " in text:
        # A one-word name that is also a common English word matches every
        # book and means nothing. `On` is an Egyptian city, `Put` a nation and
        # `Iron` a town in Naphtali (Josh 19:38) -- as names they are real, and
        # as evidence that the place is on the page they are worthless. The
        # first pass over Proverbs admitted all three, plus a Nehemiah Levite
        # via "Judah". Multi-word names are exempt: their rarity is in the
        # combination, not the words.
        words = needle.split()
        if len(words) > 1 or freq.get(words[0], 0) < _NAME_RARITY:
            return True

    for name in e.aka:
        words = _re.findall(r"[a-z]+", name.lower())
        if not words or min(freq.get(w, 0) for w in words) >= _AKA_RARITY:
            continue
        alt = _flat(name).strip()
        if alt and f" {alt} " in text:
            return True
    return False


def build(book: str, entities: dict[str, Entity] | None = None) -> Prefix:
    """The cacheable head of every call in a run over `book`."""
    ents = entities if entities is not None else load_entities()
    vocab = load_vocabulary()
    genre = genre_of(book)
    mode = mode_of(book)
    wanted = SCOPE[genre]

    chosen = {}
    dropped = 0
    roster = roster_only()
    body = _text_of(book)

    # The cut is by KIND OF THING, not by genre. It used to be by genre, and
    # when narrative stopped running coarse that quietly made `person`
    # unconditional -- so Genesis, John and Matthew each came out at 2,288
    # nodes and 51,445 tokens, identical, because each was carrying all 1,608
    # people in the graph.
    #
    #   abstract   always carried. A verse can be ABOUT wisdom without using
    #              the word, so a name test would hide exactly the node the
    #              worker needs.
    #   concrete   carried only when the book names them. A verse cannot be
    #              about Hiram without saying Hiram, and 1,608 people in a
    #              prompt is most of a small model's context spent on names
    #              that will not come up.
    ABSTRACT = ("concept", "image", "text", "title", "covenant",
                "assessment", "observance", "being")
    # Nodes that break the rules this same prompt states are not shown.
    #
    # The block is headed "reuse these ids verbatim", and 522 of the entries
    # handed to the Genesis worker were sentences used as ids, whole verses
    # used as names, or questions used as ids -- every one of them a live
    # counter-example to a rule stated a hundred thousand tokens earlier.
    # `he_leadeth_me_in_the_...` (Ps 23:3 as an id) was in
    # there, which is the exact string the naming rule cites as what NOT to do.
    #
    # 5,856 tokens of instruction against 100,000 of demonstration is not a
    # contest the instruction wins, and it explains why rules with worked
    # examples still failed: the worked example was outvoted.
    #
    # Withholding them costs the reuse of a node that should not be reused
    # anyway. If the worker re-mints something similar it will do so under the
    # current rules, and the old record can be corrected later; showing it is
    # how the mistake propagates.
    from .lint import ID_WORDS, NAME_CHARS, _QUESTION

    def _teaches_the_wrong_thing(e) -> bool:
        return (e.id.count("_") >= ID_WORDS - 1
                or bool(_QUESTION.match(e.id))
                or len(e.name or "") > NAME_CHARS)

    # A bare verse locator is never listed, because its id is DERIVABLE.
    #
    # `gen_1_16` is what the reference Gen 1:16 becomes, every time, so the
    # worker can construct it without being shown it and cannot mint a
    # duplicate by not knowing. Listing 2,109 of them spends tokens telling
    # the worker something it can work out.
    #
    # The real cost was worse than the tokens. Re-running a book hands it its
    # own previous output as ids to reuse -- 1,167 Genesis locators, 808 of
    # them the carriers of exactly the tag-cloud shape the re-run exists to
    # replace. The naming filter above cannot catch them: their names are
    # fine, and only what they were USED for was wrong. A re-run anchored to
    # its own worst output would suppress the improvement it was measuring.
    #
    # Named units keep their place -- `gen_18_10_promise`, `job_18_bildad_
    # speech` -- because those ids are coined and cannot be guessed.
    import re as _re

    _LOCATOR = _re.compile(r"^[1-3]?[a-z]+_\d+_\d+$")

    withheld = 0
    for eid, e in ents.items():
        if eid in roster:
            dropped += 1
            continue
        if _teaches_the_wrong_thing(e) or _LOCATOR.match(eid):
            withheld += 1
            continue
        if e.type not in wanted:
            continue
        if e.type in ABSTRACT or named_in(e, body):
            chosen[eid] = e
        elif any(r.startswith(book + " ") for r in (e.refs or [])):
            chosen[eid] = e

    rules = CONCEPT_RULES if mode == "concept" else COARSE_RULES

    # THE PRINCIPLES GO FIRST, AND THEY ARE NOT WRITTEN HERE.
    #
    # 2026-09-01, on Deuteronomy 6:9 -- "Write them on the doorposts of your
    # houses and on your gates": the principles belong everywhere, the About
    # page and the caches included.
    #
    # First is the position that costs nothing and buys the most. It is the
    # head of the cached prefix, so it is byte-identical across every call in a
    # run and priced at the cache rate; and it is the one part of a 100,000
    # token prompt that is read before anything competes with it.
    #
    # They are rendered from `docs/PRINCIPLES.md` rather than restated here,
    # because a copy is how a rule becomes true in one place and stale in
    # another -- and unlike a stale number, nothing reports it.
    from . import principles

    parts = [principles.head(), "", rules,
             "", "RELATION VOCABULARY -- use these and no others", ""]
    parts += _relation_lines(vocab)
    if dropped:
        parts += ["", ROSTER_NOTE.format(n=dropped)]
    parts += ["", f"EXISTING NODES ({len(chosen)}) -- reuse these ids verbatim",
              ""]
    by_type: dict[str, list[Entity]] = {}
    for e in chosen.values():
        by_type.setdefault(e.type, []).append(e)
    for t in sorted(by_type):
        rows = sorted(by_type[t], key=lambda x: x.id)
        parts.append(f"-- {t} ({len(rows)})")
        parts += [_entity_line(e) for e in rows]
        parts.append("")

    return Prefix(book=book, genre=genre, mode=mode,
                  text="\n".join(parts), nodes=len(chosen))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    show = "--show" in argv
    argv = [a for a in argv if not a.startswith("--")]
    if not argv:
        print("usage: python -m bibleont.prefix <Book> [--show]")
        print("       python -m bibleont.prefix Ps")
        return 2
    p = build(argv[0])
    if show:
        print(p.text)
        return 0
    print(f"book        {p.book}")
    print(f"genre       {p.genre}")
    print(f"mode        {p.mode}")
    print(f"nodes       {p.nodes}")
    print(f"tokens      ~{p.tokens:,}")
    print(f"cached      ${p.cost_per_call():.6f} per call")
    print(f"first call  ${p.tokens * 0.22 / 1e6:.4f} (cache miss, paid once)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
