"""THE VERSE MAP CHECKED AGAINST STEP BIBLE'S (2026-10-24).

out/versemap.json maps a MACULA (Hebrew-numbered) verse to the Berean verse that
carries its text, found by aligning each book on Strong's numbers (tools/versify.py).
Two of the image audit's evidence packs found it wrong in Hosea: the site showed
the vine at 14:8 where the vine is 14:7, and the wrong text at 12:12. The map had
mapped Hosea 12:6-10 and 14:2, 14:10, and not 12:1-5, 12:11-15 or 14:3-9.

STEP Bible's Translators Amalgamated Hebrew OT (TAHOT, Tyndale House, CC BY 4.0;
already a source here) writes each word's English reference with the Hebrew one
beside it where they differ: "Hos.12.1(12.2)" is English 12:1, Hebrew 12:2. That
is a versification table made by people whose work it is, so the alignment is
checked against it, verse by verse.

    python tools/versemap_step.py            report where the two disagree
    python tools/versemap_step.py --table    also write out/versemap-step.json
                                             (Hebrew -> English, from STEP)
"""
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = re.compile(r"^([1-3]?[A-Za-z]{2,3})\.(\d+)\.(\d+)(?:\((\d+)\.(\d+)\))?#")


def step_table():
    """Hebrew (MACULA-style) verse -> English verse, where STEP says they differ"""
    table = {}
    for f in sorted(glob.glob(str(ROOT / "data" / "raw" / "stepbible" / "TAHOT *.txt"))):
        for ln in open(f, encoding="utf-8"):
            m = REF.match(ln)
            if m and m.group(4):
                b, c, v, hc, hv = m.groups()
                table[f"{b}.{hc}.{hv}"] = f"{b}.{c}.{v}"
    return table


def main():
    step = step_table()
    moved = json.loads((ROOT / "out" / "versemap.json").read_text(encoding="utf-8"))["moved"]
    books = {k.split(".")[0] for k in step}
    missing = sorted(k for k in step if k not in moved and step[k] != k)
    wrong = sorted(k for k in moved if k in step and moved[k] != step[k])
    extra = sorted(k for k in moved if k.split(".")[0] in books and k not in step)
    print(f"STEP renumbers {len(step)} Hebrew verses; the map moves {len(moved)}")
    print(f"  in STEP, not in the map: {len(missing)}  e.g. {missing[:8]}")
    print(f"  in both, to different verses: {len(wrong)}  e.g. {[(k, moved[k], step[k]) for k in wrong[:6]]}")
    print(f"  in the map, not in STEP: {len(extra)}  e.g. {[(k, moved[k]) for k in extra[:8]]}")
    by = {}
    for k in missing + wrong:
        by[k.split(".")[0]] = by.get(k.split(".")[0], 0) + 1
    print("  disagreements by book:", sorted(by.items(), key=lambda kv: -kv[1]))
    if "--table" in sys.argv:
        (ROOT / "out" / "versemap-step.json").write_text(json.dumps(step, indent=0, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
