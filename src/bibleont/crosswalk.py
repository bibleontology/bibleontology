"""Derive KJV -> ASV proper-name equivalences from the parallel text.

The KJV renders New Testament names through Greek — "Urias", "Booz", "Roboam",
"Naasson" — while the same people appear in the Old Testament as Uriah, Boaz,
Rehoboam, Nahshon. Extraction batches therefore mint two ids for one person, and
the split has to be repaired by hand in identity.yaml.

The ASV (1901, public domain) normalizes those names to their Hebrew forms and is
verse-aligned with the KJV. So the equivalences can be *computed*: line up the two
renderings of the same verse, and where they differ by a single similar-looking
name, that is a transliteration pair.

This proposes; it does not decide. Output is a reviewed-then-pasted block for
ontology/identity.yaml, because merging two people who merely look alike is the
one error the rest of the pipeline cannot catch.

Usage:
    python -m bibleont.crosswalk                 # pairs seen in the ontology
    python -m bibleont.crosswalk --all           # every pair found in the text
    python -m bibleont.crosswalk --min-count 3
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher

from .paths import VERSES_JSONL
from .refs import VerseId
from .schema import load_persons, load_relations, slugify

# Words that are capitalized mid-sentence but are not personal names.
_STOPWORDS = {
    "God", "Lord", "LORD", "GOD", "Christ", "Jesus", "Spirit", "Holy", "Father",
    "Son", "King", "Sabbath", "Amen", "Selah", "Behold", "But", "And", "For",
    "The", "Then", "Now", "So", "Thus", "When", "Who", "That", "This", "There",
    "Israel", "Judah", "Egypt", "Jerusalem", "Zion", "Babylon", "Jordan",
    "Pharaoh", "Levite", "Levites", "Jew", "Jews", "Gentiles", "Passover",
}

_TOKEN = re.compile(r"\b[A-Z][a-zA-Z'-]{2,}\b")


def _names(text: str) -> list[str]:
    """Capitalized, name-shaped tokens, minus the obvious non-names."""
    out = []
    for m in _TOKEN.finditer(text):
        tok = m.group(0)
        if tok in _STOPWORDS:
            continue
        # skip a capital that is only there because it starts the verse
        if m.start() == 0:
            continue
        out.append(tok)
    return out


def _load(path) -> dict[VerseId, str]:
    verses: dict[VerseId, str] = {}
    if not path.exists():
        return verses
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if "translation" in rec:
                continue
            verses[VerseId(rec["b"], rec["c"], rec["v"])] = rec["t"]
    return verses


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def derive(min_count: int = 2) -> dict[tuple[str, str], dict]:
    """Candidate (kjv_name, asv_name) pairs with their supporting verses."""
    kjv = _load(VERSES_JSONL)
    asv = _load(VERSES_JSONL.with_suffix(".asv.jsonl"))
    if not asv:
        raise SystemExit(
            "ASV text not built. Download data/raw/ASV.json and run "
            "python -m bibleont.build_corpus"
        )

    found: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"count": 0, "refs": []}
    )

    for vid, ktext in kjv.items():
        atext = asv.get(vid)
        if not atext:
            continue
        ka, aa = _names(ktext), _names(atext)
        if not ka or not aa or ka == aa:
            continue
        for op, i1, i2, j1, j2 in SequenceMatcher(None, ka, aa).get_opcodes():
            if op != "replace" or (i2 - i1) != (j2 - j1):
                continue
            for k, a in zip(ka[i1:i2], aa[j1:j2]):
                if k == a:
                    continue
                # Same person spelled differently, not two different people:
                # require a shared first letter and real string overlap.
                if k[0].lower() != a[0].lower() or _similar(k, a) < 0.55:
                    continue
                rec = found[(k, a)]
                rec["count"] += 1
                if len(rec["refs"]) < 4:
                    rec["refs"].append(str(vid))

    return {p: r for p, r in found.items() if r["count"] >= min_count}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    min_count = 2
    if "--min-count" in argv:
        min_count = int(argv[argv.index("--min-count") + 1])
    show_all = "--all" in argv

    pairs = derive(min_count)
    people = load_persons()
    ids = set(people)

    # Spelling similarity alone is not identity. The ASV sometimes normalizes two
    # genuinely different men onto one spelling: KJV Salah (son of Arphaxad) and
    # Shelah (son of Judah) both become "Shelah"; Joses and Joseph both become
    # "Joseph". Parentage is the discriminator — two people with different
    # recorded fathers are two people, whatever they are spelled.
    parents: dict[str, set[str]] = defaultdict(set)
    for rel in load_relations():
        if rel.type in ("father_of", "mother_of"):
            parents[rel.dst].add(rel.src)

    safe, rejected, review, latent = [], [], [], []
    for (kjv_name, asv_name), rec in sorted(
        pairs.items(), key=lambda kv: -kv[1]["count"]
    ):
        k_id, a_id = slugify(kjv_name), slugify(asv_name)
        if k_id in ids and a_id in ids and k_id != a_id:
            pk, pa = parents.get(k_id, set()), parents.get(a_id, set())
            row = (kjv_name, asv_name, k_id, a_id, rec, pk, pa)
            if pk and pa and not (pk & pa):
                rejected.append(row)
            elif pk & pa:
                safe.append(row)
            else:
                review.append(row)
        elif k_id in ids:
            latent.append((kjv_name, asv_name, k_id, a_id, rec, "KJV form is in the graph"))
        elif show_all:
            latent.append((kjv_name, asv_name, k_id, a_id, rec, "neither id present yet"))

    if safe:
        print("# SAME PERSON - both ids exist and share a recorded parent.")
        print("# Paste under `same:` in ontology/identity.yaml.\n")
        for kjv_name, asv_name, k_id, a_id, rec, pk, _ in safe:
            print(f"  # {kjv_name} = {asv_name}  (both child of {', '.join(sorted(pk))}; "
                  f"{rec['count']}x: {', '.join(rec['refs'][:2])})")
            print(f"  {a_id}: [{k_id}]")
        print()

    if rejected:
        print("# DIFFERENT PEOPLE - do NOT merge. The ASV spells them alike but the")
        print("# text gives them different parents.\n")
        for kjv_name, asv_name, k_id, a_id, rec, pk, pa in rejected:
            print(f"  # {kjv_name} ({k_id}, child of {', '.join(sorted(pk))}) "
                  f"is NOT {asv_name} ({a_id}, child of {', '.join(sorted(pa))})")
        print()

    if review:
        print("# NEEDS A HUMAN - both ids exist, but at least one has no recorded")
        print("# parent, so identity cannot be settled from the graph alone.\n")
        for kjv_name, asv_name, k_id, a_id, rec, pk, pa in review:
            print(f"  # {kjv_name} ({k_id}, parents={sorted(pk) or 'none'}) vs "
                  f"{asv_name} ({a_id}, parents={sorted(pa) or 'none'})  "
                  f"{rec['count']}x: {rec['refs'][0]}")
        print()

    if latent:
        print("# The KJV spelling is in the graph but the ASV form is not (yet).")
        print("# Prefer the ASV spelling when a later batch introduces the same person.\n")
        for kjv_name, asv_name, k_id, a_id, rec, why in latent:
            print(f"  # {kjv_name} -> {asv_name}  ({rec['count']}x: {rec['refs'][0]}) [{why}]")
        print()

    print(
        f"# {len(pairs)} name pairs derived. Live in the graph today: "
        f"{len(safe)} safe to merge, {len(rejected)} rejected as different people, "
        f"{len(review)} need review."
    )
    if not show_all:
        print("# Run with --all to see every pair found in the text.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
