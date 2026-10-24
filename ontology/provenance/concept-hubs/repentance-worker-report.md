# Repentance hub: report

Spec: `ontology/concept-hubs/repentance.json` (`shown: false`). Built to `out/concept-hubs/repentance.json`. 4 builds. 0 cards missing.

## Words (verses in the concept's sense / verses of another sense)

| word | uses | other sense | how it counts |
|---|---|---|---|
| μετανοέω (verb) | 32 | 0 | all |
| μετάνοια (noun) | 22 | 0 | all |
| שׁוּב (verb) | 114 | 839 | the few where MACULA glosses 'repent' or 'relent', plus the rest named by hand (`sense_keep`, each with the Berean words): turning to God or from sin only |
| ἐπιστρέφω (verb) | 18 | 17 | by hand only (turn to God / from sin / back to God); 'turn around', 'return home' dropped |
| μεταμέλομαι (verb) | 5 | 0 | its own row, named as another word (regret, change of mind) |
| נָחַם (verb) | 32 | 68 | 'regret / relent / change mind / sorry / repent' only; 'comfort' (62) dropped |
| ἐπιστροφή (noun), שׁוּבָה (noun, Isa 30:15), ἀμετανόητος (adjective, Rom 2:5) | 1 each | 0 | all |

`others` ("Other words translated 'repent'") came out empty: no other word is rendered 'repent' often enough. תְּשׁוּבָה (h8666, 8 uses) is left out on purpose (it is 'answer', 'the spring', 'return' to Ramah).

## Rows after consolidation (25: 16 verb, 8 noun, 1 adjective, each form's catch-all counted; was 30)

Verb ("Who turns, who repents, and to whom"), 190 verses:
1. The call: repent, turn, return, 36 (pick)
2. Turn to the LORD, to God, 60 (pick)
3. "Turned to the Lord", to the Shepherd, 4 (pick; the page does not say which person)
4. Turn from wickedness, sin, idols, deeds; the repentant ones, 53 (pick)
5. Turn, and be forgiven, healed, saved, live, 26 (rule: in_verse)
6. Repent and be baptized, 1 (rule: Acts 2:38)
7. Repent and believe, 4 (pick)
8. One sinner repents: joy in heaven; a brother repents, forgive him, 4 (pick)
9. They did not repent, would not return, 30 (pick)
10. Unless you repent, if one does not repent, 8 (pick)
11. Nineveh repented; Tyre and Sidon would have, 6 (pick)
12. Turning others back, 10 (pick)
13. The LORD relents, regrets (נָחַם), 22 (pick)
14. The LORD does not relent or change His mind, 7 (pick)
15. Regret, remorse, a change of mind (נָחַם and μεταμέλομαι), 7 (pick)
16. Every other use: turn, return, repent, 9 (fallback: Isa 57:6, Luke 16:30, Jer 34:15, Luke 22:32, Neh 9:29, Prov 1:23, Ps 119:59, Ps 78:34, Zech 1:6)

Noun ("What the text says of repentance"), 24 verses: A baptism of repentance 5; Repentance and forgiveness of sins 4; Repentance and faith 3; God grants repentance; kindness leads to it 5; Fruit and deeds in keeping with repentance 4; Repentance, salvation and life; godly sorrow 4; No ground for repentance, restored to repentance 2; Every other use: called to repentance, conversion (ἐπιστροφή) 3.
Adjective: Unrepentant 1 (Rom 2:5).

### What merged into what (consolidation, 30 to 25)

- "The repentant: those who turn from transgression" (Isa 1:27, 59:20) into "Turn from wickedness, sin, idols, deeds" (label now ends "; the repentant ones"). Isa 59:20 was already in both; Isa 1:27 'her repentant ones' is added at the head of the pick list.
- "Joy over one sinner who repents" (Luke 15:7, 15:10) and "A brother repents, and forgiveness" (Luke 17:3-4) into one row. The no-side note on whether forgiveness waits for repenting is kept.
- "A people turns, and the LORD relents" (Jer 18:8, 26:3, Joel 2:13, Jonah 3:10) into "The LORD relents, regrets": all four were already in it; the note now names them. "The LORD does not relent" stays beside it, with its 1 Samuel 15 note.
- "Godly sorrow and repentance" (2 Cor 7:9-10) and "Repentance, salvation and life" (Isa 30:15, Acts 11:18, 2 Cor 7:10) into "Repentance, salvation and life; godly sorrow" (pick of the four verses; 2 Cor 7:10 was in both).
- "Sinners called to repentance" (Luke 5:32, 15:7) dissolved into the noun catch-all, now labelled "Every other use: called to repentance, conversion (ἐπιστροφή)" (3 verses: Luke 5:32, 15:7, Acts 15:3). Isa 30:15 (שׁוּבָה) moved out of the catch-all into the salvation row.
- Kept apart on purpose: "Repent and be baptized" (1 verse), the baptism / forgiveness / faith rows with their no-side notes, "No ground for repentance" (Heb 6:6 note), the divine-person rows ("Turn to the LORD, to God", "Turned to the Lord", "God grants repentance"), and the relents / does not relent pair.
- Nothing lost: the coverage check (212 of 212 verses placed, 0 under "More") was re-run on the final build; Matt 3:2, Mark 1:15 and Ezek 33:14 are still in rows 1 and 4 (and Mark 1:15 in 7).

Coverage check: all 212 verses the words count as this sense sit in at least one row (0 under "More").

## Wrong turns (kept so they are not re-proposed)

- **Row 1 by the verb's mood (`stance: command`)**: took Exod 32:12 (Moses asking the LORD to turn) and Lam 5:21 / Jer 31:18 ("Restore us ... that we may return", a plea to the LORD), and missed Matt 3:2, 4:17, Mark 1:15, 6:12, because `out/frames.jsonl.gz` has no entry for them. Now by hand.
- **Row 4 by evil words in the verse**: filled with the LORD's own relenting "from the calamity" (Exod 32:14, 2 Sam 24:16, 1 Chr 21:15, Jer 26:13, 26:19, 42:10, Jonah 4:2). רָעָה is "disaster" there, not sin. It also missed Ezek 33:14 and Isa 1:27 (no frames entry). Now by hand.
- **"Repent and believe" by `πίστις` in the verse**: took Luke 22:32 ("that your faith will not fail. And when you have turned back"). Now by hand.
- **"Repentance and forgiveness" by ἀφίημι**: took Heb 6:1, where ἀφίημι is "leave the elementary teachings" (the panel's forgiveness worry, same word). `not_verses`, with the reason.
- **Hosea 14**: the builder files MACULA's Hos 14:3 ("Take words with you and return to the LORD") at the Berean's 14:3, whose text is "Assyria will not save us". `moves` sends it to 14:2.
- **Matt 21:29-30**: the Greek text MACULA follows orders the two sons the other way, so μεταμεληθείς is at its 21:30; the Berean prints "changed his mind" at 21:29. `moves`.

## 16-verse sample (read in the Berean text from the server): 18 of 18 show their row

Deut 30:10 (turn to God) pass; Jer 15:19 (turn to the LORD) pass; Acts 26:18 (turn from darkness / to God / turning others) pass; Dan 9:13 (turn from iniquities) pass; Ezek 33:14 (turns from his sin) pass; Isa 19:22 (turn to the LORD, healed) pass; Jas 5:20 (turns a sinner, saved) pass; Luke 17:4 (brother repents, forgive) pass; Hos 14:2 (call; checks the move) pass; Rev 9:20 (did not repent) pass; Matt 21:29 (checks the move; "changed his mind", so the regret row's label was widened from "grief" to "remorse, a change of mind") pass after the label fix; 1 Sam 15:35 (LORD regretted) pass; Ps 110:4 (will not change His mind) pass; Heb 6:6 (restored to repentance) pass; Isa 30:15 (By repentance and rest) pass; 2 Pet 3:9 (everyone to come to repentance) pass; plus Isa 49:5 (bring Jacob back to Him) pass and Jer 8:6 (No one repents of his wickedness) pass.
(Sample taken on the 30-row build; after the consolidation the four examples of every merged row were re-read in the Berean text and all show their new label: Turn from wickedness ... the repentant ones, Isa 1:27 included but not among the four shown; One sinner repents / a brother repents; The LORD relents; Repentance, salvation and life; godly sorrow; Every other use: called to repentance, conversion.) Besides the sample, every verse of the picked rows was read in the Berean text (from the same server) while the picks were made.

## Contested points the review panel should read

1. **Verb rows 5 "Turn, and be forgiven, healed, saved, live", 6 "Repent and be baptized", 7 "Repent and believe"; nouns "A baptism of repentance", "Repentance and forgiveness of sins", "Repentance and faith".** Acts 2:38, Luke 3:3, Mark 1:4, Acts 5:31, 19:4, 20:21, Luke 24:47, Mark 1:15. Traditions: baptismal regeneration (Catholic, Orthodox, Lutheran, Churches of Christ), repentance as a prior condition (Baptist / free church, Reformed, Wesleyan), sacramental penance (Catholic, Orthodox). A verse sits in every row it fits (`match: all`); each row carries a note that the page takes no side; no row orders the three. Judge: does placing "Repent and be baptized" in a row of one verse read as singling Acts 2:38 out? It is there because the panel asked for the sentence to stay as written.
2. **Verb row 8 "One sinner repents: joy in heaven; a brother repents, forgive him" (Luke 15:7, 15:10, 17:3-4).** Whether forgiveness is conditional on repenting; the forgiveness hub meets the same verses.
3. **Noun row "God grants repentance; kindness leads to it" (Acts 5:31, 11:18, 2 Tim 2:25, Rom 2:4, 2 Pet 3:9).** Reformed / Lutheran (God's gift) against Wesleyan / Baptist (a response to God's kindness, "everyone to come to repentance"). Five verses together in one row with a note. Judge whether one row with "grants" and "leads to" reads as two views set side by side or as one view; the alternative is two rows.
4. **Noun row "No ground for repentance, restored to repentance" (Heb 6:6, 12:17).** Whether one who has fallen away can be restored (Reformed, Wesleyan, Catholic, Orthodox differ). Note says the page takes no side.
5. **Noun row "Fruit and deeds in keeping with repentance" (Matt 3:8, Luke 3:8, Acts 26:20, Heb 6:1 "repentance from dead works").** Faith and works. Heb 6:1 sits here and in "Repentance and faith". Note says no side.
6. **Verb rows 13 and 14: the LORD relents / does not relent** (Gen 6:6, Exod 32:14, 1 Sam 15:11, 35, Jer 18, Jonah 3:10 against Num 23:19, 1 Sam 15:29, Ps 110:4, Heb 7:21). Open theism, classical theism, Jewish readers. Named as a different word and sense (נָחַם, not שׁוּב), set side by side, with a note that 1 Sam 15 has both and the page does not reconcile them. Judge: is "The LORD relents, regrets" fair to classical readers who read it as how it appears to us? The label is the Berean's own words.
7. **Verb row 3 "Turned to the Lord", to the Shepherd** (Acts 9:35, 11:21, 2 Cor 3:16, 1 Pet 2:25). The text says "the Lord" and "the Shepherd and Overseer"; readers take them of Jesus or of the Father; the note says the page does not choose, as righteousness's "He is righteous". Row 2 holds only verses that name the LORD, God, the Most High or the Almighty, or the LORD speaking, or a prayer addressed to Him.
8. **Verb row 10 "Unless you repent, if one does not repent"** (Luke 13:3, 5, Rev 2:5, 16, 22, Ps 7:12, Ezek 3:19, 33:9). Word-for-word warnings; no verdict on what "perish" is (annihilation / eternal punishment). The _why says the page does not generalize.
9. **Verb row 12 "Turning others back"** includes Isa 49:5 ("to bring Jacob back to Him", the Servant) and Luke 1:16-17. Christian and Jewish readers differ on who the Servant is; the label says nothing of him.
10. **Jewish teshuvah.** The Hebrew שׁוּב rows are limited to turning to God or from sin as the panel asked; a Jewish reader may think verb rows 2 and 4 are right but that the 839 other uses hide that "return" is the root metaphor. The spec's `_about` says why they are not listed.

## Left out on purpose (the panel may want some back)

- שׁוּב of the LORD's anger turning away or not (Ps 85:3, Isa 5:25, 9:12, 12:1, Jer 4:8, 23:20, 30:24): the LORD's side, not a person's repenting; Exod 32:12, Jonah 3:9, Joel 2:14 are kept because the "turn and relent" pair names it.
- Turning away FROM the LORD (Num 14:43, Josh 22:16-29, Jer 3:19, 11:10, 1 Kgs 9:6, Ezek 18:24-26 "a righteous man turns from his righteousness"): the opposite direction. Ezek 18 therefore shows only the wicked man turning.
- The other Hebrew and Greek words for the same act without the root: סוּר "turn aside from evil", הִתְוַדָּה "confess", כָּנַע "humble oneself" (2 Chr 7:14, 33:12), ἐξομολογέομαι, στρέφω (Matt 18:3 "unless you turn").
- Deut 30:8 and Hos 14:4 / Ps 85:8 ("turns away anger", "will not let them return to folly").

## What the builder could not express

1. **A second list for the other uses of שׁוּב.** The panel asked that "the other uses of שׁוּב get their own list". The builder only counts them (`other_sense`: 839 for שׁוּב, 17 for ἐπιστρέφω, 68 for נָחַם). Option needed: `other_uses: true` on a word, listing its dropped verses beside it, as `others` lists other words.
2. **`stance` (and verb-row rules) rest on `out/frames.jsonl.gz`, which has no entry for some μετανοέω verses (Matt 3:2, 4:17, Mark 1:15, 6:12), Ezek 33:14 and Isa 1:27.** A rule row can never reach them; only `pick` can, and `add` needs a frames entry too. Option needed: `add` that does not require `seen_form`, or a fallback for word occurrences with no frame.
3. **A condition "both words in the verse".** `in_verse` is any-of. "Turn (שׁוּב) and the LORD relents (נָחַם)" is a verse with both words; I made it a pick. Option: `in_verse_all`.
4. **`not_agent` on verb rows.** The rule-made "turn from evil" row took the LORD's relenting because the agent could not be excluded.
5. **A verse-level condition on which of two words in the verse is the verb:** Jer 8:6 has נָחַם (repents) and שׁוּב; Jonah 3:10 has both; they sit in rows by pick.
6. **`sense_keep` is per verse, not per word.** A kept verse counts for every word of the concept that stands in it. It did no harm here but it could.
7. **Hosea 14 and Matt 21:29-30** needed `moves`; the builder's chapter table does not carry the Hosea 14 shift.

## Files

- Spec: `<local> Ontology\ontology\concept-hubs\repentance.json`
- Built: `<local> Ontology\out\concept-hubs\repentance.json`

## Panel fixes (review "ship after fixes": 14 fixes plus 3 missing; rebuilt twice; 26 rows)

Final rows: 26 (17 verb including the catch-all, 8 noun including the catch-all, 1 adjective); 221 verses placed, 0 under "More". Every changed row's four shown examples were re-read in the Berean text from the build and show the new label.

Applied, one per panel item:

1. **Isa 6:10, Matt 13:15, Mark 4:12, Acts 28:27 out of "Turn, and be forgiven, healed, saved, live"** (`not_verses`, with reason), into a row of their own, "Lest they turn and be healed (hearts made callous)", with a note: the text says it of this people, the turning is not said to happen, the page does not say why and takes no side on election and hardening. The forgiven row now shows 2 Chr 7:14, Luke 17:3, Jas 5:20, Luke 17:4 first (the panel suggested Ezek 18:23 and Isa 55:7 as leads; I did not set `lead`, since the four shown already fit and a third build was over the limit).
2. **Baptism / faith / forgiveness order.** Verb rows are now: forgiven (first verse 2 Chr 7:14), then two unrelated rows, "Repent and believe; believed and turned" (Mark 1:15), then "Unless you repent" and others, then "Repent and be baptized" (Acts 2:38). Noun rows: "A baptism of repentance" (Matt 3:11), "Repentance granted..." between, "Repentance and forgiveness of sins" (Mark 1:4), "Fruit and deeds" between, "Repentance and faith" (Acts 19:4). Each of the six carries the sentence "These rows are listed in the order of their first verse in the Bible, with other rows between them; the page does not order repentance, baptism, faith and forgiveness."
3. **"Repent and believe" relabelled "Repent and believe; believed and turned"** (Mark 1:15 and Acts 11:21 in the text's own words); note says the page puts neither first.
4. **Matt 21:32 (μεταμέλομαι) removed** from "Repent and believe" and from "They did not repent"; it stays in the regret row, where its word is named.
5. **"One sinner repents ... a brother repents" note rewritten** as the panel gave it, pointing to the forgiveness card for verses on forgiving with no repenting. Kept as one row (the panel's optional split not taken, for the row count).
6. **"God grants repentance; kindness leads to it" relabelled "Repentance granted; God's kindness and patience lead to it"**; note says Acts 5:31 does not say who grants. One row kept.
7. **"Fruit and deeds in keeping with repentance" relabelled "...; repentance from dead works"** (Heb 6:1).
8. **Heb 6 row relabelled "“Impossible ... to be restored to repentance”; “no ground for repentance”"**, Heb 6:4 added and led first so "impossible" is shown as the text has it, note names Esau for Heb 12:17.
9. **Exod 32:12, Joel 2:14, Jonah 3:9 out of "The LORD relents, regrets"** into "Turn and relent: asked of the LORD, hoped for, and done" (the earlier "A people turns" row, restored), whose note says which is asked (Moses), which hoped (“Who knows?”), which done (Jonah 3:10). The relents-row note is shortened as the panel gave it. Label of the relents row widened to "relents, regrets, has compassion" with the missing pity verses (below).
10. **Catch-all relabelled "Every other use: turn, return, repent, relent"**, lead = Luke 16:30, Jer 34:15, Luke 22:32, Zech 1:6, so Isa 57:6 is no longer the first example; its note says Isa 57:6 is the LORD's "Should I relent". (The builder's catch-all `not_verses` and `sense_drop` were not needed.)
11. **שׁוּב framing: partly.** A note on "The call" says that in Hebrew שׁוּב is "turn, return" in most of its 953 uses and that only the turning to God or from sin is gathered here, the rest being on the word's card. The panel's other ask, changing the word line's gloss from "to return: repent" and showing the other-sense count there, is app/UI and not in the spec; the counts are in the build (`other_sense`: 833 after the additions).
12. **"The call" leads with the Hebrew Scriptures** (Ezek 33:11, Joel 2:12, then Mark 1:15, Acts 3:19).
13. **Mal 4:6 added to "Turning others back"** (the Hebrew source of Luke 1:17); versification checked: the build files it at Mal 4:6 with text "he will turn the hearts of the fathers to their children".
14. **Noun section retitled "Where the word “repentance” stands".**

Missing, all three added:
- **Deut 30:8** (Berean "again obey" = שׁוּב "return and obey") by `sense_keep`; it has no row it fits, so it stands in the verb catch-all, whose note says what "again" is.
- **Ezek 3:20, 18:24, 18:26, 33:18** (a righteous man turns from his righteousness) into the warnings row, relabelled "Unless you repent, if one does not repent; a righteous man turns from his righteousness", with a note that the page takes no side on whether it can be lost. This also answers the worker point on Ezek 18.
- **Deut 32:36, Ps 135:14, Judg 2:18** (נָחַם as compassion or pity) into the relents row by `sense_keep`; Judg 2:18 is kept out of the forgiven row by `not_verses` ("saved them" is the judge).

Also: "Nineveh repented; Tyre and Sidon would have" merged into "They did not repent, would not return; ..." to hold the count at 26 (Matt 11:20-21 and Luke 10:13 are one saying). The label now ends with the Nineveh clause. 

Not used: `sense_drop` and `others.add` (nothing needed them; `others` is still empty). Not changed: "does not relent" (the panel found it fair), "Turned to the Lord", "Unless you repent" warnings, "Turning others back" (Isa 49:5 kept).
