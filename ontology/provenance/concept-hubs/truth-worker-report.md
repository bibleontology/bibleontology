# Hub report: truth

Spec: `ontology/concept-hubs/truth.json` (`shown: false`). Built output: `out/concept-hubs/truth.json`.
Builds run: 5 (the first two exploratory, the last three after reading the rows). Cards missing: none.

## Consolidation (rule 8: 15-25 rows) -- read this first

**49 rows -> 24 rows** (noun 39 -> 17, adjective 9 -> 6, verb 1). Two further builds were used (7 in all). The hub's verses are unchanged: before and after, noun 213, adjective 48, verb 2 verses, none lost, none new (checked by comparing the two built files). Everything the small rows held is either in a broader row or in the catch-all.

After (24 rows; counts from the last build):

Noun (17): Loving devotion and faithfulness 29 | Truth beside justice, righteousness, judgment and peace 35 | The truth of the LORD, of God; the true God 7 | "Your truth," "Your faithfulness," said to the LORD, to God (pick) 8 | The Spirit of truth; the Spirit is the truth 5 | Worship in spirit and in truth (pick) 2 | Truth said of Christ, of Jesus (pick) 7 | Walk in the truth, the way and the truth 17 | Speak the truth, tell it, do it, show faithfulness 24 | Knowing the truth: knowledge, wisdom, instruction 13 | Truth beside faith, obedience and love 20 | Against the truth: the lie, wickedness, deception, turning from it; truth missing 29 | The word of truth, "Your word is truth", the truth of the gospel 19 | Set free, sanctified, purified, guided by the truth (pick) 5 | Truth and the law, commandments 12 | In truth, truly, faithfully 41 | Every other use 32.
Adjective (6): The true light / bread / vine / worshipers 5 | Testimony, words and judgments called true; "faithful and true" 23 | God is true (pick) 5 | "He who sent Me is true" (pick) 2 | "Him who is true", "the true God" (pick) 1 | Every other use: true 13.
Verb (1): Speaking the truth 2.

Where the 49 went:
- Truth/justice/righteousness/peace (Hebrew) + Truth and righteousness, judgment (Greek) -> one row (Hebrew and Greek words now share it; each example names its word).
- The true God (pick, 2) -> the LORD/God phrase row (Jer 10:10 `add`ed by hand; 2 Chr 15:3 fell into the phrase by rule).
- The Spirit of truth + The Spirit is the truth (1 John 5:6 `add`ed) -> one row; the no-side note kept.
- The way and the truth + Walk in the truth -> one row.
- Speak the truth + Show, do, practice the truth -> one row (both are verbs whose object is the truth).
- Know the truth + The knowledge of the truth + Wisdom, knowledge, instruction -> one row; the no-side note on "the knowledge of the truth" kept. New false hits from γινώσκω and יָדַע (the Spirit "known", "I know Him", "know for certain") were cut with `not_verses` and their reasons.
- Truth and faith + Obeying the truth + Truth and love -> one row; the no-side note on faith kept.
- Turned from ... + Truth and the lie + Truth, wickedness and deception + Truth missing (pick) + The truth is not in him (pick) -> one row (the five "missing" verses and 1 John 1:8 are `add`ed by hand; John 8:44 stays in it).
- The word of truth + The word is truth + The truth of the gospel -> one row (the subject-shape verses `add`ed by hand, listed with reasons in the spec); a no-side note was added ("the word" read as Scripture, Christ or the gospel), as rule 3 asks and the first build lacked.
- Hebrew "in truth" + Greek "in truth" -> one row; all `not_verses` kept.
- Grace and truth, Testimony/witness (noun), Truth and the light, Truth and the heart, The belt of truth, "What is truth?" -> dissolved into the catch-all or the rows above (most of their verses already sat in other rows; the rest are in Every other use, where the doors to the belt of truth and to Pilate's question now hang).
- Adjective: Testimony + True ways, true judgments + Faithful and true + Words said true -> one row; the other `not_verses` kept.
- Kept as their own rows because contested or by hand: the LORD/God phrase, "Your truth" said to the LORD, the Spirit row, Worship in spirit and truth, Truth said of Christ, Set free/sanctified, Truth and the law, Truth beside faith, obedience and love, Knowing the truth, the word row, God is true, "He who sent Me is true", "Him who is true" (1 John 5:20).

Cost of the merge, for the panel: Hebrew and Greek companions that the committee wanted in separate sub-rows now share five rows (justice, walk/way, speak/do, knowing, in truth). Each example still names its word, and the first row's note says the two words differ.

**Re-read of the two first-sample fixes after the rebuild:**
- Rom 3:7 ("if my falsehood accentuates God's truthfulness ... why am I still condemned as a sinner?") now sits only in "The truth of the LORD, of God; the true God" (it is out of the justice/judgment row by `not_verses`). Shows its label: pass.
- Mark 12:32 ("You have stated correctly that God is One") sits in "In truth, truly, faithfully", whose note names "correctly". The Berean text does not say "truth" there; the Greek phrase is the same. Pass with the note, as before.

**First examples of every remaining row** were re-read in the Berean text from the last build and each shows its label (e.g. justice row: Jer 4:2 "in truth, in justice, and in righteousness"; knowing row: John 8:32, 1 Tim 2:4, Prov 23:23, Rom 2:20; faith/obedience/love row: 1 John 3:18, Gal 5:7, 2 Thess 2:12, Zech 8:19; testimony row: John 19:35, 3 John 12, Rev 15:3, Rev 19:11). One row's lead was changed: John 5:31 (the Berean prints "not valid") no longer leads the testimony row, and its note now says so. The catch-all rows (noun and adjective) are by definition not a label. Contested-point numbers 10 and 11 below still hold: John 8:44 now sits in "Against the truth" (not among its four shown examples, which the spec leads with Isa 59:15, Prov 12:19, Eph 4:25, 2 Tim 4:4; the verse is still in the row) and 1 Tim 3:15 is the second shown example of "Every other use".

Everything below describes the 49-row first build (row names and counts are from that build); the contested points and the builder limits apply unchanged, with the row names mapped as above.

## Rows of the first build (49 rows; 396 placements; "More" is empty in all three forms because each form ends in a catch-all row)

Noun (lead), 39 rows, 213 verses:

| Row | n |
|---|---|
| Loving devotion and faithfulness (Hebrew חֶסֶד beside אֱמֶת) | 29 |
| Truth, justice, righteousness and peace (Hebrew) | 29 |
| Truth and righteousness, judgment (Greek) | 6 |
| The truth of the LORD, of God (phrase, adjacent) | 5 |
| "Your truth," "Your faithfulness," said to the LORD, to God (pick) | 8 |
| The true God (pick) | 2 |
| The Spirit of truth (phrase) | 4 |
| The Spirit is the truth (pick) | 1 |
| Worship in spirit and in truth (pick) | 2 |
| Truth said of Christ, of Jesus (pick) | 7 |
| The way and the truth | 6 |
| Grace and truth | 4 |
| Testimony, witness and the truth | 9 |
| Speak the truth, tell the truth | 15 |
| Show, do, practice the truth | 9 |
| Know the truth | 4 |
| The knowledge of the truth | 5 |
| Wisdom, knowledge, instruction and the truth | 4 |
| Truth and faith | 9 |
| Obeying the truth, refusing to obey it | 3 |
| Truth and love | 10 |
| Turned from, strayed from, opposed, suppressed, exchanged for a lie | 7 |
| Truth and the lie, falsehood | 13 |
| Truth, wickedness and deception | 6 |
| Truth missing, stumbled, flung down (pick) | 5 |
| The truth is not in him, not in us (pick) | 3 |
| The word of truth | 10 |
| The word is truth, the message is true | 7 |
| The truth of the gospel | 4 |
| Set free, sanctified, purified, guided by the truth (pick) | 5 |
| Truth and the law, commandments | 12 |
| Truth and the light | 4 |
| Truth and the heart | 13 |
| Walk in the truth | 11 |
| In truth, truly, faithfully (Hebrew, בְּ + אֱמֶת) | 24 |
| In truth, truly (Greek, ἐν / ἐπί + ἀλήθεια) | 17 |
| The belt of truth (pick) | 1 |
| "What is truth?" (pick) | 1 |
| Every other use (catch-all) | 28 |

Adjective, 9 rows, 48 verses: The true light / bread / vine / worshipers 5; Testimony, witness: true, or not true 11; True ways, true judgments 4; Faithful and true 4; Words, sayings said to be true 7; God is true (pick) 5; "He who sent Me is true" (pick) 2; "Him who is true", "the true God" (pick) 1; Every other use: true 13.

Verb, 1 row, 2 verses: Speaking the truth (ἀληθεύω: Eph 4:15, Gal 4:16).

A verse sits in every row it fits (`match: "all"`), so the placements (396) exceed the verses (263).

## The words, and the "others"

Words: אֱמֶת h571 (114 verses in sense, 10 not), Aramaic קְשֹׁט h7187 (2), ἀλήθεια g225 (98), ἀληθής g227 (25), ἀληθινός g228 (25, 1 not), ἀληθεύω g226 (2). Two Greek adjectives are printed "true"; each example names the one its verse uses, and the first adjective row carries a note saying so.

Sense: אֱמֶת is kept whole -- the Berean prints it "truth" (37), "faithfulness" (41), "true" (19), plus faithful, faithfully, good faith, truthful, trustworthy, reliable, faith -- because the Hebrew gives no second word. Left out as another sense (10 verses): "security" (2 Kgs 20:19, Isa 39:8, Jer 33:6), "sure" (Josh 2:12, Ps 132:11, Ps 69:14), "lasting" (Jer 14:13), "purest" (Jer 2:21), "fairness" (Prov 29:14), "right" (Gen 24:48). ἀληθινός at Heb 10:22 ("a sincere heart") is left out. "real" keeps Acts 12:9; "surety" keeps Dan 2:47.

Others (apart from the rows, never handed over as the same word): ἀληθῶς "truly" (17), ὄντως "really" (3), γνήσιος "genuine" (3), and three single Aramaic/Hebrew words (Dan 3:14 צְדָא, Dan 7:19 יְצַב, Josh 7:20 אׇמְנָה). ἀμήν does not appear (the Berean prints "Truly, truly" but the gloss is not "truly").

Not made words, on purpose: אֱמוּנָה / אָמַן (faithfulness, believe: the faith concept's, same root; the Berean renders אֱמוּנָה "truth" only 6 of 49 times) and the adverb ἀληθῶς (see below).

## The 16-verse sample (read in the Berean through /api/verse)

Chosen from deeper in the rows, not their first four examples.

| # | Row | Verse | Verdict |
|---|---|---|---|
| 1 | Loving devotion and faithfulness | Prov 14:22 "find loving devotion and faithfulness" | pass |
| 2 | Truth, justice, righteousness, peace | Ps 111:7 "truth and justice" | pass |
| 3 | Truth and righteousness, judgment (Greek) | Rom 3:7 "God's truthfulness ... condemned as a sinner" | FAIL first pass (the Berean prints "condemned", not judgment); verse removed from this row with `not_verses` (it stays in the row of God's truth) |
| 4 | The truth of the LORD, of God | Rom 15:8 "on behalf of God's truth" | pass |
| 5 | The way and the truth | Mark 12:14 "teach the way of God in accordance with the truth" | pass |
| 6 | Testimony, witness and the truth | Prov 14:25 "A truthful witness saves lives" | pass |
| 7 | Speak the truth | Mark 5:33 "she told Him the whole truth" | pass |
| 8 | Show, do, practice the truth | 2 Chr 31:20 "He did what was good and upright and true" | pass |
| 9 | Truth and faith | Titus 1:1 "the faith of God's elect and their knowledge of the truth" | pass |
| 10 | Truth and love | 3 John 1 "whom I love in the truth" | pass |
| 11 | Turned from, strayed, opposed, suppressed | Titus 1:14 "men who have rejected the truth" | pass |
| 12 | Truth and the lie, falsehood | Prov 12:19 "Truthful lips ... a lying tongue" | pass |
| 13 | In truth, truly, faithfully (Hebrew) | Ps 111:8 "enacted in truth and uprightness" | pass |
| 14 | In truth, truly (Greek) | Mark 12:32 "You have stated correctly" | FAIL first pass (no "truth" in the Berean; the Greek is ἐπ' ἀληθείας); kept, with the row's note now naming "correctly", as the Greek is the same phrase |
| 15 | Truth and the law, commandments | Mal 2:6 "True instruction was in his mouth" | pass |
| 16 | Testimony, witness: true, or not true | Titus 1:13 "This testimony is true" | pass |

Tally: 16 sampled, 14 pass on the first reading, 2 fail, both fixed (one removed, one noted). Extra spot checks, all pass: Jer 32:41, Rev 3:14, 2 Tim 2:15, Jas 1:18, Ps 89:14, Ezek 18:9. Weak but kept: John 8:17 (the Berean prints "valid" for ἀληθής), Zech 8:8 ("faithful and righteous God" for בֶּאֱמֶת וּבִצְדָקָה).

Fixes made in the three read-and-rebuild rounds, by rule where a rule could do it, otherwise `not_verses` with the reason in the spec: Col 1:5 and Rom 2:2 and similar `ἐν`/`ἐπί` false hits; Deut 13:15, 17:4, 22:20 (דָּבָר = "thing", "charge"); 2 Chr 32:1, Ps 45:4 (דָּבָר = "acts", "cause"); 1 Kgs 22:16 / 2 Chr 18:15 (בְּ is "in the name of the LORD"); 1 John 1:6 (walk in darkness); 1 John 3:19 (πείθω = "assure"); Matt 22:16 / Mark 12:14 (flatterers' "honest"); Luke 16:11 and 1 Pet 5:12 (faithful and true are two things); Rom 3:4 out of the "words" row; a rule on λέγω was replaced by `add` for John 10:41 and John 4:18 because it took every verse of dialogue.

## Contested points for the review panel

1. **"The Spirit of truth"** (John 14:17, 15:26, 16:13, 1 John 4:6; Orthodox, Catholic, Reformed). John 15:26's "who proceeds from the Father" is in the verse text the page quotes; the row note says the page takes no side on how the Spirit relates to the Father and the Son. Phrase row by rule, not by an inference about the Person. **"The Spirit is the truth"** (1 John 5:6) is a pick because the verse names the Spirit.
2. **"Him who is true", "the true God"** (1 John 5:20; Trinitarian traditions, Jehovah's-Witness-type readers, Jewish reader). Held in a row of its own with the note that readers take "He" of the Father or of Jesus Christ. Not filed under "God is true" or under Jesus.
3. **"God is true"** (John 3:33, Rom 3:4, John 17:3, 1 Thess 1:9, Rev 6:10) is by hand and only where the verse names God or the Lord. John 17:3 sets "the only true God" beside "Jesus Christ" in one sentence (Trinitarian / non-Trinitarian). **"He who sent Me is true"** (John 7:28, 8:26) is Jesus' own phrase, no identification added.
4. **"Truth said of Christ, of Jesus"** (John 1:14, 1:17, 14:6, 18:37; Rom 9:1; 2 Cor 11:10; Eph 4:21). John 14:6 ("No one comes to the Father except through Me") is exclusivism/inclusivism territory, no gloss added. John 1:17 ("the law was given through Moses; grace and truth came through Jesus Christ") will be read by a Jewish reader as a contrast of law and truth; it also stands in "Truth and the law" and "Grace and truth".
5. **"The knowledge of the truth"** (1 Tim 2:4 "wants everyone to be saved", 2 Tim 2:25 "may grant them repentance", Heb 10:26 "after we have received the knowledge of the truth", Titus 1:1 "God's elect") -- Calvinist/Arminian, universalist, apostasy. The row carries a no-side note.
6. **"Truth and faith"** (2 Thess 2:12-13 "chose you ... to be saved by the sanctification of the Spirit and by faith in the truth"; election, sanctification, faith). Also in "Truth and love" (2 Thess 2:13, listed there for "loved by the Lord"). Note: no side on what faith is or how it is given.
7. **"Set free, sanctified, purified, guided by the truth"** (John 8:32, 17:17, 17:19, 16:13; 1 Pet 1:22 "purified your souls by obedience to the truth"). Label uses the verses' own verbs. 1 Pet 1:22 touches obedience and purification (Catholic/Orthodox/Protestant) and is also in "Obeying the truth", "Truth and love", "Truth and the heart".
8. **"The word is truth"** (John 17:17) and **"The word of truth" / "The truth of the gospel"** (Eph 1:13, Col 1:5, Gal 2:5, 2:14): Scripture, Christ, or the gospel as "the word" -- the page does not say which; no note on the row.
9. **"Truth and the law, commandments"** (Rom 2:20, Titus 1:14 "Jewish myths or the commands of men who have rejected the truth", John 1:17, 1 John 2:4): law and gospel; the row note says no side. Titus 1:14 ("Jewish myths") sits in this row and in "Turned from ..." and wants a Jewish reader's eye.
10. **John 8:44** ("You belong to your father, the devil ... there is no truth in him") is the second example of "Truth and the lie, falsehood" and the first of "The truth is not in him, not in us". It is a verse often misused against Jews; the page shows it as written, without comment. The panel may wish to decide whether the leading example of those rows should be a different verse (the example order is automatic; I did not reorder).
11. **1 Tim 3:15** ("the church of the living God, the pillar and foundation of the truth") sits in the catch-all "Every other use". It has no row; the panel may decide whether a row for it (church authority: Catholic, Orthodox, Protestant) is wanted. Left alone as the lightest touch.
12. **Dan 8:12** ("it flung truth to the ground") in "Truth missing": the row says only what the verse says about truth; the "horn" is not identified (visions rule).
13. **Pooling of אֱמֶת**: the first row keeps the Berean's own "faithfulness" for 41 of its verses; the note says it is one Hebrew word and ἀλήθεια is a different one. A Jewish or academic reader will check this against the committee flag. The hub never says אֱמֶת "means" truth or faithfulness.
14. **Testimony: true, or not true** keeps John 5:31 ("not true") beside John 8:14 ("true") as the text has them; no harmonizing.
15. **"Your truth," "Your faithfulness," said to the LORD** is a hand pick of 8 verses whose own text names the LORD or God. Psalms that say "Your truth" without naming Him in the verse (Ps 26:3, 43:3, 57:10, 108:4, 138:2, 89:14, Mic 7:20, Isa 38:18-19) were left to the rows they fit, as righteousness left Rev 15:3.

## What the builder could not express

- **An adverb form.** ἀληθῶς ("truly", 18 verses, the same family as ἀληθής) cannot be a word: a pos of `ADV` is read as the letter `A`, which files it as an adjective under rows that say "called true". It shows only under "other words". Needed: an `adverb` form or a `skip_pos` rule.
- **A row condition on the concept's own word** (language, or which lemma: אֱמֶת vs ἀλήθεια; ἀληθής vs ἀληθινός). Rows can only be told apart by their companions, so Hebrew and Greek rows exist only where the companions differ. A `word: ["g228"]` row key would let "genuine" (ἀληθινός) sit apart from "truthful" (ἀληθής) without a companion.
- **`with` across the clause tree.** The next-word window stays inside one part: "the true bread" (John 6:32), "the truth of your words" (Gen 42:16), "words of peace and truth" (Esth 9:30) fell outside and were `add`ed by hand. A `within_clause: N` window would catch them.
- **`subject` reads the first word of the subject part.** "The entirety of Your word is truth" (Ps 119:160) has the head "entirety", not "word"; `add`ed by hand. Needed: skip construct heads such as רֹאשׁ.
- **No per-verse remark.** A verse where the Berean prints something other than the original (Mark 12:32 "correctly" for ἐπ' ἀληθείας; John 8:17 "valid" for ἀληθής; Rom 3:7 "condemned" for κρίνω) can only be put in a row note or taken out; a `verse_note` would let the Berean's wording and the original's both show, as the "mark findings in the verse" rule asks.
- **Divine phrase for `אֱלֹהִים אֱמֶת`.** Jer 10:10 ("the LORD is the true God") is not caught by `with: @divine, adjacent` (it is a clause, not a construct) and is a pick instead.
- **`lead` on a pick row** is ignored (a pick row is shown in its pick order); the first pick has to be the best example.

## Panel fixes (review "ship after fixes", 14 fixes + 2 missing verses)

Result: 25 rows (noun 18, adjective 6, verb 1); noun verses 213 -> 215 (2 John 1:2 and Gen 32:10 placed), adjective 48, verb 2; no verse lost (checked against the pre-fix build). Two builds used (8 and 9 in all); cards missing: none. Rebuilt output re-read in the Berean for the four shown examples of every changed row: all show their label (Gen 32:10, a fifth-or-later example of the "Your truth" row, prints "kindness and faithfulness You have shown Your servant").

1. Justice row, label: relabelled "Truth or faithfulness beside justice, righteousness, judgment and peace"; lead now Jer 4:2, Zech 8:16, Ps 111:7, Eph 5:9. Applied.
2. Justice row, note: replaced by the reader's note ("Two different words: Hebrew אֱמֶת (the Berean prints it "truth", "faithfulness" or "true") and Greek ἀλήθεια; each example names its word."); the build history moved to the row's `_why`. Applied.
3. Loving-devotion row: lead Ps 85:10, Exod 34:6, Prov 3:3, Ps 86:15; note extended (חֶסֶד printed "loving devotion", "kindness" or "mercy"; אֱמוּנָה, also printed "faithfulness", is not in this hub). Applied.
4. Word row: Gen 42:16, 1 Kgs 10:6, 2 Chr 9:5 (to the catch-all) and Esth 9:30 (to the justice row, where "peace and truth" already placed it) left the row; kept Ps 119:43, 119:160, 2 Sam 7:28, 1 Kgs 17:24, Jer 23:28, Dan 10:1; label now "Your word is truth", the word of truth, the truth of the gospel (the Hebrew Scripture's claim first); lead Ps 119:160, John 17:17, Eph 1:13, Gal 2:5; note scoped to the New Testament phrases as the panel worded it. Applied. (Eccl 12:10 "words of truth", a human teacher's, stays: the panel did not name it and the Hebrew phrase is the Teacher's own claim.)
5. Law row, Titus 1:14: removed by `not_verses` with the reason; it stays in the "Truth and its opposites" row. Applied.
6. Law row, OT framing: lead Ps 119:142, Neh 9:13, Mal 2:6, John 1:17; note scoped to John 1:17, Rom 2:20 and similar New Testament verses. Applied.
7. "Against the truth" row: relabelled "Truth and its opposites: the lie, wickedness, deception; turning from it; truth missing". Applied. (John 8:44 is not a lead example and sits in the row as written.)
8. Christ row: Rom 9:1 removed (stays in the speak-the-truth and opposites rows); label left as it was (the panel's looser relabel was conditional). Applied.
9. "God is true": two-Greek-words note added; relabelled "God is true; "the only true God", "the living and true God"". Applied.
10. Testimony row: relabelled "Testimony, words, ways and judgments called true; "faithful and true""; note extended with the two-Greek-words sentence and "valid" in John 5:31-32, 8:13-14, 8:17. Applied.
11. Knowing row: note rewritten and scoped to the New Testament phrase (1 Tim 2:4, 2 Tim 2:25, Heb 10:26, Titus 1:1), naming "whether it can be lost". Applied.
12. Faith/obedience/love row: note rewritten and scoped, naming God's choosing. Applied.
13. Set-free/sanctified row: no-side note on sanctification, purifying and obedience added. Applied.
14. "Your truth" pick: Ps 119:151 removed (it stays in the law row). Applied.
15. Missing, 2 John 1:2: the builder never saw it (the clause starts at 1:1 and the word is filed under the first verse where it stands), so no rule or `add` can reach it. Placed by hand in a new two-verse pick row, "The truth that abides in us, that we now have" (2 John 1:2 with 2 Pet 1:12, taken from the catch-all). This is the one row added; 25 rows.
16. Missing, Gen 32:10: absent from the built occurrences of אֱמֶת (124 rows for 127 uses), so no rule can place it, and a pick cannot go into the rule-based first row the panel named. Placed by hand in the "Your truth, your faithfulness, said to the LORD" row: it is Jacob's prayer, one sentence with Gen 32:9, which names "the LORD". This departs from the panel's suggestion and from my earlier standard (only verses that name Him themselves); the panel may prefer a different row. Builder limit: a pick-row verse cannot join a rule row, and a verse the occurrence data lacks cannot be reached by `add`.
