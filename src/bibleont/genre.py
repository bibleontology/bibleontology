"""What kind of writing a passage is, as a vector, counted from the text.

2026-09-03: the idea is that not every type of passage is the same, and that
classifiers measure that precisely -- not in coarse-grained terms but fine
tuned: Job with a narrative story rating of 27, dialog rating of 72, logical
discourse rating of 51 and poetry rating of 47, while Romans 1-3 has a logical
discourse rating of 87 and a narrative rating of 1, with a hyperbolic factor
of 80 in the logical discourse rating.

## Why this is free

Every dimension he named is a countable feature of the tagged text, which is
already on disk for 29,126 verses with morphology on every word. Principle 36:
prove a task is not deterministic before giving it to a model. This one is not.

    narrative     wayyiqtol in Hebrew -- the consecutive past that *is* Hebrew
                  narration -- and aorist indicative in Greek
    dialog        verbs of speaking, and first- and second-person forms, which
                  are what a quotation is made of
    poetry        the athnach splitting a verse into balanced cola, with
                  narration absent. Hebrew verse is parallelism, not metre
    discourse     connective density: ki, lakhen, gar, oun, ara, dio. An
                  argument is joins between claims, and the joins are lexical
    rhetorical    interrogatives, and negatives that expect the answer "no".
                  The writer's rhetorical questions have to be recognised --
                  a rhetorical question minted as an assertion inverts the
                  argument

## What it replaces

`prefix.mode_of` returns "concept" for all 66 books. It is the emptiest thing
in the pipeline: a single mode, chosen once, describing a genealogy and an
apocalypse identically.

## What it is FOR, and the test that decides whether it is real

Routing. The cost function has to weigh heavily here -- this is about the
intelligence of the swarm, and one heavyweight process cannot fire
constantly. So the selection rule is **the cheapest specialist whose
measured accuracy on this profile clears the bar**, never the most accurate
one; otherwise every route collapses to the expensive model and the swarm is
decorative.

**A vector nobody acts on is astrology.** The honest test is not whether these
numbers look right -- Job scoring 72 on dialog is satisfying and proves
nothing. It is whether the vector *predicts which technique wins* on a passage
it has not seen. If the same specialist wins regardless of profile, the
classifier is decoration and should be deleted rather than admired.
"""
from __future__ import annotations

import collections
import functools
import pathlib
import re
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parents[2]
STEP = ROOT / "data" / "raw" / "stepbible"
ATH = "֑"                      # athnach: the main verse divider

DIMS = ("narrative", "dialog", "poetry", "discourse", "rhetorical",
        "figurative", "vision")

# Bump on ANY change to a counting rule, a lemma set, or a scale factor.
#
# 2026-09-03: it is not necessary to know precisely what a classification
# means, as long as the signature is established across the board evenly and
# remains constant as an experimental input.
#
# That is the right bar and it has a consequence. These numbers are a feature,
# not an interpretation -- nobody has to agree that Revelation is "narrative",
# only that the same measurement was applied everywhere. But a feature that
# drifts silently is worse than a crude one that holds still, because every
# experiment scored against an earlier version becomes incomparable without
# anything looking wrong.
#
# So the version travels with the score, exactly as `prefix.revision()` travels
# with a batch. A result is only comparable to another result under the same
# GENRE_VERSION.
#
#   v1  narrative counted only the aorist indicative in Greek and nothing at
#       all in Hebrew, where the segmented morph HC/Vqw3ms hid the verb behind
#       the waw. Hebrew scored 0 for every book -- a constant, carrying no
#       information, which is a real defect rather than a naming quarrel.
#   v2  Hebrew reads the verb segment; Greek counts both indicative past
#       tenses, aorist and imperfect. Mark 15 moved 31 -> 58.
#   v3  adds `figurative`. 2026-09-03: Matthew has a big figurative section
#       with parable after parable, which is dialog but a very special kind
#       of dialog with a pattern to it that has to be understood for what it
#       is. v2 read Matthew 13 as ordinary
#       narrative-with-dialog. Parables announce themselves lexically:
#       Matthew 13 carries 19 parable/likeness words against 1-3 in every
#       other chapter.
#   v4  adds `vision`. 2026-09-03, on Daniel scoring 0 for narrative: its
#       historical narrative should be low for a different reason -- it is a
#       vision or dream. v3 could say only that Daniel 7
#       was not narration; it could not say what it WAS.
#
#       This dimension is built on LEMMAS, not morphology, and that is
#       the architectural point: 94% of Aramaic lemmas carry Hebrew
#       lexicon numbers, so a lemma dimension crosses all three languages
#       for free, while a morphology dimension needs rules per language.
#       Daniel 2-7 gets a vision score without a line of Aramaic grammar.
GENRE_VERSION = "v4"

# Hebrew connectives that join claims rather than things.
H_JOIN = {"H3588",   # ki -- for, because, that
          "H3651",   # ken -- so, thus
          "H0518",   # im -- if
          "H6440J",  # before/because of
          "H4616",   # ma'an -- in order that
          "H5921A"}  # al -- upon, concerning
H_ASK = {"H4100",    # mah -- what
         "H4310",    # mi -- who
         "H0335",    # ay -- where
         "H4069",    # maddua -- why
         "H3808"}    # lo -- not (carries negated questions)
H_SAY = {"H0559",    # amar -- to say
         "H1696",    # dabar -- to speak
         "H7121",    # qara -- to call
         "H6030"}    # anah -- to answer

G_JOIN = {"G1063",   # gar -- for
          "G3767",   # oun -- therefore
          "G0686",   # ara -- so then
          "G1352",   # dio -- wherefore
          "G1487",   # ei -- if
          "G2443",   # hina -- in order that
          "G3754",   # hoti -- that, because
          "G1161"}   # de -- but, and
G_ASK = {"G5101",    # tis -- who, what
         "G3361",    # me -- not (expects the answer "no")
         "G3780",    # ouchi -- not indeed
         "G4459"}    # pos -- how
G_FIG = {"G3850",   # parabole -- parable
         "G3664",   # homoios -- like ("the kingdom of heaven is like")
         "G3666",   # homoioo -- to liken
         "G3945",   # paraballo -- to compare
         "G1503",   # eiko -- to resemble
         "G3942"}   # paroimia -- figure, allegory. JOHN'S word: he
                    # never uses parabole, so the Good Shepherd scored 0
                    # for figurative until this was added. A vocabulary
                    # signal inherits its author's vocabulary.
H_FIG = {"H4912",   # mashal -- proverb, parable
         "H1819",   # damah -- to be like
         "H2420",   # chidah -- riddle, dark saying
         "H4426"}   # melitsah -- figure, enigma

H_VIS = {"H2472", "H2472A", "H2472B",   # chalom -- dream
         "H2377", "H2384",              # chazon, chizzayon -- vision
         "H2493", "H2493A", "H2493B",   # chelem -- dream (ARAMAIC)
         "H2376",                       # chezev -- vision (ARAMAIC)
         "H4759A", "H4758", "H4236"}    # mareh -- vision, appearance
G_VIS = {"G3705",   # horama -- vision
         "G3706",   # horasis -- sight, vision
         "G3677",   # onar -- dream
         "G1798",   # enypnion -- dream
         "G3701"}   # optasia -- vision

G_SAY = {"G3004",    # lego -- to say
         "G2036",    # epo -- said
         "G2980",    # laleo -- to speak
         "G0611"}    # apokrinomai -- to answer


@dataclass
class Profile:
    ref: str
    words: int
    scores: dict
    version: str = GENRE_VERSION

    def __str__(self) -> str:
        return (f"{self.ref:12} "
                + "  ".join(f"{d[:4]} {self.scores.get(d, 0):>3}" for d in DIMS)
                + f"   ({self.words} words)")

    def top(self) -> str:
        return max(DIMS, key=lambda d: self.scores.get(d, 0))


@functools.lru_cache(maxsize=80)
def _rows(book_code: str) -> tuple:
    """Every tagged word of a book: (ref, pointed, gloss, lemma, morph).

    Cached, because profiling a chapter re-scanned every TAHOT and TAGNT
    file from disk. Fine for one lookup and hopeless for the 1,189
    chapters of the canon, which is what clustering needs.
    """
    out = []
    for f in list(STEP.glob("TAHOT*.txt")) + list(STEP.glob("TAGNT*.txt")):
        greek = f.name.startswith("TAGNT")
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not line.startswith(book_code + "."):
                    continue
                c = line.rstrip("\n").split("\t")
                if len(c) < 6:
                    continue
                ref = c[0].split("#")[0]
                if greek:
                    # Greek keeps "G1234=CONJ" in column 3; no column 8.
                    tag = c[3] if len(c) > 3 else ""
                    lem = tag.split("=")[0].strip()
                    morph = tag.split("=")[1].strip() if "=" in tag else ""
                    pointed, gloss = c[1], c[2]
                else:
                    lem = re.sub(r"[^HG0-9A-Z]", "", (c[8] if len(c) > 8 else "").split("\\")[0])
                    morph = c[5].strip()
                    pointed, gloss = c[1], c[3]
                if lem:
                    out.append((ref, pointed, gloss, lem, morph))
    return tuple(out)


def profile(book_code: str, chapter: int | None = None,
            version: str = GENRE_VERSION) -> Profile:
    """A genre vector for a book or one chapter, 0-100 per dimension.

    Every superseded version stays computable rather than being described in a
    comment. 2026-09-03: the vector can evolve as long as the original remains
    as a control; the key is speed of experimentation.

    A changelog cannot be re-run. Keeping v1 executable means any experiment
    scored under it can be rescored under v2 on demand, so a feature change is
    measured against the thing it replaced instead of being asserted to be
    better -- and a version that turns out worse is one argument away from
    being restored.
    """
    rows = [r for r in _rows(book_code)
            if chapter is None or r[0].split(".")[1] == str(chapter)]
    if not rows:
        return Profile(book_code, 0, {d: 0 for d in DIMS}, version)

    greek = rows[0][3].startswith("G")
    join = G_JOIN if greek else H_JOIN
    ask = G_ASK if greek else H_ASK
    say = G_SAY if greek else H_SAY
    fig = G_FIG if greek else H_FIG
    vis = G_VIS if greek else H_VIS

    n = len(rows)
    verbs = narr = dial = joins = asks = says = figs = viss = 0
    persons = 0
    for _, _, _, lem, morph in rows:
        if greek:
            if morph.startswith("V"):
                verbs += 1
                # Greek narration is carried by the indicative past tenses,
                # and there are two of them. Aorist (V-AAI, V-2AAI) is the
                # event; imperfect (V-IAI) is ongoing past action, which Mark
                # uses constantly -- "he was saying", "they were crying out".
                # Counting only the aorist found 33 of Mark 15's narrative
                # verbs and missed 29, scoring a trial narrative at 31.
                # The tense letter must be A or I; P (present) must not match,
                # since a bare "AI" test counted every present active
                # indicative and scored Romans 3 -- an argument with no story
                # in it -- at 67.
                if version == "v1":
                    if "AI" in morph:          # v1: also caught present
                        narr += 1
                elif re.match(r"V-\d?[AI][APM]I", morph):
                    narr += 1
            if re.search(r"-[12][SP]", morph) or morph.startswith(("P-1", "P-2")):
                persons += 1
        else:
            # Hebrew morphs are segmented: "and he said" is HC/Vqw3ms, with the
            # waw-consecutive as its own segment. Looking only at the first
            # three characters saw "HC/" and found no verb, which is why every
            # Hebrew book scored 0 for narrative including Genesis 1.
            if version == "v1":
                # v1 looked only at the first three characters, so the
                # segmented "HC/Vqw3ms" hid the verb behind the waw and
                # Hebrew narrative scored 0 for every book.
                if "V" in morph[:3]:   # v1, unchanged
                    verbs += 1
                    if re.match(r"HV.w", morph):
                        narr += 1
            else:
                segs = morph.split("/")
                # Aramaic (Daniel 2:4b-7:28, Ezra 4-7) is tagged with an
                # "A" prefix and the same verb structure. Stripping only
                # "H" made every Aramaic chapter score narrative 0, so
                # Daniel's largest detected shifts were its LANGUAGE
                # boundaries at 2 and 8 -- real, but not what was asked --
                # and the genre turn at 6/7 was invisible.
                vseg = next((x for x in segs
                             if x.lstrip("HA").startswith("V")), "")
                if vseg:
                    verbs += 1
                    # Vqw3ms -- the wayyiqtol, which *is* Hebrew narration.
                    if re.match(r"H?V.w", vseg):
                        narr += 1
            if re.search(r"[12](?:cs|ms|fs|cp|mp|fp)", morph):
                persons += 1
        if lem in join:
            joins += 1
        if lem in ask:
            asks += 1
        if lem in say:
            says += 1
        if lem in fig:
            figs += 1
        if lem in vis:
            viss += 1

    # Poetry: how many verses split into balanced cola on the athnach, with
    # narration absent. Hebrew verse is parallelism; Greek prose has neither.
    byv = collections.defaultdict(list)
    for r in rows:
        byv[r[0]].append(r)
    balanced = 0
    for ws in byv.values():
        idx = [i for i, w in enumerate(ws) if ATH in w[1]]
        if not idx:
            continue
        k = idx[0]
        a, b = k + 1, len(ws) - k - 1
        if a and b and min(a, b) / max(a, b) >= 0.55:
            balanced += 1
    versecount = max(len(byv), 1)

    def pct(x, of, scale=1.0):
        return max(0, min(100, round(100 * scale * x / max(of, 1))))

    scores = {
        "narrative": pct(narr, verbs, 1.6),
        "dialog": pct(says * 6 + persons, n, 1.1),
        "poetry": pct(balanced, versecount) if not greek else
                  pct(balanced, versecount, 0.5),
        "discourse": pct(joins, n, 6.0),
        "rhetorical": pct(asks, n, 12.0),
        # A parable is dialog in form and figure in function.
        # The vocabulary is the tell and it is sparse, so the
        # scale is steep: 19 words in 1,000 is a parable chapter.
        "figurative": pct(figs, n, 45.0),
        # Sparse like the figurative signal, and for the same
        # reason: a vision announces itself once and then runs
        # for a chapter.
        "vision": pct(viss, n, 55.0),
    }
    # Narration and parallelism are rivals: a chapter cannot be mostly both.
    if scores["narrative"] > 55:
        scores["poetry"] = round(scores["poetry"] * 0.5)
    return Profile(f"{book_code}{'' if chapter is None else ' ' + str(chapter)}",
                   n, scores, version)


def main(argv: list[str] | None = None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    cases = argv or ["Job:38", "Job:1", "Rom:3", "Rom:1", "Gen:1", "Gen:5",
                     "Psa:23", "Psa:119", "Pro:10", "Mrk:15", "Rev:1"]
    ver = next((a.split("=", 1)[1] for a in argv if a.startswith("--version=")),
               GENRE_VERSION)
    cases = [c for c in cases if not c.startswith("--")]
    print(f"genre {ver} -- comparable only against the same version\n")
    print(f"{'passage':12} " + "  ".join(f"{d[:4]:>8}" for d in DIMS)
          + "   words  dominant")
    for c in cases:
        b, _, ch = c.partition(":")
        p = profile(b, int(ch) if ch else None, ver)
        print(f"{p.ref:12} "
              + "  ".join(f"{p.scores[d]:>8}" for d in DIMS)
              + f"   {p.words:>5}  {p.top()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def shifts(book_code: str, chapters: range | None = None,
           version: str = GENRE_VERSION) -> list:
    """Where a book changes kind, by distance between adjacent profiles.

    2026-09-03: broad book-wide ratings are fine but must be aware that a
    book like Daniel can take a turn, and more and more the emphasis will be
    on functions that can be applied more dynamically to a smaller passage to
    detect these shifts.

    A book-level vector is an average, and an average over a book that changes
    kind describes neither half. Daniel is court narrative through chapter 6
    and apocalyptic from 7. Job is prose frame, then thirty-nine chapters of
    poetry, then prose again. A single number for either is the mean of two
    things that never co-occur.

    **This is testable rather than merely plausible**, which is the point:
    the boundaries are known independently -- Job 2/3 and 42:6/7, Daniel 6/7,
    Isaiah 39/40 -- so a detector either finds them or does not.

    Returns (chapter, distance-from-previous, profile) sorted by chapter, with
    the distance being plain Euclidean over the five dimensions.
    """
    out = []
    prev = None
    ch = 1
    while True:
        if chapters is not None and ch not in chapters:
            if chapters and ch > max(chapters):
                break
            ch += 1
            continue
        p = profile(book_code, ch, version)
        if not p.words:
            if ch > 1:
                break
            ch += 1
            if ch > 3:
                break
            continue
        d = 0.0
        if prev is not None:
            d = sum((p.scores[k] - prev.scores[k]) ** 2 for k in DIMS) ** 0.5
        out.append((ch, round(d, 1), p))
        prev = p
        ch += 1
        if ch > 160:
            break
    return out
