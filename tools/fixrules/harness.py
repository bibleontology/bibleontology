"""Claude's side of the plug-in loop (NOT released): load the built graph,
run a rule without writing, reproduce a built pass, sample hits to judge.

    python tools/fixrules/harness.py reproduce      # the worked examples
    python tools/fixrules/harness.py sample NAME [--n 16] [--folder rules]
"""
import argparse
import collections
import gzip
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from fixrules import framework as F                       # noqa: E402

OUT = ROOT / "out"


def load_graph(lang="hebrew"):
    nodes, edges = [], []
    for f, into in (("placeholder-nodes.jsonl.gz", nodes),
                    ("placeholder-edges.jsonl.gz", edges)):
        for l in gzip.open(OUT / f, "rt", encoding="utf-8"):
            r = json.loads(l)
            if r.get("lang") == lang:
                into.append(r)
    return nodes, edges


def load_text():
    moved = json.load(open(OUT / "versemap.json", encoding="utf-8")) \
        .get("moved", {})
    back = {v: k for k, v in moved.items()}
    bsb, words = {}, {}
    for l in gzip.open(OUT / "bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(l)
        if r.get("ref") and r.get("text"):
            bsb[back.get(r["ref"], r["ref"])] = (r["text"], r.get("spans")
                                                 or [])
    for l in gzip.open(OUT / "interlinear.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(l)
        if r.get("ref"):
            words[r["ref"]] = r["words"]
    return bsb, words


def reproduce():
    """Each worked example must re-find what the built pass found."""
    nodes, edges = load_graph()
    bsb, words = load_text()
    cases = {"gapped_verb": lambda e: e.get("inferred") ==
             "the verb of the line before, gapped",
             "bsb_pronoun": lambda e: e.get("reading") == "BSB" and
             e.get("type") == "refers_to"}
    for m in F.load(folder=ROOT / "tools/fixrules/examples"):
        built = [e for e in edges if cases[m.NAME](e)]
        want = {(e["src"], e["type"], e["dst"]) for e in built}
        rest = [e for e in edges if not cases[m.NAME](e)]
        r = F.run([m], nodes, rest, bsb=bsb, words=words)[m.NAME]
        got = {(c.kw["src"], c.kw["type"], c.kw["dst"])
               for _, _, cs in r["fixed"] for c in cs}
        print(f"{m.NAME}: built {len(want)}, plug-in {len(got)}, both "
              f"{len(want & got)}, only built {len(want - got)}, only "
              f"plug-in {len(got - want)}; detected {len(r['detected'])}, "
              f"invalid {len(r['invalid'])}, rejected {len(r['rejected'])}")
        for x in sorted(want - got)[:3]:
            print("   only built:", x)
        for x in sorted(got - want)[:3]:
            print("   only plug-in:", x)
        for x in (r["invalid"] + r["rejected"])[:3]:
            print("   refused:", x)


def sample(name, n, folder, detect_only):
    """A seeded sample to judge: of detections (before any fix is written)
    or of fixes."""
    nodes, edges = load_graph()
    bsb, words = load_text()
    ms = F.load([name], folder=ROOT / "tools/fixrules" / folder)
    r = F.run(ms, nodes, edges, bsb=bsb, words=words,
              detect_only=detect_only)[name]
    print(f"{name}: detected {len(r['detected'])}, fixed {len(r['fixed'])}, "
          f"invalid {len(r['invalid'])}, rejected {len(r['rejected'])}")
    pool = r["detected"] if detect_only else r["fixed"]
    for x in random.Random(20260926).sample(pool, min(n, len(pool))):
        print(f"\n{x[0]}  {bsb.get(x[0], ('',))[0]}")
        print("    found:", x[1].get("why"))
        for c in (x[2] if len(x) > 2 else []):
            print("   ", c)
    for x in (r["invalid"] + r["rejected"])[:5]:
        print("\nrefused:", x[0], x[2])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("name", nargs="?")
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--folder", default="rules")
    ap.add_argument("--detect", action="store_true",
                    help="sample detections only, before any fix")
    a = ap.parse_args()
    if a.cmd == "reproduce":
        reproduce()
    else:
        sample(a.name, a.n, a.folder, a.detect)
