"""Map a MACULA reference to the Berean verse that carries the same text.

2026-09-21, reading what the app printed under Exodus 8:6, the BSB verse
shown ('So Aaron stretched out his hand over the waters of Egypt, and the
frogs came up and covered the land of Egypt.') had no apparent relation to
the analysis beside it.

It did not relate. MACULA's `Exo.8.6` is "there is no one like the LORD our
God", which the Berean text carries at 8:10 — Hebrew Exodus 8 runs four verses
ahead of the English because the English chapter begins where the Hebrew has
7:26. The graph is keyed on the Hebrew reference and the reader printed the
Berean verse at the same number, so in every chapter where the two disagree it
showed the wrong verse under the right analysis.

    1,188 chapters present in both
      142 chapters where the last verse number differs
    3,236 verses inside them, about 10% of the corpus

## Why this is an alignment and not a table of offsets

A table of per-chapter offsets cannot express what actually happens. Exodus 7
is −4 and Exodus 8 is +4 because the CHAPTER BOUNDARY is in a different place;
the verses did not move within a chapter, the chapter moved around them. Same
for Leviticus 5/6, Numbers 16/17, 1 Kings 4/5, Job 40/41, Joel 2/3. An offset
per chapter would need the offset to change mid-chapter, which is another way
of saying it is the wrong shape.

So each BOOK is aligned as a sequence, once, by dynamic programming, and the
map falls out of the alignment.

## What the two sides are scored on

**The Berean editors tagged their own English with Strong's numbers.** So a
Hebrew verse and an English verse can be compared on lexeme identity — no
translation judgement, no word order, no language in common required. Two
verses that name the same lexemes are the same verse.

That is also the only evidence available that does not beg the question:
comparing by REFERENCE is what was wrong in the first place.

## Why the obvious cheaper method fails

Fitting one offset per chapter by maximising agreement was tried first. It
found 20 chapters and **missed Exodus 8 entirely**, because a verse shifted by
four inside the same chapter still shares LORD, said, Egypt and Pharaoh with
the verse it displaced, and clears any overlap threshold. Overlap cannot see a
shift inside matching vocabulary. The alignment can, because it is forced to
choose a single monotonic path through the whole book.

    python tools/versify.py            # what it changes, and the disagreements
    python tools/versify.py --write
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
DEST = OUT / "versemap.json"

# A pairing must be at least this good to be believed; below it the verse is
# left unmapped rather than guessed at.
MIN_SCORE = 0.15
# ...OR be carried by its neighbours. A pair is not an independent guess: the
# alignment is monotonic, so a verse sitting between two confident pairs has
# only one place it can go. Judging each pair alone threw away correct ones —
# Psalm 3:7 pairs with 3:6 at 0.00 between two pairs at 1.00, because the
# Berean editors tagged none of the same words there — and that cut the
# Psalms from around 600 moved verses to 204.
SUPPORT_WINDOW = 3


def vkey(ref):
    b, c, v = ref.split(".")
    return b, int(c), int(v)


def macula_keys():
    """-> {ref: {strong keys}} for the original-language text."""
    out = {}
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if not d.get("ref"):
            continue
        ks = collections.Counter()
        for w in d.get("words") or []:
            s = w.get("s")
            if not s:
                continue
            lang = "h" if any("֐" <= c <= "׿"
                              for c in (w.get("t") or "")) else "g"
            n = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", s))
            if n:
                ks[lang + n] += 1
        out[d["ref"]] = ks
    return out


def berean_keys():
    """-> {ref: {strong keys}} from the Berean editors' own tagging."""
    out = {}
    for line in gzip.open(OUT / "bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        if not line.startswith('{"ref"'):
            continue
        d = json.loads(line)
        ks = collections.Counter()
        for _s, _e, k in d.get("spans") or []:
            ks[k] += 1
        out[d["ref"]] = ks
    return out


def sim(a, b):
    """Shared lexemes over the smaller side, so a long verse is not penalised
    for pairing with a short one."""
    if not a or not b:
        return 0.0
    shared = sum(min(a[k], b[k]) for k in a.keys() & b.keys())
    return shared / max(min(sum(a.values()), sum(b.values())), 1)


def align(ma, be):
    """Monotonic alignment of two verse sequences -> [(ma_ref, be_ref, score)].

    Gaps are allowed on both sides, because the divisions genuinely differ:
    one Hebrew verse can answer to two English ones and the reverse. The gap
    penalty is small, since a skip is a normal event here rather than an
    error.
    """
    n, m = len(ma), len(be)
    GAP = -0.08
    # score matrix, rolling
    prev = [j * GAP for j in range(m + 1)]
    back = [[0] * (m + 1) for _ in range(n + 1)]
    for j in range(m + 1):
        back[0][j] = 2                    # came from the left
    for i in range(1, n + 1):
        cur = [i * GAP] + [0.0] * m
        back[i][0] = 1                    # came from above
        for j in range(1, m + 1):
            diag = prev[j - 1] + sim(ma[i - 1][1], be[j - 1][1])
            up = prev[j] + GAP
            left = cur[j - 1] + GAP
            best = max(diag, up, left)
            cur[j] = best
            back[i][j] = 0 if best == diag else (1 if best == up else 2)
        prev = cur
    # walk back
    out, i, j = [], n, m
    while i > 0 or j > 0:
        d = back[i][j]
        if i > 0 and j > 0 and d == 0:
            out.append((ma[i - 1][0], be[j - 1][0],
                        sim(ma[i - 1][1], be[j - 1][1])))
            i, j = i - 1, j - 1
        elif i > 0 and (d == 1 or j == 0):
            out.append((ma[i - 1][0], None, 0.0))
            i -= 1
        else:
            j -= 1
    out.reverse()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--book", help="only this book, for inspection")
    a = ap.parse_args()

    ma, be = macula_keys(), berean_keys()
    books = sorted({r.split(".")[0] for r in ma} & {r.split(".")[0]
                                                    for r in be})
    if a.book:
        books = [b for b in books if b == a.book]

    mapping, stats = {}, collections.Counter()
    moved_by_book = collections.Counter()
    for b in books:
        mseq = sorted(((r, ma[r]) for r in ma if r.startswith(b + ".")),
                      key=lambda x: vkey(x[0]))
        bseq = sorted(((r, be[r]) for r in be if r.startswith(b + ".")),
                      key=lambda x: vkey(x[0]))
        if not mseq or not bseq:
            continue
        pairs = align(mseq, bseq)
        # LOCAL SUPPORT, because a pair is not an independent guess. Only
        # pairings are considered when weighing a neighbourhood; gaps carry no
        # evidence either way.
        scored = [p for p in pairs if p[1] is not None]
        idx = {id(p): i for i, p in enumerate(scored)}
        for p in pairs:
            mref, bref, sc = p
            if bref is None:
                stats["unmapped"] += 1
                continue
            i = idx[id(p)]
            lo = max(0, i - SUPPORT_WINDOW)
            hi = min(len(scored), i + SUPPORT_WINDOW + 1)
            near = [scored[k][2] for k in range(lo, hi) if k != i]
            support = (sum(near) / len(near)) if near else 0.0
            if sc < MIN_SCORE and support < MIN_SCORE:
                stats["unmapped"] += 1
                continue
            mapping[mref] = bref
            stats["mapped"] += 1
            if mref != bref:
                stats["moved"] += 1
                moved_by_book[b] += 1

    # A CHAPTER BOUNDARY THAT MOVED, PROVED BY VERSE COUNTS. 2026-09-26:
    # a verse alignment problem in the reader at Leviticus 6:17, a 7 verse
    # shift. The Berean editors tagged Leviticus 6
    # sparsely (0-3 Strong's keys a verse), a single shared "LORD" scores 1.0,
    # and the alignment kept Hebrew 6:10 at English 6:10 — its whole second
    # half was 7 verses off. The counts see what the tags cannot: Hebrew Lev 5
    # has 26 verses to the English 19 (+7), Hebrew Lev 6 has 23 to 30 (-7).
    # Where chapter c has +k and chapter c+1 has -k, the boundary moved by k:
    # Hebrew c:(e+1 .. e+k) is English c+1:(1 .. k) and Hebrew c+1:v is
    # English c+1:(v+k). The mirror (-k then +k) the other way. Exodus 7/8
    # (+4/-4) is the check: it gives the map the alignment already had right.
    # The Psalms' heading offsets (+1, +1) are not this shape and are left to
    # the alignment.
    count = collections.defaultdict(collections.Counter)      # side -> (b,c)
    for side, keys in (("m", ma), ("b", be)):
        for r in keys:
            bk, c_, v_ = vkey(r)
            count[side][(bk, c_)] = max(count[side][(bk, c_)], v_)
    overridden = collections.Counter()
    pairs_ = []
    for (bk, c_), mlen in sorted(count["m"].items()):
        if a.book and bk != a.book:
            continue
        blen = count["b"].get((bk, c_))
        m2, b2 = count["m"].get((bk, c_ + 1)), count["b"].get((bk, c_ + 1))
        if not (blen and m2 and b2):
            continue
        k = mlen - blen
        if k == 0 or (m2 - b2) != -k:
            continue
        pairs_.append((bk, c_, mlen, blen, m2))
    # only a pair that STANDS ALONE: Hosea 11/12, 12/13, 13/14 is a chain of
    # moves, each explained by the one before, and taken pairwise it counted
    # every move twice. Chains are left to the alignment.
    used = collections.Counter()
    for bk, c_, *_ in pairs_:
        used[(bk, c_)] += 1
        used[(bk, c_ + 1)] += 1
    for bk, c_, mlen, blen, m2 in pairs_:
        if used[(bk, c_)] > 1 or used[(bk, c_ + 1)] > 1:
            overridden[f"{bk} {c_}/{c_ + 1} (chain, left to the alignment)"] += 1
            continue
        k = mlen - blen
        if k > 0:          # Hebrew c runs k verses into English c+1
            for i in range(1, k + 1):
                mapping[f"{bk}.{c_}.{blen + i}"] = f"{bk}.{c_ + 1}.{i}"
            for v_ in range(1, m2 + 1):
                mapping[f"{bk}.{c_ + 1}.{v_}"] = f"{bk}.{c_ + 1}.{v_ + k}"
        else:              # English c runs -k verses into Hebrew c+1
            k = -k
            for i in range(1, k + 1):
                mapping[f"{bk}.{c_ + 1}.{i}"] = f"{bk}.{c_}.{mlen + i}"
            for v_ in range(k + 1, m2 + 1):
                mapping[f"{bk}.{c_ + 1}.{v_}"] = f"{bk}.{c_ + 1}.{v_ - k}"
        overridden[f"{bk} {c_}/{c_ + 1} ({'+' if mlen > blen else '-'}"
                   f"{abs(mlen - blen)})"] += 1
    print("chapter boundaries moved, by verse counts:",
          ", ".join(overridden) or "none")

    # A PSALM'S TITLE, PROVED BY VERSE COUNTS (the Psalter's collection
    # layer). Hebrew numbers a psalm's superscription as verse 1 (or 1-2);
    # the Berean text sets it as a heading. So a psalm with k more Hebrew
    # verses than English, whose next psalm does not give them back (that
    # would be a boundary, above), is Hebrew v = English v - k for every v
    # after the title. Left to the alignment, the Berean tagging is too
    # sparse in the Psalms to hold the offset: 51 of the 62 titled psalms
    # drifted back to the same number part-way through (2026-09-28, found
    # when Rom 3:4 could not meet Ps 51:4 — Hebrew 51:6 — in the BSB
    # footnote benchmark). Title verses keep what the alignment gave them.
    titled = 0
    for (bk, c_), mlen in sorted(count["m"].items()):
        if bk != "Psa" or (a.book and bk != a.book):
            continue
        blen = count["b"].get((bk, c_))
        if not blen or mlen <= blen:
            continue
        k = mlen - blen
        m2, b2 = count["m"].get((bk, c_ + 1)), count["b"].get((bk, c_ + 1))
        if m2 and b2 and (m2 - b2) == -k:
            continue
        for v_ in range(k + 1, mlen + 1):
            mapping[f"{bk}.{c_}.{v_}"] = f"{bk}.{c_}.{v_ - k}"
        titled += 1
    print(f"psalm titles offset by verse counts: {titled} psalms")

    print(f"{stats['mapped']:,} verses mapped, {stats['unmapped']:,} left "
          f"unmapped (below {MIN_SCORE:.0%} agreement)")
    print(f"{stats['moved']:,} map to a DIFFERENT Berean verse number\n")

    print("books where the numbering moves:")
    for b, n in moved_by_book.most_common(20):
        print(f"   {b:<5} {n:>5} verses")

    # The reported cases, by name
    for probe in ("Exo.8.6", "Exo.8.2", "Psa.3.1", "Jol.3.1", "Mal.3.19"):
        if probe in mapping:
            print(f"\n   {probe}  ->  {mapping[probe]}")

    # CHECKED ON EVIDENCE THE ALIGNMENT DID NOT SEE. Scoring the result on
    # Strong's tags would only report how well it optimised what it optimised,
    # and it reported the map as 20% WORSE — because the editors' tagging is
    # sparse enough that two verses which are plainly the same text can share
    # almost no tagged key. Hebrew 1 Kings 5:1 is "Solomon ruled over all the
    # kingdoms ... Philistines" and Berean 4:21 is "Solomon reigned over all
    # the kingdoms ... Philistines"; by tags that pairing scored 0.00.
    #
    # MACULA's glosses and the Berean text are both English, so comparing
    # their content words is dense, independent of the alignment, and needs no
    # translation judgement.
    stop = set("the a an of to and in on at for with is are was were be that "
               "this it he she they his their them him her you your my me i "
               "we us our from as so not but by".split())

    def wordset(s):
        return {w for w in re.findall(r"[a-z']+", (s or "").lower())
                if w not in stop and len(w) > 2}

    mg, bt = {}, {}
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if d.get("ref"):
            mg[d["ref"]] = wordset(
                " ".join((w.get("g") or "") for w in d.get("words") or []))
    for line in gzip.open(OUT / "bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        if line.startswith('{"ref"'):
            d = json.loads(line)
            bt[d["ref"]] = wordset(d.get("text"))

    def jac(x, y):
        return len(x & y) / len(x | y) if x and y else 0.0

    better = worse = same = 0
    for k, v in mapping.items():
        if k == v:
            continue
        x = jac(mg.get(k) or set(), bt.get(k) or set())
        y = jac(mg.get(k) or set(), bt.get(v) or set())
        if y > x:
            better += 1
        elif y < x:
            worse += 1
        else:
            same += 1
    tot = max(better + worse + same, 1)
    print(f"\nmoved verses, checked on ENGLISH WORDING (not on the tags the "
          f"alignment used):")
    print(f"   better {better:,} ({better/tot:.0%})   "
          f"same {same:,}   worse {worse:,} ({worse/tot:.0%})")

    def overall(f):
        t = n = 0
        for r in mg:
            o = bt.get(f(r))
            if not mg[r] or not o:
                continue
            t += jac(mg[r], o)
            n += 1
        return t / max(n, 1)
    print(f"   mean agreement, whole corpus: "
          f"{overall(lambda r: r):.4f} -> "
          f"{overall(lambda r: mapping.get(r, r)):.4f}")

    # CHECKED AGAINST STEP BIBLE'S TABLE (2026-10-24, the image audit: the site
    # showed Hosea 14:8 for the vine, which is 14:7, and Psalm 12:8's text under
    # Psalm 13's title). The alignment left 208 Hebrew verses where STEP's TAHOT
    # (tools/versemap_step.py) numbers them otherwise, 124 of them in Psalms, and
    # mapped 3 that STEP leaves in place. Where the two disagree, the verse whose
    # Strong's numbers agree better wins, so STEP corrects the alignment without
    # overruling the Berean where its numbering truly differs from the English
    # tradition STEP follows. The Berean folds a psalm's title into verse 1, so
    # STEP's "verse 0" is the Berean's 1.
    from versemap_step import step_table
    step = step_table()
    fixed = []
    for r in mg:
        b = r.split(".")[0]
        if not any(k.startswith(b + ".") for k in step):
            continue                                  # a book STEP does not renumber
        s = step.get(r, r)
        if s.endswith(".0"):
            s = s[:-1] + "1"
        cur = mapping.get(r, r)
        if s == cur or s not in bt:
            continue
        if jac(mg[r], bt[s]) >= jac(mg[r], bt.get(cur) or set()):
            mapping[r] = s
            fixed.append((r, cur, s))
    print(f"   checked against STEP's table: {len(fixed)} verses re-mapped, e.g. {fixed[:4]}")
    print(f"   mean agreement after: {overall(lambda r: mapping.get(r, r)):.4f}")

    if not a.write:
        print("\nnothing written -- pass --write")
        return 0
    DEST.write_text(json.dumps({
        "_note": "MACULA reference -> the Berean verse carrying the same "
                 "text. Built by aligning each book as a sequence on the "
                 "Strong's numbers the Berean editors tagged their own "
                 "English with, because comparing by REFERENCE is the thing "
                 "that was wrong. Only entries that MOVE are stored; anything "
                 "absent maps to itself. See tools/versify.py.",
        "moved": {k: v for k, v in sorted(mapping.items()) if k != v},
    }, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"\n  -> {DEST.relative_to(ROOT)}  "
          f"{stats['moved']:,} moved references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
