"""The UBS fetch's pins hold (2026-11-04): tools/fetch_ubs.py --local, run against a copy of data/raw/ubs/.

    python -X utf8 tests/test_fetch_ubs.py

The server builds the UBS extracts itself (the text is CC BY-SA and never committed), so the pins in fetch_ubs.py
are the only thing that says the server shows what was checked here. This proves, without a download:
  1. the files on this machine match every pinned hash, and the extractor rebuilds both extracts to theirs (a change
     to tools/lexicon/ubs_extract.py fails here, before a push, not on the server);
  2. a changed byte in any source refuses, and writes nothing (planted);
  3. a changed extractor output refuses, and writes nothing (planted).
Skipped where data/raw/ubs/ is absent: the public copy, and a worktree it was not copied to.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import fetch_ubs as F  # noqa: E402

if not all((F.DEST / n).exists() for n in F.SOURCES):
    print("skipped: data/raw/ubs/ is not on this machine (it is git-ignored; copy it from a worktree that has it)")
    sys.exit(0)

fails = []


def run(dest):
    """main(--local) against dest; True if it refused. Nothing is printed unless it fails."""
    F.DEST = dest
    try:
        F.main(["--local"])
        return False
    except SystemExit:
        return True
    except subprocess.CalledProcessError:
        return True


def snapshot(d):
    return {p.name: p.read_bytes() for p in d.iterdir()}


real = F.DEST
with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp) / "ubs"
    shutil.copytree(real, d)

    # 1. the pins hold
    if run(d):
        fails.append("1: the files here do not match the pins, or the extractor no longer builds the pinned extracts")
    # 1b. the extracts' bytes do not depend on the platform. 2026-11-05: written with Windows's CRLF, pinned here,
    # and rebuilt on Linux with LF, the Hebrew extract never matched its pin on the server; this passed throughout,
    # because here both sides were CRLF
    for name in F.EXTRACTS:
        if b"\r" in (d / name).read_bytes():
            fails.append(f"1b: {name} has a carriage return: its hash would differ on the server (Linux)")

    # 2. a changed source byte refuses and writes nothing
    before = snapshot(d)
    p = d / "README-greek.md"
    p.write_bytes(p.read_bytes() + b" ")
    before["README-greek.md"] = p.read_bytes()
    (d / "ubs-greek.jsonl").write_bytes(b"stale\n")
    before["ubs-greek.jsonl"] = b"stale\n"
    if not run(d):
        fails.append("2: a changed source was accepted")
    if snapshot(d) != before:
        fails.append("2: a refused fetch wrote files")

    # 3. a changed extract refuses and writes nothing
    p.write_bytes(before["README-greek.md"][:-1])
    before = snapshot(d)
    pinned = dict(F.EXTRACTS)
    lang, dic, version, _ = pinned["ubs-hebrew.jsonl"]
    F.EXTRACTS["ubs-hebrew.jsonl"] = (lang, dic, version, "0" * 64)
    if not run(d):
        fails.append("3: an extract that differs from its pin was accepted")
    if snapshot(d) != before:
        fails.append("3: a refused build wrote files")
    F.EXTRACTS.clear()
    F.EXTRACTS.update(pinned)
F.DEST = real

for f in fails:
    print("FAIL", f)
print(f"fetch ubs: 4 checks, 2 planted faults; {len(fails)} failures")
sys.exit(1 if fails else 0)
