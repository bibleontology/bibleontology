"""Gift then response: God saves by grace, and the answer to it is a life.

2026-09-15: God saves us through grace and our response is
something positive, with two instances at deliberately different scales:

    Eph 2:8-9  -> Eph 2:10      saved by grace, not works
                                -> created in Christ FOR good works
    Rom 1-8    -> Rom 12        the whole argument of justification
                                -> "therefore present your bodies"

Theology calls this the indicative and the imperative. The point of the
pattern is the HINGE between them, and the hinge is marked.

## What is detectable, and what is not

`out/sentence-function.jsonl.gz` types the hinge exactly. Both of the
instances, and the classic others, are the same thing:

    Rom 12:1   contingency/cause, backward, "I urge you"
    Eph 2:10   contingency/cause, backward, "For"
    Rom 6:12   contingency/cause, backward, "Let not sin therefore reign"
    Col 3:1    contingency/condition, backward, "If then you have been raised"

A backward-binding causal inference: this follows FROM that. That is the
structure and it costs nothing to find.

**What the stamps cannot supply is the two sides.** The taxonomy has no
`grace`, no `good_works`, no `obedience`, no `sanctification` -- the same
kind of hole `divine_investigation` was for the Flood and Sodom. So the sides
are tested on LEMMAS, which are present and specific:

    gift       χάρις σῴζω ἔλεος δικαιόω ἀπολύτρωσις δωρεά χαρίζομαι
    response   imperative mood, παρακαλέω παρίστημι περιπατέω,
               ἔργον with ἀγαθός

Lemmas are narrower than the idea -- a passage can teach grace without the
word -- so this is a recall floor, not a definition. Where it fires it is
showing the actual words.

    python tools/giftresponse.py --check
    python tools/giftresponse.py --span 12
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

GIFT = {"χάρις", "σῴζω", "σωτηρία", "ἔλεος", "ἐλεέω", "δικαιόω", "δικαιοσύνη",
        "ἀπολύτρωσις", "δωρεά", "δωρεάν", "χαρίζομαι", "ζωοποιέω",
        "καταλλάσσω", "καταλλαγή", "ἱλαστήριον", "ἄφεσις"}
RESPONSE = {"παρακαλέω", "παρίστημι", "περιπατέω", "ἀγαθός", "ἔργον",
            "ἅγιος", "ἁγιασμός", "ὑπακοή", "ὑπακούω", "δουλεύω", "καρπός",
            "ζηλωτής", "σπουδή", "ἀγάπη", "φέρω", "שָׁמַר", "עָשָׂה", "הלך"}

# THE BRIDGE. 2026-09-15: there is a bridge between the grace and the
# response. Before the fruit in John 15:4-5 there is connection/nourishment.
# Before the behaviors in Romans 12, there is being transformed. Before works
# in Ephesians, there is workmanship.
#
# That middle term is what makes the pattern theology rather than moralism:
# something is DONE TO the person which makes the response possible. Without
# it the shape collapses to "be saved, now behave", which is not what any of
# these passages says.
#
# Ezekiel 36:25-27 is the archetype and carries all three in three verses --
# cleansed, given a new heart and spirit, and THEN walking in the statutes.
# John 15's gift is the same word: "you are already clean".
BRIDGE = {"κτίζω", "ποίημα", "κτίσις", "καινός", "μεταμορφόω", "ἀνακαίνωσις",
          "ἀνακαινόω", "παλιγγενεσία", "μένω", "λουτρόν", "ζωοποιέω",
          "συνεγείρω", "ἐνεργέω", "ἀναγεννάω", "καρδία",
          "חָדָשׁ", "לֵב", "רוּחַ", "טָהֵר", "טָהֹר", "נָתַן", "בָּרָא", "חָדַשׁ",
          "כּוּן"}

# The bridge is always God MAKING something, and Psalm 51 names it with the
# verb of Genesis 1:1. 2026-09-15: Psalm 51 - cleanse me with hyssop.
#
#   Ps 51:9    hyssop, cleanse, wash whiter than snow        the gift, asked for
#   Ps 51:12   CREATE (bara) in me a clean heart,            the bridge
#              renew a right spirit within me
#   Ps 51:15   then I will teach transgressors your ways     the response
#
# Psalm 51 is Ezekiel 36 turned into a prayer -- the same heart, the same
# spirit, the same cleansing, asked for rather than promised. And the creation
# verb runs through every instance given:
#
#   Ps 51:12   bara         create
#   Ezek 36:26 natan lev    give a new heart
#   Eph 2:10   poiema ktizo workmanship, created
#   2 Cor 5:17 kaine ktisis new creation
#   Titus 3:5  palingenesia regeneration
#
# Which is why the pattern is not moralism: the middle term is an act of
# creation, not an act of will.


def load_sf():
    out = {}
    for line in gzip.open(OUT / "sentence-function.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if any(k.startswith("_") for k in d):
            continue
        out.setdefault(d["ref"], []).append(d)
    return out


def load_il():
    out = {}
    for line in gzip.open(OUT / "interlinear.jsonl.gz", "rt",
                          encoding="utf-8"):
        d = json.loads(line)
        if d.get("ref"):
            out[d["ref"]] = d["words"]
    return out


def lemmas(il, refs):
    return [w.get("l") for r in refs for w in il.get(r, []) if w.get("l")]


def key(r):
    b, c, v = r.split(".")
    return (b, int(c), int(v))


def hinges(sf, il, span=8, back=None):
    """-> [(ref, gift refs, response ref)] every marked gift->response turn.

    The hinge is a backward-binding causal sentence. What makes it THIS
    pattern rather than any inference is that gift words sit behind it and
    response words sit in it.
    """
    back = back or span
    order = sorted(il, key=key)
    ix = {r: i for i, r in enumerate(order)}
    out = []
    for ref, sents in sf.items():
        if ref not in ix:
            continue
        turn = [s for s in sents
                if s.get("relation") == "contingency"
                and s.get("direction") == "backward"]
        if not turn:
            continue
        i = ix[ref]
        book = ref.split(".")[0]
        prior = [r for r in order[max(0, i - back):i]
                 if r.split(".")[0] == book]
        here = [r for r in order[i:i + 2] if r.split(".")[0] == book]
        g = [w for w in lemmas(il, prior) if w in GIFT]
        rsp = [w for w in lemmas(il, here) if w in RESPONSE]
        br = [w for w in lemmas(il, prior + here) if w in BRIDGE]
        if g and rsp:
            out.append((ref, sorted(set(g)), sorted(set(rsp)),
                        prior[0] if prior else ref, sorted(set(br))))
    out.sort(key=lambda x: key(x[0]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--span", type=int, default=8,
                    help="how far back the gift may sit, in verses")
    ap.add_argument("--book")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--bridged", action="store_true",
                    help="only hinges with the middle term")
    a = ap.parse_args()

    sf, il = load_sf(), load_il()
    if a.check:
        for ref in ("Eph.2.10", "Rom.12.1", "Rom.6.12", "Col.3.1", "Tit.3.8"):
            s = sf.get(ref, [])
            print(f"  {ref:<10} " + "; ".join(
                f"{x.get('act')}/{x.get('relation')}/{x.get('subtype')}"
                f"/{x.get('direction')} opens={x.get('opens')}" for x in s))
        return 0

    got = hinges(sf, il, a.span)
    if a.book:
        got = [g for g in got if g[0].startswith(a.book + ".")]
    bybook = collections.Counter(g[0].split(".")[0] for g in got)
    print(f"{len(got):,} gift->response hinges "
          f"(gift within {a.span} verses)\n")
    print("  by book: " + ", ".join(f"{b} {n}" for b, n in
                                    bybook.most_common(12)) + "\n")
    if a.bridged:
        got = [x for x in got if x[4]]
        print(f"  {len(got):,} of them carry a BRIDGE\n")
    for ref, g, r, frm, br in got[:a.top]:
        print(f"  {frm}..{ref.split('.')[-1]:<4} {ref:<12}")
        print(f"      gift     {' '.join(g[:6])}")
        if br:
            print(f"      BRIDGE   {' '.join(br[:6])}")
        print(f"      response {' '.join(r[:6])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
