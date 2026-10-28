# Brief: build one concept hub (the fourth round, 2026-10-26): good, evil

Follow `BRIEF-2.md` in every respect (what to read, the build, the rules, the check, the delivery), at

    <local>

with these differences, which win where they disagree with it:

- **The repository is this worktree**, and you work only there (read, build, write):
  `<local> Ontology/.claude/worktrees/keen-lederberg-9acb2e`
  Run the build from that folder. The verse and card lookups stay on `http://localhost:8012/...` as BRIEF-2 says.
- **Thirty-one hubs exist.** Read `ontology/concept-hubs/sin.json` and `wisdom.json` too, for the newest shape.
- **Two hubs are built at once: good and evil.** Each builder builds only its own; wait for your build to finish
  before starting another.
- **The three cards reference each other.** Good and evil are a pair in the text (Ps 34:14 "Turn away from evil and
  do good"; Rom 12:21 "overcome evil with good"); the tree of the knowledge of good and evil (card id
  `tree_of_knowledge`) names both. On your hub:
  - a row "Knowing good and evil" (by `pick`: Gen 2:9, 2:17, 3:5, 3:22; Deut 1:39; 2 Sam 14:17; 1 Kgs 3:9;
    Isa 7:15-16; Heb 5:14, wherever your concept's word stands in them), with `doors` to `tree_of_knowledge`; its note
    says what the verses say (the phrase recurs; Gen 3:5 is the serpent's promise and 3:22 God's words) and takes
    no side on what the knowledge is;
  - the other concept (`good` or `evil`) as a door: in `leads`, and on the row where the two stand together.
- **The contested points, each shown and never settled:**
  - **good:** God's goodness (by `pick`, where the text names Him); "No one is good except God alone" (Mark 10:18,
    Luke 18:19: readers differ on what it implies about the speaker; take no side); "there is no one who does good"
    (Ps 14:1-3, Rom 3:12) beside the verses that call people good (Acts 11:24, Luke 6:45): what is called total
    depravity, and its readings, set side by side; good works and salvation (Eph 2:8-10, James 2, Titus 3) side by
    side, never a verdict; the created order "very good" (Gen 1:31). טוֹב is also "pleasant", "well", "fine",
    "beautiful": keep those senses apart with `sense`. ἀγαθός and καλός are different Greek words that English
    both renders "good": rule 6 applies (informed, never equated).
  - **evil:** רַע and רָעָה are moral evil and also calamity, disaster, harm and "bad" (of figs, of land): keep the
    senses apart with `sense`. God and calamity (Isa 45:7, Amos 3:6, Job 2:10, Lam 3:38): readers differ on how this
    stands with God's goodness; set the verses side by side, take no side, and no label may say God does moral evil
    or that He does not. "The evil one" (Matt 6:13, 13:19, 13:38, John 17:15, Eph 6:16, 1 John 5:18-19) by `pick`;
    where the text itself names him (Matt 13:19 beside Mark 4:15 "Satan") say so in the note, and otherwise leave
    the identification to the reader. The evil heart (Gen 6:5, 8:21, Jer 17:9): original sin's readings part here;
    no side. "Evil in the sight of the LORD" (the kings' formula) is a row of its own. Evil spirits (1 Sam 16:14-23,
    Luke 7:21, Acts 19:12-16) as their own row, the note saying only what the text says of them.
- **The report** goes to `<id>-report.md` in
  `<local>`

Reply with one line: the concept, its row count, and the 16-sample tally.
