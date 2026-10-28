# kingdom hub: report (round 3, 2026-10-25)

Spec: `ontology/concept-hubs/kingdom.json` (`"shown": false`). Built: `out/concept-hubs/kingdom.json`. Cards missing: none. Builds used: 4 of 5. 27 rows, all noun form (a noun has no agent or patient to read, so no verb or adjective form). 438 verses; nothing under "More"; the catch-all holds 2.

## Words

| word | key | kept | other sense |
|---|---|---|---|
| מַמְלָכָה (Hebrew) | h4467 | 110 | 0 |
| βασιλεία | g932 | 154 | 0 |
| מַלְכוּת (Hebrew) | h4438 | 82 | 0 |
| מַלְכוּ (Aramaic: Ezra, Daniel) | h4437 | 43 | 0 |
| מְלוּכָה (Hebrew) | h4410 | 23 | 0 |
| מַמְלָכוּת (Hebrew) | h4468 | 9 | 0 |
| βασιλεύω "reign" (the card's family verb) | g936 | 18 | 0 |

`sense` is empty (as covenant): every use is the one word, whether the Berean prints kingdom, reign, kingship, royal, realm, dominion or sovereignty. The rows divide the uses by whose kingdom it is, and the reign/kingship/royal sense has a row of its own so the years of Asa's reign are not read as a kingdom. βασιλεύω was given the noun form by `forms` so it can carry Rev 20:4, 20:6 (the thousand years) and 1 Cor 15:25; it is the only way those verses reach the hub, since they hold no kingdom noun. Not taken in: the Hebrew verb מָלַךְ "reign" (the LORD reigns, Ps 93:1; 350 verses of every king; the card does not list it; its theme card is a door), βασιλεύς, βασίλειος, βασίλισσα, συμβασιλεύω (2 Tim 2:12 "reign with Him": named in the reign row's note).

`others` (never as the same word): מֶמְשֶׁלֶת "dominion" (11), שׇׁלְטָן "dominion" (9, with a note that in Dan 4:3, 6:26, 7:14, 7:27 it stands beside the Aramaic "kingdom"), κράτος "dominion" (3), מִמְשָׁל (2), מֹשֶׁל (2).

## Rows (verse count)

1. Kingdoms of the earth, in the plural: "all the kingdoms of the earth", "kingdom against kingdom", "the kingdoms of the world" (62; pick)
2. One king's kingdom, realm or sovereignty: Nimrod's, Og's and Sihon's, Xerxes', Nebuchadnezzar's, Darius', Egypt's, the king of the South's, the beast's (66; pick; note)
3. Israel's and Judah's own kingdom: Saul's torn away, David's and Solomon's, Rehoboam's, the kingdom divided (49; pick; note)
4. The kingdom of David and of his descendant: "established forever" (13; pick; note: no side)
5. The LORD's kingdom, and the LORD over every kingdom (44; pick; note: Ps 45:6 / Heb 1:8 no side)
6. Daniel's kingdoms: four that arise, then a kingdom that "will never be destroyed", given to "the saints of the Most High" (12; pick; note: no side)
7. The kingdom of heaven (31; rule: βασιλεία + οὐρανός as the next word; all in Matthew; note: heaven/God, no side)
8. The kingdom of God (66; rule: βασιλεία + θεός as the next word, plus 1 Cor 6:10 by `add`; note: heaven/God, no side)
9. Of the Son, of Christ: "His kingdom", "My kingdom", "Your kingdom" (12; pick, by hand)
10. The Father's kingdom (6; pick, by hand)
11. Prayed for, and sought first: "Your kingdom come", "seek first the kingdom" (4; pick; note)
12. Said as near, or as here (16; pick; note: no side on now/later/both)
13. Said as still ahead (23; pick; note: Matt 16:28/Mark 9:1/Luke 9:27 readings; no side)
14. What the text says the kingdom is not (5; pick; note)
15. "The kingdom of heaven is like ...": the parables (16; pick)
16. Preached, proclaimed, taught, argued: "the gospel of the kingdom" (16; pick)
17. "Theirs is the kingdom": the poor in spirit, the persecuted, the poor, the little children (11; pick)
18. Enter the kingdom: who will, and how hard (16; rule: εἰσέρχομαι or εἰσπορεύομαι in the verse, 2 `not_verses`; note: John 3:5, no side)
19. Receive it, inherit it, be given it; and "will not inherit" (16; pick; note: no side)
20. The keys of the kingdom, and the kingdom shut (2; pick; note: Matt 16:19, no side)
21. Given, taken away, thrown out, restored: "taken away ... and given to a people", "restore the kingdom to Israel", "a kingdom of priests" (16; pick; note: no side)
22. At table in the kingdom (9; pick; note: Last Supper, no side)
23. A kingdom divided against itself: "cannot stand"; Satan's kingdom (5; pick)
24. Reign and kingship: "He must reign", "reign upon the earth", "for a thousand years" (15; pick; note: pre-, post- and amillennial readings, no side)
25. Death, sin and grace "reign" (4; pick; the same Greek verb, another sense)
26. A king's reign, his kingship and what is "royal" (66; pick; its own sense)
27. Every other use (2: 2 Tim 4:18, 1 Thess 2:12; note)

A verse sits in every row it fits (`match: all`). Over the brief's 15-25 rows by two, because a king's reign/royal sense (66 verses) and the verb "reign" (two senses) are different records. The rows that could join if the owner wants fewer: 11 into 13; 20 into 18; 23 into 2; 25 into 24 (but see rule 6: the verb's other sense is better kept apart).

## The 16-verse sample (Berean text from the server, `curl -s http://localhost:8012/api/verse?ref=...`)

Tally: 11 pass; 4 partial (all mended); 1 fail (fixed).

| verse | row | verdict |
|---|---|---|
| Isa 19:2 "kingdom against kingdom" | 1 | pass |
| Dan 11:17 "his whole kingdom ... overthrow the kingdom" | 2 | pass |
| 1 Chr 28:7 "I will establish his kingdom forever, if he ... carries out My commandments" | 4 | pass (the condition is named in the row note) |
| Ps 79:6 "Pour out Your wrath on ... the kingdoms" | 5 | PARTIAL: a prayer for wrath, not the LORD ruling kingdoms. Fixed: out of row 5, stays in row 1 |
| Matt 19:12 "for the sake of the kingdom of heaven" | 7 | pass |
| Luke 9:62 "fit for the kingdom of God" | 8 | pass |
| Matt 20:21 "in Your kingdom" (said to Jesus) | 9 | pass |
| Matt 25:1 "the kingdom of heaven will be like ten virgins" | 13 "still ahead" | FAIL: a comparison, not a statement about when. Fixed: out of row 13; stays in row 15 |
| Rev 1:9 "partner in the tribulation and kingdom and perseverance" | 12 "near or here" | PARTIAL: present tense, not "near". Fixed: kept, the note names the present tense (with Heb 12:28) |
| Rev 11:17 "You have begun to reign" | 24 | pass |
| Luke 22:30 "eat and drink at My table in My kingdom" | 22 | pass |
| Esth 2:17 "the royal crown" | 26 | pass |
| 1 Tim 6:15 "the King of kings" | 24 | PARTIAL: the Berean prints no "reign" (Greek "of those who reign"). Fixed: kept, the row note names the difference |
| Dan 7:24 "ten kings who will rise from this kingdom" | 6 | pass |
| Matt 8:12 "the sons of the kingdom will be thrown into the outer darkness" | 21 | PARTIAL: "thrown out", not "taken away". Fixed: label widened to "thrown out" |
| Acts 14:22 "to enter the kingdom of God" | 18 | pass |

Also read in the Berean text and fixed from the first build, before the sample: the first build left 81 verses in the catch-all (the sense "reign / kingship / royal / realm"): row 26 and the additions to rows 1, 2, 4 and 5 took them. `enter` took Mark 15:43 (Joseph "went in" to Pilate) and Acts 19:8 (Paul "went into the synagogue"): `not_verses`; it missed Luke 18:24, which uses εἰσπορεύομαι: added. Matt 18:1 (a question about greatness) came out of row 17; Col 4:11 and 1 Thess 2:12 ("fellow workers for", "calls you into") came out of the preach and inherit rows (Col 4:11 is in the God row by rule, 1 Thess 2:12 in the catch-all). 2 Tim 2:12 left the reign row: its verb is συμβασιλεύω, not in the hub.

## Contested points for the review panel (row, verses, which readings part)

1. **Rows 12 and 13: the kingdom now, still to come, or both.** Row 12 (Matt 3:2, 4:17, 10:7, 11:12, 12:28; Mark 1:15; Luke 10:9, 10:11, 11:20, 16:16, 17:21, 21:31; Col 1:13; Heb 12:28; Rev 1:9, 12:10) beside row 13 (Matt 8:11, 13:41, 13:43, 16:28, 25:34, 26:29; Mark 9:1, 11:10, 14:25; Luke 9:27, 13:28-29, 14:15, 19:11, 22:16, 22:18, 23:42; 1 Cor 15:24, 15:50; 2 Thess 1:5; 2 Tim 4:1; 2 Pet 1:11; Rev 11:15). Row 12 is chosen by the text's near/came/present tense, row 13 by future tense, "until" and "prepared"; a verse in both would be in both, but none is. Each carries a no-side note. The panel should check whether the placement of Matt 11:12, Luke 16:16 (a present "is being preached") and Rev 1:9 reads as a lean toward "now"; and Luke 21:31 ("know that the kingdom of God is near") sits in row 12 although it is said of a future event. Luke 17:21 notes "in your midst" against "within you" (the Greek ἐντός).
2. **Rows 7 and 8: kingdom of heaven and kingdom of God.** The notes set Matt 19:23 beside 19:24 and Matt 13:11 beside Mark 4:11 and Luke 8:10 and say the page does not call them one. Matthew's four "kingdom of God" verses (12:28, 19:24, 21:31, 21:43) are in row 8. Dispensational and covenant readings part here; the panel should read whether "in Matthew alone" (row 7 note) is a fact (all 31 verses are in Matthew, checked on the build) that leans.
3. **Row 24: the thousand years.** Rev 20:4 and 20:6 only (the verb βασιλεύω); the rest of Rev 20:1-7 holds no kingdom word and is not in the hub. The note names pre-, post- and amillennial readings and takes no side, and says 2 Tim 2:12 (a different verb) is not in. Luke 19:12-27 (the nobleman and his kingship) is in this row because the nouns are there; the note says the page does not say whom he stands for. The panel should read whether putting the parable in the same row as the thousand years implies a link.
4. **Row 6 and row 5: Daniel.** The four kingdoms and the "kingdom that will never be destroyed" (Dan 2:44, 7:14, 7:18, 7:22, 7:27). Readings that place the stone kingdom at Christ's first coming, the church age, a millennium or the end part here; the note says so and takes no side. Dan 2:44 and 7:14 are in both rows 5 and 6.
5. **Row 21: Israel's kingdom and the kingdom of God.** Matt 21:43 ("taken away from you and given to a people who will produce its fruit"), Matt 8:11-12, Luke 13:28-29, 22:30, Acts 1:3 and 1:6, with "a kingdom of priests" (Exod 19:6; Rev 1:6; 5:10). Replacement, restoration and one-people readings part; the note says "whether the kingdom promised to Israel and the kingdom of God are one" and takes no side. The panel (the rabbi's seat especially) should read whether one row for "taken away" and "restored" and "priests" reads as claiming they are one story.
6. **Row 4: David's throne.** 2 Sam 7:12-16, 1 Chr 17:11-14, 22:10, 28:5-7, 2 Chr 13:5, 13:8, Isa 9:7, Luke 1:33, Mark 11:10. The note names the Jewish reading and Christian traditions as parting on how it stands to Jesus' kingdom and to Israel; 1 Chr 28:7 keeps its "if". The Jewish seat should read it.
7. **Rows 18, 19: enter, inherit, "will not inherit".** John 3:3 and 3:5 ("born of water and the Spirit": the note names baptism, birth, the word and the Spirit as readings), Matt 5:20, 7:21, 18:3, the camel and the needle, and 1 Cor 6:9-10, 15:50, Gal 5:21, Eph 5:5 ("will not inherit"). The note says traditions part on whether a person who has been saved can fall short and takes no side. The panel should check that listing the vice lists beside "inherit" reads neutrally.
8. **Row 20: the keys.** Matt 16:19 and 23:13 only; the note says readers part on to whom the keys are given and what binding and loosing are. Two verses kept as a row because the text sets them apart.
9. **Row 22: at table.** Matt 26:29, Mark 14:25, Luke 22:16-18 are the Last Supper; the note says what the Supper is and how it looks ahead is a point on which traditions part (real presence, memorial and others are not named: the hub names no reading of the Supper).
10. **Rows 9, 10 and the catch-all: the divine persons by hand.** Row 9 only where the verse names the Son, the Son of Man, Jesus or Christ, or is Jesus' own "My"; row 10 only where the verse names the Father. 2 Tim 4:18 ("the Lord ... His heavenly kingdom") is left in the catch-all with the "readers take it of Christ or of the Father" note; Ps 45:6 / Heb 1:8 ("Your throne, O God") is in row 5 with the note that readers part on whom Ps 45 addresses, and Heb 1:8 is in row 9 ("about the Son He says"). The panel should read whether Heb 1:8 in row 9 and Ps 45:6 in row 5 reads as placing the psalm.
11. **Row 14: John 18:36.** "My kingdom is not of this world" beside Luke 17:20-21, Rom 14:17, 1 Cor 4:20. The note says what "not of this world" means for now and later is a point on which traditions part. It stands next to rows 12-13, which it could be read as favouring.
12. **Row 5, 2 and 26: the earthly kingdoms.** Esth 5:3 and Mark 6:23 ("up to half the kingdom") sit in an earthly row, and Luke 4:5-6 (the devil's offer of "all the kingdoms of the world") in row 1; the notes say they are what a king offers and what the devil shows, and no more. The devil's claim ("relinquished to me") is the text's.

## What the builder could not express

- **A pick row with the same check as `add`.** Picks are not checked against the concept's words (an `add` row is). I checked by hand: no `"words": []` in any row's examples, and the verse total (438) did not rise when I removed the one pick that was not a hub word (2 Tim 2:12). A `pick_checked` option would make a mistyped reference fail rather than pass silently.
- **A clause that starts in the previous verse.** The rule row for "kingdom of God" files 1 Cor 6:10 under 6:9 (the builder's clause rule), so 6:10 needed `add`.
- **A Berean-English condition.** The rule rows read the original lemmas; "royal", "reign", "realm" and "sovereignty" are the Berean's choices for the same Hebrew and Aramaic words, and the rows for them are by hand.
- **A phrase window wider than one word, both sides, in a different order.** "The kingdom of Christ and of God" (Eph 5:5) is not read as "of God"; it is by pick in rows 9 and 19.
- **Verses with no kingdom word that matter for the points here:** the thousand years (Rev 20:1-7 beyond 20:4, 20:6), "the LORD reigns" (מָלַךְ), "I will build My church" and the stone kingdom's context, Luke 17:21's "within you" reading, Matt 19:28 (the regeneration, twelve thrones). They are not in the hub by design (a hub row holds only verses with the concept's word); a door to the theme cards "The LORD reigns" and "The kingdom of God has come" is in row 5 and row 12.

## Process notes

- Builds: (1) first draft, 26 rows, catch-all 81 verses; (2) the leftover senses as a new row and the additions; (3) after the 16-verse sample; (4) notes. All shell commands were the build and `curl -s http://localhost:8012/...`; the verse texts for the pick lists were read from `data/bible/verses.bsb.jsonl` (the file the server serves) with the Grep tool, and the sample verses through the server.
- The grep over the Berean text (`kingdom`) found 347 verses; the nouns also stand in 91 more where the Berean prints reign, kingship, royal, realm, dominion or sovereignty (rows 24 and 26, plus the additions to rows 2 and 5).
