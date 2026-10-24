"""Where a book's seams are, found with the book in view.

The verse pass reads twelve verses at a time and cannot see structure: a
window does not know it began mid-argument, and it certainly does not know
that the argument runs to the end of the chapter. So the hierarchy -- which
verses form a passage, which passages form a movement -- has to come from a
second pass with a wider view, after the first is merged.

Sequencing decided 2026-08-29: the groupings come in place first; the
exception is intra-book pattern matching, which can look as the grouping is
done. Both need the same vantage, so both happen here.

## Why this can run a stage behind

It needs a finished book and nothing else, so it runs over Genesis and Job
while Exodus is still decomposing. Different stage, same pipeline, no
contention -- and the hierarchy never becomes the thing holding extraction up.

## What it is asked for

    passages    a run of verses that belong together, with a label and a reason
    movements   passages that group further, where the book has that shape
    patterns    a form repeated within THIS book -- the beatitudes, the regnal
                formula, "and God saw that it was good"
    address     units spoken TO a being rather than about one

The last is nearly free from this vantage and impossible from the other one:
Psalm 23 turns to address God at verse 4 and back at verse 6, which a
twelve-verse window cannot see as a turn.

## What it must not do

**Invent structure the text does not carry.** Some chapters are one thing and
some are a list of unrelated proverbs, and a pass that must produce a hierarchy
will produce one either way. So "this chapter has no internal seams" is an
answer, and saying so is worth as much as finding six.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from .paths import ROOT
from .decompose import _load, chapter

PROPOSALS = ROOT / "ontology" / "proposals"
NEWLINE = chr(10)

RULES = """\
You are finding the SEAMS in a chapter of the King James Bible.

Not what it says -- that is already recorded, verse by verse. You are saying
which verses belong together, and why.

WHAT A PASSAGE IS

A run of CONSECUTIVE verses that do one thing: an argument, a speech, a scene,
a list with a heading. It has a beginning a reader could point at and an end.

Give each one:
  id       book_chapter_startverse_endverse, e.g. job_4_1_11
  name     a short modern-English label a reader would recognise
  verses   [first, last] -- consecutive, no gaps, no overlaps with a sibling
  because  the evidence for the seam, quoting the words that mark it

WHAT MARKS A SEAM

  a speaker changes                "Then answered Bildad the Shuhite, and said"
  a formula opens or closes        "Thus saith the LORD", "Selah"
  the address turns                from speaking about God to speaking to him
  a connective binds or breaks     "Therefore", "But", "For" -- these BIND a
                                   verse to what came before, so a seam rarely
                                   falls just before one
  the subject changes entirely

**Quote the marker in `because`.** A seam you cannot point at is a seam you
invented.

NESTING

Where passages group further, say so with `part_of` naming the larger unit.

**NEST AS DEEP AS THE TEXT DOES, AND NO DEEPER.** Depth is not a style you
pick for the book -- it is a fact about the chapter, and it varies enormously
inside one book. A chapter of separate episodes strung together is one level
and forcing a second is invention. A tightly built narrative may go three or
four, and flattening it loses the structure that makes it a narrative rather
than a list.

2026-09-01, on Mark: chapters 14-15 could go pretty deep, and the first pass
got it wrong -- Mark 14 came out two deep and
Mark 15 entirely flat, eight passages side by side with no nesting at all.

**A REPEATED CYCLE INSIDE A PASSAGE IS NESTING, AND IT IS THE CASE MOST OFTEN
MISSED.** Two examples from that same chapter, both flattened into one
undivided passage:

  Gethsemane (14:32-42) is not one prayer. He goes away, prays, returns and
  finds them sleeping -- THREE times, and the third time is the point.

  Peter's denial (14:66-72) is not one denial. It is three, and the cock
  crows between them, which is why the prediction at 14:30 said what it did.

Where you find a cycle like that, nest the members under the passage AND
record the shape as a pattern. The nesting says where they are; the pattern
says they are the same form repeated.

NO SEAMS IS AN ANSWER

Some chapters are one unbroken thing. Others -- a chapter of separate proverbs,
a genealogy -- are thirty unrelated units and grouping them is false. Say
`"passages": []` and explain in `note`. That is a real finding and it is worth
as much as a good division.

REPEATED FORMS IN THIS BOOK

If several passages share a SHAPE -- "Blessed are the X: for they shall Y", "he
did evil in the sight of the LORD", a refrain -- record it once as a pattern
and point the instances at it. Name it for the shape, not for one instance.
Only where you can see at least two instances in what you were given.

ADDRESS

For each passage say whether it is spoken TO a being (second person: "thou",
"you, O LORD") or ABOUT one. This is grammar, not devotion: Job accusing God
is addressed; Psalm 23 speaking of the shepherd is not, until verse 4 turns.

  "addressed_to": "god" | "" and nothing else. If it is addressed to someone
  who is not a being -- a friend, a nation -- leave it empty.

OUTPUT

Strict JSON, nothing around it:

{
  "passages": [
    {"id": "...", "name": "...", "verses": [1, 11], "because": "...",
     "part_of": "", "addressed_to": ""}
  ],
  "patterns": [
    {"id": "...", "name": "...", "instances": ["job_4_1_11"], "because": "..."}
  ],
  "note": "anything that did not fit, including why a chapter has no seams"
}
"""


ABOVE_RULES = """\
You are building ONE LEVEL of a book's structure, from the level below it.

2026-09-01: this is a multi-pass process. So this same task
runs again and again -- verses became passages, passages become units, units
become movements -- and each pass reads only what the pass beneath it
produced. **You are not being asked for the whole hierarchy.** You are being
asked for one level, and another pass will run over your answer.

That has two consequences worth holding:

  Group by twos and threes where the text does, not into whatever number
  looks tidy. If this level halves the count, that is a good pass. Forcing
  forty units into four movements in one step is how real seams get lost.

  **A unit with no strong connection to its neighbours is not grouped at
  all.** Say `"to_scroll": true` and it attaches directly to the book itself,
  skipping every level between. It is finished; no later pass will see it.

  2026-09-01: do not force groupings that lack the strength of connection to
  merit grouping; connect them all to the scroll. Mark is why. Two verses in three open with *And*, and it uses
  *straightway* nearly four times as often as any other gospel -- it is one
  scene after another, and binding those scenes into invented movements would
  be the pass manufacturing structure the book does not have. **A gospel that
  is a succession of scenes under one scroll should come out as a succession
  of scenes under one scroll.**

  **SET THE BAR HIGH AND GROUP LESS.** On the first Mark climb some of the
  grouping did seem forced, so the threshold for grouping was set high. When
  in doubt, do not bind. A unit wrongly sent to the scroll is visible and
  costs a reader nothing; a unit wrongly bound into a movement asserts a
  connection the text does not make, and it is invisible afterwards because
  the group has a plausible name.

  Give every group a `strength`:

    strong   the text itself binds them -- continuous time or place, one
             scene running on, an argument carried across, a formula that
             opens and closes the run
    weak     they sit next to each other and share a subject, and that is all

  **Emit only `strong` groups.** Anything you would have called weak goes to
  the scroll instead. That is the threshold, and it is deliberately set where
  most of a loosely-strung book falls outside it.

  Mark measured: *straightway* or *immediately* appears 37 times in chapters
  1-13 and 3 times in 14-16. The first two thirds of that gospel is one thing
  after another and the last third is a single narrative building. A pass with
  a high bar should produce very few groups early and a tightly bound passion
  late. If it produces evenly sized movements throughout, it has smoothed the
  book into a shape it does not have.

  So the tree is deliberately RAGGED. Depth is not uniform and is not meant to
  be: a tightly argued stretch nests four deep while the scene beside it hangs
  off the root, and that difference is information about the text rather than
  a defect in the grouping. Do not even out the depth.

Two kinds of structure, and the second is why this pass exists:

  GROUPS       runs of CONSECUTIVE units that form one larger thing -- a
               ministry, a journey, a trial, an argument. They may cross
               chapter divisions freely and usually do.

  COLLECTIONS  a form repeated across the book, whose instances are the units
               you were given rather than verses. These are invisible from
               inside a chapter, and at every level there are more of them.

**THE CHAPTER DIVISIONS ARE NOT PART OF THE TEXT.** They were added around
1227, centuries after the book was written, and a movement that ends at a
chapter boundary should end there because the text ends there, not because the
number changed. If your movements line up neatly with chapters, look again.

Here is what that costs when it is got wrong. The formula "These are the
generations of X" occurs ELEVEN times in Genesis and is the strongest
structural marker in the book. Grouped chapter by chapter, it was proposed
three separate times as three unrelated forms, in chapters 10, 25 and 36, and
the eleven-fold pattern was never proposed at all. Nothing reported the loss.
That is the failure you exist to prevent.

WHAT YOU ARE GIVEN

Every unit at the level below, in order: its id, the verses it covers, and its
name. Not the text -- the text is already grouped and you are grouping the
groups.

RULES

  A group is CONTIGUOUS in the units you were given. No gaps, no overlaps
  with a sibling. Together they cover the book end to end -- a unit you do
  not bind to anything still appears, as a group of one.

  A collection is NOT a group. It contains nothing and partitions nothing
  -- it is a relation between passages that share a form. An inclusio, a
  refrain, a repeated formula. Its instances may be scattered across the book
  and usually are.

  Name a collection for the SHAPE, never for one instance. Two instances
  minimum, and say which passages they are.

  Quote the evidence. For a group, the words at its seam. For a collection,
  the words its instances share.

OUTPUT

Strict JSON, nothing around it:

{
  "groups": [
    {"id": "mark_L2_1", "name": "...", "members": ["mark_1_1_8", "..."],
     "strength": "strong", "because": "the words that bind them"}
  ],
  "to_scroll": ["mark_4_35_41", "..."],
  "collections": [
    {"id": "...", "name": "the shape, not one instance",
     "instances": ["mark_1_9_11", "..."], "because": "the shared words"}
  ],
  "note": "anything that did not fit"
}
"""


@dataclass
class Grouping:
    ref: str
    ok: bool
    passages: list = field(default_factory=list)
    patterns: list = field(default_factory=list)
    note: str = ""
    usage: dict = field(default_factory=dict)
    error: str = ""


def material(book: str, ch: int) -> str:
    """The whole chapter, numbered, with nothing else."""
    rows = chapter(book, ch)
    lines = [f"{book} {ch} -- {len(rows)} verses", ""]
    for ref, text in rows:
        v = ref.rsplit(":", 1)[1]
        lines.append(f"{v:>3}  {text}")
    lines += ["", f"Find the seams in {book} {ch}. Return the JSON object."]
    return "\n".join(lines)


def run(book: str, ch: int, timeout: int = 180) -> Grouping:
    from .reviewer import ask

    ref = f"{book} {ch}"
    try:
        out = ask(RULES, material(book, ch), timeout=timeout, max_tokens=32000)
    except Exception as exc:                                 # noqa: BLE001
        return Grouping(ref=ref, ok=False, error=f"{type(exc).__name__}: {exc}")
    try:
        got = json.loads((out.get("text") or "").strip())
    except json.JSONDecodeError as exc:
        return Grouping(ref=ref, ok=False, usage=out.get("usage") or {},
                        error=f"not JSON: {exc}")
    return Grouping(ref=ref, ok=True,
                    passages=got.get("passages") or [],
                    patterns=got.get("patterns") or [],
                    note=got.get("note") or "",
                    usage=out.get("usage") or {})


def check(book: str, ch: int, g: Grouping) -> list[str]:
    """Faults a person should not have to notice.

    Coverage and overlap are arithmetic, and a grouping that drops verse 17 or
    claims it twice is wrong whatever its labels say.

    **The arithmetic is per level, and the first version of this got it
    wrong.** It counted every passage flat, so Mark 2 -- 2:1-12 holding 2:1-5
    and 2:6-12, each correctly marked `part_of` -- was reported as eight
    double-claimed verses. Six of sixteen chapters were flagged on a rule the
    prompt does not ask for and explicitly contradicts: *"where passages group
    further, say so with `part_of`."* The nesting was the model doing as it
    was told.

    What is actually required:

        roots tile the chapter    every verse in exactly one top-level passage
        a child sits inside       its parent's span contains it
        siblings do not overlap   children of one parent tile no more than it
        part_of resolves          it names a passage in this same answer

    The distinction matters beyond this bug. A flat check on a nested answer
    fails *more* the better the model does, because the reward for finding
    real structure is a longer fault list -- which is the shape of a check
    that would have driven the prompt toward flat output to keep the numbers
    clean.
    """
    faults = []
    n = len(chapter(book, ch))
    by_id: dict[str, tuple[int, int]] = {}

    for p in g.passages:
        vs = p.get("verses") or []
        if len(vs) != 2 or not all(isinstance(x, int) for x in vs):
            faults.append(f"{p.get('id')}: verses is not [first, last]")
            continue
        a, b = vs
        if a > b:
            faults.append(f"{p.get('id')}: {a}-{b} runs backwards")
        if b > n:
            faults.append(f"{p.get('id')}: verse {b} is past the end ({n})")
        if not (p.get("because") or "").strip():
            faults.append(f"{p.get('id')}: no evidence for the seam")
        by_id[str(p.get("id"))] = (a, b)

    def tiles(group: list[dict], lo: int, hi: int, what: str) -> None:
        seen: dict[int, int] = {}
        for p in group:
            a, b = by_id.get(str(p.get("id")), (0, -1))
            for v in range(max(a, lo), min(b, hi) + 1):
                seen[v] = seen.get(v, 0) + 1
        missing = [v for v in range(lo, hi + 1) if v not in seen]
        twice = [v for v, c in seen.items() if c > 1]
        if missing:
            faults.append(f"{what}: verses in no passage {missing[:8]}")
        if twice:
            faults.append(f"{what}: verses claimed twice {twice[:8]}")

    kids: dict[str, list[dict]] = {}
    roots = []
    for p in g.passages:
        parent = (p.get("part_of") or "").strip()
        if not parent:
            roots.append(p)
            continue
        if parent not in by_id:
            faults.append(f"{p.get('id')}: part_of {parent!r} is not a passage here")
            roots.append(p)                       # judge it where it landed
            continue
        pa, pb = by_id[parent]
        a, b = by_id.get(str(p.get("id")), (0, -1))
        if a < pa or b > pb:
            faults.append(f"{p.get('id')}: {a}-{b} is outside its parent {pa}-{pb}")
        kids.setdefault(parent, []).append(p)

    if roots:
        tiles(roots, 1, n, "top level")
    for parent, group in kids.items():
        pa, pb = by_id[parent]
        # Children need not cover the whole parent -- a passage may have one
        # named part and an unnamed remainder -- so overlap is a fault here
        # and a gap is not.
        seen: dict[int, int] = {}
        for p in group:
            a, b = by_id.get(str(p.get("id")), (0, -1))
            for v in range(max(a, pa), min(b, pb) + 1):
                seen[v] = seen.get(v, 0) + 1
        twice = [v for v, c in seen.items() if c > 1]
        if twice:
            faults.append(f"under {parent}: verses claimed twice {twice[:8]}")
    return faults


def chapters(book: str) -> list[int]:
    """Chapter numbers this book actually has, read from the corpus."""
    import json as _json
    out = set()
    from .paths import text_path
    with open(text_path(), encoding="utf-8") as fh:
        for line in fh:
            d = _json.loads(line)
            if d.get("b") == book:
                out.add(d["c"])
    return sorted(out)


def book_batch(book: str, model: str = "claude-sonnet-5",
               effort: str = "medium") -> str:
    """Submit every chapter of a book as one batch. Returns the batch id.

    A whole book at half price, and nothing is waiting on it -- which is the
    test `bibleont.batch` states for whether work belongs there. A chapter is
    independent of every other chapter here, so there is no ordering to
    preserve and no reason to pay live rates for the first one.

    **`thinking` is explicit and `max_tokens` is generous**, both for the same
    reason. The first batch this project sent left thinking to the default,
    which spent all 10,000 tokens reasoning and returned nothing for $0.4934.
    Tokens bill as produced, so a high ceiling on a model that stops early
    costs nothing, and a low ceiling on one that does not costs everything.
    """
    from . import batch as _batch

    return _batch.submit([
        {"id": f"{book}-{ch}", "model": model,
         "system": RULES, "user": material(book, ch),
         "max_tokens": 16_000,
         "thinking": {"type": "adaptive"},
         "output_config": {"effort": effort}}
        for ch in chapters(book)])


def collect(book: str, batch_id: str) -> tuple[list[Grouping], float]:
    """Fetch a book batch, check each chapter, write the result to disk."""
    from . import batch as _batch

    rows, total = [], 0.0
    out = PROPOSALS / f"{book.lower()}-groups"
    out.mkdir(parents=True, exist_ok=True)
    for r in _batch.results(batch_id):
        total += r.cost
        ch = int(r.custom_id.rsplit("-", 1)[1])
        if r.kind != "succeeded":
            rows.append(Grouping(ref=f"{book} {ch}", ok=False, error=r.text[:200]))
            continue
        # A fenced answer is a good answer in a wrapper. `reviewer.ask` has
        # stripped these since the first DeepSeek run; this path was written
        # without it and lost Mark 5 -- 918 tokens of correct JSON, discarded
        # for three backticks. Third time today that a new path failed to
        # inherit a guard from the one beside it.
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", r.text.strip())
        try:
            got = json.loads(text)
        except json.JSONDecodeError as exc:
            rows.append(Grouping(ref=f"{book} {ch}", ok=False,
                                 usage=r.usage, error=f"not JSON: {exc}"))
            continue
        g = Grouping(ref=f"{book} {ch}", ok=True,
                     passages=got.get("passages") or [],
                     patterns=got.get("patterns") or [],
                     note=got.get("note") or "", usage=r.usage)
        rows.append(g)
        (out / f"{ch:03d}.json").write_text(
            json.dumps(got, indent=1), encoding="utf-8")
    rows.sort(key=lambda g: int(g.ref.rsplit(" ", 1)[1]))
    _batch.record(batch_id, _batch.results(batch_id), f"{book} grouping")
    _provenance(out, book, batch_id, len(rows))
    return rows, total


def _provenance(out: Path, book: str, batch_id: str, n: int,
                level: int = 1) -> None:
    """Which model and which rules produced this grouping.

    Extraction batches have recorded `rules_revision` since the instructions
    started changing under them. **Grouping recorded nothing at all** -- 0 of
    the group batches on disk carry a META -- so the level-1 passages built by
    Sonnet and the levels above built by Opus were indistinguishable after the
    fact, and from each other.

    That gap matters most under the plan named on 2026-09-02: when the graph
    is rebased there is probably a reconciliation process that uses parallel
    graphs for a while. Parallel graphs can only be reconciled if each side
    says what produced it. A structure whose author is unknown cannot be
    preferred, distrusted, or re-run against a newer revision.
    """
    from .prefix import revision as _rev
    (out / "META.json").write_text(json.dumps({
        "producer": "bibleont.group",
        "rules_revision": _rev(),
        "book": book,
        "level": level,
        "batch_id": batch_id,
        "chapters": n,
        "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2), encoding="utf-8")


def passages_of(book: str) -> list[dict]:
    """Every collected passage in the book, in text order. This is level 1."""
    out = []
    d = PROPOSALS / f"{book.lower()}-groups"
    # Only files whose whole name is the chapter number. Side-by-side runs
    # live beside them as 014-deep.json and must not be read as chapters.
    for f in sorted(x for x in d.glob("*.json") if x.stem.isdigit()):
        ch = int(f.stem)
        got = json.loads(f.read_text(encoding="utf-8"))
        for pp in got.get("passages") or []:
            vs = pp.get("verses") or []
            if len(vs) == 2 and all(isinstance(x, int) for x in vs):
                out.append({"id": str(pp.get("id")), "ch": ch, "lo": vs[0],
                            "hi": vs[1], "name": pp.get("name") or "",
                            "part_of": (pp.get("part_of") or "").strip()})
    out.sort(key=lambda x: (x["ch"], x["lo"], -x["hi"]))

    # A DANGLING PARENT MUST NOT SWALLOW ITS CHILD.
    #
    # Only the top of each chapter's own nesting rises: a chapter's internals
    # are settled, and feeding them upward makes the list three times longer
    # while telling the pass above nothing it can use. But `part_of` naming a
    # passage that was never declared is not nesting -- it is a broken
    # reference, and treating it as nesting deleted the child from the climb
    # entirely, verses and all.
    #
    # Measured before the fix: 42 passages gone. Genesis 5 lost its whole
    # genealogy, Job lost speeches in 12, 21 and 22, and Mark lost 16:9-18 --
    # which is why the disputed ending was missing from that tree and looked
    # like a modelling decision rather than a dropped pointer.
    #
    # `check_above` already resolves the same case the same way: judge it
    # where it landed. The fault is still reported by `check`; it is just no
    # longer silent about the cost.
    ids = {x["id"] for x in out}
    return [x for x in out if not x["part_of"] or x["part_of"] not in ids]


def _level_path(book: str, level: int):
    return PROPOSALS / f"{book.lower()}-groups" / f"level{level}.json"


def units_at(book: str, level: int) -> list[dict]:
    """The units this book has at `level`. Level 1 is the chapter pass.

    A level is built from the one below and never from the text, which is what
    makes the passes cheap: labels and spans, not verses. Mark is 132 labels
    against 678 verses, and it halves again at every level after that.
    """
    if level <= 1:
        return passages_of(book)
    got = json.loads(_level_path(book, level).read_text(encoding="utf-8"))
    below = {u["id"]: u for u in units_at(book, level - 1)}
    # A unit sent to the scroll is FINISHED. It does not rise to this level and
    # no later pass sees it -- that is what makes the tree ragged on purpose
    # rather than by omission. It is still in the book; it hangs off the root.
    out = []
    for g in got.get("groups") or []:
        members = [below[m] for m in (g.get("members") or []) if m in below]
        if not members:
            continue
        # The end chapter comes from where the last member ENDS, not where it
        # begins. Taking members[-1]["ch"] worked at level 2, where every unit
        # sits in one chapter, and silently truncated every span above it:
        # Mark's passion showed as 15:1-15:8 for 15:1-16:8, and the temple
        # sequence as 11:12-11:12 for 11:12-12:12. A span is what a passage
        # cites, so this was one merge away from wrong citations in the graph.
        out.append({"id": str(g.get("id")), "ch": members[0]["ch"],
                    "lo": members[0]["lo"], "hi": members[-1]["hi"],
                    "hi_ch": members[-1].get("hi_ch", members[-1]["ch"]),
                    "name": g.get("name") or "",
                    "part_of": "", "members": [m["id"] for m in members]})
    out.sort(key=lambda x: (x["ch"], x["lo"]))
    return out


def _node_index(book: str):
    """Which graph nodes sit in which verse of this book, and how rare each is.

    2026-09-01: the pass was said to be reading labels, but it was not
    comparing all the node labels under the node, and that was the
    weakness -- a pass comparing model-authored summaries is comparing its own
    prose, not the text. The graph already knows what each span contains.

    **Rarity is the whole signal.** `joseph` appears in nearly every verse of
    Genesis 39 and tells you nothing about which verses belong together;
    `joseph_leaves_his_garment` tells you almost everything. That is
    the rule to weight shared evidence by how rare it is, and
    the bond metric failed the first time for want of it.
    """
    import collections
    import math
    at = collections.defaultdict(set)
    freq = collections.Counter()
    pat = re.compile(re.escape(book) + r" (\d+):(\d+)$")
    for path in (ROOT / "ontology" / "relations").glob("*.jsonl"):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                for ref in (r.get("refs") or []):
                    m = pat.match(str(ref))
                    if m:
                        key = (int(m.group(1)), int(m.group(2)))
                        for n in (r.get("src"), r.get("dst")):
                            if n:
                                at[key].add(n)
                                freq[n] += 1
                        break
    weight = {n: 1.0 / math.log(2 + c) for n, c in freq.items()}
    return at, weight


def scroll_units(book: str) -> list[tuple[int, str]]:
    """Units attached straight to the book, with the level they left at.

    These are not failures. A gospel that is a succession of scenes should
    come out as a succession of scenes, and a unit here is one the passes
    declined to bind rather than one they missed -- the difference being that
    declining is recorded and missing is silent.
    """
    out, level = [], 2
    while True:
        path = _level_path(book, level)
        if not path.exists():
            break
        got = json.loads(path.read_text(encoding="utf-8"))
        out += [(level - 1, str(u)) for u in (got.get("to_scroll") or [])]
        level += 1
    return out


def above_material(book: str, level: int, per_unit: int = 6) -> str:
    """The unit list at `level`, each with the nodes that distinguish it.

    Labels alone let the pass compare its own summaries. The nodes make the
    comparison run on what the text actually says, and they are already
    extracted -- this costs nothing but prompt space.

    Where a book is thinly extracted the node column is simply sparse, and
    that is honest: Mark carries 0.66 claims a verse against Genesis's 3.08,
    so Mark's units mostly arrive bare and the pass falls back to labels.
    """
    us = units_at(book, level)
    at, weight = _node_index(book)
    lines = [f"{book} -- {len(us)} units at level {level}, in order.",
             "Each line: id, verses, name, then the nodes that occur in it,",
             "rarest first. The nodes are what the text says; the name is a",
             "label somebody wrote. Where they disagree, trust the nodes.", ""]
    for u in us:
        a = f"{u['ch']}:{u['lo']}"
        hi_ch = u.get("hi_ch", u["ch"])
        b = f"{hi_ch}:{u['hi']}" if (hi_ch != u["ch"] or u["hi"] != u["lo"]) else ""
        span = f"{a}-{b}" if b else a
        got = set()
        for ch in range(u["ch"], hi_ch + 1):
            lo = u["lo"] if ch == u["ch"] else 1
            hi = u["hi"] if ch == hi_ch else 200
            for v in range(lo, hi + 1):
                got |= at.get((ch, v), set())
        best = sorted(got, key=lambda n: -weight.get(n, 0))[:per_unit]
        nodes = ("  ::  " + ", ".join(best)) if best else ""
        lines.append(f"  {u['id']:<28} {span:<14} {u['name']}{nodes}")
    lines += ["", f"Find level {level + 1} of {book}. Return the JSON object."]
    return NEWLINE.join(lines)


def above_batch(books_levels: list[tuple[str, int]],
                model: str = "claude-opus-5") -> str:
    """One batch covering several books, or several levels, or both."""
    from . import batch as _batch
    return _batch.submit([
        {"id": f"{b}-L{lv}", "model": model, "system": ABOVE_RULES,
         "user": above_material(b, lv), "max_tokens": 48_000,
         "thinking": "auto", "effort": "high"}
        for b, lv in books_levels])


def check_above(book: str, level: int, got: dict) -> list[str]:
    """Groups must tile the level below, once each, in order."""
    below = [u["id"] for u in units_at(book, level)]
    faults, seen = [], {}
    for g in got.get("groups") or []:
        if (g.get("strength") or "strong").lower() != "strong":
            faults.append(f"{g.get('id')}: strength {g.get('strength')!r} -- "
                          "weak groups belong on the scroll")
        members = g.get("members") or []
        idx = [below.index(m) for m in members if m in below]
        for m in members:
            seen[m] = seen.get(m, 0) + 1
            if m not in below:
                faults.append(f"{g.get('id')}: {m} is not a level-{level} unit")
        if idx and idx != list(range(min(idx), min(idx) + len(idx))):
            faults.append(f"{g.get('id')}: members are not consecutive")
    scrolled = set(got.get("to_scroll") or [])
    for s in scrolled:
        if s not in below:
            faults.append(f"to_scroll names {s}, which is not a level-{level} unit")
    missing = [m for m in below if m not in seen and m not in scrolled]
    twice = [m for m, n in seen.items() if n > 1]
    if missing:
        faults.append(f"{len(missing)} units neither grouped nor sent to the "
                      f"scroll: {missing[:5]}")
    if twice:
        faults.append(f"units in more than one group: {twice[:5]}")
    for c in got.get("collections") or []:
        if len(c.get("instances") or []) < 2:
            faults.append(f"collection {c.get('id')} has fewer than two instances")
    return faults


def collect_above(batch_id: str) -> dict:
    """Fetch one level's results and write each book's level file."""
    from . import batch as _batch
    out = {}
    for r in _batch.results(batch_id):
        book, lv = r.custom_id.rsplit("-L", 1)
        level = int(lv) + 1                      # the level it PRODUCED
        if r.kind != "succeeded":
            out[r.custom_id] = {"error": r.text[:200], "cost": r.cost}
            continue
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", r.text.strip())
        try:
            got = json.loads(text)
        except json.JSONDecodeError as exc:
            out[r.custom_id] = {"error": f"not JSON: {exc}", "cost": r.cost}
            continue
        _level_path(book, level).write_text(json.dumps(got, indent=1),
                                            encoding="utf-8")
        _provenance(_level_path(book, level).parent, book, batch_id, 1,
                    level=level)
        out[r.custom_id] = {
            "groups": len(got.get("groups") or []),
            "collections": len(got.get("collections") or []),
            "faults": check_above(book, level - 1, got),
            "cost": r.cost}
    _batch.record(batch_id, _batch.results(batch_id), "grouping level")
    return out


def climb(book: str) -> list[int]:
    """How many units this book has at each level built so far.

    2026-09-01: the pass just has to read all the top-level nodes until the
    scroll is reached. So the loop ends at one node -- the scroll -- and the
    shape of the climb is the thing to watch. A level that does not reduce the
    count has found nothing and should not be kept; a level that reduces it
    tenfold has probably flattened real seams.
    """
    counts, level = [], 1
    while True:
        try:
            n = len(units_at(book, level))
        except FileNotFoundError:
            break
        if not n:
            break
        counts.append(n)
        if n == 1:
            break
        level += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    dry = "--dry" in argv
    rest = [a for a in argv if not a.startswith("--")]

    # `group <Book> --book` submits the whole book batched; `--collect <id>`
    # fetches it. Two commands rather than one blocking call, because a batch
    # outlives the shell that sent it and the id on disk is what makes that
    # true.
    if "--book" in argv and rest:
        bid = book_batch(rest[0], model="claude-opus-5" if "--opus" in argv
                         else "claude-sonnet-5")
        path = PROPOSALS / f"{rest[0].lower()}-groups.batch"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(bid, encoding="utf-8")
        print(f"{rest[0]}: {len(chapters(rest[0]))} chapters -> {bid}")
        print(f"  python -m bibleont.group {rest[0]} --collect")
        return 0

    if "--collect" in argv and rest:
        book = rest[0]
        bid = (PROPOSALS / f"{book.lower()}-groups.batch").read_text().strip()
        rows, total = collect(book, bid)
        bad = 0
        for g in rows:
            ch = int(g.ref.rsplit(" ", 1)[1])
            if not g.ok:
                print(f"  {g.ref:10} FAIL {g.error[:70]}")
                bad += 1
                continue
            faults = check(book, ch, g)
            bad += bool(faults)
            flag = "  FAULT " + "; ".join(faults)[:70] if faults else ""
            print(f"  {g.ref:10} {len(g.passages):>3} passages "
                  f"{len(g.patterns):>2} patterns{flag}")
        print(f"\n{len(rows)} chapters, {bad} with faults, ${total:.4f}")
        return 1 if bad else 0

    if len(rest) < 2:
        print("usage: python -m bibleont.group <Book> <chapter> [--dry]")
        print("       python -m bibleont.group <Book> --book [--opus]")
        print("       python -m bibleont.group <Book> --collect")
        return 2
    book, ch = rest[0], int(rest[1])

    if dry:
        print(RULES[:400] + "\n...\n")
        print(material(book, ch)[:900])
        return 0

    g = run(book, ch)
    if not g.ok:
        print(f"FAIL {g.ref}: {g.error}")
        return 1

    print(f"{g.ref}: {len(g.passages)} passage(s), "
          f"{len(g.patterns)} pattern(s)")
    for p in g.passages:
        v = p.get("verses") or ["?", "?"]
        addr = "  ->addressed" if p.get("addressed_to") else ""
        print(f"  {str(v[0]):>3}-{str(v[1]):<3} {p.get('name','')[:52]:54}{addr}")
        print(f"        {(p.get('because') or '')[:96]}")
    for p in g.patterns:
        print(f"  pattern  {p.get('name','')[:46]}  "
              f"({len(p.get('instances') or [])} instances)")
    if g.note:
        print(f"  note: {g.note[:200]}")

    faults = check(book, ch, g)
    for f in faults:
        print(f"  FAULT {f}")
    u = g.usage
    if u:
        cost = (u.get("prompt_cache_hit_tokens", 0) * 0.007
                + u.get("prompt_cache_miss_tokens", 0) * 0.22
                + u.get("completion_tokens", 0) * 0.66) / 1e6
        print(f"  ${cost:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
