# Bible Ontology

A knowledge graph of what the text of the Bible says: its people, places,
events and claims. Each relation rests on the verses that establish it and is
credited to the voice that makes it. Clauses are read from the Hebrew and
Greek (MACULA's syntax trees), and the text shown is the Berean Standard Bible.

**Why the voice matters.** Most of the book of Job is speeches, and at the end
God rebukes Job's friends: "you have not spoken about Me accurately" (Job
42:7). A graph that stores Eliphaz's "your own mouth condemns you" (Job 15:6)
as a fact publishes a speaker's charge as the book's own verdict. So here
every relation is a claim with its speaker, and only what the narrator states
or entails is asserted as a plain triple (verb statements aside: see below).

- **Reading the Bible?** Start at the site, **https://bibleontology.org**. Its
  [About page](https://bibleontology.org/about) explains what it is, in plain
  words.
- **Working with RDF?** Start with [the schema as a map](https://bibleontology.org/ns/map)
  and [RDF 1.2 in practice](docs/rdf-1.2-in-practice.md), then the data
  below.

This repository holds the graph, its published vocabularies, the code that
builds and checks it, and the site itself. It begins at its first public
release, a fresh export by design; what changed in each release is in
`CHANGELOG.md`.

```
Job, blameless and upright             Job 1:1       the narrator: asserted
Job, his iniquities endless            Job 22:5      Eliphaz: recorded as his claim, not asserted
Saul loved David                       1 Sam 16:21   the narrator, outright: described with its verb, not asserted
```

The last of those, as it appears in the RDF 1.2 export (in full):

```turtle
c:bd10755012089fc7 a claim:Claim ;
    rdf:reifies <<( e:saul bor:states e:david )>> ;
    claim:subject e:saul ; claim:relation bor:states ; claim:object e:david ;
    claim:verse p:1Sam.16.21 ;
    claim:certainty claim:explicit ;
    claim:readBy "lifted from the clause: two judges, every end checked" ;
    claim:reader <https://bibleontology.org/reader/judges-lift-2026-10-19> ;
    prov:wasAttributedTo <https://bibleontology.org/reader/judges-lift-2026-10-19> ;
    prov:wasGeneratedBy <https://bibleontology.org/run/lift-2026-10-19> ;
    claim:verbLabel "loved" ;
    claim:verb <https://bibleontology.org/word/h157> ;
    claim:stem "qal" ;
    claim:mood "wayyiqtol" ;
    claim:person "third" ;
    claim:negated false ;
    claim:modality claim:modality_stated ; claim:modalityFrom "form" ;
    claim:family claim:family_verb_emotion ; claim:familyFrom "WordNet, through the English" ;
    claim:clause <https://bibleontology.org/structure/1Sam.16.21#cl2> ;
    claim:voice claim:narrator .
```

`bor:states` is one relation for every verb; the verb is on the claim. So a
verb statement is described and never asserted, even the narrator's: a
verbless `e:saul bor:states e:david` would be shared by every sentence with
Saul as subject and David as object, whoever said it. The claim names the
models that lifted it from the clause (the reader and the run).

## What is in it

- **About 11,500 records and 21,400 claims** (2026-10-22; the site's About
  view counts them live). About 8,400 of the records are people, places,
  concepts and the like; the rest are events, themes, story patterns and the
  passages that tell them. Every claim carries its verses, its certainty and
  its voice.
- **Claims, not facts.** Every claim reifies a triple term (`rdf:reifies`). Only
  what the narrator states or entails (certainty explicit or implied) is
  also asserted. What a character says is recorded as that character's claim
  and never comes back as the text's own fact. Conjectures, disputed claims
  and the graph's own groupings (themes, patterns, story links, the text's
  divisions) are credited to the editors and never asserted, and so is every
  verb statement (`bor:states`, above). Readings by
  people or models are marked as readings, with who made them.
  `tests/test_assertion_policy.py` checks this in the published files.
- **Structure from the original languages.** Clauses and the links between
  them (because, so that, until) are built by rule from MACULA's syntax trees,
  not from an English translation. Speech turns and their speakers are read
  from those clauses by models and recorded as readings.
- **Published vocabularies** at [bibleontology.org/ns](https://bibleontology.org/ns/meaning):
  meaning, structure, relations, claims and SHACL shapes. They extend PROV-O,
  SKOS, OntoLex and DQV, and an alignment file maps them to schema.org, FOAF,
  CIDOC CRM, OntoLex and Web Annotation (SKOS mappings, none exact).

Namespaces: `bom:` `https://bibleontology.org/ns/meaning#`, `bor:`
`…/ns/relation#`, `bos:` `…/ns/structure#`, `claim:` `…/ns/claim#`. Records
are `https://bibleontology.org/e/…`. The vocabulary addresses return Turtle
by content negotiation; record addresses open the site's pages; claim and
dataset addresses are identifiers only.

**Stability.** The vocabularies are at version 1.2.1. A term's address is never
reused, and every release is kept at a dated address (`out/ns/versions/`).
Record addresses can still be renamed; a renamed record's old page redirects.

## Three ways in

### 1. Use the published data (nothing to install)

| File | What it is |
|---|---|
| `out/export/claims-rdf12.trig.gz` | every claim, RDF 1.2: each a triple term, the narrator's statements also asserted |
| `out/export/claims.trig.gz` | the same, RDF 1.1: one named graph per voice |
| `out/export/entities.ttl.gz` | every record a claim can name, with its name, and its class where one maps |
| `out/export/ties.trig.gz` | how strongly records are tied, with each tie's measure |
| `out/export/card-words.trig.gz` | the words on each card, each with its measure and whether it is shown |
| `out/export/*.rq` | SPARQL that rebuilds two of the site's views from those files: the navigator's first view and the card words shown |
| `out/export/void.ttl` | the exports described in VoID and DCAT |
| `out/ns/*.ttl` | the vocabularies, the SHACL shapes and the alignment |

The RDF 1.1 files read in any store or library (Jena, RDF4J and rdflib
checked). The RDF 1.2 file needs a parser with triple terms: Apache Jena 6.2
and RDF4J 6.1 were checked; rdflib cannot read it yet. In the RDF 1.2 file the
narrator's triples are the default graph. In the RDF 1.1 file each voice is its
own named graph and the default graph holds the claims, so query
`GRAPH claim:narrator` for what the text states. Beware a store whose default
graph is the union of all graphs (RDF4J's is): there, an unscoped pattern
also matches every speaker's and reader's graph.

**[RDF 1.2 in practice](docs/rdf-1.2-in-practice.md)** walks through why, on
real data. The same plain query gets 0 rows from Jena and 32 from RDF4J on
the RDF 1.1 file, and 8 from both on the RDF 1.2 file. It includes the Turtle,
the SPARQL and how to reproduce it (the queries are in `tools/rdf12/`).

- **Symmetric relations are stored once.** `spouse_of`, `sibling_of`,
  `companion_of` and the other symmetric relations are stored in one
  direction only, and nothing is inferred (the vocabularies' reasoning policy).
  So ask both ways: `{ ?x bor:spouse_of ?y } UNION { ?y bor:spouse_of ?x }`.
- **The shapes pass on these files.** `out/ns/shapes.ttl` and
  `relation-shapes.ttl` report no violation over the claims, the records and
  the meaning vocabulary; `tests/test_export_shapes.py` checks it.

### 2. Run the site

Python 3.11 or later, and PyYAML:

```bash
pip install pyyaml
```

```bash
python app2/server.py
```

Then open http://localhost:8001. The first start builds its indexes and takes
a few minutes; the running site needs about 2 GB of memory. The built files the site reads are in this repository (the
list, measured, is `deploy/runtime-inputs.txt`), so no build step is needed.
The lexicon entries on word cards come from STEP Bible and are fetched, not
shipped: `python tools/fetch_lexicon.py` adds them.

### 3. Check it, and rebuild it

```bash
pip install -e ".[rdf]"
```

```bash
python -m bibleont.validate
```

The validator checks every record and relation: each cited verse exists and
names the parties, identities are not fused, and the vocabulary is closed. It
should end with 0 errors; its warnings are leads for review, not failures.
Many of the tests in `tests/` plant a fault and fail if a check stops catching
it. `python tools/run_tests.py` runs them; `--all` adds the few that load the
whole site (a few minutes each, about 2 GB of memory). One suite is known red:
`tests/test_verse_structure.py` fails 144 checks since the October structure
rebuilds and is being diagnosed. (`deploy/preflight.sh` is the check before a
deploy of the live site, and needs its remote.) How to send a finding, and
what "green" means for a change: `CONTRIBUTING.md`. What changed in each
release: `CHANGELOG.md`.

The structure layer rebuilds from MACULA. `python tools/fetch_macula.py --all`
downloads the pinned release (`data/macula-manifest.json` records its
checksums, and a changed download stops rather than re-pinning), then
`python tools/builder/build.py --install` builds it (the old graph is kept;
`--restore` puts it back). The live structure is
`out/placeholder-{nodes,edges,readings}.jsonl.gz`: the name is historical, from
the structure this builder replaced. The readings that models made
(judged passes) are not rebuilt this way. They are published as data, and each
pass's per-item trail is in `ontology/provenance/`.

**Size.** A clone is about 260 MB, mostly the site's built files in `out/`,
which are not a stable interface. For the data alone, `out/export/` is 2.4 MB.
Code comments sometimes cite design notes that are not in this repository.

## What it does not do

- **No doctrine.** It records structure and who says what. Where a link is an
  interpretation, it is marked as a reading and credited.
- **No resolving tensions the text leaves open.** Where two passages differ,
  both are kept and the difference is noted.
- **No reasoning over contradictions or revisions.** Claims that disagree sit
  side by side, each with its voice.
- **No copyrighted translation.** The English shown is the Berean Standard
  Bible (public domain). The ASV, WEB and YLT are used for comparison.

How it is built, and the rules it holds to, are in
[docs/PRINCIPLES.md](docs/PRINCIPLES.md): each rule with the case that
established it and the case that would break it.

## Sources

The Hebrew and Greek structure is MACULA's:

> MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/
>
> MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/

© Biblica, Inc., CC BY 4.0. Biblica does not endorse this project. STEP Bible
(Tyndale House) and WordNet are used too. [NOTICE](NOTICE) carries
the notices that travel with every copy; [SOURCES.md](SOURCES.md) says what
was read from each and what was changed.

## Licence and reuse

The code is under the [Apache License 2.0](LICENSE). The graph, the
vocabularies and the written material are under
[CC BY 4.0](LICENSE-DATA). [LICENSING.md](LICENSING.md) gives the map, folder
by folder.

Reuse of any kind is welcome, including training AI systems: the graph and the
writing under CC BY 4.0, the code under Apache-2.0, and the sources under their
own terms (NOTICE), most of which ask for attribution. Credit:
*Bible Ontology by Doug Egge (bibleontology.org)*. To cite it, see
[CITATION.cff](CITATION.cff).

## The name

An earlier Bible Ontology (bibleontology.com, about 2009–2011) published one
of the first Bible graphs as linked data, with a SPARQL endpoint and links to
DBpedia. This project is independent of it and not affiliated with its
authors, and gratefully acknowledges that earlier work.

## Contact

bible.ontology@gmail.com. Issues are welcome, and pull requests by invitation
([CONTRIBUTING.md](CONTRIBUTING.md)); replies may take a few days. Contributions are accepted under the licence of the files
they change.
