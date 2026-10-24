"""The speech acts: the KIND of speaking, above the divine messages
(2026-09-30).

The speech list may largely be in the graph and ontology already, but this
puts more of a meaning mapping around it all. The decisions the same day: the acts sit ABOVE the messages (each message is a
narrower form of one); instances come from the text's own label first; the
acts are grouped by function; they show on cards and in the graph, not as
reader chips.

THE TEXT'S OWN LABEL. A verse is an instance of an act where the text names
the act there: the verb or noun that says so ("he blessed them", "the
Pharisees grumbled", "a prayer of the afflicted"), confirmed by its gloss
where one Strong's number carries two senses (לִין is "grumble" and
"lodge"). A few acts have a formula that IS the act and is found as such --
"As surely as the LORD lives" (an oath), "How long, O LORD?" (a complaint),
"Grace be with you" (a benediction), "I have sinned" (a confession) -- and
those are marked `formula`, not `label`. A psalm whose heading names it ("A
prayer", "A psalm of praise", "A psalm of thanksgiving") is an instance in
every verse. The graph's own curated edges (`blessed`, `cursed`, `rebuked`,
`accused`, `warned`, `named`) are merged in as `relation`, by their first
reference (the rest are often what provoked the act).

Not MACULA's "command" speech frame: it spans the whole speech it
introduces, and 440 of its 923 verses command nothing.

WHAT IS NOT AN INSTANCE. A draft passage the text does not label this way
is shown as a marked READING, never counted. The DeepSeek clause stamps
(blessing_ev, curse, oath_swearing ...) are unreviewed, so they are measured
against the labelled verses and reported, and do not add instances.

BOUND like the messages: `specializes` act -> group and message -> act;
`spoken_in` to story patterns, role patterns, themes and events by shared
verses, with more shared verses asked of an act the more common it is, and
none where the act is no denser there than anywhere; `aspect_of` to a concept
node the graph already had under the same meaning (praise, prayer, curse),
grounded by the verses both hold.

    python tools/themes/speech_acts.py
      -> ontology/entities/speech-act-types.jsonl,
         ontology/relations/speech-act-types.jsonl,
         out/speech-act-view.json, docs/review/SPEECH-ACTS.md
"""
from __future__ import annotations

import collections
import gzip
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "themes"))
sys.path.insert(0, str(ROOT / "tools" / "events"))
sys.path.insert(0, str(ROOT / "tools" / "phrases"))
from messages import corpus, layers, DELEGATE, overlays  # noqa: E402
from theme_map import CANON, check, spans_in  # noqa: E402
from event_nodes import TO_MACULA, verses, vkey  # noqa: E402

SRC = ROOT / "ontology" / "themes" / "speech-acts.md"
ENT = ROOT / "ontology" / "entities" / "speech-act-types.jsonl"
REL = ROOT / "ontology" / "relations" / "speech-act-types.jsonl"
VIEW = OUT / "speech-act-view.json"
SOURCE = "speech-act-types"
NVERSES = 31102

GOD = "h3068|h430|h410|h136|h3050|h433"
GODSET = set(GOD.split("|")) | {"g2316", "g2962"}

# ---- The grouping: by function
GROUPS = [
    ("performative", "Performative speech",
     "Speech that does what it says: it blesses, curses, binds, names or sends.",
     ["blessing", "cursing", "oath", "vow", "naming", "commissioning", "benediction"]),
    ("prayer", "Prayer",
     "Speech addressed to God: asking, pleading for others, grieving, protesting, thanking, praising, confessing.",
     ["petition", "intercession", "lament", "complaint", "thanksgiving", "praise", "doxology",
      "confession_of_sin"]),
    ("proclamation", "Proclamation",
     "Speech that declares or directs: bearing witness, confessing faith, promising, warning, summoning, commanding.",
     ["testimony", "confession_of_faith", "promise", "warning", "summons", "command"]),
    ("confrontation", "Confrontation",
     "Speech that meets another head on: rebuking, accusing, defending, taunting, boasting, refusing.",
     ["rebuke", "accusation", "defence", "taunt", "boast", "refusal"]),
    ("forms", "Set forms of speech",
     "Recognised shapes of speaking: the riddle, the call and its answer, the lament over a city, last words.",
     ["riddle", "call_and_response", "lament_over_a_city", "last_words"]),
]

# ---- the acts. n is the draft's number (31: added from the evidence).
# sigs: label words in the original (the signature language of messages.py,
# plus g: a gloss the head must carry and s: a stem it must be in).
# eng: the Berean's words, matched as written (never widened to the original:
# that is what pulled "the outcry that has come to Me" into "come to Me").
# formula: English that IS the act rather than naming it.
ACTS = [
    dict(n=1, id="blessing", name="Blessing",
         # "God blessed Noah" (Gen 9:1) and "Bless the LORD" (Ps 103:1) put the
         # same verb beside the same name, and MACULA's positions cannot say
         # which is the object; the Berean's rendering can, so the verses it
         # renders as blessing GOD are praise and doxology, not this
         sigs=["h1288 nn g:bless", "h1293 nn g:bless", "g2127 nn -g2316|g2962/2",
               "g2129 g:bless", "h835", "g3107"],
         not_eng=["bless the lord", "blessed the lord", "bless his name", "bless your name", "bless god",
                  "blessed god", "blessed be the lord", "blessed be god", "blessed be the god",
                  "blessed be the name", "blessed be his", "blessed be your", "blessing god", "blessed the god",
                  "bless you, o lord", "i will bless you as long as i live"],
         rel=["blessed"], stamps=["blessing_ev", "blessing_commission"]),
    dict(n=2, id="cursing", name="Cursing",
         sigs=["h779 nn", "h7043 nn g:curs", "h7045", "h6895 nn g:curs", "h423 g:curs",
               "h1288 g:curs", "g2672", "g2671", "g331", "g332 g:curs"],
         rel=["cursed"], stamps=["curse"]),
    dict(n=3, id="oath", name="Oath",
         sigs=["h7650 nn", "h7621", "h423 g:oath|swear|adjur", "g3660 nn", "g3727", "g3728"],
         formula=["as surely as the lord lives", "as the lord lives", "as surely as i live",
                  "as surely as god lives", "as surely as you live"],
         stamps=["oath_swearing", "oath_to_the_fathers"]),
    dict(n=4, id="vow", name="Vow", sigs=["h5087", "h5088", "g2171 g:vow"]),
    dict(n=13, id="naming", name="Naming",
         # not "did not call on My name" (Isa 65:1, negated) or "proclaimed
         # His name" (Exod 34:5, glossed proclaim): calling on and
         # proclaiming a name are not giving one
         sigs=[f"h7121 +h8034 ~3 nn g:call|name -{GOD}/3", "g2564 +g3686 ~3"],
         eng=["named him", "named her", "named it", "named the place", "renamed", "gave him the name",
              "surnamed", "you are to name him", "you are to name her",
              # the plain ways the text names a naming that the call-a-name
              # idiom misses: "Your name will no longer be Jacob" (Gen 32:28),
              # "Name him Maher-shalal-hash-baz" (Isa 8:3), "Saul, who was
              # also called Paul" (Acts 13:9), "a new name" (Rev 2:17)
              "name will no longer be", "name him", "name her", "also called", "new name",
              "call his name", "call her name"],
         # "the house that bears My name" (Jer 34:15) is ownership
         not_eng=["bears my name", "bears your name", "bears his name", "called by my name",
                  "called by your name", "called by his name", "called by the name",
                  # and calling ON a name is worship ("we will call on Your
                  # name", Ps 80:18)
                  "call on your name", "call on his name", "call on the name", "called on the name",
                  "calls on the name", "called on your name", "call on my name", "called on my name"],
         rel=["named"], stamps=["naming"]),
    dict(n=12, id="commissioning", name="Commissioning",
         # THE ORIGINAL, where no commissioning word is used (the templates
         # audit, 2026-09-30: Acts 13:2 and John 21 were missed). Set apart
         # FOR a task: ἀφορίζω with the work, the gospel, or a calling
         # (Acts 13:2, Rom 1:1, Gal 1:15); בָּדַל hiphil with a task verb --
         # carry, minister, serve, prophesy, bless, stand, bring near -- not
         # light from darkness or clean from unclean (Deut 10:8, Num 16:9,
         # 1Chr 25:1). A charge to shepherd, by God or his messenger: "Feed
         # My lambs" (John 21:15-17), "Pasture the flock" (Zech 11:4). All
         # ten hits read; all ten commissions.
         sigs=["g873 +g2041|g2098|g2564 ~8",
               "h914 s:hiphil +h5375|h8334|h5647|h5656|h5012|h5975|h1288|h7126 ~10",
               "g1006|g4165 @imp +g4263|g721|g4168|g4167 ~3 &div",
               "h7462 @imp +h6629|h5739 ~4 &div"],
         # not "I have sent you a gift" (1Kgs 15:19) or "the prophets, whom I
         # have sent you" (Jer 26:5): sent TO you
         eng=["i am sending you", "whom shall i send",
              "i have appointed you", "i appointed you", "go and make disciples", "commissioned",
              "commission him", "i ordained you",
              # a charge laid on a successor (צִוָּה with a person: "he
              # charged his son Solomon", 1Kgs 2:1; Paul to Timothy)
              # (not "I charge you" alone: "to have this letter read", 1Thess
              # 5:27, is an adjuration)
              "charged his son", "charge joshua", "charged joshua"],
         stamps=["commissioning"]),
    dict(n=18, id="benediction", name="Benediction",
         formula=["grace be with you", "grace be with all", "grace be with your spirit",
                  "the grace of the lord jesus be with", "the grace of our lord jesus christ be with",
                  "the grace of the lord jesus christ be with", "may the god of peace",
                  "the god of peace be with you", "peace be with you all", "the lord bless you and keep you",
                  "peace to all of you who are in christ",
                  # the formula with a clause inside it: "The grace of the Lord
                  # Jesus Christ, and the love of God ... be with all of you"
                  # (2Cor 13:14); and the other closing blessings
                  "be with all of you", "may the god of hope", "grace to all who", "peace to the brothers",
                  "the lord be with you", "the lord be with your spirit", "the lord bless you",
                  "lifted up his hands and blessed", "lifted up his hands toward the people and blessed"]),
    dict(n=16, id="petition", name="Petition",
         sigs=["h6419 g:pray|plead|supplic|interced", "h8605", "h8467", "h2603 s:hithpael",
               # entreaty: to God or the Lord, not Paul's "I beg you" to a
               # tribune (Acts 21:39)
               # (not "God" alone: "We implore you ... be reconciled to God",
               # 2Cor 5:20, is Paul to a church)
               "g4336", "g4335", "g1162", "g1189 +g2962|g2424 ~v",
               # עָתַר, "Isaac pleaded with the LORD" (Gen 25:21); חָלָה פְּנֵי,
               # "Moses sought the favor of the LORD" (Exod 32:11) -- the piel
               # glossed "entreat", not the sickness the same root names
               "h6279 g:pray|supplic|plead|entreat|prayer", "h2470 s:piel nn g:entreat|favor|seek|sought"],
         # cried out TO the LORD: the Berean says to whom, where the
         # original's word order does not ("I cry out, 'Violence!'", Jer
         # 20:8; the Ekronites' outcry about the ark, 1Sam 5:10)
         eng=["cried out to the lord", "cry out to the lord", "cried to the lord", "cried out to god",
              "cry out to god", "cried out to you", "cry out to you", "i cry to you", "i call to you",
              "i called to the lord", "called on the lord", "call on the lord"],
         formula=["answer me, o lord", "hear my cry", "hear my prayer"],
         heading=["h8605"]),
    dict(n=10, id="intercession", name="Intercession",
         sigs=["h6293 g:interced|plead", "g1793", "g5241", "g1783"],
         # for a PERSON: not "prayed for daybreak" (Acts 27:29) or "plead for
         # relief" (Job 35:9)
         eng=[f"{v} for {o}" for v in ("pray", "prayed", "praying", "prays", "pray to the lord", "prayed to the lord")
              for o in ("you", "us", "them", "him", "me", "her", "one another", "each other", "those", "all",
                        "your", "his", "the people", "this people", "your servant", "the saints", "the king")]
         # (not "on our behalf" alone: God's strength "exerted on our behalf",
         # Ps 68:28)
         + ["intercede", "intercedes", "interceded", "intercession", "i ask on their behalf",
            # but PRAYING on someone's behalf is: "I will pray to the LORD on
            # your behalf" (1Sam 7:5), "prayed to the LORD on behalf of his
            # wife" (Gen 25:21)
            "pray to the lord on", "prayed to the lord on", "pray on behalf", "prayed on behalf",
            "pray on your behalf", "pray to the lord our god on", "plead with the lord for"],
         stamps=["priestly_intercession"]),
    dict(n=5, id="lament", name="Lament",
         sigs=["h7015", "h6969", "h5092", "h5594 nn", "g2354"]),
    dict(n=15, id="complaint", name="Complaint",
         sigs=["h3885 g:grumbl|murmur|complain", "h8519", "h7879 g:complain|lament|anguish|grievance",
               "h7878 g:complain", "g1111", "g1112"],
         formula=["how long, o lord", "how long, lord", "o lord, how long", "how long, o god",
                  "how long will you forget me", "how long will you hide your face",
                  "why have you forsaken me", "why, o lord", "o lord, why", "why do you hide your face"],
         heading=["h7879"]),
    dict(n=7, id="thanksgiving", name="Thanksgiving",
         sigs=["h3034 x:hithpael g:thank|prais|thanksgiving -h2403|h5771|h6588/6",
               "h8426 g:thank|prais|thanksgiving|choir", "g2168", "g2169",
               # the Aramaic: "I give thanks and praise" (Dan 2:23)
               "h3029"],
         heading=["h8426"]),
    dict(n=6, id="praise", name="Praise",
         sigs=["h1984 x:hithpael|hithpolel|poel|poal g:prais", "h7623 g:glor|prais|extol", "h2167",
               "h8416", "g134", "g5214", "g3170 g:magnif|extol",
               # "Hallelujah" in Revelation 19; "they glorified God"; and the
               # Aramaic of Daniel -- "praise and exalt and honor the King of
               # heaven" (Dan 4:37), "Daniel blessed the God of heaven" (2:19),
               # not the kneeling the same verb names (6:10)
               "g239", "g1392 +g2316 ~3", "h7624", "h1289 g:bless", "h7313 g:exalt", "h1922",
               # singing TO God (the templates audit, 2026-09-30: Rev 5:9
               # "they sang a new song: Worthy are You" was missed). שִׁיר with
               # a divine name close by and glossed "sing" (Ps 6:10 has the
               # number without the singing); ᾄδω / ψάλλω in a verse naming God.
               # 14 hits read: 13 right, Ps 137:4 ("How can we sing a song of
               # the LORD in a foreign land?") a lament, left as a known edge
               "h7891 g:sing +h3068|h430|h3050|h410 ~4", "g103|g5567 +g2316|g2962 ~v"],
         eng=["bless the lord", "blessed the lord", "bless his name", "bless your name", "bless god",
              "blessed god", "blessing god", "bless you, o lord", "i will bless you as long as i live"],
         heading=["h8416"], godward=True),
    # not the qal "blessed" beside a divine name: "you are blessed by the
    # LORD" (Gen 26:29) is a blessing on Isaac
    dict(n=17, id="doxology", name="Doxology",
         # not the title "the Son of the Blessed One" (Mark 14:61)
         sigs=["g2128 -g5207/3", "g1391 +g281 ~8"],
         formula=["blessed be the lord", "blessed be god", "blessed be the god", "blessed be his glorious name",
                  "blessed be the name of the lord", "praise be to the lord", "praise be to god",
                  "to him be the glory", "to him be glory", "to god be the glory", "to whom be glory",
                  "glory to god in the highest",
                  # "To Him be the power forever" (1Pet 5:11), "be praise and
                  # honor and glory and power forever" (Rev 5:13)
                  "to him be the power", "to him be dominion", "be praise and honor and glory",
                  "blessing and glory and wisdom"]),
    dict(n=8, id="confession_of_sin", name="Confession of sin",
         # ἐξομολογέω confesses sins (Mark 1:5) or confesses a Lord (Phil
         # 2:11, "every tongue confess that Jesus Christ is Lord"): the sins
         # must be named
         sigs=["h3034 s:hithpael", "h3034 +h2403|h5771|h6588 ~6", "h8426 g:confess",
               "g1843 g:confess +g266|g3900 ~6",
               # not "What sin have we committed?" (Jer 16:10) or "I have
               # committed no offense" (Acts 25:8)
               # nor a condition, "If I sinned, You would take note" (Job 10:14)
               "h2398 p1 @qat nn -h4100|h4310|h518|h3863/5", "g264 p1 @ind nn -g3777|g3756|g3761|g5101/8",
               "g3670 +g266 ~6"],
         # "I confess my iniquity" (Ps 38:18) is נָגַד, "declare", which is
         # every telling in the text; the Berean's "confess" says which
         formula=["i have sinned", "we have sinned"],
         eng=["i confess my", "i acknowledged my sin", "confessed their sins", "confessing their sins",
              "confess our sins", "confess your sins", "we confess"]),
    dict(n=19, id="testimony", name="Testimony",
         sigs=["g3140 nn", "g3141", "g3142", "g3144", "h5749 g:testif|witness"],
         stamps=["witness"]),
    dict(n=9, id="confession_of_faith", name="Confession of faith",
         # ὁμολογουμένως, "by common confession" (1Tim 3:16)
         # (not glossed "declare": "I will tell them plainly, 'I never knew
         # you'", Matt 7:23, is a verdict)
         sigs=["g3670 g:confess|acknowledg|profess -g266/6", "g3671", "g3672",
               # believing God, the Lord, or THAT: not "in part I believe it"
               # of a report of divisions (1Cor 11:18)
               "g4100 p1 @ind nn g:believ +g2316|g2962|g2424|g5547|g3754 ~5",
               "g1843 g:confess -g266|g3900/6 +g2962|g2424|g2316 ~6"],
         formula=["you are the christ", "my lord and my god", "jesus is lord", "jesus christ is lord",
                  "the lord our god, the lord is one"],
         # THE CONFESSION OF TRUST: "The LORD is my shepherd" (Ps 23:1), "God is
         # our refuge" (Ps 46:1), "You are my God" (Ps 31:14). The templates
         # audit (2026-09-30) found Isa 12:2 missed. In the Hebrew "my" is a
         # suffix the word layer does not keep apart, so the Berean's English
         # decides -- a translation fallback, marked as a formula. 40 verses,
         # all read; one is said to an idol ("you are my god", Isa 44:17): the
         # act is the form of speaking, not its object
         formula_re=[r"\b(the lord|god|you|lord) (is|are) (my|our) (shepherd|rock|refuge|fortress|"
                     r"strength|salvation|light|god|shield|deliverer|stronghold|portion|helper|hope|"
                     r"song|keeper|dwelling place)\b"]),
    dict(n=25, id="promise", name="Promise", sigs=["g1861", "g1860"], eng=["promised"],
         stamps=["promise_oracle"]),
    dict(n=26, id="warning", name="Warning",
         sigs=["h2094 g:warn", "h5749 g:warn", "g5263 g:warn", "g3560", "g5537 g:warn"],
         eng=["beware", "be on your guard", "i warn you", "i warned you"],
         rel=["warned"]),
    # not "called for": "the Lord GOD called for weeping" (Isa 22:12)
    dict(n=14, id="summons", name="Summons", sigs=["g4341"],
         eng=["summoned", "summon", "summons", "sent for"]),
    # the verb only. MACULA's "command" speech frame spans the whole quoted
    # speech it introduces, verses that command nothing among them ("Light
    # is withheld from the wicked", Job 38:15): 440 of its 923 verses carry
    # no command word, and the two sampled were not commands
    dict(n=31, id="command", name="Command",
         sigs=["h6680 nn", "g1781", "g2004", "g3853", "g2753"]),
    dict(n=11, id="rebuke", name="Rebuke",
         sigs=["h1605", "h1606", "h3198 g:rebuk|reprov|correct|reproach|convict", "h8433",
               "g1651 g:rebuk|reprov|convict|expos", "g2008"],
         rel=["rebuked"]),
    dict(n=20, id="accusation", name="Accusation",
         # not רִיב spoken for God: it is also the LORD pleading his people's
         # case (Jer 51:36) and a lawsuit between neighbours (Deut 19:17);
         # the charge he brings is named in so many words
         sigs=["g2723", "g2724", "g2725", "h7853", "h7855"],
         eng=["accused", "accuse", "accuser", "brought charges", "has a case against", "a charge against",
              "brings a charge against"],
         rel=["accused"]),
    dict(n=21, id="defence", name="Defence", sigs=["g626", "g627"],
         eng=["defend myself", "my defense", "argue my case"]),
    dict(n=23, id="taunt", name="Taunt",
         # the verb לָעַג as well as its noun: "I will mock your calamity"
         # (Prov 1:26), not the "stammering" lips it also glosses (Isa 28:11)
         sigs=["h4912 g:taunt|byword|ridicul|mock", "h3933", "h3932 g:mock|scorn|derid", "h8148",
               # not "my conscience will not reproach me" (Job 27:6) or Herod
               # "outwitted" (Matt 2:16)
               "h2778 nn g:taunt|mock|defy|defied|insult|ridicul|reproach", "h7046",
               # הָתַל is also "deal deceitfully" (Exod 8:29)
               "h2048 g:mock", "g1702 g:mock", "g3456"]),
    dict(n=24, id="boast", name="Boast",
         # הָלַל glossed "boast" in any stem: "In God we have boasted all day
         # long" (Ps 44:8) and "the wicked man boasts" (Ps 10:3) are the piel
         sigs=["h1984 s:hithpael|hithpolel g:boast|glor", "h1984 g:boast", "g2744", "g2745", "g2746", "g213", "g212",
               "h6286 s:hithpael g:boast|glor"]),
    # and the Berean's own "refused", which renders more than מָאֵן: "they
    # refused to come" to the wedding (Matt 22:3) is οὐκ ἤθελον
    dict(n=28, id="refusal", name="Refusal", sigs=["h3985", "!h14", "g3868 g:refus|excus|reject"],
         eng=["refused", "refuse", "refuses", "refusing"],
         # not the noun: "scum and refuse" (Lam 3:45), "like refuse in the
         # streets" (Isa 5:25)
         not_eng=["scum and refuse", "like refuse", "refuse of the world", "the refuse"]),
    # not αἴνιγμα, whose one use is "a dim reflection" (1Cor 13:12), a figure
    dict(n=22, id="riddle", name="Riddle", sigs=["h2420", "h2330"]),
    dict(n=27, id="call_and_response", name="Call and response",
         # Amen SAID or ANSWERED: not the title "the God of Amen" (Isa 65:16)
         sigs=["h543 +h559|h6030 ~6", "g281 +g3004 ~3"],
         # not "the people answered" alone: Israel answering Rehoboam "What
         # portion do we have in David?" (2Chr 10:16) is a refusal
         formula=["and all the people said", "all the people answered",
                  "all the people shall say", "we will do", "we will serve the lord", "let israel say",
                  "let the house of aaron say", "let those who fear the lord say",
                  "his loving devotion endures forever", "sang responsively",
                  "speak, for your servant is listening"],
         # "Here I am" ANSWERING God's call (Gen 22:1; 1Sam 3:4; Isa 6:8),
         # not Esau answering his father (Gen 27:1, no God in the verse) or
         # David's "Here I am, living in a house of cedar" (1Chr 17:1)
         formula_godward=["here i am he answered", "here i am he replied", "here i am he said",
                          "here i am send me", "here i am for you called me"]),
    dict(n=29, id="lament_over_a_city", name="Lament over a city",
         # a city by name: "his own city" is where a man was mourned
         # (1Kgs 13:29), not the one lamented
         # beside the name, and in the Greek, over "the city": not Paul's
         # "why are you weeping ... to die in Jerusalem" (Acts 21:13)
         sigs=["h7015|h6969|h5092|h5594 +h3389|h6726|h894|h6865|h8111|h5210 ~4",
               "g2799|g2875|g2354 +g4172 ~6"]),
    dict(n=30, id="last_words", name="Last words",
         # "the way of all the earth" alone is also "the custom" (Gen 19:31)
         eng=["last words", "go the way of all the earth", "going the way of all the earth", "before his death",
              # a dying man's charge, not Esau's hunger (Gen 25:32)
              "i am about to die, but god",
              # Jacob's charge (Gen 49:29) and Paul's farewell (Acts 20:25)
              # (not "never see my face again": Pharaoh dismissing Moses,
              # Exod 10:28)
              "i am about to be gathered to my people", "will ever see my face again",
              "the time of my departure", "time drew near for"]),
]
BY_ID = {a["id"]: a for a in ACTS}
GROUP_OF = {aid: g for g, _n, _d, ids in GROUPS for aid in ids}

# the draft's names -> the acts
DRAFT = {"blessing spoken": "blessing", "blessing": "blessing", "cursing": "cursing", "oath": "oath",
         "vow": "vow", "lament": "lament", "praise": "praise", "thanksgiving": "thanksgiving",
         "confession of sin": "confession_of_sin", "confession of faith": "confession_of_faith",
         "intercession": "intercession", "rebuke": "rebuke", "commissioning word": "commissioning",
         "naming": "naming", "summons": "summons", "complaint": "complaint", "petition": "petition",
         "doxology": "doxology", "benediction": "benediction", "testimony": "testimony",
         "accusation": "accusation", "defence": "defence", "riddle": "riddle", "taunt": "taunt",
         "boast": "boast", "promise spoken": "promise", "warning spoken": "warning",
         "call and response": "call_and_response", "refusal": "refusal",
         "lament over a city": "lament_over_a_city", "last words": "last_words"}

# ---- the standard classes of speech act (J. R. Searle, "A classification of
# illocutionary acts", 1976): a label on each act, beside the grouping by
# function. 2026-09-30, on a Copilot thread that used them: the label
# was added. Where Searle names the verb, his class is
# kept even where it surprises -- he puts boasting and complaining among the
# assertives (a claim that something is so, with an attitude to it). Two
# acts are mixed by nature and are marked so rather than forced.
SEARLE = {
    "blessing": "declarative", "cursing": "declarative", "naming": "declarative",
    "commissioning": "declarative", "benediction": "declarative",
    "oath": "commissive", "vow": "commissive", "promise": "commissive", "refusal": "commissive",
    "petition": "directive", "intercession": "directive", "summons": "directive",
    "command": "directive", "warning": "directive", "riddle": "directive",
    "testimony": "assertive", "confession_of_faith": "assertive", "confession_of_sin": "assertive",
    "accusation": "assertive", "defence": "assertive", "boast": "assertive",
    "complaint": "assertive",
    "lament": "expressive", "thanksgiving": "expressive", "praise": "expressive",
    "doxology": "expressive", "rebuke": "expressive", "taunt": "expressive",
    "lament_over_a_city": "expressive",
    "call_and_response": "mixed", "last_words": "mixed",
}
SEARLE_GLOSS = {
    "assertive": "says that something is so",
    "directive": "tries to get the hearer to act",
    "commissive": "binds the speaker to act",
    "expressive": "voices the speaker's state toward something",
    "declarative": "makes something so by saying it",
    "mixed": "more than one kind in one form",
}

# ---- the divine messages, each a narrower form of one act (by message number)
MSG_ACT = {}
for act, ns in {
        "promise": [1, 9, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 92, 95, 96, 97, 100, 101],
        "commissioning": [2, 8, 91],
        "summons": [3, 4, 5, 6, 62, 64, 65, 66, 67, 68, 71, 82, 83, 85, 93],
        "warning": [7, 13, 18, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81],
        "blessing": [10, 86, 88, 94],
        "accusation": [11, 12, 14, 15, 16, 19, 20, 21],
        "rebuke": [17],
        "naming": [32, 33, 34, 35, 36, 37, 38, 39, 40, 41],
        "command": list(range(42, 62)) + [69, 70, 84, 89, 90, 99],
        "testimony": [63],
        "benediction": [87],
        "call_and_response": [98]}.items():
    for n in ns:
        MSG_ACT[n] = act

# ---- a concept node the graph already had, with the same meaning
CONCEPT = {"praise": ["praise"], "petition": ["prayer"], "cursing": ["curse"],
           "rebuke": ["rebuke", "reproof"], "intercession": ["intercession"],
           "testimony": ["testimony", "witness"], "vow": ["vows"], "complaint": ["complaint"],
           "command": ["command"]}

# a heading outside the Psalter that heads its chapter the same way
HEADED_CHAPTERS = ["Hab.3"]


def refs_of(vs):
    return [f"{v.split('.')[0]} {v.split('.')[1]}:{v.split('.')[2]}" for v in vs]


def parse_source(text):
    """-> {act: {definition, notes, cites: [{ref, claim, spans, part}]}}"""
    out = {a["id"]: {"definition": "", "notes": [], "cites": []} for a in ACTS}
    cur, part, notes = None, "", False
    for raw in text.split("-->", 1)[1].splitlines():
        line = raw.strip()
        if not line:
            continue
        if "(Expanded)" in line:
            nm = re.sub(r"^[^A-Za-z]+", "", line.split("(Expanded)")[0]).strip().lower()
            cur, part, notes = DRAFT.get(nm), "expansion", False
            continue
        if line.startswith("🔥") or line.startswith("🗣") or line.startswith("("):
            cur = None if line.startswith("🔥") else cur
            continue
        m = re.match(r"^(\d{1,2})\.\s+(.+)$", line)
        if m and part != "expansion":
            cur, part, notes = DRAFT.get(m.group(2).strip().lower()), "instance", False
            continue
        if not cur:
            continue
        if line.startswith("Definition:"):
            out[cur]["definition"] = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Pattern Notes"):
            notes = True
            nt = line[len("Pattern Notes"):].strip()
            if nt:
                out[cur]["notes"].append(nt)
            continue
        if line.startswith("Major Instances"):
            notes = False
            continue
        if re.match(r"^[A-G]\.\s", line):
            continue
        if notes and part == "instance":
            if line.startswith("If you want") or line.startswith("Naming →") or line.startswith("Just say"):
                cur = None
                continue
            out[cur]["notes"].append(line)
            continue
        if " — " in line:
            ref, claim = line.split(" — ", 1)
        elif "(" in line and line.rstrip(".").endswith(")"):
            # "Hoshea → Joshua (Num 13:16)." -- the claim, then its reference
            body = line.rstrip(".")
            claim, ref = body[:body.rindex("(")].strip(), body[body.rindex("(") + 1:-1]
        else:
            ref, claim = line, ""
        probs = []
        sp = [s for s in spans_in(ref, probs) if s[1] is not None and check(s, probs, ref)]
        if sp:
            out[cur]["cites"].append({"ref": ref.strip(), "claim": claim.strip().rstrip("."), "part": part,
                                      "spans": [[c, list(a), list(b)] for c, a, b in sp]})
        elif claim or ref:
            out[cur].setdefault("claims", []).append(line)
    return out


def main():
    src = parse_source(SRC.read_text(encoding="utf-8"))
    C = corpus()
    moved = json.loads((OUT / "versemap.json").read_text(encoding="utf-8"))["moved"]

    def spoken(v):
        return C.speaker(C.mac(v))

    def godward(v):
        return (v.startswith("Ps.") or spoken(v) in DELEGATE
                or any(k in GODSET for _p, k, *_ in C.words.get(C.mac(v), [])))

    def eng(phrases):
        out = set()
        for ph in phrases:
            e, _sig, _orig = C.find(re.findall(r"[a-z']+", ph.lower()))
            # the Berean's own words: the search also reads the WEB and ASV,
            # whose "appointed you" put Luke 3:13 (a tax collector's quota)
            # into commissioning
            out |= {v for v, trs in e.items() if "BSB" in trs}
        # a verse the Berean does not number the same way cannot be shown
        return {v for v in out if C.shown(v)}

    # ---- the psalms the text heads: which heading word, which psalm
    headed = collections.defaultdict(set)          # key -> {"Ps.N"}
    for n in range(1, 151):
        first = None
        for v in range(1, 4):
            t = moved.get(f"Psa.{n}.{v}")
            if t and t.startswith(f"Psa.{n}."):
                first = v - int(t.split(".")[2])
                break
        if first:
            hv = [f"Psa.{n}.{i}" for i in range(1, first + 1)]
            keys = {k for r in hv for _p, k, *_ in C.words.get(r, [])}
        else:
            keys = {k for p, k, *_ in C.words.get(f"Psa.{n}.1", []) if p <= 3}
        for k in keys:
            headed[k].add(f"Ps.{n}")
    for ch in HEADED_CHAPTERS:
        b, c = ch.split(".")
        for p, k, *_ in C.words.get(f"{TO_MACULA[b]}.{c}.1", []):
            if p <= 3:
                headed[k].add(ch)

    def chapter(ch):
        b, c = ch.split(".")
        return verses({"book": b, "start": [int(c), 1], "end": [int(c), CANON.book(b)[int(c)]]})

    # ---- the graph's own curated edges
    relv = collections.defaultdict(set)
    import glob
    for f in glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl")):
        if Path(f).name == REL.name:
            continue
        for ln in open(f, encoding="utf-8"):
            r = json.loads(ln)
            if r["type"] in ("blessed", "cursed", "accused", "rebuked", "warned", "named"):
                # the FIRST reference is the act; the rest are often what
                # provoked it or who the speaker is ("How can this be?",
                # John 3:9, before the rebuke at 3:10; Gal 1:1 for Paul)
                for ref in (r.get("refs") or [])[:1]:
                    probs = []
                    for s in spans_in(ref, probs):
                        if s[1] is not None and check(s, probs, ref):
                            vs = verses({"book": s[0], "start": list(s[1]), "end": list(s[2])})
                            if len(vs) <= 6:
                                relv[r["type"]] |= set(vs)

    # ---- the unreviewed stamps, for measuring only
    stampv = collections.defaultdict(set)
    want = {t for a in ACTS for t in a.get("stamps", [])}
    for ln in gzip.open(OUT / "clause-tags.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if r.get("kind") == "stamp" and r.get("tag") in want:
            stampv[r["tag"]].add(C.bsb(r["clause"].split("#")[0]))

    # ---- who speaks, by the speech verb MACULA's frame names
    actv = collections.defaultdict(set)
    for ln in gzip.open(OUT / "speakers.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        if "ref" in r and r.get("act"):
            actv[r["act"]].add(C.bsb(r["ref"]))

    # ---- the instances
    results = {}
    for a in ACTS:
        how = collections.defaultdict(set)         # verse -> {label, formula, heading, relation, speaker}
        for s in a.get("sigs", []):
            for v in C.search(s):
                how[v].add("label")
        for v in eng(a.get("eng", [])):
            how[v].add("label")
        for v in eng(a.get("not_eng", [])):
            if v in how:
                how[v].discard("label")
                if not how[v]:
                    del how[v]
        for v in eng(a.get("formula", [])):
            how[v].add("formula")
        for rx in a.get("formula_re", []):
            pat = re.compile(rx, re.I)
            for ref, t in C.text.items():
                if pat.search(t or ""):
                    how[C.bsb(ref)].add("formula")
        for v in eng(a.get("formula_godward", [])):
            if godward(v) and not v.startswith("Ps."):
                how[v].add("formula")
        for k in a.get("heading", []):
            for ch in headed.get(k, ()):
                for v in chapter(ch):
                    how[v].add("heading")
        for t in a.get("rel", []):
            for v in relv[t]:
                how[v].add("relation")
        if a.get("speaker_act"):
            for v in actv[a["speaker_act"]]:
                how[v].add("speaker")
        how = {v: h for v, h in how.items() if C.shown(v)}
        if a.get("godward"):
            how = {v: h for v, h in how.items() if "heading" in h or godward(v)}
        # THE OVERLAYS (ontology/instance-overlays.jsonl): hand corrections
        # where a rule is known to fall short, shown as such on the card
        ov = overlays("speech_act").get(a["id"], {})
        for v in ov.get("drop", {}):
            how.pop(v, None)
        for v in ov.get("add", {}):
            how[v] = {"overlay"}
        results[a["id"]] = how
        print(f"  {a['n']:3} {a['id']:22} {len(how):6}  "
              + ", ".join(f"{k} {n}" for k, n in collections.Counter(x for h in how.values() for x in h).most_common()),
              flush=True)
    json.dump({"results": {k: sorted(v, key=vkey) for k, v in results.items()},
               "headed": {k: sorted(v) for k, v in headed.items() if k in ("h8605", "h8416", "h8426", "h7879")}},
              open(OUT / "speech-act-instances.json", "w", encoding="utf-8"))
    build(src, results, headed, stampv, C)


def build(src, results, headed, stampv, C):
    story, roles, themes, events, recurs, theme_node = layers()
    mv = json.loads((OUT / "message-view.json").read_text(encoding="utf-8"))
    msg_by_n = {m["n"]: m for m in mv["messages"].values()}
    ents = {}
    for ln in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8"):
        r = json.loads(ln)
        ents[r["id"]] = r

    def spoken(v):
        return C.speaker(C.mac(v))

    nodes, rels = [], []
    view = {"acts": {}, "groups": {}}
    report = []
    for g, gname, gdesc, ids in GROUPS:
        nodes.append({"attrs": {"kind": "speech_act_group"}, "gender": "unknown",
                      "desc": gdesc, "id": f"sactgroup_{g}", "name": f"Speech-act group: {gname}",
                      "refs": [], "source": SOURCE, "type": "pattern"})
        view["groups"][g] = {"id": f"sactgroup_{g}", "name": gname, "desc": gdesc, "acts": []}
    group_refs = collections.defaultdict(list)

    for a in ACTS:
        aid, name = a["id"], a["name"]
        g = GROUP_OF[aid]
        how = results[aid]
        inst = sorted(how, key=vkey)
        iset = set(inst)
        n = len(inst)
        s = src[aid]
        ov_add = overlays("speech_act").get(aid, {}).get("add", {})
        # ---- the draft's references: labelled, or a reading
        cites, readings = [], []
        for c in s["cites"]:
            vs = []
            for cc, x, y in c["spans"]:
                vs += verses({"book": cc, "start": x, "end": y})
            hit = [v for v in vs if v in iset]
            others = collections.Counter(o for v in vs for o, h in results.items() if o != aid and v in h)
            grade = "labelled" if hit else "reading"
            cc = {"ref": c["ref"], "claim": c["claim"], "part": c["part"], "grade": grade,
                  "first": vs[0] if vs else None, "size": len(vs), "hits": len(hit), "hit": hit[:4],
                  "instead": [o for o, _k in others.most_common(3)] if not hit else []}
            cites.append(cc)
            if not hit:
                readings.append(cc)
        # ---- the links: shared verses, more asked of a common act, and
        # only where the act is denser than it is across the whole text
        least = 1 if n <= 60 else 2 if n <= 400 else 3

        def links(space, extra=0):
            out = []
            for key, vs in space.items():
                shared = iset & vs
                if len(shared) < least + extra:
                    continue
                if len(shared) < 2 * n * len(vs) / NVERSES:
                    continue
                out.append((key, sorted(shared, key=vkey)))
            out.sort(key=lambda x: -len(x[1]))
            return out
        st = links(story)
        ro = links(roles)
        th = links(themes, 1)
        ev = []
        if n <= 150:
            ev = [(eid, t, sorted(iset & vs, key=vkey)) for eid, (t, vs) in events.items()
                  if len(iset & vs) >= least and len(iset & vs) >= 2 * n * len(vs) / NVERSES]
            ev.sort(key=lambda x: -len(x[2]))
        same_refrain = []
        for r in recurs:
            rv_ = set(r.get("english") or []) | set(r.get("across") or [])
            inter = len(rv_ & iset)
            if rv_ and inter and inter / len(rv_) >= 0.6:
                same_refrain.append({"id": r["id"], "title": r["title"], "n": r["n"], "shared": inter})
        # ---- the messages that are narrower forms of it
        msgs = []
        for mn, act in sorted(MSG_ACT.items()):
            if act != aid or mn not in msg_by_n:
                continue
            m = msg_by_n[mn]
            mvs = [i["v"] for i in m["instances"]]
            msgs.append({"id": m["id"], "name": m["name"], "n": len(mvs),
                         "labelled": sum(1 for v in mvs if v in iset), "first": mvs[:2]})
        # ---- stamps, measured
        stamp = []
        for t in a.get("stamps", []):
            sv = stampv.get(t, set())
            stamp.append({"tag": t, "verses": len(sv), "labelled": len(sv & iset),
                          "only": sorted(sv - iset, key=vkey)})
        # ---- concepts the graph already had
        concepts = []
        for cid in CONCEPT.get(aid, []):
            e = ents.get(cid)
            if not e:
                continue
            cv = set()
            for ref in e.get("refs") or []:
                probs = []
                for sp in spans_in(ref, probs):
                    if sp[1] is not None and check(sp, probs, ref):
                        cv |= set(verses({"book": sp[0], "start": list(sp[1]), "end": list(sp[2])}))
            shared = sorted(cv & iset, key=vkey)
            concepts.append({"id": cid, "name": e["name"], "shared": shared, "refs": e.get("refs") or []})

        how_n = collections.Counter(x for h in how.values() for x in h)
        speakers = collections.Counter(spoken(v) for v in inst)
        nid = f"sact_{aid}"
        nodes.append({"attrs": {"kind": "speech_act", "group": g, "label_words": a.get("sigs", []),
                                "label_english": a.get("eng", []), "formulas": a.get("formula", []),
                                "draft_number": a["n"] if a["n"] <= 30 else None,
                                "searle_class": SEARLE.get(aid)},
                      "desc": (s["definition"] or "A command: speech that directs another to act.")
                      + f" {n} verses where the text names it.",
                      "gender": "unknown", "id": nid, "name": f"Speech act: {name}",
                      "refs": refs_of(inst[:12]), "source": SOURCE, "type": "pattern"})
        rels.append({"certainty": "implied", "dst": f"sactgroup_{g}", "src": nid, "type": "specializes",
                     "note": f"{name} is one of the kinds of {dict((x, y) for x, y, *_ in GROUPS)[g].lower()}",
                     "refs": refs_of(inst[:2]), "source": SOURCE})
        group_refs[g] += inst[:3]
        for m in msgs:
            rels.append({"certainty": "implied", "dst": nid, "src": m["id"], "type": "specializes",
                         "note": f"“{m['name']}” is a narrower form of {name.lower()}"
                                 + (f" ({m['labelled']} of its {m['n']} verses also name the act)"
                                    if m["labelled"] else ""),
                         "refs": refs_of(m["first"]), "source": SOURCE})

        def rel(dst, shared, note):
            rels.append({"certainty": "implied", "dst": dst, "src": nid, "type": "spoken_in",
                         "note": note, "source": SOURCE, "refs": refs_of(shared[:6])})
        # the INSTANCE, not the pattern (a real instance is expected
        # on that card): Huldah's row of the Prophet pattern, Cain's story
        seen = set()
        for (fam, fname, stage, iid, ilabel), shared in st:
            if iid not in seen and len(seen) < 10:
                seen.add(iid)
                rel(iid, shared, f"{name} is spoken in {ilabel}, in its {stage} stage (story pattern "
                                 f"“{fname}”, {len(shared)} verse{'s' if len(shared) != 1 else ''})")
        seen_row = set()
        for (pid, pname, slot, rid, rname), shared in ro:
            if rid not in seen_row and len(seen_row) < 10:
                seen_row.add(rid)
                rel(rid, shared, f"{name} is spoken in {rname}, in the {slot.lower()} (role pattern "
                                 f"“{pname}”, {len(shared)} verse{'s' if len(shared) != 1 else ''})")
        for (tid, ttitle), shared in th[:6]:
            tn = theme_node.get("theme:" + tid)
            if tn:
                rel(tn, shared, f"{name} is spoken in passages of the major theme {ttitle} "
                                f"({len(shared)} verses)")
        ev = [e for e in ev if e[0] not in seen]      # already bound as a story's instance
        for eid, et, shared in ev[:10]:
            rel(eid, shared, f"{name} is spoken in “{et}”")
        for c in concepts:
            if c["shared"]:
                rels.append({"certainty": "implied", "dst": c["id"], "src": nid, "type": "aspect_of",
                             "note": f"{name} as spoken: the act of {c['name']}, in the verses the "
                                     f"concept already cites ({len(c['shared'])})",
                             "refs": refs_of(c["shared"][:6]), "source": SOURCE})
        view["acts"][nid] = {
            "n": a["n"], "id": nid, "name": name, "group": g,
            "group_name": dict((x, y) for x, y, *_ in GROUPS)[g],
            "definition": s["definition"], "notes": s["notes"], "added": a["n"] > 30,
            "searle_class": SEARLE.get(aid), "searle_gloss": SEARLE_GLOSS.get(SEARLE.get(aid)),
            "count": n, "how": how_n.most_common(), "speakers": speakers.most_common(),
            "instances": [{"v": v, "who": spoken(v), "how": sorted(how[v]),
                           **({"overlay": ov_add[v]} if v in ov_add else {})} for v in inst],
            "psalms": sorted({ch for k in a.get("heading", []) for ch in headed.get(k, ())},
                             key=lambda x: (x[:2] != "Ps", int(x.split(".")[1]))),
            "cites": cites, "messages": msgs, "stamps": [{k: v for k, v in x.items() if k != "only"}
                                                         for x in stamp],
            "concepts": [{"id": c["id"], "name": c["name"], "n": len(c["shared"])} for c in concepts],
            # each row carries its verses, so the card can show which they are
            # (2026-09-30, on Lament: the 1 or 2 verses
            # were not visible in "Spoken In" or by drilling into them)
            "story": [{"id": i, "name": il, "pattern": f"tpl_{f}", "pattern_name": fn, "stage": sg,
                       "n": len(sh), "first": sh[0], "verses": list(sh)}
                      for (f, fn, sg, i, il), sh in st[:12]],
            "roles": [{"id": r, "name": rn, "pattern": f"rolepat_{p}", "pattern_name": pn, "slot": sl,
                       "n": len(sh), "first": sh[0], "verses": list(sh)}
                      for (p, pn, sl, r, rn), sh in ro[:12]],
            "themes": [{"id": t, "node": theme_node.get("theme:" + t), "name": tt, "n": len(sh),
                        "first": sh[0], "verses": list(sh)} for (t, tt), sh in th[:8]],
            "events": [{"id": e, "name": t, "n": len(sh), "first": sh[0], "verses": list(sh)}
                       for e, t, sh in ev[:12]],
            "refrain": same_refrain}
        view["groups"][g]["acts"].append(nid)
        report.append((a, s, inst, how, cites, readings, speakers, st, ro, th, ev, msgs, stamp, concepts,
                       same_refrain))

    for nd in nodes:
        if nd["id"].startswith("sactgroup_"):
            nd["refs"] = refs_of(list(dict.fromkeys(group_refs[nd["id"][10:]]))[:12])
    for path, rs in ((ENT, nodes), (REL, rels)):
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for r in rs:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    VIEW.write_text(json.dumps(view, ensure_ascii=False), encoding="utf-8")
    write_report(report, headed, C)
    allc = [c for r in report for c in r[4]]
    print(f"acts {len(report)}; instances {sum(len(r[2]) for r in report)}; draft references {len(allc)}: "
          + ", ".join(f"{k} {v}" for k, v in collections.Counter(c['grade'] for c in allc).most_common())
          + f"; nodes {len(nodes)}; relations {len(rels)} ("
          + ", ".join(f"{k} {v}" for k, v in collections.Counter(r['type'] for r in rels).most_common()) + ")")


def write_report(report, headed, C):
    t = C.shown
    rnd = random.Random(20260930)
    L = ["# Speech acts, vetted and bound (2026-09-30)", "",
         "Taxonomy and definitions: a draft (credited in About), grouped by function. Built by "
         "`tools/themes/speech_acts.py`. An instance is a verse where **the text names the act** "
         "(`label`: the verb or noun; `formula`: words that are the act; `heading`: a psalm headed that "
         "way; `relation`: an edge the graph already had, by its first reference). A draft "
         "reference the text does not label is a **reading**, shown marked and never counted.", "",
         "Read by hand, four verses at random from every act, the rules corrected after each read: "
         "111/124, 109/124, 121/124, then (after the recall pass below) 119/124. Recall: every draft "
         "reference graded a reading was read against its verses; 30 where the text did name the act "
         "(Aramaic thanks in Dan 2:23, עָתַר in Gen 25:21, \"Your name will no longer be Jacob\") "
         "moved the rules, and are now labelled. The journal entry of 2026-09-30 has each fault.", ""]
    # the draft's frequency claim
    lam = {"lament", "complaint", "petition"}
    psalms = collections.defaultdict(set)
    for (a, _s, inst, *_r) in report:
        if a["id"] in lam:
            for v in inst:
                if v.startswith("Ps."):
                    psalms[int(v.split(".")[1])].add(a["id"])
    L += ["## The draft's count: \"over 40 psalms are laments\"", "",
          f"The text heads no psalm a lament (קִינָה never stands in a Psalm heading). What it does "
          f"label: {len(psalms)} psalms name a complaint, a lament or a petition in at least one verse "
          f"(complaint in {sum(1 for p in psalms.values() if 'complaint' in p)}, petition in "
          f"{sum(1 for p in psalms.values() if 'petition' in p)}, lament in "
          f"{sum(1 for p in psalms.values() if 'lament' in p)}). Headed as a prayer: "
          f"{', '.join(sorted(headed.get('h8605', ())))}. Headed as praise: "
          f"{', '.join(sorted(headed.get('h8416', ())))}. As thanksgiving: "
          f"{', '.join(sorted(headed.get('h8426', ())))}. As a complaint: "
          f"{', '.join(sorted(headed.get('h7879', ())))}.", ""]
    for g, gname, gdesc, ids in GROUPS:
        L += [f"# {gname}", "", gdesc, ""]
        for (a, s, inst, how, cites, readings, speakers, st, ro, th, ev, msgs, stamp, concepts, same) in report:
            if GROUP_OF[a["id"]] != g:
                continue
            hn = collections.Counter(x for h in how.values() for x in h)
            L.append(f"## {a['name']}  ·  {len(inst)} verses" + ("  ·  *added from the evidence*" if a["n"] > 30 else ""))
            if s["definition"]:
                L.append(f"Draft definition: {s['definition']}")
            L.append("How the text names it: " + ", ".join(f"{k} {v}" for k, v in hn.most_common()))
            L.append("Label words: " + "; ".join(a.get("sigs", []) + a.get("eng", []))
                     + (" · formulas: " + "; ".join(a["formula"]) if a.get("formula") else ""))
            L.append("Who speaks: " + ", ".join(f"{k} {v}" for k, v in speakers.most_common(6)))
            if msgs:
                L.append("Narrower forms (messages): " + "; ".join(
                    f"{m['name']} ({m['n']}, {m['labelled']} also labelled)" for m in msgs))
            for x in stamp:
                L.append(f"Stamp `{x['tag']}` (unreviewed): {x['verses']} verses, {x['labelled']} labelled here"
                         + (" · stamp only, e.g.: " + " | ".join(f"{v}: {t(v)[:70]}" for v in x["only"][::max(1, len(x['only']) // 3)][:3])
                            if x["only"] else ""))
            for c in concepts:
                L.append(f"Concept node `{c['id']}`: {len(c['shared'])} of its cited verses name the act"
                         + ("" if c["shared"] else " -- **not bound** (no shared verse)"))
            if same:
                L.append("Same as the refrain: " + "; ".join(f"{r['title']} ({r['shared']}/{r['n']})" for r in same))
            L.append("Spoken in: " + "; ".join(
                [f"{il} ({fn}) · {sg} ({len(sh)})" for (_f, fn, sg, _i, il), sh in st[:4]]
                + [f"{rn} (role {pn}) · {sl} ({len(sh)})" for (_p, pn, sl, _r, rn), sh in ro[:3]]
                + [f"Theme {tt} ({len(sh)})" for (_t, tt), sh in th[:3]]
                + [f"Event {et} ({len(sh)})" for _e, et, sh in ev[:3]]))
            lab = [c for c in cites if c["grade"] == "labelled"]
            L.append(f"Draft references: {len(cites)} -- labelled {len(lab)}, reading {len(readings)}")
            for c in cites:
                inst_ = f" (the text names {', '.join(c['instead'])} there)" if c["instead"] else ""
                part = f" {c['hits']}/{c['size']}" if c["size"] > 1 and c["hits"] else ""
                L.append(f"- {c['ref']} -- *{c['grade']}*{part}{inst_} -- {c['claim'][:70]}")
            sample = rnd.sample(inst, min(4, len(inst))) if inst else []
            if sample:
                L.append("  - random instances: " + " | ".join(
                    f"{v} [{','.join(sorted(how[v]))}; {C.speaker(C.mac(v))}]: {t(v)[:90]}" for v in sorted(sample, key=vkey)))
            L.append("")
    (ROOT / "docs" / "review" / "SPEECH-ACTS.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
