# Provenance: how each reading was judged

Every link the site shows as a reading, and every candidate that was not
kept, with the full trail of how it was decided. Doug, 2026-10-04: *"the
skeptics are going to claim that this is AI slop - so our rigor and
provenance is crucial."*

The claim the site makes is always the text itself: quotations from both
passages, side by side, each checked by machine against the Berean Standard
Bible. These records show how the candidates were found and filtered, so a
reader who doubts a link can see who proposed it, what each judge said and
why, what the review objected to, and what was thrown out.

## allusions-6.17.jsonl — what two verses share (plan 6.17)

515 records: every pair the first judge accepted from 9,134 candidate pairs
(a rare phrase two verses share word beside word in the Hebrew/Greek).

| field | |
|---|---|
| `judge_1`, `judge_2` | two independent Claude Sonnet readings, blind to each other and to the editors' notes; kept only where both said one verse takes up the other's words |
| `sort` | Claude Opus: words taken up, both use (a node), a story told again, or drop -- with the explanation readers see |
| `settled_by_claude` | where Claude overrode a sort to make like cases alike (Luke 22:20 with 1 Cor 11:25) |
| `review` | the eight-reader review (evangelical Baptist, Calvinist, Arminian, Lutheran, Methodist, Charismatic, Eastern Orthodox, secular academic): verdict and objections |
| `facts_restored` | where a revision had cut a true statement the reviewer could not check, restored from whole-Old-Testament searches |
| `outcome` | shown (and as what), or not kept and why: 306 shown; 183 the second judge rejected; 15 formulas; 11 dropped |

## story-echoes-6.18.jsonl — stories told again (plan 6.18)

344 records: every pair proposed.

| field | |
|---|---|
| `proposed_by` | a reader of a Gospel/Acts event, a reader of an Old Testament event, or the list of commonly cited echoes (`briefs/6.18-known-echoes.json`) |
| `judge_1` | Claude Sonnet with both passages in full: three beats, each quoted exactly from both texts; keep, named (the text names the earlier story), weak or drop; re-judged on the full text where a first packet had cut a passage |
| `machine_checks` | every beat in the verse it names, every quotation in a passage, no intent words |
| `corrected_by_claude` | the four wording fixes, each against the verse |
| `judge_2` | a skeptic who read both passages in full and had to quote the distinctive detail word for word (machine-checked): clear, thin or no |
| `status` | candidate (both judges clear, or named by the text) or not for readers, and why |
| `reviewed_by_owner` | set when the site's owner has read it; nothing is shown before |

## section-events-6.18.json — the events stories told again needed

48 of the 117 stories told again had a side no event list covered. No model
judged anything here; the rule did, and this is its working (2026-10-04).
`target` gives, for each [pair id, side], the existing event linked or the
span [first, last] of the new one; `new` gives each new event: the Berean
editors' sections holding the steps that pair quotes, titled by the heading
of the section holding most of them (others as aliases), and the pairs it
serves. The events themselves are `ontology/events/section-events.json`.

## letters-events-6.21.jsonl — the letters and events (plan 6.21)

Every item found, kept or not (2026-10-04). Readers: seven Sonnet and seven
Opus, each reading every verse of Romans-Jude (`briefs/6.21-BRIEF.md`);
their finds merged (`found_by`). Each item then has:

| field | what it is |
|---|---|
| `judge` | Claude Opus with the letter (two verses either side) and the event's own verses in full: refers / same_subject / no, with quotation pairs machine-checked (`briefs/6.21-JUDGE.md`) |
| `skeptic` | a second, independent Opus reading of every `refers`, required to quote the detail no one would write by chance, machine-checked (`briefs/6.21-SKEPTIC.md`) |
| `status` | kept, held (disputed which account; or the skeptic found the tie thin) or dropped, with why |
| `event_final` | the event it belongs to, after the rematch on the account's own words (l621 rematch, journal) |

The kept references are `ontology/letter-references.jsonl`; nothing is shown
until the site's owner has read `docs/review/LETTERS-EVENTS.md`.

## poems-events-6.19.jsonl — the psalms and poems and events (plan 6.19)

Every item found, kept or not (2026-10-05). Readers: eight Sonnet and eight
Opus, each reading every verse of the Psalms, Job, Proverbs–Song or the poems
in the narrative books (`briefs/6.19-BRIEF.md`); their finds merged
(`found_by`). Each item then has:

| field | what it is |
|---|---|
| `judge` | Claude Opus with the poem (two verses either side) and the event's own verses in full: refers / suggests / same_subject / no, with quotation pairs machine-checked (`briefs/6.19-JUDGE.md`) |
| `skeptic` | a second, independent Opus reading of every `refers`, told the claim by the Berean editors' section heading (not the event list's title), required to quote the detail no one would write by chance, machine-checked (`briefs/6.19-SKEPTIC.md`) |
| `status` | kept; held (only the content suggests the occasion; disputed; the skeptic found the tie thin; rests on a translation); or dropped, with why |
| `event_final` | the event it belongs to, by the account words (journal 2026-10-05) |

The kept and the disputed or thin ones are `ontology/poem-references.jsonl`;
their sentences were reviewed by the nine readers below
(`briefs/6.19-REVIEW.md`). Nothing is shown until the site's owner has read
them.

## prophets-events-6.20.jsonl — the prophets and events (plan 6.20)

Every item found, kept or not (2026-10-05/06). Readers: eleven Sonnet and
eleven Opus, each reading every verse of a stretch of Isaiah–Malachi
(Lamentations and Daniel in), told to keep the plan's three kinds apart
(`briefs/6.20-BRIEF.md`): `back` (the prophet names an earlier happening),
`own_time` (the prophet's own words date the passage to a happening of its
day), `forward` (a later text quotes the prophet or says it happened as
spoken). Each item has its `kind`, and then:

| field | what it is |
|---|---|
| `judge` | the prophet (two verses either side) and the event's own verses in full: refers / suggests / same_subject / no, with quotation pairs machine-checked (`briefs/6.20-JUDGE.md`). Claude Opus where a reader saw the text name, date or quote the happening; **Claude Sonnet** where every reader saw only content (in 6.19 such items were kept 2% of the time), whose `refers` still met the Opus skeptic |
| `skeptic` | a second, independent Opus reading of every `refers`, told the claim by kind and by the Berean editors' section heading, required to quote the detail no one would write by chance, machine-checked (`briefs/6.20-SKEPTIC.md`). Item 217 was asked twice: its first packet had cut the verse that quotes Isaiah (Matt 8:17) |
| `status` | kept; held (only the content suggests it; disputed; thin; Revelation's visions, left to plan 6.22; a letter's words, which tell no event; one by hand); or dropped, with why |
| `event_final` | the event it belongs to, by the account words, six corrected by hand where the section heading named a neighbour of the happening (journal 2026-10-06) |

The kept and the disputed or thin ones are `ontology/prophet-references.jsonl`,
each with its `kind`; their sentences were reviewed by the nine readers below
(`briefs/6.20-REVIEW.md`). Nothing is shown until the site's owner has read
them.

## revelation-6.22.jsonl — Revelation and the rest of Scripture (plan 6.22)

Every item found, kept or not (2026-10-06). Readers: twenty-two Sonnet, two
for each pair of chapters, each told to look up the other passage's words in
a plain-text Berean rather than quote from memory (`briefs/6.22-BRIEF.md`);
2,121 of 2,124 quotations were found in the verse named. Their finds merged
(`found_by`); the 74 pairs the 6.17 phrase search already shows were not
judged again. Each item then has:

| field | what it is |
|---|---|
| `judge` | Claude Opus with both passages (a verse either side) in full: words / image / names / key / shares_subject / no, the kind changed where the readers' was wrong, with quotation pairs machine-checked (`briefs/6.22-JUDGE.md`) |
| `skeptic` | a second, independent Opus reading of every linking verdict, required to quote the words that carry the link, machine-checked (`briefs/6.22-SKEPTIC.md`) |
| `status` | kept; apparent (disputed -- several passages share the words -- or thin); held (the link only the Hebrew or Greek shows, 6, for Doug); or dropped, with why |

The kept and apparent ones are `ontology/revelation-links.jsonl`, one per pair
of passages (a link inside Revelation found from both ends kept once); their
sentences were reviewed by the nine readers below (`briefs/6.22-REVIEW.md`).
Nothing is shown until the site's owner has read them.

## history-6.23.jsonl — the history books and the passages before them (plan 6.23)

Every item found, kept or not (2026-10-06): 2,577 ties from a passage of
Genesis–Esther to an earlier one, from Sonnet readers of every verse, each
told to look up the earlier words in a plain-text Berean
(`briefs/6.23-BRIEF.md`). Each item then has:

| field | what it is |
|---|---|
| `judge` | Claude Sonnet with both passages (a verse either side) in full: back / fulfilled / carried_out / quotes / same_subject / no, with quotation pairs machine-checked, each on its own side (`briefs/6.23-JUDGE.md`). Where a quotation was found in the item's own passages under a wrong reference, the right verse is written in (71 items); one pair found nowhere was dropped |
| `skeptic` | a second, independent Sonnet reading of every linking verdict, and a re-reading of the 43 within-book `no`s under the rule stated plainly (`briefs/6.23-SKEPTIC.md`) |
| `status` | kept (with "also told elsewhere" where the judge named a second telling of the same happening), apparent (thin), or dropped, with why |

The kept and apparent ones are `ontology/history-links.jsonl`: one per pair of
passages; grouped by passage, the label counting what is recalled; each with
its `reach` (across books / within the book / nearby) and `quiet` (nearby and
alone). No sentence per link: a fixed label per kind, reviewed by the nine
readers below (`briefs/6.23-LABELS-REVIEW.md`). The owner reviewed them
before they were shown (docs/review/HISTORY-LINKS.html).

## tables-7.6b.jsonl — the side-by-side tables on the theme pages (plan 7.6b)

One record per table row, from the Creation group on (2026-10-07). The
earlier tables (Apocalyptic, New Creation, Prophets and Prophecy, Messiah)
were not archived row by row; `tables-reviewed-7.6b.json` keeps three of them
as the owner read them, so later changes can be shown against that.

| field | what it is |
|---|---|
| `drafted_by` | Claude Opus chose the rows and quoted the cells from a plain-text Berean (`briefs/7.6b-G1-DRAFT.md`); every quotation machine-checked in its verse |
| `completeness` | every verse elsewhere that shares three words in a row with a row's cells, sorted by Sonnet into add / aside (shown with an asterisk: same words, another subject) / skip (`briefs/7.6b-COMPLETE.md`) |
| `review` | the nine-reader panel below on the Alike and Different lines: accept, revise or withdraw, with each objection (`briefs/7.6b-G1-REVIEW.md`) |
| `draft`, `final` | the two lines before and after review |

The tables themselves are `ontology/themes/*.json`; a table is shown only
once the owner has read it (`reviewed_by_owner`).

## meaning/ — the concept audits and the relations lifted from clauses (plans 8.2c, 2.17)

Candidates only: nothing in these files is shown on the site. Written by
`tools/meaning/archive_audit.py` (2026-10-19).

| file | what it is |
|---|---|
| `concept-audit-2026-10-18.jsonl.gz` | per concept card (1,194): what the judge was shown (its words, candidate words, cited verses holding none of them); phase 1, Claude Sonnet: add / not per candidate, keep / other_sense per word, notes, a grade; then every verse a repair would add, with each pass's verdict (two independent Sonnet passes; a second sample for 34 large cards) |
| `card-audit-2026-10-19.jsonl.gz` | the same for the 786 object, image, title, observance, creature and covenant cards |
| `sense-flags-2026-10-19.jsonl.gz` | per word phase 1 flagged as "other sense" (1,058): 20 of its verses spread over its uses, each judged by Claude Sonnet and Claude Haiku, blind to each other: does the word mean the card here |
| `divine-panel-2026-10-19.jsonl.gz` | per word that reaches God or Jesus only through a pointer chain (5,925, all held): the chain, and every objection from the panel of eleven in each of two independent Claude Sonnet passes (`tools/meaning/divine_panel.py`); verdict: candidate (no seat objects in either pass), objected, or held open. Nothing released by it; release is Doug's ruling (`docs/review/divine-ends-2026-10-19.html`) |
| `lifted-relations-2026-10-19.jsonl.gz` | per clause whose subject and object resolve to records (4,690, and the 41 of the love pilot): the statement, how each end was resolved, Sonnet's and Haiku's decision with why, kept only where both said yes; for the kept, a sense and family candidate (Sonnet), not a ruling |

## The review panel

Prose in the site's own voice is read by a second, blind model as each of a
panel of readers would take it, and shown only if all of them could accept
it. Every record above dated before 2026-10-05 was reviewed by the first
panel; reviews from that date use the second.

**Until 2026-10-05, eight:** evangelical Baptist, Calvinist, Arminian,
Lutheran, Methodist, Charismatic, Eastern Orthodox, secular academic.

**From 2026-10-05, nine**, chosen by the questions the site must not take a
side on -- baptism, election, eternal security, dispensations -- so each has
readers on both sides:

| reader | guards |
|---|---|
| Lutheran | justification by faith alone; law and gospel; the sacraments |
| Reformed | election; the perseverance of the saints |
| Wesleyan (Methodist / Arminian) | free will; that a believer can fall away |
| Baptist / free church | believer's baptism; often dispensational |
| Pentecostal / Charismatic | the gifts of the Spirit |
| secular academic | reads the text under no confession: does it say this? |
| Catholic | the largest family, missing before; Scripture read with the Church's tradition. Judges within the 66 books every reader on the panel shares, a constraint it agrees to; the further books its canon holds are outside the site |
| Eastern Orthodox | Scripture read with the Church's tradition. Judges within the same shared 66 books, a constraint it agrees to; the further books its canon holds are outside the site |
| biblical-theological (literary) | the Bible as one story that leads to Jesus, its literary design (repetition, echo, patterns across books), and the Old Testament heard on its own terms before it is read as pointing forward -- reading of the kind taught by BibleProject, Wheaton College Graduate School and Regent College, Vancouver |

**From 2026-10-10, ten: a rabbi joins**, first as a guest on the card "the
Jews" (cards/jews-review*), then with a vote on the site owner's terms: the
canon is the 66 books as shown, nothing added or taken away; the site surfaces
honestly what the text says; his vote can object to framing, a false
impression, or missing context the text itself supplies, but cannot stand in
the way of a fair representation of the text, hard verses included. The
owner's reason: *"not as much for his veto as for his insights. He may have a
perspective on the OT, in particular, that the others need to hear. Not
looking for controversy as much as mutual understanding and respect."* The seat
defers to the other seats on how a Christian tradition reads its own text, and
speaks as one Jewish reader, not for all Jews.

| reader | guards |
|---|---|
| rabbi | the Hebrew Scriptures heard first on their own terms, as their first hearers heard them; that the Jewish people are presented as the text presents them, whole, before any part; that nothing a Jewish reader holds dear is handled carelessly |

**From 2026-10-10, eleven: a young African American believer** -- a deep
faith and a high view of Scripture, attentive to justice and to how the text
has been read by and about people of colour. The seat's charge, from the site
owner: keep the site clear of US political readings of the text, in either
direction, and watch for culturally insensitive presentation, while staying
true to the text. The Baptist / free church seat may lean conservative, as a
counterweight; neither seat speaks for a party, and neither may bend what the
text says. The owner's reason for the panel as a whole: *"I want my panel to
have a cross section of voices."*

| reader | guards |
|---|---|
| young African American believer | no US political framing of the text, left or right; nothing culturally insensitive in how people, peoples and slavery, exile and oppression in the text are presented; the text's own concern for justice shown where it is there, and not supplied where it is not |

Why it changed: Methodist and Arminian answered the same way on every
question the review exists for; Catholic and Pentecostal readers were absent;
Anglicans range from evangelical to Anglo-Catholic and are read by the
Reformed and Catholic seats rather than one of their own; and Lutheran keeps
its own seat because justification is its centre. The canon is a separate
matter: the site covers 66 books, which is a stated assumption, and a
reader's canon does not stop them judging a sentence about Genesis.

## briefs/

The instructions each judge worked to, as given. They are the method.

## What went wrong, and is recorded

The record of 2026-10-04 keeps the failures with their numbers: a
reader that skipped five events without saying so; an 80-verse cut that
decided 27 verdicts (re-judged in full); skeptics that judged from the beats
without reading the passages (the whole round redone, and a quotation only a
reading could produce made a requirement); a reviewer that deleted true
statements it could not check (restored from the facts).
