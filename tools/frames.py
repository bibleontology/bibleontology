"""Events as TUPLES, from MACULA's own predicate-argument annotation.

2026-09-09, defining the unit and then its representation: generally, what can
be labelled is thought of as an event ("Jesus fed the 5000", "Jesus healed the
blind man"), and such events can be described with a tuple.

Both of those labels are **agent-predicate-patient**, and that is a tuple this
corpus can fill without a model, because MACULA carries a PropBank-style
`frame` attribute on the verb pointing at the words that fill each slot:

    frame="A0:n40001002001 A1:n40001002004"

## Why this exists when `out/events.jsonl.gz` already has participants

Because that layer is nearly empty at the slot level. Of its 26,018 events only
**2,390 (9.2%)** carry both an agent and an object, which caps every downstream
test at 9% of the corpus no matter how good the test is. Its participants were
read from the `role` attribute; `frame` is a separate and denser annotation
that this project had never read.

## What each label means, and the one that is easy to get wrong

    A0   the agent -- who does it
    A1   the patient -- what it is done to
    A2   a third argument: beneficiary, instrument, goal
    AA   the CAUSER in a causative. Hebrew's hiphil "he caused X to eat" puts
         the causer in AA and leaves the eater in A0, so reading AA as a plain
         agent inverts who did what.

A slot may point at **several** words (`A1:n...014;n...017`), which is a
compound argument, not two arguments.

## Licence

MACULA is CC BY 4.0 and is credited. Its files also carry `sdbh`, `lexdomain`,
`coredomain`, `domain` and `ln`, which are UBS semantic-domain annotations held
under permission rather than an open licence. **This module reads none of them**
and lists them here so the omission is visibly deliberate rather than accidental.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import unicodedata as ud
import xml.etree.ElementTree as ET

import provenance

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAC = ROOT / "data" / "raw" / "macula"
DEST = ROOT / "out" / "frames.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

# Never read: sdbh, lexdomain, coredomain, domain, ln  (UBS, permission-based)
WORD = re.compile(r"<w\s([^>]*?)/?>", re.S)
ATTR = re.compile(r'([\w:.-]+)="([^"]*)"', re.S)
SLOT = {"A0": "agent", "A1": "patient", "A2": "arg2", "AA": "causer",
        "AA2": "causer2"}

# ---------------------------------------------------------------- polarity
# Without these, `he sits(man)` is what we stored for Psalm 1:1 -- a verse
# whose entire point is that he does NOT sit. 29% of tuples sat inside a
# negated verse and none of them said so. Found 2026-09-11.
#
# These are LEMMAS, not surface forms. Matching surface forms fails on the
# pointing; matching lemmas against a hand-typed string has failed five times
# in this project on Unicode normalisation alone, so the run prints an attach
# count and a per-particle loose count -- both would collapse to zero if any
# string here were mis-normalised, which is the cheapest possible alarm.
NEG_H = {
    "לֹא",          # plain indicative negation
    "אַל",          # negation of a volitive -- prohibition, "do not"
    "אֵין",         # existential "there is not"; often a verbless clause
    "בַּל",         # poetic, mostly Psalms/Proverbs
    "בְּלִי",       # "without"
    "לְבִלְתִּי",   # negates an infinitive, "so as not to"
    "אַיִן",        # by-form of אֵין
}
NEG_G = {
    "οὐ", "οὐκ", "οὐχ", "οὐχί",   # factual negation
    "μή", "μηδέ", "μήτε",          # volitive/conditional negation
    "οὐδέ", "οὔτε",                # "and not", "neither"
    "οὐδείς", "μηδείς",            # "no one" -- negates by its subject
    "μηδαμῶς", "οὐδαμῶς",
}

# SCOPE COMES FROM THE SYNTAX TREE, which lowfat already is:
# <wg class="cl" rule="ADV-PP-V-PP">. Three rules were tried, in this order,
# and the first two are wrong in ways only the corpus shows:
#
#   distance window     Psa 22:6 "I am a worm and NOT a man ... despised by
#                       the people" -- the לֹא reached past אִישׁ and negated
#                       `despised`, six morphemes away. 254 such reaches.
#   stop at a noun      Psa 103:10 "He has NOT dealt with us according to our
#                       sins" is ADV-PP-V-PP: the fronted prepositional phrase
#                       puts a noun between particle and verb, and stopping
#                       there loses the verse that started this work.
#   innermost clause    Mat 5:17's second οὐκ is not in a clause at all. It
#                       hangs on a coordination node lowfat names
#                       `notCLbutCL2CL` -- "not [clause] but [clause]" -- one
#                       level ABOVE the two clauses it governs, so the rule
#                       found nothing to mark.
#
# What works is the node the annotator actually attached the particle to,
# whatever its level, searched rightward. Psa 22:6's "not a man" is a verbless
# clause: no verb in scope, nothing marked, which is the correct outcome.
XMLID = "{http://www.w3.org/XML/1998/namespace}id"

# אַיִן is the existential "there is none" AND the tail of מֵאַיִן, "from
# where" -- Num 11:13 "WHERE can I get meat" was being read as a negation.
# The interrogative always carries the מִן prefix, so it is separable.
FROM = "מִן"

# -------------------------------------------------------------------- mood
# `take(Abraham, son)` in Gen 22:2 was stored in the same shape as a report
# that Abraham took him. The source says IMPERATIVE and we were dropping it.
#
# Both languages label the form themselves -- Hebrew in `type`, Greek in
# `mood` -- so nothing here is inferred from the morph string. An earlier
# count of "12,777 commands" came from reading morph position 3 as
# `in "vc"`, which silently swept in every infinitive CONSTRUCT (Vqc, 4,548
# of them alone). The real imperative count is 6,179. Read the label.
STANCE = {
    # asserted to have happened or to be the case
    "qatal": "report", "wayyiqtol": "report",
    # told to someone: do this
    "imperative": "command", "jussive": "command",
    # let me / let us -- the speaker's own volition
    "cohortative": "wish",
    # not yet the case: future, habitual, modal
    "yiqtol": "projection", "weqatal": "projection",
    # asserts nothing on its own; inherits from the clause it hangs in
    "participle active": "nonfinite", "participle passive": "nonfinite",
    "infinitive construct": "nonfinite", "infinitive absolute": "nonfinite",
}
GREEK_STANCE = {
    "imperative": "command", "optative": "wish", "subjunctive": "projection",
    "participle": "nonfinite", "infinitive": "nonfinite",
    # indicative splits on TENSE: future projects, everything else reports
    "indicative": "report",
}

# Polarity and mood together say something neither says alone. Hebrew marks
# two kinds of prohibition and they are not interchangeable:
#
#   לֹא + yiqtol    Exo 20:13 "You shall not murder"    permanent, legal
#   אַל + volitive  Psa 95:8  "Do not harden your hearts" immediate, this once
#
# CHECKED, not assumed: all ten of Exo 20:3-17 come back `absolute` and none
# `immediate`. That is the validation for this field -- a rule that split the
# Decalogue across both buckets would be wrong on the clearest case there is.
#
# LIMIT: 123 of 3,918 prohibitions (3.1%) sit on a Greek future indicative.
# Most are genuine legal prohibitions ("You shall not murder" quoted in
# Greek), but a negative PURPOSE clause lands here too -- Mrk 14:2 "not during
# the feast, or there may be a riot" is μή + future, marked a prohibition when
# it is a fear. Separating them needs the conjunction (μήποτε, ἵνα μή), which
# this layer does not read.
IMMEDIATE = {"אַל", "μή", "μηδέ", "μήτε"}

BOOK = {
    "GEN": "Gen", "EXO": "Exo", "LEV": "Lev", "NUM": "Num", "DEU": "Deu",
    "JOS": "Jos", "JDG": "Jdg", "RUT": "Rut", "1SA": "1Sa", "2SA": "2Sa",
    "1KI": "1Ki", "2KI": "2Ki", "1CH": "1Ch", "2CH": "2Ch", "EZR": "Ezr",
    "NEH": "Neh", "EST": "Est", "JOB": "Job", "PSA": "Psa", "PRO": "Pro",
    "ECC": "Ecc", "SNG": "Sng", "ISA": "Isa", "JER": "Jer", "LAM": "Lam",
    "EZK": "Ezk", "DAN": "Dan", "HOS": "Hos", "JOL": "Jol", "AMO": "Amo",
    "OBA": "Oba", "JON": "Jon", "MIC": "Mic", "NAM": "Nam", "HAB": "Hab",
    "ZEP": "Zep", "HAG": "Hag", "ZEC": "Zec", "MAL": "Mal",
    "MAT": "Mat", "MRK": "Mrk", "LUK": "Luk", "JHN": "Jhn", "ACT": "Act",
    "ROM": "Rom", "1CO": "1Co", "2CO": "2Co", "GAL": "Gal", "EPH": "Eph",
    "PHP": "Php", "COL": "Col", "1TH": "1Th", "2TH": "2Th", "1TI": "1Ti",
    "2TI": "2Ti", "TIT": "Tit", "PHM": "Phm", "HEB": "Heb", "JAS": "Jas",
    "1PE": "1Pe", "2PE": "2Pe", "1JN": "1Jn", "2JN": "2Jn", "3JN": "3Jn",
    "JUD": "Jud", "REV": "Rev",
}
REF = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)")


def norm_ref(raw):
    """'GEN 1:1!2' -> 'Gen.1.1'. The !n is the word index and is dropped."""
    m = REF.match(str(raw or ""))
    if not m:
        return None
    b = BOOK.get(m.group(1))
    return f"{b}.{int(m.group(2))}.{int(m.group(3))}" if b else None


def words_of(text):
    """xml:id -> the few attributes this module is allowed to use."""
    out = {}
    for m in WORD.finditer(text):
        a = dict(ATTR.findall(m.group(1)))
        wid = a.get("xml:id")
        if wid:
            out[wid] = a
    return out


def is_verb(a):
    return (a.get("class") or a.get("pos")) == "verb"


def nfc(s):
    return ud.normalize("NFC", s or "")


# Pronouns that fill a frame slot and name nobody. NFC, because a hand-typed
# Hebrew literal does not byte-match MACULA's -- see compare.py for the full
# account of a bug that cost six sessions.
PRONOUN = {nfc(x) for x in (
    "הוּא", "הִיא", "הֵם", "הֵמָּה", "הֵנָּה", "אֲנִי", "אָנֹכִי",
    "אֲנַחְנוּ", "אַתָּה", "אַתְּ", "אַתֶּם", "זֶה", "זֹאת", "אֵלֶּה",
    "αὐτός", "ἐγώ", "σύ", "ἡμεῖς", "ὑμεῖς", "οὗτος", "ἐκεῖνος",
)}
# A referent is a THING. Excluding verbs was necessary in compare.py, where a
# participantref landed on δίδωμι as the referent of "they".
NOMINAL = {"noun", "name", "adj", "adjective"}


def antecedent(w, glob_lab):
    """Who a pronoun refers to, from MACULA's own annotation.

    `participantref` and `referent` name the word; `subjref` does the same for
    a verb's subject. Resolved against the GLOBAL index because these pointers
    cross files as freely as they cross verses.
    """
    for field in ("participantref", "referent", "subjref"):
        raw = w.get(field)
        if not raw:
            continue
        for one in raw.replace(";", " ").split():
            one = one.strip()
            if not one:
                continue
            got = glob_lab.get(one) or glob_lab.get("o" + one) \
                or glob_lab.get("n" + one)
            if got and got[1] in NOMINAL and nfc(got[0]) not in PRONOUN:
                return got[0]
    return None


def mood_of(at):
    """(form, stance) for a verb, read off the source's own label.

    `form` is verbatim from MACULA -- 'qatal', 'imperative', 'subjunctive' --
    so nothing is lost to our coarser grouping. `stance` is this project's
    mapping and is the thing downstream code should read.
    """
    if at.get("lang") == "G" or (at.get("xml:id") or "").startswith("n"):
        mood = (at.get("mood") or "").strip()
        if not mood:
            return None, None
        stance = GREEK_STANCE.get(mood)
        # A future indicative projects; it does not report. Greek keeps mood
        # and tense in separate attributes, so this is the one place the two
        # have to be read together.
        if mood == "indicative" and (at.get("tense") or "") == "future":
            stance = "projection"
        return mood, stance
    form = (at.get("type") or "").strip()
    return (form or None), STANCE.get(form)


def negations(path, tally=None):
    """xml:id of each negated verb -> the lemma that negates it.

    Scope is read off lowfat's syntax tree: a negator claims the first
    unclaimed verb after it inside the node it is attached to, never crossing
    into the next verse. All three verbs of Psalm 1:1 get their own particle;
    none of Genesis 22:2's four get one.

    Unattached negators are counted, not silently dropped, and that bucket is
    supposed to be large: a verbless clause ("there is no God", "not a man")
    has no verb to mark, and marking nothing there is the correct outcome.

    KNOWN LIMITS, both of which mark a verb the verse does not actually deny:

    - Constituent negation. Deu 9:6 "it is NOT because of your righteousness
      that the LORD is giving you this land" marks `give`. The giving happens;
      what is denied is the reason. 1 of 14 in a hand-checked sample.
    - Rhetorical questions. Jdg 11:24 "Do you NOT possess whatever Chemosh
      grants you" is grammatically negative and asserts the positive.

    Both are recorded as the grammar has them. This layer claims to find the
    particle and its verb, not to resolve what the sentence implies.
    """
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return {}
    parent = {c: p for p in root.iter() for c in p}

    out = {}
    prev = None
    for w in root.iter("w"):
        lem = (w.get("lemma") or "").strip()
        if lem not in NEG_H and lem not in NEG_G:
            prev = w
            continue
        if lem == "אַיִן" and prev is not None and \
                (prev.get("lemma") or "") == FROM:
            prev = w
            continue                       # מֵאַיִן, "from where", not a negator
        prev = w
        # SCOPE IS THE NEGATOR'S OWN PARENT NODE, not the nearest clause.
        # A negator usually hangs inside the clause it negates, but "not X but
        # Y" hangs it one level ABOVE two sibling clauses -- lowfat even names
        # the rule `notCLbutCL2CL`. Mat 5:17's second οὐκ is there, and an
        # innermost-clause rule finds no clause at all and marks nothing.
        # Taking whatever node the annotator attached it to handles both,
        # and negation scopes rightward so the first verb after it is the one.
        scope = parent.get(w)
        here = norm_ref(w.get("ref"))
        hit = None
        if scope is not None:
            after = False
            for b in scope.iter("w"):
                if b is w:
                    after = True
                    continue
                if not after:
                    continue
                if norm_ref(b.get("ref")) != here:
                    break                  # never reach into the next verse
                if (b.get("class") or b.get("pos")) == "verb" \
                        and b.get(XMLID) not in out:
                    hit = b
                    break
        if tally is not None:
            # `hit is not None`, NEVER `if hit`. ElementTree defines an
            # element's truth value as len(element) > 0, so a childless <w/>
            # -- which every word is -- is FALSY. The mark below used the
            # identity test and was right; this tally used the truth test and
            # reported 0 attached while 7,544 tuples carried a negator.
            got = hit is not None
            tally["negators"] += 1
            tally["attached" if got else "unattached"] += 1
            if not got:
                tally[f"loose:{lem}"] += 1
        if hit is not None:
            out[hit.get(XMLID)] = lem
    return out


def label(a):
    """A readable filler: the lemma, falling back to the gloss."""
    return (a.get("lemma") or a.get("stronglemma") or a.get("english")
            or a.get("gloss") or "").strip() or None


def gloss_of(a):
    g = (a.get("gloss") or a.get("english") or "").strip()
    return g.replace(".", " ") or None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="files, for a smoke run")
    a = ap.parse_args()

    files = sorted(MAC.glob("*/*.xml"))
    if a.limit:
        files = files[:a.limit]
    print(f"macula files: {len(files)}")

    # A frame slot may point OUT OF ITS OWN FILE. Exodus 20:13, "You shall not
    # murder", carries frame="A0:020190250042;" -- a word in Exodus 19:25, the
    # previous chapter and a different file. Resolving pointers against the
    # current file only, the slot failed, no slot filled, and the whole tuple
    # was dropped: the sixth commandment had no event record at all.
    # One cheap pre-pass of id -> label makes every pointer resolvable.
    glob_lab = {}
    for i, p in enumerate(files):
        if i % 300 == 0:
            print(f"  index {i}/{len(files)} ...", flush=True)
        for m in WORD.finditer(p.read_text(encoding="utf-8")):
            at = dict(ATTR.findall(m.group(1)))
            wid = at.get("xml:id")
            if wid:
                lab = label(at)
                if lab:
                    glob_lab[wid] = (lab, (at.get("class")
                                           or at.get("pos") or ""))
    print(f"  indexed word ids: {len(glob_lab):,}")

    rows = []
    slots = collections.Counter()
    neg = collections.Counter()
    unresolved = 0
    crossfile = 0
    resolved = 0
    for i, p in enumerate(files):
        if i % 200 == 0:
            print(f"  {i}/{len(files)} ...", flush=True)
        text = p.read_text(encoding="utf-8")
        if "frame=" not in text:
            continue
        ws = words_of(text)
        negated = negations(p, tally=neg)
        for wid, at in ws.items():
            fr = at.get("frame")
            if not fr:
                continue
            ref = norm_ref(at.get("ref"))
            if not ref:
                continue
            args = {}
            named = {}
            for part in fr.split():
                if ":" not in part:
                    continue
                tag, ids = part.split(":", 1)
                name = SLOT.get(tag)
                if not name:
                    continue
                fills = []
                for one in ids.split(";"):
                    one = one.strip()
                    if not one:
                        continue          # Hebrew slots end with a stray ';'
                    # HEBREW POINTERS DROP THE LEADING 'o' OF THE xml:id.
                    # frame="A0:010010010031;" against xml:id="o010010010031".
                    # Missing this cost the entire Old Testament on the first
                    # full run: 27 books out, all Greek, 211,945 pointers
                    # unresolved and no row emitted because no slot filled.
                    w = ws.get(one) or ws.get("o" + one) or ws.get("n" + one)
                    if w is not None:
                        lab = label(w)
                    else:
                        # Falls out of this file -- see the pre-pass above.
                        hit = (glob_lab.get(one) or glob_lab.get("o" + one)
                               or glob_lab.get("n" + one))
                        lab = hit[0] if hit else None
                        if lab:
                            crossfile += 1
                        else:
                            unresolved += 1
                            continue
                    if lab:
                        fills.append(lab)
                        # 18,650 slots said "he", "they", "I" and named
                        # nobody -- 19.1% of tuples had at least one. MACULA
                        # carries the answer on the word itself, and 58.8% of
                        # its coreference pointers cross a verse boundary,
                        # which is why nothing inside a verse could ever fix
                        # this. Kept SEPARATE from the literal filler: the
                        # text says "he" and that is not edited away.
                        if w is not None and nfc(lab) in PRONOUN:
                            who = antecedent(w, glob_lab)
                            if who:
                                named.setdefault(name, [])
                                if who not in named[name]:
                                    named[name].append(who)
                                resolved += 1
                if fills:
                    args[name] = fills
                    slots[name] += 1
            if not args:
                continue
            row = {
                "ref": ref,
                "id": wid,
                "lang": "hebrew" if wid.startswith("o") else "greek",
                "lemma": label(at),
                "gloss": gloss_of(at),
                **args,
            }
            # Only NEGATIVE is stamped. Leaving the other 71% unmarked would
            # mean "we did not look"; stamping polarity on every row says we
            # looked and found none, which is the claim actually supported.
            row["polarity"] = "negative" if wid in negated else "positive"
            if wid in negated:
                row["negator"] = negated[wid]
            if named:
                row["named"] = named
            form, stance = mood_of(at)
            if form:
                row["form"] = form
            if stance:
                row["stance"] = stance
            # A negated command is a PROHIBITION, and Hebrew has two of them
            # that mean different things. See IMMEDIATE.
            if wid in negated and stance in ("command", "projection"):
                row["prohibition"] = ("immediate"
                                      if negated[wid] in IMMEDIATE
                                      else "absolute")
            rows.append(row)

    n = len(rows)
    print(f"\npredicate-argument tuples: {n}")
    print(f"  slot pointers resolved ACROSS files: {crossfile:,}")
    print(f"  PRONOUN slots given a name: {resolved:,}")
    print(f"  unresolved slot pointers: {unresolved}")
    print("  slots filled:", dict(slots.most_common()))

    full = [r for r in rows if r.get("agent") and r.get("patient")]
    print(f"\nAGENT + PATIENT (a complete tuple): {len(full)}"
          f"  ({100*len(full)/n:.1f}% of tuples)")
    print("  the layer this replaces had 2,390 such events, from 26,018")
    print(f"  lift: {len(full)/2390:.2f}x")

    byb = collections.Counter(r["ref"].split(".")[0] for r in rows)
    print(f"\nbooks covered: {len(byb)}")
    print("  thinnest:", dict(sorted(byb.items(), key=lambda kv: kv[1])[:6]))

    print("\nSAMPLE -- read these as Doug's labels")
    seen = 0
    for r in rows:
        if r.get("agent") and r.get("patient") and r.get("gloss"):
            print(f"  {r['ref']:<11} ({', '.join(r['agent'])} | {r['gloss']} "
                  f"| {', '.join(r['patient'])})")
            seen += 1
            if seen >= 10:
                break

    # ---- polarity ---------------------------------------------------------
    nneg = sum(1 for r in rows if r["polarity"] == "negative")
    print(f"\nPOLARITY")
    print(f"  negators found            {neg['negators']:>7,}")
    print(f"    attached to a verb      {neg['attached']:>7,}  "
          f"({100*neg['attached']/max(neg['negators'],1):.1f}%)")
    print(f"    no verb in reach        {neg['unattached']:>7,}  "
          f"(verbless clauses -- 'there is no ...')")
    print(f"  tuples marked NEGATIVE    {nneg:>7,}  ({100*nneg/n:.1f}% of {n:,})")
    print("  loosest particles (expected: the existentials):")
    for k, v in neg.most_common():
        if k.startswith("loose:"):
            print(f"    {k[6:]:<12}{v:>6,}")

    # The six verses that exposed the bug. If any comes back positive the
    # scoping rule is wrong, and this is the cheapest place to find out.
    CHECK = {"Psa.1.1": 3, "Job.1.22": 2, "Psa.103.10": 2, "Isa.53.7": 2,
             "Mat.5.17": 2, "Gen.2.17": 1, "Exo.20.13": 1, "Psa.23.4": 1}
    print("\n  REGRESSION -- the verses that were stored backwards:")
    byref = collections.defaultdict(list)
    for r in rows:
        byref[r["ref"]].append(r)
    for ref, want in CHECK.items():
        got = [r for r in byref.get(ref, []) if r["polarity"] == "negative"]
        mark = "ok " if len(got) >= want else "MISS"
        shown = ", ".join(f"{r['gloss']}[{r['negator']}]" for r in got) or "-"
        print(f"    {mark} {ref:<12} {len(got)}/{want}  {shown[:60]}")

    # ---- mood -------------------------------------------------------------
    st = collections.Counter(r.get("stance") or "(none)" for r in rows)
    print("\nMOOD -- stance of each tuple")
    for k, v in st.most_common():
        print(f"  {k:<14}{v:>7,}  ({100*v/n:>4.1f}%)")
    cmds = sum(v for k, v in st.items() if k in ("command", "wish"))
    print(f"  commands + wishes: {cmds:,} tuples that tell someone to do "
          f"something, previously indistinguishable from reports")

    pro = collections.Counter(r["prohibition"] for r in rows
                              if r.get("prohibition"))
    print("\n  PROHIBITIONS (polarity x mood -- neither field alone says this)")
    for k, v in pro.most_common():
        print(f"    {k:<12}{v:>6,}")

    MOOD_CHECK = {
        "Exo.20.13": ("command-ish", "absolute"),   # לֹא + yiqtol, legal
        "Psa.95.8":  ("command", "immediate"),      # אַל + jussive, this once
        "Gen.22.2":  ("command", None),             # take / go / offer
        "Gen.1.3":   ("command", None),             # jussive "let there be"
        "Jos.1.9":   ("command", "immediate"),      # "do not be afraid"
        # Mic 6:8 is NOT a command and the first draft of this test said it
        # was. "to act justly, to love mercy, to walk humbly" are infinitive
        # constructs -- the CONTENT of what the LORD requires, not an
        # imperative addressed to anyone. The old morph rule called them
        # imperatives because it read position 3 as `in "vc"` and Vqc is the
        # infinitive construct. The label was right and the shortcut was wrong.
        "Mic.6.8":   ("nonfinite", None),
        "Deu.6.5":   ("projection", None),          # weqatal "you shall love"
        "Jhn.11.35": ("report", None),              # "Jesus wept"
    }
    print("\n  REGRESSION -- a command must not look like a report:")
    for ref, (want_st, want_pro) in MOOD_CHECK.items():
        got = byref.get(ref, [])
        sts = {r.get("stance") for r in got if r.get("stance")}
        pros = {r.get("prohibition") for r in got if r.get("prohibition")}
        ok = (want_st in sts or (want_st == "command-ish" and sts & {
            "command", "projection"}))
        if want_pro:
            ok = ok and want_pro in pros
        forms = ", ".join(sorted({f"{r.get('form')}" for r in got
                                  if r.get("form")}))
        print(f"    {'ok ' if ok else 'MISS'} {ref:<12}"
              f"{'/'.join(sorted(sts)) or '-':<26}"
              f"{'/'.join(sorted(pros)) or '-':<11}{forms[:34]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            # A build stamp, so anything reading this can tell whether it is
            # still true of its inputs. 33 of 33 layers lacked one until
            # 2026-09-11, and on that day this file changed under all of them.
            **provenance.stamp(__file__, inputs=["data/raw/macula/*/*.xml"]),
            "_source": CREDIT,
            "_note": "Predicate-argument tuples from MACULA's frame attribute "
                     "(PropBank-style A0/A1/A2/AA). AA is the CAUSER of a "
                     "causative and is not the agent. UBS semantic-domain "
                     "fields (sdbh, lexdomain, coredomain, domain, ln) are "
                     "deliberately not read.",
        }, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({n} tuples)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
