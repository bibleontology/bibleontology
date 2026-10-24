"""One verse, with MACULA's own tree beside the structure we built from it.

2026-09-21: work on verse examples one at a time until the node structures
within the sentence level are always constructed correctly; do not move on
until that happens.

This is the instrument for that. It puts three things on one screen:

    the words        lemma, gloss and the ROLE MACULA gives each constituent
    MACULA's tree    every clause, its rule, and what it covers
    our structure    the nodes and edges the extraction produced

and then says which of our edges are missing an end. An edge with one end is
not a relation, and **55.6% of the corpus's 261,919 edges had fewer than two**
when this was written — so the last section is the one to read first.

The comparison is the point. A clause MACULA tags `P-PP` — predicate plus
prepositional phrase — is a bound relation in the source; if it comes out here
as two edges hanging off `None`, the extraction lost it, and the tree above
says so in the same window.

    python tools/verse.py Exo.8.6
    python tools/verse.py Gen.1.4 --tree      # MACULA's tree in full
"""
from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

USFM = {
    "Gen": "01-Gen", "Exo": "02-Exo", "Lev": "03-Lev", "Num": "04-Num",
    "Deu": "05-Deu", "Jos": "06-Jos", "Jdg": "07-Jdg", "Rut": "08-Rut",
    "1Sa": "09-1Sa", "2Sa": "10-2Sa", "1Ki": "11-1Ki", "2Ki": "12-2Ki",
    "1Ch": "13-1Ch", "2Ch": "14-2Ch", "Ezr": "15-Ezr", "Neh": "16-Neh",
    "Est": "17-Est", "Job": "18-Job", "Psa": "19-Psa", "Pro": "20-Pro",
    "Ecc": "21-Ecc", "Sng": "22-Sng", "Isa": "23-Isa", "Jer": "24-Jer",
    "Lam": "25-Lam", "Ezk": "26-Ezk", "Dan": "27-Dan", "Hos": "28-Hos",
    "Jol": "29-Jol", "Amo": "30-Amo", "Oba": "31-Oba", "Jon": "32-Jon",
    "Mic": "33-Mic", "Nam": "34-Nam", "Hab": "35-Hab", "Zep": "36-Zep",
    "Hag": "37-Hag", "Zec": "38-Zec", "Mal": "39-Mal",
}
BOOKCODE = {
    "Gen": "GEN", "Exo": "EXO", "Lev": "LEV", "Num": "NUM", "Deu": "DEU",
    "Jos": "JOS", "Jdg": "JDG", "Rut": "RUT", "1Sa": "1SA", "2Sa": "2SA",
    "1Ki": "1KI", "2Ki": "2KI", "1Ch": "1CH", "2Ch": "2CH", "Ezr": "EZR",
    "Neh": "NEH", "Est": "EST", "Job": "JOB", "Psa": "PSA", "Pro": "PRO",
    "Ecc": "ECC", "Sng": "SNG", "Isa": "ISA", "Jer": "JER", "Lam": "LAM",
    "Ezk": "EZK", "Dan": "DAN", "Hos": "HOS", "Jol": "JOL", "Amo": "AMO",
    "Oba": "OBA", "Jon": "JON", "Mic": "MIC", "Nam": "NAM", "Hab": "HAB",
    "Zep": "ZEP", "Hag": "HAG", "Zec": "ZEC", "Mal": "MAL",
}


# The Greek files are named for the book, not numbered like the Hebrew ones,
# and a glob on the three-letter code found nothing: `*Jhn*` does not match
# `04-john.xml`. Named explicitly, since `1john` would otherwise be matched by
# a loose search for `john`.
GREEK_FILE = {
    "Mat": "01-matthew", "Mrk": "02-mark", "Luk": "03-luke", "Jhn": "04-john",
    "Act": "05-acts", "Rom": "06-romans", "1Co": "07-1corinthians",
    "2Co": "08-2corinthians", "Gal": "09-galatians", "Eph": "10-ephesians",
    "Php": "11-philippians", "Col": "12-colossians",
    "1Th": "13-1thessalonians", "2Th": "14-2thessalonians",
    "1Ti": "15-1timothy", "2Ti": "16-2timothy", "Tit": "17-titus",
    "Phm": "18-philemon", "Heb": "19-hebrews", "Jas": "20-james",
    "1Pe": "21-1peter", "2Pe": "22-2peter", "1Jn": "23-1john",
    "2Jn": "24-2john", "3Jn": "25-3john", "Jud": "26-jude",
    "Rev": "27-revelation",
}


def source_file(ref):
    b, c, _v = ref.split(".")
    stem = USFM.get(b)
    if stem:
        p = ROOT / "data" / "raw" / "macula" / "hebrew" / \
            f"{stem}-{int(c):03d}-lowfat.xml"
        if p.exists():
            return p
    g = GREEK_FILE.get(b)
    if g:
        for name in (f"{g}.xml", f"{g}-lowfat.xml"):
            p = ROOT / "data" / "raw" / "macula" / "greek" / name
            if p.exists():
                return p
    hits = sorted(glob.glob(str(ROOT / "data" / "raw" / "macula" / "greek"
                                / f"*{b.lower()}*")))
    return pathlib.Path(hits[0]) if hits else None


def words_of(ref, root):
    b, c, v = ref.split(".")
    want = f"{BOOKCODE.get(b, b.upper())} {int(c)}:{int(v)}"
    return [w for w in root.iter("w")
            if (w.get("ref") or "").startswith(want + "!")
            or (w.get("ref") or "") == want]


def show_tree(ref, root, full=False):
    ws = set(id(w) for w in words_of(ref, root))
    if not ws:
        print("  (no MACULA words found for this reference)")
        return
    parent = {c: p for p in root.iter() for c in p}
    # every wg that covers at least one of this verse's words
    groups = []
    for g in root.iter("wg"):
        inner = [w for w in g.iter("w") if id(w) in ws]
        if inner and (full or g.get("class") == "cl"):
            groups.append((g, inner))
    groups.sort(key=lambda gi: -len(gi[1]))
    seen = set()
    for g, inner in groups:
        depth = 0
        cur = g
        while cur in parent:
            cur = parent[cur]
            depth += 1
        key = (g.get("rule"), tuple(w.get("ref") for w in inner))
        if key in seen:
            continue
        seen.add(key)
        pad = "  " * min(depth, 6)
        roles = [f"{ch.get('role')}" for ch in list(g) if ch.get("role")]
        print(f"  {pad}<{g.get('class') or g.tag} rule={g.get('rule')}"
              + (f" role={g.get('role')}" if g.get("role") else "")
              + ">"
              + (f"   roles: {' '.join(roles)}" if roles else ""))
        print(f"  {pad}   " + " · ".join((w.get("gloss") or "?")
                                         for w in inner))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ref", help="a MACULA reference, e.g. Exo.8.6")
    ap.add_argument("--tree", action="store_true",
                    help="every word group, not only clauses")
    a = ap.parse_args()
    ref = a.ref

    # ---- the words ------------------------------------------------------
    print(f"\n=== {ref} — the words ===\n")
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if d.get("ref") == ref:
            for i, w in enumerate(d.get("words") or []):
                print(f"  {i:>2}  {w.get('t', ''):<16} {w.get('l', ''):<12}"
                      f" {w.get('s', ''):<7} {w.get('p', ''):<11}"
                      f" {w.get('g', '')}")
            break

    # ---- MACULA's own tree ----------------------------------------------
    print(f"\n=== MACULA's clauses ===\n")
    src = source_file(ref)
    if src and src.exists():
        try:
            show_tree(ref, ET.parse(src).getroot(), full=a.tree)
        except ET.ParseError as e:
            print(f"  (could not parse {src.name}: {e})")
    else:
        print("  (source file not found)")

    # ---- what we built ---------------------------------------------------
    print(f"\n=== our nodes ===\n")
    for line in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if d.get("ref") == ref:
            print(f"  {d['id'].split('#')[-1]:<22} {d.get('text', ''):<24}"
                  f" {d.get('lemma', ''):<12} {d.get('pos', '')}"
                  + ("  composite" if d.get("composite") else ""))

    print(f"\n=== our edges ===\n")
    loose = 0
    rows = []
    for line in gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt",
                          encoding="utf-8"):
        e = json.loads(line)
        if e.get("ref") != ref:
            continue
        s = (e.get("src") or "").split("#")[-1]
        t = (e.get("dst") or "").split("#")[-1]
        flags = [k for k in ("negated", "comparison", "intransitive",
                             "scopes_over", "inferred_subject",
                             "unresolved_possessor") if e.get(k)]
        bad = not s or not t
        loose += bad
        rows.append((bad, s or "—", e.get("type"), t or "—", flags))
    for bad, s, ty, t, flags in rows:
        print(f"  {'!' if bad else ' '} {s:<18} --{ty:^14}-> {t:<18}"
              + ("  " + ",".join(flags) if flags else ""))

    print(f"\n  {len(rows) - loose} of {len(rows)} edges have both ends"
          + (f"   —  {loose} do NOT (marked !)" if loose else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
