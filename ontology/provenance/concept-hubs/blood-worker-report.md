# Blood hub: report (third round, 2026-10-25)

Spec: `<local> Ontology\ontology\concept-hubs\blood.json` (`"shown": false`)
Built: `<local> Ontology\out\concept-hubs\blood.json` (3 builds; 382 verses, 24 rows, no missing cards)

Build note: the build command was run with the absolute script path (`python "<local> Ontology/tools/concepts/hub_build.py" blood`) because the shell started in the .claude project folder, not the repository. It ran without a prompt.

## Words

- דָּם (h1818): 292 verses. αἷμα (g129): 90. αἱματεκχυσία (g130, Heb 9:22 only): 1. `sense` is empty: none dropped (0 of 383 word-uses), because the Hebrew puts bloodshed and the altar's blood in one word and a gloss rule would have dropped the 'bloodguilt'/'bloodshed' verses.
- Different words, named under Other words with a note each: מִשְׂפָּח (Isa 5:7, Berean 'bloodshed', a play on מִשְׁפָּט 'justice') and αἱμορροέω (Matt 9:20, 'bleeding', the same story as Mark 5:25 and Luke 8:43-44 which use αἷμα). The Hebrew גֹּאֵל 'avenger/redeemer' (Num 35) is not the blood word and is said so in the avenged row's `_why`; נֶפֶשׁ 'life' sits beside blood in Gen 9:4 and Lev 17:11 and is not equated with it.
- Three verses where the Hebrew has the word and the Berean's English does not, kept and told in 'Every other use' (and Ps 94:21 in the shedding row's note): Lev 19:16 ('the life of your neighbor'), Deut 32:14 ('the juice of the finest grapes'), Ezek 19:10 ('vineyard', footnote 'in your bloodline'), and Ps 94:21 ('condemn the innocent to death', Hebrew 'innocent blood'). Candidates for ontology/translation-findings.json.

## Rows (24; the Bible's order of themes: life, bloodshed, sign, rites, what the blood does, Christ)

| # | Row | n |
|---|---|---|
| 1 | Blood that cries out: Abel's, 'The earth will reveal her bloodshed' | 10 |
| 2 | 'The life is in the blood': not to be eaten or drunk | 24 |
| 3 | 'Flesh and blood': a human being | 6 |
| 4 | A flow of blood: childbirth, a woman's flow, the woman who touched His cloak | 12 |
| 5 | Shedding blood: murder, innocent blood, hands covered with blood | 76 |
| 6 | Blood-guilt: 'his blood will be on his own head', 'no bloodguilt', 'bloodshed pollutes the land' | 50 |
| 7 | Blood avenged and required: the avenger of blood; 'How long ... avenge our blood?' | 25 |
| 8 | Blood in war and in the LORD's judgment | 30 |
| 9 | Blood as a sign: water to blood, the moon to blood, blood in the visions | 19 |
| 10 | The Passover: blood on the doorposts | 5 |
| 11 | Blood in the rites of sacrifice: at the altar, sprinkled, poured out | 59 |
| 12 | Blood put on or sprinkled over: the people, ear, thumb and toe, house, tent, scroll | 15 |
| 13 | The Day of Atonement: blood taken in before the LORD | 10 |
| 14 | Blood in the worship of other gods: 'libations of blood', sons and daughters, the prophets of Baal, pig's blood | 6 |
| 15 | Atonement and forgiveness beside blood | 19 |
| 16 | Cleansed, purified, sanctified, washed: with blood | 12 |
| 17 | Justified, at peace, brought near, given access, overcoming: 'by the blood' | 6 |
| 18 | Redeemed, purchased, released: 'by Your blood You purchased for God' | 7 |
| 19 | The blood of the covenant | 12 |
| 20 | The cup: 'This is My blood', 'drink My blood', 'a participation in the blood of Christ' | 10 |
| 21 | The blood of Christ, of Jesus, of the Son, of the Lamb | 15 |
| 22 | 'His blood', 'His own blood', 'Your blood': the verse names no one | 7 |
| 23 | In the passion: Gethsemane, innocent blood, 'blood money', the Field of Blood, 'His blood be on us', blood and water | 11 |
| 24 | Every other use | 10 |

Every blood verse is in a row (More = 0). A verse sits in every row it fits (`match: all`). Rows 15 to 18 are in the alphabetical order of their labels and each says so, as on the covenant page, so the order reads as no ranking. Rows 16 and 21 are `pick` (hand-listed, read) because the builder cannot see the word in Heb 9:14 and Luke 11:51 (the word-by-word text files their clause under the previous verse); rows 11, 15 and 19 are by rule (rite words; atonement words; covenant words) with hand additions; the rest are by hand through `add`, which drops a verse that has no blood word (Deut 12:24, Lev 15:26, 2 Sam 3:29, Num 35:26 fell out that way and were removed from the lists; Isa 63:3 uses another Hebrew word for the blood and is not in the hub).

## The 16-verse sample (read in the Berean through the server)

| Verse | Row | Verdict |
|---|---|---|
| Ezek 24:8 | Abel / blood that cries out | pass ('placed her blood on the bare rock, so that it would not be covered') |
| 2 Sam 23:17 | life in the blood | pass ('Is this not the blood of the men who risked their lives?' ... 'refused to drink it') |
| Zech 9:7 | life in the blood | pass ('remove the blood from their mouths') |
| Gal 1:16 | flesh and blood | pass |
| Ps 94:21 | shedding blood | pass, loose: the Berean prints 'condemn the innocent to death'; the Hebrew is 'innocent blood'. The row's note now says so |
| Lam 4:14 | blood-guilt | pass ('defiled by this blood') |
| Jer 51:35 | avenged | pass ('May my blood be on the dwellers of Chaldea') |
| Ezek 21:32 | war and judgment | pass, loose ('Your blood will stain your own land' in a judgment) |
| 2 Kgs 3:23 | blood as a sign: 'water that looked like blood' | FAIL: 'This is blood! The kings have clashed swords and slaughtered one another' does not say water. Fixed: 3:22 ('looked as red as blood') stays in the sign row, 3:23 moved to the war row |
| Lev 10:18 | rites | pass ('its blood was not brought inside the holy place') |
| Lev 8:30 | put on | pass (blood sprinkled on Aaron and his garments) |
| Isa 66:3 | other gods | pass, loose ('presents a grain offering ... pig's blood'; the verse names an idol; the row's note says what the verse is) |
| Deut 21:8 | atonement beside blood | pass ('Accept this atonement ... innocent blood ... bloodshed will be atoned for') |
| Heb 13:11 | Day of Atonement | pass ('brings the blood of animals into the Holy Place') |
| Luke 11:51 | Abel | pass ('from the blood of Abel to the blood of Zechariah') |
| Matt 27:8 | passion | pass ('the Field of Blood') |

Tally: 16 sampled, 15 pass (3 of them loose, each now said in the row's note), 1 fail, fixed and rebuilt. Further verses read for the notes and checked against their rows: Prov 29:10, Jonah 1:14, 1 Kgs 2:9, Heb 10:4, Rev 8:8, Ezek 44:15, 1 Kgs 18:28, Ps 16:4, Ezek 23:37, 2 Kgs 3:22, Ps 50:13, Heb 12:4 (all pass). About thirty quotations in the notes were first written from memory and 14 differed from the Berean (Ps 9:12 'Avenger of bloodshed', Ps 72:14 'their blood is precious in his sight', Isa 26:21 'reveal her bloodshed', Acts 20:26, Ps 30:9 'bloodshed', Deut 32:14, John 6:55 'real drink', Rev 12:11 'conquered', Eph 2:13 'through', Zech 9:11, Heb 11:28 'sprinkling of blood', Heb 9:7, Isa 1:15 'covered', Num 35:33 'bloodshed pollutes'): all read in the server and corrected. A lesson for the next worker: do not quote the notes from memory.

Earlier build (before the first sample): the rites rule took `חַטָּאת` and `אָשָׁם` as sacrifice words and so put 2 Kgs 21:16, Lam 4:13 and Ezek 3:20 ('sin') and Luke 13:1 (Pilate's killing of the Galileans) in the rites row. Fixed by taking the two words out of the rule and holding Luke 13:1 and six figure-of-judgment verses (Isa 34:6, Jer 46:10, Ezek 39:17, 39:19, Matt 23:35, Luke 11:51) out with `not_verses`, each with its reason.

## Contested points for the review panel (row; verses; which readings part)

1. **What the blood does** (rows 15 to 18, alphabetical, no ranking). Atonement/forgiveness (Lev 17:11; Heb 9:22; Matt 26:28; Rom 3:25; Heb 10:4): covers, pays, cleanses, turns wrath away, gives a life for a life. Rom 3:25 ἱλαστήριον: 'atoning sacrifice' (Berean), 'propitiation', 'expiation', 'mercy seat' (the word is the mercy seat in Heb 9:5): shown as words, the note says readers differ and the page takes no side. Cleansing (Heb 9:13-14, 10:29, 13:12; 1 John 1:7; Rev 7:14): what is cleansed (flesh, conscience, sin). **Heb 10:29 'the blood of the covenant that sanctified him'**: readers part on whom 'him' is (the one who trampled, or the Son), and so on whether a believer can fall away; the note says so and the page takes no side. Justified/peace/near/access/overcame (Rom 5:9; Col 1:20; Eph 2:13; Heb 10:19; Rev 12:11). Redeemed/purchased/released (Ps 72:14; Eph 1:7; Heb 9:12; 1 Pet 1:19; Rev 1:5; 5:9; Acts 20:28): who is paid, from what.
2. **Acts 20:28** ('the church of God, which He purchased with His own blood'; row 18 and row 22): the Greek 'through the blood the own' can be 'His own blood' or 'the blood of His Own', and 'God' is also a textual question; the note says readers part on whom the verse means and the page does not choose.
3. **The cup and the covenant** (rows 19 and 20): Matt 26:28; Mark 14:24; Luke 22:20 (the Berean's note that some manuscripts lack it); 1 Cor 10:16; 11:25; 11:27; John 6:53-56. Readers part on whether the cup is the blood really present, a memorial, a participation or more, on whether John 6 speaks of the Supper, and on how the cup stands to sacrifice. 1 Cor 11:25's 'in remembrance of Me' is in the same verse and is shown, not read. The note says so; no side is taken.
4. **The life is in the blood / the eating of blood** (row 2): Gen 9:4; Lev 17:10-14; Deut 12; Acts 15:20, 15:29, 21:25. Readers part on whether the Council's 'and from blood' binds still, whether it is eaten blood or bloodshed, and whether Gen 9:4 (before Moses) binds beyond Israel. The page takes no side.
5. **Matt 27:25** ('His blood be on us and on our children!'; rows 6 and 23): the verse has been used against Jewish people. The note says that, says readers part sharply on what it says of anyone beyond those who spoke it, and sets it beside Pilate's 27:24 and says no more. For the rabbi's seat and the young African American believer's: is the wording enough, or should the row be shorter? It is also in the blood-guilt row as the same idiom ('his blood be on'), with a pointer to the passion row's note.
6. **Divine persons by hand** (rows 21 and 22): row 21 holds only verses that name Christ, Jesus, the Son or the Lamb in the verse (Heb 9:14; 10:19; 10:29; 12:24; 13:12; 13:20; 1 Pet 1:2, 1:19; 1 John 1:7, 5:6; Rev 1:5, 7:14, 12:11; Eph 2:13; 1 Cor 10:16). Row 22 holds the pronoun verses ('His blood', 'Your blood': Rom 3:25, 5:9; Acts 20:28; Eph 1:7; Col 1:20; Heb 9:12; Rev 5:9) with a note naming the passage that names him. 'The Lamb' is the text's own title and the page adds no name.
7. **Rev 19:13** ('a robe dipped in blood', the war row): whose blood (His own, the enemies', the martyrs'), readers part; the note says so.
8. **Heb 12:24** (Abel row and Christ row): 'a better word than the blood of Abel': what the better word is. The note takes no side.
9. **Vengeance** (row 7): the avenger of blood (Num 35; Deut 19) and the LORD who avenges (Ps 9:12; Rev 6:10; 19:2) against the New Testament's word on vengeance: the note says readers part and the page sets verses side by side. 2 Sam 3:27 (Joab, 'for the blood of Asahel') and 1 Chr 22:8 (David may not build, 'You have shed much blood') are hard verses and stay.
10. **Sacrifice and Christ's death** (rows 10, 13 and 11): the Passover and the Day of Atonement beside Heb 9 to 13: how they are related, readers part; the notes point to the sacrifice page and take no side.
11. **Blood among other gods** (row 14): Isa 66:3 ('pig's blood') is the LORD's word about those who choose their own ways; the verse names an idol, and the page says only that.

## Anything the builder could not express

- **A clause filed under the wrong verse.** The builder files a clause under the first verse from its start where the word occurs, so a verse where the word recurs in the same long clause is invisible to `add`, `in_verse` and the catch-all (Heb 9:14, whose clause starts at 9:13; Luke 11:51, filed at 11:50). They are not in "More"; the hub's verse count was 380 until the two were picked by hand. Needed: a builder pass that reports verses with the word in `d["occ"]` and in no row (an "unseen" list), or `add` that works on the occurrence index and not the clause index. This probably affects other hubs that use `add`.
- **A lemma the rule did not match.** `in_verse` with ἱλαστήριον did not take Rom 3:25 (the lemma is probably a different form); a worker cannot see the lemma spelling without a build. Needed: a way to print the lemmas of a verse (or a warning when an `in_verse` word matches no verse in the whole corpus).
- **A note for one verse in a shared row.** Matt 27:25 is in two rows and the sensitive note is in one; a per-verse note (a `verse_notes` map in the row) would put it beside the verse wherever it stands.
- **The senses of one lemma.** דָּם has the life, bloodshed, rite and figure senses in one lemma; the builder's `sense` is a regex on a gloss and cannot split them (the gloss is 'blood' nearly everywhere), so the senses are kept apart by rows, not by `sense`. This is as intended by the brief but worth saying.
- **`others` with a note on a word the gloss rule finds** worked; `min_n: 1, min_share: 0` was needed to show a word of one verse (Isa 5:7, Matt 9:20).

## Row-count note

24 rows, inside the brief's 15 to 25. Rows that could join if the owner wants fewer: 3 (flesh and blood, 6 verses) with 4 (a flow of blood, 12); 10 (Passover, 5) with 12 (put on); 14 (other gods, 6) into the rites row; 17 (justified, 6) into 15 or 18. They are kept apart because the text sets each apart and a reader looking for 'blood and the Passover' or 'flesh and blood' should find a row of its own.
