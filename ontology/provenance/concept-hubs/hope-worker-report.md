# Hope hub -- report

Spec: `ontology/concept-hubs/hope.json` (`"shown": false`). Built output: `out/concept-hubs/hope.json`. Builds run: 5 in all (3 before, 2 after the coordinator's builder update). Cards missing: none.

Result (latest: 26 rows after the panel's fixes, see the last section): **24 rows after consolidation (16 noun, 8 verb; was 39); 16-verse sample 15 pass, 1 borderline (Eph 4:4); 12 further verses read, 2 failed and were fixed. Update 2026-10-10: קָוָה is now a hub word (`forms`), seven Berean-'hope' verses are kept by `sense_keep`; the second round's examples were rechecked (below).**

## Words

| word | form | uses in sense | other sense (dropped) |
|---|---|---|---|
| ἐλπίς | noun | 48 | 0 |
| ἐλπίζω | verb | 31 | 0 |
| תִּקְוָה | noun | 31 | 2 ('cord', Josh 2:18, 2:21) |
| מִקְוֶה | noun | 5 | 3 ('reservoirs', 'gathering', 'collecting': Exod 7:19, Gen 1:10, Lev 11:36) |
| תּוֹחֶלֶת | noun | 6 | 0 |
| מַבָּט | noun | 3 | 0 |
| שֵׂבֶר | noun | 2 | 0 |
| יָחַל | verb | 23 | 19 ('wait', 'waited': 1 Sam 13:8, Gen 8:12, ...); 4 of the 23 are `sense_keep` |
| קָוָה | verb (`forms`) | 17 | 28 ('wait', 'gathered', 'looked'); 3 of the 17 are `sense_keep` |

`sense` = `hop|expect|relied on`. 'expect' is Prov 10:28, 11:23 ('expectation') and Luke 6:34; 'relied on' only rescues Isa 20:6 (מַבָּט, Berean 'our source of hope', beside Isa 20:5).

**קָוָה (h6960)** is a hub word again, typed `"forms": {"h6960": "verb"}` (the lexicon has no entry for it, so the builder had called it a noun). Its verse count is 17: 'hope', 'hoped', 'expected' (Isa 5:2, 5:4, 64:3) and three kept by `sense_keep`.

**`sense_keep`** (each checked in the Berean via /api/verse; all seven print the word "hope"): Isa 42:4, Isa 51:5, Job 6:11, Ps 31:24 (יָחַל) and Isa 49:23, Ps 37:9, Ps 69:6 (קָוָה). Each carries its reason in the spec. Ps 39:7 was already in the hub via תּוֹחֶלֶת.

## Other words translated "hope" (`others`)

- שָׂבַר, 3: Esth 9:1, Isa 38:18, Ps 119:166.
- בִּטָּחוֹן, 1: Eccl 9:4 ('There is hope, however, for anyone among the living').
- (קָוָה is no longer here: it is a hub word.)
- Excluded gloss stray: h4993 (Mattithiah), as in love. Strays below threshold are dropped (מִבְטָח 1 of 15, שֶׁקֶר 1 of 112).

## Rows -- consolidated 2026-10-10: 39 -> 24 (brief rule 8)

The 39-row spec is saved as `hubs/hope_spec_39rows.json` (its build as `hope_out_39rows.json`). Verses placed before and after are the same (noun 93, verb 70; "More" 0): nothing dropped, only regrouped. A verse still sits in every row it fits (`match: all`). Contested rows (Israel, glory, gospel, resurrection), the divine-name picks (Spirit, Christ, the LORD, God Greek, Christ verb) and their notes are kept as they were.

Noun (lead), 16 rows:

| row | n | from (before) |
|---|---|---|
| Hope with faith and love | 12 | Hope and faith (10) + Hope and love (5) |
| The Holy Spirit named with hope (pick) | 3 | same |
| Christ named with hope (pick) | 10 | same |
| The LORD, God and hope (Hebrew, pick) | 8 | same |
| God and hope (Greek, pick) | 9 | same |
| Hope and Israel | 6 | same |
| The hope of glory | 2 | same |
| The hope of the gospel, the calling, righteousness, salvation, eternal life; hope and being saved, the Savior | 12 | gospel (7) + Hope and salvation, the Savior (6); the Savior/being-saved verses added by hand |
| Hope and the resurrection | 3 | same |
| Hope, the promise and the word | 7 | same |
| Hope with endurance, suffering, comfort, joy and peace | 11 | endurance (7) + joy/peace (5) |
| Hope with confidence and boldness, held fast, and shame | 13 | confidence (7) + Hold fast (3) + Hope and shame (5) |
| There is hope; hope and a future | 10 | There is hope (7) + Hope and the future (4) |
| The hope of the righteous, the wicked, the godless, the poor and needy | 8 | righteous/wicked (6) + poor (2) |
| Hope lost, perished, uprooted, withered; without hope | 15 | Hope lost (11) + Without hope (4, added by hand) |
| Every other use | 12 | catch-all (10) + the ordinary-sense row of two (Acts 16:19, 1 Cor 9:10) |

Verb, 8 rows:

| row | n | from (before) |
|---|---|---|
| Hope in the LORD, in God (Hebrew, pick) | 15 | same; now holds 'O my soul, put your hope in God' (3) and 'Hope and the LORD's loving devotion' (4) by their verses |
| Set hope on God (Greek, pick) | 4 | same |
| Christ named with hope (pick) | 3 | same |
| Hope in the word, the judgments | 6 | same |
| Hope and Israel; the nations, the islands will put their hope | 9 | Hope and Israel (5) + The nations, the islands (4) |
| Hope for what is not yet seen; hoped for one thing, and another came | 9 | the two picked rows (3 + 6) |
| Hoping to come, to see, to send, to speak; hoping you will understand | 11 | ordinary-sense rule (8) + 'I hope you will understand' (3, added by hand) |
| Every other use | 18 | catch-all (16) + 'Hope of repayment, a bribe' (2) |

Merged labels keep to the text's own words; each merged row's `_why` in the spec names the rows it came from. Two merges to flag for the panel: the gospel row now also holds the 'Savior / being saved' verses (Jer 14:8, Acts 27:20, 1 Tim 1:1, Rom 8:24, Titus 2:13) -- hand-added, so their label is the tail of the row's title; and 'Hope and Israel; the nations ...' puts the hope-of-Israel verses beside the nations-put-their-hope verses (Isa 42:4, 51:5, Matt 12:21, Rom 15:12) under one note that the page takes no side.

First examples rechecked after the merge (leads set so each row opens on a verse that shows its label): faith/love (1 Cor 13:13, 1 Thess 1:3, Rom 5:5, 1 Pet 1:21), gospel (Col 1:23, 1 Thess 5:8, Titus 3:7, Rom 8:24), endurance/joy (Rom 5:4, 12:12, 15:4, 15:13), confidence/shame (Heb 3:6, Rom 5:5, Phil 1:20, Isa 20:5), there is hope/future (Job 14:7, Jer 31:17, Jer 29:11, Prov 24:14), whose hope (Prov 10:28, 11:23, Job 8:13, Job 5:16), lost/without (Ezek 37:11, Job 14:19, Acts 27:20, Eph 2:12), ordinary (Rom 15:24, 1 Cor 16:7, 2 Cor 1:13, Phil 2:23), Israel/nations (Ps 130:7, Luke 24:21, Isa 42:4, Matt 12:21): all 36 shown examples read as pass.

## The 16-verse sample (read in the Berean text; taken when the spec had 39 rows -- the row names are the pre-merge ones, each now inside the merged row listed above)

| # | verse | row | verdict |
|---|---|---|---|
| 1 | 2 Cor 10:15 | Hope and faith | pass ('we hope that as your faith increases') |
| 2 | 2 Thess 2:16 | Hope and love | pass |
| 3 | Heb 3:6 | Christ named with hope | pass |
| 4 | Heb 7:19 | God and hope | pass ('a better hope ... draw near to God') |
| 5 | Ezek 37:11 | Hope and Israel | pass ('the whole house of Israel ... our hope has perished') |
| 6 | Eph 4:4 | hope of the gospel / calling ... | borderline: the Berean says 'called to one hope when you were called'; the Greek is 'one hope of your calling' (κλῆσις). Kept: the original has the phrase |
| 7 | Col 1:5 | Hope, the promise and the word | pass ('word of truth') |
| 8 | Rom 8:24 | Hope and salvation | pass ('we were saved') |
| 9 | Heb 6:18 | endurance, comfort, encouragement | pass ('strongly encouraged') |
| 10 | Acts 2:26 | joy, gladness and peace | pass ('my heart is glad') |
| 11 | Job 4:6 | boldness, confidence | pass ('your confidence ... your hope') |
| 12 | Heb 10:23 | Hold fast to hope | pass |
| 13 | Ruth 1:12 | There is hope | pass |
| 14 | Prov 24:14 | Hope and the future | pass |
| 15 | Job 11:20 | hope of the wicked | pass ('the eyes of the wicked will fail ... hope for their last breath') |
| 16 | Zech 9:5 | Hope lost, withered | pass ('her hope will wither') |

Further verses read (12): Ps 119:49, Ps 33:18, Rom 15:24, Luke 6:34, 2 Cor 5:11, 1 Pet 1:3, Rom 5:2, Jer 14:22, Phil 2:19, Ps 119:116, Isa 59:9 -- all pass. **Two failed and were fixed:**
- Isa 5:2 under "Hoped for one thing, and another came": the Berean reads 'He waited for the vineyard to yield good grapes' (MACULA gloss 'expected'). Removed from the row's picks; Isa 5:4 ('when I expected sweet grapes') stays. Isa 5:2 now appears nowhere in the hub (its gloss is 'expected', not 'hope', so `others` does not list it either).
- Ps 119:81 under "Hope in the word": the Berean reads 'I wait for Your word'. `not_verses` (with reason); it stands under "Every other use".

Versification, as the coordinator asked: MACULA Ps 33:22 is filed by the builder under Ps 34:1 and MACULA Isa 64:2 is the Berean's 64:3; both are in `moves` and both now show the Berean's hope/expect word ('as we put our hope in You', 'that we did not expect').

## Recheck after the builder update (build 5)

Examples read: Isa 42:4 and 51:5 (nations/islands row: pass), Ps 31:24, 37:9, 69:6, Isa 49:23 (hope in the LORD: pass, each names the LORD), Job 6:11 ('that I should still hope?', catch-all: pass), Isa 8:17, 64:3, Jer 13:16, Job 6:19, Ps 56:6 (catch-all, no label to fail; Isa 8:17's Berean reads 'wait ... trust'), Isa 5:2 ('waited', catch-all only). **One new failure, fixed:** the rule on מִשְׁפָּט in "Hope in the word, the judgments" caught Isa 42:4 ('establish justice'), Isa 59:9, 59:11 ('we hope for justice') -- 'justice' is not God's judgments; `not_verses` with reasons. Ps 69:6 ('O God of Israel') now falls in "Hope and Israel" by the Israel-in-verse rule; the label is 'Hope and Israel', which the verse shows, but it is the God-of-Israel address, not 'the hope of Israel' -- a panel point. The hand-placed picks I kept: Jer 14:22 (divine-name row, by rule 4) and the "Hoped for one thing" row (a pattern no rule marks) -- the rule now also catches those verses in the catch-all only, so nothing was duplicated by mistake.

## Contested points for the panel

1. **"Hope and Israel"** (noun and verb rows) and **"The hope of the gospel, of the calling, of righteousness, of salvation, of eternal life"**: set side by side as written; the Israel note says the page does not choose whether the hope of Israel and the hope of the gospel are one or two; the gospel row's note takes no side on whose hope it is (church, Israel, both). Dispensational/Jewish/Reformed/Catholic readers. Acts 26:7 (twelve tribes) is added by hand to Israel; Ezek 37:11 ('our hope has perished', house of Israel) is in the Israel row by the rule 'Israel in the verse' -- a reader may say it is not "the hope of Israel" in the Jer 14:8 sense. Eph 2:12 ('commonwealth of Israel ... without hope') is explicitly kept out of the Israel row (`not_verses`) and sits in Christ / promise / Without hope.
2. **"The hope of glory"** (Col 1:27, Rom 5:2) -- the phrase as written, no gloss on 'Christ in you' or on 'glory of God'.
3. **"Hope and the resurrection"** (Acts 23:6, 24:15 -- the resurrection of the dead; 1 Pet 1:3 -- of Jesus Christ): note says the page does not say which is meant to be the hope. Pharisee/Sadducee verses and Jewish readers: 23:6 is Paul's own claim to a hope shared with the Pharisees.
4. **"The hope of ... righteousness"** (Gal 5:5, inside the gospel row): the note names that readers part on it (justification/imputation debate). Not resolved.
5. **Divine persons by hand** (all picks): "The Holy Spirit named with hope" (Rom 15:13, 5:5, Gal 5:5), "Christ named with hope" (noun 10 verses, verb 3), "The LORD, God and hope" (Hebrew), "God and hope" (Greek). Labels say only *named with*. Specific: Titus 2:13 ('our great God and Savior Jesus Christ') is in the Christ row because Jesus Christ is named; the page does not decide the grammar (Granville Sharp debate). Rom 15:13 is in both the Spirit row and the God row. Jer 14:8 ('O Hope of Israel, its Savior') and Job 13:15, Ps 71:14 are NOT in a God row: no divine name in their own verse.
6. **Hebrew and Greek not pooled.** Rows keep the LORD/God Hebrew picks and Greek picks apart; every example names the word it stands on; the words table lists each word with the 'other sense' dropped. מִקְוֶה 'hope' (Jer 14:8, 17:13, 50:7; Ezra 10:2; 1 Chr 29:15) is a different word from תִּקְוָה; a reader may feel 'hope of Israel' (מִקְוֶה) and 'the hope of Israel' (ἐλπίς, Acts 28:20) are equated by sharing one row -- the label is the English words, the examples name the Hebrew or Greek.
7. **"Hope and the future"** puts Jer 29:11 ('a future and a hope') beside Prov 23:18 -- both readers' favourite verses; no label claims to whom the promise is made (Jer 29:11 is to the exiles).
8. **"The nations, the islands will put their hope"** (Isa 42:4, 51:5; Matt 12:21, Rom 15:12): Matthew and Romans quote Isa 42:4, now in the row beside it. The page gives no side on who the 'He' of the quotation is (Isa 42:4 reads 'His law').
9. **"Hope of repayment, a bribe, a harvest, money" / "Hoping to come, to see ..." / "I hope you will understand"** are ordinary-sense rows, kept (light is right). A reader may think they dilute the theological word; they show the word is also everyday.
10. **Hebrew verbs:** יָחַל and קָוָה count where MACULA glosses them hope/expect, plus the seven `sense_keep` verses where the Berean prints 'hope'. Panel: is it right that a verse's English decides (sense_keep) where the gloss says 'wait'?

## What the builder could not express (after the update)

The two options asked for earlier (`forms`, `sense_keep`) now exist and are used. Remaining:

1. **Frameless verbs are invisible to verb rules** (Ps 33:18, Ps 147:11, Ps 31:24, Rom 8:24, Heb 11:1 and others): only `pick` places them; a verb catch-all never sees them, so any frameless verse not picked vanishes without a trace. Picks used for those.
2. **Versification** of titled psalms and the Isaiah 63/64 boundary: handled per hub with `moves`; a fix in `bsb_ref` would serve every hub.
3. **Same-verse two-sense words:** Ps 130:5 has יָחַל 'hope' and קָוָה 'wait for'; the verse is kept once with both chips, no way to say one counts and the other does not.
4. **Heb 6:19** (the anchor, own_words) is not a hope-word verse: the Greek has a relative pronoun, 'which we have as an anchor', and the Berean supplies 'hope'. The card's own words include it; no row does. The image card `image_anchor` is a lead.
5. **Job 31:24** ('if I made gold my hope') is on the card (job_31_24_speech) but the Hebrew word is not one of the hub's (a 'confidence' word), and the gloss share is below the `others` threshold; it appears nowhere in the hub.
6. **Pronouns / "He":** Job 13:15 ('I will hope in Him'), Ps 71:14, 1 John 3:3 ('this hope in Him'), 2 Cor 1:10 ('In Him') say only 'Him'; left in "Every other use" per the divine-persons rule.

## Cards used (all exist)

leads: faith, love, god, jesus, holy_ghost, salvation, the_resurrection, hope_of_eternal_life, image_anchor, children_of_israel, patience, trust. gather: faith_hope_charity_these_three, hope_of_eternal_life, heirs_according_to_the_hope_of_eternal_life, having_hope_of_eternal_life, tribulation_works_patience, hope_that_is_seen_is_not_hope, faith_is_the_assurance_of_what_we_hope_for, job_5_16_speech, job_11_18_speech, job_11_20_speech.

## Panel fixes (2026-10-10, "ship after fixes", 12 fixes + 3 "missing")

Spec before this round saved as `hope_spec_24rows.json`. After: **26 rows (16 noun, 10 verb)**; same verses placed (noun 93, verb 70, "More" 0); 1 build. One over the 25 the brief names, because the panel asked for two splits and each of the two split pairs is a contested one; merging the contested rows back would undo the fix. Rows I would merge next if 25 is a hard limit: the verb "Set hope on God" (Greek) into the Hebrew LORD row, but the committee asked Hebrew and Greek apart.

| # | panel fix | done |
|---|---|---|
| 1 | Jer 14:8 out of the gospel row | done: gospel `add` is now 1 Tim 1:1, Rom 8:24, Titus 2:13 (all Greek); Jer 14:8 stays under "Hope and Israel". The panel's option to add it to "The LORD, God and hope" is a divine-person placement and is left to Doug (listed below) |
| 2 | Acts 27:20 out of the gospel row | done: stays under "Hope lost ... without hope". Label tail kept ("hope and being saved, the Savior") since Rom 8:24, 1 Tim 1:1, Titus 2:13 remain |
| 3 | Israel noun note: do not equate phrases from two words | done: note rewritten by word (miqweh Jer 14:8, 17:13; elpis Acts 28:20, 26:7; tiqwah Ezra 10:2, Ezek 37:11), "(the row below)" dropped |
| 4 | Ezra 10:2 not a lead example | done: lead is Jer 14:8, Jer 17:13, Acts 28:20, Ezek 37:11; Ezra 10:2 stays in the row |
| 5 | shame row note (Jer 17:13 has no idols) | done: panel's wording |
| 6 | Job friends' speeches | done: note on the "hope of the righteous, the wicked ..." row (Job 5:16, 8:13, 11:20 are Eliphaz, Bildad, Zophar; Job 42:7). Also changed that row's lead to Prov 10:28, 11:23, 11:7, Job 27:8 (Job's own) so two of four shown are not the friends' |
| 7 | Ps 9:18 out of "hope lost" | done: `not_verses` with the reason; it stays in the "whose hope" row |
| 8 | distress-speech note on "hope lost" | done: panel's note; the row's lead no longer opens with Ezek 37:11 (Job 14:19, Lam 3:18, Zech 9:5, Eph 2:12); Ezek 37:11 stays in the row |
| 9 | split the verb Israel/nations row | done: "Hope and Israel" (Ps 130:7, 131:3, 69:6, Luke 24:21, Acts 26:7; note by the panel) and "The nations, the islands will put their hope" (Isa 42:4, 51:5, Matt 12:21, Rom 15:12). **My earlier error corrected:** Rom 15:12 quotes Isa 11:10 (Hebrew "seek"), not Isa 42:4; Matt 12:21 quotes Isa 42:4. The note now says so. The report's contested point 8 and the earlier "Isa 42:4" statements above are superseded |
| 10 | split not-yet-seen / hoped-for-one-thing | done: two rows; Isa 5:4 note ("it is the LORD who expected sweet grapes") on the second |
| 11 | "hope / wait" caveat for the Hebrew verbs | done as a note on "Hope in the LORD, in God" (the panel's wording: yachal and qavah also rendered "wait" in about forty-seven verses, e.g. Ps 27:14, 25:3, Isa 40:31, Mic 7:7). The count 47 is the builder's own "not in this sense" totals (19 + 28) |
| 12 | Jer 29:11 addressee | done: note on "There is hope; hope and a future" |

"Missing":
- **Jer 14:8 in "The LORD, God and hope"**: not done. Divine-persons-by-hand is Doug's per-record decision; Jer 14:7 and 14:9 name the LORD, so he can add it to that row's `pick`.
- **1 John 3:3, 2 Cor 1:10, Job 13:15** into "Christ named with hope" (verb): not done, same reason ('Him' only; the context names Christ or God, but placing a person is Doug's). They stay under "Every other use".
- **Rom 8:20** with "not yet seen": not moved. It is the noun ἐλπίς ("in hope") and the "not yet seen" row is a verb row; putting a noun verse in a verb row would show a noun chip under a verb heading. It stays at the head of the noun's "Every other use" neighbours; the "not yet seen" row's `_why` says it opens the same passage.

First four examples of every changed row re-read in the Berean after the rebuild: gospel (Col 1:23, 1 Thess 5:8, Titus 3:7, Rom 8:24), Israel noun (Jer 14:8, 17:13, Acts 28:20, Ezek 37:11), whose hope (Prov 10:28, 11:23, 11:7, Job 27:8), lost (Job 14:19, Lam 3:18, Zech 9:5, Eph 2:12), Israel verb (Ps 130:7, 131:3, Luke 24:21, Acts 26:7), nations (Isa 42:4, 51:5, Matt 12:21, Rom 15:12), not yet seen (Rom 8:24, 8:25, Heb 11:1), one thing/another (Job 30:26, Isa 59:9, 59:11, Jer 8:15): 32 of 32 pass.
