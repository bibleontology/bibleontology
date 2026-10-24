# forgiveness hub: report

Spec: `ontology/concept-hubs/forgiveness.json` (`"shown": false`). Built: `out/concept-hubs/forgiveness.json`. Builds run: 4 (first draft; a fix round; the final; the 29-to-24 consolidation). Cards missing: none. Every verse the words stand in is in a row (verb 101, noun 18, adjective 1; "More" is 0 in each).

## Words (the sense rule keeps only verses the Berean/MACULA render forgive, pardon)

| word | kept | dropped as another sense |
|---|---|---|
| סָלַח | 45 | 0 |
| נָשָׂא | 20 | 590 (lift, carry, bear...) |
| סְלִיחָה (noun) | 3 | 0 |
| סַלָּח (adjective) | 1 (Ps 86:5) | 0 |
| ἀφίημι | 37 | 94 (leave, let, permit, forsake, the fever left her...) |
| ἄφεσις | 15 | 1 (Luke 4:18, "deliverance") |

`sense` is `forgiv|forgave|pardon`. The first draft had `forgiv|pardon` and silently dropped Matt 18:27, 18:32 (`forgave his debt`) and Ps 32:5, Ps 85:2 (`forgave`); caught from a gloss dump and fixed (recorded in `_sense_why`).

## Decisions by the brief's rule

- **כָּפַר / כִּפֶּר (atone): not a word of the hub, in `others`.** It is a different word; only 8 of its 94 verses are rendered forgive/pardon (2Chr 30:18, Deut 21:8, Ezek 16:63, Isa 22:14, Jer 18:23, Ps 65:3, 78:38, 79:9). Where it stands beside סָלַח (Lev 4-6, 19:22; Num 15), the row's label ("Atonement made, and he will be forgiven") and note name both words and say the page does not make them one.
- **נָשָׂא: only where rendered forgive** (20 verses; the rest is "bear, lift, carry").
- **ἀφίημι: only where forgive** (the sense rule above).
- **`others` ("Other words translated forgive"), min_n 1:** כִּפֶּר (8), χαρίζομαι (8: Luke 7:42-43, 2 Cor 2:7, 2:10, 12:13, Col 2:13, 3:13, Eph 4:32), כָּסָה (Prov 17:9), נָקָה (Joel 3:21), ἀπολύω (Luke 6:37).

## Rows (counts), after consolidation 2026-10-10: 24 rows (15 verb, 8 noun, 1 adjective); was 29

Verb form (title "Forgiving, and being forgiven"; lead):
1. The LORD, God, the Father forgives: 10 (by hand: verse names him)
2. "He forgives", "I will forgive", "You forgave": 10 (by hand: pronoun-only verses; note)
3. Asked in prayer: forgive: 21
4. Who can forgive sins: 7 (Mark 2:7, 2:10, John 20:23 first, then Luke 5:21, 5:24, Matt 9:6, Luke 7:49)
5. "Your sins are forgiven"; "Blessed are they whose sins are forgiven": 11 (merged: was two rows, 9 + 2)
6. People forgiving people, and asked to: 15 (merged: was "Asked of a person, or told to forgive one another" 13 + "Debts forgiven" 3, Matt 6:12 in both; carries the note that Eph 4:32 and Col 3:13 use χαρίζομαι, shown under other words)
7. Our forgiving, and our Father's: 6
8. Forgiveness, repentance, turning and confessing: 9
9. Forgiveness and faith: 4 (rule: πίστις/πιστεύω in the verse)
10. Atonement made, and he will be forgiven: 12 (Lev 4-6, 19:22; Num 15:25, 15:28)
11. Sinning unintentionally, in ignorance: forgiven: 4 (Num 15:25, 26, 28; Lev 5:18)
12. Forgiving sins, iniquity, transgression, trespass: 51 (rule: the frames' patient)
13. Will not forgive, was not forgiven: 10
14. Blasphemy against the Holy Spirit: 4
15. Every other use: 5 (Ps 25:18, Isa 33:24, Num 30:5, 8, 12; the vow row was folded in here)

Noun form (title "What the text says of forgiveness"):
1. Forgiveness of sins, of trespasses: 12 (rule: ἁμαρτία/παράπτωμα next word; the redemption/salvation row was folded in, its doors and a note came with it)
2. Repentance and forgiveness: 5 (rule)
3. Baptism and forgiveness: 3 (rule: Mark 1:4, Luke 3:3, Acts 2:38)
4. Believing, faith and forgiveness: 2 (rule: Acts 10:43, 26:18)
5. Blood, offering and forgiveness: 4 (rule: αἷμα, προσφορά, θυσία)
6. Forgiveness "in His name", "through Him", "in Him": 6 (by hand)
7. With the LORD there is forgiveness: 3 (by hand: Ps 130:4, Dan 9:9, Neh 9:17; the compassion/grace row was folded in, with its doors and a note)
8. Every other use: 1 (Mark 3:29)

Adjective form: Kind and forgiving: 1 (Ps 86:5).

### What merged into what (29 to 24)
- "Blessed are those whose sins are forgiven" (2) into "Your sins are forgiven" (both are the agentless passive "sins are forgiven"; Ps 32:1 and Rom 4:7 are the first two examples after the two sayings, so the label shows in the four examples).
- "Debts forgiven" (3) into "People forgiving people": Matt 18:27, 18:32 are a master forgiving a servant; Matt 6:12 was already there.
- "The LORD will absolve her of a vow" (3) into "Every other use" (framed, so the catch-all takes them).
- Noun "Forgiveness, redemption and salvation" (4) into "Forgiveness of sins, of trespasses": all four verses were already in it.
- Noun "Forgiveness beside compassion, grace and loving devotion" (3) into "With the LORD there is forgiveness": Dan 9:9 and Neh 9:17 were already there; Eph 1:7 stays in the phrase, blood and name rows.
- Kept apart on purpose: repentance / baptism / faith (verb and noun), "Who can forgive sins", "Our forgiving, and our Father's", the God rows (1, 2), "Will not forgive", "Blasphemy", "Atonement" and "Sinning unintentionally" (Num 15:26 has no word of atonement, so it cannot sit under that label).
- Checks after the rebuild: verb 101/101 verses placed, noun 18/18, adjective 1/1, "More" 0 in each (the frameless Leviticus and Numbers passives are all still in rows 10 and 11). The four examples of every merged row, read in the Berean text, show the label: row 5 (Mark 2:5, Luke 7:48, Ps 32:1, Rom 4:7), row 6 (Matt 18:21, 18:35, Luke 17:3, 17:4), verb catch-all (Num 30:5, Ps 25:18, Isa 33:24, Num 30:8), noun row 1 (Mark 1:4, Luke 1:77, Acts 13:38, Eph 1:7), noun row 7 (Ps 130:4, Dan 9:9, Neh 9:17). Builds for the consolidation: 1.


## The 16-verse sample (read in the Berean text, beyond the first examples)

| verse | row | verdict |
|---|---|---|
| Jer 50:20 | The LORD, God, the Father forgives | pass ("declares the LORD ... I will forgive the remnant") |
| Mark 11:25 | The LORD, God, the Father forgives; Our forgiving, and our Father's | pass |
| Lam 3:42 | "He forgives", "I will forgive", "You forgave" | FAIL: "You have not forgiven" is the opposite. Fixed: removed from that row; it stays under "Will not forgive" (re-read: pass) |
| 2Chr 6:39 | Asked in prayer | pass ("May You forgive Your people") |
| Luke 7:47 | "Your sins are forgiven" | pass, loose: the verse says "her many sins have been forgiven", not the quoted words (the note says "the saying as the text gives it") |
| 1Sam 25:28 | Asked of a person | pass ("Please forgive your servant's offense") |
| Matt 18:35 | Our forgiving, and our Father's (was "...if you forgive, your Father will forgive") | FAIL as first labelled: the verse says "unless you forgive your brother" the Father "will treat" you. Fixed: relabelled "Our forgiving, and our Father's" (re-read: pass) |
| Mark 4:12 | repentance, turning and confessing | pass ("turn and be forgiven") |
| Num 15:26 | Atonement made, and he will be forgiven | FAIL: no word of atonement in the verse. Fixed: moved to the new row "Sinning unintentionally, in ignorance: forgiven" ("unintentionally" is in the verse; re-read: pass) |
| Lev 19:22 | Atonement made | pass |
| Hos 1:6 | Will not forgive | pass |
| Col 1:14 | Forgiveness, redemption and salvation | pass |
| Heb 10:18 | Blood, offering and forgiveness | pass ("an offering for sin is no longer needed") |
| Ps 85:2 | "You forgave" | pass |
| Luke 5:24 | Who can forgive sins | pass |
| Acts 8:22 | repentance, turning and confessing | pass ("Repent ... pray to the Lord. Perhaps He will forgive") |

Also read and passed: Job 7:21, Jer 5:7, 2Kgs 5:18, Luke 17:4, Exod 10:17, Isa 33:24. Tally: 13 of 16 passed on first reading, 3 failed and were fixed; after the rebuild 16 of 16 show their label (Luke 7:47 loosely).
Other fix from reading the output: the 52-verse rule row was first labelled "...forgiven", which contradicted Josh 24:19 and Exod 23:21 ("will not forgive"); relabelled "Forgiving sins, iniquity, transgression, trespass". Acts 5:31 and Matt 26:28 were removed from the "in His name ... in Him" row (the verses say "Him"/"My blood", not the label's phrases; they stand in the repentance, blood and redemption rows). Ps 25:18 is held out of the sins row by `not_verses` because the Berean reads "take away all my sins".

## For the review panel (contested points)

1. **Who can forgive sins** (verb row 4): Mark 2:7, Luke 5:21, Luke 7:49 ("God alone"; "who is this who even forgives sins"), Matt 9:6, Mark 2:10, Luke 5:24 (the Son of Man has authority), John 20:23 (the disciples; priestly absolution for Catholic, Orthodox, some Lutheran readers; Reformed, Baptist, others read it as declaring). Order puts none first. Note says the page takes no side.
2. **Repentance, baptism, faith** (noun rows 2-4, verb rows 8 and 9): Acts 2:38 sits in both the repentance and baptism rows and in "in His name"; Mark 1:4 and Luke 3:3 in repentance and baptism; Acts 10:43 and 26:18 in faith. Each carries the same note. Readers to check: Baptist/free church (forgiveness not through baptism), Catholic, Orthodox, Lutheran, Churches of Christ (baptism for forgiveness), Reformed. Is the order of the rows (repentance, baptism, faith) a priority? It is the order of the phrases in Acts 2:38, and Luke 24:47 puts repentance first; panel to say if it reads as ordering.
3. **Conditionality** (verb rows 7 and 8): "Forgive us as we forgive" (Matt 6:12, Luke 11:4), "if you forgive ... your Father will forgive" (Matt 6:14-15, Mark 11:25), Matt 18:35, and the repentance row (2 Chr 7:14, Isa 55:7, Jer 36:3, 1 John 1:9, Luke 17:3-4, Mark 4:12). The repentance row note names verses that name no repentance (Luke 23:34, Luke 5:20, Ps 25:11) so the row does not read as "forgiveness requires repentance". Panel: does that sentence tilt?
4. **Forgiveness and sacrifice** (verb row 10, noun row 5): Lev 4-6 "make atonement ... and he will be forgiven"; Heb 9:22, Matt 26:28, Eph 1:7, Heb 10:18. The note says the page takes no side on how offering and forgiving relate (penal substitution, sacrifice as cleansing, Eucharistic readings). Jewish reader: the Hebrew pair is kept as two words.
5. **Blasphemy against the Holy Spirit** (verb row 14; Mark 3:29 is a noun-form "Every other use"): shown with the verses that say every other sin and a word against the Son of Man are forgiven. Note says readers take what it is differently. Hard verse, kept.
6. **Divine persons by hand:** row 1 names only verses where the verse itself says LORD/God/Father; Acts 8:22 ("pray to the Lord ... He will forgive") is left out of it because "the Lord" there is read of Jesus or God. Row 2 holds "He/I/You" verses with a note (1 John 1:9 "He": Father or Christ). Noun row 6 is "in His name / through Him / in Him": only Acts 2:38 and 13:38 name Jesus in the verse; the others are pronouns, so the note says the passage around them names Christ (Luke 24:46, Acts 10:36, Eph 1:5, Col 1:13) and the page does not choose. Panel to say whether that row should stay.
7. **χαρίζομαι is a different word, and it is where "people forgiving one another" is clearest** (Eph 4:32 "forgiving each other just as in Christ God forgave you", Col 3:13, Col 2:13 "He forgave us all our trespasses", 2 Cor 2:7-10). By the brief's rule it is in "Other words translated forgive" at the bottom, not in the rows. A reader looking at "God forgiving and people forgiving one another" will find the Gospels (ἀφίημι) in the rows and the letters' clearest verses only in the "other words" section. Doug/panel could decide whether a pointer from the people-forgiving rows to that section is wanted.
8. **Hebrew סָלַח is never said of a person** (45 of 45 verses: the LORD, or passive). People are asked to forgive in the Hebrew with נָשָׂא (Gen 50:17; Exod 10:17; 1 Sam 15:25; 25:28). Stated in the notes of verb rows 1 and 6. A Jewish reader will want to confirm "in none of its 45 verses ... said of a person" is the claim; it was read verse by verse.
9. **Verses where the Berean says something other than forgive:** Ps 25:18 ("take away all my sins"; MACULA gloss forgive; kept under Every other use), Num 30:5, 8, 12 ("absolve her" of a vow; separate row, not forgiveness of sin), Prov 17:9 / Joel 3:21 (other words, not in rows).
10. **Not included, on purpose:** Ps 51, Isa 1:18, Mic 7 as a whole, Rom 4 as a whole, Acts 22:16 (no forgiveness word); the Septuagint's use of ἀφίημι for the Jubilee (Lev 25, ἄφεσις "release") is outside the sense rule.

## What the builder could not express

- **A verse where the concept's verb occurs but has no frame** (all the Hebrew passives: Lev 4-6, Lev 19:22, Num 15, Ps 32:1) is never "seen" in the verb form, so no rule row and no "Every other use" row can take it and it would vanish silently, not even into "More". I covered all of them by `pick` and checked completeness against my own dump (101 = 45 + 20 + 37 - 1 for Num 14:19). Option wanted: add every verse the verb word stands in to `seen_form`, so unplaced ones show up in "More" or the fallback.
- **A row condition on negation** ("will not forgive"; Josh 24:19, Deut 29:20): the frames record stance (command/projection/report) but not polarity, so the "Will not forgive" and "Our forgiving, and our Father's" rows are by hand.
- **A different word shown in a row, marked as different** (a `also` list of other-word verses, rendered with a "a different word" mark): would let χαρίζομαι's verses appear in the people-forgiving row without equating them (point 7).
- **A per-example note** (Ps 25:18: "the Berean reads 'take away'; the Hebrew verb is the one the lexicon glosses forgive"): I used `not_verses` with a reason and left the verse under "Every other use"; the reason is not shown to a reader.
- **Verbs in other forms can't be placed by a noun-form rule and vice versa**: "Forgiveness and faith" and the repentance row had to be written twice (once in the verb form, once in the noun form) so each form's section is complete; the page might prefer one row spanning both.

## Panel fixes (2026-10-10, "ship after fixes": 10 fixes + 3 missing; 2 builds-worth of budget, 1 used)

Row count stays 24 (15 verb, 8 noun, 1 adjective); every verse still placed (verb 101/101, noun 18/18, adjective 1/1, "More" 0). Applied 13 of 13 (two of them only partly, because of the builder: see "Not fully done"). Spec edits are in `ontology/concept-hubs/forgiveness.json`; each carries its reason in `_why`.

| # | panel item | what was done |
|---|---|---|
| 1 | "Other words translated forgive": examples do not say forgive | Retitled "Other words the lexicon glosses “forgive”" (the gloss rule reads MACULA, not the Berean). `others.exclude` now drops כָּסָה (Prov 17:9, Berean "conceals an offense") and נָקָה (Joel 3:21, Berean "avenge"). The Atonement row's note now says the Berean prints "atone", "atoned for", "provide atonement" for the same כִּפֶּר (Ps 65:3, 79:9, Deut 21:8, 2 Chr 30:18) and "forgave" only at Ps 78:38, and that the page does not make the words one. Section now: כִּפֶּר 8, χαρίζομαι 8, ἀπολύω 1 |
| 2 | χαρίζομαι pointer on "Our forgiving, and our Father's"; Luke 6:37 | Sentence added to that row's note (Eph 4:32, Col 3:13 = χαρίζομαι; Luke 6:37 = ἀπολύω; listed under the other words, kept out of the rows because they are different words); the "People forgiving people" note names Luke 6:37 too. The note's "or ours on theirs repenting (Luke 17:3-4)" reworded as the panel's point 3 asked ("whether our forgiving depends on the other's repenting is the question of Luke 17:3-4, in the row above") |
| 3 | order contradicts "not before them" | Both notes now say the baptism, faith and repentance rows are in the alphabetical order of their labels and carry no ranking, and the order really is so: noun form Baptism, Believing/faith, Repentance; verb form "Forgiveness and faith" then "Forgiveness, repentance, ..." (the verb faith row moved above the repentance row). The "not before them" sentences are gone |
| 4 | Baptism row: John's baptism; Acts 22:16 | Note says Mark 1:4 and Luke 3:3 are the baptism John preached and Acts 2:38 is Peter's, at Pentecost; and quotes Acts 22:16 (Berean) as joining baptism and washing away of sins with no word for forgiveness, so not in this hub. I checked the baptism card (`/api/entity?id=baptism`): Acts 22:16 is NOT on it, so the note does not claim it is anywhere else; for Doug/the coordinator: add it to the baptism card, or the note stands as "not in this hub" |
| 5 | "Will not forgive": John 20:23, Isa 2:9 | Note added: most are the LORD's refusal; Matt 6:15 sets it beside our not forgiving; Isa 2:9 is a plea that He not forgive; John 20:23 is said to the disciples and is set with Mark 2:7 and Mark 2:10 in "Who can forgive sins", where the page takes no side. John 20:23 stays in the row |
| 6 | Verb "Every other use": Num 30, Ps 25:18 | Note added (Num 30:5, 8, 12 a vow, not a sin; Ps 25:18 the Berean reads "take away all my sins"); lead is now Isa 33:24, Num 30:5, Ps 25:18, Num 30:8 |
| 7 | Unintentional row | Note added: the four verses say unintentional or in ignorance; Lev 6:2-7 (atonement row above) has the same forgiving words for deceit, extortion and false swearing; Num 15:30-31 speaks of the one who sins defiantly, "cut off", with no word for forgiveness; "the page does not say what the text leaves unsaid". The Atonement row's note also now says Lev 6:2-7 is wrongs done knowingly |
| 8 | Merged row: Psalm 32:1 first | Label "“Blessed are they whose sins are forgiven”; “Your sins are forgiven”"; picks start Ps 32:1, Mark 2:5, Luke 7:48, Rom 4:7; the note names the psalm first; the first doors are blessed_is_the_man |
| 9 | Hebrew noun row not last | "With the LORD there is forgiveness" is now the first noun row, then "Forgiveness of sins, of trespasses" (and the Dan 9:9 / Neh 9:17 compassion-and-grace note stays) |
| 10 | Mark 3:29 note | Noun "Every other use" now has the note: see "Blasphemy against the Holy Spirit" in the verb form (Mark 3:28, Matt 12:31-32, Luke 12:10 stand with it); readers take what it is differently, the page takes no side |
| M1 | Acts 22:16 pointer | Done in the baptism note (see 4) |
| M2 | Hebrew images of sin taken away | A sentence on the first noun row ("With the LORD there is forgiveness"): the Hebrew speaks of sin taken away in other words with no word for forgiveness, not in the hub: Isa 43:25 "blots out your transgressions", Ps 103:12 "As far as the east is from the west...", Mic 7:19 "cast out all our sins into the depths of the sea", Ps 51:1-2 "blot out my transgressions" / "Wash me clean of my iniquity" (all Berean). It points to no card, because I did not confirm any other page carries them |
| M3 | Luke 4:18 | A sentence on the noun "Every other use" note: the same noun ἄφεσις is also "release", Luke 4:18 ("to proclaim liberty to the captives ... to release the oppressed") is the one of its 16 verses where it is not forgiveness and is not counted. No row, no verse added |

Also from the panel's worker points: "Who can forgive sins" note now says the page "ranks none above another" (the panel found "puts none first" loose since Mark 2:7 is first).

Examples re-read in the Berean after the rebuild for every changed row: merged blessed/sins row (Ps 32:1, Mark 2:5, Luke 7:48, Rom 4:7: show the label); Will not forgive (Josh 24:19, Deut 29:20, 2 Kgs 24:4, Exod 23:21); verb Every other use (Isa 33:24, Num 30:5, Ps 25:18, Num 30:8); noun With the LORD (Ps 130:4, Dan 9:9, Neh 9:17); noun Every other use (Mark 3:29); baptism (Acts 2:38, Luke 3:3, Mark 1:4); faith and repentance noun rows and the verb faith/repentance rows unchanged in their verses. Lev 6:2-7, Num 15:30-31, Isa 43:25, Ps 103:12, Mic 7:19, Ps 51:1-2, Luke 4:18, Acts 22:16, Luke 6:37 and Ps 78:38 were read in the Berean before being named in a note.

### Builder limits: resolved by `others.add` (2026-10-10, one more build)
- **Choosing the examples of an `others` entry, and a note under the word: now done with `others.add`.** כִּפֶּר now leads with Ps 78:38 ("He forgave their iniquity") then Ps 79:9 ("atone for our sins"), with a note under the word: it means "make atonement", a different word from סָלַח; the Berean prints "forgave" only at Ps 78:38 of the eight verses the lexicon glosses forgive, and "atone", "atoned for", "provide atonement" elsewhere (Ps 65:3, 79:9, Deut 21:8, 2 Chr 30:18). χαρίζομαι now leads with Eph 4:32 and Col 3:13 ("forgiving each other just as in Christ God forgave you"; "Forgive as the Lord forgave you"), and Col 2:13 and 2 Cor 2:10 follow in the list; its note says the Berean prints "forgive" in these verses and "granted", "freely give" elsewhere (Phil 1:29, Rom 8:32, Gal 3:18, read in the Berean). ἀπολύω shows Luke 6:37. The Deut 21:8 / 2 Chr 30:18 and Luke 7:42 / 2 Cor 12:13 examples are no longer what a reader sees first. Re-read after the build: Ps 78:38, Ps 79:9, Eph 4:32, Col 3:13, Luke 6:37 show their word's sense as the notes say. Still 24 rows; all verses placed (verb 101, noun 18, adjective 1, "More" 0).
- **Filtering `others` by the Berean's English: still not possible**, and no longer needed: the stopgaps stand (`exclude` of כָּסָה and נָקָה, the retitle) and the notes now say what the Berean prints. A verse-level filter would still be cleaner (it would drop the four "atone" verses of כִּפֶּר from a section on forgiveness), but the section no longer misleads.
- **`sense_drop` and the catch-all's own `not_verses`: no workaround needed them.** `sense_drop` is for a verse the gloss passes where the word has another sense; here the sense rule already drops those (ἀφίημι "left", ἄφεσις Luke 4:18). The Ps 25:18 workaround (`not_verses` on the sins row, so it falls to "Every other use") still stands because the row that took it is a rule row, not the catch-all.
