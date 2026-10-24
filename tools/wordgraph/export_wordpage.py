"""Data for the graphical word page (tools/wordgraph/wordpage.html).

2026-09-27: the first viewer was adequate but not the insightful graphical
view that was hoped for. This export gives each lexeme
what the page draws:
  - its NEAREST NEIGHBOURS by three kinds of evidence, each tested
    (similarity.py, roles.py; AUC on 24 known near-synonym pairs):
      context   the Hebrew words it shares clauses with (Hebrew only) 0.99
      lxx       the Greek the Septuagint translators chose           0.99
      roles     what the text says about it: does / is / undergoes  0.86
    (the BSB layer, 0.76, is shown as renderings, not used for neighbours)
  - its PORTRAIT from the structure graph: what it does, what it is, what is
    done to it, what it is said of (pronouns counted for their referents)
  - its Septuagint renderings, BSB renderings, speech-type distribution,
    and where it occurs, book by book in canonical order

    python tools/wordgraph/export_wordpage.py
"""
import collections
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import crosslang as XL                                     # noqa: E402
import greek as GK                                         # noqa: E402
import roles as R                                          # noqa: E402
import similarity as SIM                                   # noqa: E402

MIN_COUNT = 5          # lexemes on the page: at least this many occurrences
TOP_FEATURES = 60      # each vector pruned to its strongest features
MAX_DF = 800           # a feature shared by more lexemes than this is noise
K = 10                 # neighbours per evidence
OUT_JSON = HERE / "wordpage-data.json"


def unit(v):
    top = dict(sorted(v.items(), key=lambda kv: -kv[1])[:TOP_FEATURES])
    n = math.sqrt(sum(x * x for x in top.values()))
    return {k: x / n for k, x in top.items()} if n else {}


def knn(vecs, keep, min_shared=1):
    """Top-K cosine neighbours for every kept lexeme, by inverted index.
    `min_shared`: a neighbour must share at least this many features. For
    roles and context it is 2: steadfast love's structural "neighbours"
    (cake, shovels, curtain) all scored 0.293 because each shared ONE verb
    with it, which says nothing."""
    U = {l: unit(v) for l, v in vecs.items() if l in keep and v}
    post = collections.defaultdict(list)
    for l, v in U.items():
        for f, x in v.items():
            post[f].append((l, x))
    out = {}
    for l, v in U.items():
        acc, shared = collections.Counter(), collections.Counter()
        for f, x in v.items():
            p = post[f]
            if len(p) > MAX_DF:
                continue
            for m, y in p:
                if m != l:
                    acc[m] += x * y
                    shared[m] += 1
        out[l] = [(m, round(s, 3)) for m, s in acc.most_common()
                  if s > 0.02 and shared[m] >= min_shared][:K]
    return out


def space(vecs, ids, dims=64):
    """Each lexeme's COORDINATES in one evidence's space: the sparse vector
    (one axis per feature) compressed to its `dims` strongest directions
    (eigenvectors of the similarity matrix). Rows are unit length; a lexeme
    with no evidence of this kind is all zeros."""
    import numpy as np
    feats = {}
    rows_ = [unit(vecs.get(l) or {}) for l in ids]
    for r in rows_:
        for f in r:
            feats.setdefault(f, len(feats))
    X = np.zeros((len(ids), len(feats)), dtype=np.float32)
    for i, r in enumerate(rows_):
        for f, x in r.items():
            X[i, feats[f]] = x
    G = X @ X.T                                   # cosine similarities
    w, U = np.linalg.eigh(G.astype(np.float64))
    top = np.argsort(w)[::-1][:dims]
    Y = U[:, top] * np.sqrt(np.clip(w[top], 0, None))
    n = np.linalg.norm(Y, axis=1, keepdims=True)
    return np.where(n > 0, Y / np.maximum(n, 1e-9), 0).astype(np.float32)


def layout(Y, k=8, iters=300, seed=7):
    """A 2D MAP of the joined space: each word pulled toward its k nearest
    neighbours in the full space and pushed away from all others (a
    Fruchterman-Reingold layout), starting from the two main directions."""
    import numpy as np
    n = len(Y)
    S = Y @ Y.T
    np.fill_diagonal(S, -1)
    nb = np.argsort(-S, axis=1)[:, :k]
    rng = np.random.default_rng(seed)
    c = Y - Y.mean(0)
    _, _, Vt = np.linalg.svd(c, full_matrices=False)
    P = c @ Vt[:2].T
    P = P / (np.abs(P).max() + 1e-9) + rng.normal(0, .01, P.shape)
    ideal = 1.0 / np.sqrt(n)
    src = np.repeat(np.arange(n), k)
    dst = nb.ravel()
    t = 0.1
    for _ in range(iters):
        D = P[:, None, :] - P[None, :, :]
        d2 = (D ** 2).sum(-1) + 1e-6
        rep = (D / d2[..., None]).sum(1) * ideal ** 2
        E = P[src] - P[dst]
        el = np.sqrt((E ** 2).sum(1)) + 1e-9
        f = (E * (el / ideal)[:, None])
        att = np.zeros_like(P)
        np.add.at(att, src, -f)
        np.add.at(att, dst, f)
        mv = rep + att
        ml = np.sqrt((mv ** 2).sum(1)) + 1e-9
        P += mv / ml[:, None] * np.minimum(ml, t)[:, None]
        t *= 0.985
    P -= P.min(0)
    return P / P.max(0)


def across(lex, keep, n=6):
    """ACROSS THE LANGUAGES (2026-09-27: see how close the
    Greek/Hebrew/Aramaic words are together). Tested in
    crosslang.py on standard correspondences:
      Hebrew/Aramaic -> Greek  the share of the word's Septuagint renderings
                               that ARE that Greek word (36/39 first)
      Greek -> Hebrew/Aramaic  of all the times the translators wrote that
                               Greek word, the share standing for this word
      Aramaic <-> Hebrew       the same root, by the regular sound
                               correspondences (with the other bridges,
                               8/9 first)
    A Septuagint link needs at least two renderings behind it: a word seen
    once scored 1.0 by accident (λόγος -> "bed")."""
    X = XL.Index()
    behind = collections.defaultdict(collections.Counter)
    for h, v in X.sept.items():
        for s, c in v.items():
            behind[s][h] += c
    roots = collections.defaultdict(list)
    for l, L in lex.items():
        if l in keep and L.get("lang") in ("A", "H"):
            roots[(L["lang"], XL.root(L["lemma"], L["lang"] == "A"))].append(l)
    out = {}
    for l in keep:
        L, cand = lex[l], collections.Counter()
        if L.get("lang") in ("H", "A"):
            v = X.sept.get(l) or {}
            tot = sum(v.values())
            for s, c in v.items():
                if c >= 2:
                    for g in X.greek_by_strong.get(s, []):
                        if g in keep:
                            cand[g] = max(cand[g], c / tot)
            other = "H" if L["lang"] == "A" else "A"
            for m in roots.get((other, XL.root(L["lemma"], L["lang"] == "A")),
                               []):
                cand[m] = max(cand[m], 0.5)       # the same root
        elif L.get("lang") == "G":
            s = XL.num(L.get("strong"))
            tot = sum(behind[s].values())
            for h, c in behind[s].items():
                if c >= 2 and h in keep:
                    cand[h] = c / tot
        out[l] = [(m, round(s, 3)) for m, s in cand.most_common(n)
                  if s >= 0.05]
    return out


def main():
    lex, layers, pairs = R.build_pairs()
    occ_lex = SIM.load()[2]
    V = SIM.vectors(lex, layers, occ_lex)
    # GREEK, until its structure is built: clause context from MACULA's
    # Greek trees (AUC 0.92), and "renders the same Hebrew" (0.98). Their
    # features are Greek lexemes and Hebrew lexemes respectively, never
    # the Hebrew vectors' features, so one ranking cannot mix them.
    V["context"].update(GK.context_vectors(occ_lex, lex))
    V["lxx"].update(GK.behind_vectors(XL.Index()))
    prof = R.ppmi_profiles(pairs)
    keep = {l for l, d in lex.items() if d.get("count", 0) >= MIN_COUNT}
    near = {"context": knn(V["context"], keep, 2),
            "lxx": knn(V["lxx"], keep, 1),
            "roles": knn(prof, keep, 2)}
    # book order: the order the word graph reads them (Hebrew Bible, then
    # the New Testament), which is canonical within each
    books = []
    per_book = collections.defaultdict(collections.Counter)
    for d in SIM.rows(SIM.OUT / "word-occurrences.jsonl.gz"):
        b = d["ref"].split(".")[0]
        if not books or books[-1] != b:
            if b not in books:
                books.append(b)
        l = occ_lex.get(d["id"])
        if l in keep:
            per_book[l][b] += 1
    near["cross"] = across(lex, keep)

    def g(l):
        return ((layers.get(l) or {}).get("glosses") or {}).get("usual") or ""

    # THE SPACE: 64 dimensions from each evidence, joined (192 in all), and
    # a 2D map of it. Only content words are mapped: a preposition or a
    # suffix is near everything and would sit in the middle of every map.
    import numpy as np
    word_class = collections.defaultdict(collections.Counter)
    for d in SIM.rows(SIM.OUT / "word-occurrences.jsonl.gz"):
        l = occ_lex.get(d["id"])
        if l in keep:
            word_class[l][d.get("class")] += 1
    cls = {l: c.most_common(1)[0][0] for l, c in word_class.items()}
    # the joined space is Old Testament only for now: Greek has no clause
    # context or roles until its structure is built (plan Step 3)
    mapped = sorted((l for l in keep if cls.get(l) in SIM.CONTENT
                     and lex[l].get("lang") in ("H", "A")),
                    key=lambda x: -lex[x]["count"])
    blocks = [space(V["context"], mapped), space(V["lxx"], mapped),
              0.7 * space(prof, mapped)]
    Y = np.hstack(blocks)
    Y = Y / np.maximum(np.linalg.norm(Y, axis=1, keepdims=True), 1e-9)
    # No 2D map: 2026-09-27, a 2D map would be tricky and requires focusing
    # on one word at a time to see its neighbors. The
    # joined space gives a FOURTH ranking, all the evidence together.
    S = Y @ Y.T
    np.fill_diagonal(S, -1)
    top = np.argsort(-S, axis=1)[:, :K]
    near["all"] = {l: [(mapped[j], round(float(S[i, j]), 3))
                       for j in top[i] if S[i, j] > 0.05]
                   for i, l in enumerate(mapped)}
    xy = {}
    print(f"space: {len(mapped):,} content words x {Y.shape[1]} dimensions")
    # the same test as the other evidence: 24 near-synonym pairs
    idx = {l: i for i, l in enumerate(mapped)}
    Lm = SIM.by_lemma(lex)
    ps = [(idx.get(Lm.get(a)), idx.get(Lm.get(b))) for a, b in SIM.PAIRS]
    ps = [(i, j) for i, j in ps if i is not None and j is not None]
    rng = np.random.default_rng(7)
    rp = rng.integers(0, len(mapped), size=(400, 2))
    syn = [S[i, j] for i, j in ps]
    rnd = [S[i, j] for i, j in rp if i != j]
    auc = np.mean([[s > r for r in rnd] for s in syn])
    hit = sum(j in top[i] or i in top[j] for i, j in ps)
    print(f"all evidence together: {len(ps)} pairs, AUC {auc:.2f}, "
          f"partner in top-10 {hit}/{len(ps)}")

    out = []
    for l in sorted(keep, key=lambda x: -lex[x]["count"]):
        L, Y = lex[l], layers.get(l) or {}
        portrait = {}
        for rel in ("does", "is", "undergoes", "is_said_of"):
            items = sorted(((w, p) for (r, p), w in prof.get(l, {}).items()
                            if r == rel), reverse=True)[:8]
            if items:
                portrait[rel] = [[p, pairs[(l, rel, p)]] for _, p in items]
        sept = [[c["greek"], c["greekstrong"], c["count"]] for c in
                ((Y.get("septuagint") or {}).get("counts") or [])[:8]]
        bsb = [[c["english"], c["count"]] for c in
               ((Y.get("bsb_renderings") or {}).get("counts") or [])[:8]]
        force = {c["force"]: c["count"] for c in
                 ((Y.get("speech_types") or {}).get("raw_counts") or [])}
        out.append({
            "id": l, "lemma": L["lemma"], "gloss": g(l), "count": L["count"],
            "lang": L["lang"], "strong": L.get("strong"),
            "near": {k: v.get(l, []) for k, v in near.items()},
            "portrait": portrait, "sept": sept, "bsb": bsb, "force": force,
            "books": [per_book[l].get(b, 0) for b in books],
            "cls": cls.get(l), "xy": xy.get(l),
        })
    labels = {l: [lex[l]["lemma"], g(l), lex[l]["count"]] for l in lex}
    data = {"books": books, "words": out,
            # every lexeme a neighbour or portrait may name
            "labels": {l: labels[l] for l in {
                m for w in out for v in w["near"].values() for m, _ in v} |
                {p for w in out for v in w["portrait"].values() for p, _ in v}
                | {w["id"] for w in out}}}
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT_JSON.write_text(body, encoding="utf-8")        # the standalone page
    # the reader (app2) loads the committed, gzipped copy: a deploy is a
    # `git push`, and the server cannot rebuild this (MACULA is not on it)
    import gzip
    with gzip.open(SIM.OUT / "wordpage-data.json.gz", "wt",
                   encoding="utf-8", compresslevel=9) as f:
        f.write(body)
    print(f"{len(out):,} lexemes, {OUT_JSON.stat().st_size / 1e6:.1f} MB "
          f"-> {OUT_JSON.relative_to(SIM.ROOT)}")


if __name__ == "__main__":
    main()
