"""The word-group tree: nested phrases, and the highest node without a verb.

2026-09-14, the specification of the two-column reader:

> The only addition is hyperlinks on the highest level node without a verb, so
> Jesus, Jerusalem, peace, Armor of God, Living Water, and Children of God
> would all get hyperlinks, but "be strong and courageous" gets hyperlinks for
> "strong" and "courageous" individually and "The Lord is compassionate and
> gracious" gets hyperlinks for "The Lord", "compassionate", and "gracious",
> individually.

> the words are grouped in boxes by the structure and those boxes are grouped
> by boxes by the structure and so on.

Both columns want the same thing and nothing derived carries it.
`interlinear.jsonl.gz` is a flat word list; `cola.jsonl.gz` is Hebrew-only and
two levels deep. The tree is in MACULA's lowfat XML and had never been
extracted.

## The linking rule falls out of the tree

MACULA marks every word group with a `class` -- `cl` for clause, `np`, `pp`,
`adjp` -- so **the maximal `wg` containing no verb** is exactly the rule
specified, and its two examples are the two sides of it:

    Armor of God        one np, no verb inside    -> ONE link
    The Lord is         a cl, the verb is inside  -> descend, and link
    compassionate...       "The Lord", "compassionate", "gracious" apart

Nothing about that is a heuristic. A clause has a verb by definition, so a
clause is never a link; its verbless children are.

## What is deliberately not read

`w` elements carry `domain` and `ln` -- UBS semantic-domain data, which is
permission-based and which this project never reads. This extractor touches
`class`, `role`, `rule`, `ref`, `gloss`, `lemma` and `strong` and nothing else.
See `SOURCES.md`.

    python tools/phrases.py --book Rom --verse Rom.1.1
    python tools/phrases.py --check          # the specified examples
    python tools/phrases.py --write          # every book
"""
from __future__ import annotations

import argparse
import collections
import glob
import gzip
import json
import pathlib
import re
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
MAC = ROOT / "data/raw/macula"
TAG = re.compile(r"\{.*\}")
# MACULA book codes in the file refs -- "ROM 1:1!1" -- against ours.
REF = re.compile(r"^(\S+)\s+(\d+):(\d+)!(\d+)")


def tag(n):
    return TAG.sub("", n.tag)


def words(n):
    """-> [w elements] in document order beneath n."""
    return [x for x in n.iter() if tag(x) == "w"]


def has_verb(n):
    """A clause has a verb; a phrase does not. This is the whole rule."""
    return any((x.get("class") or "") == "verb" for x in words(n))


def build(n, depth=0, opening=None):
    """-> nested {class, role, rule, words:[n], children:[...]} or None.

    `opening` is the sentence's first verse as "C:V". A word in a later verse
    of the same sentence says so in `at` ("8:39"). MACULA keeps a sentence
    under its first verse, and the word's own verse was read and thrown away
    here, so prep_phrases.py had to guess it back by spelling, and filed up to
    a fifth of its phrases under the wrong verse (2026-10-18)."""
    t = tag(n)
    if t == "w":
        m = REF.match(n.get("ref") or "")
        at = f"{m.group(2)}:{m.group(3)}" if m else None
        return {"w": int(m.group(4)) if m else None,
                **({"at": at} if at and opening and at != opening else {}),
                "cls": n.get("class"), "role": n.get("role"),
                # The SURFACE FORM as well as the gloss. The first version
                # stored only the gloss, so the reader's right column -- which
                # exists to show the original -- printed English twice.
                "t": (n.text or n.get("unicode") or "").strip(),
                # gloss/lemma/strong only. NEVER `domain` or `ln`.
                "g": n.get("gloss"), "l": n.get("lemma"),
                # THE TWO CORPORA SPELL THIS ATTRIBUTE DIFFERENTLY. MACULA
                # Greek writes `strong`; MACULA Hebrew writes `strongnumberx`.
                # Reading only `strong` left every Hebrew leaf with s=None --
                # 930 of the 959 files -- so in the reader's right column each
                # Hebrew word got an empty key and nothing was clickable, while
                # Greek worked. 2026-09-15: the Greek hyperlinks worked but the
                # Hebrew ones did not.
                #
                # The flat `orig` strip never showed the bug because it is
                # built from a different loader that already read the Hebrew
                # attribute, which is why the two paths disagreed in the same
                # verse.
                "s": n.get("strong") or n.get("strongnumberx")}
    if t != "wg":
        return None
    kids = [build(c, depth + 1, opening) for c in n]
    kids = [k for k in kids if k]
    if not kids:
        return None
    return {"cls": n.get("class"), "role": n.get("role"),
            "rule": n.get("rule"), "verb": has_verb(n), "kids": kids}


# Words that are structure rather than content. A link on "and" or "the" is a
# link on nothing, and the specified examples are all content: Jesus, Jerusalem,
# peace, Armor of God, Living Water, Children of God.
# `cj` is Hebrew's conjunction class and `conj` is Greek's -- both, or the
# word "and" surfaces as a link of its own between the two it joins.
FUNCTION = {"cj", "conj", "det", "prep", "ptcl", "particle", "advb", "x",
            "om", "dm"}


def linkable(node, out):
    """Mark the maximal NON-PREDICATING nodes -- what the left column links.

    The first rule tried was "the highest node with no verb", which is the
    original wording and which fails on Hebrew. A nominal clause has no verb word at
    all -- *the LORD [is] compassionate and gracious* -- so by that test the
    whole clause is verbless and became ONE link, where the specification asked for three.

    A CLAUSE is never a link, whether its verb is written or implied. That is
    what was meant and what the tree already records: `class="cl"`. Descend
    through clauses, link the maximal phrase inside them, and a bare content
    word is its own link when it sits directly under one -- which is how
    "compassionate" and "gracious" come out apart.
    """
    if "kids" not in node:                       # a word
        cls = (node.get("cls") or "")
        if cls != "verb" and cls not in FUNCTION and (node.get("g") or "").strip(" -"):
            out.append(node)
        return
    # Only a node with a real phrase class is a link. An UNCLASSED wg is a
    # wrapper -- MACULA puts one around each sentence -- and treating it as a
    # phrase made it swallow the clause beneath it, which is what kept Psalm
    # 103:8 as a single link after the clause rule was already right.
    cls = node.get("cls")
    # A COORDINATION is descended into as well. The specification asks for "strong" and
    # "courageous" individually, and for "compassionate" and "gracious"
    # individually -- so a phrase joined by `and` is two links, not one. The
    # conjunction itself is a child, which is how the tree says so.
    coord = any("kids" not in k and (k.get("cls") or "") in ("cj", "conj")
                for k in node["kids"])
    if cls and cls != "cl" and not node.get("verb") and not coord:
        out.append(node)
        return
    for k in node["kids"]:
        linkable(k, out)


def _span(node):
    """-> [first, last] word positions, so the app can align to interlinear."""
    ws = []
    def go(n):
        if "kids" in n:
            for k in n["kids"]:
                go(k)
        elif n.get("w"):
            ws.append(n["w"])
    go(node)
    return [min(ws), max(ws)] if ws else None


def text_of(node):
    if "kids" not in node:
        return (node.get("g") or "").strip()
    return " ".join(x for x in (text_of(k) for k in node["kids"]) if x)


def verses(path, want=None):
    """-> {ref: [tree, ...]} one tree per sentence, keyed by the OPENING verse."""
    root = ET.parse(path).getroot()
    out = collections.defaultdict(list)
    for s in root.iter():
        if tag(s) != "sentence":
            continue
        for wg in s:
            if tag(wg) != "wg":
                continue
            ws = words(wg)
            if not ws:
                continue
            m = REF.match(ws[0].get("ref") or "")
            if not m:
                continue
            ref = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
            if want and ref != want:
                continue
            tr = build(wg, opening=f"{m.group(2)}:{m.group(3)}")
            if tr:
                out[ref].append(tr)
    return out


CHECKS = [("Eph", "EPH.6.11", "armor"), ("Ps", "PSA.103.8", "compassionate"),
          ("Josh", "JOS.1.9", "strong"), ("John", "JHN.4.10", "living water"),
          ("1John", "1JN.3.1", "children of God")]


def find_file(book):
    # Greek is one file per book (`06-romans.xml`); Hebrew is one per CHAPTER
    # (`19-Psa-103-lowfat.xml`), which is why a single glob cannot serve both.
    pats = {"Eph": "greek/*ephesians*", "Ps": "hebrew/*-Psa-*",
            "Josh": "hebrew/*-Jos-*", "John": "greek/04-john*",
            "1John": "greek/*1john*", "Rom": "greek/*romans*",
            "Gen": "hebrew/*-Gen-*"}
    hits = sorted(glob.glob(str(MAC / pats.get(book, f"*/*{book}*"))))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--book")
    ap.add_argument("--verse")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    if a.check:
        for book, ref, note in CHECKS:
            files = find_file(book)
            if not files:
                print(f"  {ref:<12} (no MACULA file for {book})")
                continue
            got = None
            for f in files:
                v = verses(f, ref)
                if v:
                    got = v
                    break
            if not got:
                print(f"  {ref:<12} not found in {len(files)} file(s)")
                continue
            links = []
            for tr in got[ref]:
                linkable(tr, links)
            print(f"  {ref:<12} {note}")
            print("      " + " | ".join(text_of(x) or "?" for x in links))
        return 0

    if a.book:
        files = find_file(a.book)
        if not files:
            raise SystemExit(f"no MACULA file for {a.book}")
        v = verses(files[0], a.verse)
        for ref, trees in list(v.items())[:3]:
            links = []
            for tr in trees:
                linkable(tr, links)
            print(f"{ref}: {len(trees)} tree(s), {len(links)} links")
            print("   " + " | ".join(text_of(x) for x in links))
        return 0

    if a.write:
        files = (sorted(glob.glob(str(MAC / "greek/*.xml")))
                 + sorted(glob.glob(str(MAC / "hebrew/*lowfat.xml"))))
        out = OUT / "phrases.jsonl.gz"
        n = nv = nl = 0
        with gzip.open(out, "wt", encoding="utf-8") as f:
            f.write(json.dumps({
                "_source": "MACULA Hebrew Linguistic Datasets, available at "
                           "https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek "
                           "Linguistic Datasets, available at "
                           "https://github.com/Clear-Bible/macula-greek/; © Biblica, "
                           "Inc., CC BY 4.0",
                "_note": "The word-group tree per verse: nested phrases with "
                         "class/role/rule, and `link` marking the maximal "
                         "non-predicating nodes. Never reads MACULA's `domain` "
                         "or `ln` attributes, which are UBS data this project "
                         "does not use -- see NOTICE.md."}) + "\n")
            for i, path in enumerate(files):
                try:
                    v = verses(path)
                except ET.ParseError:
                    continue
                n += 1
                for ref, trees in v.items():
                    links = []
                    for tr in trees:
                        linkable(tr, links)
                    f.write(json.dumps({"ref": ref, "trees": trees,
                                        "links": [{"w": _span(x),
                                                   "t": text_of(x)}
                                                  for x in links]},
                                       ensure_ascii=False) + "\n")
                    nv += 1
                    nl += len(links)
                if i % 60 == 0:
                    print(f"  {i}/{len(files)} files, {nv:,} verses", flush=True)
        print(f"\n  {n} files, {nv:,} verses, {nl:,} links")
        print(f"  -> {out.relative_to(ROOT)}")
        return 0

    raise SystemExit("pass --check, --book, or --write")


if __name__ == "__main__":
    raise SystemExit(main())
