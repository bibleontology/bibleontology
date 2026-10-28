# Sin hub rework, 2026-10-25

The owner's change of approach: "iniquity, transgression and sin are close to interchangeable". The hub now has עָוֺן (h5771), פֶּשַׁע (h6588), the verb פָּשַׁע (h6586), παράβασις (g3847) and παραβάτης (g3848) as its own words beside the חָטָא / ἁμαρτία family. Four builds were used. `shown` is still false. The only files edited are `ontology/concept-hubs/sin.json` and this report.

## Totals

| | before | after |
|---|---|---|
| rows | 24 (noun 15, verb 7, adjective 2) | 25 (noun 16, verb 7, adjective 2) |
| verses (noun / verb / adjective) | 472 / 186 / 65 = 723 | 686 / 201 / 65 = 952 |
| More (noun / verb / adjective) | 75 / 77 / 28 | 151 / 87 / 28 |
| words | 14 | 19 |

עָוֺן counts in 197 verses in the sense of wrongdoing (15 other). פֶּשַׁע counts in 88 (1 other). פָּשַׁע counts in 24 (13 other). παράβασις counts in 7 and παραβάτης in 5.

## Rows before and after (verses in the row)

Noun form:

| row | before | after |
|---|---|---|
| Sin beside iniquity, transgression, trespass, lawlessness, wickedness. Now a rule with the old 73 as `add`, relabelled "Iniquity, transgression and sin side by side; trespass, lawlessness, wickedness". | 74 | 90 |
| Confessing sin (relabelled "... iniquity, transgression") | 12 | 15 |
| The sin offering (unchanged) | 121 | 121 |
| Forgiven, atoned for, covered ... (relabelled; now "... removed, passed over, not counted against") | 109 | 153 |
| The sins of the kings (unchanged) | 35 | 35 |
| Sin and its consequence | 58 | 112 |
| Sin and the law, the commandment | 21 | 31 |
| Sin through one man; sinful from conception (unchanged) | 5 | 5 |
| "Each is to die for his own sin" ... | 9 | 12 |
| The fathers' sins, and the children | 7 | 18 |
| "All under sin" ... (unchanged) | 9 | 9 |
| Sin to be mastered ... (unchanged) | 14 | 14 |
| "Sin living in me": Romans 7 (unchanged) | 9 | 9 |
| A sin that leads to death; not forgiven (unchanged) | 5 | 5 |
| Christ and our sins (unchanged) | 20 | 20 |
| **new:** Sin carried or lifted (the verb נָשָׂא, αἴρω) | - | 47 |

Verb form: no one who does not sin 9 -> 9; born of God 3 -> 3; do not sin 10 -> 10; against the LORD 29 -> 33 (relabelled "Sinned, transgressed, rebelled against the LORD, against God"); against another 19 -> 19; "I have sinned" 43 -> 44 (relabelled, adds "we have transgressed"); If someone sins 13 -> 13.

Adjective form: sinners beside the righteous 16 -> 16; Christ Jesus and sinners 24 -> 24.

## What I did, and what I merged

1. **The words.** The new words are in `words`. The `sense` pattern was widened to the glosses these words carry: iniquity, guilt, transgression(s), rebel(lion/led), offense, crime, trespass, wrongdoing. The Berean's own word for עָוֺן is often "guilt" (Ps 32:5 "forgave the guilt of my sin"; Jer 3:13; Jer 33:8; Ezek 18:19), so a pattern with "iniquity" alone would have dropped hundreds of verses.
2. **Sense handling.** The wider pattern brought back three drops of the first round (Lev 19:17, Lev 22:9 "incur guilt"; Eccl 10:4 "great offenses"); I dropped them again with `sense_drop`. The political "rebelled" of פָּשַׁע (1 Kgs 12:19; 2 Kgs 1:1, 3:5, 3:7, 8:20, 8:22; 2 Chr 10:19, 21:8, 21:10) and Prov 18:19 (the brother who was wronged) are dropped by `sense_drop`, each with its reason.
3. **Gen 4:13.** עָוֺן as the punishment ("My punishment is more than I can bear"), also Job 19:29: the English gloss "punishment" is not in the pattern, so these verses are not counted anywhere. This is written in `_sense_why` and in the rework's review entry. Lam 4:6 stays, because its other word, חַטָּאת, passes the rule.
4. **Greek.** παράβασις and παραβάτης are the hub's words (they land in the law row and the consequence row by rule). ἀνομία and παράπτωμα stay in "Other words". The reason is in `_words_why`: the rows' labels use the Berean's words, and the Berean prints "lawlessness" and "trespass" for them; where they stand beside a sin word (Eph 2:1, Rom 4:7, Heb 8:12, 10:17, 1 John 3:4) the first row carries them. Both are named in the first row's label.
5. **Ps 103:12.** It is in the forgiven row (an `add`, lead example no. 2), whose label now says "removed", with a note naming the Hebrew verb רָחַק and pointing to the forgiveness hub's row "Sins put away". Mic 7:19, Isa 38:17, Zech 3:4 (removed) are added to the same row for the same picture.
6. **Merged (no row of its own).**
   - "Sin beside..." (a 73-verse hand list) became a rule (a hub word within six words of another in one phrase) with the 73 kept as `add`, plus 12 pairs read in the Berean.
   - The new words' verses went into the existing rows: forgiven +44, consequence +54, fathers +11, "each dies for his own" +3, law +10, confessing +3.
   - "passed over, not counted against" was added to the forgiven label rather than opening a row.
   - The old note on the fathers' row ("Exod 20:5 and Num 14:18 are not counted here") and on the "each dies" row (Jer 31:30) were rewritten, because they are now counted.
   - The only new row is "Sin carried or lifted" (47): the Hebrew נָשָׂא is both "bear" and "forgive/lift" in the same idiom, and the row shows both without choosing. Its verses are also in the forgiven row where the Berean says forgive/take away.
7. **Not in any row.** The 151 noun More verses are the remainder, mostly Job, Proverbs and Psalms verses on iniquity, and Ezekiel 7, 14, 16.
8. **Review log.** `_review_2026_10_25` keeps all 25 earlier entries unchanged and adds one entry that quotes the owner's words and says what the page does and does not claim.

## 16-verse sample (read in the Berean)

13 are from the new words, 3 from the old.

| # | verse | row | verdict |
|---|---|---|---|
| 1 | Ps 103:12 | forgiven (פֶּשַׁע) | pass: "so far has He removed our transgressions from us" |
| 2 | Prov 16:6 | forgiven (עָוֺן) | pass: "iniquity is atoned for" |
| 3 | Deut 19:15 | side by side (עָוֺן, חַטָּאת, חֵטְא) | pass, with a caveat: the Berean prints "wrongdoing or sin ... offense", not "iniquity"; now said in the row's note |
| 4 | Lev 26:40 | confessing (עָוֺן) | pass: "confess their iniquity and that of their fathers" |
| 5 | Ezek 18:31 | consequence (פֶּשַׁע) | pass: "all the transgressions ... Why should you die?" |
| 6 | Heb 9:15 | consequence (παράβασις) | weak pass: "died to redeem them from the transgressions"; death and transgression in one verse, but it is the death for them, not a consequence. Left, as "died to sin" is already in the row. For the panel. |
| 7 | Num 15:31 | law (עָוֺן) | pass: "broken His commandment; his guilt remains on him" |
| 8 | Rom 4:15 | law (παράβασις) | pass: "where there is no law, there is no transgression" |
| 9 | Jer 31:30 | each dies for his own (עָוֺן) | pass |
| 10 | Jer 11:10 | the fathers' sins (עָוֺן) | pass: "the sins of their forefathers" (the Berean prints "sins") |
| 11 | Lev 10:17 | carried (עָוֺן + נָשָׂא) | pass: "to take away the guilt of the congregation" |
| 12 | Jer 2:29 | against the LORD (פָּשַׁע) | pass: "rebelled against Me, declares the LORD" |
| 13 | Lam 3:42 | "I have sinned" (פָּשַׁע) | pass: "We have sinned and rebelled; You have not forgiven" |
| 14 | Gen 4:7 | mastered | pass |
| 15 | 1 John 5:16 | a sin that leads to death | pass |
| 16 | Luke 15:2 | Christ and sinners | pass |

Result: **16 pass (one weak, one with a caveat), 0 fail.**

Extra spot checks, all pass: Mal 2:6 and Rom 2:25 (law: "turned many from iniquity", "if you break the law" for παραβάτης), Ezek 44:12, Num 5:31, Exod 28:38 and Lev 20:19 (carried), Josh 22:17 ("not cleansed ourselves", forgiven), Jer 5:25 (side by side).

Fixed after reading: four forgiven-row verses took false matches from the new words and are now `not_verses` with reasons: Isa 26:21 ("cover its slain"), Lev 17:16 (bodily washing), Job 31:33 ("covered my transgressions ... hiding", concealing), Prov 28:13 ("conceals his sins"; it stays in the confessing row). Also corrected a wrong claim of my own about Lam 4:6, and a wrong Hebrew word in a note (Ps 32:1's second word is not חֵטְא).

## For the panel to re-read

- **First row** (note and label): Exod 34:7 is quoted; the note says the three words are shown together and the page does not call them one word; 1 John 3:4 is still the one verse that says one is the other. The owner's "close to interchangeable" is quoted only in the review entry. Is the first row's note too strong or too weak on the "interchangeable" point?
- **Forgiven row (153).** Hard verses stay and say "not": Isa 22:14 "will not be atoned for", 1 Sam 3:14, Jer 18:23, Ps 109:14, Josh 24:19. The new "passed over, not counted against" phrase is the text's (Mic 7:18; Ps 32:2; Rom 3:25; Rom 4:8; Ezek 18:22; Acts 7:60). The row also holds the sin-offering and Levitical verses (a held request from the first panel).
- **Carried or lifted** (47): נָשָׂא's two senses are shown together. Isa 53:6 and 53:12 are in it, and Isa 53:8 is in the consequence row; they name no one, and the page takes no side on whom they speak of. Exod 28:38 (Aaron bears the iniquity of the holy things) and Num 18:1, 18:23 (the priests bear the iniquity of the sanctuary) are in the row, which is the Hebrew idiom; is that clear?
- **Consequence row (112).** It is the broadest. 37 verses were added by hand (5 in the first pass, 32 in the second) and 17 more came by rule from the new words. The Amos formula (7 verses) is there as "judgment announced for transgressions".
- **Fathers' row (18)** and **"each dies" row (12).** These are two of the three original-sin rows set side by side; both swelled with Hebrew verses (Exod 20:5, Deut 5:9, Num 14:18, Jer 32:18, Ezek 18:17-19, Jer 31:30). Does the swelling tip the balance of the three?
- **Heb 9:15** (weak pass above) and the Greek Christ-row (unchanged; a held request still stands).
- **Isa 1:2, Jer 2:29, Jer 3:13, Isa 59:13** in the LORD row: the verse itself names the LORD in each. Ezek 2:3, Hos 7:13, Hos 8:1, Isa 43:27, Jer 2:8 and others say "Me" or "You" or name no one, and are in More.

## What the builder could not express

- **Verbs without a frame are invisible.** The builder reads verb forms only from the frames. Six פָּשַׁע verses with the verb as a participle ("transgressors", "rebels") are in no row and not even in More: Ps 37:38, Isa 48:8, Prov 28:21, Dan 8:23, Hos 14:9, Ezek 20:38. Two more (Isa 1:28, Ps 51:13) are in the adjective More. A `pick` row can place them, but the adjective row "Sinners beside the righteous" is a rule row and a rule row cannot also take picks; there was no row-count room for a row of "transgressors".
- **One `sense` pattern for all words.** A per-word sense would have avoided the three re-dropped verses (Lev 19:17, Lev 22:9, Eccl 10:4).
- **No hub-level lead note.** The builder writes no note above the rows. The three-words statement (with Exod 34:7 quoted) is in the first row's note and in `titles.noun` ("What the text says of sin, iniquity and transgression"). If a hub-level lead note is wanted, the builder needs a field for it.
- **Pair rule.** The first row's rule ("another of these words within six words in one phrase") cannot say "a different word from this one", so חַטָּאת is left out of the partner list. Pairs split across phrases of one verse (Ps 32:5, Job 7:21) are added by hand, so other such pairs may be missing.
- **Row count.** The hub is at 25. Clusters left in More that want a row of their own if the editor allows: the golden-calf verses (held request); Job's "iniquity" verses; "iniquity as a stumbling block" (Ezek 7, 14, 18); God "remembering, visiting, counting" iniquity (Ps 90:8, 130:3, Hos 8:13, Isa 13:11); the "transgressors" participles above.
