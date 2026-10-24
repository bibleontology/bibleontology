"""The verse-to-verse matches, rolled up once, in the form the reader uses.

Why it exists (docs/LAUNCH.md, plan A.20 proposed): app2 rolled 303,447
clause pairs (out/aligned.jsonl.gz) up into verse pairs at every start,
holding every pair as a full record -- 1.1 GB of a 4.8 GB server -- when the
connections panel only ever shows pairs at or above ALIGN_MIN whose forces
line up, and reads a dozen of each pair's fields. 2026-10-01: functionality
is not to be given up blindly; redundant structure is consolidated into more
efficient representations.

So the roll-up is the SERVER'S OWN (app2/server.py `_load_aligned`, imported,
not copied, so the two cannot drift), run here once; then only the pairs the
panel's own first filters keep, and only the fields it reads, are written.
The server loads this file when it is present and is newer than its inputs;
otherwise it rolls up as before.

    python tools/patterns/aligned_verses.py           # writes out/aligned-verses.jsonl.gz
    python tools/patterns/aligned_verses.py --check   # same answers? (api_echoes, both ways)

Rebuild after aligned.jsonl.gz, trim.jsonl.gz or clause-tags.jsonl.gz
changes (the server warns when it is older than any of them).
"""
from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
DEST = OUT / "aligned-verses.jsonl.gz"
INPUTS = [OUT / "aligned.jsonl.gz", OUT / "trim.jsonl.gz", OUT / "clause-tags.jsonl.gz"]
# every field api_echoes, _aligned_how and connected() read from a pair
FIELDS = ("score", "tier", "force", "verb", "obj", "neg", "stamps", "trim",
          "clauses", "of", "doer")


def server():
    spec = importlib.util.spec_from_file_location("srv", ROOT / "app2" / "server.py")
    srv = importlib.util.module_from_spec(spec)
    sys.argv = ["server.py"]
    spec.loader.exec_module(srv)
    srv.print = lambda *a, **k: None
    return srv


def keep(srv, r):
    """The panel's own first two filters (api_echoes), nothing else: a pair
    below ALIGN_MIN, or matched only through similar words with forces that
    differ, is never shown, never earns the chip, and never reaches a thread."""
    if r["score"] < srv.ALIGN_MIN:
        return False
    return r.get("tier") in ("same", "contrast") or r["force"][0] == r["force"][1]


def build():
    srv = server()
    rolled = srv._load_aligned(precomputed=False)
    n_in = sum(len(v) for v in rolled.values())
    n_out = 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        # the inputs' fingerprints, first: the server compares them, not file
        # times (a git checkout gives every file a fresh, arbitrary time)
        f.write(json.dumps({"_inputs": srv.aligned_inputs()}) + "\n")
        for a in sorted(rolled):
            pairs = {b: {k: r[k] for k in FIELDS if k in r}
                     for b, r in rolled[a].items() if keep(srv, r)}
            if pairs:
                f.write(json.dumps({"v": a, "pairs": pairs}, ensure_ascii=False,
                                   separators=(",", ":")) + "\n")
                n_out += len(pairs)
    print(f"verse pairs rolled up {n_in:,}; kept {n_out:,}; wrote {DEST.relative_to(ROOT)}")


def check(n=1500):
    """The same answers both ways: api_echoes and connected() for a sample of
    verses with the rolled-up-at-start representation and with this file."""
    srv = server()
    d = srv.load()
    full = srv._load_aligned(precomputed=False)
    slim = srv._load_aligned(precomputed=True)
    refs = sorted(set(full) | set(slim))
    random.seed(1)
    sample = random.sample(refs, min(n, len(refs)))
    # connected() over the whole canon, once per representation: every verse,
    # not a sample -- it is the chip's yes/no for all 31,102
    conn = []
    for rep in (full, slim):
        d["aligned"] = rep
        d.pop("_connected", None)
        conn.append(set(srv.connected(d)))
    print(f"connections chip: {len(conn[0]):,} verses either way; "
          f"{len(conn[0] ^ conn[1])} differ")
    bad = len(conn[0] ^ conn[1])
    answers = []
    for rep in (full, slim):
        d["aligned"] = rep
        answers.append([json.dumps(srv.api_echoes(d, {"ref": [r]}), sort_keys=True,
                                   ensure_ascii=False) for r in sample])
    diff = [r for r, x, y in zip(sample, *answers) if x != y]
    for r in diff[:5]:
        print("DIFFERS", r)
    print(f"api_echoes: {len(sample):,} verses checked; {len(diff)} differ")
    return bad + len(diff)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    sys.exit(1 if check() else 0) if a.check else build()
