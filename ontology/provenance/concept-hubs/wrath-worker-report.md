# Wrath hub report (third round, 2026-10-25)

Spec: `<local> Ontology\ontology\concept-hubs\wrath.json` (`shown: false`).
Built: `<local> Ontology\out\concept-hubs\wrath.json` (4 builds).
Result: 26 rows (23 noun, 3 verb), 409 noun verses and 118 verb verses; 16-sample tally 14 of 16 pass, 2 fail and fixed.

## The twin card `anger`

`wrath` (id wrath, named "anger", 11 relations) and `anger` (id anger, named "anger", 9 relations) stand on exactly the
same two words, אַף (h639) and θυμός (g2372), with the same `others` (παροργισμός, παροργίζω, רְגַז). They are not two
senses of one word, so the `anger` card's words belong **in the hub's rows, not in `others`**. `others` is for different
words the English also calls anger; here there is no such difference.

How the twin should be handled (Doug's decision, per the divine-persons/merge rules: merge only one thing recorded
twice, with two judges): the two cards look like one concept recorded twice (same name, same words, both reached by the
Job speeches). Recommended: (1) show this hub on both cards (give `anger` the same hub, or point its `leads` here)
so a reader landing on either gets it; (2) a merge of `anger` into `wrath` is the cleaner end, but is Doug's per-record
call: `anger` carries Gal 5:20 ("outbursts of anger", a work of the flesh) and Gen 18, 44, 45 speeches that `wrath` lacks,
so a merge would keep both card's relations. The spec lists `anger` in `gather` and `leads` so it is a door either way.
Also noted: the hub id is `wrath` but the card's displayed name is "anger"; the hub's titles are written to fit both.

## Rows (count)

Noun form, "What the text says of wrath and anger" (by the companion words in the verse or clause, the text's own
phrase, or by hand):

1. The anger of the LORD, the wrath of God (68, phrase rule: God/LORD adjacent). Note: a personal response, or what sin brings (Rom 1:24, 26, 28).
2. Slow to anger; patience beside wrath (15)
3. Anger and mercy, compassion, favor, forgiveness (17)
4. The day of wrath; wrath to come, and shelter from it (27, rule + hand)
5. Wrath poured out; the cup of wrath, the winepress of wrath (35)
6. Anger that burns, is kindled, flares like fire (74)
7. Anger turned away, or not turned away; restrained, quenched, spent (48)
8. Anger and sin, idols, unfaithfulness (33)
9. Anger against the nations, enemies and the wicked (15)
10. Anger against Israel, Judah and Jerusalem (35)
11. Anger and the law, the covenant, the commandments (6)
12. Wrath and judgment, vengeance; the ruler who brings wrath on the wrongdoer (21)
13. An oath sworn in anger: "they shall never enter My rest" (5, hand)
14. Cries to the LORD about His anger (15, hand)
15. Asked of God against enemies (8, hand; hard verses kept)
16. The rod and the weapons of His wrath (7, hand)
17. What stands between wrath and the people (12, hand; contested)
18. Children of wrath, vessels of wrath (4, hand; contested)
19. Jesus and wrath (4, hand)
20. A person's anger (24, hand; Proverbs, Ecclesiastes, Genesis 49)
21. What Jesus and the letters say of a person's anger (9, hand)
22. Anger in the stories, and a king's wrath (25, hand)
23. Every other use (67)

Verb form, "Who is angry, and with whom" (by hand: the frames hold only about three in four of these verses):

24. God angry (68, divine persons by hand)
25. A person angry (48, by hand)
26. Every other use (2: Deut 9:22 and Ps 2:12)

## 16-verse sample (build 3, read in the Berean via /api/verse)

| # | Verse | Row | Verdict |
|---|---|---|---|
| 1 | Num 22:22 | The anger of the LORD | pass ("God's anger was kindled") |
| 2 | Amos 1:11 | Anger and mercy | pass ("stifled all compassion; his anger raged") |
| 3 | Prov 11:4 | The day of wrath | pass ("worthless in the day of wrath") |
| 4 | 1 Thess 5:9 | Wrath to come, shelter | pass ("not appointed us to suffer wrath") |
| 5 | Hos 5:10 | Wrath poured out | pass ("pour out My fury ... like water") |
| 6 | Isa 30:30 | Anger like fire | pass ("angry wrath with a flame of consuming fire") |
| 7 | Josh 7:26 | Anger turned away | pass ("the LORD turned from His burning anger") |
| 8 | Job 19:29 | Anger and sin | **fail**: the Berean prints עֲוֺנוֹת as "punishment"; no sin in the English. Fixed: `not_verses`. |
| 9 | Hab 3:12 | Against the nations | pass ("threshed the nations in wrath") |
| 10 | 2 Chr 29:10 | Anger and the law/covenant | pass ("make a covenant ... His fierce anger will turn away") |
| 11 | Prov 6:34 | Wrath and judgment, vengeance | pass ("day of vengeance") |
| 12 | Isa 13:3 | The rod and weapons | pass ("summoned My warriors to execute My wrath") |
| 13 | Prov 25:15 | Slow to anger; patience | pass, thin ("Through patience a ruler can be persuaded"; the Hebrew is "length of tempers"). Removed from "A person's anger", where the English shows no anger. |
| 14 | Neh 13:18 | Against Israel | pass ("rekindling His wrath against Israel") |
| 15 | Deut 9:22 | God angry (verb) | **fail**: the Berean prints "You continued to provoke the LORD" (Hebrew הִקְצִיף, "cause wrath"). Fixed: moved to "Every other use". |
| 16 | Esth 7:7 | Anger in the stories | pass ("In his fury, the king arose") |

Tally: 14 pass, 2 fail (both fixed). Extra checks while reading the verb picks: Gen 18:30 (and 18:32) "May the Lord not
be angry" is Abraham's plea about God's anger, moved from "a person angry" to "God angry"; 1 Sam 15:11 prints "Samuel was
distressed" (the Hebrew verb is חָרָה "burned, was angry"), so it is in no row and is named in the verb catch-all note;
Lev 10:6, Zech 8:14, Gen 4:5, Gen 18:30, Gen 45:5, Jonah 4:4 read and pass. Rev 14:8 prints θυμός as "the wine of the
passion of her immorality" (the same Greek word is "wrath" in 14:10): kept out of the nations and cup rows, named in the
catch-all note.

## Words and `others`

Words (15): the card's אַף (217 verses in this sense, 52 not: "nose", "nostrils", "face") and θυμός (18); added ὀργή (34),
חֵמָה (109; "venom" and "heat of wine" drop), חָרוֹן (39), זַעַם (21), קֶצֶף (28), עֶבְרָה (30; "insolence"/"arrogant"
drop), the Aramaic חֲמָה (h2528, 2), and the verbs חָרָה (61; "scorched" at Isa 24:6 dropped by hand), אָנַף (14), קָצַף (32),
זָעַם (7; "denounce" drops), ὀργίζω (8), θυμόω (1). The hub never says Hebrew and Greek are one word; every verse names
its word.

`others` (different words the English also renders anger/wrath/fury, found by the gloss rule, with verses): כָּעַס h3707
("provoke to anger", 49 verses; added with a note), זַעַף h2197 "rage" (5), זָעַף h2196 "to enrage" (3), נָטַר h5201 "keep"
(Ps 103:9, Jer 3:5, 3:12, Nah 1:2), παραζηλόω, παροξύνω, and more (the builder lists them by size). Not in `others` but
named in the spec: רֹגֶז (Hab 3:2, "In Your wrath, remember mercy") is a row example, not a word.

## Contested points for the review panel

- **What turns wrath away** (row 17). Verses: Exod 32:12, Num 16:46, Num 25:11, Ps 106:23, Ps 78:38, Jer 18:20, Dan 9:16
  (an intercessor, a priest, a zealous man), Rom 3:25, Rom 5:9, Heb 2:17, 1 John 2:2 and 4:10 (the Berean's "atoning
  sacrifice", "make atonement"; none of those four has a word for wrath). Readers part on whether ἱλαστήριον/ἱλασμός says
  propitiation (turns God's wrath aside), expiation (removes sin) or both. The note shows the words and takes no side.
  The panel should ask whether including four verses with no wrath word is acceptable (the sacrifice hub's "Lord's table" row
  did the same, with the graph's backing; the card `atonement` is the door).
- **Children of wrath** (row 18). Eph 2:3 "by nature children of wrath" beside Eph 5:6, Col 3:6 ("sons of disobedience") and
  Rom 9:22 ("vessels of His wrath"). The note: readers part on "by nature" (inherited sin, or the course each follows).
  The panel should check the note does not read as a ruling for or against original sin.
- **What the wrath of God is** (row 1 note). A personal response, or what sin brings (Rom 1:24-28 "God gave them over").
  The note is the page's own wording; the panel should confirm it takes no side.
- **Wrath to come** (row 4 note) and **an oath sworn in anger** (row 13: Deut 1:34, Num 32:10, Ps 95:11, Heb 3:11, Heb 4:3).
  Readers part on when the coming wrath comes and who passes through it (1 Thess 1:10, 5:9; Rev 6:17); and on what
  Hebrews 3-4 does with "My rest". The page sets the verses.
- **Jesus and wrath** (row 19: Mark 3:5, Rev 6:16-17, 1 Thess 1:10). By hand, each names Jesus or the Lamb. Rev 19:15
  ("the fury of the wrath of God Almighty") names God; the rider is not named Jesus in the verse, so it is in row 1.
- **Imprecatory verses** (row 15: Ps 7:6, 56:7, 59:13, 69:24, 79:6, Jer 10:25, 18:23, Lam 3:66). Hard verses kept; the
  label is the text's own words.
- **Human anger** (rows 20-22, 25): kept apart from God's, as the brief asks. Row 21 holds "everyone who is angry with his
  brother" (Matt 5:22), "be angry and do not sin" (Eph 4:26), Jas 1:19-20. Eph 4:26 uses ὀργίζω; the panel may want a
  note on whether "be angry" is a command or a concession (not added: the page takes no side and the verse is shown).
- **Rom 13:4-5** (row 12). "an avenger who brings wrath on the wrongdoer" sits beside Rom 12:19 "leave room for God's
  wrath" with a note that the page does not say more. Readers differ on the state's authority; no side taken.
- **Ps 2:12** "lest He be angry": whom "He" means; left in the verb catch-all with a note.
- **Rev 14:8, 18:3** (the Berean's "passion"; the Greek is θυμός).
- **Translation findings** (original arbitrates): 1 Sam 15:11 (Berean "distressed", Hebrew "became angry"); Deut 9:22
  (Berean "provoke", Hebrew "provoke to wrath"); Job 19:29 (Berean "punishment" for עֲוֺנוֹת); Prov 25:15 (Berean
  "patience", Hebrew "length of tempers"); Rev 14:8. These are candidates for `translation-findings.json`; none was written
  (the brief limits edits to the spec and this report).

## What the builder could not express

1. **Separating God's anger from a person's by rule.** Hebrew pronoun suffixes ("My anger", "His wrath") are not lemmas,
   and `in_verse` has no negative form, so a verse that says "his anger burned" cannot be told by rule from "the LORD's anger
   burned" unless the LORD is named. The 67 "Every other use" noun verses are mostly God's anger in the prophets' and
   psalmists' words that no companion word catches. Needed: a condition on the verse's speaker or the noun's possessor
   (suffix person), or `not_in_verse`.
2. **The frames hold the anger verb for only about three in four verses.** Gen 4:5-6, Gen 18:30, Num 11:1/11:10/11:33/22:22,
   Jonah 4, and others have no frame, so the verb rows had to be made by pick (the divine persons by hand, so this suits
   rule 4, but a rule row would have missed a quarter). Needed: a verb row that reads the verse's own lemmas the way
   `in_verse` does for nouns (a `verb_in_verse` condition).
3. **`add` works only for verses already seen in that form.** A verse of a verb-only word cannot be added to a noun row
   (Ps 79:5 is a picked verse in the noun "Cries" row though its word is the verb אָנַף).
4. **Row order and examples.** `lead` helps, but a rule row's first examples can be a person's anger (the fire row, whose
   leads were set to the LORD's verses). Fine, but a `lead_not` or `prefer` option would have saved a build.
5. **Verses in two forms.** A verse that has both the noun and the verb (Gen 39:19, Exod 4:14) appears in a noun row and a
   verb row; this is as in the other hubs, but the "More" and counts show 409 + 118 verses with overlap.
