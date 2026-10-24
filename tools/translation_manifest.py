"""Pin the translation files the way MACULA's files are pinned.

2026-09-09, after finding that the World English Bible in a Bible app
renders the divine name *Yahweh* through Psalm 103 while our copy renders
*LORD* 6,576 times and *Yahweh* not once.

Same translation, different **edition** -- and neither of us could tell which
edition our file is, because nothing in it says. `data/macula-manifest.json`
pins a version, a sha256 and a byte count for every one of 959 MACULA files.
The entire header of `verses.bsb.jsonl` is `{"translation": "BSB"}`.

That gap cost real time twice in one session: once identifying the WEB edition,
once discovering the KJV file has lost the divine name entirely.

## What this can and cannot record

It records what is **measurable from the file**: a sha256, a byte count, verse
and book counts, and a set of edition fingerprints that distinguish editions of
the same translation.

**The source URL was not lost, only dropped.** The first draft of this module
said provenance "cannot be recovered by inspecting the bytes" and that was
wrong: `data/raw/*.json` carries a `source` field which the flattening step to
`data/bible/verses.*.jsonl` did not carry forward.

    BSB   https://bereanbible.com/bsb.txt
    WEB   https://ebible.org/Scriptures/engwebp_vpl.zip     <- names the EDITION
    YLT   https://ebible.org/Scriptures/engylt_vpl.zip
    ASV   none recorded
    KJV   none recorded

The WEB entry is the one that mattered: `engwebp` identifies which of eBible's
World English Bible packages this is, which is exactly the question that could
not be answered about an app's copy. Two files genuinely have no source and
are still emitted as `null` -- a manifest that invents a provenance is worse
than one that admits it lacks one.

## The fingerprints, and why these

    spelling        savior/honor/neighbor vs saviour/honour/neighbour.
                    Separates a US edition from a British one.
    divine_name     how YHWH is rendered: LORD, Yahweh or Jehovah. This is
                    what exposed the app's WEB edition as different from ours.
    name_distinct   whether YHWH and Adonai are DISTINGUISHABLE at all.
                    The KJV file on disk fails this: LORD 6, Lord 7,719,
                    because the small caps did not survive its conversion.
    speech_marks    whether the edition punctuates direct speech, which
                    `tools/speech.py` depends on. KJV and ASV do not.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIBLE = ROOT / "data" / "bible"
DEST = ROOT / "data" / "translation-manifest.json"

FILES = ("verses.jsonl", "verses.bsb.jsonl", "verses.web.jsonl",
         "verses.asv.jsonl", "verses.ylt.jsonl")

# The flattening step to data/bible/ dropped these; data/raw/ still has them.
RAW = ROOT / "data" / "raw"
RAW_FILE = {"verses.jsonl": "KJV.json", "verses.bsb.jsonl": "BSB.json",
            "verses.web.jsonl": "WEB.json", "verses.asv.jsonl": "ASV.json",
            "verses.ylt.jsonl": "YLT.json"}


def _raw_sources():
    out = {}
    for flat, raw in RAW_FILE.items():
        p = RAW / raw
        if p.exists():
            try:
                out[flat] = json.loads(p.read_text(encoding="utf-8")).get("source")
            except (ValueError, OSError):
                out[flat] = None
    return out


BRITISH = ("saviour", "honour", "colour", "favour", "neighbour", "labour")
AMERICAN = ("savior", "honor", "color", "favor", "neighbor", "labor")


def count(text, word):
    return len(re.findall(rf"\b{word}\b", text))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    RAW_SOURCE = _raw_sources()
    out = {}
    for name in FILES:
        p = BIBLE / name
        if not p.exists():
            print(f"  {name}: MISSING")
            continue
        raw = p.read_bytes()
        header, rows = None, {}
        for line in raw.decode("utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if "b" in d:
                rows[(d["b"], d["c"], d["v"])] = d["t"]
            elif header is None:
                header = d
        text = " ".join(rows.values())
        low = text.lower()

        br = sum(low.count(w) for w in BRITISH)
        us = sum(low.count(w) for w in AMERICAN)
        divine = {w: count(text, w) for w in ("LORD", "Lord", "Yahweh",
                                              "Jehovah", "GOD")}
        # is YHWH distinguishable from Adonai in this file at all?
        distinct = max(divine["LORD"], divine["Yahweh"],
                       divine["Jehovah"]) > 1000
        quotes = sum(1 for t in rows.values() if "“" in t)

        out[name] = {
            "declared": header,
            "source_url": RAW_SOURCE.get(name),
            "retrieved": None,
            "licence": None,
            "_unknown": "retrieved and licence were never recorded. source_url "
                        "is carried over from data/raw/*.json where that file "
                        "records one; null means none was recorded, never a "
                        "guess.",
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "verses": len(rows),
            "books": len({b for (b, _, _) in rows}),
            "fingerprints": {
                "spelling": ("american" if us and not br else
                             "british" if br and not us else "mixed/unknown"),
                "american_hits": us,
                "british_hits": br,
                "divine_name": divine,
                "name_distinct": distinct,
                "speech_marked_verses": quotes,
                "speech_marked_share": round(100 * quotes / max(len(rows), 1), 1),
            },
        }

    print(f"{'file':<20}{'verses':>7}{'spelling':>11}{'YHWH as':>10}"
          f"{'distinct':>10}{'speech':>8}")
    for name, m in out.items():
        f = m["fingerprints"]
        d = f["divine_name"]
        as_ = max(("LORD", "Yahweh", "Jehovah"), key=lambda k: d[k])
        print(f"  {name:<18}{m['verses']:>7}{f['spelling']:>11}"
              f"{as_ + '=' + str(d[as_]):>16}"
              f"{('yes' if f['name_distinct'] else 'NO'):>8}"
              f"{f['speech_marked_share']:>7.1f}%")

    bad = [n for n, m in out.items() if not m["fingerprints"]["name_distinct"]]
    if bad:
        print(f"\n  DIVINE NAME NOT DISTINGUISHABLE: {', '.join(bad)}")
        print("  The ruling of 2026-09-09: demote to verse-numbering only.")

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    DEST.write_text(json.dumps({
        "_note": "What is measurable about each translation file, plus the "
                 "source URL carried over from data/raw/*.json, which the "
                 "flattening step to data/bible/ had dropped. Retrieval date "
                 "and licence were never recorded anywhere and stay null; a "
                 "null source means none was recorded, never a guess. "
                 "Fingerprints distinguish EDITIONS of the same translation, "
                 "which is what was missing when a World English Bible from an app "
                 "rendered the divine name differently from ours.",
        "files": out,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(out)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
