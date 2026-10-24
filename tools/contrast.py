"""Contrast pairs from antithetical parallelism — the opposite of a coordination.

The pattern design wants slots that carry "coordinates and radius while also
supporting opposites in contrast patterns". `tools/senses.py` supplies the
first two and had nothing for the third: overlap between profiles measures
similarity, and nothing in it measures opposition.

The corpus states opposition constantly, and Proverbs states it structurally:

    Pro 10:1   <cl S-V-O>  s: son+WISE     v: makes glad  o: father
               w 'but'
               <cl S-P>    s: son+FOOLISH  p: grief of his mother

Two clauses joined adversatively, with their constituents in the same roles. The
subjects share a head — *son* — so the contrast lives in the modifiers, and
`wise / foolish` falls out. Where the heads differ instead, the heads are the
pair.

    clause-joining conjunctions   27,747
    adversative among them         1,565      Pro 235, Jer 107, 1Sa 95, Isa 93

Proverbs leads, which is the expected shape and a useful sanity check on the
extraction.

## One honesty note about the signal

The comparison particle in `tools/graphnodes.py` is genuine morphology — Hebrew
*ke-* compares and *le-* does not. **This is not that.** The Hebrew conjunction
here is plain *waw*, "and":

    lemma  וְ      gloss  'and'      english  'but'

The adversative reading lives in MACULA's `english` column, which is a
contextual translation judgement by Clear Bible rather than a fact of the
morphology. That makes it **inherited interpretation**: deterministic,
reproducible and attributable, but an editorial reading and not a
morphological one. Recorded here so nobody later mistakes it for the same
grade of evidence as the simile marker. Greek is better off — *alla* and *de*
are lexically adversative.

    python tools/contrast.py            # extract, report, write
    python tools/contrast.py --word wise
"""
from __future__ import annotations

import collections
import glob
import gzip
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from macula import MAC, _ref                                     # noqa: E402
from graphnodes import _pos, _text, head_word, CONTENT           # noqa: E402

OUT = ROOT / "out"
ADVERSATIVE = {"but", "yet", "however", "nevertheless", "instead", "rather"}
# Roles that answer the same question on either side of the contrast. `o` and
# `p` are deliberately treated as one slot: Pro 10:1 has an OBJECT on the left
# ("makes his father glad") and a PREDICATE on the right ("is grief to his
# mother"), which is the same position in the parallelism wearing two labels.
SLOT = {"s": "subject", "v": "verb", "o": "complement", "p": "complement",
        "pp": "adjunct", "adv": "adjunct", "io": "complement"}


def _negated(cl):
    """Does a negation scope over this clause?

    "They sought BUT did not find" is not seek-against-find. It is one frame
    with a negation on one side, and reading it as an opposition manufactured
    pairs like find/searched, find/sought and answer/called out of nothing.
    The distinction is kept rather than filtered: a negated pair is a
    FRUSTRATED EXPECTATION, which is its own useful pattern and not a contrast.
    """
    return any((w.get("type") or "").lower() == "negative" for w in cl.iter("w"))


def _fillers(cl):
    """slot -> constituent, for one clause."""
    out = {}
    for c in list(cl):
        slot = SLOT.get(c.get("role") or "")
        if slot and slot not in out:
            out[slot] = c
    return out


def _mods(e):
    """Content words under a constituent that are not its head."""
    h = head_word(e)
    ws = [e] if e.tag == "w" else list(e.iter("w"))
    return [w for w in ws if w is not h and _pos(w) in CONTENT and _text(w)]


def _lemma(w):
    return (w.get("lemma") or "").strip() or _text(w).lower()


def _contentful(w):
    """Can this word BE one side of a semantic contrast?

    Two things dominated the first run and neither is an opposition:

        not / to,  all / not,  lord / not      the negation particle
        i / you,   he / you,  father / i       pronouns

    A negation is an operator over the clause, not a term in it -- the graph
    already carries it as `negated` on the edge. And a pronoun contrast is a
    contrast of REFERENCE, not of meaning: "I will not, but you will" opposes
    two people, and says nothing about any two words.

    Both are readable off the attributes rather than off a word list:
    `type="negative"` and `type="pronominal"`, with `class="pron"` as the
    Greek-side spelling of the second.
    """
    if w is None:
        return False
    t = (w.get("type") or "").lower()
    if t in ("negative", "pronominal", "interrogative", "demonstrative"):
        return False
    if (w.get("class") or "").lower() == "pron":
        return False
    return (w.get("pos") or "").lower() != "particle" and bool(_text(w))


def _pair(a, b):
    """The contrasted words in two constituents filling the same slot.

    Two rules, and the order matters:

    **Shared head, differing modifier.** "a WISE son" against "a FOOLISH son"
    contrasts the adjectives, not the noun. Emitting `son / son` would be noise
    and would drown the real pair.

    **Differing heads.** "ill-gotten treasures" against "righteousness" (Pro
    10:2) has nothing in common, so the heads are the contrast.
    """
    ha, hb = head_word(a), head_word(b)
    if not _contentful(ha) or not _contentful(hb):
        return None
    if _lemma(ha) == _lemma(hb):
        ma = [w for w in _mods(a) if _contentful(w)]
        mb = [w for w in _mods(b) if _contentful(w)]
        if ma and mb and _lemma(ma[0]) != _lemma(mb[0]):
            return ma[0], mb[0]
        return None
    return ha, hb


def extract():
    found = collections.Counter()
    refs = collections.defaultdict(list)
    stats = collections.Counter()

    for f in sorted(glob.glob(str(MAC) + "/**/*.xml", recursive=True)):
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        for s in root.iter("sentence"):
            ws = [w for w in s.iter("w")]
            ref = _ref(ws[0].get("ref") or "") if ws else None
            if not ref:
                continue
            for parent in s.iter():
                kids = list(parent)
                for i, c in enumerate(kids):
                    if c.tag != "w" or _pos(c) != "conjunction":
                        continue
                    if _text(c).lower().strip() not in ADVERSATIVE:
                        continue
                    if i == 0 or i + 1 >= len(kids):
                        continue
                    left, right = kids[i - 1], kids[i + 1]
                    if left.get("class") != "cl" or right.get("class") != "cl":
                        continue
                    stats["adversative_pairs"] += 1
                    neg = _negated(left) != _negated(right)
                    fa, fb = _fillers(left), _fillers(right)
                    shared = set(fa) & set(fb)
                    stats["with_a_shared_slot"] += bool(shared)
                    for slot in shared:
                        got = _pair(fa[slot], fb[slot])
                        if not got:
                            continue
                        x, y = sorted([_text(got[0]).lower(),
                                       _text(got[1]).lower()])
                        if not x or not y or x == y:
                            continue
                        kind = "frustrated" if neg else "contrast"
                        found[(x, y, slot, kind)] += 1
                        if len(refs[(x, y, slot, kind)]) < 4:
                            refs[(x, y, slot, kind)].append(ref)
                        stats[kind] += 1
    return found, refs, stats


def main() -> int:
    found, refs, stats = extract()

    if "--word" in sys.argv:
        w = sys.argv[sys.argv.index("--word") + 1].lower()
        print(f"CONTRASTS OF  {w}")
        rows = [(n, k) for k, n in found.items() if w in (k[0], k[1])]
        for n, k in sorted(rows, reverse=True)[:20]:
            other = k[1] if k[0] == w else k[0]
            print(f"   {n:>3}x  {other:20}{k[3]:12}{k[2]:11}"
                  f"{', '.join(refs[k])}")
        return 0

    print("CONTRAST PAIRS - from adversative parallelism")
    print(f"  adversative clause pairs   {stats['adversative_pairs']:>6,}")
    print(f"    sharing a slot           {stats['with_a_shared_slot']:>6,}")
    print(f"  true contrasts             {stats['contrast']:>6,}")
    print(f"  frustrated expectation     {stats['frustrated']:>6,}   "
          f"one side negated -- kept apart")
    print(f"  distinct pairs             {len(found):>6,}")
    for kind in ("contrast", "frustrated"):
        print()
        print(f"  commonest {kind.upper()}, with the verses:")
        rows = [(n, k) for k, n in found.items() if k[3] == kind]
        for n, k in sorted(rows, reverse=True)[:12]:
            print(f"   {n:>3}x  {k[0]:16} / {k[1]:16}{k[2]:11}"
                  f"{', '.join(refs[k][:3])}")

    path = OUT / "contrast-pairs.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_source": "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., "
                       "CC BY 4.0",
            "_note": "Adversative reading comes from MACULA's contextual "
                     "english column, not from morphology. Inherited "
                     "interpretation -- see tools/contrast.py.",
        }) + "\n")
        for (x, y, slot, kind), n in found.most_common():
            fh.write(json.dumps({"a": x, "b": y, "slot": slot, "kind": kind,
                                 "count": n, "refs": refs[(x, y, slot, kind)]},
                                ensure_ascii=False) + "\n")
    print(f"\n  wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
