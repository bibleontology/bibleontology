"""The Berean's own notes on the manuscripts, for showing at the verse.

2026-10-08, on Mark 16:16 in a theme outline: mark it site-wide --
wherever a verse of Mark's longer ending (or John 7:53-8:11) is shown, the
Berean's own note that the earliest manuscripts lack it goes with it. The
Berean prints such notes as footnotes; this collects every footnote that
speaks of manuscripts, keyed to the verse it stands on, and spreads a note
that names a passage ("do not include John 7:53 through John 8:11", "Mark
16:9-20") to every verse of that passage.

    python tools/manuscript_notes.py   -> out/manuscript-notes.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "raw" / "usfm" / "engbsb"
OUT = ROOT / "out" / "manuscript-notes.json"

# USFM book code -> the site's book id (data/bible/verses.bsb.jsonl "b")
CODE = {"GEN": "Gen", "EXO": "Exod", "LEV": "Lev", "NUM": "Num", "DEU": "Deut", "JOS": "Josh",
        "JDG": "Judg", "RUT": "Ruth", "1SA": "1Sam", "2SA": "2Sam", "1KI": "1Kgs", "2KI": "2Kgs",
        "1CH": "1Chr", "2CH": "2Chr", "EZR": "Ezra", "NEH": "Neh", "EST": "Esth", "JOB": "Job",
        "PSA": "Ps", "PRO": "Prov", "ECC": "Eccl", "SNG": "Song", "ISA": "Isa", "JER": "Jer",
        "LAM": "Lam", "EZK": "Ezek", "DAN": "Dan", "HOS": "Hos", "JOL": "Joel", "AMO": "Amos",
        "OBA": "Obad", "JON": "Jonah", "MIC": "Mic", "NAM": "Nah", "HAB": "Hab", "ZEP": "Zeph",
        "HAG": "Hag", "ZEC": "Zech", "MAL": "Mal", "MAT": "Matt", "MRK": "Mark", "LUK": "Luke",
        "JHN": "John", "ACT": "Acts", "ROM": "Rom", "1CO": "1Cor", "2CO": "2Cor", "GAL": "Gal",
        "EPH": "Eph", "PHP": "Phil", "COL": "Col", "1TH": "1Thess", "2TH": "2Thess", "1TI": "1Tim",
        "2TI": "2Tim", "TIT": "Titus", "PHM": "Phlm", "HEB": "Heb", "JAS": "Jas", "1PE": "1Pet",
        "2PE": "2Pet", "1JN": "1John", "2JN": "2John", "3JN": "3John", "JUD": "Jude", "REV": "Rev"}
FOOT = re.compile(r"\\f \+ \\fr (\d+)[:.](\d+)\s*\\ft (.*?)\\f\*", re.S)
MARKUP = re.compile(r"\\\+?[a-z]+\d?\*?|\|[a-z]+=\"[^\"]*\"")
# a note naming a whole passage the manuscripts lack: "John 7:53 through
# John 8:11", "Mark 16:9-20"
SPAN = re.compile(r"(?:verses? |)(\d+):(\d+)\s*(?:through|–|-)\s*(?:\w+ )?(?:(\d+):)?(\d+)")


def main():
    verses = set()
    for line in (ROOT / "data" / "bible" / "verses.bsb.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if "b" in d:
            verses.add((d["b"], d["c"], d["v"]))
    notes = {}
    for f in sorted(SRC.glob("*.usfm")):
        s = f.read_text(encoding="utf-8")
        code = re.search(r"\\id (\w+)", s).group(1)
        b = CODE.get(code)
        if not b:
            continue
        for m in FOOT.finditer(s):
            text = re.sub(r"\s+", " ", MARKUP.sub("", m.group(3))).strip()
            if not re.search(r"manuscript", text, re.I):
                continue
            c, v = int(m.group(1)), int(m.group(2))
            keys = [(b, c, v)]
            sp = SPAN.search(text) if re.search(r"do not include|not include", text, re.I) else None
            if sp:
                c1, v1 = int(sp.group(1)), int(sp.group(2))
                c2, v2 = int(sp.group(3) or c1), int(sp.group(4))
                keys = [(b, cc, vv) for cc in range(c1, c2 + 1)
                        for vv in range(v1 if cc == c1 else 1, (v2 if cc == c2 else 200) + 1)
                        if (b, cc, vv) in verses]
            # "Early manuscripts end the Gospel of Mark after verse 8": the
            # note stands on 16:8 and speaks of every verse after it
            end = re.search(r"end the [\w ]+? after verse (\d+)", text, re.I)
            if end:
                keys += [(b, c, vv) for vv in range(int(end.group(1)) + 1, 200) if (b, c, vv) in verses]
            for k in keys:
                key = f"{k[0]}.{k[1]}.{k[2]}"
                if text not in notes.setdefault(key, []):
                    notes[key].append(text)
    OUT.write_text(json.dumps({"_source": "Berean Standard Bible footnotes (public domain) that speak of "
                                          "the manuscripts, keyed to the verse; a note naming a passage the "
                                          "earliest manuscripts lack is on every verse of it",
                               "notes": notes}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(notes)} verses carry a manuscript note -> {OUT.relative_to(ROOT)}")
    for k in ("Mark.16.8", "Mark.16.9", "Mark.16.16", "John.7.53", "John.8.11", "Luke.23.34", "1John.5.7"):
        print(" ", k, notes.get(k))


if __name__ == "__main__":
    main()
