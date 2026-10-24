"""Every recorded thought in the ontology, kept apart from every quotation.

2026-09-11: dropped notes should be looked at for the whole graph.

`tools/legacyaudit.py` had been reading `ontology/relations/` and nothing else.
Scanning everything:

    relations/       15,030 rows   12,702 noted     786,893 chars
    proposals/       57,811        18,234           728,388     never read
    retired/         17,168        11,136           327,044     never read
    candidates/          55            23             3,821
    entities/         8,416             0                 0
                                  --------------------------
                                     42,095         1,846,146

**1.85 million characters of recorded reasoning, of which the relation files
are 43%.** The other 57% sat in two directories nothing had ever opened.

`proposals/` is the larger surprise: 26MB of candidate extractions, most never
promoted into the graph, and carrying MORE notes than the graph itself.

## The field-name bug this found

The hand-markings of a reader in `ontology/readings-held.jsonl` record their
reasoning in a field called **`said`**, not `note`. A scan keyed on `note`
reported zero notes for them — the 43 judgments that are the most carefully
made content in the repository. Field names are not a schema here; they are
whatever each writer chose, so this reads a set of them and prints which it
found, so the next missing one is visible rather than silent.

## Quotation is not reasoning

A note that repeats its verse adds nothing a reader cannot see; one using words
the verse does not is where a person thought. The test is mechanical — what
share of the note's content words appear in the cited text — and it separates

    "brought it to his father, and said to him, My father, sit up and eat of
     your son's game"                                            QUOTATION

    "The verse is spoken by Job, though the verse itself does not name him;
     the surrounding chapter (Job 9:1) identifies him as the speaker."
                                                                 REASONING

The second is the shape that matters, because it says where an inference was
made. `tools/speakers.py` asserts 10,311 attributions and cannot say which of
them rest on a chapter-level inference. That note can.

## Why retain it even where the floor reproduces the relation

Because the note and the relation are different claims, and only one of them
regenerates. Reproducing a relation without the doubt recorded against it
yields more confidence than the text supports — see the case of the two Zanoahs
(measured 2026-09-11).
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re

import provenance

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEST = ROOT / "out" / "reasoning.jsonl.gz"

# Field names that have carried reasoning in this repository. NOT a schema --
# each writer chose its own, and `said` was missed for a whole session because
# the scan assumed `note`. The run prints which fields it actually found, so
# the next one that is missing shows up as an absence rather than a silence.
FIELDS = ("note", "notes", "said", "why", "reason", "reasoning", "rationale",
          "comment", "evidence", "justification", "caveat", "verdict",
          "explanation", "uncertainty")

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
RX = re.compile(r"^\s*([1-3]?\s?[A-Za-z]+)\s+(\d+):(\d+)")


def load_bsb():
    short = {v: k for k, v in BOOK.items()}
    out = {}
    for line in (ROOT / "data/bible/verses.bsb.jsonl").read_text(
            encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            if "b" in d:
                out[(short.get(d["b"], d["b"]), d["c"], d["v"])] = \
                    d["t"].lower()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    bsb = load_bsb()

    def text_for(o):
        out = []
        refs = o.get("refs") or ([o["ref"]] if o.get("ref") else [])
        for x in refs:
            m = RX.match(str(x))
            if m and BOOK.get(m.group(1).replace(" ", "")):
                out.append(bsb.get((m.group(1).replace(" ", ""),
                                    int(m.group(2)), int(m.group(3))), ""))
            elif isinstance(x, str) and x.count(".") == 2:
                b, c, v = x.split(".")
                try:
                    out.append(bsb.get((b, int(c), int(v)), ""))
                except ValueError:
                    pass
        return " ".join(out)

    found = collections.Counter()
    bysrc = collections.defaultdict(collections.Counter)
    rows = []
    for p in sorted((ROOT / "ontology").rglob("*.json*")):
        if p.suffix not in (".json", ".jsonl"):
            continue
        src = p.relative_to(ROOT / "ontology").parts[0]
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        lines = txt.splitlines() if p.suffix == ".jsonl" else [txt]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            for o in (d if isinstance(d, list) else [d]):
                if not isinstance(o, dict):
                    continue
                for f in FIELDS:
                    val = o.get(f)
                    if not isinstance(val, str) or not val.strip():
                        continue
                    found[f] += 1
                    note = val.strip()
                    v = text_for(o)
                    words = re.findall(r"[a-z]{4,}", note.lower())
                    share = (sum(1 for w in words if w in v) / len(words)
                             if words and v else 0)
                    kind = "quotation" if (v and share >= 0.75) else "reasoning"
                    bysrc[src][kind] += 1
                    if kind == "reasoning":
                        rows.append({
                            "from": src, "file": p.name, "field": f,
                            "type": o.get("type") or o.get("kind"),
                            "src": o.get("src"), "dst": o.get("dst"),
                            "refs": o.get("refs") or o.get("ref"),
                            "text": note,
                        })

    print("FIELDS THAT ACTUALLY CARRIED REASONING")
    for k, v in found.most_common():
        print(f"  {k:<14}{v:>8,}")
    missing = [f for f in FIELDS if not found.get(f)]
    print(f"  looked for and never found: {', '.join(missing)}")

    print(f"\n{'source':<16}{'reasoning':>11}{'quotation':>11}")
    for s, c in sorted(bysrc.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"  {s:<14}{c['reasoning']:>11,}{c['quotation']:>11,}")
    tot = sum(c["reasoning"] for c in bysrc.values())
    print(f"\n  reasoning entries: {tot:,}   "
          f"({sum(len(r['text']) for r in rows):,} characters)")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            **provenance.stamp(__file__, inputs=["ontology/**/*.jsonl",
                                                 "ontology/**/*.json"]),
            "_note": "Recorded reasoning from EVERY file under ontology/, not "
                     "only the promoted relations. Notes that merely quote "
                     "their verse are excluded. Retained regardless of "
                     "whether the computed floor reproduces the claim they "
                     "sit on: a note saying 'two Zanoahs are listed and the "
                     "verse does not say which' qualifies a relation we can "
                     "now derive with unwarranted confidence.",
        }, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(rows):,} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
