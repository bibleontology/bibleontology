# Changelog

Two things carry versions here:
- **The vocabularies** at bibleontology.org/ns. A term's address is never reused, and every release is kept at a
  dated address (`out/ns/versions/`).
- **The graph's exports** in `out/export/`, which carry a date-shaped version of their own (`ontology/ns-version.json`,
  `data`; `out/export/void.ttl`).

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
