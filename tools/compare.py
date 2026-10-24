"""Comparisons as VEHICLE and TENOR, from lowfat's syntax tree.

**It records comparisons, not similes, and the difference is measured.** Every
row is a real comparative construction -- the particle is doing comparative
work in all of them -- but only about two thirds are figures of speech. In a
hand-checked sample of 14, four were comparative without being pictures:

    Exo 7:6    "did just AS the LORD had commanded"    conformity
    Exo 16:21  "gathered AS MUCH AS was needed"        quantity
    Gen 44:7   "do SUCH a thing"  (כַּדָּבָר הַזֶּה)   idiom
    Dan 3:29   "anything LIKE this"                    deictic

The cheapest of these is separable and is: a vehicle made only of pronouns and
demonstratives is never a picture, and those rows carry `figurative: false`.
Conformity and quantity are not separable here and are left in, so a consumer
wanting figures should expect roughly a quarter of rows not to be one.

2026-09-11, on auditing the sub-sentence layer: Psa 103:13 'As a father has
compassion ... so the LORD' is stored as two unrelated `has compassion` frames
with different agents. Which term is the picture and which is the point is not
recorded -- and that is the whole content of a simile.

That is right. `has_compassion(father)` and `has_compassion(YHWH)` sitting side by side
say the two happened. The verse says one **illuminates** the other, and which
way round is not reversible: the psalm explains God by way of fathers, not
fathers by way of God.

## The terms

    VEHICLE   the picture -- a deer, a tree, sheep, a father
    TENOR     the point   -- my soul, the man, we, the LORD

## What the tree gives us

lowfat marks both shapes explicitly, so neither is guessed:

    PrepNp    כְּ + a noun phrase           Psa 1:3   "like a tree"
    PrepCL    כְּ + a whole clause          Psa 103:13 "as a father has
    ppCL                                              compassion on his
                                                      children"

and where the tenor gets its own clause, that clause opens with כֵּן, "so",
and lowfat joins the pair under one parent (`ClCl`). Psalm 42:2 is the
textbook case and comes out of the tree without any rule of ours.

## The one that is not a comparison at all

**כְּ + infinitive construct is usually temporal.** Gen 12:14 "and it came to
pass WHEN Abram came into Egypt" is כְּ + בּוֹא, structurally identical to
Psalm 103:13's כְּרַחֵם אָב, "as a father has compassion". Same pp/PrepCL over
cl/V-S-PP, same infinitive.

Of 268 such cases, 121 sit under the וַיְהִי narrative time formula and most
of the remainder are plainly temporal too. The ones that are comparisons ECHO
THE VERB -- the main clause repeats the infinitive's own lemma -- and that is
32 cases including Psalm 103:13 itself, Num 22:4 and Gen 33:10. So an
infinitive is kept only on the echo and dropped otherwise: 238 dropped, 32
kept. The trade is about 41 poetic cases we cannot separate, against not
inventing a comparison in every "and it came to pass when" in the narrative
books.

## Where the tenor is not in the verse: one rule that failed, one that works

2,251 of 3,652 comparisons have no tenor inside their own verse. Psalm 1:3's
"like a tree" compares the man of verses 1-2, who is not named in verse 3 at
all; the subject is carried by the verb alone.

### The rule that failed: proximity  (`--context`, kept, off)

Nearest clause subject in a preceding verse, stopping at a paragraph break.
Recovered 1,575 of 2,251 and a hand-check of ten put **two** right:

    Jer 17:6  "like a shrub in the desert" -> גֶּבֶר, "the man who trusts in
              mankind" (17:5)                                      CORRECT
    Psa 1:3   "like a tree"                -> חֵפֶץ "delight" (1:2)
    Isa 13:8  "writhe like a woman in labor" -> "all hands" (13:7)
    Lev 25:50 "like the days of a hired hand" -> "uncle" (25:49)
    Psa 51:3                               -> "Nathan", out of the heading

Tightening it did nothing: one verse back, noun subjects, figurative only,
grammatical agreement -- volume fell 1,575 -> 876 and precision did not move.
**A proximity rule cannot be narrowed into a topic rule.** Jeremiah 17:6 works
because its unit announces its topic, not because verse 5 is adjacent.

### The rule that works: MACULA's own coreference  (default)

A finite verb carries `subjref` naming the word its subject refers to, and a
pronoun carries `participantref`. **58.8% of the corpus's 126,151 coreference
pointers cross a verse boundary**, and this project had never read them for
anything.

    PSA 1:3!1  'he.is'  --subjref-->  PSA 1:1!2  אִישׁ  'person'

Two verses back, past the intervening subject that defeated proximity, and it
is correct. Nothing is inferred; lowfat states it.

    tenor coverage    1,401 -> 2,915 of 3,652   (38.4% -> 79.8%)
    from coreference  1,514, of which 1,046 leave the verse
                      (864 elsewhere in the chapter, 182 in another chapter)

Hand-checked twenty across two samples, roughly **fifteen to sixteen right**,
against two in ten for proximity:

    Psa 109:23  "shaken off like a locust"  -> דָּוִד, from the superscription
    Job 29:25   "I dwelt as a king"         -> אִיּוֹב
    Ezk 22:22   "as silver is melted"       -> בַּיִת, the house of Israel
    Ezk 38:9    "advancing like a storm"    -> גּוֹג
    Gen 27:4    "a dish that I love"        -> עֵשָׂו.  WRONG, it is Isaac.

A tenor is a THING, so targets are filtered to nominals: Jhn 17:16 first came
back with `δίδωμι` because a participantref may land on any word, and the
referent of "they" is not a verb.

Every derived tenor carries `tenor_by: "subjref"` and `tenor_from`, so a
consumer can always separate what the verse says from what was resolved.

## Licence

MACULA is CC BY 4.0 and is credited. Its UBS semantic-domain fields (sdbh,
lexdomain, coredomain, domain, ln) are held under permission rather than an
open licence and this module reads none of them.
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
DEST = ROOT / "out" / "comparisons.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

# Never read: sdbh, lexdomain, coredomain, domain, ln  (UBS, permission-based)

# EVERY HEBREW LEMMA COMPARISON IN THIS PROJECT GOES THROUGH nfc().
#
# This bug has now cost six separate sessions. MACULA writes כְּ as
#
#     05DB kaf   05BC dagesh   05B0 sheva
#
# and a hand-typed כְּ comes out of the editor as
#
#     05DB kaf   05B0 sheva    05BC dagesh
#
# Canonically equivalent, byte-different, and `==` says False. The first run
# of this module found 825 similes and not one of them Hebrew -- in a corpus
# where the Psalms are the densest source of similes there is. NFC puts the
# combining marks in canonical order on both sides and the comparison works.
#
# Only letters carrying BOTH a dagesh and a vowel are exposed, which is why
# לֹא and אַל in frames.py happened to work and כְּ and בְּ do not. That is
# luck, not correctness, so normalise everywhere rather than where it bites.
def nfc(s):
    return ud.normalize("NFC", s or "")


# The comparison particles. כְּ is a PREFIX and a separate <w> in lowfat, so
# it is reachable as a lemma like any other word.
VEHICLE_MARK = {nfc(x) for x in (
    "כְּ",          # "like", "as" -- by far the commonest
    "כְּמוֹ",       # the free-standing form
    "ὡς", "ὥσπερ", "καθώς", "καθάπερ", "ὁμοίως", "ὅμοιος", "ὡσεί",
)}
TENOR_MARK = {nfc(x) for x in ("כֵּן", "οὕτως", "οὕτω")}

# כְּ + infinitive construct is "when", not "like". See the module docstring.
TEMPORAL_FORMS = {"infinitive construct", "infinitive absolute"}

XMLID = "{http://www.w3.org/XML/1998/namespace}id"
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
WORD = re.compile(r"<w\s([^>]*?)/?>", re.S)
ATTR = re.compile(r'([\w:.-]+)="([^"]*)"', re.S)
CONTENT = {"noun", "verb", "adj", "adjective", "name", "pron"}
# What a tenor may be. Deliberately excludes "verb".
NOMINAL = {"noun", "name", "adj", "adjective", "pron"}


def norm_ref(raw):
    m = REF.match(str(raw or ""))
    if not m:
        return None
    b = BOOK.get(m.group(1))
    return f"{b}.{int(m.group(2))}.{int(m.group(3))}" if b else None


def cls(w):
    return (w.get("class") or w.get("pos") or "").lower()


def heads(node, skip=(), skip_ids=frozenset()):
    """Content lemmas directly under `node`, in order, minus what is skipped."""
    out = []
    for w in node.iter("w"):
        if w in skip or id(w) in skip_ids:
            continue
        if cls(w) in CONTENT:
            lab = nfc((w.get("lemma") or w.get("gloss") or "").strip())
            if lab and lab not in out:
                out.append(lab)
    return out


def subject_of(clause, exclude=frozenset()):
    """Lemmas the tree marks as the subject of this clause, if any.

    lowfat puts role="s" on the subject phrase, or on the word itself when the
    subject is a single word. An implicit subject carried only by the verb's
    inflection has neither, and returns empty -- which is the honest answer.

    `exclude` holds the ids of the vehicle's own words. Without it, Psalm
    103:13 returns אָב: its clause is PP-V-S-PP, the vehicle phrase comes
    FIRST, and a plain walk finds the father's subject before the LORD's. The
    tenor would then be dropped for duplicating the vehicle, losing the one
    verse that prompted this module.
    """
    out = []
    for n in clause.iter():
        if n.get("role") != "s" or id(n) in exclude:
            continue
        if n.tag == "w":
            lab = nfc((n.get("lemma") or "").strip())
            if lab:
                out.append(lab)
        else:
            out.extend(x for x in heads(n, skip_ids=exclude))
        if out:
            return out
    return out


def find(path, tally, breaks=None, coref=None):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    parent = {c: p for p in root.iter() for c in p}
    words = list(root.iter("w"))
    forms = {}
    for w in words:
        forms[id(w)] = (w.get("type") or w.get("mood") or "").strip()

    out = []
    hosts = {}
    for w in words:
        lem = nfc((w.get("lemma") or "").strip())
        if lem not in VEHICLE_MARK:
            continue
        ref = norm_ref(w.get("ref"))
        if not ref:
            continue
        scope = parent.get(w)
        if scope is None:
            continue
        tally["particles"] += 1
        tally[f"particle:{lem}"] += 1

        inner = [x for x in scope.iter("w") if cls(x) == "verb"]
        # ids of every node in the vehicle phrase, <w> and <wg> alike,
        # so the tenor search cannot land back inside the picture
        inside = {id(x) for x in scope.iter()} | {id(scope)}
        outer = None
        node = scope
        while node in parent:
            node = parent[node]
            if node.tag == "wg" and node.get("class") == "cl":
                cand = [x for x in node.iter("w")
                        if cls(x) == "verb" and id(x) not in inside]
                if cand:
                    outer = cand[0]
                    break

        # TEMPORAL, NOT COMPARATIVE, and the two are structurally identical:
        #
        #   Gen 12:14   וַיְהִי כְּבוֹא אַבְרָם   "when Abram came"
        #   Psa 103:13  כְּרַחֵם אָב ... רִחַם     "as a father has compassion"
        #
        # both are pp/PrepCL over cl/V-S-PP with an infinitive construct. Of
        # 268 such cases, 121 sit under the וַיְהִי narrative time formula and
        # most of the rest are plainly temporal too ("when Esau heard, he
        # cried out"). The ones that are comparisons ECHO THE VERB: the main
        # clause repeats the infinitive's own lemma, 32 cases including
        # Psa 103:13, Num 22:4 and Gen 33:10.
        #
        # So an infinitive is kept only on the echo, and dropped otherwise.
        # That trades ~41 poetic cases we cannot separate for not inventing a
        # simile in every "and it came to pass when" in the narrative books.
        if inner and forms.get(id(inner[0])) in TEMPORAL_FORMS:
            echo = (outer is not None
                    and nfc(outer.get("lemma") or "")
                    == nfc(inner[0].get("lemma") or ""))
            if not echo:
                tally["temporal (when, not like)"] += 1
                continue
            tally["infinitive kept on verb echo"] += 1

        vehicle = heads(scope, skip={w})
        vclass = [cls(x) for x in scope.iter("w")
                  if x is not w and cls(x) in CONTENT]
        if not vehicle:
            tally["no vehicle"] += 1
            continue

        # The tenor. Two shapes, and the tree tells which:
        #  - a sibling clause opening with כֵּן / οὕτως -> its subject
        #  - otherwise the subject of the clause the כְּ-phrase sits in
        tenor, shape = [], "embedded"
        gp = parent.get(scope)
        if gp is not None:
            for sib in gp:
                if sib is scope:
                    continue
                first = next((x for x in sib.iter("w")), None)
                if first is not None and \
                        nfc((first.get("lemma") or "").strip()) in TENOR_MARK:
                    tenor, shape = subject_of(sib, inside), "correlative"
                    break
        if not tenor:
            node = scope
            while node is not None and not tenor:
                node = parent.get(node)
                if node is None:
                    break
                if node.tag == "wg" and node.get("class") == "cl":
                    tenor = [t for t in subject_of(node, inside)
                             if t not in vehicle]
                    break

        if tenor:
            tally["with tenor"] += 1
        else:
            tally["tenor not in verse"] += 1
        # A vehicle made only of pronouns and demonstratives is not a
        # picture of anything -- "such a thing", "anything like this". The
        # comparison is real; the figure is not.
        fig = any(c not in ("pron", "det", "art") for c in vclass)
        tally["figurative" if fig else "deictic (not a picture)"] += 1
        out.append({
            "ref": ref,
            "particle": lem,
            "shape": shape,
            "vehicle": vehicle[:6],
            "tenor": tenor[:6] or None,
            "figurative": fig,
        })
        # The verb whose subject is the tenor. Kept so coreference can be
        # followed after the fact without re-walking the tree.
        if outer is not None:
            hosts[len(out) - 1] = outer

    if coref is not None:
        resolve_coref(out, hosts, coref, tally)
    if breaks is not None:
        resolve_back(root, out, breaks, tally)
    return out


def resolve_coref(out, hosts, coref, tally):
    """Find the tenor by following MACULA's own coreference, not by proximity.

    The proximity rule below scored two in ten. This one asks the annotator
    instead: a finite verb carries `subjref` pointing at the word its subject
    refers to, and **58.8% of the corpus's 126,151 coreference pointers cross
    a verse boundary**. That is the mechanism the whole problem needed.

        PSA 1:3!1  'he.is'  --subjref-->  PSA 1:1!2  אִישׁ  'person'

    Two verses back, past the intervening subject that defeated proximity, and
    it is the correct answer. Nothing here infers it; lowfat states it.

    `hosts` maps a comparison row's index to the verb of the clause the
    comparison hangs in -- the verb whose subject IS the tenor.
    """
    for i, row in enumerate(out):
        if row["tenor"]:
            continue
        v = hosts.get(i)
        if v is None:
            continue
        got = []
        for field in ("subjref", "participantref"):
            raw = v.get(field)
            if not raw:
                continue
            for one in raw.replace(";", " ").split():
                one = one.strip()
                if not one:
                    continue
                hit = (coref.get(one) or coref.get("o" + one)
                       or coref.get("n" + one))
                # A TENOR IS A THING, NOT AN ACTION. Jhn 17:16 came back
                # with `δίδωμι` because a participantref can land on any
                # word; the referent of "they" is not a verb.
                if (hit and hit[1] and hit[1] not in row["vehicle"]
                        and hit[2] in NOMINAL):
                    got.append(hit)
            if got:
                break
        if got:
            row["tenor"] = [x[1] for x in got[:3]]
            row["tenor_from"] = got[0][0]
            row["tenor_by"] = "subjref"
            tally["tenor from coreference"] += 1
            if got[0][0] and got[0][0] != row["ref"]:
                tally["  of those, from another verse"] += 1
                b1, c1, _ = row["ref"].split(".")
                b2, c2, _ = got[0][0].split(".")
                tally["  ... and another chapter" if (b1, c1) != (b2, c2)
                      else "  ... same chapter"] += 1


def resolve_back(root, out, breaks, tally, window=6):
    """Find the tenor in the PRECEDING verses when it is not in this one.

    2,251 of 3,652 comparisons had no tenor inside their own verse, and that
    is not noise -- it is the shape of the text. Psalm 1:3's "like a tree"
    compares the man introduced in verse 1 and names nobody in verse 3; the
    subject is carried by the verb alone. Isaiah does the same for whole
    oracles.

    So: walk back verse by verse for the nearest clause subject, and STOP AT A
    PARAGRAPH BREAK. The break is the barrier because a subject on the far
    side of one belongs to a different unit -- reaching past it would attach
    Psalm 1's tree to whatever the preceding psalm happened to be about.

    This is the first thing in the sub-sentence work that leaves the verse,
    and the ceiling it lifts was measured before it was built.
    """
    order, seen = [], set()
    for w in root.iter("w"):
        r = norm_ref(w.get("ref"))
        if r and r not in seen:
            seen.add(r)
            order.append(r)
    idx = {r: i for i, r in enumerate(order)}

    subs = collections.defaultdict(list)
    for n in root.iter():
        if n.get("role") != "s":
            continue
        ws = [n] if n.tag == "w" else list(n.iter("w"))
        if not ws:
            continue
        r = norm_ref(ws[0].get("ref"))
        if not r:
            continue
        subs[r].extend([nfc(n.get("lemma") or "")] if n.tag == "w"
                       else heads(n))

    for row in out:
        if row["tenor"]:
            continue
        i = idx.get(row["ref"])
        if i is None:
            continue
        for j in range(i - 1, max(i - 1 - window, -1), -1):
            if order[j + 1] in breaks:
                tally["stopped at a paragraph break"] += 1
                break
            cand = [t for t in subs.get(order[j], [])
                    if t not in row["vehicle"]]
            if cand:
                row["tenor"] = cand[:3]
                row["tenor_from"] = order[j]
                row["tenor_back"] = i - j
                tally["tenor recovered from context"] += 1
                break


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--context", action="store_true",
                    help="FAILED proximity rule, kept for the record")
    ap.add_argument("--no-coref", dest="coref", action="store_false",
                    default=True,
                    help="do NOT resolve a missing tenor via MACULA subjref")
    a = ap.parse_args()

    breaks = None
    if a.context:
        breaks = set()
        p = ROOT / "out" / "paragraphs.jsonl.gz"
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    if not any(k.startswith("_") for k in d):
                        breaks.add(d["ref"])
        print(f"paragraph breaks as lookback barriers: {len(breaks):,}")

    files = sorted(MAC.glob("*/*.xml"))
    print(f"macula files: {len(files)}")

    coref = None
    if a.coref:
        # Global, because a subjref crosses files as well as verses -- the
        # same lesson the frame pointers taught this morning.
        coref = {}
        for i, p in enumerate(files):
            if i % 300 == 0:
                print(f"  index {i}/{len(files)} ...", flush=True)
            for m in WORD.finditer(p.read_text(encoding="utf-8")):
                at = dict(ATTR.findall(m.group(1)))
                wid = at.get("xml:id")
                if wid:
                    coref[wid] = (norm_ref(at.get("ref")),
                                  nfc((at.get("lemma") or "").strip()),
                                  (at.get("class") or at.get("pos") or ""))
        print(f"  indexed word ids: {len(coref):,}")
    rows = []
    tally = collections.Counter()
    for i, p in enumerate(files):
        if i % 200 == 0:
            print(f"  {i}/{len(files)} ...", flush=True)
        rows.extend(find(p, tally, breaks, coref))

    print(f"\ncomparisons: {len(rows):,}")
    for k, v in tally.most_common():
        print(f"  {k:<26}{v:>7,}")

    shape = collections.Counter(r["shape"] for r in rows)
    print("\nshape:", dict(shape))
    byb = collections.Counter(r["ref"].split(".")[0] for r in rows)
    print("\ndensest books (a simile count is a genre signal):")
    for k, v in byb.most_common(10):
        print(f"  {k:<6}{v:>5,}")

    # The examples given, plus the temporal case that must NOT appear.
    CHECK = {
        "Psa.42.2":   ("אַיָּל", "נֶפֶשׁ"),     # deer / my soul
        "Psa.103.13": ("אָב", "יהוה"),          # a father / the LORD
        "Psa.1.3":    ("עֵץ", None),            # a tree / (the man, v1)
        "Isa.53.6":   ("צֹאן", None),           # sheep / we
        "Psa.103.15": ("חָצִיר", None),         # grass / man
    }
    by = collections.defaultdict(list)
    for r in rows:
        by[r["ref"]].append(r)
    print("\nREGRESSION -- vehicle must be the picture, not the point:")
    for ref, (veh, ten) in CHECK.items():
        got = by.get(ref, [])
        vs = {x for r in got for x in r["vehicle"]}
        ts = {x for r in got for x in (r["tenor"] or [])}
        ok = veh in vs and (ten is None or ten in ts)
        print(f"  {'ok ' if ok else 'MISS'} {ref:<12}"
              f"vehicle={','.join(sorted(vs))[:34]:<36}"
              f"tenor={','.join(sorted(ts))[:24] or '-'}")

    print("\nNOT a simile -- these must be absent (כְּ + infinitive = 'when'):")
    for ref in ("Gen.12.14", "Gen.19.29", "Gen.39.13"):
        print(f"  {'ok ' if ref not in by else 'MISS'} {ref}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            # See tools/provenance.py -- staleness should be a query.
            **provenance.stamp(__file__,
                               inputs=["data/raw/macula/*/*.xml",
                                       "out/paragraphs.jsonl.gz"]),
            "_source": CREDIT,
            "_note": "Similes as vehicle (the picture) and tenor (the point), "
                     "from lowfat's PrepNp/PrepCL shapes. tenor is null when "
                     "the subject is not lexically present in the verse. "
                     "UBS semantic-domain fields are deliberately not read.",
        }, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(rows):,} comparisons)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
