"""The structure ontology and the graph agree, in both directions (plan 1.42,
2026-10-18).

ontology/kinds.json declares every kind of node and edge the clean builder
makes, with a status that is a fact: built (the graph has it), proposed,
deferred (built by the earlier builder, kept for re-entry), superseded or
withdrawn. tools/ontology.py has always checked this ("CLOSED WORLD"), but it
was never in preflight, and when the builder was replaced the file went on
describing the old graph: 84 disagreements by 2026-10-17, among them 35 kinds
called built that the graph did not have. This runs the same check, without
touching its cached census (a tracked file), and proves itself with planted
faults:
  - a kind declared built that the graph has none of;
  - a kind declared proposed that the graph has;
  - an edge type the file does not declare.
And since plan 1.43 (2026-10-18) the sweep's layer the same way, with three
more planted: an undeclared type in the layer, a proposed kind shown by it, and
a deferred kind it shows whose reason does not say the sweep supplies it.
Run: python tests/test_ontology_closed_world.py   (a few minutes: it reads the
whole graph)"""
import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ontology as O  # noqa: E402

onto = O.load()
c = O.census(force=True, write=False)
faults = O.check(onto, c)

# planted faults must be caught
planted = copy.deepcopy(onto)
planted["relations"].append({"id": "planted_never_built", "label": "planted", "layer": "upper",
                             "from": "Clause", "to": "Clause", "status": "built",
                             "match": {"type": ["planted_never_built"], "flag": "clause_link"}})
q = next(x for x in planted["classes"] if x["id"] == "Question")
q["status"] = "proposed"
planted["relations"].append({"id": "sender", "label": "planted twin", "layer": "upper", "status": "proposed"})
c2 = copy.deepcopy(c)
c2["stray_edges"] = {**c2.get("stray_edges", {}), "planted_stray:clause_link": 3}
c2.setdefault("stray_example", {})["edge:planted_stray:clause_link"] = "X.1.1#cl0 -> X.1.1#cl1"
caught = O.check(planted, c2)
want = ["planted_never_built is declared built", "Question is declared proposed", "planted_stray",
        "sender is declared 2 times"]
missed = [w for w in want if not any(w in f for f in caught)]

# THE READINGS TOO (plan 1.43): the sweep's layer, through the same matchers
lc = O.layer_census(onto)
faults += O.check_layer(onto, lc)
lc2 = copy.deepcopy(lc)
lc2["stray_edges"] = {**lc2["stray_edges"], "planted_layer_stray [clause_link]": 2}
lc2["edges"] = {**lc2["edges"], "heading": 5}          # a proposed kind shown (was `warning`, built 2026-10-18)
p2 = copy.deepcopy(onto)
next(x for x in p2["relations"] if x["id"] == "content")["deferred"] = "planted: no word of who supplies it"
caught2 = O.check_layer(p2, lc2)
want2 = ["planted_layer_stray", "heading is declared proposed and the layer has", "content is deferred"]
missed += [w for w in want2 if not any(w in f for f in caught2)]
want += want2

print(f"{sum(c['nodes'].values()):,} nodes and {sum(c['edges'].values()):,} edges, and "
      f"{sum(lc['nodes'].values()) + sum(lc['edges'].values()):,} layer records, against kinds.json; "
      f"planted faults caught: {len(want) - len(missed)} of {len(want)}; {len(faults)} disagreements")
for f in faults[:12]:
    print("  FAIL", f)
for w in missed:
    print("  FAIL planted fault not caught:", w)
sys.exit(1 if faults or missed else 0)
