"""The same argument: verses whose clauses are joined the same way.

2026-09-28, on John 3:16's connections: the verse is a cause and effect
relationship, where the cause is God's love and the effect is eternal
life/salvation from sin, and the matcher was not trying to match that
pattern. A partial match like Romans 6:23 is acceptable, but a verse like
1 John 3:16 is what should rank as the best match.

aligned.py matches clause with clause, so a verse sharing ONE clause of a
five-clause verse ("God gave Heman fourteen sons") ranked as "the same
thing". What John 3:16 says is its SHAPE: God loved -> so He gave His Son
-> so that whoever believes has life. The builder records those joins as
clause links (result, purpose, because, therefore); each is a CAUSE ->
EFFECT pair ("A because B": B is the cause).

A link here aligns with a link there when its cause shares a CONCEPT FAMILY
with this cause and its effect with this effect. A family must join a verb
to its noun and Hebrew to Greek — love/loved, live/life — so it is read
off the Septuagint: a Hebrew word's family is its consonantal root
(אהבה and אהב: אהב); a Greek word's is every Hebrew root it translates
(ἀγάπη <- אהבה, ἀγαπάω <- אהב: both אהב; ζωή <- חיים, ζάω <- חיה: both
חי). Rough by design: the link's shape and BOTH ends must agree, which is
what keeps a short root's collisions out.

    python tools/patterns/argument.py        -> out/argument.jsonl.gz
"""
import collections
import gzip
import json
import math
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "out"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "tools" / "builder"))
import mine  # noqa: E402
import echoes as E  # noqa: E402
from source import norm  # noqa: E402

# how a link runs: cause -> effect, or effect <- cause
FORWARD = {"result", "purpose", "therefore", "failed_result"}
BACKWARD = {"because"}
COMMON = 0.06          # a family on more than this share of ends finds nothing
                       # (at 2%, "God" 2.9%, "give" 3.0% and "son" 2.1% left
                       # John 3:16's cause with nothing to find with)
TOP = 8                # aligned arguments kept per link
SHAPE = 3.0            # both ends lining up through a causal link
MATRES = set("וי")
BACK_SHARE = 0.25      # a Greek word's family: roots it translates this often
# an end takes in the clauses joined to it: "not perish BUT have life"
COORD = {"and", "but_rather", "contrast", "or"}
EXTRA = 0.5            # each further shared family on an end, up to two


def hroot(lem):
    """A Hebrew word's consonantal root, roughly: the plural or feminine
    ending off, the vowel letters inside off, three letters."""
    s = "".join(ch for ch in lem if "א" <= ch <= "ת")
    for suf in ("ים", "ות", "ה", "ת"):
        if len(s) > 3 and s.endswith(suf):
            s = s[: -len(suf)]
    if len(s) > 3:
        s = s[0] + "".join(ch for ch in s[1:-1] if ch not in MATRES) + s[-1]
    return s[:3]


def main():
    t0 = time.time()
    (nodes, roles, neg, part, cond, links, mention, ents, cat, label,
     simile_lemma, bridge) = mine.load()
    # Greek word -> the Hebrew root(s) it MOSTLY translates: at least
    # BACK_SHARE of its Septuagint uses. Every root that renders to it at
    # all gave δίδωμι "give" 21 roots, and "give" matched everything.
    lex, g_by_strong = {}, collections.defaultdict(collections.Counter)
    for d in mine.rows(OUT / "word-lexemes.jsonl.gz"):
        if d.get("kind") != "lexeme":
            continue
        lex[d["id"]] = (d["lang"]["value"], d["lemma"]["value"])
        if d["lang"]["value"] == "G" and d["strong"]["value"]:
            g_by_strong[str(d["strong"]["value"]).lstrip("0")][
                d["lemma"]["value"]] += d["count"]["value"]
    counts = collections.defaultdict(collections.Counter)   # greek -> roots
    for d in mine.rows(OUT / "word-lexeme-layers.jsonl.gz"):
        s = ((d.get("septuagint") or {}).get("value") or {}).get("counts")
        if not s or d["id"] not in lex or lex[d["id"]][0] not in ("H", "A"):
            continue
        r = hroot(norm(lex[d["id"]][1]))
        for c in s:
            gs = str(c.get("greekstrong") or "").lstrip("0")
            if g_by_strong.get(gs):
                g = norm(g_by_strong[gs].most_common(1)[0][0])
                counts[g][r] += c["count"]
    back = {}
    for g, rc in counts.items():
        tot = sum(rc.values())
        back[g] = {r for r, k in rc.items() if k / tot >= BACK_SHARE}

    def fam(lang, lem):
        if lang == "greek":
            return {f"r:{r}" for r in back.get(lem, ())} or {f"g:{lem}"}
        r = hroot(lem)
        return {f"r:{r}"} if len(r) >= 2 else set()

    # every word under a clause, by role (and the resolved unstated subject)
    fill = collections.defaultdict(set)
    refers = {}
    for e in mine.rows(OUT / "structure-edges.jsonl.gz"):
        if e["type"] == "refers_to":
            refers.setdefault(e["src"], e["dst"])
        elif e.get("clause_role") and "#ct" in e["src"] and \
                e["type"] in ("s", "o", "o2", "p", "pp", "io", "v"):
            fill[e["src"].replace("#ct", "#cl")].add(e["dst"])

    def ends(cid):
        c = nodes.get(cid) or {}
        out = set()
        if c.get("verb_lemma"):
            out |= fam(c["lang"], norm(c["verb_lemma"]))
        for d_ in fill.get(cid, ()):
            w = nodes.get(refers.get(d_, d_)) or nodes.get(d_) or {}
            if w.get("lemma") and w.get("class") in ("noun", "verb", "adj"):
                out |= fam(w["lang"], norm(w["lemma"]))
        return out

    coord = collections.defaultdict(set)
    for a, b, t in links:
        if t in COORD:
            coord[a].add(b)
            coord[b].add(a)
    arg = []                         # (cause clause, effect clause, type)
    for a, b, t in links:
        if t in FORWARD:
            arg.append((a, b, t))
        elif t in BACKWARD:
            arg.append((b, a, t))
    endk = {}
    for a, b, _t in arg:
        for x in (a, b):
            if x not in endk:
                endk[x] = set().union(ends(x), *(ends(y) for y in coord[x]))
    df = collections.Counter(k for ks in endk.values() for k in ks)
    n = len(endk)
    import os
    for dbg in filter(None, os.environ.get("ARG_DEBUG", "").split(",")):
        print("DEBUG", dbg, {k: round(df[k] / n, 3) for k in endk.get(dbg, ())})
    idf = {k: math.log(n / v) for k, v in df.items()}
    rare = lambda ks: {k for k in ks if df[k] <= COMMON * n}  # noqa: E731
    bucket = collections.defaultdict(list)
    for i, (a, b, _t) in enumerate(arg):
        for kc in rare(endk[a]):
            for ke in rare(endk[b]):
                bucket[(kc, ke)].append(i)
    print(f"{len(arg):,} cause->effect links, {len(bucket):,} keys "
          f"({time.time() - t0:.0f}s)", flush=True)

    out = []
    for i, (a, b, t) in enumerate(arg):
        va = a.split("#")[0]
        best = {}
        for kc in rare(endk[a]):
            for ke in rare(endk[b]):
                for j in bucket.get((kc, ke), ()):
                    c2, e2, t2 = arg[j]
                    vb = c2.split("#")[0]
                    if vb == va:
                        continue
                    shc = rare(endk[a]) & endk[c2]
                    she = rare(endk[b]) & endk[e2]
                    end = lambda sh: max(idf[k] for k in sh) + EXTRA * min(  # noqa
                        2, len(sh) - 1)
                    s = end(shc) + end(she) + SHAPE
                    if s > best.get(j, (0,))[0]:
                        best[j] = (s, shc, she)
        for j, (s, shc, she) in sorted(best.items(), key=lambda x: -x[1][0])[:TOP]:
            c2, e2, t2 = arg[j]
            out.append({"from": va, "to": c2.split("#")[0], "score": round(s, 2),
                        "link": [t, t2], "cause": [a, c2], "effect": [b, e2],
                        "shared_cause": sorted(shc), "shared_effect": sorted(she)})
    with gzip.open(OUT / "argument.jsonl.gz", "wt", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(out):,} aligned arguments ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
