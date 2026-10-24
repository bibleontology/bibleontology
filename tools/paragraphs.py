"""An editor's paragraph divisions, as an independent check on our boundaries.

2026-09-09, setting the terms before the data existed: whatever sources are
freely available may be used to help with the structure; they are not taken
blindly, but are probably a useful data point; ideally they are used as a
benchmark first and a tiebreaker overlay when stuck.

**Benchmark first, tiebreaker only when stuck.** That ordering is what keeps
this honest, and it is stricter than it sounds: a paragraph mark must never
become a feature the boundary scorer reads, because then measuring against it
would be fitting and checking on one dataset. It is held out, used to score,
and consulted for a decision only inside the band where our own signals tie.

## Where it comes from, and why it is legitimate here

Principle 44: a translation may supply **structure** the source does not record,
never **identity** it does. Paragraphing qualifies exactly. Hebrew and Greek
manuscripts carry no paragraph marks of this kind, MACULA encodes none, so an
editor's division is not a lossy copy of something we could read at source -- it
is an independent judgement about where a unit ends, made by people who never
saw our signals.

Fetched from ebible.org, the same source `data/raw/WEB.json` already records.
The earlier download took the `_vpl` package -- **verse per line**, which
strips exactly this. The USFM package carries it.

**Licence, read rather than assumed** (the failure this session already made
once): each package ships a `copr.htm` stating the text is in the **Public
Domain**. "World English Bible" is a trademark of eBible.org, which constrains
what a modified text may be *called*, not what may be read from it.

## Only one of the two is usable, and that is a finding

Both WEB and YLT were requested so two editors could be compared. Measured:

    WEB    8,170 \\p   764 \\b   8,176 \\q1   10,676 \\q2     real paragraphing
    YLT    1,189 \\p                                        ONE PER CHAPTER

YLT's USFM marks each chapter as a single paragraph and nothing finer, so it
carries no division to compare. Reported rather than quietly dropped: the plan
was two independent opinions and there is one.

## What counts as a break

    \\p    a new paragraph
    \\b    a blank line, typically a stronger break than \\p
    \\m    a paragraph with no first-line indent
    \\q1   a poetry line. NOT counted as a break -- Hebrew verse sets a new
          line every colon, so counting these would mark every second clause
          and drown the signal.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
USFM = ROOT / "data" / "raw" / "usfm"
DEST = ROOT / "out" / "paragraphs.jsonl.gz"

BREAK = {"p", "b", "m", "nb", "pi", "pmo", "pm", "pc"}
USFM_BOOK = {
    "GEN": "Gen", "EXO": "Exo", "LEV": "Lev", "NUM": "Num", "DEU": "Deu",
    "JOS": "Jos", "JDG": "Jdg", "RUT": "Rut", "1SA": "1Sa", "2SA": "2Sa",
    "1KI": "1Ki", "2KI": "2Ki", "1CH": "1Ch", "2CH": "2Ch", "EZR": "Ezr",
    "NEH": "Neh", "EST": "Est", "JOB": "Job", "PSA": "Psa", "PRO": "Pro",
    "ECC": "Ecc", "SNG": "Sng", "ISA": "Isa", "JER": "Jer", "LAM": "Lam",
    "EZK": "Ezk", "DAN": "Dan", "HOS": "Hos", "JOL": "Jol", "AMO": "Amo",
    "OBA": "Oba", "JON": "Jon", "MIC": "Mic", "NAM": "Nam", "HAB": "Hab",
    "ZEP": "Zep", "HAG": "Hag", "ZEC": "Zec", "MAL": "Mal",
    "MAT": "Mat", "MRK": "Mrk", "LUK": "Luk", "JHN": "Jhn", "ACT": "Act",
    "ROM": "Rom", "1CO": "1Co", "2CO": "2Co", "GAL": "Gal", "EPH": "Eph",
    "PHP": "Php", "COL": "Col", "1TH": "1Th", "2TH": "2Th", "1TI": "1Ti",
    "2TI": "2Ti", "TIT": "Tit", "PHM": "Phm", "HEB": "Heb", "JAS": "Jas",
    "1PE": "1Pe", "2PE": "2Pe", "1JN": "1Jn", "2JN": "2Jn", "3JN": "3Jn",
    "JUD": "Jud", "REV": "Rev",
}
MARK = re.compile(r"^\\([a-z]+[0-9]?)(?:\s|$)")
VERSE = re.compile(r"^\\v\s+(\d+)")
CHAP = re.compile(r"^\\c\s+(\d+)")
FNAME = re.compile(r"^\d+-([A-Z0-9]{3})")


def scan(pkg):
    """-> {ref: kind}, the first verse after each paragraph break."""
    out, marks = {}, collections.Counter()
    for p in sorted((USFM / pkg).glob("*.usfm")):
        m = FNAME.match(p.name)
        book = USFM_BOOK.get(m.group(1)) if m else None
        if not book:
            continue
        ch, pending = 0, None
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            mk = MARK.match(line)
            if not mk:
                continue
            tag = mk.group(1)
            marks[tag] += 1
            c = CHAP.match(line)
            if c:
                ch = int(c.group(1))
                pending = None          # a chapter start is not evidence
                continue
            if tag in BREAK:
                pending = tag
                continue
            v = VERSE.match(line)
            if v and pending:
                out[f"{book}.{ch}.{int(v.group(1))}"] = pending
                pending = None
    return out, marks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    web, wm = scan("engwebp")
    ylt, ym = scan("engylt")
    print(f"WEB paragraph starts: {len(web)}   markers {dict(wm.most_common(6))}")
    print(f"YLT paragraph starts: {len(ylt)}   markers {dict(ym.most_common(4))}")
    if len(ylt) < 2000:
        print("  -> YLT marks one paragraph per chapter; unusable as a second"
              " opinion. Reported, not hidden.")

    kinds = collections.Counter(web.values())
    print(f"\nWEB break kinds: {dict(kinds)}")

    # --- score OUR signals against this held-out benchmark -----------------
    def load(n):
        r = []
        with gzip.open(ROOT / "out" / n, "rt", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    if not any(k.startswith("_") for k in d):
                        r.append(d)
        return r

    def parts(ref):
        p = str(ref).split(".")
        return ((p[0], int(p[1]), int(p[2]))
                if len(p) > 2 and p[1].isdigit() and p[2].isdigit() else None)

    S = [s for s in load("sentence-function.jsonl.gz") if parts(s["ref"])]
    S.sort(key=lambda s: (parts(s["ref"])[0], parts(s["ref"])[1],
                          parts(s["ref"])[2], s.get("id") or ""))
    depth = {d["ref"]: d["depth"] for d in load("speech-depth.jsonl.gz")}
    ag = collections.defaultdict(set)
    for r in load("frames.jsonl.gz"):
        for x in (r.get("agent") or []):
            ag[r["ref"]].add(x)

    base = sum(1 for s in S if s["ref"] in web) / len(S)
    print(f"\nBENCHMARK: does a signal land on an EDITOR'S paragraph start?")
    print(f"  base rate {100*base:.1f}%  ({len(web)} starts over {len(S)} sentences)")

    def score(pred, name):
        hits = [s for i, s in enumerate(S)
                if i and parts(S[i-1]["ref"])[0] == parts(s["ref"])[0]
                and pred(S[i-1], s)]
        if not hits:
            print(f"  {name:<28} (never fires)")
            return
        on = sum(1 for s in hits if s["ref"] in web)
        print(f"  {name:<28} fires {len(hits):>6}  hit {100*on/len(hits):>5.1f}%"
              f"  lift {(on/len(hits))/base:>5.2f}x")

    score(lambda a_, b: depth.get(a_["ref"], 0) > 0 and depth.get(b["ref"], 0) == 0,
          "speech RETURNS to narration")
    score(lambda a_, b: (depth.get(a_["ref"]) is not None
                         and depth.get(b["ref"]) is not None
                         and depth[a_["ref"]] != depth[b["ref"]]),
          "speech depth change")
    score(lambda a_, b: b.get("relation") == "temporal", "temporal connective")
    score(lambda a_, b: a_.get("direction") == "sequence"
          and b.get("direction") != "sequence", "chain break")
    score(lambda a_, b: ag.get(a_["ref"]) and ag.get(b["ref"])
          and not (ag[a_["ref"]] & ag[b["ref"]]), "agent turnover")
    score(lambda a_, b: b.get("direction") == "free", "free sentence")
    score(lambda a_, b: (depth.get(a_["ref"], 0) > 0 and depth.get(b["ref"], 0) == 0)
          and b.get("relation") == "temporal", "speech ends + temporal")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": "World English Bible, ebible.org, engwebp USFM. Public "
                       "Domain per the package's own copr.htm; 'World English "
                       "Bible' is a trademark of eBible.org.",
            "_note": "Verses at which the editor begins a new paragraph. HELD "
                     "OUT: never a feature of the boundary scorer, only a "
                     "benchmark, and a tiebreaker only where our own signals "
                     "tie (Doug, 2026-09-09). Poetry lines are not counted as "
                     "breaks; Hebrew verse would mark every colon.",
        }, ensure_ascii=False) + "\n")
        for ref, kind in sorted(web.items()):
            f.write(json.dumps({"ref": ref, "break": kind},
                               ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(web)} paragraph starts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
