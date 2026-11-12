"""The Psalm 73 LRM/LRMoo pilot (P-2026-10-31-2): the fixture's modeling decisions, mapped to N-Triples.

    python tools/lrm_pilot.py [fixture] [out]

Every decision is in the fixture (tests/fixtures/lrm_psalm73.json); this module only maps it to triples. A Work is
not its text: Expressions realise it and Manifestations embody them. A translation is an Expression, never a new
Work, and a collection incorporates its members' texts, never has them as parts. The two texts' verses are separate
segments, aligned, never shared. Each Work Creation has no agent or date, and who composed the psalm, or which Asaph
the superscription names, is described as the editors' claim and never stated.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "lrm_psalm73.json"
DEFAULT_OUT = ROOT / "out" / "lrm" / "psalm73.nt"


def _escape(text):
    """Escape a string for an N-Triples literal."""
    return (text.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r"))


def build(fx):
    """The fixture's triples, each term already in N-Triples form: [(s, p, o)]."""
    ns = fx["ns"]
    base = fx["base"]
    terms = fx["terms"]
    rdf_type = "<" + ns["rdf"] + "type>"
    triples = []

    def iri(value):
        if value.startswith("http"):
            return "<" + value + ">"
        prefix, sep, local = value.partition(":")
        if sep and prefix in ns:
            return "<" + ns[prefix] + local + ">"
        return "<" + base + value + ">"

    def term(value):
        prefix, _, local = value.partition(":")
        return "<" + ns[prefix] + local + ">"

    def label(value):
        return '"' + _escape(value) + '"@en'

    def integer(value):
        return '"' + str(int(value)) + '"^^<' + ns["xsd"] + "integer>"

    def add(s, p, o):
        triples.append((s, p, o))

    # ---- Works: a Work is not its text
    for work in fx["works"]:
        s = iri(work["id"])
        add(s, rdf_type, term(terms["Work"]))
        add(s, term(terms["label"]), label(work["label"]))

    # ---- Expressions: the text in a language, realising the Work; a translation is still an Expression. A
    # collection's Expression incorporates its members' (LRMoo R75): each psalm stays its own Work, never a part
    # (R67) of the Psalter (2026-11-06, the scope notes)
    for expr in fx["expressions"]:
        s = iri(expr["id"])
        add(s, rdf_type, term(terms["Expression"]))
        add(s, term(terms["label"]), label(expr["label"]))
        add(s, term(terms["language"]), '"' + _escape(expr["language"]) + '"')
        add(iri(expr["realises"]), term(terms["is_realised_in"]), s)
        if expr.get("translationOf"):
            add(s, term(terms["translationOf"]), iri(expr["translationOf"]))
        for inner in expr.get("incorporates", []):
            add(s, term(terms["incorporates"]), iri(inner))

    # ---- Manifestations: what embodies an Expression
    for man in fx["manifestations"]:
        s = iri(man["id"])
        add(s, rdf_type, term(terms["Manifestation"]))
        add(s, term(terms["label"]), label(man["label"]))
        for expr in man["embodies"]:
            add(s, term(terms["embodies"]), iri(expr))
        add(s, term(terms["source"]), iri(man["source"]))

    # ---- Segments: 28 per text, each its own Expression's, aligned one to one
    seg = fx["segments"]
    for n in range(1, seg["verses"] + 1):
        hebrew = iri(seg["hebrew"]["id"].format(n=n))
        english = iri(seg["english"]["iri"].format(n=n))
        for s, expr in ((hebrew, seg["hebrew"]["expression"]), (english, seg["english"]["expression"])):
            add(s, rdf_type, term(terms["Segment"]))
            add(s, term(terms["segmentOf"]), iri(expr))
            add(s, term(terms["segmentNumber"]), integer(n))
        add(english, term(terms["alignedWith"]), hebrew)

    # ---- the Work Creations, one per Work (LRMoo R16): what each created, and nothing else
    for creation in fx["workCreations"]:
        s = iri(creation["id"])
        add(s, rdf_type, term(terms["WorkCreation"]))
        add(s, term(terms["created"]), iri(creation["created"]))

    # ---- the arrangement: the Psalter's order, its sections and its entries
    arr = fx["arrangement"]
    a = iri(arr["id"])
    add(a, rdf_type, term(terms["Arrangement"]))
    if arr.get("label"):
        add(a, term(terms["label"]), label(arr["label"]))
    add(a, term(terms["arrangementOf"]), iri(arr["of"]))
    for section in arr.get("sections", []):
        s = iri(section["id"])
        add(s, rdf_type, term(terms["Section"]))
        add(s, term(terms["label"]), label(section["label"]))
        add(s, term(terms["sectionOf"]), a)
        add(s, term(terms["firstPosition"]), integer(section["first"]))
        add(s, term(terms["lastPosition"]), integer(section["last"]))
    for entry in arr.get("entries", []):
        s = iri(entry["id"])
        add(s, rdf_type, term(terms["ArrangementEntry"]))
        add(s, term(terms["member"]), iri(entry["member"]))
        add(s, term(terms["inArrangement"]), a)
        add(s, term(terms["position"]), integer(entry["position"]))
        add(s, term(terms["inSection"]), iri(entry["section"]))
        add(s, term(terms["positionInSection"]), integer(entry["positionInSection"]))

    # ---- the readings: described as claims the editors make, never stated as plain triples
    for claim in fx["claims"]:
        s = iri(claim["id"])
        add(s, rdf_type, term(terms["Claim"]))
        add(s, term(terms["subject"]), iri(claim["subject"]))
        add(s, term(terms["relation"]), term(terms[claim["relation"]]))
        add(s, term(terms["object"]), iri(claim["object"]))
        add(s, term(terms["verse"]), iri(claim["verse"]))
        add(s, term(terms["certainty"]), term(claim["certainty"]))
        add(s, term(terms["voice"]), iri(claim["voice"]))
        if claim.get("label"):
            add(s, term(terms["label"]), label(claim["label"]))

    return triples


def to_ntriples(triples):
    """The triples as N-Triples text: one sorted, unique line each, ending in a newline."""
    lines = sorted({s + " " + p + " " + o + " ." for (s, p, o) in triples})
    return "".join(line + "\n" for line in lines)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    fixture = Path(args[0]) if len(args) > 0 else DEFAULT_FIXTURE
    out = Path(args[1]) if len(args) > 1 else DEFAULT_OUT
    fx = json.loads(fixture.read_text(encoding="utf-8"))
    text = to_ntriples(build(fx))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
