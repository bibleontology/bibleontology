"""The same word in the other languages the Bible is written in.

2026-09-19, having asked for the Greek on the word card and then: Aramaic can
go in there if applicable as well, not treated as an afterthought, but only if
there is an equivalent usage in the Bible.

Two equivalents, found two different ways, and only one of them is an
alignment. The distinction is the whole point of the file.

## Greek: an alignment, carried in the data

MACULA records on each Hebrew word the Greek the **Septuagint** used for it.
That is a translator's decision preserved in the dataset, not an inference, so
`nᵊʾum` gives λέγει 246 times as a fact about a text that exists.

## Aramaic: a cognate, and said to be one

Nothing aligns Hebrew to Aramaic — they are different passages, not
translations of each other. What *is* checkable is that the Bible's Aramaic
sections use a word with **the same consonantal skeleton**:

    Hebrew  אָמַר  H559   said        Aramaic  אֲמַר  H560   said
    Hebrew  מֶלֶךְ H4428  king        Aramaic  מֶלֶךְ H4430  king

Hebrew and Aramaic are written with the same alphabet and the vowels are
pointing added later, so identical consonants is a fact about the spelling, not
an etymological claim. **The card must say which of the two it is showing**, and
"the Aramaic sections use" is the strongest honest phrasing.

## Only where the Bible actually uses it

The constraint: the Aramaic side is drawn ONLY from the passages that are in
Aramaic -- Daniel 2:4b-7:28, Ezra 4:8-6:18, Jeremiah 10:11 and the two words at
Genesis 31:47 -- so every equivalent offered is a word a reader can go and
find. Nothing comes from a lexicon of Aramaic at large.

    python tools/equivalents.py
    python tools/equivalents.py --write
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys
import unicodedata

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
DEST = OUT / "word-equivalents.json"

NT = {"Mat", "Mrk", "Luk", "Jhn", "Act", "Rom", "1Co", "2Co", "Gal", "Eph",
      "Php", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm", "Heb", "Jas",
      "1Pe", "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Rev"}

# The Aramaic of the Hebrew Bible, by passage. There is no language flag in the
# data, and these spans are not a judgement -- they are where the text changes
# language, which every edition marks.
ARAMAIC = [("Dan", (2, 4), (7, 28)),
           ("Ezr", (4, 8), (6, 18)),
           ("Ezr", (7, 12), (7, 26)),
           ("Jer", (10, 11), (10, 11)),
           ("Gen", (31, 47), (31, 47))]


def in_aramaic(ref: str) -> bool:
    b, c, v = ref.split(".")
    c, v = int(c), int(v)
    for bk, lo, hi in ARAMAIC:
        if b == bk and lo <= (c, v) <= hi:
            return True
    return False


def skeleton(lemma: str) -> str:
    """The consonants, with the pointing stripped.

    Hebrew and Aramaic share an alphabet and the vowel points were added
    centuries after the consonants, so comparing skeletons compares what is
    actually written. Final forms are folded to their ordinary shape because
    they are positional spellings of one letter.
    """
    d = unicodedata.normalize("NFD", lemma or "")
    d = "".join(c for c in d if not unicodedata.combining(c))
    d = d.translate(str.maketrans("ךםןףץ", "כמנפצ"))
    return re.sub(r"[^א-ת]", "", d)


def load():
    """-> (hebrew, aramaic) as {lemma: {strong, translit, gloss, n}}."""
    heb, ara = {}, {}
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        ref = d.get("ref")
        if not ref:
            continue
        side = ara if in_aramaic(ref) else heb
        for w in d.get("words") or []:
            lem, s = w.get("l"), w.get("s")
            if not lem or not s:
                continue
            # HEBREW SCRIPT ONLY. Without this the New Testament's Greek
            # lemmas came through too, and since `skeleton` strips everything
            # that is not a Hebrew letter they all reduced to the same empty
            # string and matched each other: ἀφανίζω was offered as a cognate
            # of אָת, and Ἀπελλῆς of אֲמַר.
            if not any("א" <= ch <= "ת" for ch in lem):
                continue
            e = side.setdefault(lem, {"lemma": lem, "strong": s, "n": 0,
                                      "x": collections.Counter(),
                                      "g": collections.Counter()})
            e["n"] += 1
            if w.get("x"):
                e["x"][w["x"]] += 1
            if w.get("g"):
                e["g"][w["g"].strip().lower()] += 1
    return heb, ara


def top(counter):
    return counter.most_common(1)[0][0] if counter else None


def fold_latin(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    return re.sub(r"[^a-z]", "",
                  "".join(c for c in s if not unicodedata.combining(c)))


def loanwords():
    """Words the Greek New Testament spells out instead of translating.

    2026-09-19, having looked for ἀββά and found nothing: could language
    switches within the verse be supported in the reader, and what would it take
    for Abba to show up on the main father page as well?

    Both answerable from the text. **When the gloss IS the transliteration, the
    translators did not translate the word -- they spelled it**, which is a
    language switch recorded in the data rather than inferred from it.

    Proper names do that too, and are excluded by their capital: Greek writes
    Σίμων and Ἰσραήλ with one and ἀββά, ἀμήν, μάννα without. That leaves 19
    common words, of which the Semitic ones are the switches meant --
    ἀββά, ἐλωΐ, ἐφφαθά, ταλιθά, κοῦμ, λεμά, ἀμήν, μάννα -- and the rest are
    coins, measures and letter names.

    **And the New Testament glosses its own loanwords**, which is how ἀββά can
    reach a page about fathers without anyone consulting a lexicon:

        Mrk 14:36   ἀββά  ὁ πατήρ
        Rom 8:15    ἀββά  ὁ πατήρ
        Gal 4:6     ἀββά  ὁ πατήρ        three of three

        Mrk 5:41    ταλιθά κοῦμ  ὅ ἐστιν μεθερμηνευόμενον ...
        Mrk 7:34    ἐφφαθά       ὅ ἐστιν διανοίχθητι

    So `means` below is the text's own apposition -- the content words that
    follow the loanword in every one of its occurrences -- and not a reading
    supplied from outside. Where the occurrences disagree, nothing is claimed.
    """
    # μεθερμηνεύω and ἑρμηνεύω are the text saying "which translated is".
    SAYS = {"μεθερμηνεύω", "ἑρμηνεύω", "διερμηνεύω"}
    SKIP = {"ὁ", "εἰμί", "ὅς", "καί", "οὗτος", "ἐν", "αὐτός", "δέ"}
    seen = collections.defaultdict(lambda: {"n": 0, "refs": [], "after": []})
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        ref = d.get("ref") or ""
        if ref.split(".")[0] not in NT:
            continue
        ws = d.get("words") or []
        for i, w in enumerate(ws):
            lem = w.get("l") or ""
            if not lem or lem[0].isupper():
                continue
            g, x = fold_latin(w.get("g")), fold_latin(w.get("x"))
            if not g or not x or len(g) < 3 or g != x:
                continue
            e = seen[lem]
            e["n"] += 1
            e["gloss"], e["translit"] = w.get("g"), w.get("x")
            e["strong"] = w.get("s")
            if len(e["refs"]) < 6:
                e["refs"].append(ref)
            # what the text puts immediately after it, skipping the copula
            tail = []
            for nxt in ws[i + 1:i + 6]:
                nl = nxt.get("l") or ""
                if nl in SKIP or nl in SAYS:
                    continue
                if fold_latin(nxt.get("g")) == fold_latin(nxt.get("x")):
                    continue          # another loanword, not its gloss
                tail.append((nl, (nxt.get("g") or "").strip()))
                if len(tail) >= 2:
                    break
            e["after"].append(tuple(tail[:1]))
    out = {}
    for lem, e in seen.items():
        first = [a[0] for a in e["after"] if a]
        # Only where EVERY occurrence is followed by the same word: the text
        # glossing itself consistently, rather than a coincidence of order.
        means = None
        if first and len(set(first)) == 1 and len(first) == e["n"]:
            means = {"lemma": first[0][0], "gloss": first[0][1]}
        key = "g" + re.sub(r"^0+", "", re.sub(r"[^0-9]", "",
                                              e.get("strong") or ""))
        out[key] = {"lemma": lem, "gloss": e.get("gloss"),
                    "x": e.get("translit"), "n": e["n"], "refs": e["refs"],
                    "means": means}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    heb, ara = load()
    print(f"{len(heb):,} Hebrew lemmas, {len(ara):,} lemmas in the Aramaic "
          f"passages")

    # Aramaic is indexed by skeleton; a Hebrew word finds its counterpart there.
    by_skel = collections.defaultdict(list)
    for lem, e in ara.items():
        sk = skeleton(lem)
        if len(sk) >= 2:
            by_skel[sk].append(e)

    out, matched = {}, 0
    for lem, e in heb.items():
        sk = skeleton(lem)
        cands = [c for c in by_skel.get(sk, []) if c["strong"] != e["strong"]]
        if not cands:
            continue
        cands.sort(key=lambda c: -c["n"])
        c = cands[0]
        matched += 1
        key = ("h" + re.sub(r"^0+", "", re.sub(r"[^0-9]", "", e["strong"])))
        out[key] = {"lemma": c["lemma"], "strong": c["strong"],
                    "x": top(c["x"]), "g": top(c["g"]), "n": c["n"]}
    print(f"{matched:,} Hebrew lemmas have a same-consonant word in the "
          f"Aramaic passages\n")

    print("samples:")
    for k in list(out)[:8]:
        v = out[k]
        h = next((x for x in heb.values()
                  if ("h" + re.sub(r"^0+", "", re.sub(r"[^0-9]", "",
                                                      x["strong"]))) == k),
                 None)
        if h:
            print(f"   {h['lemma']:<10} {top(h['g']) or '':<12} ->  "
                  f"{v['lemma']:<10} {v['g'] or '':<12} ({v['n']}x)")

    if not a.write:
        print("\nnothing written -- pass --write")
        return 0
    # GREEK FORMS, so the LXX column can be shown as word nodes rather than
    # bare strings. the word page wants the Greek chips with the
    # original and phonetic and English label, clickable for each word
    # offered. The column gives surface forms -- λέγει, not λέγω -- so they
    # are indexed by surface, from the Greek New Testament where the same forms
    # occur with a transliteration and a gloss already attached.
    gforms = {}
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        ref = d.get("ref")
        if not ref or ref.split(".")[0] not in NT:
            continue
        for w in d.get("words") or []:
            t = (w.get("t") or "").strip(",.;·:")
            if not t or t in gforms:
                continue
            s = w.get("s")
            gforms[t] = {
                "x": w.get("x"), "g": (w.get("g") or "").strip().lower(),
                "key": ("g" + re.sub(r"^0+", "", re.sub(r"[^0-9]", "", s)))
                if s else None}
    print(f"{len(gforms):,} Greek surface forms indexed for the chips")

    # THE BRIDGE RUNS BOTH WAYS. 2026-09-19: the Greek card should
    # reference the Hebrew just as the Hebrew references the Greek.
    #
    # The Septuagint column is stored per Hebrew lexeme, so the Hebrew card
    # could answer "what Greek stands here" and the Greek card could answer
    # nothing at all -- the same alignment, readable from one end only. This
    # inverts it: for a Greek lexeme, which Hebrew words the Septuagint
    # rendered with it, and how often.
    #
    # The column holds surface forms, so each is resolved to its Greek lexeme
    # through the index above; forms that do not resolve are dropped rather
    # than guessed at.
    lmeta = json.loads((OUT / "lemma-meta.json").read_text(encoding="utf-8"))
    fold = {}
    for k, v in gforms.items():
        n = unicodedata.normalize("NFD", k)
        n = "".join(c for c in n if not unicodedata.combining(c)).lower()
        fold.setdefault(n, v)
    back = collections.defaultdict(collections.Counter)
    for hkey, meta in lmeta.items():
        if not hkey.startswith("h"):
            continue
        for x in (meta.get("greek") or []):
            form = (x.get("v") or "").strip(",.;·:")
            if not form or not form.strip("’'\""):
                continue
            nf = unicodedata.normalize("NFD", form)
            nf = "".join(c for c in nf if not unicodedata.combining(c)).lower()
            # MACULA's column writes chi as xi in 1,284 of 16,226 renderings
            # (tools/lxxbridge.py found it 2026-09-16; this file never got the
            # fix, so the Greek cards for grace, soul, hand, enemy, beginning
            # and Christ named no Hebrew at all -- found 2026-09-29). The chi
            # reading is tried only when the form as written is no Greek word:
            # preferring it always turned real xi into chi words -- ἔξω
            # "outside" became ἔχω "have", ξηρά "dry land" became χήρα
            # "widow", ἥκω and ξηρός lost every Hebrew. The cost: where both
            # readings are words it stays as written, so ראשית's "αρξη" is
            # still read as ἄρξῃ "you will begin", not ἀρχή "beginning".
            chi = fold.get(nf.replace("ξ", "χ")) if "ξ" in nf else None
            gk = (gforms.get(form) or fold.get(nf) or chi or {}).get("key")
            if gk:
                back[gk][hkey] += x.get("n") or 0
    hebrew_for = {}
    for gk, c in back.items():
        rows = []
        for hkey, n in c.most_common(4):
            e = next((v for v in heb.values()
                      if ("h" + re.sub(r"^0+", "",
                                       re.sub(r"[^0-9]", "", v["strong"])))
                      == hkey), None)
            if e:
                rows.append({"key": hkey, "t": e["lemma"], "x": top(e["x"]),
                             "g": top(e["g"]), "n": n})
        if rows:
            hebrew_for[gk] = rows
    print(f"{len(hebrew_for):,} Greek lexemes can name the Hebrew behind them")

    # WHICH LEXEMES ARE ARAMAIC. 2026-09-19, on searching "father":
    # the first and third entries looked the same -- they were not. The first
    # is Hebrew אָב H1 and the third is Aramaic אַב H2, and both were labelled
    # Hebrew, so the page looked like it was repeating itself.
    #
    # A lexeme counts as Aramaic when the Bible uses it ONLY in the Aramaic
    # passages. Anything appearing on both sides is a word the two languages
    # share, and calling it Aramaic would be the same error in reverse.
    #
    # AND THE KEY MUST BE CLEAN OF HEBREW. MACULA distinguishes lexemes with a
    # trailing letter -- 0001 is אָב "father", 0001b is the Aramaic article --
    # and the app's keys are bare numbers, so both become `h1`. Marking `h1`
    # Aramaic because one of its lexemes is would relabel אָב, a Hebrew word
    # with 2,131 uses. Same collision that made 5207 render as "son": a key
    # that is not unique cannot carry a property of one of its members.
    def keyof(strong):
        return "h" + re.sub(r"^0+", "", re.sub(r"[^0-9]", "", strong))

    heb_keys = {keyof(e["strong"]) for lem, e in heb.items()}
    aram_keys = {}
    for lem, e in ara.items():
        if lem in heb:
            continue
        k = keyof(e["strong"])
        if k in heb_keys:
            continue
        aram_keys[k] = e["n"]
    print(f"{len(aram_keys):,} lexemes occur ONLY in the Aramaic passages")

    loans = loanwords()
    print(f"{len(loans)} words the Greek New Testament SPELLS rather than "
          f"translates")

    DEST.write_text(json.dumps({
        "_note": "Per Hebrew lexeme, the word with the SAME CONSONANTS used in "
                 "the Bible's Aramaic passages (Daniel 2:4b-7:28, Ezra "
                 "4:8-6:18 and 7:12-26, Jeremiah 10:11, Genesis 31:47). This "
                 "is a COGNATE observed in the text, not a translation "
                 "alignment: Hebrew and Aramaic passages are not versions of "
                 "one another. The Greek equivalent, by contrast, IS an "
                 "alignment and comes from MACULA's own Septuagint column. A "
                 "card showing either must say which it is. See "
                 "tools/equivalents.py.",
        "aramaic": out, "greek_forms": gforms,
        "hebrew_for": hebrew_for, "loanwords": loans,
        "aramaic_lexemes": aram_keys},
        ensure_ascii=False),
        encoding="utf-8")
    print(f"\n  -> {DEST.relative_to(ROOT)}  {len(out):,} lexemes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
