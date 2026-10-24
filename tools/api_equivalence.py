"""Does the slimmed server give the same answers as the one it replaces?

2026-10-01: the aim is not to give up functionality blindly, but to consolidate
redundant structure and move to more efficient representations. Every change
to how app2 holds its data is proven here: the server as it stood at a git
revision (default: the tag app2-before-slim) and the server in the working
tree are loaded side by side in ONE process (so set order and hashing agree)
and asked the same questions. Any answer that differs is printed.

    python tools/api_equivalence.py                      # against app2-before-slim
    python tools/api_equivalence.py --rev HEAD~1 --n 400

Needs memory for two servers (about 10 GB at the time of writing).
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_server(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.argv = ["server.py"]
    spec.loader.exec_module(m)
    m.print = lambda *a, **k: None
    return m


def ask(srv, d, fn, q):
    try:
        s = json.dumps(getattr(srv, fn)(d, q), sort_keys=True, ensure_ascii=False, default=str)
    except Exception as e:                       # noqa: BLE001
        return f"ERROR {type(e).__name__}: {e}"
    # stamps tied in weight were listed in set order before 2026-10-01 (it
    # changed with every process); compared as a set, so that fix is not
    # counted as a difference and nothing else can hide behind it
    return re.sub(r"both speak of ([^·\"]+?)(?= ·|\")",
                  lambda m: "both speak of " + ", ".join(sorted(m.group(1).split(", "))), s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev", default="app2-before-slim")
    ap.add_argument("--n", type=int, default=300)
    a = ap.parse_args()
    old_src = subprocess.run(["git", "show", f"{a.rev}:app2/server.py"], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", check=True).stdout
    old_path = ROOT / "app2" / "_server_equivalence_old.py"     # beside it, so ROOT resolves
    old_path.write_text(old_src, encoding="utf-8")
    try:
        old = load_server(old_path, "srv_old")
        new = load_server(ROOT / "app2" / "server.py", "srv_new")
        d_old, d_new = old.load(), new.load()
    finally:
        old_path.unlink(missing_ok=True)

    random.seed(7)
    chapters = [(b, c) for b, cs in d_new["chapters"].items() for c in cs]
    verses = list(d_new["verses"])
    ents = list(d_new["ents"])
    tags = sorted({t["tag"] for ts in new._clause_tags().values() for t in ts})
    qs = (
        [("api_chapter", {"b": [b], "c": [str(c)]}) for b, c in random.sample(chapters, min(a.n, len(chapters)))]
        + [("api_structure", {"b": [b], "c": [str(c)], "v": [str(v)]})
           for (b, c, v) in random.sample(verses, a.n)]
        + [("api_echoes", {"ref": [f"{new.TO_MACULA.get(b, b)}.{c}.{v}"]})
           for (b, c, v) in random.sample(verses, a.n)]
        + [("api_entity", {"id": [i]}) for i in random.sample(ents, a.n)]
        + [("api_tag", {"id": [t]}) for t in random.sample(tags, min(a.n // 3, len(tags)))]
        + [("api_search", {"q": [w]}) for w in ("cross", "shepherd", "love", "Abraham", "grace",
                                                 "living water", "Ps 23", "kingdom", "faith")]
        # what read the clause structure's nodes and edges (2026-10-01: the
        # structure moved to chapter blocks)
        + [("api_unit", {"ref": [f"{new.TO_MACULA.get(b, b)}.{c}.{v}"]})
           for (b, c, v) in random.sample(verses, a.n)]
        + [("api_entity_verses", {"id": [i]}) for i in random.sample(ents, a.n)]
        + [("api_about", {}), ("api_coverage", {})]
        # Explore's Patterns, built from the clause tags (2026-10-14: the tags
        # became slotted records, read a line at a time)
        + [("api_recurs", {}), ("api_patternsets", {})]
        # the word pages: occ (each word's verses and wording) and lemmas
        + [("api_sense", {"key": [k]}) for k in random.sample(sorted(d_new["occ"]), a.n)]
    )
    bad = {}
    # what main() prints at start: len() of each store (2026-10-01: the
    # structure views had no len(), and the server failed at start while
    # every API answer here matched -- this run never called main())
    for k in ("verses", "nodes", "byref", "profiles"):
        try:
            x, y = len(d_old[k]), len(d_new[k])
        except Exception as e:                   # noqa: BLE001
            x, y = len(d_old[k]), f"ERROR {type(e).__name__}"
        if x != y:
            bad.setdefault("len(d[...])", []).append((k, str(x), str(y)))
    for fn, q in qs:
        x, y = ask(old, d_old, fn, q), ask(new, d_new, fn, q)
        if x != y:
            bad.setdefault(fn, []).append((q, x[:200], y[:200]))
    total = len(qs)
    print(f"{total:,} questions, {sum(len(v) for v in bad.values())} answers differ")
    # two identical errors are "equal" and prove nothing: count them
    errs = collections.Counter(fn for fn, q in qs if ask(new, d_new, fn, q).startswith("ERROR"))
    print(f"answers that were errors (both sides alike): {sum(errs.values())} {dict(errs)}")
    for fn, rows in bad.items():
        print(f"  {fn}: {len(rows)}")
        for q, x, y in rows[:2]:
            print("    ", q, "\n       old:", x, "\n       new:", y)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
