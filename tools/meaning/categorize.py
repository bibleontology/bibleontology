"""Can every word be given a category? Measured, before an ontology claims it.

2026-09-28: the question was what an ideal node-categorization RDFS
ontology would look like, so that nodes can be completely categorized and
types/meanings understood. The recommendation is docs/MEANING-ONTOLOGY.md.
This is its measurement: how far the top level it proposes reaches over the
corpus, from what is already on disk, and where it cannot reach.

THE TOP LEVEL is WordNet's lexicographer files (its "supersenses": 26 for
nouns, 15 for verbs), reached through MACULA's English glosses by
out/wordnet-map.jsonl.gz (tools/wordnetmap.py). Chosen because it is free,
standard, and COMPLETE BY CONSTRUCTION: every WordNet noun and verb sense
sits in exactly one file. Under PRINCIPLES 44a it is an overlay derived via
English, every gloss variant kept.

A lemma's category is a DISTRIBUTION, not a pick: each gloss contributes by
how often MACULA renders the lemma so, and within a gloss each WordNet sense
by its SemCor frequency (+1, so an untagged sense is not zero). Then:
    decided   the top category holds >= 60% of the weight
    leaning   40-60%
    split     below 40% — reported, never averaged away (chesed)
Coverage is counted in TOKENS, since a reader meets tokens.

THE INDEPENDENT CHECK: a Hebrew noun and the Greek the Septuagint renders it
with are categorized from DIFFERENT English glosses by different
translators. Where both are decided, how often do they land in the same
category? That is agreement no single gloss could manufacture.

    python tools/meaning/categorize.py            # report
    python tools/meaning/categorize.py --write    # also out/meaning-categories.jsonl.gz
"""
import argparse
import collections
import gzip
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"

# WordNet lexicographer file -> the proposed top class (docs/MEANING-ONTOLOGY.md)
NOUN_CLASS = {
    "noun.person": "PersonalBeing", "noun.group": "Group",
    "noun.animal": "Animal", "noun.plant": "Plant", "noun.body": "BodyPart",
    "noun.artifact": "Artifact", "noun.food": "Food",
    "noun.substance": "Substance", "noun.object": "NaturalObject",
    "noun.location": "Place", "noun.phenomenon": "Phenomenon",
    "noun.event": "Event", "noun.act": "Act", "noun.process": "Event",
    "noun.state": "State", "noun.feeling": "Feeling",
    "noun.cognition": "Cognition", "noun.communication": "Communication",
    "noun.attribute": "Attribute", "noun.quantity": "Quantity",
    "noun.time": "Time", "noun.possession": "Possession",
    "noun.relation": "Relation", "noun.motive": "Motive",
    "noun.shape": "Shape", "noun.Tops": "Abstraction",
}
DECIDED, LEANING = 0.6, 0.4


def distribution(row):
    """{category: share} for one lemma row of the WordNet map."""
    by_via = collections.defaultdict(list)
    for m in row.get("map") or []:
        by_via[m["via"]].append(m)
    w = collections.Counter()
    for via, ms in by_via.items():
        n = ms[0].get("n") or 1
        tot = sum((m.get("count") or 0) + 1 for m in ms)
        for m in ms:
            w[m["lexname"]] += n * ((m.get("count") or 0) + 1) / tot
    s = sum(w.values())
    return {k: v / s for k, v in w.most_common()} if s else {}


def verdict(dist):
    if not dist:
        return "unmapped"
    top = next(iter(dist.values()))
    return "decided" if top >= DECIDED else \
        "leaning" if top >= LEANING else "split"


def load():
    rows = []
    for line in gzip.open(OUT / "wordnet-map.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(line)
        if r.get("lemma"):
            rows.append(r)
    return rows


def lexemes():
    """Every lexeme with its token count and language, and each Hebrew
    lexeme's commonest Septuagint Greek (by Strong's), from the word graph."""
    lex, greek_by_strong = {}, collections.defaultdict(collections.Counter)
    for line in gzip.open(OUT / "word-lexemes.jsonl.gz", "rt", encoding="utf-8"):
        d = json.loads(line)
        if d.get("kind") != "lexeme":
            continue
        lang = d["lang"]["value"]
        lemma = d["lemma"]["value"]
        lex[d["id"]] = {"lemma": lemma, "lang": lang,
                        "count": d["count"]["value"]}
        if lang == "G" and d["strong"]["value"]:
            greek_by_strong[str(d["strong"]["value"]).lstrip("0")][lemma] += \
                d["count"]["value"]
    lxx = {}
    for line in gzip.open(OUT / "word-lexeme-layers.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        s = ((d.get("septuagint") or {}).get("value") or {}).get("counts") or []
        if s:
            by = collections.Counter()
            for c in s:
                by[str(c.get("greekstrong") or "").lstrip("0")] += c["count"]
            gs = by.most_common(1)[0][0]
            if greek_by_strong.get(gs):
                lxx[d["id"]] = greek_by_strong[gs].most_common(1)[0][0]
    return lex, lxx


LANG = {"H": "hebrew", "A": "hebrew", "G": "greek"}
POS = {"noun": "noun", "verb": "verb", "adj": "adj"}
# Words MACULA files as nouns that are quantifiers, not things: WordNet
# has no noun sense of "all", so the English bridge sends them astray
# (כֹּל -> Cognition 82% on the first run). Settled here, by their gloss.
QUANTIFIER_GLOSS = {"all", "every", "each", "whole", "any", "none", "some"}


def occurrences():
    """(lang, lemma) -> MACULA's commonest class, whether it is a proper
    noun, and its tokens: the FLOOR (PRINCIPLES 44a: overlay, never floor —
    where the map's part of speech disagrees with MACULA's class, MACULA
    wins)."""
    # read by the clean builder's own source reader, both languages (the
    # word graph's occurrence file holds only the Hebrew), keyed by the
    # normalised lemma (the map and MACULA differ in pointing)
    sys.path.insert(0, str(ROOT / "tools" / "builder"))
    import source as SRC
    c = collections.defaultdict(collections.Counter)
    proper = collections.Counter()
    for lang in ("hebrew", "greek"):
        for path in SRC.files(lang):
            _, ws = SRC.load(path, lang)
            for w in ws.values():
                key = (lang, SRC.norm(w.get("lemma")))
                c[key][w.get("class")] += 1
                if w.get("type") == "proper" or (
                        lang == "greek" and (w.get("lemma") or "x")[0].isupper()
                        and w.get("class") == "noun"):
                    proper[key] += 1
    return {k: (v.most_common(1)[0][0], proper[k] * 2 > sum(v.values()),
                sum(v.values())) for k, v in c.items()}, SRC.norm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    rows = load()
    floor, norm = occurrences()
    by_lemma = {}
    stats = collections.Counter()
    dropped = collections.Counter()
    for r in rows:
        r["lemma"] = norm(r["lemma"])
        cl, is_proper, _ = floor.get((r["lang"], r["lemma"]),
                                     (None, False, 0))
        if POS.get(cl) != r["pos"] or is_proper:
            dropped[(r["pos"], cl, is_proper)] += r.get("tokens") or 0
            continue
        dist = distribution(r)
        usual = max((m for m in r.get("map") or []), key=lambda m: m.get("n")
                    or 0, default={}).get("via")
        if r["pos"] == "noun" and usual in QUANTIFIER_GLOSS:
            dist = {"noun.quantity": 1.0}
        v = verdict(dist)
        key = (r["lang"], r["lemma"])
        top = next(iter(dist), None)
        by_lemma[key] = {"pos": r["pos"], "tokens": r.get("tokens") or 0,
                         "dist": dist, "verdict": v, "top": top,
                         "reliable": r.get("reliable")}
        stats[(r["pos"], v)] += r.get("tokens") or 0
        stats[(r["pos"], "lemmas", v)] += 1

    # ---- 1. coverage by part of speech, in tokens
    print("COVERAGE of the WordNet map, in tokens (lemmas in brackets)")
    for pos in ("noun", "verb", "adj"):
        tot = sum(stats[(pos, v)] for v in
                  ("decided", "leaning", "split", "unmapped"))
        if not tot:
            continue
        parts = "  ".join(
            f"{v} {stats[(pos, v)] / tot:5.1%} ({stats[(pos, 'lemmas', v)]:,})"
            for v in ("decided", "leaning", "split"))
        print(f"  {pos:5} {tot:>8,} tokens   {parts}")

    print("  (map rows set aside because MACULA's class disagrees, or the "
          "word is a proper name, in tokens:",
          dict((f"{p}->{c}{' proper' if pr else ''}", n) for (p, c, pr), n
               in dropped.most_common(6)), ")")

    # ---- 2. the whole of the content words, by MACULA's class: how many
    # does the map categorize at all?
    lex, lxx = lexemes()
    reach = collections.Counter()
    for key, (cl, is_proper, n) in floor.items():
        kind = "proper name" if is_proper else cl
        if kind not in ("noun", "verb", "adj", "proper name"):
            continue
        got = by_lemma.get(key)
        reach[(kind, "all")] += n
        if got and got["verdict"] in ("decided", "leaning"):
            reach[(kind, "categorized")] += n
    print("\nREACH over ALL content tokens (MACULA's class decides what "
          "counts):")
    for kind in ("noun", "verb", "adj", "proper name"):
        t = reach[(kind, "all")]
        if t:
            print(f"  {kind:11} {t:>8,} tokens   decided or leaning "
                  f"{reach[(kind, 'categorized')] / t:5.1%}")

    # ---- 3. the category distribution itself (nouns, tokens, decided+leaning)
    cls = collections.Counter()
    for (l, lem), x in by_lemma.items():
        if x["pos"] == "noun" and x["verdict"] in ("decided", "leaning"):
            cls[NOUN_CLASS.get(x["top"], x["top"])] += x["tokens"]
    tot = sum(cls.values())
    print("\nNOUN TOKENS BY PROPOSED TOP CLASS (decided or leaning):")
    for k, v in cls.most_common():
        print(f"  {k:16} {v:>7,}  {v / tot:5.1%}")

    # ---- 4. the independent check: Hebrew noun vs its Septuagint Greek
    agree = collections.Counter()
    shown = []
    for lid, g in lxx.items():
        x = lex.get(lid) or {}
        h = by_lemma.get(("hebrew", norm(x.get("lemma"))))
        gr = by_lemma.get(("greek", norm(g)))
        if not h or not gr or h["pos"] != "noun" or gr["pos"] != "noun":
            continue
        if h["verdict"] != "decided" or gr["verdict"] != "decided":
            continue
        same = h["top"] == gr["top"]
        agree[same] += 1
        agree[("tok", same)] += h["tokens"]
        if not same and len(shown) < 400:
            shown.append((h["tokens"], x["lemma"], h["top"], g, gr["top"]))
    n = agree[True] + agree[False]
    if n:
        t = agree[("tok", True)] + agree[("tok", False)]
        print(f"\nHEBREW NOUN vs ITS SEPTUAGINT GREEK, both decided: "
              f"same category {agree[True]:,} of {n:,} lemmas "
              f"({agree[True] / n:.0%}); by tokens "
              f"{agree[('tok', True)] / t:.0%}")
        print("  commonest disagreements:")
        for t_, hl, ht, gl, gt in sorted(shown, reverse=True)[:14]:
            print(f"    {hl} ({t_:,}) {ht}  vs  {gl} {gt}")

    # ---- 5. a sample to read by eye, token-weighted
    rng = random.Random(28)
    nouns = [(k, x) for k, x in by_lemma.items() if x["pos"] == "noun"]
    pick = rng.choices(nouns, weights=[x["tokens"] for _, x in nouns], k=30)
    print("\nSAMPLE (token-weighted), for reading:")
    for (l, lem), x in sorted(set((k, id(x)) and (k, x["top"]) for k, x in pick)):
        y = by_lemma[(l, lem)]
        d = ", ".join(f"{NOUN_CLASS.get(c, c)} {s:.0%}"
                      for c, s in list(y["dist"].items())[:3])
        print(f"  {l[:2]} {lem:14} {y['verdict']:8} {d}")

    if a.write:
        with gzip.open(OUT / "meaning-categories.jsonl.gz", "wt",
                       encoding="utf-8") as f:
            f.write(json.dumps({"_source": "Derived via English (PRINCIPLES "
                                "44a) from out/wordnet-map.jsonl.gz: MACULA "
                                "glosses, CC BY 4.0; WordNet 3.0, Princeton. "
                                "Overlay only.", "_what": "Per lemma: its "
                                "distribution over WordNet lexicographer files "
                                "and the proposed top class; verdict decided/"
                                "leaning/split. tools/meaning/categorize.py."},
                               ensure_ascii=False) + "\n")
            for (l, lem), x in sorted(by_lemma.items()):
                f.write(json.dumps({"lemma": lem, "lang": l, "pos": x["pos"],
                                    "tokens": x["tokens"],
                                    "verdict": x["verdict"],
                                    "class": NOUN_CLASS.get(x["top"], x["top"]),
                                    "dist": {k: round(v, 3) for k, v in
                                             x["dist"].items()}},
                                   ensure_ascii=False) + "\n")
        print("\nwrote out/meaning-categories.jsonl.gz")


if __name__ == "__main__":
    sys.exit(main())
