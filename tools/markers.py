"""Free marker passes over the whole canon, from the tagged text alone.

2026-09-03: run all the quick, essentially free marker tests that can be
thought of now, picking things that have some theory behind them. Many of the
signals that matter most will not show up until later, but the better the floor
is built out, the better that build-up will be.

**Every pass here reads only the tagged text**, so all of them run before any
extraction and all of them feed the extraction window. That is the dividing
line, and it is not a matter of taste: a pass that needs relations -- role
deviation, literal-versus-symbol by predication -- cannot run until there is a
graph. A pass that needs only words can run now, free, and improve every window
the worker ever sees.

A pass here MARKS. It does not decide. Marking passes can run in any order and
repeat until their output stops changing; only deciding passes need sequencing.
That is what makes the ordering problem tractable.

## The passes, and the theory each rests on

    pairs       Fixed word pairs -- merism and hendiadys. "heaven and earth",
                "good and evil", "compassionate and gracious". Two words that
                recur together function as one unit. Splitting
                Gen 1:2 was vetoed on exactly this worry, so this pass is evidence
                for or against that objection rather than an opinion about it.

    formulae    Repeated gloss n-grams. "and it came to pass", "thus says the
                LORD", "these are the generations of". These are the
                deterministic half of the pattern layer -- string-matchable,
                no model, no judgement.

    repetition  A lemma repeated within one chapter. Mackie on Jonah: biblical
                authors do not waste ink, and a word repeated in a short span
                is the author pointing. `fear` in Jonah 1 is the worked case.

    inclusio    A chapter opening and closing on the same content lemma. The
                standard Hebrew bookending device, and a boundary signal that
                grouping can use directly.

    turns       Speech-verb density as a proxy for dialogue turns. A turn
                is the unit and a verse is the extraction window showing
                through. Counting turns is different from -- and better than --
                the dialog density already computed.

    hapax       Words occurring once in the canon. Marked vocabulary: a hapax
                is either a technical term, a loanword, or a deliberate choice,
                and all three are worth flagging.

    names       Divine name distribution, YHWH against Elohim. A long-observed
                rhetorical and source-critical signal, free to count and
                notoriously argued about, so worth having as data rather than
                as a position.

    numbers     Symbolically loaded numerals -- seven, forty, twelve, three.
                Weak alone and useful in combination with the others.

Nothing here interprets. Each pass emits candidates with counts and locations,
and the confidence comes from several passes agreeing, which is the same
"agreement is the confidence" design the lemma layer already uses.

    python tools/markers.py              # every pass, summary to stdout
    python tools/markers.py --json       # write out/markers.json
"""
from __future__ import annotations

import collections
import functools
import json
import pathlib
import re
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
STEP = ROOT / "data" / "raw" / "stepbible"
ATH = "֑"

STOP = {"the", "and", "of", "a", "an", "to", "in", "for", "with", "on", "at",
        "he", "she", "it", "his", "her", "him", "they", "them", "their", "you",
        "your", "i", "my", "we", "our", "is", "was", "are", "were", "be",
        "that", "this", "which", "who", "not", "obj", "from", "by", "as",
        "will", "did", "do", "all", "there", "so", "then", "up", "out"}


@functools.lru_cache(maxsize=1)
def corpus() -> tuple:
    """(ref, book, chapter, gloss, lemma, morph, pointed) for every tagged word.

    One pass over disk, cached, because eight marker passes over 575,000 words
    should read the files once rather than eight times.
    """
    out = []
    ref_ok = re.compile(r"^([A-Za-z0-9]+)\.(\d+)\.(\d+)")
    for f in sorted(STEP.glob("TAHOT*.txt")) + sorted(STEP.glob("TAGNT*.txt")):
        greek = f.name.startswith("TAGNT")
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                c = line.rstrip("\n").split("\t")
                if len(c) < 9:
                    continue
                m = ref_ok.match(c[0])
                if not m:
                    continue          # headers and separators: 231,785 of them
                if greek:
                    tag = c[3] if len(c) > 3 else ""
                    lem = tag.split("=")[0].strip()
                    morph = tag.split("=")[1].strip() if "=" in tag else ""
                    gloss = c[2]
                else:
                    lem = re.sub(r"[^HG0-9A-Z]", "",
                                 (c[8] or "").split("\\")[0])
                    morph = c[5].strip()
                    gloss = c[3]
                if not lem:
                    continue
                out.append((f"{m.group(1)}.{m.group(2)}.{m.group(3)}",
                            m.group(1), int(m.group(2)),
                            gloss.strip(), lem, morph, c[1]))
    return tuple(out)


def base(lem: str) -> str:
    """Strip STEPBible's disambiguating suffixes.

    H3588A, H3588AA, H3588AB, H3588AHT are all *ki*. Matching the bare number
    missed all 4,830 of them, which would have made the connective pass useless
    for Hebrew while appearing to work.
    """
    m = re.match(r"^([HG]\d{4})", lem)
    return m.group(1) if m else lem


def words(g: str) -> list:
    return [w for w in re.findall(r"[a-z]+", (g or "").lower())
            if w not in STOP and len(w) > 2]


# --------------------------------------------------------------- the passes

def pass_pairs(rows, min_n=6):
    """Fixed word pairs, scored by association rather than by count.

    Raw counts cannot find a merism. YHWH is the commonest lemma in the corpus,
    so it co-occurs with everything, and the first run returned "yahweh+moses"
    and "words+yahweh" -- frequency artefacts, not fixed pairs.

    Pointwise mutual information asks the right question instead: do these two
    appear together MORE than their separate frequencies predict? A common word
    beside another common word scores near zero; two words that travel together
    score high however rare they are.

    This is the pass that bears on the veto of splitting Gen 1:2. The worry
    was "compassionate and gracious" -- a pairing that works as one concept. If
    fixed pairs are real they will surface here, counted rather than asserted.
    """
    seen = collections.Counter()
    where = collections.defaultdict(list)
    for i in range(len(rows) - 2):
        a, b, c2 = rows[i], rows[i + 1], rows[i + 2]
        if a[0] != c2[0]:
            continue                                   # same verse only
        for other in (b, c2):
            if other[1] != a[1]:
                continue
            ka, kb = base(a[4]), base(other[4])
            if ka == kb or not words(a[3]) or not words(other[3]):
                continue
            # Order-independent, because a fixed pair is. "compassionate and
            # gracious" runs rachum-channun in Exod 34:6 and channun-rachum in
            # Joel 2:13 and Jonah 4:2; a directional key split one pair into
            # two half-counts and dropped both below threshold.
            key = (ka, kb) if ka < kb else (kb, ka)
            seen[key] += 1
            if len(where[key]) < 3:
                where[key].append(a[0])
    gloss = {}
    freq = collections.Counter()
    for r in rows:
        gloss.setdefault(base(r[4]), r[3])
        freq[base(r[4])] += 1
    total = sum(freq.values())
    pairs_total = sum(seen.values())
    out = []
    for (ka, kb), n in seen.items():
        if n < min_n:
            continue
        ga, gb = words(gloss.get(ka, "")), words(gloss.get(kb, ""))
        if not ga or not gb or ga[0] == gb[0]:
            continue
        # PMI: log( P(a,b) / (P(a) * P(b)) )
        pab = n / pairs_total
        pa, pb = freq[ka] / total, freq[kb] / total
        import math
        pmi = math.log(pab / (pa * pb)) if pa and pb else 0.0
        out.append({"a": ka, "b": kb, "gloss": f"{ga[0]} + {gb[0]}",
                    "n": n, "pmi": round(pmi, 2), "where": where[(ka, kb)]})
    out.sort(key=lambda d: -d["pmi"])
    return out[:120]


def pass_formulae(rows, size=4, min_n=5):
    """Repeated gloss n-grams -- the string-matchable half of patterns."""
    seq = collections.Counter()
    where = collections.defaultdict(list)
    buf = []
    for r in rows:
        w = words(r[3])
        buf.append((r[0], w[0] if w else None))
        if len(buf) > size:
            buf.pop(0)
        if len(buf) == size and all(x[1] for x in buf):
            if len({x[0].rsplit(".", 1)[0] for x in buf}) == 1:
                key = " ".join(x[1] for x in buf)
                seq[key] += 1
                if len(where[key]) < 3:
                    where[key].append(buf[0][0])
    return [{"phrase": k, "n": v, "where": where[k]}
            for k, v in seq.most_common(60) if v >= min_n]


def pass_repetition(rows, min_n=4):
    """A lemma repeated inside one chapter: the author pointing."""
    per = collections.defaultdict(collections.Counter)
    gloss = {}
    for r in rows:
        per[(r[1], r[2])][base(r[4])] += 1
        gloss.setdefault(base(r[4]), r[3])
    hits = []
    for (bk, ch), c in per.items():
        for lem, n in c.items():
            g = words(gloss.get(lem, ""))
            if n >= min_n and g:
                hits.append({"book": bk, "ch": ch, "lemma": lem,
                             "gloss": g[0], "n": n})
    hits.sort(key=lambda h: -h["n"])
    return hits


def pass_inclusio(rows):
    """A chapter opening and closing on the same content lemma."""
    per = collections.defaultdict(list)
    for r in rows:
        if words(r[3]):
            per[(r[1], r[2])].append(base(r[4]))
    out = []
    for (bk, ch), lems in per.items():
        if len(lems) < 12:
            continue
        head, tail = set(lems[:4]), set(lems[-4:])
        shared = head & tail
        if shared:
            out.append({"book": bk, "ch": ch, "lemma": sorted(shared)[0]})
    return out


def pass_turns(rows):
    """Speech-verb density: turns, not verses."""
    SAY = {"H0559", "H1696", "H7121", "H6030",
           "G3004", "G2036", "G2980", "G0611"}
    per = collections.Counter()
    tot = collections.Counter()
    for r in rows:
        tot[(r[1], r[2])] += 1
        if base(r[4]) in SAY:
            per[(r[1], r[2])] += 1
    return [{"book": b, "ch": c, "turns": n, "words": tot[(b, c)]}
            for (b, c), n in per.most_common(25)]


def pass_hapax(rows):
    """Words occurring once in the canon: marked vocabulary."""
    c = collections.Counter(base(r[4]) for r in rows)
    once = {k for k, v in c.items() if v == 1}
    per = collections.Counter()
    tot = collections.Counter()
    for r in rows:
        tot[(r[1], r[2])] += 1
        if base(r[4]) in once:
            per[(r[1], r[2])] += 1
    dense = sorted(((n / max(tot[k], 1), k, n) for k, n in per.items()),
                   reverse=True)[:15]
    return {"total_hapax": len(once),
            "densest": [{"book": k[0], "ch": k[1], "rate": round(rate, 3),
                         "n": n} for rate, k, n in dense]}


def pass_names(rows):
    """YHWH against Elohim, counted rather than argued about."""
    per = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        b = base(r[4])
        if b == "H3068":
            per[r[1]][0] += 1
        elif b == "H0430":
            per[r[1]][1] += 1
    out = [{"book": k, "yhwh": v[0], "elohim": v[1],
            "ratio": round(v[0] / max(v[0] + v[1], 1), 2)}
           for k, v in per.items() if sum(v) >= 40]
    out.sort(key=lambda x: -x["ratio"])
    return out


def pass_numbers(rows):
    """Symbolically loaded numerals."""
    NUM = {"H7651": "seven", "H0705": "forty", "H8147": "two",
           "H7969": "three", "H6240": "ten/teen", "H3967": "hundred",
           "G2033": "seven", "G5062": "forty", "G1427": "twelve",
           "G5140": "three"}
    per = collections.Counter()
    for r in rows:
        b = base(r[4])
        if b in NUM:
            per[(r[1], NUM[b])] += 1
    return [{"book": k[0], "number": k[1], "n": v}
            for k, v in per.most_common(15)]


def main() -> int:
    t0 = time.time()
    rows = corpus()
    print(f"corpus: {len(rows):,} tagged words, "
          f"{len({r[0] for r in rows}):,} verses, "
          f"{len({(r[1], r[2]) for r in rows}):,} chapters "
          f"({time.time() - t0:.1f}s)\n")

    res = {}
    for name, fn in (("pairs", pass_pairs), ("formulae", pass_formulae),
                     ("repetition", pass_repetition),
                     ("inclusio", pass_inclusio), ("turns", pass_turns),
                     ("hapax", pass_hapax), ("names", pass_names),
                     ("numbers", pass_numbers)):
        t = time.time()
        res[name] = fn(rows)
        n = len(res[name]) if isinstance(res[name], list) else "-"
        print(f"  {name:12} {str(n):>7} found   {time.time() - t:>5.1f}s")

    print(f"\n=== fixed word pairs (merism / hendiadys) ===")
    for p in res["pairs"][:18]:
        print(f"  {p['gloss']:34}{p['n']:>5}x  pmi {p['pmi']:>5.1f}  "
              f"{p['where'][0]}")

    print(f"\n=== repeated formulae ===")
    for p in res["formulae"][:12]:
        print(f"  {p['phrase'][:46]:48}{p['n']:>5}x")

    print(f"\n=== heaviest in-chapter repetition ===")
    for p in res["repetition"][:12]:
        print(f"  {p['book']} {p['ch']:<4} {p['gloss'][:20]:22}{p['n']:>4}x")

    print(f"\n=== inclusio candidates: {len(res['inclusio'])} chapters ===")
    print(f"\n=== hapax: {res['hapax']['total_hapax']:,} once-only lemmas ===")
    for d in res["hapax"]["densest"][:6]:
        print(f"  {d['book']} {d['ch']:<4} rate {d['rate']:.3f}  ({d['n']})")

    print(f"\n=== divine name ratio (YHWH share) ===")
    for d in res["names"][:5]:
        print(f"  {d['book']:6} {d['ratio']:.2f}  yhwh {d['yhwh']:>4} "
              f"elohim {d['elohim']:>4}")
    for d in res["names"][-3:]:
        print(f"  {d['book']:6} {d['ratio']:.2f}  yhwh {d['yhwh']:>4} "
              f"elohim {d['elohim']:>4}")

    if "--json" in sys.argv:
        (ROOT / "out" / "markers.json").write_text(
            json.dumps(res, indent=1), encoding="utf-8")
        print("\nwrote out/markers.json")
    print(f"\ntotal {time.time() - t0:.1f}s, cost $0.00")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
