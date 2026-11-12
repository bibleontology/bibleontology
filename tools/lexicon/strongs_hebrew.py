"""Strong's own Hebrew dictionary (James Strong, 1894; public domain), the Hebrew word card's second lexicon.

The design (docs/review/permissions/sdbh-2026-11-02.md, Doug: "I would be open to including two lexicons and
crediting both since we have Strongs and that is widely sourced"): UBS's senses lead; Strong's sits one tap below,
with its own credit. Downloaded 2026-11-06 with Doug's yes ("Yes, the XML"): Open Scriptures' OSIS encoding,
hebrew/StrongHebrewG.xml at commit 0acd2f25 (6,436,400 bytes), whose header states the work is Public Domain.

WHAT IS STRONG'S, AND WHAT IS NOT. Each entry carries three things, and only two are Strong's 1894 text:
  - the derivation (note type="exegesis": "a primitive root"; "from אָרָה (in the sense of gathering)") and the
    definition (note type="explanation": "father, in a literal and immediate, or figurative and remote
    application"): kept;
  - the KJV's renderings (note type="translation"): cut, under the KJV-removal rule;
  - a numbered outline (<list>: "1) to love, 1a) (Qal), 1a1) human love ..."), which is not Strong's but the
    Brown-Driver-Briggs outline, with TWOT senses marked in it ("2)(TWOT) coffin"). The abridged BDB is withheld
    from the site under the Online Bible's permission note (app2/server.py, HEBREW_DEFINITIONS_SHOWN), so this
    outline is dropped too. Found reading the file, 2026-11-07.

    python tools/lexicon/strongs_hebrew.py      -> data/lexicon/strongs-hebrew.json (committed: public domain)
"""
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "raw" / "strongs" / "StrongHebrewG.xml"
OUT = ROOT / "data" / "lexicon" / "strongs-hebrew.json"
SHA256 = "1f9659ea208f4c498843a0280dacb1448627c33ca77712642d8705793ab66061"
COMMIT = "0acd2f251c2d35ff8db2dece4e0593979d3ac223"
URL = f"https://raw.githubusercontent.com/openscriptures/strongs/{COMMIT}/hebrew/StrongHebrewG.xml"
NS = "{http://www.bibletechnologies.net/2003/OSIS/namespace}"
CREDIT = ("Strong's Hebrew Dictionary (James Strong, 1894), public domain; the electronic text by Open Scriptures, "
          "encoded by David Troidl after David Instone-Brewer")


def text_of(el):
    """A note's text: a cross-reference <w> as its Hebrew word and transliteration, with its Strong's number; <hi>
    as plain text."""
    out = [el.text or ""]
    for ch in el:
        if ch.tag == NS + "w":
            bit = ch.get("lemma") or ""
            if ch.get("xlit"):
                bit += f" ({ch.get('xlit')})"
            if ch.get("src"):
                bit += f" [H{ch.get('src')}]"
            out.append(bit)
        else:
            out.append("".join(ch.itertext()))
        out.append(ch.tail or "")
    return re.sub(r"\s+", " ", "".join(out)).strip()


def extract():
    raw = SRC.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != SHA256:
        sys.exit(f"{SRC.name}: sha256 {got}, not the pinned {SHA256}. Fetch {URL}")
    root = ET.fromstring(raw)
    entries = {}
    for div in root.iter(NS + "div"):
        if div.get("type") != "entry":
            continue
        w = div.find(NS + "w")
        if w is None or not (w.get("ID") or "").startswith("H"):
            continue
        key = "h" + w.get("ID")[1:].lstrip("0")
        notes = {n.get("type"): n for n in div.findall(NS + "note")}
        entries[key] = {"lemma": w.get("lemma") or "", "xlit": w.get("xlit") or "", "pron": w.get("POS") or "",
                        "derivation": text_of(notes["exegesis"]) if "exegesis" in notes else "",
                        "definition": text_of(notes["explanation"]) if "explanation" in notes else ""}
    return entries


def main():
    entries = extract()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = {"_source": {"work": CREDIT, "url": URL, "sha256": SHA256, "licence": "Public Domain",
                       "kept": "the derivation and the definition, Strong's own text",
                       "cut": "the KJV renderings (the KJV-removal rule) and the numbered outline (Brown-Driver-"
                              "Briggs's, with TWOT senses, withheld from the site)"},
           "entries": dict(sorted(entries.items(), key=lambda kv: int(re.sub(r"\D", "", kv[0]) or 0)))}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=0) + "\n", encoding="utf-8", newline="\n")
    print(f"{OUT.relative_to(ROOT)}: {len(entries):,} entries, {OUT.stat().st_size:,} bytes; "
          f"with a definition {sum(1 for e in entries.values() if e['definition']):,}")


if __name__ == "__main__":
    main()
