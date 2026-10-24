"""The divine messages: vetted against the text and bound to the other
taxonomies (2026-09-30).

The brief: use the supplied taxonomy and the verse references Copilot drafted,
vet them, and work them into the graph, since these upper ontologies together
make a rich classification system that also relates to each other; check
against what the graph already holds and merge; it is not just the word 'go'
but 'go' used as a divine directive, imperative or command; not every message
is from God directly, several are from prophets on his behalf; coverage is
good, but taxonomy linking is what binds together; widening the net risks
getting things that are semantically similar but do not belong, so use
discretion.

So a MESSAGE is a form of speech, found by its form in the original: the
verb or formula (Strong's key), its grammar (an imperative "Go", a
prohibition "Do not fear" -- a negative particle before the verb -- a
first-person promise "I will gather you"), the words that must stand near it,
and, where the message says so, who speaks it. Every verse where the form
stands is an instance; the draft's references are checked against that.

WHO SPEAKS is a label, not a filter, except where the message is defined by
its speaker ("Go" as a divine directive): God, Jesus, an angel or messenger,
a prophet speaking for God, an apostle, or another person, from MACULA's own
frame annotation (out/speakers.jsonl.gz); a verse with no recorded speaker
takes its book's voice (a prophet's oracle, a psalmist, the teacher, a
letter's writer).

BOUND TO THE OTHER TAXONOMIES by shared verses (`spoken_in`): the story
patterns and the stage the message falls in, the role patterns and the cell,
the major themes, the events. And MERGED with what the graph had: a mined
refrain whose verses are the message's is the same thing and is named as
such; a phrase or text node quoting it is linked, not duplicated.

    python tools/themes/messages.py
      -> ontology/entities/messages.jsonl, ontology/relations/messages.jsonl
         out/message-view.json, docs/review/MESSAGES.md
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
sys.path.insert(0, str(ROOT / "tools" / "phrases"))
from theme_map import check, spans_in  # noqa: E402
from event_nodes import TO_MACULA, label_of, verses, vkey  # noqa: E402

SRC = ROOT / "ontology" / "themes" / "messages.md"
ENT = ROOT / "ontology" / "entities" / "messages.jsonl"
REL = ROOT / "ontology" / "relations" / "messages.jsonl"
VIEW = OUT / "message-view.json"
SOURCE = "messages"

# ---- The supplied taxonomy: the groups, by the numbers of their messages
GROUPS = [
    ("to_individuals", "Divine directives to individuals", range(1, 11)),
    ("confrontation", "Warning and confrontation", range(11, 22)),
    ("promise", "Promise and reassurance", range(22, 32)),
    ("identity", "Identity and calling", range(32, 42)),
    ("ethical", "Moral and ethical", range(42, 52)),
    ("wisdom", "Wisdom and discernment", range(52, 62)),
    ("prophetic", "Prophetic summons", range(62, 72)),
    ("judgment", "Crisis and judgment", range(72, 82)),
    ("kingdom", "Gospel and kingdom", range(82, 92)),
    ("last_things", "The last things", range(92, 102)),
]

# ---- THE FORM OF EACH MESSAGE. (number, id, who, [signatures], [English])
# A signature: "!" a negative particle just before the head; the head's
# Strong's keys ("|" = any of); "@" its moods; "p1/p2/p3" its person; "+" a
# key that must stand within the window of it ("~N" words, "~v" the verse);
# "&div" its speaker must speak for God. who "div": every instance must be
# spoken by God or on his behalf; "any": the speaker is a label only.
# English phrases (tools/phrases/phrase_search.py, all four translations and
# the same words in the original) where the form is a formula with pronouns
# the word layer does not carry ("I am with you").
MSG = [
    # a divine reassurance: God or one speaking for him (the midwife's "do not
    # be afraid", Gen 35:17, is kindness, not the message)
    # not "do not fear other gods" (worship, 2 Kgs 17:37)
    # and not "do not fear the gods of the Amorites" (Judg 6:10): gods as the
    # object, within two words; Hagar's "do not fear, for God has heard"
    # (Gen 21:17) has God three words on, as the subject of another verb
    (1, "do_not_fear", "div", ["!h3372|h6206|g5399 @imp,jus,yiq,sub p2 -h312/3 -h430/2"], []),
    # "go", not "come" or "walk" (Isa 55:1 "Come, all you who are thirsty";
    # Jer 6:16 "walk in it"), but "go" wherever the Berean says go
    (2, "go", "div", ["h1980|h3212|g4198|g5217 @imp p2 xg:come|walk en:go"], []),
    (3, "return", "div", ["h7725|g5290|g1994 @imp p2 -h3068|h430|h136|h410/1"], []),
    (4, "rise", "div", ["h6965|g1453|g450 @imp p2 -h3068|h430|h136|h410/1"], []),
    (5, "listen", "div", ["h8085|h238|g191 @imp p2 -h3068|h430|h136|h410/1 x:hiphil"], []),
    # TIGHTENED (widening the net risks getting things that are
    # semantically similar but do not belong): "hear" near "voice"
    # alone took "heard the sound of" -- 217 verses; the voice must be God's
    # שָׁמַע בְּקוֹל, "obey", is marked by a prefix the word layer drops, and
    # "heard the voice of the LORD God walking" (Gen 3:8) is hearing: the
    # Berean's "obey" decides
    (6, "obey_my_voice", "any", [], ["obey my voice", "obeyed my voice", "obey the voice of the lord",
                                     "obey his voice", "obeyed the voice of the lord", "obey me"]),
    (7, "do_not_turn_aside", "any", ["!h5493 @jus,yiq,imp p2"], []),
    (8, "be_strong_and_courageous", "any", ["h2388 @imp +h553 ~4"], []),
    (9, "i_am_with_you", "div", [], ["i am with you", "i will be with you", "the lord is with you"]),
    (10, "i_will_bless_you", "div", ["h1288 @yiq,weq,coh,qat p1"], []),
    (11, "warning_confrontation", "any", [], []),
    (12, "what_have_you_done", "any", [], ["what have you done", "what is this you have done",
                                           "why have you done this"]),
    (13, "sin_crouching", "any", ["h7257 +h2403 ~v"], []),
    (14, "you_have_not_obeyed", "any", [], ["have not obeyed", "did not obey", "not obeyed",
                                            "refused to obey", "would not obey",
                                            "did not listen to my voice"]),
    (15, "you_have_forsaken_me", "any", ["h5800 @qat,wayq &div", "h5800 +h3068 ~2"], []),
    # חָזַק + heart is "take courage" as often as "harden" (Ps 31:24): the
    # stem decides, so the Berean's "harden" / "stiff-necked" decides
    (16, "your_heart_is_hard", "any", ["g2588 +g4456|g4645 ~4", "g4641"],
     ["hardened his heart", "harden your hearts", "heart was hardened", "hardened pharaoh's heart",
      "stiff-necked", "hardness of heart", "hearts were hardened", "stubborn heart",
      "harden their hearts", "hardened their necks"]),
    (17, "you_are_the_man", "any", [], ["you are the man"]),
    (18, "your_sin_will_find_you_out", "any", ["h2403 +h4672 ~4"], []),
    (19, "you_have_provoked_me", "any", ["h3707"], []),
    (20, "you_have_forgotten", "any", ["h7911 +h3068|h430|h1285|h8451 ~v"], []),
    (21, "you_have_despised_my_word", "any", ["h959|h3988|h5006 +h1697|h8451|h565 ~6"], []),
    (22, "i_will_be_your_god", "any", [], ["i will be your god", "i will be their god",
                                           "i will be his god"]),
    # rest GIVEN: God speaking (I will give you rest) or the LORD its subject
    # near it -- "the ark came to rest" is not the message
    # rest GIVEN (not "the ark came to rest", Num 10:36)
    (23, "i_will_give_you_rest", "any", ["g373 p1 &div"],
     ["give you rest", "gave them rest", "given rest", "has given you rest", "will give you rest"]),
    (24, "i_will_fight_for_you", "any", ["h3898 +h3068 ~2"], ["fight for you", "fights for you",
                                                              "fought for israel"]),
    # God healing (not Jeremiah's "refusing to be healed", Jer 15:18)
    (25, "i_will_heal_you", "any", ["h7495 p1 &div", "h7495 +h3068 ~4"], []),
    (26, "i_will_restore_you", "any", ["h7725 +h7622|h7621 ~4"], []),
    # God gathering (not Ahab gathering prophets, 1 Kgs 22:6)
    (27, "i_will_gather_you", "any", ["h6908 p1 &div", "h6908 +h3068 ~2"], []),
    (28, "i_will_make_you_fruitful", "any", ["h6509", "g2590 +g5342 ~4"], []),
    # "not leave ... nor forsake" (not "abandon wrath", Ps 37:8)
    (29, "i_will_never_leave_you", "any", ["!h7503 +h5800 ~4", "g1459 +g447 ~4"], []),
    (30, "i_will_give_you_a_new_heart", "any", ["h3820|h3824 +h2319 ~4", "h4135 +h3820|h3824 ~4",
                                                "g4061 +g2588 ~4"], []),
    (31, "i_will_pour_out_my_spirit", "any", ["h8210|h3332|h6168 +h7307 ~5", "g1632 +g4151 ~3"], []),
    # not Eli's "my son" to Samuel (1 Sam 3:6)
    (32, "you_are_my_son", "div", [], ["you are my son", "this is my beloved son",
                                       "my firstborn son", "he will be my son",
                                       "out of egypt i called my son"]),
    (33, "you_are_my_servant", "div", [], ["my servant"]),
    # the people chosen (not "chosen Jerusalem ... David over My people", 2 Chr 6:6)
    (34, "you_are_a_chosen_people", "any", ["g1588 +g1085 ~3"],
     ["chosen people", "chosen race", "people he has chosen", "treasured possession",
      "my chosen people"]),
    (35, "you_are_a_royal_priesthood", "any", [], ["kingdom of priests", "royal priesthood",
                                                   "kingdom and priests"]),
    # God's witnesses, not Ruth 4's "you are witnesses"
    (36, "you_are_my_witnesses", "any", [], ["you are my witnesses", "you will be my witnesses",
                                             "you are witnesses of these things"]),
    # "YOU are": "I am the light of the world" is Jesus' own identity
    (37, "you_are_the_light_of_the_world", "any", [], ["you are the light of the world",
                                                       "children of light", "sons of light",
                                                       "lights in the world"]),
    # not the incense "seasoned with salt" (Exod 30:35)
    (38, "you_are_the_salt_of_the_earth", "any", [], ["salt of the earth", "salt in yourselves",
                                                      "salt is good"]),
    (39, "you_are_my_sheep", "voice", [], ["my sheep", "sheep of his pasture", "sheep of my pasture"]),
    # not "my friends" -- Job's friends are not the message
    (40, "you_are_my_friends", "any", [], ["you are my friends", "called you friends",
                                           "friend of god", "speaks with his friend",
                                           "abraham my friend"]),
    (41, "you_are_heirs", "voice", ["g2818|g4789"], []),
    # מִשְׁפָּט is also "ordinances": "do My ordinances" is not "do justice";
    # the Berean's own "justice" decides the sense
    (42, "do_justice", "any", [], ["do justice", "seek justice", "pursue justice", "act justly",
                                   "administer justice", "do what is just"]),
    # the command, not a prayer for mercy ("be merciful to me", Ps 26:11)
    # not "keeps His covenant of loving devotion with those who love Him"
    (43, "love_mercy", "any", [], ["love mercy", "i desire mercy", "be merciful, just as your father",
                                   "show mercy and compassion"]),
    # not the Day of Atonement's "humble yourselves" (a fast, Lev 16:29)
    (44, "walk_humbly", "any", ["h6800"], ["walk humbly", "grace to the humble",
                                           "humble yourselves before the lord",
                                           "humble yourselves under"]),
    # the command (not "my friends shun me", Ps 38:11)
    (45, "love_your_neighbor", "any", ["h157 @weq,yiq,imp p2 +h7453 ~3", "g25 +g4139 ~4"], []),
    (46, "forgive", "any", ["h5545 &div", "g863 +g266|g3900|g3783 ~6"], []),
    # the prohibition, not the narrative of evil repaid (Gen 44:4)
    (47, "do_not_repay_evil_for_evil", "any", ["!h7999 +h7451 ~4", "g591 +g2556 ~4 +g3367|g3361"],
     ["do not say, i will repay"]),
    (48, "do_not_oppress_the_poor", "any", ["!h6231|h3238|h3905 @jus,yiq,imp"], []),
    (49, "do_not_harden_your_heart", "any", ["!h7185|h553 +h3820|h3824 ~4", "!g4645"], []),
    # not "choose some men" (Exod 17:9)
    (50, "choose_life", "any", ["h977 +h2416|h2425 ~4"], ["choose this day", "choose life"]),
    # people told to be holy, not things that "shall be holy" (Lev 27:32)
    (51, "be_holy", "any", [], ["you shall be holy", "you are to be holy", "you must be holy",
                                "be holy in all you do", "be holy, because i",
                                "consecrate yourselves and be holy", "be holy, for i"]),
    # not "I will not be afraid" (Ps 56:4), not "awesome are His deeds" (the
    # participle, Ps 66:5)
    (52, "fear_the_lord", "any", ["h3372 @imp,yiq,qat,weq,wayq,jus,inf nn +h3068|h430 ~2",
                                  "h3374 +h3068|h430 ~2", "g5399|g5401 nn +g2316 ~3",
                                  # κύριος is also "master" (Eph 6:5): only beside the fear
                                  "g5399|g5401 nn +g2962 ~1"], []),
    (53, "trust_in_the_lord", "any", ["h982 +h3068 ~3"], []),
    # the heart as what is guarded, next to the verb -- not "obey with all
    # your heart"
    # the heart (not "spare his life", Job 2:6)
    (54, "guard_your_heart", "any", ["h5341|h8104 @imp +h3820|h3824 ~2"], []),
    # not "Incline Your ear, O LORD" (2 Kgs 19:16)
    # "ear" near "hear" took "no ear has heard" (1 Cor 2:9)
    (55, "incline_your_ear", "any", ["h5186 +h241 ~3 -h3068|h430|h136|h410/2"],
     ["ears to hear", "has an ear, let him hear"]),
    # not "the wise man has eyes in his head" (Eccl 2:14)
    (56, "do_not_be_wise_in_your_own_eyes", "any", ["g5429 +g1438 ~3"],
     ["wise in your own eyes", "wise in his own eyes", "wise in their own eyes",
      "wise in your own sight"]),
    (57, "walk_in_the_way_of_wisdom", "any", ["h1870|h734|h4570 +h2451|h998|h7922 ~5",
                                              "g4043 +g4678|g4680 ~5"], []),
    (58, "avoid_the_path_of_the_wicked", "any", ["h1870|h734|h5410 +h7563 ~2"], []),
    # the LORD as what is remembered, with its object marker אֵת -- "Remember,
    # O LORD" (a vocative) never has one
    (59, "remember_your_creator", "any", [], ["remember your creator", "remember the lord your god",
                                              "remember the lord"]),
    (60, "consider_your_ways", "any", ["h7760 +h3824|h3820 +h1870 ~5"], ["consider my ways",
                                                                         "examine our ways"]),
    # "the number of the days" is a count; numbering one's days is מָנָה
    (61, "number_your_days", "any", ["h4487 +h3117 ~3"], ["number our days", "how fleeting"]),
    (62, "hear_the_word_of_the_lord", "any", [], ["hear the word of the lord"]),
    (63, "thus_says_the_lord", "any", ["h3541 +h559 +h3068|h136 ~3"], ["this is what the lord says"]),
    # turning from sin (not "go back by the way you came", 1 Kgs 19:15)
    (64, "repent", "any", ["g3340|g3341", "h7725 @imp +h6588|h1544|h7451|h2403 ~6"], []),
    (65, "return_to_me", "div", [], ["return to me", "return to the lord"]),
    # "seek", not "inquire of the LORD" (consulting him, 2 Chr 34:26)
    (66, "seek_the_lord", "any", ["g2212 +g932|g2316 ~4"], ["seek the lord", "seek me", "seek his face",
                                                            "seek my face", "seek god"]),
    # the command (not "the fallow ground of the poor", Prov 13:23)
    (67, "break_up_your_fallow_ground", "any", ["h5214"], []),
    (68, "wash_your_hands", "any", ["h7364 +h3709 ~3", "h3709 +h5355 ~2", "g2511 +g5495 ~3"], []),
    (69, "cease_to_do_evil", "any", ["h2308 +h7489 ~3", "h5493 +h7451 ~3", "g1578 +g2556 ~3"], []),
    (70, "learn_to_do_good", "any", ["h3925 +h3190 ~3"], ["learn to do good",
                                                          "turn away from evil and do good"]),
    # פָּנָה is "prepare" only in one stem; "turned and went up the road"
    # (Num 21:33) is the other -- the Berean decides the Hebrew
    (71, "prepare_the_way_of_the_lord", "any", ["g2090 +g3598 ~4"], ["prepare the way",
                                                                     "make straight the way",
                                                                     "make straight paths",
                                                                     "prepare a way"]),
    (72, "the_day_of_the_lord_is_near", "any", [], ["day of the lord"]),
    (73, "the_axe_is_at_the_root", "any", ["g513 +g4491 ~4"], []),
    # not "the house of Israel ... in the wilderness" (Acts 7:42)
    (74, "your_house_is_left_desolate", "any", [], ["left to you desolate", "house will become a desolation",
                                                    "your house is left"]),
    # not "in the course of time" (Gen 4:3, the same two words)
    (75, "the_end_has_come", "any", ["g5056 +g1448|g2240|g2064 ~3"],
     ["the end has come", "the end is coming", "your end has come", "then the end will come",
      "the end of all things"]),
    (76, "the_lord_roars_from_zion", "any", ["h7580 +h3068|h6726 ~4"], []),
    (77, "the_heavens_will_shake", "any", ["h8064 +h7493|h7264 ~4", "g3772 +g4531 ~4"], []),
    (78, "the_nations_will_tremble", "any", ["h1471 +h7264|h2729|h7493 ~4"], []),
    # not "deserted to the king of Babylon" (2 Kgs 25:11)
    (79, "babylon_will_fall", "any", ["g897 +g4098 ~4"], ["fallen is babylon", "babylon has fallen",
                                                          "babylon must fall"]),
    (80, "the_judge_is_standing_at_the_door", "any", ["g2923 +g2374 ~5", "g1451 +g2374 ~5"], []),
    (81, "every_secret_thing_will_be_revealed", "any", ["g2927 +g5319|g601|g1097 ~5",
                                                        "h5956 +h4941 ~6"], []),
    (82, "the_kingdom_of_god_is_at_hand", "any", ["g932 +g1448|g5348|g1787 ~5"], []),
    (83, "follow_me", "div", ["g190 @imp", "g1205 +g3694 ~2"], []),
    # Jesus' summons (not Simon of Cyrene carrying it, Mark 15:21)
    (84, "take_up_your_cross", "div", ["g4716 +g142|g2983|g941 ~4"], []),
    # the invitation (not "the outcry that has come to Me", Gen 18:21)
    (85, "come_to_me", "div", [], ["come to me all", "come to me and", "whoever comes to me",
                                   "everyone who comes to me", "let him come to me",
                                   "let the little children come to me"]),
    (86, "your_faith_has_saved_you", "any", ["g4102 +g4982 ~4"], []),
    (87, "go_in_peace", "any", ["h1980|h3212 @imp +h7965 ~3", "g5217|g4198 @imp +g1515 ~4"], []),
    (88, "your_sins_are_forgiven", "any", ["g863 +g266 ~5", "g859 +g266 ~4"], []),
    (89, "you_must_be_born_again", "any", ["g1080 +g509 ~3", "g313"], []),
    # Greek prepositions are not words in the layer: "abide in Me" is μένω
    # with the pronoun beside it
    # μένω near a pronoun took "I must stay at your house" (Luke 19:5)
    (90, "abide_in_me", "any", [], ["abide in me", "remain in me", "abides in me", "remains in me",
                                    "remain in him", "abide in him", "remains in him"]),
    (91, "make_disciples_of_all_nations", "any", ["g3100 @imp", "g1484 +g2784 ~6"], []),
    # not a "new house" or "new cart" (Deut 22:8; 1 Sam 6:7)
    (92, "i_make_all_things_new", "any", [], ["all things new", "new heavens and a new earth",
                                              "new creation", "a new thing"]),
    # not the exodus "bring My people out" (Exod 3:10)
    # "my people" (not Paul to the spirit, "come out of her!", Acts 16:18)
    (93, "come_out_of_her_my_people", "any", [], ["come out of her, my people", "go out of her midst",
                                                  "depart, depart", "go out from her midst"]),
    (94, "blessed_are_those_who_wash_their_robes", "any", ["g4150 +g4749 ~4"], []),
    (95, "the_lamb_will_be_your_light", "any", ["g721 +g3088|g5457 ~6", "h216 +h3068 +h5769 ~8"], []),
    (96, "the_nations_will_walk_in_its_light", "any", ["g1484 +g5457 ~6", "h1471 +h216 ~4"], []),
    (97, "death_shall_be_no_more", "any", ["g2288 +g2089|g3765 ~4", "h1104 +h4194 ~4",
                                           "g2288 +g2666 ~4"], []),
    (98, "the_spirit_and_the_bride_say_come", "any", ["g4151 +g3565 ~6"], []),
    # not Judas's "arrest Him" (κρατέω, Matt 26:48)
    (99, "hold_fast_what_you_have", "any", [], ["hold fast", "hold firmly", "hold on to what you have"]),
    (100, "to_the_one_who_conquers", "any", ["g3528 @ptc"], []),
    # not "got up quickly and went" (John 11:29)
    (101, "surely_i_am_coming_soon", "any", [], ["i am coming soon", "i will come again",
                                                 "i am coming quickly"]),
]
# SECOND PASS (a random sample of every message read, 2026-09-30):
# the English wording alone decides these -- the phrase search's original-
# language expansion, which found "living water" across translations, here
# widens the idiom the English was chosen to narrow ("did not obey" pulled in
# "God does not listen", Job 35:13; "come to Me" pulled in "the outcry that has
# come to Me", Gen 18:21; "depart, depart" pulled in "Away, away!", Lam 4:15)
ENG_ONLY = {6, 14, 16, 23, 24, 34, 43, 51, 55, 56, 59, 65, 66, 70, 71, 72, 74, 85, 93, 99, 101}
# given by God: God speaks, or is named in the verse ("he will give you rest"
# is a disciplined son, Prov 29:17; a fruitful vine in a lament, Ezek 19:10)
GODWARD = {23, 24, 27, 28, 34, 66, 93}
GODNAMES = {"h3068", "h430", "h136", "h410", "g2316", "g2962"}
# the New Testament only: the Old has its own salt and its own "hold fast"
SCOPE_NT = {37, 38, 41, 99}
MOODS = {"imp": {"imperative"}, "jus": {"jussive"}, "yiq": {"yiqtol"}, "sub": {"subjunctive"},
         "qat": {"qatal"}, "wayq": {"wayyiqtol"}, "weq": {"weqatal"}, "coh": {"cohortative"},
         "ind": {"indicative"}, "ptc": {"participle", "participle active"},
         "inf": {"infinitive construct", "infinitive", "infinitive absolute"}}
NEG = {"h408", "h3808", "g3361", "g3756", "g3365", "g3762"}
NEG_EN = {"not", "no", "never", "none", "nor", "neither", "nothing", "cannot", "nobody"}


# "there is not": a negated existential passes its negation to the participle
# after it (οὐκ ἔστιν ... ὁ ἐκζητῶν, Rom 3:11; אֵין עֹשֵׂה־טוֹב, Ps 14:1)
EXIST_NEG = {"h369"}
EXISTENTIAL = {"g1510", "h1961", "h3426"}
VOLITIVE = {"jussive", "imperative", "cohortative", "subjunctive", "optative"}
AUX = {"a", "an", "the", "to", "has", "have", "had", "having", "is", "are", "was", "were", "be",
       "been", "being", "let", "will", "shall", "may", "i", "you", "he", "she", "it", "we", "they",
       "him", "her", "them", "me", "us", "who"}


def phrase_negated(v, content, psig, words, mac):
    """A message found by an English phrase, in a verse that denies it: "Seek
    the LORD" was bound to Rom 3:11, "There is no one who seeks God"
    (2026-09-30, on the cross-and-resurrection arc). Only the signatures had
    a negation test; the phrases had none. Decided in the original only. The
    word is the phrase's head, found by its signature key, or where the verse
    renders another word (ἐκζητέω at Rom 3:11, not ζητέω) by its gloss. A
    negative negates a VERB, never a noun ("Will not the Day of the LORD be
    darkness?", Amos 5:20, is not a denial of the day), and only the next
    verb: "They will not hand you over ... Obey the voice of the LORD" (Jer
    38:20) negates the handing over. An existential between them carries it
    on (Rom 3:11). No word found, or not a verb: kept. A first cut with an
    English fallback dropped 1 John 3:6, where "No one" belongs to "keeps on
    sinning", not to "remains in Him"."""
    ws = words.get(mac(v), [])
    if not ws or not content:
        return False
    lang = ws[0][1][0]
    head = (psig.get(lang) or [[None]])[0][0]
    # the head is the first word that carries meaning: in "has an ear, let
    # him hear" not "has", which found "no one has known" in Rev 2:17
    first = next((t for t in content if t not in AUX), None)
    if first is None:
        return False
    stem = first[:-1] if first.endswith("e") else first

    def lead(g):
        g = (g or "").split()
        while g and g[0] in AUX:
            g = g[1:]
        return " ".join(g)
    at = [w for w in ws if w[1] == head] or [w for w in ws if lead(w[5]).startswith(stem)]
    at = [w for w in at if w[2]]
    if not at:
        return False

    def negated(p, mood):
        # a prohibition warns of the thing, it does not deny it: the draft
        # itself gives "Do not harden your hearts" (Ps 95:8) as a hardened
        # heart. So a volitive verb, or אַל (always a prohibition), is kept;
        # only a statement that it is not so, or was not done, is dropped
        if mood in VOLITIVE:
            return False
        for q, k, *_ in ws:
            if not (0 < p - q <= 3 and k in NEG | EXIST_NEG) or k == "h408":
                continue
            between = [w for w in ws if q < w[0] < p and w[2]]
            if all(w[1] in EXISTENTIAL for w in between):
                return True
        return False
    return all(negated(w[0], w[2]) for w in at)


def overlays(layer):
    """Hand corrections over a rule's output, where a rule is known to fall
    short (2026-09-30: the remaining known imperfections are handled
    with overlays). ontology/instance-overlays.jsonl:
    {layer, id, verse, action add|drop, why, decided}. An added verse is
    shown as an overlay on its card, with its reason; each is meant to be
    retired when a rule can derive it. -> {id: {"add"|"drop": {verse: why}}}"""
    out = collections.defaultdict(lambda: {"add": {}, "drop": {}})
    p = ROOT / "ontology" / "instance-overlays.jsonl"
    if p.exists():
        for ln in open(p, encoding="utf-8"):
            r = json.loads(ln)
            if r["layer"] == layer:
                out[r["id"]][r["action"]][r["verse"]] = r["why"]
    return out


# the identity messages ("You are my sheep", "You are the light of the world")
IDENTITY = set(range(32, 42))
FINITE = {"indicative", "imperative", "subjunctive", "optative"}


def phrase_addressed(v, content, psig, words, mac, cases, proper, english):
    """An identity message tells its HEARERS what they are: "You are My
    servant" (Isa 41:9), "And you, My servant Jacob, do not be afraid" (Jer
    46:28). Found by an English phrase, it landed wherever God names someone
    else: "My servant Moses; he is faithful" (Num 12:7), "Have you
    considered My servant Job?", "the law of My servant Moses" (Mal 4:4),
    "my servant will be healed" (Luke 7:7) -- most of the 64 "You are my
    servant" verses (2026-09-30: the 'You are my servant' fault is fixed
    too). The noun must be the one addressed, in the original:
      Greek -- vocative; or nominative with a second-person verb or "you"
        within four words.
      Hebrew -- a "you" pronoun (אַתָּה, אַתֶּם) within three words; or a
        vocative: a second-person verb right before it, nothing between but
        a name ("listen, O Jacob My servant", Isa 44:1). A preposition or a
        construct noun before it is a gap or a noun there ("tell TO My
        servant David", 2Sam 7:5; "the law OF Moses My servant").
    Supersedes the first rule (object of a command), which it contains.

    First cut, all corrected (2026-09-30): it tested the phrase's LAST word,
    so "light of the world" tested "world" and lost Matt 5:14 and 5:13; it
    took no account of "you will BE My treasured possession" (Exod 19:5),
    "WE are His people" (Ps 100:3), "I have called YOU friends" (John
    15:15); and where the noun could not be found it kept the verse, which
    kept Ezek 34:15 ("I will tend My flock") for "my sheep". Now: the head
    noun; "be" with "you", "we", an accusative with "you"; and where the
    original noun cannot be found, the Berean's English decides."""
    m = mac(v)
    ws = words.get(m, [])
    if not ws or not content:
        return True
    lang = ws[0][1][0]
    # the head: the first word of the phrase that is a NOUN in the verse
    # ("called you friends" is headed by "friends", not "called" -- John 15:15)
    sig = psig.get(lang) or []
    head, at, stem = None, [], ""
    for i, t in enumerate(content):
        if t in AUX:
            continue
        hkey = sig[i][0] if i < len(sig) else None
        st = t[:-1] if t.endswith("s") else t
        found = [w for w in ws if hkey and w[1] == hkey and not w[2]] or \
            [w for w in ws if not w[2] and (w[5] or "").split()[-1:] and
             (w[5] or "").split()[-1].startswith(st)]
        if head is None:
            head, stem = t, st
        if found:
            head, stem, at = t, st, found
            break
    if not head:
        return True
    if not at:
        # the original cannot place the noun: the Berean's English decides,
        # "you", "we" or a vocative "O" just before the head word
        toks = re.findall(r"[a-z']+", english(m).lower())
        hits = [i for i, t in enumerate(toks) if t.startswith(stem)]
        return any(set(toks[max(0, i - 5):i]) & {"you", "ye", "we", "o"} for i in hits)
    # "you" and "we" (MACULA tags every case of σύ as g4771, of ἡμεῖς as
    # g2249). Not ἐγώ: "MY servant will be healed" (Matt 8:8) is not addressed
    YOU = {"g4771", "g5210", "g2249", "h859", "h587", "h5168"}

    def addressed(w):
        near = [w2 for w2 in ws if 0 < abs(w2[0] - w[0]) <= 4]
        if lang == "g":
            c = cases.get((m, w[0]))
            if c == "vocative":
                return True
            if c == "nominative":
                # "you" near, or the noun's OWN verb -- the nearest finite one --
                # in the first or second person: "you shine as lights" (Phil
                # 2:15), "walk as children of light" (Eph 5:8); not "my servant
                # will be healed" (Luke 7:7), whose verb is third person
                if any(w2[1] in YOU for w2 in near):
                    return True
                fin = [w2 for w2 in ws if w2[2] in FINITE and abs(w2[0] - w[0]) <= 6]
                own = min(fin, key=lambda w2: abs(w2[0] - w[0]), default=None)
                return bool(own) and own[3] in ("second", "first")
            # "I have called you friends": the noun and "you" both accusative
            return c == "accusative" and any(w2[1] in YOU and cases.get((m, w2[0])) == "accusative"
                                             for w2 in near if abs(w2[0] - w[0]) <= 3)
        # Hebrew: "you" or "we" within four words ("we are His people, the
        # sheep of His pasture", Ps 100:3, is four)
        if any(w2[1] in YOU for w2 in near):
            return True
        # "you will be My treasured possession": "be" in the second person,
        # or "to be" with "you" right after it ("for You to be My Servant",
        # Isa 49:6) -- not "and I will be with you" (1Kgs 11:38)
        for b in (w2 for w2 in near if w2[1] == "h1961"):
            if b[3] == "second" or ((b[2] or "").startswith("infinitive") and any(
                    w3[3] == "second" for w3 in ws if w3[0] == b[0] + 1)):
                return True
        # a vocative: walk back over a name, with no gap in the positions
        i = ws.index(w)
        pos = w[0]
        j = i - 1
        while j >= 0 and ws[j][0] == pos - 1 and (m, ws[j][0]) in proper:
            pos, j = ws[j][0], j - 1
        return j >= 0 and ws[j][0] == pos - 1 and bool(ws[j][2]) and ws[j][3] == "second"
    return any(addressed(w) for w in at)


def phrase_commanded(v, content, psig, words, mac, cases):
    """An identity message tells its hearers what they are. Found by an
    English phrase, it can land where the same words are the object of a
    command to someone else: "Shepherd My sheep" (John 21:16) is not "You
    are my sheep"; "let your light shine" (Matt 5:16) is not "You are the
    light". In the original: the phrase's noun with an imperative up to
    three words before it, and the noun the command's OBJECT -- Greek
    accusative, or Hebrew אֵת before it -- every time it occurs. Not a
    vocative: "listen, O Jacob My servant" (Isa 44:1) names who they are.
    A first cut without the object test dropped Isa 44:1."""
    m = mac(v)
    ws = words.get(m, [])
    if not ws or not content:
        return False
    lang = ws[0][1][0]
    keys = {k for k, _l in (psig.get(lang) or [])}
    first = next((t for t in reversed(content) if t not in AUX), None)
    if not first:
        return False
    stem = first[:-1] if first.endswith("s") else first
    at = [w for w in ws if w[1] in keys and not w[2]] or \
        [w for w in ws if not w[2] and (w[5] or "").split()[-1:] and
         (w[5] or "").split()[-1].startswith(stem)]
    if not at:
        return False

    def obj(w):
        if lang == "g":
            return cases.get((m, w[0])) == "accusative"
        return any(w2[1] == "h853" for w2 in ws if 0 < w[0] - w2[0] <= 3)
    return all(obj(w) and any(w2[2] == "imperative" for w2 in ws if 0 < w[0] - w2[0] <= 3)
               for w in at)

# ---- who speaks
PROPHETS = {"מֹשֶׁה": "Moses", "שְׁמוּאֵל": "Samuel", "נָתָן": "Nathan", "אֵלִיָּהוּ": "Elijah",
            "אֵלִיָּה": "Elijah", "אֱלִישָׁע": "Elisha", "יְשַׁעְיָהוּ": "Isaiah",
            "יִרְמְיָהוּ": "Jeremiah", "יִרְמְיָה": "Jeremiah", "יְחֶזְקֵאל": "Ezekiel",
            "יוֹנָה": "Jonah", "עָמוֹס": "Amos", "הוֹשֵׁעַ": "Hosea", "חַגַּי": "Haggai",
            "זְכַרְיָה": "Zechariah", "מִיכָיְהוּ": "Micaiah", "גָּד": "Gad", "אֲחִיָּה": "Ahijah",
            "נָבִיא": "a prophet", "חֻלְדָּה": "Huldah", "דְּבוֹרָה": "Deborah",
            "προφήτης": "a prophet"}
APOSTLES = {"Πέτρος": "Peter", "Παῦλος": "Paul"}
ANGELS = {"מַלְאָךְ", "ἄγγελος"}
DELEGATE = {"God", "Jesus", "an angel", "a prophet", "a prophet's oracle", "Moses"}
CHARACTER = {"another speaker", "Job's speakers"}
BOOK_VOICE = {**{b: "a prophet's oracle" for b in
                 "Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal".split()},
              "Ps": "a psalmist", "Prov": "the teacher", "Eccl": "the teacher", "Job": "Job's speakers",
              "Song": "the Song", "Deut": "Moses",
              **{b: "the letter's writer" for b in
                 "Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm Heb Jas 1Pet 2Pet "
                 "1John 2John 3John Jude".split()},
              "Rev": "John's vision"}


def parse_sig(s):
    """ ... "nn": the head is NOT negated ("I will not be afraid" is not "fear
    the LORD"); "-keys/N": none of these within N words AFTER the head -- the
    vocative, "Arise, O LORD" (Ps 7:6), a psalmist praying, not God
    commanding. """
    t = s.split()
    sig = {"neg": False, "head": set(), "moods": None, "person": None, "near": [], "win": 6,
           "div": False, "nn": False, "not_after": []}
    for i, tok in enumerate(t):
        if i == 0:
            if tok.startswith("!"):
                sig["neg"], tok = True, tok[1:]
            sig["head"] = set(tok.split("|"))
        elif tok.startswith("@"):
            sig["moods"] = set().union(*(MOODS[m] for m in tok[1:].split(",")))
        elif tok in ("p1", "p2", "p3"):
            sig["person"] = {"p1": "first", "p2": "second", "p3": "third"}[tok]
        elif tok.startswith("+"):
            sig["near"].append(set(tok[1:].split("|")))
        elif tok.startswith("~"):
            sig["win"] = None if tok == "~v" else int(tok[1:])
        elif tok == "&div":
            sig["div"] = True
        elif tok == "nn":
            sig["nn"] = True
        elif tok.startswith("-"):
            ks, _, n = tok[1:].partition("/")
            sig["not_after"].append((set(ks.split("|")), int(n or 1)))
        elif tok.startswith("x:"):
            # a stem the head must NOT be in: שָׁמַע in the hiphil is
            # "proclaim" (Jer 5:20), not "listen"
            sig["stem_not"] = set(tok[2:].split("|"))
        elif tok.startswith("s:"):
            # a stem the head MUST be in: יָדָה in the hithpael is "confess"
            sig["stem_in"] = set(tok[2:].split("|"))
        elif tok.startswith("g:"):
            # the head's English gloss must hold one of these: לִין is
            # "grumble" and "lodge", קָלַל "curse" and "lighten"
            sig["gloss"] = tok[2:].replace("_", " ").split("|")
        elif tok.startswith("xg:"):
            # the head's gloss must NOT hold any of these: MACULA glosses
            # each word in its context, and הָלַךְ is "come" in Isa 55:1
            # ("Come, all you who are thirsty") and "walk" in Jer 6:16
            sig["gloss_not"] = tok[3:].replace("_", " ").split("|")
        elif tok.startswith("en:"):
            # ...unless the Berean's English has this word in the verse. The
            # original cannot decide: לֵךְ is "come" and "go" alike, and
            # MACULA glosses "come" where the Berean has "go! I am sending you"
            # (Exod 3:10), "Go, say to Shebna" (Isa 22:15), "Go to your
            # people" (Ezek 3:11). Of 17 "go" hits glossed come/walk, the
            # Berean says "go" in exactly the 3 that are sendings. A fallback
            # to the translation, used only where the original is silent
            sig["gloss_not_unless_en"] = tok[3:].split("|")
        else:
            raise SystemExit(f"bad signature token {tok!r} in {s!r}")
    return sig


def key_of(d):
    s = re.sub(r"\D", "", d.get("strong") or "")
    if not s:
        return None
    return ("h" if d.get("lang") == "hebrew" else "g") + str(int(s))


def parse_source(text):
    """-> {n: {name, group, cites: [(ref, claim, kind)], note}}"""
    out, cur, kind, note_next = {}, None, "instance", False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^(\d{1,3})\.\s+“(.+?)”", line)
        if m and 1 <= int(m.group(1)) <= 101:
            n = int(m.group(1))
            cur = out.setdefault(n, {"name": m.group(2).rstrip("?"), "cites": [], "note": ""})
            kind, note_next = "instance", False
            continue
        if not cur:
            continue
        if line.startswith("Major Instance"):
            kind = "instance"
            continue
        if line.startswith("Echoes"):
            kind = "echo"
            continue
        if line == "Pattern Note":
            note_next = True
            continue
        if note_next:
            if line.startswith("⭐") or line.startswith("Just say") or line == "next":
                note_next = False
                continue
            cur["note"] = (cur["note"] + " " + line).strip()
            continue
        if " — " in line:
            ref, claim = line.split(" — ", 1)
            probs = []
            sp = [s for s in spans_in(ref, probs) if s[1] is not None and check(s, probs, ref)]
            if sp:
                cur["cites"].append({"ref": ref.strip(), "claim": claim.strip(), "kind": kind,
                                     "spans": [[c, list(a), list(b)] for c, a, b in sp],
                                     "problems": probs})
    return out


def corpus():
    """The text as the forms are read in it, shared with the speech acts
    (tools/themes/speech_acts.py): every verse's words with their grammar,
    who speaks each verse, the matcher, the phrase search, the Berean text."""
    import types
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8"))["moved"]
    to_mac = {b: m for m, b in moved.items()}
    from_mac = {v: k for k, v in TO_MACULA.items()}

    def mac(v):
        b, c, n = v.split(".")
        r = f"{TO_MACULA[b]}.{c}.{n}"
        return to_mac.get(r, r)

    def bsb(m):
        m = moved.get(m, m)
        b, c, n = m.split(".")
        return f"{from_mac.get(b, b)}.{c}.{n}"

    # the words of every verse, in order, with their grammar (MACULA refs)
    print("reading the word layer ...", flush=True)
    words = collections.defaultdict(list)
    cases = {}                  # (ref, position) -> Greek case, where MACULA gives one
    proper = set()              # (ref, position) of a proper noun (a name)
    for ln in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8"):
        d = json.loads(ln)
        if not d.get("word"):
            continue
        k = key_of(d)
        if not k:
            continue
        pos = int(re.sub(r"\D", "", d.get("local") or "0") or 0)
        if d.get("case"):
            cases[(d["ref"], pos)] = d["case"]
        if d.get("type") == "proper":
            proper.add((d["ref"], pos))
        words[d["ref"]].append((pos, k, d.get("mood"), d.get("person"), d.get("stem"),
                                (d.get("text") or "").lower()))
    for v in words.values():
        v.sort(key=lambda w: w[0])
    by_key = collections.defaultdict(set)
    for ref, ws in words.items():
        for _p, k, *_rest in ws:
            by_key[k].add(ref)

    # who speaks
    spk = collections.defaultdict(list)
    for ln in gzip.open(OUT / "speakers.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if "ref" in r:
            spk[r["ref"]].append(r)

    def speaker(mref):
        rs = spk.get(mref, [])
        labels = []
        for r in rs:
            s = r.get("speaker") or ""
            if r.get("divine") and not r.get("ambiguous"):
                labels.append("God")
            elif s == "Ἰησοῦς":
                labels.append("Jesus")
            elif s in ANGELS:
                labels.append("an angel")
            elif s in PROPHETS:
                labels.append("a prophet")
            elif s in APOSTLES:
                labels.append("an apostle")
            elif r.get("divine"):
                labels.append("God")          # κύριος, ambiguous: most often the Lord
            else:
                labels.append("another speaker")
        if labels:
            for pref in ("God", "Jesus", "an angel", "a prophet", "an apostle"):
                if pref in labels:
                    return pref
            return labels[0]
        return BOOK_VOICE.get(bsb(mref).split(".")[0], "the narrative")

    # the forms
    def match(sig, mref):
        ws = words.get(mref, [])
        for i, (p, k, mood, person, stem, gloss) in enumerate(ws):
            if k not in sig["head"]:
                continue
            if "stem_in" in sig and stem not in sig["stem_in"]:
                continue
            if "gloss" in sig and not any(g in gloss for g in sig["gloss"]):
                continue
            if any(re.search(rf"\b{re.escape(g)}", gloss or "") for g in sig.get("gloss_not", ())) \
                    and not any(re.search(rf"\b{re.escape(w)}\b", english(mref), re.I)
                                for w in sig.get("gloss_not_unless_en", ())):
                continue
            if sig["moods"] and mood not in sig["moods"]:
                continue
            if sig["person"] and person != sig["person"]:
                continue
            negated = any(k2 in NEG for p2, k2, *_ in ws if 0 < p - p2 <= 3)
            if sig["neg"] and not negated:
                continue
            if sig["nn"] and negated:
                continue
            # MACULA's positions follow its word groups, not the surface, so
            # the vocative can stand either side ("Incline Your ear, O LORD",
            # Isa 37:17, has LORD at w0 and the verb at w1)
            if any(k2 in ks for ks, n_ in sig["not_after"] for p2, k2, *_ in ws if 0 < abs(p2 - p) <= n_):
                continue
            if stem in sig.get("stem_not", ()):
                continue
            ok = True
            for near in sig["near"]:
                if not any(k2 in near and (sig["win"] is None or abs(p2 - p) <= sig["win"])
                           for p2, k2, *_ in ws):
                    ok = False
                    break
            if ok:
                return True
        return False

    print("building the phrase search ...", flush=True)
    import phrase_search
    find, _text = phrase_search.build()

    # the draft's references, and the Berean text to show them
    text = {}
    for ln in gzip.open(OUT / "bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if "ref" in r:
            text[r["ref"]] = r["text"]

    def search(s):
        """one signature -> the BSB verses its form stands in"""
        sig = parse_sig(s)
        cand = set.intersection(*(set().union(*(by_key[k] for k in ks))
                                  for ks in [sig["head"]] + sig["near"]))
        return {bsb(m) for m in cand
                if match(sig, m) and (not sig["div"] or speaker(m) in DELEGATE)}

    def shown(v):
        """the Berean text of a BSB verse id"""
        b, c, n = v.split(".")
        return text.get(f"{TO_MACULA[b]}.{c}.{n}", "")

    def english(m):
        """the Berean text of a MACULA verse (the matcher's own ids)"""
        return shown(bsb(m))
    return types.SimpleNamespace(words=words, by_key=by_key, speaker=speaker, match=match,
                                 bsb=bsb, mac=mac, text=text, find=find, search=search,
                                 shown=shown, cases=cases, proper=proper, english=english)


def main():
    src = parse_source(SRC.read_text(encoding="utf-8"))
    missing = [n for n, *_ in MSG if n not in src]
    if missing:
        raise SystemExit(f"messages not parsed: {missing}")
    C = corpus()
    import phrase_search
    words, by_key, speaker, match, bsb, mac, text, find = (
        C.words, C.by_key, C.speaker, C.match, C.bsb, C.mac, C.text, C.find)

    results = {}
    for n, mid, who, sigs, eng in MSG:
        found = set()
        for s in sigs:
            sig = parse_sig(s)
            cand = set.intersection(*(set().union(*(by_key[k] for k in ks))
                                      for ks in [sig["head"]] + sig["near"]))
            for mref in cand:
                if match(sig, mref) and (not sig["div"] or speaker(mref) in DELEGATE):
                    found.add(bsb(mref))
        for ph in eng:
            toks = re.findall(r"[a-z']+", ph.lower())
            e, psig, orig = find(toks)
            hits = set(e) | (set() if n in ENG_ONLY else set(orig))
            if not NEG_EN & set(toks):
                content = [t for t in toks if t not in phrase_search.STOP]
                hits = {v for v in hits if not phrase_negated(v, content, psig, words, mac)}
            if n in IDENTITY:
                content = [t for t in toks if t not in phrase_search.STOP]
                hits = {v for v in hits
                        if phrase_addressed(v, content, psig, words, mac, C.cases, C.proper,
                                            C.english)}
            found |= hits
        if n in GODWARD:
            found = {v for v in found if speaker(mac(v)) in DELEGATE
                     or any(k in GODNAMES for _p, k, *_ in words.get(mac(v), []))}
        if n in SCOPE_NT:
            found = {v for v in found if vkey(v) >= vkey("Matt.1.1")}
        # a verse the Berean does not number the same way cannot be shown
        found = {v for v in found if text.get(f"{TO_MACULA[v.split('.')[0]]}.{v.split('.')[1]}."
                                              f"{v.split('.')[2]}")}
        if who == "div":
            found = {v for v in found if speaker(mac(v)) in DELEGATE}
        elif who == "voice":
            # the text's own voice -- narrator, psalmist, teacher, prophet,
            # apostle -- not a character in a story (Judas's "arrest Him" is
            # not "hold fast"; the tenants' "this is the heir" is not "you
            # are heirs")
            found = {v for v in found if speaker(mac(v)) not in CHARACTER}
        # THE OVERLAYS: hand corrections where the rules are known to fall
        # short, each with its reason (ontology/instance-overlays.jsonl)
        ov = overlays("message").get(mid, {})
        found = (found - set(ov.get("drop", {}))) | set(ov.get("add", {}))
        results[n] = found
        print(f"  {n:3} {mid:36} {len(found):5}", flush=True)

    json.dump({"results": {n: sorted(v, key=vkey) for n, v in results.items()}},
              open(OUT / "message-instances.json", "w", encoding="utf-8"))
    build(src, results, speaker, mac, text)


def layers():
    """The other taxonomies' verses, for binding a new one to them: story
    stages, role cells, theme passages, events, refrains, and the theme
    nodes. Shared with the speech acts."""
    tpl = json.loads((OUT / "event-template-instances.json").read_text(encoding="utf-8"))
    # Keyed by the INSTANCE, not the pattern. 2026-09-30, on a message
    # card listing "Role pattern: Prophet · repentance": a role pattern is not
    # expected under a message even if the link is legitimate; a real instance
    # is expected on that card. So a message is
    # spoken in Huldah's row of the Prophet pattern, or in the judgment stage
    # of Cain's story; the pattern is one step up from there.
    story = collections.defaultdict(set)          # (family, family_name, stage, instance, label) -> verses
    for insts in tpl["by_node"].values():
        for i in insts:
            if i.get("via_arc"):
                continue
            for s in i["stages"]:
                for f, t in s.get("runs") or []:
                    for v in verses({"book": f.split(".")[0],
                                     "start": [int(x) for x in f.split(".")[1:]],
                                     "end": [int(x) for x in t.split(".")[1:]]}):
                        story[(i["family"], i["family_name"], s["name"], i["instance"],
                               i.get("shown") or i.get("title") or i["instance"])].add(v)
    roles = collections.defaultdict(set)          # (pid, name, slot, row, row name) -> verses
    rv = json.loads((OUT / "role-pattern-view.json").read_text(encoding="utf-8"))
    for pid, p in rv["patterns"].items():
        for r in p["rows"]:
            for slot, cs in r["cells"].items():
                for c in cs:
                    for f, t in c.get("runs") or []:
                        for v in verses({"book": f.split(".")[0],
                                         "start": [int(x) for x in f.split(".")[1:]],
                                         "end": [int(x) for x in t.split(".")[1:]]}):
                            roles[(pid, p["name"], slot, r["id"], r["name"])].add(v)
    themes = collections.defaultdict(set)         # (theme id, title) -> verses
    tm = json.loads((OUT / "theme-map.json").read_text(encoding="utf-8"))
    for t in tm["themes"]:
        for c in t["concepts"]:
            for p in c["passages"]:
                for r in p["refs"]:
                    if r.get("start"):
                        # a whole-book or long passage is not a place a
                        # message is "in"; a cited passage of a few verses is
                        vs = verses({"book": r["book"], "start": r["start"], "end": r["end"]})
                        if len(vs) <= 30:
                            themes[(t["id"], t["title"].title())] |= set(vs)
    evs = json.loads((OUT / "event-nodes.json").read_text(encoding="utf-8"))["events"]
    events = {}
    for eid, e in evs.items():
        vs = set()
        for t in e["tellings"]:
            b, c1, v1 = t["first"].split(".")
            _b, c2, v2 = t["last"].split(".")
            vs |= set(verses({"book": b, "start": [int(c1), int(v1)], "end": [int(c2), int(v2)]}))
        if vs:
            events[eid] = (e["title"], vs)
    recurs = json.loads((OUT / "recurs.json").read_text(encoding="utf-8"))["refrains"]
    # a theme's node: some reuse a node the graph already had (Covenant is
    # `covenant`), so go through the map, never "theme_" + id
    theme_node = json.loads((ROOT / "ontology" / "themes" / "theme-nodes.json")
                            .read_text(encoding="utf-8"))
    return story, roles, themes, events, recurs, theme_node


def build(src, results, speaker, mac, text):
    """The vetting, the links to the other taxonomies, and the nodes."""
    story, roles, themes, events, recurs, theme_node = layers()

    # ---- existing phrase and text nodes (merge, don't duplicate)
    ents = {}
    for f in glob.glob(str(ROOT / "ontology" / "entities" / "*.jsonl")):
        if Path(f).name == ENT.name:
            continue
        for ln in open(f, encoding="utf-8"):
            r = json.loads(ln)
            ents[r["id"]] = r
    phr = []
    for ln in gzip.open(OUT / "phrase-occurrences.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if r.get("id"):
            phr.append(r)

    gname = {g: name for g, name, _r in GROUPS}
    nodes, rels, view = [], [], {"messages": {}, "groups": {}, "by_verse": collections.defaultdict(list)}
    report = []
    for g, gtitle, rng in GROUPS:
        nodes.append({"attrs": {"kind": "message_group"}, "gender": "unknown",
                      "desc": f"A group of divine messages: {gtitle.lower()}.",
                      "id": f"msggroup_{g}", "name": f"Message group: {gtitle}",
                      "refs": [], "source": SOURCE, "type": "pattern"})
        view["groups"][g] = {"id": f"msggroup_{g}", "name": gtitle, "messages": []}
    group_refs = collections.defaultdict(list)
    for n, mid, who, sigs, eng in MSG:
        s = src[n]
        g = next(gg for gg, _t, rng in GROUPS if n in rng)
        inst = sorted(results[n], key=vkey)
        iset = set(inst)
        ov_add = overlays("message").get(mid, {}).get("add", {})
        # the draft's references, checked
        cites = []
        for c in s["cites"]:
            vs = []
            for cc, a, b in c["spans"]:
                vs += verses({"book": cc, "start": a, "end": b})
            hit = [v for v in vs if v in iset]
            if not sigs and not eng:
                grade = "genre"
            elif hit:
                grade = "found"
            elif len(vs) > 40:
                grade = "too broad"
            else:
                grade = "not this form"
            cites.append({"ref": c["ref"], "claim": c["claim"], "kind": c["kind"], "grade": grade,
                          "first": vs[0] if vs else None, "hits": hit[:5],
                          "speaker": speaker(mac(vs[0])) if vs else None})
        # a genre is its cited passages
        if not sigs and not eng:
            # only the scenes, not whole chapters: "Jeremiah 2–3" or "Matthew
            # 23" would bind the genre to everything else in them
            for c in s["cites"]:
                for cc, a, b in c["spans"]:
                    vs_ = verses({"book": cc, "start": a, "end": b})
                    if len(vs_) <= 25:
                        inst += vs_
            inst = sorted(set(inst), key=vkey)
            iset = set(inst)
        spoken = collections.Counter(speaker(mac(v)) for v in inst)
        # ---- the links, each grounded by the verses both sides hold
        # A story stage or a role cell is a few verses, and an instance is a
        # verse where the form itself stands: one shared verse is evidence
        # (Gideon's "do not fear", Judg 6:23, is in his call). A theme's
        # passages run long, so it takes two -- or one, for a rare message.
        def links(space, least):
            out = []
            for key, vs in space.items():
                shared = sorted(iset & vs, key=vkey)
                if len(shared) >= least:
                    out.append((key, shared))
            out.sort(key=lambda x: -len(x[1]))
            return out
        st = links(story, 1)
        ro = links(roles, 1)
        th = links(themes, 1 if len(inst) <= 6 else 2)
        least = 1
        ev = [(eid, t, sorted(iset & vs, key=vkey)) for eid, (t, vs) in events.items()
              if len(iset & vs) >= least]
        ev.sort(key=lambda x: -len(x[2]))
        # refrains: the same thing when most of each is the other
        same_refrain, near_refrain = [], []
        for r in recurs:
            rv_ = set(r.get("english") or []) | set(r.get("across") or [])
            if not rv_:
                continue
            inter = len(rv_ & iset)
            if inter and inter / len(rv_) >= 0.6 and inter / max(1, len(iset)) >= 0.3:
                same_refrain.append({"id": r["id"], "title": r["title"], "n": r["n"], "shared": inter})
            elif inter >= 3:
                near_refrain.append({"id": r["id"], "title": r["title"], "n": r["n"], "shared": inter})
        # phrase nodes whose verses are mostly this message's
        phrases = []
        for p in phr:
            pv = set(p.get("refs") or []) | set((p.get("english") or {}).keys())
            inter = len(pv & iset)
            if inter >= 2 and inter / max(1, len(pv)) >= 0.5:
                phrases.append({"id": p["id"], "name": p.get("name"), "shared": inter})
        # ---- the node
        name = s["name"]
        nid = f"msg_{mid}"
        grade_n = collections.Counter(c["grade"] for c in cites if c["kind"] == "instance")
        nodes.append({"attrs": {"kind": "message", "group": g, "form": sigs, "phrases": eng,
                                "speaker_rule": "spoken for God" if who == "div" else "any speaker"},
                      "desc": f"A divine message, {gname[g].lower()}: “{name}”. "
                              f"{len(inst)} verses carry it"
                              + (", spoken by God or on his behalf" if who == "div" else "") + ".",
                      "gender": "unknown", "id": nid, "name": f"Message: {name}",
                      "refs": [f"{v.split('.')[0]} {v.split('.')[1]}:{v.split('.')[2]}" for v in inst[:12]],
                      "source": SOURCE, "type": "pattern"})
        rels.append({"certainty": "implied", "dst": f"msggroup_{g}", "src": nid,
                     "note": f"“{name}” is one of the messages {gname[g].lower()}",
                     "refs": [f"{v.split('.')[0]} {v.split('.')[1]}:{v.split('.')[2]}" for v in inst[:2]] or
                             [f"{c['first'].split('.')[0]} {c['first'].split('.')[1]}:{c['first'].split('.')[2]}"
                              for c in cites if c["first"]][:1],
                     "source": SOURCE, "type": "specializes"})
        group_refs[g] += inst[:3]

        def rel(dst, shared, note):
            rels.append({"certainty": "implied", "dst": dst, "src": nid, "type": "spoken_in",
                         "note": note, "source": SOURCE,
                         "refs": [f"{v.split('.')[0]} {v.split('.')[1]}:{v.split('.')[2]}"
                                  for v in shared[:6]]})
        seen = set()
        for (fam, fname, stage, iid, ilabel), shared in st:
            if iid in seen or len(seen) >= 10:
                continue
            seen.add(iid)
            rel(iid, shared, f"“{name}” is spoken in {ilabel}, in its {stage} stage (story pattern "
                             f"“{fname}”, {len(shared)} verse{'s' if len(shared) != 1 else ''})")
        seen_row = set()
        for (pid, pname, slot, rid, rname), shared in ro:
            if rid in seen_row or len(seen_row) >= 10:
                continue
            seen_row.add(rid)
            rel(rid, shared, f"“{name}” is spoken in {rname}, in the {slot.lower()} (role pattern "
                             f"“{pname}”, {len(shared)} verse{'s' if len(shared) != 1 else ''})")
        for (tid, ttitle), shared in th[:6]:
            tn = theme_node.get("theme:" + tid)
            if tn:
                rel(tn, shared, f"“{name}” is spoken in passages of the major theme "
                                f"{ttitle} ({len(shared)} verses)")
        if len(inst) <= 120:
            for eid, et, shared in ev[:12]:
                if eid not in seen:           # already bound as a story's instance
                    rel(eid, shared, f"“{name}” is spoken in “{et}”")
        view["messages"][nid] = {
            "n": n, "id": nid, "name": name, "group": g, "group_name": gname[g], "note": s["note"],
            "who": who, "count": len(inst), "speakers": spoken.most_common(),
            "instances": [{"v": v, "who": speaker(mac(v)),
                           **({"overlay": ov_add[v]} if v in ov_add else {})} for v in inst],
            "cites": cites,
            # each row carries its verses, so the card can show which they are
            # (2026-09-30, on a speech act: the 1 or 2
            # verses were not visible in "Spoken In" or by drilling into them)
            "story": [{"id": i, "name": il, "pattern": f"tpl_{f}", "pattern_name": fn, "stage": sg,
                       "n": len(sh), "first": sh[0], "verses": list(sh)}
                      for (f, fn, sg, i, il), sh in st[:12]],
            "roles": [{"id": r, "name": rn, "pattern": f"rolepat_{p}", "pattern_name": pn, "slot": sl,
                       "n": len(sh), "first": sh[0], "verses": list(sh)}
                      for (p, pn, sl, r, rn), sh in ro[:12]],
            "themes": [{"id": t, "node": theme_node.get("theme:" + t), "name": tt, "n": len(sh),
                        "first": sh[0], "verses": list(sh)} for (t, tt), sh in th[:8]],
            "events": [{"id": e, "name": t, "n": len(sh), "first": sh[0], "verses": list(sh)}
                       for e, t, sh in ev[:12] if e not in seen],
            "refrain": same_refrain, "near_refrains": near_refrain[:5], "phrases": phrases[:5]}
        view["groups"][g]["messages"].append(nid)
        for v in inst:
            view["by_verse"][v].append(nid)
        report.append((n, mid, name, g, who, sigs, eng, inst, cites, spoken, st, ro, th, ev,
                       same_refrain, phrases))
    for g, _t, _r in GROUPS:
        for nd in nodes:
            if nd["id"] == f"msggroup_{g}":
                nd["refs"] = [f"{v.split('.')[0]} {v.split('.')[1]}:{v.split('.')[2]}"
                              for v in list(dict.fromkeys(group_refs[g]))[:12]]
    for path, rs in ((ENT, nodes), (REL, rels)):
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for r in rs:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    VIEW.write_text(json.dumps(view, ensure_ascii=False), encoding="utf-8")
    write_report(report, text)
    allc = [c for r in report for c in r[8] if c["kind"] == "instance"]
    g = collections.Counter(c["grade"] for c in allc)
    print(f"messages {len(report)}; instances {sum(len(r[7]) for r in report)}; draft references "
          f"{len(allc)}: " + ", ".join(f"{k} {v}" for k, v in g.most_common())
          + f"; nodes {len(nodes)}; relations {len(rels)} "
          f"(spoken_in {sum(1 for r in rels if r['type'] == 'spoken_in')})")


def write_report(report, text):
    def t(v):
        b, c, n = v.split(".")
        return text.get(f"{TO_MACULA[b]}.{c}.{n}", "")
    L = ["# Divine messages, vetted and bound (2026-09-30)", "",
         "Taxonomy: supplied. References: a draft, checked here. Built by "
         "`tools/themes/messages.py`. A message is found by its FORM in the original "
         "(verb, grammar, the words near it, and where the message requires it, a speaker "
         "for God). **found** = the reference carries the form; **not this form** = it does "
         "not (the draft's verse says something else, or another speaker, or another verb).", ""]
    for (n, mid, name, g, who, sigs, eng, inst, cites, spoken, st, ro, th, ev, same, phrases) in report:
        L.append(f"## {n}. {name}  ·  {len(inst)} verses")
        L.append(f"Form: {'; '.join(sigs) or '—'}{' · English: ' + '; '.join(eng) if eng else ''}"
                 f" · speaker: {'for God' if who == 'div' else 'any, labelled'}")
        L.append("Who speaks: " + ", ".join(f"{k} {v}" for k, v in spoken.most_common()))
        if same:
            L.append("Same as the refrain: " + "; ".join(f"{r['title']} ({r['shared']}/{r['n']})" for r in same))
        if phrases:
            L.append("Phrase nodes: " + "; ".join(f"{p['name']} ({p['shared']})" for p in phrases))
        L.append("Spoken in: " + "; ".join(
            [f"{il} ({fn}) · {sg} ({len(sh)})" for (_f, fn, sg, _i, il), sh in st[:4]]
            + [f"{rn} (role {pn}) · {sl} ({len(sh)})" for (_p, pn, sl, _r, rn), sh in ro[:3]]
            + [f"Theme {tt} ({len(sh)})" for (_t, tt), sh in th[:3]]))
        for c in cites:
            L.append(f"- {'echo · ' if c['kind'] == 'echo' else ''}{c['ref']} — *{c['grade']}*"
                     f" ({c['speaker']}) — {c['claim'][:80]}")
        # a sample of what the form found beyond the draft, for reading
        drafted = {h for c in cites for h in c["hits"]}
        extra = [v for v in inst if v not in drafted]
        if extra:
            step = max(1, len(extra) // 4)
            L.append("  - found beyond the draft, e.g.: " + " | ".join(
                f"{v}: {t(v)[:90]}" for v in extra[::step][:4]))
        L.append("")
    (ROOT / "docs" / "review" / "MESSAGES.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
