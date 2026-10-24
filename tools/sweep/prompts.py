"""One prompt file per verse: the task (tools/sweep/task.md) and the verse's
context (out/sweep/context/<ref>.json), for a judge that may read that one
file and write its answer, and nothing else (plan 1.34).

    python tools/sweep/prompts.py [refs]     -> out/sweep/prompts/<ref>.txt

THE BLIND CHECK. A judge is told to use exactly two tools: read its prompt
file, write its answer. The calibration reads each judge's tool count and
discards any run that used more, so no judge can have opened the gold
(tests/verses.json) and still count.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CTX = ROOT / "out" / "sweep" / "context"
DST = ROOT / "out" / "sweep" / "prompts"


def main():
    task = (Path(__file__).with_name("task.md")).read_text(encoding="utf-8")
    refs = sys.argv[1:] or [p.stem for p in sorted(CTX.glob("*.json"))]
    DST.mkdir(parents=True, exist_ok=True)
    for ref in refs:
        c = json.loads((CTX / f"{ref}.json").read_text(encoding="utf-8"))
        (DST / f"{ref}.txt").write_text(task + "\n" + json.dumps(c, ensure_ascii=False, separators=(",", ":")) + "\n",
                                        encoding="utf-8")
    print(f"{len(refs)} prompts -> {DST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
