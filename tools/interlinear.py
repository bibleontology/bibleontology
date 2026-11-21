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
    words   [{t: surface form, g: gloss, l: lemma, s: Strong's, p: pos,
              x: how to say it, w: the word's place in the verse}, …]

Word order is the ORIGINAL order, which is the point -- Hebrew puts the verb
first and English does not, and seeing that is most of what a reader gets from
looking at the original at all. `w` is that place: 1, 2, 3 … through the verse,
and the parts of one Hebrew word (the prefix בְּ and its noun רֵאשִׁית) share a
number, so a reader can join them back into the word they are.

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


_PARSE_VERB = ("stem", "type", "tense", "voice", "mood", "person", "case", "gender", "number", "state")
_PARSE_NOUN = ("case", "gender", "number", "state")


def parse_of(w):
    """One use's parsing in words, from MACULA's own attributes: "aorist active indicative third singular", "qal
    wayyiqtol third masculine singular", "genitive feminine singular", "masculine plural construct". A verb's
    `type` is its conjugation (Hebrew qatal, wayyiqtol); a noun's `type` (common, proper) is not a parse."""
    verb = (w.get("class") or w.get("pos") or "") in ("verb", "participle") or bool(w.get("tense") or w.get("stem"))
    vals = [w.get(a) for a in (_PARSE_VERB if verb else _PARSE_NOUN)]
    return " ".join(v.strip() for v in vals if v and v.strip() and not v.strip().isdigit())


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


def dedupe_names(ws):
    """Print a multi-word name once (S-28, 2026-11-14).

    MACULA gives a proper name that spans several words (Maher-shalal-hash-baz,
    Lo-ammi, Immanuel, Melchizedek) as one `w` element PER WORD, each carrying the
    whole name's surface text, so the strip printed Isa 8:3's name four times and
    Isa 7:14's Immanuel twice. A name is tagged with no Strong's number (`s`
    empty), and the copies are adjacent with the same surface text. Keep
    the first. A real repeated word (Isa 6:3 holy, holy, holy) carries a Strong's
    number and different accents, so it is never touched."""
    out = []
    for w in ws:
        prev = out[-1] if out else None
        if prev and w["t"] and not w["s"] and not prev["s"] and w["t"] == prev["t"]:
            # the copies' glosses may be the name's parts (Beer, Lahai, Roi): the
            # name's gloss is the capitalised ones joined, else the first
            gl = prev.setdefault("_gl", [prev["g"]])
            gl.append(w["g"])
            continue
        out.append(w)
    for w in out:
        gl = w.pop("_gl", None)
        if gl:
            names = list(dict.fromkeys(g for g in gl if g[:1].isupper()))
            w["g"] = "-".join(names) if names else gl[0]
    return out


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
                # THE VERSE'S ORDER, NOT THE TREE'S (FAULTS #51, 2026-10-30).
                # root.iter walks MACULA's syntax tree, and the tree lifts a
                # postpositive (γάρ, δέ, οὖν) to the head of its clause, so John
                # 3:16 printed "γὰρ Οὕτως" where the text reads "Οὕτως γὰρ".
                # Measured against each word's xml:id, 4,408 of 7,943 Greek
                # verses and 781 of 23,213 Hebrew verses came out of order. Each
                # word's `ref` ("JHN 3:16!2") carries its place in the verse; the
                # parts of one Hebrew word share it, and the xml:id orders the
                # parts. So keep the place as `w` and sort on it below.
                place = (w.get("ref") or "").rpartition("!")[2]
                byverse[ref].append({
                    "_id": w.get("{http://www.w3.org/XML/1998/namespace}id") or "",
                    "w": int(place) if place.isdigit() else 0,
                    "t":(w.get("unicode") or w.get("text") or "").strip(),
                    "g": _text(w),
                    "l": (w.get("lemma") or "").strip(),
                    "s": (w.get("strongnumberx") or w.get("strong") or ""),
                    "p": _pos(w),
                    # How to say it. Hebrew supplies its own; Greek is
                    # generated, since MACULA Greek carries no such attribute.
                    # the sof pasuq (the Hebrew full stop MACULA writes as ":" after a verse's
                    # last word) is punctuation, not a sound: hāʾāreṣ, not hāʾāreṣ: (FAULTS #19)
                    "x": ((w.get("transliteration") or "").strip().rstrip(":")
                          or translit_greek(w.get("unicode")
                                            or w.get("text") or "")),
                    # each use's parsing, spelled out as MACULA gives it (2026-11-09, a reviewer: "make sure
                    # visitors can inspect the actual forms and their grammatical parsing, not just aggregate
                    # counts"): the card counts forms by it
                    "m": parse_of(w),
                })
            for ref in order:
                ws = [w for w in byverse[ref] if w["t"] or w["g"]]
                if not ws:
                    continue
                ws.sort(key=lambda w: (w["w"], w["_id"]))
                ws = dedupe_names(ws)
                for w in ws:
                    del w["_id"]
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
