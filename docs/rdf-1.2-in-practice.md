# RDF 1.2 in practice: keeping a speaker's claim from becoming a fact

How to publish what someone said without asserting it: RDF 1.1 named graphs against RDF 1.2 triple terms, on real
data, with SPARQL results from Apache Jena 6.2 and Eclipse RDF4J 6.1.

**In short:**
- RDF 1.1 named graphs can keep each speaker's statements apart. But SPARQL leaves the meaning of the default graph
  to each store, so the same plain query returned 0 rows in Jena and 32 in RDF4J, a speaker's verdict among them.
- RDF 1.2 triple terms let a claim name a statement without that statement being written as an ordinary triple. Both
  stores then return the same 8: the text's own statements.
- Triple terms solve the representation problem. Deciding which claims are the text's own is a separate editorial
  policy, and it needed a test against the published files to be right.

A worked example, with data you can download and queries you can run.

Every number below was measured on 23 October 2026 against the files in `out/export/` of this repository
(vocabularies 1.2.1), in Apache Jena 6.2 and Eclipse RDF4J 6.1. The queries are in `tools/rdf12/`.

## The problem: quoted speech published as fact

In the book of Job, Job's friends argue for chapters that he must have deserved what happened to him. One of them,
Eliphaz, says:

> "Your own mouth, not mine, condemns you; your own lips testify against you." (Job 15:6, Berean Standard Bible)

At the end of the book God rebukes Eliphaz and the other friends: *"you have not spoken about Me accurately"* (Job
42:7). That verdict is on what they said about God, not on this charge in particular, but it leaves the friends'
speeches as theirs, not the book's. A graph that stores Eliphaz's line as a plain triple

```turtle
e:job bor:described_as e:testified_against_by_his_own_lips .
```

has published a speaker's charge as the book's own verdict. Any text with speakers has this problem: a transcript, a
court record, a novel, a news story full of quotations. **Who says something is part of what is said.**

Three things need keeping apart:
1. **the proposition:** Job is condemned by his own mouth;
2. **the character's claim:** Eliphaz says the proposition is true;
3. **the text's own assertion:** what the book presents as its own account, not as someone's words.

RDF 1.2 helps with the first two. The third is an editorial policy, below.

**A word on "asserted".** In RDF, a triple in a graph is asserted. In this document, "asserted" means my
choice to write a claim's triple as an ordinary triple: in the RDF 1.2 file's default graph, or in the RDF 1.1 file's
`claim:narrator` graph. Everything else is published as a claim that names its triple without stating it.

## RDF 1.1: one named graph per voice

The obvious RDF 1.1 answer is to keep each speaker's statements in a named graph of their own, and the text's own
statements (the narrator's) in another. The claims export still ships this form, `out/export/claims.trig.gz`:

```turtle
voice:eliphaz_the_temanite {
    e:job bor:described_as e:testified_against_by_his_own_lips .
    # ...his other claims
}

claim:narrator {
    # what the text itself states
}
```

Each statement also gets a claim node in the unnamed default graph, with its verse, certainty and speaker. The graph
names and what they stand for (one voice each) are conventions of this data model: RDF itself gives a named graph no
speaker and no truth status.

### The trap: the union default graph (RDF4J) against the unnamed default graph (Jena)

Ask the plain question, with no graph named (`tools/rdf12/q-default.rq`):

```sparql
SELECT (COUNT(*) AS ?n) WHERE { e:job bor:described_as ?o }
```

| Store | Matching triples, RDF 1.1 file | Why |
|---|---|---|
| Jena 6.2 | **0** | its default graph is the unnamed graph, which holds only the claim nodes |
| RDF4J 6.1 | **32** | its default graph is the **union of all graphs**: its documented default, since SPARQL leaves the default graph to the store (GraphDB, and Jena's TDB2 with `unionDefaultGraph`, can do the same) |

The 32 are 32 different descriptions of Job, from five voices:
- Job's own words, 14;
- the narrator, 8;
- Eliphaz, 5;
- God, 4;
- Elihu, 1.

In RDF4J, Eliphaz's verdict comes back from the default graph as if the text said it (`q-asserted.rq` finds it there).
RDF4J can be told to use only the unnamed graph (`FROM <http://rdf4j.org/schema/rdf4j#nil>`, `q-asserted-nil.rq`: 0).
But then the protection lives in each consumer's query and each store's settings, not in the data. A careful reader
is safe; a casual one is not.

The right RDF 1.1 question names the narrator's graph (`q-narrator.rq`), and both stores answer **8**:

```sparql
SELECT (COUNT(*) AS ?n) WHERE { GRAPH claim:narrator { e:job bor:described_as ?o } }
```

## RDF 1.2: triple terms and rdf:reifies

**RDF 1.1 reification** (`rdf:Statement` with `rdf:subject`, `rdf:predicate` and `rdf:object`) can already describe a
statement without asserting it, but it needs a separate resource and three properties for every claim. **RDF 1.2**
provides a **triple term**, `<<( s p o )>>`, which a claim can point at directly with `rdf:reifies`.

**W3C status, as of 23 October 2026:**
- RDF 1.2 Concepts: a Candidate Recommendation Snapshot, 7 April 2026;
- RDF 1.2 Turtle and TriG: Working Drafts, 7 October 2026;
- SPARQL 1.2 Query: Working Draft, 11 October 2026.

The files and queries here use all four, so this is early-adopter work.

The same claim in `out/export/claims-rdf12.trig.gz`, abridged. The claim also carries `claim:subject`,
`claim:relation` and `claim:object`, which SHACL checks. The RDF 1.1 file has the same claim nodes with those three
properties and no triple term, so a tool that cannot parse RDF 1.2 can use that file instead.

```turtle
c:3a11f4736068231d a claim:Claim ;
    rdf:reifies <<( e:job bor:described_as e:testified_against_by_his_own_lips )>> ;
    claim:verse p:Job.15.6 ;
    claim:certainty claim:explicit ;
    claim:claimedBy e:eliphaz_the_temanite ;
    prov:wasAttributedTo e:eliphaz_the_temanite ;
    claim:voice voice:eliphaz_the_temanite .
```

The triple term is not a triple in the graph, so nothing matches `e:job bor:described_as ?o` against it. **Only the
narrator's asserted claims are also written as plain triples, in the default graph**, so a plain question cannot reach
Eliphaz in either store.

**What this does and does not guarantee:**
- **The comparison is not quite like for like.** The 1.2 file is safe partly because it has no speaker graphs left:
  the speakers' triples exist only as triple terms.
- **The guarantee is for plain-triple queries.** Anyone who queries the claim nodes' `claim:subject`,
  `claim:relation` and `claim:object` without looking at `claim:voice` will read speakers' claims as facts, in either
  file.
- **RDF 1.2 can also assert a triple and annotate it in one step,** with the annotation syntax `{| ... |}`. The safety
  comes from how this data uses triple terms (only through `rdf:reifies`), not from the feature itself.

That is why the test below counts the published file and does not trust the exporter's code.

**Every query, both files, both stores:**

| Query | RDF 1.1, Jena | RDF 1.1, RDF4J | RDF 1.2, Jena | RDF 1.2, RDF4J |
|---|---|---|---|---|
| `q-default.rq`: Job `described_as` ?o, no graph named | 0 | 32 | 8 | 8 |
| `q-narrator.rq`: the same, in `GRAPH claim:narrator` | 8 | 8 | 0 (no such graph) | 0 |
| `q-asserted.rq`: where is Eliphaz's verdict asserted? | Eliphaz's graph | Eliphaz's graph, and the default graph | nowhere | nowhere |
| `q-asserted-nil.rq`: the same, RDF4J's unnamed graph only | — | 0 | — | 0 |
| `q-eliphaz.rq`: who claims what about Job, by triple term | none (no triple terms) | none | each claim, with its speaker | the same |
| `q-reported.rq`: speech within speech | none | none | 1 row (Jer 32:7) | the same |
| `q-prov.rq`: attributions of claims about Job | the same in all four | | | |

`q-eliphaz.rq` is how you ask *for* the speakers, deliberately:

```sparql
SELECT ?speaker ?relation ?object ?verse WHERE {
  ?c rdf:reifies <<( e:job ?relation ?object )>> ;
     claim:claimedBy ?speaker ;
     claim:verse ?verse .
}
```

**Triple terms solve the representation problem, not the editorial one.** The graph still needs an explicit policy for
which claims are written as the text's own statements.

## The editorial policy: what "the narrator's" means

**The narrator** is the name I use for the book's own voice: the storyteller in a narrative, and the writer where
a book has no narrator (a letter, a psalm). Characters who speak inside a book have voices of their own. The published
claims have not fully caught up with that: part of Titus is credited to Paul, while the rest of Titus, and Galatians,
sit in the narrator's voice.

**What is asserted:** a narrator claim whose certainty is
- **explicit**, which the verse states in so many words: "this man was blameless and upright" (Job 1:1); or
- **implied**, which the verse entails without saying it: 1 Samuel 17:13 names Eliab and Abinadab among Jesse's sons,
  so they are recorded as brothers.

**Never asserted:**
- a conjectured or disputed claim, in any voice;
- the graph's own groupings (themes, pattern instances, "these two stories follow the same steps"), credited to an
  editors' voice;
- a command, promise, question or wish;
- any `bor:states` triple. That one relation carries every verb, with the verb on the claim, so as a plain triple two
  different sentences with the same subject and object would be the same statement.

**How the policy was found wrong, and checked since.** Before publishing, I counted what the RDF 1.2 file asserted
and found it wrong. Anything not credited to someone else had been given to the narrator by default: 18,701 asserted
triples. After the fix, 8,103 were asserted (8,119 today: the 16 relations added since are the narrator's). Of the
roughly 10,600 no longer asserted, about 9,600 were the graph's own
groupings, about 570 were conjectured or disputed, and the rest were verb statements.
`tests/test_assertion_policy.py` checks the rule in the published files, not in the code, and must catch six planted
faults:
1. a theme link in the narrator's graph;
2. a conjecture asserted;
3. a disputed claim asserted;
4. a grouping claim given the narrator's voice;
5. the RDF 1.2 file asserting what the 1.1 file does not;
6. a `states` triple asserted.

**One known fault the test does not see:** some claims inside speeches (one clause grounding another, a speaker's
simile) still sit in the narrator's voice, so they are asserted. Job has 83, 14 of them Eliphaz's in chapter 15. The
test checks a claim's certainty and relation, not where in the text it sits.

## Speech within speech, and PROV

Two more queries show the rest of the model:
- **`q-reported.rq`: speech within speech.** In Jeremiah 32:7, Jeremiah reports God's words: "Hanamel, the son of
  your uncle Shallum, is coming to you". So the claim that Shallum is Hanamel's father is God's, as Jeremiah reports
  it. Jeremiah's own claim is that God says it:

  ```turtle
  c:0eec4091e97b5f0b a claim:Claim ;
      rdf:reifies <<( e:god claim:says c:0c315a2131b92d6d )>> ;
      claim:claimedBy e:jeremiah ;
      claim:voice voice:jeremiah .
  c:0c315a2131b92d6d a claim:Claim ;
      rdf:reifies <<( e:shallum_father_of_hanameel bor:father_of e:hanameel_son_of_shallum )>> ;
      claim:claimedBy e:god ;
      claim:voice <https://bibleontology.org/voice/jeremiah/reports/god> .
  ```

  The verse has a third layer that is not modelled: Hanamel's own words, as God predicts them ("Buy for yourself my
  field in Anathoth").
- **`q-prov.rq`: who said what, with no reasoner.**
  - `claim:claimedBy` and `claim:reader` are sub-properties of `prov:wasAttributedTo`, and the export writes the PROV
    triple out too.
  - So a PROV-aware tool can see who the claims about Job are attributed to: Job (the character) 47 claims, Eliphaz
    17, God 8, Elihu 5, Zophar 1, the devil 1.
  - Two judging runs are listed too. A claim whose speaker was found by a model is attributed to both the speaker and
    the run, so the counts overlap. The runs are `prov:Activity` nodes in the export (`/run/sweep-2026-10-17` and
    `/run/lift-2026-10-19`), each naming its models.
  - This co-attribution is the third open question below.

## Reproduce it in Apache Jena and RDF4J

From the repository's root:

```bash
gzip -dk out/export/claims.trig.gz out/export/claims-rdf12.trig.gz
```

**Jena 6.2** (Java 21):

```bash
riot --validate --count out/export/claims.trig out/export/claims-rdf12.trig
arq --data=out/export/claims-rdf12.trig --query=tools/rdf12/q-eliphaz.rq
```

**RDF4J 6.1** (Java 25: its classes need it). `tools/rdf12/Rdf4jCheck.java` loads each file into a memory store and
runs every query in turn. Run it from `tools/rdf12/`, where the queries are, with the RDF4J SDK's `lib` folder on the
classpath:

```bash
javac -cp "<rdf4j>/lib/*" Rdf4jCheck.java
java -cp "<rdf4j>/lib/*:." Rdf4jCheck ../../out/export/claims.trig ../../out/export/claims-rdf12.trig
```

(On Windows the classpath separator is `;`.)

**Expected results:**

| File | Jena quads |
|---|---|
| `claims.trig` (RDF 1.1) | 227,226 |
| `claims-rdf12.trig` (RDF 1.2) | 236,622 |

The 9,396 more in the RDF 1.2 file are the difference of form. It carries one `rdf:reifies` per claim (21,394) and
the 8,119 asserted triples, in place of the RDF 1.1 file's 20,117 triples in 76 named graphs. The queries' expected
answers are in the table above.

rdflib 7.6 (Python) reads the RDF 1.1 file but not the 1.2 one: its TriG parser does not accept the `<<( ... )>>`
triple term syntax.

## Open questions

- **Event nodes, or a verb on the claim?** `bor:states` with the verb on the claim keeps one relation for all verbs, at
  the price of never asserting them. The claim already carries the verb and both parties. The open question is whether
  the event gets a node of its own, apart from the claims that record it, so two books can describe one event.
- **One narrator, or one per book?** Two books tell the same census and name different instigators (2 Samuel 24:1,
  1 Chronicles 21:1). Neither instigator is recorded yet. With one narrator it would be one disputed claim; with one
  per book, two narrators disagreeing.
- **Is `prov:wasAttributedTo` right for a speaker in a text?** It makes a character and a model run co-attributed
  agents of the same record. `prov:wasQuotedFrom` a speech turn may fit better.

Issues on the repository are welcome (`CONTRIBUTING.md`).
