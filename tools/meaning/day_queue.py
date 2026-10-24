"""ONE COMMAND FOR A DAY'S JUDGING, 2026-10-19 (prepared so that one job can
be kicked off to use the last 16% of the weekly tokens optimally).

Runs the steps below in order, each as its own process, each with its own
token cap (written to its run's BUDGET), most useful first, so a day cut short
loses the least. Calibrated the night before: about 3-4M tokens to 1% of the
weekly limit (the all-verb run moved it 81% -> 82% on ~4M). The caps total
about 45M, but the work is smaller than its caps: about 30M expected (the
pilots: ~4,800 tokens a sense flag; concept pools mostly judged already).

A deadline stops everything before the weekly reset (2026-10-19 22:00 UTC):
at DEADLINE the running step gets a STOP file and the queue ends, so nothing
waits on a usage limit into the next week's allowance.

    python tools/meaning/day_queue.py          -> out/meaning/day-queue.log
    (to stop early: create out/meaning/day-queue.STOP)

Each step's run directory is resumable: re-running the queue skips finished
work.
"""
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "out" / "meaning" / "day-queue.log"
STOP = ROOT / "out" / "meaning" / "day-queue.STOP"
DEADLINE = dt.datetime(2026, 10, 19, 21, 30, tzinfo=dt.timezone.utc)
PY = sys.executable
M = "tools/meaning/"
CA = ROOT / "out" / "meaning" / "concept-audit"
CARD = ROOT / "out" / "meaning" / "card-audit"
LIFT = ROOT / "out" / "meaning" / "lift"
CARD_ENV = {"CA_TYPES": "object,image,title,observance,creature,covenant", "CA_DIR": "card-audit"}

# (label, run dir or None, cap in tokens, command, extra env)
STEPS = [
    # 1. the audit's 1,058 "other sense" flags, re-judged on 20 verses each, two judges
    ("senses, Sonnet", CA / "senses-1", 6_500_000, [M + "concept_senses.py", "run", "senses-1", "sonnet"], {}),
    ("senses, Haiku", CA / "senses-2", 6_500_000, [M + "concept_senses.py", "run", "senses-2", "haiku"], {}),
    ("senses, merge", None, 0, [M + "concept_senses.py", "merge", "senses-1", "senses-2"], {}),
    # 2. plan 2.17: the verb's sense and a family for each relation both judges kept
    #    overnight, evidence for the predication decision 1.2.0 waits on
    ("verb families", LIFT / "families-1", 4_000_000, [M + "lift_relations.py", "senses", "families-1", "sonnet"], {}),
    # 3. the same audit over the 786 object, image, title, observance, creature, covenant cards
    ("cards phase 1", CARD / "card-1", 3_000_000, [M + "concept_audit.py", "run", "card-1", "sonnet"], CARD_ENV),
    ("cards verses, pass 1", CARD / "verses-1", 8_000_000, [M + "concept_verses.py", "run", "verses-1", "card-1"],
     {**CARD_ENV, "CV_PER_CARD": "250"}),
    ("cards verses, pass 2", CARD / "verses-2", 8_000_000, [M + "concept_verses.py", "run", "verses-2", "card-1"],
     {**CARD_ENV, "CV_PER_CARD": "250"}),
    ("cards, merge", None, 0, [M + "concept_verses.py", "merge", "verses-1", "card-1", "verses-2"], CARD_ENV),
    # 4. the concept cards' large pools: 150 MORE verses a card, not the ones judged last night
    ("concepts, next 150, pass 1", CA / "verses-3", 4_000_000, [M + "concept_verses.py", "run", "verses-3", "sonnet-1"],
     {"CV_PER_CARD": "150", "CV_SKIP_RUNS": "verses-1"}),
    ("concepts, next 150, pass 2", CA / "verses-4", 4_000_000, [M + "concept_verses.py", "run", "verses-4", "sonnet-1"],
     {"CV_PER_CARD": "150", "CV_SKIP_RUNS": "verses-1"}),
    ("concepts next 150, merge", None, 0, [M + "concept_verses.py", "merge", "verses-3", "sonnet-1", "verses-4"],
     {"CV_BACKLOG": "backlog-2.jsonl"}),
]


def log(msg):
    line = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    log(f"queue start: {len(STEPS)} steps, caps {sum(s[2] for s in STEPS):,} tokens, deadline {DEADLINE:%H:%M}Z")
    for label, run_dir, cap, cmd, env in STEPS:
        if STOP.exists():
            log("STOP file: queue ends")
            return
        if dt.datetime.now(dt.timezone.utc) >= DEADLINE:
            log("deadline: queue ends")
            return
        if run_dir is not None:
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "BUDGET").write_text(str(cap), encoding="ascii")
            (run_dir / "STOP").unlink(missing_ok=True)
        log(f"step: {label}")
        # the step's output to a file, never a pipe: a pipe nobody reads fills and
        # stalls the step
        out = LOG.with_name(f"day-queue.{label.replace(' ', '_').replace(',', '')}.out")
        with open(out, "w", encoding="utf-8") as fo:
            p = subprocess.Popen([PY] + cmd, cwd=ROOT, env={**os.environ, "PYTHONIOENCODING": "utf-8", **env},
                                 stdout=fo, stderr=subprocess.STDOUT)
            while p.poll() is None:
                if (dt.datetime.now(dt.timezone.utc) >= DEADLINE or STOP.exists()) and run_dir is not None:
                    (run_dir / "STOP").write_text("deadline", encoding="ascii")
                time.sleep(20)
        tail = out.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:]
        for t in tail:
            log(f"  {t}")
        log(f"step done: {label} (exit {p.returncode})")
    log("queue end: all steps done")


if __name__ == "__main__":
    main()
