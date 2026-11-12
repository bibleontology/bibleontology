"""Strong's Hebrew Dictionary on the Hebrew word cards (tools/lexicon/strongs_hebrew.py; 2026-11-07).

  1. The committed extract (data/lexicon/strongs-hebrew.json): 8,674 entries, each with Strong's definition; none
     carries the Brown-Driver-Briggs outline the source file also holds ("1) to love, 1a) (Qal) ...", "(TWOT)").
  2. Where the source file is on disk (data/raw/strongs, git-ignored): the extract is exactly what the extractor
     makes from it, and no entry carries its KJV renderings (the file's own "translation" note).
  3. The server credits it as Strong's, public domain, its definition and derivation only, and links Open
     Scriptures, never STEP, and names no other translation (no word page may); the abridged BDB stays withheld
     (HEBREW_DEFINITIONS_SHOWN is False).

Each check is proved by a planted fault. Run: python -X utf8 tests/test_strongs_hebrew.py"""
import copy
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "lexicon"))
sys.path.insert(0, str(ROOT / "app2"))
import strongs_hebrew as SH  # noqa: E402

DOC = json.loads((ROOT / "data" / "lexicon" / "strongs-hebrew.json").read_text(encoding="utf-8"))
OUTLINE = re.compile(r"(^|\s)\d+[a-z]?\d*[a-z]?\)\s|\(TWOT\)")


def kjv_notes():
    """{key: its KJV renderings}, from the source file, or None where it is not on disk."""
    if not SH.SRC.exists():
        return None
    import xml.etree.ElementTree as ET
    root = ET.fromstring(SH.SRC.read_bytes())
    out = {}
    for div in root.iter(SH.NS + "div"):
        w = div.find(SH.NS + "w")
        if div.get("type") != "entry" or w is None or not (w.get("ID") or "").startswith("H"):
            continue
        for n in div.findall(SH.NS + "note"):
            if n.get("type") == "translation":
                out["h" + w.get("ID")[1:].lstrip("0")] = SH.text_of(n)
    return out


KJV = kjv_notes()


def faults(doc, credit, link, shown):
    f = []
    e = doc["entries"]
    if len(e) != 8674:
        f.append(f"{len(e)} entries, not 8,674")
    for k, v in e.items():
        if not v.get("definition"):
            f.append(f"{k}: no definition")
            break
        if OUTLINE.search(v["definition"]) or OUTLINE.search(v.get("derivation") or ""):
            f.append(f"{k}: carries the BDB outline: {v['definition'][:60]!r}")
            break
    if KJV is not None:
        for k, v in e.items():
            r = KJV.get(k)
            if r and len(r) > 12 and (r in v["definition"] or r in (v.get("derivation") or "")):
                f.append(f"{k}: carries its KJV renderings: {r[:50]!r}")
                break
    for must in ("Strong", "1894", "public domain", "definition and derivation only"):
        if must not in credit:
            f.append(f"the credit does not say {must!r}")
    if re.search(r"\b(KJV|AV)\b|King James", credit):
        f.append("the credit names the King James Version, which no word page may")
    if "openscriptures" not in link or "STEPBible" in link:
        f.append(f"the link is {link!r}, not Open Scriptures'")
    if shown:
        f.append("the abridged Brown-Driver-Briggs is shown (HEBREW_DEFINITIONS_SHOWN)")
    return f


import server as S  # noqa: E402

fails = faults(DOC, S.LEXICON_CREDIT["strongs"], S.LEXICON_LINK["strongs"], S.HEBREW_DEFINITIONS_SHOWN)
if KJV is not None:
    fresh = SH.extract()
    if fresh != DOC["entries"]:
        fails.append("the committed extract differs from what the extractor makes from the pinned source")
else:
    print("(the source file is not on disk: checks 2 skipped)")

planted = []
bad = copy.deepcopy(DOC)
bad["entries"]["h157"]["definition"] += " 1) to love 1a) (Qal)"
planted.append(("the BDB outline in an entry", faults(bad, S.LEXICON_CREDIT["strongs"], S.LEXICON_LINK["strongs"], False)))
if KJV is not None:
    bad = copy.deepcopy(DOC)
    bad["entries"]["h157"]["definition"] += " " + KJV["h157"]
    planted.append(("an entry's KJV renderings", faults(bad, S.LEXICON_CREDIT["strongs"], S.LEXICON_LINK["strongs"], False)))
planted.append(("a credit without the public-domain line", faults(DOC, "Strong's Hebrew Dictionary (1894). Its "
                                                                     "definition and derivation only.",
                                                                     S.LEXICON_LINK["strongs"], False)))
planted.append(("a credit naming the KJV", faults(DOC, S.LEXICON_CREDIT["strongs"] + " The KJV renderings are cut.",
                                                  S.LEXICON_LINK["strongs"], False)))
planted.append(("STEP's link on Strong's", faults(DOC, S.LEXICON_CREDIT["strongs"], "https://www.STEPBible.org", False)))
planted.append(("the BDB switched on", faults(DOC, S.LEXICON_CREDIT["strongs"], S.LEXICON_LINK["strongs"], True)))
caught = sum(1 for _w, f in planted if f)
fails += [f"planted: {w} was not caught" for w, f in planted if not f]
for m in fails:
    print("FAIL", m)
print(f"Strong's Hebrew: {len(DOC['entries']):,} entries; planted faults caught: {caught} of {len(planted)}; "
      f"{len(fails)} failures")
sys.exit(1 if fails else 0)
