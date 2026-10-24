"""What the worker is told, and what it is allowed to say.

The prompt and the relation vocabulary are the two things that decide the
SHAPE of everything extracted, and until now neither had a test. That is the
wrong way round: a stylesheet regression is visible and a vocabulary
regression is not. Genesis produced 2,064 relations wiring a verse straight to
an idea and every one of them validated.

Four findings on 2026-08-30 all reduced to one sentence -- **the worker emits
what the vocabulary allows** -- so the vocabulary is the thing to pin:

    tag clouds        the only relation offered was `speaks_of`
    speaker index     the only relation offered was `told`
    no census         there was no relation for causation at all, so
                      "he moved David to number Israel" had nowhere to go
    Job 42:7 absent   `assessed_as` would not take a speech as its subject,
                      so the verse where the book judges its own argument
                      could not be written down

Each was invisible until someone read output and counted. These cases make
the next one loud instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    if not ok:
        FAILURES.append(f"{label}: {detail}" if detail else label)


# ---------------------------------------------------------------------------
# the vocabulary must be able to say the things the corpus says
# ---------------------------------------------------------------------------
from bibleont.schema import load_vocabulary                     # noqa: E402

_V = load_vocabulary().types

# Each of these was added because a specific verse could not be recorded.
# The verse is named so that a future reader can judge whether the type is
# still earning its place rather than guessing.
REQUIRED = {
    "asserted_by": "1Chr 21:1 vs 2Sam 24:1 -- two scrolls, two agents, and "
                   "the graph must assert neither",
    "grounds": "Gen 18:19 grounds 18:17, the only place in the Torah where "
               "God states a reason for electing Abraham",
    "conditional_on": "Gen 18:26, 'if I find fifty... then I will spare' -- a "
                      "bargain with no terms is not a bargain",
    "recounts": "2Sam 24 and 1Chr 21 recount one census; needed at "
                "Samuel/Chronicles, long before the synoptics",
    "incited": "H5496 in both 2Sam 24:1 and 1Chr 21:1, which the KJV renders "
               "'moved' and 'provoked'",
}
for name, why in REQUIRED.items():
    check(f"the vocabulary can express {name!r}", name in _V, why)

# `assessed_as` must accept a SPEECH as its subject, or Job 42:7 -- the book
# adjudicating its own argument -- cannot be recorded.
_a = _V.get("assessed_as")
check("an assessment can be made of a speech",
      bool(_a) and "text" in _a.src_types,
      "Job 42:7, 'ye have not spoken of me the thing that is right', is God "
      "assessing what the friends SAID")

# God is the most active agent in Genesis, and these were person-only until
# the day Genesis was merged.
for name, verse in (("cursed", "Gen 3:17"), ("healed", "Gen 20:17"),
                    ("killed", "Gen 38:7"), ("party_to", "Gen 9:9")):
    t = _V.get(name)
    check(f"a being can be the source of {name!r}",
          bool(t) and "being" in t.src_types, f"{verse}")


# ---------------------------------------------------------------------------
# the prompt must still teach the rule that matters most
# ---------------------------------------------------------------------------
from bibleont.prefix import CONCEPT_RULES, build                # noqa: E402

check("the prompt states that a verse is not a participant",
      "A VERSE IS NOT A PARTICIPANT" in CONCEPT_RULES,
      "the rule that 2,064 Genesis relations broke")

# Checking the HEADING is not checking the rule. A first version of this case
# tested only that the title was present, and passed happily against a prompt
# whose section had been renamed out from under it -- so it would also have
# passed against a section emptied of everything but its title. These are the
# sentences that do the teaching.
for _phrase, _why in (
    ("could someone find this by searching",
     "the test a worker applies before writing an edge"),
    ("empty answer is correct and costs nothing",
     "without this the worker invents an edge rather than emit none"),
    # `described_as` since 2026-10-02: "X is Y" left assessed_as ("did")
    ("job -described_as-> perfect",
     "the correct form, beside the wrong one"),
):
    check(f"the rule keeps its substance: {_phrase[:38]}...",
          _phrase in CONCEPT_RULES, _why)

# The format that measurably transmits: rule, worked example, why, and the
# anti-pattern beside it. Prose alone did not move the misquotation classes;
# worked examples took one from 10 occurrences to 0.
check("...with a worked example, not only a statement",
      "WRONG" in CONCEPT_RULES and "RIGHT" in CONCEPT_RULES
      and "job_1_1 -speaks_of-> man" in CONCEPT_RULES,
      "the rule needs the anti-pattern beside the correct form")

# Taught in the per-verse prompt. `recounts` is deliberately absent: a worker
# seeing one verse cannot know that 2Sam 24 and 1Chr 21 tell one event, so it
# belongs to the alignment pass and would only be noise here.
TAUGHT = set(REQUIRED) - {"recounts"}
for name in TAUGHT:
    check(f"the prompt shows how to use {name!r}", name in CONCEPT_RULES)

# ---------------------------------------------------------------------------
# and the vocabulary the worker is handed must be reachable from the rules
# ---------------------------------------------------------------------------
_p = build("Gen")
_head = getattr(_p, "text", None) or str(_p)

for name in REQUIRED:
    check(f"{name!r} reaches the worker's relation list", name in _head,
          "the rules tell it to use a word its vocabulary does not contain")

# THE ONE THAT WOULD OTHERWISE COME BACK SILENTLY.
#
# The block is headed "reuse these ids verbatim". 522 of the entries handed to
# the Genesis worker were sentences used as ids or whole verses used as names
# -- including the exact string the naming rule cites as what not to do. 5,856
# tokens of instruction against 100,000 of demonstration is not a contest the
# instruction wins, and it is why rules with worked examples still failed.
import re                                                       # noqa: E402

from bibleont.lint import ID_WORDS, NAME_CHARS, _QUESTION       # noqa: E402
from bibleont.schema import load_entities                       # noqa: E402

_ents = load_entities()
_bad = {e.id for e in _ents.values()
        if e.id.count("_") >= ID_WORDS - 1
        or _QUESTION.match(e.id)
        or len(e.name or "") > NAME_CHARS}

_LOCATOR_ID = re.compile(r"^[1-3]?[a-z]+_\d+_\d+$")

for _book in ("Gen", "Job"):
    _h = getattr(build(_book), "text", None) or ""
    _i = _h.find("EXISTING NODES")
    _entries = set(re.findall(r"^\s*([a-z0-9_]+)\s", _h[_i:], re.M)) if _i >= 0 else set()
    _hits = _bad & _entries
    check(f"{_book}: the worker is shown no node that breaks its own rules",
          not _hits, f"{len(_hits)} counter-examples, e.g. {sorted(_hits)[:2]}")

    # A bare verse locator is derivable from its reference, so listing it
    # spends tokens on something the worker can construct -- and worse,
    # re-running a book hands back its own previous output as ids to reuse.
    # 808 of the Genesis locators carried the tag-cloud shape the re-run
    # exists to replace, and the naming filter cannot catch them because
    # their names are fine and only their USE was wrong.
    _loc = {e for e in _entries if _LOCATOR_ID.match(e)}
    check(f"{_book}: no derivable verse locator is listed as vocabulary",
          not _loc,
          f"{len(_loc)} locators, e.g. {sorted(_loc)[:3]} -- a re-run would be "
          "anchored to the output it is meant to replace")

# Coined ids cannot be guessed and must survive. Dropping them would cause
# real duplicates, which is the failure the vocabulary block exists to prevent.
_hj = getattr(build("Job"), "text", None) or ""
for _coined in ("job_18_bildad_speech", "the_fear_of_the_lord", "wisdom"):
    check(f"the coined id {_coined!r} is still offered", _coined in _hj,
          "unguessable ids must be listed or the worker mints a duplicate")


# Events. The `event` entity type existed from the beginning and was used
# ZERO times in 8,475 records, because the prompt mentioned the word only
# inside "the same words are not the same event" and never told the worker it
# could make one. The purest instance of the project's most reliable finding:
# the worker emits what it is told is available, and a capability nobody names
# is a capability nobody has.
check("the prompt says an event can be a node",
      "AN EVENT IS A NODE" in CONCEPT_RULES,
      "the type existed unused for the whole project")
check("...with the test for when to make one",
      "the event is referred to later" in CONCEPT_RULES
      and "cannot be an edge" in CONCEPT_RULES,
      "one participant, or later text points at it")
check("...and the warning against making one for everything",
      "Do NOT make one for every action" in CONCEPT_RULES,
      "without this every action becomes a node")

from bibleont.schema import ENTITY_TYPES                        # noqa: E402
check("the schema still allows an event", "event" in ENTITY_TYPES)


# The principles reach the worker, and reach it from the file.
#
# `docs/PRINCIPLES.md` is the source and the prompt head is rendered from it,
# so the failure this guards against is not a wrong rule -- it is the parse
# quietly returning nothing. A head of zero principles is a valid string, the
# prompt still builds, every run still costs the same, and the only symptom is
# that the first thing the worker reads is a heading with nothing under it.
from bibleont import principles                                 # noqa: E402

_marked = principles.worker()
check("some principles are marked for the worker", len(_marked) >= 8,
      f"{len(_marked)} marked -- did the `Carried by the worker.` line move?")

# A FLOOR IS NOT A PIN, and the floor let one through.
#
# Editing the body of Principle 9 dropped its `Carried by the worker.` line,
# and the worker prompt lost "the verse is an index, not a unit" -- the rule
# the prompt itself measures as the most-broken one, 2,064 of 6,644 relations
# in a single Genesis run. The count went 13 to 12 and every check above still
# passed, because eight is fewer than twelve.
#
# So the rules whose absence has a measured cost are named. This does not stop
# the list changing; it stops it changing by accident. Removing one now means
# editing this line, which is a decision somebody makes rather than a line
# somebody loses while rewriting the paragraph above it.
_MUST_CARRY = [
    "The verse is an index, not a unit",
    "Record what the text says, not what it means",
    "A quotation is a copy, and it fails at its boundary",
    "Always split",
    "Where the text has no narrator, someone is still speaking",
]
_titles = {p.title for p in _marked}
for _t in _MUST_CARRY:
    check(f"the worker still carries {_t!r}", _t in _titles,
          "its `Carried by the worker.` line is gone -- restore it, or remove "
          "it from _MUST_CARRY on purpose")
check("not all of them are", len(_marked) < len(principles.load()),
      "the marking is meant to be a subset; a prompt carrying rules a worker "
      "cannot apply spends attention on nothing")

_head = principles.head()
_flat_head = " ".join(_head.split())      # the head wraps; titles cross lines
for _p in _marked:
    check(f"the prompt carries {_p.title!r}", " ".join(_p.title.split()) in _flat_head)
    # An empty statement is fine -- some titles say the whole rule -- but a
    # statement that is page furniture is not. "---" got in this way once,
    # because the scan for the first ordinary paragraph ran off the end of a
    # principle whose only paragraphs were its evidence and its falsifier.
    check(f"{_p.title!r} has a real statement or none",
          len(_p.statement) > 20 or not _p.statement,
          f"statement is {_p.statement!r}")

_gen = getattr(build("Gen"), "text", None) or ""
check("the principles open the prompt, before the rules",
      _gen.index("THE PRINCIPLES THIS GRAPH IS BUILT ON") < _gen.index(
          "You are decomposing one verse"),
      "first is the position that costs nothing and buys the most")


# The site publishes files, not directories.
#
# `docs/` was served whole from a directory allowlist, which published every
# file later added to it: the journal, the backlog, an unfinished personal
# statement, and the queue of notes readers left in confidence. A directory
# allowlist is a decision made once about files that do not exist yet.
#
# This checks the first app (app/), which the public repository does not carry
# (2026-10-21, plan 8.3a); a copy without it skips this part.
if (Path(__file__).resolve().parents[1] / "app" / "server.py").exists():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    import server                                               # noqa: E402

    check("the server has no public directory root", not hasattr(server, "PUBLIC_ROOTS"),
          "a root publishes whatever is put in it later")
    _public = set(server.PUBLIC_FILES)
    for _linked in ("/docs/ROADMAP.md", "/docs/TESTING.md", "/NOTICE.md",
                    "/LICENSE.md", "/ontology/EXTRACTION_GUIDE.md"):
        check(f"{_linked} is still published", _linked in _public,
              "the About view links to it")
    for _private in ("/docs/PRINCIPLES.md", "/docs/JOURNAL.md",
                     "/docs/NOTES-BACKLOG.md", "/docs/FOUNDER-NOTES.md",
                     "/docs/DISCIPLINE.md", "/docs/OPERATIONS.md"):
        check(f"{_private} is not published", _private not in _public,
              "nothing links to it, and three of these are private for different "
              "reasons -- reader notes, an unfinished statement, and the method")
else:
    print("skipped the first app's published-files check: app/ is not in this copy")


if FAILURES:
    print(f"FAILED ({len(FAILURES)})")
    for f in FAILURES:
        print(f"  - {f}")
    raise SystemExit(1)
print("ok - extraction contract holds")
