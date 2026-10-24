"""Event templates as nodes of the event classification (plan A.9).

Decisions of 2026-09-30 (event templates confirmed against
the text): Copilot's 43 templates (37 sequences) become EIGHT families,
each a pattern node with optional stages; where a template's stages reach
past one event, the ARC of events is the instance; TURNING (repentance or
intercession), CRY and OBJECTION are added as optional stages where the text
shows them; symbolic stages only where the text declares them.

Graph shape (no new relation types):
  family            pattern node      tpl_<family>
  stage kind        concept node      tplstage_<kind>
  instance          the event, or an arc node (type event, kind "arc") the
                    events it spans are part_of;  instance -instance_of-> family
  stage             passage node (its verse ranges)
                    stage -part_of-> instance;  stage -instance_of-> stage kind
Every node carries the verses it rests on; every stage its ranges, checked
against the Berean text, with the clause stamps and original words that
support it (tools/events/templates.py's evidence).

The APPLICATIONS table below is where each of Copilot's templates is mapped
to a family, its stages relabelled to the family's vocabulary, and every
departure from Copilot noted. Relabelled or reassigned instances are
`conjectured` -- a reading, with its reason -- to be confirmed by hand.

    python tools/events/template_nodes.py
      -> ontology/entities/event-templates.jsonl
         ontology/relations/event-templates.jsonl
         out/event-template-instances.json     (the server's view)
         docs/review/EVENT-TEMPLATE-NODES.md
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "themes"))
sys.path.insert(0, str(ROOT / "tools" / "events"))
from theme_map import BOOKS, check, spans_in  # noqa: E402
from event_nodes import TO_MACULA, label_of, verses, vkey  # noqa: E402
import importlib.util  # noqa: E402
# by path: tools/templates.py is another module of the same name
_spec = importlib.util.spec_from_file_location("event_templates_check",
                                               ROOT / "tools" / "events" / "templates.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
KINDS = _mod.KINDS

ENT = ROOT / "ontology" / "entities" / "event-templates.jsonl"
REL = ROOT / "ontology" / "relations" / "event-templates.jsonl"
VIEW = OUT / "event-template-instances.json"
SOURCE = "event-templates"

# ---- the eight families: (id, name, [(stage kind, optional, added?)], note)
FAMILIES = [
    # NAMES A READER WOULD USE. 2026-09-30: give these names, searchable
    # by really intuitive names, perhaps with some kind of type prefix. The
    # node's name is "Story pattern: <this>" (PREFIX below).
    # mercy optional (2026-09-30, made optional): Achan, Ananias
    # and Sapphira and the fall of Babylon have none -- 7 of 10 carry it
    ("judgment_mercy", "Sin, judgment and mercy",
     [("fall", True, False), ("judgment", False, False), ("turning", True, True),
      ("mercy", True, False), ("restoration", True, False)],
     "A wrong, judgment on it, a turning (repentance or intercession), mercy, and "
     "restoration. Some instances end at judgment."),
    ("deliverance", "Cry and rescue",
     [("fall", True, True), ("threat", False, False), ("cry", True, True),
      ("deliverance", False, False), ("judgment_on_oppressor", True, False),
      ("praise", True, False)],
     "A threat or bondage, a cry, deliverance, the oppressor judged, praise. The text "
     "states it in Judges 2:11–19: they did evil, He gave them over, they groaned, He "
     "raised up judges who saved them."),
    # "exile" and "commissioning" folded into descent and restoration (each
    # carried by 2 of 6), humbling optional (4 of 6): 2026-09-30, folded
    # in and made optional. Descent stays required: after the
    # fold all six stories carry it.
    ("descent_return", "Brought low, raised up",
     [("descent", False, False), ("humbling", True, False), ("restoration", False, False)],
     "Going down — into prison, exile or loss — often a time of humbling, and being "
     "raised again, often to a task."),
    ("call", "Called, reluctant, sent",
     [("call", False, False), ("objection", True, True), ("sign", False, False),
      ("mission", False, False)],
     "God calls, the one called objects, a sign is given, and the mission begins."),
    ("promise", "Promise kept",
     [("promise", False, False), ("obstacle", True, False), ("fulfilment", False, False)],
     "A promise, what stands in its way (barrenness, doubt), and its fulfilment."),
    ("word_order", "The word brings order",
     [("chaos", True, False), ("word", False, False), ("order", False, False),
      ("presence", True, False)],
     "The word spoken, order made by it, and a presence or memorial at the end."),
    ("testing_failure", "Tested and failed",
     [("testing", False, False), ("failure", False, False), ("judgment", False, False)],
     "A test failed and its consequence — the counter-shape of deliverance and call."),
    # a prayer before the life is given back: Elijah (1Kgs 17:20-21), Elisha
    # (2Kgs 4:33), Jesus at Lazarus' tomb (John 11:41-42), Peter (Acts 9:40)
    # -- four instances, enough to carry an optional stage (2026-09-30:
    # optional steps need to have enough participation to justify them)
    ("death_life", "Death to life",
     [("death", False, False), ("cry", True, True), ("life", False, False)],
     "Death, sometimes a prayer, and life given back."),
    # ADDED 2026-09-30 (plan A.9, P-66). A reader's find: a variation on the
    # first pattern where a remnant is saved - the flood, Sodom, Jesus being
    # prominent examples. The text states it: Jesus pairs Noah and Lot (Luke
    # 17:26-30), Peter says the Lord "preserved Noah ... rescued Lot" and
    # "knows how to rescue the godly" (2Pet 2:5-9), Isaiah "unless the LORD
    # had left us a few survivors, we would have become like Sodom" (Isa 1:9).
    ("remnant", "Judgment and a remnant spared",
     [("corruption", True, False), ("set_apart", True, True), ("judgment", False, False),
      ("remnant", False, False), ("new_beginning", True, False)],
     "Wickedness, those to be spared set apart (the ark, led out, the mark), a judgment "
     "that takes the rest, a remnant left, and sometimes a new beginning. Jesus draws it "
     "from Noah and Lot (Luke 17:26–30)."),
    # From the Copilot draft's twelve, kept where the text marks the stages:
    ("tested_faithful", "Tested and found faithful",
     [("testing", False, False), ("faithfulness", False, False), ("reward", False, False)],
     "A test the text names as a test (\"God tested Abraham\", Gen 22:1), a faithful "
     "answer, and what follows it — the counter-shape of Tested and failed."),
    ("evil_to_good", "Meant for evil, turned to good",
     [("intent", False, False), ("reversal", False, False), ("good", False, False)],
     "Harm planned, the plan turned back, and good from it. The text says it of itself: "
     "\"what you intended against me for evil, God intended for good\" (Gen 50:20); and "
     "Paul says it of all things, \"God works all things together for the good of those "
     "who love Him\" (Rom 8:28) -- read here as the same pattern, stated generally."),
    ("recognition", "Hidden, then revealed",
     [("hidden", False, False), ("revealed", False, False)],
     "Someone not known for who they are (\"they did not recognize him\"), then made "
     "known (\"I am Joseph\")."),
    # Suggested from the text and chosen by hand, 2026-09-30 (decision card):
    ("barren", "The barren woman conceives",
     [("barren", False, False), ("cry", True, True), ("promise", True, False),
      ("birth", False, False)],
     "A woman the text calls barren, sometimes a prayer or a promise, and a son born: "
     "Sarah, Rebekah, Rachel, Manoah's wife, Hannah, Elizabeth."),
    ("younger", "The younger over the elder",
     [("elder", False, False), ("contest", True, False), ("chosen", False, False)],
     "The elder named, sometimes his protest, and the younger preferred. Stated at the "
     "start: \"the older will serve the younger\" (Gen 25:23)."),
    ("well", "Meeting at a well, then marriage",
     [("journey", False, False), ("well", False, False), ("water", False, False),
      ("telling", False, False), ("marriage", False, False)],
     "A journey to a far country, a well, water drawn, a girl running home to tell it, "
     "and a marriage: Rebekah, Rachel, Zipporah."),
    ("covenant_renewal", "Covenant renewed before the people",
     [("assembly", True, False), ("reading", True, False), ("pledge", False, False),
      ("sealing", False, False)],
     "The people gathered, the covenant read or set out, their answer (\"we will serve "
     "the LORD\"), and the covenant made or sealed."),
]
STAGE_NAME = {"judgment_on_oppressor": "judgment on the oppressor", "turning": "turning",
              "fulfilment": "fulfilment", "set_apart": "set apart",
              "new_beginning": "new beginning", "chosen": "the younger chosen",
              "elder": "the elder", "telling": "running to tell"}
# passages where the TEXT states a pattern of itself (the pattern node cites
# them first, as it cites Judges 2:11 for Cry and rescue)
DECLARED_REFS = {"deliverance": ["Judg 2:11"],
                 "remnant": ["Luke 17:26", "2Pet 2:5", "Isa 1:9", "1Pet 3:20"],
                 # Rom 8:28 states it generally (2026-09-30: one
                 # link -- a stated text, not a hub)
                 "evil_to_good": ["Gen 50:20", "Deut 23:5", "Rom 8:28"],
                 "younger": ["Gen 25:23"]}
# instances whose one event card is much larger than the story (a gospel
# event holding every telling): made an arc of their own
FORCE_ARC = {"Mary at the tomb", "The nations left to test Israel", "Deborah and Barak"}
# which evidence kind (templates.KINDS) tests a family stage
EVIDENCE = {"threat": "bondage", "humbling": "humility", "praise": "exaltation",
            "judgment_on_oppressor": "judgment", "turning": "repentance",
            "sign": "empowerment", "call": "anointing", "obstacle": "testing",
            "life": "resurrection", "fulfilment": "fulfillment"}

# ---- Copilot's applications, mapped. (title, family, arc title or None,
# [(stage, ranges)], conjectured?, note). Ranges in the Berean's numbering.
C = True
APPLICATIONS = [
    ("Cain builds a city", "judgment_mercy", "Cain (Gen 4:8–15)",
     [("fall", "Genesis 4:8"), ("judgment", "Genesis 4:11–12"), ("mercy", "Genesis 4:15")], C,
     "Copilot: fall → exile → human striving (4:8; 4:11–16; 4:17). The text gives a "
     "judgment (4:11–12) and a mercy, the mark (4:15); the city (4:17) is held, no family "
     "stage."),
    ("Abraham rescues Lot", "deliverance", None,
     [("threat", "Genesis 14:1–12"), ("deliverance", "Genesis 14:13–16")], False, ""),
    ("Hagar & Ishmael", "deliverance", None,
     [("threat", "Genesis 21:8–14"), ("cry", "Genesis 21:15–17"),
      ("deliverance", "Genesis 21:18–19"), ("praise", "Genesis 21:20–21")], C,
     "Copilot: judgment → mercy → restoration. The text is an expulsion, not a judgment on "
     "Hagar; she weeps and God hears the boy (21:16–17), then opens her eyes to a well."),
    # "skip" holds the place of a stage folded away, so the stages after it
    # keep their numbered ids (readers' notes point at ids)
    ("Jacob purges idols", "descent_return", None,
     [("descent", "Genesis 34:25–31"), ("restoration", "Genesis 35:1–15"),
      ("skip", None)], C,
     "Copilot: exile → return → covenant renewal (Gen 34 as background). Relabelled: "
     "Shechem's aftermath, the return to Bethel, the name Israel and the charge to be "
     "fruitful."),
    ("Joseph interprets dreams", "descent_return", "Joseph in Egypt (Gen 39:20–41:44)",
     [("descent", "Genesis 39:20–23"), ("humbling", "Genesis 40:1–23"),
      ("restoration", "Genesis 41:14–44")], False,
     "The arc runs past the one event: prison (39), the dreams (40), Pharaoh (41)."),
    ("Moses flees to Midian", "descent_return", None,
     [("descent", "Exodus 2:11–20"), ("skip", None),
      ("humbling", "Exodus 2:21–22"), ("restoration", "Exodus 3:10")], C,
     "Stages trimmed so they do not overlap (Copilot: 2:11–15, 2:15–22, 2:21–22). The "
     "flight to Midian is now part of the descent; the raising is the call from the bush, "
     "\"I am sending you to Pharaoh\" (3:10) -- a reading."),
    ("Burning bush", "call", "The call of Moses (Exod 3:1–4:23)",
     [("call", "Exodus 3:1–10"), ("objection", "Exodus 3:11–13; Exodus 4:10–17"),
      ("sign", "Exodus 3:14–22; Exodus 4:1–9"), ("mission", "Exodus 4:18–23")], C,
     "Copilot: anointing → empowerment → mission. Moses objects five times (3:11, 3:13, 4:1, "
     "4:10, 4:13); the name and the signs answer him. The mission (4:18–23) is past the "
     "event, so the arc is the instance."),
    ("Red Sea", "deliverance", "The Red Sea (Exod 14:1–15:21)",
     [("threat", "Exodus 14:1–9"), ("cry", "Exodus 14:10–12"),
      ("deliverance", "Exodus 14:13–25"), ("judgment_on_oppressor", "Exodus 14:26–31"),
      ("praise", "Exodus 15:1–21")], C,
     "Copilot: bondage → deliverance → covenant. The Israelites cry out (14:10); the "
     "Egyptians are drowned (14:26–31); Copilot's covenant stage is the Song (15:1–21), "
     "praise. The Song is past the event: the arc is the instance."),
    ("Golden calf", "judgment_mercy", "The golden calf (Exod 32–34)",
     [("fall", "Exodus 32:1–6"), ("judgment", "Exodus 32:7–10; Exodus 32:15–29"),
      ("turning", "Exodus 32:11–14; Exodus 32:30–32"), ("mercy", "Exodus 33:12–23"),
      ("restoration", "Exodus 34:1–10")], C,
     "Moses intercedes twice (32:11–14, 32:30–32) inside Copilot's judgment stage; the "
     "judgment is split around them. Mercy and restoration are Exod 33–34: the arc."),
    ("Tabernacle", "word_order", "The tabernacle (Exod 25–40)",
     [("word", "Exodus 25–31"), ("order", "Exodus 35–39"),
      ("presence", "Exodus 40:34–38")], False,
     "Copilot's line names chaos, but its stages begin at the word; no chaos stage."),
    ("Twelve spies", "testing_failure", None,
     [("testing", "Numbers 13:1–25"), ("failure", "Numbers 13:26–14:10"),
      ("judgment", "Numbers 14:26–35")], False,
     "Moses' intercession and the pardon (14:13–20) sit between failure and judgment: this "
     "event also has the judgment-and-mercy shape inside it."),
    ("Bronze serpent", "judgment_mercy", None,
     [("fall", "Numbers 21:4–5"), ("judgment", "Numbers 21:6"), ("turning", "Numbers 21:7"),
      ("mercy", "Numbers 21:8"), ("restoration", "Numbers 21:9")], C,
     "Copilot: judgment 21:4–6, mercy 21:7–8. The people speak against God (21:5), then "
     "confess and Moses prays (21:7): the turning."),
    ("Jordan crossing", "word_order", None,
     [("word", "Joshua 3:7–13"), ("chaos", "Joshua 3:14–16"),
      ("order", "Joshua 3:17; Joshua 4:10–13"), ("presence", "Joshua 4:1–9; Joshua 4:20–24")],
     C, "The text's order is word, then the waters stand; the memorial stones (presence) "
        "are cut out of Copilot's order stage."),
    ("Jericho", "deliverance", None,
     [("threat", "Joshua 6:1"), ("deliverance", "Joshua 6:2–20"),
      ("judgment_on_oppressor", "Joshua 6:21–27")], False, ""),
    ("Achan", "judgment_mercy", "Achan and Ai (Josh 7:1–8:29)",
     [("fall", "Joshua 7:1"), ("judgment", "Joshua 7:2–5; Joshua 7:10–26"),
      ("turning", "Joshua 7:6–9"), ("restoration", "Joshua 8:1–29")], C,
     "Joshua falls before the ark and prays (7:6–9). No mercy stage; the restoration "
     "(Ai) is past the event: the arc."),
    ("Gideon’s fleece", "call", "The call of Gideon (Judg 6:11–7:8)",
     [("call", "Judges 6:11–14"), ("objection", "Judges 6:15; Judges 6:36–37"),
      ("sign", "Judges 6:17–21; Judges 6:38–40"), ("mission", "Judges 7:1–8")], C,
     "Copilot: testing → reassurance → commissioning. Gideon objects (6:15) and asks for "
     "signs twice (6:17, 6:36–37): the call shape, across the chapter."),
    ("Gideon’s 300", "deliverance", "Gideon against Midian (Judg 6:33–7:25)",
     [("threat", "Judges 6:33"), ("deliverance", "Judges 7:9–25")], C,
     "Copilot's 'order' stage (the reduction, 7:1–8) is the call's mission above; held here."),
    ("Samson & Delilah", "judgment_mercy", None,
     [("fall", "Judges 16:4–20"), ("judgment", "Judges 16:21"), ("turning", "Judges 16:28"),
      ("mercy", "Judges 16:29–30")], C,
     "Copilot: fall → death → resurrection (symbolic). The symbolic stage is not declared "
     "by the text and is dropped; Samson calls on the LORD (16:28) and is strengthened."),
    ("Boaz redeems Ruth", "promise", None,
     [("promise", "Ruth 4:11–12"), ("fulfilment", "Ruth 4:13–17")], C,
     "Copilot: restoration → covenant → mission. The elders' blessing (4:11–12) and 'the "
     "LORD enabled her to conceive' (4:13) read as promise and fulfilment."),
    ("Solomon’s judgment", "word_order", None,
     [("chaos", "1 Kings 3:16–22"), ("word", "1 Kings 3:23–25"), ("order", "1 Kings 3:26–28")],
     C, "Copilot: chaos → wisdom → order. The king's word (3:24–25) makes the order; the "
        "wisdom is named at 3:28."),
    ("Naaman", "descent_return", None,
     [("descent", "2 Kings 5:1–12"), ("humbling", "2 Kings 5:13–14"),
      ("restoration", "2 Kings 5:15–19")], False,
     "Trimmed so the stages do not overlap (Copilot: 5:1–14, 5:13–14, 5:14–19)."),
    ("Shunammite’s son", "death_life", None,
     # the prayer listed last: stage ids are numbered by position, and the
     # existing death/life stage nodes keep theirs (readers' notes point at ids)
     [("death", "2 Kings 4:18–20"), ("life", "2 Kings 4:34–37"), ("cry", "2 Kings 4:33")],
     False, "Elisha shuts the door and prays to the LORD (4:33) before the boy lives."),
    ("Ezra’s return", "descent_return", "The return under Ezra (Ezra 1–10)",
     [("descent", "Ezra 2:1"), ("restoration", "Ezra 1:1–4; Ezra 7:1–10"), ("skip", None)], C,
     "Copilot: exile → return → covenant renewal. The descent is the exile Ezra names: "
     "\"carried away to Babylon by Nebuchadnezzar\" (2:1); the return and Ezra's coming, "
     "the raising. Ezra 9–10 (the confession) is a turning, not part of this shape."),
    ("Nehemiah’s walls", "word_order", None,
     [("chaos", "Nehemiah 1:1–4; Nehemiah 2:11–15"), ("word", "Nehemiah 2:17–18"),
      ("order", "Nehemiah 3–4"), ("presence", "Nehemiah 6:15–16")], C,
     "Copilot: chaos → order → restoration. 'Let us rebuild' (2:17–18) is the word; the "
     "enemies see 'this work had been done by our God' (6:16)."),
    ("Esther intervenes", "deliverance", "Esther and Purim (Esth 3–9)",
     [("threat", "Esther 3:8–15"), ("cry", "Esther 4:1–3"), ("deliverance", "Esther 7:1–10"),
      ("judgment_on_oppressor", "Esther 9:1–16"), ("praise", "Esther 9:17–32")], C,
     "Copilot's two templates (Esther intervenes; Purim) are one deliverance: the decree, "
     "Mordecai's loud cry (4:1), Haman hanged, the enemies struck, the feast."),
    ("Job restored", "descent_return", "Job (Job 1–42)",
     [("descent", "Job 1–2"), ("humbling", "Job 3:1–42:6"),
      ("restoration", "Job 42:10–17")], C,
     "Copilot: descent → ascent → restoration. God's speeches (38–41) end in Job's "
     "repentance (42:1–6): the humbling."),
    ("Fiery furnace", "deliverance", None,
     [("threat", "Daniel 3:1–18"), ("deliverance", "Daniel 3:19–30")], False, ""),
    ("Nebuchadnezzar’s madness", "judgment_mercy", None,
     [("fall", "Daniel 4:28–30"), ("judgment", "Daniel 4:31–33"), ("turning", "Daniel 4:34"),
      ("mercy", "Daniel 4:36"), ("restoration", "Daniel 4:37")], C,
     "Copilot: descent → judgment → restoration. The pride (4:30), the sentence, 'I lifted "
     "my eyes to heaven' (4:34)."),
    ("Lions’ den", "deliverance", None,
     [("threat", "Daniel 6:6–16"), ("deliverance", "Daniel 6:17–23"),
      ("judgment_on_oppressor", "Daniel 6:24"), ("praise", "Daniel 6:25–28")], False, ""),
    ("Jonah swallowed", "death_life", "Jonah (Jonah 1:15–2:10)",
     [("death", "Jonah 1:15–17"), ("life", "Jonah 2:10")], False,
     "Symbolic, and kept because the text declares it: 'as Jonah was three days and three "
     "nights in the belly of the great fish' (Matt 12:40)."),
    ("Nineveh repents", "judgment_mercy", None,
     [("judgment", "Jonah 3:1–4"), ("turning", "Jonah 3:5–9"), ("mercy", "Jonah 3:10")], C,
     "Copilot's 'mercy' (3:5–9) is the repentance — the turning; the mercy is God "
     "relenting (3:10)."),
    ("Birth of John", "promise", None,
     [("promise", "Luke 1:13–17"), ("obstacle", "Luke 1:18–22"),
      ("fulfilment", "Luke 1:57–66")], C,
     "Zechariah's doubt and silence (1:18–22) is the obstacle."),
    ("Ananias & Sapphira", "judgment_mercy", None,
     [("fall", "Acts 5:1–4"), ("judgment", "Acts 5:5–10")], C,
     "Judgment without mercy. Copilot's 'purification' (5:11, the fear) is held."),
    # FOLDED IN FROM THE ENEMY ROLE PATTERN (plan A.10). 2026-09-30:
    # the recommendations on folding in patterns were agreed -- Enemy →
    # oppression → deliverance → victory is this family without its cry.
    # These are the Enemy list's stories not already here; its collective
    # enemies (Satan, sin, death, the beast) tell no rescue as a passage and
    # are held (tools/themes/role_patterns.py).
    ("David and Goliath", "deliverance", "David and Goliath (1 Sam 17)",
     [("threat", "1 Samuel 17:4–11"), ("deliverance", "1 Samuel 17:45–50"),
      ("judgment_on_oppressor", "1 Samuel 17:51–53")], False,
     "From the Enemy list: 'the LORD saves … the battle is the LORD's' (17:47)."),
    ("Sennacherib against Jerusalem", "deliverance",
     "Sennacherib against Jerusalem (2 Kgs 18:13–19:37)",
     [("threat", "2 Kings 18:13–17"), ("cry", "2 Kings 19:1–4; 2 Kings 19:14–19"),
      ("deliverance", "2 Kings 19:35"), ("judgment_on_oppressor", "2 Kings 19:36–37")], False,
     "From the Enemy list. Hezekiah's prayer is the cry: 'please save us from his hand' (19:19)."),
    ("Legion", "deliverance", "Legion (Mark 5:1–20)",
     [("threat", "Mark 5:2–5"), ("deliverance", "Mark 5:8–13"), ("praise", "Mark 5:19–20")], C,
     "From the Enemy list: a bondage no one could subdue (5:4) as the threat; 'tell them how "
     "much the Lord has done for you, and what mercy He has shown you' (5:19) as the praise."),
    ("Paul and Silas freed", "deliverance", "Paul and Silas at Philippi (Acts 16:22–34)",
     [("threat", "Acts 16:22–24"), ("cry", "Acts 16:25"), ("deliverance", "Acts 16:26"),
      ("praise", "Acts 16:34")], C,
     "From the Enemy list. Praying and singing at midnight (16:25) as the cry; they do not "
     "leave when the doors open, and the rescue the text dwells on is the jailer's: 'what must "
     "I do to be saved?' (16:30)."),
    ("Peter freed", "deliverance", None,
     [("threat", "Acts 12:3–4; Acts 12:6"), ("cry", "Acts 12:5"),
      ("deliverance", "Acts 12:7–11")], C,
     "The church prays earnestly (12:5): the cry."),
    ("Fall of Babylon", "judgment_mercy", "The fall of Babylon (Rev 17–19:8)",
     [("fall", "Revelation 17:1–6"), ("judgment", "Revelation 17:7–18:24"),
      ("restoration", "Revelation 19:1–8")], C,
     "Copilot: judgment → fall → restoration. Its 'fall' is Babylon falling (the judgment); "
     "her sin is 17:1–6. No mercy."),
    # ---- ADDED 2026-09-30 (P-66): the remnant pattern and the draft's
    # candidates the text carries (ontology/themes/story-patterns-missing.md)
    ("The flood", "remnant", "The flood (Gen 6–9)",
     [("corruption", "Genesis 6:5–7; Genesis 6:11–12"), ("set_apart", "Genesis 7:1; Genesis 7:16"),
      ("judgment", "Genesis 7:21–22"), ("remnant", "Genesis 7:23; Genesis 8:1"),
      ("new_beginning", "Genesis 9:1; Genesis 9:8–11")], False,
     "\"Only Noah and those with him in the ark remained\" (7:23); the LORD shut him in (7:16). "
     "One of the two stories Jesus draws the pattern from (Luke 17:26–27)."),
    ("Sodom", "remnant", None,
     [("corruption", "Genesis 18:20–21; Genesis 19:4–5"), ("set_apart", "Genesis 19:12–17"),
      ("judgment", "Genesis 19:24–25"), ("remnant", "Genesis 19:29")], False,
     "\"Get up! ... or you will be swept away in the punishment of the city\" (19:15); \"He "
     "brought Lot out of the catastrophe\" (19:29). The other story Jesus draws it from "
     "(Luke 17:28–29)."),
    ("Korah", "remnant", None,
     [("corruption", "Numbers 16:1–3"), ("set_apart", "Numbers 16:23–27"),
      ("judgment", "Numbers 16:31–35"), ("remnant", "Numbers 16:46–48")], C,
     "\"Move away now from the tents of these wicked men ... or you will be swept away\" "
     "(16:26), the words said to Lot (Gen 19:15). The remnant is the congregation spared: "
     "Aaron \"stood between the living and the dead\" (16:48)."),
    ("Rahab spared", "remnant", None,
     [("set_apart", "Joshua 6:17; Joshua 6:22–23"), ("judgment", "Joshua 6:21; Joshua 6:24"),
      ("remnant", "Joshua 6:25")], False,
     "\"Only Rahab the prostitute and all those with her in her house will live\" (6:17); "
     "\"she has lived among the Israelites to this day\" (6:25). No corruption stage: the "
     "chapter names none for Jericho."),
    ("Elijah’s seven thousand", "remnant", None,
     [("corruption", "1 Kings 19:14"), ("judgment", "1 Kings 19:15–17"),
      ("remnant", "1 Kings 19:18"), ("new_beginning", "1 Kings 19:19–21")], False,
     "\"I have reserved seven thousand in Israel — all whose knees have not bowed to Baal\" "
     "(19:18); the charge passes to Elisha (19:19–21)."),
    ("The mark on the foreheads", "remnant", "The mark on the foreheads (Ezek 9)",
     [("set_apart", "Ezekiel 9:4"), ("judgment", "Ezekiel 9:5; Ezekiel 9:7"),
      ("remnant", "Ezekiel 9:6"), ("corruption", "Ezekiel 9:9")], False,
     "A vision, whose city the text names (9:4, 9:9): \"do not go near anyone who has the "
     "mark\" (9:6); Ezekiel asks, \"will You destroy the entire remnant of Israel?\" (9:8)."),
    ("The Passover", "remnant", "The Passover (Exod 12)",
     [("set_apart", "Exodus 12:12–13; Exodus 12:23"), ("judgment", "Exodus 12:29–30"),
      ("remnant", "Exodus 12:27"), ("new_beginning", "Exodus 12:31")], C,
     "The blood distinguishes the houses (12:13) and the LORD \"spared our homes\" (12:27). "
     "A reading: the text does not call Israel a remnant here, and the same night is the "
     "Red Sea story's beginning."),
    ("Jerusalem’s remnant", "remnant", "Jerusalem falls, a remnant left (2 Kgs 24–25; Ezra 1–9)",
     [("corruption", "2 Kings 24:3–4"), ("judgment", "2 Kings 25:8–11"),
      ("remnant", "2 Kings 25:12; 2 Kings 25:22; Ezra 9:8; Ezra 9:15"),
      ("new_beginning", "Ezra 1:1–4")], C,
     "\"The captain of the guard left behind some of the poorest of the land\" (25:12); the "
     "returned community calls itself the remnant: \"we remain this day as a remnant\" "
     "(Ezra 9:15)."),
    ("Abraham tested", "tested_faithful", None,
     [("testing", "Genesis 22:1–2"), ("faithfulness", "Genesis 22:9–12"),
      ("reward", "Genesis 22:15–18")], False,
     "\"God tested Abraham\" (22:1); \"now I know that you fear God\" (22:12); \"because you "
     "have done this ... I will surely bless you\" (22:16–17)."),
    ("Daniel’s test", "tested_faithful", "Daniel’s test (Dan 1)",
     [("testing", "Daniel 1:8–14"), ("faithfulness", "Daniel 1:15–16"),
      ("reward", "Daniel 1:17–20")], False,
     "\"Please test your servants for ten days\" (1:12); \"they entered the king's service\" "
     "(1:19)."),
    ("Jesus tempted", "tested_faithful", None,
     [("testing", "Matthew 4:1–3"), ("faithfulness", "Matthew 4:4–10"),
      ("reward", "Matthew 4:11")], C,
     "\"Led by the Spirit into the wilderness to be tempted\" (4:1); \"angels came and "
     "ministered to Him\" (4:11) read as what follows faithfulness."),
    ("Job tested", "tested_faithful", "Job (Job 1–42)",
     [("testing", "Job 1:6–19"), ("faithfulness", "Job 1:20–22"),
      ("reward", "Job 42:10–17")], C,
     "\"In all this, Job did not sin\" (1:22). The same arc is Brought low, raised up."),
    ("Hezekiah’s treasures", "testing_failure", "Hezekiah shows his treasures (2 Kgs 20; 2 Chr 32)",
     [("testing", "2 Chronicles 32:31"), ("failure", "2 Kings 20:12–15"),
      ("judgment", "2 Kings 20:16–18")], C,
     "\"God left him alone to test him, that He might know all that was in Hezekiah's heart\" "
     "(2 Chr 32:31); the envoys are shown everything (2 Kgs 20:13); \"nothing will be left\" "
     "(20:17)."),
    ("Joseph’s brothers", "evil_to_good", "Joseph and his brothers (Gen 37–50)",
     [("intent", "Genesis 37:18–20"), ("reversal", "Genesis 45:5–8"),
      ("good", "Genesis 50:19–21")], False,
     "The text's own statement of the pattern: \"what you intended against me for evil, God "
     "intended for good ... to preserve the lives of many people\" (50:20)."),
    ("Balaam hired to curse", "evil_to_good", "Balaam hired to curse (Num 22–24; Deut 23)",
     [("intent", "Numbers 22:4–6"), ("reversal", "Numbers 24:10"),
      ("good", "Deuteronomy 23:5")], False,
     "\"I summoned you to curse my enemies, but behold, you have persisted in blessing them\" "
     "(Num 24:10); \"the LORD your God turned the curse into a blessing for you\" (Deut 23:5)."),
    ("Haman’s plot", "evil_to_good", "Esther and Purim (Esth 3–9)",
     [("intent", "Esther 3:6"), ("reversal", "Esther 7:9–10; Esther 9:1"),
      ("good", "Esther 9:22; Esther 9:24–25")], False,
     "Hanged on the gallows he built (7:10); \"their plan was overturned\" (9:1); \"their "
     "sorrow turned to joy\" (9:22)."),
    ("Joseph makes himself known", "recognition", "Joseph makes himself known (Gen 42–45)",
     [("hidden", "Genesis 42:7–8"), ("revealed", "Genesis 45:1–4")], False,
     "\"They did not recognize him\" (42:8); \"I am Joseph\" (45:3)."),
    ("Esther’s people", "recognition", "Esther's hidden people (Esth 2–7)",
     [("hidden", "Esther 2:10"), ("revealed", "Esther 7:3–6")], C,
     "\"Esther did not reveal her people\" (2:10); \"my people and I have been sold out to "
     "destruction\" (7:4)."),
    ("Road to Emmaus", "recognition", None,
     [("hidden", "Luke 24:15–16"), ("revealed", "Luke 24:30–31")], False,
     "\"Their eyes were kept from recognizing Him\" (24:16); \"their eyes were opened and "
     "they recognized Jesus\" (24:31)."),
    ("Mary at the tomb", "recognition", "Mary Magdalene at the tomb (John 20:11–18)",
     [("hidden", "John 20:14–15"), ("revealed", "John 20:16")], False,
     "\"She did not recognize that it was Jesus\" (20:14); \"Mary.\" ... \"Rabboni!\" (20:16)."),
    ("The call of Jeremiah", "call", "The call of Jeremiah (Jer 1:4–10)",
     [("call", "Jeremiah 1:4–5"), ("objection", "Jeremiah 1:6"), ("sign", "Jeremiah 1:9"),
      ("mission", "Jeremiah 1:7–8; Jeremiah 1:10")], False,
     "\"I surely do not know how to speak, for I am only a child!\" (1:6); the LORD touches "
     "his mouth (1:9)."),
    ("The call of Isaiah", "call", "The call of Isaiah (Isa 6)",
     [("objection", "Isaiah 6:5"), ("sign", "Isaiah 6:6–7"), ("call", "Isaiah 6:8"),
      ("mission", "Isaiah 6:9–10")], C,
     "\"Woe is me ... a man of unclean lips\" (6:5) is unworthiness, not a refusal; the coal "
     "(6:6–7) answers it. The text's order: objection and sign before the call (6:8)."),
    ("Isaac promised", "promise", "Isaac promised and born (Gen 18–21)",
     [("promise", "Genesis 18:10; Genesis 18:14"), ("obstacle", "Genesis 18:11–13"),
      ("fulfilment", "Genesis 21:1–2")], False,
     "\"The LORD did for Sarah what He had promised\" (21:1); she had laughed, being past "
     "age (18:11–12)."),
    ("Samson promised", "promise", "Samson promised and born (Judg 13)",
     [("obstacle", "Judges 13:2"), ("promise", "Judges 13:3–5"), ("fulfilment", "Judges 13:24")],
     False,
     "\"Barren and had no children\" (13:2); \"you will conceive and give birth to a son\" "
     "(13:3); \"the woman gave birth to a son and named him Samson\" (13:24)."),
    ("Amos intercedes", "judgment_mercy", "Amos intercedes (Amos 7:1–6)",
     [("judgment", "Amos 7:1; Amos 7:4"), ("turning", "Amos 7:2; Amos 7:5"),
      ("mercy", "Amos 7:3; Amos 7:6")], False,
     "Twice: \"Lord GOD, please forgive!\" (7:2) ... \"So the LORD relented\" (7:3, 7:6)."),
    # A reader's reading of the remnant pattern, on the text's explanation
    # (2026-09-30): the cross and the resurrection, with the explanatory text
    # used to support the assertion. The corruption stage is the reader's too:
    # there is plenty of support for CORRUPTION in the cross and resurrection,
    # including Romans 3:10-19,23, and one could go back to Genesis 3;
    # Romans 5:12 is actually the best of both. It goes last so the other
    # stage ids keep their numbers. The other four stages' verses are the
    # reader's as well: for judgment Romans 2:5-6 and Matthew 27:46; for
    # set apart John 17:24; for remnant John 3:16 and Matthew 28:19-20; for
    # new beginning Matthew 28:5-7 and 2 Cor 4:17. The id drops the
    # parenthesis, so the title names the narrated chapters without moving it.
    # CORRECTED 2026-10-01, before going live: the new-beginning verse given
    # as 2 Corinthians 4:17 was meant to be 2 Corinthians 5:17. 5:17: "if anyone
    # is in Christ, he is a new creation ... the new has come!" The verse
    # below is the one meant.
    ("The cross and the resurrection", "remnant",
     "The cross and the resurrection (Matt 27–28)",
     [("judgment", "Romans 2:5–6; Matthew 27:46"), ("set_apart", "John 17:24"),
      ("remnant", "John 3:16; Matthew 28:19–20"),
      ("new_beginning", "Matthew 28:5–7; 2 Corinthians 5:17"),
      ("corruption", "Romans 3:10–19; Romans 3:23; Romans 5:12")], C,
     "It rests on the text's own explanation. Corruption: \"sin entered the world through "
     "one man, and death through sin, so also death was passed on to all men, because all "
     "sinned\" (Rom 5:12) -- Genesis 3 and all who came after, in one verse; \"There is no "
     "one righteous, not even one\" (3:10) quotes Psalm 14, whose \"corrupt\" in 14:1 is the "
     "flood's verb, with God looking to see it as in Gen 6:12; \"all have sinned and fall "
     "short of the glory of God\" (3:23). Judgment: \"the day of wrath, when God's righteous "
     "judgment will be revealed\" (Rom 2:5), and on the cross, \"My God, My God, why have You "
     "forsaken Me?\" (Matt 27:46). Set apart: \"I want those You have given Me to be with Me "
     "where I am\" (John 17:24). Remnant: \"everyone who believes in Him shall not perish\" "
     "(John 3:16), sent to \"make disciples of all nations\" (Matt 28:19). New beginning: "
     "\"He has risen\" (Matt 28:6), and \"if anyone is in Christ, he is a new creation. The "
     "old has passed away. Behold, the new has come!\" (2 Cor 5:17). The text itself ties "
     "this story to the flood's: Peter sets the eight "
     "saved in the ark beside \"the resurrection of Jesus Christ\" (1 Pet 3:20–21), and "
     "Jesus takes \"I will strike the Shepherd\" to himself (Matt 26:31), where Zechariah "
     "goes on, \"a third will be left\" (Zech 13:7–8)."),
    # ---- the four chosen from my suggestions (2026-09-30, decision card)
    ("Sarah’s son", "barren", "Sarah's son (Gen 11–21)",
     [("barren", "Genesis 11:30"), ("promise", "Genesis 18:10"), ("birth", "Genesis 21:1–2")],
     False, "\"Sarai was barren; she had no children\" (11:30)."),
    ("Rebekah’s twins", "barren", None,
     [("barren", "Genesis 25:21"), ("cry", "Genesis 25:21"), ("birth", "Genesis 25:24–26")],
     False, "\"Isaac prayed to the LORD on behalf of his wife, because she was barren\" (25:21)."),
    ("Rachel’s son", "barren", "Rachel's son (Gen 29–30)",
     [("barren", "Genesis 29:31; Genesis 30:1"), ("cry", "Genesis 30:22"),
      ("birth", "Genesis 30:23–24")], C,
     "\"Rachel was barren\" (29:31); \"God remembered Rachel. He listened to her\" (30:22) "
     "read as a prayer the text does not quote."),
    ("Manoah’s wife", "barren", "Samson promised and born (Judg 13)",
     [("barren", "Judges 13:2"), ("promise", "Judges 13:3–5"), ("birth", "Judges 13:24")],
     False, "\"His wife was barren and had no children\" (13:2)."),
    ("Hannah’s son", "barren", None,
     [("barren", "1 Samuel 1:5–6"), ("cry", "1 Samuel 1:10–11"), ("birth", "1 Samuel 1:19–20")],
     False, "\"The LORD had closed her womb\" (1:5)."),
    ("Elizabeth’s son", "barren", None,
     [("barren", "Luke 1:7"), ("cry", "Luke 1:13"), ("promise", "Luke 1:13"),
      ("birth", "Luke 1:57")], False,
     "\"Elizabeth was barren\" (1:7); \"your prayer has been heard\" (1:13)."),
    ("Jacob over Esau", "younger", "Jacob over Esau (Gen 25–27)",
     [("elder", "Genesis 25:25"), ("chosen", "Genesis 25:23; Genesis 27:27–29"),
      ("contest", "Genesis 27:34–37")], False,
     "\"The older will serve the younger\" (25:23); \"may the sons of your mother bow down "
     "to you\" (27:29); Esau's \"loud and bitter cry\" (27:34)."),
    ("Ephraim over Manasseh", "younger", None,
     [("elder", "Genesis 48:14"), ("contest", "Genesis 48:17–18"), ("chosen", "Genesis 48:19–20")],
     False, "\"Although Manasseh was the firstborn\" (48:14); \"his younger brother shall be "
             "greater than he\" (48:19)."),
    ("David among his brothers", "younger", None,
     [("elder", "1 Samuel 16:6–10"), ("chosen", "1 Samuel 16:11–13")], False,
     "\"There is still the youngest ... he is tending the sheep\" (16:11)."),
    ("Isaac over Ishmael", "younger", None,
     [("elder", "Genesis 21:9"), ("chosen", "Genesis 21:12")], C,
     "\"Through Isaac your offspring will be reckoned\" (21:12). Ishmael the elder is "
     "implied by the story, not stated in these verses."),
    ("Abel over Cain", "younger", None,
     [("elder", "Genesis 4:1–2"), ("chosen", "Genesis 4:4"), ("contest", "Genesis 4:5")], C,
     "Cain born first (4:1–2); \"the LORD looked with favor on Abel\" (4:4); Cain \"very "
     "angry\" (4:5). A reading: the text does not frame it as elder and younger."),
    ("Joseph over his brothers", "younger", None,
     [("elder", "Genesis 37:3"), ("chosen", "Genesis 37:5–7"), ("contest", "Genesis 37:8")], C,
     "\"Born to him in his old age\" (37:3); the sheaves bow (37:7); \"Do you intend to reign "
     "over us?\" (37:8)."),
    ("A wife for Isaac", "well", "A wife for Isaac (Gen 24)",
     [("journey", "Genesis 24:10"), ("well", "Genesis 24:11–14"), ("water", "Genesis 24:17–20"),
      ("telling", "Genesis 24:28"), ("marriage", "Genesis 24:67")], False, ""),
    ("Jacob meets Rachel", "well", "Jacob meets Rachel (Gen 29)",
     [("journey", "Genesis 29:1"), ("well", "Genesis 29:2–3"), ("water", "Genesis 29:10"),
      ("telling", "Genesis 29:12"), ("marriage", "Genesis 29:28")], False, ""),
    ("Moses at the well of Midian", "well", None,
     [("journey", "Exodus 2:15"), ("well", "Exodus 2:16"), ("water", "Exodus 2:17"),
      ("telling", "Exodus 2:18–19"), ("marriage", "Exodus 2:21")], False, ""),
    ("The covenant sealed at Sinai", "covenant_renewal", "The covenant sealed at Sinai (Exod 24)",
     [("pledge", "Exodus 24:3"), ("reading", "Exodus 24:7"), ("sealing", "Exodus 24:8")], False,
     "\"All the words that the LORD has spoken, we will do\" (24:3); \"This is the blood of the "
     "covenant\" (24:8). The first telling, not a renewal."),
    ("Covenant at Shechem", "covenant_renewal", None,
     [("assembly", "Joshua 24:1"), ("pledge", "Joshua 24:16–18; Joshua 24:21–24"),
      ("sealing", "Joshua 24:25–27")], False, "\"We will serve the LORD our God\" (24:24)."),
    ("Josiah’s covenant", "covenant_renewal", None,
     [("assembly", "2 Kings 23:1"), ("reading", "2 Kings 23:2"), ("pledge", "2 Kings 23:3"),
      ("sealing", "2 Kings 23:3")], False,
     "The king \"made a covenant before the LORD\" and \"all the people entered into the "
     "covenant\" (23:3): one verse, both stages."),
    ("The covenant under Nehemiah", "covenant_renewal", None,
     [("assembly", "Nehemiah 8:1"), ("reading", "Nehemiah 8:2–3"),
      ("sealing", "Nehemiah 9:38"), ("pledge", "Nehemiah 10:28–29")], False, ""),
    ("Asa’s covenant", "covenant_renewal", None,
     [("assembly", "2 Chronicles 15:9–10"), ("pledge", "2 Chronicles 15:12"),
      ("sealing", "2 Chronicles 15:14–15")], False,
     "\"They entered into a covenant to seek the LORD\" (15:12); \"They took an oath\" (15:14)."),
    # Tested and failed had one story (2026-09-30: Tested and Failed
    # appeared to have only one story). Those the text calls a test first:
    ("The nations left to test Israel", "testing_failure",
     "The nations left to test Israel (Judg 2:20–3:8)",
     [("testing", "Judges 2:21–22; Judges 3:1; Judges 3:4"), ("failure", "Judges 3:5–7"),
      ("judgment", "Judges 3:8")], False,
     "\"These nations were left to test the Israelites, to find out whether they would keep "
     "the commandments of the LORD\" (3:4); they served the Baals (3:7) and were sold to "
     "Cushan-rishathaim (3:8)."),
    ("The manna test", "testing_failure", None,
     [("testing", "Exodus 16:4"), ("failure", "Exodus 16:19–20; Exodus 16:27"),
      ("judgment", "Exodus 16:28")], C,
     "\"In this way I will test whether or not they will follow My instructions\" (16:4). The "
     "consequence is a rebuke, \"How long will you refuse ...?\" (16:28), and the spoiled "
     "manna (16:20)."),
    ("Moses at Meribah", "testing_failure", None,
     [("testing", "Numbers 20:8"), ("failure", "Numbers 20:10–11"), ("judgment", "Numbers 20:12")],
     C, "\"Because you did not trust Me ... you will not bring this assembly into the land\" "
        "(20:12). The text does not call the command a test: a reading."),
    ("Saul spares Agag", "testing_failure", None,
     [("testing", "1 Samuel 15:1–3"), ("failure", "1 Samuel 15:9"),
      ("judgment", "1 Samuel 15:22–23")], C,
     "\"Because you have rejected the word of the LORD, He has rejected you as king\" (15:23). "
     "A command, not called a test: a reading."),
    ("The command in Eden", "testing_failure", "The command in Eden (Gen 2–3)",
     [("testing", "Genesis 2:16–17"), ("failure", "Genesis 3:6"), ("judgment", "Genesis 3:16–19")],
     C, "\"You must not eat from the tree\" (2:17); \"because you ... have eaten from the tree of "
        "which I commanded you not to eat\" (3:17). Not called a test: a reading."),
    # an arc: the one event card ("Judges raised up") holds the whole book
    ("Deborah and Barak", "deliverance", "Deborah and Barak (Judg 4–5)",
     [("fall", "Judges 4:1"), ("threat", "Judges 4:2"), ("cry", "Judges 4:3"),
      ("deliverance", "Judges 4:14–16"), ("judgment_on_oppressor", "Judges 4:21–24"),
      ("praise", "Judges 5:1–3")], False,
     "The stated cycle a third time: \"the Israelites again did evil\" (4:1), \"cried out to "
     "the LORD\" (4:3), and the Song (5:1)."),
    ("Hannah", "deliverance", None,
     [("threat", "1 Samuel 1:6–7"), ("cry", "1 Samuel 1:10–11"),
      ("deliverance", "1 Samuel 1:19–20"), ("praise", "1 Samuel 2:1–10")], C,
     "Barrenness and a rival's taunting as the threat; \"the LORD remembered her\" (1:19); "
     "\"I rejoice in Your salvation\" (2:1)."),
    ("The flight to Egypt", "deliverance", "The flight to Egypt (Matt 2:13–15)",
     [("threat", "Matthew 2:13"), ("deliverance", "Matthew 2:14–15")], C,
     "\"Herod is going to search for the Child to destroy Him\" (2:13). No cry."),
    ("Elijah raises the widow’s son", "death_life", "Elijah raises the widow’s son (1 Kgs 17:17–24)",
     [("death", "1 Kings 17:17"), ("cry", "1 Kings 17:20–21"), ("life", "1 Kings 17:22–23")],
     False, "\"O LORD my God, please let this boy's life return to him!\" (17:21)."),
    ("Widow of Nain’s son", "death_life", None,
     [("death", "Luke 7:12"), ("life", "Luke 7:14–15")], False, ""),
    ("Jairus’ daughter", "death_life", None,
     [("death", "Mark 5:35"), ("life", "Mark 5:41–42")], False, ""),
    ("Lazarus", "death_life", None,
     [("death", "John 11:14"), ("cry", "John 11:41–42"), ("life", "John 11:43–44")], False,
     "\"Father, I thank You that You have heard Me\" (11:41) before \"Lazarus, come out!\""),
    ("Tabitha", "death_life", "Peter raises Tabitha (Acts 9:36–42)",
     [("death", "Acts 9:37"), ("cry", "Acts 9:40"), ("life", "Acts 9:40–41")], False,
     "\"He knelt down and prayed\" (9:40)."),
    ("Jesus dies and rises", "death_life", "Jesus dies and rises (Matt 27–28)",
     [("death", "Matthew 27:50"), ("life", "Matthew 28:5–7")], False,
     "\"He is not here; He has risen, just as He said\" (28:6)."),
]
# held: none of the eight shapes fits, or the stage is not declared
HELD = {"Creation of Eve": "a making and a union; none of the eight shapes",
        "Melchizedek blesses Abraham": "a blessing, not an anointing or a call",
        "Balaam": "God overrules a hired prophet to bless; none of the eight shapes",
        "Temple tax coin": "a question and a provision; none of the eight shapes",
        "Fig tree": "a judgment and a teaching on faith; none of the eight shapes",
        "Seven churches": "each letter is its own instance; to be built per letter",
        "Paul stoned": "resurrection (symbolic) is not declared by the text",
        "Purim": "joined with 'Esther intervenes' as one deliverance"}
# a pattern the TEXT states, and its first instance
DECLARED = [("Othniel", "deliverance", None,
             [("fall", "Judges 3:7"), ("threat", "Judges 3:8"), ("cry", "Judges 3:9"),
              ("deliverance", "Judges 3:10"), ("praise", "Judges 3:11")], False,
             "The cycle the text states (Judg 2:11–19), first told of Othniel: 'the "
             "Israelites cried out to the LORD, and He raised up Othniel' (3:9); 'the land "
             "had rest forty years' (3:11)."),
            ("Ehud", "deliverance", "Ehud (Judg 3:12–30)",
             [("fall", "Judges 3:12"), ("threat", "Judges 3:13–14"), ("cry", "Judges 3:15"),
              ("deliverance", "Judges 3:16–28"), ("judgment_on_oppressor", "Judges 3:29–30")],
             False,
             "The same stated cycle, second time: 'again they cried out to the LORD, and He "
             "raised up Ehud … as their deliverer' (3:15); 'Moab was subdued' (3:30). On the "
             "Enemy list too.")]


def spans(ref):
    probs = []
    out = [s for s in spans_in(ref, probs) if check(s, probs, ref)]
    if probs or not out:
        raise SystemExit(f"bad reference {ref!r}: {probs}")
    return out


def vs_of(ref):
    out = []
    for code, a, b in spans(ref):
        out += verses({"book": code, "start": list(a), "end": list(b)})
    return sorted(set(out), key=vkey)


def store(v):
    b, c, n = v.split(".")
    return f"{b} {c}:{n}"


def slug(t):
    t = re.sub(r"\(.*?\)", "", t.lower().replace("’", "").replace("'", ""))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")[:50]


def card_note(note):
    """The note as a card shows it. 2026-09-30: the About page is the
    place for all AI credits -- the About page calls the source list "a
    draft (see Who built it)", so a card says "the draft" and the review
    report keeps the name."""
    if not note:
        return note
    note = re.sub(r"^Copilot: ", "The draft: ", note)
    note = re.sub(r"^Copilot['’]s ", "The draft's ", note)
    note = re.sub(r"\(Copilot: ", "(the draft: ", note)
    return re.sub(r"Copilot['’]s ", "the draft's ", note)


def main():
    ev = json.loads((OUT / "event-nodes.json").read_text(encoding="utf-8"))["events"]
    ents = {}
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        if Path(f).name == ENT.name:
            continue
        for ln in open(f, encoding="utf-8"):
            r = json.loads(ln)
            ents[r["id"]] = r

    def tellings(e):
        out = []
        for t in e["tellings"]:
            b, c1, v1 = t["first"].split(".")
            _b, c2, v2 = t["last"].split(".")
            out.append(set(verses({"book": b, "start": [int(c1), int(v1)],
                                   "end": [int(c2), int(v2)]})))
        return out
    telsets = {k: tellings(e) for k, e in ev.items()}
    evsets = {k: set().union(*t) if t else set() for k, t in telsets.items()}

    def told_size(k, allv):
        # an event's size as this arc meets it: the tellings it touches, not
        # all four gospels -- the crucifixion is 125 verses told four times,
        # 30 in the Matthew an arc reads, and was dropped as too big (2026-09-30)
        return sum(len(t) for t in telsets[k] if t & allv)

    # evidence: the same primitive layers templates.py reads
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8"))["moved"]
    to_mac = {b: m for m, b in moved.items()}

    def mac(v):
        b, c, n = v.split(".")
        r = f"{TO_MACULA[b]}.{c}.{n}"
        return to_mac.get(r, r)
    stamps = collections.defaultdict(collections.Counter)
    for ln in gzip.open(OUT / "clause-tags.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if r.get("kind") == "stamp" and r.get("strength") in ("high", "medium"):
            stamps[r["clause"].split("#")[0]][r["tag"]] += 1

    def evidence(kind, vs):
        # a turning is repentance OR intercession (Moses and Joshua pray,
        # Nineveh fasts); a cry is often a prayer too
        ks = {"turning": ("repentance", "intercession"),
              "cry": ("cry", "intercession", "repentance")}.get(kind, (EVIDENCE.get(kind, kind),))
        st = set().union(*(KINDS[k][0] for k in ks if k in KINDS))
        if not st:
            return []
        c = collections.Counter()
        for v in vs:
            for t, n in stamps.get(mac(v), {}).items():
                if t in st:
                    c[t] += n
        return [t for t, _n in c.most_common(3)]

    nodes, rels, view = [], [], collections.defaultdict(list)
    fam_refs, kind_refs = collections.defaultdict(list), collections.defaultdict(list)
    fam_of = {f[0]: f for f in FAMILIES}
    report = []
    arcs_made = {}
    for title, fid, arc, stages, conj, note in APPLICATIONS + DECLARED:
        fam = fam_of[fid]
        order = [k for k, _o, _a in fam[2]]
        st = []
        for pos, (kind, ref) in enumerate(stages, 1):
            if kind == "skip":
                continue                        # a folded stage's place, kept
            if kind not in order:
                raise SystemExit(f"{title}: stage {kind} not in family {fid}")
            vs = vs_of(ref)
            st.append({"kind": kind, "ref": ref, "verses": vs, "pos": pos})
        allv = {v for s in st for v in s["verses"]}
        # the events the stages fall in
        touched = [k for k, s in evsets.items() if s & allv]
        main_ev = max(touched, key=lambda k: len(evsets[k] & allv)) if touched else None
        # the stages outside the main event make this an arc
        outside = main_ev is None or any(not (set(s["verses"]) & evsets[main_ev]) for s in st)
        as_arc = bool(arc) and (outside or len(touched) > 1 or title in FORCE_ARC)
        iid = "arc_" + slug(arc) if as_arc else main_ev
        if as_arc and iid in arcs_made:
            # one arc, two patterns (Esther and Purim is a rescue and a plot
            # turned back): the node and its parts are written once
            pass
        elif as_arc:
            parts = sorted({k for k in touched
                            if len(evsets[k] & allv) >= 1 and told_size(k, allv) <= 3 * len(allv)},
                           # the id breaks a tie, or two events opening on
                           # one verse swap places from build to build
                           key=lambda k: (vkey(min(evsets[k], key=vkey)), k))
            node = {"attrs": {"kind": "arc", "family": fid,
                              "events": parts},
                    "desc": f"{arc}: an arc of events, one instance of the template "
                            f"“{fam[1]}”. Each stage is checked against the Berean text.",
                    "disambiguation": "an arc of events (a template's instance)",
                    "gender": "unknown", "id": iid, "name": "Story arc: " + arc,
                    "refs": [store(s["verses"][0]) for s in st],
                    "source": SOURCE, "type": "event"}
            nodes.append(node)
            arcs_made[iid] = node
            for p in parts:
                rels.append({"certainty": "implied", "dst": iid,
                             "note": f"'{ev[p]['title']}' is part of the arc '{arc}'",
                             "refs": [store(min(evsets[p] & allv, key=vkey))],
                             "source": SOURCE, "src": p, "type": "part_of"})
        elif not iid:
            raise SystemExit(f"{title}: no event card and no arc")
        rels.append({"certainty": "conjectured" if conj else "implied", "dst": "tpl_" + fid,
                     "note": f"an instance of the template “{fam[1]}”"
                             + (f" — {card_note(note)}" if note else ""),
                     "refs": [store(s["verses"][0]) for s in st][:4],
                     "source": SOURCE, "src": iid, "type": "instance_of"})
        stage_rows = []
        for s in st:
            sid = f"stage_{slug(title)}_{s['pos']}"
            name = STAGE_NAME.get(s["kind"], s["kind"])
            lab = "; ".join(label_of([v for v in s["verses"] if v.split(".")[0] == b])
                            for b in dict.fromkeys(v.split(".")[0] for v in s["verses"]))
            # one label per contiguous run
            runs, cur = [], []
            for v in s["verses"]:
                if cur and vkey(v)[0] == vkey(cur[-1])[0] and (
                        vkey(v)[1:] == (vkey(cur[-1])[1], vkey(cur[-1])[2] + 1)
                        or (vkey(v)[1] == vkey(cur[-1])[1] + 1 and vkey(v)[2] == 1)):
                    cur.append(v)
                else:
                    if cur:
                        runs.append(cur)
                    cur = [v]
            if cur:
                runs.append(cur)
            lab = "; ".join(label_of(r) for r in runs)
            nodes.append({"attrs": {"kind": "template_stage", "stage": s["kind"], "family": fid},
                          "desc": f"{name[:1].upper() + name[1:]} — a stage of “{fam[1]}” in "
                                  f"{title}: {lab}.",
                          "gender": "unknown", "id": sid,
                          "name": f"{name[:1].upper() + name[1:]} ({fam[1]}): {lab}",
                          "refs": [store(r[0]) for r in runs] + [store(s["verses"][-1])],
                          "source": SOURCE, "type": "passage"})
            rels.append({"certainty": "implied", "dst": iid,
                         "note": f"the {name} stage of “{fam[1]}” in {title}",
                         "refs": [store(s["verses"][0])], "source": SOURCE, "src": sid,
                         "type": "part_of"})
            rels.append({"certainty": "conjectured" if conj else "implied",
                         "dst": "tplstage_" + s["kind"],
                         "note": f"the {name} stage of {title}",
                         "refs": [store(s["verses"][0])], "source": SOURCE, "src": sid,
                         "type": "instance_of"})
            fam_refs[fid].append(store(s["verses"][0]))
            kind_refs[s["kind"]].append(store(s["verses"][0]))
            stage_rows.append({"id": sid, "kind": s["kind"], "name": name, "label": lab,
                               "first": s["verses"][0], "n": len(s["verses"]),
                               # the reader marks these runs in its chapters
                               "runs": [[r[0], r[-1]] for r in runs],
                               "added": dict((k, a) for k, _o, a in fam[2])[s["kind"]],
                               "evidence": evidence(s["kind"], s["verses"])})
        # shown in the pattern's order: a stage added to a story later is
        # listed last in APPLICATIONS only so its siblings keep their ids
        order = [k for k, _o, _a in fam[2]]
        stage_rows.sort(key=lambda r: order.index(r["kind"]))
        inst = {"instance": iid, "arc": arc if iid.startswith("arc_") else None,
                # what the pattern's table calls this story: the arc's label
                # where the mapping gives one (it names the verses, where the
                # source title "Cain builds a city" named the verse held out)
                "title": title, "shown": arc or title, "family": fid, "family_name": fam[1],
                "conjectured": bool(conj), "note": card_note(note), "stages": stage_rows}
        # shown on the instance, and (below) on every event the arc holds
        view[iid].append(inst)
        report.append(dict(inst, note=note))
    # the arcs' events see the template too
    arcs = {n["id"]: n for n in nodes if n.get("attrs", {}).get("kind") == "arc"}
    for aid, a in arcs.items():
        for p in a["attrs"]["events"]:
            view[p] += [dict(i, via_arc=a["name"]) for i in view[aid]]
    # the families and stage kinds, each resting on its instances' verses
    for fid, name, stages, note in FAMILIES:
        decl = DECLARED_REFS.get(fid, [])
        nodes.append({"attrs": {"kind": "event_template",
                                "stages": [{"stage": k, "optional": o, "added_from_text": a}
                                           for k, o, a in stages]},
                      # the card draws the stages as its table's columns, so
                      # the description says what the pattern is in words
                      "desc": f"A story pattern: {note[:1].lower() + note[1:]}",
                      "gender": "unknown", "id": "tpl_" + fid, "name": f"Story pattern: {name}",
                      "refs": list(dict.fromkeys(decl + fam_refs[fid])),
                      "source": SOURCE, "type": "pattern"})
    for kind in dict.fromkeys(k for _f, _n, st, _o in FAMILIES for k, _o2, _a in st):
        name = STAGE_NAME.get(kind, kind)
        if not kind_refs[kind]:
            continue
        nodes.append({"attrs": {"kind": "template_stage_kind"},
                      "desc": f"{name[:1].upper() + name[1:]}: a stage of the event templates.",
                      "gender": "unknown", "id": "tplstage_" + kind,
                      "name": f"Story stage: {name}",
                      "refs": list(dict.fromkeys(kind_refs[kind])), "source": SOURCE,
                      "type": "concept"})
    clash = [n["id"] for n in nodes if n["id"] in ents]
    if clash:
        raise SystemExit(f"ids already in the store: {clash[:5]}")
    for path, rs in ((ENT, nodes), (REL, rels)):
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for r in rs:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    fams = {fid: {"name": name, "note": note,
                  "stages": [{"stage": k, "name": STAGE_NAME.get(k, k), "optional": o,
                              "added": a} for k, o, a in st],
                  "instances": [{"instance": i["instance"], "title": i["shown"],
                                 "conjectured": i["conjectured"]}
                                for i in report if i["family"] == fid]}
            for fid, name, st, note in FAMILIES}
    VIEW.write_text(json.dumps({"by_node": view, "families": fams, "held": HELD},
                               ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(report, fams)
    print(f"families {len(FAMILIES)}; instances {len(report)} "
          f"({sum(1 for i in report if i['arc'])} arcs, "
          f"{sum(1 for i in report if i['conjectured'])} conjectured); held {len(HELD)}; "
          f"nodes {len(nodes)}; relations {len(rels)}")


def write_report(report, fams):
    L = ["# Event templates as nodes (plan A.9)", "",
         "Built by `tools/events/template_nodes.py` from Microsoft Copilot's templates "
         "(`ontology/events/event-templates.md`), by the decisions of 2026-09-30. "
         "**Conjectured** = relabelled or reassigned by reading the text, to be "
         "confirmed; the note says why.", ""]
    for fid, f in fams.items():
        L.append(f"## {f['name']}")
        L.append("Stages: " + " → ".join(
            (f"[{s['name']}]" if s["optional"] else s["name"]) + (" *(added)*" if s["added"] else "")
            for s in f["stages"]))
        L.append("")
        for i in [x for x in report if x["family"] == fid]:
            L.append(f"- **{i['arc'] or i['title']}**{' — conjectured' if i['conjectured'] else ''}"
                     + (f" (Copilot: {i['title']})" if i["arc"] else ""))
            for s in i["stages"]:
                L.append(f"  - {s['name']}: {s['label']}"
                         + (f" — {', '.join(s['evidence'])}" if s["evidence"] else " — no stamp"))
            if i["note"]:
                L.append(f"  - *{i['note']}*")
        L.append("")
    L += ["## Held", ""] + [f"- {k}: {v}" for k, v in HELD.items()]
    (ROOT / "docs" / "review" / "EVENT-TEMPLATE-NODES.md").write_text("\n".join(L) + "\n",
                                                                      encoding="utf-8")


if __name__ == "__main__":
    main()
