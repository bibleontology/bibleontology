"""Hebrew says "is" without saying it, and the layer was hearing nothing.

Found while testing *"God is my rock"*: **Psalm 18:2 produces no `is`
edge at all.** Every node is there and correct -- `LORD`, `rock`, `fortress`,
`deliverer`, `God`, `shield` -- but Hebrew states predication in a **verbless
clause**, with no copula for a verb-driven parser to catch. What came out
instead was `member` and `possessed_by`: the layer saw the list, and the
possession, and not the claim.

So the canonical example of the whole figurative-language question was
structurally unreachable, while its Greek equivalent -- *I am the vine*, which
has εἰμί -- was found.

MACULA marks these clauses, so this is a join rather than an inference:

    clauses                                        132,981
      verbless                                      53,871   41%
      verbless AND carrying a subject and predicate 11,667

**41% of the corpus's clauses have no verb**, which is a fact about Hebrew
rather than a defect, and 11,667 of them state a predication that nothing
downstream could previously see.

## What is emitted

One `is` edge per verbless clause that has both roles, from the subject's head
to the predicate's head. The type is `is` -- the same type a Greek copular
clause already produces -- so nothing downstream needs to know which language
stated it, and `tools/selectional.py` picks these up for free.

## Where it stops

A verbless clause with only a predicate (2,673 of them) has nothing to attach
to, and one whose head cannot be resolved to a node is skipped rather than
guessed at. Both are counted rather than hidden.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
CLAUSES = ROOT / "data" / "macula-clauses.jsonl.gz"
DEST = OUT / "verbless-edges.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

# Not the head of its constituent. Same list the selectional work needed, and
# for the same reason: taking the first lemma gives "the" as the subject.
NOT_HEAD = {"הַ", "ὁ", "וְ", "אֵת", "כִּי", "אֲשֶׁר", "כָּל", "כֹּל",
            "אֶת", "לְ", "בְּ", "מִן", "עַל", "καί", "δέ", "ὅς"}


def head_lemma(part: dict) -> str | None:
    for lem in part.get("lemmas") or []:
        if lem and lem not in NOT_HEAD:
            return lem
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--show", type=int, default=14)
    a = ap.parse_args()

    # nodes, indexed by verse then lemma
    byverse = collections.defaultdict(dict)
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            if d.get("lemma"):
                byverse[d["ref"]].setdefault(d["lemma"], d)

    total = verbless = withsp = made = 0
    no_subject = unresolved = 0
    edges, examples = [], []
    with gzip.open(CLAUSES, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            total += 1
            if not d.get("verbless"):
                continue
            verbless += 1
            parts = d.get("parts", [])
            s = next((p for p in parts if p.get("role") == "s"), None)
            p_ = next((p for p in parts if p.get("role") == "p"), None)
            if not (s and p_):
                if p_ and not s:
                    no_subject += 1
                continue
            withsp += 1
            sl, pl = head_lemma(s), head_lemma(p_)
            ref = d["ref"]
            sn = byverse.get(ref, {}).get(sl or "")
            pn = byverse.get(ref, {}).get(pl or "")
            if not (sn and pn) or sn["id"] == pn["id"]:
                unresolved += 1
                continue
            made += 1
            edges.append({"ref": ref, "type": "is", "src": sn["id"],
                          "dst": pn["id"], "verbless": True})
            if len(examples) < a.show:
                examples.append((ref, sn.get("text"), pn.get("text"),
                                 s.get("gloss"), p_.get("gloss")))

    print(f"clauses                          {total}")
    print(f"  verbless                       {verbless}  ({100*verbless/total:.0f}%)")
    print(f"  with a subject and predicate   {withsp}")
    print(f"    both heads resolve to nodes  {made}")
    print(f"    a head did not resolve       {unresolved}")
    print(f"  predicate but no subject       {no_subject}   (nothing to attach to)")

    print(f"\n  {'verse':13} {'subject':18} {'is':18} clause")
    for ref, st, pt, sg, pg in examples:
        print(f"  {ref:13} {str(st)[:16]:18} {str(pt)[:16]:18} "
              f"{str(sg)[:20]} / {str(pg)[:22]}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0

    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": CREDIT,
            "_note": "Predication stated by a verbless clause. Hebrew says "
                     "'X is Y' with no copula, so a verb-driven pass emits "
                     "nothing; MACULA marks the clause and these are its "
                     "subject-to-predicate edges.",
        }, ensure_ascii=False) + "\n")
        for e in edges:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(edges)} edges)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
