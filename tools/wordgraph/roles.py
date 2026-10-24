"""What the text SAYS ABOUT a word, from the structure graph's roles.

2026-09-27: is there something about the concepts a word is paired with in
the structure, for example attributes paired with God, attributes paired with
David, attributes of the Babylonians, and so on?

Each clause of the clean structure builder says who does what (s, v), what
something is (s, p) and what is done to whom (o, v). Reading those roles
over the whole Hebrew Bible gives every lexeme a PROFILE:
  does      the verbs it is the subject of          ("the LORD ... remembers")
  is        what is predicated of it                ("the LORD is compassionate")
  undergoes the verbs it is the object of           ("... bless the LORD")
  is_said_of (for a predicate word) the subjects it is said of
A pronoun counts for its referent where S5 resolved it ("he" -> the LORD).

The profiles give a FOURTH similarity: two words are alike when the text
says the same kinds of things about them. Tested like the others
(similarity.py's pairs).

    python tools/wordgraph/roles.py profile <lemma> [n]
    python tools/wordgraph/roles.py test
"""
import collections
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import similarity as SIM                                   # noqa: E402

OUT = SIM.OUT


def build_pairs():
    """(lexeme, relation, partner lexeme) for every role in the graph."""
    lex, layers, occ_lex = SIM.load()
    nodes = {d["id"]: d for d in SIM.rows(OUT / "structure-nodes.jsonl.gz")}
    edges = list(SIM.rows(OUT / "structure-edges.jsonl.gz"))
    members = collections.defaultdict(list)
    refers = {}
    roles = collections.defaultdict(lambda: collections.defaultdict(list))
    for e in edges:
        t = e.get("type")
        if t == "member":
            members[e["src"]].append(e["dst"])
        elif t == "refers_to":
            refers[e["src"]] = e["dst"]
        elif e.get("clause_role") and t in ("s", "v", "o", "p"):
            roles[e["src"]][t].append(e["dst"])

    def lexemes(nid, depth=0):
        """The lexemes a filler stands for: a word's own, a composite's
        members', a pronoun's referent's."""
        if not nid or depth > 4:
            return []
        if nid in refers:
            return lexemes(refers[nid], depth + 1)
        n = nodes.get(nid) or {}
        if n.get("composite"):
            return [x for m in members.get(nid, [])
                    for x in lexemes(m, depth + 1)]
        return [occ_lex[i] for i in (n.get("src") or [])[:1]
                if i in occ_lex]

    pairs = collections.Counter()
    for ct, r in roles.items():
        subj = [x for s in r.get("s", []) for x in lexemes(s)]
        verb = [x for v in r.get("v", []) for x in lexemes(v)]
        obj = [x for o in r.get("o", []) for x in lexemes(o)]
        pred = [x for p in r.get("p", []) for x in lexemes(p)]
        for s in subj:
            for v in verb:
                pairs[(s, "does", v)] += 1
            for p in pred:
                pairs[(s, "is", p)] += 1
                pairs[(p, "is_said_of", s)] += 1
        for o in obj:
            for v in verb:
                pairs[(o, "undergoes", v)] += 1
    return lex, layers, pairs


def ppmi_profiles(pairs):
    """lexeme -> {(relation, partner): PPMI}."""
    f_l, f_f = collections.Counter(), collections.Counter()
    for (l, rel, p), n in pairs.items():
        f_l[l] += n
        f_f[(rel, p)] += n
    total = sum(pairs.values())
    prof = collections.defaultdict(dict)
    for (l, rel, p), n in pairs.items():
        pmi = math.log(n * total / (f_l[l] * f_f[(rel, p)]))
        if pmi > 0 and n >= 2:
            prof[l][(rel, p)] = pmi * math.log(1 + n)
    return prof


def gloss(layers, lid):
    return ((layers.get(lid) or {}).get("glosses") or {}).get("usual") or ""


def profile(lemma, n=10):
    lex, layers, pairs = build_pairs()
    L = SIM.by_lemma(lex)
    lid = L.get(lemma)
    if not lid:
        print("no such lemma")
        return
    prof = ppmi_profiles(pairs)
    print(f"{lex[lid]['lemma']} ({gloss(layers, lid)}), "
          f"{lex[lid]['count']} occurrences")
    for rel in ("does", "is", "undergoes", "is_said_of"):
        items = sorted(((w, p) for (r, p), w in prof.get(lid, {}).items()
                        if r == rel), reverse=True)[:n]
        if items:
            print(f"  {rel:10} " + ", ".join(
                f"{gloss(layers, p) or lex[p]['lemma']} "
                f"({pairs[(lid, rel, p)]})" for _, p in items))


def test():
    lex, layers, pairs = build_pairs()
    prof = ppmi_profiles(pairs)
    L = SIM.by_lemma(lex)
    ps = [(L.get(a), L.get(b)) for a, b in SIM.PAIRS]
    common = [l for l, d in lex.items() if d.get("lang") == "H"
              and d.get("count", 0) >= 20]
    import random
    rng = random.Random(7)
    rand = [(rng.choice(common), rng.choice(common)) for _ in range(400)]
    syn = [SIM.cos(prof.get(a), prof.get(b)) for a, b in ps]
    syn = [s for s in syn if s is not None]
    rnd = [SIM.cos(prof.get(a), prof.get(b)) for a, b in rand if a != b]
    rnd = [s for s in rnd if s is not None]
    auc = sum((s > r) + 0.5 * (s == r) for s in syn for r in rnd) \
        / max(1, len(syn) * len(rnd))
    pool = set(common)
    top = 0
    for a, b in ps:
        nb = {x for _, x in SIM.neighbours(prof, a, 10, pool)}
        nb2 = {x for _, x in SIM.neighbours(prof, b, 10, pool)}
        top += (b in nb) or (a in nb2)
    print(f"  roles    coverage {len(syn)}/{len(ps)} pairs  mean syn "
          f"{sum(syn) / max(1, len(syn)):.2f} vs random "
          f"{sum(rnd) / max(1, len(rnd)):.2f}  AUC {auc:.2f}  "
          f"partner in top-10: {top}/{len(ps)}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["profile"]:
        profile(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 10)
    else:
        test()
