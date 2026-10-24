# Brief: build one concept hub

You are building the **hub** for one concept card on bibleontology.org, a
non-profit knowledge graph of the Bible built from the original Hebrew,
Aramaic and Greek (MACULA data) with the Berean Standard Bible's English. Two
hubs exist and are live: **love** and **righteousness**. Yours must reach the
same level. The site's owner: *"I really see value in getting as many concepts
to that level as realistic."*

Repository: `<local> Ontology`. Work only there.

## Read first (in this order)

1. `ontology/concept-hubs/love.json` and `ontology/concept-hubs/righteousness.json`
   -- the two finished specs. Their `_why`, `_about`, `_review` fields explain
   every decision. Copy their shape.
2. `out/concept-hubs/love.json` -- what the builder produces from a spec.
3. `tools/concepts/hub_build.py` -- the builder. Read its comments: they list
   every row option. Summary:
   - spec keys: `id`, `shown` (**false** -- always), `lead` (verb/noun/
     adjective), `titles`, `words` (Strong's keys like "h157", "g25"),
     `sense` (regex on each verse's English gloss: keeps only occurrences in
     the concept's sense), `others` (other words English renders the same way,
     shown apart -- see love.json), `leads` and `gather` (card ids shown as
     doors), `own_words` (key verses, "Book.c.v"), `sets` (named lemma sets,
     e.g. "divine"), `match` ("all": a verse sits in every row it fits; use it
     wherever row order would decide a contested verse), `moves` (a verse
     the Greek/Hebrew and the Berean number differently: {"Book.c.v": {"to":
     "Book.c.v", "why": "..."}}), `forms` ({"h6960": "verb"} -- a word's part
     of speech where the lexicon has none), `sense_keep` ({"Isa.42.4":
     "reason"} -- keep a verse the gloss rule drops, where the Berean itself
     has the concept's word), `rows`.
   - row keys: `form`, `label`, `doors`, `note`, and conditions: `agent`,
     `patient`, `not_patient` (verb frames), `with` (+ `adjacent`: true = next
     word, or a number = window), `in_verse`, `in_clause`, `object_of`,
     `not_object_of`, `subject`, `stance` / `not_stance` (e.g. "command"),
     `pick` (verses by hand), `add` (verses added by hand), `lead` (verses
     shown first as examples), `not_verses` ({"Book.c.v": "reason"}). A row
     with no condition is the catch-all for its form.
4. `ontology/provenance/concept-hubs/committee-flags.json` -- the review
   panel's worries per concept (faith, forgiveness, repentance flagged high;
   grace, hope, holiness medium).
5. The card as it is now: `curl -s "http://localhost:8002/api/entity?id=<id>"`
   (a local server is running) -- its words, its relations.

## Build

```
cd "<local> Ontology"
set PYTHONIOENCODING=utf-8
python tools/concepts/hub_build.py <id>
```
(Bash: `PYTHONIOENCODING=utf-8 python tools/concepts/hub_build.py <id>`.)
It loads the whole graph (1-2 minutes, ~3 GB) and writes
`out/concept-hubs/<id>.json`, printing each row's count and first examples,
and any `cards missing` (door ids that do not exist -- fix them). Aim for at
most 5 builds; read the output between builds.

## Rules (they outrank everything else)

1. **True to the text, first.** Nothing softened, nothing added. A row's
   label says only what its verses say. Labels in the text's own words where
   you can.
2. **The words.** The concept's own word family in Hebrew and Greek (a Hebrew
   word and the Greek word that renders it are rightly together). A
   *different* word that English also renders this way goes in `others`, not
   in the rows (love: φιλέω and חֶסֶד apart from ἀγαπάω and אהב). Use `sense`
   so a word's other senses do not count.
3. **No doctrine.** Where Christian traditions part (faith and works; grace
   and merit; repentance and baptism; who "the righteousness of God" is), set
   the text's verses side by side (`match: "all"`) with a `note` saying the
   page takes no side -- as righteousness's "Justified, and faith" / "and
   works" rows do. Never a label that is a verdict.
4. **The divine persons by hand.** God, the Father, Jesus, the Holy Spirit:
   a row about one of them is filled with `pick` (verses where the text itself
   names him), never by an inferred rule. Where the text says only "He", leave
   it, or make a separate row whose note says readers take it of the Father or
   of Christ and the page does not choose (righteousness: "He is righteous").
5. **Every example must show its label.** Check the four examples of every
   row. If a verse is in a row for a word that sits elsewhere in a long
   sentence, or a companion that means something else there, fix the rule
   (adjacent, object_of, in_clause) -- and only where no rule can, use
   `not_verses` with the reason.
6. **Different words, informed.** Never let a row equate two different
   words; never present one sense of a word as its whole.
7. **Hard verses stay.** Light is right where the text is light; do not pad.
8. **A reader's number of rows: about 15-25 in all, never 40+.** Love has 22,
   righteousness 26. Merge rows that say the same thing; a row of one or two
   verses belongs in a broader row or the catch-all unless the text sets it
   apart. (Early workers returned 35-49 rows; that is a concordance, not a
   hub.)

## Check

Before you finish, sample **16 verses across the rows** (not only the first
examples), read each in the Berean text (`curl -s
"http://localhost:8002/api/verse?ref=Book.c.v"`), and judge: does it show its
row's label? Fix what fails, rebuild, and record the tally.

## Deliver

- `ontology/concept-hubs/<id>.json` with `"shown": false` and `_why` notes on
  every non-obvious choice.
- `out/concept-hubs/<id>.json` (the builder writes it).
- A report at `<local>`:
  the rows with counts; the 16-verse sample with verdicts (and what you fixed);
  the words and the `others`; every contested point the review panel should
  read (be specific: row, verses, which traditions); anything the builder
  could not express (describe the option you needed -- do not edit the
  builder).

## Do not

- Edit any file except your concept's spec (no server, no `index.html`, no
  `hub_build.py`, no other spec, no docs).
- Run git (no commit, no add, no checkout).
- Set `"shown": true`.
- Quote from anywhere but the Berean text the server returns.

Reply with one line: the concept, its row count, and the 16-sample tally.
