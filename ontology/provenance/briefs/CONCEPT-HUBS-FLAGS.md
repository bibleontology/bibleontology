# The committee flags the concepts it is worried about

A Bible website is building "hubs" for fifteen concepts: truth, love,
righteousness, faith, grace, mercy, hope, holiness, glory, peace, joy,
forgiveness, repentance, prayer, praise. Each hub sets out what the text says
of the concept by the forms its Hebrew and Greek words take, every row a set
of verses in the Berean Standard Bible's words, grouped by the grammar and
not by a reading:

- **the verb**: who does it to whom ("The LORD loves", "Love one another",
  "Love your enemies"), from the subject and object the original records;
- **the noun**: what it stands beside in its phrase ("the love of God",
  "justice and righteousness", "righteousness by faith"), and what the text
  says it is ("Love is patient");
- **the adjective**: who is called it ("beloved", "righteous").

The site takes no side where Christian traditions part, and says nothing in
its own voice that a tradition would object to. The profile of each concept
(its words and the commonest groupings) is in out/hub-forms.md.

Read as the site's nine readers: a Lutheran, a Reformed Christian, a
Wesleyan, a Baptist / free church Christian (often dispensational), a
Pentecostal / Charismatic, a secular academic scholar of the Bible (with
Jewish readers of the Hebrew Bible in mind), a Catholic, an Eastern
Orthodox Christian, and a biblical-theological (literary) reader.

For each concept, flag how worried you are that grouping its verses this way
would take a side or mislead -- **high**, **medium** or **low** -- and say
where: which form or row, which readers, and why. Examples of the kind of
thing to flag: "the righteousness of God" (whose righteousness: God's own,
or one given?), "justified by faith / by works" set apart rather than side by
side, faith grouped as belief versus faithfulness, grace "received" in the
sacraments, repentance set beside baptism, the Hebrew and Greek words a
grouping silently equates. Do not flag what is merely difficult; flag what a
reader of one tradition would find tilted against them.

**Separately, for every concept: does a row put different original words
together as one?** A Hebrew word beside the Greek word that renders it in the
Greek Old Testament is one thing (אהב and ἀγαπάω in the greatest
commandment). Two different words that English translates alike are another:
φιλέω is not ἀγαπάω, and חֶסֶד is not אַהֲבָה. Name every row where the second
kind happens, the words, and a verse. Answer this whatever the worry level,
because it is a matter of what the text says, not of tradition. (Added
2026-10-09: the first pass missed φιλέω at Matthew 23:6 grouped with ἀγαπάω.)

Write a JSON list to the path you are given:

```json
[{"concept": "...", "worry": "high" | "medium" | "low",
  "where": "<form or row>", "readers": ["..."], "why": "<one or two sentences>",
  "how_to_keep_level": "<what the page should do: side by side, the phrase kept as written, a row split>"}]
```

One entry per concept, all fifteen. Reply with one line: how many high,
medium, low.
