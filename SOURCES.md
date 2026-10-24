# The texts this project is built on

Five English translations and two original-language datasets (one of which
also supplies the word cards' lexicon), a reference lexicon, and the software
and typefaces the site ships. The site's About view thanks each of them by
name under "With thanks"; this file gives their terms. The translations
are all public domain or dedicated to it, which is why they are here: a graph
whose argument is that every claim can be checked is worthless if the reader
cannot legally see the text it was checked against.

The two original-language sources are **not** public domain and are treated
differently from each other. They are described under "The original languages"
below, after the translations.

Each is quoted below in **its own words** where it makes a statement about its
terms, rather than in a summary of them. A paraphrase of a licence is not a
licence.

The notices that must travel with every copy are in [NOTICE](NOTICE); this
project's own terms, folder by folder, are in [LICENSING.md](LICENSING.md). This
file is the long account: what each source is, what is read from it, what was
changed, and why.

---

## King James Version (1769)

Public domain in the United States and in most of the world.

**In the United Kingdom it is not.** The KJV is under perpetual Crown
copyright, exercised through letters patent, and administered there by
Cambridge University Press as the Queen's/King's Printer. Reproduction within
the UK is permissible only under the terms the patent holders allow.

This matters here for one reason and it is not academic: this project puts the
text on a public website, and a public website is reachable from the United
Kingdom. Anyone deploying it should read the current Cambridge University Press
permissions rather than rely on this paragraph.

**No longer shown (plan A.22, 2026-10-02).** It was the base text the earlier
graph was named and cited from; every visible quotation, phrase and name
spelling has since been replaced by the Berean's (or the WEB's or ASV's where
they fit better). The live site keeps the old wording in hidden fields
(`*_kjv`), searched so an old link or an old phrase still finds its record,
and never displayed.

**The public repository carries none of it.** Those fields, the KJV text
files and the tools that read them are left out when the repository is cut
(`tools/export_public.py`), and the cut refuses to be written while any file
holds a run of KJV wording that the other four translations do not share. This
section stays because the project's history runs through this text.

## American Standard Version (1901)

Public domain. Its copyright expired and was not renewed.

Used for the name crosswalk — comparing it verse by verse against the KJV is
what yields the Hebrew/Greek name equivalences mechanically instead of by hand.

## Young's Literal Translation (1898)

Public domain. Robert Young, translator.

Obtained from <https://ebible.org/Scriptures/engylt_vpl.zip>, which lists it as
Redistributable with copyright "public domain".

## World English Bible

Public domain, by the deliberate dedication of its editor, Michael Paul
Johnson. It is a revision of the American Standard Version.

Obtained from <https://ebible.org/Scriptures/engwebp_vpl.zip>.

## Berean Standard Bible

Dedicated to the public domain by its publishers. Their own statement, carried
in the first lines of the text file itself:

> The Holy Bible, Berean Standard Bible, BSB is produced in cooperation with
> Bible Hub, Discovery Bible, unfoldingWord, Bible Aquifer, OpenBible.com, and
> the Berean Bible Translation Committee.
>
> This text of God's Word has been dedicated to the public domain. Free
> resources and databases are available at BereanBible.com.

Obtained from <https://bereanbible.com/bsb.txt>.

Attribution is not required by that dedication. It is given here because the
work was done by people, and saying so costs nothing.

---

## The original languages

Two datasets, under different terms, handled differently. **Neither is public
domain**, which is why this section is specific rather than summarised.

### MACULA Hebrew and Greek Linguistic Datasets — Clear Bible, Biblica

**© 2022–2024 Biblica, Inc.**, licensed **CC BY 4.0**, which permits
redistribution and adaptation with attribution. Clear Bible is Biblica's
(clear.bible redirects to biblica.com/clear/). The attribution the licence asks
for, in its own words:

> MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/

> MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/

And its condition: attribution "in any reasonable manner, but not in any way
that suggests the licensor endorses you or your use". Biblica does not endorse
this project.

Sources: <https://github.com/Clear-Bible/macula-hebrew> ·
<https://github.com/Clear-Bible/macula-greek>

**Biblica's AI policy does not reach this data.** Biblica's permissions page
requires a licence for "any use of Biblica content in connection with
artificial intelligence". That page governs its Bible texts (the NIV and
others), none of which this project uses. MACULA is released under CC BY 4.0.
That licence grants use "for any purpose", says "No additional restrictions",
and "The licensor cannot revoke these freedoms as long as you follow the
license terms". The site itself has no AI feature: the server makes no
outbound call at run time. Models were used in building it, as About says.

**What MACULA gathers, and which parts are read here.** The release read is
the WLC lowfat trees (Hebrew) and the Nestle1904 lowfat trees (Greek)
(`tools/fetch_macula.py`). Within them, under the terms MACULA's README
gives:
- the Westminster Leningrad Codex: "All biblical Hebrew text, in any format,
  may be viewed or copied without restriction";
- the Westminster Hebrew Syntax, © 1991–2018 The J. Alan Groves Center for
  Advanced Biblical Research, CC BY 4.0;
- the OpenScriptures Hebrew Bible morphology, CC BY 4.0;
- the Nestle 1904 Greek New Testament (British and Foreign Bible Society,
  1904; transcription by Diego Santos, morphology by Ulrik Sandborg-Petersen,
  markup by Jonathan Robie), terms at github.com/biblicalhumanities/Nestle1904;
- English glosses: the Berean Interlinear Bible's (public domain since 30
  April 2023) and Cherith Glosses by Andi Wu, © 2022–2023 Cherith Analytics,
  CC BY 4.0. The site shows these glosses on every word.

The SBLGNT trees are in the same repository and are not read.

This is the syntactic backbone: sentences, clauses, roles, lemmas, and the
morphology the comparison and coordination work reads. Derived extracts of it
*are* in this repository, and **each one carries that attribution as its own
first line**, so the credit travels with the data rather than living only in
this file, which a copied artefact would leave behind.

**The version read.** Release tags, pinned, with a SHA-256 for every file
and for each release's whole archive (`tools/fetch_macula.py`;
`data/macula-manifest.json`, committed):
- macula-hebrew **26.04.13** (archive SHA-256 `167d2803…94b576`);
- macula-greek **24.06.17** (archive SHA-256 `05751ac1…965362`).

A newer release is adopted only after its differences are reviewed (`--check`,
`--adopt`), so a rebuild cannot change silently.

**What this project changed (CC BY 4.0, section 3(a)(1)(B)).** The MACULA
files are read as released and are not modified. From them this project
*derives*:
- the clause structure shown on every verse (clauses, their roles, how they
  join, speech turns and command groups), built by rule
  (`tools/builder/`);
- the prepositional phrases and what they relate (`tools/wordgraph/`);
- the word-level layers (glosses, lemma groupings).

The derived extracts (the prepositional phrases, the word-level files) carry
MACULA's attribution as their first line. **The structure files**
(`out/placeholder-*`, `out/structure-*`) **do not.** Their readers expect
every line to be a record. They are not in the public repository (they are
rebuilt from MACULA by `tools/builder/`); on the live site, this file and
[NOTICE](NOTICE) are their attribution.

**One part of MACULA is deliberately not used.** The SDBH and Louw-Nida fields
— `sdbh`, `lexdomain`, `coredomain`, `domain`, `ln` — are UBS
permission-based rather than openly licensed, and are excluded at the point of
reading in `tools/interlinear.py` rather than filtered downstream, so nothing
built here can come to depend on them. They appear in no file in this tree.

### STEP Bible — Tyndale House, Cambridge

Licensed **CC BY 4.0**. In the data repository's own words (its README, read
2026-10-04, which supersedes the older file-header wording this section used
to quote):

> STEPBible Data Repository CC BY 4.0

> Include any part of STEPBible-Data in any software or publications without
> requesting permission

> Refer others to this repository as the source of the data. ... You are
> welcome to make a mirror, so long as it is kept up-to-date and has a link
> back here.

> Credit it to "STEP Bible" linked to www.STEPBible.org

Source: <https://github.com/STEPBible/STEPBible-Data> · <https://www.STEPBible.org>

**What is used.** The Translators Brief lexicons — TBESH (Hebrew, an abridged
Brown-Driver-Briggs) and TBESG (Greek, after Abbott-Smith) — give the lexicon
entry shown on every word card, credited there as they ask. The site's server
fetches them from their repository (`tools/fetch_lexicon.py`) rather than from
ours, as the README asks: refer others to the source. TIPNR (Translators
Individualised Proper Names with all References) tells which of several
people of one name a word means; it is fetched the same way
(`tools/fetch_tipnr.py`), only where the mentions are rebuilt, and what is
committed is the resolver's output naming this project's records
(`out/mentions.jsonl.gz`), not the file. The TAHOT and TAGNT
amalgamated texts are read from disk to derive lemma assignments. None of the
raw files is committed (`data/raw/` is ignored), and neither is
`out/lemma-assignments.json`, which is reproducible with
`python -m bibleont.lemmas`.

**The version read, and when.** STEP Bible's data has no release tags. It is
read from the repository's `master` branch, so the honest record is the date:
- TAHOT and TAGNT: read 2026-08-28;
- the TBESH and TBESG lexicons: read 2026-08-29 here. The live server fetches
  its own copy from their repository when it is set up (`tools/fetch_lexicon.py`);
- TIPNR: read 2026-10-04.

**What this project changed (CC BY 4.0, section 3(a)(1)(B)).**
- **The lexicon entries are shown in STEP Bible's words.** Only their markup
  is turned into plain text: reference tags are removed, and a line break
  becomes " · " (`src/bibleont/lemma.py`).
- **TIPNR is not shown.** It is used to tell people of one name apart, and
  only the result names this project's records.
- **TAHOT and TAGNT are read** to derive which lemma each word is.
- **What travels from here:** the lemma assignments derived from TAHOT and
  TAGNT, carried in `ontology/entities/entities.jsonl` (236 records, each
  credited in its own `lemma_source`). Their lexicons, TIPNR and the raw files
  are fetched from their repository, not redistributed. (This said "nothing of
  theirs is redistributed from here" until 2026-10-22, when the legal seat's
  review of the public repository found the credited lemmas.)

(The BSD 3-Clause licence on github.com/STEPBible/step is their *software's*,
not the data's.)

## A reference lexicon

Not a text of Scripture and not an original-language dataset, so it sits in its
own section rather than being filed with either.

### WordNet — Princeton University

**Unencumbered, and commercial use is granted explicitly.** In its own words:

> WordNet® is unencumbered, and may be used in commercial applications

> Permission to use, copy, modify and distribute this software and database and
> its documentation for any purpose and without fee or royalty is hereby
> granted, provided that you agree to comply with the following copyright
> notice and statements, including the disclaimer, and that the same appear on
> ALL copies of the software, database and documentation, including
> modifications that you make for internal use or for distribution.

> WordNet 3.0 Copyright 2006 by Princeton University. All rights reserved.

> THIS SOFTWARE AND DATABASE IS PROVIDED "AS IS" AND PRINCETON UNIVERSITY MAKES
> NO REPRESENTATIONS OR WARRANTIES, EXPRESS OR IMPLIED.

SPDX identifier: `WordNet`. Source: <https://wordnet.princeton.edu>

**The notice requirement is stricter than CC BY on one point** — it covers
modifications made *for internal use*, not only for distribution. So
`out/wordnet-map.jsonl.gz` carries the attribution as its own first line, the
same way the MACULA extracts do, and would even if it never left this machine.
The public repository carries WordNet's verb classes in
`ontology/relations/verb-statements.jsonl` (each row's `family`, marked
`"family_from": "WordNet, through the English"`), so its notice, disclaimer
included, is reproduced in full in [NOTICE](NOTICE).

**One restriction that is not about copying.** Princeton's name may not be used
"in advertising or publicity pertaining to distribution of the software and/or
database". Attribution here, and in the `_source` line of the derived file, is
compliance rather than publicity — but any release announcement has to respect
the distinction.

What it is used for: a coarse semantic class per Hebrew and Greek lemma, reached
through MACULA's own English glosses. `docs/PRINCIPLES.md` 44a sets out why this
is permitted — the source records no taxonomy, so an external judgement is the
only evidence available — and the three conditions attached to it. **It is an
overlay and never the floor.** Where it disagrees with MACULA, MACULA wins, and
every row carries the English gloss it was derived from so a reader can discount
it.

## Software and typefaces the site ships

- **Cytoscape.js** (MIT licence) draws the Knowledge Graph Navigator;
  <https://js.cytoscape.org>. Its notice is kept in the file served.
- **Mermaid** (MIT licence) draws the verse-structure diagrams;
  <https://mermaid.js.org>. Its bundled file does not carry its own notice,
  so its LICENSE, fetched from their repository at the release shipped (tag
  `mermaid@11.17.2`), is served beside it:
  `app2/static/vendor/mermaid-11.17.2-LICENSE.txt` (Copyright (c) 2014 - 2022
  Knut Sveidqvist).
- **Spectral** (Production Type), **IBM Plex Mono** (IBM) and **Noto Serif
  Hebrew** (Google), under the SIL Open Font License 1.1, served from the
  site. Each font's licence, with its own copyright line, is served beside it
  (`app2/static/vendor/fonts-2026-10-01/OFL-*.txt`). They were fetched
  2026-10-18: Spectral's from Google Fonts' repository (google/fonts,
  ofl/spectral), IBM Plex's from IBM/plex, and Noto Serif Hebrew's from
  notofonts/hebrew.
- **Until 2026-10-18 the Mermaid licence above was not actually served.**
  The server answers only for the kinds of file the site is made of, and a
  `.txt` was not one of them. It now also serves a `.txt` under `vendor/` whose
  name says it is a licence, and nothing else new.

## Rebuilding the corpus

The raw downloads are not in this repository — they are large and they are
reproducible. `python -m bibleont.acquire` carries the source URLs and the
normalisation, including the three quirks that had to be handled to align them:
eBible's older book codes, differing book-name conventions, and the World
English Bible numbering the Romans doxology at 14:24-26 where the King James
has 16:25-27.

## What is not here

No copyrighted translation, and none is planned. Not the NIV, ESV, NASB, NLT
or any other text under an active licence — including for internal comparison,
where a licence would still be required and where "we only used it to check"
is not a defence anyone should have to make.

**This section used to say "comparison against the Greek and Hebrew is not
done." That stopped being true** when the MACULA layer was added, and the
sentence is corrected rather than quietly deleted, because a licence page that
understates what a project consumes is worse than one that says nothing. The
original languages are now read, under the terms set out above.

---

Questions about anything on this page: bible.ontology@gmail.com
