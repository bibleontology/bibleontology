"""Regression cases for tier-1 phrase detection.

Run with: python tests/test_phrases.py

John 1:1-18 is the standing case. It was chosen because the prologue layers
allusion densely, and running it exposed four defects in the first design --
most seriously that the stopword filter deleted the Genesis 1:1 link, which is
the single connection the feature most obviously has to make.

The rules are tuned, so the independent cases below matter as much as the
John 1 ones: they were not used to choose any threshold. If a change to
detection improves aggregate numbers but breaks these, it has regressed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# THE PUBLIC REPOSITORY HAS NO KJV (2026-10-21, plan 8.3b): the phrases these
# cases expect are the KJV's, so a copy without its verse file skips them.
if not (Path(__file__).resolve().parents[1] / "data" / "bible" / "verses.jsonl").exists():
    print("skipped: these cases read the KJV verse file, which the public repository does not carry")
    raise SystemExit(0)

from bibleont.phrases import links_for_verse  # noqa: E402
from bibleont.refs import parse_ref  # noqa: E402
from bibleont.corpus import get_corpus  # noqa: E402

failures: list[str] = []


def _vid(ref: str):
    return get_corpus().expand(parse_ref(ref))[0]


def links(ref: str):
    return links_for_verse(_vid(ref))


def targets(ref: str) -> set[str]:
    out = set()
    for link in links(ref):
        out |= {str(o.verse) for o in link.occurrences}
    return out


def expect_link(src: str, dst: str, phrase: str | None = None) -> None:
    for link in links(src):
        if phrase and link.text != phrase:
            continue
        if dst in {str(o.verse) for o in link.occurrences}:
            return
    got = ", ".join(sorted(targets(src))) or "nothing"
    failures.append(f"{src} should link to {dst}"
                    + (f' via "{phrase}"' if phrase else "")
                    + f" -- found: {got}")


def expect_no_link(src: str, dst: str) -> None:
    if dst in targets(src):
        failures.append(f"{src} should NOT link to {dst}")


# --- the crux: the prologue's opening is Genesis ------------------------------
expect_link("John 1:1", "Gen 1:1", "in the beginning")
expect_link("John 1:2", "Gen 1:1", "in the beginning")

# Day one of creation, behind John's light and darkness.
expect_link("John 1:5", "Gen 1:5")

# Known-good before the rework; must survive it.
expect_link("John 1:18", "1John 4:12", "no man hath seen god at any time")

# The Baptist's saying, shared with the synoptics.
expect_link("John 1:15", "Matt 3:11")

# --- idiom suppression --------------------------------------------------------
# "In the beginning of the reign of..." is a dating formula. Thirteen verses use
# it and none of them is alluding to Genesis. If these start linking, the
# continuation-based suppression has stopped working.
expect_no_link("Jer 26:1", "Gen 1:1")
expect_no_link("Ezra 4:6", "Gen 1:1")
expect_no_link("Ruth 1:22", "Gen 1:1")

# --- function-word noise ------------------------------------------------------
# "with god and the" genuinely recurs in Job 27:13 and means nothing.
expect_no_link("John 1:1", "Job 27:13")

# --- independent cases, not used to tune any threshold ------------------------
# Hebrews 1:10-12 quotes Psalm 102:25-27 nearly verbatim across three verses,
# applying a psalm addressed to the LORD to the Son.
expect_link("Heb 1:10", "Ps 102:25")
expect_link("Heb 1:11", "Ps 102:26")

# --- the tree/vine/fruit case -------------------------------------------------
# Jer 17, John 15 and Gal 5 paint one picture with different referents, and
# tier 1 deliberately does NOT join them -- they share no wording. What it must
# find is each passage's own verbatim anchor. If these three ever start linking
# to each other at tier 1, something has started matching on meaning, which is
# the one thing this detector must never do.
expect_link("Jer 17:7", "Ps 1:1", "blessed is the man that")
expect_link("Jer 17:8", "Ps 1:3", "a tree planted by the")
expect_link("Jer 17:8", "Ezek 19:10", "planted by the")  # the tree/vine bridge
expect_link("John 15:5", "Rom 11:16", "are the branches")
expect_link("Gal 5:22", "Eph 5:9", "the fruit of the spirit is")

expect_no_link("John 15:5", "Jer 17:8")
expect_no_link("Gal 5:22", "John 15:5")

# --- quotation aggregation: two shapes of the same act -----------------------
# A quotation that survived translation intact is one long run. One that came
# through the Septuagint is not: Luke follows it, so the KJV wording drifts from
# KJV Isaiah and the match shatters. Both must rank their source first.
from bibleont.phrases import sources_for_verse  # noqa: E402


def top_source(ref: str) -> str:
    found = sources_for_verse(_vid(ref))
    return str(found[0].target) if found else "nothing"


def expect_top_source(ref: str, dst: str, min_fragments: int = 1) -> None:
    found = sources_for_verse(_vid(ref))
    hit = next((s for s in found if str(s.target) == dst), None)
    if hit is None:
        failures.append(f"{ref} should draw on {dst} -- top was {top_source(ref)}")
        return
    if hit.fragments < min_fragments:
        failures.append(
            f"{ref} -> {dst} should merge to at least {min_fragments} disjoint "
            f"fragments, got {hit.fragments}"
        )


# Fragmented: Luke 4:18 quotes Isa 61:1 in four separate pieces, and no single
# one of them is remarkable. The evidence is that they land on one verse.
expect_top_source("Luke 4:18", "Isa 61:1", min_fragments=3)
expect_top_source("Luke 4:19", "Isa 61:2")

# Verbatim: Luke 3 quotes Isa 40. Overlapping n-grams must merge -- before they
# did, Matt 3:3 scored as "13 fragments, 136 words" for one 20-word run.
expect_top_source("Luke 3:4", "Isa 40:3")
expect_top_source("Luke 3:5", "Isa 40:4")
for _r, _d in [("Luke 3:4", "Matt 3:3"), ("Luke 3:4", "Mark 1:3")]:
    _hit = next((s for s in sources_for_verse(_vid(_r)) if str(s.target) == _d), None)
    if _hit and _hit.fragments > 2:
        failures.append(
            f"{_r} -> {_d} is one continuous quotation but merged to "
            f"{_hit.fragments} fragments; overlapping n-grams are not merging"
        )

# --- the temple saying: what tier 1 can and cannot reach --------------------
# John 2:19 "Destroy this temple, and in three days I will raise it up" recurs
# five times across four books, and three separately defensible thresholds were
# each deleting part of it. Aggregation now sees phrases display rejects.
expect_top_source("John 2:19", "Mark 14:58", min_fragments=2)
expect_top_source("John 2:19", "Matt 27:63")

# And the honest limit, recorded so nobody "fixes" it by lowering the bar: the
# accusation verses reach John 2:19 only through "in three days", which scores
# identically to pure coincidence in Judges and Exodus. Wording cannot separate
# them -- what distinguishes the real ones is carrying "temple" AND "three days"
# together, which is co-occurrence rather than shared phrasing. That is tier 2.
for _noise in ["Exod 23:26", "1Kgs 11:12", "Judg 14:14"]:
    if _noise in {str(s.target) for s in sources_for_verse(_vid("John 2:19"))}:
        failures.append(
            f"John 2:19 should not surface {_noise} at tier 1 -- if it does, the "
            f"aggregation threshold has been lowered past what wording supports"
        )

# --- rarity, and the best link in the corpus -------------------------------
# "Merciful and gracious" occurs in exactly two verses: Exodus 34:6, where it
# is proclaimed to Moses on the mount, and Psalm 103:8, which quotes it three
# verses after saying "He made known his ways unto Moses". Three words and one
# fragment scored 3.0 against a threshold of 4.0, so the strongest link in the
# corpus was dropped for being short, while "and plenteous in" -- twice as
# common, no longer -- scored the same.
expect_top_source("Ps 103:8", "Exod 34:6")

# The rarity bonus is earned by rare words, not by a rare sequence, and this is
# the case that fixes the bar. Awarding it on sequence rarity alone added 28%
# more links, nearly all noise. These two must never come back.
for _seq in ["turn aside and", "and see this"]:
    _hits = [s for s in sources_for_verse(_vid("Exod 3:3"))
             if any(p.text == _seq for p in s.phrases)]
    if _hits:
        failures.append(
            f"Exod 3:3 surfaced a link resting on {_seq!r} -- the rarity bonus "
            f"is being awarded for an unusual ordering of ordinary words"
        )

# What the corrected bar is supposed to reach: one sheep gone astray finding
# the other.
if "Ps 119:176" not in {str(s.target) for s in sources_for_verse(_vid("Isa 53:6"))}:
    failures.append(
        "Isa 53:6 should reach Ps 119:176 on 'have gone astray' -- two rare "
        "content words in a phrase used three times in the corpus"
    )

if failures:
    print(f"FAIL ({len(failures)})")
    for f in failures:
        print("  -", f)
    raise SystemExit(1)
print("ok - all phrase regression cases pass")
