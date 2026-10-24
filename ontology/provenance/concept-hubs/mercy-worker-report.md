# Mercy hub: report

## Update: regrouped from 35 to 23 rows (rule 8: about 15-25)

Current spec: `ontology/concept-hubs/mercy.json` (`shown: false`, **23 rows**: 8 verb, 11 noun, 4 adjective). One further build (2 allowed); 0 cards missing. The 35-row spec is saved as `mercy_spec_35rows.json` (and its build as `mercy_built_35rows.json`) in this folder. The Hosea `moves` entry (Hos 14:4 -> 14:3) was already in the spec and stays.

Nothing dropped: compared verse by verse against the 35-row build, the only verse that lost a row-placement is Ps 103:13 in the noun tab (it was picked there for "On those who fear Him"); it is still under the LORD row in the verb tab, and Luke 1:50 stays in the noun catch-all. Every other verse is in a row or a catch-all.

| Before (35) | After (23) |
|---|---|
| Verb: “Have mercy on me” 11 | same, 11 |
| LORD will have compassion 24 | same, 24 |
| “I will have mercy on whom I have mercy” 4 | same, 4 (contested note kept) |
| “Now you have received mercy” 7 | same, 7 (the Hosea / 1 Pet 2:10 pairing now in its `_why`) |
| Show mercy to others 5 | same, 5 |
| “No Compassion” and “Not My People” 3 | removed as a row: Hos 1:6 is in “No compassion...”, Hos 2:23 in the LORD row, 1 Pet 2:10 in “Now you have received mercy” |
| Mercy through disobedience 3 | same, 3 (Rom 11:32 note kept) |
| A father, a mother, a son 4 | removed as a row: Ps 103:13 and Jer 31:20 in the LORD row, Matt 17:15 in “Have mercy on me”, Isa 49:15 in the verb catch-all |
| No compassion, no mercy, no pity 10 | same, 10 (hard verses kept) |
| “The Lord has shown you mercy” 1 | into the verb catch-all, which now carries the bare-“He” / “the Lord” note (Isa 49:10, Mark 5:19) |
| Mercy in the eyes of others 2 (verb) | into the verb catch-all (1 Kgs 8:50, Jer 42:12) |
| Every other use 1 | “Every other use” 5 (Isa 49:10, Isa 49:15, Mark 5:19, 1 Kgs 8:50, Jer 42:12) |
| Noun: Mercy and peace 6 | same, 6 (Gal 6:16 note kept) |
| Compassion beside חֶסֶד 11 | same, 11 |
| Justice, judgment and mercy 4 + Anger, and mercy 7 | one row “Beside justice, judgment and anger”, 11 (by pick: the rule row cannot be ANDed with Hab 3:2, which has no noun clause) |
| His great mercy 13 + The mercy of the LORD, of God 19 | one row “The mercy of the LORD, of God”, 22 (the three that name Him only by address or speech, Neh 9:19, 9:27, Isa 54:7, are noted in its `_why`) |
| The mercy of our Lord Jesus Christ 1 + “The Lord grant mercy” 2 | one row “Our Lord Jesus Christ”, “the Lord”, 3, with a note: Jude 21 names Christ, 2 Tim 1:16 and 1:18 say “the Lord”, and the page does not choose |
| Compassion, and forgiveness 6 | same, 6 (note kept) |
| Not our deeds, but His mercy 2 | same, 2 (Titus 3:5 note kept) |
| “I desire mercy, not sacrifice” 2 | same, 2 |
| Asking for mercy 14 | same, 14 |
| Mercy in the eyes of others 7 | into the noun catch-all (2 Chr 30:9, Ps 106:46, Dan 1:9, Jer 42:12; Gen 43:14, 1 Kgs 8:50, Neh 1:11 stay in “Asking for mercy”) |
| Mercy to one another 2 + No mercy shown 4 | one row “Mercy shown, and no mercy shown”, 6 |
| Remembering mercy 3, On those who fear Him 2 | into the noun catch-all (Luke 1:50, 1:54, 1:72); Hab 3:2 in “Beside justice, judgment and anger”, Ps 25:6 in the LORD and Asking rows |
| Every other use 8 | “Every other use” 13 |
| Adjective: LORD is compassionate, merciful 11 | same, 11 |
| A merciful and faithful high priest 1 | same, 1 |
| The merciful, and the merciless 3 + Compassionate people 2 | one row “The merciful, the merciless, the compassionate”, 5 (Ps 112:4 note kept) |
| Every other use 2 | same, 2 |

First examples re-checked for every remaining row after the rebuild: each of the first four shows its row's label (the pick rows list their best examples first; “Beside justice, judgment and anger” opens with the four justice/judgment verses, Hos 2:19, Matt 23:23, Jas 2:13, Zech 7:9, then the anger verses; “Compassion beside חֶסֶד” opens Dan 1:9, Hos 2:19, Isa 63:7, Jer 16:5). The 16-verse sample below was taken on the 35-row spec; the merged rows contain the same verses, so it stands. Row counts and names below this section describe the 35-row version.

(Everything below is the original 35-row report.)

---

Spec: `ontology/concept-hubs/mercy.json` (`shown: false`, 35 rows). Built 4 times into `out/concept-hubs/mercy.json`; 0 cards missing.

## The words (and what was decided)

The card held only ἔλεος. The hub's words:

- Greek, the ἔλεος family: ἔλεος (26 verses in this sense), ἐλεέω (29), ἐλεήμων (2), ἐλεεινός (1; 1 other sense dropped), and the negatives ἀνέλεος (Jas 2:13) and ἀνελεήμων (Rom 1:31).
- Hebrew, the רחם family: רָחַם verb (41; 2 dropped: "loved" at Ps 18:1, the name Ruhamah), רַחֲמִים noun (38; 1 dropped, Gen 43:30 "emotion"), רַחוּם adjective (13), Aramaic רַחֲמִין (Dan 2:18), רַחֲמָנִי (Lam 4:10, "compassionate women").
- Why the Hebrew and Greek are together: the text pairs them. Hos 1:6 and 2:23 name "No Compassion" (Lo-ruhamah); 1 Pet 2:10 says "once you had not received mercy, but now you have received mercy".
- Sense pattern: `merc|compassion|pit`.

**Decided apart (not in the rows):**

- **חֶסֶד** is not in the rows. It is the love hub's "other word"; the Berean prints "loving devotion" for it, and "mercy" in only a few verses (Hos 6:6, Mic 6:8, Ps 23:6, Neh 13:22, 1 Kgs 20:31 "merciful"). The two words are named side by side in one row, "Compassion beside חֶסֶד, “loving devotion”" (11 verses), with a note that they are two words. The committee's advice (link out, do not merge) is followed.
- חנן (Ps 51:1 "Have mercy on me, O God" is this word), חמל and חוס (spare, pity), נחם, σπλαγχνίζομαι (Jesus "moved with compassion", 12), οἰκτιρμός, οἰκτίρω, οἰκτίρμων, ἱλάσκομαι, ἵλεως and the rest are named under `others` with their verses (19 words, built by the gloss).
- ἐλεημοσύνη is "alms" in the Berean, so it is left out. This is the committee's "works of mercy" point (see below).
- "Mercy seat" (כַּפֹּרֶת, ἱλαστήριος) is an object and is kept out by the pattern on the gloss.

## Rows (count) — all by hand except the four rule rows

**Verb** (lead; "Who has mercy on whom"): “Have mercy on me” 11 · The LORD will have compassion 24 · “I will have mercy on whom I have mercy” 4 · “Now you have received mercy” 7 · Show mercy to others 5 · “No Compassion” and “Not My People” 3 · Mercy through disobedience 3 · A father, a mother, a son 4 · No compassion, no mercy, no pity 10 · “The Lord has shown you mercy” 1 · Mercy in the eyes of others 2 · Every other use 1 (Isa 49:10).

**Noun** ("What the text says of mercy"): Mercy and peace 6 (rule: εἰρήνη/שָׁלוֹם in the verse) · Compassion beside חֶסֶד 11 (rule) · Justice, judgment and mercy 4 (rule: κρίσις/מִשְׁפָּט; Ps 119:156 `not_verses`, "ordinances") · Anger, and mercy 7 · His great mercy, His great compassion 13 · The mercy of the LORD, of God 19 · The mercy of our Lord Jesus Christ 1 · “The Lord grant mercy” 2 · Remembering mercy 3 · On those who fear Him 2 · Compassion, and forgiveness 6 · Not our deeds, but His mercy 2 · “I desire mercy, not sacrifice” 2 · Asking for mercy 14 · Mercy in the eyes of others 7 · Mercy to one another 2 · No mercy shown 4 · Every other use 8.

**Adjective** ("Called merciful, compassionate"): The LORD is compassionate, merciful 11 · A merciful and faithful high priest 1 · The merciful, and the merciless 3 · Compassionate people 2 · Every other use 2.

`More` is 0 in all three forms. Totals: 69 verb verses, 74 noun, 19 adjective.

## The 16-verse sample (read in the Berean text from the server)

Tally: **14 pass, 2 failed and were fixed, 0 left failing** (after the rebuild, each fixed verse sits where it shows its label).

| # | Verse | Row | Verdict |
|---|---|---|---|
| 1 | Luke 16:24 | Have mercy on me | pass (the rich man to Abraham) |
| 2 | Isa 49:10 | The LORD will have compassion | FAIL: the verse says only "He who has compassion". Taken out; now in verb "Every other use" |
| 3 | Hos 14:3 | The LORD will have compassion | pass, after `moves` (see builder gaps) |
| 4 | Rom 9:16 | I will have mercy on whom... | pass ("God's mercy") |
| 5 | Jude 1:22 | Show mercy to others | pass |
| 6 | Prov 28:13 | Now you have received mercy | pass ("will find mercy") |
| 7 | Jer 50:42 | No compassion, no mercy | pass ("cruel and merciless") |
| 8 | Jer 31:20 | A father, a mother, a son | pass ("a precious son ... great compassion") |
| 9 | Gal 6:16 | Mercy and peace | pass |
| 10 | Dan 1:9 | Compassion beside חֶסֶד | pass ("favor and compassion"; the row's note says the Berean prints "favor" here) |
| 11 | Matt 23:23 | Justice, judgment and mercy | pass |
| 12 | Isa 60:10 | Anger, and mercy | pass |
| 13 | Eph 2:4 | The mercy of the LORD, of God | pass ("God, who is rich in mercy") |
| 14 | Luke 1:72 | Remembering mercy | FAIL: it remembers the covenant, not the mercy. Taken out; now in noun "Every other use" |
| 15 | Dan 2:18 | Asking for mercy | pass |
| 16 | Amos 1:11 | No mercy shown | pass ("stifled all compassion") |

Also read and fixed: Jas 3:17 (wisdom "full of mercy") is not mercy to one another, so it was taken out of that row. Also read and passed: Lam 4:10, Jer 16:5, Hos 2:19, Rom 12:8, Ps 102:13.

## Contested points for the review panel (row, verses, traditions)

1. **“I will have mercy on whom I have mercy”** (Exod 33:19, Rom 9:15, 9:16, 9:18). Calvinist/Reformed, Arminian/Wesleyan, Catholic, Orthodox and Jewish readers part on election and human choice. The row has a no-side note. The row sets the text only; check that grouping 9:16 ("does not depend on man's desire or effort") with the other three does not tilt.
2. **Mercy through disobedience** (Rom 11:30-32), which ends "so that He may have mercy on everyone". Universalist and particularist readers part; no-side note.
3. **Not our deeds, but His mercy** (Dan 9:18, Titus 3:5). Titus 3:5 also says "washing of new birth" (baptismal regeneration: Catholic, Orthodox, Lutheran against Baptist and Reformed readings) and sets mercy against "righteous deeds" (Catholic and Orthodox against Reformed and Lutheran on merit). A no-side note covers both. Two verses only; the panel may prefer to fold Dan 9:18 into "Asking for mercy" and drop the row.
4. **Mercy and peace** (Gal 6:16 "the Israel of God"). Replacement/covenant-theology readers, dispensational readers and Jewish readers part on who is meant; no-side note.
5. **Compassion, and forgiveness** (1 Kgs 8:50, Isa 55:7, Ps 78:38, Neh 9:17, Dan 9:9, Hos 1:6). Whether forgiveness waits on repentance (Isa 55:7 "let him return to the LORD, that He may have compassion"; Prov 28:13) is held differently by Catholic, Orthodox, Lutheran, Reformed and free-church readers; no-side note on this row. Prov 28:13 is also in "Now you have received mercy"; that row has no note and states no order.
6. **“The Lord grant mercy”** (2 Tim 1:16, 1:18) and **“The Lord has shown you mercy”** (Mark 5:19): the verse says "the Lord"; the notes say readers take it of the Father or of Christ and the page does not choose. Ps 112:4 ("the gracious, compassionate, and righteous") is read of the upright man or of the LORD; note in "Compassionate people".
7. **Divine persons by hand.** "The LORD will have compassion" (24) lists verses by hand. Some name the LORD in the verse; some name Him only by address ("You": Ps 102:13, Hos 14:3, Mic 7:19) or by His first-person speech in the passage ("I": Isa 60:10, Jer 12:15, Hos 2:23). The panel should say whether that is "the text itself names him". Isa 49:10, a bare "He", was taken out. "A merciful and faithful high priest" (Heb 2:17) says "He"; Jesus is named in 2:9, and the verse also names atonement. "The mercy of our Lord Jesus Christ" (Jude 21) names him.
8. **Hard verses stay**, set beside mercy as the text sets them: "No compassion, no mercy, no pity" (10: the LORD in Isa 9:17, 27:11, Jer 13:14, Hos 1:6, 2:4; the enemy He raises in Isa 13:18, Jer 6:23, 50:42, 21:7; Zech 1:12 asks "will You withhold mercy"); Lam 4:10 ("compassionate women have cooked their own children") under "Compassionate people". A Jewish or secular reader may find these essential; a devotional reader may find them harsh next to the others.
9. **Hos 6:6 / Mic 6:8 are the card's own key verses, and they are חֶסֶד**, not the רחם/ἔλεος words in the rows. They are shown in `own_words`, in no row. Check that this reads as honest. The row "I desire mercy, not sacrifice" (Matt 9:13, 12:7) carries a note naming Hosea's Hebrew as חֶסֶד, "two words". That note states a fact about the original, not a quotation; the panel may want it moved to the About text.
10. **Works of mercy (Catholic and Orthodox emphasis).** The hub follows the Berean's words, so "alms" (ἐλεημοσύνη) is not included, and Matt 25 has no mercy word. Rows "Show mercy to others" (5) and "Mercy to one another" (2) are the text's own. The panel may say whether that under-serves the point.
11. **Jesus' compassion in the Gospels** is σπλαγχνίζομαι, a different word, so it appears only under `others`, never in a row. A Christian reader may expect it at the head of the hub. It is deliberate (rule 2).
12. The `others` section includes ἱλάσκομαι (Luke 18:13, "God, have mercy on me"), ἵλεως (Heb 8:12) and חנן; these touch propitiation and grace. They are listed apart with verses only.

## What the builder could not express

1. **Verb verses without a frame vanish.** The verb rows are filled from `out/frames.jsonl.gz`; six verses where the word stands with no frame (Hab 3:2, Rom 9:16, Rom 12:8, Jude 22, Jude 23; Lam 4:10 for the adjective) never enter `seen_form`. They are not under "More" and `add` cannot reach them (it requires `seen_form`). They are reached here only by `pick`. Needed: an unplaced-verse "More" that takes every sense-matching occurrence, or `add` that accepts any verse the word's occurrences hold.
2. **Frame agent/patient are unusable for these verbs.** The frames give, for example, Matt 9:27's agent as υἱός (the vocative "Son of David"). `agent`/`patient` rules could not build "who has mercy on whom", so the verb rows are picks.
3. **`others` reads MACULA's gloss, not the Berean's printed word.** Verses where the Berean prints "mercy" for a word MACULA glosses otherwise are missed: חֶסֶד at Hos 6:6, Mic 6:8 (and, under another gloss, תַּחֲנוּן "cry for mercy" at Ps 28:2, 28:6, 31:22, 86:6, 116:1, 130:2). Needed: a way to give `others` a lemma list plus a regex on the verse text.
4. **Versification.** The frames file the fatherless finding compassion under MACULA's Hos 14:4 and the builder keeps it there, while the Berean prints it at 14:3. A `moves` entry fixes the one verse; other shifted verses in Hosea 13-14, Joel and Jonah may exist and were not checked.
5. **Gloss strays in `others`** (the article ה glossed "Dothan" at Joel 2:17 and Neh 13:22; אִי "woe!" at Eccl 4:10). They are excluded by key (`h1886`, `h337`). The regex cannot say "not the article".
6. `lead` has no effect on a `pick` row (the pick order is the display order), so the picks are listed with the best examples first.
7. A row's example does not show which divine person a "He" is, and there is no per-example note. The panel's "He is righteous"-style handling is done here by separate one-verse rows.

## Files

- Spec: `<local> Ontology\ontology\concept-hubs\mercy.json`
- Built: `<local> Ontology\out\concept-hubs\mercy.json`
- Scratch scripts and dumps are in this folder (`mercy_*.py`, `mercy_*.txt`).

---

# Panel fixes (2026-10-10, "ship after fixes", 8 fixes; panel file `mercy-panel.json`)

Result: **23 rows** (8 verb, 11 noun, 4 adjective), one build, every verse still placed (compared with the 35-row build: nothing lost; Prov 28:13 gains a noun row and Rom 9:23 a verb row; Ps 103:13 is as before in the verb tab only). `shown` false.

## Applied (the panel's 8 fixes, with the coordinator's change to the first, and the 3 "missing")

| # | Panel item | What was done |
|---|---|---|
| 1 | Key verses Hos 6:6, Mic 6:8 (coordinator's change) | `own_words` is now verses of the hub's own words only, each checked in the original: Exod 34:6 (רַחוּם), Ps 103:13 (רָחַם), Lam 3:22 (רַחֲמִים), Matt 5:7 (ἐλεήμων, ἐλεέω), Matt 9:13 (ἔλεος), Rom 9:15 (ἐλεέω), Eph 2:4 (ἔλεος), Jas 2:13 (ἔλεος). Luke 6:36 is not an own word (οἰκτίρμων) and is not there. Hos 6:6 and Mic 6:8 are out of the key verses and are held in the חֶסֶד entry (item 2). |
| 2 | חֶסֶד entry in `others` | Hand-added Hos 6:6 and Mic 6:8 (first), with the entry note: the Berean prints "mercy" for חֶסֶד in a few verses, the rows of this page are built on another word, חֶסֶד is set out under Love. The entry now has 4 verses (Hos 6:6, Mic 6:8, 1 Kgs 20:31, Ps 23:6). **Done by a post-build patch, see "Builder gap" below.** |
| 3 | “I desire mercy, not sacrifice” note | Opens with Hosea 6:6 in the Hebrew (חֶסֶד, printed "mercy" there, usually "loving devotion", see Love), then Matthew's ἔλεος; "They are two words" removed; says the hub's rows are built on the Greek ἔλεος and the Hebrew רחם words and Hosea's word is under Love. Door to Love added. |
| 4 | “Now you have received mercy” | Prov 28:13 moved to "Compassion, and forgiveness" (next to Isa 55:7, where the repentance note applies; row now 7). 1 Pet 2:10 is first in the "received" row. Row note: each verse gives its own reason, or none; the page takes no side on what mercy depends on. |
| 5 | Mercy and peace | Jer 16:5 taken out by `not_verses` (a withdrawal, not a greeting). It stays in "Compassion beside חֶסֶד" and "Mercy shown, and no mercy shown". Row now 5. |
| 6 | No compassion, no mercy, no pity | Note: Zech 1:12 is a question put to the LORD, "How long?"; the verses are said of the LORD, of the enemy He raises, or asked of Him. |
| 7 | “Have mercy on me” | Relabelled “Have mercy on me, on us”; note: the cry in the Gospels, to Jesus, and from the rich man to Abraham, "my son" in Matt 17:15; the Hebrew cry of Ps 51:1 is another word, חָנַן, under Other words (see Grace). Door to Grace added. Ps 51:1 not added. |
| 8 | Every other use (noun) | Note: Rom 9:23 belongs with Rom 9:15-18 and Rom 11:31 with Rom 11:30-32; the page takes no side. Also (coordinator) Rom 9:23 added to the verb row "I will have mercy on whom I have mercy" (now 5), whose note now says Rom 9:23 continues the passage; the no-side note stays. Rom 9:23 stays in the noun catch-all as well. |
| m1 | תַּחֲנוּן "plea for mercy" | Another word, not an own word, so shown apart in `others` (by the same patch): תַּחֲנוּן 11 verses (Job 41:3, Ps 28:2, 28:6, 31:22, 86:6, 116:1, 130:2, Prov 18:23, Jer 3:21 added to Dan 9:3 and Jer 31:9) and תְּחִנָּה 2 (Ps 6:9, Josh 11:20), each with a note. Ps 116:1 and the rest: verified by lemma in the verse. |
| m2 | Hos 1:6 / 2:23 to 1 Pet 2:10 | Notes on the three rows that hold them: the "received mercy" row (1 Pet 2:10 answers Hosea's "No Compassion", Hos 1:6 and 2:23), the LORD row (Hos 2:23), and the no-compassion row (Hos 1:6). |
| m3 | Luke 6:36, Jas 5:11 | Luke 6:36 and Jas 5:11 are other words (οἰκτίρμων; πολύσπλαγχνος, οἰκτίρμων), already in `others`. Pointer notes added on "Show mercy to others" (Luke 6:36) and on the adjective row "The LORD is compassionate, merciful" (Jas 5:11). |

Not changed, as the panel judged them fine: the Rom 9:15-18 grouping, Mercy through disobedience, Not our deeds but His mercy, Mercy and peace (Gal 6:16 note), the forgiveness note, "the Lord" rows, divine persons by hand, the hard verses, alms, σπλαγχνίζομαι, ἱλάσκομαι/ἵλεως/חנן apart.

## Re-check of the first four examples of every changed row (Berean text)

- Have mercy on me, on us: Matt 9:27 ("Have mercy on us, Son of David"), 15:22, 17:15 ("on my son"), 20:30. Show their label.
- “Now you have received mercy”: 1 Pet 2:10, 1 Cor 7:25, 2 Cor 4:1, 1 Tim 1:13. Show it.
- Compassion, and forgiveness: 1 Kgs 8:50, Isa 55:7, Prov 28:13 ("will find mercy" beside confessing sins), Ps 78:38. Show it.
- “I will have mercy on whom I have mercy”: Exod 33:19, Rom 9:15, 9:18, 9:16; Rom 9:23 ("the vessels of His mercy") is the fifth. Show it, with Rom 9:23 the continuation named in the note.
- Mercy and peace: 1 Tim 1:2, 2 John 1:3, Jude 1:2, Gal 6:16. Show it; Jer 16:5 no longer in the row.
- No compassion, no mercy, no pity: Isa 9:17, 13:18, 27:11, Jer 6:23 (unchanged examples; the note now says which verses ask).
- “I desire mercy, not sacrifice”: Matt 9:13, 12:7 (unchanged).
- The key verses: all eight read in the Berean and each is a verse of the hub's own words.
- Others entries: Hos 6:6 ("I desire mercy, not sacrifice"), Mic 6:8 ("to love mercy"), Ps 28:2 ("cry for mercy"), Josh 11:20 ("receive no mercy"), Ps 6:9 ("cry for mercy") read in the Berean.

## Builder gap (needs your decision)

`hub_build.py` has no way to put a hand list of verses, or a note, on an `others` word, and `others` reads MACULA's gloss, not the Berean's printed word. So items 2 and m1 are applied **after the build** by `mercy_others_patch.py` (this folder), which reads the spec's `others.add` key (the builder ignores it) and rewrites the three entries (h2617, h8469, h8467) in `out/concept-hubs/mercy.json`, adding `note` and `hand_added` fields. **A rebuild loses the patch** until the builder reads `others.add` and the app shows a per-word `note`: re-run the script after every build, or give the builder an `others.add` option ({word key: {verses, note}}, new verses first) and the UI a per-word note. If the app is not changed, the notes are not seen, but the verses are.

Everything else is in the spec and survives a rebuild.
