"""References across the testaments, through the Greek the Septuagint used.

2026-09-16, on the sequence cards: what would it take to get "refers to" as
well, given that the BSB cross references exist.

The Berean notes are 2,026 parallel-passage references, made by an editor for
readers. They are precise and they are sparse, and they do not contain the case
used as the worked example: John 3:14, *"just as Moses lifted up the serpent in
the wilderness"*, carries no note back to Numbers 21.

## Why the existing allusion layer cannot reach it

`out/allusions.jsonl.gz` holds 141,365 links and **exactly zero cross the
testaments**, because it matches shared LEMMAS and the testaments are in
different languages. `נָחָשׁ` can never equal `ὄφις` however low the threshold
goes. That was measured on 2026-09-15 and is a property of the method, not a
tuning problem.

## The bridge that is already on disk

MACULA Hebrew records, per word, the Greek the **Septuagint** used for it —
the `greek` attribute, carried into `out/lemma-meta.json` by
`tools/interlinear.py`. **5,619 Hebrew lemmas have one.**

That is the join the lemma layer lacked, and it is the right one historically:
the New Testament writers quote the Greek Old Testament, so a quotation looks
like a NT verse reusing the LXX's own vocabulary for a particular passage.

Tested on that example before anything was built:

    Num 21:8-9   נָחָשׁ  serpent  ->  LXX ὄφις
    John 3:14    ὄφις
    overlap:     ὄφις, ἄνθρωπος, ἐν, ὁ

Which is the method working and the reason it needs weighting: `ὄφις` carries
the link and `ὁ` carries nothing.

## Scoring

A shared word is worth `log(N / verses containing it)` over the Greek New
Testament, so a common article counts for almost nothing and a rare noun counts
for a great deal. A link needs at least two content words and a score above the
floor, because one rare word in common is a coincidence and two is a pattern.

## The source column is corrupted, and it was silently breaking the join

Two character-level faults in MACULA's `greek` column, both found 2026-09-16
by testing the worked cases rather than by reading the data:

**1. Case and accents.** The column is lowercase and unaccented (`μωυσῆς`)
while the Greek NT lemma column is capitalised and accented (`Μωϋσῆς`). They
never compared equal, so **every proper name dropped out of the join** -- the
one class of word that reliably crosses the testaments. On the serpent
case, Moses, wilderness and serpent were enough that it should have been
evaluated automatically. It was all there; the strings just never met.

**2. Chi is written as xi.** `ἀρξή` for ἀρχή, `ξρυσίον` for χρυσίον, `ἄρξοντες`
for ἄρχοντες, `ἰσξὺν` for ἰσχὺν, `τεῖξος` for τεῖχος, `ξαλκοῦ` for χαλκοῦ.
**1,284 of 16,226 renderings are affected and 688 are clean**, so it is a
partial corruption, not a transliteration convention.

`norm()` folds case, strips accents, and maps ξ to χ. The fold slightly
over-merges genuine xi (δόξα, σάρξ, ξύλον) but no real collision exists --
there is no δόχα -- and without it Gen 1:1 and John 1:1 share NOTHING, because
the one word they have in common is ἀρχή.

**This reaches past this tool.** `h2580` is חֵן, grace, and its LXX rendering
is stored as `ξάριν, ξάρις` -- so the corruption was breaking χάρις, one of the
three word families being fast-tracked.

## MEASURED: what it reaches, and what it cannot

With the trigger inverted -- the NT verse must DECLARE a reference, and
vocabulary only ranks which passage -- **382 NT verses carry an explicit
referring construction** (γέγραπται 181, ἵνα πληρωθῇ 86, καθώς...οὕτω 33,
τύπος 14, ἀλληγορέω 1). That is the text saying it points somewhere, which is
readable and checkable, rather than a similarity score standing in for one.

On the earlier scoring the verdict was that it really is pattern matching under
a different name. That was right, and the fix is not a better weighting. Shared vocabulary
cannot distinguish resembling from citing; only the citing construction can.
Vocabulary is then demoted to retrieval -- which of the candidate passages --
where being approximate is harmless.

Matched against EPISODES rather than verses, because a reference names things
that a single verse does not hold together (John 3:14 has Moses, wilderness and
serpent; Num 21:9 has the serpent and the episode has the rest):

    Jhn 3:14  just as...so   -> Num 21:6-8, Num 21:9-18   μωυσης, οφις
    Mat 12:40 just as...so   -> Jon 1:15-2:9              ιωνας, κοιλια, τρεις
    Gal 4:24  allegorically  -> Exo 31:18-32:2 (Sinai)    σινα, ορος, δυο

**Where it fails, and why that is structural.** Reach is proportional to
lexical reuse:

    Psalm 104  -> Gen 1   #18 of 929    151 shared: δρακων, αβυσσος, ερπετα
    John 1:1-5 -> Gen 1   #96 of 696      2 shared: αρχη

John's prologue alludes to Genesis 1 by its opening phrase and by the
creation-by-speech pattern. Genesis says God SAID (εἶπεν); John says the WORD
(λόγος). **There is almost no shared vocabulary, so no lexical method can find
it** -- and a threshold loose enough to admit it admits everything. That is a
property of the allusion, not a tuning problem, and it is the honest boundary
of what this tool can claim.

## STILL NOT WIRED INTO THE READER

The retrieval is good where words are reused and silent where they are not, so
what a reader would see is uneven in a way the card cannot explain. A model
may adjudicate (stamping the reference with a worker model is acceptable), and
that is the right shape: 382 candidates is a small, affordable
set, the trigger is in the text, and the model judges a checkable question
(does this declared reference point at this episode) rather than inventing a
theme. Recorded in BACKLOG; not built here.

The ORIGINAL scoring, kept as the record of what not to do -- 5,970 candidates
with no trigger, ranked purely on shared vocabulary:

    20.6  1Ch 26:5  -> Rev 21:20   eighth, seventh, sixth
    18.6  Num 18:12 -> Rev 6:6     oil, grain, wine
    18.6  Neh 5:11  -> Rev 6:6     oil, grain, wine
    18.6  Joel 1:10 -> Rev 6:6     oil, grain, wine
    ...
     6.3  Num 21:9  -> John 3:14   serpent          <- below the floor

The head of the list is passages that mention the same COMMODITIES, and a
roster of sons matched to the foundation stones of the new Jerusalem on the
ordinals. None of those is a reference. The worked example -- the case the
method was built for -- sits below the threshold, because a real citation can
turn on a single rare word while topical overlap accumulates several ordinary
ones.

The head is passages that mention the same COMMODITIES, and a roster of sons
matched to the foundation stones of the new Jerusalem on the ordinals. None is
a reference, and the worked case sat below the threshold. Volume of shared
vocabulary is not evidence of citation at any weighting, which is what the
inversion above exists to fix.

**Nothing from this is wired into the reader.** A list that looks like
references and is mostly shared shopping lists is exactly the failure this
project exists to avoid -- authoritative-looking where it is empty.

    python tools/lxxbridge.py --check          # the worked example
    python tools/lxxbridge.py --write
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

# Greek words too common to carry a link. Not a judgement about interest -- the
# IDF weighting already handles that -- but a floor, because a verse pair
# sharing only these has shared nothing and would otherwise pass on volume.
STOP = {"ὁ", "καί", "δέ", "ἐν", "εἰς", "ἐκ", "αὐτός", "οὗτος", "ὅς", "τε",
        "γάρ", "μέν", "οὐ", "μή", "ὅτι", "ἀλλά", "σύ", "ἐγώ", "ἡμεῖς",
        "ὑμεῖς", "εἰμί", "πρός", "ἐπί", "κατά", "διά", "περί", "ἀπό", "σύν",
        "ὑπό", "παρά", "ἵνα", "ὡς", "εἰ", "ἄν", "τις", "πᾶς", "ποιέω",
        "λέγω", "ἔχω", "γίνομαι", "ἄνθρωπος", "θεός", "κύριος"}


def norm(w):
    """Fold case, accents, and MACULA's chi/xi corruption. See the docstring.

    Without this the join drops every proper name and every word containing
    chi, which between them are most of what actually crosses the testaments.
    """
    d = unicodedata.normalize("NFD", w or "")
    d = "".join(c for c in d if not unicodedata.combining(c))
    return unicodedata.normalize("NFC", d).casefold().replace("ξ", "χ")


NSTOP = {norm(w) for w in STOP}


def strongkey(lang, s):
    s = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", s or ""))
    return (lang[:1] + s) if s else None


def load():
    il = {}
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if d.get("ref"):
            il[d["ref"]] = d["words"]
    meta = json.loads((OUT / "lemma-meta.json").read_text(encoding="utf-8"))
    return il, meta


def lxx_of(meta, key, cap=4):
    """-> {Greek lemmas the Septuagint used for this Hebrew word}.

    Capped at the commonest few. A Hebrew word rendered a dozen ways in the
    LXX is rendered loosely, and taking all of them would let it match almost
    anything.
    """
    v = meta.get(key) or {}
    out = set()
    for x in (v.get("greek") or [])[:cap]:
        w = norm((x.get("v") or "").strip(",.;·:"))
        if w:
            out.add(w)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--min-words", type=int, default=2)
    ap.add_argument("--floor", type=float, default=11.0)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    il, meta = load()
    ot = {r: w for r, w in il.items() if r.split(".")[0] not in NT}
    nt = {r: w for r, w in il.items() if r.split(".")[0] in NT}

    # What each verse offers, as Greek.
    def nt_words(ws):
        return {norm(w["l"]) for w in ws
                if w.get("l") and norm(w["l"]) not in NSTOP
                and len(norm(w["l"])) > 2}

    ntv = {r: nt_words(w) for r, w in nt.items()}
    df = collections.Counter()
    for s in ntv.values():
        df.update(s)
    n = max(len(ntv), 1)
    idf = {w: math.log(n / c) for w, c in df.items()}

    otv = {}
    for r, ws in ot.items():
        got = set()
        for w in ws:
            k = strongkey("hebrew", w.get("s"))
            if k:
                got |= lxx_of(meta, k)
        otv[r] = {x for x in got if x not in NSTOP and len(x) > 2}

    if a.check:
        for src, dst in (("Num.21.9", "Jhn.3.14"), ("Num.21.8", "Jhn.3.14")):
            both = otv.get(src, set()) & ntv.get(dst, set())
            sc = sum(idf.get(w, 0) for w in both)
            print(f"  {src} -> {dst}  score {sc:5.1f}  "
                  f"{', '.join(sorted(both)) or '(nothing)'}")
        return 0

    # Index the NT by word so the sweep is not 23,000 x 8,000.
    where = collections.defaultdict(set)
    for r, s in ntv.items():
        for w in s:
            if idf.get(w, 0) > 3.0:          # only distinctive words index
                where[w].add(r)

    links = []
    for src, s in otv.items():
        hits = collections.Counter()
        for w in s:
            for r in where.get(w, ()):
                hits[r] += 1
        for dst, k in hits.items():
            if k < a.min_words:
                continue
            both = s & ntv[dst]
            sc = sum(idf.get(w, 0) for w in both)
            if sc >= a.floor:
                links.append((sc, src, dst, sorted(both, key=lambda w:
                                                   -idf.get(w, 0))[:6]))
    links.sort(reverse=True)
    print(f"{len(links):,} candidate references "
          f"({a.min_words}+ shared words, score {a.floor}+)\n")
    for sc, src, dst, both in links[:a.top]:
        print(f"  {sc:5.1f}  {src:<12} -> {dst:<12} {', '.join(both)}")

    if a.write:
        p = OUT / "lxx-references.jsonl.gz"
        with gzip.open(p, "wt", encoding="utf-8") as f:
            f.write(json.dumps({
                "_source": "MACULA Hebrew/Greek, Clear Bible, CC BY 4.0 -- the "
                           "`greek` attribute records the Septuagint's "
                           "rendering of each Hebrew word.",
                "_note": "CANDIDATE references from the Old Testament to the "
                         "New, matched on the Greek the LXX used, weighted by "
                         "rarity in the Greek NT. Evidence that a passage is "
                         "in view, NOT proof of citation -- the shared words "
                         "are given so a reader can judge. See "
                         "tools/lxxbridge.py."}) + "\n")
            for sc, src, dst, both in links:
                f.write(json.dumps({"ot": src, "nt": dst,
                                    "score": round(sc, 2),
                                    "shared": both},
                                   ensure_ascii=False) + "\n")
        print(f"\n  -> {p.relative_to(ROOT)}  {len(links):,} links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
