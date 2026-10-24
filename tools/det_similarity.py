"""Can deterministic signals reproduce the blind similarity scores?

Principle 36 says prove a task is not deterministic before giving it to a
model. Similarity scoring has never had that test. It has had four model
judges, measured 2026-09-02 against the owner's own blind sheet, and the best of
them -- DeepSeek -- sat 7.1 points from it on average and cost money per
pair. This asks what rules alone can do, for free, against the same twelve
answers.

## The signals, and why each is here

    overlap      Jaccard over content words of the two definitions. The
                 obvious signal, and on its own it is the trap: antonyms
                 describe the same subject, so valuable/useless scores high.

    polarity     negation asymmetry -- "not", "without", "-less", "un-" on one
                 side and not the other. This is what separates *opposite*
                 from *unrelated*, which is the fold in the 0/50/100 scale
                 that Sonnet and Haiku could not read. A deterministic rule
                 does not have to "read the fold": it computes each axis
                 separately and composes them, which is the two-question
                 design that was proposed and never built.

    lxx          the Septuagint note in the lexicon entry, naming the Hebrew
                 a Greek word chiefly renders. Attested equivalence from the
                 third century BC, covering 39% of Greek entries. Strong where
                 present and silent elsewhere.

    cooccur      whether the two lemmas appear in the same verses. Weak
                 evidence of relatedness, and near-worthless alone, but free.

## What would count as success

Not beating DeepSeek. **Matching it would be the result**, because the rules
cost nothing and can run over all 16,465 lemmas in seconds where a model
cannot. If the rules land near 7.1 mean error, the model tier is unnecessary
for the bulk and should be reserved for the disputed remainder.

If they land far worse, that is also worth knowing, and it is the falsifier
for applying Principle 36 here.
"""
import json
import pathlib
import re
import statistics
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from blind_pairs import lexicon                                  # noqa: E402
from bibleont.lemmas import load_tagged                          # noqa: E402

STEP = ROOT / "data" / "raw" / "stepbible"

# The blind sheet, 0-100. The two grain pairs are absent: they were withdrawn
# as outside the scorer's expertise, and pair 5 was ambiguous on the sheet.
DOUG = {1: 100, 2: 0, 3: 75, 4: 100, 6: 50, 8: 75, 10: 50,
        11: 50, 12: 100, 13: 75, 14: 50, 15: 75}

STOP = {"the", "of", "a", "an", "and", "to", "in", "with", "for", "or", "be",
        "is", "was", "that", "it", "as", "by", "on", "at", "from", "one",
        "see", "also", "cf", "id", "so", "his", "her", "him", "they", "them",
        "who", "which", "not", "no", "before", "accusative", "dative",
        "genitive", "absol", "pass", "mid", "act", "intrans", "trans", "pr",
        "pf", "aor", "impf", "subst", "adj", "adv", "qal", "niphal", "hiphil",
        "hophal", "piel", "pual", "hithpael", "twot", "lxx"}

NEG = re.compile(r"\b(?:not|non|un\w+|without|lack\w*|fail\w*|worthless|"
                 r"useless|unprofitable|barren|empty|void|refus\w*|deny|"
                 r"denies|reject\w*|oppos\w*|contrary|against)\b", re.I)


def words(t: str) -> set:
    return {w for w in re.findall(r"[a-z]{3,}", (t or "").lower())} - STOP


def lxx_map() -> dict:
    """Greek lemma -> the Hebrew it chiefly renders, from the lexicon note."""
    out = {}
    for f in STEP.glob("TBESG*.txt"):
        for line in f.open(encoding="utf-8", errors="replace"):
            c = line.split("\t")
            if len(c) > 7 and re.match(r"^G\d{4}[A-Z]?$", c[0].strip()):
                m = re.search(r"\[in LXX[^\]]*\]", c[7])
                if m:
                    out[c[0].strip()] = m.group(0)
    return out


def score(a: str, b: str, lex: dict, lxx: dict, tagged: dict) -> tuple:
    """0-100 on the sheet's scale, plus the signals that produced it."""
    da, db = lex.get(a, ""), lex.get(b, "")
    wa, wb = words(da), words(db)
    inter, union = wa & wb, wa | wb
    overlap = len(inter) / max(len(union), 1)

    # Polarity: negation on one side and not the other. Computed on the words
    # each definition does NOT share, so "not" appearing in both cancels.
    na = len(NEG.findall(" ".join(wa - wb)))
    nb = len(NEG.findall(" ".join(wb - wa)))
    polar = abs(na - nb) / max(na + nb, 1) if (na or nb) else 0.0
    opposed = (na > 0) != (nb > 0)

    # LXX: does either entry's note name the other lemma?
    att = False
    for g, h in ((a, b), (b, a)):
        note = lxx.get(g)
        if note and h.lstrip("H").lstrip("0")[:4] and h.startswith("H"):
            att = att or (h[:5] in note or h in note)

    # Co-occurrence in the same verses.
    va = {r for r, ws in tagged.items() if any(w.lemma == a for w in ws)}
    vb = {r for r, ws in tagged.items() if any(w.lemma == b for w in ws)}
    co = len(va & vb) / max(min(len(va), len(vb)), 1) if va and vb else 0.0

    # Compose. Two axes kept separate, then folded onto the sheet's scale at the
    # end -- which is the design Sonnet and Haiku could not hold in one
    # question and a rule holds trivially.
    sim = 100 * min(1.0, overlap * 2.2 + co * 0.15)
    if att:
        sim = max(sim, 80)
    if opposed and overlap > 0.10:
        # Same subject, opposite polarity: that is contrast, not similarity.
        val = round(max(0, 25 - polar * 25))
    else:
        val = round(50 + sim / 2)          # 50 is unrelated, 100 is identical
    return val, dict(overlap=round(overlap, 3), co=round(co, 3),
                     opposed=opposed, lxx=att)


def main() -> int:
    key = json.loads((ROOT / "out" / "blind-pairs-key.json").read_text(
        encoding="utf-8"))
    lex, lxx, tagged = lexicon(), lxx_map(), load_tagged()
    print(f"lexicon {len(lex):,} entries, {len(lxx):,} carry an LXX note\n")

    ds = json.loads((ROOT / "out" / "blind-model-scores.json").read_text(
        encoding="utf-8"))["models"]

    def got(n, p):
        return ds[n].get(str(p), ds[n].get(p))

    print(f"{'p':4}{'doug':>5}{'rules':>7}{'dpsk':>6}{'opus':>6}   signals")
    errs, derr, oerr = [], [], []
    for k in key:
        p = k["pair"]
        if p not in DOUG:
            continue
        val, sig = score(k["a"], k["b"], lex, lxx, tagged)
        errs.append(abs(val - DOUG[p]))
        if got("deepseek", p) is not None:
            derr.append(abs(got("deepseek", p) - DOUG[p]))
        if got("opus", p) is not None:
            oerr.append(abs(got("opus", p) - DOUG[p]))
        print(f"{p:<4}{DOUG[p]:>5}{val:>7}{str(got('deepseek', p)):>6}"
              f"{str(got('opus', p)):>6}   {sig}")

    print(f"\n{'judge':12}{'mean err':>10}{'cost':>12}{'speed':>14}")
    print(f"{'rules':12}{statistics.mean(errs):>10.1f}{'free':>12}"
          f"{'all pairs/sec':>14}")
    print(f"{'deepseek':12}{statistics.mean(derr):>10.1f}{'metered':>12}"
          f"{'~3s/pair':>14}")
    print(f"{'opus':12}{statistics.mean(oerr):>10.1f}{'metered':>12}"
          f"{'~2s/pair':>14}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
