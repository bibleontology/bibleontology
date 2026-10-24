"""Forms as CLAUSE SHAPES, composed — the unit the earlier pattern tools missed.

2026-09-12, in four corrections that each changed the design:

> make them node based if possible
> there is real value in matching the same events across the synoptics
> complete tuples at a minimum in form, not just random three words
> if the beatitudes were the only verses in the Bible in that form, the
> pattern would still be captured, as it is important for the collection
> it is a more complex structure of two subpatterns paired together

The last two broke the previous unit. `tools/formulaic.py` keys on a VERB with
argument slots, so it cannot see the Beatitudes at all:

    Mat 5:3   no frame recorded -- the clause is verbless
    Mat 5:4   "will be comforted", agent absent

`μακάριος` is an ADJECTIVE holding `role="p"` in a verbless clause, and
`tools/metaphor.py` explicitly discards adjectival predicates as "attribution,
not a figure". **The form fell between two layers because both were
verb-centric**, and so do "Woe to you, scribes", "Cursed be the man who" and
"Blessed is the man that walketh not".

## The unit

A clause's **shape**: its head predicate plus its role inventory, where the
predicate may be a verb, an adjective or a noun. 132,981 clauses carry one.

    p-s      7,588   verbless predication  -- Beatitude, metaphor
    o-v     12,808   transitive
    pp-s-v   9,087

## Composition, because a form is made of subpatterns

The form is a more complex structure of two subpatterns paired together. Tested
and true -- the declaration occurs WITHOUT the ground four times in five:

    'blessed' as a clause predicate      90 occurrences
      paired with a ground clause        19
      standing alone                     71   (79%)

So the declaration is a recognisable subpattern **because** it appears unpaired
-- his own argument from 2026-09-10: *"if there were only one kind of cat in
the world, say the lion, cats would not be a classification."*

A unit here is therefore a head clause **plus its subordinate clauses, with the
word that introduces each**:

    (μακάριος, p-s) + [ ὅτι -> (verb, s-v) ]

which is the Beatitude, and which recurs eight times in Matthew 5.

## Rules are LABELS, not gates

Every filter in the earlier tool deleted a real class to keep the output tidy:
discount synoptics, require three chapters, require a verb. Each was wrong.
Here a form is kept if it **repeats**, and everything else is recorded:

    scope    within-passage | across-chapters | across-books
    claim    form (one shape, many events) | alignment (one event retold)

Genesis 5's ten-fold genealogy is `within-passage`, which is what the previous
MIN_CHAPTERS rule threw away -- the most formulaic writing in the corpus is
deliberately concentrated.

## And the variation is part of the form

The Beatitudes' ground clauses are future at 5:4-9 and **present at 5:3 and
5:10**, bracketing the set. A layer recording only "eight verses share this
shape" loses the inclusio, which is the most interesting thing in the passage.
So each form carries what VARIES across its instances.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import pathlib
import re
import unicodedata as ud
import xml.etree.ElementTree as ET

import provenance

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAC = ROOT / "data" / "raw" / "macula"
DEST = ROOT / "out" / "clauseforms.jsonl.gz"

REF = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)")
BOOK = {"GEN": "Gen", "EXO": "Exo", "LEV": "Lev", "NUM": "Num", "DEU": "Deu",
        "JOS": "Jos", "JDG": "Jdg", "RUT": "Rut", "1SA": "1Sa", "2SA": "2Sa",
        "1KI": "1Ki", "2KI": "2Ki", "1CH": "1Ch", "2CH": "2Ch", "EZR": "Ezr",
        "NEH": "Neh", "EST": "Est", "JOB": "Job", "PSA": "Psa", "PRO": "Pro",
        "ECC": "Ecc", "SNG": "Sng", "ISA": "Isa", "JER": "Jer", "LAM": "Lam",
        "EZK": "Ezk", "DAN": "Dan", "HOS": "Hos", "JOL": "Jol", "AMO": "Amo",
        "OBA": "Oba", "JON": "Jon", "MIC": "Mic", "NAM": "Nam", "HAB": "Hab",
        "ZEP": "Zep", "HAG": "Hag", "ZEC": "Zec", "MAL": "Mal", "MAT": "Mat",
        "MRK": "Mrk", "LUK": "Luk", "JHN": "Jhn", "ACT": "Act", "ROM": "Rom",
        "1CO": "1Co", "2CO": "2Co", "GAL": "Gal", "EPH": "Eph", "PHP": "Php",
        "COL": "Col", "1TH": "1Th", "2TH": "2Th", "1TI": "1Ti", "2TI": "2Ti",
        "TIT": "Tit", "PHM": "Phm", "HEB": "Heb", "JAS": "Jas", "1PE": "1Pe",
        "2PE": "2Pe", "1JN": "1Jn", "2JN": "2Jn", "3JN": "3Jn", "JUD": "Jud",
        "REV": "Rev"}
MIN_OCC = 3         # a form repeats; that is the whole gate
STOPW = {"he", "she", "it", "they", "you", "i", "we", "the", "a", "of", "to",
         "and", "will", "was", "were", "be", "is", "are", "them", "him",
         "her", "his", "did", "do", "in", "on", "up", "out", "for"}


def nfc(s):
    return ud.normalize("NFC", s or "")


def norm_ref(raw):
    m = REF.match(str(raw or ""))
    if not m:
        return None
    b = BOOK.get(m.group(1))
    return f"{b}.{int(m.group(2))}.{int(m.group(3))}" if b else None


# ---------------------------------------------------------------- function
# 2026-09-12: what really matters is the function of the
# clause, as that is meaningful for higher level patterns.
#
# Right, and it is what makes a form GENERALISE. Keyed on the lemma,
#
#     "Blessed are the X, for they Y"      μακάριος + ὅτι
#     "Woe to you X, because you Y"        οὐαί     + ὅτι
#
# are two unrelated forms. Keyed on FUNCTION they are one -- a PRONOUNCEMENT
# paired with a GROUND -- which is a higher-level pattern and the thing the
# whole taxonomy is for. The lemma stays on the instance, so nothing is lost.
#
# Derived from the ORIGINAL LANGUAGE, not from English connectives:
# the subordinating word, the verb's own form, and what carries the predicate.
# `out/sentence-function.jsonl.gz` already holds PDTB-style relations but they
# are read off English punctuation and connectives, so they cannot serve here.
GROUND = {"ὅτι", "διότι", "γάρ", "כִּי", "יַעַן"}
CONDITION = {"εἰ", "ἐάν", "אִם", "לוּ"}
PURPOSE = {"ἵνα", "ὅπως", "לְמַעַן", "פֶּן"}
TEMPORAL = {"ὅτε", "ὅταν", "כַּאֲשֶׁר", "בְּ", "טֶרֶם"}
RELATIVE = {"ὅς", "ὅστις", "אֲשֶׁר", "שֶׁ"}
# NOT a generator expression. Written as one first, and it is silently wrong:
# the generator is consumed lazily DURING the tuple unpacking, so by the time
# it yields the second set, GROUND has already been rebound to the first
# result and CONDITION is being read from the new value. Every subordinator
# then fell through to the generic "subordinate" and the whole functional key
# collapsed -- visible only as "+ subordinate" on every single row.
TEMPORAL |= {"עַד", "אַחַר", "אַחֲרֵי", "מִן"}
# Comparison, already established by tools/compare.py against the same tree.
COMPARISON = {"כְּ", "כְּמוֹ", "ὡς", "ὥσπερ", "καθώς", "καθάπερ"}
# A PREPOSITION GOVERNING A CLAUSE IS NOT A CONJUNCTION. לְ + infinitive is
# "to do X" -- a complement, not a ground or a condition. 4,548 of them fell
# through to the generic bucket and dragged every Hebrew form with them.
COMPLEMENT = {"לְ", "אֶל", "עַל", "בְּ", "εἰς", "ἐν", "διά", "πρός", "ἀπό"}
# A determiner heading a clause is a headless relative: ὁ πενθέω, "those who
# mourn".
RELATIVE |= {"ὁ", "הַ"}
COORD = {"וְ", "καί", "δέ", "אוֹ", "ἤ"}

GROUND = {nfc(x) for x in GROUND}
CONDITION = {nfc(x) for x in CONDITION}
PURPOSE = {nfc(x) for x in PURPOSE}
TEMPORAL = {nfc(x) for x in TEMPORAL}
RELATIVE = {nfc(x) for x in RELATIVE}
COMPARISON = {nfc(x) for x in COMPARISON}
COMPLEMENT = {nfc(x) for x in COMPLEMENT}
COORD = {nfc(x) for x in COORD}

# Verb form -> speech act. Same tables frames.py uses; duplicated rather than
# imported because that module reads the frame attribute and this one reads
# the tree, and a shared import would tie two different passes together.
STANCE = {"qatal": "report", "wayyiqtol": "report", "imperative": "command",
          "jussive": "command", "cohortative": "wish", "yiqtol": "projection",
          "weqatal": "projection", "indicative": "report",
          "imperative ": "command", "subjunctive": "projection",
          "optative": "wish"}


def stance_of(w):
    if w is None:
        return ""
    t = (w.get("type") or "").strip()
    if t in STANCE:
        return STANCE[t]
    m = (w.get("mood") or "").strip()
    if m == "indicative" and (w.get("tense") or "") == "future":
        return "projection"
    return STANCE.get(m, "")


def function_of(cl, head, subordinator):
    """What this clause DOES, in one word.

    A pronouncement is the case that matters most here and the one both
    earlier tools missed: a verbless clause whose predicate is an adjective,
    noun or interjection asserts a state of someone. "Blessed are the poor",
    "Woe to you", "Cursed be the man".
    """
    if subordinator:
        if subordinator in GROUND:
            return "ground"
        if subordinator in CONDITION:
            return "condition"
        if subordinator in PURPOSE:
            return "purpose"
        if subordinator in TEMPORAL:
            return "temporal"
        if subordinator in RELATIVE:
            return "relative"
        if subordinator in COMPARISON:
            return "comparison"
        if subordinator in COMPLEMENT:
            return "complement"
        if subordinator in COORD:
            return "coordinate"
        return "subordinate"
    if not head:
        return ""
    lemma, cls, _g, w = head
    if cls in ("adj", "noun", "ij", "adjective"):
        return "pronouncement"
    st = stance_of(w)
    return st or "predication"


def head_of(cl):
    """(lemma, class, gloss) of the clause's predicate.

    A verb if it has one, else whatever carries role="p" -- which is how a
    verbless clause states its predicate, and the reason this tool exists.
    """
    # A COPULA IS A CARRIER, NOT THE CONTENT. "theirs IS the kingdom" and
    # "theirs the kingdom" make the same assertion; Greek needs εἰμί where
    # Hebrew does not. Taking `vc` as the head classified Mat 5:3 and 5:10 as
    # reports and split the Beatitudes off from their own six middle verses --
    # and those two are the inclusio, so the split fell exactly where the
    # passage is most tightly bound. Predicate before copula.
    for want in ("v", "p", "vc"):
        for ch in cl:
            if ch.get("role") != want:
                continue
            w = ch if ch.tag == "w" else next(iter(ch.iter("w")), None)
            if w is not None:
                return (nfc(w.get("lemma") or ""),
                        (w.get("class") or "").lower(),
                        (w.get("english") or w.get("gloss") or "").strip(), w)
    return None


def roles_of(cl):
    return "-".join(sorted({ch.get("role") for ch in cl if ch.get("role")}))


def subordinates(cl):
    """[(introducing word, sub-clause head, sub-clause roles)] for one clause.

    A subordinate arrives as a child node carrying a role of its own with a
    clause inside it; the word that opens it is the subordinator -- ὅτι, כִּי,
    אֲשֶׁר. That word is what makes the pairing legible as a pairing.
    """
    out = []
    for ch in cl:
        if ch.tag != "wg" or ch.get("class") == "cl":
            continue
        # A CORE ARGUMENT IS NOT A SUBORDINATE. Mat 5:4's subject is a
        # headless relative -- `ὁ πενθέω`, "those who mourn" -- which is a
        # clause filling role="s". Counting it as a subordinate put a
        # meaningless ('subordinate','v') at the head of every Beatitude key
        # and buried the ὅτι ground that actually makes the form.
        if (ch.get("role") or "") in ("s", "o", "p", "v", "o2", "vc"):
            continue
        inner = next((x for x in ch.iter("wg")
                      if x.get("class") == "cl"), None)
        if inner is None:
            continue
        first = next(iter(ch.iter("w")), None)
        if first is None:
            continue
        h = head_of(inner)
        sw = nfc(first.get("lemma") or "")
        out.append((sw,
                    (first.get("english") or first.get("gloss") or "").strip(),
                    function_of(inner, h, sw), roles_of(inner),
                    stance_of(h[3]) if h else ""))
    return out[:2]


def slug(parts):
    out = []
    for g in parts:
        w = [x for x in re.sub(r"[^a-z ]", " ", (g or "").lower()).split()
             if x not in STOPW]
        out.append("_".join(w[:2]) if w else "x")
    return "form_" + "_".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--top", type=int, default=14)
    a = ap.parse_args()

    units = collections.defaultdict(list)
    files = sorted(MAC.rglob("*.xml"))
    for i, f in enumerate(files):
        if i % 250 == 0:
            print(f"  {i}/{len(files)} ...", flush=True)
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for cl in root.iter("wg"):
            if cl.get("class") != "cl":
                continue
            h = head_of(cl)
            if not h or not h[0]:
                continue
            w0 = next(iter(cl.iter("w")), None)
            ref = norm_ref(w0.get("ref")) if w0 is not None else None
            if not ref:
                continue
            subs = subordinates(cl)
            fn = function_of(cl, h, None)
            # THE KEY IS FUNCTIONAL. The lemma rides along on the instance so
            # nothing is lost, but two forms that DO the same thing with
            # different words are one form here -- which is the point.
            key = (fn, roles_of(cl),
                   tuple((s[2], s[3], s[4]) for s in subs))
            # the SUBJECT is the varying filler; keep it so variation is
            # inspectable rather than merely asserted
            subj = ""
            for ch in cl:
                if ch.get("role") == "s":
                    ws = [x for x in (ch.iter("w") if ch.tag != "w" else [ch])]
                    subj = " ".join((x.get("english") or x.get("gloss") or "")
                                    for x in ws)[:40]
                    break
            units[key].append({
                "ref": ref, "head_gloss": h[2], "subject": subj.strip(),
                "subs": [(s[1], s[2], s[4]) for s in subs],
                "head_lemma": h[0], "function": fn,
            })

    print(f"\ndistinct clause-shape units: {len(units):,}")
    rows = []
    for key, places in units.items():
        if len(places) < MIN_OCC:
            continue
        refs = [p["ref"] for p in places]
        chs = {r.rsplit(".", 1)[0] for r in refs}
        bks = {r.split(".")[0] for r in refs}
        scope = ("within-passage" if len(chs) == 1
                 else "across-books" if len(bks) > 1 else "across-chapters")
        subjects = {p["subject"] for p in places if p["subject"]}
        rows.append({
            "id": slug([key[0]] + [s[0] for s in key[2]]),
            "function": key[0], "roles": key[1],
            "pairs_with": [f"{s[0]}({s[2]})" if s[2] else s[0]
                           for s in key[2]],
            "heads_seen": sorted({p["head_gloss"] for p in places})[:6],
            "paired": bool(key[2]),
            "occurrences": len(places), "chapters": len(chs),
            "books": sorted(bks)[:6], "scope": scope,
            "distinct_subjects": len(subjects),
            "at": refs[:60],
        })
    print(f"forms repeating {MIN_OCC}+ times: {len(rows):,}")
    sc = collections.Counter(r["scope"] for r in rows)
    pr = collections.Counter("paired" if r["paired"] else "simple"
                             for r in rows)
    print(f"  scope {dict(sc)}")
    print(f"  {dict(pr)}")

    print("\nPAIRED FUNCTIONAL FORMS -- head clause + subordinate, most used")
    pair = sorted((r for r in rows if r["paired"]),
                  key=lambda r: -r["occurrences"])[:a.top]
    print(f"  {'occ':>5}{'heads':>6}  {'form':<40}words seen as the head")
    for r in pair:
        f = f"{r['function']}[{r['roles']}] + {'/'.join(r['pairs_with'])}"
        print(f"  {r['occurrences']:>5}{len(r['heads_seen']):>6}  {f[:40]:<40}"
              f"{', '.join(r['heads_seen'][:3])[:34]}")

    print("\nPRONOUNCEMENT forms -- the class both earlier tools could not see")
    pr = sorted((r for r in rows if r["function"] == "pronouncement"),
                key=lambda r: -r["occurrences"])[:a.top]
    for r in pr:
        f = f"pronouncement[{r['roles']}]" + (
            f" + {'/'.join(r['pairs_with'])}" if r["paired"] else "")
        print(f"  {r['occurrences']:>5}{len(r['heads_seen']):>6}  {f[:40]:<40}"
              f"{', '.join(r['heads_seen'][:3])[:34]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            **provenance.stamp(__file__, inputs=["data/raw/macula/*/*.xml"]),
            "_source": "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., "
                       "CC BY 4.0 -- clause boundaries, roles and classes.",
            "_note": "A form is a clause SHAPE -- head predicate (verb, "
                     "adjective or noun) plus role inventory -- optionally "
                     "PAIRED with a subordinate clause and its introducing "
                     "word. Kept when it repeats 3+ times ANYWHERE; scope and "
                     "claim are labels, never gates, because every gate in "
                     "the previous tool deleted a real class.",
        }, ensure_ascii=False) + "\n")
        seen = collections.Counter()
        for r in rows:
            seen[r["id"]] += 1
            if seen[r["id"]] > 1:
                r["id"] = f"{r['id']}_{seen[r['id']]}"
            f.write(json.dumps({"kind": "form",
                                **{k: v for k, v in r.items() if k != "at"}},
                               ensure_ascii=False) + "\n")
        for r in rows:
            for at in r["at"]:
                f.write(json.dumps({"kind": "instance_of", "src": at,
                                    "dst": r["id"]}, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(rows):,} forms, "
          f"{sum(len(r['at']) for r in rows):,} instances)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
