"""Watch the finding batch: one line per verse, and any failure at once.

2026-09-26: report on progress as it goes and intervene if needed; make sure
blank results are not being returned. Reads docs/FIXLOOP.md sections headed "— find —" and the batch
log; prints a line per new verse (verdict, faults, cost) and BLANK for any
answer with no VERDICT line, plus breaker / traceback / budget lines.
"""
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG, RUN = ROOT / "docs" / "FIXLOOP.md", ROOT / "out" / "find-batch.log"
seen = set()
log_at = 0
LOG_AT = {}
# on re-arm, the verses already reported are passed as SKIP=N and not repeated
SKIP = int(sys.argv[1]) if len(sys.argv) > 1 else 0
_t = LOG.read_text(encoding="utf-8") if LOG.exists() else ""
for _m in list(re.finditer(r"^## (\S+) — find — ", _t, re.M))[:SKIP]:
    seen.add(_m.group(1))
if RUN.exists():
    log_at = len(RUN.read_text(encoding="utf-8", errors="replace"))
blanks = 0
while True:
    t = LOG.read_text(encoding="utf-8") if LOG.exists() else ""
    for m in re.finditer(r"^## (\S+) — find — .*?\(\$([\d.]+)[^\n]*\n(.*?)"
                         r"(?=^---$|\Z)", t, re.M | re.S):
        ref, cost, body = m.groups()
        if ref in seen:
            continue
        seen.add(ref)
        v = re.search(r"^VERDICT:\s*(\w+)", body, re.M)
        n = len(re.findall(r"^FAULT \d+:", body, re.M))
        alg = len(re.findall(r"^\s*ALGORITHM:", body, re.M))
        if not v:
            blanks += 1
            print(f"BLANK {ref} ${cost}: no VERDICT — {body.strip()[:120]!r}",
                  flush=True)
        else:
            print(f"{len(seen)}. {ref} {v.group(1)} faults={n} "
                  f"algorithms={alg} ${cost}", flush=True)
    runs = sorted(ROOT.glob("out/find-batch-w*.log")) or \
        ([RUN] if RUN.exists() else [])
    ended = 0
    for run in runs:
        r = run.read_text(encoding="utf-8", errors="replace")
        at = LOG_AT.get(run, log_at if run == RUN else 0)
        for line in r[at:].splitlines():
            if re.search(r"BREAKER|Traceback|Error|budget|peak|refused",
                         line):
                print(f"RUN {run.stem}: {line}", flush=True)
        LOG_AT[run] = len(r)
        ended += any(x in r for x in ("BREAKER", "budget $", "peak hours",
                                      "Traceback", "queue done"))
    if runs and ended == len(runs):
        print(f"batch ended: {len(seen)} verses, {blanks} blank", flush=True)
        sys.exit(0)
    time.sleep(20)
