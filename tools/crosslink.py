"""Links that cross the testaments, which the lemma layer cannot make.

2026-09-15, on the death-and-new-creation pattern: is there any OT
foreshadowing? -- and then, on finding the graph could not answer, that pass is
needed and the question is not to be lost.

`out/allusions.jsonl.gz` holds **141,365 links and exactly ZERO cross the
testaments.** Not a threshold problem: it matches shared LEMMAS, and the
testaments are in different languages, so Ἰωνᾶς can never match יוֹנָה. Every
typology the New Testament states outright is invisible to it by
construction --

    Matt 12:40   as Jonah was three days in the belly of the fish
    John 3:14    as Moses lifted up the serpent in the wilderness
    1 Cor 10:2   baptised into Moses in the cloud and in the sea
    1 Pet 3:21   this water symbolises baptism
    Heb 11:19    he received him back from the dead, figuratively

`signalmatch.py` had the same blind spot without showing it: `Exo.34.6-8`
matched `Psa.103.8-12` because both are Hebrew. The method was never tested
across the boundary and would have failed.

## What can cross

**Stamps are language-independent.** Jonah 2 and Galatians 2 share
`death_produces_life`, `humiliation_to_vindication` and `resurrection_ev` --
three rare traits in common, no shared vocabulary, opposite sides of the
canon. That is the typological link, and it is already in the data.

So a link is scored by the RARITY of what two passages share, not the amount:
two sections agreeing on `people_of_god` have agreed on nothing, and two
agreeing on `dying_and_rising_with_christ` (11 sections in the corpus) have
agreed on almost everything they could.

    score = sum over shared traits of log(N / how many sections carry it)

## What this is not

A shared trait is a shared STAMP, and a stamp is a model's reading. Two
passages linked here are two passages a model described the same way, which
is weaker than two passages that share words. The link is a proposal for a
reader, not a claim that the text asserts a type -- the taxonomy's own
`_intent` again: a finding aid, not an authority.

    python tools/crosslink.py --of Jon.2.1
    python tools/crosslink.py --testaments --top 40
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
SRC = OUT / "stamps-leveled.jsonl"

NT = {"Matt", "Mark", "Luke", "John", "Acts", "Rom", "1Cor", "2Cor", "Gal",
      "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus",
      "Phlm", "Heb", "Jas", "1Pet", "2Pet", "1John", "2John", "3John",
      "Jude", "Rev"}


# Two categories are excluded, each for its own measured reason.
#
# `character_roles` is over-stamped -- established 2026-09-14 when Gen 1:24
# "The Sixth Day" came back carrying bridegroom, builder and fisherman. Left
# in, it links Job 38 to The Rich Young Man through fisherman, vinedresser and
# woman_folly, and those links dominated the first run.
#
# `devices` are GENRE markers. Every Hebrew poem carries inclusio and
# synonymous parallelism, so they make all poetry look alike and say nothing
# about what a passage is about.
NOISE = {"character_roles", "devices"}


def load():
    sec = collections.defaultdict(set)
    title = {}
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("category") in NOISE:
            continue
        sec[d["ref"]].add(d["id"])
        title[d["ref"]] = d.get("title", "")
    df = collections.Counter()
    for ids in sec.values():
        df.update(ids)
    return sec, title, df


def score(a, b, df, n):
    """Rarity of what two passages share. Common agreement is not agreement."""
    both = a & b
    if not both:
        return 0.0, []
    s = sum(math.log(n / max(df[x], 1)) for x in both)
    return s, sorted(both, key=lambda x: df[x])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--of", help="a section ref, e.g. Jon.2.1")
    ap.add_argument("--testaments", action="store_true",
                    help="the strongest OT<->NT links in the whole corpus")
    ap.add_argument("--min-shared", type=int, default=3)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    sec, title, df = load()
    n = len(sec)
    is_nt = {r: r.split(".")[0] in NT for r in sec}

    if a.of:
        me = sec.get(a.of)
        if not me:
            raise SystemExit(f"no stamps for {a.of}")
        out = []
        for r, ids in sec.items():
            if r == a.of:
                continue
            s, both = score(me, ids, df, n)
            if len(both) >= a.min_shared:
                out.append((s, r, both))
        out.sort(reverse=True)
        print(f"{a.of}  {title.get(a.of,'')}  "
              f"[{'NT' if is_nt[a.of] else 'OT'}]\n")
        for s, r, both in out[:a.top]:
            side = "NT" if is_nt[r] else "OT"
            mark = "  <-- crosses" if is_nt[r] != is_nt[a.of] else ""
            print(f"  {s:6.1f} [{side}] {r:<14} {title.get(r,'')[:34]:<36}"
                  f"{mark}")
            print(f"         {', '.join(f'{x}({df[x]})' for x in both[:5])}")
        return 0

    refs = sorted(sec)
    out = []
    for i, x in enumerate(refs):
        for y in refs[i + 1:]:
            if is_nt[x] == is_nt[y]:
                continue                      # the lemma layer has these
            s, both = score(sec[x], sec[y], df, n)
            if len(both) >= a.min_shared and s > 0:
                out.append((s, x, y, both))
    out.sort(reverse=True)
    print(f"{len(out):,} cross-testament links "
          f"({a.min_shared}+ shared traits)\n")
    for s, x, y, both in out[:a.top]:
        ot, nt = (x, y) if not is_nt[x] else (y, x)
        print(f"  {s:6.1f}  {ot:<13} {title.get(ot,'')[:26]:<28} "
              f"~  {nt:<13} {title.get(nt,'')[:26]}")
        print(f"          {', '.join(f'{t}({df[t]})' for t in both[:5])}")

    if a.write:
        p = OUT / "crosstestament.jsonl.gz"
        with gzip.open(p, "wt", encoding="utf-8") as f:
            f.write(json.dumps({"_note": "OT<->NT links by shared RARE stamps. "
                                "The lemma allusion layer cannot cross the "
                                "testaments at all -- different languages. "
                                "See tools/crosslink.py."}) + "\n")
            for s, x, y, both in out:
                ot, nt = (x, y) if not is_nt[x] else (y, x)
                f.write(json.dumps({"ot": ot, "nt": nt, "score": round(s, 2),
                                    "shared": both}) + "\n")
        print(f"\n  -> {p.relative_to(ROOT)}  {len(out):,} links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
