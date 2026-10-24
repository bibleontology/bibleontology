# Principles

Doug, 2026-09-01: *"I feel like we need is a list of principles which we adhere
to until we find a case that proves that the principle doesn't hold."*

So each one carries **what would break it**. A principle with no stated
falsifier is a preference wearing a uniform, and this file is worth nothing if
it becomes a place to record taste.

Rules for the file itself:

- **Nothing enters without evidence.** Every principle below was learned from
  a specific case, and the case is named. A rule derived by reasoning alone
  belongs among the recorded intentions until something demonstrates it.
- **A broken principle is amended in place, not deleted.** The old text stays
  with the case that broke it, because someone will otherwise re-propose it.
  There is already one such entry.
- **The falsifier must be a case, not an argument.** "Someone might disagree"
  is not a falsifier. "Matthew 16:23 does this and the rule gets it wrong" is.
- **Refer to a principle by its title, not its number.** The list grows in the
  middle — a rule about grouping is filed with the other rules about grouping —
  so the numbers are an index and not an identifier.

## Where these live

Doug, 2026-09-01, on the Shema: *"there is a verse about the law that says to
essentially put it everywhere .... well that is what we do with the principles
... prominent on the about page ... in the caches etc"*

Deuteronomy 6:9 — "Write them on the doorposts of your houses and on your
gates." So this file is not a document that gets read once. It is the
source, and everywhere else they appear is **rendered** from it rather than
copied:

| where | what appears | built by |
|---|---|---|
| the head of every worker prompt | the marked subset, first, before anything else | `bibleont.prefix` |

That is the same rule the graph follows for anything derivable: compute it,
never store a second copy. A copy is how a rule stays true in one place and
goes stale in another, and unlike a stale number, nothing reports it.

**Not the About view, and not yet.** Doug, 2026-09-01, on being told this list
looks like an invention rather than a restatement of anything published:
*"If it is our invention I don't want it to be on the about page quite yet. It
might be our secret sauce."* And on how it should eventually come out: *"I
would rather convey them bit by bit in explainer videos but we will get
there."*

Which makes this an unusual entry in a project whose whole argument is that it
shows its workings. The distinction that holds it together: **the About view
owes a reader the truth about what the graph contains and what it does not.**
It does not owe them the method that produced it, and one principle at a time
with a worked case is a better way to hand that over than thirty-three of them
in a scrolling panel.

**Open, and Doug's to settle:** *"maybe we only surface 5-8 on the site - that
decision is TBD."* So the question is not whether but which, and the shape of
the answer is already visible — the ones a reader needs in order to judge what
they are looking at (record what the text says; having a default is the error;
nothing leaves silently) are not the ones that make the extraction work. The
marking machinery here takes a second flag the day that is decided; nothing
needs designing in advance of it.

Until that day this file is not served. It was, for a while, without anyone
deciding to — `app/server.py` published the whole of `docs/` from a
directory allowlist, so this file, the journal, the backlog, the unfinished
founder's statement and the queue of reader notes were all one guessed URL
away. Fixed the same day by naming the six files the app actually links to.
**A decision not to publish something is worth nothing while the file is being
served.**

A principle ending **`Carried by the worker.`** goes into the extraction prompt.
That marking is deliberately narrow. Thirteen of these decide what a worker
does inside a single window; the rest are ours, and putting them in front of a
model reading one verse spends attention on rules it has no way to apply.

---

## I. What the graph may assert

### 1. Record what the text says, not what it means

The graph reports; it does not conclude. Where readers have differed for
centuries the text underdetermines the answer, so a faithful tool
underdetermines it too.

*Evidence.* The Trinity. The graph holds `jesus -spoken_of_as-> god` (John 1:1,
20:28) and `god -distinguished_from-> jesus` (Mark 10:18, Matt 27:46)
side by side, both explicit, both cited, neither resolved.

*Falsifier.* A passage where recording both readings makes the graph assert
something **neither** reading contains.

`Carried by the worker.`

### 2. Identity edges cannot hold a non-identity relationship

Where a corpus asserts A is B and A is distinct from B, both explicitly, no
`same_as` edge survives and no confidence score rescues it — the contradiction
just acquires a decimal. Both assertions were predications: somebody said
something, and the saying is the fact.

*Evidence.* Father is not Son, Father is God, Son is God. Recorded as
predications with speakers and citations, all three survive.

*Falsifier.* A contradiction that predication cannot hold either.

### 3. Before marking an edge uncertain, check whether the edge type is wrong

Uncertainty is for thin evidence. Strong evidence on both sides of a
contradiction is not thin evidence — it is the wrong relation.

*Falsifier.* A case with strong evidence both ways where every available
relation type is correct and the conflict remains.

### 4. A type system makes claims

A type is the one assertion in a record arriving with no citation, no grade
and usually no decision. Finish the sentence *"calling this X asserts
that…"*; if the answer is disputable, the type is doing work that belongs in
an edge.

*Evidence.* `jesus` typed `person` beside `god` typed `being` asserts a
Christology no edge asserts and no verse was cited for.

*Falsifier.* A type whose claim cannot be moved to an edge without losing
information.

### 5. A narrowly scoped relation claims the scope is meaningful

Choosing a specific target rather than a general one is itself an assertion.
Pointing at part of a set tells a reader the part is distinctive — otherwise
why name it rather than the whole?

*Evidence.* One figure was recorded as leading two of twelve tribes, from
verses where he sets terms for those two about a land settlement. He led all
twelve. Correcting the relation type was the visible half of the fix; the
invisible half was that a correctly-typed edge at the wrong altitude still
misleads.

*Falsifier.* A passage where the general edge is true, the narrow edge is
true, and the general one is the one that misleads.

`Carried by the worker.`

### 6. A document that performs an act is not a document that reports one

A corpus holds both and they look identical to a search. One narrates
something that happened between two parties; the other *is* the thing
happening, addressed to whoever is reading.

*Evidence.* "When Cephas came to Antioch, however, I opposed him to his face"
(Gal 2:11) is a confrontation with two named parties, a place and a time.
1 Corinthians 5 is a rebuke too — explicit, sustained, and with an author, an
audience and no reported outcome. Only the first is an event the graph can
hold. And a letter is **one act, not one act per paragraph**: treating each
imperative as its own speech-act from author to recipient multiplies edges
without adding facts and buries the narrated encounters that are real.

*Falsifier.* A performed act a reader needs as an event, that no other shape
can record.

`Carried by the worker.`

---

## II. Grouping

### 7. Groups are sequential and contiguous

A group is a partition of the text in its own order. Every verse falls in
exactly one group per level.

*Evidence.* Doug, on the first Titus chart: *"my expectation is that groupings
are sequential through the text."*

*Falsifier.* A unit that is genuinely discontinuous and is not better
described as a pattern over several groups.

> **AMENDED 2026-09-01.** This file first carried a span/thread distinction —
> narrative groups contiguous, argument groups possibly discontinuous. Titus's
> inclusio (1:2 and 3:7) looked like a discontinuous group and is not one; it
> is a pattern connecting two sequential groups. The error's shape is worth
> more than the correction: **a new case appeared and a new kind of container
> was invented to hold it.** Inventing a container per awkward case is how a
> model stops describing anything.

> **CHALLENGED 2026-09-01, and upheld. The case is real and the cost is
> accepted.** Two outside reviewers (`docs/reviews/`) independently identified
> this principle as the OHCO thesis — text as an ordered hierarchy of content
> objects, DeRose, Durand, Mylonas and Renear 1990 — and as refuted by three
> of the same authors in 1993, because real texts carry crossing structures no
> single partition holds.
>
> **The case they name is real and is in an extracted book.** Genesis 2:4,
> *"These are the generations of the heavens and the earth"*, is read as the
> colophon closing 1:1-2:3 and as the heading opening 2:4b. Principle 17 says
> a contested reading records both. A total partition has nowhere to put a
> second answer, so at a disputed seam this principle settles it **and does
> not say that it settled it**. That is the cost, it is named here, and it is
> accepted rather than answered.
>
> Their proposed replacement — store cited boundary claims, compute intervals
> at read time, never store a group — was **rejected on two grounds, and the
> first is Doug's**:
>
> - **A group must be a node.** Storing groups as nodes is what lets a simple
>   node, a complex node and a pattern be substituted for one another, and
>   what lets containment recurse — movement, unit, section are one type at
>   different scales. An interval computed at read time cannot be a pattern's
>   endpoint and cannot recurse. That is a real architectural property being
>   traded for a citation field, and the trade is bad.
> - **Patterns need stable ids at both ends.** A pattern is an edge between
>   groups, found corpus-wide. If intervals are ephemeral, resolving one
>   pattern edge means recomputing the grouping of the whole corpus. The
>   reviewers' answer — that an inclusio is two markers sharing a string —
>   covers marker-shaped patterns only, and not the one already built: Titus
>   2:2-10's *addressee named, then charged* is a pattern over what the groups
>   contain, not over their boundaries.
>
> Half of the 1990 citation is spent, too. The refutation had a tooling half —
> concurrent hierarchies were unbearable when a person hand-encoded them in
> SGML — and that cost is now near zero. What survives is the claim about the
> text, which no amount of cheap inference changes.
>
> **What was adopted from the challenge:** a group records the marker and the
> verse that justify each of its boundaries, so a seam is checkable by the
> verbatim gate that already exists rather than only by re-reading the
> passage. Storage does not change; groups remain nodes.
>
> **RESOLVED 2026-09-01, and more cleanly than the amendment above.** Doug,
> after seeing Mark and Titus come through the multi-pass climb: *"the
> groupings may be algorithmic but they really are not meant to be
> interpretive - they are organizational and really an overlay - actually feel
> strong about them as ever and they really are supportive of reader
> visualization."*
>
> **That dissolves the Genesis 2:4 objection rather than paying for it.** A
> partition declared as an overlay does not assert that 2:4 *is* a colophon.
> It says: for navigation, it is filed here, and here is the marker it was
> filed on. Section headings in every study Bible are editorial, contested,
> and nobody mistakes them for doctrine. The reviewers' complaint was that the
> structural layer makes uncitable claims; the answer is that it makes no
> claims at all, and the cost recorded above is smaller than it looked.
>
> **This is a promise the app has to keep, not a sentence.** If passages merge
> as ordinary nodes and are drawn like claims -- same shape, same weight, same
> arrows -- then "organizational, not interpretive" is a disclaimer
> contradicted by every screen a reader sees. The overlay has to LOOK like an
> overlay. That obligation is the price of the resolution and it falls on the
> interface rather than on the schema.
>
> A second thing follows and it is why the algorithmic turn matters here: an
> overlay derived by a stated rule can be regenerated, argued with, and
> replaced wholesale. One authored seam by seam cannot. **The rules are the
> artefact; the tree is a rendering of them.**

> **The trigger that would reverse this**, named in advance so that regret is
> recognisable rather than a feeling: the `pattern` bucket beginning to hold
> structure that would otherwise have been called a group. That is the
> reviewers' specific prediction — that `pattern` becomes where the real
> structure hides while `group` degenerates into paragraph numbering — and if
> it does not happen, they were wrong.

### 8. Patterns connect groups after the fact; they are never groups

A recurring theme contains nothing and partitions nothing.

*Evidence.* Titus 2:2-10 is a *collection* — an ordinary group. What repeats
inside it, an addressee named then charged, is a form its four members
instantiate.

*Falsifier.* A pattern that must contain its instances to be stated correctly.

### 9. The verse is an index, not a unit

The verse division is medieval and the text is older. Anything treating it as
a unit measures an artefact. Group on **nodes**; the verse is what a node
cites.

*Evidence, four symptoms of one cause.* Twelve-verse windows cut speech
mid-turn and cost 27% more reasoning. Job 38 is one utterance in 42 pieces.
Antithesis at Titus 3:8-9 scores 0.000 on verse text and is plain in nodes.
Duplicate nodes — four for *profitable* — hide in separate verse spans.

*Falsifier.* A structural question answerable from verse text and not from
nodes.

`Carried by the worker.`

> **EXTENDED 2026-09-01 to the chapter, and to the window.** This principle
> named the verse and stopped, so nothing forbade scoping a pass to a chapter
> — and `group.py` was written that way, which bakes a 13th-century editorial
> decision into the pipeline where nobody would look for it. The general form
> is that **the unit of transmission is not the unit of sense**: verse (1551),
> chapter (c. 1227) and the twelve-verse extraction window are all packaging,
> and none of them is a thing the text has.
>
> Doug, 2026-09-01, on the sliding node window: *"the floating window does not
> know about chapters - only nodes."* That is the shape that makes the rule
> true by construction rather than by discipline — a window over nodes in
> order cannot bake in a boundary it has no way to see.
>
> **The book is not packaging.** A scroll is a real unit with an author and an
> end, so the window resets at a book and slides freely through everything
> inside it. That is the one division of the four that the text itself has.

### 10. Every level assembles from the level below, and the bottom is the claim

The passage is not the bottom. **The claim is the bottom**, and a passage is
already the first assembly — so a pass that builds passages from *text* is the
only pass in the stack that ignores its own inputs.

*Evidence.* The climb reads the level beneath it at every step: units from
passages, movements from units. The chapter pass reads verse text. Psalm 103
is what that costs. Doug's reading — four parts, each a statement then its
unfolding — lives in the claims: `god -assessed_as-> slow_to_anger`,
`-assessed_as-> merciful_and_gracious`, `-likened_to-> image_father`. The
grouper never saw one of them, grouped on subject matter because subject
matter was all it could see, and returned a topical division that is
defensible and is not the psalm's shape.

*And the loss compounds upward.* Genesis found the toledot formula eleven
times and exact at the first assembly, then the same motif again at seven,
four and three instances in progressively vaguer form, until the level-4
spans read `12:1`, `29:1`, `32:1` — opening verses standing in for four
chapters. Doug, 2026-09-02: *"it is always about meaning but if any level
misses the meaning, the level above it is missing what it needs to do its
job."*

*The corollary that bites hardest.* A quarter of this graph is
`tagged-not-decomposed` — 865 verses recording who spoke and which words the
saying mentions, and nothing about what was claimed. Every assembly above
those verses is built on aboutness. Fixing a level above cannot recover it,
and feeding a starved level *more* of the wrong thing produces more confident
vagueness rather than better structure.

*Falsifier.* A level that is demonstrably better built from the raw text than
from the level below it. Narrative seams may turn out to be such a case —
Genesis and Job seams found from text cut through only 0.17% and 0.04% of
claims, which is close enough to right that the text and the claims may simply
agree there.

### 11. Two orderings, kept apart even where they agree

Group order is the sequence of the text. Event order is chronology. Through
long narrative stretches they coincide exactly and recording both feels like
duplication — record both anyway. **Nothing derives event order from group
order.**

*Evidence.* Matthew arranges by topic; textual adjacency there is not
chronological sequence.

*Falsifier.* A corpus where the two can be shown to coincide always.

### 12. Rules key on markers present, not genre assumed

Books mix. A rule keyed to *"Job is wisdom literature"* is wrong for chapters
1, 2 and 42.

*Evidence.* Genesis's eleven toledot, and the density of finer markers inside
each, sorts narrative sections from genealogies with nobody declaring a genre.

*Falsifier.* A section whose applicable rules cannot be determined from its
markers.

---

## III. Language

### 13. A retrospective marker belongs with what it refers to

It is not a hinge and does not stand alone.

*Evidence.* Titus 3:8 — *"these things"* is assessed profitable while 3:9's
*foolish questions* are assessed unprofitable. Different nodes. Reading 3:8
forward makes Paul contradict himself in consecutive verses.

*Falsifier.* A marker that demonstrably governs what follows it.

### 14. The narrator's addressee and the speech's vocative are different facts

*Evidence.* Matt 16:23 — the narrator says *"said unto Peter"*, the speech says
*"Get thee behind me, Satan"*. Second-person pronouns follow the vocative.

*Falsifier.* Nothing yet; the rule is young.

### 15. Where the text has no narrator, someone is still speaking

The absence of a speech marker is not the absence of a speaker.

*Evidence.* Job's marked speeches carry 838 attributions; the Psalms carried 3
across 83 relations, because nothing marked them — so the psalmist's claims
read as the graph's own.

*Falsifier.* A text with no determinable speaker where attributing one is
worse than leaving it open.

`Carried by the worker.`

### 16. The same rule for praise and for lament

If a rule is applied where the content is uncomfortable and skipped where it
is congenial, the graph records a preference and does so invisibly.

*Evidence.* Doug: *"praises don't get special treatment because I like them
more."* Ps 88:6 and Ps 23:1 are the same kind of sentence.

*Falsifier.* A distinction between two passages that is in the text rather
than in the reader.

`Carried by the worker.`

### 17. Shared symbolism is not similarity

A signifies C and B signifies C says nothing about A and B. Symbolic relations
do not chain.

*Evidence.* The shipped path finder produced `image_seed -> word_of_god ->
image_sword`. Every edge sound and cited; no passage relates the seed to the
sword.

*Falsifier.* A corpus where symbolic convergence does imply similarity.

`Carried by the worker.`

### 18. Having a default is the error, in either direction

Resolving ambiguity toward the literal asserts what the text may not claim;
toward the figurative explains away what it may mean plainly. Marked and
type-impossible cases record as figures; **contested ones record both**.

*Falsifier.* A class of ambiguity where one default is demonstrably right.

`Carried by the worker.`

### 19. A quotation is a copy, and it fails at its boundary

Not at its existence. The words between the quotation marks must appear in the
cited verse, in that order, with nothing removed from the middle.

*Evidence.* Twenty-five bad quotations came out of one book and **not one was
invented** — every one a real phrase, recognisably about the verse it was
attached to. They failed on *source* (the comparison translation quoted
instead of the base text), on *extent* ("maketh Orion" where the line reads
"maketh Arcturus, Orion"), and on *locus* (a phrase from Job 24:1 attached to
24:2 through 24:11). A substring match against exactly the cited span catches
all three for nothing.

*Falsifier.* A fabricated quotation — the failure an expensive plausibility
check would have been built for, and which has not occurred once.

`Carried by the worker.`

### 20. Antithesis is invisible to every measure here, so it is recorded when seen

*Evidence.* Titus 3:8 "profitable" against 3:9 "unprofitable" is the strongest
link between the two verses and signature scoring rates the pair **0.000** —
they share only *the*, *and* and *to be*. The Greek is G5624 against G0512,
the same root with an alpha-privative, and a privative makes a different
lexeme. The corollary is counter-intuitive and worth holding: **the more
deliberately a writer constructs an opposition, the lower it scores**, because
every term has been replaced by its opposite.

*Falsifier.* A mechanical measure that finds oppositions at the rate it finds
echoes.

`Carried by the worker.`

---

## IV. Sources

### 21. Go to the original language; surface disputes, take no side

*Evidence.* Titus 3:15. The recommendation was to exclude the subscription as
a late addition; the Greek layer here contains it, and the whole corpus is
Byzantine — Mark 16:9-20, John 7:53-8:11, the Johannine Comma all present.
**Checking reversed an hour-old conclusion reached by reasoning.**

*Falsifier.* A dispute where surfacing both readings misleads more than
choosing.

### 22. A candidate is promoted by being re-derived, never by being moved

*Evidence.* `ontology/candidates/` — hand-written relations held out until the
process finds them independently.

*Falsifier.* Material the process cannot reach whose absence damages the graph
more than its unearned presence would.

### 23. Nothing leaves the graph silently

Cleanup is welcome. Silent cleanup is not.

*Evidence.* Retiring the old Genesis pass dropped 23 curated relations and no
number on screen moved. The merge now prints what it stopped including.

*Falsifier.* None expected.

### 24. Look for the record before minting one, and look by name

The check is not on the id. It is on the name and its variants.

*Evidence.* Five ids minted in one session for things the graph already held —
`works_of_the_flesh` against `the_works_of_the_flesh`, `beth_lehem` against
`bethlehem`, `children_of_israel` against `israel_people`. **Not one was an id
collision**, so an id lookup finds none of them and a name search finds all of
them. A duplicate passes every mechanical check and quietly halves the
connectivity of whatever it duplicates.

A name that is a **role** — the gatekeepers, the multitude, the scribes — is a
strong prior that the record exists already, because roles persist across
documents while individuals do not. A proper name is a *weak* prior, since
documents reuse personal names freely. That is the opposite of the intuition,
and it is why per-document extraction re-mints standing bodies: each document
says them plainly, none says they are the same body as last time, and every
copy passes validation alone.

*Falsifier.* A duplicate a name-and-alias search could not have found.

`Carried by the worker.`

### 25. Always split

Two things that might be one are two nodes and one question.

*Evidence.* Two batches independently minted ids for the same person and the
graph carried her twice, including two separate marriages to the same spouse.
A later merge repaired it. Nothing repairs the other direction: a wrong merge
destroys the distinction, and no later pass can see that there was one.

*Falsifier.* A wrongly split pair whose repair cost more than a wrong merge
would have.

`Carried by the worker.`

### 26. Say "nothing here", never nothing

An empty answer and a failed one are the same bytes.

*Evidence.* Of 1,189 chapters, 403 carry a citation — which alone reads as 66%
failure. Triaged against how many known entities each uncited chapter
mentions: **133 are probably real gaps and 103 are probably genuinely empty.**
Three numbers telling three different stories, and only the first is a work
list.

*Falsifier.* A signal that separates the two after the fact as cheaply as
saying so at the time.

`Carried by the worker.`

### 27. A layer earns its place by answering a question the layer below cannot

Not by being true, and not by validating. The test is a named question a
reader would ask, that the graph could not answer before the layer existed
and can after.

*Evidence, and it is the failure this whole project turns on.* 16,124
relations once validated perfectly and meant nothing — 75% of them recording
which words are where. **No check caught it.** It was caught by a person
reading the output and feeling that it was empty, which is not a mechanism and
does not run when nobody is watching. Two outside reviewers, independently,
named the absence of any reader-side test as the largest gap in this file, and
they were right: every other falsifier here is producer-side.

Grouping is the first layer to pass the test rather than assert it. *One story
broken open and finished around another* — Mark 3:22, 5:25, 6:14, 11:15, 14:3,
14:66 — is unreachable from claims. It needs the tree, and the tree found it
for $0.24.

Doug, 2026-09-01: *"they are organizational and really an overlay ... they
really are supportive of reader visualization."* Which is the same test stated
from the other end: **the overlay is judged by what a reader can then see, not
by whether it is defensible.**

*Falsifier.* A layer that answers no question the layer below could not, and
is worth building anyway. If one is found, this rule is too strict and the
case will say why.

---

## V. Working

### 28. A guard added at zero is provable; the same guard at five hundred is a cleanup project

*Evidence.* The metaphor-taken-literally rule was added while it read zero
across every extracted book, and verified to fire on a synthetic case. John 6
and Matthew 13 are what it is for.

### 29. Zero is indistinguishable from thrift

A spend guard that cannot price a call must stop, never score it free.

*Evidence.* Eighteen misrouted windows priced at exactly $0.00 and cost
$14.55.

### 30. Measure before concluding, and check the source before both

*Evidence, three in one day.* Mark and Exodus scoring 0% verse-nodes was the
model, not the prompt. The Titus subscription was in the Greek all along. The
antithesis needed one edge, not the morphological layer proposed for it.

### 31. A validator checks consistency, not truth

Build the checks — they are cheap and they catch real errors. Never report
their passing as evidence of quality.

*Evidence.* Validation reported **zero errors across 1,654 entities and 2,299
relations** and was entirely correct: every reference resolved, every type was
in the vocabulary, nobody had two fathers. Meanwhile an entire chapter had
never been extracted, and nothing reported it, because **an absence passes
every test**.

*Falsifier.* A mechanical check that finds something that was never written.

### 32. Route by capability, not cost, wherever recall matters

*Evidence.* Cheap models under-extract and report confidently on work they did
not do. Under-extraction is invisible downstream, so the saving is realised
immediately and the cost is discovered later by someone else. Mark and Exodus
scoring 0% verse-nodes was the capable model, not the prompt fix credited for
it at the time.

*Falsifier.* A cheap model matching a capable one's recall on a stratified
sample with a control batch included.

### 33. Deduplication is a fixed point, not a pass

Re-run after every merge until it stops finding anything. Zero on the first
run proves only that the first run found nothing.

*Evidence.* One man was in the graph twice, which made his two sons look like
four men; a duplicate two links up a priestly line did the same to a son and
then a grandson. Six records, and the check reported nothing — its strongest
veto is *different parents means different people*, and the parents were the
duplicates. Merging the parent is what lets the children be seen. **A rule
that consumes the graph to judge the graph inherits the graph's errors**, and
a veto that returns zero rather than a report can never be read.

*Falsifier.* A second pass finding nothing on a graph where the first found
something.

### 34. The worked failure beats the stated rule

*Evidence.* "Quote exactly" was already in the prompt and already being
followed as far as its author could tell. Three real pairs — the base text and
the misquote, side by side, labelled as refused — did work that restating the
principle did not, because they define the boundary where it actually bends.
The same arithmetic runs the other way: 5,856 tokens of instruction against
100,000 tokens of vocabulary demonstrating the opposite is not a contest the
instruction wins, and the fix was to withhold the counter-examples.

*Falsifier.* A rule that holds in practice with no example attached.

### 35. Write the scope into the rule, not around it

A rule justified by a special case outlives the case.

*Evidence.* The roles rule — *"my son", "the wicked", "a friend" are roles,
not persons* — was true of Proverbs and was scoped by a routing mode rather
than by its own words. The mode was removed for good reasons, the scope
silently became *always*, and Genesis's chief butler and Potiphar's wife were
typed as ideas. **The damage did not appear where it was caused**: a concept
cannot be imprisoned, so thirty-four relations were refused across a dozen
types and each looked like a separate vocabulary problem. When refusals spread
evenly across many types, suspect what they have in common.

*Falsifier.* A rule whose scope cannot be stated without naming the routing
that carries it.

### 36. Before a task becomes a model's, prove it is not deterministic

Doug, 2026-09-03, on the tiering: *"100% on deterministic."*

Reach for a rule first. A model is what remains after the deterministic part
is taken out, not the default that a rule occasionally replaces.

*Evidence, and it is the same mistake eight times.* Every one of these was
first proposed as work for a model, and every one turned out to need none:

| task | what it actually needed |
|---|---|
| which original word a node is about | four scoring methods; 913 agreed, 2,546 single |
| a relation type being legal | set membership against the vocabulary |
| a lemma tag naming a word the verse contains | lookup in the tagged text |
| a node minted from a translator's phrase | unresolved, plus two content-word candidates from its own verse |
| splitting a verse into its two cola | the Masoretic athnach; 903 of 915 Proverbs verses |
| who a passage is addressed to | inheritance down the group tree |
| resolving a pronoun | the speaker and addressee of the enclosing group; half of Genesis |
| which vocabulary a window needs | three string tests; 1,033 nodes of 7,597, a 68% smaller prompt |

The last one is the sharpest. **86% of every prompt was vocabulary the window
could not use**, shipped on every call, and finding it took no model and no
embedding -- book, name-word overlap, lemma presence. It also crosses a
threshold nothing else could: with it the full algorithm fits inside a local
model's 32,768-token context, where the unfiltered prompt is 68,500.

Why the error repeats: a model *can* do all eight, visibly and immediately,
and a rule has to be derived first. The model is the path of least resistance
at the moment of writing and the expensive one forever after.

*And free changes the economics of being wrong.* Doug: *"the approach favors
being free over being perfect because being free invites iteration in waves
that involve continual improvement."* A deterministic rule can be re-run over
the whole corpus at no cost, so a wrong one is cheap to discover and cheap to
replace. A paid pass is rationed, and rationed passes get guessed at instead
of measured.

*Falsifier, and there is already a case shaped like it.* A deterministic rule
that looks sufficient and is silently wrong where only a model would notice:
the flat coverage check called good nesting a fault in 6 of 16 Mark chapters.
Determinism buys repeatability, not correctness. A rule still has to be
measured against cases it did not come from.

`Carried by the worker.`

### 37. Scope a marker to what it binds, not to the container it sits in

A negation, a conditional or an interrogative attaches to **one verb**. Scoping
it to the verse marks every clause in that verse, and the error is invisible
because the output stays plausible.

*The case that established it.* Questions were detected by looking for *mah*
anywhere in a verse. Genesis 2:19 came out as a question — *mah* there is
"whatever the man called". 6,049 questions, and the count looked reasonable.
The same fault marked 22% of the corpus `denied`, because one *lo* in a verse
denied every verb in it.

*The fix is not a smaller window, it is the right boundary.* Both languages put
these particles **before** the verb they bind, so the scope is the pre-field —
the words between the previous finite verb and this one. Exact, derived from the
text, and not a number chosen because the output looked better with it.
Questions fell 6,049 → 1,327, `denied` fell 22% → 9%, and every survivor
checked out by hand.

*Why the wrong version is attractive.* A verse is the unit the data is keyed
by, so verse-level scoping is one line of code and clause-level scoping is
twenty. The cost never appears as an error; it appears as a plausible number.

*Falsifier.* A marker that genuinely scopes to a larger unit — a chapter
heading, a superscription, a discourse-level frame. Scoping those to a clause
would be the mirror-image mistake. The rule is *match the scope to the marker*,
not *always go smaller*.

`Carried by tools/acts.py.`

### 38. The floor and the structure above it refine each other, in a loop

Doug, 2026-09-04: *"what is also going to happen here is that we will build up
but then refine reverify the lower over and over as we have more context to
apply by building up."*

**This is not a pipeline with a direction.** The deterministic floor is built
from words; grouping is built on the floor; and then the grouping resolves
things at word level that the words could never have settled on their own. Then
the improved floor changes the grouping. It terminates when the passes stop
changing anything, the same shape as Principle 33.

*The case that established it, measured three separate ways.*

- **Speech in letters.** The floor detects speech from quotation marks, which
  works everywhere except where it matters most: 7% of the graph's speech
  relations fall outside a span in narrative, and **96% in the epistles** — Eph
  15 of 15, Gal 14 of 14, Titus 69 of 70. In a letter the *book* is the speech
  and there is nothing to punctuate. No improvement to morphology finds it; the
  fact "this is a letter from Paul" descends from above and attributes 223
  clauses for free.
- **Pronouns.** Resolution failed at 29% on agreement and recency, because
  Hebrew gender is too coarse. Inside a quotation span, first person *is* the
  speaker with no agreement involved — and the span is a grouping fact, not a
  word fact.
- **The other direction.** The floor found 392 imperatives in narrative and
  prophetic books outside any span. A narrator gives no orders, so those are
  speech the grouping missed — the floor auditing the layer above it.

*Why the wrong version is attractive.* A pipeline can be reasoned about one
stage at a time and a loop cannot, so "finish the floor, then group" is the
tempting order. It is also unachievable: the floor cannot be finished, because
part of its input only exists once the grouping does.

*What this changes operationally.* An audit is not a score taken once. It is
re-run after every pass, and the number moving is the signal. The old graph is
what makes that possible, which is why it is held as an independent witness and
annotated rather than edited into agreement.

*Falsifier.* A layer that stops improving its neighbours after one round trip,
where the loop is real overhead and a two-pass pipeline would do. Worth
checking rather than assuming: iteration that never converges is as much a
failure as one that never starts.

`Carried by tools/audit.py.`

### 39. Three levels of evidence, and a rule may only be tuned against the top two

Doug, 2026-09-04, completing the model across three messages: a casebook part
*"verified by me as I have limited capacity"*, a second part *"which we let
opus verify and has a different level of certification"*, and then *"the rest
of the graph which is part of the audit but not the standard but even it has
annotations from as we learn."*

    L1  Doug-certified casebook     12 chapters      the standard
    L2  Opus-certified casebook     68 chapters      standard, weaker
    L3  the rest of the graph      670 chapters      audit source, NOT standard

Measured: the casebook is 80 chapters and **15% of the graph's node
references. 85% of the graph is audit source and not standard** -- 256 chapters
cited in the docs but below the casebook line, and 414 the graph holds
something for that were never discussed at all.

*The asymmetry is the whole point, and it is not symmetric by accident.*

- **A rule that fails on L1 is a defective rule.** There is a right answer on
  record in Doug's own words, so the rule is what moves.
- **A rule that fails on L3 is a finding, not a verdict.** The node was
  produced by the same fallible process the rule is meant to improve on, so
  either side may be wrong and the disagreement is a question to investigate.

*Why the wrong version is attractive.* L3 has 11,595 node references and L1 has
twelve chapters. Optimising against the big number looks like rigour and is the
exact mechanism by which a standard stops being Doug's: tune to fit 8,416
unreviewed nodes and the target becomes the old pipeline's average behaviour,
reproduced faithfully, defects included. A standing ruling names this failure
already -- *"the standard is mine wearing his name"* -- and the size of L3 is
what makes it tempting rather than obvious.

*What L3 is genuinely for.* Volume, coverage of forms the casebook does not
contain, and accumulating annotations as things are learned. A disagreement
there is a candidate for promotion into the casebook, which is how the standard
grows -- by Doug or Opus certifying a case, never by a case drifting upward on
its own.

*Falsifier.* An L1 case that turns out to rest on a misreading Doug would
withdraw. That is not a reason to demote the level; it is a reason to
re-adjudicate the case and annotate it, which is the mechanism the graph
already uses for the same problem.

`Carried by tools/casebook.py.`



### 40. A validator queried often becomes a training set

Doug, 2026-09-05, on whether SDBH could be used as a validator while permission
was pending: *"I don't want to fit too early to it and become a derivation
which can be proven by statistical analysis - the validator can become more
than that if the fitting is tested often and is iterative - if we develop our
methods independently then we can come back to it."*

**Repeated validation is fitting**, and it leaves a fingerprint. A rule that
agrees with a validator at 98% after fifty rounds of checking against it is
evidence of derivation, not evidence of correctness — and the derivation is
demonstrable statistically, which matters when the validator is someone else's
copyrighted work.

This is adaptive data analysis; the formal results (Dwork and others on
reusable holdouts) say a holdout degrades in proportion to the number of
*adaptive* queries made against it. Doug arrived at it from the licensing side
rather than the statistical side, which is a second route to the same rule.

*It applies to the old graph, which is the validator actually in use.* On
2026-09-04 it was queried three times — grounding, image/literal prediction,
edge agreement — and each result changed something. That is the same mechanism,
already spending a budget nobody was counting.

*The mitigation is free.* Develop the method independently, then check. Same
shape as derive-first-check-second: the independent derivation of Hebrew clause
structure is precisely what made it possible to *evaluate* MACULA instead of
absorbing it.

*The operational form.* Log every consultation — what was asked, what came
back, and whether anything changed as a result. Contamination becomes auditable
rather than invisible, and "this rule has never been fitted to the old graph"
becomes a checkable fact rather than a memory. A query that changed nothing
costs nothing; a query that caused a change is what spends the budget.

### Which validators this actually binds, and why

Doug, immediately after: *"the big difference is the licensing around sdbh -
and frankly I think that the general breakdown of sentence structures should
align."*

Right, and the distinction is the one copyright itself draws. **Structure is
fact; taxonomy is expression.**

That the subject of *bara elohim et hashamayim* is *elohim* is a fact about the
text. Any competent analyst reaches it independently, so convergence is
expected rather than suspicious, and agreeing with MACULA's clause roles at 95%
proves nothing beyond both parties reading Hebrew. But `001001001` for God is a
chosen hierarchy — it could have gone otherwise, and agreement with it is
agreement with a choice.

**The licensing splits exactly along that line**: MACULA's syntax trees are CC
BY 4.0 and SDBH is permission-only. So the query budget binds hardest on
expressive, third-party, taxonomic validators, and barely at all on structural
agreement with an openly licensed one.

*Grey, and worth knowing before it comes up:* **sense number** — which sense of
a polysemous word is meant here — is editorial judgment rather than fact, and
two competent analysts can differ. It belongs with the domain codes, not with
the clause roles. 37% of Hebrew and 42% of Aramaic.

*Our own casebook is clear on both counts.* The stress set is our selection
from a public-domain text, fitted against our own derivation, so the licensing
concern does not arise. The overfitting it produced — 1% on fourteen verses
against 25% off them — is a real methodology failure and entirely ours to
manage.

*Falsifier.* A validator large and diverse enough that adaptive queries cannot
meaningfully overfit it — the whole canon rather than 48 words. Scale is the
real defence, and where it exists the query budget stops binding.

`Carried by docs/BACKLOG.md (SDBH set aside) and tools/audit.py.`


### 41. An explicit uncertain category is cheaper than a forced decision

Doug, 2026-09-05, on the 204 same-name pairs no deterministic rule separated:
*"it is actually good to have an uncertain category - makes for a much smaller
set of indeterministic evaluations for us to retain and smaller is cheaper if
we decide to take another look later."*

Forcing every case to a decision buys 100% coverage and destroys the one thing
worth having: **a bounded list of what to look at again.** Keeping the residue
explicit buys three things instead.

- **A revisit list that is small.** 204 pairs, not 968, and not 15,023.
- **Honest certainty on the rest.** A 78% that is really 78% beats a 100% that
  is 78% with the failures hidden inside it.
- **A place to spend money.** The expensive tier applies to the residue only,
  and 204 items at model prices is nothing while 968 is not.

*This is already the shape of four things here*, which is why it is worth
naming rather than inventing: elision resolves to `unresolved`,
`agent: unexpressed`, or inferred-with-a-reason; assertion status separates
asserted from attributed, entertained and denied; the casebook separates L1
from L2 from L3; and the change-set design lets rules take the mass while the
residue stays recorded.

*The vocabulary already exists and is unused.* Relations carry `certainty` with
four values, and **16 of 15,023 use the uncertain ones** — 10 disputed, 6
conjectured, 86% marked explicit. The mechanism was built and never populated.
The ones that are there are good, and show what the category is for:

> `[disputed] Mary sibling_of Mary` — *"the Greek is ambiguous whether 'his
> mother's sister' names a fourth woman or is in apposition"*

*Falsifier, and it is a real risk rather than a formality.* A domain where the
uncertain set does not stay small. If 60% lands in `uncertain`, the category is
buying nothing and is hiding a method that does not work — the residue has to be
a residue. Watch the ratio, not just the existence of the bucket.

`Carried by the certainty field, and by the 204 unseparated person pairs.`


### 42. A premature restriction is a bug; looseness is the recoverable state

Doug, 2026-09-05: *"premature restrictions are bugs - keeping it loose is just
part of the process."*

The general form of four separate failures on one day, which is why it is a
principle rather than four fixes:

- **An empty candidate set.** 18,635 nodes ended typed as *nothing*, because a
  rule read "common noun: not a named person or deity" and removed `person`
  outright — but *king*, *servant* and *priest* are common nouns denoting
  people, and *elohim* and *theos* are common nouns denoting God.
- **The person default.** Starting from *separate unless merged* gave 69%
  over-split; David appeared as 69 men. The loose default — one person unless
  the text separates them — took agreement from 28% to 68%.
- **Neighbourhood splitting.** Restricting on token proximity, which was a weak
  proxy for the graph position actually wanted, cost 14 points of agreement.
- **Absence read as evidence.** Twice — a bare name with no patronymic, and an
  empty neighbourhood — treated as *different* rather than *not stated*.

*Why it is an asymmetry and not a preference.* **Loose states are recoverable
and narrow ones frequently are not.** A merged group whose parts were kept can
be split at any time; a wrongly split group has to be re-derived; an empty
candidate set cannot be recovered from at all. So the default belongs on the
side that can be undone, which is the same reasoning behind Doug's D1 veto —
keep the pairing *and* the halves — and behind the change-set design, where
replay is only possible because nothing was destructively committed.

*The counterweight, which is Principle 41's falsifier.* Looseness is not free:
a candidate set that never narrows carries no information. The two principles
work together — keep it loose, and watch that the loose set shrinks. If it does
not, the method is not working and the looseness is hiding that.

*Falsifier.* A domain where an early commitment is cheap to reverse and
carrying the alternatives is expensive — a hot loop, a large fan-out, a
structure rebuilt from scratch each pass anyway. There the asymmetry runs the
other way and committing early is right.

`Carried by tools/typing.py and tools/people.py.`

## 43. Restrict the candidate set by structure before comparing

A weak signal is decisive inside a small set and useless across a large one. So
the work is in the restriction, not in the comparison — and a comparison method
that looks hopeless at corpus scale is often exactly right once the structure
has narrowed what it is asked about.

*The case that established it.* Matching a legacy name to a MACULA node by
sound, across 1,600 biblical names, is the Esau/Joshua disaster: a bucketing
scheme merged four unrelated men. The *same measure*, asked only about the four
names in one roster against the four members of one parsed list, is safe enough
to lower the threshold, because it is a one-to-one assignment over a closed set
rather than a lookup against everything. Doug named it: *"if you narrow to a
collection of sons it should help figure out which matches to which"*, then
*"we do this naturally"*, then *"the context thing in another form."*

*Why it is the same principle three times.* It is Principle 37 — scope a marker
to what it binds, not to the verse — arriving from a different direction. It is
also how pronouns resolve: from the enclosing group, not by searching the book.
Three problems that look unrelated have one shape.

    the marker    scope it to the words it binds        Principle 37
    the pronoun   resolve it inside its group           2026-08-31
    the name      match it inside its collection        2026-09-05

*The corollary that keeps it honest.* Restriction is only as good as the
structure doing it. All three of the name-mapping methods tried on 2026-09-05
were blocked by the same upstream defect — 807 kin-construct chains parsed with
611 missing their children — so **when several independent methods stall at the
same number, suspect the structure they share rather than the methods.**

*Falsifier.* A case where the restricted set is systematically biased — where
the structure that narrows the candidates is itself derived from the thing being
measured. There the restriction manufactures agreement instead of enabling it,
and the wider comparison, however weak, is the honest one.

`Carried by tools/namemap.py and tools/derive.py.`

## 44. A translation may supply structure, never identity

Doug, 2026-09-09, drawing the line in two messages:

> *"The divine name is the kind of thing that should come exclusively from
> original language"* ... *"that is fundamentally different than letting BSB
> help us discern where quotes belong"*

**Both halves are needed and the distinction between them is the principle.**

*Structure may be borrowed.* Quotation marks have no counterpart in Hebrew or
Greek -- they are an editorial convention a modern editor applies, and MACULA
carries no speech markup at all: no `speaker`, no `quote`, no `sp` element
anywhere. So where a quotation opens and closes is a judgement the source text
does not record, and taking it from BSB adds information rather than replacing
any. `tools/speech.py` does exactly this, and it recovered the parable layer.

*Identity may not.* Which divine name stands in a verse **is** in the original,
so reading it off an English word is replacing evidence with a translator's
rendering. Our own files prove how badly that fails: the KJV on disk flattened
YHWH and Adonai into one string, `LORD` 6 against `Lord` 7,719, and the loss
is unrecoverable from the file.

*The measurement that settles it.* The English regex found **351** divine
speech attributions, every one the undifferentiated string "the Lord". The
frame layer, reading MACULA's own predicate-argument annotation, found
**1,449** and told them apart:

    יהוה 1,005    אֲדֹנָי 170    אֱלֹהִים 112    אֵל 13    κύριος 117    θεός 32

The original language gave four times as many attributions *and* preserved a
distinction English had destroyed. There was never a trade-off to weigh.

*The test to apply.* Ask whether the source text records the thing at all. If
it does, a translation is a lossy copy and may not be consulted. If it does not
-- paragraphing, punctuation, section breaks, verse numbers -- then an editor's
judgement is the only evidence available and should be used, with its
provenance pinned.

*Falsifier.* A case where the original-language annotation is itself derived
from a translation, which would make "go to the source" circular. Greek
`κύριος` is the near miss: it renders YHWH in Septuagint quotations and is also
an ordinary title, so the Greek does **not** resolve what the Hebrew does. Where
the source is genuinely ambiguous, say so rather than inventing a distinction.

### 44a. Semantic class is structure, not identity

Applied 2026-09-12 to the question of reaching WordNet through English glosses.
Doug:

> *"I do not know the original languages. I need to rely on the interpretation
> into English to have any chance... I don't believe that this is crossing the
> line into interpretation and by crediting the source I make clear what
> additional sources I need to surface the original text to an English speaking
> audience."*

**This is not an exception to 44; it is an application of 44's own test.** Ask
whether the source records the thing. *Does Hebrew record that grass is a plant
and smoke is a gas?* It does not. MACULA carries lemma, morphology, syntax and
coreference, and **no taxonomy anywhere** — the one part that would, SDBH and
Louw-Nida, is excluded on licence grounds and is an editorial imposition in any
case. Semantic class therefore sits where paragraphing sits: the source is
silent, so an external judgement is the only evidence available and may be used
with its provenance pinned.

*What makes it safe, and must be protected.* Doug understates his own position.
His **reading** goes through English; the graph's **floor** does not. The
strongest results of 2026-09-12 — the anchor grouping, the four-trait signature
selecting Psa.103.15-17 and Isa.40.6-8 from 21,355 spans, and the polarity
sequence matching Psa 103:8-10 to 1Co 13:4-7 — used **zero English**. A
gloss-derived class is therefore *additive on top of a source-derived floor*,
not a substitute for one.

Three rules follow, and they are what keep this on the right side of the line:

1. **Overlay, never floor.** Where a gloss-derived class and MACULA disagree,
   MACULA wins, and a query must be able to ask for source-only.
2. **Keep every gloss variant, not the most common one.** The real risk here is
   not classification but *sense selection*: `chesed` glossed "loyalty" vs
   "steadfast love" vs "covenant loyalty" lands in different synsets, and
   picking one silently turns a translator's choice into a claim about the
   Hebrew. Land on several synsets and say so.
3. **Mark it as derived via English**, so a reader can discount it. This is
   Doug's own point about crediting sources, made operational.

*Falsifier for 44a.* A case where the original language **does** encode the
class distinction being imported — grammatical gender assignment, or a
construct-state pattern that sorts nouns by kind. There, 44 applies in its
original form and the English route is barred.

`Carried by tools/speech.py, tools/frames.py and src/bibleont/turns.py.`


## 45. A subordinate clause attaches to the nearest candidate, and the other one is kept

Doug, 2026-09-21, on Psalm 107:1 — *"Give thanks to the LORD, for he is good;
for his steadfast love endures forever"*:

> *"the tricky thing when you get there is that the second 'for' actually
> gives the basis for the declaration that God is good"* ... *"it is the
> logical reading when you really think about it"* ... *"there might be a rule
> there - do it the right way and see if it holds up when we add verses"*

**The rule: a connective attaches to the clause nearest before it. Where
another candidate exists, that candidate is recorded on the edge rather than
discarded.**

*Why a rule is needed at all.* MACULA marks the conjunction and does not say
what it attaches to. The two כִּי clauses of Psalm 107:1 are **siblings under
one `ClCl` parent**, not nested, so "both ground the imperative" and "the
second grounds the first" are equally available and the source settles
neither. The first version of this silently chose the first reading by
skipping back past same-connective clauses — a reading written into the data
as though it were derived.

*Why nearest.* It is the minimal assumption about scope: a reason attaches to
what it is next to unless something says otherwise, and nothing here does.
Doug's reading of this verse is also the plain one — "he is good" is the
claim, and "his steadfast love endures forever" is how one would know it.

*Why the alternative is kept.* Because the rule is a judgement, and a
judgement that erases its competitor cannot be revisited. `alt_host` carries
the other candidate and `ambiguous: true` marks the edge.

    ambiguous attachments recorded   3,567
      and     3,432
      because    70
      if         47
      or         17
      lest        1

**The `and` figure is the warning, not the result.** וְ is 5,202 of the 7,463
conjunction-wrapped clauses and does everything in Hebrew, so a run of them
produces ambiguity almost by definition. The 135 non-`and` cases are where
this rule is doing real work.

*What would falsify it.* A verse where the nearest reading is plainly wrong
and the further one plainly right — a reason that grounds the main clause
across an intervening clause of a different kind. `tests/verses.json` is where
that case gets recorded when it turns up; Doug's instruction was *"see if it
holds up when we add verses"*, so the rule is on probation by design rather
than settled.

## 46. Nodes do not live in verses; verses are a reference layer over the graph

Doug, 2026-09-25, while a speech turn that spans BSB 8:1–4 showed in only
one of those four verses' diagrams:

> nodes should not live in verses - verses are layered on top of the graph as
> a reference mapping

*The case that established it.* The speech turn of Exodus 7:26–7:29 was given
the id `Exo.7.27#turn` and `ref: Exo.7.27` — "minted in the first verse that
continues it" — so every view that asks "what is in this verse?" found it in
one verse and not the other three. Its members were correct; its ADDRESS was
a verse, and a speech is not in a verse. The same is true of an action-state
pair recorded "by the verse holding its second member", of an episode, of a
turn, of anything above the clause.

*What it means.* A node's identity is its own. Where it sits in the text is a
SPAN — the words it covers — and a verse is one of several reference systems
mapped onto spans (MACULA's numbering, the Berean's, a chapter, a section).
"What is in this verse" is a query: the nodes whose span overlaps it. Verse
numbering is editorial and later than the text; the Hebrew and English
numbering of this very passage differ by four.

*What it does not mean.* Word occurrences and clauses are still located by
their words, and a clause will almost always fall inside one verse. The
principle bites where a unit is larger than, or crosses, a verse boundary —
exactly the units that grouping is for.

*Current state, honestly.* The graph still keys every id by verse
(`Ref#local`). The first application is in the VIEW: a verse diagram now
includes every node whose span touches the verse. Re-keying the graph so a
node carries a span instead of an address is recorded in `docs/BACKLOG.md`.

*What would falsify it.* A unit whose meaning genuinely depends on the verse
division — none is known; the divisions are medieval.

## 47. A kind is the most specific thing the graph can say NOW, and patterns match by kind

Doug, 2026-09-25, on "the LORD is my shepherd" as an illustration:

> so the metaphor is a specialization of the assertion based on the current
> state of the graph - giving it a polymorphic quality when we get to
> pattern matching

*Two consequences, both binding on the pattern layer (step 6).*

1. **Classification is derived and refinable.** A node's kind is the most
   specific kind the graph's current state supports. Psalm 23:1 is today an
   assertion whose construction is X-is-Y; when the meaning graph can see
   that "the LORD" is not in the category "shepherd", the same node becomes
   an illustration. It is specialized in place — never re-created, never
   re-keyed — and it keeps every kind above it.
2. **Patterns match by subsumption.** A slot typed with a kind accepts that
   kind or any specialization of it. A pattern over *assertion* matches an
   illustration; a pattern over *illustration* matches only illustrations.
   So "X is my shepherd" and "X is my rock" can meet as illustrations, and
   still meet a broader pattern as assertions — the polymorphism Doug named.
   `tools/ontology.py` answers it: `is_a(kind, ancestor)` and `lineage(kind)`,
   read off the `parent` chain in `ontology/kinds.json`.

3. **A slot has two dimensions, KIND and CONTENT, and either may be the
   pattern.** Doug, the same day: *"patterns may be interested in either the
   specialization or the generalization - if the specialization always holds
   the content may not even matter for purposes of the pattern."* A slot's
   kind is the most specific kind ALL its fillers share — their least common
   subsumer, `common_kind()` in tools/ontology.py. Where every instance
   fills a slot with an illustration — "the LORD is my shepherd", "you are my
   rock", "you are our potter" — the slot IS "an illustration", and the image
   is free. Content constrains a slot only where the content itself recurs.
   The first pattern layer did the opposite: it keyed slots on words and
   treated every filler as content, which is why its patterns were "triples
   with the relationship fixed on a common word" (Doug, 2026-09-20).

*What it rules out.* A pattern keyed on a leaf kind only, which would miss
every node the graph has not yet specialized; and a node that changes
identity when it is specialized, which would break every pattern instance
that pointed at it.

*What would falsify it.* A specialization that contradicts its parent — an
illustration that is not an assertion — which would make it a different
kind, not a refinement.

---

> **CONFIRMED by Doug, 2026-09-27: "those are fine".** 50-52 keep their
> PROVISIONAL mark on the EVIDENCE: Doug accepts them as understood and
> sound, but under this file's rule they still wait for a case that proves
> or breaks them.
>
> *Original note:* 48-52 were added on 2026-09-27 and were NOT yet
> confirmed by Doug. Doug: *"make a note to circle back and confirm that we got
> these additions right. I want to make sure that we aren't randomly adding
> principles on an unproven hunch but that they are grounded in something
> or at least that they are well understood by me."* Each entry says how it
> is grounded. 48 and 49 rest on cases from the fix loop of 26-27 Sep.
> 50-52 are PROVISIONAL: reasoning plus thin evidence. Under this file's own
> rule they are not yet principles, and they stay marked until a case or
> Doug settles them. Tracked as P-2026-09-27-29 in docs/PLAN-PROPOSALS.md.

## 48. A rule is trusted on its measurement, never on how right its code reads

*The case.* On 26 Sep DeepSeek wrote 7 rules as plug-ins for the framework,
and each read plausibly. The whole-corpus harness showed:
- Two detected NOTHING, including in the verse they were written for. One
  read `verb_person` from a verb node, and one looked for clause links on
  the content node.
- One fired 1,506 times and broke command groups and nested quotations
  (`turn_composition`).
- One was 0 for 3: it fired on new speeches ("But the Israelites said").
- One doubled a noun ("springs and springs"), because two quantifiers share
  one node.

Only `baavur_purpose` was right as written. Nothing reached the graph,
because every rule was counted and sampled before it could be enabled.

*What it binds.* A rule, whether a worker's or Claude's, is run over the
whole corpus (`tools/fixrules/harness.py`). Its detections are sampled and
judged against the text. It enters the build only after that, and only on
Doug's yes. This is Principle 39 applied to generated code.

*Falsifier.* A class of rule whose reading is reliably its measurement (say,
a pure lexicon lookup), such that a year of samples finds no gap between the
two.

## 49. Sort a fault by what decides it: form is fixed, judgement is flagged, meaning is read

*The case.* Rules decided by the Hebrew's FORM measured well:
- `parallel_lines_agree` (person agreement) removed 214 wrongly carried
  subjects, 7/7.
- `gapped_verb` (roles and order) 11/13.
- `second_person_subject` (verb person) 4/4.
- `baavur_purpose` (a function word) 3/3.

Rules that needed JUDGEMENT misfired:
- `turn_composition` (what counts as speech) broke 1,506 groups.
- `narrator_reason_after_speech` 0/3.
- Psa 103:9's "he", four agreeing candidates: every structural rule was
  between 2/16 and 10/16.

*What it binds.* Three tiers.
- **Form-decided** (agreement, morphology, a function word): build a fixer,
  with the precision bar and the checks in 51.
- **Judgement-decided** (speech scope, elaboration, which of several
  agreeing referents): a detector flags it, and the graph marks it as a
  candidate or holds it (docs/HELD.md). It is not auto-fixed.
- **Meaning** (reason-for-the-reason, topic across verses): Doug's
  readings, and plan Steps 4-5.

*Falsifier.* A judgement-decided relation for which a form rule measures
about 14/16 or better. That would move it into the first tier, and it would
show the tier boundary is drawn too cautiously.

## 53. When a solution loses its elegance, examine it for inessential complexity and side effects

Doug's own principle, stated 2026-09-27: *"I have a principle that when the
solution loses its elegance it should be examined for inessential
complexity and side effects."*

*The cases that show it here.*
- **tools/placeholders.py** grew to 5,000+ lines of passes that correct
  each other:
  - a fold that dropped every self-loop in the graph (699) until limited
    to the loops it made (141)
  - a "then" rule that had to skip condition hosts
  - a pass that drops "and" from a consequence
  - plug-in fixes that re-point what an earlier pass dissolved

  The complexity was the symptom; the side effects (carried subjects,
  orphaned speech parts) were the cost. It is why the builder is being
  rebuilt clean (plan 1.26).
- **tools/invariants.py**, within an hour of being written, needed five
  exception lists to tell "accounted for" from "lost". The lists were not
  the check's own complexity: they came from the graph not recording which
  source morpheme each node and edge stands for. Stamping every node and
  edge with its MACULA morpheme ids reduces word accountability and span
  containment to set arithmetic, and removes the guessing.

*What it binds.* When a rule, a pass or a check starts collecting special
cases, stop and ask what missing piece of information forces them. Supply
that information upstream rather than adding the next exception.

*Falsifier.* A domain whose truth is irreducibly a list of exceptions, where
no upstream information removes them. Hebrew morphology has some of this
(suppletive forms), which is where the lexicon, not the rule, should carry
it.

## Provisional, awaiting Doug's confirmation

## 50. Correct at the source, not downstream — PROVISIONAL

*Grounding, thin.*
- The 103:3 frame fold merged the frame but left BOTH clauses standing, and
  Doug asked why there were two.
- `parallel_lines_agree` dissolved a group but left the speech turn's
  `part` pointing at the empty group. The clauses fell out of the speech
  until Claude added the re-pointing.

Both are downstream corrections that left the upstream decision in place.
The clustering of 65 audited verses found 6 BLENDED mechanisms, each one
decision early in the build that answers several fault patterns
(docs/FIXLOOP-PATTERNS.md):
- force from morphology
- one function-word lexicon
- climbing to the finite host before linking
- a clause splitter and folder
- one pronoun resolver
- one turn and quotation builder

*What it would bind.* A fault pattern with a blended mechanism is fixed in
the builder where the decision is made. A post-hoc plug-in is for
measuring and for narrow cases.

*Falsifier.* A builder-level change that measures worse than the plug-in
patches it replaces.

## 51. A fix ships only if it moves its own measure and no other — PROVISIONAL

*Grounding.* Doug's concern, 2026-09-27: *"deterministic programs will fix
one situation and cause other breaks."* The re-pointing gap in 50 is one
such break, and a fix's own validate() did not see it. Not yet run as a
gate.

*What it would bind.* Every build compares every invariant (52) and every
detector's hit count with the last build (the blast radius). A fix is kept
only if it moves its own measure the right way and leaves the others
alone. A rise in an unrelated detector's count is a break.

*Falsifier.* A correct fix that must legitimately move an unrelated
measure, and cannot be expressed so that it doesn't. That would show the
gate is too strict and needs a declared-effects list.

## 52. Three layers of checking: the vetted benchmark, invariants from the source, translations as flags — PROVISIONAL

*Grounding.* Doug, 2026-09-27: *"We need to continue to lock in the
benchmark which we are constantly checking for integrity. But I also think
that we can have a set of deterministic measurements which we can run
regularly."* It extends Principle 39 (three levels of evidence) and
Principle 44 (a translation may supply structure, never identity). The
evidence that invariants would have caught real faults:
- Psa 103:1's "all that is within me" was in NO node. A
  word-accountability check finds it at once.
- 2Sa 17:14's "to the LORD" and 1Ki 1:18's carried subject were roles
  outside their clause's own words, which a span-containment check finds.
- Speech scope is the most-cited audit pattern (15 verses), and the BSB's
  quotation marks are already used as structure (Principle 44).

*The layers.*
1. **Benchmark:** tests/verses.json, Doug's vetted readings. It is small
   and deep. Integrity rule: an expected answer never comes from the
   graph's output, and its hash changes only with Doug's approval.
2. **Invariants:** deterministic, whole-corpus, every build, where the
   SOURCE is the oracle:
   - word and connector accountability
   - span containment
   - negation and question fidelity
   - agreement
   - referent sanity
   - group well-formedness from kinds.json
   - identical Hebrew gets identical structure (Kings // Chronicles, Psa
     14 // 53)
   - declared kinds against used kinds, and label honesty
   - determinism and id stability
3. **Comparison signals:** translations against our readings (BSB links,
   question marks, quotation marks, supplied words). A disagreement is a
   FLAG, never a verdict. Several translations agreeing against us is the
   strongest flag.

*What it would bind.* The invariants and the drift report become the gate
in 51. The list of checks to build is P-2026-09-27-29.

*Falsifier.* An invariant that fires mostly on correct structure, for
example if Hebrew legitimately leaves many words structurally unaccounted.
That would show the source is not the oracle for that check.
