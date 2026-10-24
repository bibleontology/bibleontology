"""Do the words in a template actually appear in its instances?

2026-09-15, on the first row of the reworked Explore view: the first pattern
should say 'declares the [X]', not 'declares of [X]', as the first reference
makes obvious; check these systematically.

He is right about the row and right that it needs checking rather than
patching. `out/patterns.jsonl.gz` holds 12,494 templates and **the tool that
built them is not in this repository** -- nothing under `tools/` writes
`top_filler` or `distinct_fillers`, and the file's own header names only its
source corpus. So the wording cannot be fixed at the source until that is
found, and in the meantime the honest move is to MEASURE how far the templates
depart from the text.

## The test

A template is part slot and part literal: `declares of [X]` claims the corpus
says *declares* and *of*. Strip the slots, and every remaining word is a claim
that can be checked against the interlinear glosses of the verses the pattern
itself cites.

    literal word appears in the instance's glosses    -> attested
    literal word appears in none of them              -> inserted

`of` is the interesting case and the one caught first. Hebrew marks the genitive
by construct rather than by a word, so a template that renders it as *of* is
describing a RELATION in English rather than quoting the text. That is
defensible for `son of [X]`, which is how the phrase is read, and wrong for
`declares of [X]`, where the same construct is read *declares the LORD*.

## What this does not do

It does not rewrite the templates. The generator is missing, the fix belongs
there, and editing 12,494 derived strings by hand in the app would put a
correction somewhere it cannot be regenerated from.

    python tools/templateaudit.py
    python tools/templateaudit.py --word of --examples 12
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

SLOT = re.compile(r"\[[A-Z]\]")


def glosses():
    """-> {ref: {gloss words}} every English word MACULA puts on the verse."""
    out = {}
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if not d.get("ref"):
            continue
        ws = set()
        for w in d["words"]:
            for t in re.findall(r"[a-z]+", (w.get("g") or "").lower()):
                ws.add(t)
        out[d["ref"]] = ws
    return out


def patterns():
    for line in gzip.open(OUT / "patterns.jsonl.gz", "rt", encoding="utf-8"):
        d = json.loads(line)
        if not any(k.startswith("_") for k in d):
            yield d


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sample", type=int, default=12,
                    help="instances checked per template")
    ap.add_argument("--word", help="drill into one literal word")
    ap.add_argument("--examples", type=int, default=8)
    a = ap.parse_args()

    # TWO WITNESSES, AND THE SECOND IS THE ONE THAT MATTERS.
    #
    # The glosses alone cannot tell a harmless insertion from a wrong one.
    # Hebrew marks the genitive by construct, so NEITHER `word of [X]` nor
    # `declares of [X]` has an "of" in its glosses -- yet Gen 15:1 reads "the
    # word of the LORD", where "of" is exactly right, and Gen 22:16 reads
    # "declares the LORD", where it is not. The first
    # reference makes it obvious.
    #
    # So the BSB text is the second witness: a supplied word that the
    # translation also uses is a fair description of the phrase, and one the
    # translation does not use is the template inventing English.
    sys.path.insert(0, str(ROOT / "tools"))
    from bsbconvert import verses as bsb_verses
    bsb = bsb_verses("verses.bsb.jsonl")
    sys.path.insert(0, str(ROOT))
    from app2.server import MACULA_BACK

    def english(ref):
        try:
            mb, c, v = ref.split(".")
            b = MACULA_BACK.get(mb, mb)
            return set(re.findall(r"[a-z]+",
                                  (bsb.get((b, int(c), int(v))) or "").lower()))
        except ValueError:
            return set()

    gl = glosses()
    seen = collections.Counter()      # literal word -> templates using it
    hits = collections.Counter()      # ... attested in at least one instance
    rate = collections.defaultdict(list)
    worst = []

    for p in patterns():
        lits = [w for w in re.findall(r"[a-z]+",
                                      SLOT.sub(" ", p["template"]).lower())]
        if not lits:
            continue
        refs = [r for r in p.get("refs", [])[:a.sample] if r in gl]
        if not refs:
            continue
        bad = []
        for w in set(lits):
            seen[w] += 1
            n = sum(1 for r in refs if w in gl[r])
            rate[w].append(n / len(refs))
            if n:
                hits[w] += 1
            # UNSUPPORTED = absent from the glosses AND from the translation.
            # Absent from the glosses alone is ordinary: English needs words
            # Hebrew marks grammatically.
            elif not any(w in english(r) for r in refs):
                bad.append(w)
        if bad:
            worst.append((p["instances"], p["template"], sorted(bad),
                          refs[0]))

    if a.word:
        w = a.word
        print(f"“{w}” appears in {seen[w]} templates; attested in the glosses "
              f"of at least one cited instance in {hits[w]}\n")
        for inst, tmpl, bad, ref in sorted(worst, reverse=True):
            if w in bad:
                print(f"  {inst:>5}×  {tmpl:<30} first instance {ref}")
                if a.examples <= 0:
                    break
                a.examples -= 1
        return 0

    print(f"{sum(seen.values()):,} literal-word claims across the templates\n")
    print(f"  {'word':<14}{'templates':>10}{'attested':>10}{'mean rate':>11}")
    for w, n in seen.most_common(18):
        r = sum(rate[w]) / len(rate[w])
        print(f"  {w:<14}{n:>10}{hits[w]:>10}{r:>10.0%}")

    worst.sort(reverse=True)
    print(f"\n{len(worst):,} templates use a word found in NEITHER the glosses "
          f"NOR the Berean text of any instance they cite")
    print(f"  — these are the ones putting words in the text's mouth.\n")
    for inst, tmpl, bad, ref in worst[:20]:
        print(f"  {inst:>5}×  {tmpl:<32} supplies: {', '.join(bad):<14} "
              f"e.g. {ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
