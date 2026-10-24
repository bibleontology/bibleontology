"""Semantic types straight from the lexicon, for the nodes that can take them.

The question was whether the dictionaries categorize words (e.g. object) or
just give definitions.

They categorize, and I had said otherwise an hour earlier without checking.
Column 5 of TBESH/TBESG is not merely part-of-speech: its suffixes carry the
semantic class, and the definitions confirm each reading.

    N:N-M-P   2,906   H0005 Abagtha    "A man living at the time of Exile"
    N:N--L    1,067   H0011 Abaddon    "a place of destruction"
    N:N--PG     136   H0033 Abiezrite  "Someone descended from Abiezer"
    N:N--LG     124   H0130 Edomite    "Someone from Edom"

Those map onto this project's domains with no translation: Person -> `person`,
Location -> `place`, and both group codes -> `group`.

## What it does NOT give, which is the half that was asked about

Common nouns are typed only by gender -- `H:N-M`, `H:N-F` -- so **concept
versus object versus creature is still not in the data.** The proposed tier of
"static classes with no instances" remains undetermined, and the no-plural
heuristic tested against it caught 30% of known concepts, which is worse than
useless. Proper nouns are typed; common nouns are not.

## The relations the lexicon also declares

Column 1 carries links between entries -- *a Name of* (429), *a Spelling of*
(283), *a group of* (157), *a Part of* (102), *in Aramaic of* (581). Those are
alias and meronymy claims made by the lexicographers, free to read, and the
graph currently derives its aliases by other means entirely.
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
STEP = ROOT / "data" / "raw" / "stepbible"
KEY = re.compile(r"^[HG]\d{4}")

# The lexicon's semantic suffixes, mapped to this project's domains.
DOMAIN = {
    "P": "person",     # a named individual
    "L": "place",      # a named location
    "PG": "group",     # a people group -- "someone descended from X"
    "LG": "group",     # a location group -- "someone from X"
    "T": "title",      # titles and calendar names, mixed
}


def lexicon_types() -> dict:
    """lemma -> (domain, gloss, definition-head), for what the lexicon types."""
    out = {}
    for pat in ("TBESH*", "TBESG*"):
        for f in STEP.glob(pat):
            with f.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    c = line.rstrip("\n").split("\t")
                    if len(c) < 8 or not KEY.match(c[0].strip()):
                        continue
                    cat = c[5].strip()
                    if not cat.startswith("N:"):
                        continue
                    suffix = cat.rsplit("-", 1)[-1] if "-" in cat else ""
                    dom = DOMAIN.get(suffix)
                    if not dom:
                        continue
                    lem = c[0].strip()
                    if lem in out:
                        continue                 # first sense wins
                    d = re.sub(r"<[^>]+>", " ", c[7])
                    out[lem] = (dom, c[6].strip(), re.sub(r"\s+", " ", d).strip()[:70])
    return out


def relations() -> list:
    """The alias and part-of claims the lexicon declares in column 1."""
    out = []
    for pat in ("TBESH*", "TBESG*"):
        for f in STEP.glob(pat):
            with f.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    c = line.rstrip("\n").split("\t")
                    if len(c) < 3 or not KEY.match(c[0].strip()):
                        continue
                    m = re.search(r"=\s*(a |the |in )?(.+)$", c[1].strip())
                    if not m or not m.group(2).strip():
                        continue
                    tgt = c[2].strip().rstrip(",")
                    if tgt and tgt != c[0].strip():
                        out.append({"from": c[0].strip(), "kind":
                                    m.group(2).strip()[:28], "to": tgt})
    return out


def main() -> int:
    t = lexicon_types()
    by = collections.Counter(v[0] for v in t.values())
    print(f"lemmas typed by the lexicon: {len(t):,}")
    for k, v in by.most_common():
        print(f"    {k:10}{v:>6,}")
    print()

    rels = relations()
    print(f"relations declared between entries: {len(rels):,}")
    for k, v in collections.Counter(r["kind"] for r in rels).most_common(8):
        print(f"    {k:24}{v:>6,}")
    print()

    sys.path.insert(0, str(ROOT / "src"))
    from bibleont.schema import load_entities
    e = load_entities()
    lemmad = {x.id: (x.attrs or {}).get("lemma") for x in e.values()
              if (x.attrs or {}).get("lemma")}
    agree = dis = 0
    for nid, lem in lemmad.items():
        got = t.get(lem if isinstance(lem, str) else (lem or [None])[0])
        if not got:
            continue
        if got[0] == e[nid].type:
            agree += 1
        else:
            dis += 1
    print(f"against the {len(lemmad):,} graph nodes that carry a lemma:")
    print(f"    lexicon has a type for {agree + dis}")
    print(f"    agrees with the graph  {agree}")
    print(f"    disagrees              {dis}")
    if "--json" in sys.argv:
        p = ROOT / "out" / "lexicon-types.json"
        p.write_text(json.dumps({"types": t, "relations": rels[:4000]},
                                ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nwrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
