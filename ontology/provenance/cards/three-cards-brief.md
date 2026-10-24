# Review: three cards on a public Bible website

A non-profit website shows a knowledge graph of the Bible. Each person, group
and idea has a card: a one- or two-sentence description in the site's own
voice, verses quoted from the card, and relations to other cards, each citing
verses (Berean Standard Bible). The site takes no doctrinal side.

The card "the Jews" was just reviewed because Jewish readers are likely to
open it first. Its description said the Jews, "acting as one body", sought to
kill Jesus; the text does not say "as one body" and shows them divided. The
card now says who they are before what some of them did, and keeps every hard
verse. These three cards are the ones Jewish readers are likely to open next:

- the Pharisees -- file pharisees.md
- the chief priests -- file chief_priests.md
- the sons of Israel (the people of Israel) -- file children_of_israel.md

## FIRST PRINCIPLE: TRUE TO THE TEXT

The site's owner, in his words: *"we have to stay true to the text as a first
principle."* So:

- Nothing the text says is softened, hidden or explained away. If the text
  mostly shows a group in conflict, the card says so, in proportion.
- Nothing is added that the text does not say -- no history from outside the
  Bible, no later tradition, no sympathy the verses do not carry.
- "Balance" means only what the text itself supplies: if the text also shows
  members of a group otherwise (named people, other scenes), the card must not
  leave that out; if it does not, the card must not invent it.
- What the panel may fix: framing that claims more than the verses (a whole
  group where the verse names some; "always" where it is "often"); a fact the
  text plainly states that the card omits; words in the site's voice a reader
  would take as a verdict the text does not give.

## Facts (measured from the Greek and Hebrew, unique verses)

- Φαρισαῖος "Pharisee": 93 verses -- Matthew 29, Luke 26, John 19, Mark 11,
  Acts 7, Philippians 1.
- ἀρχιερεύς "high priest / chief priest": 119 verses -- Matthew 24, Acts 22,
  Mark 21, John 20, Hebrews 17 (of Jesus as high priest), Luke 15.
- יִשְׂרָאֵל "Israel": 2,227 verses across the Hebrew Bible; Ἰσραήλ 66 in the New
  Testament; Ἰσραηλίτης "Israelite" 9.

Verses to read in full: verses.md (30 verses -- Nicodemus, Gamaliel, the
Pharisees' warning about Herod, Paul "a Pharisee", Matt 23, the council of John
11, priests who believed in Acts 6:7, Israel's election in Deuteronomy 7,
Romans 9 and 11, and others). Cite any other verse you rely on by reference.

## The panel (eleven seats; all must be able to accept a change)

Lutheran; Reformed; Wesleyan; Baptist / free church (may lean conservative);
Pentecostal / Charismatic; secular academic scholar of the Bible; Catholic and
Eastern Orthodox (judging within the 66 books shown); biblical-theological
(literary); **a rabbi** (voting; reads the Hebrew Scriptures on their own
terms; may object to framing or missing context the text supplies, but cannot
stand in the way of a fair representation of the text; defers to the other
seats on how a Christian tradition reads its own text); **a young African
American believer** (deep faith, high view of Scripture, attentive to
justice; guards against US political framing in either direction and against
culturally insensitive presentation, while staying true to the text).

## What to return

Write JSON to review.json beside this file:

```json
{"cards": [
  {"id": "pharisees" | "chief_priests" | "children_of_israel",
   "verdict": "keep" | "change",
   "description": {"proposed": "<new description, or the same if keep; every claim checkable in the verses>", "why": "..."},
   "quote_first": ["<up to 6 references the card should quote first, in order>"],
   "relations": {"missing": [{"relation": "...", "verses": ["..."]}],
                 "misleading": [{"relation": "...", "why": "...", "fix": "..."}]},
   "objections": ["<any seat that could not accept the proposal, and why>"]}],
 "eleventh_seat_asks": [{"card_or_topic": "...", "why": "<one or two sentences>"}],
 "summary": "<two sentences>"}
```

**Separately, the eleventh seat is asked by the owner:** are there a couple of
cards (people, peoples, ideas or passages in the Bible) he would like the
panel to look at next, for the reasons his seat exists? Name two or three, by
the name a reader would search for, each with why. Keep to what the site would
show from the text (e.g. the card for a people, a passage on slavery, an
image), not modern topics.

Reply with one line per card: the verdict and the proposed description.
