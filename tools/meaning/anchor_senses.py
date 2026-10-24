"""Merge blind passes of judged anchor senses (2026-09-30).

A card's anchors are the Hebrew and Greek words its English name renders,
and an English name can render two words that mean different things: "cross"
renders σταυρός and עָבַר "cross over". tools/meaning/concept_anchors.py
lists every card with two anchors of different roots in one language
(out/anchor-candidates.json). Sonnet 5.5 was to judge them. Two passes judged every anchor, blind to
each other and to any expected answer: keep, drop or unsure.

A drop BOTH passes give is applied -- written to
ontology/anchor-senses.jsonl, which concept_anchors.py reads. Where they
differed, or either was unsure, a THIRD blind pass judged that anchor alone
(a third pass breaks the ties): two drops of three apply it,
two keeps of three keep it. What three passes leave unsettled (a three-way
split, or a third pass that is itself unsure) goes to
docs/review/ANCHOR-SENSES.md for a ruling, and the anchor stays until it is made.

    python tools/meaning/anchor_senses.py <A dir: batch_NN + A_NN> <B dir: B_NN> [<T dir: T_NN>]
"""
import collections
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READER = "Claude Sonnet 5.5, two blind passes, 2026-09-30"
READER3 = "Claude Sonnet 5.5, two of three blind passes, 2026-09-30"
READER_T = ("Claude Sonnet 5.5, third blind pass on a three-way split; adopted by Doug "
            "after checking about 10 (2026-09-30)")
READER_U = ("unsettled after three blind passes (Claude Sonnet 5.5); dropped by Doug: "
            "'less is probably more' (2026-09-30)")
# Drops that a check against the text found wrong (Claude Opus 5.5, reading a
# sample of 25 agreed drops: 23 right, 1 debatable, 1 wrong)
OVERRULE = {
    ("kiss", "kiss", "g5368"):
        "φιλέω is the kiss itself: 'The One I kiss is the man' (Matt 26:48, Mark "
        "14:44, MACULA 'i shall kiss'); Luke 22:47 'to kiss'",
    # a two-of-three drop, read against the text in a sample of 25
    ("perfect", "blameless", "h8552"):
        "תָּמַם is the blameless one's verb: 'with the blameless You show Yourself "
        "blameless' (2 Sam 22:26, Ps 18:25), 'then I will be blameless' (Ps 19:13), "
        "Job 22:3 -- MACULA 'blameless' in each",
}


def load(d, p):
    """Only <p>_NN.json. A loose glob once read a set-aside file
    (B_03.misaligned.json) after the fresh B_03.json and let it win."""
    out = {}
    for f in sorted(glob.glob(str(Path(d) / f"{p}_*.json"))):
        if not re.fullmatch(rf"{p}_\d\d\.json", Path(f).name):
            continue
        for x in json.load(open(f, encoding="utf-8")):
            out[(x["card"], x["word"])] = x
    return out


def main(da, db, dt=None):
    # what was judged: the batches in pass A's folder, not today's candidate
    # file, which shrinks once the agreed drops are applied
    cand = {(x["card"], x["word"]): x
            for f in sorted(glob.glob(str(Path(da) / "batch_*.json")))
            for x in json.load(open(f, encoding="utf-8"))}
    A, B = load(da, "A"), load(db, "B")
    T = load(dt, "T") if dt else {}
    missing = [k for k in cand if k not in A or k not in B]
    if missing:
        raise SystemExit(f"{len(missing)} cards lack a verdict in one pass: {missing[:5]}")
    agreed, unsettled = [], []
    tally, third = collections.Counter(), collections.Counter()
    for k, c in cand.items():
        a, b = A[k]["verdicts"], B[k]["verdicts"]
        an = {x["key"]: x for x in c["anchors"]}
        for key in an:
            va, vb = a.get(key), b.get(key)
            if va is None or vb is None:
                raise SystemExit(f"{k} {key}: no verdict in one pass")
            tally[(va, vb)] += 1
            row = {"card": k[0], "word": k[1], "key": key, "lemma": an[key]["lemma"],
                   "glosses": an[key]["glosses"][:3], "share": an[key]["share"]}
            if va == vb == "drop":
                verdict, reader = "drop", READER
                why = A[k].get("why") or B[k].get("why") or ""
            elif va == vb == "keep":
                continue
            else:
                vt = (T.get(k) or {}).get("verdicts", {}).get(key) if T else None
                if dt and vt is None:
                    raise SystemExit(f"{k} {key}: disputed, and no third verdict")
                votes = collections.Counter([va, vb, vt])
                third[vt] += 1
                if votes["drop"] >= 2:
                    verdict, reader = "drop", READER3
                    why = (T[k].get("why") or "") if T else ""
                elif votes["keep"] >= 2:
                    third["kept"] += 1
                    continue
                # A THREE-WAY SPLIT: THE THIRD DECIDES. 2026-09-30, on the
                # 79 left for review: about 10 were checked by hand and the
                # third pass agreed every time; its reasoning is solid and its
                # reading of the original language is better than a blind
                # judgment. Only where it gave a verdict: its own
                # "unsure" stays for review
                elif vt == "drop":
                    verdict, reader = "drop", READER_T
                    why = T[k].get("why") or ""
                elif vt == "keep":
                    third["kept_by_third"] += 1
                    continue
                # the third was unsure too. 2026-09-30: the unsure ones were
                # checked by hand and were unsure there too, but less is
                # probably more, so those are dropped as well
                elif vt == "unsure":
                    verdict, reader = "drop", READER_U
                    why = T[k].get("why") or ""
                else:
                    unsettled.append({**row, "a": va, "b": vb, "t": vt, "name": c["name"],
                                      "why_a": A[k].get("why") or "",
                                      "why_b": B[k].get("why") or "",
                                      "why_t": (T.get(k) or {}).get("why") or ""})
                    continue
            if (k[0], k[1], key) in OVERRULE:
                tally["overruled"] += 1
                continue
            agreed.append({**row, "verdict": verdict, "reader": reader, "why": why})
    # VERDICTS FROM OTHER PASSES ARE KEPT: the file also holds the judgments
    # of cards re-anchored after a rename (2026-10-03, Haiku then Sonnet),
    # whose judging folders this run never reads; rewriting from this run's
    # folders alone would silently drop them
    p = ROOT / "ontology" / "anchor-senses.jsonl"
    ours = {READER, READER3, READER_T, READER_U}
    others = [json.loads(ln) for ln in open(p, encoding="utf-8")
              if ln.strip() and json.loads(ln).get("reader") not in ours] if p.exists() else []
    mine = {(r["card"], r["word"], r["key"]) for r in agreed}
    kept = agreed + [r for r in others if (r["card"], r["word"], r["key"]) not in mine]
    with open(p, "w", encoding="utf-8") as f:
        for r in sorted(kept, key=lambda r: (r["card"], r["word"], r["key"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    overruled = tally.pop("overruled", 0)
    n = sum(tally.values())
    agree = sum(v for (x, y), v in tally.items() if x == y and x != "unsure")
    two = sum(1 for r in agreed if r["reader"] == READER)
    by3 = len(agreed) - two
    lines = ["# Anchor senses -- what three judges left for Doug", "",
             "Made by `tools/meaning/anchor_senses.py`. Every card whose English name "
             "anchors it to two words of different roots in one language: does each word "
             "carry what the card names? Judged twice, blind; where the two differed, a "
             "third blind pass judged that word alone. Two drops of three take the word "
             "off the card (ontology/anchor-senses.jsonl), two keeps of three keep it. "
             "**Below: what three passes left unsettled; each word stays until Doug "
             "rules.**", "",
             f"{len(cand):,} cards, {n:,} anchors. The first two passes agreed on "
             f"{agree:,} ({agree / n:.0%}). Taken off: {two:,} by both, {by3:,} by two "
             f"of three; {overruled} overruled on the text (below). Unsettled: "
             f"{len(unsettled):,}.", ""]
    lines += [f"- Overruled, kept: `{c}` {k} -- {why}" for (c, _w, k), why in OVERRULE.items()]
    lines += ["", "| card | word | anchor | A | B | third | the third's reason |",
              "|---|---|---|---|---|---|---|"]
    for r in sorted(unsettled, key=lambda r: (r["card"], r["key"])):
        lines.append(f"| {r['name']} | {r['word']} | {r['key']} {r['lemma']} "
                     f"({', '.join(r['glosses'])}; {int(r['share'] * 100)}%) | {r['a']} | "
                     f"{r['b']} | {r['t']} | {r['why_t'].replace('|', '/')} |")
    # the majority drops, listed too: they are the hard cases, and a reading of
    # 25 against the text found 17 clearly right, 7 debatable, 1 likely wrong
    # (תָּמַם off "blameless", Ps 19:13) -- each is here to be restored
    lines += ["", "## Taken off by two of three", "",
              "Applied, but these were the hard cases: of 25 read against the text, 17 "
              "were clearly right, 7 debatable, 1 likely wrong. Each can be restored.", "",
              "| card | word | anchor | the third's reason |", "|---|---|---|---|"]
    for r in sorted((r for r in agreed if r["reader"] == READER3),
                    key=lambda r: (r["card"], r["key"])):
        lines.append(f"| {r['card']} | {r['word']} | {r['key']} {r['lemma']} "
                     f"({', '.join(r['glosses'])}; {int(r['share'] * 100)}%) | "
                     f"{str(r['why']).replace('|', '/')} |")
    (ROOT / "docs" / "review" / "ANCHOR-SENSES.md").write_text("\n".join(lines) + "\n",
                                                              encoding="utf-8")
    print(f"{len(cand)} cards, {n} anchors; first two agreed {agree} ({agree / n:.0%}); "
          f"off by both {two}, by two of three {by3}; unsettled {len(unsettled)}; "
          f"third pass {dict(third)}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
