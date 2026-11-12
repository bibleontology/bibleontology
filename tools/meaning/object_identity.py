"""Things the text treats as one object (plan A.45; 2026-11-06): the five-card test's pairs, for the orchestrator.

People resolve to individuals, and objects resolved only to kinds: the twelve stones from the Jordan had no node,
and fell to the general "stones" card. A noun that points back ("these stones", "the stones they had taken") is a
reference, like a pronoun. Structure surfaces the candidate pairs, and one narrow question decides each: is this the
same physical thing? The answer is one of: yes, stated in the text; yes, plainly implied; no, or the text does not
say; unclear.

Measured first (2026-11-06): the 5,751 objects the clause records mark "a particular one" are mostly a name, a face,
a hand, a people or words, not things. So the pass starts from each object's own word, by Strong's number, and pairs
every mention with the mentions before it, within the books where its story is told.

The test set is Doug's five cards (the Jordan stones, the bronze serpent, Joseph's bones, oxen, wells), with what
the text keeps apart beside them: Achan's stoning, the altar on Ebal, Lazarus's tomb, and the two struck rocks.
Each pair is a claim ("the stones in Joshua 4:20 are the same stones as the stones in Joshua 4:3") read against
both verses, so the orchestrator's gate, plants and DeepSeek second pass work as for any claim. Nothing is written
to the graph.

    python tools/meaning/object_identity.py build   -> out/orchestra-intake/17-object-identity/ (copied to the Mac)
"""
import gzip
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from structure import to_english  # noqa: E402

NAME = "17-object-identity"
OUT = ROOT / "out" / "orchestra-intake" / NAME
OPTIONS = {"temperature": 0, "num_ctx": 4096}
SEED = 20261106
EARLIER = 2          # earlier verses paired from other chapters, beyond every earlier verse in the same chapter

# card set -> (Strong's numbers, where its story is told: book -> chapters, or None for every chapter)
SETS = {
    "jordan-stones": ({"h68"}, {"Jos": None, "Deu": {27}, "Lev": {24}}),
    "tomb-stone": ({"g3037"}, {"Mat": {27, 28}, "Mrk": {15, 16}, "Luk": {24}, "Jhn": {11, 20}}),
    "struck-rock": ({"h6697", "h5553"}, {"Exo": {17}, "Num": {20}}),
    "bronze-serpent": ({"h5175", "h5180"}, {"Num": {21}, "2Ki": {18}}),
    "josephs-bones": ({"h6106"}, {"Gen": {50}, "Exo": {13}, "Jos": {24}}),
    "oxen": ({"h1241", "h6510", "h7794"},
             {"1Sa": {6, 11}, "2Sa": {6, 24}, "1Ki": {7, 19}, "2Ki": {16}, "2Ch": {4}, "Exo": {21}, "Deu": {25}}),
    "wells": ({"h875"}, {"Gen": {16, 21, 24, 26, 29}, "Num": {21}}),
}
# where the text crosses languages, the pair is named by hand: the later verse names the earlier thing
CROSS = [
    ("bronze-serpent", "Num.21.9", "serpent", "Jhn.3.14", "serpent"),
    ("josephs-bones", "Gen.50.25", "bones", "Heb.11.22", "bones"),
    ("oxen", "Deu.25.4", "ox", "1Co.9.9", "ox"),
    ("wells", "Gen.29.2", "well", "Jhn.4.6", "well"),           # "Jacob's well": Genesis never puts one at Sychar
]
BOOK = dict(zip(
    ["Gen", "Exo", "Lev", "Num", "Deu", "Jos", "Jdg", "Rut", "1Sa", "2Sa", "1Ki", "2Ki", "1Ch", "2Ch", "Ezr", "Neh", "Est",
     "Job", "Psa", "Pro", "Ecc", "Sng", "Isa", "Jer", "Lam", "Ezk", "Dan", "Hos", "Jol", "Amo", "Oba", "Jon", "Mic", "Nam",
     "Hab", "Zep", "Hag", "Zec", "Mal", "Mat", "Mrk", "Luk", "Jhn", "Act", "Rom", "1Co", "2Co", "Gal", "Eph", "Php", "Col",
     "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb", "Jas", "1Pe", "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev"],
    ["Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
     "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job", "Psalm", "Proverbs",
     "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
     "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi", "Matthew", "Mark",
     "Luke", "John", "Acts", "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians", "Philippians",
     "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon", "Hebrews",
     "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude", "Revelation"]))
ORDER = list(BOOK)

BRIEF = """You read Bible verses (the Berean Standard Bible) and say whether two mentions are the same physical thing.

You get a CLAIM that two mentions name one and the same thing, and the two VERSES: the EARLIER verse and the LATER
verse. Answer each with ONE line of JSON:
{"id": "...", "verdict": "...", "words": "...", "why": "..."}

verdict:
- "stated": the later verse itself points back to the earlier thing: "these stones", "the stones they had taken
  from the Jordan", "the bronze serpent that Moses had made", "the sword of Goliath, whom you killed".
- "implied": the account plainly goes on with the same thing in the same scene, and nothing else of its kind has
  come in: the stone a man rolls away is the one just named on the well's mouth.
- "not_said": they are different things (another stoning, another altar, another rock, another well), or only the
  same KIND of thing, or the text does not tie them together. The same word is never enough. A thing used as an
  image, or a law about any ox, is not a particular ox in a story.
- "unclear": the verses could be read either way and you cannot tell.

words: the later verse's words that point back, copied exactly ("" if none).
why: one short reason.

Worked examples (not from the items):
- EARLIER 1 Samuel 17:51 "David ran and stood over him. He grabbed the Philistine's sword ..." LATER 1 Samuel 21:9
  "The priest replied, 'The sword of Goliath the Philistine, whom you killed in the Valley of Elah ...'" ->
  "stated", words "The sword of Goliath the Philistine, whom you killed".
- EARLIER Genesis 29:3 "... they would roll away the stone from the mouth of the well ..." LATER Genesis 29:10
  "... he went up and rolled the stone away from the mouth of the well ..." -> "implied": the same scene, the same
  well, no other stone.
- EARLIER Genesis 28:18 "... Jacob took the stone that he had placed under his head, and he set it up as a pillar
  ..." LATER Genesis 31:45 "So Jacob picked out a stone and set it up as a pillar." -> "not_said": another place,
  another stone, the same kind of act.
- EARLIER Exodus 21:28 "If an ox gores a man or a woman to death, the ox must surely be stoned ..." LATER 2 Samuel
  6:6 "... Uzzah reached out and took hold of the ark of God, because the oxen had stumbled." -> "not_said": a law
  about any ox, and a particular team in a story.

Answer every item, one line each, nothing else."""


def words_by_set():
    """(set, ref, BSB word) for every mention in each set's scope, one per verse and set, in canon order."""
    want = {s for strongs, _ in SETS.values() for s in strongs}
    got = {}
    for line in gzip.open(ROOT / "out" / "structure-nodes.jsonl.gz", "rt", encoding="utf-8"):
        d = json.loads(line)
        if not d.get("word"):
            continue
        s = str(d.get("strong") or "").lstrip("0").rstrip("abcdefgh")
        k = ("g" if d.get("lang") == "greek" else "h") + s
        if k not in want:
            continue
        ref = to_english(d["ref"])          # MACULA numbers some verses as the Hebrew does (Exod 21:37 is 22:1)
        b, c, v = ref.split(".")
        for name, (strongs, scope) in SETS.items():
            if k in strongs and b in scope and (scope[b] is None or int(c) in scope[b]):
                got.setdefault((name, ref), (d.get("text") or "").strip() or "it")
    return sorted(((n, r, w) for (n, r), w in got.items()),
                  key=lambda x: (x[0], ORDER.index(x[1].split(".")[0]), int(x[1].split(".")[1]), int(x[1].split(".")[2])))


def verses():
    """The Berean's verses, keyed as the structure layer writes them (its "Deu.27.2", the verse file's "Deut")."""
    codes = ["Gen", "Exo", "Lev", "Num", "Deu", "Jos", "Jdg", "Rut", "1Sa", "2Sa", "1Ki", "2Ki", "1Ch", "2Ch", "Ezr",
             "Neh", "Est", "Job", "Psa", "Pro", "Ecc", "Sng", "Isa", "Jer", "Lam", "Ezk", "Dan", "Hos", "Jol", "Amo",
             "Oba", "Jon", "Mic", "Nam", "Hab", "Zep", "Hag", "Zec", "Mal", "Mat", "Mrk", "Luk", "Jhn", "Act", "Rom",
             "1Co", "2Co", "Gal", "Eph", "Php", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb", "Jas", "1Pe",
             "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev"]
    seen, out = [], {}
    for line in open(ROOT / "data" / "bible" / "verses.bsb.jsonl", encoding="utf-8"):
        d = json.loads(line)
        if "b" in d:
            if d["b"] not in seen:
                seen.append(d["b"])
            out[f"{codes[seen.index(d['b'])]}.{d['c']}.{d['v']}"] = d["t"]
    assert len(seen) == len(codes) == 66, len(seen)
    return out


def say(ref):
    b, c, v = ref.split(".")
    return f"{BOOK[b]} {c}:{v}"


def pair(name, a, wa, b, wb, text, n):
    return {"key": f"{name}:{a}>{b}", "id": f"o{n}", "set": name,
            "claim": f"The {wb.lower()} of {say(b)} and the {wa.lower()} of {say(a)} are one and the same.",
            "ref": say(b), "verse": text[b], "context": [f"EARLIER ({say(a)}): {text[a]}"]}


# PLANTS: pairs that look like real ones (the same word, often the same book), where the text plainly keeps the two
# apart. Each must come back "not_said". (later, its word, earlier, its word), picked by hand on 2026-11-06.
PLANTS = [
    ("Jos.8.31", "stones", "Jos.4.20", "stones"),       # the altar of uncut stones on Ebal; the twelve at Gilgal
    ("Jos.10.18", "stones", "Jos.4.20", "stones"),      # the large stones over the cave at Makkedah
    ("Jos.24.26", "stone", "Jos.4.20", "stones"),       # the large stone under the oak at Shechem
    ("Jos.7.26", "stones", "Lev.24.23", "stones"),      # Achan's heap; the blasphemer's stoning
    ("Jos.10.11", "hailstones", "Jos.4.3", "stones"),   # the hailstones at Beth-horon
    ("Jhn.11.38", "stone", "Mat.27.60", "stone"),       # Lazarus's tomb; the tomb of Jesus
    ("1Ki.7.25", "oxen", "1Sa.6.7", "cows"),            # the twelve bronze oxen under the Sea; the milk cows
    ("1Ki.19.21", "oxen", "2Sa.24.22", "oxen"),         # Elisha's yoke of oxen; Araunah's
    ("2Ki.16.17", "oxen", "1Sa.6.7", "cows"),           # the bronze oxen Ahaz took the Sea from; the milk cows
    ("2Ki.18.4", "serpent", "Gen.3.1", "serpent"),      # the bronze serpent; the serpent in the garden
    ("Num.21.16", "well", "Gen.26.32", "well"),         # the well at Beer; Isaac's well at Beersheba
    ("Gen.29.2", "well", "Gen.16.14", "well"),          # the well at Haran; Beer-lahai-roi
]


# THE WIDER PASS (2026-11-06, the same day): the same question over objects the text follows through their stories,
# built while the test was read, and sent only if the test held. Each set mixes the one thing with others of its kind
# the text keeps apart (Gideon's ephod, Jeroboam's calves, the Samaritan woman's jar).
WIDE = "18-object-identity-wide"
WIDE_SETS = {
    "ark": ({"h727"}, {"Exo": {25, 37, 40}, "Num": {10}, "Deu": {10}, "Jos": {3, 4, 6}, "1Sa": {4, 5, 6, 7},
                       "2Sa": {6}, "1Ki": {8}, "1Ch": {13, 15, 16}, "2Ch": {5, 35}, "Gen": {50}, "2Ki": {12}}),
    "goliaths-sword": ({"h2719"}, {"1Sa": {17, 21, 22}}),
    "staff-and-rod": ({"h4294"}, {"Exo": {4, 7, 8, 9, 10, 14, 17}, "Num": {17, 20}}),
    "elijahs-mantle": ({"h155"}, {"1Ki": {19}, "2Ki": {2}}),
    "the-tablets": ({"h3871"}, {"Exo": {24, 31, 32, 34}, "Deu": {4, 5, 9, 10}, "1Ki": {8}, "2Ch": {5}}),
    "lampstand": ({"h4501"}, {"Exo": {25, 37, 40}, "Lev": {24}, "Num": {8}, "Zec": {4}}),
    "ephod": ({"h646"}, {"Exo": {28, 39}, "Jdg": {8, 17, 18}, "1Sa": {2, 21, 23, 30}}),
    "the-cart": ({"h5699"}, {"1Sa": {6}, "2Sa": {6}, "1Ch": {13}}),
    "altars": ({"h4196"}, {"Gen": {8, 12, 13, 22, 26, 33, 35}, "Jos": {22}, "Jdg": {6}, "1Ki": {18}, "2Ki": {16}}),
    "golden-calf": ({"h5695"}, {"Exo": {32}, "Deu": {9}, "1Ki": {12}, "Neh": {9}, "Psa": {106}}),
    "jacobs-pillar": ({"h4676"}, {"Gen": {28, 31, 35}}),
    "josephs-robe": ({"h3801"}, {"Gen": {37}}),
    "jars": ({"g5201"}, {"Jhn": {2, 4}}),
    "boats": ({"g4143"}, {"Mrk": {4, 5, 6, 8}}),
    "nets": ({"g1350"}, {"Luk": {5}, "Jhn": {21}}),
    "the-cup": ({"g4221"}, {"Mat": {26}, "Mrk": {14}, "Luk": {22}, "1Co": {11}}),
}
WIDE_CROSS = [
    ("ark", "Exo.25.10", "ark", "Heb.9.4", "ark"),
    ("staff-and-rod", "Num.17.8", "staff", "Heb.9.4", "staff"),
    ("the-tablets", "Exo.34.1", "tablets", "Heb.9.4", "tablets"),
]
WIDE_PLANTS = [
    ("Jdg.8.27", "ephod", "Exo.28.6", "ephod"),          # Gideon's ephod at Ophrah; the high priest's
    ("1Ki.12.28", "calves", "Exo.32.4", "calf"),         # Jeroboam's two calves; Aaron's at Sinai
    ("Heb.11.7", "ark", "Heb.9.4", "ark"),               # Noah's ark; the ark of the covenant
    ("Jhn.4.28", "jar", "Jhn.2.6", "jars"),              # the Samaritan woman's jar; the jars at Cana
    ("Jhn.21.6", "net", "Luk.5.4", "nets"),              # the net after the resurrection; the nets at Gennesaret
    ("Zec.4.2", "lampstand", "Exo.25.31", "lampstand"),  # the lampstand in Zechariah's vision; the tabernacle's
    ("Gen.35.20", "pillar", "Gen.28.18", "pillar"),      # the pillar on Rachel's grave; the pillar at Bethel
    ("2Ki.16.10", "altar", "1Ki.18.30", "altar"),        # the altar Ahaz saw at Damascus; the altar on Carmel
    ("Jos.22.10", "altar", "Gen.12.7", "altar"),         # the altar by the Jordan; Abram's at Shechem
    ("Gen.50.26", "coffin", "Exo.25.10", "ark"),         # Joseph's coffin (the same Hebrew word); the ark
    ("1Sa.17.51", "sword", "1Sa.17.39", "sword"),        # Goliath's sword; the sword David put on and took off
    ("Mrk.8.10", "boat", "Mrk.4.1", "boat"),             # the boat to Dalmanutha; the boat he taught from
]


def build(name=NAME, sets=None, cross=None, plants_spec=None, budget=0.25, same_cap=None):
    """same_cap: pair each mention with only its nearest earlier mentions in the chapter (the wide pass: the ark alone
    made 751 pairs with every one, from chapters that name it dozens of times; the nearest four still link the chain)."""
    global SETS
    if sets is not None:
        SETS = sets
    cross = CROSS if cross is None else cross
    plants_spec = PLANTS if plants_spec is None else plants_spec
    out_dir = ROOT / "out" / "orchestra-intake" / name
    text = verses()
    mentions = words_by_set()
    items, n = [], 0
    for set_name in SETS:
        ms =[(r, w) for s, r, w in mentions if s == set_name]
        for i, (rb, wb) in enumerate(ms):
            chap = rb.rsplit(".", 1)[0]
            same = [(ra, wa) for ra, wa in ms[:i] if ra.rsplit(".", 1)[0] == chap]
            if same_cap:
                same = same[-same_cap:]
            other = [(ra, wa) for ra, wa in ms[:i] if ra.rsplit(".", 1)[0] != chap][-EARLIER:]
            for ra, wa in other + same:
                n += 1
                items.append(pair(set_name, ra, wa, rb, wb, text, n))
    for set_name, ra, wa, rb, wb in cross:
        n += 1
        items.append(pair(set_name, ra, wa, rb, wb, text, n))
    # a plant that is also a real pair is read once, as the plant (its answer is known); the test pass has none
    planted_keys = {f"{a}>{b}" for b, _wb, a, _wa in plants_spec}
    dropped = [x for x in items if x["key"].split(":", 1)[1] in planted_keys]
    items = [x for x in items if x not in dropped]
    if dropped:
        print(f"{len(dropped)} real pair(s) read as plants instead: {[x['key'] for x in dropped]}")
    plants = []
    for i, (b, wb, a, wa) in enumerate(plants_spec, 1):
        p = pair("plant", a, wa, b, wb, text, 0)
        plants.append({"id": f"p{i}", "claim": p["claim"], "ref": p["ref"], "verse": p["verse"],
                       "context": p["context"], "expect": "not_said"})
    rnd = random.Random(SEED)
    rnd.shuffle(items)                    # the Mac reads them out of canon order, as DeepSeek does
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "object_identity"}}) + "\n")
        for it in items:
            f.write(json.dumps({"key": it["key"], "messages": messages(it)}, ensure_ascii=False) + "\n")
    spec = {"pass": name, "mac_job": f"{name}.jsonl", "priority": 10,
            # a small whole pass: every pair the Mac reads goes to DeepSeek, so each has three readings
            "flag": {"verdict_in": ["stated", "implied", "partly", "not_said", "unclear"]},
            "deepseek": {"runs": 2, "batch": 36, "brief": "brief.md", "planted": "planted.jsonl", "budget_usd": budget},
            "allowed_fields": ["id", "claim", "ref", "verse", "context"]}
    (out_dir / f"{name}.pass.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "brief.md").write_text(BRIEF + "\n", encoding="utf-8", newline="\n")
    with open(out_dir / "items.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps({k: it[k] for k in ("key", "id", "claim", "ref", "verse", "context")},
                               ensure_ascii=False) + "\n")
    with open(out_dir / "planted.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for p in plants:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    by = {}
    for it in items:
        by[it["set"]] = by.get(it["set"], 0) + 1
    print(f"{name}: {len(items)} pairs {by}; {len(plants)} plants")


def messages(it, brief=None):
    return [{"role": "system", "content": brief or BRIEF},
            {"role": "user", "content": f"id: {it['id']}\nCLAIM: {it['claim']}\n{it['context'][0]}\n"
                                        f"LATER ({it['ref']}): {it['verse']}"}]


# ---- WORD BY WORD (2026-11-06, the evening) ---------------------------------------------------------------------------
# The verse-level pass kept one mention per verse, and a verse that names two things of one kind became one mention:
# Num 17:6 ("twelve staffs, and Aaron's staff was among them") joined the tribes' staffs to Aaron's, Judg 6:28 Baal's
# altar to Gideon's, 2 Kgs 16:14 Solomon's bronze altar to Ahaz's copy. Both models agreed on those pairs, because a
# pair named a verse and not a word, and no plant could catch it. Here every word is its own mention, and each claim
# quotes the clause it stands in, in MACULA's own English gloss: the same source for the items and the plants, so a
# plant cannot be told by its style.
WORDS = "19-object-identity-words"
WORD_SETS = {k: WIDE_SETS[k] for k in ("staff-and-rod", "altars", "the-tablets")}
# plants by word: (set, later ref, which mention of the word in that verse, earlier ref, which mention), counted in
# the Hebrew's order from 0; each pair is two things the text keeps apart
WORD_PLANTS = [
    ("staff-and-rod", "Num.17.6", "two ten «", "Num.17.8", "Aaron"), # the tribes' twelve; Aaron's, which budded
    ("staff-and-rod", "Num.20.8", "", "Num.17.2", "two ten «"),      # the staff from before the LORD; the twelve
    ("altars", "Jdg.6.28", "«altar» Baal", "Jdg.6.26", ""),          # Baal's altar; the altar Gideon was to build
    ("altars", "2Ki.16.14", "bronze", "2Ki.16.11", ""),              # Solomon's bronze altar; Uriah's copy
    ("altars", "Jos.22.19", "«altar» LORD", "Jos.22.10", ""),        # the altar of the LORD; the altar by the Jordan
    ("altars", "1Ki.18.30", "", "1Ki.18.26", ""),                    # the LORD's altar repaired; Baal's altar
    ("altars", "Gen.13.18", "", "Gen.12.7", ""),                     # at Hebron; at Shechem
    ("altars", "Gen.35.7", "", "Gen.33.20", ""),                     # El-bethel; El-Elohe-Israel at Shechem
    ("the-tablets", "Exo.34.4", "", "Exo.32.19", ""),                # the second set; the first, broken
    ("the-tablets", "Deu.10.3", "", "Deu.9.17", ""),                 # the second set; the first, shattered
    ("the-tablets", "Deu.10.5", "", "Deu.10.2", "former which"),     # the second, in the ark; "the former tablets"
    ("the-tablets", "Exo.34.28", "", "Exo.34.1", "first which"),     # what he wrote on; "the first tablets"
]


def _gloss(text):
    """A clause's MACULA gloss, readable: 'it.had.been.pulled.down the.altar of.(the) Baal' -> 'it had been pulled
    down the altar of Baal'."""
    s = re.sub(r"\((?:et|cmp|the)\)\s*", "", text or "")
    s = re.sub(r"[֐-׿Ͱ-Ͽἀ-῿]+", "", s)       # a Hebrew or Greek word left in the gloss
    s = s.replace(".", " ").replace("[", "").replace("]", "")
    return re.sub(r"\s+", " ", s).strip()


SPAN = 5      # words each side of the mention, within its clause


def words_by_word(sets):
    """(set, English ref, word id, its BSB word, its words in the verse with itself marked) for every word in each
    set's scope, in canon order and then the word's place in the verse. The run is the clause's words, in the
    original's order, each in its own English rendering, with the mention in «»: in Num 17:21 (English 17:6) one
    clause holds Aaron's rod and the twelve, and only the mark tells "«staff» Aaron among staffs" from
    "staff Aaron among «staffs»"."""
    want = {s for strongs, _ in sets.values() for s in strongs}
    words, clauses, verse_words = [], {}, {}
    for line in gzip.open(ROOT / "out" / "structure-nodes.jsonl.gz", "rt", encoding="utf-8"):
        d = json.loads(line)
        if "#cl" in d.get("id", "") and d.get("w") and d.get("text"):
            clauses.setdefault(d["ref"], []).append((len(d["w"]), set(d["w"])))
        if not d.get("word"):
            continue
        verse_words.setdefault(d["ref"], {})[d["w"][0]] = (d.get("text") or "").strip()
        k = ("g" if d.get("lang") == "greek" else "h") + str(d.get("strong") or "").lstrip("0").rstrip("abcdefgh")
        if k in want:
            words.append((k, d))
    out = []
    for k, d in words:
        ref = to_english(d["ref"])
        b, c, _v = ref.split(".")
        w = d["w"][0]
        cl = min((x for x in clauses.get(d["ref"], []) if w in x[1]), default=None, key=lambda x: x[0])
        vw = verse_words.get(d["ref"], {})
        ws = sorted(i for i in (cl[1] if cl else vw) if i in vw and vw[i])
        at = ws.index(w) if w in ws else 0
        run = " ".join(f"«{vw[i]}»" if i == w else vw[i] for i in ws[max(0, at - SPAN):at + SPAN + 1])
        if k == "h4294" and re.match(r"(?i)tribe", d.get("text") or ""):
            continue                     # מַטֶּה is a staff and a tribe; the English rendering tells which
        for name, (strongs, scope) in sets.items():
            if k in strongs and b in scope and (scope[b] is None or int(c) in scope[b]):
                out.append((name, ref, d["id"], (d.get("text") or "").strip() or "it", run))
    return sorted(out, key=lambda x: (x[0], ORDER.index(x[1].split(".")[0]), int(x[1].split(".")[1]),
                                      int(x[1].split(".")[2]), int(x[2].rsplit("#w", 1)[1])))


WORD_BRIEF = BRIEF.replace(
    "Answer every item, one line each, nothing else.",
    "THE MARKED WORDS. Each CLAIM quotes a few of the verse's words, in the original language's order, each in its "
    "English rendering, with the mention it means in «» (\"two ten «staffs»\" is \"twelve staffs\"). A verse may name "
    "two different things of one kind: \"Aaron's staff was among their staffs\", or Baal's altar torn down and the new "
    "altar built. Judge only the marked word, never another of its kind in the same verse.\n\n"
    "Answer every item, one line each, nothing else.")
assert WORD_BRIEF != BRIEF


def word_pair(name, a, b, text, n):
    """a, b: (ref, word id, word, gloss)."""
    (ra, ia, wa, ga), (rb, ib, wb, gb) = a, b
    wa, wb = (re.sub(r"(?i)^(a|an|the) ", "", x) for x in (wa, wb))     # the Greek's "a stone": "The a stone ..."
    return {"key": f"{name}:{ia}>{ib}", "id": f"w{n}", "set": name,
            "claim": f"The {wb.lower()} marked in {say(rb)} (\"{gb}\") and the {wa.lower()} marked in {say(ra)} "
                     f"(\"{ga}\") are one and the same.",
            "ref": say(rb), "verse": text[rb], "context": [f"EARLIER ({say(ra)}): {text[ra]}"]}


def build_words(budget=0.6, same_cap=4, name=None, sets=None, plants_spec=None):
    name, sets, plants_spec = name or WORDS, sets or WORD_SETS, plants_spec or WORD_PLANTS
    text = verses()
    mentions = words_by_word(sets)
    items, n = [], 0
    for set_name in sets:
        ms = [(r, i, w, g) for s, r, i, w, g in mentions if s == set_name]
        for j, mb in enumerate(ms):
            chap = mb[0].rsplit(".", 1)[0]
            same = [ma for ma in ms[:j] if ma[0].rsplit(".", 1)[0] == chap][-same_cap:]
            other = [ma for ma in ms[:j] if ma[0].rsplit(".", 1)[0] != chap][-EARLIER:]
            for ma in other + same:
                n += 1
                items.append(word_pair(set_name, ma, mb, text, n))
    # the plants, found by word: the mention of the set's word in that verse whose clause gloss holds the hint
    def find(s, ref, hint):
        cands = [(r, i, w, g) for s2, r, i, w, g in mentions if s2 == s and r == ref]
        hit = [c for c in cands if hint.lower() in c[3].lower()] if hint else cands
        assert hit, f"plant: no {s} word in {ref} whose clause holds {hint!r}: {[c[3] for c in cands]}"
        return hit[0]
    plants, planted_keys = [], set()
    for i, (s, rb, hb, ra, ha) in enumerate(plants_spec, 1):
        p = word_pair(s, find(s, ra, ha), find(s, rb, hb), text, 0)
        planted_keys.add(p["key"])
        plants.append({"id": f"p{i}", "claim": p["claim"], "ref": p["ref"], "verse": p["verse"],
                       "context": p["context"], "expect": "not_said"})
    dropped = [x for x in items if x["key"] in planted_keys]
    items = [x for x in items if x["key"] not in planted_keys]
    if dropped:
        print(f"{len(dropped)} real pair(s) read as plants instead")
    random.Random(SEED).shuffle(items)
    out_dir = ROOT / "out" / "orchestra-intake" / name
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"_job": {"model": "gemma4:26b", "options": OPTIONS, "pass": "object_identity"}}) + "\n")
        for it in items:
            f.write(json.dumps({"key": it["key"], "messages": messages(it, WORD_BRIEF)}, ensure_ascii=False) + "\n")
    spec = {"pass": name, "mac_job": f"{name}.jsonl", "priority": 10,
            "flag": {"verdict_in": ["stated", "implied", "partly", "not_said", "unclear"]},
            "deepseek": {"runs": 2, "batch": 36, "brief": "brief.md", "planted": "planted.jsonl", "budget_usd": budget},
            "allowed_fields": ["id", "claim", "ref", "verse", "context"]}
    (out_dir / f"{name}.pass.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "brief.md").write_text(WORD_BRIEF + "\n", encoding="utf-8", newline="\n")
    with open(out_dir / "items.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for it in items:
            f.write(json.dumps({k: it[k] for k in ("key", "id", "claim", "ref", "verse", "context")},
                               ensure_ascii=False) + "\n")
    with open(out_dir / "planted.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for p in plants:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    by = {}
    for it in items:
        by[it["set"]] = by.get(it["set"], 0) + 1
    print(f"{name}: {len(items)} pairs {by}; {len(plants)} plants")


# THE FIVE TEST CARDS, WORD BY WORD (2026-11-07). The five cards are built from the first pass's chains, and that
# pass was verse-level, with the same risk the staffs showed: Deut 27 names the plastered stones and the altar's a
# few verses apart, and Josh 4:9 stands beside the Gilgal twelve. So the same sets are read again, word by word,
# before any chain becomes a card. The test pass's plants, by word; the garden's serpent (Gen 3:1) is outside the
# bronze serpent's books, so that plant is the bronze snake against the venomous ones (ruled different, 2026-11-06).
FIVE = "20-object-identity-five-words"
FIVE_PLANTS = [
    ("jordan-stones", "Jos.8.31", "", "Jos.4.20", ""),
    ("jordan-stones", "Jos.10.18", "", "Jos.4.20", ""),
    ("jordan-stones", "Jos.24.26", "", "Jos.4.20", ""),
    ("jordan-stones", "Jos.7.26", "", "Lev.24.23", ""),
    ("jordan-stones", "Jos.10.11", "", "Jos.4.3", ""),
    ("tomb-stone", "Jhn.11.38", "", "Mat.27.60", ""),
    ("oxen", "1Ki.7.25", "", "1Sa.6.7", ""),
    ("oxen", "1Ki.19.21", "", "2Sa.24.22", ""),
    ("oxen", "2Ki.16.17", "", "1Sa.6.7", ""),
    ("bronze-serpent", "Num.21.9", "", "Num.21.6", ""),
    ("wells", "Num.21.16", "", "Gen.26.32", ""),
    ("wells", "Gen.29.2", "", "Gen.16.14", ""),
]


if __name__ == "__main__":
    {"build": build,
     "wide": lambda: build(WIDE, WIDE_SETS, WIDE_CROSS, WIDE_PLANTS, budget=1.0, same_cap=4),
     "words": build_words,
     "five": lambda: build_words(budget=0.6, name=FIVE, sets=SETS, plants_spec=FIVE_PLANTS)}[sys.argv[1]]()
