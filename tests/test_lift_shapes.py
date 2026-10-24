"""The 1.2.0 shape against one worked example of each lift (plan 8.1e item 5).

ontology/claim/examples-lifts.trig holds one claim per lift of plan 2.19, on
real verses and records. This checks, each with a planted fault:

  1. Every claim:, bor: and bos: term the examples use is declared today.
     The terms the shape lacks are written gap:, and must be exactly the gaps
     docs/review/lift-shapes-1.2.0.md lists: a gap closed or a new one found
     is noticed here, not later.
  2. Every e: record the examples use exists.
  3. The claims conform to the claim shapes (the ones on a gap relation aside).
  4. A claim's triple is stated in a graph exactly when the export's own rule
     (tools/export_claims.asserted) says it is made outright: the command and
     the prediction are described and never stated.

    python tests/test_lift_shapes.py          (preflight runs it so)
"""
import json
import re
import sys
from pathlib import Path

import pyshacl
import rdflib
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from export_claims import BOR as BOR_NS, asserted, stated  # noqa: E402

CLAIM = "https://bibleontology.org/ns/claim#"
BOR = "https://bibleontology.org/ns/relation#"
BOS = "https://bibleontology.org/ns/structure#"
GAP = "https://bibleontology.org/ns/proposed#"
E = "https://bibleontology.org/e/"
C = rdflib.Namespace(CLAIM)
# the gaps docs/review/lift-shapes-1.2.0.md proposed (G1, G2, G4) were
# approved on the refreshed inventory (2026-10-20) and are now declared terms:
# none is left. A new gap written gap: in the examples fails until decided
GAPS = set()
STRUCT = "https://bibleontology.org/structure/"
EXAMPLES = ROOT / "ontology" / "claim" / "examples-lifts.trig"


def load(text=None):
    ds = rdflib.Dataset()
    ds.parse(data=text if text is not None else EXAMPLES.read_text(encoding="utf-8"), format="trig")
    return ds


def declared():
    claim = {str(s) for s in rdflib.Graph().parse(ROOT / "ontology" / "claim" / "claim.ttl").subjects()}
    types = (yaml.safe_load((ROOT / "ontology/schema/relationship_types.yaml").read_text(encoding="utf-8"))
             .get("types") or {})
    bor = {BOR + k for k in types}
    bos = {str(s) for s in rdflib.Graph().parse(ROOT / "out" / "ns" / "structure.ttl").subjects()}
    return claim | bor | bos


def terms(ds):
    out = set()
    for s, p, o, _g in ds.quads((None, None, None, None)):
        for t in (p, o) if not isinstance(o, rdflib.Literal) else (p,):
            out.add(str(t))
        out.add(str(s))
    return out


def undeclared(ds, known):
    return sorted(t for t in terms(ds) if t.startswith((CLAIM, BOR, BOS)) and t not in known)


def gaps(ds):
    return {t[len(GAP):] for t in terms(ds) if t.startswith(GAP)}


def missing_records(ds):
    have = {json.loads(x)["id"] for x in open(ROOT / "ontology" / "entities" / "entities.jsonl", encoding="utf-8")}
    return sorted(t for t in terms(ds) if t.startswith(E) and t[len(E):] not in have)


def macula_addresses(ds):
    """Structure addresses not in the verse pages' book codes (G5): a clause
    must join its verse without a table."""
    from derive import BOOK
    site = set(BOOK)
    return sorted(t for t in terms(ds) if t.startswith(STRUCT) and t[len(STRUCT):].split(".")[0] not in site)


def as_export(ds, c):
    """The claim as the export's rule sees it: its certainty (plan 8.3f) and,
    for a verb statement, its force."""
    cert = ds.value(c, C.certainty)
    out = {"c": str(cert).split("#")[-1]} if cert is not None else {}
    mod = ds.value(c, C.modality)
    if mod is None:
        return out
    name = str(mod).split("#")[-1].removeprefix("modality_").replace("_", " ")
    return {**out, "st": {"modality": name, "negated": (c, C.negated, rdflib.Literal(True)) in ds}}


def stated_wrongly(ds):
    """Claims whose triple's presence in a graph disagrees with the export's rule."""
    bad = []
    for c in set(ds.subjects(rdflib.RDF.type, C.Claim)):
        s, p, o = ds.value(c, C.subject), ds.value(c, C.relation), ds.value(c, C.object)
        written = any(True for _ in ds.quads((s, p, o, None)))
        if written != stated({**as_export(ds, c), "p": str(p)}):
            bad.append(str(c))
    return sorted(bad)


def failures():
    out = []
    ds, known = load(), declared()
    u = undeclared(ds, known)
    if u:
        out.append(f"undeclared terms: {u}")
    planted = load(EXAMPLES.read_text(encoding="utf-8").replace("claim:modality_commanded", "claim:modality_comanded"))
    if "https://bibleontology.org/ns/claim#modality_comanded" not in undeclared(planted, known):
        out.append("planted: a misspelled modality was not caught")
    g = gaps(ds)
    if g != GAPS:
        out.append(f"the gaps changed: {sorted(g - GAPS)} new, {sorted(GAPS - g)} closed "
                   "(update docs/review/lift-shapes-1.2.0.md and GAPS)")
    m = missing_records(ds)
    if m:
        out.append(f"records that do not exist: {m}")
    a = macula_addresses(ds)
    if a:
        out.append(f"structure addressed with another book code: {a}")
    if not macula_addresses(load(EXAMPLES.read_text(encoding="utf-8").replace("structure/John.3.16#cl0",
                                                                               "structure/Jhn.3.16#cl0"))):
        out.append("planted: a MACULA book code in a structure address was not caught")
    # shapes, over the claims whose relation is declared
    g1 = rdflib.Graph()
    skip = {c for c in ds.subjects(C.relation, None) if str(ds.value(c, C.relation)).startswith(GAP)}
    for t in ds.triples((None, None, None)):
        if t[0] not in skip:
            g1.add(t)
    shapes = rdflib.Graph().parse(ROOT / "ontology" / "claim" / "shapes.ttl")
    ok, _, text = pyshacl.validate(g1, shacl_graph=shapes, inference="none")
    if not ok:
        out.append("the examples do not conform:\n" + text[:800])
    w = stated_wrongly(ds)
    if w:
        out.append(f"stated against the rule: {w}")
    text = EXAMPLES.read_text(encoding="utf-8").replace("voice:moses {\n}",
                                                       "voice:moses {\n    e:children_of_israel bor:states e:god .\n}")
    if "https://bibleontology.org/claim/example-command" not in stated_wrongly(load(text)):
        out.append("planted: a command stated in its speaker's graph was not caught")
    # plan 8.3f, "states: A": a verb statement made outright is described and
    # still never stated, its relation having no verb
    text = EXAMPLES.read_text(encoding="utf-8").replace("claim:narrator {\n",
                                                       "claim:narrator {\n    e:god bor:states e:world .\n")
    if not stated_wrongly(load(text)):
        out.append("planted: a bor:states triple in the narrator's graph was not caught")
    for d, want in (({"p": BOR_NS + "states"}, False), ({"p": BOR_NS + "father_of"}, True),
                    ({"p": BOR_NS + "states", "st": {"modality": "stated"}}, False)):
        if stated(d) != want:
            out.append(f"the export's triple rule: {d} gave {not want}")
    # the export's rule itself, on each kind of statement
    for d, want in (({}, True), ({"st": {"modality": "stated"}}, True), ({"st": {"modality": "nonfinite"}}, True),
                    ({"st": {"modality": "commanded"}}, False), ({"st": {"modality": "promised"}}, False),
                    ({"st": {"modality": "stated", "negated": True}}, False),
                    ({"st": {"modality": "stated", "time": "future (by form)"}}, False),
                    ({"st": {"modality": "stated", "time": "yiqtol: not decided by form"}}, False),
                    ({"st": {"modality": "stated", "time": "past or present (by reading)"}}, True),
                    ({"st": {"modality": "foretold", "time": "yiqtol: not decided by form; read as foretold"}}, False),
                    # plan 8.3f: a conjecture is never stated, whatever its force
                    ({"c": "implied"}, True), ({"c": "conjectured"}, False), ({"c": "disputed"}, False),
                    ({"c": "conjectured", "st": {"modality": "stated"}}, False)):
        if asserted(d) != want:
            out.append(f"the export's rule: {d} gave {not want}")
    return out, len(set(ds.subjects(rdflib.RDF.type, C.Claim)))


if __name__ == "__main__":
    fails, n = failures()
    print(f"lift shapes: {n} worked claims, {len(GAPS)} gaps named, "
          f"{'all checks passed' if not fails else str(len(fails)) + ' failed'}, planted faults among them")
    for f in fails:
        print("FAIL " + f)
    sys.exit(1 if fails else 0)
