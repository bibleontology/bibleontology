# Changelog

Two things carry versions here:
- **The vocabularies** at bibleontology.org/ns. A term's address is never reused, and every release is kept at a
  dated address (`out/ns/versions/`).
- **The graph's exports** in `out/export/`, which carry a date-shaped version of their own (`ontology/ns-version.json`,
  `data`; `out/export/void.ttl`).

## Vocabularies 1.4.0: 2026-11-11

**`/ns/biblio`, the texts vocabulary.** 19 terms: LRMoo 1.1.1's Work, Expression and Manifestation, with only what
the published data uses beside them (arrangements, sections, verse segments and their alignment, and a heading's two
claim relations, `superscriptionNames` and `composedBy`). `translationOf` is declared a subproperty of
`lrmoo:R76_is_derivative_of`. Its shapes join `/ns/shapes`. None removed or deprecated. Released with the data it
describes. The write-up: `docs/who-wrote-psalm-73.md`.

## Data 2026.11.11: 2026-11-11

**The Psalter as Works** (`out/export/psalter.nt.gz`, 22,431 triples): the 150 psalms as LRMoo Works, each realized
in its Hebrew (MACULA, after the Westminster Leningrad Codex) and its Berean English, verse by verse and aligned. The
Psalter's Expressions incorporate the psalms' (`R75`). The Masoretic order is in five books. Every Work has a creation
event naming no author, date or place. Who a heading names, and who composed the psalm, are claims with their
certainty and voice; composition is always marked disputed. The sons of Korah (11 psalms) are held, since the graph
has no record for them. A heading's kind, directions and occasions are counted, not published.

**Cards lead with what the text says most.** Stories told again put their steps side by side first, on the card and
the served page. Places rank their stories by how much the text tells there. Images open on what the picture stands
for, in the verse's words. Events say what is spoken in them and the themes they're in, open. Objects show where a
thing stands and what it is one of.

**Corrections:** relations the cited verses do not say are held or dropped (five Last Supper messages, "Julius
imprisoned Paul", "Naboth died at Jezreel", three of the lamp's verses that rest on the King James reading), and King
James wording is out of six cards' "also called".

## Vocabularies 1.3.0: 2026-11-01

Eleven relation types added, none removed or deprecated: `knows`, `loves`, `sees`, `rewards`, `forgives`, `reveals`,
`hides`, `glorifies`, `honors`, `testifies_about`, `dwells_in`. They came from reading the 184 verses that name the
Father and were cited by none of his card's relations: 101 of 171 candidate relations needed a verb the graph lacked.
The Father's card gains 47 relations, each with its verse and, where a speaker says it, credited to the speaker
(most to Jesus). About 120 candidates are held, most because their other end ("you", "what you need") has no record.

## Data 2026.11.01: 2026-11-01

**Every kind of card has a face of its own.** Each was designed on mockups and read by a Bible scholar, a
BibleProject-style reader and a search reviewer before it was built; each has a test with planted faults.
- **People:** who they are, each with its verse (son of, husband of, called), the name in the original, the family as
  a figure, and every relation in drawers by kind of evidence. God, the Father and the Holy Spirit now use this face
  too, with drawers titled for what they hold ("People and peoples", "Places"), never "Family and kin".
- **Places, events, objects and groups:** a place's story and what is inside it; an event's neighbors, its passage
  and a cast whose verses name who did what; an object's or a group's members and the verses that name them.
- **The 18 parables** as showcase cards: the story and its explanation side by side, with what each part of the story
  is said to stand for, where the text says it (`answered_in`, a new relation type).
- **Images:** a simple line sketch of the thing named, never of a divine person.
- **I AM:** the 56 places where the original has the words, grouped, led by Exodus 3:14.
- **Every other record** has a fallback face: what the text says of it, the verses in the Berean's words, where its
  Hebrew and Greek words stand.

**Questions, side by side.** All ten shown question cards now compare their readings item by item: free will, can
salvation be lost, total depravity, human nature, election, faith and works, baptism, communion, the Sabbath and
speaking in tongues. Each comparison was passed by a panel of readers from the traditions it names. The six held
cards stay off the site, and a test keeps them off.

**A relation can say whether a verse is of a whole people or a part of it.** The Jewish people's card is the first:
its 18 relations became 25, each marked whole or part, with the part named in the verse's own words. The claims export
does not yet carry this; a part's relation is still exported as the narrator's triple.

**The original prints in the verse's order** wherever the text is shown.

**Claims:** 21,795 (21,451 before). **Records:** 11,555. **Ties:** 19,296. **Card words:** 7,018 on 1,883 cards.

**How some of the code is now written:** `docs/a-cheap-model-as-a-contractor.md` describes a cheap model writing code
to a specification and a test written first, in a contained worker, with Claude reading every change before it is
committed.

**Vocabularies:** unchanged at 1.2.1.

## Data 2026.10.27: 2026-10-27

**Questions Christians read the text on differently, side by side.**
- Ten "What does the Bible say about ...?" cards, in four groups (Salvation; The human person; Sacraments and
  ordinances; Church life): what every reading agrees the text says, then each reading with the verses its own
  holders cite first, and no side taken. The cards on last things (the end times, the thousand years, the rapture,
  what happens after death, and the end of the lost) and the card on tithing are held back and are not in this
  release.
- Each reading's verses were audited against what at least three of that position's own sources cite. Every quote is
  the Berean Standard Bible's exact words.
- Each card was read by a panel holding each of its readings and by readers of nine traditions; every linked document
  was fetched and judged for agreement with what the card says of it.
- Where a quoted verse reads differently without the verses around it, the card can show them in place (13 places).
- The traditions' own documents (confessions, catechisms, adopted standards; a founder's work, a committee's report
  and a teacher's answer each marked as such) are listed and linked. A tradition is named as holding a reading only
  where its own document states it.

**The traditions' own words, as a layer** (`ontology/traditions/`, built from the shown cards by
`tools/traditions/build.py`): nine traditions, 23 church bodies, 248 documents; 939 edges (`issued_by`, `speaks_on`,
`states_reading`), each carrying the verses of the reading it supports. The statements are the traditions', never the
site's claims. Each tradition has a page.

**The tree of the knowledge of good and evil:** its name joined to the cards for knowledge, good and evil
(`composed_of`, Gen 2:9, 2:17), and the serpent's words at Gen 3:5 to the tree (`speaks_of`).

**Word cards:** how the Berean renders each word (counted), verses in canonical order (they were in alphabetical
order of book), the Greek lexicon entry whole (Abbott-Smith, via STEP), and the site's word groupings. The Hebrew
lexicon entries are withheld for now: their source asks that permission be sought from the Online Bible, whose
abridged Brown-Driver-Briggs they follow. 9,501 word cards are listed in `sitemap-words.xml`.

**Claims:** 21,451 (21,440 before).

**Vocabularies:** unchanged at 1.2.1.

## Data 2026.10.25: 2026-10-25

**Claims:** 21,440 (21,394 before), of them **8,089 asserted** (8,119).
- **Claims inside speeches credited to their speakers in every book.** The credits had been looked up in the site's
  book codes while the speech data uses MACULA's, so outside the books whose codes coincide none was found.
- **The fault disclosed in the r/semanticweb post shrinks.** Links inside speeches still in the narrator's voice
  (how one clause grounds another, a speaker's simile) were 83 in Job and are now **71**, 14 of them Eliphaz's in
  Job 15. Still a known fault.
- **Jena and RDF4J re-run on both files:** 227,920 quads (RDF 1.1, 92 graphs) and 237,291 (RDF 1.2); every query
  answers as before (`tools/rdf12/README.md`).

**Image cards: the verses where the text uses the figure** (the image audit, plan 8.2h).
- Each image card had listed every verse of its word: "the hand of God" every "hand". 195 image cards were read verse
  by verse, by two or three readers each, and now hold the verses where the figure is used. 30,734 card verses
  became 6,220; verses the readers split three ways over are held on neither card. "The hand of God": 1,444 to 457.
- **The first eight** (wine, lion, vine, the candlestick, lamb, clothes, ox, bread) also hold their literal cards'
  verses apart from the figure's, with the relations their descriptions name (52 added): wine 169 verses to 38,
  ox 236 to 10.
- **92 image cards that showed no verses** now show the verses their own descriptions cite.
- **76 image cards named by their figure,** no longer by a bare word another card uses: "the two houses", "a city on
  a hill", "light, as a figure". Sixteen twin image cards keep their names until the twins are settled.
- **The temple:** the temple of Baal (2 Kgs 11:18) and the cult prostitutes' houses (2 Kgs 23:7) no longer resolve
  to the LORD's temple.

**Vocabularies:** unchanged at 1.2.1.

## Data 2026.10.23: first public release, 2026-10-23

- **The repository is public:** https://github.com/bibleontology/bibleontology. It begins here, a fresh export by
  design.
- **The graph's licence is granted:** CC BY 4.0, with credit to Bible Ontology by Doug Egge (bibleontology.org). The
  exports' headers and `out/export/void.ttl` say so; until today they said "all rights reserved".
- **The temple, both cards:** the building's verses (583) and the figure's (9) by named-verse rulings, and the
  relations the cards' text names. Built by Solomon, Zerubbabel and Jeshua; destroyed by the Babylonians; repaired by
  Joash, Hezekiah and Josiah. The figure signifies God, Jesus, the churches at Corinth and Ephesus, and the body
  (1 Cor 6:19).
- **Vocabularies:** unchanged at 1.2.1.

## Vocabularies 1.2.1 and data 2026.10.22: 2026-10-22

**Changed: what is asserted.**
- **Only what the narrator states or entails is asserted** (certainty explicit or implied).
- **Never asserted:**
  - conjectured and disputed claims;
  - the graph's own groupings: themes, pattern instances, story links, the text's divisions, and what a passage
    speaks of. These are credited to the editors' voice (`voice/reader/editors`).
- **No `bor:states` triple is asserted.** The relation carries no verb, so different sentences shared one triple. Each
  verb statement is described by its claim, verb and grammar included.
- **The effect:** asserted triples fell from 18,701 to 8,103. `tests/test_assertion_policy.py` checks the published
  files.

**Fixed.**
- **Gen 20:16** credited to the Abimelech of Psalm 34; now Abimelech king of Gerar.
- **The 228 speeches of Elihu in Job** credited to another Elihu; now Elihu son of Barachel.
- **Isa 54:7's second verb statement** ("gather") was lost when two statements shared a key.
- **Claims that named a record the graph had merged into another now name the one kept** (25 duplicate claims
  removed).
- **`entities.ttl.gz` now holds every record a claim names** (11,503, up from 8,378). The published shapes report no
  violation on the published data (`tests/test_export_shapes.py`).
- **The exports are reproducible byte for byte:** LF line ends, no timestamp in the gzip header.

**Vocabularies.**
- `claim.ttl`'s definitions match the above.
- The two shapes files and `/ns/word` state their rights and licence.
- No term added, removed or deprecated.

**Data.**
- The exports carry their own version, `2026.10.22`, apart from the vocabularies'.

## Vocabularies 1.2.0: 2026-10-21

- **The reviewed release:** 110 terms added, none removed or deprecated. In the four vocabularies:
  - structure: the prepositional relations, Generic, Together, List;
  - relation: `spoke_to`, `states`;
  - meaning: the filter as data, CardWord, Tie, Tier, the DQV metrics and policy;
  - claim: the verb statements' modality and family schemes, `clause`, `evidencedBy`.
- `/ns/alignment` (SKOS mappings to schema.org, FOAF, CIDOC CRM, OntoLex and Web Annotation) and `/ns/map` begin.

## Vocabularies 1.1.1: 2026-10-17

- The vocabularies are licensed under CC BY 4.0. No term changed.

## Vocabularies 1.1.0: 2026-10-15

- `/ns/claim`, the claim vocabulary of the export, and its shapes in `/ns/shapes`.

## Vocabularies 1.0.0: 2026-10-14

- `/ns/meaning`, `/ns/structure` and `/ns/relation` first released, with the reasoning policy: checked by SHACL, not
  inferred.
