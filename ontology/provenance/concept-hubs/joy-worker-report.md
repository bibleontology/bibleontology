# Joy hub report (consolidated: 65 rows to 25; after the panel's fixes: 26)

Current state after the review panel: see the last section, "Panel fixes". Where the sections above give row counts, noun/verb numbers, or row lists, the Panel fixes section supersedes them: 26 rows (12 noun, 13 verb, 1 adjective); 177 noun, 257 verb and 19 adjective verses placed; "More" 0.

Spec: `ontology/concept-hubs/joy.json` (`"shown": false`, 25 rows: 11 noun, 13 verb, 1 adjective). Built: `out/concept-hubs/joy.json`. Cards missing: none. Builds: 5 for the first version, 3 for the consolidation and the new builder options. The 65-row version is kept at `scratchpad/hubs/joy/joy-65rows.json` (spec) and `out-65rows.json` (output); the generator is `scratchpad/hubs/joy/consolidate.py`. Placed: 177 noun, 258 verb and 19 adjective verses; "More" is 0 in every form. The 258 is 260 minus 2 deliberately dropped by `sense_drop` (2 John 10-11, the greeting χαίρω).

## Words (17) and what they cover

Nouns: שִׂמְחָה 88, χαρά 57, שָׂשׂוֹן 22, מָשׂוֹשׂ 15, חֶדְוָה 2, גִּילָה 2, גִּיל (noun, h1524) 6, ἀγαλλίασις 5.
Verbs: שָׂמַח 146, χαίρω 59 (+9 "Greetings"/"Hail", dropped by the sense filter), גִּיל 44, שׂוּשׂ 24, חָדָה 3, συγχαίρω 7, ἀγαλλιάω 11, εὐφραίνω 14.
Adjective: שָׂמֵחַ 21.

The card lists six nouns. As asked, the verbs of the same families are words: שָׂמַח and שָׂמֵחַ with שִׂמְחָה; שׂוּשׂ with שָׂשׂוֹן and מָשׂוֹשׂ; גִּיל with גִּילָה and the noun גִּיל (h1524, a word the card did not list); חָדָה with חֶדְוָה; χαίρω and συγχαίρω with χαρά. The Greek words that render them are included on the brief's rule: ἀγαλλιάω and ἀγαλλίασις (LXX for גיל) and εὐφραίνω (LXX for שמח). The verse keeps the word it uses.

Word order in the spec matters: h1523 (verb גִּיל) stands before h1524 (noun גִּיל). The builder keys a word by pointed lemma and the later one wins.

`sense`: `joy|rejoic|glad|exult|merr|mirth|gaiety|cheer|happ|delight|enjoy|pleasure|jubil|gloat|glee`. "Delight/pleasure/enjoy/mirth" are how the Berean renders the same Hebrew word (Eccl 2:1-2, 8:15; Deut 28:63); "gloat/glee" are שָׂמַח at an enemy's fall. Dropped as another sense: χαίρω as "Greetings"/"Hail" (9), שָׂמַח "welcomed" (Isa 39:2).

## Others (named apart, not in rows)

רָנַן "sing for joy" 34 verses; עָלַז "exult" 15; רִנָּה 11; עָלַץ 7; עַלִּיז 5; רְנָנָה 4; εὐφροσύνη 2; and singletons (טְאֵב Aramaic, הֵד, Aramaic חֶדְוָה h2305, עָלֵז, מַבְלִיגִית, עָלַס, סָלַד, σκιρτάω "leap for joy"). The regex excludes "gladly" (ἡδέως, an adverb) and "jubilee" (יוֹבֵל, a year). The Aramaic חֶדְוָה (Ezra 6:16) has the same spelling as h2304 and would shadow it, so it stays in others.

## The 26 rows (n) and what merged into what

Counts are verses. "A+B" means the old rows were merged; old counts in brackets.

**Noun (11)**
1. Joy from the LORD: given by God, in His presence, in His word, **34** [Joy God gives 17 + Joy in the presence of the LORD 9 + Joy and the word, the testimonies 7 + The joy of the LORD, of God 2 (the rule on the divine name next to the noun, with its note)]. Pick; divine-person row kept by hand, note on "the joy of the LORD" kept.
2. Joy and the Holy Spirit, 5 (unchanged; pick, note).
3. The joy of Jesus, 3 (unchanged; pick).
4. Joy in heaven over one sinner who repents; "Enter into the joy of your master"; joy and the kingdom, **6** [Luke 15:7, 10 + Matt 25:21, 23 + Matt 13:44, Rom 14:17]. Pick; the no-side note (repentance, who the master is) kept.
5. Joy and salvation, rescue, victory: the redeemed, the good news, a king enthroned, **15** [Joy and salvation 7 + Joy at a victory, a rescue, a king enthroned 8].
6. Joy beside peace, love, hope and faith; joy filled, full, complete, **27** [Joy and peace 6 + Joy, hope and faith 8 + Joy and love 5 + Joy filled, full, complete 13]. One rule on the union of the words; love by `add`.
7. Joy and sorrow: trial, affliction, mourning, weeping; joy taken away, ended, **40** [Joy and trial 9 + Joy and mourning 18 + Joy taken away, ended 17 (picks, now `add`)].
8. Joy weighed: pleasure and mirth; the righteous and the wicked, fools and sinners, **13** [Joy, pleasure and mirth weighed 7 + Joy, the righteous, the wicked, fools and sinners 8; picks].
9. Joy at feasts: food, wine, the harvest, the bride and bridegroom, **32** [Joy beside feasts 26 + The voice of joy and gladness, the bride and bridegroom 6; rule union].
10. Joy with singing, music and dancing; in Zion, in Jerusalem; at the ark, the sacrifice, the altar, **41** [singing 25 + Zion 16 + ark 7; rule union].
11. Every other use of the joy nouns, 38.

**Verb (13)**
1. The LORD rejoices, delights, 8 (unchanged; pick; Deut 28:63 and its note kept).
2. Jesus rejoiced, 2 (unchanged; pick).
3. The LORD makes glad: made them glad; asked to make us glad, **12** [7 + 5; picks].
4. Rejoice in the LORD, in God, in the Lord; before Him; in His salvation, His word, what He has done, **48** [Rejoice in the LORD 22 + in the Lord 3 + before the LORD 9 + at what the LORD has done 7 + in salvation 7 + in the word 3]. Pick; the note on "the Lord" (κύριος) kept.
5. Rejoice over what was lost and found, 6 (unchanged; pick, note).
6. Who rejoices: the righteous, the upright, the humble, Zion and Jerusalem, the heart, the heavens and the earth, **49** [14 + 15 + 12 + 8].
7. Rejoicing together: the household, the people, rejoice with others; "I rejoice" over you; in the truth, **46** [together 6 + rejoice with 7 + the people 19 + "I rejoice" in the letters 16 + in the truth 3].
8. Told to rejoice, and told not to, **38** [Told to rejoice 32 (rule: stance "command") + Told not to rejoice 7]. The prohibitions (Hos 9:1, Isa 14:29, Ezek 7:12, Prov 24:17, Obad 12, Mic 7:8, Luke 10:20) are commands too, so the rule takes them and they no longer need picking or excluding; the "do not rejoice" verses are kept.
9. Rejoice at what they see or hear, 32 (unchanged; pick).
10. Rejoice in trials and sorrow: suffering, persecution; rejoice and weep, **25** [8 + 18; rule union].
11. Everyday joy: one's work and youth, a wife, a son; what makes glad (wine, oil, a good word); making merry at a feast, **38** [Ecclesiastes 7 + wife 4 + son 11 + what makes glad 9 + make merry 9].
12. Rejoicing over another's fall or ruin, at judgment; in wealth, an idol, plunder, evil, **27** [fall 17 + judgment 4 + wealth/idol 6]. Note kept (the righteous rejoicing at judgment; no side).
13. Every other use: rejoice, be glad, exult, **27** (24 + Job 3:6, John 5:35, Prov 13:9, which had been in the removed "Not joy in the Berean's words" row; the row carries a note about them). The old "greeting" row is gone: 2 John 10-11 are out of the concept by `sense_drop`.

**Adjective (1)**
1. Glad, joyful, rejoicing: of heart; the people at a king, a feast; and over another's calamity, **19** [glad heart 7 + people 8 + calamity 3 + the rest].

## 2 John 10-11, Job 3:6, John 5:35, Prov 13:9 (with the builder's new `sense_drop`)

- **2 John 10-11: dropped** by `sense_drop` (limited to g5463). The original is the greeting idiom χαίρειν λέγειν ("greet"), not joy; the Berean prints "greet". They are no longer in the concept at all (verb verses 260 to 258).
- **Job 3:6, John 5:35, Prov 13:9: kept**, in "Every other use: rejoice, be glad, exult", with a note on the row. I checked the original, not only the English: MACULA glosses each with the joy word (חָדָה "rejoice", ἀγαλλιάω "to rejoice", שָׂמַח "rejoices"), so the original IS joy and only the Berean rewords (a curse on the night; "bask in his light"; "shines brightly"). Job 3:6 is the least sure: the Hebrew form could be read as יחד "be joined" (some do), which the Berean seems to follow; if the owner reads it so, it is a one-line `sense_drop` addition (g? h2302, "Job.3.6").
- The "Not joy in the Berean's words" row is removed (it would have held only these three, which are now in the catch-all). The builder's other new option, `not_verses` honoured in the catch-all row, was not needed.

## Examples check (the four examples of every merged row, read in the Berean text)

Every one of the 26 rows' four examples was read after the last build. First pass found that merged rows showed only the first of their parts (e.g. "Rejoicing together" showed four Deuteronomy household verses; "Who rejoices" showed four "righteous" verses; "Everyday joy" four Ecclesiastes verses; "Rejoicing over another's fall" four fall verses; "Joy and salvation, rescue, victory" no victory). Fixed with `lead` so each part of the label is shown in the first four:
- Joy from the LORD: Neh 8:10 (joy of the LORD), Ps 16:11 (presence), Ps 45:7 (God anoints with the oil of joy), Jer 15:16 (the word) - pass
- Joy and salvation, rescue, victory: Isa 12:3, Isa 35:10, 1 Kgs 1:40, Esth 8:17 - pass
- Joy weighed: Eccl 2:1, Prov 14:13, Prov 10:28, Luke 15:7 - pass
- Joy at feasts: Esth 9:19, Jer 7:34 (bride and bridegroom), Neh 8:12, Isa 62:5 - pass
- Rejoice in the LORD...: Ps 32:11, Phil 4:4, Deut 12:7 (before), Isa 25:9 (salvation) - pass
- Who rejoices: Ps 32:11, Zeph 3:14, Ps 35:9 (soul), Ps 96:11 (heavens) - pass
- Rejoicing together: Deut 16:11, Rom 12:15, Rom 16:19, 2 John 4 - pass
- Everyday joy: Eccl 3:12, Prov 5:18, Prov 10:1, Ps 104:15 - pass
- Rejoicing over another's fall...: Job 31:29, Ps 58:10, Job 31:25, Obad 12 - pass
- Adjective row: 1 Kgs 1:40, Prov 15:13, Prov 17:5, Deut 16:15 - pass
- Rows whose first four already showed the label (unmerged, or merged from like rows): Joy and the Holy Spirit, The joy of Jesus, Joy in heaven / master / kingdom (Luke 15:7, 15:10, Matt 25:21, 25:23), Joy beside peace... (Rom 15:13, Gal 5:22, Isa 55:12, 1 John 1:4), Joy and sorrow (Jas 1:2, Ps 30:11, Jer 31:13, John 16:20), singing/Zion/ark (1 Chr 15:16, Luke 24:52, 1 Chr 15:25, 1 Kgs 1:40), and verb rows 1-3, 5, 8-10 and the catch-all (row 13; its first four, 1 Sam 11:15, Acts 15:31, 1 Pet 1:8, 2 Chr 15:15, show the label; Job 3:6, John 5:35 and Prov 13:9 are not among them and are named in the row's note) - pass.

The earlier 32-verse sample of the rows (two rounds of 16; 26 passed first time, 6 weak ones fixed: 2 John 12, Heb 12:11, Isa 61:7, Ezek 35:14, Ps 46:4, Acts 7:41) still applies to the same verses; those fixes were carried into the merged rows (Heb 12:11 and Isa 61:7 and Song 3:11 and Ps 45:15 stay out by `not_verses`; Ezek 35:14 stays out; Acts 7:41 stays in the wealth/idol part only; Ps 46:4 in "what makes glad"). 2 John 12 now stands in the peace/love/hope/faith row for "our joy may be complete", which it says. A check of all 425 row verses for a joy word in the Berean text found only 5 without one: 2 John 10-11 (now dropped by `sense_drop`), Job 3:6, John 5:35, Prov 13:9 (in the catch-all with a note).

## Contested points for the review panel (row, verses, who)

1. **Divine persons by pick.** Verb rows 1 ("The LORD rejoices, delights"), 3 ("makes glad"), 4 ("Rejoice in the LORD..."), noun rows 1 ("Joy from the LORD") and 3 (Jesus), 2 (Holy Spirit). Isa 65:19 and Jer 32:41 are the LORD speaking in the first person (named in the same speech, not in the verse). Several picks are addressed "You" in a psalm whose opening names the LORD (Ps 4:7, 16:11, 21:6, 30:11, 51:8, 51:12, 92:4; Ps 5:11, 33:21, 40:16, 66:6, 89:16 in verb row 4). Panel: accept addressed "You" as naming Him, or drop those picks?
2. **Deut 28:63** in "The LORD rejoices, delights": the same verb for the LORD's pleasure in destroying. Kept with a note (hard verses stay).
3. **"Rejoice in the Lord"** (Phil 3:1, 4:4, 4:10; inside verb row 4): κύριος; the note says readers take it of Christ or of the Father. Verb row 2, "Jesus rejoiced" (Luke 10:21, John 11:15 by speaker).
4. **Joy and the Holy Spirit** (Gal 5:22, Rom 14:17, 15:13, 1 Thess 1:6, Acts 13:52): the page says no more than the verses.
5. **Joy in heaven over one sinner who repents** (Luke 15:7, 10), **Rejoice over what was lost and found** (Luke 15 and Matt 18:13): repentance is flagged high; both carry a no-side note. Luke 15:7, 10 also stand in "Joy weighed" (the righteous and the sinner) by the match-all rule. Row 4 now also holds "Enter into the joy of your master" (Matt 25) and the kingdom verses (Matt 13:44, Rom 14:17) with one combined note.
6. **Joy from the LORD** carries "the joy of the LORD" (Neh 8:10, Ps 43:4): his joy or the joy he gives; the note keeps the love hub's treatment of "the love of God".
7. **Rejoicing over another's fall or ruin, at judgment; in wealth, an idol...** (Ps 48:11, 58:10, 97:8, Rev 18:20): the righteous rejoicing at judgment; peace-church readers and love of enemies; the note says no side. The row now sets forbidden, reported and prayed-against gloating (Prov 24:17, Obad 12, Mic 7:8, Ps 35) beside the judgment verses and the joy in wealth and idols.
8. **Joy and sorrow** (Jas 1:2, 1 Pet 4:13 in verb row 10): no doctrine, but the label must not read as telling the suffering to be glad; it is "and".
9. **Joy beside peace, love, hope and faith** (Rom 15:13, 1 Pet 1:8, Phil 2:2): set side by side with no priority among them (flagged medium for love; the faith/love order).
10. **Joy and salvation, rescue, victory**: Judg 16:23 (the Philistines' joy over Samson) and Esth 8-9 (joy over defeated enemies): hard verses, kept.
11. **Everyday joy** / **Rejoicing over ... wealth, an idol**: unapproved joys (Luke 12:19, 16:19, Rev 11:10, Job 31:25, Hos 10:5, Acts 7:41) beside approved ones; labels are descriptive, not verdicts.
12. **Joy weighed** (Eccl 2:1-2, 7:4, Prov 14:13, 15:21, 21:17, Job 20:5): labelled by what verses weigh; a reader may take it as a verdict on joy.
13. **Told to rejoice, and told not to**: the stance "command" rule, with 10 reasoned exclusions (prayers that enemies not rejoice Ps 35:19, 35:24; a taunt Lam 4:21; a curse Job 3:6; prayers to the Lord Ps 86:4, 90:15; Prov 27:11, 23:25; 1 Pet 1:8 states; Judg 9:19 conditional).
14. **Rejoice at what they see or hear**, **Rejoicing together**, **Everyday joy**: judgement picks, no doctrine.
15. Verses kept because the original has the joy word although the Berean prints another (original arbitrates): Eccl 4:16, Jonah 4:6 ("pleased"), Hos 7:3 ("delight the king"), Ps 46:4, and Job 3:6, John 5:35, Prov 13:9 (in the catch-all with a note; Job 3:6 least sure).

## Builder limits met (options needed, builder not edited)

- **Global verse exclusion: now available** (`sense_drop`, `not_verses` in the catch-all); used for 2 John 10-11. No longer a limit.
- **Conditions are ANDed.** One row cannot take "agent in A, or Zion in the verse, or a heart": merging rule rows of different kinds meant converting them to picks (same verses as built and sampled) or using `in_verse` unions and `add`. An `any_of: [conditions]` would keep the rules.
- **Negation.** No `not_in_verse` / `negated`: "do not rejoice" was picked. (In the consolidation the stance rule takes them, which is also what the label now says.)
- **`not_agent`** (only `not_patient` exists): "rejoices in the LORD" without the LORD as the rejoicer was done by picks.
- **OR of agent and patient** in one row (Paul is agent in some frames and patient in others, 2 Cor 7:13): pick.
- **Collision of words with the same pointed lemma** (גִּיל verb/noun, חֶדְוָה Hebrew/Aramaic): worked around by spec order; a form-qualified key would remove the fragility.
- **Versification.** Ps 13:5-6 (Hebrew numbering) were filed one verse late; fixed with `moves`, as was 1 Chr 12:41.
- **`pick` rows accept verses with no occurrence of the row's form** unchecked; I validated picks against the occurrence data by script.
- **`add` ignores `not_verses`** and `lead` is shown for pick rows too (used).

## Notes

- Nothing outside `ontology/concept-hubs/joy.json` (and the builder's output `out/concept-hubs/joy.json`) was edited; no git; `shown` is false.
- Looping curl over `/api/verse` for all 425 verses never finished; the text check used the Berean text from the loaded data plus single curl calls.


## Panel fixes (review panel "ship after fixes": 13 fixes + 1 missing, all 14 applied)

Source: `scratchpad/hubs/joy-panel.json`. Generator: `scratchpad/hubs/joy/consolidate.py` (the "PANEL FIXES" block); 1 build (of 2 allowed). Row count 25 to 26 (one split). Verses: noun 177, verb 257 (260 minus 2 John 10-11 and Job 3:6 dropped by `sense_drop`), adjective 19; "More" 0 in every form. Cards missing: none.

| # | Panel point | Applied |
|---|---|---|
| 1 | Isa 9:3 filed under the LORD by inference ("You" not named near) | Removed from "The joy of the LORD..." (noun) and "Rejoice in the LORD..." (verb). It stays in "Joy and salvation, rescue, victory" and "Joy at feasts" (nouns); as a verb it now sits in the catch-all. |
| 2 | Rocky-ground hearers under a heading that says the joy is from the LORD | Mark 4:16, Matt 13:20, Luke 8:13 out of that row. Mark and Matt are now in "Every other use of the joy nouns"; Luke 8:13 is in "Joy and sorrow" and "Joy beside ... faith". |
| 3 | Label chooses "from" while the note refuses to | Relabelled "The joy of the LORD, and joy God gives: in His presence, in His word"; note kept. |
| 4 | Three unrelated sayings under one heading and one note | Split into "Joy in heaven over one sinner who repents" (Luke 15:7, 15:10; repentance no-side note, now covering exactly those two) and "Enter into the joy of your master; joy and the kingdom" (Matt 25:21, 25:23, Matt 13:44, Rom 14:17; note: whose joy the master's is, not decided; lead shows the kingdom part). |
| 5 | Zech 4:10 under "The LORD rejoices" | Removed (7 verses remain: Zeph 3:17, Isa 62:5, 65:19, Jer 32:41, Deut 30:9, 28:63, Ps 104:31). It stays in "Rejoice at what they see or hear". |
| 6 | Deut 28:63 note leaves out the setting | Note replaced with the panel's text (covenant curses; "just as ... so also"; kept as the text has it). |
| 7 | "Asked to make us glad" not shown | Lead set: Ezra 6:22, 2 Chr 20:27, Ps 90:15, Isa 56:7 (a request, Ps 90:15, is now third). |
| 8 | Torah festival commands missing from "Told to rejoice" | Nine added by hand (Lev 23:40, Deut 12:7, 12:12, 12:18, 14:26, 16:11, 16:14, 26:11, 27:7); the row is now 46 verses; lead Ps 32:11, Deut 16:11, Phil 4:4, Hos 9:1. |
| 9 | Luke 12:19 is the rich fool's self-address; "Rejoice always" beside "Do not rejoice" | Luke 12:19 excluded from the row (stays in "Everyday joy"); note added saying the prohibitions are about particular joys, not about joy as such. |
| 10 | Five verses that do not say anyone rejoices in trial | Lam 1:21, Hos 10:5, Prov 10:1, Prov 17:21, Prov 29:2 excluded (they stand in the fall row, the wealth/idol part, Everyday joy, and Rejoicing together); row relabelled "Rejoicing in suffering and persecution; rejoicing and weeping together" (20 verses). |
| 11 | "Everyday joy" hides the warning cases; Rev 11:10 | Rev 11:10 removed (it stays in the fall row); note: merry-making the text sets against itself or its makers (Luke 12:19, 16:19, Job 21:12); label now "one's work, one's household (a wife, a son); wine, oil and a good word; making merry at a feast"; lead Eccl 3:12, Prov 5:18, Ps 104:15, Luke 15:23 (the son, Prov 10:1, is the fifth example, so the four examples show work, household, wine and oil, the feast). |
| 12 | Job 3:6 a minority parse; note used the word MACULA | Job 3:6 added to `sense_drop` (h2302); the catch-all note rewritten without "MACULA": John 5:35 and Prov 13:9 are the ordinary "rejoice" words that the Berean renders "bask" and "shines brightly". |
| 13 | Merged noun rows whose examples miss a part of the label | Leads: "Joy and sorrow": Jas 1:2, Ps 30:11, John 16:20, Isa 24:8 (joy taken away); "Joy and salvation, rescue, victory": Isa 12:3, Isa 35:10, Luke 2:10 (good news), 1 Kgs 1:40 (king); "Joy with singing...": 1 Chr 15:16, Luke 24:52, 1 Chr 15:25 (ark), Ps 43:4 (the altar); also "Joy weighed" fourth example is now Ps 97:11, not Luke 15:7. |
| M | Missing: καυχάομαι ("boast"; the Berean prints "rejoice"/"exult") | `others.add` g2744 with Rom 5:2, 5:3, 5:11, Jas 1:9 and the note "The Greek is καυχάομαι, 'to boast'; the Berean prints 'rejoice' or 'exult' in these four verses. A different word from the joy words above, named apart." It is in the "other words" block, never in the rows. |

Points the panel marked "fine" were left as they were (addressed-"You" psalm picks, the Lord/Jesus rows, the Holy Spirit row, fall/ruin/wealth row, peace/love/hope/faith row, victory row, rule 4 on the Greek words).

### Divine-person placements needing Doug's per-record decision

The panel proposed none: every divine-person change it asked for is a removal (Isa 9:3, Zech 4:10) and was applied. Open for Doug as before: the addressed-"You" picks (Ps 4:7, 16:11, 21:6, 30:11, 51:8, 51:12, 92:4; 5:11, 33:21, 40:16, 66:6, 89:16), which the panel judged close enough to stay, and Isa 65:19 and Jer 32:41 (the LORD in first person).

### Examples of every row after the build (new book order), all 26 read

All first-four examples were read in the Berean text after the build, because rows are now in the Bible's order. Rows whose first four now differ from before and were re-led where the label was not shown: the repentance row and the master/kingdom row (split), "The LORD makes glad", "Told to rejoice, and told not to", "Everyday joy", "Joy and sorrow", "Joy and salvation", "Joy with singing", "Joy weighed". Rows whose examples show the label without a lead: Holy Spirit, Jesus, peace/love/hope/faith, feasts, Rejoice in the LORD, lost and found, Who rejoices, Rejoicing together, see or hear, suffering and weeping, fall/ruin, and the three catch-alls (noun: Deut 28:47, Matt 2:10, Rom 15:32, 1 Chr 29:9; verb: Judg 9:19, Luke 19:6, 1 Pet 1:8, 1 Sam 11:15; adjective: 1 Kgs 1:40, Prov 15:13, Prov 17:5, Deut 16:15). No example fails its label. The hub is still `"shown": false`.
