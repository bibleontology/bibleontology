# Is this one thing recorded twice?

A Bible knowledge graph has two records with the same name and type. Two
records should become one only when they are **the same thing recorded
twice**: not two things that are alike, not one word used of different
things. The default is to keep them apart; a merge needs clear evidence.

You are given both records: name, type, description, every verse each cites
(Berean Standard Bible), and the links each has. For an image, "the same
thing" means the same figure: the text uses the one picture with the same
sense in both places, so a reader would expect one card to gather both.

Write a JSON object to the path you are given:

```json
{"verdict": "same" or "different", "confidence": "high" or "low",
 "why": "<two or three sentences, quoting the verses>"}
```

Reply with one word: same or different.
