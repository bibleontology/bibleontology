"""Ask whether a person is already in the ontology, and under what id.

Extraction batches are written independently, which is what makes new ids drift
apart from ones already in the graph ("Bathsheba" vs "bath_sheba", plain
"phinehas" vs "phinehas_son_of_eleazar"). Reconciling that afterwards is manual
work. Checking here first avoids it.

Usage:
    python -m bibleont.lookup Phinehas
    python -m bibleont.lookup Phinehas Abinadab "Bath-sheba"
    python -m bibleont.lookup --all-ids > /tmp/ids.txt
"""

from __future__ import annotations

import sys

from .schema import load_persons, name_variants, slugify


def find(needle: str) -> list[dict]:
    """Every existing person whose name or alias plausibly matches `needle`."""
    people = load_persons()
    low = needle.strip().lower()
    slug = slugify(needle)
    variants = {v.lower() for v in name_variants(needle)}

    hits = []
    for pid, person in people.items():
        names = {n.lower() for n in person.names()}
        names |= {v.lower() for n in person.names() for v in name_variants(n)}
        exact = bool(names & variants) or pid == slug
        prefix = any(n.startswith(low) or low.startswith(n) for n in names)
        contains = pid.startswith(slug + "_") or slug in pid
        if exact or prefix or contains:
            hits.append(
                {
                    "id": pid,
                    "name": person.name,
                    "aka": person.aka,
                    "disambiguation": person.disambiguation,
                    "refs": person.refs[:2],
                    "exact": exact,
                }
            )
    hits.sort(key=lambda h: (not h["exact"], h["id"]))
    return hits


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if "--all-ids" in argv:
        for pid in sorted(load_persons()):
            print(pid)
        return 0

    names = [a for a in argv if not a.startswith("--")]
    if not names:
        print(__doc__)
        return 2

    for name in names:
        hits = find(name)
        print(f"\n{name}")
        if not hits:
            print("  not in the ontology yet - mint a new id, e.g. "
                  f"{slugify(name)!r}")
            continue
        if len(hits) > 1:
            print(f"  {len(hits)} people share or resemble this name - pick the "
                  "right one, or mint a NEW qualified id if yours is a different person")
        for h in hits:
            mark = "=" if h["exact"] else "~"
            bits = []
            if h["aka"]:
                bits.append("aka " + ", ".join(h["aka"]))
            if h["disambiguation"]:
                bits.append(h["disambiguation"])
            if h["refs"]:
                bits.append(", ".join(h["refs"]))
            print(f"  {mark} {h['id']:34} {h['name']:16} {'; '.join(bits)}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
