# covenant hub: report

Spec: `ontology/concept-hubs/covenant.json` (`"shown": false`). Built: `out/concept-hubs/covenant.json`. Builds run: 3 (first draft; a fix round from reading the first output; a last round of labels and notes). Cards missing: none. Every verse the words stand in is in a row (noun form 293 verses; "More" 0).

## Words and the sense rule

| word | kept | dropped as another sense |
|---|---|---|
| בְּרִית (noun) | 263 verses | 0 |
| διαθήκη (noun) | 30 verses | 0 |

`sense` is empty (as holiness): every use of בְּרִית is the one word whether the Berean prints covenant, treaty, alliance or allies; a gloss rule would have dropped the treaty verses (Josh 9, 1 Kgs 15:19), which the Hebrew puts in the same word as Sinai. There is no verb of the family, so the hub is the noun form only (title "What the text says of the covenant"). The verbs of the idiom (כָּרַת cut, קוּם establish, נָתַן give, שָׁמַר keep, זָכַר remember, פָּרַר break, and the rest) are not counted as the concept; they are the conditions of four rows (`object_of`, from the frames), each naming its verb in its `_why`.

**Other words (`others`, title "Other words translated covenant, treaty, alliance"):** one entry, כָּרַת "cut", in five verses (1 Sam 11:2, 20:16, 22:8; 1 Kgs 8:9; 2 Chr 5:10) where the Hebrew has only the verb and the Berean supplies "covenant" or "treaty". The note says so. (An unwanted-word check: no oath word qualifies; אָלָה and שְׁבוּעָה are not covenant and sit in a row beside it, as words in a verse.)

**A finding that shaped the notes:** in Heb 8:7, 8:13, 9:1 and 9:18 the Berean prints "covenant" ("that first covenant", "a new covenant", "the first covenant") where the Greek has no noun at all (read the word-by-word text of 8:7 and 8:13: "ἡ πρώτη", "Καινὴν ... τὴν πρώτην"). No word of the family stands in them, so the hub cannot hold them; the note of the row "A new covenant; the first covenant, the old covenant" says so, and Heb 8:13 is kept as a key verse (`own_words`) with the same caution in the spec.

## Rows (26 including the catch-all, all noun form), with counts

Named covenants (by hand through `add`, which keeps a verse only where the covenant word stands in it; a mistyped or wrong verse falls out silently, and the build output showed which did):

1. With Noah and every living creature: 8 (Gen 6:18, 9:9-17)
2. With the day and the night, the beasts, the stones, one's eyes, death: 8 (Jer 33:20, 33:25; Hos 2:18; Job 5:23, 31:1, 41:4; Isa 28:15, 28:18)
3. With Abram, Abraham, Isaac and Jacob: 19 (names in the verse, plus the Genesis 15 and 17 verses of God's speech to Abram, plus Jacob verses; note says which)
4. Egypt, Sinai, Horeb and Moses: 26 (rule on the names; Exodus, Deuteronomy verses added)
5. Covenants made in Moab, at Shechem and in the days of Jehoiada, Asa, Hezekiah, Josiah and Ezra: 13
6. David: 10
7. Levi, Phinehas and the priests: 9 (note says which verses name the person only in the verse before)

The block where Christian traditions part (listed in the alphabetical order of the labels, each with the same no-side sentence, the order said to carry no ranking):

8. A new covenant; the first covenant, the old covenant: 8
9. An everlasting covenant; a covenant of peace: 25
10. The covenant and foreigners, strangers, the nations: 8
11. The covenant and Israel, Judah: 52
12. The covenant and the law, the commandments, the promise: 33
13. The covenants, two covenants, a better covenant; Jesus its guarantor and mediator: 7 (by hand: Rom 9:4, Eph 2:12, Gal 4:24, Heb 7:22, 8:6, 9:15, 12:24)
14. Written on the heart; the Spirit and My words: 5 (Jer 31:33, Heb 8:10, 10:16, Isa 59:21, 2 Cor 3:6)

What the covenant is made with, marked by, or sworn on:

15. The blood of the covenant, the cup, the sacrifice: 12
16. The sign of the covenant: the rainbow and circumcision: 8
17. The ark, the tablets and the book of the covenant: 49
18. The covenant and loving devotion, mercy: 14
19. The covenant with an oath or a curse: 19
20. Between people and nations: made, sworn and forbidden: 40
21. Where the Berean prints "will": 2 (Heb 9:16-17; kept as a two-verse row on purpose: one Greek word, two English words, inside one passage)

The verbs (the covenant as the object of the verb):

22. Make, establish, give a covenant: 87
23. Keep, observe, hold fast to the covenant: 20
24. Remember, forget the covenant: 19
25. Broken, transgressed, forsaken, despised, profaned, corrupted; "did not continue in": 39
26. Every other use: 16

That is 26 rows counting the catch-all (brief: about 15-25, never 40).

## What the first build showed, and was fixed (before the sample)

- "Egypt, Sinai, Horeb and Moses" took three verses with Egypt only as a place (Gen 15:18 "river of Egypt", Ezek 17:15 envoys to Egypt, Hos 12:1): held out with `not_verses`, each stays in its own row.
- "Foreigners, ... the nations" took Josh 3:17 and Judg 2:20 (גּוֹי "nation" = Israel) and Deut 31:16 (נֵכָר "foreign gods"): held out.
- "The blood of the covenant ..." took Exod 34:15 (the neighbours' sacrifice to their gods) and Ezek 44:7 (foreigners offering fat and blood): held out.
- "The sign ..." took Josh 8:33 (מוּל "in front of", the same letters as circumcise): held out. The label no longer says "the Sabbath": Exod 31:13-17 carries the word "sign" in verses that do not carry the covenant word.
- "Where the Berean prints will" first held Gal 3:15; read: the Berean prints "covenant" there ("a human covenant"). Taken out; the note names Gal 3:15 as the contrast.
- "Levi, Phinehas and the priests" first held Lev 24:8 (the Sabbath bread, names no priest): taken out, it stays under "An everlasting covenant".
- "Moab, Shechem ..." first held verses that only read or keep the Book (Deut 29:9, 29:21; 2 Kgs 23:2; 2 Chr 34:30): taken out; they say read or keep, not made. 2 Chr 23:16 added (Jehoiada made a covenant).
- "Between people" first held Dan 11:22 ("prince of the covenant"): taken out.
- The first/old row was two verses; merged into "A new covenant" so no row is a stub except the deliberate "will" row.
- The verb rows from the frames alone left obvious verses in the catch-all (Gen 17:14 "he has broken My covenant", Judg 2:1, Exod 6:4, Isa 56:4 "hold fast", Luke 1:72 "remember"): added by hand, each only where the verse has the covenant word. The catch-all fell from 27 to 16.
- The patriarchs row first missed the Genesis 17 verses (they say "you", with Abram named in 17:1): added by hand and the label made "Abram, Abraham, Isaac and Jacob"; the note says so.

## The 16-verse sample (read in the Berean text, beyond the first examples)

| verse | row | verdict |
|---|---|---|
| Isa 28:15 | With the day and the night ... death | pass ("We have made a covenant with death") |
| Gen 17:19 | With Abram, Abraham, Isaac and Jacob | pass ("My covenant with him [Isaac] as an everlasting covenant") |
| Num 14:44 | Egypt, Sinai, Horeb and Moses | pass (Moses and the ark of the covenant) |
| 2 Chr 29:10 | Covenants made in Moab, ... Hezekiah | pass ("to make a covenant with the LORD", Hezekiah's speech; he is named in the chapter) |
| Mal 2:5 | Levi, Phinehas and the priests; An everlasting covenant; a covenant of peace | pass, loosely in the first (the verse says "him", Levi is named in 2:4; the row's note says so) |
| Ezek 44:7 | The covenant and foreigners ...; Broken ... | pass ("foreigners uncircumcised ... you broke My covenant") |
| Zech 9:11 | The blood of the covenant | pass ("the blood of My covenant") |
| Josh 3:17 | The ark, the tablets and the book | pass ("the ark of the covenant of the LORD") |
| Ps 25:10 | The covenant and loving devotion; Keep | pass ("loving and faithful to those who keep His covenant") |
| Jer 34:8 | Between people and nations | pass ("Zedekiah had made a covenant with all the people") |
| Isa 56:4 | Keep, observe, hold fast | pass ("hold fast to My covenant") |
| Prov 2:17 | Remember, forget | pass ("forgets the covenant of her God") |
| Dan 11:32 | Broken, transgressed ... | pass ("those who violate the covenant") |
| Ps 111:9 | An everlasting covenant | pass ("ordained His covenant forever") |
| Ps 50:16 | The covenant and the law | pass ("recite My statutes and bear My covenant") |
| Jer 33:21 | David; Levi, Phinehas and the priests; Broken | pass ("My covenant may also be broken with David ... the Levites who are priests") |

Also read and passed: Ps 44:17 ("betrayed Your covenant"), Deut 31:20 ("break My covenant"), Gen 14:13 (correctly held out of the patriarchs row: "bound by treaty to Abram", in "Between people"), Heb 8:6, Rom 11:26-27, Gen 26:28, Num 18:19, Lev 24:8, 2 Cor 3:14, Hos 6:7, Gen 17:14, Exod 6:4, Heb 9:1, 9:15, 9:18, Gal 3:15, Dan 9:27, 1 Kgs 8:9, 2 Chr 5:10, 1 Sam 22:8, 2 Chr 23:16.

**Tally: 16 of 16 show their row's label on the final build** (15 plainly, 1 loosely: Mal 2:5). Before that, reading the first build's lists and examples found 10 verses that did not show a label; all were fixed (above) and the final build re-read.

## For the review panel (contested points; each is set side by side, the page takes no side)

1. **How the covenants relate (the covenant-theology and dispensational readings part).** Rows 8-14 are the block, in the alphabetical order of their labels, with the same sentence in each: "A new covenant; the first covenant, the old covenant" (Jer 31:31, Luke 22:20, 1 Cor 11:25, 2 Cor 3:6, 3:14, Heb 8:8, 9:15, 12:24); "An everlasting covenant; a covenant of peace" (Noah, Abraham, David, the priests, Heb 13:20, 25 verses); "foreigners, strangers, the nations" (Gen 17:4, Isa 56:6, Eph 2:12); "Israel, Judah" (52 verses, including Jer 31:31, Rom 9:4, Heb 8:8, 8:10); "the law, the commandments, the promise" (Gal 3:17, Eph 2:12, Heb 8:6); "The covenants, two covenants, a better covenant" (Rom 9:4, Gal 4:24, Heb 7:22, 8:6, 9:15, 12:24); "Written on the heart" (Jer 31:33, Heb 8:10, 10:16, Isa 59:21, 2 Cor 3:6). Please check that the block as a whole reads as no ranking, and that the label "A new covenant; the first covenant, the old covenant" (joined in one row to avoid a two-verse row) does not read as setting "new" above "old".
2. **Heb 8:7, 8:13, 9:1, 9:18** (the decisive verses on the first covenant being "obsolete") are not in the hub because the Greek has no noun in them (the Berean supplies "covenant"). The note of row 8 says so, and Heb 8:13 is kept among the key verses. Panel: does a reader of this card miss them? Is the note enough, or should they sit in the row with the noun marked as supplied (the builder cannot do that; see below)?
3. **Rom 11:27** ("And this is My covenant with them when I take away their sins") sits under "Every other use" with a note naming Rom 11:26 ("all Israel will be saved"); it is not in the Israel row because the verse does not name Israel. Readers part on whom "them" is.
4. **"The covenants ... Jesus its guarantor and mediator"** (row 13): the label names Jesus; Heb 7:22, 8:6, 12:24 name Jesus in the verse and Heb 9:15 names Christ, so the row is by hand (pick-style) as the divine persons are. Rom 9:4, Eph 2:12 and Gal 4:24 stand beside them as the plural covenants. Check the label reads as the text's, not as a doctrine of mediation.
5. **"The blood of the covenant, the cup, the sacrifice"** (row 15): note takes no side on what a sacrifice does and on the Lord's Supper as sacrifice or memorial (Matt 26:28, Mark 14:24, Luke 22:20, 1 Cor 11:25, Heb 9:20, 10:29, 13:20). It also holds Dan 9:27 ("he will confirm a covenant with many ... put an end to sacrifice and offering"), a verse readers take of Antiochus, of Christ, of an Antichrist; the note says readers part on who "he" is and the page does not choose. Panel: Dan 9:27 is a hard verse kept on purpose; is it right here?
6. **"Where the Berean prints will"** (Heb 9:16-17): one Greek word, two English words in one passage; the note does not say which is right. A two-verse row kept on purpose (rule 6). Heb 9:15 and 9:18 flank it as "covenant".
7. **"With Abram, Abraham, Isaac and Jacob"** includes the Gen 17 verses that say "you" (God's speech to Abram, 17:1 and 17:5); the note says so. A Jewish reader may want the Hebrew בְּרִית מִילָה (the covenant of circumcision) noticed: Gen 17:10-14 are in "The sign of the covenant" as well; Acts 7:8 is "the covenant of circumcision".
8. **Hos 6:7** ("like Adam, they have transgressed the covenant") is in the "Broken" row in the Berean's words and is hard: readers part on whether Adam is the man or a place; the spec says the page says nothing of who Adam is. If the panel wants a note, it is a one-line addition.
9. **Between people and nations** (40 verses) puts Abraham and Abimelech, David and Jonathan, Solomon and Hiram, the Gibeonites (Josh 9) and the forbidden "make no covenant with them" (Exod 23:32, 34:12, Deut 7:2, Judg 2:2) in one row, under the one Hebrew word. Please check the label "made, sworn and forbidden" is right and that Ps 83:5 (an alliance against God) is not misleading there.
10. **Divine persons by hand:** no row names God, the Father or the Spirit; Jesus is named only in row 13 (by hand). The word "the LORD" is in verse texts only. "Keep, observe, hold fast" carries a note that the page says nothing of what keeping earns or whether it can be lost (an eternal-security hook, deliberately not touched).
11. **The Israel row is 52 verses and the ark row 49:** a reader may think they dominate; they are the plain counts of the Hebrew.

## What the builder could not express

- **A verse the builder does not see.** Isa 42:6 ("appoint you to be a covenant for the people and a light to the nations") has the covenant word as a prefix-split pair (לִ + בְרִית) and is in no row and not under "More"; its covenant word is the Hebrew but the builder's occurrence list does not hold it, so it cannot be added (`add` keeps only verses the builder has seen). It belongs in the "nations" row and the "new covenant"-adjacent block. Option wanted: let `add` name a verse the occurrence list lacks, or add every verse a word's lemma stands in (as the forgiveness worker also wanted).
- **A verse where the Berean supplies the noun** (Heb 8:7, 8:13, 9:1, 9:18): a row option "also" listing verses with no word of the family, marked "the Berean's 'covenant' has no noun in the Greek", would let the first-covenant verses stand in the row without equating anything.
- **A `pick`-style row that checks the verse has the concept word.** I used `add` with a never-matching `in_verse` (`"∅"`) so that a reference without the covenant word falls out, a workaround that works but reads odd. A `pick` that did the same check (or an `only_seen` flag) would be cleaner; `pick` as it stands shows any reference even where the word is absent.
- **OR between conditions of a row** (a verb row whose object is covenant by `object_of` OR is named by hand): the verb rows needed `add` lists for the verses the frames lack (hiphil "He has broken", infinitives, passives). Not wrong, but 60 percent of the "Broken" row is by hand.
- **A per-example note** (e.g. Mal 2:5 "him" is Levi): the row's note carries it for the whole row; one example cannot carry its own.
