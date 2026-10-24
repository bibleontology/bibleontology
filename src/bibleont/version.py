"""What version of the graph and the app a reader was looking at.

Feedback that is not pinned to a version stops being actionable the moment the
graph moves. "This relation is wrong" three weeks and four hundred edges later
is a puzzle rather than a report, and the fix costs nothing at capture time and
cannot be reconstructed afterwards.

**Nothing here is bumped by hand.** A version number somebody has to remember
to increment is the same maintenance burden as a hand-kept status page, and it
fails the same way -- silently, by staying the same when it should have moved.
Both versions are content hashes: they change exactly when the bytes they cover
change, and they cannot drift.

Three things are recorded together because they answer different questions:

  ontology   a hash over the entity and relation files and the schema.
             Changes iff the graph changed. This is what a claim about a
             relation is pinned to.
  app        a hash over the served front end. Changes iff the interface
             changed, which is what a complaint about a view is pinned to.
  counts     entities and relations, carried alongside because a human
             reading a report needs a number they can recognise, and a hash
             tells them nothing about whether the graph grew or shrank.

The git commit is included when it is available and omitted when it is not.
It is the most useful of the four to a developer and the least dependable:
the beta ships as a static export with no repository behind it.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import ONTOLOGY

# the site (app2/ since 2026-10-01; until 2026-10-22 this still named app/, so
# in a checkout without it every note carried the hash of nothing)
APP = Path(__file__).resolve().parents[2] / "app2"


def _digest(paths: list[Path]) -> str:
    """A short content hash over files, stable across platforms.

    Sorted by name so the order files happen to be listed in cannot change
    the result, and hashing the name as well as the bytes so that renaming a
    file is a change.
    """
    h = hashlib.sha256()
    for p in sorted(paths, key=lambda x: x.as_posix()):
        if not p.is_file():
            continue
        h.update(p.name.encode("utf-8"))
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ONTOLOGY.parent), capture_output=True, text=True,
            timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    sha = out.stdout.strip()
    return sha or None


@dataclass(frozen=True)
class Build:
    ontology: str
    app: str
    entities: int
    relations: int
    commit: str | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


def _count_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("rb") as fh:
        return sum(1 for line in fh if line.strip())


def build(store=None) -> Build:
    """The current version of everything a reader could be looking at."""
    ont_files = [ONTOLOGY / "identity.yaml"]
    ont_files += sorted((ONTOLOGY / "entities").glob("*.jsonl"))
    ont_files += sorted((ONTOLOGY / "relations").glob("*.jsonl"))
    ont_files += sorted((ONTOLOGY / "schema").glob("*.yaml"))

    app_files = sorted(APP.glob("static/*.html")) + \
        sorted(APP.glob("static/*.js")) + sorted(APP.glob("server.py"))
    if not app_files:
        raise RuntimeError(f"version: no site files under {APP}; the app hash would be the hash of nothing")

    if store is not None:
        entities, relations = len(store.people), len(store.relations)
    else:
        entities = sum(_count_lines(p)
                       for p in (ONTOLOGY / "entities").glob("*.jsonl"))
        relations = sum(_count_lines(p)
                        for p in (ONTOLOGY / "relations").glob("*.jsonl"))

    return Build(
        ontology=_digest(ont_files),
        app=_digest(app_files),
        entities=entities,
        relations=relations,
        commit=_git_commit(),
    )


def main(argv: list[str] | None = None) -> int:
    print(json.dumps(build().as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
