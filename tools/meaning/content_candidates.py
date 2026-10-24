"""Candidate pairs by CONTENT: verses that share rare words, whatever their
sentence structure (P-53, approved 2026-09-29).

2026-09-29: good matches must not be left out because of too much attention
to structure rather than content; of John 1:1-5, the hope was to catch Gen 1
in those 5 verses; and near cross-language matches might weigh higher than
exact intra-language matches. Structure only PROPOSES — Flash reads every
candidate on its content before anything is shown — so a looser proposer
costs money, not precision.

Two kinds, the cross-language kind first in the queue:

  CROSS   a Greek verse and a Hebrew verse sharing rare words through the
          Septuagint: each Hebrew lexeme's Greek renderings (MACULA's LXX
          column, out/lemma-meta.json) inverted, so a Greek word stands for
          the Hebrew words it translated. A rendering that does not resolve
          to a Greek lexeme may resolve at one letter's distance if exactly
          one lexeme is that close: ראשית's column reads "ἀρξὴ", so John
          1:1's ἀρχή never met Gen 1:1's "beginning" (a spelling fault in
          the source, ξ for χ).
  WITHIN  two verses of one language sharing rare words.

A verse's content is its content lemmas (noun, verb, adjective; proper
names left out — shared names proposed lists: Manasseh, Zebulun, Asher).
A pair's score is the summed rarity (idf, in the Hebrew space for CROSS) of
the lemmas it shares rarer than COMMON; it needs MIN_SHARED. Neighbours
within NEAR verses of one chapter are left out. Each verse keeps its TOP
partners of each kind. Pairs already judged are dropped.

    python tools/meaning/content_candidates.py   -> out/content-candidates.jsonl.gz
"""
from __future__ import annotations

import collections
import gzip
import json
import math
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
CONTENT = {"noun", "verb", "adj"}
COMMON = 4.0          # idf below this is too common to propose a pair
MAX_DF = 400
MIN_SHARED = 2
TOP = 3
NEAR = 3
SHARE = 0.2           # a Hebrew rendering counts if it is 20%+ of the Greek word's top one
ONE_RARE = 5.5        # across languages, one shared word this rare may propose a pair


def rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith('{"_'):
                yield json.loads(line)


def fold(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip(",.;·:’'\" ")


def one_off(a, b):
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1


def main():
    lem = collections.defaultdict(set)
    lang = {}
    gloss = collections.defaultdict(collections.Counter)
    forms = {}                                   # folded Greek surface form -> g-key
    classes = collections.defaultdict(collections.Counter)
    for n in rows(OUT / "structure-nodes.jsonl.gz"):
        if not n.get("word") or n.get("class") not in CONTENT or n.get("proper") \
                or n.get("type") == "proper":
            continue
        d = "".join(c for c in (n.get("strong") or "") if c.isdigit())
        if not d:
            continue
        g = n.get("lang") == "greek"
        k = ("g" if g else "h") + str(int(d))
        classes[k][n["class"]] += 1
        v = n["id"].split("#")[0]
        lem[v].add(k)
        lang[v] = "g" if g else "h"
        gloss[k][(n.get("text") or "").lower()] += 1
        if g:
            forms.setdefault(fold(n.get("original")), k)
    cls = {k: c.most_common(1)[0][0] for k, c in classes.items()}
    gclass, hclass = cls, cls
    # the Septuagint, inverted: Greek lexeme -> the Hebrew lexemes it rendered
    lmeta = json.loads((OUT / "lemma-meta.json").read_text(encoding="utf-8"))
    by_len = collections.defaultdict(list)
    for f in forms:
        by_len[len(f)].append(f)
    back = collections.defaultdict(collections.Counter)
    fuzzy = 0
    for hk, meta in lmeta.items():
        if not hk.startswith("h"):
            continue
        for x in meta.get("greek") or []:
            f = fold(x.get("v"))
            if len(f) < 3:
                continue
            # the column writes ξ for χ throughout ("αρξοντες" for ἄρχοντες,
            # "ψυξη" for ψυχή; 1,284 renderings). Where both readings are
            # Greek words, the one whose part of speech matches the Hebrew:
            # ראשית's "αρξη" is ἀρχή (beginning, a noun), not ἄρξῃ (you will
            # begin, Luke 14:9), which read as-is it had become
            gk, gx = forms.get(f), forms.get(f.replace("ξ", "χ")) if "ξ" in f else None
            if gk and gx and gk != gx and gclass.get(gx) == hclass.get(hk) != gclass.get(gk):
                gk = gx
            gk = gk or gx
            if not gk and len(f) >= 4:
                near = [c for c in by_len[len(f)] if one_off(f, c)]
                if len({forms[c] for c in near}) == 1:
                    gk, fuzzy = forms[near[0]], fuzzy + 1
            if gk:
                back[gk][hk] += x.get("n") or 0
    heb_for = {}
    for gk, c in back.items():
        top = c.most_common(1)[0][1]
        heb_for[gk] = {hk for hk, n in c.most_common(3) if n >= SHARE * top}
    # a Greek word the Septuagint never uses borrows the bridge of its
    # sibling: John's σκοτία (darkness) from the Septuagint's σκότος, one
    # root, four letters in common, the sibling with the most renderings
    glemma = {}
    for n_ in rows(OUT / "structure-nodes.jsonl.gz"):
        if n_.get("word") and n_.get("lang") == "greek" and n_.get("strong"):
            k = "g" + str(int("".join(ch for ch in n_["strong"] if ch.isdigit()) or 0))
            glemma.setdefault(k, fold(n_.get("lemma")))
    stems = collections.defaultdict(list)
    for k, l in glemma.items():
        if k in heb_for and len(l) >= 5:
            stems[l[:4]].append(k)
    borrowed = 0
    for k, l in glemma.items():
        if k not in heb_for and len(l) >= 5 and stems.get(l[:4]):
            sib = max(stems[l[:4]], key=lambda s: sum(back[s].values()))
            heb_for[k] = heb_for[sib]
            borrowed += 1
    # rarity: within each language; CROSS in the Hebrew space
    hverses = [v for v in lem if lang[v] == "h"]
    df = collections.Counter(k for ks in lem.values() for k in ks)
    N = len(lem)
    idf = {k: math.log(N / n) for k, n in df.items()}
    hdf = collections.Counter(k for v in hverses for k in lem[v])
    hidf = {k: math.log(len(hverses) / n) for k, n in hdf.items()}
    judged = set()
    p = OUT / "pair-judgments.jsonl.gz"
    if p.exists():
        judged = {tuple(sorted((r["a"], r["b"]))) for r in rows(p)}

    def near(a, b):
        ba, ca, va = a.split(".")
        bb, cb, vb = b.split(".")
        return ba == bb and ca == cb and abs(int(va) - int(vb)) <= NEAR

    def pairs(index, weight, sets):
        score, shared = collections.defaultdict(float), collections.defaultdict(list)
        for k, vs in index.items():
            for i, a in enumerate(vs):
                for b in vs[i + 1:]:
                    if lang[a] == lang[b] and sets == "cross":
                        continue
                    pr = (a, b) if a < b else (b, a)
                    score[pr] += weight[k]
                    shared[pr].append(k)
        return score, shared

    # WITHIN: one language
    index = collections.defaultdict(list)
    for v, ks in lem.items():
        for k in ks:
            if df[k] <= MAX_DF and idf[k] >= COMMON:
                index[k].append(v)
    wscore, wshared = pairs(index, idf, "within")
    # CROSS: Greek verses in the Hebrew space, against Hebrew verses
    hspace = {}
    for v, ks in lem.items():
        if lang[v] == "h":
            hspace[v] = ks
        else:
            hspace[v] = {hk for gk in ks for hk in heb_for.get(gk, ())}
    cindex = collections.defaultdict(list)
    for v, ks in hspace.items():
        for k in ks:
            if hdf.get(k, 0) and hdf[k] <= MAX_DF and hidf[k] >= COMMON:
                cindex[k].append(v)
    cscore, cshared = pairs(cindex, hidf, "cross")

    def keep(score, shared, one_rare=None):
        """one_rare: across languages a single very rare shared word may
        propose a pair (John 1:1 and Gen 1:1 share only "beginning"; God is
        everywhere)"""
        best = collections.defaultdict(list)
        for pr, s in score.items():
            ok = len(shared[pr]) >= MIN_SHARED or (one_rare and s >= one_rare)
            if not ok or near(*pr):
                continue
            for v in pr:
                best[v].append((s, pr))
        out = {}
        for v, xs in best.items():
            for s, pr in sorted(xs, reverse=True)[:TOP]:
                out[pr] = s
        return out

    cross, within = keep(cscore, cshared, one_rare=ONE_RARE), keep(wscore, wshared)
    within = {pr: s for pr, s in within.items() if pr not in cross}
    hgloss = {}
    for hk in {k for ks in cshared.values() for k in ks}:
        hgloss[hk] = gloss[hk].most_common(1)[0][0] if gloss.get(hk) else hk
    out = []
    for kind, got, shared, gl in (("cross", cross, cshared, hgloss), ("within", within, wshared, None)):
        for pr, s in sorted(got.items(), key=lambda x: -x[1]):
            if pr in judged:
                continue
            out.append({"a": pr[0], "b": pr[1], "kind": kind, "score": round(s, 2),
                        "shared": [(gl or {}).get(k) or gloss[k].most_common(1)[0][0]
                                   for k in shared[pr]]})
    with gzip.open(OUT / "content-candidates.jsonl.gz", "wt", encoding="utf-8") as f:
        f.write(json.dumps({"_note": "Verse pairs proposed by shared rare words, cross-language "
                            "(through the Septuagint) first (tools/meaning/content_candidates.py), "
                            "for Flash to judge."}) + "\n")
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    nc = sum(r["kind"] == "cross" for r in out)
    print(f"Septuagint bridge: {len(heb_for):,} Greek lexemes ({fuzzy} renderings resolved at one "
          f"letter, {borrowed} borrowed from a sibling); ἀρχή -> "
          + ", ".join(f"{h} {gloss[h].most_common(1)[0][0]} ({back['g746'][h]})"
                      for h in sorted(heb_for.get("g746", ()))))
    for v in ("Jhn.1.1", "Gen.1.1"):
        print(f"  {v} in the Hebrew space: " + ", ".join(
            f"{k}{'' if k in cindex and v in cindex[k] else '(not indexed)'}" for k in sorted(hspace.get(v, ()))))
    print(f"cross {len(cross):,} kept, {nc:,} new; within {len(within):,} kept, {len(out) - nc:,} new")
    for want in (("Jhn.1.1", "Gen.1.1"), ("Jhn.1.3", "Gen.1.1"), ("Jhn.1.5", "Gen.1.4"),
                 ("Jhn.1.4", "Jhn.8.12"), ("Jhn.1.5", "1Jn.2.8"), ("Jhn.1.1", "1Jn.1.1")):
        pr = tuple(sorted(want))
        for kind, got, score, shared in (("cross", cross, cscore, cshared), ("within", within, wscore, wshared)):
            if pr in score:
                print(f"  {want[0]} / {want[1]} [{kind}]: " + ("kept" if pr in got else "not kept")
                      + f", {score[pr]:.1f} on {len(shared[pr])} shared")
                break
        else:
            print(f"  {want[0]} / {want[1]}: no shared rare word")


if __name__ == "__main__":
    main()
