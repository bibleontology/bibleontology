"""Signal matching: surface every signal on a span, then rank spans that share them.

2026-09-12, stating the architecture: the only way to make this findable is to
get really good at classifying the nodes (finding the strong signals) and
checking the surrounding nodes; get good at surfacing all the signals and
looking for matches.

## Why this does not enumerate the corpus

The expensive design scores every span against every span. This one does not.

  1. A **seed** is a signal rare enough to be worth starting from. Seeds are
     sparse by construction -- the grace formula is 7 verses in the Hebrew
     Bible, a doubled kinship term 31.
  2. Only spans containing a seed are ever built. Everything else is skipped
     before a profile is computed.
  3. Matching is then seed-bucketed: two spans are compared only if they share
     at least one seed.

Measured 2026-09-12: pairing collapses a useless signal into a decisive one --
Moses alone 705 verses, Moses + derek 4; 'av alone 1,063, 'av + racham 3.

## What a signal is

A `(kind, key)` pair, weighted by how rare the key is across spans. Kinds:

    lemma        a content lemma, Hebrew or Greek
    gendepth     a kinship term in construct with itself (livney vanim)
    pair         two content lemmas co-occurring in the span

Deliberately NOT included: the `figurative` flag from the comparison layer,
which fires on 95.8% of rows and cannot express failure (see BACKLOG).

## The honest limits

**Polarity is carried in the signal key** (fixed 2026-09-12; it was a real
defect before, not a simplification). 7,713 of 92,567 verbs in `out/frames.jsonl.gz` are negated
(8.3%), and some lemmas are negated more often than they are asserted --
`'avah` 96.3%, `yakhol` 75.1%, `dynamai` 55.5%. Every one of those matches
inverts the sense.

Psalm 103 was the worst case and is this module's own demo query. v8 is
`'erekh 'appayim`, literally *"long of anger"*, and v9 is *"nor keep his ANGER
forever"* -- so `'af` occurs twice and was read the wrong way both times.
A negated lemma is now a distinct signal (`lemma!`), and with `--invert` it also
emits its WordNet opposite, so *"not accusing"* can agree with *"merciful"*.

Cross-language matching rides on MACULA's own English glosses, which is the
other weak link and is flagged wherever it is used. A Hebrew span and a Greek
span share no lemmas; they share gloss keys.
"""
from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import math
import pathlib
import re
import unicodedata as ud
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
HEB = ROOT / "data/raw/macula/hebrew"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

# function words carry no matching information
STOP = {"הַ", "וְ", "בְּ", "לְ", "כְּ", "מִן", "אֵת", "אֲשֶׁר", "כִּי", "הוּא",
        "אֲנִי", "לֹא", "כֹּל", "עַל", "אֶל", "זֶה", "אִם", "גַּם", "אַף", "נ",
        "אַתָּה", "אֲנַחְנוּ", "מָה", "עַד", "כֵּן", "אֵין", "יֵשׁ"}
KIN = {"אָב", "בֵּן", "בַּת", "אֵם", "זֶרַע", "דּוֹר", "אָח", "נֶכֶד"}


def nfc(s):
    return ud.normalize("NFC", s or "")


def load_hebrew():
    """-> {ref: [lemma...]} in word order, Hebrew only."""
    per = collections.defaultdict(list)
    for p in sorted(glob.glob(str(HEB / "*.xml"))):
        for w in ET.parse(p).getroot().iter("w"):
            m = re.search(r"([A-Za-z0-9]+)\s+(\d+):(\d+)", w.get("ref") or "")
            if not m:
                continue
            per[f"{m.group(1).title()}.{m.group(2)}.{m.group(3)}"].append(
                nfc(w.get("lemma")))
    return per


def key(ref):
    b, c, v = ref.split(".")
    return (b, int(c), int(v))


FINITE = {"qatal", "wayyiqtol", "yiqtol", "weqatal", "imperative", "jussive",
          "cohortative", "weyiqtol"}
NONFIN = {"participle", "infinitive construct", "infinitive absolute"}


def dependents():
    """Verses that cannot stand alone and must bind to the one before.

    2026-09-12: with bottom-up grouping, 17-18 have to bind early.

    A verse with **no finite verb** that **opens with a preposition** governing a
    participle or infinitive is grammatically dependent -- Psa 103:18
    `li-shomrey verito`, "to those who keep his covenant", which continues v17
    and has no predicate of its own.

    Measured 2026-09-12: **86 of 23,213 verses (0.4%)**, and Psa.103.18 is the
    only one in its chapter. The loose form (no finite verb, any opening) fires
    on 2,782 (12.0%) and sweeps in verbless nominal clauses, which are
    independent sentences in Hebrew -- so the preposition test is doing real
    work, not tightening for its own sake.
    """
    dep = set()
    for p in sorted(glob.glob(str(HEB / "*.xml"))):
        for s in ET.parse(p).getroot().iter("sentence"):
            ws = [w for w in s.iter("w")]
            if not ws:
                continue
            m = re.search(r"([A-Za-z0-9]+)\s+(\d+):(\d+)", ws[0].get("ref") or "")
            if not m:
                continue
            if any(w.get("type") in FINITE for w in ws if w.get("class") == "verb"):
                continue
            if ws[0].get("class") != "prep":
                continue
            if not any(w.get("class") == "verb" and w.get("type") in NONFIN
                       for w in ws):
                continue
            dep.add(f"{m.group(1).title()}.{m.group(2)}.{m.group(3)}")
    return dep


def units(bychap, dep):
    """Bottom-up binding: a dependent verse joins the unit before it.

    -> {(book, chapter): [[v...], [v...], ...]}
    """
    out = {}
    for k, vs in bychap.items():
        bk, ch = k
        seq = []
        for v in sorted(vs):
            if seq and f"{bk}.{ch}.{v}" in dep:
                seq[-1].append(v)
            else:
                seq.append([v])
        out[k] = seq
    return out


def negated():
    """-> {(ref, lemma)} for verbs MACULA's frame layer marks negative.

    7,713 of 92,567 verbs are negated (8.3%), and some lemmas are negated more
    often than asserted -- `'avah` 96.3%, `yakhol` 75.1%, `dynamai` 55.5%.
    Matching bare lemmas inverts every one of those.
    """
    out = set()
    p = OUT / "frames.jsonl.gz"
    if not p.exists():
        return out
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            if d.get("polarity") == "negative" and d.get("lemma"):
                out.add((d["ref"], nfc(d["lemma"])))
    return out


def opposites():
    """-> {hebrew_lemma: {hebrew_lemma, ...}} via WordNet antonyms.

    2026-09-12: not hot = cold, and in a lot of cases the negative sentence
    will agree with the positive within a pattern. Psalm 103 is built
    on it -- v8 states the grace formula positively and v9-10 restates it by
    negating its opposite, which is why v8 anchors 9-12.

    Route: lemma -> its English glosses -> WordNet antonyms of those -> back to
    any lemma carrying the antonym as a gloss. Antonymy covers 24.3% of content
    lemmas. This is the ONLY place the two halves meet: polarity comes from
    MACULA, opposition from WordNet.
    """
    p = OUT / "wordnet-map.jsonl.gz"
    if not p.exists():
        return {}
    dominant = {}
    lang = {}
    gloss_to_lemma = collections.defaultdict(set)
    lemma_gloss = collections.defaultdict(set)
    lemma_ant = collections.defaultdict(set)
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            lm = nfc(d["lemma"])
            lang[lm] = d.get("lang")
            # CONTEXT HOP 3: only the lemma's DOMINANT gloss may be used as a
            # reverse key. Allowing any gloss let one negated verb explode into
            # dozens of lemmas that merely share a rare secondary rendering.
            best = max(d["map"], key=lambda m: m["n"])["via"]
            dominant[lm] = best
            gloss_to_lemma[best].add(lm)
            for m in d["map"]:
                lemma_gloss[lm].add(m["via"])
                # CONTEXT HOP 2: antonyms only of the DOMINANT gloss's synsets.
                if m["via"] != best:
                    continue
                for a in (m.get("rel") or {}).get("antonym", []):
                    lemma_ant[lm].add(a.split(".")[0])
    out = {}
    for lm, ants in lemma_ant.items():
        hit = set()
        for a in ants:
            # CONTEXT HOP 1: never cross languages. A Hebrew verb's opposite
            # must be a Hebrew lemma.
            hit |= {x for x in gloss_to_lemma.get(a, set())
                    if lang.get(x) == lang.get(lm)}
        hit.discard(lm)
        if hit:
            out[lm] = hit
    return out


def profile(verses, per, neg=frozenset(), opp=None, invert=False):
    """Signals present in a span, as (kind, key) pairs.

    **Polarity is part of the key.** A negated lemma is a DIFFERENT signal from
    the same lemma asserted, so Psalm 103 v9 ("nor keep his ANGER forever") no
    longer matches passages that assert anger. Without this the module reads
    Psalm 103 as a text about anger -- twice over, since v8 is `'erekh 'appayim`,
    literally "long of anger".

    With `invert`, a negated lemma ALSO emits its opposite as an asserted
    signal, so "not accusing" can agree with "merciful".
    """
    lem, tagged = [], []
    for r in verses:
        for l in per.get(r, []):
            lem.append(l)
            tagged.append((r, l))
    sig, content = set(), set()
    for r, l in tagged:
        if not l or l in STOP:
            continue
        content.add(l)
        if (r, l) in neg:
            sig.add(("lemma!", l))
            if invert and opp:
                for o in opp.get(l, ()):
                    # its OWN kind: an inferred signal must never outweigh an
                    # observed one. Inferred lemmas are rare, so on raw IDF they
                    # score HIGHEST -- noise outranking evidence.
                    sig.add(("lemma~", o))
        else:
            sig.add(("lemma", l))
    # generational depth: a kinship term in construct with itself
    for i in range(len(lem) - 1):
        if lem[i] in KIN and lem[i] == lem[i + 1]:
            sig.add(("gendepth", lem[i]))
    return sig, content


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--span", default="Psa.103.13-18",
                    help="Book.Chap.Start-End")
    ap.add_argument("--width", type=int, default=3)
    ap.add_argument("--seed-max", type=int, default=40,
                    help="a signal is a SEED if it occurs in <= this many verses")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--invert", action="store_true",
                    help="a negated lemma also emits its opposite (not X = Y)")
    ap.add_argument("--bind", action="store_true",
                    help="bind dependent verses to the unit before (bottom-up)")
    a = ap.parse_args()

    print("loading Hebrew ...", flush=True)
    per = load_hebrew()
    print(f"  verses {len(per):,}")

    # verse-level document frequency for every content lemma
    df = collections.Counter()
    for r, ls in per.items():
        for l in {x for x in ls if x and x not in STOP}:
            df[l] += 1
    N = len(per)

    m = re.match(r"([\w]+)\.(\d+)\.(\d+)-(\d+)$", a.span)
    if not m:
        print("bad --span"); return 2
    b, c, s, e = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
    query = [f"{b}.{c}.{v}" for v in range(s, e + 1)]
    neg = negated()
    opp = opposites() if a.invert else None
    print(f"  negated (ref,lemma) pairs {len(neg):,}")
    if opp is not None:
        print(f"  lemmas with an opposite   {len(opp):,}")
    qsig, qcontent = profile(query, per, neg, opp, a.invert)

    seeds = {l for l in qcontent if df[l] <= a.seed_max}
    print(f"\nQUERY {a.span}   signals {len(qsig)}   seeds {len(seeds)}")
    for l in sorted(seeds, key=lambda x: df[x]):
        print(f"    seed  {l:<12} {df[l]:>4} verses")
    if not seeds:
        print("  no seed in the query span; nothing to start from")
        return 1

    # PRUNE: only verses carrying a seed are ever expanded into spans
    carriers = {r for r, ls in per.items() if seeds & set(ls)}
    print(f"\n  verses carrying any seed  {len(carriers):,} "
          f"of {N:,}  ({100*len(carriers)/N:.2f}%)")

    # build candidate spans around carriers only
    bychap = collections.defaultdict(set)
    for r in per:
        bk, ch, v = key(r)
        bychap[(bk, ch)].add(v)
    # BOTTOM-UP BINDING: dependent verses join the unit before them, so no
    # window can cut between v17 and v18.
    dep = dependents() if a.bind else set()
    uns = units(bychap, dep)
    print(f"  dependent verses bound    {len(dep):,}")

    cands = set()
    for r in carriers:
        bk, ch, v = key(r)
        seq = uns[(bk, ch)]
        idx = next((i for i, u in enumerate(seq) if v in u), None)
        if idx is None:
            continue
        for start in range(max(0, idx - a.width + 1), idx + 1):
            win = seq[start:start + a.width]
            if len(win) < a.width:
                continue
            cands.add((bk, ch, win[0][0], win[-1][-1]))
    print(f"  candidate spans built     {len(cands):,}  "
          f"(vs {sum(len(v) for v in bychap.values()):,} verses x widths if unpruned)")

    def w(sig):
        kind, k = sig
        if kind == "gendepth":
            return 6.0
        base = math.log(N / max(df.get(k, 1), 1))
        # An inferred opposite is evidence of a different order from a word
        # actually present. Discounted so it can break ties and add recall
        # without ever outranking observation. Measured 2026-09-12: undiscounted
        # it put three spurious spans above Exo.34.6-8, the source text of the
        # very formula being matched.
        return base * 0.25 if kind == "lemma~" else base

    scored = []
    for bk, ch, s2, e2 in cands:
        refs = [f"{bk}.{ch}.{v}" for v in range(s2, e2 + 1)]
        # any overlap with the query is self-match, not evidence
        if (bk, ch) == (b, c) and not (e2 < s or s2 > e):
            continue
        sig, _ = profile(refs, per, neg, opp, a.invert)
        shared = qsig & sig
        if len(shared) < 3:
            continue
        scored.append((sum(w(x) for x in shared), f"{bk}.{ch}.{s2}-{e2}", shared))
    scored.sort(reverse=True)

    print(f"\n  spans sharing 3+ signals  {len(scored):,}")
    print(f"\nTOP MATCHES for {a.span}\n")
    seen = set()
    shown = 0
    for sc, lbl, shared in scored:
        bk, ch = lbl.split(".")[0], lbl.split(".")[1]
        if (bk, ch) in seen:
            continue
        seen.add((bk, ch))
        shown += 1
        if shown > a.top:
            break
        rare = sorted(shared, key=lambda x: -w(x))[:6]
        print(f"  {sc:6.1f}  {lbl:<16} " +
              " ".join(f"{k}" for _, k in rare))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
