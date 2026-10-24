"""Regression cases for the citation-formula detector.

Every case here comes from a real failure during development, not from
imagining what might break. The comment on each says what went wrong.

Run: python tests/test_citations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

# THE PUBLIC REPOSITORY HAS NO KJV (2026-10-21, plan 8.3b). These cases were
# written against its wording, so a copy without its verse file skips them and
# says so, rather than failing on a text it was never meant to carry.
if not (Path(__file__).resolve().parents[1] / "data" / "bible" / "verses.jsonl").exists():
    print("skipped: these cases read the KJV verse file, which the public repository does not carry")
    raise SystemExit(0)

from bibleont.citations import (  # noqa: E402
    agreement,
    announcements,
    placements,
)
from bibleont.phrases import sources_for_verse  # noqa: E402

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if not ok:
        FAILURES.append(f"{label}: {detail}" if detail else label)


_ANN = {a.pretty: a for a in announcements(nt_only=True)}


def _state(ref: str) -> str:
    return agreement(_ANN[ref]).state


# -- detection ---------------------------------------------------------------

# The formulas have to be found at all.
for ref in ("Matthew 4:4", "Luke 3:4", "Romans 10:16", "Acts 2:16"):
    check(f"{ref} is an announcement", ref in _ANN)

# "The book of life" is not a citation of anything. Four verses matched the
# "in the book of" formula and were reported as quotations.
for ref in ("Philippians 4:3", "Revelation 13:8", "Revelation 20:15"):
    check(f"{ref} is not an announcement", ref not in _ANN,
          "the book of life is not a source being quoted")

# Hebrews 7:14 is "a tribe as to which Moses said nothing about priests" --
# a denial that a source says something, recorded as a citation of it.
check("Hebrews 7:14 is not an announcement", "Hebrews 7:14" not in _ANN,
      "'Moses spake nothing' denies a source rather than citing one")


# -- naming the source -------------------------------------------------------

check("Matthew 8:17 names Isaiah", _ANN["Matthew 8:17"].named_books == ["Isa"])
# Book codes, not display titles. Storing "Isaiah" and comparing it against
# VerseId.book ("Isa") reported disagreement in all thirteen cases.
check("named books are canonical codes",
      all(b == b.strip() and len(b) <= 6 for a in _ANN.values() for b in a.named_books))

# Most announcements name nothing, and none may be invented for them.
check("Matthew 4:4 names no source", not _ANN["Matthew 4:4"].names_a_source,
      "'It is written' names no book and none may be supplied")


# -- placement ---------------------------------------------------------------

# The formula routinely ends the verse -- "spoken by Esaias the prophet,
# saying," -- and the quotation is the next verse. Looking only at the
# announcing verse finds nothing, because there is nothing there.
check("Matthew 4:14 places Isaiah 9:1", _state("Matthew 4:14") == "confirmed",
      "the quotation is in the following verse, not this one")
check("Acts 2:16 places Joel", _state("Acts 2:16") == "confirmed")

# Acts 2:16 is entirely formula: "this is what was spoken by the prophet
# Joel." It reached Exodus 16:23 through its opening words ("this is that
# which" in the older wording) -- one introduction matching another -- and
# that outranked Joel.
_acts = [str(s.target) for _o, s in placements(_ANN["Acts 2:16"])]
check("Acts 2:16 does not reach Exodus", not any(t.startswith("Exod") for t in _acts),
      f"formula matched formula: {_acts[:4]}")

# Sibling quotations are not rivals. Luke 3:4 was reported as outranked by
# Matthew 3:3 -- but both quote Isaiah 40:3, so Matthew corroborates Luke
# rather than competing with it.
check("Luke 3:4 confirms Isaiah", _state("Luke 3:4") == "confirmed",
      "outranked by the synoptic parallel, which quotes the same passage")
_sibs = [str(s.target) for s in agreement(_ANN["Luke 3:4"]).siblings]
check("Luke 3:4 lists its parallels", "Matt 3:3" in _sibs or "Mark 1:3" in _sibs,
      f"siblings were {_sibs[:4]}")


# -- the cases that must stay unresolved -------------------------------------

# Matthew attributes to Jeremiah a passage that reads like Zechariah 11. This
# is a real and much-discussed difficulty, and the tool must not quietly settle
# it. A boolean "confirmed" did exactly that, by finding some verse of Jeremiah
# far down the ranking on connective wording.
check("Matthew 27:9 does not confirm Jeremiah", _state("Matthew 27:9") != "confirmed",
      "the Jeremiah/Zechariah attribution must not be silently resolved")
_m279 = agreement(_ANN["Matthew 27:9"])
check("Matthew 27:9 surfaces Zechariah", str(_m279.rival.target) == "Zech 11:13",
      "the reader is owed the passage the wording actually lands on")

# Isaiah 53:4 and 29:13 come through into English wording that shares almost
# nothing with the quoting verse. These are the honest gaps: the text says it
# is quoting Isaiah and the word matching cannot say where. Claiming a
# placement would be worse than admitting none.
for ref in ("Matthew 8:17", "Mark 7:6"):
    check(f"{ref} does not claim Isaiah", _state(ref) != "confirmed",
          "translation divergence, and it should stay visible as a gap")

# Mark 7:6 and Matthew 15:8 both quote Isaiah 29:13, and the eleven words they
# share are much the strongest evidence available about that verse. Filtering
# same-testament matches out of the source ranking must not throw them away --
# they belong in the sibling list.
_mk76 = agreement(_ANN["Mark 7:6"])
check("Mark 7:6 keeps its parallel",
      any(str(s.target) == "Matt 15:8" for s in _mk76.siblings),
      "the synoptic parallel is corroboration, not a rival")


# -- the silent-empty lookup -------------------------------------------------

# sources_for_verse compared a string against VerseId and returned [] rather
# than raising, so a run measuring 117 announcements reported that none could
# be placed and looked like a real answer.
check("sources_for_verse accepts a reference string",
      bool(sources_for_verse("Luke 3:4")),
      "a string used to return no results instead of an error")



# -- an announcement without a named source still places -----------------------

# "Unnamed" used to return before the wording was consulted, which discarded
# the more useful half. A verse can announce a quotation without saying whose,
# and the phrase index usually finds it anyway. One instrument says *this is a
# quotation* and declines to name the source; the other says *of this*.
def _placed(ref):
    for a in announcements():
        if str(a.verse) == ref:
            ag = agreement(a)
            return str(ag.rival.target) if ag.rival else None
    return None


check("Rom 8:36 places on Ps 44:22 though Paul names no book",
      _placed("Rom 8:36") == "Ps 44:22",
      "as it is written, and the wording finds the psalm")

# The antitheses of Matthew 5 answer commandments they quote without naming.
check("Matt 5:21 places on the sixth commandment",
      _placed("Matt 5:21") in ("Exod 20:13", "Deut 5:17"),
      "ye have heard that it was said ... Thou shalt not kill")
check("Matt 5:43 places on Leviticus 19:18",
      _placed("Matt 5:43") == "Lev 19:18",
      "thou shalt love thy neighbour")

# And the honest limit, recorded so nobody reads the feature as reliable:
# Matthew 5:38 quotes "An eye for an eye" against Exodus 21:24's "Eye for eye",
# so no n-gram survives and it places on an unrelated verse at the floor score.
# The placement is a candidate, never a conclusion.
check("Matt 5:38 does NOT place on Exodus 21:24",
      _placed("Matt 5:38") != "Exod 21:24",
      "if this ever passes, the article problem was fixed and this case should "
      "be rewritten to expect it")


# ---------------------------------------------------------------------------
# Addresses above a verse, added 2026-08-30.
#
# Until then a verse was the only thing this system could name, which made a
# verse the only container anything could hang from -- so a speech, a
# collection or a scroll had nowhere to attach and 5,925 relations wired a
# verse straight to an idea instead. These cases exist because that limit was
# invisible: nothing failed, the graph simply grew the wrong shape.

from bibleont.corpus import get_corpus                          # noqa: E402
from bibleont.refs import RefError, parse_ref                   # noqa: E402

_c = get_corpus()

# The forms that already worked must go on meaning exactly what they meant.
for _text, _n in (("Gen 5:3", 1), ("Gen 5:3-5", 3), ("Gen 5:3-6:2", 32),
                  ("1 Samuel 16:13", 1)):
    _r = parse_ref(_text)
    check(f"{_text} still parses as verses", _r.granularity == "verse")
    check(f"{_text} still covers {_n} verse(s)", len(_c.expand(_r)) == _n,
          f"got {len(_c.expand(_r))}")

check("Job 1 is a chapter", parse_ref("Job 1").granularity == "chapter")
check("Job 1 covers the whole chapter", len(_c.expand(parse_ref("Job 1"))) == 22,
      f"got {len(_c.expand(parse_ref('Job 1')))}")

# The speech from the whirlwind: four chapters, the climax of the book, and
# unaddressable until this existed.
check("Job 38-41 is a chapter range",
      parse_ref("Job 38-41").granularity == "chapter")
check("Job 38-41 covers 129 verses", len(_c.expand(parse_ref("Job 38-41"))) == 129,
      f"got {len(_c.expand(parse_ref('Job 38-41')))}")

check("a whole book needs allow_book", len(_c.expand(parse_ref("Obadiah", True))) == 21)

# A book reference must terminate at the end of the book rather than walking
# empty chapters to the iteration guard, which is what it did first.
check("a whole book stops at the end of the book",
      len(_c.expand(parse_ref("Job", True))) == 1070,
      f"got {len(_c.expand(parse_ref('Job', True)))}")

# THE ONE THAT MATTERS MOST. Seventeen books are ordinary English words, so a
# bare book name parsing by default would turn the person Mark into the gospel
# and any prose containing "Numbers" into scripture.
for _word in ("Mark", "Numbers", "Job", "Acts", "Judges", "Revelation"):
    try:
        parse_ref(_word)
        check(f"bare {_word!r} is refused by default", False,
              "it parsed, and every mention of the word is now a citation")
    except RefError:
        check(f"bare {_word!r} is refused by default", True)

# A citation must survive the round trip saying what it said. "Job 1" and
# "Job 1:1-22" cover the same verses and are not the same claim.
for _text in ("Gen 5:3", "Gen 5:3-5", "Gen 5:3-6:2", "Job 1", "Job 38-41"):
    check(f"{_text} round-trips unchanged", str(parse_ref(_text)) == _text,
          f"became {str(parse_ref(_text))!r}")

# Corroboration asks whether the cited text names both parties. That is a fair
# question of one verse and a meaningless one of 129, where any pair of names
# will appear somewhere -- so a container must not count as evidence, or
# citing broadly becomes the cheapest way past the check.
check("a verse is evidence for corroboration", not parse_ref("Gen 14:9").is_whole)
check("a chapter is not", parse_ref("Job 1").is_whole)
check("a chapter range is not", parse_ref("Job 38-41").is_whole)

# ...and the check must actually behave that way, not merely be able to tell
# the difference. A first version of these cases tested `is_whole` alone and
# passed happily while the filter using it was deleted.
import json as _json                                            # noqa: E402
import tempfile as _tmp                                         # noqa: E402
from pathlib import Path as _Path                               # noqa: E402

from bibleont.check_extraction import check as _check_batch     # noqa: E402


def _batch(refs: list[str]) -> dict:
    """A two-person relation cited however the caller says, checked."""
    d = _Path(_tmp.mkdtemp())
    people = [
        {"id": "abner", "name": "Abner", "type": "person", "gender": "male"},
        {"id": "asahel", "name": "Asahel", "type": "person", "gender": "male"},
    ]
    rel = {"src": "abner", "dst": "asahel", "type": "killed", "refs": refs,
           "certainty": "explicit", "note": "test fixture"}
    (d / "persons.jsonl").write_text(
        "\n".join(_json.dumps(p) for p in people), encoding="utf-8")
    (d / "relations.jsonl").write_text(_json.dumps(rel), encoding="utf-8")
    return _check_batch(d)


# 2 Samuel 2:23 names both men and says one killed the other: real evidence.
_ok = _batch(["2Sam 2:23"])
check("a verse naming both parties corroborates",
      not [e for e in _ok["errors"] if "name either" in e],
      f"{_ok['errors'][:1]}")

# The same claim cited to the whole chapter. Both names appear somewhere in
# those 32 verses, so a naive check passes it -- which is exactly why a
# container must not count. The relation goes unverified, not unnoticed.
_wide = _batch(["2Sam 2"])
check("a whole chapter does not corroborate a claim about two people",
      not any("name either" in e for e in _wide["errors"]),
      "container citations should be dropped from the evidence, not judged")
check("and the chapter citation itself is still accepted as a citation",
      not any("resolves to no verse" in e for e in _wide["errors"]),
      f"{_wide['errors'][:1]}")

# THE CASE THAT DISTINGUISHES. A relation cited only to a container looks the
# same either way -- dropping the container skips the check, keeping it passes
# the check, and both are silent. The behaviours separate only when a
# container is cited ALONGSIDE a verse that corroborates nothing:
#
#   Gen 1:1  names neither Abner nor Asahel
#   2Sam 2   names both, being the chapter they fight in
#
# Keep the container in evidence and it vouches for the bad verse, and the
# relation passes on a citation that supports nothing. Drop it and the verse
# is judged on its own, which is the point.
_masked = _batch(["Gen 1:1", "2Sam 2"])
check("a container citation cannot vouch for a verse that corroborates nothing",
      any("name either" in e for e in _masked["errors"]),
      "the chapter was allowed to stand in for Gen 1:1, which names neither man")


if FAILURES:
    print(f"FAILED ({len(FAILURES)})")
    for f in FAILURES:
        print(f"  - {f}")
    raise SystemExit(1)
print("ok - all citation regression cases pass")
