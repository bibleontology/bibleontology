"""Rule 3, mechanically: a subject that cannot do what the verb says.

A rule set was supplied for telling a symbol from a literal thing, ranking
three of its seven as catching most cases: **literal impossibility, category
mismatch, property transfer**.

**Two of those three are closed to us, and it is worth saying why.** Category
mismatch (*"God is my rock"* — agent against geological object) and property
transfer (*"the righteous shine"*) both require a semantic domain per word, and
the semantic-domain fields in our source — SDBH and Louw-Nida — are the UBS
permission-based ones this project does not use. They are not unbuilt; they are
unavailable.

**The third needs no lexicon at all**, because the corpus can supply it. *"The
mountains skipped"* is detectable without knowing what a mountain is, provided
you know that skipping is something the corpus's other subjects do and mountains
are not among them. That is a selectional violation, and it is arithmetic over
the clause layer.

## How animacy is derived rather than assumed

No animacy list is written down here. Instead:

1. A handful of verbs are unambiguously **speech**: say, speak, answer, call.
   Only an agent speaks. This is the one seed, and it is small on purpose.
2. **A lemma's animacy** is how often it is the subject of one of those.
3. **A verb's demand** is the average animacy of the subjects it usually takes.
4. A clause where a **high-demand verb** has a **low-animacy subject** is a
   candidate for figurative reading.

Step 2 bootstraps from step 1 and nothing else, so the only thing asserted by
hand is that speaking requires a speaker.

## What this is and is not

It is a **candidate detector**, not a classifier. A violation means the sentence
is doing something other than reporting a physical event, which covers metaphor,
personification and idiom together and does not separate them. That separation
is a reading, and stays in the overlay.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLAUSES = ROOT / "data" / "macula-clauses.jsonl.gz"

# The only hand-written input: verbs that require a speaker. Everything else is
# derived from how the corpus uses these.
SPEECH = {
    "אָמַר", "דָּבַר", "עָנָה", "קָרָא", "צָוָה", "שָׁאַל",
    "λέγω", "λαλέω", "ἀποκρίνομαι", "φημί", "κράζω", "ἐρωτάω",
}

# Articles, particles and pronouns are not the head of their constituent. Taking
# the first lemma of a subject gave "the" as the commonest subject in the corpus.
NOT_HEAD = {"הַ", "ὁ", "וְ", "אֵת", "כִּי", "אֲשֶׁר", "הוּא", "הֵם", "אֲנִי",
            "אַתָּה", "τὶς", "αὐτός", "ἐγώ", "σύ", "οὗτος", "ὅς", "καί", "δέ"}


def head_lemma(part: dict) -> str | None:
    """The first lemma that is not a determiner, particle or pronoun."""
    for lem in part.get("lemmas") or []:
        if lem and lem not in NOT_HEAD:
            return lem
    return None


def load_clauses():
    rows = []
    with gzip.open(CLAUSES, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            parts = d.get("parts", [])
            v = next((p for p in parts if p.get("role") == "v"), None)
            s = next((p for p in parts if p.get("role") == "s"), None)
            if not v or not s:
                continue
            vl, sl = head_lemma(v), head_lemma(s)
            if vl and sl:
                rows.append((d["ref"], sl, vl, s.get("gloss"), v.get("gloss"),
                             d.get("gloss")))
    return rows


# First and second person pronouns. The nodes carry no `person` field, but these
# lemmas ARE the speaker and the addressee -- that is what the words mean, not a
# fact about any particular sentence. Third person is deliberately absent: `he`
# may be a man or a mountain, and the point stands that resolving it needs the
# enclosing group, which does not exist yet.
DEICTIC = {
    "ἐγώ", "κἀγώ", "σύ", "ἡμεῖς", "ὑμεῖς", "ἐμός", "σός",
    "אֲנִי", "אָנֹכִי", "אַתָּה", "אַתְּ", "אַתֶּם", "אֲנַחְנוּ",
}


def score(node: dict, animacy: dict) -> float | None:
    """A node's animacy, with first and second person taken as given.

    "I am the vine, you are the branches" was missed, and the reason was
    a filter of mine rather than anything about the text: pronouns are excluded
    when finding the head noun of a subject, correctly, and that left `I` and
    `you` with no animacy score at all. **A speaker and an addressee are the two
    most animate things a sentence has**, so they are given 1.0 outright rather
    than being waited for in a distribution they were never allowed to enter.

    Third person is left to the distribution: `he` may be a man or a mountain,
    and the antecedent is not in this layer.
    """
    if node.get("person") in (1, 2, "1", "2", "first", "second") \
            or node.get("lemma") in DEICTIC:
        return 1.0
    x = animacy.get(node.get("lemma"))
    if x is not None:
        return x
    # An unseen COMMON noun is not unknown, it is not a speaker: `vine` never
    # heads a clause often enough to earn a score, and that absence is the
    # evidence. Without this, "I am the vine" was skipped for want of a number
    # on the side that was obviously inanimate. Proper nouns get no such default
    # -- an unseen name is far more likely to be a person than a thing.
    if node.get("class") == "noun" and node.get("type") == "common":
        return 0.0
    return None


def category_mismatch(animacy, show):
    """Rule 1, after all: an identity or comparison across the animacy line.

    When told this needed a licensed semantic lexicon, the answer was not to
    give up so easily on rule 1 -- God is my rock, he will be like a tree, I am
    the vine and you are the branches -- and that was right. **The domain does not have to come from a
    lexicon when the corpus can supply it.** Those three sentences all put a
    speaker on one side and a thing that has never spoken on the other, and the
    animacy score derived above already knows the difference.

    So this reads the `is` and `like` edges and reports the pairs that cross the
    line. It says a category boundary was crossed, not what the figure means.
    """
    import gzip as _gz
    nodes = {}
    with _gz.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt",
                  encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if not any(k.startswith("_") for k in d):
                nodes[d["id"]] = d
    # Both sources. The verbless file carries the predications Hebrew states
    # without a copula, which is where "God is my rock" lives -- without it this
    # rule could only ever see the Greek half of the canon.
    sources = [ROOT / "out" / "placeholder-edges.jsonl.gz",
               ROOT / "out" / "verbless-edges.jsonl.gz"]
    hits, seen_edge = [], set()
    for src_path in [p for p in sources if p.exists()]:
      with _gz.open(src_path, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            e = json.loads(line)
            if any(k.startswith("_") for k in e):
                continue
            if e["type"] not in ("is", "like"):
                continue
            a, b = nodes.get(e["src"]), nodes.get(e["dst"])
            if not (a and b):
                continue
            xa, xb = score(a, animacy), score(b, animacy)
            if xa is None or xb is None:
                continue
            key = (e["ref"], e["src"], e["dst"])
            if key in seen_edge:
                continue
            seen_edge.add(key)
            if max(xa, xb) >= 0.15 and min(xa, xb) <= 0.01:
                hits.append((max(xa, xb) - min(xa, xb), e["ref"], e["type"],
                             a.get("text"), b.get("text"), xa, xb))
    hits.sort(reverse=True)
    print(f"\ncategory mismatches across `is`/`like`: {len(hits)}\n")
    print(f"  {'verse':13} {'':6} {'one side':22} {'other side'}")
    for _, ref, ty, ta, tb, xa, xb in hits[:show]:
        print(f"  {ref:13} {ty:6} {str(ta)[:20]:22} {str(tb)[:22]:24} "
              f"({xa:.2f} / {xb:.2f})")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--min-verb", type=int, default=8,
                    help="verb needs this many subjects before it has a demand")
    ap.add_argument("--min-subj", type=int, default=5)
    ap.add_argument("--show", type=int, default=18)
    ap.add_argument("--mismatch", action="store_true",
                    help="rule 1: identity/comparison across the animacy line")
    a = ap.parse_args()

    rows = load_clauses()
    print(f"subject-verb clauses: {len(rows)}")

    # 1-2. animacy per subject lemma: share of its uses that are speech verbs
    spoke = collections.Counter()
    seen = collections.Counter()
    for _, s, v, *_ in rows:
        seen[s] += 1
        if v in SPEECH:
            spoke[s] += 1
    animacy = {s: spoke[s] / n for s, n in seen.items() if n >= a.min_subj}
    print(f"subject lemmas with >= {a.min_subj} uses: {len(animacy)}")
    top = sorted(animacy.items(), key=lambda kv: -kv[1])[:8]
    print("  most animate:", ", ".join(f"{s}={v:.2f}" for s, v in top))

    # 3. each verb's demand: mean animacy of the subjects it takes
    dem = collections.defaultdict(list)
    for _, s, v, *_ in rows:
        if s in animacy and v not in SPEECH:
            dem[v].append(animacy[s])
    demand = {v: sum(xs) / len(xs) for v, xs in dem.items()
              if len(xs) >= a.min_verb}
    print(f"verbs with >= {a.min_verb} usable subjects: {len(demand)}")
    hi = sorted(demand.items(), key=lambda kv: -kv[1])[:8]
    print("  most agent-demanding:", ", ".join(f"{v}={d:.2f}" for v, d in hi))

    if a.mismatch:
        category_mismatch(animacy, a.show)
        return 0

    # 4. violations
    out = []
    for ref, s, v, sg, vg, cg in rows:
        d = demand.get(v)
        an = animacy.get(s)
        if d is None or an is None or v in SPEECH:
            continue
        if d >= 0.25 and an <= 0.02:
            out.append((d - an, ref, sg, vg, cg))
    out.sort(reverse=True)
    print(f"\nselectional violations: {len(out)} "
          f"(agent-demanding verb, inanimate subject)\n")
    print(f"  {'verse':13} {'subject':22} {'verb':18} clause")
    for score, ref, sg, vg, cg in out[:a.show]:
        print(f"  {ref:13} {str(sg)[:20]:22} {str(vg)[:16]:18} "
              f"{str(cg)[:44]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
