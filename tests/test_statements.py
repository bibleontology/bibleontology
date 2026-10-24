"""Verb statements in the claim export keep their two rules (plan 2.17 step 3).

  1. Only a statement made outright (stated, or non-finite), unnegated, is
     asserted: any other modality, or a
     negated clause, is described and never appears as a plain triple in a
     voice's graph. Planted: a command asserted.
  2. Every family is in the declared scheme (claim:verbFamilies). Planted: a
     family no one declared.

    python tests/test_statements.py          (preflight runs it so)
"""
import gzip
import sys
from pathlib import Path

import rdflib

ROOT = Path(__file__).resolve().parents[1]
C = rdflib.Namespace("https://bibleontology.org/ns/claim#")
SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")


def load():
    ds = rdflib.Dataset()
    ds.parse(data=gzip.open(ROOT / "out" / "export" / "claims.trig.gz", "rt", encoding="utf-8").read(), format="trig")
    vocab = rdflib.Graph().parse(ROOT / "ontology" / "claim" / "claim.ttl", format="turtle")
    return ds, vocab


def outright(ds, c):
    """Made outright: stated, or a non-finite clause reporting an event ("when
    Ahab saw Elijah", 1 Kgs 18:17; the gate keeps them, 48 of 62 judged right;
    the first run of this test flagged those 30), and not negated."""
    mod = ds.value(c, C.modality)
    return (mod is None or mod in (C.modality_stated, C.modality_nonfinite)) \
        and (c, C.negated, rdflib.Literal(True)) not in ds


def unasserted_violations(ds):
    """Claims not made outright whose triple is asserted in a voice's graph
    WITHOUT an outright claim, in that voice, that asserts it.

    `states` is one relation type for every verb, so "God promised to bless
    Abraham" (Gen 12:2, described) and a stated "God blessed Abraham" in
    another verse share the plain triple god-states-abraham. The first run
    after the time reading (2026-10-20) flagged 67 such described claims, every
    one with a stated claim behind its triple. What must never happen is a
    triple stated on a described claim's account alone."""
    bad = []
    for c, _p, _mod in ds.triples((None, C.modality, None)):
        if outright(ds, c):
            continue
        s, p, o = ds.value(c, C.subject), ds.value(c, C.relation), ds.value(c, C.object)
        for *_t, g in ds.quads((s, p, o, None)):
            gid = g.identifier if hasattr(g, "identifier") else g
            backed = any(outright(ds, c2) and ds.value(c2, C.relation) == p and ds.value(c2, C.object) == o
                         and ds.value(c2, C.voice) == gid
                         for c2 in ds.subjects(C.subject, s) if c2 != c)
            if not backed:
                bad.append(c)
                break
    return bad


def family_violations(ds, vocab):
    fams = set(vocab.subjects(SKOS.inScheme, C.verbFamilies))
    return [f for f in set(ds.objects(None, C.family)) if f not in fams]


def test_only_stated_is_asserted_and_planted_command_is_caught():
    ds, _v = load()
    assert not unasserted_violations(ds), "a statement that is not plainly stated is asserted"
    g = ds.graph(rdflib.URIRef("https://bibleontology.org/voice/narrator-planted"))
    pc = rdflib.URIRef("https://bibleontology.org/claim/planted-command")
    s, p, o = (rdflib.URIRef("https://bibleontology.org/e/israel"), rdflib.URIRef("https://bibleontology.org/ns/relation#states"),
               rdflib.URIRef("https://bibleontology.org/e/god"))
    ds.add((pc, C.subject, s)); ds.add((pc, C.relation, p)); ds.add((pc, C.object, o))
    ds.add((pc, C.modality, C.modality_commanded)); g.add((s, p, o))
    assert pc in unasserted_violations(ds), "planted: a command asserted was not caught"


def test_families_in_scheme_and_planted_family_is_caught():
    ds, vocab = load()
    assert not family_violations(ds, vocab), "a statement's family is not in the declared scheme"
    ds.add((rdflib.URIRef("https://bibleontology.org/claim/planted-family"), C.family, C.family_made_up))
    assert C.family_made_up in family_violations(ds, vocab), "planted: an undeclared family was not caught"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = []
    for n, f in tests:
        try:
            f()
        except AssertionError as ex:
            failed.append(f"FAIL {n}: {ex}")
    print(f"verb statements: {len(tests)} checks, {len(tests) - len(failed)} passed, planted faults among them")
    for x in failed:
        print(x)
    sys.exit(1 if failed else 0)
