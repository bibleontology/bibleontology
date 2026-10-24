# Grace hub: report

## Revision 2 (consolidation, 2026-10-10): 46 rows -> 24

Result line: **grace, 24 rows (19 noun, 4 verb, 1 adjective); 16-sample after the change 16 of 16.** This round used two builds (one through the scratch wrapper, one official).
The pre-consolidation spec is kept at `scratchpad/hubs/grace-v46.json`; `scratchpad/hubs/consolidate.py` regenerates the new spec from it.

**Two builder changes taken up**
- `"forms": {"h2603": "verb"}`: the occurrences are keyed h2603 (`S.occurrences` finds 72 there; h2603a/b have none), so חָנַן is now in `words` as a verb. The verb rows catch it by the frames' agent: 35 verses in one rule row (a prayer, a wish, a promise, a report, with God or the LORD as the one who is gracious), against 92 verses placed by hand before. Words now: χάρις 131, χαριτόω 2, χαρίζομαι 19, חֵן 66, חַנּוּן 13, חָנַן 71 (the card now lists the verb, with 1 other-sense verse, "loathsome").
- `"moves": {"Hos.12.5": 12.4}`: works; Hos 12:4 ("sought His favor") now comes through the rule path.
- `sense_keep` (also new) keeps what the gloss filter would drop: the 15 hithpael verses of חָנַן (Berean "plead", "make supplication"; MACULA "seek favor") and Acts 25:11, 25:16 (χαρίζομαι "give up"). Without it the "Seek favor, plead" row would have been blank of word names. `h2603` is no longer excluded from "Other words" (it is the hub's own).

**One remaining gap**: Ps 109:12 (חָנַן, "no one to favor his fatherless children") has no entry in the frames, so no verb row can reach it (neither the rule nor `add`). It is picked into the noun row "Favor and grace between people". Needed: let the verb path fall back on the clauses when a word's verse has no frame, or let `add` place a verse the frames never saw.

**Before and after (nothing dropped: 215 noun, 91 verb, 13 adjective verses all still placed; verb 92 -> 91 only because Ps 109:12 moved to the noun side as above; Hos 12:4 is the one verse that moved by `moves`)**

| after (24) | n | was (46) |
|---|---|---|
| Find favor, find grace; favor given | 51 | Find favor 45 + Favor given 6 |
| Grace given (note) | 15 | same |
| The grace of God | 23 | same |
| The grace of the Lord Jesus, grace in Christ Jesus (pick) | 11 | same |
| A spirit of grace (pick) | 2 | same |
| Grace beside truth, kindness, mercy and steadfast love (note) | 9 | Grace and truth 3 + Grace beside kindness... 6 |
| Grace and faith (note) | 10 | same |
| Grace and works | 6 | same |
| Grace and the law | 7 | same |
| Grace and sin | 9 | same |
| Grace and being justified (note) | 6 | same |
| Grace and being saved, redeemed, forgiven | 8 | Grace and being saved 6 + Grace, redemption and forgiveness 2 |
| Grace and being called, chosen (note) | 5 | same |
| Stand, continue, grow, be strengthened in grace; in vain, fallen away from, fallen short of it (note) | 10 | Fallen away 4 + Stand 6 |
| Full of grace; the word of His grace; grace to the humble; grace and glory; grace turned into a license | 21 | Full of grace 5 + The word of His grace 3 + Grace to the humble 3 + Grace and glory 10 + Jude 4 (1), less overlaps |
| Gracious lips and words; grace as charm, a garland, an adornment | 13 | Lips 6 + Charm 7 |
| Favor and grace between people: favor with God and man, a favor done or asked, the gift for the saints | 13 | Favor with God and man 3 + A favor done 4 + An act of grace 5, + Ps 109:12 |
| The same Greek word as thanks, credit, what is commendable | 17 | Thanks 12 + Credit 5 |
| The letters' greeting and closing | 32 | Greeting 17 + Closing 15 |
| verb: The LORD gracious: "Be gracious to me", "May He be gracious", "has been gracious" | 35 | Be gracious 21 + May the LORD be gracious 9 + He will be gracious 2 + God has been gracious 3 |
| verb: Seek favor, plead | 17 | same |
| verb: The Greek verbs of grace | 21 | Forgave 8 + Granted 7 + Highly favored 1 + Gave, released 5 |
| verb: Favor, kindness and pity shown or withheld: to the poor, between people, to the wicked | 18 | Show favor to the poor 8 + Shown no favor 5 + Pity... 6, less Ps 109:12 |
| adjective: Gracious and compassionate; called "gracious" | 13 | 11 + 2 |

Kept as asked: every contested row (faith, works, the law, sin, justified, saved, called) and its note; the Jesus and Spirit rows by pick; the hard verses (Jude 4, Nah 3:4, Prov 17:8, Prov 22:1, Eccl 9:11, Zech 4:7 stay, the last three in More). "Grace and being saved" now also takes redemption and forgiveness, so it is still the saved row, widened. Standing and falling are one row: they were set side by side before, and now sit together in one list, so the reader no longer sees them as two opposed sets; the note still says the page takes no side.

Cost of the merge a reviewer should weigh: the "Full of grace; the word of His grace; ..." row is a bucket of five small groups (21 verses) and the greeting and closing are one 32-verse list. Each part of their long labels is shown by verses in the row, but they are the least coherent rows. If the panel wants them split again, the old definitions are in `grace-v46.json`.

First examples re-checked for every changed row: all show their label (Gen 6:8, Ruth 2:2, Luke 1:30, Gen 39:21; John 1:17, Eph 2:7, Heb 4:16, Esth 2:17; Eph 2:8, 2:5, Acts 15:11, Eph 1:7; Rom 5:2, 1 Pet 5:12, Acts 13:43, Heb 13:9; John 1:14, 1:16, Luke 2:40, Acts 4:33; Ps 45:2, Prov 22:11, Eccl 10:12, Luke 4:22; Luke 2:52, Acts 2:47, 7:10, Gen 34:11; Rom 6:17, 7:25, 1 Cor 15:57, 2 Cor 2:14; 1 Cor 1:3, 1 Pet 1:2, 1 Thess 1:1, 1 Tim 1:2; Ps 4:1, Num 6:25, Gen 33:5, Exod 33:19; Deut 3:23, 1 Kgs 8:33; Eph 4:32, Rom 8:32, Luke 1:28, Acts 27:24; Prov 19:17, Ps 112:5, Deut 7:2, Isa 26:10; Exod 34:6, Ps 103:8, Joel 2:13, Jonah 4:2).

New 16-sample over the rule-driven verb row and the merged rows: Ps 41:10, Mal 1:9, Ps 102:13, Gen 43:29, Ps 119:58, Amos 5:15 (the LORD gracious); Job 9:15, Gen 42:21, Hos 12:4 (seek favor); Ps 37:26, Prov 14:21, Lam 4:16, Judg 21:22 (favor shown or withheld); Ps 109:12 (favor between people); Col 2:13, Phlm 1:22 (Greek verbs). **16 of 16 show their label** (Phlm 22 shows as "restored", named in the row's note).

What follows is the first-round report (46 rows), kept for the record; where it conflicts with the above, the above governs.

---

Spec: `ontology/concept-hubs/grace.json` (`shown: false`). Built: `out/concept-hubs/grace.json`.
Five builds (the last two through a scratch wrapper that calls the builder's own `build()` and then reads every verse's Berean text). Every door card exists (`cards missing: []`).

Result line: **grace, 46 rows (32 noun, 12 verb, 2 adjective), 16-sample: 13 clear, 1 partial (label widened), 2 failed (both fixed) -> 16 of 16 after fixes.**

## The words

Counted in the grace sense (the sense filter reads MACULA's gloss):

| word | form | in sense | other sense |
|---|---|---|---|
| χάρις | noun | 131 | 16 (thanks, credit, commendable, thankfulness; shown in their own rows, see below) |
| χαριτόω | verb | 2 | 0 |
| χαρίζομαι | verb | 17 | 2 (Acts 25:11, 25:16 "give up"; named in a row) |
| חֵן | noun | 66 | 1 (Prov 17:8 "magic"; picked into the charm row) |
| חַנּוּן | adjective | 13 | 0 |

Not in `words`, and why (all in `_words_why`):
- **חָנַן (h2603), the verb of the root.** The lexicon holds only `h2603a`/`h2603b`, so the builder cannot read it as a verb and files it as a noun. Its verses are set by hand in 12 verb rows, from the frames' agent, patient and stance. It is excluded from "Other words" by `exclude`.
- **χάρισμα (gift, 17)**: a different word, "gift" in the Berean. A row cannot be confined to one word of the hub, and 1 Cor 12's gifts would have flooded the grace rows. δωρεά and δῶρον likewise.
- **חֶסֶד**: a different word, named apart (below).

"Other words translated grace or favor" (`others`, gloss grace/gracious/favor, min_n 3 or every use):
רָצוֹן 18 (acceptance), פָּנֶה 17 ("lift up the face"), טוֹב 9, רָצָה 4, נֹעַם 4, **חֶסֶד 3** (Dan 1:9, Esth 2:9, Isa 63:7), חֲנִינָה 1 (Jer 16:13), חִין 1 (Job 41:12).
Note: חֲנִינָה is from the same root as חָנַן. It shows here only because every one of its uses is "favor". A reviewer may want it in the family.

## The rows (final counts)

**Noun (214 verses, 13 left in "More")**
- Find favor, find grace 45; Favor given 6; Grace given 15
- The grace of God 23; The grace of the Lord Jesus, grace in Christ Jesus 11 (by hand); A spirit of grace 2 (by hand); Full of grace, grace upon grace, grace upon them 5; The word of His grace, the good news of God's grace 3
- Grace and truth 3; Grace beside kindness, mercy and steadfast love 6
- Contested pairings, side by side (`match: all`): Grace and faith 10; Grace and works 6; Grace and the law 7; Grace and sin 9; Grace and being justified 6; Grace and being saved 6; Grace, redemption and forgiveness 2; Grace and being called, chosen 5; In vain, fallen away from, fallen short of grace 4; Stand, continue, grow, be strengthened in grace 6; The grace of our God turned into a license 1
- Grace to the humble 3; Grace and glory, honor 10; An act of grace: the gift for the saints 5; Gracious lips and words 6; Grace as charm: a garland, an adornment, graceful 7; Favor in the sight of God and of people 3; A favor done or asked 4
- Other senses of χάρις, marked as the same Greek word: Thanks, thankfulness, gratitude 12; Credit, what is commendable 5
- Formulas, last and apart: Grace and peace to you; grace, mercy and peace 17; The closing blessing 15

**Verb (92 verses; Hebrew rows by hand)**
Be gracious to me, to us 21; May the LORD be gracious; the LORD will be gracious 9; He will be gracious; You will show favor 2; God has been gracious, has graciously given 3; Show favor to the poor and needy 8; Shown no favor, no mercy 5; Seek favor, plead 17; Pity and favor between people, and to the wicked 6; Forgave, forgive 8; Granted, freely given 7; Highly favored 1; Gave, released, handed over 5.

**Adjective (13)**: Gracious and compassionate 11; Called "gracious" 2.

"More" (13 noun verses, no row): 1 Pet 1:13, 1 Pet 3:7, 1 Sam 16:22, 2 Cor 1:15, 2 Cor 12:9, 2 Thess 2:16, Acts 15:40, Deut 24:1, Eccl 9:11, Phil 1:7, Prov 13:15, Prov 22:1, Zech 4:7. Of these, 1 Sam 16:22, Deut 24:1 and Prov 13:15 are there on purpose, because the Berean's English does not show the row they would otherwise sit in; Acts 15:40 is "the grace of the Lord" with Lord left open.

## The 16-verse sample (not only first examples)

| # | verse | row | verdict |
|---|---|---|---|
| 1 | Esth 5:2 | Find favor | shows (found favor in his sight) |
| 2 | Deut 24:1 | Find favor | **failed**: Berean says "becomes displeasing", only "finds some indecency"; the Hebrew is "finds no favor". Fixed: `not_verses`, now in More |
| 3 | 1 Sam 16:22 | Find favor | **failed**: Berean "I am pleased with him". Fixed: `not_verses`, now in More |
| 4 | Rom 15:15 | Grace given | shows ("the grace God has given me") |
| 5 | Col 1:6 | The grace of God | shows |
| 6 | Gen 47:29 | Beside kindness, mercy | shows (found favor ... show me kindness) |
| 7 | Rom 4:4 | Grace and works | shows (the worker, credited as a gift) |
| 8 | Heb 13:9 | Stand, be strengthened | shows |
| 9 | Rev 1:4 | Grace and peace | shows |
| 10 | Eph 6:24 | Closing blessing | **partial**: "Grace to all who love our Lord", not "be with you". Fixed: row relabelled "The closing blessing: Grace be with you" and its note names the variant |
| 11 | Ps 119:29 | Be gracious to me | shows ("graciously grant me Your law") |
| 12 | Prov 28:8 | Show favor to the poor | shows ("kind to the poor") |
| 13 | Phil 1:29 | Granted, freely given | shows ("it has been granted to you") |
| 14 | Isa 30:19 | He will be gracious | shows |
| 15 | Hos 12:4 | Seek favor, plead | shows ("sought His favor") |
| 16 | Acts 25:11 | Gave, released, handed over | shows ("hand me over") |

Beyond the 16: every example and every pick in the hub was read in the Berean text by script, with a per-row word test. Found and fixed from that pass: Prov 13:15 under "Favor given" (Berean "wins favor"); Eph 4:29 under "Grace given" (a speaker's word "brings grace"); John 1:17, 2 Thess 2:16, Acts 14:3, Acts 20:32 under "Grace given" (what was given is the law, comfort, signs, an inheritance); Acts 2:47 under "being saved"; Gen 47:29 under "Grace and truth"; the greeting and closing verses (1 Tim 1:2, Titus 1:4, 1 Tim 6:21, Titus 3:15) under "Grace and faith"; Prov 22:1 and Acts 11:23 under "called, chosen"; Acts 3:14 and Phlm 22 under "Granted" (Berean "released", "restored"); Gen 34:11 moved to "A favor done or asked"; Hos 12:5 mistyped for 12:4.

## Contested points for the review panel

1. **"Grace given"** (15). Verses with "given", "grants", "gave". Note says the page takes no side on how or when grace is received (baptism, sacraments, prevenient, resistible, irresistible). Panel: Catholic, Orthodox, Wesleyan, Reformed, Lutheran, Pentecostal. Is the note enough, or should the row not exist?
2. **Grace and faith / works / the law / sin / justified / saved / called, chosen** (the nine pairing rows). Side by side, `match: all`, each verse in every row it fits, and notes on faith, justified and called. Specific points: Rom 11:6 and 2 Tim 1:9 stand with 2 Cor 9:8 ("abound in every good work") in "Grace and works"; Eph 2:8 is added to "works" because its sentence runs into 2:9 "not from works". Ordering is the verse-division order within each row, not a priority. Panel: Lutheran, Reformed, Catholic, Wesleyan, Orthodox.
3. **"In vain, fallen away from, fallen short of grace"** (Gal 5:4, Heb 12:15, 2 Cor 6:1, 1 Cor 15:10) beside **"Stand, continue, grow, be strengthened in grace"** (Rom 5:2, 1 Pet 5:12, Acts 13:43, Heb 13:9, 2 Tim 2:1, 2 Pet 3:18). Side by side, with a note taking no side on whether grace can be resisted or lost. Panel: Reformed (perseverance), Wesleyan, Baptist, Catholic. Check that 1 Cor 15:10 ("was not in vain") belongs in the first row.
4. **"Grace and being justified"** (6) with a note. Gal 2:21 and 5:4 are there because the verse names "righteousness through the law" and "justified by the law" beside grace.
5. **"The grace of the Lord Jesus, grace in Christ Jesus"** (11, by hand): "of Jesus/Christ" and "in Christ Jesus" in one row, because the text writes both. 1 Cor 1:4 and 2 Tim 1:9 and 2:1 are "in Christ Jesus", not "of". The Spirit row (Zech 12:10 "a spirit of grace", Heb 10:29 "the Spirit of grace") is by hand with a note that the Berean's capitalisation differs and the page does not say they are the same. 2 Cor 13:14 stands in the closing blessings: no gloss on the Trinitarian wording.
6. **"The grace of God"** (23) is a rule on the next word (`with` @divine, adjacent), as righteousness's "of the LORD, of God" is, not a hand pick. The brief says divine persons by hand; I read the text's own phrase as not an inference. If the panel wants it by hand it is a 23-verse pick list.
7. **Hebrew rows by hand.** "Be gracious to me, to us" (21 psalm and prophet verses) is labelled without "O LORD" because not every verse names him; "God has been gracious" has only verses that name God or the LORD; "He will be gracious; You will show favor" (Isa 30:19, Ps 102:13) is separate because the verse says only "He" / "You", and the note names the verse before.
8. **"Seek favor, plead"** (17): the Hebrew verb is the reflexive stem of "be gracious" (MACULA: "seek favor"); the Berean says plead, implore, make supplication. Grouping them is the original arbitrating over the translation; the note says so. A Jewish or academic reader may like it; a reviewer who wants only the Berean's own word under the label may not.
9. **"Forgave, forgive"** (8, χαρίζομαι): the Berean renders the verb of grace as forgive in Eph 4:32, Col 2:13, 3:13 and others. The note says the usual verb of forgiving, ἀφίημι, is another word, not counted. This touches the forgiveness hub.
10. **Different words, named apart.** "Grace beside kindness, mercy and steadfast love" (6) sets חֵן/χάρις, חֶסֶד and רַחֲמִים/ἔλεος side by side with a note that they are different words and the page does not say one is another. חֶסֶד is also in "Other words" with its 3 "favor" verses. The greeting "grace, mercy and peace" is in the formula row only, kept out of the pairing rows by `not_verses` (panel's "keep the greeting rows apart").
11. **χάρις as "thanks" and "credit"** (17 verses) in two marked rows at the foot. This is rule 6 (not one sense as the whole) paid for by rows that are not grace in the theological sense; the panel may prefer them only in the word card.
12. **"Grace as charm"** (Prov 1:9, 3:22, 4:9, 5:19, 17:8, 31:30, Nah 3:4): Nah 3:4 is "seductive mistress of sorcery" and Prov 17:8 "a bribe is a charm". Hard verses kept; the note lists the Berean's words.
13. **"The grace of our God turned into a license"** (Jude 4), one verse, kept for what it says.
14. **Greeting vs the rest**: two formula rows are last, with notes, per the panel.
15. **Left in More on purpose**: 2 Cor 12:9 ("My grace is sufficient") is an own_words verse but has no row; the hub shows it under More. A row for it would be one verse.

## What the builder could not express

1. **A verb the lexicon holds only as `hNNNNa`/`hNNNNb`** (חָנַן, h2603) is classed as a noun, so verb frames are not read and its verses fall into noun rows by the companion tests. Needed: read `pos` from the `a`/`b` key when the plain key has no entry (or let the spec say `"form": "verb"` for a word). Worked around with hand picks in verb rows.
2. **Versification.** The builder's `bsb()` leaves MACULA's Hebrew numbering for Hos 12 (Hebrew 12:5 = Berean 12:4: "sought His favor" is printed under 12:5, whose Berean text is another sentence). Probably the same for the Hebrew-numbered ends of Hosea 11-14, Joel, Jonah 1:17, Mal 3-4, Zech 2 and Dan 4. I used the Berean number in my picks.
3. **A row confined to one of the hub's words.** χάρισμα could not be in `words` without flooding the grace rows, and "thanks" (a sense of χάρις) could not be a per-row `sense`. Needed: a row key like `word: "g5486"` or a per-row `sense`.
4. **`pick: []` is a catch-all.** An empty pick list is falsy, so with `match: all` a placeholder row takes every unplaced verse (this happened in build 1 and put 75 verses under "The grace of Jesus Christ"). Not a problem once filled; worth a guard.
5. **Pick rows of sense-excluded or unlisted words carry no word names** (the thanks rows, all Hebrew verb rows show `words: []`), so the "which word is this" display is blank there.
6. **`not_verses` drops a verse into "More" with no reason shown** (Deut 24:1, 1 Sam 16:22, Prov 13:15). A way to show "the Berean renders this otherwise" next to it would serve the reader.
7. **Cross-reference of `others`**: it admitted חֲנִינָה (h2594) of the hub's own root and had no way to mark a word as "same family, different word".

---

## Panel fixes (2026-10-10, "ship after fixes")

Rows: 24 -> **26** (20 noun, 5 verb, 1 adjective): one row added for 2 Cor 12:9 and its neighbours, one for the five non-grace senses of the Greek verb (see below). Two builds (one through the scratch wrapper, one official). Every verse still placed (noun 218, verb 91, adjective 13). Pre-fix spec: `grace-v24.json`; scripts `panelfix.py`, `panelfix2.py`. Of the 26 numbered items below, 22 are applied as asked, 2 differently or in part (14, 19), and 2 not done (21, 25); the 3 "missing" items are all placed.

| # | panel fix | done |
|---|---|---|
| 1 | Stand/fall row: first screen both halves | lead Rom 5:2, 1 Pet 5:12, Gal 5:4, Heb 12:15 |
| 2 | Stand/fall: door | the one-sided door removed; the row has no door (the card stays in `gather`) |
| 3 | Stand/fall: 1 Cor 15:10 under "in vain" | relabelled "...grace received in vain, or not in vain; fallen away from it, fallen short of it"; note's first sentence replaced as written, no-side sentence kept |
| 4 | Acts 7:10 out of Grace given | `not_verses`; it stays in "Favor and grace between people"; 4th example now 1 Cor 1:4 |
| 5 | Grace given note: most are for a work or gift | added, with the no-side sentence kept |
| 6 | Works: note | added (grace against works; work done by grace or for it; no side) |
| 7 | Works: examples, Rom 4:4 and Eph 2:8 | examples Rom 11:6, 2 Tim 1:9, 2 Cor 9:8, Acts 14:26; the note says Rom 4:4 prints "gift" and Eph 2:8's sentence runs into 2:9 |
| 8 | Law: note with the Hebrew Scriptures | added (Exod 34:6, Num 6:25, Ps 103:8 are in the verb and adjective rows) |
| 9 | Sin: "trespass" | relabelled "Grace and sin, trespass" with the note on the two Greek words; Jude 4 added by `add` (and removed from the bucket) |
| 10 | Justified: "righteousness" | relabelled "Grace, being justified, righteousness"; note extended; 3rd example Gal 5:4 |
| 11 | Faith: note | "as the text has them" dropped; sentence on verses that only share a sentence added |
| 12 | Bucket: Prov 11:16, 2 Cor 8:19, Jude 4 | to the charm row, "Favor and grace between people" (already held it), and the sin row |
| 13 | Bucket: Hebrew verses visible, order | label drops the license part; order Prov 3:34 before its quotations, Ps 84:11 before the NT glory verses; examples John 1:14, Prov 3:34, Ps 84:11, Acts 20:32; note "Jas 4:6 and 1 Pet 5:5 quote Prov 3:34". Kept as one row (not split) |
| 14 | Greek verbs: non-grace senses | Acts 3:14, 25:11, 25:16, Phlm 22, Luke 7:21 moved. **Done differently**: into their own verb row "The same Greek verb in other senses", not the noun thanks/credit row. When I put them in the noun row the builder's verb catch-all took them back into the "shown or withheld" row (5 extra verses), because the catch-all takes every verb verse no verb row placed. The thanks/credit row keeps its label as before |
| 15 | God/the LORD gracious: label | "God, the LORD, is gracious: ..."; 4th example 2 Kgs 13:23 (not Exod 33:19) |
| 16 | The same: "mercy" note | added: the Berean prints the same Hebrew חָנַן as "have mercy" (Exod 33:19, Ps 6:2, 51:1), רַחֲמִים is another word |
| 17 | Ps 59:5 out of the first verb row | `not_patient` בָּגַד; it falls to the "withheld" row |
| 18 | Job 33:24 into the first verb row | `add` |
| 19 | Prov 26:25 to the charm/lips row | **in part**: added to "Gracious lips and words", but it also stays in the last verb row, because the builder's catch-all cannot drop a verb verse |
| 20 | Last verb row: label and examples | relabelled "...to the wicked, withheld in judgment or war"; examples Prov 14:21, Isa 26:10, Lam 4:16, Prov 19:17 |
| 21 | Ps 109:12 to the verb row | **not done**: the frames have no entry for it, and no verb row (rule, `add` or pick) can hold it. It stays in the noun row "Favor and grace between people", whose label now says "a favor done, asked or withheld"; More cannot show it either (not a seen verse). Needs the builder option named in revision 2 |
| 22 | Greeting examples | 1 Cor 1:3, 1 Tim 1:2, 1 Cor 16:23, Rev 22:21 |
| 23 | Spirit row label | "A spirit of grace (Zechariah); the Spirit of grace (Hebrews)" |
| 24 | Grace beside...: Esth 2:17 | 4th example now Gen 39:21 |
| 25 | "Other words" examples (1 Kgs 13:6, Prov 15:26) | **not done**: `others` takes no per-word examples (it shows the first two of the word's spread). Needs a spec key such as `eg` per word, or a gloss test on the shown examples |
| 26 | Grace of God note | now says the Berean sometimes prints "God's grace" / "the grace God has given" |

Missing items:
- **2 Cor 12:9**: new noun row "Grace in weakness and need; 'Has God forgotten to be gracious?'" (2 Cor 12:9, Heb 4:16, 1 Pet 5:10, Ezra 9:8, 2 Cor 9:8, Ps 77:9), door `my_grace_is_sufficient`, `the_god_of_all_grace`. It left More.
- **Ps 77:9 and Ezra 9:8**: neither is a word of the hub's rows (Ezra 9:8 is תְּחִנָּה h8467 glossed "grace"; Ps 77:9 the infinitive of חָנַן, filed in the occurrences under h2589 with the lemma shown as "כִּיד"), so both are picked into the new row, and the row's note says so. A data quirk worth knowing: h2589's lemma is wrong in the lexicon.
- **Luke 1:28**: stays in the Greek-verb row; label no longer says "highly favored"; the note names κεχαριτωμένη (a perfect participle of χαριτόω), the Berean's wording, and that traditions read the form differently and the page does not choose.

Re-check: the four examples of every changed row were read in the Berean text after the final build (Grace given, Spirit, truth/kindness, faith, works, law, sin, justified, stand/fall, bucket, weakness, lips, greeting, God gracious, Greek verbs, other-senses verb, shown/withheld): all show their label. Ps 77:9 reads "Has God forgotten to be gracious?" in the Berean.

Row count is 26 against the "about 15-25" guidance: fixes 14 and the missing 2 Cor 12:9 row each needed a row. If one must go, the least costly merge is the new verb row back into "The Greek verbs of grace", at the price of the builder's catch-all behaviour above (or after a builder fix letting a noun row hold verb verses).

### Panel fixes, second pass (the builder's new options): 26 -> 25 rows

Rows: **25** (20 noun, 4 verb, 1 adjective). One build (the official one; the spec before it is `grace-v26.json`, the script `panelfix3.py`). Words now: χάρις 131, χαριτόω 2, χαρίζομαι 14 (+5 other sense), חֵן 66, חַנּוּן 13, חָנַן 70 (+2 other sense).

| item | now |
|---|---|
| 14 (the five non-grace χαρίζομαι senses) | `sense_drop` for g5483 on Acts 3:14, 25:11, 25:16, Phlm 22, Luke 7:21: they leave the verb rows, and so the builder's verb catch-all can no longer take them. I judged a reader should still see them (rule 6, as the thanks and credit senses of the noun are shown), so they are picked back into the noun row, now "The same Greek words in other senses: thanks, credit, what is commendable, released, handed over, restored, sight given". The separate verb row is gone; the `sense_keep` entries for Acts 25:11, 25:16 are removed |
| 19 (Prov 26:25) | `sense_drop` for h2603: gracious speech, not favor shown. It is out of the verb rows and only in "Gracious lips and words" (the verb section is now 85 verses, "shown or withheld" 17) |
| 25 (Other words, examples) | `others.add`: פָּנֶה leads with 1 Sam 13:12, Mal 1:9, 2 Chr 33:12, Exod 32:11, each printing "favor", with the note that the Hebrew word is "face"; נֹעַם leads with Ps 90:17 and a note that Prov 15:26 prints "pleasant" and Zech 11 names a staff "Favor". Read in the Berean after the build: 1 Sam 13:12 and Mal 1:9 and Ps 90:17 show "favor"; the first two examples of every other word also show grace, gracious or favor (רָצוֹן, טוֹב "favorably", רָצָה, חֶסֶד, חֲנִינָה, חִין) |
| 21 (Ps 109:12) | unchanged: no rule can place it (a pick row cannot mix with the rules, and the frames have no entry for it), so it stays in "Favor and grace between people" under the label "...a favor done, asked or withheld...", and `_why` says so |

The `_why` of the Greek-verbs row, the shown-or-withheld row, the lips row, the other-senses row, the "favor between people" row and `others` were updated to say what `sense_drop`, `others.add` and the move now do. Every verse is still placed (noun 223, verb 85, adjective 13: the 6 verb verses moved to the noun side are the five χαρίζομαι ones and Prov 26:25, which was already in the lips row). The four examples of the changed rows were re-read: the other-senses row opens on Rom 6:17, 7:25, 1 Cor 15:57, 2 Cor 2:14 (thanks), as before, and its five verb verses (Acts 3:14 "released", 25:11 "hand me over", Phlm 22 "restored", Luke 7:21 "gave sight") are named by its note.
