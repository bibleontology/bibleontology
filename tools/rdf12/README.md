# Checking the claim export in Apache Jena and RDF4J (plan 8.1a)

`tools/export_claims.py` writes `out/export/claims.trig` (RDF 1.1) and
`out/export/claims-rdf12.trig` (RDF 1.2). These are the checks that showed
both files parse and answer correctly, and what to rerun after a change.

## Setup (outside the project, e.g. `C:\tmp\rdftools`, 2026-10-14)

| Tool | Version | Needs |
|---|---|---|
| Apache Jena | 6.2.0 (`apache-jena-6.2.0.zip`, sha512 checked) | Java 21 (Eclipse Temurin 21) |
| Eclipse RDF4J | 6.1.0 SDK | **Java 25**: its classes are version 69; Java 21 refuses them ("wrong version 69.0, should be 65.0") |

Jena's `bin/riot` script does not run under Git Bash on Windows ("Could not
find or load main class riotcmd.riot"): call Java directly with a Windows
classpath:

```
java -cp "C:\tmp\rdftools\apache-jena-6.2.0\lib\*" riotcmd.riot --validate claims-rdf12.trig
java -cp "C:\tmp\rdftools\apache-jena-6.2.0\lib\*" arq.sparql --data=claims-rdf12.trig --query=q-eliphaz.rq
javac -cp "C:\tmp\rdftools\eclipse-rdf4j-6.1.0\lib\*" Rdf4jCheck.java
java  -cp "C:\tmp\rdftools\eclipse-rdf4j-6.1.0\lib\*;." Rdf4jCheck claims.trig claims-rdf12.trig
```

## The queries

- `q-eliphaz.rq`: who claims what about Job, through RDF 1.2 triple terms
  (`?c rdf:reifies <<( e:job ?relation ?object )>>`).
- `q-default.rq`: a plain query with no graph named: what is Job described as?
- `q-asserted.rq`: where is Eliphaz's verdict (Job 15:6) asserted?
- `q-asserted-nil.rq`: the same, restricted in RDF4J to the unnamed graph
  (`FROM <http://rdf4j.org/schema/rdf4j#nil>`).

## What they showed (2026-10-14)

- **Both files parse in both tools.** Statement counts differ slightly between
  a stream count and a deduplicated set (Jena `riot --count` 180,096 for the
  1.1 file; RDF4J's Model 180,093; rdflib 180,088): two claims with the same
  triple and different verses put the same triple in a voice graph twice.
- **The default graph is not the same thing in the two stores.** With the
  speakers' triples in named voice graphs, a plain `q-default.rq` returned
  **0** in Jena (its default graph is the unnamed one) and **39** in RDF4J
  (by default, the union of all graphs), Eliphaz's verdict among them.
  Restricting RDF4J to `rdf4j:nil` gave 0.
- **So the RDF 1.2 file asserts only the narrator.** A speaker's or reader's
  claim exists there only as the unasserted triple term its claim
  `rdf:reifies`. After that change both stores answer `q-default.rq` with
  **17** (the narrator's), `q-asserted.rq` with nothing, and `q-eliphaz.rq`
  with each speaker's claim credited to the speaker. The RDF 1.1 file keeps
  the voice graphs; there, the reader of the data must name the narrator's
  graph.

## 2026-10-18: the sweep's speakers (plan 8.1c)

67 claims gained a speaker from the structure sweep's speech turns, each with
`claim:readBy "automated analysis: ..."`. Rerun as above (RDF4J from this
folder, which holds the queries, with full paths to the data):

- Both files parse in both tools (RDF4J: 180,231 statements in 77 graphs;
  198,773 in the RDF 1.2 file).
- `q-default.rq`: **17 → 15** in both stores. The two that left are God's
  words about Job in Job 2:3, which the narrator had been asserting.
- `q-asserted.rq`: still nothing. Eliphaz's verdict is asserted nowhere.

## 2026-10-18: speech within speech (plan 8.1d)

Words one speaker gives another are the inner speaker's as reported by the
outer one. The inner claim's triple is stated (RDF 1.1) in a voice of its
own, `voice/<reporter>/reports/<speaker>`, neither speaker's. The reporter's
own claim is `claim:says`, and in RDF 1.2 it reifies a nested triple term:

```
c:… rdf:reifies <<( e:god claim:says <<( e:shallum… bor:father_of e:hanameel… )>> )>> ;
    claim:claimedBy e:jeremiah .
```

`q-reported.rq` finds it through the nesting. Both Jena 6.2 (`riot
--validate`, `arq.sparql`) and RDF4J 6.1 parse both files and return the same
row (Jeremiah 32:7). `q-default.rq` is still 15 in both.

**Changed 2026-10-19 (plan 8.1e item 4, the committee):** `claim:says` had
two ranges, the inner claim's IRI in the 1.1 file and a nested triple term in
the 1.2 file. Now both files say the reporter says the inner CLAIM, which
reifies its own triple:

```
c:… rdf:reifies <<( e:god claim:says c:inner )>> ; claim:claimedBy e:jeremiah .
c:inner rdf:reifies <<( e:shallum… bor:father_of e:hanameel… )>> .
```

`q-reported.rq` follows the inner claim instead of the nesting. The nested
form above stays as a demonstration for the blog, not the data.

## 2026-10-20: re-run before 1.2.0, done

On the export after the time reading (21,852 claims, 111 of them described
and never asserted), with clause addresses in the verse pages' book codes:

- **Parsing:** `riot --validate` passes both files with no warning (Jena:
  205,391 quads in the 1.1 file, 224,716 in the 1.2 file).
- **Both stores give the same answers:**
  - `q-default.rq` returns **15**, unchanged;
  - `q-asserted.rq` returns nothing, so Eliphaz's verdict is asserted nowhere;
  - `q-reported.rq` returns the one row, Jeremiah 32:7, found through the
    inner claim;
  - `q-prov.rq` returns Job 47, Eliphaz 17, God 8 and Elihu 5, as before;
  - `q-eliphaz.rq` returns each speaker's claim credited to the speaker.

## 2026-10-23: re-run after plan 8.3f, for the public page

On the export after the assertion policy (21,378 claims, 8,103 asserted). `Rdf4jCheck` now queries both files, adding
`q-narrator.rq` (the 1.1 file's right question: name the narrator's graph) and `q-asserted-nil.rq`.
- **Parsing:** Jena counts 227,083 quads in the 1.1 file and 236,463 in the 1.2 file. RDF4J parses the same number of
  statements: 77 graphs, and 1.
- **The 1.1 file:**
  - `q-default.rq` returns **0** in Jena and **32** in RDF4J (its union default graph). The trap still stands.
  - `q-asserted.rq` finds Eliphaz's verdict in RDF4J's "default graph" and in his own voice graph.
  - `q-asserted-nil.rq` returns 0.
  - `q-narrator.rq` returns **8** in both stores.
- **The 1.2 file:**
  - `q-default.rq` returns **8** in both stores. It was 15 before 8.3f: seven triples no longer asserted (groupings,
    conjectures or verb statements).
  - `q-asserted.rq` returns nothing.
  - `q-reported.rq` returns the one row (Jer 32:7).
  - `q-prov.rq` is unchanged (Job 47, Eliphaz 17, God 8, Elihu 5).
- **Written up for practitioners** in `docs/rdf-1.2-in-practice.md`, the page the README and the r/semanticweb post
  link.

## 2026-10-23 (later): re-run on the data released with the public repository

On data 2026.10.23: 21,394 claims, 8,119 asserted. The 16 more are the temple relations added that evening.
- **Parsing:** Jena counts 227,226 quads in the 1.1 file and 236,622 in the 1.2 file. RDF4J parses the same numbers:
  77 graphs, and 1.
- **Every query answers as before, in both stores:**
  - `q-default.rq`: 0 and 32 on the 1.1 file, 8 on the 1.2 file;
  - `q-narrator.rq`: 8 on the 1.1 file;
  - `q-asserted-nil.rq`: 0;
  - `q-asserted.rq`, `q-eliphaz.rq` and `q-reported.rq`: the same rows;
  - `q-prov.rq`: Job 47, Eliphaz 17, God 8, Elihu 5.
- **The page's quad table updated to these.** Its query answers needed no change.
- **Java, for the record:** neither JDK is on Git Bash's path. Call `bin\java` in the JDK 21 folder under
  `C:\tmp\rdftools\` for Jena, and the JDK 25 folder's for RDF4J. (Their full folder names look like IPv4 addresses
  to the public copy's scan, which refused this README once for that.)
