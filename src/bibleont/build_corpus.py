"""Normalize downloaded translation JSON into the project's verse store.

KJV is the primary text: every citation in the ontology resolves against it, and
the per-book text files extraction agents read are built from it.

ASV (1901, public domain) is built alongside as a secondary, verse-aligned text.
It is not used for citations. Its job is proper nouns: the KJV renders New
Testament names through Greek ("Urias", "Booz", "Roboam") while the ASV
normalizes them to their Hebrew forms ("Uriah", "Boaz", "Rehoboam"). Comparing
the two verse by verse yields the name equivalences mechanically instead of by
hand — see bibleont.crosswalk.

Outputs:
  data/bible/verses.jsonl      KJV, one record per verse: {"b","c","v","t"}
  data/bible/verses.asv.jsonl  ASV, same shape (only if data/raw/ASV.json exists)
  data/bible/text/<Book>.txt   KJV plain text, one verse per line, "Gen 5:3\tIn the..."

Usage:  python -m bibleont.build_corpus
"""

from __future__ import annotations

import json
import sys

from .books import BOOK_TITLE, SOURCE_NAME_TO_ID
from .paths import BIBLE, BOOK_TEXT, RAW, VERSES_JSONL

# The source uses typographic punctuation. The en dash stands in for the maqqef
# inside compound proper names ("Bath-sheba", "Beth-el"); folding these to ASCII
# keeps name matching simple without changing any word.
_PUNCT = str.maketrans({"’": "'", "–": "-", "—": "-"})


def build(translation: str, out_path, write_text_files: bool) -> int:
    """Normalize one translation. Returns the verse count, or -1 if absent."""
    src = RAW / f"{translation}.json"
    if not src.exists():
        return -1

    data = json.loads(src.read_text(encoding="utf-8"))
    total = 0
    with out_path.open("w", encoding="utf-8", newline="\n") as out:
        out.write(json.dumps({"translation": translation}) + "\n")
        for book in data["books"]:
            bid = SOURCE_NAME_TO_ID.get(book["name"])
            if bid is None:
                print(f"unmapped book name: {book['name']!r}", file=sys.stderr)
                return -1
            lines = [f"# {BOOK_TITLE[bid]} ({bid}) — {translation}"]
            for chapter in book["chapters"]:
                c = int(chapter["chapter"])
                for verse in chapter["verses"]:
                    v = int(verse["verse"])
                    text = " ".join(verse["text"].translate(_PUNCT).split())
                    out.write(
                        json.dumps({"b": bid, "c": c, "v": v, "t": text}, ensure_ascii=False)
                        + "\n"
                    )
                    lines.append(f"{bid} {c}:{v}\t{text}")
                    total += 1
            if write_text_files:
                (BOOK_TEXT / f"{bid}.txt").write_text(
                    "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
                )
    return total


def main() -> int:
    if not (RAW / "KJV.json").exists():
        print(f"missing {RAW / 'KJV.json'}; download it first", file=sys.stderr)
        return 1

    BIBLE.mkdir(parents=True, exist_ok=True)
    BOOK_TEXT.mkdir(parents=True, exist_ok=True)

    total = build("KJV", VERSES_JSONL, write_text_files=True)
    if total < 0:
        return 1
    print(f"wrote {total} KJV verses to {VERSES_JSONL}")
    print(f"wrote 66 book text files to {BOOK_TEXT}")

    # Every secondary text is built the same way and aligned to the same verse
    # ids. `bibleont.acquire` is what guarantees the alignment; this step only
    # normalises the shape.
    #
    # The ASV came first and is still the one the name crosswalk uses. The
    # other three are there so a reader can choose the English they read in,
    # and because the five of them do not agree about which verses exist --
    # which is data rather than noise. Sorted by what they omit they fall into
    # manuscript families, not into old and new:
    #
    #     YLT   0 absent    Textus Receptus, like the KJV
    #     WEB   4 absent
    #     ASV  16 absent
    #     BSB  16 absent    the critical-text set exactly
    for name in ("ASV", "YLT", "WEB", "BSB"):
        path = VERSES_JSONL.with_suffix(f".{name.lower()}.jsonl")
        count = build(name, path, write_text_files=False)
        if count < 0:
            note = (" (name crosswalk will be unavailable)"
                    if name == "ASV" else "")
            print(f"{name}.json not present - skipping{note}")
        else:
            print(f"wrote {count} {name} verses to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
