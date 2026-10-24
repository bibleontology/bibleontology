"""A deterministic 3-coordinate theme space, plus shape and discourse role.

2026-09-09, the request:

> A table driven by a deterministic algorithm with every verse assigned a
> 'theme' value which can have a strength degree as well, while some verses
> are kind of neutral. Ideally (for now) a theme would consist of 3
> coordinates so that it could be plotted on a 3d space, to allow for concepts
> to be relative distances from each other; a similar pattern shape value for
> each verse or sentence; and the role that each verse plays in the outer
> context.

Three columns, three sources, and **no model anywhere**:

    THEME   3 coordinates from an eigendecomposition of the corpus's own
            word co-occurrence. Deterministic: the same input yields the same
            axes every run, with sign fixed by a stated convention.
    SHAPE   the colon structure from the Masoretic accents (tools/cola.py),
            written as the syntactic skeleton of each half-verse.
    ROLE    the discourse relation and direction from tools/sentfunc.py --
            PDTB's classes over translator consensus on the connective. This
            is the "gives the reason or whatever" role that was asked for:
            contingency/cause is a verse that grounds its neighbour.

## Why an eigendecomposition rather than an embedding model

Because the project's rule is that a number must be reproducible and
explainable. An embedding from a trained model is neither: it cannot be
recomputed from this repository, and no one can say what its axes mean.

Here the axes are **derived from the corpus and then labelled by their own top
loadings**, so the printout says what each dimension turned out to be about.
The procedure is:

1. Each verse becomes a bag of MACULA's own English glosses. Glosses, not
   lemmas, because Hebrew and Greek do not share a vocabulary and connections
   were asked for *elsewhere in the ontology* -- which has to cross testaments.
2. Features are IDF-weighted. Raw counts put every verse near the words that
   appear everywhere; the same fix the sense profiles needed.
3. The feature co-occurrence matrix is eigendecomposed, and the top three
   eigenvectors become the axes.
4. Verses are projected onto them. **Sign convention:** each axis is oriented so
   that its single largest loading is positive, which removes the arbitrary
   sign an eigenvector carries.

## Strength, and what "neutral" means

Strength is the length of a verse's own vector, reported as a percentile of the
corpus. **A neutral verse is one built from words that carry no thematic
weight** -- it sits near the origin, not because it means nothing but because
its vocabulary is shared with everything. That is a real and useful reading:
"and it came to pass" is thematically neutral in a way "steadfast love" is not.

## The honest limit

Three dimensions of a corpus this size explain only a small share of its
variance, and the printout reports how much. The coordinates are good for
*relative distance* -- which is what was asked for -- and are not a claim that
a psalm's meaning is three numbers.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import pathlib
import re
import sys

# RESOLVED 2026-09-11: `tools/typing.py` is now `tools/typerestrict.py`.
#
# It shadowed the standard library's `typing`, because Python puts a script's
# own directory FIRST on sys.path. numpy's `linalg` imports typing, so any
# tool here needing numpy died with "cannot import name 'Any' from 'typing'"
# -- an error naming the wrong cause entirely.
#
# The local workaround below was written when the cost looked like numpy
# alone. It was not: on 2026-09-11 the same shadowing broke `google-genai`
# (via pydantic) and wasted an evening's benchmark run, because
# `python tools/triage.py` fails where `python -c "import google.genai"`
# from the repo root succeeds. A shadowing module poisons EVERY import in its
# directory, not the one that first reveals it.
#
# The guard is kept: it costs nothing and protects against the next file in
# here that happens to share a stdlib name.
_here = str(pathlib.Path(__file__).resolve().parent)
sys.path[:] = [p for p in sys.path if p not in ("", ".", _here)]

import numpy as np                                            # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
MAC = ROOT / "data" / "raw" / "macula"
DEST = OUT / "themespace.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

W = re.compile(r"<w\s([^>]*?)/?>", re.S)
A = re.compile(r'([\w:.-]+)="([^"]*)"', re.S)
REF = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)")

STOP = set("""a an the and or but of to in on at by for with from is are was
were be been being he she it they them his her its their him i me my we us our
you your thou thy thee not no all that this these those which who whom what
when where how then there here as so if than up out down over under into upon
one two do did does done have has had will shall would should may might can
could shall let unto also very much many any some such other same each every
both more most now yet even only just about after before against among between
through during while because since until unless though although whether either
neither nor own too able""".split())

BOOK = {
    "GEN": "Gen", "EXO": "Exo", "LEV": "Lev", "NUM": "Num", "DEU": "Deu",
    "JOS": "Jos", "JDG": "Jdg", "RUT": "Rut", "1SA": "1Sa", "2SA": "2Sa",
    "1KI": "1Ki", "2KI": "2Ki", "1CH": "1Ch", "2CH": "2Ch", "EZR": "Ezr",
    "NEH": "Neh", "EST": "Est", "JOB": "Job", "PSA": "Psa", "PRO": "Pro",
    "ECC": "Ecc", "SNG": "Sng", "ISA": "Isa", "JER": "Jer", "LAM": "Lam",
    "EZK": "Ezk", "DAN": "Dan", "HOS": "Hos", "JOL": "Jol", "AMO": "Amo",
    "OBA": "Oba", "JON": "Jon", "MIC": "Mic", "NAM": "Nam", "HAB": "Hab",
    "ZEP": "Zep", "HAG": "Hag", "ZEC": "Zec", "MAL": "Mal",
    "MAT": "Mat", "MRK": "Mrk", "LUK": "Luk", "JHN": "Jhn", "ACT": "Act",
    "ROM": "Rom", "1CO": "1Co", "2CO": "2Co", "GAL": "Gal", "EPH": "Eph",
    "PHP": "Php", "COL": "Col", "1TH": "1Th", "2TH": "2Th", "1TI": "1Ti",
    "2TI": "2Ti", "TIT": "Tit", "PHM": "Phm", "HEB": "Heb", "JAS": "Jas",
    "1PE": "1Pe", "2PE": "2Pe", "1JN": "1Jn", "2JN": "2Jn", "3JN": "3Jn",
    "JUD": "Jud", "REV": "Rev",
}


def tokens(a):
    g = (a.get("english") or a.get("gloss") or "").lower()
    g = g.replace(".", " ").replace("~", " ")
    return [w for w in re.findall(r"[a-z]+", g)
            if w not in STOP and len(w) > 2]


def read_corpus():
    bags = {}
    files = sorted(MAC.glob("*/*.xml"))
    for i, p in enumerate(files):
        if i % 250 == 0:
            print(f"  reading {i}/{len(files)} ...", flush=True)
        for m in W.finditer(p.read_text(encoding="utf-8")):
            a = dict(A.findall(m.group(1)))
            r = REF.match(a.get("ref", "") or "")
            if not r or not BOOK.get(r.group(1)):
                continue
            ref = f"{BOOK[r.group(1)]}.{int(r.group(2))}.{int(r.group(3))}"
            bags.setdefault(ref, []).extend(tokens(a))
    return bags


def load(name):
    rows = []
    p = OUT / name
    if not p.exists():
        return rows
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                if not any(k.startswith("_") for k in d):
                    rows.append(d)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vocab", type=int, default=4000)
    ap.add_argument("--passage", default="Psa.103")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--csv", metavar="PATH", default=None,
                    help="also write the passage table to a CSV that opens in "
                         "a spreadsheet. 2026-09-09: the table existed only in "
                         "scrollback.")
    a = ap.parse_args()

    bags = read_corpus()
    print(f"verses with glosses: {len(bags)}")

    df = collections.Counter()
    for toks in bags.values():
        df.update(set(toks))
    vocab = [w for w, _ in df.most_common(a.vocab)]
    idx = {w: i for i, w in enumerate(vocab)}
    N = len(bags)
    idf = np.array([math.log(N / df[w]) for w in vocab], dtype=np.float64)
    print(f"vocabulary {len(vocab)}  (of {len(df)} distinct glosses)")

    refs = sorted(bags)
    M = np.zeros((len(refs), len(vocab)), dtype=np.float32)
    for r, ref in enumerate(refs):
        c = collections.Counter(t for t in bags[ref] if t in idx)
        for w, n in c.items():
            M[r, idx[w]] = n
    M *= idf.astype(np.float32)
    norm = np.linalg.norm(M, axis=1, keepdims=True)
    norm[norm == 0] = 1.0
    Mn = M / norm

    # MEAN-CENTRE FIRST. Skipping this was a real bug on the first run: an
    # uncentred eigendecomposition returns the *average document direction* as
    # its leading eigenvector, so axis 1 came back as "lord, god, said, israel,
    # king" -- which is word frequency, not theme -- and every verse scored
    # cosine 1.00 against every other because they all pointed the same way.
    # Centring is what makes this PCA rather than a restatement of the mean.
    mu = Mn.mean(axis=0, keepdims=True)
    Mc = Mn - mu

    # eigendecomposition of the feature covariance: deterministic
    print("eigendecomposing feature covariance ...", flush=True)
    C = (Mc.T @ Mc).astype(np.float64)
    vals, vecs = np.linalg.eigh(C)
    order = np.argsort(vals)[::-1][:3]
    axes = vecs[:, order]
    # SIGN CONVENTION: largest-magnitude loading of each axis is positive
    for k in range(3):
        j = int(np.argmax(np.abs(axes[:, k])))
        if axes[j, k] < 0:
            axes[:, k] *= -1
    share = float(vals[order].sum() / vals.sum())
    print(f"  variance captured by 3 axes: {100*share:.1f}%")

    print("\nWHAT THE AXES TURNED OUT TO BE (top loadings)")
    for k in range(3):
        top = np.argsort(axes[:, k])[::-1][:8]
        bot = np.argsort(axes[:, k])[:5]
        print(f"  axis {k+1}  +: {[vocab[i] for i in top]}")
        print(f"          -: {[vocab[i] for i in bot]}")

    coords = Mc @ axes
    mag = np.linalg.norm(coords, axis=1)
    rank = mag.argsort().argsort() / max(len(mag) - 1, 1)

    pos = {ref: i for i, ref in enumerate(refs)}
    shape = {}
    for r in load("cola.jsonl.gz"):
        shape[r["ref"]] = r
    role = {}
    for s in load("sentence-function.jsonl.gz"):
        role.setdefault(s["ref"], s)

    rows = []
    for i, ref in enumerate(refs):
        c = shape.get(ref) or {}
        s = role.get(ref) or {}
        rows.append({
            "ref": ref,
            "theme": [round(float(x), 4) for x in coords[i]],
            "strength": round(float(rank[i]), 3),
            "cola": c.get("n"),
            "role": (f"{s.get('relation')}/{s.get('subtype')}"
                     if s.get("relation") else None),
            "direction": s.get("direction"),
        })

    # ---- the passage table ------------------------------------------------
    print(f"\n{'=' * 78}\n{a.passage} -- theme, shape, role\n{'=' * 78}")
    print(f"  {'v':<4}{'theme (x, y, z)':<28}{'str':<6}{'shape':<12}"
          f"{'role':<24}{'dir'}")
    sel = [r for r in rows if r["ref"].startswith(a.passage + ".")]
    sel.sort(key=lambda r: int(r["ref"].split(".")[2]))
    for r in sel:
        t = ", ".join(f"{x:+.2f}" for x in r["theme"])
        sh = shape.get(r["ref"]) or {}
        cs = "|".join(str(c["words"]) for c in sh.get("cola", []))
        neutral = " (neutral)" if r["strength"] < 0.25 else ""
        print(f"  {r['ref'].split('.')[2]:<4}{t:<28}{r['strength']:<6.2f}"
              f"{cs:<12}{str(r['role'] or '-'):<24}"
              f"{str(r['direction'] or '-')}{neutral}")

    # ---- the table as a FILE, not just scrollback ------------------------
    if a.csv:
        import csv as _csv
        dest = pathlib.Path(a.csv)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", newline="", encoding="utf-8-sig") as fh:
            w = _csv.writer(fh)
            w.writerow(["ref", "verse", "theme_x", "theme_y", "theme_z",
                        "strength", "neutral", "cola", "shape", "role",
                        "direction", "nearest_1", "dist_1", "nearest_2",
                        "dist_2", "nearest_3", "dist_3"])
            inp = np.array([r["ref"].startswith(a.passage + ".") for r in rows])
            for r in sel:
                i = pos[r["ref"]]
                d = np.linalg.norm(coords - coords[i], axis=1)
                d[inp] = np.inf
                b = np.argsort(d)[:3]
                sh = shape.get(r["ref"]) or {}
                w.writerow([
                    r["ref"], r["ref"].split(".")[2],
                    *[f"{x:.4f}" for x in r["theme"]],
                    f"{r['strength']:.3f}",
                    "yes" if r["strength"] < 0.25 else "",
                    sh.get("n") or "",
                    "|".join(str(c["words"]) for c in sh.get("cola", [])),
                    r["role"] or "", r["direction"] or "",
                    refs[b[0]], f"{d[b[0]]:.4f}",
                    refs[b[1]], f"{d[b[1]]:.4f}",
                    refs[b[2]], f"{d[b[2]]:.4f}"])
        print(f"\n  table written to {dest}")

    # ---- connections elsewhere -------------------------------------------
    print(f"\n{'=' * 78}\nCONNECTIONS ELSEWHERE -- nearest verse outside "
          f"{a.passage}\n{'=' * 78}")
    # EUCLIDEAN, not cosine. Cosine measures ANGLE, and in a 3-dimensional
    # space holding 31,156 points some verse always sits at nearly zero angle
    # to any other -- the first run returned similarity 1.00 for every single
    # neighbour, which is a property of the metric and not a finding. The request
    # was for "relative distances", which is what this now measures.
    inpass = np.array([r["ref"].startswith(a.passage + ".") for r in rows])
    for r in sel:
        i = pos[r["ref"]]
        d = np.linalg.norm(coords - coords[i], axis=1)
        d[inpass] = np.inf
        best = np.argsort(d)[:3]
        got = ", ".join(f"{refs[j]} ({d[j]:.3f})" for j in best)
        print(f"  v{r['ref'].split('.')[2]:<4} {got}")

    # --- DOES THE SPACE MEAN ANYTHING? a falsifiable check ----------------
    print(f"\n{'=' * 78}\nIS THE SPACE MEANINGFUL? nearest neighbour by book\n"
          f"{'=' * 78}")
    rng = np.random.default_rng(11)
    sample = rng.choice(len(refs), size=600, replace=False)
    bookof = [r.split(".")[0] for r in refs]
    same = 0
    for i in sample:
        d = np.linalg.norm(coords - coords[i], axis=1)
        d[i] = np.inf
        j = int(np.argmin(d))
        if bookof[j] == bookof[i]:
            same += 1
    bookshare = collections.Counter(bookof)
    exp = sum((bookshare[b] - 1) / (len(refs) - 1) for b in
              (bookof[i] for i in sample)) / len(sample)
    print(f"  nearest neighbour is in the SAME BOOK: {same}/{len(sample)} "
          f"= {100*same/len(sample):.1f}%")
    print(f"  expected by chance:                    {100*exp:.1f}%")
    print(f"  lift {(same/len(sample))/max(exp, 1e-9):.2f}x   "
          f"{'the space carries real signal' if same/len(sample) > 2*exp else 'WEAK -- treat coordinates as provisional'}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": CREDIT,
            "_note": "Deterministic 3-coordinate theme space from an "
                     "eigendecomposition of IDF-weighted gloss co-occurrence, "
                     "with the colon count from the Masoretic accents and the "
                     "PDTB-style discourse role. No model is used; the same "
                     "input reproduces the same axes, whose sign is fixed by "
                     "making each axis's largest loading positive.",
            "variance_captured": round(share, 4),
            "axes": [[vocab[i] for i in np.argsort(axes[:, k])[::-1][:10]]
                     for k in range(3)],
        }, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(rows)} verses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
