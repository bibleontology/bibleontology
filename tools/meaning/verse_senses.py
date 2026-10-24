"""Which uses of a word belong on a card: the C-D13 judgments, merged.

A card's "where the text speaks of it" listed every use of its words, so a
word with another sense brought that sense too: the temple card had 1,830
verses of בַּיִת "house", the curse card the waters that "abated" (Gen 8:8,
קָלַל). The candidates are the card-word pairs where the card's own English
renders under half of the word's uses (796). A gloss filter alone cannot
tell a second sense from a synonym ("search" would have lost its "seek"
verses), so each pair was judged blind (2026-10-03: judge the pairs
with Haiku, escalating to Sonnet):

- Claude Haiku judged every pair: all uses are this card's sense, or only
  those rendered as the card's word, or unsure.
- Every Haiku verdict that would CHANGE a list (card_only, or unsure) went
  to Claude Sonnet, blind to Haiku's answer. Only Sonnet's card_only applies.
- What Sonnet left unsure stays as it was and is listed for review.

    python tools/meaning/verse_senses.py <judge dir>
        -> ontology/verse-senses.jsonl      (applied: card_only)
        -> docs/review/VERSE-SENSES.md      (counts, and the unsure for review)
"""
import collections
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READER = "Claude Haiku 4.5, then Claude Sonnet 5.5 blind where Haiku would change it, 2026-10-03"


def load(d, inp, out):
    """{pair: verdict row} for every input pair answered in its output file."""
    got = {}
    for b in sorted(glob.glob(str(Path(d) / inp))):
        nn = re.search(r"_(\d\d)\.json$", b).group(1)
        f = Path(d) / f"{out}{nn}.json"
        if not f.exists():
            continue
        ans = {x["pair"]: x for x in json.load(open(f, encoding="utf-8"))}
        for it in json.load(open(b, encoding="utf-8")):
            if it["pair"] in ans and ans[it["pair"]].get("verdict") in ("all", "card_only", "unsure"):
                got[it["pair"]] = {**it, **ans[it["pair"]]}
    return got


def main(d):
    pairs = {it["pair"]: it for b in sorted(glob.glob(str(Path(d) / "batch_*.json")))
             for it in json.load(open(b, encoding="utf-8"))}
    haiku = load(d, "batch_*.json", "A_")
    haiku.update(load(d, "redo_*.json", "RA_"))
    sonnet = load(d, "esc_*.json", "S_")
    applied, unsure, tally = [], [], collections.Counter()
    for p, it in pairs.items():
        h = (haiku.get(p) or {}).get("verdict")
        s = (sonnet.get(p) or {}).get("verdict")
        if h == "all" and s is None:
            tally["kept: Haiku all"] += 1
            continue
        if s is None:
            tally["unjudged"] += 1
            continue
        tally[f"Haiku {h or 'none'} / Sonnet {s}"] += 1
        card, key = p.split("|")
        if s == "card_only":
            applied.append({"card": card, "key": key, "word": it["word"], "verdict": "card_only",
                            "kept": it["n_as_card"], "of": it["word_uses"],
                            "reader": READER, "why": sonnet[p].get("why", "")})
        elif s == "unsure":
            unsure.append((it, sonnet[p].get("why", "")))
    if tally["unjudged"]:
        raise SystemExit(f"{tally['unjudged']} pairs have no verdict; nothing written")
    with open(ROOT / "ontology" / "verse-senses.jsonl", "w", encoding="utf-8") as f:
        for r in sorted(applied, key=lambda r: (r["card"], r["key"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    lines = ["# Verse senses -- which uses of a word belong on a card (C-D13)", "",
             "Made by `tools/meaning/verse_senses.py`. A card's verse list takes every use "
             "of its words; for the 796 card-word pairs where the card's own English renders "
             "under half of the word's uses, Claude Haiku judged whether the other uses are "
             "the same sense (synonyms) or another sense, and every verdict that would change "
             "a list went to Claude Sonnet, blind. Only Sonnet's \"card only\" applies "
             "(`ontology/verse-senses.jsonl`).", "",
             "| outcome | pairs |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(tally.items())]
    lines += ["", f"**Applied: {len(applied)}.** **Left as they are for Doug (Sonnet unsure): "
              f"{len(unsure)}.**", "",
              "| card | word | uses as the card's word | Sonnet's reason |", "|---|---|---|---|"]
    for it, why in sorted(unsure, key=lambda x: x[0]["pair"]):
        lines.append(f"| {it['card']} | {it['word']} | {it['n_as_card']} of {it['word_uses']} | "
                     f"{why.replace('|', '/')} |")
    (ROOT / "docs" / "review" / "VERSE-SENSES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(dict(tally), "| applied", len(applied), "| unsure", len(unsure))


if __name__ == "__main__":
    main(sys.argv[1])
