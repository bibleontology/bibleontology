# Extraction brief

You are extracting **person-to-person relationships** from the Bible into a
citation-backed knowledge graph. Everything you record must be traceable to a
verse. Nothing you record may come from memory, commentary, or tradition — only
from the text in front of you.

## Your inputs

- `data/bible/text/<BOOK>.txt` — the KJV text of your assigned book, one verse
  per line, tab-separated: `Gen 5:3<TAB>And Adam lived an hundred and thirty...`
  The reference at the start of each line is exactly the citation string to use.
- `ontology/schema/relationship_types.yaml` — the **only** relationship types you
  may use. Read it before you start. Do not invent types.

## Your outputs

Write exactly two files into your assigned batch directory:

### `persons.jsonl` — one JSON object per line

```json
{"id":"solomon","name":"Solomon","aka":["Jedidiah"],"gender":"m","roles":["king"],"tribe":"Judah","era":"united_monarchy","desc":"Son of David and Bathsheba; third king of Israel.","refs":["2Sam 12:24"],"disambiguation":"son of David","source":"batch-2sam"}
```

- `id` — lowercase, ASCII, underscores: `bath_sheba`, `jeroboam_son_of_nebat`.
  When a name is shared by several people (there are many Zechariahs), qualify
  the id and fill in `disambiguation`.
- `refs` — one or two verses that introduce the person.
- Every person mentioned in `relations.jsonl` must appear here.

### `relations.jsonl` — one JSON object per line

```json
{"src":"david","type":"father_of","dst":"solomon","refs":["2Sam 12:24"],"certainty":"explicit","note":"","source":"batch-2sam"}
```

- `src`/`dst` — person ids. Direction matters: read it as
  "*src* «label» *dst*" using the `label` from the vocabulary.
  `father_of` means src **is the father of** dst.
- `type` — must exist in `relationship_types.yaml`.
- `refs` — the verse(s) that establish this relationship, in the exact
  `Book C:V` or `Book C:V-V` form used in the text files. **Cite the verse that
  shows the relationship, not the verse where you first thought of it.**
- `certainty` — one of:
  - `explicit` — the verse says it.
  - `implied` — the verse entails it, e.g. two men called sons of one father are
    therefore brothers.
  - `conjectured` — neither stated nor entailed, but the most reasonable reading.
    **Use this rather than staying silent** when the honest answer is "probably,
    and here is why". The `note` must carry the reasoning *and* name the doubt:
    what makes it likely, and what would overturn it. An annotated best reading
    helps a reader; an unmarked assertion misleads them; a gap tells them
    nothing. If you find yourself about to drop something because you are not
    certain, this is the field for it.
  - `disputed` — readings genuinely differ, or parallel passages disagree.
    Distinct from `conjectured`: disputed means the evidence pulls two ways,
    conjectured means it points one way without settling.
- `note` — only when it adds something: an indirect agency, a parallel passage
  that disagrees, a qualification.
- For **symmetric** types (`sibling_of`, `spouse_of`, `ally_of`, `friend_of`,
  `enemy_of`, `companion_of`, `co_regent_with`, `betrothed_to`, `half_sibling_of`)
  record the pair **once**, with the alphabetically smaller id as `src`.

## Rules

1. **Only people.** Not tribes, nations, cities, or angels. God, the Holy Spirit,
   and Satan are out of scope for this pass. Jesus is in scope as a person.
2. **Only the text.** If your book does not establish it, do not record it, even
   if you know it from elsewhere. Another batch covers that book.
3. **Every relation needs a real citation.** Before writing a reference, confirm
   the line exists in the text file. Invented references are the one failure
   mode that ruins the dataset.
4. **Prefer the specific type.** `persecuted` over `enemy_of` when one party
   holds the power and pursues the other. `killed` over `attacked` when someone
   dies. `father_of` over `ancestor_of` for a direct generation.
5. **Hebrew idiom.** "X son of Y" is usually direct parentage, but in summary
   formulas ("Jesus Christ, the son of David, the son of Abraham") it means
   descent — use `ancestor_of` there. "Brother" can mean kinsman; if the text
   does not make siblinghood clear, say `implied` and note it.
6. **Genealogy chains** (`Gen 5`, `Gen 11`, `Matt 1`, `Luke 3`, `1Chr 1-9`)
   become `father_of` edges link by link, each citing the verse that names both
   the father and the son.
7. **Don't pad.** A precise 200 relations beats a vague 600. Skip anything you
   cannot cite.

   But "I cannot prove it with a name match" is **not** the same as "I cannot
   cite it", and the difference matters. Some of the most consequential people
   in scripture are never named — the widow of Nain, the woman at the well, the
   centurion's servant, Jairus's daughter, Pharaoh's daughter. Their
   relationships are certain even though no name can corroborate them.

   Record them. Give the entity a descriptive id and name, and mark it:

   ```json
   {"id":"widow_of_nain","name":"the widow of Nain","type":"person",
    "attrs":{"unnamed":true},
    "disambiguation":"unnamed widow whose only son Jesus raised (Luke 7:11-15)",
    "refs":["Luke 7:12"],"source":"..."}
   ```

   `attrs.unnamed` tells the checker not to look for a name it will never find.
   In exchange, say in the relation's `note` how you identified them, and use
   `certainty: implied` when neither party is named. Being unable to verify
   something mechanically is a fact about the tool, not about the text —
   deleting the record hides a real relationship and quietly overstates how
   complete the graph is.

8. **"A, the son of B, the son of C" is a CHAIN, not two fathers.** It means B is
   the father of A, and C is the father of B. Recording both B and C as fathers of
   A is wrong, and the checker will reject it. This construction runs for many
   links in places (Josh 17:3; 1Chr 6:33-38; Luke 3:23-38) — walk it link by link.

9. **One id is one person.** The Bible reuses names relentlessly: there are two
   Abinadabs (Jesse's son, 1Chr 2:13, and Saul's son, 1Chr 8:33), two Ahazes,
   dozens of Zechariahs, and a Jehoram in each kingdom. When the same name belongs
   to two people, they get **two ids**, each qualified (`abinadab_son_of_jesse`)
   and each with a `disambiguation` note. Never merge two people because they
   share a name; never split one person who is called two things (put the second
   name in `aka`). Giving one id two different fathers is the classic symptom, and
   the checker treats it as an error.

## Places

A place record is an entity with `"type":"place"`:

```json
{"id":"beth_el","name":"Beth-el","type":"place","aka":["Bethel","Luz"],
 "attrs":{"kind":"town","region":"Canaan"},
 "refs":["Gen 28:19"],"source":"..."}
```

`kind` must be one of the values listed under `place_kinds` in the vocabulary.

Three rules learned from the first pass:

1. **Mint a place only when a relation anchors it.** The wilderness itinerary of
   Num 33 names some forty stops that the text says nothing else about. A place
   with no relation is padding. The exception is a deliberate list — Gen 10,
   Num 34 — where the enumeration is itself the content.

   But **do not read that as a reason to omit journeys the narrative cares
   about.** `traveled_to` is weighted 1 so it cannot swamp stronger ties, not so
   it can be skipped. Record a journey when the text makes something of the
   arrival: something happens there, it is a destination reached, it recurs.
   Skip bare stages in a list of ports.

   The first passes got this wrong in the cautious direction and left Jesus with
   no tie to Jerusalem at all — a place he is carried to as an infant, found in
   at twelve, goes up to for feasts, enters in triumph, and is crucified in.
   Omitting a central fact is as much an error as inventing a marginal one.

4. **Bodies of water are places.** Rivers, seas and brooks take `kind: river` or
   `kind: sea`: the river Jordan, the Red sea, Euphrates, the brook Cherith, the
   sea of Galilee (one place under several names — put Tiberias and Gennesaret
   in `aka`).

5. **Regions contain towns, and the graph is thin on it.** Join them with
   `located_in`: Bethlehem in Judah, Capernaum in Galilee, Zion within
   Jerusalem. This is what lets a region answer "who and what was here".

2. **Names shared by a person and a place need separate ids, always.** Canaan,
   Midian, Moab, Gilead, Hebron, Mamre, Shechem and Haran are each both a person
   and a place. Suffix the place by what it is: `canaan_land`, `hebron_city`,
   `gilead_region`, `mamre_site`.

   **Run `lookup` on every id you mint, not only on the people you reference.**
   The first places pass looked up the people it cited and not the places it
   created, and produced seven collisions that silently fused a person and a
   place into one entity. The checker now rejects a relation pointing the wrong
   kind of entity at either end, but it can only see records that exist — two
   batches that each mint one half of a collision will not notice until merge.

3. **Use the KJV spelling for `name`** so the citation check can find it in the
   text, and put the familiar modern form in `aka`: `Beth-el` with `Bethel`,
   `Beer-sheba` with `Beersheba`.

## Groups and peoples

A group record is an entity with `"type":"group"`:

```json
{"id":"philistines","name":"the Philistines","type":"group",
 "attrs":{"kind":"nation"},"refs":["Judg 3:31"],"source":"..."}
```

`kind` comes from `group_kinds` in the vocabulary.

**The test for whether a group belongs: does the text make it act, or address
it, as one?** It fights, is spoken to, is judged, is delivered, goes into exile.
The Philistines fight; the Levites are set apart; the house of Saul wars long
with the house of David; the church at Ephesus receives a letter. Those are
groups.

**Incidental plurals are not groups.** "The people who were with him", "certain
men", "the multitude" — the text is counting, not naming an actor. Leave them
out. If you cannot point to the text treating the group as a single subject,
it does not belong.

Three further rules:

1. **Tribe names collide three ways.** Judah is a person, a territory and a
   tribe; so are Benjamin, Dan, Levi, Ephraim, Manasseh, Simeon, Asher, Gad,
   Naphtali, Zebulun, Issachar and Reuben. The person and the region already
   exist. Mint the group as `<name>_tribe` and check first:
   `python -m bibleont.lookup Judah` will show you what is already taken.

2. **Join a people to the person it is named for** with `descended_from_person`.
   That is how the text itself explains a nation's origin — the Moabites from
   Moab (Gen 19:37) — and it keeps the person and the people distinct while
   linked.

3. **Do not dissolve a group into its members.** "Saul smote the Amalekites" is
   one relation to a people, not a claim about individuals. Equally, do not
   invent membership: record `member_of` only where the text places the person
   in the group.

## Before you mint an id, check whether the person is already in the graph

Other batches have already been merged. If you invent `bathsheba` for someone the
graph already calls `bath_sheba`, they become two people. Look first:

```bash
python -m bibleont.lookup Phinehas Abinadab Bathsheba
```

It reports every existing person whose name matches or resembles yours, with
their disambiguation and first citations:

```
Phinehas
  = phinehas_son_of_eleazar   Phinehas   grandson of Aaron (1Chr 6:4)
  = phinehas_son_of_eli       Phinehas   son of Eli, died carrying the ark (1Sam 4:11)
```

Three outcomes:

- **It is the same person** → reuse that exact id.
- **It is a different person with the same name** → mint a NEW qualified id
  (`phinehas_son_of_ahab`) and fill in `disambiguation`. Never reuse an id for
  someone else.
- **Not found** → mint a new id and move on.

Run it for every name you are unsure about, and for every name common enough to
be shared — the Zechariahs, Azariahs, Jonathans, Marys, Simons and Josephs.

## Check your work before you finish

Run this from the repository root and fix everything it reports:

```bash
python -m bibleont.check_extraction ontology/staging/<your-batch>
```

It verifies that every citation resolves to a real verse, that your types are in
the vocabulary, and — the important one — that the verses you cited actually
name the people involved. **A batch that fails this check is not done.** Iterate
until it prints `PASS`.
