"""Learn the taxonomy by mapping across the two graphs.

The idea: for the verbs, the combination of the literal
words used and the legacy relationships might build out the taxonomy by mapping
across graphs.

The two layers have opposite problems and they are each other's answer:

    the floor    16,113 edge types, because every verb becomes one.
                 Complete, canon-wide, and an OPEN vocabulary with no semantics.
    the overlay     113 curated types with reasoning in their notes.
                 Meant, checkable, and covering what a worker was pointed at.

Where both describe **the same two things in the same verse**, the pair is
evidence: *this surface verb was read as that relation, by someone, here.* Enough
such agreements and the surface verb has a curated type attached to it — learned
from the overlay rather than asserted by me, and then applicable to every verse
the overlay never reached.

That is what the earlier audit saw in passing and did not use: `fathered` sat
against `father_of` fifteen times, `took` against `took`, `gave` against `gave`.
This turns those co-occurrences into a table.

## What makes a mapping trustworthy

Three numbers per candidate, because any one of them alone lies:

- **support** -- how many verses agree. Two is a coincidence.
- **purity** -- of all the legacy types this verb co-occurs with, the share
  taken by the winner. A verb that maps to six relations equally maps to none.
- **reach** -- how many distinct books. A mapping seen nine times in one
  genealogy is one habit, not a rule.

## What this does NOT do

It does not relabel a single edge. The output is a proposal table to be
ruled on by hand, because **naming a relation is the overlay's act**: that
judgement is made by hand and recorded as a ruling. The floor keeps saying
`fathered`, and this says what the graph has historically meant by it.
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

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "verb-map.json"

STOPW = {
    "the", "a", "an", "of", "and", "to", "in", "on", "at", "by", "for", "with",
    "from", "his", "her", "their", "its", "this", "that", "these", "those",
    "is", "was", "were", "be", "he", "she", "it", "they", "them", "him", "who",
}
# Structural edge kinds carry no verb, so they cannot map onto a relation type.
STRUCTURAL = {
    "adjunct", "member", "references", "possessed_by", "apposition", "is",
    "to", "in", "from", "for", "on", "with", "at", "by", "as", "like",
    "justas", "of", "into", "than", "among", "before", "under", "upon",
    "after", "until", "through", "between", "about", "over", "against",
    "accordingto", "there", "when",
}
REF = re.compile(r"^\s*(\S+?)[\s.](\d+)[:.](\d+)\s*$")


def words(s):
    return set(re.findall(r"[a-z]+", (s or "").lower())) - STOPW


def norm_ref(r):
    m = REF.match(str(r))
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min-support", type=int, default=3)
    ap.add_argument("--min-purity", type=float, default=0.6)
    ap.add_argument("--show", type=int, default=30)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    ents = {}
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            ents[e["id"]] = e
    rels = []
    for f in sorted(glob.glob(str(ROOT / "ontology" / "relations" / "*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            if line.strip():
                rels.append(json.loads(line))

    nodes = collections.defaultdict(list)
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if not any(k.startswith("_") for k in d):
                nodes[d["ref"]].append(d)
    edges = collections.defaultdict(list)
    with gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            if not any(k.startswith("_") for k in e):
                edges[e["ref"]].append(e)

    wordix = {}
    for ref, ns in nodes.items():
        ix = collections.defaultdict(list)
        for n in ns:
            for w in words(n.get("text", "")):
                ix[w].append(n["id"])
        wordix[ref] = ix

    # (surface verb, legacy type) -> {verses, books}
    seen = collections.defaultdict(lambda: {"n": 0, "books": set(),
                                            "ex": []})
    for r in rels:
        s, d = ents.get(r["src"]), ents.get(r["dst"])
        if not (s and d):
            continue
        aw, bw = words(s.get("name", "")), words(d.get("name", ""))
        if not (aw and bw):
            continue
        for x in r.get("refs", []):
            ref = norm_ref(x)
            ix = wordix.get(ref)
            if not ix:
                continue
            a_ids = {i for w in aw for i in ix.get(w, [])}
            b_ids = {i for w in bw for i in ix.get(w, [])}
            if not (a_ids and b_ids) or a_ids == b_ids:
                continue
            for e in edges.get(ref, []):
                if e["type"] in STRUCTURAL:
                    continue
                fwd = e.get("src") in a_ids and e.get("dst") in b_ids
                rev = e.get("src") in b_ids and e.get("dst") in a_ids
                if not (fwd or rev):
                    continue
                k = (e["type"], r["type"], "->" if fwd else "<-")
                rec = seen[k]
                rec["n"] += 1
                rec["books"].add(ref.split(".")[0])
                if len(rec["ex"]) < 3:
                    rec["ex"].append(f"{ref} {s['name'][:16]}/{d['name'][:16]}")

    # purity: of everything this verb maps to, what share is the winner?
    per_verb = collections.defaultdict(int)
    for (verb, _, _), rec in seen.items():
        per_verb[verb] += rec["n"]

    rows = []
    for (verb, rel, direction), rec in seen.items():
        purity = rec["n"] / per_verb[verb]
        rows.append({"verb": verb, "relation": rel, "direction": direction,
                     "support": rec["n"], "purity": round(purity, 2),
                     "books": len(rec["books"]),
                     "examples": rec["ex"]})
    rows.sort(key=lambda r: (-r["support"], -r["purity"]))

    kept = [r for r in rows
            if r["support"] >= a.min_support and r["purity"] >= a.min_purity]
    print(f"co-occurring (verb, relation) pairs: {len(rows)}")
    print(f"surface verbs involved:              {len(per_verb)}")
    print(f"kept at support >= {a.min_support}, purity >= {a.min_purity}: "
          f"{len(kept)}\n")
    print(f"  {'surface verb':22} {'legacy relation':22} {'sup':>4} "
          f"{'pur':>5} {'bks':>4}")
    for r in kept[:a.show]:
        arrow = "" if r["direction"] == "->" else "  (reversed)"
        print(f"  {r['verb'][:20]:22} {r['relation'][:20]:22} "
              f"{r['support']:>4} {r['purity']:>5.2f} {r['books']:>4}{arrow}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    DEST.write_text(json.dumps({
        "_note": "Proposed surface-verb to relation-type mappings, learned by "
                 "co-occurrence across the two graphs. NOT applied to any edge; "
                 "naming a relation is a ruling, not a computation.",
        "min_support": a.min_support, "min_purity": a.min_purity,
        "mappings": kept,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(kept)} proposals)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
