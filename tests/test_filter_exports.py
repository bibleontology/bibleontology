"""The filter, published, holds to its policy (plan 8.1f).

  card words   the shown named graph passes the SHACL shape bosh:ShownCardWord,
               and a planted weak word (anchored, share 0.05) fails it; the
               published CONSTRUCT reproduces the shown graph exactly
  ties         each centre's published floor is what the policy's rule gives
               from the published ties, and draws no more than the rank; a
               planted change to one tie's strength is caught

    python tests/test_filter_exports.py          (preflight runs it so)
"""
import gzip
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
import salience  # noqa: E402
from export_ties import floor_for  # noqa: E402

SITE = "https://bibleontology.org"
EXP = ROOT / "out" / "export"


def card_graphs():
    import rdflib
    ds = rdflib.Dataset()
    ds.parse(data=gzip.open(EXP / "card-words.trig.gz", "rt", encoding="utf-8").read(), format="trig")
    return ds, ds.graph(rdflib.URIRef(f"{SITE}/graph/shown-card-words"))


def test_shown_card_words_pass_and_planted_weak_word_fails():
    import rdflib
    from pyshacl import validate
    _ds, shown = card_graphs()
    shapes = rdflib.Graph().parse(ROOT / "ontology" / "meaning" / "shapes.ttl", format="turtle")
    g = rdflib.Graph()
    for t in shown:
        g.add(t)
    ok, _r, text = validate(g, shacl_graph=shapes, advanced=True)
    assert ok, "the shown card words fail the filter policy's shape:\n" + text[:600]
    g.parse(data=f"""@prefix bom: <{SITE}/ns/meaning#> . @prefix dqv: <http://www.w3.org/ns/dqv#> .
        <{SITE}/e/planted#word-h1> a bom:CardWord ; bom:wordBasis "anchored" ; bom:tier bom:default ;
          dqv:hasQualityMeasurement [ dqv:isMeasurementOf bom:cardWordShare ; dqv:value 0.05 ] .""", format="turtle")
    ok2, _r2, _t2 = validate(g, shacl_graph=shapes, advanced=True)
    assert not ok2, "planted: a weak word in the shown graph passed the shape"


def test_construct_reproduces_the_shown_graph():
    import rdflib.compare
    ds, shown = card_graphs()
    built = ds.default_graph.query((EXP / "shown-card-words.rq").read_text(encoding="utf-8")).graph
    assert rdflib.compare.isomorphic(built, shown), "the published CONSTRUCT does not give the shown graph"


def ties_and_floors():
    text = gzip.open(EXP / "ties.trig.gz", "rt", encoding="utf-8").read()
    ties = re.findall(rf"bom:source <{SITE}/e/([^>]+)> ; bom:relation \S+ ; bom:target <{SITE}/e/([^>]+)> ;.*?"
                      r'navigatorTieStrength ; dqv:value "([0-9.]+)"', text, re.S)
    floors = dict(re.findall(rf"<{SITE}/e/([^>]+)> dqv:hasQualityMeasurement \[ a dqv:QualityMeasurement ; "
                             r'dqv:isMeasurementOf bom:navigatorFloor ; dqv:value "([0-9.]+)"', text))
    return [(a, b, float(s)) for a, b, s in ties], {k: float(v) for k, v in floors.items()}


def test_floors_follow_the_rule_and_planted_change_is_caught():
    ties, floors = ties_and_floors()
    rank = salience.entry("navigator_tie_strength")["rank"]["desktop"]
    by = {}
    for a, b, s in ties:
        by.setdefault(a, []).append((a, b, s))
        by.setdefault(b, []).append((a, b, s))
    for c in ("david", "jacob", "moses", "peter", "world"):
        if c not in by:
            continue
        f = floor_for(c, by[c], rank)
        assert abs(f - floors[c]) < 1e-5, f"{c}: published floor {floors[c]} is not the rule's {f}"
        drawn = {c} | {x for a, b, s in by[c] if s >= f for x in (a, b)}
        assert len(drawn) <= rank or len({s for _a, _b, s in by[c]}) == 1, f"{c}: {len(drawn)} records drawn"
    a, b, s = max(by["david"], key=lambda t: t[2])
    planted = [(x, y, (z if (x, y, z) != (a, b, s) else 0.0)) for x, y, z in by["david"]]
    planted += [("david", f"planted{i}", 99.0) for i in range(rank)]
    assert abs(floor_for("david", planted, rank) - floors["david"]) > 1e-5, "planted ties did not move the floor"


def unbacked_statement_ties(text, shown):
    """'states' ties whose two ends no shown statement joins."""
    pairs = re.findall(rf"bom:source <{SITE}/e/([^>]+)> ; bom:relation bor:states ; bom:target <{SITE}/e/([^>]+)>", text)
    return [(a, b) for a, b in pairs if (a, b) not in shown and (b, a) not in shown]


def test_statement_ties_rest_on_what_is_shown():
    """THE PUBLISHED TIES AGAINST THE STORE (the committee's practitioner,
    second sitting): the ties file was last written before the time hold, the
    repairs and the time reading, and 42 of its statement ties rested on
    statements since held or described. The test above checked the file
    against itself; this checks it against what is shown. Planted: a held
    statement's pair."""
    import json
    rows = [json.loads(x) for x in (ROOT / "ontology" / "relations" / "verb-statements.jsonl").read_text(
        encoding="utf-8").splitlines() if x.strip()]
    shown = {(r["src"], r["dst"]) for r in rows if not r.get("held") and not r.get("described")}
    text = gzip.open(EXP / "ties.trig.gz", "rt", encoding="utf-8").read()
    bad = unbacked_statement_ties(text, shown)
    assert not bad, f"{len(bad)} statement ties rest on no shown statement, e.g. {bad[:3]}"
    held = next((r["src"], r["dst"]) for r in rows if r.get("held")
                and (r["src"], r["dst"]) not in shown and (r["dst"], r["src"]) not in shown)
    planted = text + (f"\n<{SITE}/tie/planted> a bom:Tie ; bom:source <{SITE}/e/{held[0]}> ; bom:relation bor:states ; "
                      f"bom:target <{SITE}/e/{held[1]}> ; bom:label \"x\" .\n")
    assert unbacked_statement_ties(planted, shown), "planted: a tie on a held statement was not caught"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = []
    for n, f in tests:
        try:
            f()
        except AssertionError as ex:
            failed.append(f"FAIL {n}: {ex}")
    print(f"filter exports: {len(tests)} checks, {len(tests) - len(failed)} passed, planted faults among them")
    for x in failed:
        print(x)
    sys.exit(1 if failed else 0)
