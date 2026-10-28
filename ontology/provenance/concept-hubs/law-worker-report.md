# Law hub (id `law`, shown on the site as "instruction"): report

Spec: `<local> Ontology\ontology\concept-hubs\law.json` ("shown": false).
Built: `<local> Ontology\out\concept-hubs\law.json`. Four builds. 25 rows (24 and the catch-all), 366 verses, `cards missing: []`, `More` 0.

## Words
- תּוֹרָה (h8451): 186 verses in the law sense, 26 in the instruction sense (kept apart by `sense: "law"`; those 26 are the row "Instruction and teaching", listed by hand from MACULA's glosses "instruction", "teaching", "instructions", "ruling").
- νόμος (g3551): 154 verses, none dropped. `sense_keep` for Rom 3:27 and 7:21 (MACULA glosses "principle"; the Berean also prints "principle", so those two verses show no word "law" in the English; the rows' notes say so) and Isa 2:3 (same sentence as Mic 4:2; Berean prints "law" in both).
- Left out as different words: מִצְוָה/ἐντολή (commandment), חֹק/חֻקָּה (statute), מִשְׁפָּט (ordinance, justice), עֵדוּת (testimony), פִּקּוּד, and the family words νομικός, νομοδιδάσκαλος, νομοθεσία, ἄνομος.
- `others` ("Other words translated law, instruction, teaching"): דָּת in Hebrew (Esth) and Aramaic (Ezra 7, Dan 6) added by hand with notes (Persian loanword, the king's edict; also "the law of your God" in Ezra 7); מוּסָר (Proverbs, "instruction/discipline"); לֶקַח; νομοδιδάσκαλος; ἔννομος (1 Cor 9:21, "under the law of Christ", the only place the Greek has no νόμος); νομοθέτης (Jas 4:12); παρανομέω; and a few strays. Excluded after build 1: διδάσκω, διδαχή, διδασκαλία (New Testament "teach/teaching": 96 verses of noise that say nothing of the law). Father/mother/son-in-law are kept out by the regex lookbehind. The `anger`-style overlap does not arise here.

## Rows with counts (in the order shown)
1. The law of the LORD, of God (30)
2. Given through Moses; set before the people; "the Law of Moses" (53)
3. The book of the law; what is written in the law (37)
4. The Law and the Prophets (18)
5. Keep, do, walk in, obey the law (38)
6. Loved and delighted in; called perfect, good, holy, spiritual, true; more precious than gold (19)
7. Forsaken, rejected, forgotten, transgressed, not kept (34)
8. Taught and read aloud; the priests, Levites, scribes and Pharisees (59)
9. On the heart, in the mind; "within my heart" (9)
10. The foreigner, the Gentiles, the nations; circumcision and uncircumcision (15)
11. Instruction and teaching: a father's, a mother's, a priest's, God's (26)
12. "This is the law of ...": the offerings, clean and unclean, childbirth, jealousy, the Nazirite (25)
13. Judged by the law; brought to court (15)
14. Beside the covenant and the promise; the testimony, statutes, ordinances (also "justice") and commandments (69)
15. The law, and faith, believing (19)
16. The law, and works (9)
17. The law, and grace (7)
18. "Under the law" (8)
19. Sin, trespass, the curse (35)
20. Other "laws" the text names: of faith, of sin and death, of the Spirit of life, of Christ, of freedom, the royal law, of marriage (12)
21. "Before the law was given"; "added because of transgressions"; "our guardian to lead us to Christ"; "only a shadow of the good things to come" (7)
22. Died to the law, released from it, not under it, redeemed from its curse; "Christ is the end of the law"; "abolished in His flesh"; "a change of law" (11)
23. "Not to abolish but to fulfill"; "we uphold the law"; not the least stroke will pass; summed up and fulfilled in love (11)
24. Jesus speaks of the law: "I have not come to abolish", "in your own Law", "not one of you keeps it" (15)
25. Every other use (26)

A verse sits in every row it fits (`match: "all"`). 25 rows is at the top of the 15-25 range; rows 21-23 are a deliberate triple (see contested point 1).

## The 16-verse sample (Berean text read through the server)
Verdict key: P = shows its label; F = failed, fixed; L = true but the label did not say it, label changed.

| # | Verse | Row | Verdict |
|---|---|---|---|
| 1 | Neh 9:14 | Given through Moses | P ("commandments and statutes and laws through ... Moses") |
| 2 | Jer 8:8 | The law of the LORD | P |
| 3 | Zeph 3:4 | The Law and the Prophets | P |
| 4 | Neh 13:3 | Keep, do, walk in, obey | F: "As soon as the people heard this law, they excluded ..." says hear, not obey. Fix: שָׁמַע taken out of the verb list; the verse now stands in "Every other use". |
| 5 | Ps 89:30 | Forsaken | P ("If his sons forsake My law") |
| 6 | Neh 12:44 | Taught ...; the priests, Levites | P (names the priests and Levites) |
| 7 | Isa 51:7 | On the heart | P ("My law in your hearts") |
| 8 | Lam 2:9 | The foreigner, the Gentiles, the nations | F: the nations are where the king is exiled; nothing of the law and the nations. Fix: `not_verses` (it stands in "The Law and the Prophets"). |
| 9 | Lev 11:46 | "This is the law of ..." | P ("the law regarding animals, birds ...") |
| 10 | Exod 18:16 | Judged by the law | P ("judge between one man and another ... the statutes and laws of God") |
| 11 | Hab 1:4 | Beside the covenant ... ordinances | L: the Berean prints "justice" for מִשְׁפָּט. Label now says ordinances (also "justice"). |
| 12 | Acts 21:20 | The law, and faith, believing | P ("have believed, and ... zealous for the law") |
| 13 | Gal 4:21 | Under the law | P |
| 14 | Isa 42:24 | Sin, trespass, the curse | P ("against whom we have sinned ... would not obey His law") |
| 15 | Rom 7:21 | Other laws | F: the Berean prints "principle" and no "law" (Greek νόμος). Kept (original arbitrates); the row's note now says so, and Rom 3:27 (same) in the faith and works rows. |
| 16 | Rom 5:13 | Before the law was given ... | L: true ("sin was in the world before the law was given") but the label did not say it. Label now opens with it. |

Tally: 11 pass, 3 failed and fixed (4, 8, 15), 2 label-only fixes (11, 16); 0 left failing after rebuild. Read besides, for notes and labels: Eph 2:15, Luke 16:17, Ps 119:163, Gal 2:21, Rom 7:2, Num 19:2, Deut 31:9, Prov 3:1, Jas 1:25, Acts 7:53, Rom 8:4, 1 Tim 1:8, John 19:7, Rom 4:15, Gal 3:13, Rom 7:6, Heb 7:19, Matt 5:18, Matt 23:23, John 8:17, 15:25, Jas 2:8, Lev 14:57, Num 6:13, Jer 32:23, Acts 13:39, and the instruction-sense verses (2 Sam 7:19, Exod 16:4, 16:28, Ezek 7:26, Hos 8:12, Isa 1:10, 2:3, 8:16, 8:20, 30:9, Jer 18:18, Hag 2:11, Mal 2:7, 2:9, Prov 1:8, 13:14, 31:26, Ps 78:1, Prov 28:4).

Other fixes made from the first build's rows: Luke 2:22 out of "The law of the LORD" (Moses, not the Lord, in that verse); heart row rebuilt as a hand list (a rule on "heart" took Deut 30:10 and Ezra 7:10, where the heart is turning to the LORD); Matt 23:23 out of "faith" (πίστις is "faithfulness") and "Judged" (κρίσις is "justice"); Rom 7:25 out of "grace" (χάρις is "thanks"); Rom 3:21, Heb 9:19, Jas 2:9 out of "Under the law" (ὑπό is "by"); Lev 6:25, 7:7, 7:37 and Heb 10:8 out of "Sin" (sin offering); Jer 32:23 and 44:23 out of "Taught" (קָרָא is "come upon"); Rom 7:1 out of "Died to the law"; Acts 13:38 moved to 13:39 as on the righteousness hub, and out of "Sin" there. All notes were then re-checked word for word against the Berean text (about twenty quotations I had first written from memory were not the Berean's, among them Rom 3:20, Rom 3:31, Eph 2:15, John 19:7, 1 Tim 1:8, Gal 3:19, Rom 8:4, all corrected).

## Contested points for the review panel (be specific)
1. **The law and the Christian (fulfilled, ended, or continuing as a guide).** Three rows set side by side, in the alphabetical order of their labels, each with the same no-side sentence and a note quoting the Berean:
   - Row 21 "Before the law was given ... guardian ... shadow": Rom 5:13, 5:20; Gal 3:17, 3:19, 3:23, 3:24; Heb 10:1.
   - Row 22 "Died to the law, released ... the end of the law ... a change of law": Rom 6:14, 6:15, 7:4, 7:6, 10:4; Gal 2:19, 3:13, 5:18; Eph 2:15; Heb 7:12, 7:19.
   - Row 23 "Not to abolish but to fulfill ... uphold ... summed up in love": Matt 5:17, 5:18, 7:12, 22:40; Luke 16:17; Rom 3:31, 8:4, 13:8, 13:10; Gal 5:14; Jas 2:8.
   The panel should check: (a) whether the order (A, D, N) or the weight of the labels tilts toward "ended" (the middle row's label is the longest, six phrases) or toward "continuing"; (b) Rom 10:4 (τέλος: the note says end, goal or completion and that readers part); (c) whether Gal 3:24 ("guardian") belongs with Row 21 or with Row 22, since readers who take the law as ended read it there; it is in Row 21 only, and Row 22 does not include Gal 3:25 (no νόμος in it); (d) that no row names law-and-gospel, the "third use", or a dispensation, as asked.
2. **Law, faith, works, grace** (rows 15-17). Faith and works are two rule rows, whole-verse, so Rom 3:28 and Gal 2:16 stand in both; Rom 3:27 is shown with the Berean's "principle". "Law and grace" is Rom 6:14-15, John 1:17, Gal 5:4, Rom 4:16, 5:20, Gal 2:21 with the no-side sentence. Rom 4:15 ("the law brings wrath") is in Row 19 (sin), not the grace row.
3. **"Under the law"** (row 18): 8 verses by the word-by-word text (ὑπό next to νόμος). 1 Cor 9:20 is quoted in the note with its parenthesis; the page does not say who is "under" it. Rom 3:19 ("those under the law") is the Greek ἐν, not ὑπό, and is in "Every other use".
4. **The Torah on its own terms** (rows 1-3, 5-13). For the rabbi's seat in particular: (a) row 11 shows that תּוֹרָה is "instruction and teaching" in Proverbs, Isaiah, Malachi and Exodus 16 and says it is one word, not two; Isa 8:16, 8:20, Jer 18:18, Hos 8:12 and Mal 2:9 are in it though the Berean prints "law" there (the MACULA gloss is "instruction"/"teaching"), and 2 Sam 7:19 prints "custom" and Hag 2:11 "ruling": the note says so. (b) Row 12 ("This is the law of ...") is the Torah as particular rulings, with the Berean's words "skin diseases and mildew" and "a woman giving birth"; no row there says these are ended. (c) Row 10 gives Exod 12:49 and Num 15:29 ("one law for the native and the foreigner") and Isa 2:3/Mic 4:2 beside Rom 2:14; the note takes no side on the law and Gentile believers. (d) Row 9 ("on the heart") puts Jer 31:33 with Heb 8:10, 10:16, Rom 2:15 and Ps 37:31 under one no-side note about the new covenant; a Jewish reader may find it too quick to set Jer 31:33 beside the Hebrews quotations, though the Greek quotes it.
5. **The other "laws"** (row 20): "law of faith", "law of sin and death", "law of the Spirit of life", "law of Christ", "perfect law of freedom", "royal law", "law of marriage". Whether these are the Mosaic law under other names is stated as a point where traditions part, no side. 1 Cor 9:21 "under the law of Christ" is ἔννομος, a different word, so it is not in the row but under the other words (named in the row's note).
6. **Divine persons by hand.** "The law of the LORD, of God" is by adjacency to the divine names only (no inference); "the law of Christ" is by hand in row 20 and Jesus' own speech in row 24 is a `pick` list (each verse is Jesus speaking of the law).
7. **Heb 9:19, Acts 7:53, Gal 3:19** ("ordained by angels", "administered through angels by a mediator") are in row 2 with the Berean's words and no comment on whether they mean Moses.

## What the builder could not express
- An OR of two conditions in one row (e.g. "the book next to the law" or "written in the law") needed `add` lists. An `or` key on rows would help.
- A `sense`-like split: the builder drops the instruction sense of תּוֹרָה from the law rows but cannot put it in a row by rule, so row 11 is a hand `pick` list (`pick` verses are not checked against the word). A `sense_row` option (a row that takes only the verses `sense` dropped) would let it be rule-made and guarded.
- `in_verse` is whole-verse, so a `heart` or `judge` word elsewhere in the verse puts it in a row (hence the hand lists in rows 9 and 13 and several `not_verses`); an `in_clause` with the clause of the law word would be the right condition, but clauses are filed under the verse they start in.
- Hebrew `שָׁמַע` "hear/obey" cannot be told apart by the rule (taken out).
- Showing the Berean's "principle" for νόμος (Rom 3:27, 7:21): the builder has no way to mark a verse "Berean differs from the original here" beyond the row's note.
- Acts 13:38/13:39: the `moves` remap makes words of 13:38 count in 13:39, so rows keyed on a word of the moved clause (sin) needed a `not_verses`.
