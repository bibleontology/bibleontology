"""THE NAVIGATOR'S TIES, PUBLISHED WITH THEIR STRENGTH (plan 8.1f item 3;
2026-10-19: card words + navigator).

The navigator draws, around a centre, the strongest ties first (about twenty-one
records), and a slider shows the rest. Here that becomes data:

  bom:Tie            two records and a relation type, as the navigator draws it:
                     bom:source, bom:relation, bom:target, and its strength as a
                     dqv:QualityMeasurement of bom:navigatorTieStrength
  a record's floor   the strength floor the policy's rule gives that record as a
                     centre, as a dqv:QualityMeasurement of bom:navigatorFloor
  the default view   out/export/navigator-default.rq: the ties touching ?centre
                     whose strength is at least the centre's floor

Computed with the SERVER'S OWN functions (app2/server.py: load, _graph_ix,
_shared, the relation weights) and the policy's numbers (salience.json), so the
published strength is the navigator's, not a second copy of it. A speaker's
claim and an inferred sibling are not ties here, as the navigator draws neither
as the narrator's.

    python tools/export_ties.py   -> out/export/ties.trig.gz, out/export/navigator-default.rq
"""
import collections
import gzip
import hashlib
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
sys.path.insert(0, str(ROOT / "tools" / "meaning"))
sys.path.insert(0, str(ROOT / "tools"))
from ns_common import export_rights, gz_text  # noqa: E402
import salience  # noqa: E402

SITE = "https://bibleontology.org"
OUT = ROOT / "out" / "export"
QUERY = f"""PREFIX bom: <{SITE}/ns/meaning#>
PREFIX dqv: <http://www.w3.org/ns/dqv#>
# The navigator's first view around ?centre (bind it, e.g. <{SITE}/e/david>):
# every tie touching the centre whose strength is at least the centre's floor,
# the floor being the policy's rule (ontology/schema/salience.json) applied to
# that centre: the lowest strength that keeps the drawing to its rank of records.
# Two records joined by several relations are drawn as one line, the strongest;
# the records are the same either way (David: 85 ties, 20 records around him,
# 21 drawn, floor 5.413942, equal to the navigator's own, 2026-10-19).
SELECT ?tie ?other ?strength WHERE {{
  ?centre dqv:hasQualityMeasurement [ dqv:isMeasurementOf bom:navigatorFloor ; dqv:value ?floor ] .
  {{ ?tie bom:source ?centre ; bom:target ?other }} UNION {{ ?tie bom:target ?centre ; bom:source ?other }}
  ?tie dqv:hasQualityMeasurement [ dqv:isMeasurementOf bom:navigatorTieStrength ; dqv:value ?strength ] .
  FILTER (?strength >= ?floor)
}} ORDER BY DESC(?strength)
"""


def strength(certainty, weight, sv, sc, p):
    cf = p["certainty_factor"].get(certainty, p["certainty_factor_default"])
    w = weight if weight is not None else p["weight_default"]
    return cf * (w * p["weight_coefficient"] + math.log2(1 + sv + sc * p["chapter_weight"]) * p["shared_coefficient"])


def floor_for(centre, touching, ceiling):
    """The navigator's autoFloor (kgnAutoFloor): the lowest strength level that
    keeps the centre and the records it ties to within the ceiling; a tier of
    equal strengths kept or dropped whole."""
    def nodes_at(f):
        ids = {centre}
        for a, b, s in touching:
            if s >= f:
                ids.add(a)
                ids.add(b)
        return len(ids)
    if nodes_at(0) <= ceiling:
        return 0.0
    levels = sorted({s for _a, _b, s in touching})
    for lv in levels:
        if nodes_at(lv) <= ceiling:
            return lv
    return levels[-1] if levels else 0.0


def main():
    import server as S
    d = S.load()
    ix = S._graph_ix(d)
    nav = salience.entry("navigator_tie_strength")
    p, ceiling = nav["parameters"], nav["rank"]["desktop"]
    drawable = lambda x: (d["ents"].get(x) or {}).get("type") in S.GRAPH_TYPES  # noqa: E731
    ties, seen = [], set()
    for a in sorted(d["rels"]):
        if not drawable(a):
            continue
        for r in d["rels"][a]:
            if r["dir"] != "out" or r.get("claimed_by") or not drawable(r["other"]):
                continue
            label = r.get("label_out")
            key = (a, r["type"], r["other"], label)       # as api_graph dedupes its edges
            if key in seen:
                continue
            seen.add(key)
            spec = d["cats"].get(r["type"], {})
            sv, sc = S._shared(ix, a, r["other"])
            s = round(strength(r.get("certainty") or "explicit", spec.get("weight"), sv, sc, p), 6)
            ties.append((a, r["type"], r["other"], label, s))
    by_centre = collections.defaultdict(list)
    for a, _t, b, _l, s in ties:
        by_centre[a].append((a, b, s))
        by_centre[b].append((a, b, s))
    floors = {c: floor_for(c, tt, ceiling) for c, tt in by_centre.items()}
    lines = [f"@prefix bom: <{SITE}/ns/meaning#> .", "@prefix dqv: <http://www.w3.org/ns/dqv#> .",
             f"@prefix bor: <{SITE}/ns/relation#> .", "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .", ""]
    for a, t, b, label, s in ties:
        tid = hashlib.sha1(f"{a}|{t}|{b}|{label or ''}".encode()).hexdigest()[:16]
        lines.append(f"<{SITE}/tie/{tid}> a bom:Tie ; bom:source <{SITE}/e/{a}> ; bom:relation bor:{t} ; "
                     f"bom:target <{SITE}/e/{b}> ;" + (f" bom:label {json_lit(label)} ;" if label else "")
                     + f"\n    dqv:hasQualityMeasurement [ a dqv:QualityMeasurement ; dqv:isMeasurementOf "
                       f"bom:navigatorTieStrength ; dqv:value \"{s}\"^^xsd:decimal ] .")
    for c, f in sorted(floors.items()):
        lines.append(f"<{SITE}/e/{c}> dqv:hasQualityMeasurement [ a dqv:QualityMeasurement ; dqv:isMeasurementOf "
                     f"bom:navigatorFloor ; dqv:value \"{round(f, 6)}\"^^xsd:decimal ] .")
    OUT.mkdir(parents=True, exist_ok=True)
    with gz_text(OUT / "ties.trig.gz") as fh:
        fh.write(f"# The navigator's ties and each centre's floor, under the declared policy (rank {ceiling}).\n"
                 + "\n".join(export_rights()) + "\n" + "\n".join(lines) + "\n")
    (OUT / "navigator-default.rq").write_text(QUERY, encoding="utf-8")
    dv = [x for x in by_centre.get("david", []) if x[2] >= floors.get("david", 0)]
    print(f"{len(ties):,} ties; floors for {len(floors):,} centres; david: floor {floors.get('david')}, "
          f"{len(dv)} ties, {len({y for a, b, _s in dv for y in (a, b)})} records drawn")


def json_lit(s):
    import json
    return json.dumps(s, ensure_ascii=False)


if __name__ == "__main__":
    main()
