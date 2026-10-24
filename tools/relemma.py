"""Re-source the entity lemma attributes from MACULA instead of STEPBible.

320 entities carry `lemma_gloss` and `lemma_word` copied out of the STEPBible
TAHOT/TAGNT texts, tagged `lemma_source: "STEPBible TAHOT/TAGNT, CC BY 4.0,
www.STEPBible.org"`. That attribution was written under the CC BY 4.0 reading of
their licence, which is one of three readings their own materials support:

    the TAHOT/TAGNT file header    "CC BY 4.0"
    their repository README        "Refer others to github.com/STEPBible as the
                                    source of the data. Please do not
                                    redistribute it yourself."
    stepbible.org Copyrights page  "CC BY-NC 3.0 Licence"

Those cannot all be true at once, and the question is still open with them.
No licence violation is to be risked, so rather than pick the reading that
suits us, the dependency goes away.

**It costs nothing, because MACULA is keyed by the same numbers.** Strong's
numbers are public domain, so the `lemma` code itself was never in question --
only the gloss and the surface word hanging off it. MACULA carries a gloss for
98.6% of 613,673 words and a Strong's number for 99.7%, across all 66 books, so
the same fields come back from a source licensed CC BY 4.0 without ambiguity.

Re-runnable: it rewrites from the MACULA index every time rather than patching,
so running it twice changes nothing the first run did not already do.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENTS = ROOT / "ontology" / "entities" / "entities.jsonl"
INTERLINEAR = ROOT / "out" / "interlinear.jsonl.gz"

MACULA_CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"
STEP_MARK = "STEPBible"


def strong_key(code: str) -> str | None:
    """`G0005` -> `g5`, `H0001G` -> `h1`.

    STEPBible disambiguates homographs with a trailing letter (H0001G is a
    different sense from H0001). MACULA does not carry that distinction, so the
    letter is dropped and the base number is what both sides agree on.
    """
    if not code or code[0] not in "GgHh":
        return None
    digits = re.match(r"0*(\d+)", code[1:])
    return f"{code[0].lower()}{digits.group(1)}" if digits else None


def macula_index() -> dict[str, tuple[collections.Counter, collections.Counter]]:
    """Strong's key -> (gloss counts, lemma-form counts).

    Counts rather than a single winner, because the commonest gloss is not
    always the right one. STEPBible disambiguates homographs with a trailing
    letter -- H0905H, H6924I -- which MACULA does not carry, so the base number
    can hold several senses. Taking the most frequent turned *backward* (H6924I)
    into "east" and *alone* (H0905H) into "himself": both are real glosses of
    the base number and neither is the sense the entity was named for.

    So the counts are kept and the choice is made per entity, against the name
    the graph already gave it.
    """
    gloss = collections.defaultdict(collections.Counter)
    word = collections.defaultdict(collections.Counter)
    with gzip.open(INTERLINEAR, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if any(k.startswith("_") for k in d):
                continue
            lang = "g" if d["ref"].split(".")[0] in GREEK_BOOKS else "h"
            for w in d.get("words", []):
                s, g, lem = w.get("s"), w.get("g"), w.get("l")
                if not s:
                    continue
                k = f"{lang}{str(s).lstrip('0') or s}"
                if g and g != "-":
                    gloss[k][g] += 1
                if lem:
                    word[k][lem] += 1
    return {k: (gloss[k], word[k]) for k in set(gloss) | set(word)}


def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-z]+", (s or "").lower()))


def choose(counts: collections.Counter, name: str) -> str:
    """The gloss this entity was named for, else the commonest.

    A tie on name-overlap is broken by frequency, so the rule only ever
    reorders candidates that genuinely mention the entity's own words.
    """
    if not counts:
        return ""
    want = _words(name)
    if want:
        scored = [(len(want & _words(g)), n, g) for g, n in counts.items()]
        best = max(scored)
        if best[0]:
            return best[2]
    return counts.most_common(1)[0][0]


GREEK_BOOKS = {
    "Mat", "Mrk", "Luk", "Jhn", "Act", "Rom", "1Co", "2Co", "Gal", "Eph",
    "Php", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb", "Jas",
    "1Pe", "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true",
                    help="rewrite entities.jsonl (default is a dry run)")
    a = ap.parse_args()

    ix = macula_index()
    print(f"MACULA lemma index: {len(ix)} Strong's keys")

    # The worker proposals carry the same attribution as the entities they were
    # promoted into, so cleaning only the graph would leave 724 copies of the
    # same text one directory away.
    targets = sorted(
        p for p in (ROOT / "ontology").rglob("*.jsonl")
        if STEP_MARK in p.read_text(encoding="utf-8", errors="ignore"))
    print(f"files to clean: {len(targets)}")

    resourced = missing = 0
    examples = []
    for path in targets:
        rows = [json.loads(x) for x in
                path.read_text(encoding="utf-8").splitlines() if x.strip()]
        n = _clean(rows, ix, examples)
        resourced += n[0]
        missing += n[1]
        if a.apply and (n[0] or n[1]):
            path.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True)
                          for r in rows) + "\n", encoding="utf-8")

    print(f"re-sourced from MACULA   {resourced}")
    print(f"no MACULA gloss found    {missing}")
    print()
    for tag, eid, lem, old, new in examples[:14]:
        print(f"  {tag:4} {eid[:22]:24} {str(lem):8} "
              f"{str(old)[:22]:24} -> {str(new)[:26]}")

    if not a.apply:
        print("\ndry run -- pass --apply to rewrite")
        return 0

    left = sum(
        1 for p in targets
        for x in p.read_text(encoding="utf-8").splitlines()
        if STEP_MARK in x)
    print(f"\nrecords still citing STEPBible: {left}")
    return 0


def _clean(rows, ix, examples, apply=True):
    """Rewrite one file's rows in place. Returns (re-sourced, missing)."""
    resourced = missing = 0
    for e in rows:
        at = e.get("attrs") or {}
        if STEP_MARK not in str(at.get("lemma_source", "")):
            continue
        k = strong_key(at.get("lemma", ""))
        hit = ix.get(k or "")
        if not hit or not (hit[0] or hit[1]):
            # No MACULA gloss for this number. The Strong's code stays -- it is
            # public domain -- and their text goes, rather than being kept on
            # the grounds that we could not replace it.
            missing += 1
            if len(examples) < 20:
                examples.append(("DROP", e.get("id", "?"), at.get("lemma"),
                                 at.get("lemma_gloss"), "(gloss removed)"))
            at.pop("lemma_gloss", None)
            at.pop("lemma_word", None)
            at["lemma_source"] = "Strong's number only; no MACULA gloss"
            continue
        name = e.get("name") or e.get("id", "")
        g = choose(hit[0], name)
        w = hit[1].most_common(1)[0][0] if hit[1] else ""
        if len(examples) < 20:
            examples.append(("ok", e.get("id", "?"), at.get("lemma"),
                             at.get("lemma_gloss"), g))
        at["lemma_gloss"] = g or ""
        at["lemma_word"] = w or ""
        at["lemma_source"] = MACULA_CREDIT
        resourced += 1
    return resourced, missing


if __name__ == "__main__":
    sys.exit(main())
