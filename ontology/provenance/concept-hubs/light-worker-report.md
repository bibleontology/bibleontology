# Light hub: report (third round, 2026-10-25)

Spec: `ontology/concept-hubs/light.json` (`shown: false`). Built: `out/concept-hubs/light.json`. Three builds. 26 rows in all: noun 20 (counting "Every other use"), verb 5, adjective 1 (righteousness has 26, love 22). No door card is missing.

## The words
- Hebrew: אוֹר noun h216 (106 verses in sense), אוֹר verb h215 (43), מָאוֹר h3974 (16), אֹרֹת h219 (3, one other sense: 2 Kgs 4:39 "herbs").
- Greek: φῶς g5457 (60), φωτίζω g5461 (11), φωτισμός g5462 (2), φωστήρ g5458 (2), φωσφόρος g5459 (0 by the sense rule; 2 Pet 1:19 is in its row by hand), φωτεινός g5460 (4, adjective).
- Not made one word: every verse names the word it stands on.
- `others` (different words the English renders light, shine, bright), shown apart: נֹגַהּ, φαίνω, λάμπω, יָפַע, נָגַהּ, λαμπρός, Aramaic נְהֹור (Dan 2:22, 5:11, 5:14: "light dwells with Him"), קָרַן (Moses' face), נָהַר, φέγγος, περιλάμπω, זֹהַר, ἐπιφαίνω (Luke 1:79), ἐπιφαύσκω (Eph 5:14), ἀπαύγασμα (Heb 1:3), ἐκλάμπω, στίλβω and others. `ἐλαφρός` (Matt 11:30, 2 Cor 4:17: "light" as not heavy) is added by hand with a note. Excluded as noise: Πύρρος "bright red" (Rev 6:4) and צַח "dazzling" (Song 5:10).

## Rows and counts
Noun (lead; 188 verses):
1. The light of the first day; God forms light and darkness: 8 (pick)
2. Sun, moon and stars; the lights set in the sky; morning light, daylight and the dawn: 37 (rule + add)
3. Lightning: 7 (pick; the Hebrew is אוֹר, the same word)
4. A lamp, a lampstand, oil for the light; the light of a fire: 23 (rule + add)
5. Light and darkness: beside it, against it, turned into it: 53 (rule)
6. "The LORD is my light", "God is light", "the LORD will be your everlasting light", "the Light of Israel": 6 (pick)
7. Light about God: "in Your light we see light", "wraps Himself in light", "the light of Your face", "Father of the heavenly lights": 9 (pick)
8. Jesus: "I am the light of the world", "the light of the gospel of the glory of Christ": 8 (pick)
9. Where the verse says only "the Light" or "He": John's prologue, "the Light has come into the world", "as He is in the light", "dwells in unapproachable light": 10 (pick)
10. A light for the nations, for the Gentiles; a light to those in darkness; "your light has come": 10 (pick)
11. A light from heaven, a light shining: Damascus road, the prison cell, the mountain: 7 (pick)
12. Walk in the light, abide in the light, stumble where there is no light: 9 (pick)
13. "You are the light of the world"; children of light; armor of light; out of darkness into His light: 13 (pick)
14. Light through the word: the law, the commandment, the prophets' word; the light of the gospel: 7 (pick)
15. The light within: the eye as the lamp; light that is darkness; an angel of light: 5 (pick)
16. Light and life: "the light of life"; to see the light, never to see it: 14 (rule + add + 1 not_verses)
17. Light beside the righteous and the upright, righteousness and justice, gladness and salvation: 10 (pick)
18. Light withheld, put out, turned to darkness; "the day of the LORD is darkness, not light": 17 (pick)
19. Light with no night: "the Lord God will shine on them", "the Lamb is its lamp": 8 (pick)
20. Every other use: 6 (Exod 10:23; Job 22:28, 25:3, 28:11, 29:24, 37:21). More: 0.

Verb (54 verses, every occurrence of h215 and g5461 is in a row, all by pick):
21. "Make Your face shine upon us": 8
22. Eyes made bright; the heart and the simple enlightened; hidden things brought to light: 16
23. Light given in the dark: pillar of fire, lamp, lightning; a lamp lit, a fire kindled: 15
24. The lights give light on the earth; the day dawns: 8
25. "Arise, shine": the glory of the LORD; the city lit by the glory of God; resplendent: 7

Adjective: "Full of light", "bright": the body, the cloud: 4 (Matt 6:22, 17:5; Luke 11:34, 11:36).

## The 16-verse sample (Berean text read with `curl -s .../api/verse?ref=`)
Result: **15 of 16 shown outright; 1 failed and was fixed.**

| # | Verse | Row | Verdict |
|---|---|---|---|
| 1 | Gen 1:18 | first day | FAIL: "separate the light from the darkness" by the lights of the fourth day; moved to the sun, moon and stars row (and no longer in the first-day row) |
| 2 | Job 31:26 | sun, moon, stars | shown ("the sun in its radiance or the moon moving in splendor") |
| 3 | Job 37:11 | lightning | shown ("scatters His lightning") |
| 4 | Num 4:16 | lamp | shown ("the oil for the light") |
| 5 | Rom 13:12 | light and darkness | shown ("deeds of darkness ... armor of light") |
| 6 | Isa 60:20 | the LORD is my light | shown ("the LORD will be your everlasting light") |
| 7 | Ps 90:8 | light about God | shown ("the light of Your presence") |
| 8 | John 12:36 | Jesus | shown (names Jesus: "After Jesus had spoken these things"; "believe in the Light") |
| 9 | John 3:21 | only "the Light" | shown ("comes into the Light") |
| 10 | Matt 4:16 | light for the nations | shown ("people living in darkness have seen a great light") |
| 11 | Col 1:12 | children of light | shown, weakly ("the inheritance of the saints in the light"); note corrected (it had said "kingdom of light", which the verse does not) |
| 12 | Ps 38:10 | the light within | shown ("the light of my eyes has faded") |
| 13 | Prov 16:15 | light and life | shown ("a king's face brightens, there is life") |
| 14 | Lam 3:2 | light withheld | shown ("darkness instead of light") |
| 15 | Ps 119:130 | verb: eyes, heart | shown, loosely ("gives light; it informs the simple"); row label widened to "the heart and the simple" |
| 16 | 1 Sam 29:10 | verb: day dawns | shown ("as soon as it is light") |

Other things fixed in the checks: Isa 50:10 was in the walking row (the Hebrew there is נֹגַהּ, not אוֹר: a pick lists a verse whether or not it holds the word, so every pick was checked against the occurrences of the words listed by the sense endpoint); a rule row on righteousness and joy words took Acts 13:47, Isa 49:6 and Jer 25:10 on a word elsewhere in them and was made a pick row; 1 Sam 25:34 left the life row (חַי is "as the LORD lives"); 1 Tim 6:16 and 1 John 1:7 moved from the God rows to the "only He" row.

## Contested points for the panel
- **Light as God's, and as Christ's** (rows 6, 7, 8, 9): by pick only. Row 6 and 7 hold verses that name the LORD or God (or address Him); row 8 holds verses that name Jesus or Christ or are Jesus' own "I" (John 8:12, 9:5, 12:46; John 12:35-36 names Jesus in the verse; 2 Cor 4:4, 4:6; Acts 26:23). Row 9 holds John 1:4-9, 3:19-21, 1 John 1:7 and 1 Tim 6:16, where the verse says only "the Light" or "He": John's prologue names the Word (1:1, 1:14) and Jesus Christ (1:17); 1 Tim 6:14-15 names "our Lord Jesus Christ" and "the blessed and only Sovereign One". The note says readers take these of the Word, Christ or the Father and the page does not choose. The panel should check that 1 Tim 6:16 and 1 John 1:7 belong in row 9 rather than rows 6-7 (they were moved there because readers differ on "He").
- **The light of the first day and the lights of the fourth** (rows 1 and 2): the note sets Gen 1:3-5 before Gen 1:14-19 and says the page does not say how they relate (the question of light before the sun). 2 Cor 4:6 is said to "recall" Gen 1:3 (the verse itself does not cite the book).
- **The servant who is "a light for the nations"** (row 10): Isa 42:6, 49:6 (49:3 calls the servant Israel), Luke 2:32, Acts 13:47, Acts 26:23, with Isa 9:2/Matt 4:16, 51:4, 60:1, 60:3 and Rom 2:19. The note says readers part (Israel, the Messiah, the prophet, the nation and its Messiah) and the page chooses none. Rom 2:19 is the self-description of one relying on the law; the panel should judge whether it belongs.
- **Heb 6:4 and 10:32 "enlightened"** (row 22): the note says readers part on what the enlightening is. The panel should confirm that is not itself taking a side on baptism (it names none).
- **Light with no night** (row 19): Isa 60:19-20, Zech 14:6-7, Rev 21:23-24, 22:5 set side by side; the note takes no side on how the earlier relate to the later.
- **Light from heaven** (row 11): Acts 9:3, 22:6-11, 26:13 beside Acts 12:7 and Matt 17:2; the page lists them as written and says nothing of who the light is (Acts 26:15 is not in the row).
- **Angel of light** (row 15): 2 Cor 11:14 stands beside the eye as lamp; a hard verse, kept.
- **Lightning** (row 3): the Hebrew word is the same as "light"; the sense is kept apart.
- **The sun and lamps** (rows 2 and 4): kept as senses of their own, as the brief asked.
- **Isa 10:17** ("the Light of Israel will become a fire, its Holy One a flame") is in row 6 as a title of the LORD; whether it is a title of God is a reading the panel may check.

## What the builder could not express
- **A lemma the clause tree spells otherwise than the lexicon.** The lexicon's h219 is אֹרֹת; at Ps 139:12 and Esth 8:16 the clause tree has אוֹרָה (the singular), so `which()` never matches and the noun is not "seen" in those two verses. A rule row cannot reach them and `add` fails (it needs a seen verse). Handled by hand: Esth 8:16 is in the pick row 17, Ps 139:12 is in verb row 23 (it holds the verb too). Needed: a way to name a second spelling for a word (an alias in `words`), or `add` that can introduce an unseen verse.
- **Verbs with no frame.** The frames carry the agent of only a few verbs and no record of most h215 and g5461 verses, so no verb rule row can place them. All 54 verb verses are in pick rows, which is faithful but means the verb form has no rule check; a mistake in a pick is invisible to the builder (it lists a verse whether or not it holds the word; an unattached pick shows an empty word tag only if its example is among the first four).
- **Two words with the same letters** (h215 verb, h216 noun) key the same pointed lemma; only listing the verb first keeps the noun. Worth saying in the builder's comments if it is not already.
- **A row's second form.** The same verse can be wanted in a noun row and a verb row (John 1:9, Rev 21:23, Isa 60:19); each is in both forms by pick. That works, but a reader sees the verse twice.
- **The 16-verse sample would be cheaper if the output listed every row's verses with their word tags.** Only the first four examples carry tags.

## Things the panel may want to decide
- Row count is 26 (the brief's 15-25; righteousness has 26). Candidates to join if fewer is wanted: rows 6 and 7; rows 15 and 16; rows 12 and 13.
- Row 20 is thin on purpose: six verses that fit no label (Exod 10:23, Job 22:28, 25:3, 28:11, 29:24, 37:21).
- The About view is untouched; this hub is `shown: false`.
