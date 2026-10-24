# Review: cards on Ham and Canaan, Cush, and slavery

A non-profit website shows a knowledge graph of the Bible. Each person, group,
place, idea or passage has a card: a short description in the site's own voice
(some cards have none yet), verses quoted from the card, and relations to other
cards, each citing verses (Berean Standard Bible). The site takes no doctrinal
side. Its owner wants readers of every background to be welcome on it.

The panel's eleventh seat asked to see these cards next. Her reasons: Genesis
9:20-27 has been used to justify the enslavement of Africans, though the curse
falls on Canaan (9:25); the Cushites -- Moses's Cushite wife, Ebed-melech, the
Ethiopian official -- should be shown as the text shows them; and slavery, which
the text both regulates and frees from, is met by readers with strong feeling.

The cards (files beside this one): ham.md, canaan.md, canaanites.md, cush.md,
ethiopia.md, event_philip_and_the_ethiopian_eunuch.md, bondmen.md (the concept
"slaves"), titus_2_9_command.md ("Slaves are to submit..."). Verses in full:
verses.md (50 verses). Word counts: counts.txt.

## FIRST PRINCIPLE: TRUE TO THE TEXT

The owner: *"we have to stay true to the text as a first principle."*
- Nothing the text says is softened, hidden or explained away; the hard verses
  stay (Exod 21:20-21, Lev 25:44-46, Eph 6:5, Titus 2:9 among them).
- Nothing is added that the text does not say. **No modern categories the
  text does not use**: the text says "Cush" and "Cushite", not a race or a
  colour; it does not mention Africa by that name, or the later history of the
  curse's misuse. That history may not be stated in the site's voice as if the
  text said it. (What the site CAN do: say exactly what the text says -- e.g.
  that the curse in 9:25 is spoken over Canaan, by Noah -- so no reader is left
  with what it does not say.)
- "Balance" means only what the text itself supplies.
- Where one word covers several things, say so: Hebrew עֶבֶד (713 verses) is
  rendered "servant(s)" 657 times, "slave(s)" 67, "officials" 23, "slavery" 13 --
  the same word names a slave, a king's officer, and "the servant of the LORD".
  Greek δοῦλος (118 verses) is glossed "servant" more often than "slave". A card
  that presents one sense as the whole misleads.

## The panel (eleven seats; all must be able to accept a change)

Lutheran; Reformed; Wesleyan; Baptist / free church (may lean conservative);
Pentecostal / Charismatic; secular academic scholar of the Bible; Catholic and
Eastern Orthodox (within the 66 books shown); biblical-theological (literary);
a rabbi (voting; reads the Hebrew Scriptures on their own terms; defers to the
other seats on how a Christian tradition reads its own text); and the eleventh
seat, a young African American believer (deep faith, high view of Scripture,
attentive to justice; guards against US political framing in either direction
and against culturally insensitive presentation, while staying true to the
text). The panel is a cross-section on purpose: the owner wants every reader
it represents to be welcome on the site, so a card must read as written for
all of them.

## What to return

Write JSON to review.json beside this file:

```json
{"cards": [
  {"id": "<card id>", "verdict": "keep" | "change",
   "description": {"proposed": "<description in the site's voice; one to three sentences; every claim checkable in the verses; or the current one if keep>", "why": "..."},
   "quote_first": ["<up to 6 references, in order>"],
   "relations": {"missing": [{"relation": "...", "verses": ["..."]}],
                 "misleading": [{"relation": "...", "why": "...", "fix": "..."}]},
   "objections": ["<any seat that could not accept, and why>"]}],
 "summary": "<two sentences>"}
```

Cards with no description now: propose one only if the card needs it to be
read rightly (e.g. Ham, where a reader may arrive expecting the curse to be
his). Keep descriptions plain, short, and in the text's own words where you
can.

Reply with one line per card: the verdict and the proposed description (or
"keep").
