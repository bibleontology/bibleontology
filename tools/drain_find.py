"""Stop the wide finding batch cleanly: each worker finishes the verse it is
on, and is stopped before it sends another (2026-09-27: cut it
off after the next runs complete). Prints one line per worker stopped.
"""
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
logs = sorted(ROOT.glob("out/find-batch-w[0-9].log"))
start = {p: p.read_text(encoding="utf-8", errors="replace").count(" — spent $")
         for p in logs}
live = set(logs)
# workers already stopped by hand are passed as arguments and skipped
import sys                                             # noqa: E402
for k in sys.argv[1:]:
    live -= {p for p in logs if p.stem.endswith(f"w{k}")}


def kill(shard):
    # every process of the worker (python3.13.exe from the Store install,
    # and the nohup that holds it) — "python.exe" matched nothing
    ps = ("Get-CimInstance Win32_Process | "
          "Where-Object { $_.CommandLine -match 'deepseek_fixloop' -and "
          f"$_.CommandLine -match '--shard {shard}/' }} | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force; "
          "$_.ProcessId }")
    return subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                          capture_output=True, text=True).stdout.strip()


while live:
    for p in list(live):
        t = p.read_text(encoding="utf-8", errors="replace")
        k = re.search(r"w(\d)", p.stem).group(1)
        ended = any(x in t for x in ("BREAKER", "budget $", "peak hours",
                                     "Traceback", "queue done"))
        if ended or t.count(" — spent $") > start[p]:
            pid = kill(k) if not ended else ""
            print(f"worker {k} stopped after its verse "
                  f"{'(already ended)' if ended else f'(pid {pid})'}",
                  flush=True)
            live.discard(p)
    time.sleep(10)
print("all workers stopped", flush=True)
