"""Give the parser something that outlives a verse.

The parser emits 231,876 word occurrences at exactly 1.00 nodes per id:
`Gen.1.1#god` and `Gen.1.2#god` are different nodes and nothing says they are
the same God. That is why the legacy graph can hold `father_of` and the parser
cannot — the relation needs an Abraham who outlives the sentence.

This builds that missing layer, deterministically and for free, from the one
rule the measurement supports (`tools/coref.py`, 2026-09-07):

    corpus frequency   maps to 1 legacy entity
    1-25                   93%
    26-100                 84%
    101-400                63%
    401-1500               32%
    1501+                  25%

**A rare lemma names a thing; a frequent lemma names a kind.** So every
occurrence of a lemma below the threshold is joined into one referent, and
nothing above it is joined at all -- `bayit` occurs in the thousands and is not
one house. Claiming nothing there is the correct answer, not a gap: a common
noun's identity is local (its possessor, its appositive, its role), and that is a
different mechanism rather than a weaker version of this one.

## How this is scored, and the trap in scoring it

The legacy graph is the check. But **its `refs` are the verses a worker cited,
not every verse the entity appears in**, so precision against them is
meaningless -- finding Abraham in a verse nobody cited is a success that would
score as an error. Two things are measured instead:

- **coverage**: of the verses a legacy entity DOES cite, how many did we join?
- **purity**: does one referent answer to exactly one legacy entity, or did we
  merge two the graph keeps apart?

Purity is the one that can go wrong quietly, so it is reported per threshold
rather than at a chosen value.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "referents.jsonl.gz"

CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

STOPW = {
    "the", "a", "an", "of", "and", "to", "in", "on", "at", "by", "for", "with",
    "from", "his", "her", "their", "its", "this", "that", "these", "those",
    "is", "was", "were", "be", "he", "she", "it", "they", "them", "him", "who",
}
REFERRING = {
    "person", "place", "group", "object", "creature", "being", "title",
    "concept", "image", "covenant", "observance",
}
REF = re.compile(r"^\s*(\S+?)[\s.](\d+)[:.](\d+)\s*$")


def words(s: str) -> set[str]:
    return set(re.findall(r"[a-z]+", (s or "").lower())) - STOPW


def norm_ref(r: str) -> str:
    m = REF.match(str(r))
    return f"{m.group(1)}.{m.group(2)}.{m.group(3)}" if m else ""


def lemma_key(n: dict) -> str:
    return ("h" if n.get("lang") == "hebrew" else "g") + str(n.get("strong") or "?")


def load_nodes():
    by_ref = collections.defaultdict(list)
    by_lemma = collections.defaultdict(list)
    with gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            by_ref[d["ref"]].append(d)
            if d.get("strong"):
                by_lemma[lemma_key(d)].append(d)
    return by_ref, by_lemma


def adverbial_uses() -> set[tuple]:
    """(verse, original lemma form) pairs where a single word IS the adjunct.

    Rule 4 of the decision tree as set out: *a word that modifies a verb is an
    adverb*, whatever its dictionary class. MACULA marks the role, so this is a
    join rather than an inference.

    **Single-word adjuncts only.** The `adv` role sits on the whole adjunct, so
    counting every word inside one attributed the phrase's function to each of
    its members and reported 69% of adverbial words as "not lexically adverbs" --
    when what it had found was nouns inside prepositional phrases like *to all
    the peoples*. Restricted to `n == 1` the figure is 25% of 18,093, and the
    cases are the real thing:

        g2117  euthys   adj "straight"  -> "immediately"   Mark's straightway
        g3440  monos    adj "only"      -> "only"
        g4053  perissos adj "abundant"  -> "abundantly"    John 10:10
        h3915  laylah   noun "night"    -> "by night"
    """
    out = set()
    p = ROOT / "data" / "macula-clauses.jsonl.gz"
    if not p.exists():
        return out
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            for part in d.get("parts", []):
                if part.get("role") != "adv" or part.get("n") != 1:
                    continue
                lems = part.get("lemmas") or []
                if lems:
                    out.add((d["ref"], lems[0]))
    return out


def load_legacy():
    ents = {}
    for line in (ROOT / "ontology" / "entities" / "entities.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            e = json.loads(line)
            ents[e["id"]] = e
    return ents


# A minority reading below this share is annotation noise, not a distinct use.
SPLIT_SHARE = 0.20


def word_class(n: dict) -> str:
    """MACULA's own word class, falling back to the coarser `pos`.

    Both are present and `class` is much the better field -- 132,389 nouns
    against `pos`'s 110,283, and 37,744 nulls against 82,218. Reading `pos`
    first was measuring the sparser of two answers to the same question.
    """
    c = n.get("class")
    if c:
        return c
    p = n.get("pos")
    return p if p and p != "?" else ""


def use_key(n: dict, adverbial: set) -> str:
    """The word's class, overridden by its FUNCTION when the clause disagrees.

    A lexically adjectival word standing alone as an adjunct is being used as an
    adverb, and that is a different concept from its attributive use -- `euthys`
    meaning *straight* against `euthys` meaning *immediately*.
    """
    c = word_class(n)
    if c and c != "adv" and (n.get("ref"), n.get("lemma")) in adverbial:
        return "adv:used"
    return c


def pos_groups(ns: list[dict], adverbial: set = frozenset()) -> dict[str, list[dict]]:
    """Split a lemma's occurrences by part of speech, but only when it earns it.

    The requirement: concepts are keyed on the original-language word, but the
    type is isolated by how it is used (noun, adjective, adverb), and there
    are grammar rules for that.

    There are, and **MACULA has already applied them.** It is a syntactic
    treebank: article, agreement, case, state and position were resolved by
    annotators, so the decision tree those rules describe is upstream of this
    file. Re-deriving it from surface forms would produce worse answers to a
    question already answered.

    And the original word does most of the remaining work by itself. **Only 97
    of 11,081 lemmas are used with more than one word class at all**, because a
    Hebrew or Greek lemma encodes class in a way English does not: it is `love`
    that is both noun and verb, while `chesed` is a noun. That is an argument for
    keying concepts on the original word rather than the English.

    Nearly all of those 97 are annotation noise -- thousands of one reading
    against a single instance of another -- so the test is SHARE, not presence.
    **39 lemmas clear the bar** and they are real:

        g5384  philos    adj 5 / noun 3      dear      vs a friend
        g2532  kai       adv 206 / conj 141  also      vs and
        g3699  hopou     adv 37 / conj 36    where

    Those are two concepts sharing a word, and joining them would be the same
    error as merging Lot's wife with Potiphar's.

    What this does NOT capture is *function* -- an adjective used adverbially,
    rule 4 of that decision tree. That lives in the clause layer's `role` (adv
    appears 8,483 times) rather than in the word, and is a separate join.
    """
    real = collections.Counter(use_key(n, adverbial) for n in ns
                               if use_key(n, adverbial))
    if len(real) < 2 or min(real.values()) / sum(real.values()) < SPLIT_SHARE:
        return {"": ns}
    groups = collections.defaultdict(list)
    for n in ns:
        c = use_key(n, adverbial)
        groups[c if c in real else ""].append(n)
    return dict(groups)


def build(by_lemma, threshold, proper_only=False, adverbial=frozenset()):
    """One referent per lemma that is rare enough to name a thing."""
    out = {}
    for lem, all_ns in by_lemma.items():
        if len(all_ns) > threshold:
            continue
        if proper_only and not any(n.get("proper") for n in all_ns):
            continue
        for pos, ns in pos_groups(all_ns, adverbial).items():
            if not ns:
                continue
            key = f"{lem}.{pos}" if pos else lem
            surf = collections.Counter(n.get("text", "") for n in ns if n.get("text"))
            forms = collections.Counter(n.get("lemma", "") for n in ns if n.get("lemma"))
            out[key] = {
                "id": f"ref:{key}",
                "lemma": lem,
                "class": pos or (collections.Counter(
                    word_class(n) for n in ns if word_class(n)).most_common(1) or
                    [("", 0)])[0][0],
                "split_by_class": bool(pos),
                "adverbial_use": pos == "adv:used",
                "name": surf.most_common(1)[0][0] if surf else lem,
                "original": forms.most_common(1)[0][0] if forms else "",
                "lang": "Hebrew" if lem[0] == "h" else "Greek",
                "proper": bool(sum(1 for n in ns if n.get("proper")) > len(ns) / 2),
                "occurrences": len(ns),
                "verses": sorted({n["ref"] for n in ns}),
                "nodes": [n["id"] for n in ns],
            }
    return out


def score(refts, ents, by_ref):
    """Coverage and purity against the legacy graph."""
    verse_of_lemma = {lem: set(r["verses"]) for lem, r in refts.items()}
    covs, pures, lexcovs = [], [], []
    lemma_claims = collections.defaultdict(set)

    for eid, e in ents.items():
        if e.get("type") not in REFERRING:
            continue
        cited = {norm_ref(x) for x in e.get("refs", [])}
        cited = {c for c in cited if c in by_ref}
        nw = words(e.get("name", ""))
        if len(cited) < 2 or not nw:
            continue
        # which lemmas actually sit under this entity's name, in its verses?
        lem = collections.Counter()
        lexical = set()          # verses where the name is actually a word
        for r in cited:
            for n in by_ref[r]:
                if nw & words(n.get("text", "")) and n.get("strong"):
                    lem[lemma_key(n)] += 1
                    lexical.add(r)
        if not lem:
            continue
        best = None
        for cand, _ in lem.most_common(4):
            if cand in verse_of_lemma:
                best = cand
                break
        if not best:
            continue
        got = verse_of_lemma[best] & cited
        covs.append(len(got) / len(cited))
        # A lexical rule can only ever reach the verses where the thing is
        # NAMED. The rest are pronouns and epithets -- "he", "his servant" --
        # and counting them against a lemma joiner measures the wrong thing.
        lexcovs.append(len(verse_of_lemma[best] & lexical) / max(1, len(lexical)))
        lemma_claims[best].add(eid)

    for lem, es in lemma_claims.items():
        pures.append(1 if len(es) == 1 else 0)
    return covs, pures, lemma_claims, lexcovs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--threshold", type=int, default=25)
    ap.add_argument("--proper-only", action="store_true")
    ap.add_argument("--sweep", action="store_true", help="score several thresholds")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    by_ref, by_lemma = load_nodes()
    ents = load_legacy()
    adverbial = adverbial_uses()
    print(f"single-word adverbial adjuncts: {len(adverbial)}")
    total_nodes = sum(len(v) for v in by_lemma.values())
    print(f"parser  {total_nodes} lemma-bearing occurrences over "
          f"{len(by_lemma)} lemmas, {len(by_ref)} verses\n")

    if a.sweep:
        print(f"{'thresh':>7} {'referents':>10} {'occ joined':>11} "
              f"{'%corpus':>8} {'checked':>8} {'lexical':>10} {'allrefs':>9} "
              f"{'purity':>7}")
        for t in (10, 25, 50, 100, 200, 400):
            r = build(by_lemma, t, a.proper_only, adverbial)
            c, p, _, lx = score(r, ents, by_ref)
            joined = sum(x["occurrences"] for x in r.values())
            print(f"{t:>7} {len(r):>10} {joined:>11} "
                  f"{100*joined/total_nodes:>7.1f}% {len(c):>8} "
                  f"{100*sum(lx)/max(1,len(lx)):>9.0f}% "
                  f"{100*sum(c)/max(1,len(c)):>8.0f}% "
                  f"{100*sum(p)/max(1,len(p)):>6.0f}%")
        return 0

    refts = build(by_lemma, a.threshold, a.proper_only, adverbial)
    covs, pures, claims, lexcovs = score(refts, ents, by_ref)
    joined = sum(x["occurrences"] for x in refts.values())
    print(f"threshold {a.threshold}"
          f"{' (proper nouns only)' if a.proper_only else ''}")
    print(f"  referents built       {len(refts)}")
    print(f"  occurrences joined    {joined}  "
          f"({100*joined/total_nodes:.1f}% of the corpus)")
    print(f"  checked against legacy {len(covs)} entities")
    print(f"  coverage where the thing is NAMED  "
          f"{100*sum(lexcovs)/max(1,len(lexcovs)):.0f}%")
    print(f"  coverage of every cited verse      "
          f"{100*sum(covs)/max(1,len(covs)):.0f}%   "
          f"(the rest are pronouns and epithets)")
    print(f"  purity (one referent = one entity) "
          f"{100*sum(pures)/max(1,len(pures)):.0f}%")

    impure = {l: es for l, es in claims.items() if len(es) > 1}
    if impure:
        print(f"\n  merged entities the graph keeps apart: {len(impure)}")
        for lem, es in sorted(impure.items(), key=lambda kv: -len(kv[1]))[:8]:
            names = sorted(ents[i]["name"][:20] for i in es)
            print(f"    {lem:8} {refts[lem]['name'][:16]:18} {', '.join(names[:4])}")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0

    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": CREDIT,
            "_note": f"Cross-verse referents. One per lemma occurring <= "
                     f"{a.threshold} times, which the legacy graph agrees with "
                     f"for a measured share of cases; frequent lemmas name kinds "
                     f"and are deliberately NOT joined.",
        }, ensure_ascii=False) + "\n")
        for r in sorted(refts.values(), key=lambda x: x["id"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
