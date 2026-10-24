"""Word-level original-language strip, one line per verse.

2026-09-05: the original language and the selected translation are to be shown
by default, with some way to understand the mapping between the two, without
trying to be a Bible app.

The last clause is the constraint that shapes this. A full interlinear is a
Bible-app feature and a large undertaking; what is actually needed is **enough
alignment to follow a thread from an English word back to the word underneath
it**. So this extracts the original words in their own order with the gloss
each one carries, and stops there. No parsing display, no morphology tables, no
parallel translations.

## Why not the source already on disk

`data/raw/stepbible/index.json` holds exactly this alignment and is better
tagged. It is read-from-disk-only: the licence asks that others be referred to
github.com/STEPBible rather than served copies, and an app endpoint is serving
a copy. MACULA is CC BY 4.0 and may be redistributed with attribution, so the
strip is built from MACULA and the question to STEPBible stays a courtesy
rather than a dependency.

## What one line holds

    ref     Gen.1.1
    words   [{t: surface form, g: gloss, l: lemma, s: Strong's, p: pos}, …]

Word order is the ORIGINAL order, which is the point -- Hebrew puts the verb
first and English does not, and seeing that is most of what a reader gets from
looking at the original at all.

    python tools/interlinear.py
"""
from __future__ import annotations

import glob
import gzip
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from macula import MAC, _ref                                      # noqa: E402
from graphnodes import _pos, _text                                # noqa: E402

OUT = ROOT / "out"


# SDBH and Louw-Nida ride along inside MACULA as `sdbh`, `lexdomain`,
# `coredomain`, `domain` and `ln`. Those are UBS, permission-based, and already
# set aside by this project -- the existing macula-clauses extract excludes them
# by name. Listed here so nobody adds them back by reaching for "one more field".
FORBIDDEN = {"sdbh", "lexdomain", "coredomain", "sensenumber", "domain", "ln"}

# What MACULA knows about a word that the app was not showing. `transliteration`
# is the pronunciation; `greek`/`greekstrong` is the LXX equivalent of a Hebrew
# word, which is the cross-language bridge the sense profiles could not build.
META = ("transliteration", "greek", "greekstrong", "stem", "state", "case",
        "tense", "voice", "mood", "degree", "normalized")


# GREEK HAS NO TRANSLITERATION ATTRIBUTE; HEBREW DOES. 2026-09-16: the sound
# and the definition are wanted below each original-language
# word. MACULA Hebrew carries `transliteration` per word and MACULA Greek
# carries none, so the Greek is generated here from the standard
# correspondences -- deterministic, and better than leaving half the corpus
# unpronounceable.
_GK = {
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "ē",
    "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x",
    "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y",
    "φ": "ph", "χ": "ch", "ψ": "ps", "ω": "ō",
}


def translit_greek(word):
    """A readable approximation, not a scholarly scheme.

    Accents and breathings are stripped rather than rendered: a rough
    pronunciation is the point, and `ἀγάπη -> agapē` serves a reader who cannot
    read the alphabet, which is the whole reason this exists.
    """
    import unicodedata as _u
    bare = [c for c in _u.normalize("NFD", word or "") if not _u.combining(c)]
    out = []
    for i, ch in enumerate(bare):
        low = ch.lower()
        # Upsilon is "u" inside a diphthong and "y" alone: Ἰησοῦς is iēsous,
        # not iēsoys, and πνεῦμα is pneuma.
        if low == "υ" and i and bare[i - 1].lower() in "αεηο":
            out.append("u")
            continue
        out.append(_GK.get(low, "" if not ch.isalnum() else ch))
    return "".join(out)


def lemma_meta(root, meta):
    for w in root.iter("w"):
        # Greek MACULA words carry NO `lang` attribute, so keying off it put
        # every Greek lemma under `h` and collided it with Hebrew -- agape had
        # no grammar and hesed was showing Greek tenses. The reliable
        # discriminator is which Strong's field is present: Hebrew uses
        # `strongnumberx`, Greek uses `strong`.
        heb = bool(w.get("strongnumberx"))
        s = (w.get("strongnumberx") or w.get("strong") or "")
        num = "".join(ch for ch in s if ch.isdigit()).lstrip("0")
        if not num:
            continue
        k = ("h" if heb else "g") + num
        m = meta.setdefault(k, {"n": 0, "f": {}})
        m["n"] += 1
        for a in META:
            v = w.get(a)
            if v:
                m["f"].setdefault(a, {})
                m["f"][a][v] = m["f"][a].get(v, 0) + 1


def main() -> int:
    path = OUT / "interlinear.jsonl.gz"
    verses, words = 0, 0
    meta = {}
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_source": "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., "
                       "CC BY 4.0",
            "_note": "Original-language words in original order with glosses. "
                     "Not a full interlinear; enough to follow a word back.",
        }) + "\n")
        for f in sorted(glob.glob(str(MAC) + "/**/*.xml", recursive=True)):
            try:
                root = ET.parse(f).getroot()
            except ET.ParseError:
                continue
            lemma_meta(root, meta)
            byverse = {}
            order = []
            for w in root.iter("w"):
                ref = _ref(w.get("ref") or "")
                if not ref:
                    continue
                if ref not in byverse:
                    byverse[ref] = []
                    order.append(ref)
                byverse[ref].append({
                    "t": (w.get("unicode") or w.get("text") or "").strip(),
                    "g": _text(w),
                    "l": (w.get("lemma") or "").strip(),
                    "s": (w.get("strongnumberx") or w.get("strong") or ""),
                    "p": _pos(w),
                    # How to say it. Hebrew supplies its own; Greek is
                    # generated, since MACULA Greek carries no such attribute.
                    "x": ((w.get("transliteration") or "").strip()
                          or translit_greek(w.get("unicode")
                                            or w.get("text") or "")),
                })
            for ref in order:
                ws = [w for w in byverse[ref] if w["t"] or w["g"]]
                if not ws:
                    continue
                fh.write(json.dumps({"ref": ref, "words": ws},
                                    ensure_ascii=False) + "\n")
                verses += 1
                words += len(ws)

    # keep only the commonest few values per field, so the file stays small and
    # a card can say "usually qal" without shipping a frequency table
    slim = {}
    for k, m in meta.items():
        if m["n"] < 2:
            continue
        f = {}
        for a, counts in m["f"].items():
            top = sorted(counts.items(), key=lambda x: -x[1])[:4]
            f[a] = [{"v": v, "n": n} for v, n in top]
        slim[k] = {"n": m["n"], **f}
    mpath = OUT / "lemma-meta.json"
    mpath.write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")

    print("ORIGINAL-LANGUAGE STRIP")
    print(f"  verses  {verses:>8,}")
    print(f"  words   {words:>8,}")
    print(f"  wrote {path}  ({path.stat().st_size/1e6:.1f} MB)")
    print(f"  lemmas with metadata  {len(slim):>7,}")
    print(f"  wrote {mpath}  ({mpath.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
