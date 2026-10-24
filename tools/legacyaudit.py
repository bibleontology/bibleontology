"""Where the legacy graph still exceeds the computed floor — measured, not assumed.

2026-09-11: next, an audit of the places where the legacy graph exceeds the
new. Then, after the first version, the audit was to be rebuilt.

## Why it needed rebuilding

The first version decided coverage by a **type-level mapping** — `likened_to`
is covered by the comparison layer, `told` by the speaker layer, `took` by the
frame layer — written down as "a stated mapping, not a computation... the part
to argue with". Nobody argued with it, including its author, because **a stated
assumption renders identically to a verified result once it is in a table.**

Every one of those mappings overstated coverage. Measured per relation:

    claimed                       measured
    comparisons / allusions 100%    23%     (found via the image_* namespace)
    frames, action relations 100%    46%
    speakers, speech         100%    55%

So this version has **no type-level mapping at all**. Every claim of coverage
is a probe run against the actual layer output for that relation's own verses.
A type is covered to whatever degree its relations individually test covered,
which is usually neither 0% nor 100%.

## The probes

    people      both endpoints named in the people layer
    places      the place endpoint named in the place layer
    kinship     the two names typed as a bond
    frames      a frame in the verse whose predicate glosses to this action
    speakers    an attribution exists in the verse
    comparison  a marked simile exists (vehicle and tenor)
    metaphor    an X-is-Y with a nominal predicate exists

A relation is covered if any applicable probe fires. The probe that fired is
recorded, so the claim is inspectable rather than trusted.

## What it writes

    out/legacy-delta.jsonl.gz      relations no probe covers -- the overlay
    out/legacy-reasoning.jsonl.gz  notes that REASON rather than quote,
                                   retained for EVERY relation including the
                                   covered ones, because a note recording a
                                   doubt qualifies a relation we now derive
                                   with unwarranted confidence

## The namespace check, which a type-based view cannot do

The legacy graph names conventions in its node ids, not only in its types:
`image_*` (507 relations, 246 nodes) and `pattern_*` (225, 87). `image_*` cuts
across `draws_on`, `likened_to`, `speaks_of` and `signifies`; no type-level
report could show it, and that is how the figure gap stayed hidden. Coverage is
therefore reported by namespace as well as by type.
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import pathlib
import re

import provenance

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "legacy-delta.jsonl.gz"
REASON_DEST = OUT / "legacy-reasoning.jsonl.gz"

BOOK = {"Gen": "Gen", "Exod": "Exo", "Exo": "Exo", "Lev": "Lev", "Num": "Num",
        "Deut": "Deu", "Deu": "Deu", "Josh": "Jos", "Judg": "Jdg",
        "Ruth": "Rut", "1Sam": "1Sa", "2Sam": "2Sa", "1Kgs": "1Ki",
        "2Kgs": "2Ki", "1Chr": "1Ch", "2Chr": "2Ch", "Job": "Job", "Ps": "Psa",
        "Prov": "Pro", "Eccl": "Ecc", "Isa": "Isa", "Jer": "Jer",
        "Lam": "Lam", "Ezek": "Ezk", "Dan": "Dan", "Hos": "Hos", "Joel": "Jol",
        "Amos": "Amo", "Jonah": "Jon", "Mic": "Mic", "Nah": "Nam",
        "Hab": "Hab", "Zeph": "Zep", "Hag": "Hag", "Zech": "Zec", "Mal": "Mal",
        "Matt": "Mat", "Mark": "Mrk", "Luke": "Luk", "John": "Jhn",
        "Acts": "Act", "Rom": "Rom", "1Cor": "1Co", "2Cor": "2Co",
        "Gal": "Gal", "Eph": "Eph", "Phil": "Php", "Col": "Col",
        "1Thess": "1Th", "2Thess": "2Th", "1Tim": "1Ti", "2Tim": "2Ti",
        "Titus": "Tit", "Phlm": "Phm", "Heb": "Heb", "Jas": "Jas",
        "1Pet": "1Pe", "2Pet": "2Pe", "1John": "1Jn", "2John": "2Jn",
        "3John": "3Jn", "Jude": "Jud", "Rev": "Rev", "Neh": "Neh",
        "Ezra": "Ezr", "Esth": "Est", "Song": "Sng", "Obad": "Oba"}
SHORT = {v: k for k, v in BOOK.items()}
RX = re.compile(r"^\s*([1-3]?\s?[A-Za-z]+)\s+(\d+):(\d+)")
BSB = {}

# An action relation is covered when a frame in its own verse carries THAT
# action. Matching is on MACULA's English gloss, because the legacy node ids
# are English and the frame lemmas are Hebrew and Greek -- the first attempt
# compared the two directly and reported 0%, which was the test failing rather
# than the layer.
ACTION = {
    "took": "took|take|taking", "gave": "gave|give|given",
    "made": "made|make", "killed": "kill|slew|slay|smote|smite",
    "sent": "sent|send", "ate": "ate|eat", "built": "built|build",
    "carried": "carr|bore|bare", "destroyed": "destroy",
    "attacked": "attack|smote|fought", "healed": "heal",
    "fought": "fought|fight", "conquered": "conquer|took|subdu",
    "repaired": "repair", "blessed": "bless", "wore": "wore|clothed|put on",
    "bought": "bought|buy", "offered": "offer", "anointed": "anoint",
    "imprisoned": "prison|bound", "cast_into": "cast",
    "led": "led|lead|brought", "observed": "observ|kept|saw",
    "heard": "heard|hear", "appeared_to": "appear",
    "came_upon": "came|come", "judged": "judg",
}
SPEECH = {"told", "answered", "besought", "rebuked", "charged", "warned",
          "accused", "explained", "quoted", "cursed", "asserted_by",
          "wrote_to", "wrote_letter_to", "named", "spoke", "commanded"}
FIGURE = {"likened_to", "signifies", "token_of", "spoken_of_as", "draws_on",
          "drawn_from"}
PLACE = {"located_in", "traveled_to", "dwelt_at", "ruled_from", "buried_at",
         "based_at", "died_at", "born_at", "kept_at", "stationed_at",
         "founded", "reigned_over", "cast_into"}
KIN = {"father_of", "mother_of", "sibling_of", "spouse_of", "ancestor_of",
       "descended_from_person", "half_sibling_of", "uncle_of",
       "adoptive_parent_of", "concubine_of", "betrothed_to",
       "predecessor_of"}
JUDGMENT = {"assessed_as", "conditional_on", "grounds", "contrary_to",
            "supersedes", "distinguished_from", "self_designated_as",
            "ascribed_to"}


def parse(x):
    m = RX.match(str(x))
    if not m:
        return None
    b = BOOK.get(m.group(1).replace(" ", ""))
    return f"{b}.{int(m.group(2))}.{int(m.group(3))}" if b else None


def rows(name):
    p = OUT / name
    if not p.exists():
        return
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                if not any(k.startswith("_") for k in d):
                    yield d


def key(n):
    return str(n).split("_")[0].lower()


def main() -> int:
    for line in (ROOT / "data/bible/verses.bsb.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            if "b" in d:
                BSB[(SHORT.get(d["b"], d["b"]), d["c"], d["v"])] = \
                    d["t"].lower()

    rels = []
    for f in sorted(glob.glob(str(ROOT / "ontology/relations/*.jsonl"))):
        for line in pathlib.Path(f).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rels.append(json.loads(line))

    # ---- the layers, loaded once -----------------------------------------
    frames = collections.defaultdict(list)
    for d in rows("frames.jsonl.gz"):
        frames[d["ref"]].append(d)
    people = collections.defaultdict(set)
    for d in rows("people-xref.jsonl.gz"):
        for p in d.get("people", []):
            nm = (p.get("name") or "").lower().replace("of ", "").strip()
            if nm:
                people[d["ref"]].add(nm.split()[0])
    placed = collections.defaultdict(set)
    for d in rows("places.jsonl.gz"):
        for p in d.get("places", []):
            nm = (p.get("name") or "").lower().strip()
            if nm:
                placed[d["ref"]].add(nm.split()[0])
    kinpair = set()
    for d in rows("kinship.jsonl.gz"):
        x, y = (d.get("a") or "").lower().split(), (d.get("b") or "").lower().split()
        if x and y:
            kinpair.add(tuple(sorted((x[0], y[0]))))
    speakers = collections.defaultdict(list)
    for d in rows("speakers.jsonl.gz"):
        speakers[d["ref"]].append(d)
    comps = collections.defaultdict(list)
    for d in rows("comparisons.jsonl.gz"):
        comps[d["ref"]].append(d)
    mets = collections.defaultdict(list)
    for d in rows("metaphor.jsonl.gz"):
        mets[d["ref"]].append(d)
    print(f"layers: frames {len(frames):,} verses | people {len(people):,} | "
          f"places {len(placed):,} | kinship {len(kinpair):,} pairs | "
          f"speakers {len(speakers):,} | simile {len(comps):,} | "
          f"metaphor {len(mets):,}")

    # ---- probes: each returns the layer name if it covers, else None -----
    # The pattern layers built 2026-09-12. A legacy relation pointing at a
    # pattern_* node counts as covered when one of our computed forms has an
    # instance in the same verses. That is WEAKER than naming the same
    # pattern -- it says we found A form there, not THE form -- and the report
    # labels it so.
    formed = set()
    for name in ("formulaic.jsonl.gz", "clauseforms.jsonl.gz"):
        for d in rows(name):
            if d.get("kind") == "instance_of":
                formed.add(str(d.get("src", "")).split("-")[0])
    print(f"pattern layers: {len(formed):,} verses carry a computed form")

    def probe(r, refs):
        t = r["type"]
        if str(r.get("dst", "")).startswith("pattern_") and \
                any(x in formed for x in refs):
            return "a form found there"
        s, d = key(r["src"]), key(r["dst"])
        if t in PLACE:
            pool = set()
            for x in refs:
                pool |= placed.get(x, set())
            if s in pool or d in pool:
                return "places"
        if t in KIN and tuple(sorted((s, d))) in kinpair:
            return "kinship"
        if t in ACTION:
            rx = re.compile(ACTION[t], re.I)
            if any(rx.search(f.get("gloss") or "")
                   for x in refs for f in frames.get(x, [])):
                return "frames"
        if t in SPEECH and any(speakers.get(x) for x in refs):
            return "speakers"
        if t in FIGURE:
            if any(comps.get(x) for x in refs):
                return "comparison"
            if any(mets.get(x) for x in refs):
                return "metaphor"
        pool = set()
        for x in refs:
            pool |= people.get(x, set())
        if s in pool and d in pool:
            return "people (both named)"
        return None

    stat = collections.defaultdict(collections.Counter)
    byprobe = collections.Counter()
    delta, reasoning = [], []
    for r in rels:
        t = r["type"]
        refs = [x for x in (parse(v) for v in (r.get("refs") or [])) if x]
        s = stat[t]
        s["n"] += 1
        note = (r.get("note") or "").strip()
        if note:
            v = " ".join(BSB.get((x.split(".")[0], int(x.split(".")[1]),
                                  int(x.split(".")[2])), "") for x in refs)
            words = re.findall(r"[a-z]{4,}", note.lower())
            share = (sum(1 for w in words if w in v) / len(words)
                     if words and v else 0)
            if not (v and share >= 0.75):
                reasoning.append({"type": t, "src": r["src"], "dst": r["dst"],
                                  "refs": r.get("refs"), "note": note})
        by = probe(r, refs)
        if by:
            s["covered"] += 1
            byprobe[by] += 1
            continue
        # speaks_of is the shape recognised as the project's mistake;
        # kept out of the delta so it does not inflate the work remaining.
        bucket = ("superseded-by-design" if t == "speaks_of"
                  else "judgment" if t in JUDGMENT
                  else "place" if t in PLACE
                  else "kinship" if t in KIN
                  else "figure" if t in FIGURE
                  else "action" if t in ACTION
                  else "speech" if t in SPEECH
                  else "other")
        delta.append({"bucket": bucket, "type": t, "src": r["src"],
                      "dst": r["dst"], "refs": r.get("refs"), "note": note})

    tot = len(rels)
    cov = sum(s["covered"] for s in stat.values())
    print(f"\nlegacy relations {tot:,}   covered by a MEASURED probe "
          f"{cov:,} ({100*cov/tot:.0f}%)")
    print("  which probe fired:",
          {k: v for k, v in byprobe.most_common()})

    print(f"\n{'type':<22}{'n':>6}{'covered':>9}")
    for t, s in sorted(stat.items(), key=lambda kv: -kv[1]["n"])[:16]:
        print(f"  {t:<20}{s['n']:>6}{100*s['covered']/s['n']:>8.0f}%")

    # namespaces -- what a type-based view structurally cannot show
    print("\nBY NODE NAMESPACE (a type-based report cannot see these):")
    for pre in ("image_", "pattern_"):
        got = [r for r in rels if str(r.get("dst", "")).startswith(pre)
               or str(r.get("src", "")).startswith(pre)]
        d = sum(1 for r in got
                if any(x["src"] == r["src"] and x["dst"] == r["dst"]
                       for x in delta))
        print(f"  {pre:<12}{len(got):>5} relations   "
              f"{100*(len(got)-d)/max(len(got),1):>3.0f}% covered")

    bk = collections.Counter(d["bucket"] for d in delta)
    print("\nTHE DELTA, by what it is:")
    for k, v in bk.most_common():
        print(f"  {k:<24}{v:>6,}")
    real = sum(v for k, v in bk.items() if k != "superseded-by-design")
    print(f"\n  genuine delta (excluding speaks_of): {real:,}")

    for dest, payload, note in (
        (DEST, delta,
         "Legacy relations NO MEASURED PROBE covers. Coverage is tested per "
         "relation against the actual layer output for its own verses -- "
         "there is no type-level mapping, because every such mapping in the "
         "first version overstated coverage (frames 46% not 100%, speakers "
         "55% not 100%, figures 23% not 100%)."),
        (REASON_DEST, reasoning,
         "Notes that REASON rather than quote, retained for every relation "
         "INCLUDING covered ones: a note recording a doubt qualifies a "
         "relation the floor now derives with unwarranted confidence."),
    ):
        with gzip.open(dest, "wt", encoding="utf-8") as f:
            f.write(json.dumps({
                **provenance.stamp(__file__, inputs=[
                    "ontology/relations/*.jsonl", "out/frames.jsonl.gz",
                    "out/people-xref.jsonl.gz", "out/places.jsonl.gz",
                    "out/kinship.jsonl.gz", "out/speakers.jsonl.gz",
                    "out/comparisons.jsonl.gz", "out/metaphor.jsonl.gz"]),
                "_note": note,
            }, ensure_ascii=False) + "\n")
            for d in payload:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        print(f"  wrote {dest.relative_to(ROOT)}  ({len(payload):,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
