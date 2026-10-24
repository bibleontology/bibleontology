"""Greek-to-Greek similarity before the Greek structure exists (plan Step 3).

2026-09-27: the Greek might need tweaking after the structure is built out.
Until then two kinds of evidence are available:
  context   the Greek words sharing a clause with it, read straight off
            MACULA's Greek clause trees (<wg class="cl">), content words
            only, PPMI weighted: the same measure as the Hebrew context
  behind    the Hebrew words the Septuagint translators used it for: two
            Greek words are close when they render the same Hebrew
TESTED on Greek near-synonym pairs, never tuned to.

    python tools/wordgraph/greek.py test
"""
import collections
import math
import random
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import crosslang as XL                                     # noqa: E402
import similarity as SIM                                   # noqa: E402

XID = "{http://www.w3.org/XML/1998/namespace}id"
GREEK = SIM.ROOT / "data" / "raw" / "macula" / "greek"
CONTENT = {"noun", "verb", "adj", "adv", "num"}
PAIRS = [
    ("ἀγαπάω", "φιλέω"), ("ὁράω", "βλέπω"), ("ἱερόν", "ναός"),
    ("γινώσκω", "οἶδα"), ("ἔρχομαι", "πορεύομαι"), ("λέγω", "λαλέω"),
    ("ἁμαρτία", "ἀνομία"), ("νόμος", "ἐντολή"), ("σῴζω", "ῥύομαι"),
    ("φόβος", "τρόμος"), ("χαρά", "ἀγαλλίασις"), ("ἔλεος", "οἰκτιρμός"),
    ("λαός", "ἔθνος"), ("κύριος", "θεός"), ("προσεύχομαι", "δέομαι"),
    ("δύναμις", "ἐξουσία"), ("ἀλήθεια", "πίστις"), ("θάνατος", "ἀποθνῄσκω"),
    ("δόξα", "τιμή"), ("ψυχή", "καρδία"),
]


def own_words(cl):
    """The <w> of a clause, stopping at any clause nested inside it."""
    out = []
    for ch in cl:
        if ch.tag == "w":
            out.append(ch)
        elif ch.get("class") != "cl":
            out.extend(own_words(ch))
    return out


def context_vectors(occ_lex, lex, min_count=5):
    co = collections.defaultdict(collections.Counter)
    freq = collections.Counter()
    for p in sorted(GREEK.glob("*.xml")):
        if not p.name[:2].isdigit():
            continue                       # the whole-NT files repeat all
        for cl in ET.parse(p).getroot().iter("wg"):
            if cl.get("class") != "cl":
                continue
            # the clause's OWN words, not those of clauses nested in it (as
            # the Hebrew context counts them)
            ls = {occ_lex.get(w.get(XID)) for w in own_words(cl)
                  if w.get("class") in CONTENT} - {None}
            ls = {l for l in ls if lex.get(l, {}).get("count", 0) >= min_count}
            for a in ls:
                freq[a] += 1
                for b in ls:
                    if a != b:
                        co[a][b] += 1
    total = sum(freq.values())
    out = {}
    for a, row in co.items():
        v = {b: math.log(n * total / (freq[a] * freq[b]))
             for b, n in row.items()}
        v = {b: x for b, x in v.items() if x > 0}
        if v:
            out[a] = v
    return out


def behind_vectors(X):
    """Greek lexeme -> {Hebrew lexeme: times the Septuagint used it for it}."""
    behind = collections.defaultdict(collections.Counter)
    for h, v in X.sept.items():
        for s, c in v.items():
            behind[s][h] += c
    out = {}
    for s, row in behind.items():
        for g in X.greek_by_strong.get(s, []):
            out[g] = dict(row)
    return out


def test():
    X = XL.Index()
    _, _, occ_lex = SIM.load()
    V = {"context": context_vectors(occ_lex, X.lex), "behind": behind_vectors(X)}
    ps = [(X.get(a, "G"), X.get(b, "G"), a, b) for a, b in PAIRS]
    miss = [(a, b) for x, y, a, b in ps if not x or not y]
    ps = [p for p in ps if p[0] and p[1]]
    print(f"{len(ps)} Greek pairs" + (f" ({miss} not found)" if miss else ""))
    common = [l for l, d in X.lex.items() if d.get("lang") == "G"
              and d.get("count", 0) >= 20]
    rng = random.Random(7)
    rand = [(rng.choice(common), rng.choice(common)) for _ in range(400)]
    pool = set(common)
    for name, vec in V.items():
        syn = [SIM.cos(vec.get(a), vec.get(b)) for a, b, *_ in ps]
        syn = [s for s in syn if s is not None]
        rnd = [SIM.cos(vec.get(a), vec.get(b)) for a, b in rand if a != b]
        rnd = [s for s in rnd if s is not None]
        auc = sum((s > r) + .5 * (s == r) for s in syn for r in rnd) \
            / max(1, len(syn) * len(rnd))
        top = sum((b in {x for _, x in SIM.neighbours(vec, a, 10, pool)}) or
                  (a in {x for _, x in SIM.neighbours(vec, b, 10, pool)})
                  for a, b, *_ in ps)
        print(f"  {name:8} coverage {len(syn)}/{len(ps)}  AUC {auc:.2f}  "
              f"partner in top-10: {top}/{len(ps)}")
    return V


if __name__ == "__main__":
    test()
