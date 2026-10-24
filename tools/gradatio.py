"""Character stacking: chains where each link's end begins the next.

2026-09-15: the pattern is called character stacking; the examples are
Romans 5:3-4 and 2 Peter 1:5-8, and the question was whether there are others.

    Rom 5:3-4    θλῖψις -> ὑπομονή -> δοκιμή -> ἐλπίς
                 suffering, endurance, character, hope
    2 Pet 1:5-7  πίστις -> ἀρετή -> γνῶσις -> ἐγκράτεια -> ὑπομονή
                 -> εὐσέβεια -> φιλαδελφία -> ἀγάπη

The rhetorical name is *gradatio* (a ladder), built out of *anadiplosis* --
the word that ends one step begins the next. **That is mechanically
detectable**, which makes this a different kind of pattern from the shepherd
one: no model has to assert it, and every instance can show its own chain.

## How it is found

Take the CONTENT lemmas of a short window in order, dropping articles,
conjunctions and prepositions, which carry the syntax and not the ladder. A
link is a lemma that occurs twice with a new content lemma immediately after
its second occurrence. A chain is two or more links end to end.

Requiring TWO links is what separates a ladder from ordinary repetition: any
text repeats a word and carries on. Only a ladder repeats, advances, repeats
the advance, and advances again.

## What it is not

It does not know that the links are virtues. Romans and 2 Peter stack
character; Romans 10:14 stacks the conditions of preaching and Romans 8:29-30
stacks election. Those are the same FORM with different fill, which is what a
template is for -- and telling them apart is a job for reading, or for the
slot-filling pass, not for this.

    python tools/gradatio.py --check          # the two worked examples
    python tools/gradatio.py --min-links 3    # the whole corpus
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

# Syntax, not content. A ladder is built of nouns and verbs; the articles and
# particles between them are the rungs' fixings, not the rungs.
SKIP = {"ὁ", "δέ", "καί", "ἐν", "εἰς", "ἐκ", "τε", "γάρ", "μέν", "οὐ", "μή",
        "ὅτι", "ἀλλά", "σύ", "ἐγώ", "αὐτός", "οὗτος", "ὡς", "εἰ", "ἵνα",
        "πρός", "ἐπί", "κατά", "διά", "περί", "ἀπό", "σύν", "ὑπό", "παρά",
        "ה", "ו", "ב", "ל", "כ", "מן", "את", "אשר", "כי", "לא", "על", "אל"}


def chains(lemmas, gap=2):
    """-> [[a, b, c, ...]] every ladder in this lemma sequence.

    A link is a lemma repeated with a NEW content lemma directly after the
    repeat. Links join when one ends where the next begins.

    `gap` is what separates a ladder from narrative. At 6 content words the
    corpus returned 2,509 "chains" led by Ezekiel's land allotments and
    Chronicles' inventories of gold, silver, bronze and iron -- narrative
    repeats a noun constantly and drifts. A ladder repeats IMMEDIATELY: in
    Romans 5 the two occurrences of θλῖψις are two content words apart, and in
    2 Peter every rung touches the one below it.
    """
    links = []
    for i, w in enumerate(lemmas):
        for j in range(i + 1, min(i + 1 + gap, len(lemmas))):
            if lemmas[j] != w:
                continue
            for k in range(j + 1, min(j + 3, len(lemmas))):
                nxt = lemmas[k]
                if nxt != w:
                    links.append((w, nxt))
                    break
            break
    # join links end to start
    out, used = [], set()
    nxt_of = {}
    for a, b in links:
        nxt_of.setdefault(a, b)
    for a, b in links:
        if a in used:
            continue
        ch, seen = [a], {a}
        cur = a
        while cur in nxt_of and nxt_of[cur] not in seen:
            cur = nxt_of[cur]
            ch.append(cur)
            seen.add(cur)
        if len(ch) >= 3:                      # two links or more
            out.append(ch)
            used |= seen
    return out


# A ladder is built of NOUNS. Filtering by lemma alone let Hebrew's prefixed
# particles -- the vav, the article, the prepositions, each a lemma of its own
# -- flood every chain, and 6,963 "chains" came back led by Ezekiel's temple
# measurements and Exodus 21's eye-for-eye list. The interlinear carries a
# part of speech and it settles this in one test.
KEEP_POS = {"noun", "adj"}
NAMES = set()


def is_name(lemma, names):
    """Proper nouns are ladders too -- Matthew 1 is a perfect gradatio of
    begettings -- but they are ladders of PEOPLE, and the pattern sought is a
    ladder of qualities. Greek marks a proper noun by capitalising it; Hebrew
    does not, so the people and place layers supply the rest."""
    return (lemma[:1].isupper() and lemma[:1].isalpha()) or lemma in names


def windows(il, size=3):
    """-> (start ref, [lemmas]) rolling windows of `size` verses in one book."""
    order = sorted(il, key=lambda r: (r.split(".")[0],
                                      *(int(x) for x in r.split(".")[1:])))
    for i in range(len(order)):
        w = [order[i]]
        for j in range(i + 1, min(i + size, len(order))):
            a, b = order[i].split("."), order[j].split(".")
            if a[0] != b[0]:
                break
            w.append(order[j])
        lem = []
        for r in w:
            for x in il[r]:
                l = (x.get("l") or "").strip()
                if (l and l not in SKIP and (x.get("p") or "") in KEEP_POS
                        and not is_name(l, NAMES)):
                    lem.append(l)
        yield order[i], w[-1], lem


def proper_names():
    """-> {lemma} every lemma the graph knows as a person or a place."""
    out = set()
    for f in ("people-xref.jsonl.gz", "places.jsonl.gz"):
        p = OUT / f
        if not p.exists():
            continue
        for line in gzip.open(p, "rt", encoding="utf-8"):
            d = json.loads(line)
            for k in ("lemma", "name", "head"):
                v = d.get(k)
                if isinstance(v, str) and v:
                    out.add(v)
    return out


def load():
    il = {}
    p = OUT / "interlinear.jsonl.gz"
    for line in gzip.open(p, "rt", encoding="utf-8"):
        d = json.loads(line)
        if d.get("ref"):
            il[d["ref"]] = d["words"]
    return il


# ---------------------------------------------------------------- 2026-09-16
# On the first version of this list the ladder chains were judged interesting
# in concept but poor in execution, with four specific faults. Each is
# answered below and the fix is named where it lives.


def gloss_index(il):
    """-> {lemma: commonest gloss}. Also the proper-name test.

    `proper_names()` reads the people and place layers, which store ENGLISH
    names, while a step is a Hebrew or Greek LEMMA -- so it matched nothing,
    and 1 Chronicles 2:36-41 came through as a six-step "ladder" of Nathan,
    Zabad, Ephlal, Obed, Jehu, Azariah. Most were people and not
    interesting.

    MACULA capitalises the gloss of a proper noun and nothing else, which
    settles it in one test: `יֵהוּא` glosses "Jehu", `נֶפֶשׁ` glosses "soul".
    3,337 of 13,851 lemmas are names by that measure.
    """
    tally = collections.defaultdict(collections.Counter)
    for words in il.values():
        for w in words:
            l, g = w.get("l"), (w.get("g") or "").strip()
            if l and g:
                tally[l][g] += 1
    return {l: c.most_common(1)[0][0] for l, c in tally.items()}


# A STEP HAS TO CARRY MEANING. 2026-09-16: more interesting ladders were
# wanted surfaced, even ones as short as 3 steps. Dropping the length floor to three works only once
# the quantifiers and relatives are out: without this the three-step list is
# "all -> what -> which", "many -> one -> who". Same judgement, and the same
# short arguable list, as SUBSTRATE in tools/lexcoverage.py.
STOPSTEP = {
    "all", "what", "which", "who", "whom", "whose", "one", "many", "any",
    "some", "every", "each", "other", "another", "such", "same", "this",
    "that", "these", "those", "men", "man", "thing", "things", "himself",
    "themselves", "itself", "there", "here", "where", "when", "how", "why",
    "great", "much", "more", "most", "very", "own", "both", "few", "them",
    "they", "he", "she", "it", "we", "you", "i", "him", "her", "us", "me",
}


def weak(step, gloss):
    g = (gloss.get(step, "") or "").strip().lower().strip("[]()")
    return not g or g in STOPSTEP


def named(step, gloss):
    g = gloss.get(step, "")
    return bool(g) and g[:1].isupper()


def vkey(ref):
    b, c, v = ref.split(".")
    return (b, int(c), int(v))


def overlaps(a, b, slack=2):
    """Do two chains sit in the same stretch of text?"""
    (ab, ac, av), (ae, _, aev) = vkey(a[1]), (vkey(a[2]), 0, vkey(a[2])[2])
    (bb, bc, bv), (be, _, bev) = vkey(b[1]), (vkey(b[2]), 0, vkey(b[2])[2])
    if ab != bb or ac != bc:
        return False
    return not (aev + slack < bv or bev + slack < av)


def dedupe(rows):
    """One ladder per stretch of text, not one per window position.

    The first two on the list were parts of the same larger
    list -- Exo 21:23-25 and 21:24-26 are the same chain shifted by a verse,
    because the detector walks a rolling window and every position that still
    contains the ladder emits it. 1 Chronicles 2 produced four.

    Two chains are the same ladder when they sit in the same chapter, their
    verse spans touch, and they share a step. The longest survives.
    """
    rows = sorted(rows, key=lambda r: (-r["n"], vkey(r["start"])))
    kept = []
    for r in rows:
        me = (r["steps"], r["start"], r["end"])
        dup = False
        for k in kept:
            other = (k["steps"], k["start"], k["end"])
            if overlaps(me, other) and set(r["steps"]) & set(k["steps"]):
                dup = True
                break
        if not dup:
            kept.append(r)
    return kept


def repeats(rows, least=3):
    """Ladders the text uses TWICE, in different places.

    One of the most interesting things on the list was not obvious: the
    repeat of part of a ladder later -- Exodus 21:23-25's
    life-eye-tooth-hand-foot returns at Deuteronomy 19:20-21. A ladder repeated
    across books is a stronger finding than either instance alone, and the
    first version buried it in a list sorted by length.

    Matched on the SET of steps rather than the order, because the second
    telling need not keep it, and required to be in different chapters so a
    rolling-window artefact cannot masquerade as a repetition.
    """
    out = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            shared = [s for s in a["steps"] if s in set(b["steps"])]
            if len(shared) < least:
                continue
            if vkey(a["start"])[:2] == vkey(b["start"])[:2]:
                continue
            out.append({"a": a, "b": b, "shared": shared})
    out.sort(key=lambda x: -len(x["shared"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--min-links", type=int, default=3,
                    help="chain length; 3 means two links")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    il = load()
    global NAMES
    NAMES = proper_names()
    if a.check:
        for refs in (["Rom.5.3", "Rom.5.4"],
                     ["2Pe.1.5", "2Pe.1.6", "2Pe.1.7"]):
            lem = [x.get("l") for r in refs for x in il.get(r, [])
                   if (x.get("l") or "").strip() not in SKIP and x.get("l")
                   and (x.get("p") or "") in KEEP_POS
                   and not is_name(x.get("l"), NAMES)]
            print(f"  {refs[0]}..{refs[-1]}")
            for ch in chains(lem):
                print("      " + " -> ".join(ch))
        return 0

    gloss = gloss_index(il)
    raw, seen = [], set()
    for start_ref, end_ref, lem in windows(il):
        for ch in chains(lem):
            if len(ch) < a.min_links:
                continue
            # A LADDER OF PEOPLE IS A GENEALOGY. See gloss_index().
            if any(named(x, gloss) for x in ch):
                continue
            # And a ladder of quantifiers is not a ladder. See STOPSTEP.
            if any(weak(x, gloss) for x in ch):
                continue
            key = tuple(ch)
            if key in seen:
                continue
            seen.add(key)
            raw.append({"start": start_ref, "end": end_ref, "steps": ch,
                        "n": len(ch),
                        "glossed": [gloss.get(x, x) for x in ch]})
    rows = dedupe(raw)
    reps = repeats(rows)
    print(f"{len(raw):,} chains of {a.min_links}+ steps once names are dropped; "
          f"{len(rows):,} after merging rolling-window duplicates\n")

    if reps:
        print(f"  REPEATED -- the same ladder in two places, "
              f"{len(reps)} pair(s):\n")
        for r in reps[:a.top]:
            for side in ("a", "b"):
                x = r[side]
                span = (x["start"] if x["start"] == x["end"]
                        else f"{x['start']}..{x['end'].split('.')[-1]}")
                print(f"    {span:<18} " + " -> ".join(x["glossed"][:7]))
            print(f"    shares {len(r['shared'])}: "
                  + ", ".join(gloss.get(x, x) for x in r["shared"]) + "\n")

    print("  LONGEST:\n")
    for x in rows[:a.top]:
        span = (x["start"] if x["start"] == x["end"]
                else f"{x['start']}..{x['end'].split('.')[-1]}")
        print(f"    {x['n']} steps  {span:<18} " + " -> ".join(x["glossed"][:7]))
    best = [(x["n"], x["start"], x["end"], x["steps"]) for x in rows]
    GLOSSED = {tuple(x["steps"]): x["glossed"] for x in rows}
    REPEATED = {tuple(r[s]["steps"]) for r in reps for s in ("a", "b")}

    if a.write:
        p = OUT / "gradatio.jsonl.gz"
        with gzip.open(p, "wt", encoding="utf-8") as f:
            f.write(json.dumps({"_source": "Derived from MACULA lemmas via "
                                "out/interlinear.jsonl.gz",
                                "_note": "Chains where each link's end begins "
                                "the next -- gradatio. See tools/gradatio.py."})
                    + "\n")
            for n, s, e, ch in best:
                f.write(json.dumps({"start": s, "end": e, "steps": ch,
                                    "n": n}, ensure_ascii=False) + "\n")
        print(f"\n  -> {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
