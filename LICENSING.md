# Terms

**Two licences, by kind of work.** Credit for either: *Bible Ontology by Doug
Egge (bibleontology.org)*.

- **The code** is under the [Apache License, Version 2.0](LICENSE).
- **The graph, the vocabularies and the written material** are under
  [Creative Commons Attribution 4.0 International](LICENSE-DATA) (CC BY 4.0).
- **The texts and data this project draws on** keep their own terms, which no
  file here changes: see [NOTICE](NOTICE) for the notices that travel with
  every copy, and [SOURCES.md](SOURCES.md) for the full account.

## Folder by folder

| Path | What it is | Licence |
|---|---|---|
| `app2/` (except `app2/static/vendor/`) | the site: its server and its pages | Apache-2.0 |
| `app2/static/vendor/` | Cytoscape.js and Mermaid (MIT); Spectral, IBM Plex Mono, Noto Serif Hebrew (SIL OFL 1.1) | their own, kept beside each file |
| `src/`, `tools/`, `tests/`, `deploy/`, `pyproject.toml` | the library, the build and checking tools, the tests, the deployment | Apache-2.0 |
| `ontology/` | the records, relations, schema, vocabularies' sources, themes, and the provenance of judged passes | CC BY 4.0 |
| `ontology/relations/verb-statements.jsonl` | as above; its verb classes come from WordNet | CC BY 4.0, with WordNet's notice (NOTICE) |
| `ontology/entities/entities.jsonl` | as above; 236 records carry lemmas derived from STEP Bible, each credited in its record | CC BY 4.0, with STEP Bible's credit |
| `out/ns/` | the published vocabularies, their pages, the map and the alignment | CC BY 4.0 |
| `out/export/` | the published claims, card words, ties and typed records, and their VoID/DCAT description; the claims carry WordNet verb classes | CC BY 4.0, with WordNet's notice (NOTICE) |
| `out/sweep/speaker-credits*` | who says each speaker's line, credited by the sweep | CC BY 4.0 |
| the rest of `out/` | the site's built files (`deploy/runtime-inputs.txt`), many derived from MACULA; not a stable interface | CC BY 4.0, with MACULA's attribution where derived (NOTICE) |
| prose and readings inside the code folders (the site's pages and blog, `tests/*.json`, `tests/*.txt`) | written material that lives with the code | Apache-2.0 with its folder, and also CC BY 4.0, at the reuser's choice |
| `data/macula-*` | extracts derived from MACULA | CC BY 4.0, (c) Biblica, Inc.: MACULA's attribution first (NOTICE) |
| `data/bible/verses.{bsb,asv,web,ylt}.jsonl` | the Berean, ASV, WEB and YLT | public domain |
| `README.md`, `SOURCES.md`, `docs/PRINCIPLES.md` | the written material | CC BY 4.0 |
| `LICENSE`, `LICENSE-DATA`, `NOTICE` | the licence texts and notices | as they state |

## Why these licences

**The graph under CC BY 4.0.** Anyone may share and adapt it, commercially
too, with credit. It fits the project's reasoning: the work is built on texts
nobody owns, its whole argument is that a reader can check it themselves, and
a claim that can be checked is more useful the more freely it travels.
Attribution is asked because the selection and arrangement are the work. (CC0
was weighed and set aside: it would give up the attribution that is the
point.)

**Reuse by machines is welcome.** That includes search and answer engines and
the training of AI systems: a CC BY repository can be read by anyone, and the
licence asks only for the credit. The live site's `robots.txt` admits the
crawlers that cite their sources and turns away the ones that do not; that is
the site's preference about its pages, and it does not narrow this licence.

**The vocabularies took the same licence first** (granted 2026-10-17, version
1.1.1): a vocabulary is only useful if others may use its terms in their own
data. Attribution travels with it in the namespace and the metadata
(`dcterms:license` and `dcterms:rights` in every file).

**The code under Apache-2.0.** A permissive licence, so the tools can be used
on another corpus; the Apache licence adds an explicit patent grant and keeps
the NOTICE file with every copy.

**Why the order.** A Creative Commons licence cannot be withdrawn from copies
already taken, so it is granted deliberately: the vocabularies once their
files could be downloaded, the graph and the code when this repository was
published.

## What is not mine to license at all

Notes and profiles written by readers of the site. Those are theirs, held in
confidence, are not in this repository, and no licence chosen here applies to
them or makes them available to anyone. A note is read by the site's owner
and by the tools he builds with, and goes no further unless the person who
wrote it chooses to share it.

---

*Nothing in this file is legal advice, and none of it has been reviewed by a
lawyer.*

Questions about anything on this page: bible.ontology@gmail.com
