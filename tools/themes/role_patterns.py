"""Role patterns, grounded against the text (2026-09-30).

Copilot was put to work on roles and produced some good patterns, which
still need grounding in the text. The source is ontology/themes/role-patterns.md,
verbatim: nine role patterns (Shepherd, King, Prophet, Priest, Bridegroom,
Father, Servant, Enemy, and spiritual warfare), each laid out twice --
"horizontally" (each movement, with verses) and "vertically" (each figure
carried through the movements) -- plus three additions: the
Prodigal Son (Luke 15), the foot washing (John 13), and spiritual warfare
(Eph 6, Jas 4:7).

What this measures, per citation:
  resolves   the reference exists in the Berean text
  broad      it cites more than 40 verses for one movement (a book-part is
             not evidence for a single claim)
  word       the movement's own word is in the cited verses, in the Hebrew
             or Greek (MACULA): the text SAYS it
  role       only the pattern's role word is there
  none       neither: the claim rests on description or interpretation,
             and has to be read
  quote      the words Copilot quotes are found in the Berean text of the
             cited verses (a quote from another translation can differ)

And per figure, THE ROLE THE TEXT GIVES: verses where the role word
(shepherd, king, prophet, priest, bridegroom, father, servant) stands within
three verses of the figure named in the graph's mentions -- candidates, read
before they are claimed. A figure the text never gives the role word is
carrying the role by a reader's analogy, which is a reading, not a finding.

    python tools/themes/role_patterns.py
      -> out/role-patterns.json
         docs/review/ROLE-PATTERNS.md
"""
from __future__ import annotations

import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "themes"))
sys.path.insert(0, str(ROOT / "tools" / "events"))
sys.path.insert(0, str(ROOT / "tools" / "phrases"))
from theme_map import check, spans_in  # noqa: E402
from event_nodes import TO_MACULA, verses  # noqa: E402
from phrase_search import hebrew_words  # noqa: E402

SRC = ROOT / "ontology" / "themes" / "role-patterns.md"

# ---- the patterns: (id, role, movements, {movement: its words}, role words)
# Every key is checked against MACULA's lemma when the tool runs (printed at
# the head of the report), so a wrong Strong's number shows.
P = [
    ("shepherd", "Shepherd",
     ["Shepherd", "Sheep", "Pasture", "Protection", "Provision"],
     # h7473: MACULA numbers the participle "shepherd" (Ps 23:1 "is my
     # shepherd", Isa 63:11) apart from the verb h7462; without it both read
     # as unsupported
     {"Shepherd": "h7462 h7473 g4166 g4165 g750", "Sheep": "h6629 h7716 h5739 h3532 g4263 g4167 g4168 g721 g286",
      # h4999 נָאָה, the pastures of Ps 23:2 -- a third Hebrew word for it
      "Pasture": "h4829 h4830 h5116 h4999 g3542", "Protection": "h5337 h3467 h8104 g4506 g5083 g5442 g726 g3074",
      "Provision": "h2637 g5142 g5526 h3557"},
     "h7462 h7473 g4166 g4165 g750"),
    # THE FORMS SWEEP (2026-09-30): the words that recurred in citations
    # graded "read it", kept only where they are the text's own word for the
    # part -- anointed and ruler for king (h4886, h5057), fathered and
    # firstborn (h3205, g1080, h1060), wife and adultery for the bride and her
    # faithfulness (h802, g1135, h5003, h2181), slaughter for sacrifice
    # (h7819), preach for the prophet's word (g2784, g2097), forgive and heal
    # for restoration (h5545, h7495), minister for servant (h8334), make peace
    # and reconcile for peace (g1517, g604)
    ("king", "King", ["King", "Kingdom", "Law", "Judgment", "Peace"],
     {"King": "h4428 h4427 g935 g936 h4886 h5057", "Kingdom": "h4467 h4438 h4410 g932",
      "Law": "h8451 h2706 h4687 g3551 g1785", "Judgment": "h8199 h4941 h1777 g2919 g2920 g2917",
      "Peace": "h7965 h5117 h8252 g1515 g1517 g604"},
     "h4428 h4427 g935 g936"),
    ("prophet", "Prophet", ["Prophet", "Word", "Confrontation", "Repentance", "Restoration"],
     {"Prophet": "h5030 h5031 h5012 g4396 g4395", "Word": "h1697 g3056 g4487 g2784 g2097",
      "Confrontation": "", "Repentance": "h7725 h5162 g3340 g3341 g1994",
      "Restoration": "h7725 g600 g605 h5545 h7495"},
     "h5030 h5031 h5012 g4396 g4395"),
    ("priest", "Priest", ["Priest", "Sacrifice", "Cleansing", "Access", "Presence"],
     {"Priest": "h3548 h3547 g2409 g749 g2406 g2405", "Sacrifice": "h2077 h2076 h5930 h7133 g2378 h7819",
      "Cleansing": "h2891 h2889 h2893 h3722 g2511 g2513", "Access": "g4318 g4334",
      "Presence": "h6440 h7931 h3519 g4637 g1391"},
     "h3548 h3547 g2409 g749 g2406 g2405"),
    ("bridegroom", "Bridegroom", ["Bridegroom", "Bride", "Covenant", "Faithfulness", "Consummation"],
     {"Bridegroom": "h2860 g3566 h1166 h1167", "Bride": "h3618 g3565 h781 g718 h802 g1135",
      "Covenant": "h1285 g1242", "Faithfulness": "h530 h571 h2617 g4102 g4103 h5003 h2181",
      "Consummation": "g1062 g1060"},
     "h2860 g3566 h1166 h1167 h3618 g3565"),
    # "FATHER AND SON", not "Father": on Jesus's card the chip read "Role
    # pattern: Father · Jesus -- the text calls it so: John 5:18", i.e. Jesus
    # as the Father, while John 5:18 fills the pattern's Father slot with God
    # and Jesus is the Son (2026-10-02, reading the Jesus card). The
    # pattern's own slots are a father AND a son; its name says both.
    ("father", "Father and son", ["Father", "Son", "Inheritance", "Obedience", "Blessing"],
     {"Father": "h1 g3962 h3205 g1080 h1060", "Son": "h1121 g5207 g5043 g5206",
      "Inheritance": "h5159 h5157 h3423 g2817 g2818 g2816",
      "Obedience": "h8085 g5218 g5219 g5255", "Blessing": "h1288 h1293 g2127 g2129"},
     "h1 g3962"),
    ("servant", "Servant", ["Servant", "Suffering", "Vindication", "Glory"],
     {"Servant": "h5650 h5647 g1401 g3816 g1249 g1398 h8334", "Suffering": "g3958 g3804 h6031 h2490 h1792",
      "Vindication": "h6663 g1344 h7311 g5251", "Glory": "h3519 g1391 g1392"},
     "h5650 g1401 g3816 g1249"),
    ("enemy", "Enemy", ["Enemy", "Oppression", "Deliverance", "Victory"],
     {"Enemy": "h341 h6862 h6887 g2190", "Oppression": "h3905 h6031 h6040 h5065 g2616",
      "Deliverance": "h5337 h3467 h3444 g4506 g4982 g859", "Victory": "h8668 g3529 g3528 g3534"},
     "h341 h6862 g2190"),
    # SUBMISSION is added from the text, not Copilot's: James 4:6-10 and
    # 1 Peter 5:5-10 both quote Prov 3:34, both say "submit" and "humble
    # yourselves ... He will exalt you", and both put it BEFORE "resist the
    # devil" (READINGS below).
    ("warfare", "Spiritual warfare",
     ["Submission", "Spiritual Powers", "Opposition", "Resistance", "Divine Aid", "Stand / Victory"],
     {"Submission": "g5293 g5013 g4352 g3000",
      "Spiritual Powers": "g746 g1849 g2888 g4152 g1228 h7854 g4567",
      "Opposition": "g3985 g3986 g4105", "Resistance": "g436 g3833 g2476",
      "Divine Aid": "g1743 g1412 g997 g998", "Stand / Victory": "g2476 g3528 g4937"},
     "g1228 h7854 g4567"),
]
PAT = {p[0]: p for p in P}

# ---- READ BY HAND: the three additions, verse by verse. Copilot's prose
# for these quotes the text without references; a word-overlap locator put
# "all things into His hands" at John 13:29 and the betrayal at 13:17, so
# these rows were read instead. (pattern, figure, movement, reference, what
# the text says there)
READINGS = [
    ("father", "Prodigal Son (Luke 15)", "Father", "Luke 15:11",
     "“There was a man who had two sons.”"),
    ("father", "Prodigal Son (Luke 15)", "Father", "Luke 15:20",
     "his father saw him and was filled with compassion; he ran to his son"),
    ("father", "Prodigal Son (Luke 15)", "Son", "Luke 15:19",
     "“no longer worthy to be called your son. Make me like one of your hired servants”"),
    ("father", "Prodigal Son (Luke 15)", "Son", "Luke 15:21",
     "the same confession, cut off before “make me like one of your hired servants”: "
     "the father does not let him finish"),
    ("father", "Prodigal Son (Luke 15)", "Inheritance", "Luke 15:12",
     "“my share of the estate” (οὐσία, property) — the text does not use the word inheritance"),
    ("father", "Prodigal Son (Luke 15)", "Inheritance", "Luke 15:31",
     "to the OLDER son: “all that is mine is yours”"),
    ("father", "Prodigal Son (Luke 15)", "Obedience", "Luke 15:29",
     "the older son: “I have served (δουλεύω) you and never disobeyed a commandment of yours” "
     "— and he is the one outside the feast (15:28)"),
    ("father", "Prodigal Son (Luke 15)", "Blessing", "Luke 15:22–24",
     "robe, ring, sandals, the fattened calf — given to the son who came back saying "
     "“I have sinned” (15:18, 21)"),
    ("father", "Prodigal Son (Luke 15)", "Blessing", "Luke 15:32",
     "the reason, said twice (15:24, 32): “was dead and is alive again; he was lost and is found”"),
    ("servant", "Jesus (John 13)", "Servant", "John 13:3–5",
     "knowing “the Father had delivered all things into His hands … so He got up … laid aside "
     "His outer garments … began to wash the disciples’ feet”"),
    ("servant", "Jesus (John 13)", "Servant", "John 13:13–16",
     "“You call Me Teacher and Lord, and rightly so … no servant (δοῦλος) is greater than his "
     "master” — the text calls the disciples servants, and Jesus the Lord who does their task"),
    ("servant", "Jesus (John 13)", "Suffering", "John 13:2",
     "the devil had put it into the heart of Judas to betray Him"),
    ("servant", "Jesus (John 13)", "Suffering", "John 13:18",
     "Psalm 41:9 fulfilled: “has lifted up his heel against Me”"),
    ("servant", "Jesus (John 13)", "Suffering", "John 13:21",
     "troubled in spirit: “one of you will betray Me”"),
    ("servant", "Jesus (John 13)", "Suffering", "John 13:27–30",
     "Satan entered into Judas; he went out, “and it was night”"),
    ("servant", "Jesus (John 13)", "Vindication", "John 13:19",
     "“so that when it comes to pass, you will believe that I am He” (ἐγώ εἰμι) — the betrayal "
     "foretold becomes the proof"),
    ("servant", "Jesus (John 13)", "Glory", "John 13:31–32",
     "“Now the Son of Man is glorified” (δοξάζω five times), said when Judas had gone out"),
    ("servant", "Jesus (John 13)", "Suffering", "John 13:4",
     "“laid aside” (τίθημι) His garments: John’s verb for “I lay down My life” (10:11, 15, 17, 18)"),
    ("servant", "Jesus (John 13)", "Glory", "John 13:12",
     "“put on” (λαμβάνω) His garments: John’s verb for “to take it up again” (10:17–18); Peter "
     "answers with the first verb at once, “I will lay down my life for You” (13:37–38)"),
    ("warfare", "James 4:6–10", "Submission", "James 4:6–7",
     "“God opposes the proud, but gives grace to the humble” (Prov 3:34) … “Submit yourselves, "
     "then, to God.”"),
    ("warfare", "James 4:6–10", "Resistance", "James 4:7", "“Resist the devil”"),
    ("warfare", "James 4:6–10", "Stand / Victory", "James 4:7", "“and he will flee from you”"),
    ("warfare", "James 4:6–10", "Divine Aid", "James 4:8–10",
     "“Draw near to God, and He will draw near to you … Humble yourselves before the Lord, and "
     "He will exalt you”"),
    ("warfare", "1 Peter 5:5–10", "Submission", "1 Peter 5:5–6",
     "the same Prov 3:34, “submit yourselves”, “humble yourselves … that He may exalt you”"),
    ("warfare", "1 Peter 5:5–10", "Spiritual Powers", "1 Peter 5:8",
     "“Your adversary the devil prowls around like a roaring lion”"),
    ("warfare", "1 Peter 5:5–10", "Resistance", "1 Peter 5:9",
     "“Resist him, standing firm in your faith”"),
    ("warfare", "1 Peter 5:5–10", "Divine Aid", "1 Peter 5:10",
     "“will Himself restore you, secure you, strengthen you, and establish you”"),
    ("warfare", "Ephesians 6:10–18", "Divine Aid", "Ephesians 6:10",
     "“be strong in the Lord and in His mighty power”"),
    ("warfare", "Ephesians 6:10–18", "Spiritual Powers", "Ephesians 6:11–12",
     "the devil’s schemes; rulers, authorities, powers of this world’s darkness"),
    ("warfare", "Ephesians 6:10–18", "Resistance", "Ephesians 6:13–17",
     "the full armor; “withstand” (ἀνθίστημι, the verb of Jas 4:7 and 1 Pet 5:9)"),
    ("warfare", "Ephesians 6:10–18", "Stand / Victory", "Ephesians 6:13–14",
     "“having done everything, to stand. Stand firm then”"),
    ("warfare", "Jesus tempted (Matt 4:1–11)", "Spiritual Powers", "Matthew 4:1",
     "led by the Spirit into the wilderness “to be tempted by the devil”"),
    ("warfare", "Jesus tempted (Matt 4:1–11)", "Opposition", "Matthew 4:3–9",
     "three temptations: bread, the pinnacle, the kingdoms"),
    ("warfare", "Jesus tempted (Matt 4:1–11)", "Resistance", "Matthew 4:4",
     "“It is written … every word (ῥῆμα) that comes from the mouth of God” — Eph 6:17’s sword "
     "is “the word (ῥῆμα) of God”"),
    ("warfare", "Jesus tempted (Matt 4:1–11)", "Submission", "Matthew 4:10",
     "“Worship the Lord your God and serve Him only”"),
    ("warfare", "Jesus tempted (Matt 4:1–11)", "Stand / Victory", "Matthew 4:11",
     "“Then the devil left Him” — Jas 4:7’s “he will flee from you”"),
    ("warfare", "Jesus tempted (Matt 4:1–11)", "Divine Aid", "Matthew 4:11",
     "“angels came and ministered to Him”"),
]
HAND = {(p, f) for p, f, *_ in READINGS}

# ---- TOO BROAD, NARROWED. A citation over 40 verses is not evidence for one
# claim ("Genesis 35–50" for "Jacob, father of the twelve tribes"). Each is
# narrowed to the verse that says it, or dropped where the range never does:
# (pattern, movement, the draft's reference) -> the verse, or None
NARROW = {
    # Psalm 119 carries no heading naming David; Psalm 19 is "of David"
    ("king", "Law", "Psalm 119"): None,
    ("king", "Law", "Psalm 19; Psalm 119"): "Psalm 19:7",
    ("king", "Law", "Jeremiah 31:33; Revelation 21–22"): "Jeremiah 31:33",
    ("priest", "Sacrifice", "Leviticus 1–7"): "Leviticus 1:5",
    ("priest", "Priest", "Leviticus 8–9"): "Leviticus 8:12",
    ("priest", "Cleansing", "Leviticus 14"): "Leviticus 14:20",
    # the text never calls the flood a cleansing ("macro-priestly act" is
    # the draft's)
    ("priest", "Cleansing", "Genesis 7–8"): None,
    ("bridegroom", "Faithfulness", "Ezekiel 16; 23"): "Ezekiel 16:32; Ezekiel 16:60",
    ("father", "Father", "Genesis 12–25"): "Genesis 21:3",
    ("father", "Father", "Genesis 25–35"): "Genesis 25:26",
    ("father", "Father", "Genesis 35–50"): "Genesis 35:22–26",
    ("father", "Inheritance", "Joshua 13–21"): "Joshua 13:7; Joshua 21:43",
    ("father", "Blessing", "Genesis 48–49"): "Genesis 48:15–16; Genesis 49:28",
    ("father", "Son", "Genesis 27–28"): "Genesis 28:4",
    ("father", "Son", "Genesis 37–50"): "Genesis 37:3",
    ("father", "Inheritance", "Revelation 21–22"): "Revelation 21:7",
    ("servant", "Suffering", "1 Samuel 19–27"): "1 Samuel 19:10; 1 Samuel 23:14",
    ("servant", "Suffering", "1 Sam 19–27; Ps 22"): "1 Samuel 19:10; 1 Samuel 23:14; Psalm 22:1",
    ("servant", "Suffering", "Gen 37–40"): "Genesis 37:28; Genesis 39:20",
    ("servant", "Glory", "Gen 45–50"): "Genesis 45:13; Genesis 50:20",
    ("servant", "Suffering", "Mark 8:31; Luke 22–23"): "Mark 8:31; Luke 23:33",
    ("shepherd", "Provision", "1 Chronicles 15–16"): "1 Chronicles 16:2–3",
    ("prophet", "Confrontation", "Ezekiel 8–11"): "Ezekiel 11:4",
    ("prophet", "Word", "Revelation 2–3"): "Revelation 2:1",
    ("prophet", "Confrontation", "Revelation 2–3"): "Revelation 2:4",
    ("prophet", "Restoration", "Revelation 21–22"): "Revelation 21:5",
    ("warfare", "Stand / Victory", "Revelation 2–3"): "Revelation 2:7",
}

# ---- THE DRAFT, CORRECTED. 2026-09-30: Copilot is the draft; the
# evidence overrides it. Each change: (pattern, figure, what
# changes, the verses that decide it). The report prints those verses'
# Berean text beside the change, so each one can be checked.
OVERRIDES = [
    ("warfare", None,
     "ADD a first stage, SUBMISSION. James and 1 Peter both quote Prov 3:34, both say "
     "“submit” (ὑποτάσσω) and “humble yourselves … He will exalt you” (ταπεινόω, ὑψόω), and "
     "both put it BEFORE “resist the devil” (ἀνθίστημι + διάβολος). The draft began with the enemy.",
     "James 4:6–7; James 4:10; 1 Peter 5:5–6"),
    ("warfare", None,
     "ADD Jesus tempted (Matt 4:1–11) as the pattern’s story: tempted by the devil, answers "
     "with “every word (ῥῆμα) from the mouth of God” (Eph 6:17’s sword is “the word (ῥῆμα) of "
     "God”), “serve Him only”, “the devil left Him”, angels ministered. The draft filed it "
     "under Satan as an enemy only.",
     "Matthew 4:4; Matthew 4:10–11; Ephesians 6:17"),
    ("father", "Prodigal Son (Luke 15)",
     "MOVE obedience to the older son. The draft made the younger son’s return his "
     "“obedience”; the text gives obedience to the older son (“never disobeyed a commandment”), "
     "and he is outside the feast. The blessing goes to the son who said “I have sinned”. So "
     "Luke 15 does not run obedience → blessing; it answers it.",
     "Luke 15:18; Luke 15:28–29; Luke 15:22–24"),
    ("father", "Prodigal Son (Luke 15)",
     "ADD Luke 15 as instances of two story patterns the text itself marks: “Death to life” "
     "(the father says it twice: “was dead and is alive again”) and “Sin, judgment and mercy” "
     "(turning 15:17–21, mercy 15:20, restoration 15:22–24).",
     "Luke 15:24; Luke 15:32; Luke 15:17–20"),
    ("father", "Prodigal Son (Luke 15)",
     "CORRECT “inheritance”: the text says “my share of the estate” (οὐσία) — not the "
     "inheritance words of the pattern. The share is property, and what the father gives the "
     "older son is “all that is mine is yours”.",
     "Luke 15:12; Luke 15:31"),
    ("shepherd", None,
     "ADD Luke 15:4–7: one parable in three (“He told them this parable”, 15:3), and its first "
     "is the shepherd who leaves the ninety-nine in the pasture and carries the lost sheep home. "
     "The text joins the Shepherd and the Father patterns in one parable.",
     "Luke 15:3–6"),
    ("shepherd", "Moses as Shepherd",
     "ADD where the text calls Moses the flock’s shepherd; the draft had only his father-in-law’s "
     "sheep (Exod 3:1) and a request for a successor (Num 27:17).",
     "Psalm 77:20; Isaiah 63:11"),
    ("servant", "Jesus (John 13)",
     "KEEP the garments–death link, on the text’s own verbs: “laid aside” (τίθημι) and “put on” "
     "(λαμβάνω) are John’s “lay down My life … take it up again”; Peter uses the first in the "
     "same chapter. DROP “water → blood” and “basin → sceptre”: not in the words.",
     "John 13:4; John 13:12; John 10:17–18; John 13:37"),
    ("servant", "Jesus (John 13)",
     "ADD vindication from the text: “so that when it comes to pass, you will believe that I "
     "am He” — the draft’s “vindication in seed form” was its own phrase.",
     "John 13:19"),
    ("servant", "Joseph", "ADD where the text calls Joseph a servant: “sold as a slave” (עֶבֶד).",
     "Psalm 105:17"),
    ("servant", "Moses",
     "ADD where the text calls Moses’ shining face glory (δόξα); the draft cited the shining "
     "(Exod 34) and Hebrews 3, which does not.",
     "2 Corinthians 3:7"),
    ("priest", "David — The Priestly King (Hints and Exceptions)",
     "MOVE Psalm 110:4 from David to Jesus and Melchizedek: it is spoken to “my Lord” (110:1), "
     "and Hebrews applies it to Jesus. The text never calls David a priest; it does call his "
     "sons priests.",
     "Psalm 110:1; Psalm 110:4; Hebrews 5:6; 2 Samuel 8:18"),
    ("priest", "Patriarchal Priests (Adam → Noah → Abraham → Jacob)",
     "MARK Adam as a reading: “cultivate and keep” are the Levites’ duty words, but the text "
     "never calls Adam a priest. The shared words are the evidence, and they are shown as a "
     "suggestion.",
     "Genesis 2:15; Numbers 3:7–8; Numbers 18:7"),
    ("enemy", "Egypt",
     "ADD the CRY the draft filed as oppression — the same optional stage as Story pattern: "
     "Cry and rescue, where Egypt already is an instance. Enemy → oppression → deliverance → "
     "victory is that story pattern without its cry.",
     "Exodus 2:23–24"),
]

# The additions, and where the prose (not a reference) points
ASIDES = [("Prodigal Son as a Full Instance", "father", "Prodigal Son (Luke 15)", "Luke 15"),
          ("Jesus as Servant (John 13)", "servant", "Jesus (John 13)", "John 13"),
          ("Spiritual Warfare as a Vertical Sub", "warfare", None, None)]
ASIDE_END = ("How the Prodigal Son Fits", "Vertical Placement of John 13",
             "Why John 13 is Essential", "Why the Prodigal Son Is Essential",
             "How This Fits Into the Vertical Enemy", "Why This Deserves")

# a vertical figure's heading -> the graph's records for them
FIGURES = [("patriarch", ["abraham", "isaac", "jacob"]), ("moses", ["moses"]),
           ("davidic", ["david"]), ("david", ["david"]), ("saul", ["saul"]),
           ("solomon", ["solomon"]), ("hezekiah", ["hezekiah"]), ("josiah", ["josiah"]),
           ("prodigal", []), ("isaiah’s servant", []), ("jesus", ["jesus"]),
           ("messiah", ["jesus"]), ("elijah", ["elijah"]), ("elisha", ["elisha"]),
           ("samuel", ["samuel"]), ("isaiah", ["isaiah"]), ("jeremiah", ["jeremiah"]),
           ("ezekiel", ["ezekiel"]), ("john the baptist", ["john_the_baptist"]),
           ("aaron", ["aaron"]), ("melchizedek", ["melchizedek"]),
           ("hosea", ["hosea", "gomer_wife_of_hosea"]), ("joseph", ["joseph"]),
           ("yhwh", ["god"]), ("apostl", ["peter", "paul"])]

VERTICAL_START = "now take these patterns and show the vertical orientation"
DASH = " — "


def keys(s):
    return set(s.split())


# each role's own English: a role word counts where MACULA renders it so
ROLE_EN = {"bridegroom": ("bridegroom", "bride", "husband", "marr", "wedding"),
           "king": ("king", "reign", "kingdom"), "priest": ("priest",),
           "prophet": ("prophet", "prophes", "seer"), "father": ("father", "son"),
           "servant": ("servant", "serv", "slave"), "enemy": ("enem", "foe", "advers"),
           "warfare": ("devil", "satan", "evil one"),
           "shepherd": ("shepherd", "pastor", "tend", "flock")}
NT_BOOKS = set("Mat Mrk Luk Jhn Act Rom 1Co 2Co Gal Eph Php Col 1Th 2Th 1Ti 2Ti Tit Phm Heb "
               "Jas 1Pe 2Pe 1Jn 2Jn 3Jn Jud Rev".split())


def role_glosses():
    """(MACULA verse, word key) -> MACULA's renderings of it there."""
    out = collections.defaultdict(list)
    for ln in gzip.open(OUT / "interlinear.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        ref = r.get("ref") or ""
        for w in r.get("words") or []:
            s = re.sub(r"\D", "", str(w.get("s") or ""))
            if s:
                k = ("g" if ref.split(".")[0] in NT_BOOKS else "h") + str(int(s))
                out[(ref, k)].append((w.get("g") or "").lower())
    return out


def movement_of(line, pat):
    """'1. Shepherd', '🔥 Suffering (John 13 anticipates it)', 'Stand / Victory'"""
    t = re.sub(r"^[^\w]*", "", line).strip()
    t = re.sub(r"^\d+\.\s*", "", t)
    t = re.sub(r"\s*\(.*\)\s*$", "", t)
    for m in PAT[pat][2]:
        if t.lower() == m.lower():
            return m
    return None


def ref_parts(line):
    """The reference-bearing parts of a line: before ' — ', inside (...), or
    the whole line; split at '→' (Deut 18:15–18 → Acts 3:22–23)."""
    out = []
    if DASH in line:
        out.append(line.split(DASH)[0])
    out += re.findall(r"\(([^()]*\d[^()]*)\)", line)
    # a bare line is a reference only if no prose follows its first number:
    # "Genesis 47:3" is; "John 13 opens with a shock" is not
    m = re.search(r"\d", line)
    if not out and m and not re.search(r"\b[a-z]{2,}\b", line[m.start():]):
        out.append(line)
    parts = []
    for o in out:
        o = re.sub(r"\((?:violated|[a-z ]+)\)", "", o)
        parts += [x.strip(" .:") for x in o.split("→")]
    return [x for x in parts if re.search(r"\d", x)]


def quoted(s):
    return re.findall(r"“([^”]+)”", s)


def parse(text):
    rows, mode, pat, fig, mov, group, home = [], "horizontal", None, None, None, None, None
    last_prose = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or "\t" in line or line.startswith("<!--") or line.startswith("-->"):
            continue
        if VERTICAL_START in line:
            mode = "vertical"
            continue
        # a pattern begins where its movements are written as an arrow chain
        if "→" in line:
            hit = None
            for p in P:
                ms = p[2]
                i = line.find(ms[0])
                # after the first movement, not inside it: "Bridegroom"
                # begins with "Bride", and the Bridegroom citations were
                # filed under the Priest pattern until this said so
                if i >= 0 and line.find(ms[1], i + len(ms[0])) > i:
                    hit = p[0]
                    break
            # the warfare section quotes the Enemy chain it is a version of
            # ("This is the spiritual-warfare version of: Enemy → ..."); it
            # is the last section, so once in it, stay
            if hit and not ref_parts(line) and pat != "warfare":
                if hit != pat:
                    pat, fig, mov, group, home = hit, None, None, None, None
                continue
        aside = next((a for a in ASIDES if a[0] in line), None)
        if aside:
            pat, fig, home, mov = aside[1], aside[2], aside[3], None
            mode = "vertical" if fig else mode
            continue
        if any(e in line for e in ASIDE_END):
            fig = home = mov = None
            continue
        if not pat:
            continue
        m = movement_of(line, pat)
        if m:
            mov = m
            continue
        if mode == "vertical" and re.match(r"^\d+\.\s", line) and pat != "warfare":
            fig, mov, home = re.sub(r"^\d+\.\s*", "", line).split(DASH)[0].strip(), None, None
            continue
        if not mov:
            continue
        parts = ref_parts(line)
        spans, problems = [], []
        for part in parts:
            got = spans_in(part, problems)
            spans += [s for s in got if s[1] is not None and check(s, problems, part)]
        if not spans and home and quoted(line):
            rows.append({"pattern": pat, "mode": mode, "figure": fig, "movement": mov,
                         "group": group, "ref": "", "home": home,
                         "claim": line, "spans": []})
            continue
        if not spans:
            if not parts:
                if not quoted(line) and len(line) < 60 and not line.endswith((".", ":")):
                    group = line
                last_prose = line
            continue
        claim = line.split(DASH, 1)[1] if DASH in line else (
            line if line != " ".join(parts) else last_prose)
        rows.append({"pattern": pat, "mode": mode, "figure": fig, "movement": mov,
                     "group": group, "ref": "; ".join(parts), "home": home,
                     "claim": claim, "spans": [[c, list(a), list(b)] for c, a, b in spans]})
    return rows


def original_words():
    """-> ({MACULA verse: {strong keys}}, {key: lemma}, mac(bsb verse id))"""
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8"))["moved"]
    to_mac = {b: m for m, b in moved.items()}

    def mac(v):
        b, c, n = v.split(".")
        r = f"{TO_MACULA[b]}.{c}.{n}"
        return to_mac.get(r, r)

    words, lemma = collections.defaultdict(set), {}
    hw, hl = hebrew_words()
    for ref, ws in hw.items():
        words[ref] |= {k for _n, k, _f in ws}
    lemma.update(hl)
    for ln in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if not r.get("word") or not r.get("strong") or r.get("lang") != "greek":
            continue
        s = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", r["strong"]))
        if s:
            words[r["ref"]].add("g" + s)
            lemma.setdefault("g" + s, r.get("lemma"))
    return words, lemma, mac


def main():
    rows = parse(SRC.read_text(encoding="utf-8"))
    words, lemma, mac = original_words()
    # the Berean text per verse (BSB numbering, MACULA book codes)
    text = {}
    for ln in gzip.open(OUT / "bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if "ref" in r:
            text[r["ref"]] = r["text"]

    def bsb_text(v):
        b, c, n = v.split(".")
        return text.get(f"{TO_MACULA[b]}.{c}.{n}", "")

    # every verse where each record is mentioned
    want = {r for _k, rs in FIGURES for r in rs}
    seen = collections.defaultdict(set)
    for ln in gzip.open(OUT / "mentions.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if r["record"] in want:
            seen[r["record"]].add(r["occurrence"].split("#")[0])

    def stem(w):
        return w.lower().rstrip("s")

    # Copilot's prose inside the additions quotes without references;
    # those passages are read by hand instead (READINGS)
    rows = [r for r in rows if not (r["home"] and not r["spans"])]
    for pat, fig, mov, ref, note in READINGS:
        probs = []
        sp = [s for s in spans_in(ref, probs) if s[1] is not None and check(s, probs, ref)]
        if probs or not sp:
            raise SystemExit(f"READINGS: {ref}: {probs or 'no span'}")
        rows.append({"pattern": pat, "mode": "reading", "figure": fig, "movement": mov,
                     "group": None, "ref": ref, "home": None, "claim": note,
                     "spans": [[c, list(a), list(b)] for c, a, b in sp]})
    kept = []
    for r in rows:
        key = (r["pattern"], r["movement"], r["ref"])
        if key in NARROW:
            new = NARROW[key]
            if new is None:
                continue
            probs = []
            sp = [s for s in spans_in(new, probs) if s[1] is not None and check(s, probs, new)]
            if probs or not sp:
                raise SystemExit(f"NARROW: {new}: {probs or 'no span'}")
            r["narrowed_from"], r["ref"] = r["ref"], new
            r["spans"] = [[c, list(a), list(b)] for c, a, b in sp]
        kept.append(r)
    dropped = len(rows) - len(kept)
    rows = kept
    for r in rows:
        vs = []
        for c, a, b in r["spans"]:
            vs += verses({"book": c, "start": a, "end": b})
        r["verses"] = vs
        p = PAT[r["pattern"]]
        here = set().union(*(words.get(mac(v), set()) for v in vs)) if vs else set()
        mk = keys(p[3].get(r["movement"], ""))
        r["word"] = sorted(here & mk)
        r["role_word"] = sorted(here & keys(p[4]))
        r["n"] = len(vs)
        if not vs:
            r["grade"] = "unresolved"
        elif len(vs) > 40:
            r["grade"] = "broad"
        elif r["word"]:
            r["grade"] = "word"
        elif r["role_word"]:
            r["grade"] = "role"
        else:
            r["grade"] = "hand" if r["mode"] == "reading" else "none"
        # the quote, against the Berean text of the cited verses
        qs = quoted(r["claim"])
        if qs and vs and len(vs) <= 40:
            t = " ".join(bsb_text(v) for v in vs).lower()
            ws = [w for q in qs for w in re.findall(r"[A-Za-z]+", q) if len(w) > 3]
            got = sum(1 for w in ws if stem(w) in t)
            r["quote"] = round(got / len(ws), 2) if ws else None

    # THE ROLE THE TEXT GIVES each vertical figure
    #
    # A ROLE WORD COUNTS ONLY WHERE IT IS RENDERED AS THE ROLE (item 7 of the
    # 2026-10-02 evaluation). The bridegroom's words have other senses --
    # חָתָן is also "son-in-law" (1 Sam 18:18), כַּלָּה "daughter-in-law",
    # בַּעַל "owner" and Baal -- and "YHWH and Israel" listed 69 verses, the
    # marriage law of Deut 24:1 among them. MACULA renders every occurrence,
    # so a role word stands only where its own rendering is the role's word.
    # AND A FIGURE AS PERVASIVE AS GOD is near every verse, so "within three
    # verses" says nothing: its candidates are read (ontology/role-declared.
    # jsonl), and only those read as the text giving the role are kept
    gloss = role_glosses()
    judged = collections.defaultdict(dict)
    for ln in (ROOT / "ontology" / "role-declared.jsonl").open(encoding="utf-8") \
            if (ROOT / "ontology" / "role-declared.jsonl").exists() else []:
        if ln.strip():
            j = json.loads(ln)
            judged[j["key"]][j["verse"]] = j["verdict"]
    declared = {}
    figs = sorted({(r["pattern"], r["figure"]) for r in rows if r["figure"]})
    for pat, fig in figs:
        low = fig.lower()
        recs = next((rs for k, rs in FIGURES if k in low), None)
        if not recs:
            continue
        rk = keys(PAT[pat][4])
        en = ROLE_EN.get(pat, ())
        near = set()
        for rec in recs:
            for v in seen.get(rec, ()):
                b, c, n = v.split(".")
                for d in range(-3, 4):
                    near.add(f"{b}.{c}.{int(n) + d}")
        hits = sorted(v for v in near if words.get(v, set()) & rk
                      and any(e in g for k in rk for g in gloss.get((v, k), ()) for e in en))
        key = f"{pat}|{fig}"
        if key in judged:
            hits = [v for v in hits if judged[key].get(v) == "yes"]
        declared[key] = {"records": recs, "verses": hits,
                         **({"read": True} if key in judged else {})}

    used = sorted({k for p in P for s in list(p[3].values()) + [p[4]] for k in s.split()})
    lemmas = {k: lemma.get(k) for k in used}
    (OUT / "role-patterns.json").write_text(json.dumps(
        {"rows": rows, "declared": declared, "lemmas": lemmas}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    write_report(rows, declared, lemmas, bsb_text)
    g = collections.Counter(r["grade"] for r in rows if r["mode"] != "reading")
    print(f"Copilot's citations {sum(g.values())}: " + ", ".join(f"{k} {v}" for k, v in g.most_common())
          + f"; read by hand {sum(1 for r in rows if r['mode'] == 'reading')}"
          + f"; narrowed {sum(1 for r in rows if r.get('narrowed_from'))}, dropped {dropped}")
    missing = [k for k, v in lemmas.items() if not v]
    print(f"keys {len(used)}; not in MACULA: {missing}")


GRADE = {"word": "the text says it", "role": "role word only", "none": "read it",
         "broad": "too broad", "unresolved": "not found", "hand": "read by hand"}


def write_report(rows, declared, lemmas, bsb_text):
    L = ["# Role patterns, grounded (2026-09-30)", "",
         "Source: `ontology/themes/role-patterns.md` (Copilot, verbatim, with three "
         "additions). Built by `tools/themes/role_patterns.py`. Each citation is resolved in "
         "the Berean text and tested for the movement's own word in the Hebrew or Greek "
         "(MACULA). **the text says it** = the movement's word is in the verses; **role word "
         "only** = only the role's word; **read it** = neither, the claim rests on "
         "description or interpretation; **too broad** = over 40 verses for one claim.", ""]
    cp = [r for r in rows if r["mode"] != "reading"]
    g = collections.Counter(r["grade"] for r in cp)
    L.append(f"Copilot's {len(cp)} citations: "
             + ", ".join(f"{GRADE[k]} {v}" for k, v in g.most_common())
             + f". Read by hand: {len(rows) - len(cp)} rows.")
    L += ["", "Keys used (lemma from MACULA): " + ", ".join(
        f"{k} {v}" for k, v in lemmas.items() if v), ""]
    L += ["## The draft, corrected", "",
          "2026-09-30: Copilot is the draft; the evidence overrides it. "
          "Each change with the verses that decide it, in the Berean text:", ""]
    for pid, fig, change, refs in OVERRIDES:
        L.append(f"- **{PAT[pid][1]}**" + (f" · {fig}" if fig else "") + f": {change}")
        probs = []
        for s in spans_in(refs, probs):
            for v in verses({"book": s[0], "start": list(s[1]), "end": list(s[2])}):
                L.append(f"  - {v}: {bsb_text(v)[:160]}")
        if probs:
            raise SystemExit(f"OVERRIDES: {refs}: {probs}")
    L.append("")
    for pid, role, movs, _w, _r in P:
        rs = [r for r in rows if r["pattern"] == pid]
        if not rs:
            continue
        L.append(f"## {role}: " + " → ".join(movs))
        gg = collections.Counter(r["grade"] for r in rs)
        L.append(f"{len(rs)} citations: " + ", ".join(f"{GRADE[k]} {v}" for k, v in gg.most_common()))
        L.append("")
        for mode in ("horizontal", "vertical", "reading"):
            ms = [r for r in rs if r["mode"] == mode]
            if not ms:
                continue
            L.append("### Read by hand (the additions)" if mode == "reading"
                     else f"### {mode.capitalize()} (Copilot)")
            cur = object()
            for r in ms:
                if r["figure"] != cur:
                    cur = r["figure"]
                    if cur:
                        L.append(f"- **{cur}**")
                        dk = declared.get(f"{pid}|{cur}")
                        if dk is not None:
                            L.append(f"  - role word near {', '.join(dk['records'])}: "
                                     + (", ".join(v for v in dk["verses"][:25]) or "**none**")
                                     + (f" (+{len(dk['verses']) - 25})" if len(dk["verses"]) > 25 else ""))
                q = r.get("quote")
                qn = f" · quote {int(q * 100)}%" if q is not None and q < 0.6 else ""
                ref = r["ref"] or ("located in " + (r["home"] or "") + ": " + ", ".join(r["verses"]))
                L.append(f"  - {r['movement']}: {ref} — *{GRADE[r['grade']]}*"
                         + (f" ({' '.join(r['word'] or r['role_word'])})" if r["grade"] in ("word", "role") else "")
                         + qn + f" — {r['claim'][:110]}")
            L.append("")
    (ROOT / "docs" / "review" / "ROLE-PATTERNS.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
