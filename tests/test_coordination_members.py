"""A coordination's members are its conjuncts, never the conjunction (plan
2.15, 2026-10-17).

Greek MACULA wraps every later conjunct with its conjunction,
<wg type="group">καί Ἰωάννην</wg>, and the builder once read that group as a
phrase headed by καί: "Peter and John" (Luke 22:8) had the members Peter and
"and", and was named "Peter and and". 2,188 of 2,433 Greek coordinations were
so, found only when one was read aloud on the divine-flag sheet. This checks,
without the server:
  - the BUILDER: Luke 22:8 built afresh has the members Peter and John;
  - the GRAPH served (out/placeholder-*.jsonl.gz): no coordination has a
    conjunction as a member, but for the two known oddities of another kind
    (KNOWN), and none is named with a doubled conjunction ("X and and");
  - a planted fault is caught: a composite whose member is a conjunction.
Run: python tests/test_coordination_members.py"""
import collections
import gzip
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "builder"))
import source as S0                                        # noqa: E402
from s1_clauses import S1, Tables                          # noqa: E402

# Not this fault: Heb 6:19's "both ... and" spans a whole clause, and Luke
# 7:39's is an ἄν beside a clause. Two of 2,433; left as they are.
KNOWN = {"Heb.6.19#c0", "Luk.7.39#c17"}


def check(nodes, members):
    """Coordinations with a conjunction member, or a doubled last word."""
    bad = []
    for cid, ms in members.items():
        n = nodes.get(cid) or {}
        if not n.get("composite") or cid in KNOWN:
            continue
        cj = [m for m in ms if (nodes.get(m) or {}).get("class") == "cj"]
        if cj:
            bad.append(f"{cid} {n.get('text')!r}: the conjunction {cj[0]} is a member")
        # a conjunction named twice; not any doubled word: "gold gold"
        # (2 Kgs 25:15, Jer 52:19) is the Hebrew's own repetition
        elif re.search(r"\b(and|or|nor|both|neither|also) \1$", n.get("text") or ""):
            bad.append(f"{cid} {n.get('text')!r}: named with a doubled word")
    return bad


fails = []

# the builder, on the verse that found it. It reads MACULA's own files, which a
# public copy fetches only on request (python tools/fetch_macula.py); without
# them this half is skipped, saying so, and the served graph is still checked.
path = next((p for p in S0.files("greek") if "luke" in p.name), None)
if path is None:
    print("skipped the builder half: MACULA's files are not here (python tools/fetch_macula.py)")
else:
    root, words = S0.load(path, "greek")
    s1 = S1(words, "greek", Tables("greek"))
    vs = s1.run(root)
    v = vs["Luk.22.8"]
    got = sorted(e["dst"] for e in v.edges if e["type"] == "member" and e["src"] == "Luk.22.8#c2")
    if got != ["Luk.22.8#w2", "Luk.22.8#w4"]:
        fails.append(f"Luke 22:8 built afresh: members {got}, not Peter (w2) and John (w4)")
    if v.nodes.get("Luk.22.8#c2", {}).get("text") != "Peter and John":
        fails.append(f"Luke 22:8 built afresh: named {v.nodes.get('Luk.22.8#c2', {}).get('text')!r}")

# the graph served
nodes = {}
with gzip.open(ROOT / "out" / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        if d.get("composite") or d.get("class") == "cj":
            nodes[d["id"]] = d
members = collections.defaultdict(list)
with gzip.open(ROOT / "out" / "placeholder-edges.jsonl.gz", "rt", encoding="utf-8") as f:
    for line in f:
        e = json.loads(line)
        if e.get("type") == "member":
            members[e["src"]].append(e["dst"])
found = check(nodes, members)
fails += found[:8] + ([f"... and {len(found) - 8} more"] if len(found) > 8 else [])
n_coord = sum(1 for c in members if (nodes.get(c) or {}).get("composite"))

# a planted fault must be caught
planted = check({"X.1.1#c0": {"composite": True, "text": "Peter and John"},
                 "X.1.1#w1": {"class": "cj"}}, {"X.1.1#c0": ["X.1.1#w0", "X.1.1#w1"]})
if not planted:
    fails.append("planted fault (a conjunction as a member) was not caught")

print(f"{n_coord:,} coordinations, Luke 22:8 built afresh; planted fault caught: {bool(planted)}; "
      f"{len(fails)} failures")
for f in fails:
    print("  FAIL", f)
sys.exit(1 if fails else 0)
