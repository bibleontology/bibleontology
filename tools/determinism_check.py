"""Is the build deterministic? Build twice under different hash seeds and
compare the graph byte for byte.

2026-09-25: make this a deterministic extraction. The build is rules
over MACULA with no model in it, but rule-based is not the same claim as
deterministic: Python randomises string hashing per process, so any rule
that takes "the first" item of a set — or iterates a set to decide what to
emit — can give a different graph on a different run, silently. This builds
with two fixed, different seeds and fails if the nodes or edges differ.

First run, 2026-09-25: identical (random seed, then 12345).

Run:  python tools/determinism_check.py        (two full builds, ~2 minutes)
"""
import gzip
import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
FILES = ("placeholder-nodes.jsonl.gz", "placeholder-edges.jsonl.gz")


def digest():
    out = {}
    for f in FILES:
        h = hashlib.sha256()
        with gzip.open(OUT / f, "rb") as fh:          # content, not gzip header
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        out[f] = h.hexdigest()
    return out


def build(seed):
    env = dict(os.environ, PYTHONHASHSEED=str(seed),
               PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, str(ROOT / "tools" / "placeholders.py")],
                   env=env, check=True, stdout=subprocess.DEVNULL)
    return digest()


def main():
    a, b = build(1), build(2)
    for f in FILES:
        same = a[f] == b[f]
        print(f"{'same' if same else 'DIFFERENT':<10} {f}  "
              f"{a[f][:16]}  {b[f][:16]}")
    if a != b:
        print("NOT deterministic: find the set or dict whose order decides "
              "what is emitted")
        return 1
    print("ok - the build is deterministic (two hash seeds, identical graph)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
