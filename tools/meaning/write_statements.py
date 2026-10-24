"""VERB STATEMENTS INTO THE RELATION STORE (plan 2.19, lift 1;
2026-10-19: not just direction, but relationships on the clause level (God
loved world) should show up on the relationship level; then the verb
statement preview approved).

From the statements both judges kept, every end checked
(out/meaning/lift/relations-final.jsonl), one relation row each, in the store's
own shape, so the cards, the navigator and the claim export carry them:

  type      `states`: a statement the text makes, its verb as its label
  label     the verse's own rendering of the verb, pronouns and helpers taken
            off ("He loved" -> "loved"); inverse for the other end ("loved by")
  family    the verb's WordNet class (verb.emotion for love), the published top
            tier of plan 2.17 step 3, drawn through English and marked so
  verb      the Hebrew or Greek lemma and its key; modality "stated" (the gate
            sends only stated clauses); the clause it was lifted from
  time      whether the verb's form says it happened; where it does not (a
            future, a subjunctive, a Hebrew yiqtol or weqatal) the row is
            `held` until a reading decides its time
  reading   lifted from the clause, two judges, every end checked

Where a hand-built relation already says it (the same two records, a verse in
common), the hand row stays the curated form and no `states` row is written:
the statement is its evidence (plan 2.19), counted.

    python tools/meaning/write_statements.py   -> ontology/relations/verb-statements.jsonl
"""
import collections
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from derive import BOOK  # noqa: E402

DEST = ROOT / "ontology" / "relations" / "verb-statements.jsonl"
FROM_ABBR = {v: k for k, v in BOOK.items()}          # Mat -> Matt
# the prophets (MACULA codes), where a qatal may be a prophetic perfect
PROPHETS = {"Isa", "Jer", "Lam", "Ezk", "Dan", "Hos", "Jol", "Amo", "Oba", "Jon", "Mic", "Nam", "Hab", "Zep",
            "Hag", "Zec", "Mal"}
# books whose narrator is an "I": the letters, Revelation, Acts' "we", and the
# memoirs (Ezra, Nehemiah, Ecclesiastes, Daniel's visions)
I_NARRATOR = {"Rom", "1Co", "2Co", "Gal", "Eph", "Php", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb",
              "Jas", "1Pe", "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev", "Act", "Ezr", "Neh", "Ecc", "Dan"}
# verbs no WordNet family fits honestly (their English misleads the lookup)
NO_FAMILY = {"h3205": "begetting and birth (יָלַד): the English 'bore' reads as feeling",
             "g1080": "begetting (γεννάω): no family; God begetting (Heb 5:5) is not 'the body'"}
# the divine persons: never the narrator's "I" (Heb 5:5 quotes God)
DIVINE = {"god", "jesus", "holy_ghost", "the_father", "spirit", "spirit_of_god"}
# held by row, with the reason, where neither the form nor a rule shows it
# (the committee's third sitting, D3)
HELD_ROWS = {("Rom 2:16", "god", "secret"): "the present form (κρίνει) is the final judgment, 'on the day when God "
                                           "will judge': not a past event"}
_QUOTES = None


def quote_side(ref, plain):
    """Whether a statement in verse `ref` stands inside the Berean's quotation
    marks: "inside", "outside", "unknown" (tools/meaning/quoted.py)."""
    global _QUOTES
    if _QUOTES is None:
        from quoted import berean_quotes
        _QUOTES = berean_quotes()
    from quoted import verb_side
    q, texts = _QUOTES
    kind = q.get(ref)
    if kind == "whole":
        return "inside"
    if kind == "part":
        return verb_side(plain, [texts[ref]])
    return "outside"
LEAD = {"i", "he", "she", "it", "we", "you", "they", "who", "will", "shall", "would", "may", "might", "can",
        "could", "do", "does", "did", "have", "has", "had", "to", "let", "us", "me", "him", "them", "and", "not"}
PARTICIPLE = {"gave": "given", "give": "given", "took": "taken", "take": "taken", "saw": "seen", "see": "seen",
              "knew": "known", "know": "known", "smote": "smitten", "struck": "struck", "strike": "struck",
              "bore": "borne", "bear": "borne", "begot": "begotten", "beget": "begotten", "ate": "eaten",
              "wrote": "written", "spoke": "spoken", "chose": "chosen", "choose": "chosen", "forsook": "forsaken",
              "forsake": "forsaken", "drew": "drawn", "threw": "thrown", "slew": "slain", "slay": "slain",
              "sold": "sold", "brought": "brought", "bring": "brought", "built": "built", "build": "built",
              "found": "found", "find": "found", "told": "told", "tell": "told", "heard": "heard", "hear": "heard",
              "kept": "kept", "keep": "kept", "left": "left", "leave": "left", "led": "led", "lead": "led",
              "met": "met", "meet": "met", "paid": "paid", "put": "put", "set": "set", "said": "said",
              "sought": "sought", "seek": "sought", "taught": "taught", "teach": "taught", "caught": "caught",
              "fought": "fought", "fight": "fought", "held": "held", "hold": "held", "hid": "hidden",
              "rode": "ridden", "rose": "risen", "sent": "sent", "send": "sent", "made": "made", "make": "made",
              "became": "become", "began": "begun", "bound": "bound", "bind": "bound", "fed": "fed",
              "feed": "fed", "won": "won", "lost": "lost", "struck down": "struck down", "shot": "shot",
              "laid": "laid", "lay": "laid", "met with": "met with", "overtook": "overtaken", "forgave": "forgiven",
              "forgive": "forgiven", "anointed": "anointed", "hated": "hated", "hate": "hated", "loved": "loved"}
FAMILY_LABEL = {"verb.emotion": "feeling", "verb.possession": "giving and taking", "verb.contact": "touching and striking",
                "verb.motion": "moving", "verb.communication": "speaking", "verb.creation": "making",
                "verb.perception": "seeing and hearing", "verb.social": "acting toward others",
                "verb.cognition": "knowing and thinking", "verb.change": "changing", "verb.body": "the body",
                "verb.competition": "fighting", "verb.consumption": "eating and drinking", "verb.stative": "being",
                "verb.weather": "weather"}


# THE STORE CITES ENGLISH VERSE NUMBERS, the clauses carry MACULA's: Mal 3:22 in
# the Hebrew is Mal 4:4 in the Berean, and the validator refused 12 such rows as
# dead references on the first write (2026-10-19). The same map the sweep's text
# lookup uses (tools/sweep/context.py)
MOVED = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8")).get("moved") or {}


def human(ref):
    b, c, v = MOVED.get(ref, ref).split(".")
    return f"{FROM_ABBR.get(b, b)} {c}:{v}"


def label_of(vt):
    """The verse's own verb, its pronouns and helpers taken off."""
    words = " ".join(unjoin(w) for w in re.findall(r"[A-Za-z']+", (vt or "").replace("~", " "))).split()
    # pronouns and helpers off the front, and an adverb before its verb: "I
    # dearly love" (John 21:15) had no verb at its head and was held back
    while words and (words[0].lower() in LEAD or (words[0].lower().endswith("ly") and len(words) > 1)):
        words = words[1:]
    return " ".join(w.lower() for w in words) or (vt or "").lower()


# ONE TENSE FOR EVERY LABEL (2026-10-19): the renderings mix them ("show",
# "shown", "commanding", "will save"), and 264 of 848 inverses could not be
# made from them ("afraided by"). So each verb goes to its base form (WordNet),
# then to its simple past for the subject's card and its past participle for
# the other's: "commanded" / "commanded by", "showed" / "shown by"
IRREGULAR = {  # base: (past, participle)
    "give": ("gave", "given"), "take": ("took", "taken"), "see": ("saw", "seen"), "show": ("showed", "shown"),
    "know": ("knew", "known"), "smite": ("smote", "smitten"), "strike": ("struck", "struck"),
    "bear": ("bore", "borne"), "beget": ("begot", "begotten"), "eat": ("ate", "eaten"), "write": ("wrote", "written"),
    "speak": ("spoke", "spoken"), "choose": ("chose", "chosen"), "forsake": ("forsook", "forsaken"),
    "draw": ("drew", "drawn"), "throw": ("threw", "thrown"), "slay": ("slew", "slain"), "sell": ("sold", "sold"),
    "bring": ("brought", "brought"), "build": ("built", "built"), "find": ("found", "found"), "tell": ("told", "told"),
    "hear": ("heard", "heard"), "keep": ("kept", "kept"), "leave": ("left", "left"), "lead": ("led", "led"),
    "meet": ("met", "met"), "pay": ("paid", "paid"), "repay": ("repaid", "repaid"), "put": ("put", "put"),
    "set": ("set", "set"), "say": ("said", "said"), "seek": ("sought", "sought"), "teach": ("taught", "taught"),
    "catch": ("caught", "caught"), "fight": ("fought", "fought"), "hold": ("held", "held"), "hide": ("hid", "hidden"),
    "ride": ("rode", "ridden"), "rise": ("rose", "risen"), "send": ("sent", "sent"), "make": ("made", "made"),
    "become": ("became", "become"), "begin": ("began", "begun"), "bind": ("bound", "bound"), "feed": ("fed", "fed"),
    "win": ("won", "won"), "lose": ("lost", "lost"), "shoot": ("shot", "shot"), "lay": ("laid", "laid"),
    "overtake": ("overtook", "overtaken"), "forgive": ("forgave", "forgiven"), "do": ("did", "done"),
    "break": ("broke", "broken"), "cast": ("cast", "cast"), "drive": ("drove", "driven"), "come": ("came", "come"),
    "go": ("went", "gone"), "get": ("got", "gotten"), "stand": ("stood", "stood"), "swear": ("swore", "sworn"),
    "tear": ("tore", "torn"), "bite": ("bit", "bitten"), "hang": ("hanged", "hanged"), "spread": ("spread", "spread"),
    "shut": ("shut", "shut"), "cut": ("cut", "cut"), "hit": ("hit", "hit"), "let": ("let", "let"),
    "dwell": ("dwelt", "dwelt"), "flee": ("fled", "fled"), "feel": ("felt", "felt"), "weep": ("wept", "wept"),
    "deal": ("dealt", "dealt"), "buy": ("bought", "bought"), "think": ("thought", "thought"), "fall": ("fell", "fallen"),
    "forget": ("forgot", "forgotten"), "shake": ("shook", "shaken"), "tread": ("trod", "trodden"),
    "commit": ("committed", "committed"), "permit": ("permitted", "permitted"), "submit": ("submitted", "submitted"),
    "rebuke": ("rebuked", "rebuked"), "lift": ("lifted", "lifted"), "anoint": ("anointed", "anointed"),
    "overcome": ("overcame", "overcome"), "withhold": ("withheld", "withheld"), "uphold": ("upheld", "upheld"),
    "forbid": ("forbade", "forbidden"), "undertake": ("undertook", "undertaken"), "mistake": ("mistook", "mistaken"),
    "drink": ("drank", "drunk"), "have": ("had", "had"), "overthrow": ("overthrew", "overthrown"),
    "rebuild": ("rebuilt", "rebuilt"), "shed": ("shed", "shed"), "sweep": ("swept", "swept"),
    "rebel": ("rebelled", "rebelled"), "extol": ("extolled", "extolled"), "spend": ("spent", "spent"),
    "lend": ("lent", "lent"), "bend": ("bent", "bent"), "sling": ("slung", "slung"), "fling": ("flung", "flung"),
    "spring": ("sprang", "sprung"), "sing": ("sang", "sung"), "ring": ("rang", "rung"), "sink": ("sank", "sunk"),
    "swing": ("swung", "swung"), "dig": ("dug", "dug"), "beat": ("beat", "beaten"), "grow": ("grew", "grown"),
    "blow": ("blew", "blown"), "fly": ("flew", "flown"), "wear": ("wore", "worn"), "steal": ("stole", "stolen"),
    "weave": ("wove", "woven"), "wake": ("woke", "woken"), "lie": ("lay", "lain"), "sit": ("sat", "sat"),
    "bid": ("bid", "bid"), "split": ("split", "split"), "quit": ("quit", "quit"), "thrust": ("thrust", "thrust"),
}
FUNC = {"to", "into", "as", "a", "an", "the", "with", "for", "of", "on", "in", "up", "out", "down", "off", "more",
        "away", "back", "over"}


def unjoin(word):
    """Words the renderings run together ("toan", "adrink", "abundantlyprosperous"):
    split where both halves are known, a function word first."""
    from nltk.corpus import wordnet as wn
    lw = word.lower()
    if lw in FUNC or wn.synsets(lw):
        return word
    # the longest function word first: "asa" is "as a", not "a sa"
    for f in sorted(FUNC, key=len, reverse=True):
        b = lw[len(f):]
        if lw.startswith(f) and b and (b in FUNC or wn.synsets(b)):
            return f"{f} {b}"
    for i in range(4, len(lw)):
        a, b = lw[:i], lw[i:]
        if wn.synsets(a) and (b in FUNC or wn.synsets(b)):
            return f"{a} {b}"
    return word
BE = {"be", "was", "were", "is", "are", "been", "am"}
PAST_TO_BASE = {f: b for b, (p, pp) in IRREGULAR.items() for f in (p, pp) if f != b}


def _regular(base):
    if base.endswith("e"):
        return base + "d"
    if base.endswith("y") and len(base) > 2 and base[-2] not in "aeiou":
        return base[:-1] + "ied"
    # one syllable, consonant-vowel-consonant: "stop" -> "stopped"
    if re.fullmatch(r"[^aeiou]*[aeiou][^aeiouwxy]", base):
        return base + base[-1] + "ed"
    return base + "ed"


def forms(lab):
    """(past, participle) of a label's verb, or None when its head is no verb
    or a bare form of "be"."""
    from nltk.stem import WordNetLemmatizer
    from nltk.corpus import wordnet as wn
    head, _, rest = lab.partition(" ")
    if head in BE:
        return None
    # a known irregular past or participle first: WordNet takes "saw" as the
    # verb "to saw" ("sawed", 15 rows on the first run), "found" as "to found"
    # and "-es" by its "-e" verb before WordNet's guess: "hates" came back as
    # "to hat" ("hatted", John 15:18)
    # "hated" likewise ("hat" + "ed"): an "-ed" or "-es" word's "-e" verb wins
    es = head[:-1] if head.endswith(("es", "ed")) and head[-3] != "e" and wn.synsets(head[:-1], pos="v") else None
    base = PAST_TO_BASE.get(head) or es or WordNetLemmatizer().lemmatize(head, "v")
    if not wn.synsets(base, pos="v"):
        return None
    past, part = IRREGULAR.get(base, (_regular(base), _regular(base)))
    tail = (" " + rest) if rest else ""
    return past + tail, part + tail


def inverse_of(lab):
    head, _, rest = lab.partition(" ")
    if lab in PARTICIPLE:
        p = PARTICIPLE[lab]
    elif head in PARTICIPLE:
        p = PARTICIPLE[head] + (" " + rest if rest else "")
    elif head.endswith("ed"):
        p = lab
    elif head.endswith("e"):
        p = head + "d" + (" " + rest if rest else "")
    elif head.endswith("s") and len(head) > 3:            # "loves" -> "loved"
        p = inverse_of(head[:-1] + (" " + rest if rest else "")).removesuffix(" by")
    else:
        p = head + "ed" + (" " + rest if rest else "")
    return p + " by"


def family_of(lab):
    from nltk.corpus import wordnet as wn
    for w in [lab.split(" ")[0], lab.split(" ")[-1]]:
        s = wn.synsets(w, pos="v")
        if s:
            return s[0].lexname()
    return None


def main():
    kept = [json.loads(x) for x in (ROOT / "out/meaning/lift/relations-final.jsonl").read_text(encoding="utf-8").splitlines()]
    recs = {json.loads(x)["clause"]: json.loads(x)
            for x in (ROOT / "out/meaning/clause-records.jsonl").read_text(encoding="utf-8").splitlines()}
    # the hand-built relations, by their two ends IN ORDER, with their verb.
    # The first version counted ANY relation between the pair in the verse as
    # "already said": "Jesus charged Peter" (John 21:15, 17) suppressed "Peter
    # loved Jesus" there (2026-10-19). Only the same statement is the same: same
    # direction, and the hand type's verb is the statement's verb
    import yaml
    tlabel = {k: (v or {}).get("label") or k for k, v in
              (yaml.safe_load((ROOT / "ontology/schema/relationship_types.yaml").read_text(encoding="utf-8"))
               .get("types") or {}).items()}
    hand = collections.defaultdict(list)
    for p in glob.glob(str(ROOT / "ontology/relations/*.jsonl")):
        if Path(p) == DEST:
            continue
        for line in open(p, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                hand[(r.get("src"), r.get("dst"))].append(r)

    def base(words):
        from nltk.stem import WordNetLemmatizer
        w = (words or "").split(" ")[0].lower()
        return PAST_TO_BASE.get(w) or WordNetLemmatizer().lemmatize(w, "v")
    # WHOSE WORDS, PER CLAUSE (out/sweep/statement-voices.jsonl, written by
    # tools/sweep/speaker_credit.py from the rows' clauses): a statement inside a
    # speech turn is the speaker's claim (Peter's "I dearly love You", John
    # 21:15), and rows merge only within one voice, since the same statement in
    # two verses can be in two voices ("deny": Jesus' prediction in John 13:38,
    # the narrator in Mark 14:72). Run this, then speaker_credit.py, then this
    # again; the voices depend on the clauses only, so the second run is stable
    voices = {}
    vp = ROOT / "out" / "sweep" / "statement-voices.jsonl"
    if vp.exists():
        for line in vp.read_text(encoding="utf-8").splitlines():
            v = json.loads(line)
            voices[v["clause"]] = (("held", v["held"]) if "held" in v else
                                   ("speaker", v["speaker"]) if "speaker" in v else ("narrator",))
    # THE TIME READING (plan 2.19a, tools/meaning/statement_time.py): clause ->
    # the answer both judges gave
    tp = ROOT / "ontology" / "provenance" / "meaning" / "statement-time-2026-10-20.jsonl"
    time_read = {}
    if tp.exists():
        for line in tp.read_text(encoding="utf-8").splitlines():
            t_ = json.loads(line)
            if t_.get("answer"):
                time_read[t_["clause"]] = t_["answer"]
    # ONE ANSWER ACROSS PARALLEL PASSAGES (the committee's scholar, second
    # sitting): the same verb in the same form between the same two records
    # must be read the same way, or none of its readings is applied. The
    # judges read the English, and the Berean's tense decided: Ps 9:8 "judges"
    # was released while the same Hebrew in Ps 96:13 and 98:9 was "foretold";
    # אֶקְרָא was "promised" in 2 Sam 22:4 and "happened" in 22:7
    groups = collections.defaultdict(set)
    for x in kept:
        r_ = recs.get(x["id"]) or {}
        if x["id"] in time_read:
            groups[(x["subject"], x["object"], r_.get("verb_key"), r_.get("mood"))].add(time_read[x["id"]])
    split = {k for k, v in groups.items() if len(v) > 1}
    for x in kept:
        r_ = recs.get(x["id"]) or {}
        if (x["subject"], x["object"], r_.get("verb_key"), r_.get("mood")) in split and x["id"] in time_read:
            del time_read[x["id"]]
    parallel_split = len(split)
    st, out, seen, evidence = collections.Counter(), [], {}, []
    if parallel_split:
        st["parallel passages read differently (their readings not applied)"] = parallel_split
    for x in kept:
        # a reflexive ("Elizabeth hid herself", "serve one another") is not a
        # relation between two records: another shape, not written
        if x["subject"] == x["object"]:
            st["reflexive (not a relation between two records)"] += 1
            continue
        ref = human(x["ref"])
        lab = label_of(x["verb_text"])
        # A FORM THAT DOES NOT SAY IT HAPPENED (1.2.0 step 5, 2026-10-20;
        # resolve_records.time_of): a promise or a purpose told in the past
        # tense as a fact ("God put enmity", Gen 3:15's "I will put") is held
        # until a reading decides its time, and is no evidence for a hand row
        rec = recs.get(x["id"]) or {}
        when = rec.get("time") or "past or present (by form)"
        book = x["id"].split(".")[0]
        voice = voices.get(x["id"], ("unknown",))
        mood = (rec.get("mood") or "").lower()
        # A QATAL IN SPEECH OR PROPHECY (the committee's scholar, second
        # sitting): the prophetic perfect tells the future as done ("God
        # swallowed up death", Isa 25:8) and a performative qatal does what it
        # says ("I hereby give"); only in plain narrative does the form say it
        # happened. Weqatal tagged as qatal (Nah 3:6) is caught the same way
        if when == "past or present (by form)" and mood in ("qatal", "weqatal") \
                and (voice[0] in ("speaker", "held") or book in PROPHETS):
            when = f"{mood} in speech or prophecy: not decided by form"
        undecided = when != "past or present (by form)"
        # ...AND THEN READ (plan 2.19a): where two judges agree it happened, it
        # is released as stated; where they agree it is a promise, prediction,
        # command or wish, it is a described statement (exported, never
        # asserted, not drawn on the cards). Anything else stays held
        read = time_read.get(x["id"]) if undecided else None
        described = read if read in ("promised", "foretold", "commanded", "wished") else None
        # THE READING MUST AGREE WITH THE VERB'S PERSON (checking follows the
        # layers): a promise is the speaker's own (first person), a command is
        # to the hearer (second), a prediction is of another (not first). The
        # first spot-check found "commanded" for "all that I command you" (Jer
        # 1:7, Ex 7:2): the judges read the sentence's force, not the clause's
        person = str(rec.get("person") or "")
        if described and not {"promised": person.startswith("first"), "commanded": person.startswith("second"),
                              "foretold": not person.startswith("first"), "wished": True}[described]:
            st[f"time read: {described}, but the verb is {person or 'no'} person (held)"] += 1
            described, read = None, None
        if read == "happened":
            when, undecided = "past or present (by reading)", False
        rows = hand.get((x["subject"], x["object"]), [])
        vb = base(lab)
        same = [r for r in rows
                if (ref in (r.get("refs") or []) or any(str(q).startswith(ref) for q in r.get("refs") or []))
                and base(tlabel.get(r.get("type"), r.get("type", "")).replace("_", " ")) == vb]
        if same and not undecided:
            # the hand row stays the curated form; the clause is its evidence
            # (claim:evidencedBy in the export), never a family over its type
            for r in same:
                evidence.append({"src": r["src"], "type": r["type"], "dst": r["dst"], "ref": ref, "clause": x["id"]})
            st["already a hand-built relation (the statement is its evidence)"] += 1
            continue
        fm = forms(lab)
        if not fm:
            # "was" with its preposition lost ("was with"), or a rendering
            # whose head is no verb ("afraid"): held, not shown wrong
            st["no verb form to label it (held back)"] += 1
            continue
        # THE PLAIN FORM TOO (G6, approved on the 1.2.0 inventory, 2026-10-20):
        # a statement described and not stated -- a command, a promise, a
        # prediction -- is labelled by its plain form ("love", Deut 6:5), never
        # the past tense, which would say it happened
        plain = " ".join([base(lab)] + lab.split(" ")[1:])
        lab, inv = fm[0], fm[1] + " by"
        # ONE ROW PER STATEMENT, its verses together: the same two records and
        # the same verb in several verses is one row citing them all (the
        # validator flagged 158 rows as copies on the first write)
        voice = voices.get(x["id"], ("unknown",))
        key = (x["subject"], x["object"], lab, voice,
               f"described: {described}" if described else when if undecided else None)
        if key in seen:
            row = seen[key]
            if ref not in row["refs"]:
                row["refs"].append(ref)
                st["the same statement in another verse (merged)"] += 1
            row["clauses"].append(x["id"])
            continue
        fam = family_of(lab)
        fam_from = "WordNet, through the English"
        # BEGETTING AND BIRTH TAKE NO FAMILY (the committee's scholar, both
        # sittings): through the English "bore" filed eleven births under
        # "feeling", and γεννάω put God begetting (Heb 5:5) under "the body".
        # Better none than a wrong one
        if rec.get("verb_key") in NO_FAMILY:
            fam, fam_from = None, "withheld: " + NO_FAMILY[rec["verb_key"]]
        seen[key] = row = {"src": x["subject"], "type": "states", "dst": x["object"], "refs": [ref],
                    "certainty": "explicit", "label": lab, "inverse_label": inv, "label_plain": plain,
                    "verb": x["verb"], "verb_key": rec.get("verb_key"), "verb_strong": rec.get("verb_strong"),
                    "verb_text": x["verb_text"],
                    "family": fam, "family_label": FAMILY_LABEL.get(fam), "family_from": fam_from,
                    "modality": rec.get("modality", "stated"), "modality_from": rec.get("modality_from", "form"),
                    # the clause's own grammar (plan 2.17 step 3): without the
                    # stem and voice, 1 Tim 1:11 read "Paul entrusted the gospel"
                    "stem": rec.get("stem"), "mood": rec.get("mood"), "person": rec.get("person"),
                    "grammatical_voice": rec.get("voice"), "negated": bool(rec.get("negated")),
                    "tense": rec.get("tense"), "time": when,
                    "clauses": [x["id"]],
                    "reading": "lifted from the clause: two judges, every end checked",
                    "source": "verb-statements"}
        if voice[0] == "speaker":
            row["claimed_by"] = voice[1]
            st["in a speaker's words"] += 1
        elif voice[0] == "held":
            # in speech, but whose cannot be said: never shown as the narrator's.
            # Kept in the store, marked, so speaker_credit.py still sees its
            # clauses; the server and the claim export skip a held row
            row["held"] = voice[1]
            st[f"held: {voice[1]}"] += 1
        # WHO THE "I" IS (the committee's scholar, second sitting): a first-
        # person verb with no speaker on record went out in the narrator's
        # voice (45, 17 with God as subject: Heb 5:5 "God begot Jesus", Mal
        # 1:3). The narrator is an "I" only in the letters and the memoirs,
        # and even there not when the "I" is God quoted
        person = str(rec.get("person") or "")
        if "held" not in row and person.startswith("first") and voice[0] != "speaker" \
                and not (book in I_NARRATOR and x["subject"] not in DIVINE):
            row["held"] = "first person with no speaker on record: the narrator is not the 'I'"
            st["held: first person, no speaker on record"] += 1
        # ...AND THE "YOU" (the committee's third sitting, D1; ruled "all as
        # recommended"): a second-person verb with no speaker on record is
        # someone addressing someone -- Jer 20:7 "You deceived me" is
        # Jeremiah's complaint -- never the narrator's statement. The letters
        # and memoirs keep their exemption, as for the "I"
        if "held" not in row and person.startswith("second") and voice[0] != "speaker" \
                and not (book in I_NARRATOR and x["subject"] not in DIVINE):
            row["held"] = "second person with no speaker on record: someone is addressed, not narrated"
            st["held: second person, no speaker on record"] += 1
        # INSIDE THE BEREAN'S QUOTATION MARKS (D1): the structure layer had no
        # speaker on record, but the Berean's editors print the words as
        # speech -- Job 23:16 (Job), Isa 38:12 (Hezekiah's writing), John 3:16
        # (inside 3:10-21, as they mark it; D2(a): follow the marks).
        # Held, never credited: the marks say it is speech, not whose. A verse
        # with speech and narration both decides by where the verb's English
        # word stands (tools/meaning/quoted.py); where that cannot be told,
        # held as well ("better none than a wrong one")
        if "held" not in row and voice[0] != "speaker":
            side = quote_side(ref, plain)
            if side == "inside":
                row["held"] = "inside quoted speech (the Berean's quotation marks), speaker not on record"
                st["held: inside the Berean's quotation marks"] += 1
            elif side == "unknown":
                row["held"] = "a verse with speech and narration, and the verb's place in it could not be told"
                st["held: speech or narration, undecided"] += 1
        # A PSALM'S VOICE (2026-10-20: "the scroll decides" -- the heading
        # names the speaker, or none; never the narrator. The committee's
        # corrections are in docs/review/committee-2026-10-20/psalm-ruling.md).
        # Until that is built, EVERY psalm statement without a speaker on
        # record is held (D1(c); it had been only those whose end is David)
        if "held" not in row and book == "Psa" and voice[0] != "speaker":
            row["held"] = "a psalm's voice: who speaks is decided by its heading (to be built)"
            st["held: a psalm's voice"] += 1
        # BY ROW, where the form does not show the time (D3): Rom 2:16's
        # present form (κρίνει) is the final judgment, "on the day when God
        # will judge" -- not a past event
        if "held" not in row and (ref, x["subject"], x["object"]) in HELD_ROWS:
            row["held"] = HELD_ROWS[(ref, x["subject"], x["object"])]
            st["held: by row"] += 1
        if row.get("held") and described:
            described, read = None, None
        if read == "happened":
            row["modality_from"] = "reading"
            st["time read: happened (released as stated)"] += 1
        if described:
            row.update({"modality": described, "modality_from": "reading", "described": True,
                        "time": f"{when}; read as {described}"})
            st[f"time read: {described} (described, not asserted)"] += 1
        elif undecided and "held" not in row:
            row["held"] = f"{when}; waits for a reading of its time"
            st[f"held: {when}"] += 1
        out.append(row)
        st["written"] += 1
        st[f"family: {fam}"] += 1
    # TWO VERBS, ONE PAIR, THE SAME VERSES: one statement told with two verbs
    # ("Joab fought against and captured Rabbah"), one row (48 the validator
    # still flagged as copies, 2026-10-19)
    joined, order = {}, []
    for r in out:
        k = (r["src"], r["dst"], tuple(r["refs"]), r.get("claimed_by"), r.get("held"), r.get("modality"))
        if k in joined:
            j = joined[k]
            if r["label"] not in j["label"].split(" and "):
                j["label"] += " and " + r["label"]
                j["label_plain"] += " and " + r["label_plain"]
                j["inverse_label"] = j["inverse_label"].removesuffix(" by") + " and " + r["inverse_label"]
                j["verbs"] = j.get("verbs", [j["verb"]]) + [r["verb"]]
            j["clauses"] += r["clauses"]
            st["two verbs, one statement (joined)"] += 1
            continue
        joined[k] = r
        order.append(r)
    out = order
    if not voices:
        print("no out/sweep/statement-voices.jsonl yet: run tools/sweep/speaker_credit.py, then this again")
    # the hand-built relations a lifted statement evidences, for the export
    (ROOT / "ontology" / "relations" / "statement-evidence.json").write_text(
        json.dumps({"_what": "hand-built relations a clause statement evidences: the clause is written as the "
                             "claim's claim:evidencedBy (plan 2.17 step 3); tools/meaning/write_statements.py",
                    "evidence": evidence}, ensure_ascii=False, indent=0), encoding="utf-8")
    DEST.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    print(json.dumps(dict(st.most_common()), indent=1))
    for r in out:
        if r["refs"][0] in ("John 3:16", "John 21:15", "Gen 29:18", "Luke 1:30"):
            print(r["src"], r["label"], r["dst"], "|", r["inverse_label"], "|", r["family"], r["refs"])


if __name__ == "__main__":
    main()
