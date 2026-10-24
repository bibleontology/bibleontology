"""Search aliases: an English word -> the Hebrew and Greek words it renders
(2026-09-30).

The first idea was to mine all translations plus Strong's/MACULA for aliases;
the other translations carry no Strong's tags and would need statistical
alignment, so they were dropped on 2026-09-30. So two sources,
both already on disk and both tied to the original word by word:

  - MACULA's English gloss on every Hebrew and Greek word
    (out/placeholder-nodes.jsonl.gz) -- complete, and it decides
  - the Berean editors' Strong's tags on their own English
    (out/bsb-align.jsonl.gz) -- only for a form MACULA never glosses: the
    tags are partial (Deut 7:8's "loved" carries none) and in places
    displaced onto the phrase beside their word (measured 2026-09-30)

An English form keeps a Strong's number when it is a common rendering of
it (3 or more times and a tenth of the form's uses) or a rare word that
carries a large share of the form (ἑτεροζυγέω is "unequally yoked" once,
2Cor 6:14). Measured on the images audit (2026-09-30): an
English-only word test was wrong on 5 of 14 references; with these two
sources, 14 of 16, the misses real aliases only another translation holds.

    python tools/aliases.py  ->  out/word-aliases.json
"""
from __future__ import annotations

import collections
import gzip
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
# function words, including the prepositions and auxiliaries MACULA's glosses
# carry ("grumbled against", "brought ~ out"): without them the gloss is one
# content word and counts
STOP = set("the and of to in a an is was were be are his her their our your my you he she it they we "
           "who that this with for on as by from not no all will shall have has had him them me us "
           "i o against upon into over before after about unto out up down off then there when what "
           "which may might would could should did does do been being also even so because but or nor "
           "yet if among through under above near away again its thy thee thou ye".split())


def key_of(lang, strong):
    s = re.sub(r"\D", "", strong or "")
    return (("h" if lang == "hebrew" else "g") + str(int(s))) if s else None


def main():
    # kept apart, because they are not trusted alike: out/bsb-align.jsonl.gz
    # sometimes sits a tag on the phrase beside its word -- "the earth" in
    # "all the earth" carries כֹּל 167 times (1Chr 16:23) -- where MACULA's
    # glosses never do
    forms = collections.defaultdict(collections.Counter)      # Berean tags
    macs = collections.defaultdict(collections.Counter)       # MACULA glosses
    n_bsb = n_mac = 0
    for ln in gzip.open(OUT / "bsb-align.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(ln)
        t = r.get("text") or ""
        for a, b, s in r.get("spans") or []:
            # one content word, as with the glosses: a span "all the earth"
            # tagged כֹּל made "earth" an alias of "all"
            ws = [w for w in re.findall(r"[a-z]+", t[a:b].lower()) if w not in STOP and len(w) > 2]
            if len(ws) == 1:
                forms[ws[0]][s.lower()] += 1
                n_bsb += 1
    for ln in gzip.open(OUT / "placeholder-nodes.jsonl.gz", "rt", encoding="utf-8"):
        d = json.loads(ln)
        if not d.get("word"):
            continue
        k = key_of(d.get("lang"), d.get("strong"))
        if not k:
            continue
        # one content word only: MACULA sometimes glosses a word with a
        # phrase ("the whole earth" on כֹּל), which would make "earth" an
        # alias of "all"
        ws = [w for w in re.findall(r"[a-z]+", (d.get("text") or "").lower()) if w not in STOP and len(w) > 2]
        if len(ws) == 1:
            macs[ws[0]][k] += 1
            n_mac += 1
    out = {}
    for w in set(forms) | set(macs):
        c, g = forms.get(w, collections.Counter()), macs.get(w, collections.Counter())
        n, m = sum(c.values()), sum(g.values())
        keep = collections.Counter()
        # MACULA: a common rendering (3+, a tenth), or a rare word carrying a
        # large share when seen twice or when that one gloss is all it has
        for s, x in g.items():
            if (x >= 3 and x / m >= 0.1) or (x / m >= 0.3 and (x >= 2 or x == m)):
                keep[s] += x
        # the Berean's tags only for a form MACULA never glosses
        # ("cornerstone"): its single-word "earth" spans never carry אֶרֶץ
        # at all, and 151 of 312 carry כֹּל -- the tag displaced
        # systematically, so no threshold separates it (tried: a quarter, then
        # 40%, both let כֹּל through)
        if not m:
            for s, x in c.items():
                if x >= 2 and x / n >= 0.25:
                    keep[s] += x
        if keep:
            out[w] = [[s, x] for s, x in keep.most_common()]
    (OUT / "word-aliases.json").write_text(json.dumps({"_note": __doc__.split("\n\n")[0], "forms": out},
                                                      ensure_ascii=False), encoding="utf-8")
    print(f"forms {len(out)} (tags read: Berean {n_bsb:,}, MACULA glosses {n_mac:,})")
    for probe in ("earthquake", "shook", "loved", "cornerstone", "lampstand", "yoked", "rooted", "dust"):
        print(f"  {probe:12} {out.get(probe, [])[:4]}")


if __name__ == "__main__":
    main()
