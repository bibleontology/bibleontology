"""Find what a finished book got wrong, and re-extract only that.

A pass over a merged book: the supervisor reads sampled chapters, says what is
defective and how the worker should be corrected, and this re-runs the affected
windows with that correction in the prompt. Nothing else is touched.

## Why repair rather than re-run everything

The rule, and it is the one that decides what belongs here:

    ADDITIVE   -> overlay.  Events, frames, groupings, patterns. Cheap later
                            and better later, because they need a wider view
                            than a twelve-verse window has.
    CORRECTIVE -> re-run.   A level-skip is wrong data, not missing data, and
                            fixing it means reading the source again.

**This module is the corrective half.** It exists because a full re-run of
Genesis costs $2.60 and four hours, while the chapters actually at fault are
usually a handful. Repair is the difference between fixing what is broken and
paying to redo what is not.

## The supervisor decides what is broken, not the linter

The linter already catches everything mechanical, for nothing, on every window.
What survives the linter and is still wrong is exactly what needs judgement --
and the day this was written the supervisor read a chapter I had personally
approved an hour earlier and found the thing I had missed: Job 3's central
claims about death and rest were absent while I was measuring that its SHAPE
had improved.

So the selection is the supervisor's. This module is scheduling and arithmetic.

## The criteria are provisional and the supervisor is told so

The rubric was written by one person in one afternoon from a handful of
failures. It will be wrong somewhere. A supervisor that applies a bad rule
faithfully produces confident nonsense and a repair pass that entrenches it,
which is worse than no pass at all -- so the rubric asks it to say when a rule
looks wrong, and that answer is reported rather than acted on.

The repair mode includes the supervisor understanding that it will
potentially need to be tweaked based on the results.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field

from .paths import ROOT

# Appended to the rubric for a repair pass. The supervisor is judging work
# against criteria that are themselves under test, and needs to know it.
PROVISIONAL = """

## These criteria are provisional, and saying so is part of the job

This rubric was written by one person in one afternoon, from a handful of
observed failures. It is not settled and it will be wrong somewhere.

If a rule here looks wrong for the passage in front of you -- if what it calls
a fault is actually correct for this kind of text, or if it misses something
that matters more -- **say so in `rubric`** rather than applying it faithfully.
A supervisor that enforces a bad rule produces confident nonsense, and a repair
pass built on it entrenches the error across a whole book.

Two cases seen already, both real:

  A lament has few events and that is not a defect. Job 3 is a man arguing
  that death is preferable to life; measuring it against narrative expectations
  reports a healthy chapter or a broken one depending on which rule you reach
  for, and neither answer is about the chapter.

  A genealogy is *supposed* to be a list of kinship relations. Flagging Genesis
  5 for "no propositions between durable entities" would be the rule failing,
  not the extraction.

Add one field to your JSON:

  "rubric": ""   empty when the criteria fit. Otherwise: which rule, and why it
                 does not fit this passage. Reported to a person, never acted
                 on automatically.
"""


@dataclass
class Finding:
    ref: str
    verdict: str
    faults: list = field(default_factory=list)
    coach: str = ""
    escalate: str = ""
    rubric: str = ""
    spent: float = 0.0


def chapters_of(book: str) -> list[int]:
    from .farm import chapters_of as _c
    return _c(book)


def sample_chapters(book: str, n: int) -> list[int]:
    """Which chapters to look at.

    Spread evenly rather than taken from the front, because a worker that
    starts well and drifts is the failure this is most likely to meet -- and
    the front is also what everyone eyeballs by hand anyway.
    """
    chs = chapters_of(book)
    if n >= len(chs):
        return chs
    step = len(chs) / n
    return [chs[int(i * step)] for i in range(n)]


def review_chapter(book: str, ch: int, batch: str | None = None) -> Finding:
    import os

    from .reviewer import ask
    from .supervisor import RUBRIC, material, price

    os.environ["BIBLEONT_PROVIDER"] = "anthropic"
    verdict, raw = ask(RUBRIC + PROVISIONAL, material(book, ch, batch=batch),
                       timeout=240, max_tokens=4000)
    return Finding(
        ref=f"{book} {ch}",
        verdict=str(verdict.get("verdict") or "?"),
        faults=verdict.get("faults") or [],
        coach=str(verdict.get("coach") or ""),
        escalate=str(verdict.get("escalate") or ""),
        rubric=str(verdict.get("rubric") or ""),
        spent=price(raw.get("usage") or {}),
    )


def windows_for(book: str, chapters: list[int]) -> list[str]:
    """The farm's window keys for these chapters, so state can be cleared."""
    from .decompose import windows

    keys = []
    for c in chapters:
        for w in windows(book, c):
            refs = w if isinstance(w, list) else [w]
            first, last = str(refs[0]), str(refs[-1])
            keys.append(f"{first}-{last.rsplit(':', 1)[1]}"
                        if first != last else first)
    return keys


def plan(book: str, sample: int = 5, batch: str | None = None) -> dict:
    """Review a sample, and say what would be re-run and what it would cost."""
    from .supervisor import position

    pos = position()
    findings = []
    for ch in sample_chapters(book, sample):
        findings.append(review_chapter(book, ch, batch))

    bad = [f for f in findings if f.verdict in ("concern", "stop")]
    coaching = "\n\n".join(f.coach for f in findings if f.coach.strip())
    rubric_notes = [(f.ref, f.rubric) for f in findings if f.rubric.strip()]
    escalations = [(f.ref, f.escalate) for f in findings if f.escalate.strip()]

    chapters = [int(f.ref.rsplit(" ", 1)[1]) for f in bad]
    keys = windows_for(book, chapters) if chapters else []

    return {
        "book": book,
        "findings": findings,
        "reviewed": len(findings),
        "concerning": len(bad),
        "chapters": chapters,
        "windows": keys,
        "coaching": coaching,
        "rubric_notes": rubric_notes,
        "escalations": escalations,
        "review_cost": sum(f.spent for f in findings),
        "rerun_cost": len(keys) * 0.018,
        "budget_left": pos["left"],
    }


def apply(book: str, keys: list[str], coaching: str) -> None:
    """Clear the named windows and stage the coaching for the next farm run.

    The coaching rides the same append-only rail as the created-node delta, so
    it reaches the next window without breaking the cached prefix. It is
    REPLACED rather than accumulated: a growing pile of corrections
    contradicts itself, which is why derived output is not where corrections
    live.
    """
    import shutil
    from pathlib import Path

    p = ROOT / "ontology" / "proposals" / ".farm" / f"{book.lower()}.json"
    if not p.exists():
        raise SystemExit(f"no farm state for {book}")
    shutil.copy(p, p.with_suffix(".json.prerepair"))
    d = json.loads(p.read_text(encoding="utf-8"))
    before = len(d.get("done") or {})
    d["done"] = {k: v for k, v in (d.get("done") or {}).items() if k not in keys}
    d["coaching"] = ("\n\nA REVIEW OF EARLIER WORK ON THIS BOOK FOUND THIS:\n"
                     + coaching + "\n\nApply it from here on.\n") if coaching else ""
    p.write_text(json.dumps(d, indent=2), encoding="utf-8")
    print(f"  cleared {before - len(d['done'])} window(s); coaching staged")
    print(f"  backup at {p.with_suffix('.json.prerepair').name}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m bibleont.repair <Book> [--sample=5] "
              "[--batch=NAME] [--apply]")
        print("       reviews a sample, reports what it would re-run;")
        print("       --apply clears those windows and stages the coaching.")
        return 2

    book = argv[0]
    sample = 5
    batch = None
    for a in argv:
        if a.startswith("--sample="):
            sample = int(a.split("=", 1)[1])
        if a.startswith("--batch="):
            batch = a.split("=", 1)[1]

    print(f"  reviewing {sample} chapter(s) of {book}"
          + (f" from {batch}" if batch else " from the merged graph"))
    p = plan(book, sample, batch)

    print()
    for f in p["findings"]:
        mark = {"sound": "ok  ", "concern": "CONCERN", "stop": "STOP"}.get(
            f.verdict, "?   ")
        print(f"  {mark:8} {f.ref:12} {len(f.faults)} fault(s)  ${f.spent:.4f}")
        for x in f.faults[:2]:
            print(f"           [{x.get('kind')}] {str(x.get('example'))[:56]}")

    print()
    print(f"  reviewed        {p['reviewed']} chapters, ${p['review_cost']:.3f}")
    print(f"  concerning      {p['concerning']}")
    print(f"  would re-run    {len(p['windows'])} window(s), "
          f"~${p['rerun_cost']:.2f}")
    print(f"  supervisor left ${p['budget_left']:.2f}")

    if p["rubric_notes"]:
        print()
        print("  THE SUPERVISOR QUESTIONS THE CRITERIA:")
        for ref, note in p["rubric_notes"]:
            print(f"    {ref}: {note[:200]}")

    if p["escalations"]:
        print()
        print("  ESCALATED -- for a person, not the supervisor:")
        for ref, note in p["escalations"]:
            print(f"    {ref}: {note[:200]}")

    if p["coaching"]:
        print()
        print("  coaching that would be staged:")
        print(f"    {p['coaching'][:400]}")

    if "--apply" not in argv:
        print()
        print("  dry run. Add --apply to clear those windows and stage the")
        print("  coaching, then re-run the farm for this book.")
        return 0

    if not p["windows"]:
        print("\n  nothing to repair.")
        return 0
    print()
    apply(book, p["windows"], p["coaching"])
    print(f"  next: python -m bibleont.farm {book} --budget=<above lifetime spend>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
