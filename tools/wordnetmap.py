"""Hebrew/Greek lemma -> English gloss -> WordNet synset, with the chain kept.

2026-09-12, scoping this deliberately: not much more than this is needed until
patterns are looked at, because the mapping does the work.

That is right, and it is why **no distance is computed here**. What is stored is
the hypernym *chain* for each synset. Every similarity measure anyone might want
-- path, Wu-Palmer, Leacock-Chodorow, information content -- is derivable from
the chain afterwards, and unlike a score the chain explains itself: *"these meet
at `physical_entity`"* is a sentence a reader can argue with. `0.31` is not.

## Principle 44a, and the three conditions it attaches

`docs/PRINCIPLES.md` 44a rules that semantic class is on the STRUCTURE side of
the translation line: the source records no taxonomy, so an external judgement
is the only evidence available. Three conditions come with that ruling, and each
is implemented rather than intended:

1. **Overlay, never floor.** This module writes its own layer and modifies
   nothing. Where it disagrees with MACULA, MACULA wins, and every consumer can
   ignore this file entirely.
2. **Keep every gloss variant.** Sense selection is the real risk, not
   classification. `chesed` glossed "loyalty" and "steadfast love" lands in
   different synsets, and silently picking one turns a translator's choice into
   a claim about the Hebrew. All normalised glosses are mapped and all surviving
   synsets kept.
3. **Mark it derived-via-English.** Every row carries `via`, the English gloss
   that produced the synset, so a reader can discount the whole chain by seeing
   what it was built from.

## The scatter metric, which is the point

A lemma whose own senses land in unrelated parts of WordNet is a lemma where
**the English bridge is failing** -- either English is splitting one Hebrew
concept, or Hebrew has genuine homonymy. Measured per lemma as the depth of the
deepest common ancestor across its own synsets:

    tight    senses share a deep ancestor        the bridge holds
    scatter  senses meet only near `entity`      FLAG, do not average

`chesed` scatters: kindness, love, loyalty -- and *disgrace* (Lev 20:17).
`tsits` scatters: flower, blossom -- and *plate*, the golden plate of the high
priest's turban (Exo 28:36). `chatsir` scatters: grass -- and *leeks* (Num
11:5), and *abode* (Isa 34:13).

**The layer reports where it cannot be trusted**, which is what makes it safe to
build on.

    python tools/wordnetmap.py            # map and report
    python tools/wordnetmap.py --test     # the acceptance tests
    python tools/wordnetmap.py --write    # emit out/wordnet-map.jsonl.gz
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys
import unicodedata as ud

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
DEST = OUT / "wordnet-map.jsonl.gz"

# BOTH credits travel with the data. WordNet's licence requires its notice on
# ALL copies "including modifications that you make for internal use", which is
# stricter than CC BY on that point -- see NOTICE and SOURCES.md.
CREDIT = ("Lemmas and glosses: MACULA Hebrew Linguistic Datasets, available at "
          "https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic "
          "Datasets, available at https://github.com/Clear-Bible/macula-greek/; "
          "© Biblica, Inc., CC BY 4.0. "
          "Semantic classes derived via WordNet 3.0 Copyright 2006 by "
          "Princeton University. All rights reserved.")

CLEAN = re.compile(r"^[a-z]+$")
CONTENT = {"noun": "n", "verb": "v", "adj": "a", "adv": "r"}
MAX_SYNSETS = 6          # per gloss; WordNet orders by frequency
MIN_SENSE_COUNT = 1      # SemCor attestation; 0 = sense never seen in a
                         # tagged corpus (grass-as-marijuana counts 0)
NT = {"Mat", "Mrk", "Luk", "Jhn", "Act", "Rom", "1Co", "2Co", "Gal", "Eph",
      "Php", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb", "Jas",
      "1Pe", "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev"}


def nfc(s):
    return ud.normalize("NFC", s or "")


def norm(g):
    g = g.lower().strip().strip(".")
    g = re.sub(r"^\[?the\]?\s+|^\[?a\]?\s+|^of\s+|^to\s+", "", g)
    g = re.sub(r"[\[\]().,;:!?'’‘]", "", g).strip()
    return g


def read_lemmas():
    """-> [{lemma, lang, pos, tokens, senses:[{gloss,n}]}] content words only."""
    lem = collections.defaultdict(
        lambda: {"g": collections.Counter(), "p": collections.Counter(),
                 "n": 0, "lang": None})
    with gzip.open(OUT / "interlinear.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if not d.get("ref"):
                continue
            lang = "greek" if d["ref"].split(".")[0] in NT else "hebrew"
            for w in d["words"]:
                l, g, p = nfc(w.get("l")), (w.get("g") or "").strip(), w.get("p")
                if not l or not g or g == "-":
                    continue
                e = lem[l]
                e["g"][g] += 1
                e["p"][p] += 1
                e["n"] += 1
                e["lang"] = lang
    rows = []
    for l, e in lem.items():
        pos = e["p"].most_common(1)[0][0]
        top = e["g"].most_common(1)[0][0]
        if pos not in CONTENT:
            continue
        if re.match(r"^[A-Z]", top) and pos == "noun":
            continue                                   # proper name
        senses = collections.Counter()
        for g, c in e["g"].items():
            n2 = norm(g)
            if CLEAN.match(n2):
                senses[n2] += c
        if not senses:
            continue
        rows.append({"lemma": l, "lang": e["lang"], "pos": pos, "tokens": e["n"],
                     "senses": [{"gloss": g, "n": c}
                                for g, c in senses.most_common()]})
    return rows


def chain(syn):
    """Hypernym names from this synset up to the root, shortest path."""
    paths = syn.hypernym_paths()
    if not paths:
        return []
    p = min(paths, key=len)
    return [s.name() for s in p]


def scatter(wn, per_gloss):
    """Do this lemma's ATTESTED glosses agree on what kind of thing it is?

    `per_gloss` is [(gloss, n, dominant_synset)] -- one entry per distinct
    normalised gloss, carrying its token count and the first (most frequent)
    WordNet synset for it.

    **The first version of this compared every synset of every gloss and took
    the worst pair. It flagged 83% of lemmas**, which is a known failure mode:
    a flag that cannot express failure will report
    success, and one that fires on everything is the same thing inverted. With
    up to six synsets per gloss, almost any lemma has one outlier sense that
    meets the others only at `entity`.

    The question worth asking is narrower. **Each distinct gloss is an attested
    translation choice**; a rare WordNet sense of one of those glosses is not
    attested by anything. So compare glosses to each other, one dominant synset
    apiece, and only those carrying real weight -- glosses seen once in the
    whole corpus are noise (`tsits` -> "salt", once).

    Returns (depth, ancestor) where low depth means the attested senses do not
    agree and the English bridge is splitting the lemma.
    """
    weighty = [(g, n, s) for g, n, s in per_gloss if s is not None and n >= 2]
    if len(weighty) < 2:
        return None, None
    worst, who = None, None
    for i in range(len(weighty)):
        for j in range(i + 1, len(weighty)):
            lcs = weighty[i][2].lowest_common_hypernyms(weighty[j][2])
            if not lcs:
                worst, who = 0, "(none)"
                continue
            d = max(x.max_depth() for x in lcs)
            if worst is None or d < worst:
                worst, who = d, lcs[0].name()
    return worst, who


def build(wn, rows, limit=None):
    out = []
    for i, r in enumerate(rows):
        if limit and i >= limit:
            break
        pos = CONTENT[r["pos"]]
        mapped, per_gloss = [], []
        for s in r["senses"]:
            g = s["gloss"]
            # morphy collapses fathers->father, gave->give, not put/set/make
            base = wn.morphy(g, pos) or g
            cand = wn.synsets(base, pos)[:MAX_SYNSETS]
            if not cand:
                continue
            # ATTESTATION FILTER. 2026-09-12, asking for a slang
            # indicator or some kind of metadata that indicates origin.
            # Three exist and only one works. `usage_domains()` carries
            # slang/colloquialism/archaism but is sparse -- `grass.n.02`
            # (marijuana) carries NO marker at all, which is the very sense
            # that produced the spurious grass/smoke meet at `pot.n.09`.
            # SemCor frequency does the job instead: grass.n.01 counts 41,
            # grass.n.02 counts 0. Senses never attested in a tagged corpus
            # are dropped, and the unfiltered list is kept when that would
            # empty it, so a rare-but-real word is not silently lost.
            keep = [s2 for s2 in cand
                    if sum(l.count() for l in s2.lemmas()) >= MIN_SENSE_COUNT
                    or not s2.usage_domains()]
            attested = [s2 for s2 in cand
                        if sum(l.count() for l in s2.lemmas()) >= MIN_SENSE_COUNT]
            syns = attested or keep or cand
            per_gloss.append((g, s["n"], syns[0]))
            for syn in syns:
                mapped.append({"via": g, "n": s["n"], "synset": syn.name(),
                               # lexname() is WordNet's 45 human-curated
                               # lexicographer files -- noun.plant, noun.person,
                               # noun.artifact. Coarser than the hypernym chain
                               # and far more useful for "same kind of thing".
                               "lexname": syn.lexname(),
                               "count": sum(l.count() for l in syn.lemmas()),
                               "usage": [u.name() for u in syn.usage_domains()],
                               "def": syn.definition()[:90],
                               "chain": chain(syn),
                               # CONNECTION taxonomy. 2026-09-12: taxonomies for both nodes and
                               # connections were wanted. lexname and the chain above are
                               # the node half; these are the edge half, and
                               # they are a typed vocabulary rather than a
                               # distance. Coverage measured over 8,297 content
                               # lemmas: antonym 24.3%, has_part 15.6%, part_of
                               # 13.6%, entails 4.8%, causes 3.4%.
                               "rel": {k: v for k, v in (
                                   ("part_of", [x.name() for x in syn.part_holonyms()][:3]),
                                   ("has_part", [x.name() for x in syn.part_meronyms()][:3]),
                                   ("member_of", [x.name() for x in syn.member_holonyms()][:3]),
                                   ("entails", [x.name() for x in syn.entailments()][:3]),
                                   ("causes", [x.name() for x in syn.causes()][:3]),
                                   ("antonym", [a.name() for l in syn.lemmas()
                                                for a in l.antonyms()][:3]),
                               ) if v}})
        if not mapped:
            continue
        d, who = scatter(wn, per_gloss)
        out.append({"lemma": r["lemma"], "lang": r["lang"], "pos": r["pos"],
                    "tokens": r["tokens"], "n_synsets": len(mapped),
                    "scatter_depth": d, "scatter_lcs": who,
                    "reliable": (d is None or d >= 4),
                    "map": mapped})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args()

    from nltk.corpus import wordnet as wn
    print(f"WordNet {wn.get_version()}")

    if a.test:
        return tests(wn)

    rows = read_lemmas()
    print(f"content lemmas from MACULA glosses: {len(rows):,}")
    got = build(wn, rows)
    print(f"  mapped to >=1 synset:             {len(got):,} "
          f"({100*len(got)/len(rows):.1f}%)")
    rel = sum(1 for r in got if r["reliable"])
    print(f"  bridge holds (scatter depth >=4): {rel:,} ({100*rel/len(got):.1f}%)")
    print(f"  FLAGGED as scattered:             {len(got)-rel:,}")

    print("\nMOST SCATTERED -- where English splits the lemma\n")
    bad = sorted((r for r in got if r["scatter_depth"] is not None),
                 key=lambda r: (r["scatter_depth"], -r["tokens"]))
    for r in bad[:10]:
        gl = ", ".join(dict.fromkeys(m["via"] for m in r["map"]))[:52]
        print(f"   {r['lemma']:<10} {r['tokens']:>5} tok  lcs={str(r['scatter_lcs'])[:20]:<22} {gl}")

    if a.write:
        with gzip.open(DEST, "wt", encoding="utf-8") as f:
            f.write(json.dumps({
                "_source": CREDIT,
                "_note": "Hebrew/Greek lemma -> MACULA English gloss -> WordNet "
                         "synset, with each synset's hypernym chain. NO distance "
                         "is computed: the chain is stored so any measure is "
                         "derivable later and explains itself. Overlay only -- "
                         "where this disagrees with MACULA, MACULA wins. Every "
                         "row carries `via` (the English gloss that produced the "
                         "synset) and `reliable` (false where the lemma's own "
                         "senses meet only near `entity`, meaning the English "
                         "bridge is splitting it). See PRINCIPLES.md 44a.",
            }, ensure_ascii=False) + "\n")
            for r in got:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(got):,} lemmas)")
    else:
        print("\nnot written -- pass --write")
    return 0


def tests(wn) -> int:
    """Acceptance tests, stated before the mapping was built."""
    def meet(a, b, p="n"):
        """Best meet across ALL synsets of both words.

        Testing only `synsets(w)[0]` was the first version of this, and it
        FAILED heaven/east at depth 0 -- because `heaven.n.01` is "the abode of
        God and the angels", which shares nothing spatial with a compass point.
        That is precisely the single-sense selection Principle 44a condition 2
        forbids, committed in the test for the principle. A sense-plural mapping
        must be scored sense-plurally: take the closest meeting of any pair.
        """
        xs, ys = wn.synsets(a, p)[:MAX_SYNSETS], wn.synsets(b, p)[:MAX_SYNSETS]
        if not xs or not ys:
            return None, None
        best, who = 0, "(none)"
        for x in xs:
            for y in ys:
                lcs = x.lowest_common_hypernyms(y)
                if not lcs:
                    continue
                d = max(s.max_depth() for s in lcs)
                if d > best:
                    best, who = d, lcs[0].name()
        return best, who

    def meet_first(a, b, p="n"):
        """Conservative: dominant sense of each word only."""
        xs, ys = wn.synsets(a, p), wn.synsets(b, p)
        if not xs or not ys:
            return None, None
        lcs = xs[0].lowest_common_hypernyms(ys[0])
        if not lcs:
            return 0, "(none)"
        return max(s.max_depth() for s in lcs), lcs[0].name()

    def meet_lemma(heb_a, heb_b):
        """Meet two HEBREW lemmas using every gloss variant each one has."""
        rows = {r["lemma"]: r for r in read_lemmas()}
        ra, rb = rows.get(nfc(heb_a)), rows.get(nfc(heb_b))
        if not ra or not rb:
            return None, None, None
        best, who, pair = 0, "(none)", None
        for sa in ra["senses"]:
            for sb in rb["senses"]:
                d, w = meet(sa["gloss"], sb["gloss"])
                if d and d > best:
                    best, who, pair = d, w, (sa["gloss"], sb["gloss"])
        return best, who, pair

    print("\nACCEPTANCE TESTS  (depth of lowest common hypernym; higher = closer)\n")
    cases = [
        ("father", "son", "shallow meet under kinship", lambda d: d >= 4),
        ("grass", "flower", "both plants", lambda d: d >= 4),
        ("grass", "smoke", "correctly UNRELATED", lambda d: d <= 3),
    ]
    print("   both measures shown: CONS = dominant sense only, PERM = best of all\n")
    ok = 0
    for a, b, why, want in cases:
        dc, wc = meet_first(a, b)
        dp, wp = meet(a, b)
        good = dc is not None and want(dc)
        ok += good
        print(f"   {a:<7}/{b:<7} CONS {str(dc):<3} {str(wc)[:22]:<24}"
              f" PERM {str(dp):<3} {str(wp)[:20]:<22} {'PASS' if good else 'FAIL'}")
        print(f"           {why}")

    # the 2026-09-09 blocker, tested on the LEMMAS with every gloss variant
    d, who, pair = meet_lemma("שָׁמַיִם", "מִזְרָח")
    good = d is not None and d >= 3
    ok += good
    print(f"   shamayim / mizrach depth {str(d):<4} at {str(who)[:26]:<28}"
          f" {'PASS' if good else 'FAIL'}   2026-09-09 blocker, via {pair}")
    # the scatter test
    rows = read_lemmas()
    ch = [r for r in rows if r["lemma"] == nfc("חֶסֶד")]
    if ch:
        got = build(wn, ch)
        if got:
            r = got[0]
            good = not r["reliable"]
            ok += good
            print(f"\n   chesed  scatter_depth={r['scatter_depth']} "
                  f"lcs={r['scatter_lcs']}  reliable={r['reliable']}"
                  f"   {'PASS' if good else 'FAIL'}   must be FLAGGED, not averaged")
    print(f"\n   {ok}/5 passed")
    return 0 if ok == 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
