"""EVERY JUDGED RUN RECORDS WHAT IT WAS (plan 8.1e item 4; the committee's
practitioner: "your provenance is not reproducible" -- no prompt, model id or
code commit was kept with a run).

    from run_record import record
    record(run_dir, model="claude-sonnet-5-5", prompt=TASK, tool=__file__)

writes <run_dir>/run.json once, at launch: the model id, the code commit and
whether the tree had uncommitted changes, the tool, the full prompt text and
its sha256, and the start time. A run resumed later keeps the first record and
adds a resumption line, so what judged each item is never overwritten.
"""
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(*args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:                                    # noqa: BLE001
        return ""


def record(run_dir, model, prompt, tool):
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    p = run_dir / "run.json"
    if p.exists():
        r = json.loads(p.read_text(encoding="utf-8"))
        r.setdefault("resumed", []).append({"at": now, "commit": _git("rev-parse", "HEAD"), "model": model})
    else:
        r = {"model": model, "commit": _git("rev-parse", "HEAD"), "uncommitted_changes": bool(_git("status", "--porcelain", "--untracked-files=no")),
             "tool": str(Path(tool).resolve().relative_to(ROOT)), "started": now,
             "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(), "prompt": prompt}
    p.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return r
