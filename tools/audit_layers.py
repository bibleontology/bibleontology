"""Old against new, within a sentence. What did the legacy graph reach that the
MACULA pipeline does not?

The brief: before the graph is built up, one more complete intra-sentence
comparison of old to new. Audit everything at that level and determine where the
old has gone farther than the new or made substantially different judgements
than the new. Where the new is farther along than the old is not a concern,
since the approach is now much more thorough and that is progress.

So this is deliberately one-directional. Everything the parser reads that the
workers never did -- 613,673 words with morphology, 31,224 sentences, clause
roles -- is progress and is not counted here. **The question is only what would
be LOST if the legacy graph were retired**, and where the two disagree about the
same words in the same verse.

## How the two are joined

They have no shared identifiers, so the join is Strong's numbers. A legacy
entity carries `attrs.lemma` (a Strong's code); a parser node carries `strong`.
Where a legacy relation cites a verse and both of its endpoints have a lemma,
the same two words can be located in the parser's output for that verse and the
two accounts compared directly.

That join only reaches the legacy entities that have a lemma at all, which is
the audit's main limitation and is reported rather than hidden.

## The three questions, and why they are separate

1. **Expressible?** Could the parser produce this KIND of claim at all? A verb
   between two nouns, yes. An evaluation, a symbol, a condition -- no vocabulary
   for it exists. This is a property of the type, not of any verse.
2. **Present?** For the verses a legacy relation actually cites, did the parser
   emit anything connecting the same two words?
3. **Agreed?** Where both spoke, do they say the same thing?

A type can be expressible in principle and absent in practice, which is a
different problem from one the parser can never reach, and conflating them would
hide the second behind the first.
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

# The parser emits syntax: roles, prepositions, and the verb itself as an edge.
# These are the kinds of claim that a syntactic reading CAN in principle reach.
STRUCTURAL = {
    "member", "apposition", "possessed_by", "adjunct", "references", "is",
}

# Matching an entity name to the parser's surface text has to run on contentful
# words: "the LORD" and "the ark" both contain "the", and joining on that would
# link every pair in the verse to every other.
STOPW = {
    "the", "a", "an", "of", "and", "to", "in", "on", "at", "by", "for", "with",
    "from", "his", "her", "their", "its", "this", "that", "these", "those",
    "is", "was", "were", "be", "he", "she", "it", "they", "them", "him",
}


def norm_ref(r: str) -> str:
    """`Gen 1:1` and `Gen.1.1` are the same verse, written by different tools."""
    m = re.match(r"^\s*(\S+?)[\s.](\d+)[:.](\d+)\s*$", str(r))
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else ""


def strong_key(code: str) -> str:
    """`H0430` -> `h430`. Trailing homograph letters dropped; MACULA has none."""
    if not code or code[0] not in "GgHh":
        return ""
    d = re.match(r"0*(\d+)", str(code)[1:])
    return f"{code[0].lower()}{d.group(1)}" if d else ""


def load_legacy():
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
    return ents, rels


def load_parser():
    nodes = collections.defaultdict(list)          # ref -> [node]
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            nodes[d["ref"]].append(d)
    edges = collections.defaultdict(list)          # ref -> [edge]
    with gzip.open(OUT / "placeholder-edges.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            edges[d["ref"]].append(d)
    return nodes, edges


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--show", type=int, default=12, help="examples per section")
    a = ap.parse_args()

    ents, rels = load_legacy()
    nodes, edges = load_parser()
    print(f"legacy   {len(ents)} entities, {len(rels)} relations")
    print(f"parser   {sum(len(v) for v in nodes.values())} nodes, "
          f"{sum(len(v) for v in edges.values())} edges, "
          f"{len(nodes)} verses\n")

    lemma_of = {k: strong_key((e.get("attrs") or {}).get("lemma", ""))
                for k, e in ents.items()}
    have_lemma = sum(1 for v in lemma_of.values() if v)
    print(f"legacy entities carrying a Strong's lemma: {have_lemma} of {len(ents)}"
          f"  ({100*have_lemma/len(ents):.0f}%)")
    print("  -- too sparse to join on, so the join below is by NAME against the\n"
          "     parser's English surface text in the same verse, which is how the\n"
          "     app already aligns the two layers.\n")

    # ---- 1. can the parser express this KIND of claim at all? -------------
    by_type = collections.Counter()
    joinable = collections.Counter()
    present = collections.Counter()
    agreed = collections.Counter()
    misses = collections.Counter()
    notlexical = collections.Counter()
    noref = collections.Counter()
    disagreements = []
    missed = []

    def words(s):
        return set(re.findall(r"[a-z]+", (s or "").lower())) - STOPW

    # verse -> {content word: [node ids]}, from the parser's English surface
    wordix = {}
    for ref, ns in nodes.items():
        ix = collections.defaultdict(list)
        for n in ns:
            for w in words(n.get("text", "")):
                ix[w].append(n["id"])
        wordix[ref] = ix

    for r in rels:
        t = r["type"]
        by_type[t] += 1
        a_e, b_e = ents.get(r["src"]), ents.get(r["dst"])
        if not (a_e and b_e):
            continue
        aw, bw = words(a_e.get("name", "")), words(b_e.get("name", ""))
        if not (aw and bw):
            continue
        refs = [norm_ref(x) for x in r.get("refs", [])]
        refs = [x for x in refs if x in wordix]
        if not refs:
            continue
        found = None
        joined_here = False
        for ref in refs:
            ix = wordix[ref]
            a_ids = {i for w in aw for i in ix.get(w, [])}
            b_ids = {i for w in bw for i in ix.get(w, [])}
            if not (a_ids and b_ids) or a_ids == b_ids:
                continue
            joined_here = True
            for e in edges.get(ref, []):
                if ((e["src"] in a_ids and e["dst"] in b_ids)
                        or (e["src"] in b_ids and e["dst"] in a_ids)):
                    found = (ref, e["type"])
                    break
            if found:
                break
        if joined_here:
            joinable[t] += 1
        if found:
            present[t] += 1
            if len(disagreements) < 4000:
                disagreements.append((t, found[1], found[0], r["src"], r["dst"]))
        elif joined_here:
            misses[t] += 1
            if len(missed) < 4000:
                missed.append((t, refs[0], r["src"], r["dst"], r.get("note")))
        elif refs:
            # the verse is parsed and cited, but the two things the relation
            # connects are not both surface words in it
            notlexical[t] += 1
        else:
            noref[t] += 1

    print("=" * 74)
    print("1. WHAT THE PARSER HAS NO VOCABULARY FOR")
    print("=" * 74)
    print("A legacy type is 'unreachable' when the parser emits no structural")
    print("edge kind that could carry it -- not merely absent, but inexpressible.\n")
    kinds = collections.Counter()
    for ref in list(edges)[:4000]:
        for e in edges[ref]:
            kinds[e["type"]] += 1
    print(f"parser structural kinds: {sorted(STRUCTURAL)}")
    print(f"parser total distinct edge types: {len(set(e['type'] for v in edges.values() for e in v))}"
          "   (verbs become types, so the vocabulary is open)\n")

    print(f"{'legacy type':26} {'total':>7} {'joinable':>9} {'parser also':>12}")
    rows = []
    for t, n in by_type.most_common():
        rows.append((t, n, joinable.get(t, 0), present.get(t, 0)))
    for t, n, j, p in rows[:28]:
        print(f"  {t:24} {n:>7} {j:>9} {p:>12}")

    tot_j = sum(joinable.values())
    tot_p = sum(present.values())
    print(f"\n  joined pairs {tot_j}, parser also linked {tot_p} "
          f"({100*tot_p/max(1,tot_j):.0f}%)")

    print()
    print("=" * 74)
    print("2. WHERE BOTH SPOKE ABOUT THE SAME TWO WORDS")
    print("=" * 74)
    pair = collections.Counter((t, pt) for t, pt, _, _, _ in disagreements)
    print(f"{'legacy says':26} {'parser says':22} {'n':>5}")
    for (lt, pt), c in pair.most_common(a.show * 2):
        print(f"  {lt:24} {pt:22} {c:>5}")

    print()
    print("  examples:")
    seen = set()
    for t, pt, ref, s, dd in disagreements:
        if (t, pt) in seen:
            continue
        seen.add((t, pt))
        print(f"    {ref:14} {ents[s]['name'][:20]:22} "
              f"legacy={t:20} parser={pt}")
        if len(seen) >= a.show:
            break

    print()
    print("=" * 74)
    print("3. WHERE THE LEGACY CLAIM LIVES, AND WHETHER THE PARSER COULD SEE IT")
    print("=" * 74)
    tj, tm, tn, tr = (sum(joinable.values()), sum(misses.values()),
                      sum(notlexical.values()), sum(noref.values()))
    total = len(rels)
    print(f"  both things are surface words in a cited verse   {tj:>6}"
          f"  {100*tj/total:>5.1f}%")
    print(f"     of those, the parser links them               {tot_p:>6}"
          f"  {100*tot_p/total:>5.1f}%")
    print(f"     of those, it does not                         {tm:>6}"
          f"  {100*tm/total:>5.1f}%")
    print(f"  verse is parsed, but they are NOT both words     {tn:>6}"
          f"  {100*tn/total:>5.1f}%")
    print(f"  no cited verse the parser holds                  {tr:>6}"
          f"  {100*tr/total:>5.1f}%")
    print(f"  {'':47} {'-'*6}")
    print(f"  {'legacy relations':47} {total:>6}")

    print("\n  the biggest 'both present, parser silent' types:")
    for t, c in misses.most_common(a.show):
        print(f"    {t:26} {c:>5}   of {joinable.get(t,0)} joinable")
    print("\n  examples of what is lost there:")
    seent = set()
    for t, ref, s, dd, note in missed:
        if t in seent:
            continue
        seent.add(t)
        print(f"    {ref:13} {ents[s]['name'][:18]:20} -{t}-> "
              f"{ents[dd]['name'][:22]}")
        if note:
            print(f"        note: {note[:88]}")
        if len(seent) >= a.show:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
