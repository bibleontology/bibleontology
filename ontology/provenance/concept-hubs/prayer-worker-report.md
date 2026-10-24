# prayer hub: report

Spec: `ontology/concept-hubs/prayer.json` (`"shown": false`). Built file: `out/concept-hubs/prayer.json`. 26 rows (16 verb, 10 noun); 200 verb verses and 143 noun verses; "More" is 0 in both. 26 is the count of righteousness; the row that could go first is the noun "Prayer and fasting" (its four verses would fall to the catch-all).

Builds: I loaded the graph once into a small local HTTP wrapper that calls `hub_build.build()` on the spec (no builder edit, same output file), so the "five builds" came to about six runs of the real function over one load.

## Rows

Verb section, "Who prays, to whom, and for what" (lead):

| Row | n | How filled |
|---|---|---|
| Jesus prays | 22 | pick (frames agent Jesus, each verse read) |
| Prayer to the Father | 5 | pick (Matt 6:6, 6:9, Luke 11:2, Matt 26:39, 26:42) |
| Prayer to "the Lord" | 3 | pick (Acts 1:24, 8:22, 8:24), note: referent not chosen |
| Prayed to the LORD, to God | 44 | in_clause יהוה / אֱלֹהִים / θεός, 6 not_verses |
| Prayed for others, on their behalf | 29 | in_clause בַּעַד / ὑπέρ / περί, 3 not_verses |
| Asked to pray for them | 13 | pick |
| Told to pray | 33 | stance command, 3 Jeremiah not_verses |
| "Do not pray for this people" | 3 | pick (Jer 7:16, 11:14, 14:11) |
| He intercedes for us | 4 | pick (Rom 8:26, 8:27, 8:34, Heb 7:25), note |
| Prayer and the Spirit | 7 | pick, note |
| Prayer for show, with many words | 4 | pick (Matt 6:5, 6:7, Mark 12:40, Luke 20:47) |
| Prayer toward this house, this place, this city | 19 | pick (1 Kgs 8; 2 Chr 6; Jonah 2:7; Dan 6:10) |
| Prayer, confession and forgiveness | 12 | in_verse, 1 not_verse (Matt 26:44) |
| Prayer and healing | 6 | in_verse, note |
| Prayer and fasting | 4 | in_verse |
| Every other use: prays, prayed | 55 | catch-all |

Noun section, "What the text says of prayer":

| Row | n | How filled |
|---|---|---|
| A house of prayer, a place of prayer | 6 | with בַּיִת / οἶκος adjacent, plus add Acts 16:13, 16:16 |
| "A prayer of David": prayers named for who prayed them | 7 | pick (Ps 17:1, 86:1, 90:1, 102:1, 142:1, 72:20; Hab 3:1) |
| Prayer and petition | 18 | with the two words side by side (adjacent 4) |
| Hearing and answering prayer | 48 | in_verse שָׁמַע / אָזַן / קָשַׁב / ἀκούω family / עָנָה, 5 not_verses |
| The prayer of the righteous, of the wicked | 5 | in_verse, 2 not_verses |
| Prayer rises before God, like incense | 7 | pick, note |
| Prayer with thanks, and "remembering you in my prayers" | 8 | in_verse εὐχαριστέω / εὐχαριστία / μνεία / μνημονεύω / תּוֹדָה |
| Devoted to prayer, night and day | 10 | in_verse προσκαρτερέω / γρηγορέω / ἀγρυπνέω / νύξ, plus add Neh 1:6 |
| Prayer and fasting | 4 | in_verse |
| Every other use: prayer, petition | 54 | catch-all, with a note on petitions made to men |

## Words and `others`

Words (uses in the prayer sense / uses dropped by the sense rule): προσεύχομαι 79/2, προσευχή 36/0, פָּלַל 79/3, תְּפִלָּה 70/0, δέομαι 9/13, δέησις 16/0, עָתַר 17/2, תְּחִנָּה 22/2, תַּחֲנוּן 16/2, Aramaic בָּעוּ 2/0, בעה 3/9, צלה 2/0, ἐντυγχάνω 4/1, ὑπερεντυγχάνω 1/0, εὐχή 1/2.

The sense rule (`^(?!I pray$).*(pray|supplicat|petition|interced|intercess|entreat|\bpleas?\b)`) keeps a word only where its verse renders it as prayer:
- δέομαι is begging a person as often as praying (Luke 8:28, Acts 21:39, 2 Cor 5:20 are out).
- Acts 8:34 is out (the eunuch asks Philip; MACULA's gloss is "I pray").
- פָּלַל drops Ezek 16:52, Gen 48:11 and Ps 106:30.
- בעה is "ask, seek" in nine of twelve verses.
- תְּחִנָּה is "grace, mercy" in Ezra 9:8 and Josh 11:20.

`sense_keep` (Berean has the word, MACULA's gloss does not): Luke 22:32 ("I have prayed for you"), 1 Thess 3:10, Matt 9:38 ("Ask the Lord of the harvest", the same saying as Luke 10:2), Rom 11:2 ("appealed to God against Israel").

`others` (different words the English renders pray / petition / intercede, named apart): שְׁאֵלָה "petition" 9, חָלָה "entreat" 8, פָּגַע "intercede" 5 (Isa 53:12; Jer 7:16; 27:18 and others), חָנַן 5, εὔχομαι 4, ἔντευξις 2, ἱκετηρία 1.

## Sample: 16 random verses, then one more per row

Random draw of 16 from deeper than the first examples (seed 7), each read in the Berean through `/api/verse`. All 16 show their row.

Luke 9:18 (Jesus prays), Exod 10:17 (Prayed to the LORD), Num 21:7 (Prayed for others), Jer 37:3 (Asked), 1 Cor 14:13 (Told), Zech 12:10 (Spirit), 1 Kgs 8:42 (toward this place), 2 Chr 7:14 (confession and forgiveness), Isa 45:14 (catch-all; see below), Ps 142:1 (prayer of David), 2 Chr 6:39 (petition), 2 Chr 6:21 (hearing), Rev 5:8 (rises like incense), Col 4:2 (thanks), Eph 6:18 (devoted), Lam 3:8 (noun catch-all).

Tally: 16 of 16 show their label's claim. Two caveats: Isa 45:14 (label is only "every other use"; the Berean prints no prayer word, see below) and Luke 9:18 (Jesus is named in this verse; many of his other rows are not, see below).

I also read one verse for every row of the final build (26 verses, mostly first examples): 26 of 26 pass. The fixes below came from reading whole rows (all verses of the larger rows) after the first build.

Fixes made after reading:
- "Prayed to the LORD, to God": Rom 8:27 ("according to the will of God" is the measure, not the one prayed to), Phil 1:9, Col 4:3, 1 Sam 2:25, 2 Sam 21:14 and 24:25 (the last two tell an answer, not a prayer made) removed with reasons.
- "Prayed for others": Rom 8:27, Rom 8:34 and Heb 7:25 removed (their own row; the page does not set Christ's and the Spirit's intercession beside human prayer).
- "Told to pray": the three Jeremiah prohibitions are not commands; they have their own row.
- "Prayer, confession and forgiveness": Matt 26:44 removed (ἀφίημι is "left").
- "Hearing and answering prayer": Isa 37:4, 2 Kgs 19:4 (the Rabshakeh's words), Prov 18:23, Jer 37:20 (a petition to a man), Prov 28:9 (the hearing is of the law) removed; אָזַן / קָשַׁב added so "give ear" counts (Ps 86:6, 143:1, 17:1).
- "The prayer of the righteous, of the wicked": Jer 31:9 (יָשָׁר is a level path) and Ps 141:5 removed.
- `sense`: Acts 8:34 dropped.

## Contested points for the panel

1. **"Jesus prays", 22 verses, by pick.** Most name Jesus only as "He" (Matt 14:23; 26:39, 26:42, 26:44; Mark 6:46, 14:35, 14:39; Luke 5:16, 22:41, 22:44) or speak as him (Luke 22:32 "I have prayed for you"). The Greek frames give Jesus as the agent and the surrounding narrative does too, so I picked them. If the panel wants "text names him" strictly, the unnamed ones would move to a row with a note. Heb 5:7 names Jesus.
2. **"Prayer to the Father"** (Matt 6:6, 6:9, Luke 11:2, Matt 26:39, 26:42): picked, each verse names the Father. Traditions differ on the Lord's Prayer as a set prayer; the row does not call it one and says nothing about use.
3. **"Prayer to 'the Lord'"** (Acts 1:24; 8:22, 8:24): the text says "the Lord"; readers take it of the Father or of Jesus; the note says the page does not choose. Prayer to Jesus by name is not a row: no verse with a prayer word (προσεύχομαι, δέομαι, δέησις) names Jesus as the one addressed.
4. **"He intercedes for us"** (Rom 8:26-27 Spirit; Rom 8:34, Heb 7:25 Christ): one row, note. Catholic / Orthodox / Protestant readers differ on what this is; the row sets the verses side by side and these verses are removed from "Prayed for others" so human and divine intercession are not equated. Isa 53:12 (the Servant "made intercession", פָּגַע) is a different word and is in `others`, not here.
5. **"Asked to pray for them"** (13 verses): people in the text asking another living person to pray for them. This is the only text for "intercessors" the hub gives; there is no verse here in which anyone asks someone who has died. The note says only what the row is. Prayer to saints or the Virgin is absent because the text has no prayer-word verse for it; no row implies it.
6. **"Prayer rises before God, like incense"** (Ps 141:2, Jonah 2:7, 2 Chr 30:27, Acts 10:4, Rev 5:8, 8:3, 8:4): Rev 5:8 and 8:3-4 say "the prayers of the saints" held or offered by the elders and an angel. Catholic / Orthodox readers take this for intercession by or through those in heaven; Protestant readers mostly do not. The row keeps the text's picture and the note says the page takes no side. Only these seven verses are in it; the row does not link to the saints' card as an authority, only as a door.
7. **"Prayer and the Spirit"** (Eph 6:18, Jude 20, 1 Cor 14:14-15, Acts 4:31, 8:15, Zech 12:10): Pentecostal / Charismatic, Catholic (Acts 8:15 and confirmation), and Reformed readings differ. 1 Cor 14:14-15 ("my spirit prays", "in a tongue") is the text's, in the row with the note; there is no row on tongues as a practice. Whether "my spirit" is the human spirit or the Holy Spirit is in the note.
8. **"Prayer, confession and forgiveness" and "Prayer and healing"**: verses that name both, as written (Jas 5:14-16, Mark 11:25, Acts 8:22; Jas 5:14-16, Acts 28:8). Notes say the page takes no side on confession or on anointing. The verses are grouped by co-occurrence only; nothing says prayer causes either.
9. **"Prayed to the LORD, to God"** is filled by a rule on the words in the verb's clause, not by pick. It reads only the text's own יהוה / אֱלֹהִים / θεός in the verb's own clause (no κύριος, no πατήρ), with 6 hand exclusions. Love's divine rows are by rule on a divine set, so I followed that; if the panel wants every divine row by pick, this one is 44 verses.
10. **"Told to pray"** is any imperative, and it includes people ordering or begging prayer (Pharaoh, Zedekiah, Simon), which the note says. It is by stance, not by pick.
11. **פָּלַל** also means "intercede, judge": the 3 verses of 82 that are not prayer are dropped. Num 21:7, 1 Kgs 13:6 and 1 Sam 2:25 render it "intercede" in the Berean and stay (prayer of intercession to the LORD); Ps 106:30 ("intervened", Phinehas) is out because the Berean does not say prayer.
12. **Isa 45:14** is in the catch-all because the Hebrew verb is פָּלַל ("they will pray / make supplication to you", MACULA gloss "make supplication"), but the Berean prints "they will confess to you". The original is followed; a mark on this verse is probably wanted ("where the original reads otherwise, an asterisk and our finding").
13. Tongues, set or liturgical prayer, the Rosary, the Hours, kneeling and the posture of prayer, and the Lord's Prayer as a recited text are in no row. Kneeling and lifted hands are in verses (1 Tim 2:8; Acts 20:36) that sit in the catch-all, with no row about posture.

## What the builder could not express

- **A row that requires two of the concept's words together** (e.g. prayer with a thanks word AND a hope word), and **a negative condition on a word elsewhere in the verse** ("not_in_verse"). I used `not_verses` with reasons instead. A global `drop` for a verse (remove it from every row and "More", for a verse the sense rule cannot exclude but I want out of the hub: Acts 8:34 was handled by the sense regex only because the gloss was exactly "I pray") would have been cleaner.
- **A row for "prayer and faith"** (Matt 21:22; Mark 11:24; Jas 5:15): `in_verse` for πίστις / πιστεύω would catch Luke 22:32, 1 Thess 3:10 and Acts 14:23 as well, where faith is not the manner of the prayer. I left it unmade rather than let the label overreach; those verses are in the catch-alls. It could be added with a `pick`.
- **`pick` covers both forms**, but a row only appears in the section of its `form`, so a topical row (fasting) has to be made twice (verb and noun) to show both. I did that for fasting only.
- **Prepositions as objects**: "prayed to" is the word after אֶל / the dative in the verb's own clause; the builder has only the clause's whole word-set (`in_clause`), so a God named in the clause as the one who will act (Col 4:3, Phil 1:9, Rom 8:27) is read as the one addressed unless I exclude it by hand (done, with reasons).
- **`add`/`pick` verses with no concept word are refused or silently unplaced** (Isa 53:12, whose word is פָּגַע, cannot be added to the intercession row).

Files: `<local> Ontology\ontology\concept-hubs\prayer.json`, `<local> Ontology\out\concept-hubs\prayer.json`.

## Panel fixes (2026-10-10)

Panel verdict: "ship after fixes", 12 fixes plus three "missing" items. Rebuilt with the changed builder (verses now in the Bible's order). Rows: 26 (15 verb, 11 noun). The four examples of every row were re-read in the Berean text after the rebuild; all show their labels. Verses read deeper for the new rows (Ps 80:4, Lam 3:8, 3:44, Prov 28:9, 1 Pet 3:7, Acts 28:8, Jas 5:15, Luke 22:44) also pass.

Applied (12 of 12 fixes, plus 2 of 3 "missing"):
1. Matt 19:13 moved out of "Jesus prays" (21 now) into "Asked to pray for them" (14); a note on "Jesus prays": where a verse says only "He", the verses just before name Jesus; Luke 22:43-44 is absent from some early manuscripts.
2. "Prayed to the LORD, to God" relabelled "Praying to the LORD, to God".
3. "Prayed for others" relabelled "Praying for others, on their behalf"; Jer 7:16, 11:14, 14:11 dropped from it (26 now), they stay in "Do not pray for this people".
4. New noun row "Prayer not heard, shut out, hindered" (9: Isa 1:15, Jer 7:16, 11:14, Ps 35:13, 80:4, Lam 3:8, 3:44, Prov 28:9, 1 Pet 3:7); Isa 1:15, Jer 7:16, 11:14 and Ps 35:13 taken out of "Hearing and answering prayer" (44 now).
5. "Prayer rises before God, like incense" relabelled "Prayer goes up to God; prayers and incense"; note now says incense is in Ps 141:2 and Rev 5:8, 8:3-4 and that in Rev 5:8 the bowls are before the Lamb; the old note sentence kept.
6. "Prayer and the Spirit" relabelled "Prayer and the Spirit, or the spirit"; Zech 12:10 listed first; note adds the Hebrew ("a spirit of grace and supplications", poured out by God).
7. "Prayer and healing": note says what is healed in Gen 20:17, 2 Chr 7:14, Isa 19:22; Hebrew verses first; Jas 5:15 added. Because Jas 5:15's prayer word is a noun (εὐχή) a rule on the verb cannot reach it, so the row is now by pick (7 verses).
8. "Prayer, confession and forgiveness": note reworded (Israel's own prayers of confession first, then the New Testament; the Christian-tradition sentence kept).
9. "Prayer for show, with many words" relabelled "Praying to be seen; "babbling" like the pagans", with the panel's note.
10. Neh 1:11 and 1 Kgs 8:52 taken out of "Prayer and petition" (16 now).
11. "He intercedes for us" relabelled "The Spirit intercedes; Christ intercedes"; note kept.
12. Verb catch-all note added (idols Isa 44:17, 45:20; foreign sanctuary Isa 16:12; a king Dan 6:7, 6:12; Isa 45:14 with the Hebrew verb and the Berean's "confess").
- "Prayer and faith" (named "Prayer and believing"): new noun row, pick of Matt 21:22, Mark 11:24, Jas 5:15.
- John 17: added to `others` as ἐρωτάω (g2065) with its three verses (17:9, 17:15, 17:20) and a note that the Greek word is "ask", not the prayer verb, so it is named apart. Jesus' own prayer thus has a place without handing one word over as the other.
- Also: "righteous / wicked" row given a `lead` so its examples are the verses that show the label (the order fix had put Ps 109:7 first).

To hold the count at 26 I cut both "Prayer and fasting" rows (verb and noun); the fasting verses stay in the catch-alls and "Devoted to prayer" (Luke 2:37). Put them back if the panel wants fasting named.

Not done, with reasons:
- **Isa 45:14 asterisk in the verse**: the panel asks for the project's mark at "confess" in the verse text. That is a verse-text mark of the app (vmarks), not something the hub spec holds; the catch-all note carries the finding, and the mark itself is left to whoever owns vmarks.
- **Acts 7:59-60** ("Lord Jesus, receive my spirit", ἐπικαλέομαι) as prayer addressed to Jesus by name: a divine-person placement, so it needs Doug's per-record decision. Left out; listed here. Acts 7:59 reads "Stephen appealed, 'Lord Jesus, receive my spirit'". If he approves, it would go in as an `others.add` of ἐπικαλέομαι (g1941) with a note, or in a pick row by name.
