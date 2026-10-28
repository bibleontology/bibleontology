# Blessing hub: report (third round, 2026-10-25)

Spec: `ontology/concept-hubs/blessing.json` (`"shown": false`). Built file: `out/concept-hubs/blessing.json`. Built 4 times (a trial skeleton to read the verse lists, then three).

## Rows (25: 13 verb, 7 noun, 5 adjective; the three "Every other use" rows counted)

Verb section, "Who blesses, and whom" (342 verses)

| n | row |
|---|---|
| 41 | God blessed: the living creatures, the man and the woman, the seventh day; "the LORD has blessed him" |
| 20 | "I will bless you", "all the families of the earth will be blessed through you": God's word to Abraham, Sarah, Ishmael, Isaac and Jacob; and the verses that speak of the nations blessed |
| 26 | "The LORD your God will bless you": said to Israel in the law, in the land and in the work of their hands |
| 30 | A father's blessing: Isaac to Jacob and Esau, Jacob to Joseph's sons and to his own, Moses to the tribes |
| 26 | The priests, Moses, Joshua, David and Solomon bless the people in the LORD's name: "The LORD bless you and keep you" |
| 9 | Balaam, hired to curse Israel, blesses them |
| 49 | People bless one another and call one another blessed (includes the verbs אָשַׁר and μακαρίζω, "call blessed") |
| 6 | A request for God's blessing |
| 89 | "Blessed be the LORD", "Bless the LORD, O my soul": people bless God (בָּרוּךְ, εὐλογητός, εὐλογέω) |
| 11 | Jesus blessed: the children, the loaves and fish, the bread, His disciples; "the cup of blessing that we bless" |
| 9 | Blessing set against cursing |
| 13 | Where the Berean prints "curse", "greet" or "congratulate": the same Hebrew word |
| 15 | Every other use |

Adjective section, "Blessed is...: who is called blessed" (100 verses): 45 "Blessed is the one who..." (the Old Testament beatitudes, Rom 4:7-8 quoting Ps 32); 16 "Blessed are the poor, those who mourn, the meek, those who hunger, the persecuted; if you suffer..."; 26 "Blessed is the one who..." in the rest of the New Testament; 8 "Blessed is He who comes in the name of the Lord"; 5 Every other use.

Noun section, "What the text says of blessing" (81 verses): 13 The blessing and the curse; 10 A blessing pronounced or bestowed (Isaac's, Moses'); 16 Where the verse names harvest, barns, flocks, meat, rain, land, riches or children with the blessing; 15 Blessing beside the righteous, life, the Spirit and Christ; 8 "You will be a blessing", "May Your blessing be on Your people", "rich blessings"; 11 Blessing as a gift of goods (and where the Berean prints "peace" or "generous"); 8 Every other use.

The verb section is led (the brief's blessing is mostly something someone does or says).

Why so many rows: the three senses the brief asks to keep apart (God's favour, the spoken word, the gift of goods) each need their own rows, and the Hebrew verb, the noun and "Blessed is..." are three different sections. Rows that could join if the owner wants fewer, in order of how little they lose: "A request for God's blessing" (6) into "The priests, Moses..." or "Every other use"; "Balaam" (9) into "People bless one another"; "Blessing set against cursing" (9) into "Where the Berean prints curse..."; "You will be a blessing" (8) into "Every other use" (noun).

## The words and "others"

Words (12): Hebrew בָּרַךְ (verb, 286 verses in the sense), Aramaic בְּרַךְ (Daniel, 4), Greek εὐλογέω (39), ἐνευλογέω (2), εὐλογητός (8); Hebrew noun בְּרָכָה (64), Greek εὐλογία (14); and the "blessed is" family: Hebrew אֶשֶׁר (אַשְׁרֵי, 42), Greek μακάριος (49), Hebrew אָשַׁר (9) and Greek μακαρίζω (2), "call blessed", and μακαρισμός (3). The card listed the last five as "other words"; they are brought in because the Greek Old Testament renders אַשְׁרֵי by μακάριος (38 of 38) and אָשַׁר by μακαρίζω, and because the card's own word list already held אֶשֶׁר. The Hebrew and Greek are not said to be one word; every verse names its word. The section note says that אַשְׁרֵי / μακάριος declare a state ("Blessed is the one who...") where בָּרַךְ / εὐλογέω give or ask for a blessing.

`others`: none. The builder looked for any other word the Berean renders "bless", "blessed", "blessing" often enough to be named (threshold 5 verses or 25% of the word's uses) and found none, so there is no "Other words" section and the spec has no `others` key (the About view and the front end should not expect one). "Praise" (הָלַל, αἰνέω) and "give thanks" (יָדָה, εὐχαριστέω) are different words with their own hubs; the cup Jesus "gave thanks" over (Matt 26:27) is εὐχαριστέω and is not here.

Senses: kept in the hub by `sense_keep` because the Berean prints another English word for the same Hebrew or Greek: בְּרָכָה as "gift" (Gen 33:11, 1 Sam 25:27, 30:26, 2 Kgs 5:15), "peace" (2 Kgs 18:31, Isa 36:16: "make a blessing with me") and "generous" (Prov 11:25); the same Hebrew בָּרַךְ as "curse", "greet" and "congratulate" (13 verses, own row); εὐλογία as "flattery" (Rom 16:18); μακάριος as "fortunate" (Acts 26:2). Dropped as another sense: בָּרַךְ "kneel" (Gen 24:11, 2 Chr 6:13, Ps 95:6), Aramaic "knees" (Dan 6:10), אָשַׁר "go straight, lead" (6 verses).

## 16-verse sample (read in the Berean text from the server)

Tally: 16 sampled; 9 showed their row's label as built; 7 did not and were fixed (4 by moving the verse, 3 by widening the label); after the rebuild all 16 show their label. Three more found while reading, outside the sixteen, were also moved (Ps 41:2, Ps 49:18, Ps 112:2 / 128:4).

| verse | row | verdict |
|---|---|---|
| Ps 65:10 "You ... bless its growth" | God blessed | pass |
| Jer 4:2 "the nations will be blessed by Him" | I will bless you ... nations blessed | fail as built: the label said "and where it is taken up" and the verse names no Abraham. Label now says "the verses that speak of the nations blessed"; the note says Ps 72:17, Isa 19:25 and Jer 4:2 do not name Abraham and the page does not say they refer to the promise |
| Deut 15:4 "no poor among you ... because the LORD will surely bless you in the land" | The LORD your God will bless you | pass |
| Heb 11:21 "Jacob ... blessed each of Joseph's sons" | A father's blessing | pass |
| 1 Sam 2:20 "Eli would bless Elkanah and his wife" | The priests ... bless the people | pass |
| Num 24:1 "it pleased the LORD to bless Israel" | Balaam | pass |
| Job 29:11 "those who heard me called me blessed" | Where the Berean prints curse, greet, congratulate, "commended" | fail as built: MACULA glosses it "commended", the Berean prints "called me blessed". Moved to "People bless one another and call one another blessed"; the row name no longer carries "commended" |
| Ps 67:1 "May God be gracious to us and bless us" | Asked of God | fail as built (a wish in the third person, not a request made to God): row now "A request for God's blessing: ... 'May God be gracious to us and bless us'" |
| Zech 11:5 "Blessed be the LORD, for I am rich!" | People bless God | pass (a hard verse; the note says so) |
| Luke 24:51 "While He was blessing them" | Jesus blessed | pass |
| Ps 62:4 "with their mouths they bless, but inwardly they curse" | Blessing set against cursing | pass |
| Job 1:5 "cursed God in their hearts" | Where the Berean prints "curse" | pass |
| Prov 10:22 "The blessing of the LORD enriches" | Where the verse names harvest, barns... | fail as built: no listed good is in it. Label now ends "...land, riches or children" |
| Luke 23:29 "Blessed are the barren women" | Blessed are the poor... | fail as built: not about the poor or the persecuted. Moved to the adjective "Every other use", with a note |
| Ps 21:3 "welcomed him with rich blessings; ... a crown of pure gold" | Where the verse names harvest... | fail as built: no listed good. Moved to "You will be a blessing", "May Your blessing be on Your people", "rich blessings" |
| Rom 14:22 "Blessed is the one who does not condemn himself by what he approves" | "Blessed is the one who..." in the NT | partial: the label's list (hearing, keeping, believing...) does not fit; label now "in the New Testament, apart from the Beatitudes" and the note names Rom 14:22 and 1 Cor 7:40 as the letters' two other uses |

Moved on reading, outside the sixteen: Ps 41:2 ("He will bless him in the land", the LORD, not "call blessed") to God blessed; Ps 49:18 ("he blesses his soul") to Every other use, beside Deut 29:19; Ps 112:2 and 128:4 ("will be blessed", no one named as the one who blesses) from God blessed to Every other use, by the rule that a row about God is filled only where the text names Him. Ps 84:6 is not in the prosperity row: the Berean prints "pools" where the Hebrew בְּרָכוֹת is "blessings"; it is under the noun "Every other use" with a note.

First examples: all 25 rows' first four were read (`out/concept-hubs/blessing.json`) and each shows its label.

## Contested points the panel should read

1. Prosperity (the brief's point). Set side by side, three places: the verb row "The LORD your God will bless you" (26: Exod 20:24, 23:25, Deut 1:11-30:16, Hag 2:19; includes Deut 15:4 "There will be no poor among you"); the noun row "Where the verse names harvest, barns, flocks, meat, rain, land, riches or children with the blessing" (16: Gen 39:5, 49:25-26, Lev 25:21, Deut 12:15, 16:17, 28:8, 33:23, Prov 10:22, 11:26, Isa 65:8, Ezek 34:26, 44:30, Joel 2:14, Mal 3:10, Heb 6:7); against the adjective row "Blessed are the poor, those who mourn, the meek, those who hunger, the persecuted" (16: Matt 5:3-11, Luke 6:20-22, Jas 1:12, 1 Pet 3:14, 4:14, Rev 14:13). Each carries a note that readers part on whether material blessing is promised to the faithful now and the page takes no side. Labels are the text's own words, "said to Israel", no label is a promise, and Deuteronomy 28 is deliberately not among the card's key verses. Hard cases for the panel: Mal 3:10 and Ezek 44:30 (the tithe verses, shown with no word on tithing today); Prov 10:22 and 28:20; Ps 112:1-3, 127:5 and 128:2-3 (Old Testament "Blessed is..." verses that name house, children and bread; named in the note of the first adjective row); Job 42:12; Prov 11:25 "A generous soul will prosper" and 2 Cor 9:5-6 (in the gift row: the Greek word is the "generous gift" and "sows generously").
2. The promise to Abraham (verb row 2, noun row "Blessing beside the righteous, life, the Spirit and Christ"): who "your offspring" and "those who have faith" are, and how Israel and the church stand to the promise (Gen 22:18, Acts 3:25-26, Gal 3:8-9, 3:14, Heb 6:14). Shown by the verses; no side.
3. The Lord's Supper words (row "Jesus blessed"): Matt 26:26 and Mark 14:22 ("spoke a blessing"), 1 Cor 10:16 ("the cup of blessing that we bless a participation in the blood of Christ"); memorial, real presence, participation. Shows only where the text says "bless". Matt 26:27 (the cup, "gave thanks") is a different Greek verb and is not here.
4. Rom 9:5 (row "Blessed be the LORD"): whether the doxology blesses Christ ("who is God over all") or God apart from Christ turns on punctuation the Greek leaves open. Also Mark 14:61 "the Son of the Blessed One". Note present; no side.
5. Rev 20:6 ("Blessed and holy is the one who shares in the first resurrection", row of New Testament "Blessed is...") is read differently on the millennium. Note present.
6. Job 1:5, 1:11, 2:5, 2:9, 1 Kgs 21:10, 21:13: the Hebrew is "bless", the Berean prints "curse"; the note says readers have long taken "bless" there as a softened "curse" and the page does not decide.
7. Divine persons by hand: "God blessed" and "I will bless you" are filled only with verses that name the LORD, God, the Almighty or "My Father" as the one who blesses (Gen 5:2, Ps 37:22, 107:38, 147:13 say "He"/"Him" with the LORD named just before, and the note says so). "Jesus blessed": the Gospel narratives, where several say "He" (Mark 10:16, Luke 24:30, 24:51), noted. "Blessed is He who comes in the name of the Lord" claims no person (the crowds say it; the Gospels' Son of David, Matt 21:9, is in the verse). Eph 1:3 and 2 Cor 1:3 are in "Blessed be the LORD" with "the God and Father of our Lord Jesus Christ".
8. Hard verses kept: Ps 137:8-9 ("Blessed is he who repays you... who seizes your infants"), Mal 3:15 ("we call the arrogant blessed"), Zech 11:5, Ps 10:3 ("he blesses the greedy and reviles the LORD", which readers take two ways), Luke 23:29, Deut 29:19 (a man "invokes a blessing on himself").
9. Gen 27 (Isaac's blessing of the son he took to be Esau) beside Heb 11:20 ("By faith Isaac blessed Jacob and Esau"): shown, no word on the deceit beyond the text's own (Gen 27:35 "came deceitfully"). Gen 32:26-29 (Jacob and "the man") is in the row of people blessing one another; the text says no more.
10. Multi-tradition reading, the rabbi's seat especially: the "father's blessing", "priests bless the people" (Num 6:24-27) and "Balaam" rows are the Torah on its own terms; the Hebrew בְּרָכָה as "gift" (Gen 33:11, Josh 15:19) is the word's own sense in the Torah and Joshua.

## What the builder could not express

- `forms` puts a word in one section only. εὐλογητός (Hebrew בָּרוּךְ's Greek) is forced to "verb" so that its 8 verses sit with the Hebrew in "Blessed be the LORD"; its lexicon part of speech is noun/adjective. A word shown in two sections (verb and adjective) was not possible. Jer 17:7 ("Blessed is the man who trusts") and John 12:13 are the verb בָּרַךְ / εὐλογέω and so are also in the verb section's "Every other use"; a pick in another form does not remove the verse from its own form's catch-all. Needed: an option that a picked verse in one form is "placed" for the same word in every form.
- The frames and clauses missed 9 verses (Ps 37:22; Matt 21:9, 23:39, Mark 10:16, 11:9, 11:10, Luke 1:42, 13:35, 19:38: the passive participles εὐλογημένος / בָּרוּךְ). They were added by `pick`, which does not check that the word is in the verse (the `add` safety the covenant hub used only applies to verses the builder has already seen). Every pick here was copied from the builder's own verse lists or the word-by-word sense lists, and the 9 were read in the server's text. Needed: a pick-check against `d["orig"]` (the verse's own lemmas) that fails a mistyped reference.
- No per-verse note inside a row (the notes name Gen 5:2, Ps 107:38, Ps 132:15, Luke 24:51 in prose); and no way to show the Hebrew-versus-Berean difference automatically: Ps 84:6 (Berean "pools" for "blessings") and Luke 1:64, 24:53 (Berean "praising" for εὐλογέω) are worked by hand in the notes.
- `sense` is one regex for all twelve words; "happy" had to be kept for the whole hub to keep אָשַׁר "call happy" (Gen 30:13), which also admits any other word glossed "happy".
- The "Every other use" rows of the adjective and noun sections hold a few unrelated things (adjective: 1 Tim 1:11, 6:15, Titus 2:13, Acts 26:2, Luke 23:29; noun: Rev 5:12-13, 7:12, Neh 9:5, 1 Cor 10:16, Ps 21:6, Ps 84:6, Rom 16:18). Each has a note that names them; `lead` was set so the first four examples are the clearest. Rev 5:12-13, 7:12 and Neh 9:5 (blessing given to God and the Lamb) would be a row of their own (4 verses) if the owner wants the room.

## Other notes

- Cards missing: none after changing `holy_spirit` to `holy_ghost` (the card for the Holy Spirit is `holy_ghost`).
- The About view is not touched (no `index.html` edits allowed in this task). It states nothing that this hub changes; the `others` section is absent for this concept.
- `_review` in the spec says "Not yet reviewed."
