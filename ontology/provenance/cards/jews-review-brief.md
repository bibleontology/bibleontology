# Review: the card "the Jews" on a public Bible website

A non-profit website shows a knowledge graph of the Bible. Each person, group
and idea has a card: a one- or two-sentence description in the site's own
voice, then relations to other cards, each citing verses (Berean Standard
Bible text). The site takes no doctrinal side and says nothing in its own
voice that a reader of a tradition would object to.

A reader searching "jew" lands first on this card. The site's owner noticed
that many people who search that word will be Jewish, and will look at once to
see whether the site is antisemitic. The card is honest to the text, but its
description and its relations show one slice of how the text uses the word.

## The card as it stands

**Description (site voice):** "The Jewish people as the Gospels and Acts
repeatedly present them acting as one body: seeking to kill Jesus, and
conspiring against Paul."

**Relations shown:**
- Conflict (8): was an enemy of Haman (Esth 9:24, 3:10); was persecuted by
  Haman (Esth 3:6, 3:13); persecuted / sought to kill Jesus (John 5:18, 10:31,
  7:1); persecuted / sought to kill Paul (Acts 9:23, 14:5, 23:12-13); attacked
  Jesus (John 8:59, 10:31, 10:33); was accused by some astrologers (Dan 3:8);
  accused Paul (Acts 22:30, 25:7); was accused by Moses (John 5:45)
- Peoples & groups (3): descends from Abraham (John 8:33-39); Esther a member
  (Esth 7:4, 2:10); Mordecai a member (Esth 2:5, 10:3)
- Encounters & speech (2): was rebuked by Jesus (John 8:39, 8:44); pleaded with
  Festus (Acts 25:2-3)
- Observances (1): kept Purim (Esth 9:27-28)
- Service & authority (1): was charged by Esther (Esth 4:16)

## Where the words occur (measured from the Hebrew, Aramaic and Greek)

- Hebrew יְהוּדִי ("of Judah", Jew/Judean): 69 verses -- Esther 52, Jeremiah 10,
  Nehemiah 10, 2 Kings 2, Zechariah 1 (Zech 8:23). Also the adjective in 2 Kings,
  Isaiah, 2 Chronicles, Nehemiah ("in Judean", the language).
- Aramaic יְהוּדַי: Ezra 8, Daniel 2.
- Greek Ἰουδαῖος (Jew / Judean): 185 verses -- Acts 79, John 71, Romans 11,
  1 Corinthians 8, Mark 6, Luke 5, Matthew 5, Galatians 4, Revelation 2, others 1
  each. Ἰουδαϊσμός "Judaism" Gal 1:13-14.
- The Hebrew Scriptures mostly say "Israel", "the children of Israel", "Judah";
  "Jew" as a name is late (Esther, Ezra-Nehemiah, Jeremiah's last chapters).

## Verses to read (Berean text, in full)

See the file jews-verses.md beside this one (49 verses: conflict and
non-conflict, Hebrew Bible and New Testament).

## The panel

Read as the site's nine readers -- a Lutheran, a Reformed Christian, a
Wesleyan, a Baptist / free church Christian, a Pentecostal / Charismatic, a
secular academic scholar of the Bible, a Catholic, an Eastern Orthodox
Christian, a biblical-theological (literary) reader -- **and, as a guest
without a vote, a rabbi.**

The rabbi's ground rules, from the site's owner: the canon is what it is (the
66 books, as shown; nothing is removed or softened that the text says). The
rabbi may advocate for his people: that the card state honestly what the text
says, and do it with sensitivity to Jewish readers who come to this card
first. He may point out where the card gives a false impression of the text as
a whole, or of the Jewish people, even if each line is true. He does not vote;
the nine decide, but they must answer his points.

## What to return

Write JSON to jews-review.json beside this file:

```json
{"rabbi": {"reading": "<how a Jewish reader arriving first would take the card, in a few sentences>",
           "points": [{"point": "...", "verses": ["..."]}]},
 "description": {"verdict": "keep" | "change",
                 "proposed": "<a new description in the site's voice, one or two sentences, every claim checkable in the verses>",
                 "why": "...",
                 "readers_objecting_to_proposed": ["...", "<any of the nine who could not accept it, and why>"]},
 "relations": {"missing": [{"relation": "<e.g. 'Jesus is called a Jew'>", "verses": ["..."], "why": "..."}],
               "misleading": [{"relation": "...", "why": "...", "fix": "..."}]},
 "word_pages": "<what the word pages for יְהוּדִי and Ἰουδαῖος should make plain -- e.g. that the word also means Judean -- without taking a side on how John uses it>",
 "summary": "<two sentences>"}
```

Rules for the proposal: nothing the text does not say; no softening of what it
does say (the conflict verses stay); no position on how any book's use of the
word should be read (e.g. whether John's "the Jews" means the Judean leaders --
that is contested and the site does not choose); the description in plain
words, no scholarly jargon. A relation must cite verses that say it.

Reply with one line: the proposed description.
