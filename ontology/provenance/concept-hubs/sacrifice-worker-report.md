# sacrifice hub: report

Spec: `<local> Ontology\ontology\concept-hubs\sacrifice.json` (`"shown": false`). Built: `<local> Ontology\out\concept-hubs\sacrifice.json`. Builds run: 5 (rule draft; the full spec; the 16-verse check; the fixes it found; notes). Cards missing: none. Every verse the words stand in is in a row (noun 443, verb 153; "More" is 0 in both). 24 rows: 18 noun (17 + catch-all), 6 verb (5 + catch-all).

## Words

Own words (sense rule `sacrific|offer|burnt` on MACULA's gloss in the verse):

| word | kept | dropped as another sense |
|---|---|---|
| זֶבַח (noun, sacrifice) | 152 | 1 |
| זָבַח (verb) | 118 | 9 (Deut 12:15, 12:21, 2 Kgs 23:20, Ezek 34:3 and others: "slaughter", meat for eating) |
| עֹלָה (noun, burnt offering) | 259 | 1 |
| דְּבַח noun / verb, עַלְוָה (Aramaic of Ezra) | 1 / 1 / 1 | 0 |
| θυσία | 28 | 0 |
| θύω | 6 | 7 (kill, slaughter: Matt 22:4, Luke 15:23, John 10:10, Acts 10:13) |
| ὁλοκαύτωμα | 3 | 0 |
| προσφορά | 9 | 0 |
| προσφέρω | 25 | 19 (bring, present) |
| ἀναφέρω | 4 | 5 (bear, carry up) |
| εἰδωλόθυτος (set with the nouns) | 10 | 0 |

The card lists three Hebrew words and no Greek one. The Greek was added because Heb 5-10 and Matt 5:23 cannot be reached without προσφέρω and ἀναφέρω (Heb 9:14 and 9:28 are verbs only). The hub never says Hebrew and Greek are one word: every example is tagged with the word it stands on.

`sense_keep`: 2 Chr 18:2 (MACULA "slaughtered", Berean "sacrificed"). `sense_drop`: Matt 2:11 (magi "offered gifts"), Luke 23:36 (soldiers "offering" wine), Acts 8:18 (Simon "offered" money), each limited to προσφέρω.

`others` ("Other words translated sacrifice and offering", each with its verses, never handed over as the same word): מִנְחָה 158 (grain offering or gift; Gen 4:3-5, Cain and Abel, is this word and not זֶבַח), חַטָּאת 109 (sin and sin offering, one word), עָלָה 80 (the verb "go up"), קׇרְבָּן 78, אִשֶּׁה 64, נֶסֶךְ 58, שֶׁלֶם 57, קָרַב 45, אָשָׁם 34, תְּנוּפָה 24, נְדָבָה 21, תְּרוּמָה 19, קָטַר 18, and a few Aramaic words (Ezra, Dan 2:46). Excluded: עָשָׂה "do" (the Berean prints "offer" for "make a burnt offering") and צָבַט (Ruth 2:14, "offered her roasted grain"). `add` puts first the verses that show each word and gives five of them a note. min_share raised to 0.6 to drop one-verse strays.

## Rows (the order is the Bible's order of the earliest verse each row holds; the catch-alls last)

Noun form, title "What the text says of sacrifice" (lead):

| # | row | n | how filled |
|---|---|---|---|
| 1 | A pleasing aroma | 25 | pick (the 24 the rule on נִיחֹחַ / ὀσμή gave, plus Gen 8:21) |
| 2 | Isaac: "offer him as a burnt offering", "the lamb for the burnt offering" | 8 | pick (Gen 22:2, 3, 6, 7, 8, 13; Heb 11:17; Jas 2:21) |
| 3 | Bull, ram, lamb, goat, dove; "without blemish" | 113 | rule: animal words or תָּמִים / ἄμωμος in the verse; 1 not_verse |
| 4 | Eating from the sacrifice | 29 | rule: אָכַל / ἐσθίω; 5 not_verses where the fire or the sword "consumes" |
| 5 | The Passover | 10 | pick (Hebrew and the Greek verbs: Exod 12:27, Deut 16, Mark 14:12, Luke 22:7, 1 Cor 5:7) |
| 6 | Peace offering, thank offering, vow, freewill offering | 96 | rule: שֶׁלֶם, תּוֹדָה, נֶדֶר, נְדָבָה in the verse |
| 7 | Blood beside sacrifice | 23 | rule: דָּם / αἷμα |
| 8 | Daily, Sabbath, New Moon and festival offerings | 41 | rule: תָּמִיד, שַׁבָּת, חֹדֶשׁ, חַג, ἑορτή, σάββατον; 1 not_verse; add Lev 23:37, Num 15:3 |
| 9 | Atonement made; a hand laid on the head | 25 | rule: כִּפֶּר, ἱλ- words, סָמַךְ |
| 10 | Sacrifice and sin: the sin offering, the guilt offering, "for sins" | 62 | rule: חַטָּאת, אָשָׁם, ἁμαρτία |
| 11 | Sacrifice set beside what the LORD asks: not desired, not accepted, "mercy, not sacrifice" | 26 | pick |
| 12 | A son or daughter given in sacrifice | 5 | pick |
| 13 | Other gods, idols and demons | 14 | rule: the idol words (incl. εἰδωλόθυτος) |
| 14 | Thanksgiving, praise, a broken spirit, bodies and lives as sacrifices | 15 | pick |
| 15 | Sacrifice in days to come: offered again, or brought to an end | 14 | pick |
| 16 | The Lord's table: blood "poured out", "in remembrance of Me", "a participation" | 8 | pick |
| 17 | Offered again and again, unable to cleanse; once for all | 8 | pick (Hebrews) |
| 18 | Every other use: sacrifice, offering (note names the fire, Abel, Ps 50:8, Amos 5:25) | 100 | catch-all |

Verb form, title "Who sacrifices, to whom, and where":

| # | row | n | how filled |
|---|---|---|---|
| 1 | Sacrificed to the LORD, before the LORD | 37 | pick (the rule on the LORD in the verb's clause gave 34; Exod 5:8, 8:25, 1 Sam 6:15, Mal 1:14 added) |
| 2 | Other gods, idols and demons | 19 | pick |
| 3 | At the high places, on the hills, under the trees | 16 | rule on בָּמָה (13) + add Isa 57:7, Hos 4:13, Ezek 20:28 |
| 4 | The gift offered at the altar and by the priest, "according to the law" | 11 | pick |
| 5 | Christ offered Himself; Christ our Passover lamb has been sacrificed | 6 | pick (Heb 7:27, 9:14, 9:25, 9:28, 10:12; 1 Cor 5:7) |
| 6 | Every other use: sacrificed, offered | 65 | catch-all (note) |

## The 16-verse sample (read in the Berean through /api/verse, deeper than the first examples)

| verse | row | verdict |
|---|---|---|
| Lev 3:5 | A pleasing aroma | pass ("a pleasing aroma to the LORD") |
| Gen 22:6 | Isaac | pass (the wood for the burnt offering placed on Isaac) |
| Judg 6:26 | Bull, ram ... | pass ("take the second bull and offer it as a burnt offering") |
| Deut 32:38 | Eating | pass ("ate the fat of their sacrifices") |
| 2 Chr 35:16 | The Passover | pass |
| Prov 7:14 | Peace offering, ... vow | pass ("I have made my peace offerings; today I have paid my vows") |
| Acts 21:25 | Blood | pass ("food sacrificed to idols, from blood") |
| Neh 10:33 | Daily, Sabbath ... | pass ("regular grain offerings and burnt offerings ... Sabbath ... New Moons and appointed feasts") |
| 1 Sam 3:14 | Atonement made | pass (hard verse: "never be atoned for by sacrifice or offering") |
| Isa 43:24 | Sacrifice for sin (as first labelled) | FAIL: "the fat of your sacrifices ... burdened Me with your sins" is not "sacrifice for sin". Fixed: relabelled "Sacrifice and sin: ...", which the verse shows; the hard verse stays |
| Amos 5:25 | Sacrifice not desired, not accepted (as first labelled) | FAIL: a question ("Did you bring Me sacrifices and offerings forty years in the wilderness?"), not a statement. Fixed: out of the row (with Mic 6:7, also only a question); the row relabelled "set beside what the LORD asks"; the question is named in the row's note and the catch-all's note |
| Rev 2:14 | Other gods, idols and demons | pass ("eat food sacrificed to idols") |
| Rom 15:16 | Thanksgiving ... bodies and lives | pass ("the Gentiles might become an offering acceptable to God") |
| Zech 14:21 | Sacrifice in days to come | pass ("all who sacrifice will come and take some pots and cook in them") |
| 1 Cor 10:21 | The Lord's table | pass ("the table of the Lord and the table of demons") |
| Heb 9:9 | Offered again and again ... | pass ("gifts and sacrifices being offered were unable to cleanse the conscience") |

Read besides, all passing: Exod 8:25 (sacrifice to your God), Ezek 20:28 (any high hill or leafy tree), 2 Kgs 10:25 (the burnt offering and the temple of Baal), Hos 13:2 (human sacrifice, the calves), Hos 9:4, Jer 19:5, 2 Chr 34:4, Acts 14:13, 14:18, Hos 4:13, Mal 1:14, Heb 9:7, 9:25, and the Ezekiel 40-46 verses of the "days to come" row. Tally: 14 of 16 passed on first reading, 2 failed and were fixed; after the rebuild the fixed verses read: Isa 43:24 now sits under a label it shows, Amos 5:25 is in the catch-all (checked in the built file). 16 of 16.

Other things fixed from reading, before the sample: `מוֹעֵד` ("Tent of Meeting" as well as "appointed time") had put Lev 1:3, 4:7, 12:6 in the festival row (removed; Lev 23:37 and Num 15:3 added by hand); `אֵילִם` ("porticoes") is lemmatised as אַיִל "ram" in MACULA, which put Ezek 40:38 in the animals row (not_verses); the idol rule had the wrong lemma for εἰδωλόθυτος (it is the adjective `εἰδωλόθυτος`); the "Eating" rule took the fire that "consumes" the burnt offering (Lev 6:10, 9:24, 1 Kgs 18:38, 2 Chr 7:1) and the sword in Jer 46:10 (not_verses with reasons); the first-draft "priest offers" rule row took Exod 5:3 and 8:25-28, apparently because Aaron (with Moses) was the agent in its set (dropped; Hebrews' priest verses are in the gift row).

## Contested points for the review panel (row, verses, which readings part)

1. **What a sacrifice does.** Rows 1 (aroma, Gen 8:21; Lev 1:9; Eph 5:2; Phil 4:18), 9 (atonement made, "he will be forgiven", Lev 4:26; 5:10; the hand laid on the head, Lev 1:4; 4:24), 7 (blood, Lev 4:7; Ezek 43:18), 3 (without blemish), 4 and 6 (eating, peace offerings), 10 (sin). Readings that part: covering or cleansing, ransom or substitution, turning wrath away (propitiation), pleasure and acceptance, fellowship or communion; the hand as identification, dedication or transfer. Each of the first four rows carries a note that the page takes no side. No row orders them: the rows are in the Bible's order of their earliest verse. The Hebrew כִּפֶּר is not set equal to סָלַח (the note points to the forgiveness page, which sets them side by side). Panel to read: whether "he will be forgiven" in the atonement note tilts toward a penal or a purely ritual reading.
2. **Fulfilled, ended or continued.** Row 17 (Heb 7:27; 9:9; 9:26; 10:1; 10:10; 10:11; 10:12; 10:14), row 11 (Ps 40:6 beside Heb 10:5, 8; Hos 6:6; Matt 9:13; Jer 7:22-23; Isa 1:11; Amos 5:22-24; Mic 6:6-8), row 15 (Isa 56:7; 19:21; Jer 33:18; Ezek 40:39, 43:18, 43:27, 44:11, 45:17, 46:2, 46:24; Ps 51:19; Zech 14:21; Hos 3:4; Dan 9:27), verb row 4 (Matt 5:23-24; 8:4; Acts 21:26; Heb 5:1, 3; 8:3, 4; 9:7). Readings that part: the sacrifices of the law fulfilled in Christ's; ended by it; still to be offered (Ezek 40-46, literally); Ezekiel's sacrifices as a picture of worship; the "he" of Dan 9:27 (a past king, a Roman, a future figure). Each carries "readers part ... the page takes no side". Row 11 is the one most likely to read as a verdict ("set beside what the LORD asks"): it holds statements and Mic 6:6 with 6:8 and Jer 7:22 with 7:23, and names the Amos 5:25 question separately.
3. **Jer 7:22.** The Berean prints "did not merely command them"; the Hebrew (read in MACULA, `24-Jer-007`) has no word for "merely": not spoke with your fathers, not commanded them, on the day He brought them out of Egypt, concerning burnt offering and sacrifice. The row's note says so. A finding for `ontology/translation-findings.json` / a verse mark, not made by me (not my file).
4. **The Lord's Supper.** Row 16: Matt 26:28; Luke 22:19, 20; 1 Cor 10:16, 18, 21; 11:24, 25. Readings that part: the Supper as itself a sacrifice, as a memorial ("in remembrance"), as participation in Christ's body and blood, as more than one. Only 1 Cor 10:18 has a sacrifice word. The row is the one place the hub sets verses with none of the card's words, on the card's graph (`event_last_supper` is a core concept of the card; its refs are Matt 26:28 and Luke 22:20). Mark 14:22-24, Matt 26:26-27, 1 Cor 11:23, 26 and Heb 13:10 ("We have an altar") are left out to hold to what the graph backs. Panel to say: widen, keep, or drop.
5. **Christ's sacrifice by hand (verb row 5, noun row 17).** Heb 9:14, 9:28, 1 Cor 5:7 name Christ; Heb 7:27, 9:25, 10:12 say "He", "Himself", "this Priest" inside Hebrews' argument where Jesus is named (7:24, 9:24, 10:10). The note says which is which; Hebrews is not in doubt on whom it means, so the note does not say "readers differ" on that. What the sacrifice does (atones, redeems, substitutes, conquers, shows love) is left to "readers take differently".
6. **Eating from the sacrifice (row 4)** as communion: Lev 7:15; Deut 12:27; 1 Cor 8:10; 10:18 ("fellow partakers in the altar"); Rev 2:14, 20; and the hard verses: Ezek 39:17-19 (the LORD's sacrificial feast for birds and beasts), Hos 9:4, Num 25:2. Readings that part: the meal as fellowship with the LORD, gift received, sharing in the offered.
7. **Sacrifice and sin (row 10), Heb 10:26** ("no further sacrifice for sins remains"): stays with Heb 10:12 and 10:18. Readings that part: whether a believer can fall away. Note names it and takes no side (the sin and salvation pages are the other places).
8. **Isaac (row 2)**: Heb 11:17 and Jas 2:21 (the latter inside the faith and works argument). Note: a test, a substitute, a picture of a later sacrifice.
9. **Children given in sacrifice (row 12)**: 2 Kgs 3:27, Ps 106:37-38, Jer 19:5 ("something I never commanded"), Ezek 16:20. Hard verses kept; Judg 11:31 (Jephthah's vow) is only in the catch-all.
10. **Other gods (row 13, verb 2)**: Paul on food sacrificed to idols (1 Cor 8; 10:19-21; Acts 15:29; Rev 2:14, 20) sits with 2 Kgs 5:17 (Naaman's vow). Readings of 1 Cor 8-10 and Acts 15 part, and the page says nothing of them.
11. **The prophets' "sacrifice of the LORD"** (Isa 34:6; Jer 46:10; Ezek 39:17-19), a day of judgment pictured as the LORD's own sacrifice: kept (blood and eating rows) and named in the notes; hard verses stay.
12. **Divine persons**: nothing is placed by rule. The Father/Son/Spirit are not the subject of any row; "Christ offered Himself" is by pick; the aroma "to the LORD" and "sacrificed to the LORD" rows say what the verse says.

## What the builder could not express

- **A verb verse with no frame is never seen** (Exod 5:8, Exod 22:20, 1 Sam 2:15, 1 Sam 6:15, 2 Chr 34:4, Hos 13:2, Zech 14:21): no rule row and no catch-all reaches it; I found them by comparing MACULA's list of זָבַח (128 verses) with the verb form (about 120) and put them in pick rows. Wanted (as the forgiveness worker said): add every verse the verb stands in to `seen_form`, so unplaced ones fall into the catch-all or "More". 1 Sam 2:15 is not in any row (a man "sacrificing", the priest's servant asking for raw meat): it is the only one I did not place, and it would be in the verb catch-all if the option existed.
- **A pick row cannot also carry a rule** (a row of "A pleasing aroma" had to become a pick row to add Gen 8:21). A row with `pick` plus `rule` (the rule's verses and these extras) is the option I wanted.
- **A negative condition on a word in the verse** (not_in_verse); not_verses with a reason did it ("consumes" is the fire, not eating).
- **A rule on a lemma that stands for two words in MACULA** (אֵילִם / אַיִל; מוֹעֵד "Tent of Meeting" / "appointed time"): I used not_verses and `add`.
- **The row's tag for a picked verse that lacks a word of the card** (Gen 8:21, the Supper's verses, 2 Tim 4:6) is empty; the example shows no word tag, as it should, but a reader may wonder why it is there. The notes say so.
- **`others.add` does not check that an added verse has the word**: I read each (Gen 4:3-4, Lev 2:1, Exod 29:14, Lev 4:3, Lev 5:15, Isa 53:10, Exod 20:24, Lev 7:13, Gen 8:20, Gen 22:13).
- **Numbering**: `/api/verse?ref=Exod.8.25` returns the Berean text of 8:25 beside the Hebrew words of Hebrew 8:25 (which is the Berean's 8:29). The hub's verse lists are in the Berean's numbering (`moves` and `bsb()` handle it), so the hub is right; the verse card's original-language strip is out of line in Exodus 8. Observed, not touched.

## Not included, on purpose, with the reason

- Lev 17:11 ("the life of the flesh is in the blood ...") and Heb 9:22 have no word of the card's own; both are among the verses at the head of the page (own_words), not in a row.
- Gen 4:3-5 (Cain and Abel) is מִנְחָה, a different word; named in `others`. Mal 1:11, Mal 3:3-4, Isa 66:20, Isa 60:7 likewise (grain offering or "go up").
- A row on "fire from the LORD consumes the offering" (Lev 9:24; Judg 6:21; 13:20; 1 Kgs 18:38; 1 Chr 21:26; 2 Chr 7:1): left to hold the page to 24 rows; the verses are in the catch-all and named in its note. Could be a row of 5-6.
- A row on the Israelite offerings of the first fruits, tithes, wave offerings: different words (תְּנוּפָה, תְּרוּמָה), in `others`.
- Deut 12:15, 21 (זָבַח "slaughter" for eating meat) and 2 Kgs 23:20: dropped by the sense rule.
- Hos 4:14, Hab 1:16, Isa 65:3: name no other god or no hill and are in the catch-all.
- Acts 22:16, Rom 3:25 (ἱλαστήριον), 1 John 2:2 and 4:10 (ἱλασμός): no word of the card's own in the verse; they belong to the atonement and propitiation cards.
