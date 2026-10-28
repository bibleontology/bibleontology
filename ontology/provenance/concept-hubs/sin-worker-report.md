# Sin hub: report (2026-10-25)

Spec: `ontology/concept-hubs/sin.json` (`"shown": false`). Built: `out/concept-hubs/sin.json`.
26 rows in all: 16 noun, 8 verb, 2 adjective. No catch-all rows; what no row takes is under More (noun 75, verb 62, adjective 35). Builds run: 8, over the brief's 5 (four were drafts and probes: two row-rule drafts, and two with `sense` open to see what the sense rule drops; four were of the real spec).

## Rows and counts

Noun form (lead; 467 verses)

| # | Row | n | How made |
|---|-----|---|----------|
| 1 | Sin beside iniquity, transgression, trespass, lawlessness, wickedness | 74 | rule (73) + Exod 34:7 by hand, now a pick |
| 2 | Sin and the law, the commandment | 21 | rule (in_verse law words); 4 ritual-law verses out by `not_verses` |
| 3 | Sin through one man, Adam; sinful from conception; "born in utter sin" | 6 | pick (original sin, 1 of 3) |
| 4 | "Each is to die for his own sin"; the son does not bear the father's | 8 | pick (original sin, 2 of 3) |
| 5 | The fathers' sins, and the children | 7 | pick (original sin, 3 of 3) |
| 6 | "All under sin", "slaves to sin", "dead in your trespasses and sins" | 10 | pick (what is called total depravity, 1 of 3) |
| 7 | Sin to be mastered, resisted, thrown off: "you must master it", "sin shall not be your master", "set free from sin", "dead to sin" | 14 | pick (2 of 3) |
| 8 | "Sin living in me": Romans 7 | 9 | pick (3 of 3) |
| 9 | Sin and death | 41 | rule (death words); Jer 18:23 and Rev 1:5 out |
| 10 | Sin and what follows: "sevenfold for your sins", ... | 17 | pick |
| 11 | A sin that leads to death; a sin that is not forgiven | 5 | pick |
| 12 | Confessing sin | 12 | pick |
| 13 | Sin forgiven, atoned for, covered, wiped away, cleansed, taken away | 109 | rule (forgive/atone/cover/cleanse words) + 6 added by hand; Hos 10.8 out |
| 14 | The sin offering; a sacrifice for sin | 121 | pick: every verse where the Berean prints "sin offering" (114) + 7 "offering/sacrifice for sin" |
| 15 | Christ and our sins: "died for", "bore", "takes away", "knew no sin" | 20 | pick (Jesus by hand) |
| 16 | The sins of the kings: "the sin Jeroboam caused Israel to commit", Baasha, Manasseh | 30 | rule (Jeroboam in verse, 21) + 9 added |

Verb form (186 verses)

| # | Row | n | How made |
|---|-----|---|----------|
| 17 | "There is no one who does not sin"; "all have sinned"; "if we say we have not sinned" | 10 | pick (whether a believer sins, 1 of 3) |
| 18 | "Anyone born of God ... cannot go on sinning" | 3 | pick (2 of 3) |
| 19 | "Do not sin", "sin no more", "stop sinning" | 10 | pick (3 of 3) |
| 20 | Sinned against the LORD, against God | 29 | pick (God named in the verse) |
| 21 | Sinned against another: a neighbor, a brother, one's own body | 19 | pick |
| 22 | "I have sinned", "we have sinned" | 43 | pick |
| 23 | "If someone sins": the Law's cases, sinning unintentionally; sinning deliberately | 13 | pick |
| 24 | "He caused Israel to sin", "caused Judah to sin" | 15 | rule (Jeroboam in verse, 12) + 3 added |

Adjective form (65 verses)

| # | Row | n | How made |
|---|-----|---|----------|
| 25 | Sinners and the righteous | 9 | rule (righteous in verse) |
| 26 | Christ Jesus and sinners: tax collectors and sinners, "came into the world to save sinners" | 24 | pick (Jesus by hand) |

Dropped on the way, to stay near 25: a row for "against You / against Me / against Him" (16 verses, the first build had it; they stand in More and Ps 51:4 is in row 22); a golden-calf row (Exod 32, Deut 9; More); John's "guilty of sin" verses (9:41, 15:22, 15:24, 16:8-9, 19:11; More); an Old Testament "sinners" row (Gen 13:13, Ps 1:1, Isa 33:14 ...; More).

## The 16-verse check (Berean text, read from the server)

| # | Verse | Row | Verdict |
|---|-------|-----|---------|
| 1 | Amos 5:12 | 1 beside iniquity/transgression | shows it: "transgressions are many and your sins are numerous" |
| 2 | 2 Kgs 10:31 | 2 law | shows it: "follow the instruction of the LORD ... the sins that Jeroboam had caused Israel to commit" (Berean "instruction", Hebrew תּוֹרָה) |
| 3 | Rom 5:16 | 3 one man | shows it: "the one man's sin" |
| 4 | Rom 6:17 | 6 slaves to sin | shows it |
| 5 | Heb 12:4 | 7 mastered/set free | FAILED: "In your struggle against sin" was under a label that named only mastering and being set free. Fixed: label now reads "mastered, resisted, thrown off" (Heb 12:1 "throw off ... the sin", 12:4 "resisted"); note and `_why` say so |
| 6 | Rom 7:9 | 8 Romans 7 | shows it: "sin sprang to life" |
| 7 | Num 18:22 | 9 sin and death | shows it in the Hebrew only: the Hebrew has "bear sin ... die" (חֵטְא, מוּת); the Berean prints "incur guilt and die". Kept (the original arbitrates) and flagged below |
| 8 | Hos 9:9 | 10 follows | shows it: "He will punish their sins" |
| 9 | Mark 3:28 | 11 not forgiven | shows it as the contrast the row sets side by side: "forgiven all sins and blasphemies" (3:29 is the unforgiven) |
| 10 | Heb 10:2 | 13 forgiven/cleansed | shows it: "cleansed once for all ... guilt of their sins" |
| 11 | Num 29:38 | 14 sin offering | shows it |
| 12 | Gal 1:4 | 15 Christ | shows it: "who gave Himself for our sins" (the verse says "Himself"; Gal 1:3 names Christ) |
| 13 | 2 Kgs 17:21 | 16 kings | shows it: "Jeroboam ... caused them to commit a great sin" |
| 14 | Jer 44:23 | 20 against the LORD | shows it: "sinned against the LORD" |
| 15 | Luke 17:4 | 21 against another | shows it: "sins against you" |
| 16 | Lev 6:3 | 23 "If someone sins" | shows it: "if he commits any such sin that a man might commit" |

Tally: 14 show their label as first built, 1 failed and was fixed (Heb 12:4, label), 1 shows it in the Hebrew only (Num 18:22). After the fix, 15 of 16 show it in the Berean's English and 1 in the Hebrew.

Beyond the 16, the first examples of every row were read while building: all show their label. Texts also read in the Berean to choose picks: Rom 5-8, 1 John, Heb 10 and 12, Lev 4-6, Num 15, Ezek 18, Deut 24:16, Josh 7, and the 114 "sin offering" verses.

## Words and `others`

Words (all in the sense of "sin"; 14 words): Hebrew nouns חַטָּאת h2403 (263 verses in sense, 5 not; also the sin offering), חֵטְא h2399 (28, 5 not), חֲטָאָה h2401 (7), חַטָּאָה h2402 (2), Aramaic חֲטָא h2408 (Dan 4:27), Aramaic חַטָּאָה h2409 (Ezra 6:17); Greek ἁμαρτία g266 (150), ἁμάρτημα g265 (4); verbs חָטָא h2398 (156 in sense, 63 not), ἁμαρτάνω g264 (37), προαμαρτάνω g4258 (2); adjectives חַטָּא h2400 (19), ἁμαρτωλός g268 (45), ἀναμάρτητος g361 (1).
- Sense rule: MACULA gloss reads sin/sinned/sinning/sinful/sinner. It drops חָטָא as "purify/cleanse" (Lev 8:15, Num 8:21, 19:12, Ps 51:7), "bear the loss" (Gen 31:39), "miss" (Judg 20:16, Prov 8:36) and 11 noun verses glossed guilt/punishment/offense/failure. Four verses the Berean itself prints "sin" in are put back (`sense_keep`: Deut 15:9, 21:22, Ezek 23:49, Eccl 5:6).
- The sin card lists h5512 סִין (the wilderness of Sin) as one of its six words. It is a place name and is not in the hub. The card's owner should look at that (the card itself, not this hub).
- `others` (shown apart, with notes saying they are different words and that the page does not make them one): עָוֺן "iniquity" h5771, פֶּשַׁע "transgression" h6588, ἀνομία "lawlessness" g458, παράπτωμα "trespass" g3900 (all four placed by `add` with their own verses), plus what the gloss rule found where the Berean says "sin" (עָוֺן in 5 verses; ἀγνόημα "sins of ignorance", Heb 9:7). Row 1 sets sin beside these as the text does (Exod 34:7 lists three).

## Contested points for the review panel

Original sin and inherited guilt: rows 3, 4, 5 (noun form), one note each, "the page takes no side and ranks none above another".
- Row 3: Rom 5:12, 5:14, 5:16, 5:19 (the many were made sinners; an adjective verse, placed by pick); Ps 51:5 ("I was sinful when my mother conceived me", David's confession); John 9:34 (the Pharisees' retort, "born in utter sin"; the note says whose words they are). Readers part on: whether Rom 5:12's "because all sinned" is Adam's guilt imputed, a nature inherited, or each one's own sin; whether Ps 51:5 is general or David's own; whether John 9:34 is evidence at all. Panel question: is "Sin through one man, Adam; sinful from conception" a label that leans? It only repeats the verses' words, but "Adam" is named only in Rom 5:14.
- Row 4: Deut 24:16, 2 Kgs 14:6, 2 Chr 25:4 ("each is to die for his own sin"), Num 27:3, Ezek 18:4, 18:20, John 9:2-3. Panel question: John 9:2-3 is about a man's blindness and a parent's sin, not a law of guilt; the note says so.
- Row 5: Exod 34:7, Lam 5:7, Jer 14:20, Neh 9:2, Dan 9:16, Ps 106:6, Ezek 18:14. Ezek 18:14 sits here (a son who sees his father's sins and does not do likewise) though it also speaks for row 4; the panel should say which side reads it.
- Not shown, named in notes: Gen 8:21, Job 14:4, Ps 58:3, Eph 2:3, Rom 5:18, 1 Cor 15:22 (no hub word), Exod 20:5, Num 14:18, Jer 31:30 (iniquity, a different word).

What is called total depravity: rows 6, 7, 8 (noun form).
- Row 6 "All under sin, slaves to sin, dead in sins": Rom 3:9, Gal 3:22, John 8:34, Rom 6:6, 6:16, 6:17, 6:20, 7:14, Eph 2:1, Rom 8:10.
- Row 7 "mastered, resisted, thrown off": Gen 4:7, Rom 6:2, 6:7, 6:11-14, 6:18, 6:22, 8:2, Heb 12:1, 12:4, 1 Pet 2:24, 4:1. Panel question: Rom 6 is said of believers and Gen 4:7 of Cain, so the row mixes who is addressed; the note says the row is about the verbs (master, reign, free), not about a person's ability.
- Row 8 Rom 7:8-25: readers part on whether "I" is Paul before Christ, a believer, or a person under the law; Rom 7:14 is also in row 6.

Whether a believer sins: rows 17, 18, 19 (verb form).
- Row 17 (no one is without sin): 1 Kgs 8:46, 2 Chr 6:36, Eccl 7:20, Prov 20:9, Jer 2:35 (a people denying sin), Rom 3:23, 5:12, 1 John 1:8, 1:10, 2:1. Row 18 (1 John 3:6, 3:9, 5:18). Row 19 (commands: Exod 20:20, Ps 4:4, 119:11, Ezek 3:21, John 5:14, 8:11, Rom 6:15, 1 Cor 15:34, Eph 4:26, 1 John 2:1). 1 John 2:1 stands in rows 17 and 19. Readers part on 1 John 3:9 (cannot go on sinning: continuing practice, or no sin, of every believer or an ideal), against 1:8-10.
- Panel question: row 17 mixes Old Testament "no one" (everyone) with 1 John (believers); the note says so.

Sin leading to death; the unforgivable sin: row 11 (noun form): 1 John 5:16, 5:17, Matt 12:31, Mark 3:28, 3:29. Readers part on what the sin to death is, whether the death is bodily or of the soul, and what blasphemy against the Spirit is. Mark 3:28 (all sins forgiven) is in the row as the contrast the text sets; Heb 10:26 (sinning deliberately; no sacrifice remains) is in row 23 (verb form) with a note that readers part on whether it describes a believer who falls away. Panel question: does putting Heb 10:26 in the Law's cases row, beside Num 15:30, read as a ruling? (It is there because the text says "deliberately"/"defiantly" in both.)

Sacrifice and atonement (the brief's point for the sacrifice hub, touched here): row 14 and row 13 have notes (what a sacrifice does; fulfilled, ended or continued) that take no side; Heb 10:4 and 10:11 ("can never take away sins") stand in row 13. Rom 8:3 is in row 14 because the Berean prints "as an offering for sin"; the Greek (περὶ ἁμαρτίας) is "concerning sin", and the panel should say whether that sits right.

Divine persons by hand: row 15 (Jesus) names him in the verse for Matt 1:21, John 1:29, 1 Cor 15:3, Heb 1:3 (the Son), Rom 8:3 is in row 14 not 15; John 8:46 and Matt 26:28 are in his own words ("Me", "My blood"); Gal 1:4, 1 Pet 2:24, 1 Pet 3:18, 1 John 2:2 and 3:5, Heb 2:17, 9:26, 9:28, 4:15, 2 Cor 5:21 say "He", "Himself", "Him", "Christ" and the sentence or the one before names Christ; the note says so. Panel question: is that honest for 2 Cor 5:21 ("God made Him who knew no sin to be sin", the verse says "Him")? Row 20 (the LORD, God): picks where the verse itself names him (listed in `_why`); "against You/Me/Him" verses are not placed in a God row (they are in More or in row 22) and the note says so. Row 26: Matt 9:10, Mark 14:41 name Jesus in the scene.

Rows with no doctrinal point but where the panel might check wording: row 16 (the kings' sin; no side), row 24, row 10 (sin and what follows).

## What the builder could not express

1. `add` did not take Exod 34:7 into a rule row (row 1, `in_verse` of the iniquity words): the verse is in the noun list (it was in the first draft's catch-all), and `add` requires the verse to be in `seen_form`, but the build still left it out. I did not find why. I turned the row into a pick of its 73 rule verses plus Exod 34:7. A cause to look at: the data spells the lemma of עָוֺן two ways (holam / holam haser), and Exod 34:7's phrase structure.
2. A row condition on what the Berean prints: Num 18:22 and a number of verses are in the hub through the Hebrew (חֵטְא "sin") while the Berean says "guilt", "punishment", "offenses" or "purify". The hub cannot say, per verse, "the original has sin here; the English does not". The sense rule filters on MACULA's gloss. I could not count how many hub verses lack the word "sin" in the Berean; the "mark findings in the verse" asterisk would cover it if the site wants that.
3. A verse placed under a row of one form but containing the other form's word: verb-form verses in noun-form rows (Ezek 18:4 and 18:20 in row 4, John 9:2-3) also show under the verb form's More; noun-form verses in verb rows (1 John 1:8 and 3:9, Prov 20:9) under the noun form's More. A "placed anywhere" test for More would clear this.
4. A condition on the causative stem (הֶחֱטִיא "caused to sin"): rows 16 and 24 are built on Jeroboam's name in the verse because MACULA's lemma for the causative is the same חָטָא. A `stem` condition would let one row say "caused to sin" without the name.
5. Ranking of examples in a pick row: `lead` works; the rest are in the order given (I gave Bible order after the lead).
6. A server note (not the builder): `curl http://localhost:8012/api/verse?ref=Lev.6.3` shows the Berean's Lev 6:3 text over the Hebrew word strip of Hebrew Lev 6:3 (the priest's linen robe, which is the Berean's 6:10). The Berean's Lev 5:20-26 is the Hebrew's 6:1-7; the strip is not shifted. It does not touch the hub, but Lev 6:2-4 (row 23) show a mismatched original on the verse card.

## Other notes

- The Aramaic words h2408 and h2409 were added as nouns (Dan 4:27 "break away from your sins", Ezra 6:17 a sin offering).
- `sin.json`'s `_about`, `_words_why`, `_sense_why`, `_own_words_why` and each row's `_why` record these decisions.
- `leads` are cards (iniquity, transgression, forgiveness, repentance, sacrifice, law, death, righteousness, jesus, grace); no door is a missing card.
