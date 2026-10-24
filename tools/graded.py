"""The three graded tests, as a harness rather than a scratch script.

2026-09-10: three tests of increasing difficulty were set instead of asking
for a metric, and they located the ceiling precisely:

    EASY    the sea calmed: Jonah 1 and Jesus stilling the storm
    MEDIUM  the Sermon on the Mount, its Old Testament references
    HARD    Psalm 32:1-5 in three directions -- back to David's story,
            across to a peer psalm, forward to a citation

They were run from scratch scripts that did not survive the session, so the
numbers were recorded and the method was not. That is exactly the
shape of a result nobody can check. This module is the repair: the same three
tests, the recorded baseline beside each, and a diff.

## Baselines, as recorded on 2026-09-10

    EASY    PASS  Jon 1:4 -> Mat 8:24, Jon 1:15 -> Luk 8:24, after the
                  cross-testament layer was regated on RARITY instead of the
                  COUNT of shared glosses. Mat 5:21 shares only `murder`
                  with Exo 20:13 and a count gate discarded it.
    MEDIUM  part  the antitheses resolve; the structural references do not
    HARD    fail  backlink: 2Sa 24 outranks 2Sa 12
                  peer:     Psa 51 at rank 6 of the psalms
                  forward:  Rom 4 quotes Psa 32:1-2 verbatim

**The hard backlink may be unfair and that is recorded, not hidden.** Psalm
51's superscription names Nathan and Bathsheba; Psalm 32's names nothing. The
link to 2 Samuel 12 is a traditional reading, not a stated fact, and David
confesses in 2 Samuel 24 as well. Scoring it as a miss was defensible once and
is worth re-examining every time this runs.

## What it measures

One metric throughout: IDF-weighted shared content glosses. Glosses rather than
lemmas because the Sermon and the psalm citation cross the language boundary,
and a Hebrew lemma and a Greek lemma have nothing to compare.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"

# Words that carry no topic. A length filter was used for this once and let
# `from`, `with`, `your`, `them` carry a whole comparison on their own.
STOP = {
    "that", "this", "they", "them", "their", "there", "then", "than", "with",
    "from", "have", "has", "had", "will", "shall", "was", "were", "been",
    "your", "yours", "you", "and", "the", "for", "not", "but", "all", "any",
    "who", "whom", "which", "what", "when", "into", "unto", "upon", "over",
    "him", "his", "her", "she", "its", "our", "out", "are", "his", "one",
    "also", "such", "same", "because", "about", "before", "after", "himself",
    "it", "he", "of", "to", "in", "on", "at", "by", "as", "is", "be", "my",
    "me", "we", "us", "a", "an", "or", "so", "if", "do", "did", "does",
}


def rows(name):
    p = OUT / name
    if not p.exists():
        return
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                if not any(k.startswith("_") for k in d):
                    yield d


# Content parts of speech. The gloss of a preposition or a determiner is a
# function word in English too, and including them let `from`, `with`, `your`
# and `them` carry an entire passage comparison once already.
CONTENT_POS = {"verb", "noun", "adj", "adjective", "name", "adv"}


def load_vocab():
    """ref -> set of content glosses, for BOTH testaments.

    NOT from `cola.jsonl.gz`. That layer splits at Masoretic accents and is
    therefore Hebrew only -- 23,213 verses, no New Testament. The first run of
    this harness scored 0/3 on EASY and 0/6 on MEDIUM for exactly that reason:
    every Gospel verse in both tests was simply absent, and the harness
    reported it as "missing from the layer" rather than as a failure, which is
    the only reason the cause was visible at all.

    `interlinear.jsonl.gz` carries all 31,156 verses across 66 books with
    MACULA's own English glosses, which is one vocabulary across the language
    boundary. That boundary is the whole point of the Sermon and the Psalm 32
    forward link.
    """
    lem = {}
    for d in rows("interlinear.jsonl.gz"):
        w = set()
        for word in d.get("words", []):
            if (word.get("p") or "").lower() not in CONTENT_POS:
                continue
            for x in (word.get("g") or "").lower().replace(".", " ").split():
                x = x.strip("[](),;:'\"-")
                if len(x) > 2 and x not in STOP and not x.isdigit():
                    w.add(x)
        if w:
            lem[d["ref"]] = w
    return lem


def idf_of(lem):
    df = collections.Counter()
    for s in lem.values():
        df.update(s)
    n = max(len(lem), 1)
    return {w: math.log(n / c) for w, c in df.items()}


def mass(a, b, idf):
    """Rarity mass of what two vocabularies share.

    Deliberately NOT a count. Jonah 1:4 and Matthew 8:24 share three glosses
    and Matthew 5:21 shares one with Exodus 20:13; both are right and a count
    gate threw both away. What matters is how rare the shared words are.
    """
    sh = a & b
    return sum(idf.get(w, 0) ** 2 for w in sh), sh


def chapter_of(ref):
    b, c, _ = ref.split(".")
    return f"{b}.{c}"


def polarity_index():
    """ref -> (n_negative, n_total) over its predicate-argument tuples.

    Added 2026-09-11. Nothing downstream read polarity until this.
    """
    out = collections.defaultdict(lambda: [0, 0])
    for d in rows("frames.jsonl.gz"):
        out[d["ref"]][1] += 1
        if d.get("polarity") == "negative":
            out[d["ref"]][0] += 1
    return out


def speech_act(pol_rows):
    """ref -> the set of (polarity, prohibition) shapes a verse asserts.

    This is the sharp use of the new fields, and the chapter-level negation
    RATE tried first is the blunt one. "You shall not murder" is not merely a
    verse containing a negation: it is an ABSOLUTE PROHIBITION, and so is the
    verse Matthew 5:21 quotes it from. Two verses agreeing on that are making
    the same kind of utterance, which shared vocabulary alone cannot tell you
    -- Matthew 5:22, which outranks the true source, is a positive assertion
    built from the same words.
    """
    out = collections.defaultdict(set)
    for d in pol_rows:
        tag = d.get("polarity") or "positive"
        if d.get("prohibition"):
            tag = f"prohibition:{d['prohibition']}"
        elif d.get("stance") in ("command", "wish"):
            tag = f"{tag}:{d['stance']}"
        out[d["ref"]].add(tag)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--polarity", action="store_true",
                    help="apply the polarity penalty to the HARD ranking")
    a = ap.parse_args()

    lem = load_vocab()
    idf = idf_of(lem)
    print(f"verses with vocabulary: {len(lem):,}")
    pol = polarity_index()
    act = speech_act(list(rows("frames.jsonl.gz")))

    verdict = {}

    # ---- EASY -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("EASY -- the sea calmed. Jonah 1 and Jesus stilling the storm.")
    print("=" * 70)
    PAIRS = [("Jon.1.4", "Mat.8.24"), ("Jon.1.15", "Luk.8.24"),
             ("Jon.1.15", "Mrk.4.39")]
    easy = 0
    for x, y in PAIRS:
        if x not in lem or y not in lem:
            print(f"  ?    {x} ~ {y}   (a verse is missing from the layer)")
            continue
        m, sh = mass(lem[x], lem[y], idf)
        ok = m > 0 and len(sh) >= 1
        easy += ok
        print(f"  {'ok ' if ok else 'MISS'} {x} ~ {y}   mass {m:>6.1f}   "
              f"shared: {', '.join(sorted(sh)[:6])}")
    verdict["EASY"] = (easy, len(PAIRS))

    # ---- MEDIUM -----------------------------------------------------------
    print("\n" + "=" * 70)
    print("MEDIUM -- the Sermon on the Mount and what it cites.")
    print("=" * 70)
    SERMON = [
        ("Mat.5.21", "Exo.20.13", "you shall not murder"),
        ("Mat.5.27", "Exo.20.14", "you shall not commit adultery"),
        ("Mat.5.31", "Deu.24.1", "a certificate of divorce"),
        ("Mat.5.33", "Lev.19.12", "do not swear falsely"),
        ("Mat.5.38", "Exo.21.24", "eye for eye"),
        ("Mat.5.43", "Lev.19.18", "love your neighbour"),
    ]
    med = 0
    ranks = []
    for src, dst, what in SERMON:
        if src not in lem or dst not in lem:
            print(f"  ?    {src} -> {dst}  ({what}) missing")
            continue
        m, sh = mass(lem[src], lem[dst], idf)
        # Rank the true target among every verse this source shares anything
        # with -- finding it is not the same as PREFERRING it, and the whole
        # failure of this method has been the second one.
        cand = []
        for other, v in lem.items():
            if other == src:
                continue
            mm, _ = mass(lem[src], v, idf)
            if mm <= 0:
                continue
            if a.polarity:
                # Agreeing on the KIND of utterance is independent evidence
                # from sharing words. Mat 5:21 and Exo 20:13 are both
                # absolute prohibitions; Mat 5:22, which outranks the true
                # source on vocabulary, is a positive assertion.
                shared_act = act.get(src, set()) & act.get(other, set())
                strong = {x for x in shared_act if x.startswith("prohibition")
                          or x.endswith("command")}
                if strong:
                    mm *= 1.6
            cand.append((mm, other))
        cand.sort(reverse=True)
        rank = next((i + 1 for i, (_, r) in enumerate(cand) if r == dst), None)
        ok = rank is not None and rank <= 20
        med += ok
        if rank:
            ranks.append(rank)
        print(f"  {'ok ' if ok else 'MISS'} {src} -> {dst:<11} rank "
              f"{str(rank):>6} of {len(cand):>5}   mass {m:>6.1f}   {what}")
        if rank and rank > 1:
            print(f"        outranked by: "
                  f"{', '.join(r for _, r in cand[:3])}")
    # MEAN RANK, because a pass count at a threshold of 20 hides the result.
    # The speech-act bonus scores 5/6 with it ON and 5/6 with it OFF while
    # moving Mat 5:21 from rank 20 to 3 and Mat 5:33 from 40 to 18. A count
    # that cannot see that is the wrong instrument.
    if ranks:
        print(f"\n  mean rank of the true source: "
              f"{sum(ranks)/len(ranks):.1f}   (lower is better)")
    verdict["MEDIUM"] = (med, len(SERMON))

    # ---- HARD -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("HARD -- Psalm 32:1-5, three directions.")
    print("=" * 70)
    src = {w for v in range(1, 6) for w in lem.get(f"Psa.32.{v}", set())}
    print(f"  source vocabulary: {len(src)} content glosses")

    chap = collections.defaultdict(set)
    negrate = collections.defaultdict(lambda: [0, 0])
    for ref, v in lem.items():
        c = chapter_of(ref)
        chap[c] |= v
        n, t = pol.get(ref, (0, 0))
        negrate[c][0] += n
        negrate[c][1] += t

    scored = []
    for c, v in chap.items():
        if c == "Psa.32":
            continue
        m, sh = mass(src, v, idf)
        if m <= 0:
            continue
        if a.polarity:
            # Two passages that share vocabulary but DISAGREE in polarity are
            # not saying the same thing. Job 1:22 "Job did not sin" and a
            # verse about sinning share every content word and assert
            # opposites. Penalise by the gap in negation rate.
            sn, st = negrate[c]
            srcneg = sum(pol.get(f"Psa.32.{i}", (0, 0))[0] for i in range(1, 6))
            srctot = sum(pol.get(f"Psa.32.{i}", (0, 0))[1] for i in range(1, 6))
            r1 = srcneg / max(srctot, 1)
            r2 = sn / max(st, 1)
            m *= 1.0 - 0.5 * abs(r1 - r2)
        scored.append((m, c, len(sh)))
    scored.sort(reverse=True)

    def rank_of(c):
        return next((i + 1 for i, (_, x, _) in enumerate(scored) if x == c),
                    None)

    TARGETS = [("2Sa.12", "backlink  -- Nathan confronts David"),
               ("2Sa.24", "         (the rival the method preferred)"),
               ("Psa.51", "peer      -- the other confession psalm"),
               ("Rom.4",  "forward   -- Paul quotes Psa 32:1-2 verbatim")]
    print(f"\n  ranked {len(scored):,} chapters"
          f"{'  [polarity penalty ON]' if a.polarity else ''}")
    for c, what in TARGETS:
        r = rank_of(c)
        print(f"    {c:<8}rank {str(r):>6}   {what}")
    print("\n  top 10:")
    for m, c, n in scored[:10]:
        print(f"    {c:<9}{m:>8.1f}  {n:>4} shared")

    hard = sum(1 for c, _ in TARGETS[:1] + TARGETS[2:]
               if (rank_of(c) or 9999) <= 10)
    verdict["HARD"] = (hard, 3)

    print("\n" + "=" * 70)
    print("SUMMARY                          now        baseline 2026-09-10")
    print("=" * 70)
    BASE = {"EASY": "3/3 pass", "MEDIUM": "partial",
            "HARD": "0/3 (2Sa 24 beat 2Sa 12; Psa 51 rank 6)"}
    for k in ("EASY", "MEDIUM", "HARD"):
        got, tot = verdict[k]
        print(f"  {k:<8}{got}/{tot:<26}{BASE[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
