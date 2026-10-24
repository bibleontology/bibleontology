"""Repetition at marked moments: a motif, measured — its meaning left open.

2026-09-28: the repetition idea has something to it, but it will be captured
a different way. Biblical authors rely heavily on repetition to make a point.
A Copilot thread offered ten such things (water, mountains,
bread, light, shepherds, doors, wilderness, storms, stones, trees) as
"symbolism strongly implied but never explicitly stated".

What the TEXT shows, and the graph can record, is not the symbolism: it is
that an ordinary thing RECURS, and recurs where something marked happens.
So a motif is measured, not read:

    lift = P(a verse is a divine encounter | the word is in it)
           / P(a verse is a divine encounter)

where a DIVINE ENCOUNTER verse is one whose structure has God (יְהוָה,
אֱלֹהִים) as the subject of a verb of speaking or appearing — marked by the
text's own form, from the structure graph. A lift well above 1 says the
thing gathers at those moments; it does not say what it means. Two
ordinary words (silver, cubit) are the controls.

    python tools/meaning/motifs.py
"""
import collections
import gzip
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT / "tools" / "builder"))
from source import norm  # noqa: E402

GOD = {"יהוה", "אלהים"}
ENCOUNTER = {"אמר", "דבר", "ראה", "ירד", "קרא", "צוה"}
MOTIFS = {
    "water": {"מים"}, "mountain": {"הר"}, "bread": {"לחם"},
    "light": {"אור"}, "shepherd / flock": {"רעה", "צאן"},
    "door / gate": {"דלת", "שער", "פתח"}, "wilderness": {"מדבר"},
    "storm / whirlwind": {"סערה", "סער"}, "stone": {"אבן"},
    "tree": {"עץ"}, "fire": {"אש"}, "cloud": {"ענן"},
    # controls: ordinary things
    "silver (control)": {"כסף"}, "cubit (control)": {"אמה"},
}


def main():
    words = collections.defaultdict(set)      # verse -> normalised lemmas
    clause_verb = {}
    for line in gzip.open(OUT / "structure-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        n = json.loads(line)
        if n.get("lang") != "hebrew":
            continue
        if n.get("word") and n.get("lemma"):
            words[n["ref"]].add(norm(n["lemma"]))
        elif n.get("clause"):
            clause_verb[n["id"]] = norm(n.get("verb_lemma") or "")
    nodes_lemma = {}
    for line in gzip.open(OUT / "structure-nodes.jsonl.gz", "rt",
                          encoding="utf-8"):
        n = json.loads(line)
        if n.get("lang") == "hebrew" and n.get("word"):
            nodes_lemma[n["id"]] = norm(n.get("lemma") or "")
    refers = {}
    encounter = set()
    edges = [json.loads(l) for l in gzip.open(
        OUT / "structure-edges.jsonl.gz", "rt", encoding="utf-8")]
    for e in edges:
        if e["type"] == "refers_to":
            refers[e["src"]] = e["dst"]
    for e in edges:
        if e.get("lang") != "hebrew" or e["type"] != "s":
            continue
        subj = refers.get(e["dst"], e["dst"])
        if nodes_lemma.get(subj) in GOD and \
                clause_verb.get(e["src"].replace("#ct", "#cl")) in ENCOUNTER:
            encounter.add(e["ref"])
    verses = set(words)
    base = len(encounter) / len(verses)
    print(f"{len(verses):,} Hebrew verses; {len(encounter):,} where God "
          f"speaks or appears ({base:.1%})\n")
    print(f"{'motif':22} {'verses':>7} {'at encounters':>14} {'lift':>6}"
          f"  {'95% range':>12}")
    for name, lemmas in MOTIFS.items():
        vs = {v for v in verses if words[v] & lemmas}
        k = len(vs & encounter)
        p = k / len(vs) if vs else 0
        # a rough interval for the proportion (Wilson), carried into lift
        n = len(vs)
        z = 1.96
        if n:
            c = (p + z * z / (2 * n)) / (1 + z * z / n)
            h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / \
                (1 + z * z / n)
            lo, hi = (c - h) / base, (c + h) / base
        else:
            lo = hi = 0
        print(f"{name:22} {n:>7,} {k:>14,} {p / base if base else 0:>6.2f}"
              f"  {lo:5.2f}–{hi:<5.2f}")


if __name__ == "__main__":
    main()
