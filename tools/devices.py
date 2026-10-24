"""Simple marking passes: each one flags one thing, deterministically.

2026-09-09, after a 3b model failed to group Psalm 119 from metadata: simple
rules are needed, perhaps passes that make markings for different things that
could help make deterministic calls.

That is the right architecture and it matches what has actually worked. Every
result that survived testing today was **one simple signal measured alone** --
a quote closing at 2.28x, a temporal connective at 1.78x, the acrostic at 22 of
22 exact. Every attempt at a holistic judgement failed: the five-signal episode
scorer at 1.52x, first-colon shape at 0.99x, person shift at a coin flip, and
the model itself at 18% recall with its boundaries bunched in the last third of
the prompt.

So this makes no calls. **It marks, and something else decides.**

## The passes

    ACROSTIC   consecutive verses whose first Hebrew letter walks the alphabet.
               Exact where it applies: Psalm 119 comes back as 22 runs of
               exactly 8, with no errors.
    ANAPHORA   consecutive verses opening on the same lemma. Psalm 103:20-22
               all open בָּרַךְ.
    INCLUSIO   a lemma present at the head and the tail of a passage and
               NOWHERE between. Psalm 103 returns בָּרַךְ and נֶפֶשׁ.
    REFRAIN    a colon whose content lemmas repeat elsewhere in the passage.
    ADDRESS    a change in grammatical person -- who is being spoken to.
               Marked, never scored: measured across all 150 psalms it changes
               at 50.7% of verse boundaries, so it is a coin flip on its own
               and is emitted only as context for a rule that combines it.

## Why marks and not scores

A score commits to a weighting before anyone knows which signals matter for the
passage in hand, and the weights that suit narrative invert in poetry -- five
signals were measured doing exactly that. A mark commits to nothing: it says
"an acrostic runs here" and leaves the decision to a rule that can see what else
is marked. Earlier the same day: multiple grouping schemes are to be supported.
Marks support many schemes; a single score supports one.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
HEB = ROOT / "data" / "raw" / "macula" / "hebrew"
DEST = ROOT / "out" / "devices.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, Clear Bible, CC BY 4.0"

W = re.compile(r"<w\s([^>]*?)/?>", re.S)
A = re.compile(r'([\w:.-]+)="([^"]*)"', re.S)
REF = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)!(\d+)")
FUNC = {"prep", "conj", "art", "ptcl"}
ALEF, TAV = "א", "ת"
OLE, ETNAHTA = "֫", "֑"

BOOK = {"GEN": "Gen", "EXO": "Exo", "LEV": "Lev", "NUM": "Num", "DEU": "Deu",
        "JOS": "Jos", "JDG": "Jdg", "RUT": "Rut", "1SA": "1Sa", "2SA": "2Sa",
        "1KI": "1Ki", "2KI": "2Ki", "1CH": "1Ch", "2CH": "2Ch", "EZR": "Ezr",
        "NEH": "Neh", "EST": "Est", "JOB": "Job", "PSA": "Psa", "PRO": "Pro",
        "ECC": "Ecc", "SNG": "Sng", "ISA": "Isa", "JER": "Jer", "LAM": "Lam",
        "EZK": "Ezk", "DAN": "Dan", "HOS": "Hos", "JOL": "Jol", "AMO": "Amo",
        "OBA": "Oba", "JON": "Jon", "MIC": "Mic", "NAM": "Nam", "HAB": "Hab",
        "ZEP": "Zep", "HAG": "Hag", "ZEC": "Zec", "MAL": "Mal"}


def read(path):
    byv = collections.defaultdict(list)
    for m in W.finditer(path.read_text(encoding="utf-8")):
        a = dict(A.findall(m.group(1)))
        r = REF.match(a.get("ref", "") or "")
        if r and BOOK.get(r.group(1)):
            byv[(BOOK[r.group(1)], int(r.group(2)), int(r.group(3)))].append(
                (int(r.group(4)), a))
    return {k: [a for _, a in sorted(v, key=lambda x: x[0])]
            for k, v in byv.items()}


def first_letter(ws):
    for a in ws:
        for ch in unicodedata.normalize("NFD", a.get("unicode") or ""):
            if ALEF <= ch <= TAV:
                return ch
    return None


def content(ws):
    return [a["lemma"] for a in ws
            if a.get("lemma") and (a.get("class") or a.get("pos")) not in FUNC]


def cola(ws):
    out, cur = [], []
    for a in ws:
        cur.append(a)
        u = unicodedata.normalize("NFD", a.get("unicode") or "")
        if any(c in (OLE, ETNAHTA) for c in u):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def mark_chapter(verses):
    """verses: {v: [words]} for ONE chapter -> {v: [device, ...]}"""
    vs = sorted(verses)
    marks = collections.defaultdict(list)

    # ACROSTIC: runs of a shared first letter, walking the alphabet
    letters = {v: first_letter(verses[v]) for v in vs}
    runs, cur = [], None
    for v in vs:
        L = letters[v]
        if cur and L == cur[1]:
            cur[2] = v
        else:
            if cur:
                runs.append(cur)
            cur = [v, L, v]
    if cur:
        runs.append(cur)
    # A REAL acrostic walks most of the 22-letter alphabet in order. The first
    # threshold here was ">=8 runs, 60% ascending" and it fired on 2Ch 34,
    # Exo 23, Gen 32, Job 37 and Sng 1 -- roughly 40% precision, because any
    # chapter whose verses happen to start with rising letters cleared it.
    # Requiring alphabet COVERAGE and near-monotonic order is what separates
    # a designed acrostic from a run of luck.
    seq = [r[1] for r in runs if r[1]]
    walks = sum(1 for i in range(len(seq) - 1)
                if seq[i] and seq[i + 1] and ord(seq[i + 1]) > ord(seq[i]))
    covered = len(set(seq))
    span = (ord(max(seq)) - ord(min(seq)) + 1) if seq else 0
    if (len(runs) >= 8 and covered >= 12 and span >= 18
            and walks >= max(len(seq) - 1 - 3, 0)):
        for a0, L, b in runs:
            for v in range(a0, b + 1):
                marks[v].append({"device": "acrostic", "letter": L,
                                 "run": [a0, b]})

    # ANAPHORA: consecutive verses opening on the same content lemma
    opens = {}
    for v in vs:
        c = content(verses[v])
        if c:
            opens[v] = c[0]
    i = 0
    ov = sorted(opens)
    while i < len(ov):
        j = i
        while (j + 1 < len(ov) and ov[j + 1] == ov[j] + 1
               and opens[ov[j + 1]] == opens[ov[i]]):
            j += 1
        if j > i:
            for k in range(i, j + 1):
                marks[ov[k]].append({"device": "anaphora",
                                     "lemma": opens[ov[i]],
                                     "run": [ov[i], ov[j]]})
        i = j + 1

    # INCLUSIO: a lemma at head and tail and nowhere between
    if len(vs) >= 6:
        head = set(content(verses[vs[0]])) | set(content(verses[vs[1]]))
        tail = set(content(verses[vs[-1]])) | set(content(verses[vs[-2]]))
        mid = set()
        for v in vs[2:-2]:
            mid |= set(content(verses[v]))
        for L in (head & tail) - mid:
            for v in (vs[0], vs[1], vs[-2], vs[-1]):
                marks[v].append({"device": "inclusio", "lemma": L,
                                 "run": [vs[0], vs[-1]]})

    # REFRAIN: a colon whose content lemma set recurs in the chapter
    sigs = collections.defaultdict(list)
    for v in vs:
        for c in cola(verses[v]):
            s = frozenset(x for x in content(c))
            if len(s) >= 2:
                sigs[s].append(v)
    for s, where in sigs.items():
        if len(set(where)) >= 3:
            for v in set(where):
                marks[v].append({"device": "refrain",
                                 "lemmas": sorted(s),
                                 "count": len(set(where))})
    return marks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--passage", default="Psa.103")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    files = sorted(HEB.glob("*.xml"))
    allmarks = {}
    tally = collections.Counter()
    for i, p in enumerate(files):
        if i % 250 == 0:
            print(f"  {i}/{len(files)} ...", flush=True)
        byv = read(p)
        chapters = collections.defaultdict(dict)
        for (bk, ch, v), ws in byv.items():
            chapters[(bk, ch)][v] = ws
        for (bk, ch), verses in chapters.items():
            for v, ms in mark_chapter(verses).items():
                allmarks[f"{bk}.{ch}.{v}"] = ms
                for m in ms:
                    tally[m["device"]] += 1

    print(f"\nverses carrying at least one mark: {len(allmarks)}")
    print(f"  marks by device: {dict(tally.most_common())}")

    print(f"\n{a.passage} -- what is marked")
    pref = a.passage + "."
    got = sorted((k for k in allmarks if k.startswith(pref)),
                 key=lambda k: int(k.split(".")[2]))
    if not got:
        print("   nothing marked")
    for k in got:
        v = k.split(".")[2]
        for m in allmarks[k]:
            extra = {x: y for x, y in m.items() if x != "device"}
            print(f"   v{v:<4} {m['device']:<10} {extra}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": CREDIT,
            "_note": "Marking passes, not decisions (2026-09-09). Each "
                     "pass flags one device deterministically and commits to "
                     "no weighting; a rule that can see several marks makes "
                     "the call. Acrostic, anaphora, inclusio and refrain are "
                     "structural devices of Hebrew poetry.",
        }, ensure_ascii=False) + "\n")
        for k in sorted(allmarks):
            f.write(json.dumps({"ref": k, "marks": allmarks[k]},
                               ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(allmarks)} verses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
