"""The clean structure builder (plan 1.26).

    python tools/builder/build.py            # writes out/structure-*.jsonl.gz
    python tools/builder/build.py --install  # ...and makes them the live graph
    python tools/builder/build.py --verse 2Sa.17.14   # one verse, printed

Stages run in order; each may add only what the design lets it decide: S0
(source), S1 (clauses and roles), S2-S3, S4-S5, and S6 (the BSB's readings,
in a layer of their own).

The live structure graph is out/placeholder-{nodes,edges,readings}.jsonl.gz.
The name is historical (the first structure was a placeholder for this
builder's); --install copies the new structure-* files over it and keeps the
old as *.old.jsonl.gz.
"""
import argparse
import gzip
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import source as S0                                        # noqa: E402
from s1_clauses import S1, Tables                          # noqa: E402
from s2_s3 import Lexicon, s2, s3                          # noqa: E402
from s4_s5 import s4, s4_letters, s4_writings, s5          # noqa: E402
from s6_readings import s6                                 # noqa: E402

OUT = ROOT / "out"
LIVE = ("placeholder-nodes.jsonl.gz", "placeholder-edges.jsonl.gz",
        "placeholder-readings.jsonl.gz")
LANGS = ("hebrew", "greek")


def build(langs=LANGS, only=None):
    """Every language through the same stages, each with its own tables
    (2026-09-27: the more aligned in structure, the more effective
    the pattern matching). The Aramaic of Daniel and Ezra is in MACULA's
    Hebrew files, read with the Hebrew tables."""
    verses = {}
    for lang in langs:
        t, lx = Tables(lang), Lexicon(lang)
        mine = {}
        for path in S0.files(lang):
            root, words = S0.load(path, lang)
            if only and not any(w["ref"] == only for w in words.values()):
                continue
            one = S1(words, lang, t)
            vs = one.run(root)
            s2(vs, words, lx)
            s3(vs, lx)
            s4(vs, lx, one.sentences)
            mine.update(vs)
        s4_writings(mine, lx) if lang == "hebrew" else s4_letters(mine, lx)
        verses.update(mine)
    s5(verses, reflexive_marked={l for l in langs
                                 if Lexicon(l).reflexive_marked})
    return verses


def install():
    """Put the new graph where the app reads it, keeping the old one.
    Reversible with --restore (the new base is evaluated in the app)."""
    for name in LIVE:
        live, old = OUT / name, OUT / name.replace(".jsonl", ".old.jsonl")
        new = OUT / name.replace("placeholder", "structure")
        if not new.exists():
            continue
        if live.exists() and not old.exists():
            live.replace(old)
        new_bytes = new.read_bytes()
        live.write_bytes(new_bytes)
    print("installed the new graph; the old one is kept as *.old.jsonl.gz")


def restore():
    for name in LIVE:
        live, old = OUT / name, OUT / name.replace(".jsonl", ".old.jsonl")
        if old.exists():
            old.replace(live)
    print("restored the old graph")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verse")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    if a.restore:
        restore()
        return
    t0 = time.time()
    verses = build(only=a.verse)
    if not verses:
        # a fresh clone has no data/raw/macula: the stages ran over nothing,
        # and --install would have put an empty structure over the live one
        # (the correctness review, 2026-10-22)
        sys.exit("built 0 verses: is MACULA fetched? python tools/fetch_macula.py --all (nothing written)")
    # S6, LAST, AND APART: the BSB's readings go to their own layer file,
    # never into the structure (docs/BUILDER-DESIGN.md, decision 3)
    readings, stats = s6(verses)
    if a.verse:
        for e in readings:
            if e["ref"] == a.verse:
                print("R", e["src"].split("#")[1], "->", e["dst"],
                      e["inferred"])
        v = verses[a.verse]
        for n in v.nodes.values():
            print("N", json.dumps({k: n[k] for k in n if k not in
                                   ("src", "lang")}, ensure_ascii=False))
        for e in v.edges:
            print("E", e["type"], e["src"].split("#")[1], "->",
                  (e["dst"] or "").split("#")[-1],
                  {k: e[k] for k in ("rel", "prep", "role") if e.get(k)})
        for c in v.connectives:
            print("C", c)
        return
    nn = ne = 0
    with gzip.open(OUT / "structure-nodes.jsonl.gz", "wt",
                   encoding="utf-8") as nf, \
            gzip.open(OUT / "structure-edges.jsonl.gz", "wt",
                      encoding="utf-8") as ef:
        for ref in sorted(verses):
            v = verses[ref]
            for n in v.nodes.values():
                nf.write(json.dumps(n, ensure_ascii=False) + "\n")
                nn += 1
            for e in v.edges:
                ef.write(json.dumps(e, ensure_ascii=False) + "\n")
                ne += 1
    with gzip.open(OUT / "structure-readings.jsonl.gz", "wt",
                   encoding="utf-8") as rf:
        for e in readings:
            rf.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"{len(verses):,} verses, {nn:,} nodes, {ne:,} edges, "
          f"{time.time() - t0:.0f}s")
    print(f"S6 readings layer: {len(readings):,} pronouns named by the BSB",
          dict(stats))
    if a.install:
        install()


if __name__ == "__main__":
    main()
