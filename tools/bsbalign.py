"""Which English words of the Berean text stand for which word of the original.

2026-09-19, after the misleading emphasis was removed: if the words in the BSB
can be pinpointed, the emphasis is wanted in both texts; it had seemed it might
be hard to guess.

It does not have to be guessed. **The Berean editors tagged their own English
with Strong's numbers**, so the alignment is theirs rather than ours:

    \\w the|strong="H5002"\\w* prophecy \\w of|strong="H5869"\\w*

The emphasis that was removed WAS a guess -- it collected every word of a
template and of all its fillers, then bolded any of them anywhere in the verse,
so Numbers 24:4 lit up "the" and "words" because another instance of the
pattern is filled with "words". This is a different thing: a span the
translators themselves attached to a lexeme.

## The tag opens a run

A tag marks where a rendering STARTS. `prophecy` carries no tag of its own;
only the `the` before it does. So a span is the tagged word plus the bare words
that follow it, up to the next tag — the same rule `tools/bsbwords.py` arrived
at, and for the same reason.

## What it is not

**Not a word-level alignment, and this file says so rather than implying
otherwise.** The Berean text sometimes leaves English untagged that belongs to
a different word of the original, and the run then swallows it: in Jeremiah,
`\\w the|strong="H5002"\\w* land` makes `land` -- which is אֶרֶץ -- look like
part of נְאֻם. At Numbers 24:4 the second `the words` is tagged H5002 where the
word is really אִמְרֵי H561.

So the spans are offered as **the translators' own marking, approximate**, and
the reader is told that. Highlighting a span the editors attached to this
lexeme is a claim about their file; claiming it is the exact word is a claim
about Hebrew, and only the first is made.

    python tools/bsbalign.py            # accuracy against the interlinear
    python tools/bsbalign.py --write
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
SRC = ROOT / "data" / "raw" / "usfm" / "engbsb"
DEST = OUT / "bsb-align.jsonl.gz"

WORD = re.compile(
    r'\\w ([^|\\]+)\|[^\\]*?strong="([HG]\d+[a-z]?)"[^\\]*?\\w\*([^\\]*)')
NOTE = re.compile(r"\\f .*?\\f\*", re.S)
VERSE = re.compile(r"\\v (\d+)\s")
CHAP = re.compile(r"\\c (\d+)")
IDLINE = re.compile(r"\\id\s+(\w+)")
MARKUP = re.compile(r"\\[a-z0-9]+\*?\s?")

USFM_TO_REF = {
    "GEN": "Gen", "EXO": "Exo", "LEV": "Lev", "NUM": "Num", "DEU": "Deu",
    "JOS": "Jos", "JDG": "Jdg", "RUT": "Rut", "1SA": "1Sa", "2SA": "2Sa",
    "1KI": "1Ki", "2KI": "2Ki", "1CH": "1Ch", "2CH": "2Ch", "EZR": "Ezr",
    "NEH": "Neh", "EST": "Est", "JOB": "Job", "PSA": "Psa", "PRO": "Pro",
    "ECC": "Ecc", "SNG": "Sng", "ISA": "Isa", "JER": "Jer", "LAM": "Lam",
    "EZK": "Ezk", "DAN": "Dan", "HOS": "Hos", "JOL": "Jol", "AMO": "Amo",
    "OBA": "Oba", "JON": "Jon", "MIC": "Mic", "NAM": "Nam", "HAB": "Hab",
    "ZEP": "Zep", "HAG": "Hag", "ZEC": "Zec", "MAL": "Mal", "MAT": "Mat",
    "MRK": "Mrk", "LUK": "Luk", "JHN": "Jhn", "ACT": "Act", "ROM": "Rom",
    "1CO": "1Co", "2CO": "2Co", "GAL": "Gal", "EPH": "Eph", "PHP": "Php",
    "COL": "Col", "1TH": "1Th", "2TH": "2Th", "1TI": "1Ti", "2TI": "2Ti",
    "TIT": "Tit", "PHM": "Phm", "HEB": "Heb", "JAS": "Jas", "1PE": "1Pe",
    "2PE": "2Pe", "1JN": "1Jn", "2JN": "2Jn", "3JN": "3Jn", "JUD": "Jud",
    "REV": "Rev",
}


def key_of(strong: str):
    lang, num = strong[0].lower(), re.sub(r"[^0-9]", "", strong[1:])
    num = re.sub(r"^0+", "", num)
    return f"{lang}{num}" if num else None


def verses():
    """-> {ref: [(text, [[start, end, key], ...])]} for the Berean text."""
    out = {}
    for f in sorted(SRC.glob("*.usfm")):
        raw = f.read_text(encoding="utf-8", errors="replace")
        m = IDLINE.search(raw)
        bk = USFM_TO_REF.get((m.group(1) if m else "").upper())
        if not bk:
            continue
        chap = 0
        # split on verse markers, keeping chapter state
        for chunk in re.split(r"(?=\\[cv] )", NOTE.sub(" ", raw)):
            cm = CHAP.match(chunk)
            if cm:
                chap = int(cm.group(1))
                continue
            vm = VERSE.match(chunk)
            if not vm or not chap:
                continue
            ref = f"{bk}.{chap}.{int(vm.group(1))}"
            body = chunk[vm.end():]
            # OFFSETS ARE RECORDED AGAINST THE FINISHED TEXT. Collapsing
            # whitespace at the end -- after the spans were measured -- shifted
            # every one of them, so Numbers 24:4 reported `es a` and `sion f`
            # where it meant `sees a vision`. Each piece is therefore
            # normalised as it is appended, and nothing touches the string
            # afterwards.
            def add(text, piece):
                piece = re.sub(r"\s+", " ", MARKUP.sub("", piece))
                if not text:
                    piece = piece.lstrip()
                elif text.endswith(" ") and piece.startswith(" "):
                    piece = piece.lstrip()
                return text + piece

            text, spans = "", []
            pos = 0
            while pos < len(body):
                w = WORD.search(body, pos)
                if not w:
                    text = add(text, body[pos:])
                    break
                text = add(text, body[pos:w.start()])
                start = len(text)
                text = add(text, w.group(1) + (w.group(3) or ""))
                k = key_of(w.group(2))
                if k and len(text) > start:
                    spans.append([start, len(text.rstrip()), k])
                pos = w.end()
            text = text.rstrip()
            spans = [s for s in spans if s[0] < len(text) and s[1] > s[0]]
            if text:
                out[ref] = (text, spans)
    return out


def winnow(vs):
    """Drop spans whose English belongs to a different lexeme.

    The tag is over-applied: measured against the interlinear, 47.3% of
    verse-and-lexeme pairs carry MORE spans than the verse has occurrences of
    that word. Numbers 24:4 tags H5002 twice, once on `the prophecy`, which is
    right, and once on `the words`, which is אִמְרֵי H561.

    `out/bsb-words.json` already settled this question for the word cards: a
    rendering belongs to the lexeme that claims it most across the corpus, and
    `words` is claimed overwhelmingly by H561. So a span survives when its
    content word is one this lexeme is actually known to be rendered by.

    Where a lexeme has no recorded renderings at all -- proper names mostly,
    and anything too rare to have registered -- nothing is dropped, because an
    empty list is ignorance rather than evidence of a wrong span.
    """
    p = OUT / "bsb-words.json"
    if not p.exists():
        print("  (no out/bsb-words.json -- run tools/bsbwords.py; "
              "spans left unwinnowed)")
        return vs
    known = {k: {w for w, _n in rows}
             for k, rows in (json.loads(p.read_text(encoding="utf-8"))
                             .get("words") or {}).items()}
    SUPPLIED = {"the", "a", "an", "of", "to", "and", "in", "on", "at", "for",
                "with", "is", "are", "was", "were", "be", "that", "this",
                "it", "he", "she", "they", "his", "their", "i", "you", "we"}
    kept = dropped = 0
    out = {}
    for ref, (text, spans) in vs.items():
        keep = []
        for s, e, k in spans:
            good = known.get(k)
            if not good:
                keep.append([s, e, k])
                kept += 1
                continue
            words = [w for w in re.findall(r"[A-Za-z']+", text[s:e].lower())
                     if w not in SUPPLIED]
            # A span of nothing but supplied English says only that the editors
            # hung a tag on an article. Numbers 24:4 carries a bare `the` for
            # H5002 beside the real `the prophecy`, and highlighting both makes
            # the reader look for a second occurrence that is not there.
            if not words:
                dropped += 1
                continue
            # the whole span, or any content word in it
            if text[s:e].strip().lower() in good \
                    or any(w in good for w in words):
                keep.append([s, e, k])
                kept += 1
            else:
                dropped += 1
        out[ref] = (text, keep)
    print(f"winnowed: kept {kept:,}, dropped {dropped:,} "
          f"({dropped/max(kept+dropped,1):.1%}) whose English belongs "
          f"elsewhere\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    if not SRC.exists():
        raise SystemExit(f"missing {SRC}")
    vs = verses()
    tot = sum(len(s) for _t, s in vs.values())
    print(f"{len(vs):,} verses, {tot:,} tagged spans\n")

    # ACCURACY, against the interlinear rather than asserted. A span is right
    # when the verse really does contain that lexeme; it cannot prove the span
    # covers the right English, only that the lexeme is there to be covered.
    have = {}
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if not d.get("ref"):
            continue
        ks = set()
        for w in d.get("words") or []:
            s = w.get("s")
            if s:
                lang = "h" if any("\u0590" <= c <= "\u05ff"
                                  for c in (w.get("t") or "")) else "g"
                n = re.sub(r"^0+", "", re.sub(r"[^0-9]", "", s))
                if n:
                    ks.add(lang + n)
        have[d["ref"]] = ks
    ok = bad = 0
    for ref, (_t, spans) in vs.items():
        ks = have.get(ref)
        if not ks:
            continue
        for _s, _e, k in spans:
            if k in ks:
                ok += 1
            else:
                bad += 1
    print(f"spans whose lexeme IS in that verse: {ok:,} of {ok+bad:,} "
          f"({ok/max(ok+bad,1):.1%})")
    print("   -- the tag names a word the verse contains; it does not prove")
    print("      the span covers the English that renders it\n")

    vs = winnow(vs)

    probe = vs.get("Num.24.4")
    if probe:
        t, sp = probe
        print("Num 24:4 —", t[:70])
        for s, e, k in sp[:6]:
            print(f"   {k:<8} {t[s:e]!r}")

    if not a.write:
        print("\nnothing written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_source": "Berean Standard Bible USFM, ebible.org, Public Domain.",
            "_note": "Per verse, the character spans the BEREAN EDITORS tagged "
                     "with each Strong's number, as `[start, end, key]` over "
                     "the verse text given here. A tag opens a run: it marks "
                     "where a rendering starts, so a span is the tagged word "
                     "plus the untagged words after it. APPROXIMATE -- the "
                     "editors leave some English untagged and the run then "
                     "swallows it. This is their marking, not a computed "
                     "alignment. See tools/bsbalign.py."}) + "\n")
        for ref, (text, spans) in sorted(vs.items()):
            fh.write(json.dumps({"ref": ref, "text": text, "spans": spans},
                                ensure_ascii=False) + "\n")
    print(f"\n  -> {DEST.relative_to(ROOT)}  {len(vs):,} verses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
