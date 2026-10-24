"""What a re-run would lose, checked before anything is retired.

## The question this answers

2026-08-31, on re-running Genesis and Job: how does one know what to clear
out of the merged graph if the re-run route is taken?

Provenance is per batch -- every entity and relation carries `source` -- so
the mechanical answer is "retire the old batch". That answer is not enough,
and the two ways it is not enough have both already cost this project
something.

**Entities are shared.** A batch does not only assert relations; it DECLARES
nodes, and other batches point at them. Retiring the batch that declared
`tamar` orphans every relation elsewhere that names her. This is what was
misdiagnosed on 2026-08-31: two hand-built batches fell out of the graph and
the retirement was blamed for a whole day.

**Relations are duplicated.** The same claim often appears in several batches
and the merge attributes it to one of them, so "relations whose source is the
old batch" is not the same set as "relations the old batch is holding up".

So the safe procedure is not to reason about it. It is:

    1. extract the new pass, gate it, promote it to staging
    2. run THIS, comparing old against new
    3. retire the old batch only if the report is acceptable
    4. merge, and read the DROPPED line, which is the same question asked
       again from the other side

Step 2 is cheap and specific -- it names the verses. Step 4 is the backstop.
Neither is optional, because they catch different things: this compares two
batches, and DROPPED compares two states of the whole graph.

## It over-reports, on purpose, and slightly

The orphan check was wrong three times running and each fix was the same
lesson: it was asking a narrower question than the merge asks. It compared
only old against new (63 false alarms on the Job swap), then ignored other
batches' declarations (2), then ignored identity aliases on one side (2
again). Every one of those nodes turned out to be present in the graph.

It still flags one or two that survive, because the merge also mints
canonical records from `identity.yaml` that no batch declares literally.
Matching it exactly would mean reimplementing it, and a pre-flight that
duplicates the thing it checks has stopped being a check.

So this errs toward reporting, and every line is marked for a person to look
at rather than acted on. The backstop at step 4 is what actually knows.

    python -m bibleont.supersede gen-farm-20260829-182034 gen-full-20260830-195828
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .paths import ONTOLOGY

STAGING = ONTOLOGY / "staging"
RETIRED = ONTOLOGY / "retired"
PROPOSALS = ONTOLOGY / "proposals"


def _find(name: str) -> Path:
    for base in (STAGING, PROPOSALS, RETIRED):
        p = base / name
        if p.is_dir():
            return p
    raise SystemExit(f"no batch called {name!r} in staging, proposals or retired")


def _rows(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()]


def _key(r: dict) -> tuple:
    return (r.get("src"), r.get("type"), r.get("dst"))


def compare(old_name: str, new_name: str) -> dict:
    old, new = _find(old_name), _find(new_name)

    old_rel = {_key(r): r for r in _rows(old / "relations.jsonl")}
    new_rel = {_key(r): r for r in _rows(new / "relations.jsonl")}
    old_ent = {e["id"]: e for e in _rows(old / "entities.jsonl") if e.get("id")}
    new_ent = {e["id"]: e for e in _rows(new / "entities.jsonl") if e.get("id")}

    # Relations only the old pass has. Not automatically a loss -- the new
    # pass may say the same thing better, or may have been right to drop it --
    # but it is the set nobody can evaluate without seeing it.
    lost_rel = [r for k, r in old_rel.items() if k not in new_rel]

    # Nodes only the old pass declares. Harmless unless something else points
    # at them, so that is the thing actually worth reporting.
    # At risk only if the OLD batch is the last thing declaring it.
    #
    # The first version compared old against new alone and cried wolf: it
    # reported 63 nodes at risk for the Job swap -- `love`, `suffering`,
    # `image_seed` -- and every one of them survived, because the graph is the
    # union of every batch and Genesis or a curated batch also declares them.
    # A warning that fires on things which turn out fine is one nobody reads,
    # which is the failure this whole module exists to prevent.
    gone_ent = {i for i in old_ent if i not in new_ent}

    # Resolve identity aliases first. `ram` is not orphaned by retiring the
    # batch that declared him -- identity.yaml maps him onto
    # `ram_son_of_hezron`, which another batch declares, and the merge
    # rewrites every relation accordingly. Without this the report claimed a
    # broken link in the line to David and there was none.
    #
    # Third correction to this same check, and they were all the same
    # mistake: asking a narrower question than the merge asks. First it
    # compared only old against new (63 false alarms), then it ignored other
    # batches' declarations (2), now aliases (0). The merge resolves ids,
    # unions every batch and follows identity.yaml, so a pre-flight that does
    # less than that will always over-report.
    try:
        from .merge import _alias_map, load_identity
        alias = _alias_map(load_identity())
    except Exception:                                        # noqa: BLE001
        alias = {}
    gone_ent = {alias.get(i, i) for i in gone_ent}

    for d in sorted(STAGING.iterdir()):
        if not d.is_dir() or d.name in (old_name, new_name):
            continue
        for e in _rows(d / "entities.jsonl"):
            # Alias BOTH sides. Aliasing only `gone_ent` left the comparison
            # asking whether anyone declares `ram_son_of_hezron` when what
            # they declare is `ram`, so two nodes that plainly exist were
            # still reported at risk.
            eid = e.get("id")
            gone_ent.discard(alias.get(eid, eid))
        if not gone_ent:
            break

    needed: dict[str, list[str]] = {}
    for d in sorted(STAGING.iterdir()):
        if not d.is_dir() or d.name in (old_name, new_name):
            continue
        for r in _rows(d / "relations.jsonl"):
            for side in ("src", "dst"):
                node = alias.get(r.get(side), r.get(side))
                if node in gone_ent:
                    needed.setdefault(node, []).append(d.name)

    return {
        "old": old_name, "new": new_name,
        "old_rel": len(old_rel), "new_rel": len(new_rel),
        "old_ent": len(old_ent), "new_ent": len(new_ent),
        "kept": len(set(old_rel) & set(new_rel)),
        "lost_rel": lost_rel,
        "gone_ent": sorted(gone_ent),
        "orphaning": {k: sorted(set(v)) for k, v in needed.items()},
    }


SHARED = STAGING / "shared-vocabulary"


def rescue(old_name: str, ids: list[str]) -> int:
    """Copy at-risk nodes into a batch that owns nothing and declares only.

    A concept belongs to the corpus, not to whichever book first mentioned
    it. `love` was declared by the Job pass because Job talks about love, and
    six curated batches then pointed at it -- so re-extracting Job, an
    operation with nothing to do with those batches, would have taken it
    away.

    Declaration-only batches already exist for exactly this (`gen-vocabulary`,
    `job-vocabulary`, 0 relations each) and were holding 50 nodes between
    them, none of the shared ones. This puts them where they belong before
    the retirement rather than after the breakage.
    """
    src = _find(old_name)
    have = {e["id"]: e for e in _rows(src / "entities.jsonl") if e.get("id")}
    SHARED.mkdir(parents=True, exist_ok=True)
    ent_file = SHARED / "entities.jsonl"
    already = {e["id"] for e in _rows(ent_file) if e.get("id")}

    written = 0
    with ent_file.open("a", encoding="utf-8", newline="\n") as f:
        for i in ids:
            if i in already or i not in have:
                continue
            row = dict(have[i])
            row["source"] = "shared-vocabulary (rescued before a re-run)"
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
    (SHARED / "relations.jsonl").touch()
    (SHARED / "META.json").write_text(json.dumps({
        "produced_by": "bibleont.supersede --rescue",
        "brief": "Entity declarations only, no relations. Shared concepts "
                 "that several batches point at and no single book owns, "
                 "moved here so re-extracting one book cannot orphan them.",
    }, indent=1), encoding="utf-8")
    return written


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print("usage: python -m bibleont.supersede <old-batch> <new-batch>")
        print("       what retiring <old-batch> would cost, before doing it")
        return 2

    c = compare(argv[0], argv[1])
    print(f"  {c['old']}  ->  {c['new']}")
    print(f"    relations  {c['old_rel']:>6} -> {c['new_rel']:<6} "
          f"({c['kept']} identical in both)")
    print(f"    entities   {c['old_ent']:>6} -> {c['new_ent']:<6}")
    print()

    # THE ONE THAT BITES. A node the old pass declared, the new pass does not,
    # and a THIRD batch is standing on.
    if c["orphaning"]:
        print(f"  WOULD ORPHAN -- {len(c['orphaning'])} node(s) that other "
              f"batches point at and the new pass does not declare:")
        # Type and edge count, because they separate the two kinds of
        # orphan and the difference decides whether to care. A `concept`
        # carrying one `speaks_of` from a tag-cloud-era batch IS the
        # residue being cleaned out. A substantive node with real
        # citations is a loss.
        from .graph import Store
        g = Store.load()
        deg = {}
        for r in g.relations:
            deg[r.src] = deg.get(r.src, 0) + 1
            deg[r.dst] = deg.get(r.dst, 0) + 1
        rows = []
        for node, batches in c["orphaning"].items():
            e = g.people.get(node)
            rows.append((deg.get(node, 0), node, e.type if e else "?", batches))
        for n, node, typ, batches in sorted(rows, reverse=True):
            mark = "  <-- LOOK" if typ not in ("concept", "image") or n > 6 else ""
            print(f"    {node:<34} {typ:<9} {n:>3} edge(s)  "
                  f"{', '.join(batches[:2])}{mark}")
        print()
        if "--rescue" in argv:
            n = rescue(argv[0], sorted(c["orphaning"]))
            print(f"  RESCUED {n} node(s) -> ontology/staging/"
                  f"shared-vocabulary/")
            print("  Retiring the old pass can no longer orphan them.")
        else:
            print("  These have no owner. Whichever book happened to mention a")
            print("  shared concept first is the batch that declared it, which")
            print("  is why an unrelated re-run can drop `love` or `suffering`.")
            print()
            print("  Add --rescue to copy them into a declaration-only batch")
            print("  first, which is what gen-vocabulary and job-vocabulary")
            print("  already are and what they should have been holding.")
        print()
    else:
        print("  nothing would be orphaned: every node the new pass drops is "
              "unused elsewhere.")
        print()

    lost = c["lost_rel"]
    print(f"  {len(lost)} relation(s) in the old pass and not the new one")
    if lost:
        print("  (not automatically a loss -- the new pass may be right to "
              "drop them -- but nobody can tell without looking)")
        shown = 0
        for r in lost:
            if shown >= 15:
                break
            refs = ", ".join(str(x) for x in (r.get("refs") or [])[:2])
            print(f"    {r.get('src')} -{r.get('type')}-> {r.get('dst')}"
                  f"   [{refs}]")
            shown += 1
        if len(lost) > shown:
            print(f"    ... {len(lost) - shown} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
