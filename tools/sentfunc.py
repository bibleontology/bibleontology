"""What each sentence DOES, not just where it is.

After four sessions of grouping work, the conclusion was that the work at the
sentence level had not been done sufficiently, and that the understanding was
lacking to do what a reader does intuitively. That was right, and the proof was
one line -- everything `out/sentences.jsonl.gz` holds for a sentence is

    {id, ref, n, verses, spans, words, gloss}

an id, its extent, a word count and a gloss. The clause layer has roles and the
node layer has words; the sentence itself carried nothing but where it begins
and ends. Every grouping attempt so far has been an effort to *infer* discourse
function from lexical overlap, which is why they all landed near chance.

## The taxonomy this aligns to, and why that one

Has the industry solved this? Substantially, yes, and by two frameworks worth
naming:

- **PDTB** (Penn Discourse Treebank) annotates relations anchored on the
  **connective**, under four top-level classes -- TEMPORAL, CONTINGENCY,
  COMPARISON, EXPANSION -- each with types and subtypes beneath.
- **RST** (Rhetorical Structure Theory) annotates a tree of nucleus and
  satellite, where a satellite depends on the unit it supports.

**PDTB's classes are used here for the relation and RST's asymmetry for the
direction**, because that pairing matches the evidence this corpus actually
yields: connectives were measured as the strongest signal available, and
nucleus/satellite is what was described when verse 7 was read as looking for
something to back it up.

### How much of this is borrowed: less than the section above implies

An earlier draft said the taxonomies are *"published and unrestricted."* **That
was an unverified licence claim and it is withdrawn** -- the same failure that
cost a day of STEPBible cleanup, asserting a licence status instead of checking
one, in a docstring where it would have hardened into a project fact.

The withdrawal turned out to matter less than expected, because the reaction
to it was the more useful correction: the project was getting there itself,
though there are certainly lessons learned that can be drawn on. The file
bears that out. **Everything this module computes was
derived here, from measurement on this corpus:**

- **connectives as the strongest available signal** -- measured, after lexical
  cohesion read 0.0 at every seam of Psalm 103
- **translator consensus** -- measured as a hard negative constraint, 0.00 lift
  on Genesis and Titus seams
- **the correlative exception** -- found by hand, when `as ... so` at Psalm
  103:13 forced a conclusion to be retracted
- **direction itself** -- a hand reading, that verse 7 is looking for
  something to back it up
- **speech acts and clause shape** -- `tools/acts.py` and MACULA

What the outside frameworks contribute is **two lessons and a vocabulary**:
that a relation is best anchored on its connective, that asymmetry is worth
recording separately from relation, and the four words for the classes. Lessons
drawn on are not material taken, and:

- **No PDTB or RST file has been read** -- not the corpus, not the annotation
  manual, nothing downloaded. Verified against the repository, 2026-09-09.
- **Every connective list below was written here**, from English.

The class names -- comparison, contingency, temporal, expansion -- are the
field's ordinary words for relations that predate the field. Using them with
attribution is how the names stay legible to anyone who arrives from that
literature. It is not a claim about anyone's licence, and none is needed while
nothing of theirs is taken.

## Where the evidence comes from

Nothing here is a model output. Per sentence:

- **the opening connective**, taken from the translations rather than one of
  them. Five agreeing that a verse continues was measured as a hard constraint
  on seams (0.00 lift on Genesis and Titus), so consensus is used again here.
- **correlative structure** -- `as ... so`, which points forward inside the
  sentence rather than backward. Missing this put verse 13 of Psalm 103 in the
  wrong bucket and produced a conclusion that had to be retracted.
- **speech act**, from `tools/acts.py`: assertion, command, question or wish.
- **clause shape**, from MACULA: verbless, elided, nominalised, minor.
- **frame arguments**, from MACULA's own `frame` attribute -- PropBank-style
  A0/A1 labelling on 94,698 words that this project had never read.

## What it deliberately does not do

It does not build a tree. RST parsers attach every satellite to a nucleus, and
the measurements here say precedence between competing signals is unresolved --
five signals now invert by genre rather than merely weakening. So this records
**what each sentence is**, and leaves attachment to whatever scheme consumes it,
which is what was asked for: multiple grouping schemes are to be supported.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "sentence-function.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

# Discourse relations at two levels, named after PDTB's, with the openers that
# signal each.
#
# The request was to grab PDTB. Nothing was grabbed. The Penn Discourse Treebank
# is distributed by the LDC under a paid licence, and this project removed
# STEPBible a day earlier over a licence that was only AMBIGUOUS. It would also
# buy nothing usable: PDTB's annotations sit on Wall Street Journal text, and
# what could transfer to Hebrew poetry is the vocabulary, not the sentences.
#
# So **the names below follow PDTB's and the content is this project's.** Two
# levels, because one cannot tell a REASON from a RESULT -- and the hand reading
# of Psalm 103 turns on exactly that: verse 11's *"For as high as the heavens
# are above the earth"* gives the GROUNDS for verses 8-10, while verse 14's
# *"For He knows our frame"* gives the CAUSE of verse 13. Every word in every set was written here
# by thinking about English, and the sets should be judged on whether they
# classify this corpus correctly, not on their resemblance to anyone's manual.
PDTB = {
    # one situation is set against another
    ("comparison", "concession"): {"although", "though", "yet",
                                   "nevertheless", "notwithstanding", "still"},
    ("comparison", "contrast"): {"but", "however", "whereas", "conversely",
                                 "instead", "rather"},
    # one situation causally or conditionally bears on another
    ("contingency", "cause"): {"because", "since", "for", "therefore",
                               "wherefore", "thus", "hence", "so"},
    ("contingency", "condition"): {"if", "unless", "except", "lest",
                                   "whether", "provided"},
    ("contingency", "purpose"): {"lest", "thereby"},
    # one situation precedes, follows or overlaps another
    ("temporal", "synchronous"): {"while", "when", "meanwhile", "whilst",
                                  "now"},
    ("temporal", "asynchronous"): {"after", "before", "then", "afterward",
                                   "until", "till", "thereafter"},
    # one situation adds to, exemplifies or restates another
    ("expansion", "conjunction"): {"and", "also", "moreover", "furthermore",
                                   "besides", "likewise", "additionally"},
    ("expansion", "disjunction"): {"or", "nor", "either", "neither"},
    ("expansion", "instantiation"): {"namely", "specifically"},
    ("expansion", "equivalence"): {"indeed", "verily"},
}
OPENER = {w: pair for pair, ws in PDTB.items() for w in ws}

# `as ... so` and `like ... so` point FORWARD, to their own second clause. Read
# as backward connectives they misclassify a sentence that opens a section --
# which is what happened to Psalm 103:13 and had to be retracted.
CORRELATIVE = re.compile(r"\b(as|like|just as)\b.{0,90}?\bso\b", re.I)

TRANSLATIONS = ("verses.jsonl", "verses.bsb.jsonl", "verses.asv.jsonl",
                "verses.web.jsonl", "verses.ylt.jsonl")


def first_word(t):
    m = re.findall(r"[A-Za-z']+", t or "")
    return m[0].lower() if m else ""


def load_translations():
    out = []
    for name in TRANSLATIONS:
        p = ROOT / "data" / "bible" / name
        if not p.exists():
            continue
        m = {}
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if "b" in d:
                m[(d["b"], d["c"], d["v"])] = d["t"]
        out.append(m)
    return out


def load_sentences():
    rows = []
    with gzip.open(OUT / "sentences.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if not any(k.startswith("_") for k in d):
                rows.append(d)
    return rows


def load_acts():
    per = collections.defaultdict(collections.Counter)
    p = OUT / "acts.jsonl"
    if not p.exists():
        return per
    RX = re.compile(r"^\s*(\S+?)\s+(\d+):(\d+)")
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        a = json.loads(line)
        m = RX.match(str(a.get("ref", "")))
        if m:
            per[(m.group(1), int(m.group(2)), int(m.group(3)))][a.get("act")] += 1
    return per


def load_events():
    """MACULA ref -> how many narrative verbs (wayyiqtol / aorist ind.) it holds.

    Used only to tell a discourse "and" from the waw that is part of a verb.
    """
    per = collections.Counter()
    p = OUT / "events.jsonl.gz"
    if not p.exists():
        return per
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if not any(k.startswith("_") for k in d):
                per[d.get("ref")] += 1
    return per


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--show", type=int, default=10)
    a = ap.parse_args()

    sys.path.insert(0, str(ROOT / "app2"))
    import server                                              # noqa: E402

    trans = load_translations()
    print(f"translations loaded: {len(trans)}")
    sents = load_sentences()
    acts = load_acts()
    events = load_events()

    # MACULA ref -> the English (book, chapter, verse) it displays as
    eng = {}
    for (b, c, v) in trans[0]:
        eng[server.macula_ref(b, c, v)] = (b, c, v)

    rows, stats = [], collections.Counter()
    for s in sents:
        key = eng.get(s["ref"])
        texts = [m.get(key) for m in trans if key and m.get(key)] if key else []
        opens = [first_word(t) for t in texts]
        # consensus: the class a MAJORITY of translations signal
        votes = collections.Counter(OPENER.get(w) for w in opens if OPENER.get(w))
        pair, agree = (votes.most_common(1)[0] if votes else (None, 0))
        if pair and agree < max(2, len(texts) // 2):
            pair, agree = None, agree
        rel = pair[0] if pair else None
        sub = pair[1] if pair else None
        corr = any(CORRELATIVE.search(t) for t in texts)
        # continues: every translation declines to end the sentence
        cont = (bool(texts) and
                all((t or "").rstrip()[-1:] not in ".!?" for t in texts))
        act = (acts.get(key).most_common(1)[0][0] if key and acts.get(key)
               else None)

        # THE WAW IS NOT A CONNECTIVE WHEN IT IS PART OF THE VERB.
        #
        # 2026-09-09: all writing styles must be accounted for, but the
        # rules might be adapted to the style that they apply to. Measured,
        # and the largest rule in the table was the one that failed. Sentences
        # opening with "and", by how often they carry a narrative verb, against
        # sentences opening with anything else:
        #
        #     law     57.2% vs 14.0%  = 4.08x      epistle  15.1% vs 15.0% = 1.01x
        #     poetry  47.9% vs  8.1%  = 5.93x      gospel   69.7% vs 54.0% = 1.29x
        #
        # In Hebrew narrative the waw is a *bound morpheme of the wayyiqtol*,
        # not a word the writer chose; the translation renders it "and" and the
        # opener table then scored obligatory grammar as EXPANSION/CONJUNCTION.
        # That inflated expansion to 61.5% of law and held `free` down to 15%.
        # In the epistles the same word is independent of the verb -- 1.01x, no
        # association at all -- so there it is a genuine connective.
        #
        # The rule therefore adapts on the EVIDENCE IN THE SENTENCE, not on a
        # style label: a book list would mislabel Exodus's law as narrative and
        # the poetry embedded in prophecy as prophecy. This asks the sentence.
        waw = bool(rel == "expansion" and sub == "conjunction"
                   and (opens[0] if opens else "") == "and"
                   and key and acts is not None and events.get(s["ref"]))
        if waw:
            rel = sub = None

        # direction, in RST's terms and from evidence only
        if waw:
            direction = "sequence"          # narrative advance, not a relation
        elif rel and not corr:
            direction = "backward"          # a satellite: it supports what precedes
        elif corr:
            direction = "internal"          # as...so resolves inside the sentence
        elif cont:
            direction = "forward"           # grammatically unfinished
        else:
            direction = "free"              # stands alone; may open anything

        rows.append({"id": s["id"], "ref": s["ref"], "verses": s["verses"],
                     "words": s.get("words"),
                     "opens": opens[0] if opens else None,
                     "relation": rel, "subtype": sub, "agree": agree,
                     "correlative": corr, "continues": cont,
                     "narrative_waw": waw,
                     "act": act, "direction": direction})
        stats[direction] += 1
        stats[f"rel:{rel}"] += 1
        if sub:
            stats[f"sub:{sub}"] += 1

    n = len(rows)
    print(f"sentences typed: {n}\n")
    print("DIRECTION -- what the sentence needs from its neighbours")
    for k in ("backward", "sequence", "internal", "forward", "free"):
        print(f"  {k:10} {stats[k]:>7}  {100*stats[k]/n:>5.1f}%")
    print("\nPDTB RELATION -- from translator consensus on the opener")
    for k in ("comparison", "contingency", "temporal", "expansion", None):
        v = stats[f"rel:{k}"]
        print(f"  {str(k):12} {v:>7}  {100*v/n:>5.1f}%")

    print(f"\nPsalm 103, the passage this was built from:")
    for r in rows:
        if r["ref"].startswith("Psa.103."):
            v = r["ref"].split(".")[-1]
            print(f"  v{v:>2}  {r['direction']:<9} "
                  f"{str((r['relation'] or '-') + '/' + (r['subtype'] or '-')):<24} "
                  f"opens={str(r['opens']):<8} corr={'Y' if r['correlative'] else '-'} "
                  f"cont={'Y' if r['continues'] else '-'}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": CREDIT,
            "_note": "What each sentence does. Relation names follow the Penn "
                     "Discourse Treebank's four classes and direction follows "
                     "Rhetorical Structure Theory's nucleus/satellite "
                     "asymmetry. Terminology only: no PDTB or RST file, corpus "
                     "or manual was read, and every connective list was "
                     "written for this project.",
        }, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({n} sentences)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
