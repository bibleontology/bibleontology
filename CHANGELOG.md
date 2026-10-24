# Changelog

Two things carry versions here:
- **The vocabularies** at bibleontology.org/ns. A term's address is never reused, and every release is kept at a
  dated address (`out/ns/versions/`).
- **The graph's exports** in `out/export/`, which carry a date-shaped version of their own (`ontology/ns-version.json`,
  `data`; `out/export/void.ttl`).

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
