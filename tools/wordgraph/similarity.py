"""Lexeme similarity from three independent kinds of evidence, and a test of
whether each one works.

2026-09-27: can it be used to measure the similarity between two
words? Before building on any measure, it is TESTED: known near-synonym
pairs (standard Hebrew lexicography) must score higher than random pairs of
comparable frequency, and a word's partner must appear among its nearest
neighbours.

Evidence, one vector per lexeme each:
  lxx      the Greek words (Strong's) the Septuagint translators used for it
           (MACULA's alignment)                       -- a translation
  bsb      the English the Berean editors tagged to its Strong's number
                                                       -- a translation
  context  the other lexemes in the same clauses (PPMI weighted) from the
           clean structure builder's clauses           -- the Hebrew alone

    python tools/wordgraph/similarity.py test
    python tools/wordgraph/similarity.py near <lemma> [n]
"""
import collections
import gzip
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
MIN_COUNT = 5          # lexemes rarer than this get no context vector
# Context counts CONTENT words only: a conjunction, preposition, article,
# suffix pronoun or particle shares a clause with nearly everything.
CONTENT = {"noun", "verb", "adj", "adv", "num"}
EN_STOP = {"the", "a", "an", "to", "of", "and", "will", "shall", "be", "is",
           "was", "were", "are", "has", "have", "had", "been", "his", "her",
           "their", "its", "my", "your", "our", "in", "on", "for", "with",
           "from", "by", "at", "that", "who", "which", "not", "i", "you",
           "he", "she", "it", "we", "they", "him", "them", "me", "us"}


def en_base(w):
    """A crude English base form, for counting renderings together."""
    for suf, rep in (("ies", "y"), ("ied", "y"), ("sses", "ss"), ("es", ""),
                     ("s", ""), ("ed", ""), ("ing", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3 and \
                not (suf == "s" and w.endswith("ss")):
            return w[: -len(suf)] + rep
    return w

# Standard near-synonym (or tight semantic-field) pairs. The TEST set, never
# a tuning target: nothing below is fitted to them.
PAIRS = [
    ("חַטָּאת", "עָוֹן"), ("עָוֹן", "פֶּשַׁע"), ("חַטָּאת", "פֶּשַׁע"),
    ("אָמַר", "דָבַר"), ("שָׁמַר", "נָצַר"), ("רָאָה", "חָזָה"),
    ("בָּרָא", "עָשָׂה"), ("תּוֹרָה", "מִצְוָה"), ("מִשְׁפָּט", "חֹק"),
    ("חֹק", "מִצְוָה"), ("אֹיֵב", "צַר"), ("צֶדֶק", "צְדָקָה"),
    ("שִׂמְחָה", "גִּיל"), ("יָרֵא", "פָּחַד"), ("חֶסֶד", "אֱמֶת"),
    ("רַחֲמִים", "חֶסֶד"), ("זָבַח", "עֹלָה"), ("כֹּהֵן", "לֵוִי"),
    ("אֶרֶץ", "אֲדָמָה"), ("עִיר", "קִרְיָה"), ("גּוֹי", "עַם"),
    ("לֵב", "נֶפֶשׁ"), ("שָׁמַיִם", "רָקִיעַ"), ("יָשַׁע", "נָצַל"),
]


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            yield {k: (v["value"] if isinstance(v, dict) and "value" in v
                       and "source" in v else v) for k, v in d.items()}


def load():
    lex = {d["id"]: d for d in rows(OUT / "word-lexemes.jsonl.gz")}
    layers = {d["id"]: d for d in rows(OUT / "word-lexeme-layers.jsonl.gz")}
    occ_lex = {}
    for d in rows(OUT / "word-edges.jsonl.gz"):
        if d.get("edge") == "of_lexeme":
            occ_lex[d["from"]] = d["to"]
    return lex, layers, occ_lex


def vectors(lex, layers, occ_lex):
    lxx, bsb = {}, {}
    for lid, L in layers.items():
        s = (L.get("septuagint") or {}).get("counts") or []
        v = collections.Counter()
        for c in s:
            v[c["greekstrong"]] += c["count"]
        if v:
            lxx[lid] = v
        b = (L.get("bsb_renderings") or {}).get("counts") or []
        v = collections.Counter()
        for c in b:
            # the BASE of each content word in the tagged phrase: "the
            # houses" and "a house" both count for "house"
            ws = [w for w in (x.strip(".,;:!?'\"()[]") for x in
                              c["english"].lower().split())
                  if w and w not in EN_STOP]
            for w in ws:
                v[en_base(w)] += c["count"] / len(ws)
        if v:
            bsb[lid] = v
    # context: lexemes co-occurring in a clause (the clause's own words)
    occ_class = {d["id"]: d.get("class")
                 for d in rows(OUT / "word-occurrences.jsonl.gz")}
    co = collections.defaultdict(collections.Counter)
    freq = collections.Counter()
    for d in rows(OUT / "structure-nodes.jsonl.gz"):
        if not d.get("clause"):
            continue
        ls = {occ_lex.get(i) for i in d.get("src") or []
              if occ_class.get(i) in CONTENT} - {None}
        ls = {l for l in ls if lex.get(l, {}).get("count", 0) >= MIN_COUNT}
        for a in ls:
            freq[a] += 1
            for b in ls:
                if a != b:
                    co[a][b] += 1
    total = sum(freq.values())
    ctx = {}
    for a, row in co.items():
        v = {}
        for b, n in row.items():
            pmi = math.log((n * total) / (freq[a] * freq[b]))
            if pmi > 0:
                v[b] = pmi
        if v:
            ctx[a] = v
    return {"lxx": lxx, "bsb": bsb, "context": ctx}


def cos(u, v):
    if not u or not v:
        return None
    dot = sum(x * v.get(k, 0) for k, x in u.items())
    nu = math.sqrt(sum(x * x for x in u.values()))
    nv = math.sqrt(sum(x * x for x in v.values()))
    return dot / (nu * nv) if nu and nv else None


def bare(s):
    return "".join(ch for ch in (s or "") if "א" <= ch <= "ת")


class ByLemma(dict):
    """Lemma -> the most frequent Hebrew lexeme; looked up by the pointed
    form, else by consonants (MACULA points some lemmas differently from
    the usual citation form: עָוֺן / עָוֹן)."""

    def __init__(self, lex):
        super().__init__()
        self.cons = {}
        for lid, L in lex.items():
            if L.get("lang") != "H":
                continue
            for table, k in ((self, L.get("lemma")),
                             (self.cons, bare(L.get("lemma")))):
                if k not in table or L["count"] > lex[table[k]]["count"]:
                    table[k] = lid

    def get(self, k, default=None):
        return dict.get(self, k) or self.cons.get(bare(k), default)


def by_lemma(lex):
    return ByLemma(lex)


def neighbours(vec, lid, n=10, pool=None):
    u = vec.get(lid)
    if not u:
        return []
    out = []
    for other in (pool or vec):
        if other == lid or other not in vec:
            continue
        s = cos(u, vec[other])
        if s:
            out.append((s, other))
    return sorted(out, reverse=True)[:n]


def test():
    lex, layers, occ_lex = load()
    V = vectors(lex, layers, occ_lex)
    L = by_lemma(lex)
    pairs = [(L.get(a), L.get(b), a, b) for a, b in PAIRS]
    missing = [(a, b) for x, y, a, b in pairs if not x or not y]
    pairs = [p for p in pairs if p[0] and p[1]]
    print(f"{len(pairs)} test pairs ({len(missing)} not found: {missing})")
    common = [l for l, d in lex.items() if d.get("lang") == "H"
              and d.get("count", 0) >= 20]
    rng = random.Random(7)
    rand = [(rng.choice(common), rng.choice(common)) for _ in range(400)]
    pool = set(common)
    for name, vec in V.items():
        syn = [cos(vec.get(a), vec.get(b)) for a, b, *_ in pairs]
        syn_ok = [s for s in syn if s is not None]
        rnd = [cos(vec.get(a), vec.get(b)) for a, b in rand if a != b]
        rnd = [s for s in rnd if s is not None]
        # AUC: chance a synonym pair outscores a random pair
        auc = sum((s > r) + 0.5 * (s == r) for s in syn_ok for r in rnd) \
            / max(1, len(syn_ok) * len(rnd))
        # partner in the top 10 neighbours (among frequent lexemes)
        top = 0
        for a, b, *_ in pairs:
            nb = {x for _, x in neighbours(vec, a, 10, pool)}
            nb2 = {x for _, x in neighbours(vec, b, 10, pool)}
            top += (b in nb) or (a in nb2)
        print(f"  {name:8} coverage {len(syn_ok)}/{len(pairs)} pairs  "
              f"mean syn {sum(syn_ok) / max(1, len(syn_ok)):.2f} vs "
              f"random {sum(rnd) / max(1, len(rnd)):.2f}  AUC {auc:.2f}  "
              f"partner in top-10: {top}/{len(pairs)}")
    return V, lex, L


def near(lemma, n=12):
    lex, layers, occ_lex = load()
    V = vectors(lex, layers, occ_lex)
    L = by_lemma(lex)
    lid = L.get(lemma)
    if not lid:
        print("no such lemma")
        return
    pool = {l for l, d in lex.items() if d.get("count", 0) >= 5}
    for name, vec in V.items():
        nb = neighbours(vec, lid, n, pool)
        print(f"{name}: " + ", ".join(
            f"{lex[x]['lemma']} ({(layers.get(x, {}).get('glosses') or {}).get('usual')}) {s:.2f}"
            for s, x in nb))


if __name__ == "__main__":
    if sys.argv[1:2] == ["near"]:
        near(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 12)
    else:
        test()
