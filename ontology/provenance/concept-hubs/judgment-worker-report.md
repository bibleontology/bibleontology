# judgment hub: report (third round, 2026-10-25)

Spec: `<local> Ontology\ontology\concept-hubs\judgment.json` (`"shown": false`)
Built: `<local> Ontology\out\concept-hubs\judgment.json` (5 builds)

## Rows (26: 15 noun, 11 verb; the noun form leads)

Over the brief's 15-25 because the noun and the verb are separate records in the data, and the rows on who judges are by hand. Joinable if fewer are wanted: "Told to judge" + "Told not to judge"; the two "Judged, and ..." verb rows; "Justice for the poor" + "Justice and righteousness".

**Noun, "What the text says of judgment" (369 verses)**

| Row | n |
|---|---|
| The day of judgment, the hour of judgment; "at the judgment"; "after that to face judgment"; the judgment seat of God; the court seated, the books opened | 25 |
| Judgment and works, deeds | 15 |
| Condemnation, and "no condemnation"; "does not come into judgment" | 6 |
| Judgment and mercy, loving devotion, grace: "mercy triumphs over judgment" | 13 |
| Judgment and what follows, in the text's own words: eternal, fire, destruction, Gehenna | 9 |
| Judgment and the world, the nations | 21 |
| Judgments on Egypt, Moab, Edom, Babylon, Sidon, Thebes; judgments on Judah, Israel and Jerusalem | 32 |
| Justice for the poor, the fatherless, the widow, the foreigner | 16 |
| Justice and righteousness | 71 |
| In the gate and the court: judges, elders, witnesses, bribes; trials and sentences | 44 |
| The king and the throne | 24 |
| A judge, the Judge; "all judgment to the Son" | 24 |
| The LORD's justice and judgments: "a God of justice", "true and just are Your judgments" | 56 |
| Justice denied, perverted, asked for: "God has deprived me of justice", "Does God pervert justice?", "Where is the God of justice?" | 25 |
| Every other use | 56 |

**Verb, "Who judges whom" (301 verses)**

| Row | n |
|---|---|
| God judges, and is asked to judge | 89 |
| Jesus: "I judge", "I do not judge", "has entrusted all judgment to the Son", "who will judge the living and the dead" | 11 |
| Judged by "the Lord", "He", "the One": the verse does not name him | 9 |
| Told to judge, and promised judging | 20 |
| Told not to judge, and rebuked for judging | 18 |
| The judges (Moses, the judges of Israel, Samuel, the king, elders, priests) | 95 |
| Judged, and works, deeds, ways | 15 |
| Judged, and believing, faith | 6 |
| Judging the living and the dead, the world, the nations | 31 |
| Condemn, condemned (the 18 verses of κατακρίνω) | 18 |
| Every other use | 45 |

"More" is 0 in both forms. A verse stands in every row it fits (`match: "all"`).

## Words and the other senses

Words (each verse names the one it stands on; the hub never says the Greek and Hebrew are one word): κρίνω (86 in this sense, 12 not), κρίσις 46, κρίμα 25 (2 not), δικαιοκρισία 1 (Rom 2:5), κριτής 17, βῆμα 10 (2 not), δίκη 4, κατακρίνω 18, κατάκριμα 3, κατάκρισις 2, ἀνακρίνω 2 (12 not: "examine"); שָׁפַט 180 (2 not), מִשְׁפָּט 240 (**163 not**), שֶׁפֶט 16, דִּין verb 20 (4 not), דִּין noun 12 (5 not), Aramaic דִּין 5, דַּיָּן 2.

**Senses kept apart by `sense`:** מִשְׁפָּט as "ordinance, custom, regulation, prescribed, manner, share, plan" (163 of 403 verses, 40%: Lev 18:4, Deut 4:5, 1 Kgs 8:58, Ps 119's ordinances, Ezek 20) is out; κρίνω as "decided"/"concluded" (Acts 16:4, 20:16, 25:25, 1 Cor 2:2, Tit 3:12, 2 Cor 5:14) is out; ἀνακρίνω as "examine" is out. Held out by hand (`sense_drop`, reasons in the spec): Lev 19:35 (measures), Acts 3:13, 21:25, 15:19 (decisions), 1 Cor 7:37, 2 Cor 2:1. Kept by hand (`sense_keep`): Isa 40:27, Isa 32:7, Job 34:6 ("my right", a claim in law).

**Others** (different words the Berean also renders judge/judgment/condemn, named apart with notes): רָשַׁע "declare guilty" (Deut 25:1), γνώμη "opinion" (printed "judgment" at 1 Cor 7:25), καταδικάζω (Matt 12:7, Jas 5:6), καταγινώσκω (1 John 3:20), κριτικός (Heb 4:12), δικαστής, שְׁפוֹט, δ-forms of the court (Dan 3:2, Ezra 7:25), διάκρισις (Rom 14:1), κριτήριον (1 Cor 6:4), פָּלִיל, ὑπόδικος (Rom 3:19), αὐτοκατάκριτος (Titus 3:11).

## The 16-verse check

Read in the Berean text (`/api/verse`), one or more per row, not the first examples:

| Verse | Row | Verdict |
|---|---|---|
| Rev 14:7 "the hour of His judgment has come" | day / hour | yes |
| Jude 15 "execute judgment on everyone ... every ungodly act" | works | yes |
| 2 Cor 7:3 "I do not say this to condemn you" | condemnation | yes |
| Isa 16:5 "in loving devotion a throne ... a judge seeking justice" | mercy, loving devotion | yes |
| Matt 23:33 "the sentence of hell" | what follows | yes |
| Zeph 3:8 "My decision is to gather nations" | world, nations | yes |
| Jer 51:9 "her judgment extends to the sky" (Babylon) | judgments on peoples | yes |
| Ezek 22:29 "foreign resident without justice" | poor, foreigner | yes |
| Prov 19:28 "A corrupt witness mocks justice" | gate and court | yes |
| Zeph 3:5 "He applies His justice morning by morning" | LORD's justice | yes |
| Isa 59:14 "justice is turned away" | justice denied | yes |
| Eccl 3:17 "God will judge ... every deed" | judged, and works | yes |
| John 8:50 "There is One who seeks it, and He is the Judge" | "the Lord, He, the One" | yes |
| 1 Pet 4:6 "preached even to those who are now dead, so that they might be judged" | living and dead | yes |
| Ps 141:6 "When their rulers [judges] are thrown down" | the judges (label said "judge the people") | **partly**; label now starts "The judges:" so the verse that names judges fits |
| Rom 14:22 "Blessed is the one who does not condemn himself" | told not to judge | **no**: a blessing, not a command; removed, and the row relabelled "Told not to judge, and rebuked for judging" |

Tally: **14 yes, 1 partly (relabelled), 1 no (removed).**

Seventeen more read while checking notes and risky rows: Dan 4:37, Rom 13:2, Jas 3:1, Jas 5:12, Mark 12:40, Hos 6:5, Hos 10:4, Mal 3:5, Mic 5:1 (the Berean prints "judge of Israel"), Ps 58:11, Ps 82:3, Isa 51:5, Jer 2:35, Gen 49:16, Rev 17:1 (the Berean prints "punishment of the great prostitute") all fit. Two faults fixed: **1 Cor 11:29** (my note said "the Lord's supper without discerning"; the Berean says "without recognizing the body": note corrected) and **Job 22:13** ("Does He judge through thick darkness?" is Eliphaz's question to Job, not God judging: out of the God row, named under "Every other use"). **Jude 9**: the Berean prints "slanderous charge" for κρίσις; the note says so.

## Contested points for the review panel

1. **The final judgment and what follows (eternal punishment, annihilation, universalism).**
   - Row "Judgment and what follows ... eternal, fire, destruction, Gehenna" (9: Matt 5:22, 23:33, Heb 6:2, 10:27, 2 Thess 1:9, 2 Pet 2:3, 3:7, Jude 6, 7). Rows by the verses' own words, no verdict in the label; note: "punishment without end, an end of the wicked, or the restoration of all ... the page takes no side".
   - Verb row "Judging the living and the dead, the world, the nations" (31, includes Rev 20:12-13, 1 Pet 4:6, 2 Tim 4:1, Acts 17:31), same note.
   - Row "Condemnation, and no condemnation" holds Rom 5:16, 5:18 ("condemnation for all men" beside "justification and life for all men"; the note says how far "all" reaches is a point where traditions part) and Rom 8:1.
   - **Limit:** the hub holds only verses with a judgment word. Annihilationist proof-texts that name death or perishing without one (Matt 10:28) and the main universalist ones (Rom 11:32, 1 Cor 15:22, Col 1:20) are not here, and Matt 25:31-46 has no judgment word at all (it is in the card's gather list, "the sheep and the goats"). The panel should know the hub is silent on those texts, not neutral about them.
2. **Judgment by works beside being counted righteous by faith.** Noun rows "Judgment and works, deeds" (15) and "Condemnation, and no condemnation" (includes John 5:24); verb rows "Judged, and works, deeds, ways" (15: Rev 20:12-13, 1 Pet 1:17, Rom 2:1/2:3, Ezek 7:3) and "Judged, and believing, faith" (6: John 3:18, Mark 16:16, 2 Thess 2:12, Heb 11:7, Rom 14:22-23). Each carries "set side by side ... a verse that names more than one stands in each ... the page takes no side". A reader will notice the believing row is small (6): few verses join a judgment word to the word for faith. The hub does not add δικαιόω (the righteousness hub has it).
3. **God's justice in Israel's courts, kept as its own sense.** Row "In the gate and the court" (44), which also holds Pilate's, Gallio's and Festus's seats and kings' sentences (the Berean prints them with the same word). Also "Justice for the poor", "The king and the throne". **Note for the rabbi's seat:** the Torah is read through its courts and its poor here, with no Christian gloss; Isa 53:8 and Acts 8:33 ("deprived of justice") stand in the courts row as the word-by-word text has them, with no reading of who is meant.
4. **Divine persons by hand.** "God judges" (89; 3 participles by `pick`), "Jesus" (11), and "the Lord, He, the One" (9, Rev 19:11 "Faithful and True", Acts 17:31 "the Man He has appointed", 1 Pet 4:5, John 8:50, 1 Cor 4:4-5, 11:32, Rev 6:10, 16:5): note says readers take these of the Father or of Christ and the page does not choose. In the noun form, "A judge, the Judge" carries the same note for 2 Tim 4:8 and Jas 5:9 ("the Lord", "the Judge"). Jesus verses side by side as they stand: "I judge no one" (John 8:15), "I do not judge him" (12:47), "I judge as I hear" (5:30), "the word I spoke will judge him on the last day" (12:48).
5. **"Do not judge" and "judge righteously"** in adjacent rows (verb), with a note that the page does not say how they are reconciled. The "Told not to judge" row includes Rom 2:1/2:3 and Jas 4:11-12, which are rebukes of judging rather than commands; the label says so.
6. **Isa 11:3-4** (the shoot of Jesse "will judge the poor with righteousness") is in the judges row with a note that readers differ on whom it means.
7. **Mark 16:16** (longer ending) in the believing row and the condemn row, flagged in both notes.
8. **Hard verses kept:** Rev 20:12-13 and 1 Pet 4:6; the Job and prophets row of complaints that God denies justice (Job 27:2, Hab 1:4, Mal 2:17) beside "God does not pervert justice" (Job 34:12), shown together with a note and no choice.
9. **Placement worth a second look:** Rom 2:5 and 2 Thess 1:5 ("righteous judgment of God") are in the LORD's justice row, not the day-of-judgment row, because the verses speak of the quality of the judgment rather than the day. Ezek 21:27 ("until He comes whose right it is") is left under "Every other use" because readers differ on whom it means.

## What the builder could not express

- **Frames lack the Hebrew participle.** 'The judge', 'the judges', 'my Judge' (שֹׁפֵט) carries no frame record, so about 45 verses were missing from the verb form (Judg 2:16-19, Deut 17:9, Isa 33:22, Job 9:15, Ps 2:10 ...). I put them in by `pick` (not validated against the word: each was taken from the word's own verse list, in the English numbering; Mic 5:1 is Hebrew 4:14). An option to take a lemma's verses from the word-by-word text for a verb row would remove the hand list.
- **No AND between conditions.** "ἡμέρα next to κρίσις" was only possible as `with` + `adjacent`, which also took κριτής ("that day" in 2 Tim 4:8) and 2 Pet 2:4 (a clause filed under the wrong verse); both are `not_verses`.
- **No "not_agent".** A rule for "God judges" would have been easy with an agent condition; "a person judges" needs one that excludes the divine set. All agent rows are by hand.
- **A pick and a rule cannot share a row.** The condemn row is all `pick` (18) because the frames lack John 8:10 and Rom 8:34.
- **The word-by-word text uses Hebrew numbering for the Psalms**, so `/api/verse` for Ps 58:11 and Mic 5:1 shows the Hebrew words of the neighbouring verse beside the right English. Not a hub fault, but a reader who opens the word strip will see a mismatch.
- **Judged by the law / by the gospel** (Rom 2:12, 2:16, 2:27, Jas 2:12) would have been a good row; there are only about eight verses and it sits under "Every other use" with a note.

## Other

- Door "hell" resolves to the card named Sheol; not used, to avoid calling Gehenna Sheol. The eternal row opens "death".
- `leads` use only cards that exist (checked: none missing).
- Not reviewed by the panel; `_review` says so.
- Not touched: `hub_build.py`, any other spec, the server, `index.html`, git.
