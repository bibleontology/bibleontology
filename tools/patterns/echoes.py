"""Echoes: which Old Testament verses a New Testament verse restates.

2026-09-28, reading Rom 4:3 beside Gen 15:6: a great match; and of Deut 9:5,
which the first attempt ranked above it, an interesting contrast, where the
author seems to be making a point by comparing to Gen 15:6, a find of the
hidden-gem kind. A shared-rarity link is graded, not binary:
quotation, echo, contrast. This layer records the grade and does not decide
which it is.

The method is tools/allusions.py's (2026-09-09, the Grace Formula), made to
cross the language boundary: a verse is the set of its nouns and verbs in
Greek, a Hebrew word entering as EVERY Septuagint rendering that covers at
least 10% of its uses (אמן -> πιστεύω, πίστις, πιστός, ...). One rendering
per word is right for the pattern miner, where it is a key; here it is a
net, and one rendering found 3 of 15 known quotations against 13 of 20.

A pair scores the IDF mass of the words it shares, scaled by how much of
both verses that is (see links()); a link needs SHARED words and FLOOR.
For every OT verse an NT verse echoes, its own echoes in other OT books are
listed too: Gen 15:6 -> Deut 9:5 is that kind.

    python tools/patterns/echoes.py
writes out/echoes.jsonl.gz and docs/review/echoes.html.
"""
import collections
import gzip
import html
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "builder"))
from source import norm  # noqa: E402

SHARE = 0.10          # a rendering must cover this share of a word's uses
FLOOR = 5.0           # score a link needs (the page opens at PAGE_FROM)
SHARED = 3            # and this many words in common
TOP = 5               # links kept per verse
COMMON = 3000         # words in more verses than this do not FIND candidates
IDF_MAX = 12000       # but count in scoring up to here: "out of Egypt I
                      # called my SON" (Mat 2:15 / Hos 11:1) rests on one
RESCORE = 150         # candidates per verse rescored word by word
GROUPS = {}           # verse -> {source word: its Greek set}, set by main()
BRIDGED, SEEN = collections.Counter(), collections.Counter()# well-known quotations: the source should be in the NT verse's top three
KNOWN = {"Rom.4.3": "Gen.15.6", "Gal.3.6": "Gen.15.6", "Jas.2.23": "Gen.15.6",
         "Rom.9.7": "Gen.21.12", "Heb.11.18": "Gen.21.12",
         "Mat.4.4": "Deu.8.3", "Mat.22.37": "Deu.6.5",
         "Rom.10.13": "Jol.3.5", "Mat.1.23": "Isa.7.14",
         "Mrk.12.36": "Psa.110.1", "Act.2.17": "Jol.3.1",
         "Rom.1.17": "Hab.2.4", "Mat.21.42": "Psa.118.22",
         "Heb.1.5": "Psa.2.7", "Jhn.3.14": "Num.21.9",
         "Mat.19.5": "Gen.2.24", "Rom.12.20": "Pro.25.21",
         "Heb.13.5": "Deu.31.6", "1Pe.1.24": "Isa.40.6", "Mat.2.6": "Mic.5.1"}


def rows(p):
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def septuagint():
    """Every Greek lemma the Septuagint renders a Hebrew word with at least
    SHARE of the time, from the word graph's septuagint layer, keyed two
    ways: ("H", Strong's number) — the LEXEME — and ("hebrew", consonants)
    as the fallback for a word with no number.

    BY LEXEME, NOT BY CONSONANTS. Keyed by consonants alone, homographs
    merge: נָצַר "guard" (5341) and נֵצֶר "branch" (5342) were one key, so
    Prov 4:23's "guard" carried the renderings "flower" and "dead"; ראש
    "head" carried "gall" (2026-09-28)."""
    lex, by_strong = {}, collections.defaultdict(collections.Counter)
    for d in rows(OUT / "word-lexemes.jsonl.gz"):
        if d.get("kind") != "lexeme":
            continue
        lex[d["id"]] = (d["lemma"]["value"], d["lang"]["value"],
                        str(d["strong"]["value"] or ""))
        if d["lang"]["value"] == "G" and d["strong"]["value"]:
            by_strong[str(d["strong"]["value"]).lstrip("0")][
                d["lemma"]["value"]] += d["count"]["value"]
    out = collections.defaultdict(set)
    for d in rows(OUT / "word-lexeme-layers.jsonl.gz"):
        s = ((d.get("septuagint") or {}).get("value") or {}).get("counts")
        if not s or d["id"] not in lex:
            continue
        by = collections.Counter()
        for c in s:
            by[str(c.get("greekstrong") or "").lstrip("0")] += c["count"]
        tot = sum(by.values())
        lemma, lg, strong = lex[d["id"]]
        sk = strong_key(strong)
        for gs, n in by.most_common():
            if n / tot < SHARE:
                break
            if by_strong.get(gs):
                g = norm(by_strong[gs].most_common(1)[0][0])
                out[("hebrew", norm(lemma))].add(g)
                if sk and lg in ("H", "A"):
                    out[("H", sk)].add(g)
    return out


def primary(share_min=0.4):
    """("H", extended Strong's) -> the Greek word the Septuagint uses for a
    Hebrew word MOST of the time — at least share_min of its uses — or
    nothing. A commonest rendering that covers a fraction is not an
    identity: נצר "guard" is rendered ἐκζητέω "seek out" most often (the
    Ps 119 idiom) but not mostly, and "guard" met "seek" as the same verb
    (Prov 4:23 -> 1 Chr 28:9, 2026-09-28)."""
    lex, by_strong = {}, collections.defaultdict(collections.Counter)
    for d in rows(OUT / "word-lexemes.jsonl.gz"):
        if d.get("kind") != "lexeme":
            continue
        lex[d["id"]] = (d["lang"]["value"], str(d["strong"]["value"] or ""))
        if d["lang"]["value"] == "G" and d["strong"]["value"]:
            by_strong[str(d["strong"]["value"]).lstrip("0")][
                d["lemma"]["value"]] += d["count"]["value"]
    out = {}
    for d in rows(OUT / "word-lexeme-layers.jsonl.gz"):
        s = ((d.get("septuagint") or {}).get("value") or {}).get("counts")
        if not s or d["id"] not in lex:
            continue
        lg, strong = lex[d["id"]]
        if lg not in ("H", "A"):
            continue
        by = collections.Counter()
        for c in s:
            by[str(c.get("greekstrong") or "").lstrip("0")] += c["count"]
        gs, n = by.most_common(1)[0]
        if n / sum(by.values()) >= share_min and by_strong.get(gs):
            out[("H", strong_key(strong))] = norm(
                by_strong[gs].most_common(1)[0][0])
    return out


def strong_key(s):
    """An extended Strong's number as an identity: leading zeros dropped,
    the letter KEPT — 3820 is לֵב "heart", 3820b is בּוֹא "entrance", and
    stripping the letter gave "heart" the renderings "come" and "go in"."""
    s = (s or "").strip().lower()
    m = re.match(r"^[hg]?0*(\d+)([a-z]?)", s)
    return (m.group(1) + m.group(2)) if m else ""


def renders(bridge, lang, lemma, strong):
    """A word's Greek: itself if Greek; else by lexeme (extended Strong's),
    falling back to consonants only when the word has no number."""
    if lang == "greek":
        return {lemma}
    sk = strong_key(strong)
    if sk:
        g = bridge.get(("H", sk))
        if g is not None:
            return set(g)
    return set(bridge.get((lang, lemma), set()))


TBESG = ROOT / "data" / "raw" / "stepbible" / (
    "TBESG - Translators Brief lexicon of Extended Strongs for Greek - "
    "STEPBible.org CC BY.txt")


def greek_of_hebrew():
    """Hebrew Strong's number -> the Greek lemmas STEPBible's Greek lexicon
    names as "the Greek of" it: the NT's own spelling of an OT name
    (G3198 = the Greek of H4442, Melchizedek). The Septuagint layer carries
    no names, so without this Heb 7:17 could not meet Ps 110:4 (2026-09-28,
    the BSB footnote benchmark). STEPBible, CC BY."""
    out = collections.defaultdict(set)
    if not TBESG.exists():
        return out
    for line in TBESG.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^G\d+\w*\t\S+ = the Greek of\t(H\d+)\w*\t(\S+)", line)
        if m:
            out[str(int(m.group(1)[1:]))].add(norm(m.group(2)))
    return out


def testament_of():
    # the miner's canonical families (the node file is not in canon order)
    sys.path.insert(0, str(HERE))
    from mine import FAM, NTFAM
    return lambda v: "NT" if FAM.get(v.split(".")[0], 0) >= NTFAM else "OT"


def bags(bridge):
    """verse -> {source word: its Greek set}; a Hebrew word is one word
    however many renderings it brings.

    Read from MACULA itself, not from the structure's word nodes: the
    structure drops 845 Hebrew nouns (0.6%) — and at Isa 8:14 they are the
    stone, the stumbling and the rock, so Rom 9:33 and 1 Pet 2:8 could not
    meet the verse they quote (2026-09-28)."""
    import source as S
    names = greek_of_hebrew()
    groups, gloss = collections.defaultdict(dict), collections.defaultdict(
        collections.Counter)
    for lang in ("hebrew", "greek"):
        for p in S.files(lang):
            _root, ws = S.load(p, lang)
            for w in ws.values():
                # adjectives too: "your ENEMIES", "at my RIGHT hand" (Mat
                # 22:44 / Ps 110:1) are adjectives used as nouns
                if not w.get("lemma") or \
                        w.get("class") not in ("noun", "verb", "adj"):
                    continue
                lem = norm(w["lemma"])
                st = w.get("strongnumberx") or w.get("strong") or ""
                gs = renders(bridge, lang, lem, st)
                if lang != "greek":
                    d_ = "".join(ch for ch in st if ch.isdigit())
                    if d_:
                        gs |= names.get(str(int(d_)), set())
                BRIDGED[lang] += 1 if gs else 0
                SEEN[lang] += 1
                if gs:
                    groups[w["ref"]][(lang, lem)] = gs
                if lang == "greek":
                    gloss[lem][(w.get("english") or "").split(" ")[-1]] += 1
    return groups, {g: c.most_common(1)[0][0] for g, c in gloss.items()}


PAIR_DF = {}          # (word, word) -> verses holding both
VERSES_OF = {}        # word -> verses holding it, set by main()
PAIR_MAX = 2000       # pairs are looked up among words in at most this many


def collocation(shared, idf):
    """What a RARE PAIR adds beyond its rarer word. 2026-09-28: when the
    reference includes something really unique like a stumbling stone, it
    automatically needs to rise in ranking. Summing words one by one
    cannot see it: stone is common and stumbling fairly rare, but the two in
    one verse almost never. The best pair among the shared words scores the
    rarity of the pair (verses holding both) minus that of its rarer word;
    added once."""
    rare = sorted(x for x in shared if len(VERSES_OF.get(x, ())) <= PAIR_MAX)
    best = 0.0
    n = len(GROUPS) or 1
    for i, a in enumerate(rare):
        for b in rare[i + 1:]:
            k = (a, b)
            df = PAIR_DF.get(k)
            if df is None:
                df = PAIR_DF[k] = len(VERSES_OF[a] & VERSES_OF[b])
            best = max(best, math.log(n / max(df, 1)) - max(idf[a], idf[b]))
    return best


SCORE_MODE = "dice"


def _score(s, m_src, m_u):
    if SCORE_MODE == "overlap":      # shared over the SMALLER verse
        return s * s / max(min(m_src, m_u), 1e-9)
    if SCORE_MODE == "target":       # shared over the earlier verse
        return s * s / max(m_u, 1e-9)
    return s * 2 * s / (m_src + m_u)


def links(src, pool, bag, idf, post, mass, other_book=False):
    """The verses in `pool` src shares rare words with, best first.

    SCORE = shared x Dice. Shared IDF mass alone ranks a long verse that
    happens to hold three middling words ("hear", "day", "God") beside a
    quotation; dividing by both verses' own mass (each Hebrew word counted
    once, at its rarest rendering) removes that. Graded by hand, 8 per band
    (2026-09-28, after the bridge fixes: names, adjectives, common words):
    NT verses ranked 1-200 by their best link (score 14.5+) 5 of 8 real,
    200-400 (12.4+) 4, 400-800 (10.7+) 2-3, 800-1600 0-1, 1600-3200 2 —
    real quotations among the chance matches down there (Rev 5:10 ->
    Exod 19:6), which verse-level scoring cannot lift. Known quotations
    with the source in the top three 15 of 20; the BSB footnote benchmark
    (xref_bench.py) 59% of quotations found."""
    acc = collections.Counter()
    for g in bag[src]:
        if g not in idf or len(VERSES_OF.get(g, ())) > COMMON:
            continue
        for u in post[g]:
            acc[u] += idf[g]
    out = []
    # EACH WORD COUNTS ONCE. A Hebrew word enters as all its Septuagint
    # renderings, so when BOTH verses are Hebrew one shared word matched
    # five or ten times over: Ps 118:22 scored 53 against Isa 41:26 on
    # ראש ("head") alone, its renderings gall, hair, anger, ruler, face
    # (2026-09-28, from a pasted example). The raw sum only picks candidates; a
    # candidate is scored on the source verse's WORDS, each at its rarest
    # rendering the other verse shares.
    for u, _raw in acc.most_common(RESCORE):
        if u == src or u not in pool or (
                other_book and u.split(".")[0] == src.split(".")[0]):
            continue
        s, n, sh = 0.0, 0, []
        for gs in GROUPS[src].values():
            hit = [x for x in gs if x in idf and x in bag[u]]
            if hit:
                best = max(hit, key=lambda x: idf[x])
                s += idf[best]
                n += 1
                sh.append(best)
        if n < SHARED:
            continue
        s += collocation(sh, idf)
        score = _score(s, mass[src], mass[u])
        if score >= FLOOR:
            out.append((u, round(score, 2), round(s, 1),
                        sorted(set(sh), key=lambda g: -idf.get(g, 0))))
    out.sort(key=lambda x: -x[1])
    return out[:TOP]


RUN_STEPS = [(a, b) for a in (1, 2, 3) for b in (1, 2, 3)]
RUN_MIN = 2           # neighbouring pairs a retelling needs (a run of three)


def _step(v, d):
    b, c, n = v.rsplit(".", 2)
    return f"{b}.{c}.{int(n) + d}"


def parallels(bag, idf, mass):
    """Pairs of verses in different books that are parts of one RETELLING.

    A quotation is a point, a retelling is a run: v and u are parallel when
    v echoes u and a verse after v echoes a verse after u (each up to 3 on —
    a retelling adds and drops verses; 1-2 on missed Mat 14:8 / Mrk 6:25).
    Word overlap alone is NOT a retelling: it is also what a repeated
    phrase is made of (Ps 50:13 / Ezek 39:18), so order is the test.
    Chronicles retelling Samuel-Kings, one gospel retelling another, Heb 3
    reciting Ps 95: two records of one text or event, not two occurrences
    (2026-09-28: they filled the pattern miner's lists as repeats)."""
    post = collections.defaultdict(list)
    for v, gs in bag.items():
        for g in gs:
            post[g].append(v)
    pool = set(bag)
    link = {}
    for v in sorted(bag):
        for u, sc, _s, _sh in links(v, pool, bag, idf, post, mass,
                                    other_book=True):
            link[(v, u)] = sc
    # A RUN OF THREE: v <-> u needs TWO neighbouring pairs that also line
    # up. With one, John 3:16-17 and 1 John 5:11-12 (gave, life, Son) were
    # "parallel accounts" — an echo within one writer, not a retelling
    # (2026-09-28, reading John 3:16's connections).
    par = {}
    for (v, u), sc in link.items():
        confirm = [(_step(v, dv), _step(u, du)) for dv, du in RUN_STEPS
                   if (_step(v, dv), _step(u, du)) in link] + \
                  [(_step(v, -dv), _step(u, -du)) for dv, du in RUN_STEPS
                   if (_step(v, -dv), _step(u, -du)) in link]
        if len(confirm) >= RUN_MIN:
            for a, b in [(v, u)] + confirm:
                key = (a, b) if a < b else (b, a)
                par[key] = max(par.get(key, 0), link.get((a, b), 0))
    return par


OT_COMMON = 1500      # Hebrew lexemes in more OT verses than this find nothing
SAME_SAYING = 24.0    # an OT pair this strong is one saying told twice


def canon_key(ref):
    """Canon position of a verse: book, chapter, verse."""
    sys.path.insert(0, str(HERE))
    from mine import BOOK_ORDER
    b, c, v = ref.split(".")
    return (BOOK_ORDER.get(b, 99), int(c), int(v))
OT_TOP = 6            # OT echoes kept per OT verse


def ot_echoes():
    """OT verse <-> OT verse, on HEBREW LEXEMES directly — same language, no
    bridge, each lexeme once. 2026-09-28: Ps 103:8 ("The LORD is
    compassionate and gracious, slow to anger, abounding in loving
    devotion") was found with no connections, and it should have strong
    ones. It is the Grace Formula (Exod 34:6, Neh 9:17,
    Ps 86:15, 145:8, Joel 2:13, Jonah 4:2), which tools/allusions.py found
    from Hebrew lemmas on 2026-09-09 — but echoes were computed only NT->OT,
    and the verse has no verb for the structural alignment to hold. Same
    scoring as links(): shared rarity x Dice, plus the rarest shared pair.
    Excluded: the verse's own chapter (local repetition, not allusion)."""
    import source as S
    bag = collections.defaultdict(set)
    for p in S.files("hebrew"):
        _root, ws = S.load(p, "hebrew")
        for w in ws.values():
            if not w.get("lemma") or w.get("class") not in ("noun", "verb", "adj"):
                continue
            sk = strong_key(w.get("strongnumberx") or w.get("strong") or "")
            bag[w["ref"]].add(sk or norm(w["lemma"]))
    verses_of = collections.defaultdict(set)
    for v, ks in bag.items():
        for k in ks:
            verses_of[k].add(v)
    n = len(bag)
    idf = {k: math.log(n / len(vs)) for k, vs in verses_of.items()}
    mass = {v: sum(idf[k] for k in ks) for v, ks in bag.items()}
    pair_df = {}

    def colloc(shared):
        rare = sorted(k for k in shared if len(verses_of[k]) <= PAIR_MAX)
        best = 0.0
        for i, a in enumerate(rare):
            for b in rare[i + 1:]:
                df = pair_df.get((a, b))
                if df is None:
                    df = pair_df[(a, b)] = len(verses_of[a] & verses_of[b])
                best = max(best, math.log(n / max(df, 1)) - max(idf[a], idf[b]))
        return best
    out = []
    for v, ks in bag.items():
        chap = v.rsplit(".", 1)[0]
        acc = collections.Counter()
        for k in ks:
            if len(verses_of[k]) > OT_COMMON:
                continue
            for u in verses_of[k]:
                acc[u] += idf[k]
        cand = []
        for u, _raw in acc.most_common(RESCORE):
            if u == v or u.rsplit(".", 1)[0] == chap:
                continue
            sh = ks & bag[u]
            if len(sh) < SHARED:
                continue
            s = sum(idf[k] for k in sh) + colloc(sh)
            score = s * 2 * s / (mass[v] + mass[u])
            if score >= FLOOR:
                cand.append((round(score, 2), u, sh))
        cand.sort(reverse=True)
        for rank, (sc, u, sh) in enumerate(cand[:OT_TOP], 1):
            out.append((v, u, sc, rank, sh))
    return out


def main():
    bridge = septuagint()
    tst = testament_of()
    groups, gloss = bags(bridge)
    GROUPS.clear()
    GROUPS.update(groups)
    bag = {v: set().union(*g.values()) for v, g in groups.items()}
    VERSES_OF.clear()
    PAIR_DF.clear()
    for v, gs in bag.items():
        for g in gs:
            VERSES_OF.setdefault(g, set()).add(v)
    df = collections.Counter(g for v in bag.values() for g in v)
    idf = {g: math.log(len(bag) / k) for g, k in df.items() if k <= IDF_MAX}
    mass = {v: sum(max(idf.get(x, 0) for x in gs) for gs in g.values())
            for v, g in groups.items()}
    ot = {v for v in bag if tst(v) == "OT"}
    nt = set(bag) - ot
    post = collections.defaultdict(list)
    for v in ot:
        for g in bag[v]:
            post[g].append(v)
    recs, echoed = [], set()
    for v in sorted(nt):
        for rank, (u, sc, s, sh) in enumerate(
                links(v, ot, bag, idf, post, mass), 1):
            recs.append({"from": v, "to": u, "kind": "NT->OT", "rank": rank,
                         "score": sc, "shared_mass": s, "shared": sh,
                         "shared_en": [gloss.get(g, g) for g in sh]})
            echoed.add(u)
    # OT <-> OT for EVERY OT verse, on Hebrew lexemes (ot_echoes): graded
    # by hand 7-8 of 8 real down to score 12.7 (2026-09-28)
    hgloss = {}
    for n in rows(OUT / "structure-nodes.jsonl.gz"):
        if n.get("word") and n.get("lang") == "hebrew" and n.get("strong"):
            hgloss.setdefault(strong_key(n["strong"]),
                              (n.get("text") or "").split(" ")[-1])
    for v, u, sc, rank, sh in ot_echoes():
        r = {"from": v, "to": u, "kind": "OT->OT", "rank": rank,
             "score": sc, "shared": sorted(sh),
             "shared_en": [hgloss.get(k, k) for k in sorted(sh)]}
        # THE SAME SAYING, AND WHERE IT WAS FIRST TOLD. 2026-09-28: the link
        # between Psalm 103:8 and Exo 34:6 should register as too strong to
        # be coincidence, and Exo 34:6 should be identifiable as the
        # originating instance, so that is the direction of the pointer;
        # registering that helps later. At SAME_SAYING the pair is one saying told twice; its
        # source is the telling earlier in CANON ORDER — a reading, stated
        # as such (by: "canon order"), not a claim about composition.
        if sc >= SAME_SAYING:
            r["same_saying"] = True
        recs.append(r)
    # ONE SOURCE PER FAMILY: pair by pair, "earlier in canon" named Ps 86:15
    # the source of Ps 103:8 and Exod 34:6 the source of the same verse. The
    # verses one saying joins are a family; its first telling is the
    # family's earliest in canon order, for every member.
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x
    for r in recs:
        if r.get("same_saying"):
            a, b = find(r["from"]), find(r["to"])
            if a != b:
                parent[max(a, b, key=canon_key)] = min(a, b, key=canon_key)
    for r in recs:
        if r.get("same_saying"):
            r["source"] = find(r["from"])
            r["source_by"] = "canon order: the family's earliest telling"
    par = parallels(bag, idf, mass)
    for (a, b), sc in sorted(par.items()):
        recs.append({"from": a, "to": b, "kind": "parallel", "score": sc})
    pairs = collections.Counter(
        tuple(sorted((a.split(".")[0], b.split(".")[0]))) for a, b in par)
    print(f"parallel verse pairs {len(par):,}; book pairs most parallel: " +
          ", ".join(f"{x}/{y} {n}" for (x, y), n in pairs.most_common(25)))
    with gzip.open(OUT / "echoes.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # the answer key, against every NT verse's top three (above the floor
    # or not: recall of the method, not of the threshold)
    hit = []
    for k, want in KNOWN.items():
        top = [x[0] for x in links_any(k, ot, bag, idf, post, mass)]
        hit.append(want in top[:3])
    n_nt = len({r["from"] for r in recs if r["kind"] == "NT->OT"})
    print(f"{len(recs):,} links: NT verses with an echo {n_nt:,} of "
          f"{len(nt):,}; OT verses echoed {len(echoed):,}; known quotations "
          f"with the source in the top three {sum(hit)}/{len(KNOWN)}")
    print("words reaching Greek: " + ", ".join(
        f"{lg} {BRIDGED[lg]:,}/{SEEN[lg]:,} ({100 * BRIDGED[lg] / SEEN[lg]:.1f}%)"
        for lg in SEEN))
    page(recs, gloss)


def links_any(src, pool, bag, idf, post, mass):
    global FLOOR, SHARED
    f, s = FLOOR, SHARED
    FLOOR, SHARED = 0.0, 2
    try:
        return links(src, pool, bag, idf, post, mass)
    finally:
        FLOOR, SHARED = f, s


def page(recs, gloss):
    moved = {}
    try:
        moved = json.loads((OUT / "versemap.json").read_text(
            encoding="utf-8")).get("moved") or {}
    except (OSError, ValueError):
        pass
    text = {}
    for line in open(ROOT / "data" / "bible" / "verses.bsb.jsonl",
                     encoding="utf-8"):
        d = json.loads(line)
        if "b" in d:
            text[f"{d['b']}.{d['c']}.{d['v']}"] = d["t"]

    sys.path.insert(0, str(ROOT / "tools"))
    from acts import BOOK      # MACULA book codes -> the BSB file's

    def ref(v):
        b, c, n = moved.get(v, v).split(".")
        return f"{b} {c}:{n}", text.get(f"{BOOK.get(b, b)}.{c}.{n}", "")
    ot_of = collections.defaultdict(list)
    for r in recs:
        if r["kind"] == "OT->OT":
            ot_of[r["from"]].append(r)
    by = collections.defaultdict(list)
    for r in recs:
        if r["kind"] == "NT->OT":
            by[r["from"]].append(r)
    items = []
    for v, rs in sorted(by.items(), key=lambda x: -x[1][0]["score"]):
        nr, nt_text = ref(v)
        links_ = []
        for r in rs:
            orf, ot_text = ref(r["to"])
            links_.append({"ref": orf, "text": ot_text, "score": r["score"],
                           "shared": [gloss.get(g, g) for g in r["shared"]],
                           "also": [dict(zip(("ref", "text"), ref(x["to"])),
                                         score=x["score"],
                                         shared=[gloss.get(g, g)
                                                 for g in x["shared"]])
                                    for x in ot_of.get(r["to"], [])[:3]]})
        items.append({"ref": nr, "text": nt_text, "best": rs[0]["score"],
                      "links": links_})
    tpl = (HERE / "echoes-viewer.html").read_text(encoding="utf-8")
    (ROOT / "docs" / "review" / "echoes.html").write_text(
        tpl.replace("/*DATA*/[]", json.dumps(items, ensure_ascii=False)
                    .replace("</", "<\\/")), encoding="utf-8")
    print(f"page: {len(items):,} NT verses -> docs/review/echoes.html")


if __name__ == "__main__":
    main()
