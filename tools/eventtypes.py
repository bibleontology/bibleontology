"""What KIND of event: from the predicate and what it acts on.

2026-09-10: more interestingly, the events should be categorizable -- healing
diseases, casting out demons (with these two fitting a coarser grained
pattern), confronting the religious leaders, etc.

Two grains, and the second is the interesting one.

## The fine grain: predicate plus patient

`out/frames.jsonl.gz` already carries agent, predicate and patient for 91,402
verbs, from MACULA's own PropBank-style annotation. An event type falls straight
out of the pair:

    ἐκβάλλω  cast out   +  δαιμόνιον demon      x23    EXORCISM
    καθαρίζω cleanse    +  λεπρός leper         x6     CLEANSING
    θεραπεύω heal       +  νόσος, μαλακία       x7     HEALING
    ἐγείρω   raise      +  νεκρός, παραλυτικός  x9     RAISING

No lexicon is consulted. The verb is what the text says was done and the patient
is what the text says it was done to.

## The coarse grain: verbs that act on the same things

The parenthesis -- these two fitting a coarser grained pattern -- is
the real request, and asserting a category called "restoration" would be the
wrong way to meet it. **A coarser type is derived instead: two predicates belong
together when they take the same kinds of patient.**

That is distributional and falsifiable. If healing and exorcism really are one
coarser thing, the verbs will share patients (the afflicted person, the crowd,
the named sufferer) and cluster without being told to. If they do not cluster,
the coarse category was a reader's intuition rather than a property of the text,
and this will say so.

The measure is cosine over each verb's patient distribution, IDF-weighted so a
patient like *αὐτός* (him) -- which everything takes -- cannot bind two verbs
together, while *δαιμόνιον* or *λεπρός* can.

## What this does not do

**It does not name the clusters.** A cluster is reported as its member verbs and
their commonest patients. Naming one "restoration" is a reading, and readings
belong to the reader; the machine's job is to say which verbs behave alike.

**It has no lexicon and no semantic domains.** UBS's `lexdomain` and `coredomain`
sit in the MACULA files and are permission-based; this project does not read
them, here or anywhere.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "eventtypes.jsonl.gz"

# patients so general they say nothing about the verb
GENERIC = {"αὐτός", "οὗτος", "ἐγώ", "σύ", "ἡμεῖς", "ὑμεῖς", "τίς", "πᾶς",
           "πολύς", "ἄλλος", "ἕκαστος", "ὅς", "ἐκεῖνος", "הוּא", "אֲנִי",
           "אַתָּה", "זֶה", "כֹּל", "אֲשֶׁר", "אֵת"}


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
    ap.add_argument("--scope", default="gospels",
                    choices=("gospels", "nt", "all"))
    ap.add_argument("--min-verb", type=int, default=8,
                    help="a predicate needs this many patiented uses")
    ap.add_argument("--join", type=float, default=0.24,
                    help="cosine at or above this puts two verbs together")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    NT = set("Mat Mrk Luk Jhn Act Rom 1Co 2Co Gal Eph Php Col 1Th 2Th 1Ti "
             "2Ti Tit Phm Heb Jas 1Pe 2Pe 1Jn 2Jn 3Jn Jud Rev".split())
    keep = ({"Mat", "Mrk", "Luk", "Jhn"} if a.scope == "gospels"
            else NT if a.scope == "nt" else None)

    fr = [f for f in load("frames.jsonl.gz")
          if f.get("patient") and (keep is None
                                   or f["ref"].split(".")[0] in keep)]
    print(f"frames with a patient, scope={a.scope}: {len(fr):,}")

    # ---- fine grain: (predicate, patient) ------------------------------
    pat = collections.defaultdict(collections.Counter)
    gloss, uses = {}, collections.Counter()
    for f in fr:
        L = f.get("lemma")
        if not L:
            continue
        uses[L] += 1
        gloss.setdefault(L, (f.get("gloss") or "").strip())
        for p in f["patient"]:
            if p not in GENERIC:
                pat[L][p] += 1

    verbs = [L for L in pat if uses[L] >= a.min_verb and pat[L]]
    print(f"predicates with >= {a.min_verb} patiented uses: {len(verbs)}")

    df = collections.Counter()
    for L in verbs:
        df.update(pat[L].keys())
    N = max(len(verbs), 1)
    idf = {p: math.log(N / c) for p, c in df.items()}

    def vec(L):
        v = {p: n * idf.get(p, 0) for p, n in pat[L].items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {k: x / norm for k, x in v.items()}

    V = {L: vec(L) for L in verbs}

    def cos(a_, b_):
        x, y = V[a_], V[b_]
        if len(x) > len(y):
            x, y = y, x
        return sum(w * y.get(k, 0) for k, w in x.items())

    # ---- coarse grain: verbs that act on the same things ---------------
    parent = {L: L for L in verbs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    pairs = []
    for i, u_ in enumerate(verbs):
        for w in verbs[i + 1:]:
            s = cos(u_, w)
            if s >= a.join:
                pairs.append((round(s, 3), u_, w))
                ra, rb = find(u_), find(w)
                if ra != rb:
                    parent[ra] = rb
    pairs.sort(reverse=True)

    groups = collections.defaultdict(list)
    for L in verbs:
        groups[find(L)].append(L)
    multi = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"joins at cosine >= {a.join}: {len(pairs)}   "
          f"clusters of 2+: {len(multi)}")

    print(f"\n{'='*74}\nCOARSE TYPES — verbs that act on the same kinds of "
          f"thing\n{'='*74}")
    for k, members in sorted(multi.items(), key=lambda kv: -len(kv[1])):
        members = sorted(members, key=lambda L: -uses[L])
        shared = collections.Counter()
        for L in members:
            shared.update(pat[L])
        top = [p for p, _ in shared.most_common(6)]
        print(f"\n  {len(members)} predicates, {sum(uses[L] for L in members)} uses")
        for L in members[:7]:
            print(f"     {L:<14} {gloss.get(L,'')[:20]:<21}"
                  f"{uses[L]:>4} uses   {list(pat[L])[:4]}")
        print(f"     patients in common: {top}")

    print(f"\n{'='*74}\nSTRONGEST PAIRS\n{'='*74}")
    for s, x, y in pairs[:12]:
        print(f"  {s:.2f}  {x:<14} {gloss.get(x,'')[:16]:<18}"
              f"{y:<14} {gloss.get(y,'')[:16]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    rows = []
    for L in verbs:
        rows.append({"predicate": L, "gloss": gloss.get(L), "uses": uses[L],
                     "patients": pat[L].most_common(8),
                     "coarse": find(L)})
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_note": "Event types from MACULA's frame annotation: the fine "
                     "grain is predicate plus patient, the coarse grain is "
                     "verbs that take the same kinds of patient, joined by "
                     "IDF-weighted cosine. Clusters are NOT named -- naming one "
                     "'restoration' is a reading and belongs to the reader. No "
                     "lexicon is used; UBS semantic domains are not read.",
            "scope": a.scope, "join": a.join,
        }, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(rows)} predicates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
