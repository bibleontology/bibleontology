"""Connections between passages, from the agreement of independent signals.

2026-09-18: a generic method applied broadly opens other opportunities to match
as well.

## Why this shape

Every link method built before this one accumulated a single kind of evidence --
shared words -- and sorted by how much. Measured against one case all week, it
failed four times in the same direction, because **more of one kind of evidence
always helps long ordinary passages more than short marked ones**:

    bag of words, stopworded             #280 of 1,113
    bag of words, content restored       #521 of 1,882   (worse)
    BSB section boundaries, both sides   #280 of 1,113
    ordered phrase + book position         #1 of 1,882

The case is Genesis 1 against John 1, arguably the most
important link in the Bible, and the noise it lost to was Numbers/Nehemiah/
Joel against Revelation 6:6 on *oil, wheat and wine*.

So: **count agreeing signal FAMILIES, do not sum evidence.** Each family is
independently rare and answers a different question, so two agreeing is already
strong and three is near-unique. The noise scores zero by construction rather
than by a threshold -- which matters, because every attempt to tune a cutoff
that excluded oil/wheat/wine also excluded Genesis.

MEASURED, 2026-09-18:

    Gen 1:1-5   <-> Jhn 1:1-5   2   phrase `εν αρχη` + root `λεγε` (λέγω/λόγος)
    Num 21:9    <-> Jhn 3:14    1   name `μωυσης`
    Num 18:12   <-> Rev 6:6     0   the noise that headed every earlier ranking
    Ecc 7:1-9   <-> Jhn 1:1-5   0   the four-common-word near miss
    Psa 104:1-9 <-> Gen 1:1-5   1   the control -- low family count, very high
                                    lexical overlap, and it must still surface

The Psalm 106 case, which asked for many small event connections to Exodus
and beyond in the lower levels and a wide connection when moving up to the
higher level groupings, produces both:

    Psa 106:17 -> Num 16:12   Dathan, Abiram      the rebellion
    Psa 106:19 -> Exo 17:6    Horeb               the golden calf
    Psa 106:30 -> Num 25:11   Phinehas            his zeal staying the plague
    Psa 106:38 -> Exo 3:8     Canaanites

    whole psalm -> Num 33  Forty-Two Journeys of the Israelites   18 names
                -> Jos 24  Joshua Reviews Israel's History        13 names
                -> Num 21  The Bronze Serpent                     13 names

Joshua 24 is the same GENRE as Psalm 106 -- a historical recital of the same
events -- and Numbers 33 is the itinerary summary. Both surfaced from names
alone, with nothing in the tool knowing what a recital is.

## The question that matters is LOCAL, not global

2026-09-18: John 1 does not have to lead, but a reader reading John 1:1-5
should see a pattern chip point to Genesis 1. That is what matters to the
reader.

This is a much easier problem than the one being solved before it, and a
better-specified one. Genesis 1 does not have to outrank every pair in the
corpus; it has to be in **John 1:1-5's own top few**. Every ranking earlier in
this file answered the global question and is beside the point.

Ranked locally, by family count and then by lexical evidence:

    Jhn 1:1-5  -> Gen 1  "The Creation"          rank 1 of 1,703
    Jhn 3:14   -> Num 21 "The Bronze Serpent"    rank 1 of 1,445
    Mat 12:40  -> Jon 2  "Jonah's Prayer"        rank 1 of 1,316
    Jhn 6:31   -> Exo 16 "The Jar of Manna"      rank 3 of   678

**Both axes are needed and neither is sufficient.** Family count alone put the
serpent at rank 203, because sharing *Moses* fires the name family exactly as
hard as sharing *Phinehas* and every Chronicles genealogy tied with Numbers 21.
Lexical evidence alone is what failed all week. Families say what KIND of
connection; evidence says how strong. Sort by the first, break ties with the
second, and show both.

## A chip needs a PATTERN, and the pattern has to be established

2026-09-18: the pattern has to be actually established to have the chip. A chip that says "related to Genesis 1" is a cross-reference. A chip
has to name something and be able to show its instances.

Inverting the feature index over the corpus says which families form real
classes and which do not:

    name      148 features bridge the testaments   -- a real class
    root      985                                  -- unmeasured, likely noisy
    phrase      6                                  -- five are function-word junk

So `εν αρχη` is **not** an instance of a populous type. It is a singleton, and
five of the phrase family's six cross-testament features were noise from an
incomplete function-word list. Widening that list and requiring the opening to
be absolute gives the actual finding:

    2,460 distinct absolute openings at book and section starts
        1 occurs in BOTH testaments:  εν αρχη   Gen 1:1 <-> Jhn 1:1

**That is the chip, and it is a stronger claim than class membership.** The
pattern is "a book's opening echoed at the opening of another book"; the corpus
was swept; it happens exactly once. A reader can check both ends and check the
count.

State its limits with it. The sweep is over 2- and 3-word openings at BSB
section and book starts, joined through the Greek the LXX used for each Hebrew
word, so the Hebrew side is a translation choice rather than the text itself,
and the section boundaries are the Berean editors'. None of that weakens the
count; all of it belongs on the card.

For `name`, the class is genuine and populous -- Salem to Hebrews 7, Gabriel,
Siloam, Magog -- so those chips can say "an OT figure or place named here,
one of 148 that bridge the testaments" and list them.

## BENCHMARKED PROPERLY: the method is sound, the LANGUAGE JOIN is broken

The reasoning: if the poor performance is due to the mismatch across
languages, intra-testament tests should fare much better, which pinpoints what
to solve for.

Exactly right, and it isolates the fault. Same method, same section
granularity, same scoring; the only variable is whether a language boundary is
crossed.

    scored against the Berean parallel notes, section to section

                                       n     @1     @3    @10   median
    INTRA-testament, native lemmas  1,656  37.2%  56.5%  65.9%       2
      Kings/Chronicles                213  69.5%  79.3%  85.9%       1
      synoptic                        687  42.6%  77.9%  88.2%       2
      other OT<->OT                   528  26.5%  33.5%  42.2%      27
      other NT<->NT                   228  15.4%  24.1%  34.6%      46

    CROSS-testament, via the LXX      350   5.7%   8.6%  15.7%     258

**6.5x at rank 1 and 129x on median rank.** Ranking sections by IDF-weighted
shared vocabulary works: it recovers Kings/Chronicles parallels 69.5% of the
time at rank 1 and puts the synoptic parallel at median rank 2. The families
add little on top (5.2% -> 5.7% cross-testament).

So the thing to solve for is **the Hebrew-to-Greek join**, not the ranking.
Known faults in it, all found this session:

1. Case and accents -- fixed by `norm`.
2. Chi written as xi in 1,284 of 16,226 renderings -- folded by `norm`.
3. **Inflected forms against lemmas** -- NOT fixed. `αρτον, αρτου, αρτους`
   never meet `αρτος`, so only nominative singulars have ever matched.
4. Coverage: the `greek` column carries a rendering for 5,619 Hebrew lemmas,
   so anything outside that simply has no bridge.

### A correction: the first benchmark was measured wrong

The run before this one reported 2.9% recall@1 and "barely better than chance",
and that figure came from a **broken harness**, not from the method. A note
reads `Mat 14:13 -> Mrk 6:30-6:44`: the end marks the TARGET's span, and the
harness queried the single source VERSE against whole sections. Matthew 14:13
alone is "Jesus withdrew by boat to a solitary place" -- the intro sentence,
not the feeding of the five thousand, whose section shares 44 lemmas with
Mark's including κόφινος, κλάσμα, ἰχθύς and δώδεκα.

Both numbers in that run were wrong in the same direction. Verify the
measurement before believing a result, including -- especially -- a result that
confirms a suspicion.

## Superseded: the first benchmark run

Scored against the 364 cross-testament Berean parallel notes -- independent
evidence, made by people for readers, with no knowledge of anything here:

    scored 272, unresolvable 92

    recall@1     2.9%
    recall@3     3.3%
    recall@5     3.7%
    recall@10    5.9%
    recall@25   10.7%
    median rank  588 of 2,079        (random would sit near 1,040)

**Every case this file reports above was hand-picked** -- by a reader, or by me
after seeing what the method did. Six for six on chosen examples; 2.9% on 272
nobody chose. The measured prior in this project is that marker harvests run
about 40% precision, and reporting case-by-case success as evidence of a
working method was exactly the error that prior exists to prevent.

**Do not ship chips on this.** A reader shown a link at 2.9% recall is being
shown noise with a citation attached, which is the failure mode the whole
project is built to avoid.

### One real cause, which makes this a floor rather than a verdict

The lexical axis breaks every tie, and it is crippled: MACULA's LXX column
stores INFLECTED FORMS against the New Testament's LEMMAS, so `αρτον, αρτου,
αρτους` never met `αρτος` and only nominative singulars were ever matching.
Fix that and re-run before drawing any conclusion about the approach. But a
stemmer loose enough to join `αρτον` to `αρτος` will also join things that
should not be joined, so it needs its own precision figure first.

### The process lesson

This benchmark existed all along, already labelled *"held as a BENCHMARK:
nothing tunes toward it"*, and it was run last instead of first. Run it before
the next change, not after.

And when re-running it: **nothing may be tuned toward these 364.** The moment a
threshold is chosen because it lifts recall here, they stop measuring and
become the target. Hold a slice out.

## Known faults, unfixed

- **Inflections count as separate names.** `αιγυπτον, αιγυπτου, αιγυπτω` are
  one name, Egypt, counted three times, so section-level totals inflate.
- **The capitalisation test still admits artifacts.** `πνευμα` and `θαλασσα`
  reach the name family because the glosses read "Spirit" and "Sea".
  `DIVINE_TITLES` handles the worst of it and is not a general solution.
- **`register` and `frame` are UNMEASURED** and do not contribute to the count.
- **`_root` is crude** -- a 4-character stem with the ablaut folded. It finds
  λεγε for λέγω/λόγος, which is what it was built for, and it also yields junk
  like `εκαλ`/`εσαλ`. It needs a precision figure before it is trusted.

## Adding a family

A family is a function `ref -> {feature keys}`. It must be:

- **Rare.** The tool measures each family's base rate and prints it. A family
  whose features are common is doing what the bag of words did.
- **Independent of the others.** Lift between families is measured and printed.
  Two families that fire together are one family, and counting them twice
  reproduces the accumulation problem in a new costume.
- **Showable.** The reader is given the matched feature, not a number.

Register at the bottom of `FAMILIES`. Nothing else changes.

## What this does NOT do

It does not rank by importance. Evidence strength and importance are separate
axes (2026-09-16) and this tool is the evidence half.
The importance half is the old app's per-type weight, still to be recovered.

Psalm 104 against Genesis 1 is the control: **0 families, very high lexical
overlap**, and it must still surface as the literal parallel it is. If the
family count becomes a gate rather than a second axis, it vanishes -- which
would mean the two axes had collapsed back into one.

    python tools/bridge.py --rates          # base rate and lift per family
    python tools/bridge.py --pair Gen.1.1-5 Jhn.1.1-5
    python tools/bridge.py --sweep --min-families 2
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import pathlib
import re
import sys
import unicodedata

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

NT = {"Mat", "Mrk", "Luk", "Jhn", "Act", "Rom", "1Co", "2Co", "Gal", "Eph",
      "Php", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb", "Jas",
      "1Pe", "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev"}

FUNCTION = {
    "ο", "και", "δε", "εν", "εισ", "εκ", "αυτοσ", "ουτοσ", "οσ", "τε", "γαρ",
    "μεν", "ου", "μη", "οτι", "αλλα", "συ", "εγω", "ημεισ", "υμεισ", "ειμι",
    "προσ", "επι", "κατα", "δια", "περι", "απο", "συν", "υπο", "παρα", "ινα",
    "ωσ", "ει", "αν", "τισ",
}


def norm(w: str) -> str:
    """Fold case, accents, and MACULA's chi/xi corruption.

    The `greek` column is lowercase and unaccented where the Greek NT lemma
    column is capitalised and accented, and 1,284 of its 16,226 renderings
    write chi as xi. Without folding both, proper names never join -- and names
    are the class that actually crosses the testaments. See tools/lxxbridge.py.
    """
    d = unicodedata.normalize("NFD", w or "")
    d = "".join(c for c in d if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", d).casefold().replace("ξ", "χ")


def strongkey(lang: str, s: str | None) -> str | None:
    s = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", s or ""))
    return (lang[:1] + s) if s else None


# --------------------------------------------------------------------------
# corpus


class Corpus:
    """Everything the families read, loaded once."""

    def __init__(self) -> None:
        self._namedf: collections.Counter | None = None
        self.words: dict[str, list] = {}
        for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                              encoding="utf-8"):
            d = json.loads(line)
            if d.get("ref"):
                self.words[d["ref"]] = d["words"]
        self.meta = json.loads((OUT / "lemma-meta.json")
                               .read_text(encoding="utf-8"))
        self.frames: dict[str, list] = collections.defaultdict(list)
        fp = OUT / "frames.jsonl.gz"
        if fp.exists():
            for line in gzip.open(fp, "rt", encoding="utf-8"):
                if line.startswith('{"_'):
                    continue
                d = json.loads(line)
                if d.get("ref"):
                    self.frames[d["ref"]].append(d)
        # Structural openings: a book's first verse, and each BSB section's.
        self.book_open: set[str] = set()
        self.sec_open: set[str] = set()
        first: dict[str, tuple] = {}
        for r in self.words:
            b, c, v = r.split(".")
            k = (int(c), int(v))
            if b not in first or k < first[b][0]:
                first[b] = (k, r)
        self.book_open = {r for _, r in first.values()}
        sp = OUT / "structure.jsonl.gz"
        if sp.exists():
            for line in gzip.open(sp, "rt", encoding="utf-8"):
                if not line.strip():
                    continue
                d = json.loads(line)
                if any(k.startswith("_") for k in d):
                    continue
                if d.get("level") != "section":
                    continue
                if "engbsb" not in (d.get("by") or []):
                    continue
                self.sec_open.add(d["ref"])

    def name_df(self, key: str) -> int:
        """How many verses a name feature occurs in; built lazily, once."""
        if self._namedf is None:
            self._namedf = collections.Counter()
            for r in self.words:
                for x in fam_name(self, [r]):
                    self._namedf[x] += 1
        return self._namedf.get(key, 0)

    def is_nt(self, ref: str) -> bool:
        return ref.split(".")[0] in NT

    def lemmas(self, ref: str) -> list[set[str]]:
        """Per word, the Greek it is or the Greek the LXX used for it.

        A list, not a set: order is a signal and the bag-of-words attempts
        that discarded it all failed. Hebrew words yield several candidate
        renderings, so each position is a set.
        """
        out = []
        for w in self.words.get(ref) or []:
            if self.is_nt(ref):
                lem = norm(w.get("l") or "")
                out.append({lem} if lem else set())
            else:
                k = strongkey("hebrew", w.get("s"))
                got = set()
                if k:
                    for x in ((self.meta.get(k) or {}).get("greek") or [])[:4]:
                        g = norm((x.get("v") or "").strip(",.;·:"))
                        if g:
                            got.add(g)
                out.append(got)
        return out

    def flat(self, ref: str) -> set[str]:
        s: set[str] = set()
        for x in self.lemmas(ref):
            s |= x
        return s


def expand(span: str) -> list[str]:
    """'Gen.1.1-5' -> ['Gen.1.1', ..., 'Gen.1.5']; a plain ref passes through."""
    m = re.match(r"^(\w+)\.(\d+)\.(\d+)(?:-(\d+))?$", span)
    if not m:
        return [span]
    b, c, a, z = m.group(1), m.group(2), int(m.group(3)), m.group(4)
    return [f"{b}.{c}.{v}" for v in range(a, int(z) + 1 if z else a + 1)]


# --------------------------------------------------------------------------
# signal families
#
# Each takes (corpus, [refs]) and returns {feature key}. Keys must be
# comparable across the testaments, so they are built from normalised Greek.


def fam_phrase(co: Corpus, refs: list[str]) -> set[str]:
    """Angle 1 -- an ordered phrase at a structurally marked position.

    "The Beginning" is distinct from beginning. A phrase in a
    position is a different object from its words, and turning verses into
    sets destroyed it. Ten OT verses open with `εν αρχη` and only Gen 1:1 also
    opens a book; John 1:1 opens the fourth Gospel the same way. That single
    constraint moved the pair from #280 to #1 of 1,882.

    Only OPENINGS are marked here. A phrase buried mid-paragraph is not
    titular, and admitting it would return this family to counting n-grams.

    A titular opening is also ABSOLUTE. Jeremiah 26:1 and 27:1 both open `εν
    αρχη` and neither is a title: they read "in the beginning OF THE REIGN of
    Jehoiakim", where the phrase is a construct governing what follows. Genesis
    and John use it with nothing depending on it, and the next word is a verb --
    ἐποίησεν, ἦν. So the phrase is recorded only when the word after it is
    verbal. Without this the two Jeremiahs tie with Genesis for John's
    prologue, and on shared vocabulary they beat it.
    """
    out = set()
    for r in refs:
        if r not in co.book_open and r not in co.sec_open:
            continue
        seq = co.lemmas(r)
        for n in (2, 3):
            if len(seq) < n:
                continue
            heads = seq[:n]
            content = [h for h in heads if h - FUNCTION]
            if not content:
                continue
            if not _absolute(co, r, n):
                continue
            for combo in _combos(heads):
                key = " ".join(combo)
                if any(c not in FUNCTION for c in combo):
                    out.add(f"open:{key}")
    return out


def _absolute(co: Corpus, ref: str, n: int) -> bool:
    """Is the opening phrase absolute, or does it govern what follows?

    Verbal next word -> absolute (Gen 1:1 ἐποίησεν, Jhn 1:1 ἦν).
    Nominal next word -> a construct like Jeremiah's "of the reign of".
    """
    ws = co.words.get(ref) or []
    if len(ws) <= n:
        return True
    pos = (ws[n].get("p") or "").lower()
    return pos.startswith("verb")


def _combos(positions: list[set[str]], cap: int = 8) -> list[tuple]:
    """Every reading of an ambiguous Hebrew->Greek sequence, capped."""
    acc: list[tuple] = [()]
    for p in positions:
        if not p:
            return acc
        nxt = []
        for a in acc:
            for x in sorted(p)[:3]:
                nxt.append(a + (x,))
                if len(nxt) >= cap:
                    break
            if len(nxt) >= cap:
                break
        acc = nxt
    return acc


def fam_name(co: Corpus, refs: list[str]) -> set[str]:
    """Proper nouns, which are the class that really crosses the testaments.

    The lemma allusion layer holds 141,365 links and zero crossing, because
    Hebrew and Greek share no lemma. Names bridge through the LXX column --
    once its case and chi/xi faults are folded, which is what `norm` is for.
    """
    out = set()
    for r in refs:
        for w in co.words.get(r) or []:
            if co.is_nt(r):
                lem = w.get("l") or ""
                if lem[:1].isupper() and len(lem) > 2:
                    out.add(f"name:{norm(lem)}")
            else:
                # Hebrew has no case and MACULA's part-of-speech field does not
                # separate proper nouns -- Moses is tagged plainly `noun`. The
                # English gloss DOES capitalise them, so that is the signal.
                gl = (w.get("g") or "").strip()
                if gl[:1].isupper() and (w.get("p") or "") == "noun":
                    k = strongkey("hebrew", w.get("s"))
                    for x in ((co.meta.get(k) or {}).get("greek") or [])[:3]:
                        g = norm((x.get("v") or "").strip(",.;·:"))
                        if len(g) > 2:
                            out.add(f"name:{g}")
    return out


# Predicates that bring something into existence or state it as existing.
# An image that is their argument is being spoken of LITERALLY.
EXISTENTIAL = {"γινομαι", "ειμι", "κτιζω", "ποιεω", "היה", "עשׂה", "ברא"}


def fam_register(co: Corpus, refs: list[str]) -> set[str]:
    """Angle 2 -- an image that changes register between the two passages.

    Not "both mention light" but **literal in one, symbolic in the other** --
    the physical thing becoming the image. The same shape as the serpent: a
    bronze snake on a pole in Num 21, the lifting up of the Son in John 3.

        Gen 1:3   אוֹר  הָיָה  "let it be"  comes into being -> LITERAL
        Jhn 1:5   φῶς  φαίνω  "shines"     acts             -> SYMBOLIC

    The key carries the register so that a match requires DIFFERENT registers
    on the same image; two literal mentions of light are not a connection.

    **UNMEASURED.** The literal/symbolic split below is a heuristic drawn from
    two examples. Marker harvests in this project have twice measured about 40%
    precision, so this needs a hand-marked set before it ranks anything a
    reader sees. `--rates` reports its base rate; that is not the same as
    knowing it is right.
    """
    out = set()
    for r in refs:
        for f in co.frames.get(r, []):
            lem = (f.get("lemma") or "")
            pred = norm(lem) if not _hebrew(lem) else lem
            for role in ("agent", "patient"):
                for a in (f.get(role) or []):
                    img = norm(a) if not _hebrew(a) else _greek_of(co, a)
                    if not img or img in FUNCTION or len(img) < 3:
                        continue
                    reg = "lit" if pred in EXISTENTIAL else "sym"
                    out.add(f"img:{img}:{reg}")
    return out


def _hebrew(s: str) -> bool:
    return any("֐" <= c <= "׿" for c in s or "")


_GREEK_OF: dict[str, str] = {}


def _greek_of(co: Corpus, heb: str) -> str:
    """A Hebrew frame argument, as the Greek the LXX used for it."""
    if heb in _GREEK_OF:
        return _GREEK_OF[heb]
    best = ""
    for k, v in co.meta.items():
        if (v.get("lemma") or "") == heb:
            g = ((v.get("greek") or [{}])[0].get("v") or "")
            best = norm(g.strip(",.;·:"))
            break
    _GREEK_OF[heb] = best
    return best


def fam_root(co: Corpus, refs: list[str]) -> set[str]:
    """Angle 3 -- words related by derivation, where the lemmas differ.

    The Word is an image of speech. λέγω and λόγος are the ordinary
    Greek e/o ablaut; Genesis says *said* eight times in chapter 1 and John
    makes the saying a person. Lemma matching cannot see it.

    Root matching rather than a distance model, deliberately: the relation is
    morphological and exact, and an embedding would also admit a cloud of
    merely-similar words -- which is the failure mode this whole file exists
    to avoid.
    """
    out = set()
    for r in refs:
        for w in co.flat(r):
            if w in FUNCTION or len(w) < 4:
                continue
            # The feature carries BOTH the root and the lemma that realised it,
            # so `agree` can require the two passages to have reached the same
            # root by DIFFERENT words. A shared root via the same lemma is just
            # a shared word, and counting it here reproduced the bag of words:
            # the first run gave Ecclesiastes 7 a root match against John's
            # prologue on ανθρ, αρχε, ευδε, λεγε.
            out.add(f"root:{_root(w)}|{w}")
    return out


_ABLAUT = str.maketrans({"ο": "ε", "ω": "ε", "η": "ε"})


def _root(w: str) -> str:
    """A crude stem: drop the ending, fold the e/o/eta ablaut grade.

    Crude on purpose. It must relate λεγ-/λογ- and nothing subtler; a cleverer
    stemmer would start relating words that merely look alike.
    """
    stem = w[:4]
    return stem.translate(_ABLAUT)


def fam_frame(co: Corpus, refs: list[str]) -> set[str]:
    """The shape of a proposition: predicate class plus its argument.

    Genesis 1:3 is two frames in sequence -- [said, agent=God] then [it was,
    agent=light] -- repeated at 1:6, 1:9 and 1:26. That is creation by
    speaking, stated as a formula and already extracted.

    Note what this cannot yet reach. John 1:3 is [came into being, agent=all
    things]; the `δι' αὐτοῦ` is absent because dia+genitive agency is not a
    recorded role. The reading wanted is that all things came through him, where him refers to the
    Word of God. Capturing that role, and resolving it with the existing
    `named` mechanism, is in BACKLOG.
    """
    out = set()
    for r in refs:
        for f in co.frames.get(r, []):
            lem = f.get("lemma") or ""
            pred = norm(lem) if not _hebrew(lem) else _greek_of(co, lem)
            if not pred:
                continue
            kind = "exist" if pred in EXISTENTIAL else "act"
            for a in (f.get("agent") or []):
                img = norm(a) if not _hebrew(a) else _greek_of(co, a)
                if img and img not in FUNCTION and len(img) > 2:
                    out.add(f"frm:{kind}:{img}")
    return out


# `θεός` and `κύριος` are COMMON NOUNS that English capitalises by convention,
# so the gloss test reads them as proper names and the family then fires on
# almost every pair -- Psalm 104 against Genesis 1 matched on `name:θεος`,
# which says nothing about either passage.
#
# A document-frequency ceiling was tried first and is WRONG: it also dropped
# Moses, who appears in hundreds of verses and is still exactly the kind of
# proper reference this family exists to catch. The problem was never that the
# word is common; it is that it is not a name. Excluding the artifact is right
# where excluding the common is not -- and it keeps to the project's rule of
# ranking rather than filtering, since nothing real is being cut.
DIVINE_TITLES = {"θεοσ", "θεου", "θεω", "θεον", "κυριοσ", "κυριου", "κυριω",
                 "κυριε", "κυριον", "υψιστοσ", "παντοκρατωρ"}
NAME_MAX_VERSES = 6000


FAMILIES = {
    "phrase": fam_phrase,
    "name": fam_name,
    "register": fam_register,
    "root": fam_root,
    "frame": fam_frame,
}

# Families that are measured and may rank; the rest are reported but do not
# contribute to the count until they have a precision figure.
MEASURED = {"phrase", "name", "root"}


# --------------------------------------------------------------------------


def features(co: Corpus, span: str) -> dict[str, set[str]]:
    refs = expand(span)
    out = {k: fn(co, refs) for k, fn in FAMILIES.items()}
    out["name"] = {x for x in out["name"]
                   if x[5:] not in DIVINE_TITLES
                   and co.name_df(x) <= NAME_MAX_VERSES}
    return out


def agree(a: dict[str, set[str]], b: dict[str, set[str]]
          ) -> dict[str, set[str]]:
    """Families in which the two passages share a feature.

    `register` is special: a match requires the SAME image in DIFFERENT
    registers, since two literal mentions of light are not a connection.
    """
    out = {}
    for k in FAMILIES:
        if k == "root":
            # Same root, different lemma -- the derivational link (λεγω/λογος).
            ra = collections.defaultdict(set)
            rb = collections.defaultdict(set)
            for x in a[k]:
                stem, lem = x[5:].split("|", 1)
                ra[stem].add(lem)
            for x in b[k]:
                stem, lem = x[5:].split("|", 1)
                rb[stem].add(lem)
            both = {f"root:{st}" for st in (set(ra) & set(rb))
                    if ra[st] != rb[st] and (ra[st] - rb[st])
                    and (rb[st] - ra[st])}
        elif k == "register":
            la = {x.rsplit(":", 1)[0] for x in a[k] if x.endswith(":lit")}
            sb = {x.rsplit(":", 1)[0] for x in b[k] if x.endswith(":sym")}
            lb = {x.rsplit(":", 1)[0] for x in b[k] if x.endswith(":lit")}
            sa = {x.rsplit(":", 1)[0] for x in a[k] if x.endswith(":sym")}
            both = (la & sb) | (lb & sa)
        else:
            both = a[k] & b[k]
        if both:
            out[k] = both
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pair", nargs=2, metavar=("A", "B"))
    ap.add_argument("--rates", action="store_true",
                    help="base rate and independence of each family")
    ap.add_argument("--cases", action="store_true",
                    help="the four regression cases from BACKLOG")
    a = ap.parse_args()

    print("loading …", flush=True)
    co = Corpus()
    print(f"  {len(co.words):,} verses, {len(co.frames):,} with frames\n")

    if a.rates:
        import random
        random.seed(7)
        sample = random.sample(sorted(co.words), 400)
        hit = {k: 0 for k in FAMILIES}
        per = {}
        for r in sample:
            f = features(co, r)
            per[r] = f
            for k, v in f.items():
                hit[k] += bool(v)
        print("family        fires on   features/verse   measured?")
        for k in FAMILIES:
            n = sum(len(per[r][k]) for r in sample) / len(sample)
            print(f"  {k:<11} {hit[k]/len(sample):>6.1%} {n:>14.1f}"
                  f"        {'yes' if k in MEASURED else 'NO'}")
        print("\nindependence (lift of firing together; 1.0 = independent):")
        ks = sorted(FAMILIES)
        for i, x in enumerate(ks):
            for y in ks[i + 1:]:
                px = hit[x] / len(sample)
                py = hit[y] / len(sample)
                both = sum(1 for r in sample if per[r][x] and per[r][y])
                pb = both / len(sample)
                if px and py:
                    lift = pb / (px * py)
                    flag = "  <-- not independent" if lift > 1.6 else ""
                    print(f"  {x:<9} x {y:<9} {lift:5.2f}{flag}")
        return 0

    pairs = [tuple(a.pair)] if a.pair else []
    if a.cases or not pairs:
        pairs = [("Gen.1.1-5", "Jhn.1.1-5"),
                 ("Num.21.9", "Jhn.3.14"),
                 ("Num.18.12", "Rev.6.6"),
                 ("Psa.104.1-9", "Gen.1.1-5"),
                 ("Ecc.7.1-9", "Jhn.1.1-5")]
    for x, y in pairs:
        fa, fb = features(co, x), features(co, y)
        sh = agree(fa, fb)
        n = len([k for k in sh if k in MEASURED])
        print(f"{x} <-> {y}   {n} measured famil{'y' if n == 1 else 'ies'}"
              f"  (+{len(sh) - n} unmeasured)")
        for k, v in sorted(sh.items()):
            tag = "" if k in MEASURED else "  [UNMEASURED]"
            print(f"    {k:<9} {', '.join(sorted(v)[:5])}{tag}")
        if not sh:
            print("    (nothing)")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
