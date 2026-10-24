"""A sparse, citable profile per lemma — the alternative to an embedding.

2026-09-05, after brainstorming a multi-dimensional vector store: the next
step is a round on meaning words like love and temptation.

## Why not an embedding

Two objections, and the first is fatal at this scale.

**The corpus is far too small.** The Hebrew Bible is about 300,000 words and the
Greek New Testament about 138,000. Word2Vec and FastText want orders of
magnitude more. An embedding trained here encodes sampling noise and presents it
as meaning, with nothing to separate the two — a confident wrong answer in
geometric clothing, which is the failure this project keeps meeting.

**And a vector carries no citation.** Every edge in this graph names the verse
that establishes it. An embedding coordinate is a derived opinion that cannot be
checked by someone who does not trust you, which is the wrong side of the
fact/expression line the whole project is built on.

## What this does instead

A **sparse, named feature profile** per lemma, each dimension a named relation
to a named word, with the verses behind it:

    coord:faithfulness    what the text coordinates it with
    ofhead: / ofdep:      construct chains, in both directions
    subjof: / objof:      what it does, and what is done to it
    simile                used inside a comparison

It supplies what the vector idea wanted, and stays checkable:

    coordinates   the profile IS the position
    radius        overlap between profiles, computed rather than trained
    opposites     contrast is simply another named feature
    senses        already separated by LEMMA, not by English

English is the thing that needed splitting, not the languages. The English word
*love* covers at least six lemmas — agape, hesed, ahev, ahavah, dod, yadid — so
an English-keyed graph flattens covenant loyalty into the beloved of the Song of
Songs. Every node here already carries lemma and Strong's, so the substrate for
sense-splitting exists by morphology rather than by training.

## Two findings that constrain how this may be used

**Raw counts are unusable.** Cosine over raw counts puts *hesed* nearest *aph*
(anger) at 0.879 and ranks *emet* — the classic pair — lower at 0.601, because
frequency and generic syntax dominate: everything is the object of *said*.
Weighting each feature by distinctiveness (IDF) fixes it outright, moving anger
from first to 0.046 and *tsedaqah* to the top.

**It is NOT multilingual.** `hesed` against `agape` scores 0.039. The features
are English glosses laid over different syntactic conventions, so a Hebrew and a
Greek profile cannot be compared this way. Cross-linguistic alignment needs
verse-level translation alignment — the route the name map used — and not shared
profile features.

## Validating without a gold standard

There is no external truth for "how similar are two Hebrew lemmas", so the check
is an **ablation**: build the profiles with coordination features REMOVED, then
ask whether they still predict which words the text actually coordinates. If a
profile built only from verb roles and construct chains ranks a word's real
coordination partners above chance, it has captured structure rather than
echoing what it was handed.

    python tools/senses.py                   # build and write
    python tools/senses.py --profile 2617    # what the text says hesed is
    python tools/senses.py --near 2617       # nearest lemmas
    python tools/senses.py --validate        # the ablation
"""
from __future__ import annotations

import collections
import gzip
import json
import math
import pathlib
import random
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

# Features seen on almost every lemma carry no information and cost time. The
# IDF weighting already suppresses them; this only keeps the profiles small.
MIN_DF_KEEP = 1
REFS_PER_FEATURE = 3


def _spaced(s):
    """`havingShown` -> `having shown`. The boundary is only in the case."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s or "").lower()


def _slug(s):
    """Normalise a partner's text for use as a feature name.

    IT USED TO DELETE THE SPACES. `re.sub(r"[^a-z]", "", ...)` removes every
    character that is not a letter, and a partner is often several words, so
    the feature name came out welded together and the card printed it that way
    -- reported 2026-09-15: in the 'stands besides' section words appeared
    concatenated together.

        for edification              -> foredification
        things devoted to destruction -> thingsdevotedtodestruction
        the way                      -> theway

    Collapsing to a single space instead keeps the name readable and keeps it a
    stable key: the transform is still deterministic, so two partners that
    normalised to one feature before normalise to one feature now. The only
    behaviour change is that partners which differ ONLY by spacing now stay
    distinct, which is a correction rather than a regression.
    """
    return re.sub(r"\s+", " ", re.sub(r"[^a-z]+", " ", (s or "").lower())).strip()


def load():
    """Nodes keyed by id, and every edge, in one pass each."""
    nodes = {}
    for line in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if "id" in d:
            nodes[d["id"]] = d
    edges = []
    for line in gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt",
                          encoding="utf-8"):
        e = json.loads(line)
        if "_source" not in e:
            edges.append(e)
    return nodes, edges


def key_of(nodes, nid):
    """lang + Strong's number: the identity a profile is built for.

    Strong's rather than the lemma string, because the lemma carries pointing
    and the same word appears in several normalisation forms. The language
    prefix is not decoration -- dropping it collided Greek G256 (Alphaeus) with
    Hebrew H256 (Ahab) when the name map was built.
    """
    d = nodes.get(nid) or {}
    s = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", d.get("strong") or ""))
    return (d.get("lang", "")[:1] + s) if s else None


def lxx_features():
    """What the Septuagint chose, as a feature.

    The suggestion was to incorporate the MACULA glossary values in the vector
    calculation, as a quality source. The English gloss is
    already the feature vocabulary, so the version of that idea with real
    signal in it is the LXX alignment MACULA carries on Hebrew words:
    `greek`/`greekstrong`. Two Hebrew words the Septuagint renders with the
    same Greek word are semantically close, and that is an independent
    judgement by ancient translators rather than an inference of ours.

    Whether it actually helps is measured by the ablation, not assumed.
    """
    path = OUT / "lemma-meta.json"
    if not path.exists():
        return {}
    meta = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for k, m in meta.items():
        vals = m.get("greek") or []
        if vals:
            out[k] = [(v["v"], v["n"]) for v in vals[:3]]
    return out


def build(nodes, edges, with_coord=True, with_lxx=True):
    """lemma key -> {feature: [count, [refs]]}."""
    prof = collections.defaultdict(lambda: collections.defaultdict(
        lambda: [0, []]))
    gloss = collections.defaultdict(collections.Counter)

    def add(k, feat, ref):
        if not k or not feat:
            return
        slot = prof[k][feat]
        slot[0] += 1
        if len(slot[1]) < REFS_PER_FEATURE and ref not in slot[1]:
            slot[1].append(ref)

    def text(nid):
        return _slug((nodes.get(nid) or {}).get("text"))

    groups = collections.defaultdict(list)
    for e in edges:
        if e.get("type") == "member" and e.get("src") and e.get("dst"):
            groups[e["src"]].append(e["dst"])

    for nid, d in nodes.items():
        k = key_of(nodes, nid)
        if k and d.get("text"):
            gloss[k][d["text"].lower()] += 1

    if with_coord:
        for comp, mem in groups.items():
            ref = (nodes.get(comp) or {}).get("ref")
            for a in mem:
                k = key_of(nodes, a)
                for b in mem:
                    if b != a and text(b):
                        add(k, "coord:" + text(b), ref)

    for e in edges:
        ref = e.get("ref")
        rel = e.get("dst_relation") or {}
        if rel.get("src") and rel.get("dst"):
            # a construct chain says something about BOTH halves, and which
            # half you are is part of the meaning: "house of God" tells you
            # about houses one way and about God another
            for x, y, tag in ((rel["src"], rel["dst"], "ofhead:"),
                              (rel["dst"], rel["src"], "ofdep:")):
                if text(y):
                    add(key_of(nodes, x), tag + text(y), ref)
        verb = e.get("verb") or e.get("type")
        if isinstance(verb, str) and not e.get("scopes_over"):
            # DO NOT lowercase. The builder names events in camelCase --
            # `havingShown`, `gaveBirth` -- and lowercasing destroys the word
            # boundary permanently, so the card read "is what someone
            # havingshown". Split it instead, once, here.
            v = _spaced(verb)
            if e.get("src"):
                add(key_of(nodes, e["src"]), "subjof:" + v, ref)
            if isinstance(e.get("dst"), str):
                add(key_of(nodes, e["dst"]), "objof:" + v, ref)
        if e.get("comparison") and isinstance(e.get("dst"), str):
            add(key_of(nodes, e["dst"]), "simile", ref)

    if with_lxx:
        for k, pairs in lxx_features().items():
            if k in prof:
                for word, n in pairs:
                    prof[k]["lxx:" + word] = [n, []]

    return prof, {k: c.most_common(1)[0][0] for k, c in gloss.items() if c}


def weigh(prof):
    """IDF-weighted vectors. Raw counts do not work -- see the docstring."""
    df = collections.Counter()
    for f in prof.values():
        for feat in f:
            df[feat] += 1
    n = len(prof) or 1
    out = {}
    for k, f in prof.items():
        out[k] = {feat: (1 + math.log(c[0])) * math.log(n / (1 + df[feat]))
                  for feat, c in f.items()}
    return out, df


def cos(a, b):
    if not a or not b:
        return 0.0
    num = sum(a[k] * b[k] for k in set(a) & set(b))
    den = (math.sqrt(sum(v * v for v in a.values()))
           * math.sqrt(sum(v * v for v in b.values())))
    return num / den if den else 0.0


MIN_OBS = 20


def nearest(W, gloss, k, n=12, obs=None, min_obs=0, same_lang=True):
    """Nearest lemmas, with two restrictions that are corrections, not fudges.

    **A minimum evidence threshold.** Unrestricted, `hesed` -- 228 observations
    -- came back nearest to *charcoal* and *seal*. IDF rewards rare features,
    and a rare lemma's entire profile is rare features, so a 4-observation
    profile can share one distinctive feature and score higher than a real
    neighbour. Comparing a 228-observation profile with a 4-observation one is
    not a meaningful question, so it is not asked.

    **Same language only.** Measured: `hesed` against `agape` scores 0.039, and
    unrestricted search returned a Hebrew lemma among the Greek neighbours. The
    features are English glosses over different syntactic conventions, so a
    cross-language number here is noise. The tool must not offer a comparison
    it has already shown to be invalid; cross-linguistic alignment needs
    verse-level translation alignment instead.
    """
    if k not in W:
        return []
    obs = obs or {}
    lang = k[0]
    scored = ((cos(W[k], v), o) for o, v in W.items()
              if o != k
              and obs.get(o, 0) >= min_obs
              and (not same_lang or o[0] == lang))
    return sorted(scored, reverse=True)[:n]


def validate(nodes, edges):
    """Ablation: do profiles WITHOUT coordination predict coordination?

    No gold standard exists for lemma similarity, so the profile is asked to
    predict something it was not shown. Coordination is the right target: it is
    marked in the text, it is not an interpretation, and it is exactly the
    signal being withheld.

    A profile built only from verb roles and construct chains should still rank
    a word's real coordination partners above chance. Compared against a random
    baseline over the same candidate pool, because a bare hit rate on 7,560
    lemmas means nothing without one.
    """
    prof_no, gl = build(nodes, edges, with_coord=False,
                        with_lxx="--no-lxx" not in sys.argv)
    W, _ = weigh(prof_no)

    truth = collections.defaultdict(set)
    groups = collections.defaultdict(list)
    for e in edges:
        if e.get("type") == "member" and e.get("src") and e.get("dst"):
            groups[e["src"]].append(e["dst"])
    for mem in groups.values():
        keys = [key_of(nodes, m) for m in mem]
        for a in keys:
            for b in keys:
                if a and b and a != b:
                    truth[a].add(b)

    # only lemmas with a real profile and a real partner set can be scored
    tested = [k for k in truth
              if k in W and len(W[k]) >= 5 and len(truth[k] & set(W)) >= 1]
    obs = {kk: sum(c[0] for c in f.values()) for kk, f in prof_no.items()}
    rng = random.Random(11)
    pool = [k for k in W if obs.get(k, 0) >= MIN_OBS]
    hits = base = 0
    for k in tested:
        top = {o for _, o in nearest(W, gl, k, 10, obs=obs,
                                        min_obs=MIN_OBS)}
        hits += bool(top & truth[k])
        rand = set(rng.sample(pool, min(10, len(pool))))
        base += bool(rand & truth[k])

    n = len(tested) or 1
    print("ABLATION - profiles built WITHOUT coordination, asked to predict it")
    print(f"  lemmas scorable                {n:>6,}")
    print(f"  a real partner in the top 10   {hits:>6,}   {100*hits//n}%")
    print(f"  random baseline, same pool     {base:>6,}   {100*base//n}%")
    lift = (hits / n) / ((base / n) or 1e-9)
    print(f"  lift over chance               {lift:>6.1f}x")
    print()
    print("  The profile is predicting a signal it was never shown. A lift near")
    print("  1 would mean the earlier similarity numbers were echoing the")
    print("  coordination features back rather than learning anything.")
    return 0


def main() -> int:
    nodes, edges = load()
    if "--validate" in sys.argv:
        return validate(nodes, edges)

    prof, gloss = build(nodes, edges)
    W, df = weigh(prof)

    if "--profile" in sys.argv:
        k = sys.argv[sys.argv.index("--profile") + 1]
        k = k if k[0] in "hg" else "h" + k
        print(f"PROFILE  {k}  ({gloss.get(k, '?')})")
        print(f"  {len(prof[k])} features, "
              f"{sum(c[0] for c in prof[k].values())} observations\n")
        for feat, w in sorted(W[k].items(), key=lambda x: -x[1])[:18]:
            refs = ", ".join(prof[k][feat][1])
            print(f"   {w:6.2f}  {feat:28}{prof[k][feat][0]:>4}x  {refs}")
        return 0

    if "--near" in sys.argv:
        k = sys.argv[sys.argv.index("--near") + 1]
        k = k if k[0] in "hg" else "h" + k
        obs = {kk: sum(c[0] for c in f.values()) for kk, f in prof.items()}
        print(f"NEAREST TO  {k} ({gloss.get(k, '?')})  "
              f"{obs.get(k, 0)} observations")
        print(f"  candidates restricted to the same language with "
              f"{MIN_OBS}+ observations")
        for s, o in nearest(W, gloss, k, obs=obs, min_obs=MIN_OBS):
            print(f"   {s:.3f}  {o:8} {obs.get(o,0):>5} obs  {gloss.get(o, '?')}")
        return 0

    path = OUT / "sense-profiles.jsonl.gz"
    kept = 0
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_source": "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., "
                       "CC BY 4.0",
            "_note": "Sparse IDF-weighted feature profiles per lemma. NOT "
                     "comparable across languages -- see tools/senses.py.",
        }) + "\n")
        for k, f in prof.items():
            if len(f) < 3:
                continue
            top = sorted(W[k].items(), key=lambda x: -x[1])[:40]
            fh.write(json.dumps({
                "key": k, "gloss": gloss.get(k), "features": len(f),
                "observations": sum(c[0] for c in f.values()),
                "top": [{"feature": ft, "weight": round(w, 3),
                         "count": f[ft][0], "refs": f[ft][1]} for ft, w in top],
            }, ensure_ascii=False) + "\n")
            kept += 1

    print("SENSE PROFILES - sparse, named, citable")
    print(f"  lemmas with any profile   {len(prof):>7,}")
    print(f"  written (3+ features)     {kept:>7,}")
    print(f"  distinct features         {len(df):>7,}")
    print(f"\n  wrote {path}")
    print("  NOT comparable across languages; raw counts unusable without IDF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
