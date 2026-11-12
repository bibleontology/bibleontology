"""/ns/biblio and its shapes (plan 8.1g step 2, 2026-11-06), checked on the Psalm 73 pilot.

  1. The vocabulary: every biblio: term the pilot or the shapes use is defined in ontology/biblio/biblio.ttl, with a
     label and a definition, and the file defines nothing the pilot does not use (its terms are only the published
     data's). translationOf is declared a subproperty of LRMoo's R76.
  2. The pilot (tools/lrm_pilot.py on tests/fixtures/lrm_psalm73.json) conforms to the published shapes: the biblio
     shapes and the claim shapes, run with pyshacl, inference off.
  3. Every rule is proven by a planted fault, each added alone, each of which must make the pilot fail: authorship
     stated; an agent on a creation event; an Expression with a second language; a Work typed an Expression; a
     certainty outside the four; the psalm a part (R67) of the Psalter; the Psalter with no creation event; a
     translation of another Work's text; an Expression incorporating one of its own Work; a segment aligned within
     one text; a section that ends before it begins; an entry outside its section; a claim relation outside the
     vocabularies.

Run: python -X utf8 tests/test_biblio_shapes.py"""
import json
import sys
from pathlib import Path

import pyshacl
import rdflib
import rdflib.compare

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import lrm_pilot  # noqa: E402

BIBLIO = "https://bibleontology.org/ns/biblio#"
LRMOO = "http://iflastandards.info/ns/lrm/lrmoo/"
SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
FX = json.loads((ROOT / "tests" / "fixtures" / "lrm_psalm73.json").read_text(encoding="utf-8"))
fails = []

vocab = rdflib.Graph().parse(ROOT / "ontology" / "biblio" / "biblio.ttl", format="turtle")
shapes = rdflib.Graph().parse(ROOT / "ontology" / "biblio" / "shapes.ttl", format="turtle")
shapes.parse(ROOT / "ontology" / "claim" / "shapes.ttl", format="turtle")
pilot_text = lrm_pilot.to_ntriples(lrm_pilot.build(FX))
pilot = rdflib.Graph().parse(data=pilot_text, format="nt")

# ---- 1. the vocabulary
defined = {str(s) for s in vocab.subjects() if str(s).startswith(BIBLIO)}


def used(g):
    return {str(x) for t in g for x in t if isinstance(x, rdflib.URIRef) and str(x).startswith(BIBLIO)}


in_shapes = {t for t in used(shapes) if not t.startswith("https://bibleontology.org/ns/biblio/shapes#")}
for t in sorted((used(pilot) | in_shapes) - defined):
    fails.append(f"vocabulary: {t} is used and not defined in biblio.ttl")
for t in sorted(defined - used(pilot)):
    fails.append(f"vocabulary: {t} is defined but the published data does not use it")
for t in sorted(defined):
    s = rdflib.URIRef(t)
    if not vocab.value(s, rdflib.RDFS.label) or not vocab.value(s, SKOS.definition):
        fails.append(f"vocabulary: {t} lacks a label or a definition")
if (rdflib.URIRef(BIBLIO + "translationOf"), rdflib.RDFS.subPropertyOf,
        rdflib.URIRef(LRMOO + "R76_is_derivative_of")) not in vocab:
    fails.append("vocabulary: translationOf is not declared a subproperty of LRMoo R76")


# ---- 2. the pilot conforms
def conforms(g):
    return pyshacl.validate(g, shacl_graph=shapes, inference="none", advanced=True)


ok, _, report = conforms(pilot)
if not ok:
    fails.append("the pilot does not conform to the published shapes:\n" + report[:3000])


# ---- 3. planted faults: each must fail
def I(x):
    return f"<{FX['base']}{x}>"


def T(p, local):
    return f"<{FX['ns'][p]}{local}>"


W73, PSALTER = I("work/psalm-73"), I("work/psalter")
ASAPH = "<https://bibleontology.org/e/asaph_singer>"
TYPE = T("rdf", "type")
CRM_P14 = "<http://www.cidoc-crm.org/cidoc-crm/P14_carried_out_by>"


def without(*bits):
    """The pilot with every line holding one of bits removed. Each bit must remove a line, or the plant beside it
    would be caught for the wrong reason (a second value, not the bad one)."""
    lines = [l for l in pilot_text.split("\n") if l]
    for b in bits:
        if not any(b in l for l in lines):
            fails.append(f"planted: {b!r} removes nothing from the pilot")
    return "".join(l + "\n" for l in lines if not any(b in l for b in bits))


PLANTS = [
    ("authorship stated", pilot_text + f"{W73} {T('biblio', 'composedBy')} {ASAPH} .\n"),
    ("an agent on the creation event", pilot_text + f"{I('event/psalm-73-creation')} {CRM_P14} {ASAPH} .\n"),
    ("an Expression with a second language",
     pilot_text + f'{I("expr/psalm-73-bsb")} {T("dcterms", "language")} "de" .\n'),
    ("a Work typed an Expression", pilot_text + f"{W73} {TYPE} {T('lrmoo', 'F2_Expression')} .\n"),
    ("a certainty outside the four",
     without("psalm-73-composer> <" + FX["ns"]["claim"] + "certainty>")
     + f"{I('claim/psalm-73-composer')} {T('claim', 'certainty')} {T('claim', 'certain')} .\n"),
    ("the psalm a part (R67) of the Psalter", pilot_text + f"{PSALTER} {T('lrmoo', 'R67_has_part')} {W73} .\n"),
    ("the Psalter with no creation event", without("psalter-creation")),
    ("a translation of another Work's text",
     without(I("expr/psalm-73-bsb") + " " + T("biblio", "translationOf"))
     + f"{I('expr/psalm-73-bsb')} {T('biblio', 'translationOf')} {I('expr/psalter-hebrew')} .\n"),
    ("an Expression incorporating one of its own Work",
     pilot_text + f"{I('expr/psalter-bsb')} {T('lrmoo', 'R75_incorporates')} {I('expr/psalter-hebrew')} .\n"),
    ("a segment aligned within one text",
     pilot_text + f"<https://bibleontology.org/p/Ps.73.1> {T('biblio', 'alignedWith')} <https://bibleontology.org/p/Ps.73.2> .\n"),
    ("a section that ends before it begins",
     without("book-3> " + T("biblio", "lastPosition"))
     + f'{I("arr/psalter-mt/book-3")} {T("biblio", "lastPosition")} "72"^^{T("xsd", "integer")} .\n'),
    ("an entry outside its section",
     without("entry-73> " + T("biblio", "position") + " ")
     + f'{I("arr/psalter-mt/entry-73")} {T("biblio", "position")} "90"^^{T("xsd", "integer")} .\n'),
    ("a claim relation outside the vocabularies",
     without("psalm-73-composer> " + T("claim", "relation"))
     + f"{I('claim/psalm-73-composer')} {T('claim', 'relation')} {T('biblio', 'authoredBy')} .\n"),
]
caught = 0
for what, text in PLANTS:
    g = rdflib.Graph().parse(data=text, format="nt")
    if rdflib.compare.isomorphic(g, pilot):
        fails.append(f"planted: {what}: the plant changed nothing")
        continue
    if conforms(g)[0]:
        fails.append(f"planted: {what} was not caught")
    else:
        caught += 1

for m in fails:
    print("FAIL", m)
print(f"/ns/biblio: {len(defined)} terms; the pilot ({len(pilot)} triples) "
      f"{'conforms' if ok else 'does NOT conform'}; planted faults caught: {caught} of {len(PLANTS)}; "
      f"{len(fails)} failures")
sys.exit(1 if fails else 0)
