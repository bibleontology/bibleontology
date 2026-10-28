# Death hub: worker report (round two, 2026-10-25)

Spec: `<local> Ontology\ontology\concept-hubs\death.json` (`"shown": false`)
Built: `<local> Ontology\out\concept-hubs\death.json`
4 builds (a diagnostic, then three). Final: 25 rows (10 noun, 11 verb, 4 adjective). Lead form: noun. `cards missing: []`.

## Rows and counts (final build)

Noun, "What the text says of death" (251 verses; More 115)
1. Death with sin and the law: 24 (rule: sin or law word in the verse)
2. Death and life: 42 (rule: life word in the verse; 2 Kgs 14:17 and 2 Chr 25:25 out, they count years lived after a death)
3. "The second death": 4 (pick: Rev 2:11, 20:6, 20:14, 21:8)
4. Death beside Sheol, Hades, the grave, the pit: 25 (rule)
5. Death and the resurrection: "raised", "rise": 8 (rule)
6. Death as ruler and enemy: it reigns, stings, is swallowed up, destroyed, no more: 16 (pick)
7. The death of Christ: 10 (pick, each verse names Christ, Jesus or the Son; 1 Cor 11:26 "the Lord's death")
8. Delivered from death: 17 (rule; Num 35:25 and Eccl 7:26 out)
9. Worthy of death, sentenced to death: 22 (pick)
10. The death of the wicked, of the righteous, of His saints: 8 (pick)

Verb, "Dying, and being put to death" (764 verses; More 507)
1. The LORD brings death and gives life: 12 (pick, each verse names the LORD)
2. "You will surely die": the sentence spoken: 9 (pick)
3. "Each will die for his own sin": 15 (pick)
4. Adam died; "as in Adam all die": 3 (pick)
5. Christ died: 12 (pick, each verse names Christ, Jesus or the Son)
6. Died to sin, died to the law, died with Christ: 9 (pick)
7. What the text says follows dying, side by side: 12 (pick; neutral label, no ranking)
8. Asleep: "not dead but asleep", "rested with his fathers": 6 (pick)
9. The law's penalty: "must surely be put to death", "stone them to death": 43 (pick)
10. Buried, mourned, "gathered to his people", full of years: 52 (rule; 4 false positives out)
11. Struck down, killed, fallen by the sword: 108 (rule; 7 false positives out)

Adjective, "The dead" (122 verses; More 41)
1. Jesus Christ raised from the dead: 25 (pick, each verse names Jesus, Christ or the Son of Man)
2. The resurrection of the dead; the dead raised: 33 (rule ἀνάστασις + 19 `add`)
3. "Not the God of the dead", "Lord of the dead"; the dead judged: 13 (pick)
4. "Dead" said of the living: dead in sin, dead faith, dead works: 14 (pick)

## The 16-verse sample (final build; Berean text read from the server)

All 16 pass.
1 Rom 6:16 (sin and death) pass. 2 Prov 12:28 (death and life) pass. 3 Rev 20:13 (Death and Hades) pass. 4 Heb 2:15 (death as a power: slavery by fear of death) pass. 5 Luke 23:15 (nothing deserving of death) pass. 6 Gen 38:10 (the LORD put Onan to death) pass. 7 Ezek 3:19 (he will die in his iniquity) pass. 8 Col 2:20 (died with Christ) pass. 9 Rev 14:13 (blessed are the dead who die in the Lord; under the neutral label) pass. 10 Matt 9:24 (not dead but asleep) pass. 11 Lev 20:13 (must surely be put to death) pass. 12 Judg 12:7 (died, buried) pass. 13 2 Sam 18:15 (struck him and killed him) pass. 14 Mark 12:25 (when the dead rise) pass. 15 Rev 11:18 (judge the dead) pass. 16 Rom 10:7 (bring Christ up from the dead) pass.

Earlier sample on the second build (16 verses, 13 pass, 1 fail, 2 partial), what it found and what I fixed:
- Rom 14:8 failed: it sat in the row labelled "To die is gain / I will go to him / after that judgment" and shows none of those. Fixed: the two afterlife rows are one row with a neutral label (see contested point 6); John 11:25-26 and Rev 14:13 had the same fault.
- Num 26:65 and Rev 6:8 partial: the row said "puts to death" / "reigns, stings...", the verses say the LORD "had told them they would surely die" and Death is given "authority ... to kill". Fixed by relabelling: "The LORD brings death and gives life" (with a note listing which verses put to death, strike, send, decree) and "Death as ruler and enemy".
- Also fixed after reading the full rows: Num 35:25, Eccl 7:26 (deliver), 2 Kgs 14:17, 2 Chr 25:25 (life), 2 Sam 14:14, Exod 9:19, 1 Sam 5:11, 2 Kgs 5:7 (אָסַף means gather water / livestock / rulers / cure a leper, not "gathered to his people"), Gen 36:35, 1 Chr 1:46, Isa 22:13, Jonah 4:8, Josh 5:4, Deut 2:16, 1 Sam 5:12 (נָכָה "defeated", "beat down"; מִלְחָמָה "men of war"; הָרַג sheep). John 11:14 left the Asleep row (does not show "asleep"); John 11:13 ("actual sleep" against "the death of Lazarus") took its place. Luke 16:30-31 moved from the "dead judged" row to the resurrection row. Rom 7:8 and Rom 11:15 left "Dead said of the living" (sin is dead; "life from the dead" is read both ways).
- Verses checked and left out by hand: 1 Pet 3:18 (the Berean prints "suffered", not died), Phil 2:8 and 1 Thess 5:10 (say "He"), Gen 38:7's gloss problem (below).

## Words

Rows stand on: מָוֶת (h4194, 147 verses in sense) and θάνατος (g2288, 105) the noun; מוּת (h4191, 700) with ἀποθνῄσκω (g599, 100), θνῄσκω (g2348, 9), θανατόω (g2289, 11) the verb; νεκρός (g3498, 120) with θανάσιμος, θανατηφόρος, ἐπιθανάτιος the adjective. The card lists only h4191, h4194, g2288; ἀποθνῄσκω and νεκρός are added (without them the New Testament verb "die" and "the dead" would be missing: g599 is 100 verses). Hebrew and Greek are not pooled: each example tags the word it stands on. νεκρός is "dead" and not the same root as θάνατος; it is in the family because English renders both "dead" and the Greek Old Testament pairs it with the Hebrew participle of מוּת.
`sense` is a regex on MACULA's gloss: `death|\bdie[sd]?\b|\bdying\b|\bdead|kill|slay|slain|slew|perish|mortal|corpse|lifeless`. The first draft ("put to death" as a phrase) dropped 28 מוּת verses (Gen 38:7, 2 Kgs 25:21 and the like) because MACULA writes the Hiphil gloss "put ~ todeath" with no word boundary; unanchored `death` takes them back (other_sense 29 to 1).

`others` ("Other words translated death, dead, die"), different words named apart with their verses: נְבֵלָה carcass (11), ἀναιρέω to kill (11), τελευτάω to decease (9), גָּוַע to breathe one's last (9; Gen 25:8 has both גָּוַע and מוּת), רְפָאִים the shades (5), συναποθνῄσκω die with (3), νεκρόω put to death (3), תְּמוּתָה (2), and single words ἀπογίνομαι, νέκρωσις, מְמֹותִים, מוֹת, ἡμιθανής, τελευτή. Excluded: h4192 (the psalm title Muth-labben) and h8367 (a stray gloss). Added by hand with a note: צַלְמָוֶת (h6757), where the Berean prints "the shadow of death" at Ps 23:4, Ps 107:10 and Isa 9:2 (Berean numbering) and "gloom" or "darkness" elsewhere; the note says the page does not decide whether it is "shadow of death" or "deep darkness" and does not make it the word מָוֶת.

## Contested points for the review panel (each shown, none settled)

1. Noun row 1 "Death with sin and the law" (Rom 5:12, 5:14, 5:17, 5:21, 6:16, 6:23, 7:5, 7:10, 7:13, 8:2; 1 Cor 15:56; Jas 1:15; 1 John 5:16-17 "sin that leads to death") set beside verb rows 3 and 4. Parts: whether death and guilt pass from the first man to all (Rom 5:12 "death was passed on to all men, because all sinned") or each dies for his own sin (Ezek 18:4, 18:20; Deut 24:16; Jer 31:30); what a sin "leading to death" is (1 John 5:16-17). Notes say the page takes no side and name Ps 51:5 and 58:3 as outside the hub (no death word). Panel: is "Adam died; "as in Adam all die"" a fair label for Gen 5:5 beside 1 Cor 15:22 and Rom 5:15? (Gen 5:5 only says Adam died.)
2. Verb row 2 ""You will surely die"" (Gen 2:17, 3:3, 3:4, 20:7; 1 Sam 14:44, 22:16; 1 Kgs 2:37, 2:42; Jer 26:8). Parts: what "die" means in Gen 2:17 (the body, separation from God, both). Gen 3:4 (the serpent's denial) is in the row, flagged in the note.
3. Noun row 3 ""The second death"" (Rev 2:11, 20:6, 20:14, 21:8). Parts: an ending or lasting suffering; who comes to it. Note neutral; Rev 21:8 lists sins by name and stays.
4. Noun row 4 "Death beside Sheol, Hades, the grave, the pit" (25 verses, Ps 6:5 and Isa 38:18 "no remembrance / praise" are in it). Parts: Sheol and Hades as the grave, the place of all the dead, a place of reward or punishment. The note says they are different words and the page does not make them one.
5. Noun row 5 and adjective rows 2 and 3 on the resurrection: Rev 20:4-6 "the first resurrection" and the thousand years (note on adjective row 2); order and timing of the resurrection; 1 Pet 4:6 "the gospel was preached even to those who are now dead" (in adjective row 3, note says it is read more than one way).
6. Verb row 7 "What the text says follows dying, side by side" (2 Sam 12:23; Job 14:10, 14:14; Eccl 9:4, 9:5; Luke 16:22; John 11:25-26; Rom 14:8; Phil 1:21; Heb 9:27; Rev 14:13). Parts: the dead know nothing / sleep / present with the Lord / Hades; judgment at death or at the last day. It is one row on purpose (two rows with quoted labels left verses that did not show their label). Panel to judge: does one neutral label with the lead order Eccl 9:5, Job 14:14, 2 Sam 12:23, Phil 1:21 read as balanced? Does placing Luke 16:22 (the beggar and the rich man both die; Luke 16:23 Hades has no death word and is not in the hub) here favour one reading? The Asleep row (verb 8: Mark 5:39, Matt 9:24, Luke 8:52, John 11:13, 1 Thess 4:14, 2 Chr 16:13) carries the soul-sleep question; its note says whether the dead are conscious in sleep is read differently.
7. Noun row 6 "Death as ruler and enemy" : the text has the end of death as done (2 Tim 1:10 "has abolished death") and as still to come (1 Cor 15:26 "The last enemy to be destroyed is death"; Rev 21:4). Note says how they fit is read differently.
8. Noun row 7 "The death of Christ" (Rom 5:10, 6:3; Phil 3:10; Heb 2:9, 5:7, 9:15; Col 1:22; 1 Cor 11:26; John 18:32; 2 Tim 1:10) and verb row 5 "Christ died" (Rom 5:6, 5:8, 6:9, 8:34, 14:9, 14:15; 1 Cor 8:11, 15:3; 2 Cor 5:14; Gal 2:21; 1 Thess 4:14; John 11:51). Parts: what the death does (atones, covers, appeases, ransoms, communes); the Lord's Supper as sacrifice or memorial (1 Cor 11:26); Heb 9:15 "mediator of a new covenant ... the first covenant" (covenant readings part here). Notes say the page takes no side. Heb 5:7 and Heb 9:15 also stand in other rows.
9. Verb row 6 "Died to sin, died to the law, died with Christ" (Rom 6:2, 6:8, 6:10, 7:4, 7:6; Gal 2:19; Col 2:20, 3:3; 2 Cor 5:14), note on Rom 6:3-4 "baptized into His death": the role of baptism.
10. Adjective row 4 ""Dead" said of the living" includes Jas 2:17 and 2:26 ("faith without deeds is dead"): faith and works; note sends to the faith hub and takes no side.
11. Verb row 1 "The LORD brings death and gives life" (1 Sam 2:6; Deut 32:39; Gen 38:7, 38:10; Lev 10:2; 1 Sam 25:38; 2 Sam 6:7; 1 Chr 13:10; Num 14:35, 21:6, 26:65; Jer 28:16): hard verses kept, each names the LORD; not a doctrine row. Verb row 9 "The law's penalty" (43 verses incl. Exod 31:14 Sabbath, Lev 20:13, Deut 22:22-25): hard verses kept, label only quotes the text; panel (the rabbi and the young African American believer) to judge framing.
12. Noun row 9 "Worthy of death" sets the verdicts against Jesus (Matt 26:66; Mark 14:64; Luke 23:15, 23:22; Matt 20:18; Mark 10:33), Paul (Acts 25:11, 25:25, 26:31, 28:18) and the law's own (Deut 19:6, 21:22, 22:26) side by side, plus Rom 1:32.
13. Divine persons are by hand: rows naming the LORD (verb 1) and Christ (noun 7, verb 5, adjective 1) are picks of verses that name him. Verses that say only "Him"/"He" (Acts 13:30, 13:34; Col 1:18; Matt 28:7; Phil 2:8; 1 Thess 5:10; 2 Cor 5:15) are under More, not a row. Rev 6:8 puts "Death" and "Hades" as riders; nothing claims a person.

## What the builder could not express (I did not edit it)

1. A frame is needed for a verb to be seen: infinitives ("to die is gain" Phil 1:21, "appointed to die once" Heb 9:27) and Hebrew nominal participles ("the dead", מֵתִים: Ps 115:17, 88:10) have no frame, so they are absent from "seen" and from the form counts. They can only be reached by `pick`, which works (word tags still show) but they are not counted in the verb form's verse total or in More. Option wanted: a per-verse or per-lemma "also seen in form X" list, or reading participles/infinitives from the clauses.
2. A row cannot be conditioned on the verb's stem or voice (Hophal/passive "must be put to death", Hiphil "put to death", Niphal), so "The law's penalty" (43) and "The LORD brings death" are by hand. Option wanted: `stem` / `voice` in the row conditions.
3. `in_verse` is any word anywhere in the verse and cannot be limited to the same clause as the concept's word. אָסַף (gather) gave 4 false positives and נָכָה (strike = defeat / beat down) 3; each needed `not_verses`. Option wanted: `in_clause` for noun and verb rows both from the concept's word, or a sense test on the companion word's gloss (נָכָה "defeat" against "strike").
4. No condition on MACULA's gloss or the Berean's English at the word (Gal 5:22 problem in faith): I needed "the Berean prints 'asleep'", "prints 'suffered'" (1 Pet 3:18), "prints 'defeated'". Option wanted: `gloss` regex on the companion word, and a `berean` regex on the verse.
5. `pick` rows are shown in the order given, `lead` moves four to the front; there is no option to sort a pick row in the Bible's order. I listed picks in canon order by hand; the first four are the lead.
6. The `sense` regex is read against the gloss, and MACULA writes some Hiphil glosses with a joiner ("put ~ todeath", "set ~ inorder"), so a word-boundary test silently drops them (28 verses here). A warning that lists the verses dropped by sense (not only the count) would have found it at once.
7. `others` `add` takes Berean verse ids, not MACULA's, with no check that the word occurs there (Isa 9:2 for צַלְמָוֶת was verified by hand: the Berean numbers MACULA's 9:1 as 9:2).
8. The 507 narrative "and he died" verbs of the Hebrew Bible (the Genesis 5 genealogies, the king lists, "he died and was buried", the plague and war reports) are largely under More. A few rules took 52 + 108; the rest has no companion word to rule on. A "who" condition (agent or subject, e.g. a king) would let a "death of a king" row exist; the frames' subject for מוּת was not conditionable without listing names.
