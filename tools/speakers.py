"""Who speaks, from the original language and nothing else.

2026-09-09: the divine name is the kind of thing that should come exclusively
from the original language -- and, distinguishing it from the speech layer
built an hour earlier, that is fundamentally different from letting BSB help
discern where quotes belong. Principle 44 records the line: a
translation may supply **structure** the source does not record, never
**identity** it does.

Speaker identity is squarely on the forbidden side, and the English route was
failing in a way that had gone unnoticed. `_speaker()` in
`src/bibleont/turns.py` regexes a name out of the KJV, and our KJV file has lost
the small caps that separate YHWH from Adonai -- `LORD` 6 against `Lord` 7,719.
So every divine attribution it produced was the same undifferentiated string.

## What replaces it

MACULA's `frame` attribute already names the agent of every verb it annotates,
including the verbs of speaking. Filtering `out/frames.jsonl.gz` to speech verbs
gives the speaker in the language the text was written in, with no English step
at any point.

    speech-verb frames        9,005
    with an agent named       8,585   (95.3%)

    English regex, divine       351   all of them the string "the Lord"
    this layer, divine        1,449   told apart by lemma

Four times the attributions **and** a distinction English had destroyed. There
was no trade-off to weigh.

## The honest limit, stated because it is the falsifier for Principle 44

**Greek `κύριος` does not resolve.** It renders YHWH in Septuagint quotations
and is also an ordinary title of respect, so on this one point the source
language is genuinely ambiguous and going to it buys nothing. Those 117
attributions are emitted with `ambiguous: true` rather than silently assigned.
Hebrew has no such problem: יהוה, אֲדֹנָי, אֱלֹהִים and אֵל are four different words.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
DEST = OUT / "speakers.jsonl.gz"
CREDIT = "MACULA Hebrew Linguistic Datasets, available at https://github.com/Clear-Bible/macula-hebrew/; MACULA Greek Linguistic Datasets, available at https://github.com/Clear-Bible/macula-greek/; © Biblica, Inc., CC BY 4.0"

# Verbs of speaking. Hebrew first, then Greek.
SAY = {
    "אָמַר": "say", "דָּבַר": "speak", "קָרָא": "call", "עָנָה": "answer",
    "צָוָה": "command", "נָגַד": "tell", "שָׁאַל": "ask", "שָׁבַע": "swear",
    "λέγω": "say", "λαλέω": "speak", "ἀποκρίνομαι": "answer", "φημί": "say",
    "κράζω": "cry out", "ἐρωτάω": "ask", "παραγγέλλω": "command",
    "κηρύσσω": "proclaim", "προσφωνέω": "address",
}

# The divine names, and whether the ORIGINAL settles which is meant.
DIVINE = {
    "יהוה": ("YHWH", False),
    "אֲדֹנָי": ("Adonai", False),
    "אֱלֹהִים": ("Elohim", False),
    "אֵל": ("El", False),
    # AMBIGUOUS IN THE SOURCE: kyrios renders YHWH in LXX quotation and is also
    # an ordinary title. Going to the original does not settle it, so it is not
    # pretended to. This is the stated falsifier for Principle 44.
    "κύριος": ("Kyrios", True),
    "θεός": ("Theos", False),
}


def load(name):
    rows = []
    with gzip.open(OUT / name, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            if not any(k.startswith("_") for k in d):
                rows.append(d)
    return rows


def propagate(rows):
    """A speaker named at the head of a quotation governs the rest of it.

    Measured 2026-09-11: **8,798 verses sit inside a quotation and carry no
    attribution** -- 14,808 in quotation against 7,444 attributed. Those are
    not verses without a speaker; they are verses whose speaker was named
    once and not repeated, which is how direct speech is written.

        contiguous quotation runs   2,704
        median 2 verses, 90th percentile 14, longest 68

    This is the inheritance measured in August from the other side: 53% of
    Genesis's turns, 78% of Job's and 93% of Mark's never state who they are
    addressed to. Context descends the group tree or it does not exist.

    ## The two sources, and why mixing them is allowed here

    IDENTITY stays MACULA's. EXTENT comes from BSB punctuation, and Principle
    44 permits exactly that: the original records no quotation marks at all,
    so borrowing where a quotation runs adds information rather than replacing
    any. A propagated row carries `by: "span"` so it is never mistaken for a
    verse that names its own speaker.

    A run is broken by any verse leaving the quotation, so a new speaker
    starting a new quotation begins a new run and inherits nothing.
    """
    depth = {}
    p = ROOT / "out" / "speech-depth.jsonl.gz"
    if not p.exists():
        print("\n  no speech-depth layer; nothing to propagate")
        return rows
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                if not any(k.startswith("_") for k in d):
                    depth[d["ref"]] = d.get("depth") or 0
    stated = {}
    for r in rows:
        r["by"] = "stated"
        stated.setdefault(r["ref"], r)

    def sortkey(ref):
        b, c, v = ref.split(".")
        return (b, int(c), int(v))

    inside = sorted((r for r, v in depth.items() if v and v > 0), key=sortkey)
    added, carry, prev = [], None, None
    for ref in inside:
        b, c, v = sortkey(ref)
        # a gap, a new chapter or a new book ends the run
        if prev is None or (b, c) != (prev[0], prev[1]) or v != prev[2] + 1:
            carry = None
        prev = (b, c, v)
        if ref in stated:
            carry = stated[ref]
            continue
        if carry is not None:
            added.append({**{k: carry[k] for k in
                             ("lang", "speaker", "verb", "act", "divine",
                              "ambiguous") if k in carry},
                          "ref": ref, "addressee": carry.get("addressee"),
                          "by": "span", "from": carry["ref"]})
    print(f"\nSPAN PROPAGATION (extent from BSB, identity from MACULA)")
    print(f"  verses inside a quotation        {len(inside):>7,}")
    print(f"  already attributed               {len(stated):>7,}")
    print(f"  attributed by span inheritance   {len(added):>7,}")
    print(f"  still unattributed inside a span "
          f"{len(inside) - len(stated & set(inside)) - len(added):>7,}"
          if False else
          f"  still unattributed inside a span "
          f"{len([r for r in inside if r not in stated]) - len(added):>7,}")
    return rows + added


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    frames = load("frames.jsonl.gz")
    say = [r for r in frames if r.get("lemma") in SAY]
    named = [r for r in say if r.get("agent")]
    print(f"speech-verb frames: {len(say)} of {len(frames)}")
    print(f"  with an agent named: {len(named)} ({100*len(named)/len(say):.1f}%)")

    rows = []
    for r in named:
        for who in r["agent"]:
            div, amb = DIVINE.get(who, (None, False))
            rows.append({
                "ref": r["ref"], "lang": r["lang"],
                "speaker": who, "verb": r["lemma"],
                "act": SAY[r["lemma"]],
                "divine": div, "ambiguous": bool(div and amb),
                "addressee": r.get("patient") or None,
            })

    c = collections.Counter(x["speaker"] for x in rows)
    print(f"\nattributions {len(rows)}   distinct speakers {len(c)}")
    print("top speakers, no English at any step:")
    for w, n in c.most_common(10):
        print(f"   {w:<14} {n}")

    div = collections.Counter(x["divine"] for x in rows if x["divine"])
    print(f"\ndivine attributions {sum(div.values())}:", dict(div))
    amb = sum(1 for x in rows if x["ambiguous"])
    print(f"  of which the SOURCE cannot disambiguate: {amb} (Greek kyrios)")
    print("  the English regex found 351, every one the string 'the Lord'")

    rows = propagate(rows)

    if not a.write:
        print("\nnot written -- pass --write")
        return 0
    with gzip.open(DEST, "wt", encoding="utf-8") as f:
        f.write(json.dumps({
            "_source": CREDIT + "; quotation extent from BSB punctuation "
                                "via out/speech-depth.jsonl.gz",
            "_note": "Who speaks. IDENTITY is MACULA's frame annotation and "
                     "nothing else; no English is consulted for it. EXTENT -- "
                     "where a quotation runs -- is BSB punctuation, which "
                     "Principle 44 permits: the source records no quotation "
                     "marks at all, so this adds information rather than "
                     "replacing any. Every row says which it is in `by`: "
                     "'stated' where the verse names its speaker, "
                     "'span' where a speaker named at the head of a "
                     "quotation governs a verse inside it. Greek kyrios is "
                     "marked ambiguous because the source does not settle it.",
        }, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nwrote {DEST.relative_to(ROOT)}  ({len(rows)} attributions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
