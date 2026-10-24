"""A blind scoring sheet for lemma pairs, to calibrate the judges.

2026-09-02: look up the Hebrew and Greek definitions and have the reader do a
blind scoring of various combinations. The reader is not qualified to judge
Greek and Hebrew words, though able to read dictionary definitions.

So the sheet shows **definitions only**. No Strong's number, no language, no
transliteration, no gloss -- because every one of those leaks the answer. A
pair labelled H0530/G4102 tells a reader they are cross-language before they
have read a word, and a pair sharing a headword is answered by the headword.

## Why a human sheet at all, when the Septuagint attests some of these

Three sources, and each validates something the others cannot:

    LXX correspondences   attested equivalence, from the third century BC. The
                          strongest evidence and it covers 39% of Greek
                          entries. It says nothing about pairs it does not
                          mention, and nothing about Hebrew-to-Hebrew.

    the model judges      cheap, cover everything, and demonstrably wrong on
                          the cases that matter -- the local 3B called
                          "to persuade"/"to trust" OPPOSITE where the LXX
                          attests them as one pair, and did the same for the
                          Psalm 34:8 trust/refuge pair.

    this sheet            whether a careful reader of DEFINITIONS agrees with
                          either. That is the actual task the pipeline
                          performs, so it is the only check that measures the
                          thing being built rather than a proxy for it.

## What is in the set

Deliberately mixed, and the mix is the point -- a sheet of hard cases measures
nothing, because there is no baseline to read the hard cases against:

    attested   the LXX names them. We know the answer; the sheet does not.
    contested  the judges disagreed with each other or with the LXX.
    control    obviously unrelated, and obviously identical. If these come
               back wrong the instrument is broken, not the reader.
    the cluster faith / trust / belief / refuge, which is the case that was asked
               about and the one English shuffles worst.

Answers are written to a separate file that the sheet never reads, so the
scoring cannot be checked against them until it is submitted.
"""
import html
import json
import pathlib
import random
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
STEP = ROOT / "data" / "raw" / "stepbible"

# (a, b, why it is in the set, what we believe and how strongly)
PAIRS = [
    ("G4102", "H0530", "attested",  "LXX: pistis chiefly renders emunah"),
    ("G4100", "H0539", "attested",  "LXX: pisteuo chiefly renders aman (hiphil)"),
    ("G3982", "H0982", "attested",  "LXX: peitho chiefly renders batach"),
    ("G1656", "H2617", "attested",  "LXX: eleos chiefly renders chesed"),
    ("G5485", "H2580", "attested",  "LXX: charis chiefly renders chen"),
    ("G1515", "H7965", "attested",  "LXX: eirene chiefly renders shalom"),
    ("H0982", "H2620", "contested", "the Psalm 34:8 pair; 3B said OPPOSITE"),
    ("H0530", "H0539", "contested", "one root, noun and verb"),
    ("G4100", "G3982", "contested", "3B said OPPOSITE"),
    ("H0982", "H4009", "contested", "trust, and the confidence that results"),
    ("G4102", "H0982", "contested", "faith against trust -- not attested"),
    ("H2451", "H0998", "contested", "wisdom/understanding; English once merged them"),
    ("G5624", "G0512", "control",   "valuable/useless -- true opposites"),
    ("H8184", "H2406", "control",   "barley/wheat -- near, not same"),
    ("H8184", "H0890", "control",   "barley/foul weed -- unrelated"),
    ("G1656", "H0175", "control",   "mercy/Aaron -- unrelated"),
]


def lexicon() -> dict:
    out = {}
    for f in STEP.glob("TBES*.txt"):
        for line in f.open(encoding="utf-8", errors="replace"):
            c = line.split("\t")
            if len(c) > 7 and re.match(r"^[HG]\d{4}[A-Z]?$", c[0].strip()):
                full = re.sub(r"<[^>]+>", " ", c[7])
                # The LXX note names the Hebrew word outright, which would
                # hand over the answer on every attested pair.
                full = re.sub(r"\[in LXX[^\]]*\]", "", full)
                # Verse references narrow the language as effectively as a tag.
                full = re.sub(r"\b[1-3]?[A-Z][a-z]{2}\.\d+[:.]\d+\S*", "", full)
                full = re.sub(r"[^\x00-\x7f]+", "", full)      # drop the script
                full = re.sub(r"\s+", " ", full).strip(" ,;:")
                if full:
                    out[c[0].strip()] = full
    return out


def build() -> pathlib.Path:
    lex = lexicon()
    rows, key = [], []
    items = [p for p in PAIRS if p[0] in lex and p[1] in lex]
    random.seed(1729)
    random.shuffle(items)
    for n, (a, b, kind, note) in enumerate(items, 1):
        # Which definition is shown first is randomised too, so a reader
        # cannot learn "the Greek one is always on the left".
        x, y = (a, b) if random.random() < 0.5 else (b, a)
        rows.append(
            f"<li><div class='q'>Pair {n}</div>"
            f"<div class='d'><b>A.</b> {html.escape(lex[x][:400])}</div>"
            f"<div class='d'><b>B.</b> {html.escape(lex[y][:400])}</div>"
            f"<div class='r'>SAME &nbsp; NEAR &nbsp; OPPOSITE &nbsp; NO"
            f"<span class='in'>____</span></div></li>")
        key.append({"pair": n, "a": x, "b": y, "kind": kind, "expect": note})

    (ROOT / "out" / "blind-pairs-key.json").write_text(
        json.dumps(key, indent=1), encoding="utf-8")

    page = """<!doctype html><html><head><meta charset="utf-8">
<title>Blind pair scoring</title><style>
 body{font:15px/1.6 system-ui,sans-serif;margin:0 auto;padding:2rem;max-width:820px;
      background:#faf9f7;color:#191919}
 h1{font-size:1.4rem;margin:0 0 .3rem}
 .note{color:#5a5a5a;font-size:.92rem;margin:.3rem 0 1.4rem}
 ol{list-style:none;padding:0;margin:0}
 li{background:#fff;border:1px solid #e3e0da;border-radius:8px;padding:.9rem 1.1rem;
    margin:0 0 .9rem}
 .q{font-size:.72rem;color:#8a8375;text-transform:uppercase;letter-spacing:.05em;
    font-weight:600;margin-bottom:.5rem}
 .d{margin:.35rem 0;font-size:.94rem;line-height:1.5}
 .d b{color:#6d6144;margin-right:.3rem}
 .r{margin-top:.7rem;padding-top:.6rem;border-top:1px solid #f0ece2;
    font-size:.82rem;color:#8a8375;letter-spacing:.02em}
 .in{display:inline-block;margin-left:1.2rem;border-bottom:1px solid #b9b0a0;
     min-width:6rem;color:#191919}
 @media(prefers-color-scheme:dark){
  body{background:#15140f;color:#ededed} .note,.q,.r{color:#a8a8a8}
  li{background:#201e17;border-color:#3a362b} .d b{color:#cdbf95}
  .r{border-color:#2f2c22} .in{border-color:#4a4436;color:#ededed}}
</style></head><body>
<h1>Blind pair scoring</h1>
<p class="note">Definitions only &mdash; no Strong's numbers, no language, no
headwords, no verse references, and the order within each pair is randomised.
Mark each <b>SAME</b>, <b>NEAR</b>, <b>OPPOSITE</b> or <b>NO</b>.
<br><br><b>SAME</b> one is a translation of the other, or they name one concept
&nbsp;&middot;&nbsp; <b>NEAR</b> overlapping but a reader could tell them apart
&nbsp;&middot;&nbsp; <b>OPPOSITE</b> one negates or contrasts with the other
&nbsp;&middot;&nbsp; <b>NO</b> unrelated.
<br><br>The answers are in a separate file this page never reads.</p>
<ol>""" + "".join(rows) + """</ol></body></html>"""
    out = ROOT / "out" / "blind-pairs.html"
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build()
    print(f"wrote {p}")
    print(f"key   {ROOT / 'out' / 'blind-pairs-key.json'}  (do not open first)")
