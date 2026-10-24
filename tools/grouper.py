"""Build the group tree by closing the tightest seam first.

The method asked for: look at all borders between sentence groups, group the
tightest border first, then recalculate the strength on either side before
finding the next tightest border.

That is agglomerative merging with recomputation, and it is the right shape for
this problem for a reason the project already stated: *"the build is from the
bottom up but the look is from the top down."* A seam is not judged once against
a threshold; it is judged against every other seam, and the judgement changes as
its neighbours close.

## What "strength" is, and why each part of it is here

Every signal below was measured before being used, and none is sufficient alone
-- `docs/GROUPING-TESTS.md` established that for connectives, and this session
established it again for pronouns.

- **Shared content lemmas.** The primary signal, as first put: Genesis 2:4
  groups backward, because the node overlap runs that way: heavens, earth,
  created, made are all shared with chapter 1 and none with what follows. Rare words
  count for more than common ones, because sharing `said` is not evidence and
  sharing `Nimrod` is.
- **A shared referent.** Stronger than a shared lemma: the same *thing*, not the
  same word. From `tools/referents.py`.
- **Subject continuity.** The same subject across a seam is a scene continuing.
- **A backward-binding opening.** *For*, *Which*, *Therefore*, *So*. Measured on
  Titus as exactly right and on Mark as useless, so it is weighted low and never
  decides alone.
- **A pronoun subject**, which binds backward. Measured this session at 36%
  against a 43% baseline -- a real 7-point effect and no more, so it is worth a
  nudge and not a vote.

## What it does not do

It does not name a group, and it does not decide how many levels there are. It
closes seams until the tightest remaining one is weaker than the threshold, and
what is left is the tree. Naming is a reading.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import heapq
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "groups.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

# Openings that bind a unit to what precedes it. Deliberately short: the Mark
# measurement showed a long list makes this worse, not better.
BACKWARD = {"for", "which", "therefore", "so", "thus", "then", "wherefore",
            "because", "that", "but", "yet", "nevertheless"}

WEIGHT = {"lemma": 1.0, "referent": 2.0, "subject": 1.5,
          "backward": 0.8, "pronoun": 0.4, "speech": -6.0}

# A speech edge is a SEAM, so its weight is negative: it pushes two units apart
# rather than binding them. The ruling was that speech boundaries should
# always be a dominant signal; the first measurement was too crude --
# lumping every quotation together gave Mark a lift of 1.03, because a
# one-verse `and he said, X` is not a boundary. Filtered to speeches of at
# least MIN_SPEECH verses:
#
#     speech START   Job 3.05   Mrk 2.39   Gen 1.90
#     speech END+1    Job 1.82   Mrk 3.43   Gen 3.00
#
# And the asymmetry is real. In DIALOGUE the speech is the unit, so its opening
# is the seam; in NARRATIVE the speech is embedded and the seam is where
# narration resumes. Both edges are used and the genre decides which earns more.
MIN_SPEECH = 3


def norm(ref: str):
    p = ref.split(".")
    return (p[0], int(p[1]), int(p[2])) if len(p) == 3 and p[1].isdigit() else None


def load():
    """Verse-level units: content lemmas, referents, subject, opening word."""
    lemmas = collections.defaultdict(set)
    subj = {}
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            if d.get("lemma") and d.get("class") in ("noun", "adj", "verb"):
                lemmas[d["ref"]].add(d["lemma"])

    refof = {}
    p = OUT / "referents.jsonl.gz"
    if p.exists():
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                if any(k.startswith("_") for k in d):
                    continue
                for v in d["verses"]:
                    refof.setdefault(v, set()).add(d["id"])

    pron = set()
    cl = ROOT / "data" / "macula-clauses.jsonl.gz"
    PRON = {"הוּא", "הֵם", "אֲנִי", "אַתָּה", "αὐτός", "ἐγώ", "σύ", "οὗτος",
            "ἡμεῖς", "ὑμεῖς", "ἐκεῖνος"}
    if cl.exists():
        with gzip.open(cl, "rt", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                d = json.loads(line)
                if any(k.startswith("_") for k in d):
                    continue
                s = next((x for x in d.get("parts", []) if x.get("role") == "s"),
                         None)
                if not s:
                    continue
                lems = [l for l in (s.get("lemmas") or []) if l]
                if lems and lems[0] not in PRON:
                    subj.setdefault(d["ref"], lems[0])
                if set(lems) & PRON:
                    pron.add(d["ref"])

    verses = {}
    for line in (ROOT / "data" / "bible" / "verses.jsonl").read_text(
            encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if "b" in d:
            verses[(d["b"], d["c"], d["v"])] = d["t"]
    return lemmas, refof, subj, pron, verses


def speech_edges(min_verses=MIN_SPEECH):
    """Verses where a substantial speech opens, or where narration resumes."""
    RX = re.compile(r"^\s*(\S+?)\s+(\d+):(\d+)\s*$")
    BK = {"Gen": "Gen", "Job": "Job", "Mark": "Mrk", "Titus": "Tit"}
    out = collections.defaultdict(set)
    p = ROOT / "out" / "quotes.jsonl"
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        q = json.loads(line)
        if (q.get("verses") or 1) < min_verses:
            continue
        a, b = RX.match(str(q.get("from", ""))), RX.match(str(q.get("to", "")))
        if a:
            out[BK.get(a.group(1), a.group(1))].add((int(a.group(2)), int(a.group(3))))
        if b:
            out[BK.get(b.group(1), b.group(1))].add((int(b.group(2)), int(b.group(3)) + 1))
    return out


def build_units(lemmas, refof, subj, pron, verses, book_map):
    """One unit per verse, in canonical order, per book."""
    sp = speech_edges()
    by_book = collections.defaultdict(list)
    for ref in lemmas:
        k = norm(ref)
        if k:
            by_book[k[0]].append((k[1], k[2], ref))
    units = {}
    for b, rows in by_book.items():
        rows.sort()
        seq = []
        for c, v, ref in rows:
            kjv = book_map.get(b, b)
            text = verses.get((kjv, c, v), "")
            first = (re.findall(r"[A-Za-z]+", text) or [""])[0].lower()
            seq.append({
                "id": ref, "book": b, "c": c, "v": v,
                "lemmas": set(lemmas.get(ref, ())),
                "refs": set(refof.get(ref, ())),
                "subject": subj.get(ref),
                "opens_backward": first in BACKWARD,
                "pronoun": ref in pron,
                "speech_edge": (c, v) in sp.get(b, ()),
                "members": [ref],
            })
        units[b] = seq
    return units


def strength(a, b, idf):
    """How tightly two adjacent units hold together."""
    s = 0.0
    shared = a["lemmas"] & b["lemmas"]
    if shared:
        s += WEIGHT["lemma"] * sum(idf.get(x, 1.0) for x in shared)
    if a["refs"] & b["refs"]:
        s += WEIGHT["referent"] * len(a["refs"] & b["refs"])
    if a["subject"] and a["subject"] == b["subject"]:
        s += WEIGHT["subject"]
    if b["opens_backward"]:
        s += WEIGHT["backward"]
    if b["pronoun"]:
        s += WEIGHT["pronoun"]
    if b["speech_edge"]:
        s += WEIGHT["speech"]
    return s


def merge(a, b):
    return {"id": a["id"], "book": a["book"], "c": a["c"], "v": a["v"],
            "lemmas": a["lemmas"] | b["lemmas"],
            "refs": a["refs"] | b["refs"],
            "subject": a["subject"] or b["subject"],
            "opens_backward": a["opens_backward"],
            "pronoun": a["pronoun"],
            "speech_edge": a["speech_edge"],
            "members": a["members"] + b["members"]}


def group_book(seq, idf, threshold):
    """Close the tightest seam, recompute its neighbours, repeat."""
    live = list(range(len(seq)))
    nodes = {i: seq[i] for i in live}
    prev = {i: i - 1 for i in live}
    nxt = {i: i + 1 for i in live}
    prev[0] = None
    nxt[len(seq) - 1] = None

    heap = []
    for i in live[:-1]:
        heapq.heappush(heap, (-strength(nodes[i], nodes[i + 1], idf), i, i + 1))
    alive = set(live)
    merges = 0
    while heap:
        neg, i, j = heapq.heappop(heap)
        if i not in alive or j not in alive or nxt.get(i) != j:
            continue
        st = -neg
        if st < threshold:
            break
        nodes[i] = merge(nodes[i], nodes[j])
        alive.discard(j)
        merges += 1
        k = nxt.get(j)
        nxt[i] = k
        if k is not None:
            prev[k] = i
            heapq.heappush(heap, (-strength(nodes[i], nodes[k], idf), i, k))
    return [nodes[i] for i in sorted(alive)]


def legacy_starts():
    """The verse each legacy passage unit begins at, as ground truth seams."""
    BK = {"Gen": "Gen", "Job": "Job", "Mark": "Mrk", "Titus": "Tit"}
    RX = re.compile(r"^\s*(\S+?)[\s.](\d+)[:.](\d+)\s*$")
    starts = collections.defaultdict(set)
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(
            encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("type") != "passage":
            continue
        pts = []
        for x in e.get("refs", []):
            m = RX.match(str(x))
            if m:
                pts.append((BK.get(m.group(1), m.group(1)),
                            int(m.group(2)), int(m.group(3))))
        if pts:
            b, c, v = min(pts)
            starts[b].add((c, v))
    return starts


def score_book(groups, gold):
    """Boundary F1: did we cut where the workers cut?

    Boundaries rather than group membership, because a single wrong seam
    inside a long unit would otherwise be scored as many errors, and the
    question being asked is where the text turns.
    """
    ours = {(g["members"][0].split(".")[1], g["members"][0].split(".")[2])
            for g in groups}
    ours = {(int(c), int(v)) for c, v in ours}
    if not gold:
        return None
    tp = len(ours & gold)
    prec = tp / max(1, len(ours))
    rec = tp / max(1, len(gold))
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"f1": f1, "precision": prec, "recall": rec,
            "ours": len(ours), "gold": len(gold), "hit": tp}


def fit(units, idf, gold, train, test, trials, seed=7):
    """Search the weights against the legacy seams, on TRAIN books only.

    The question was whether to fit a function against the legacy. Yes, with one
    guard. The legacy Genesis units **contain the Tier 1 answer key** -- the six
    days of creation, the toledot -- and `docs/GROUPING-TESTS.md` is explicit
    that spending a held-out case to steer the work destroys it. So the fit
    never sees Genesis or Titus; they are the report.
    """
    import random
    rng = random.Random(seed)
    best = None
    keys = list(WEIGHT)
    for t in range(trials):
        cand = ({k: round(rng.uniform(0, 3), 2) for k in keys}
                if t else dict(WEIGHT))
        thr = round(rng.uniform(1, 14), 1) if t else 6.0
        WEIGHT.update(cand)
        f1s = []
        for b in train:
            if b not in units or not gold.get(b):
                continue
            sc = score_book(group_book(units[b], idf, thr), gold[b])
            if sc:
                f1s.append(sc["f1"])
        if not f1s:
            continue
        mean = sum(f1s) / len(f1s)
        if best is None or mean > best[0]:
            best = (mean, dict(cand), thr)
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--threshold", type=float, default=6.0)
    ap.add_argument("--book")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--show", type=int, default=12)
    ap.add_argument("--fit", action="store_true",
                    help="search weights against the legacy seams")
    ap.add_argument("--trials", type=int, default=400)
    a = ap.parse_args()

    BOOKMAP = {"Gen": "Gen", "Job": "Job", "Mrk": "Mark", "Tit": "Titus",
               "Psa": "Ps", "Exo": "Exod", "Deu": "Deut"}
    lemmas, refof, subj, pron, verses = load()
    units = build_units(lemmas, refof, subj, pron, verses, BOOKMAP)
    print(f"verses with content: {sum(len(v) for v in units.values())} "
          f"in {len(units)} books")

    df = collections.Counter()
    for seq in units.values():
        for u in seq:
            df.update(u["lemmas"])
    N = sum(len(v) for v in units.values())
    idf = {w: math.log(N / (1 + n)) for w, n in df.items()}

    if a.fit:
        gold = legacy_starts()
        TRAIN, TEST = ["Job", "Mrk"], ["Gen", "Tit"]
        print(f"\nfitting on {TRAIN}, holding out {TEST} "
              f"(they carry the Tier 1 answer key)")
        print(f"  legacy seams: "
              + ", ".join(f"{b}={len(gold.get(b, ()))}" for b in TRAIN + TEST))
        base = {b: score_book(group_book(units[b], idf, a.threshold), gold[b])
                for b in TRAIN + TEST if b in units and gold.get(b)}
        print("\n  BEFORE (hand-set weights)")
        for b, s in base.items():
            print(f"    {b:5} f1={s['f1']:.3f}  p={s['precision']:.2f} "
                  f"r={s['recall']:.2f}  ours={s['ours']} gold={s['gold']}")
        best = fit(units, idf, gold, TRAIN, TEST, a.trials)
        if not best:
            print("  no fit found")
            return 1
        mean, w, thr = best
        WEIGHT.update(w)
        print(f"\n  fitted on train: mean f1 {mean:.3f}")
        print(f"    weights {w}  threshold {thr}")
        print("\n  AFTER")
        for b in TRAIN + TEST:
            if b not in units or not gold.get(b):
                continue
            s = score_book(group_book(units[b], idf, thr), gold[b])
            tag = "train" if b in TRAIN else "HELD OUT"
            print(f"    {b:5} f1={s['f1']:.3f}  p={s['precision']:.2f} "
                  f"r={s['recall']:.2f}  ours={s['ours']} gold={s['gold']}"
                  f"   {tag}")
        return 0

    out, total = {}, 0
    for b, seq in units.items():
        if a.book and b != a.book:
            continue
        groups = group_book(seq, idf, a.threshold)
        out[b] = groups
        total += len(groups)
    src = sum(len(units[b]) for b in out)
    print(f"threshold {a.threshold}:  {src} verses -> {total} groups "
          f"({src/max(1,total):.1f} verses per group)")

    if a.book and out.get(a.book):
        print(f"\n{a.book}:")
        for g in out[a.book][:a.show]:
            ms = g["members"]
            print(f"  {ms[0]:12} .. {ms[-1]:12}  {len(ms):>3} verses")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({"_source": CREDIT,
                            "_note": "Bottom-up groups: the tightest seam "
                                     "closed first, neighbours recomputed."},
                           ensure_ascii=False) + "\n")
        for b, groups in out.items():
            for g in groups:
                f.write(json.dumps({"book": b, "members": g["members"],
                                    "n": len(g["members"])},
                                   ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({total} groups)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
