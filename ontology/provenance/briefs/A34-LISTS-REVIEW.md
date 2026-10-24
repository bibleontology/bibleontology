# Reviewing the declared lists (A.34)

A Bible website gives each of thirteen lists in the Bible one card: the full
armor of God, the fruit of the Spirit, the Beatitudes, and others. On each
card every member opens a card of its own, and "what the passage says to do"
shows the passage's verbs, each opening its verse. Six cards are new, and
their descriptions are in the site's own voice. Your packet gives every list
with every verse in full, and the About paragraph that describes them.

The site speaks only in the texts' words or plain labels, and takes no side
where Christian traditions part. Check:

1. **Each member's card.** The member's label is the verse's words; the card
   it opens is the graph's existing card for that thing where one exists.
   Does opening that card say something the verse does not, or take a side?
   (A member wrongly sent to a card about something else is the error to
   find: e.g. a verse about one kind of baptism sent to a card about another.)
2. **The moves.** Each must be the passage's own words, and the set must not
   imply a sequence or teaching the passage does not give.
3. **The six new cards' descriptions and the About paragraph**: every quoted
   phrase must be in its verse exactly; nothing may say more than the verses.
4. **As nine readers would take it**: a Lutheran, a Reformed Christian, a
   Wesleyan, a Baptist / free church Christian (often dispensational), a
   Pentecostal / Charismatic, a secular academic scholar of the Bible (does
   the text say this? -- with Jewish readers of the Hebrew Bible in mind), a
   Catholic, an Eastern Orthodox Christian, and a biblical-theological
   (literary) reader. Would any object that a card, a link, a grouping or a
   word takes a side -- on baptism, on the gifts continuing or ceasing, on how
   the commandments are numbered, on Revelation's sevens, on what the armor
   is, on the seven spirits?

Write a JSON object to the path you are given:

```json
{"verdict": "accept" or "revise",
 "items": [{"list": "<list id>", "what": "<member, move, description or About>",
            "verdict": "accept" or "revise", "change": "<the exact change>",
            "why": "<which reader, and the reason>"}]}
```

List only items that need a change, plus one line per list you accept whole.
Reply with one line: how many lists accepted / revised.
