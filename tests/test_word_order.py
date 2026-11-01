"""The original prints in the verse's order, not the syntax tree's (FAULTS #51, 2026-10-30).

MACULA's XML is a syntax tree, and the tree lifts a postpositive (γάρ, δέ, οὖν) to the head of its clause. The strip
was built by walking the tree, so John 3:16 printed "γὰρ Οὕτως" where the text reads "Οὕτως γὰρ": 4,408 of 7,943 Greek
verses and 781 of 23,213 Hebrew verses came out of order, and every view of the original showed it. tools/interlinear.py
now stores each word's own place in the verse (`w`, from its `ref` "JHN 3:16!2") and sorts on it. This reads the built
file out/interlinear.jsonl.gz, in seconds and without the server, and checks:
  (a) John 3:16 begins Οὕτως γὰρ;
  (b) Genesis 1:1 begins with the two parts of בְּרֵאשִׁית (בְּ and רֵאשִׁית), which share one word number;
  (c) every verse's words are in nondecreasing `w`, and none has a missing or zero `w`;
  planted faults it must catch: a reversed John 3:16, a Hebrew verse with its first word's parts swapped, a shuffled
  verse, a verse with a word that has no number.
Run: python tests/test_word_order.py"""
import gzip
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V = {}
with gzip.open(ROOT / "out" / "interlinear.jsonl.gz", "rt", encoding="utf-8") as fh:
    for line in fh:
        d = json.loads(line)
        if d.get("ref"):
            V[d["ref"]] = d["words"]


def check(verses):
    """Every fault in a dict of {ref: words}, as readable strings."""
    bad = []
    j = verses.get("Jhn.3.16")
    if not j or [w.get("t") for w in j[:2]] != ["Οὕτως", "γὰρ"]:
        bad.append(f"John 3:16 begins {[w.get('t') for w in (j or [])[:2]]}, not Οὕτως γὰρ")
    g = verses.get("Gen.1.1")
    if (not g or len(g) < 3 or not (g[0].get("t") or "").startswith("ב") or not (g[1].get("t") or "").startswith("ר")
            or g[0].get("w") != 1 or g[1].get("w") != 1 or g[2].get("w") != 2):
        bad.append("Genesis 1:1 does not begin with the two parts of בְּרֵאשִׁית sharing one word number")
    for ref, ws in verses.items():
        ns = [w.get("w") for w in ws]
        if any(not isinstance(n, int) or n < 1 for n in ns):
            bad.append(f"{ref}: a word with no number")
        elif ns != sorted(ns):
            bad.append(f"{ref}: words out of the verse's order {ns[:8]}")
    return bad


fails = check(V)
n_verses, n_words = len(V), sum(len(ws) for ws in V.values())
n_multi = sum(1 for ws in V.values() if len({w["w"] for w in ws}) < len(ws))

# ---- planted faults, each on a copy: every one must be caught
rng = random.Random(51)


def plant(name, ref, mutate):
    v = {k: [dict(w) for w in ws] for k, ws in V.items() if k in ("Jhn.3.16", "Gen.1.1", "Gen.1.2", "Jhn.1.1")}
    mutate(v[ref])
    return name, bool(check(v))


def reverse(ws):
    ws.reverse()


def swap_parts(ws):          # Genesis 1:1's two parts of one word, in the wrong order
    ws[0], ws[1] = ws[1], ws[0]


def shuffle(ws):
    while True:
        rng.shuffle(ws)
        if [w["w"] for w in ws] != sorted(w["w"] for w in ws):
            return


def unnumber(ws):
    ws[2]["w"] = 0


def tree_order(ws):          # the fault itself: the tree's order, γάρ ahead of Οὕτως
    ws[0], ws[1] = ws[1], ws[0]


planted = [plant("a reversed John 3:16", "Jhn.3.16", reverse),
           plant("a Hebrew verse with its parts swapped (Genesis 1:1)", "Gen.1.1", swap_parts),
           plant("a shuffled verse (Genesis 1:2)", "Gen.1.2", shuffle),
           plant("a word with no number (John 1:1)", "Jhn.1.1", unnumber),
           plant("the tree's order, γὰρ before Οὕτως", "Jhn.3.16", tree_order)]
caught = sum(1 for _n, c in planted if c)
for n, c in planted:
    if not c:
        fails.append(f"planted fault not caught: {n}")

print(f"{n_verses:,} verses, {n_words:,} words ({n_multi:,} verses with a word in several parts); "
      f"{caught} of {len(planted)} planted faults caught; {len(fails)} failures")
for f in fails[:12]:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
