"""What the claims export asserts is the narrator's, as claimed (plan 8.3f).

The README's strongest claim is that a tool loading only the asserted triples
gets what the text itself states and nothing else. On 2026-10-22 the simulated
Reddit critics counted the published export and found it false: about 3,500
conjectured, disputed and editorial claims were asserted as the narrator's,
because anything credited to no one fell to the narrator. Four review seats had
checked the README against the code and missed it. So this test counts in the
PUBLISHED FILES, not in the exporter:

  1. No claim of a grouping relation (themes, patterns, story links, the
     text's divisions, what a passage speaks of) is in the narrator's voice.
  2. Every triple in the narrator's graph (RDF 1.1) has a narrator claim that
     is explicit or implied, of a relation that is not a grouping.
  3. The RDF 1.2 file asserts exactly the 1.1 narrator graph's triples.
  4. No bor:states triple is asserted: the relation has no verb, so different
     sentences would share one triple (Doug, 2026-10-22, "states: A").

Each with a planted fault, aimed at that check, that must be caught (a check
that never fires is not a check). The same checks as SPARQL, for a consumer
who wants to run them against a store (rdflib's engine takes over ten minutes
on the 1.1 file, so the test counts in Python):

  1. ASK { ?c claim:relation ?p ; claim:voice claim:narrator .
           VALUES ?p { bor:in_theme bor:instance_of ... } }        -> false
  2. ASK { GRAPH claim:narrator { ?s ?p ?o }
           FILTER NOT EXISTS { ?c claim:subject ?s ; claim:relation ?p ;
             claim:object ?o ; claim:voice claim:narrator ;
             claim:certainty ?k . VALUES ?k { claim:explicit claim:implied } } }
                                                                    -> false

    python tests/test_assertion_policy.py
"""
import gzip
import sys
from pathlib import Path

import rdflib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from export_claims import GROUPING, STATED_CERTAINTY  # noqa: E402

OUT = ROOT / "out" / "export"
SITE = "https://bibleontology.org"
C = rdflib.Namespace(SITE + "/ns/claim#")
BOR = SITE + "/ns/relation#"
E = SITE + "/e/"
HEAD12 = "# What the text itself states (the narrator), asserted:\n"


def short(u):
    u = str(u)
    for pre, ns in (("e:", E), ("bor:", BOR)):
        if u.startswith(ns):
            return pre + u[len(ns):]
    return f"<{u}>"


def published():
    """(claims, narrator triples in 1.1, asserted triples in 1.2), as written."""
    ds = rdflib.Dataset()
    with gzip.open(OUT / "claims.trig.gz", "rt", encoding="utf-8") as f:
        ds.parse(data=f.read(), format="trig")
    claims = {}
    for c in set(ds.default_graph.subjects(rdflib.RDF.type, C.Claim)):
        v = ds.default_graph.value
        claims[c] = (short(v(c, C.subject)), short(v(c, C.relation)), short(v(c, C.object)),
                     str(v(c, C.voice)), str(v(c, C.certainty)).split("#")[-1])
    n11 = {tuple(short(x) for x in t) for t in ds.graph(C.narrator)}
    with gzip.open(OUT / "claims-rdf12.trig.gz", "rt", encoding="utf-8") as f:
        t12 = f.read()
    if HEAD12 not in t12:
        raise SystemExit("claims-rdf12.trig: the asserted section's heading is missing")
    # rdflib reads no RDF 1.2, and the asserted section is plain lines
    # (an IRI the file could not prefix is written whole: normalised to short)
    a12 = {tuple(short(x[1:-1]) if x.startswith("<") else x for x in ln.rstrip(" .").split())
           for ln in t12.split(HEAD12, 1)[1].splitlines() if ln.strip()}
    return claims, n11, a12


def checks(claims, n11, a12):
    """{check number: what failed}, so a planted fault is known to be caught
    by the check meant for it and not by another one by accident."""
    out = {}
    nar = str(C.narrator)
    grouped = [c for c, (s, p, o, v, k) in claims.items() if v == nar and p[4:] in GROUPING]
    if grouped:
        out[1] = f"{len(grouped)} grouping claims in the narrator's voice, e.g. {grouped[0]}"
    warranted = {(s, p, o) for s, p, o, v, k in claims.values()
                 if v == nar and k in STATED_CERTAINTY and p[4:] not in GROUPING}
    bare = n11 - warranted
    if bare:
        out[2] = (f"{len(bare)} triples in the narrator's graph with no explicit or implied narrator claim, "
                  f"e.g. {sorted(bare)[0]}")
    if n11 != a12:
        out[3] = f"the files disagree: {len(n11 - a12)} stated only in 1.1, {len(a12 - n11)} only in 1.2"
    # 4. no verbless triple: bor:states carries no verb, so a speaker's
    # sentence and the narrator's would share it ("states: A", 2026-10-22)
    verbless = [t for t in a12 | n11 if t[1] == "bor:states"]
    if verbless:
        out[4] = f"{len(verbless)} bor:states triples asserted, e.g. {verbless[0]}"
    return out


def main():
    claims, n11, a12 = published()
    found = checks(claims, n11, a12)
    fails = list(found.values())
    for f in fails:
        print("FAIL " + f)
    nar = str(C.narrator)
    theme = ("e:abraham", "bor:in_theme", "e:faith")
    conj = ("e:planted_s", "bor:father_of", "e:planted_o")
    # PLANTED FAULTS, each aimed at one check (the 1.2 side made to agree
    # where needed, so the files' comparison is not what catches it)
    planted = {
        "a theme link in the narrator's graph": (2, claims, n11 | {theme}, a12 | {theme}),
        "a conjecture stated": (2, {**claims, "planted": (*conj, nar, "conjectured")}, n11 | {conj}, a12 | {conj}),
        "a disputed claim stated": (2, {**claims, "planted": (*conj, nar, "disputed")}, n11 | {conj}, a12 | {conj}),
        "a grouping claim voiced as the narrator": (
            1, {**claims, "planted": ("e:x", "bor:part_of", "e:y", nar, "explicit")}, n11, a12),
        "the 1.2 file asserting a grouping": (3, claims, n11, a12 | {theme}),
        # a verb statement asserted, though its narrator claim warrants it
        "a bor:states triple asserted": (
            4, {**claims, "planted": ("e:god", "bor:states", "e:david", nar, "explicit")},
            n11 | {("e:god", "bor:states", "e:david")}, a12 | {("e:god", "bor:states", "e:david")}),
    }
    caught = 0
    for name, (want, cl, n, a) in planted.items():
        if want in checks(cl, n, a):
            caught += 1
        else:
            print(f"FAIL planted fault not caught by check {want}: {name}")
            fails.append(name)
    print(f"assertion policy: {len(claims):,} claims, {len(a12):,} asserted triples; "
          f"planted faults caught: {caught} of {len(planted)}; {len(fails)} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
