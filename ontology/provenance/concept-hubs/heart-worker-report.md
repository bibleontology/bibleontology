# Report: the heart hub (third round, 2026-10-25)

Spec: `<local> Ontology\ontology\concept-hubs\heart.json` (`"shown": false`).
Built: `<local> Ontology\out\concept-hubs\heart.json` (5 builds; build 5 is the delivered one).

## The words

Kept in the rows (935 verses): Hebrew לֵב (563 verses), לֵבָב (228), לִבָּה (1); Aramaic לְבַב (6, Daniel); Greek καρδία (149), σκληροκαρδία (3), καρδιογνώστης (2). `sense` is empty: every use is the one word, whether the Berean prints heart, mind, thoughts, understanding, sense or courage, and the rows divide the uses by what the verse says. None dropped.

`others` ("Other words translated heart"), each with a note and never made the same word: נֶפֶשׁ (soul; MACULA glosses it "heart" in about a dozen verses, Ps 10:3 first), כִּלְיָה (kidneys: Ps 7:9, Jer 11:20, where the Berean prints "hearts and minds", "heart and mind"), σπλάγχνον (1 John 3:17), ἐγκακέω (Luke 18:1, "lose heart": no word for heart in the Greek), διάνοια (Mark 12:30 and Luke 10:27 name it beside καρδία as a second word), and the Aramaic לֵב of Dan 7:28 (see "could not express", first item). The gloss rule also finds εὔσπλαγχνος, כָּאָה, טֻחוֹת, לִבֵּב and others with one or two verses.

## The rows (one form, noun; 24 rows, 935 verses, none under More)

| # | Row | n |
|---|---|---|
| 1 | The LORD, God, searches, tests and knows the heart | 23 |
| 2 | Jesus knows their hearts: "I am the One who searches minds and hearts" | 5 |
| 3 | "The Lord", "He", no name in the verse: knowing, opening, directing the heart | 5 |
| 4 | Evil, deceitful, foolish, devising, proud | 83 |
| 5 | Hardened, stubborn, calloused, uncircumcised | 64 |
| 6 | Pure, clean, upright, whole, blameless; and not whole | 50 |
| 7 | What a person does with the heart, or is told to do: set, prepare, turn, guard, give, circumcise, make new | 41 |
| 8 | What God does to the heart: gives, creates, changes, turns, opens, writes on it, humbles, makes faint; gives over | 45 |
| 9 | A willing heart: resolved, moved, given freely, obeyed "from the heart" | 21 |
| 10 | In believers' hearts: the Spirit, Christ, the peace of God; cleansed by faith | 18 |
| 11 | "All the heart": with all the heart, every heart, a whole heart | 59 |
| 12 | Beside loving, seeking, praying, praising and giving thanks | 77 |
| 13 | Beside the law, the commandments and the word; the word kept in the heart | 65 |
| 14 | Wisdom, understanding, sense, knowledge: a wise or discerning heart; the heart that does not understand | 109 |
| 15 | Says, thinks, plans, reasons and ponders in the heart; takes it to heart, considers | 125 |
| 16 | Where the heart goes: desire, craving, treasure, loyalty; and the heart turned away | 53 |
| 17 | The heart of God, and of Jesus: "after My own heart", "grieved in His heart", "gentle and humble in heart" | 25 |
| 18 | Beside the mouth, lips, tongue, eyes and ears | 89 |
| 19 | Believing, trusting and doubting in the heart | 31 |
| 20 | Glad, joyful, merry | 68 |
| 21 | Troubled, broken, faint or afraid; and strengthened, comforted, spoken to kindly, steady | 115 |
| 22 | The middle: the heart of the sea, of the earth, of the heavens | 13 |
| 23 | The body: pierced, struck, over the heart | 15 |
| 24 | Every other use | 15 |

A verse sits in every row it fits (`match: all`), so the counts add to more than 935. Rows 1-3, 4-8 and 9-10 are by hand (`add`, which keeps a verse only where the word for heart really stands in it); rows 11-14, 18-20 are a rule on the companion words in the verse plus `add`.

Order: rows 4, 5, 6, 7, 8 are the contested block and stand in the alphabetical order of their labels (Evil, Hardened, Pure, What a person, What God), each with the same no-side sentence, as on covenant.

## The 16-verse sample (build 4, verses not read before, from 16 different rows)

15 shown outright, 1 failed and was fixed.

| Verse | Row | Verdict |
|---|---|---|
| Prov 17:3 "the LORD is the tester of hearts" | 1 | shown |
| Rom 8:27 "He who searches our hearts knows the mind of the Spirit" | 3 | shown |
| Jer 23:26 "the hearts of these prophets who prophesy falsehood ... delusion of their own minds" | 4 | shown |
| Exod 9:34 "he sinned again and hardened his heart" | 5 | shown |
| Ezek 11:19 "singleness of heart ... heart of stone ... heart of flesh" | 8 | shown |
| Mal 2:2 "if you do not take it to heart" | 7 | shown (set the heart to it) |
| 1 Chr 29:9 "given to the LORD freely and wholeheartedly" | 9 | shown |
| Ps 119:7 "with an upright heart" | 6 | shown |
| Col 3:15 "Let the peace of Christ rule in your hearts" | 10 | shown |
| Eccl 9:1 "I took all this to heart ... whether love or hate" | 12 | shown (the verse has "love"; weakest in the row) |
| Prov 10:8 "A wise heart will receive commandments" | 13 | shown |
| Prov 18:2 "A fool does not delight in understanding, but only in airing his opinions" | 14 | shown (the Berean prints "opinions" for the heart) |
| Ezek 14:3 "set up idols in their hearts" | 16 | shown |
| Rom 10:6 "the righteousness that is by faith says: Do not say in your heart" | 19 | FAILED: names faith and "in your heart", no believing, trusting or doubting in the heart. Out by `not_verses` (a quotation of Deut 30:12); it stays under row 15. |
| Isa 24:7 "All the merrymakers now groan" | 20 | shown (the Berean prints no heart; the Hebrew is "merry of heart") |
| Ezek 27:4 "Your borders are in the heart of the seas" | 22 | shown |

Also read: about 130 more verses (every verse quoted in a note, and the rows' rule-made verses), against the Berean text. Failures found and fixed: Ps 33:15 out of row 14 ("considers all their works"), Judg 9:3 out of row 18 (the Berean prints "in the presence of", no ear), "all" belonging to the Levites, the workmen or the men of Judah in 2 Chr 30:22, Exod 31:6 and 2 Sam 19:14 (out of row 11), five אָמַן "faithful" verses out of row 19 (1 Sam 2:35, Neh 9:8, Ps 78:8, Ps 78:37) and πιστεύω "entrusted" (1 Thess 2:4), Num 24:13 and Prov 12:8 (פֶּה as "command" and "according to"), Judg 5:15 and Jer 5:24 out of row 13 (a word for "commanders" and one for "fixed weeks"), Dan 5:21 out of row 8 (the verse names no one who did it; it is under row 24). About forty quotations in my first draft of the notes were not the Berean's words (it has "the LORD sees the heart", not "looks at"; Gen 6:5 "altogether evil"; Ezek 18:31 "fashion for yourselves a new heart"; Jer 31:33 "inscribe it on their hearts"; Deut 29:4 "a mind to understand", with no word for heart; Prov 4:23 "Guard your heart with all diligence"; Rev 2:23 "the One who searches"); every one was corrected. Where the Berean hides the heart the notes say so: Deut 29:4, Dan 1:8, Ps 27:14, Gen 17:17, Lam 3:33, Deut 4:11, Judg 19:22, Isa 24:7, Hos 2:14, Gen 31:20, Num 16:28, Exod 9:14.

## Contested points the panel should read

1. **How far sin reaches in the heart (what is called total depravity), and whether God's work on the heart comes before a person's turning (what is called prevenient grace).** Five rows, one no-side sentence each, listed in the alphabetical order of their labels with the sentence "carry no ranking":
   - *Evil, deceitful, foolish, devising, proud* (83): Gen 6:5 and 8:21, Jer 17:9, Eccl 9:3, Prov 22:15 ("Foolishness is bound up in the heart of a child"), Matt 15:19, Mark 7:21, Rom 1:21, Heb 3:12 ("a wicked heart of unbelief"), and the proud heart (Prov 16:5, Ezek 28:5, Dan 5:20).
   - *Pure, clean, upright, whole, blameless; and not whole* (50): Ps 24:4, 73:1, 101:2, Matt 5:8, 1 Sam 13:14 and Acts 13:22 ("after His own heart"), 1 Kgs 9:4, Prov 20:9 ("Who can say, I have kept my heart pure ...?"), with the negatives on purpose (1 Kgs 11:4, 2 Chr 25:2, Ps 78:37, Ps 73:13 "in vain have I kept my heart pure").
   - *What a person does or is told to do* (41): Deut 10:16 and Jer 4:4 ("circumcise your hearts"), Jer 4:14, Ezek 18:31 ("fashion for yourselves a new heart and a new spirit"), Joel 2:13, Prov 4:23, Prov 23:26, Jas 4:8, and the hearts that did or did not set themselves (1 Chr 22:19, 2 Chr 12:14, Ezra 7:10).
   - *What God does to the heart* (45): Ezek 36:26 and 11:19, Ps 51:10, Jer 24:7, 31:33 and 32:39-40, Deut 30:6 ("The LORD your God will circumcise your hearts"), 1 Sam 10:9, Eccl 3:11, and on the other side Deut 29:4 ("has not given you a mind to understand"), Rom 1:24 ("God gave them over in the desires of their hearts"), Ps 105:25, Lev 26:36, Job 23:16. Ezek 18:31 and Ezek 36:26 are set in different rows and the notes say both are the text's.
   - *Hardened, stubborn, calloused, uncircumcised* (64): the LORD hardens (Exod 4:21, 9:12, 10:1, Josh 11:20, Isa 63:17), Pharaoh hardens his own (Exod 8:15, 8:32, 9:34), "was hardened" with no one named (Exod 7:13, 7:22). Rom 9:18 has no word for heart and is left out; the note says so. Where traditions part on how God's hardening and a person's own stand (the Pharaoh verses are the usual ground), the page takes no side. Isa 6:10 and Rom 2:5 are hard verses and stay.
2. **The three searcher rows (divine persons by hand).** Row 1 names the LORD or God in the verse (1 Sam 16:7, 1 Chr 28:9, Ps 139:23, Luke 16:15). Row 2 names Jesus (Mark 2:8, Luke 5:22, Luke 9:47, Matt 9:4) or is His own "I" (Rev 2:23). Row 3 holds the verses that say only "the Lord" or "He" (Acts 1:24, Acts 16:14, Rom 8:27, 1 Cor 4:5, 2 Thess 3:5); the note says readers take them of the Father or of Christ and the page does not choose. Rom 8:27's Searcher stands beside the Spirit.
3. **Row 17, "The heart of God, and of Jesus"** (Gen 6:6, 1 Sam 13:14, Hos 11:8, Ps 33:11, Jer 3:15, Matt 11:29). Set down as written; the note says the page does not say how literally it is taken. Gen 8:21 is in this row and in row 4. A panel may want to ask whether the row reads as a doctrine of God's emotions; it uses only the text's words.
4. **The pronoun-only verses inside "What God does"** (1 Kgs 8:58, Ps 33:15, 105:25, 107:12, 119:32/36/80, 141:4, Eccl 3:11): "He" or "You" in a prayer or speech whose passage names the LORD. This follows the forgiveness hub's rule for the Hebrew, and the note lists them. If the panel wants the stricter rule (name in the verse), those nine go to row 3 or out.
5. **Heart as mind and will, not only feeling** (rows 9, 14, 15): the notes say so in the text's words; the Berean prints "mind" at Deut 29:4 (heart), Jer 11:20, Prov 16:9 and "opinions" at Prov 18:2.
6. **Human skill** (Exod 28:3; 31:6; 35:10, 25, 35; 36:1-2, 8: "wise of heart" craftsmen) is in row 14 with a note that it is skill given to the craftsmen, not the wisdom of Proverbs 8 (the wisdom round's sense of its own).
7. **Hard verses kept:** Heb 3:12, Isa 6:10, Isa 63:17, Rom 1:24, Rev 17:17, Ps 105:25, Prov 22:15, Ps 73:13, John 13:2 and Acts 5:3 (Satan filling a heart, in row 4 as the verses say it).

## Could not express

- **A word keyed by spelling.** `hub_build.py` keys the concept's words by their pointed lemma, so the Aramaic לֵב (Dan 7:28, h3821) overwrote the Hebrew לֵב (h3820) and the first build lost 563 verses. The Aramaic one is out of `words` and named under "Other words" with a note; Dan 7:28 is therefore in no row. Needed: key by the word's key (`h3820` / `h3821`), or by language and spelling.
- **`not_verses` does not apply to `add`.** A verse added by hand cannot be held out by `not_verses` (only a rule's match can). I kept the two apart (hand rows use `add` only), but a hub that mixes both cannot hold an `add`ed verse out of a rule row it also fits.
- **The English.** No row can be conditioned on the Berean's words. Where the Berean prints "in the sight of" for the Hebrew "in the eyes of" (Ruth 2:13, 2 Kgs 20:3, Isa 38:3), "in the presence of" for "in the ears of" (Judg 9:3), "willingly" for "from His heart" (Lam 3:33), a rule on the Hebrew word shows a verse that does not show its label, and each had to be put out by hand. A way to require (or forbid) an English word in the verse would have saved about twelve `not_verses`.
- **A companion that belongs to another noun.** `with` / `adjacent` on "all" cannot tell "all the Levites" from "all the heart" (2 Chr 30:22, Exod 31:6, 2 Sam 19:14); three `not_verses`.
- **A rule on a word that has two uses in one hub.** `רָנַן` ("ring out") is joy and a cry; it was taken out of the joy rule, and Ps 84:2 and Lam 2:19 sit under row 12 and the hand rows instead.
- **Rows that are idioms.** "Take it to heart" / "set the heart on" (שִׂים לֵב), "speak to the heart", "refresh the heart" are Hebrew idioms the Berean mostly prints without the word heart ("consider", "speak tenderly", "encouraged"); they are rows by hand, with the Hebrew said in the note.

## Row count

24 (the brief's 15-25). Rows that could join if the owner wants fewer: 21 into 22 are not joinable (different senses); 22 and 23 (the middle; the body) are small but the text sets them apart (Exod 15:8, 2 Sam 18:14); 9 (willing) could join 7 (what a person does); 16 could join 15 (Phil 1:7 and 2 Sam 15:13 are loyalty, not thinking).
