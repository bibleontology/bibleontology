"""A build stamp on every layer, so staleness is a query and not a memory.

Audited 2026-09-11: **33 of 33 generated layers carried a licence credit and
not one carried a build stamp.** None recorded when it was built, from which
inputs, or at what version of the tool that wrote it.

That morning the frame layer changed underneath all of them — polarity, mood,
coreference resolution, 1,165 recovered tuples — and nothing downstream could
have detected it. `seams`, `themespace`, `episodes` and `paragraphs` were
rebuilt only because a human remembered they needed to be.

The architecture makes this load-bearing: overlays are retained until they
are regenerated, while the deterministic layers are regenerated continually.

Retention is only safe if staleness is detectable. **An overlay nobody can
invalidate is worse than no overlay, because it looks current forever.** The
deterministic side has the same problem and has been getting away with it
because one person happened to remember the dependency order.

## What a stamp records

    _built        UTC timestamp, ISO 8601
    _tool         the module that wrote it, and a hash of its source, so a
                  CODE change invalidates even when the inputs did not
    _inputs       every file read, with size and mtime -- cheap to compute
                  and sufficient to notice a real change. Hashing 107MB of
                  MACULA XML on every run is not, and would make the stamp
                  something people skip.

## What it deliberately does not do

It does not rebuild anything. Deciding what to regenerate is a judgment about
cost and risk; this only answers "is what I am reading still true of its
inputs", which is the part that cannot be held in a head.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _fingerprint(p: pathlib.Path):
    """Size and mtime. Enough to notice a real change, cheap enough to run."""
    st = p.stat()
    return {"path": str(p.relative_to(ROOT)).replace("\\", "/"),
            "size": st.st_size, "mtime": int(st.st_mtime)}


def _tool_hash(tool_file) -> str:
    b = pathlib.Path(tool_file).read_bytes()
    return hashlib.sha256(b).hexdigest()[:16]


def stamp(tool_file, inputs=(), extra=None) -> dict:
    """The header dict a writer should emit as its first line.

    `inputs` may be paths or globs relative to the repo root. A glob that
    matches thousands of files (the MACULA tree) is collapsed to a count and a
    summed size rather than listed, so the header stays readable.
    """
    got, groups = [], {}
    for spec in inputs:
        spec = str(spec)
        paths = ([p for p in ROOT.glob(spec) if p.is_file()]
                 if any(c in spec for c in "*?[")
                 else ([ROOT / spec] if (ROOT / spec).exists() else []))
        if len(paths) > 8:
            total = sum(p.stat().st_size for p in paths)
            newest = max(int(p.stat().st_mtime) for p in paths)
            groups[spec] = {"files": len(paths), "bytes": total,
                            "newest_mtime": newest}
        else:
            got.extend(_fingerprint(p) for p in paths)
    h = {
        "_built": datetime.datetime.now(datetime.timezone.utc)
                  .replace(microsecond=0).isoformat(),
        "_tool": {"file": pathlib.Path(tool_file).name,
                  "sha256_16": _tool_hash(tool_file)},
    }
    if got:
        h["_inputs"] = got
    if groups:
        h["_input_sets"] = groups
    if extra:
        h.update(extra)
    return h


def read_header(path) -> dict | None:
    import gzip
    p = pathlib.Path(path)
    if not p.exists():
        return None
    opener = gzip.open if p.suffix == ".gz" else open
    try:
        with opener(p, "rt", encoding="utf-8") as f:
            first = f.readline()
        d = json.loads(first)
        return d if any(k.startswith("_") for k in d) else None
    except Exception:
        return None


def stale(path):
    """(is_stale, reasons). Unknown is NOT stale -- say so instead of guessing.

    An unstamped layer returns ("unstamped", ...) so the audit can separate
    "this is out of date" from "this cannot tell us", which are different
    problems with different fixes.
    """
    h = read_header(path)
    if h is None:
        return "unreadable", []
    if "_built" not in h:
        return "unstamped", []
    why = []
    for rec in h.get("_inputs", []):
        p = ROOT / rec["path"]
        if not p.exists():
            why.append(f"{rec['path']}: gone")
            continue
        st = p.stat()
        if st.st_size != rec["size"] or int(st.st_mtime) != rec["mtime"]:
            why.append(f"{rec['path']}: changed")
    for spec, rec in (h.get("_input_sets") or {}).items():
        paths = [p for p in ROOT.glob(spec) if p.is_file()]
        if len(paths) != rec["files"]:
            why.append(f"{spec}: {len(paths)} files, was {rec['files']}")
        elif paths and max(int(p.stat().st_mtime) for p in paths) != \
                rec["newest_mtime"]:
            why.append(f"{spec}: a file changed")
    return ("stale" if why else "current"), why


def audit():
    out = sorted((ROOT / "out").glob("*.jsonl*"))
    tally = {"current": 0, "stale": 0, "unstamped": 0, "unreadable": 0}
    print(f"{'layer':<34}{'state':<12}why")
    for p in out:
        state, why = stale(p)
        tally[state] = tally.get(state, 0) + 1
        mark = {"stale": "STALE", "unstamped": "-", "current": "ok",
                "unreadable": "??"}[state]
        print(f"  {p.name:<32}{mark:<12}{'; '.join(why[:2])}")
    print(f"\n  {tally}")
    if tally.get("unstamped"):
        print(f"\n  {tally['unstamped']} layers cannot report staleness at all.")
        print("  Their writers need: header = provenance.stamp(__file__, inputs=[...])")
    return 0


if __name__ == "__main__":
    raise SystemExit(audit())
