"""No KJV wording in the question cards, the concept hubs or the traditions layer, shown or held (A.22).

The public export scans for KJV text (tools/export_public.py), but only what it publishes, so a card is first scanned
on the day it is shown, at the last step of a release. On 2026-10-27 that is where two confessions' KJV phrasings
were found in the election and human-nature cards (the KJV's wording of 1 Peter 1:20 and Romans 5:12, carried in a
confession's own phrasing), after preflight had passed. This runs the same detector, the same rule (a six-word
KJV-only run with an archaic word, or an eight-word one), over every card in preflight.

Proven 2026-10-27 by planting both verses in-process (below): both caught. The plants are read from the KJV on this
machine at run time, never written here, so this file can go out in the public copy (whose own KJV scan refused it
when they were). Needs data/raw/kjv/ (the detector), as the export does. Run: python tests/test_kjv_cards.py"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import export_public as E                           # noqa: E402


def files():
    for d, pat in (("ontology/questions", "*.json"), ("ontology/concept-hubs", "*.json"),
                   ("ontology/traditions", "*.jsonl")):
        yield from sorted((ROOT / d).glob(pat))


def kjv_verse(book, ch, v):
    """One KJV verse's words, from data/raw/kjv/ (the detector's own source)."""
    tags = re.compile(r"\\[a-z0-9]+\*?|\|[^\\]*?(?=\\w\*)|strong=\"[^\"]*\"")     # export_public's
    path = next((ROOT / "data" / "raw" / "kjv").glob(f"*-{book}eng-*.usfm"))
    c = None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("\\c "):
            c = int(line[3:].split()[0])
        elif c == ch and line.startswith(f"\\v {v} "):
            return " ".join(E.words(tags.sub(" ", line[3 + len(str(v)):])))
    raise SystemExit(f"KJV {book} {ch}:{v} not found")


def main():
    # the public copy has no KJV (data/raw/ never travels): nothing to detect with, so nothing to check
    if not (ROOT / "data" / "raw" / "kjv").exists():
        print("KJV in cards: skipped, data/raw/kjv/ is not on this machine (the detector)")
        return
    runs6, runs8 = E.kjv_only_runs(6), E.kjv_only_runs(8)
    hits = lambda text: E.kjv_hits(E.words(text), runs6, runs8)
    fails = []
    n = 0
    for f in files():
        n += 1
        w = E.words(f.read_text(encoding="utf-8"))
        for i in range(len(w) - 5):                 # the rule of E.kjv_hits, with the words shown
            r6 = tuple(w[i:i + 6])
            if r6 in runs6 and (E.archaic(r6) or tuple(w[i:i + 8]) in runs8):
                fails.append(f"FAIL {f.relative_to(ROOT).as_posix()}: KJV wording '{' '.join(w[i:i + 8])}'")
    # the two verses, as a card would carry them: a sentence of ours around the KJV's own words
    planted = {"Rom 5:12": '{"says": "it says ' + kjv_verse("ROM", 5, 12) + '"}',
               "1 Pet 1:20": '{"says": "Article III says Christ ' + kjv_verse("1PE", 1, 20) + '"}'}
    for what, text in planted.items():
        if not hits(text):
            fails.append(f"FAIL planted: the KJV of {what} was not caught")
    if hits('{"says": "death spread to all men, because all sinned (Romans 5:12)"}'):
        fails.append("FAIL planted: the Berean's wording was taken for the KJV")
    for f in fails:
        print(f)
    if fails:
        sys.exit(1)
    print(f"KJV in cards: {n} files (question cards, concept hubs, traditions layer; shown and held) clean; "
          f"3 planted checks held")


if __name__ == "__main__":
    main()
