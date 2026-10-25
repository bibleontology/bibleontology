"""THE PC SIDE OF THE GRUNT RUNNER (plan 8.2j, 2026-10-24): install it on the Mac, push jobs, pull answers.

The Mac (ssh host `macmini`, see docs/OPERATIONS.md) runs tools/grunt/runner.py under launchd and works through
its queue unattended. This side only moves files. A pass (e.g. tools/meaning/local_structure_check.py) exports a
job of model calls, keeping its answer key and planted faults here in out/grunt/jobs/; the answers come back raw
into out/grunt/done/ and the pass imports them.

    python tools/grunt/grunt.py install          copy the runner and its launchd agent, (re)start it
    python tools/grunt/grunt.py push JOBFILE     queue a job (out/grunt/jobs/<name>.jsonl)
    python tools/grunt/grunt.py pull             fetch every answer file
    python tools/grunt/grunt.py status           what it is doing now, and the queue
    python tools/grunt/grunt.py drop NAME        take a job out of the queue (e.g. one built on a brief since fixed)
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST = "macmini"
JOBS, DONE = ROOT / "out" / "grunt" / "jobs", ROOT / "out" / "grunt" / "done"
PLIST = "org.bibleontology.grunt.plist"


def sh(*args, check=True):
    return subprocess.run(args, check=check, text=True, capture_output=True)


def ssh(cmd, check=True):
    return sh("ssh", HOST, cmd, check=check)


def install():
    ssh("mkdir -p ~/grunt/queue ~/grunt/done ~/Library/LaunchAgents")
    sh("scp", str(ROOT / "tools" / "grunt" / "runner.py"), f"{HOST}:grunt/runner.py")
    sh("scp", str(ROOT / "tools" / "grunt" / PLIST), f"{HOST}:Library/LaunchAgents/{PLIST}")
    ssh(f"launchctl bootout gui/$(id -u)/org.bibleontology.grunt", check=False)
    ssh(f"launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/{PLIST}")
    print(ssh("sleep 3; launchctl print gui/$(id -u)/org.bibleontology.grunt | grep -E 'state|pid'; "
              "cat ~/grunt/status.json").stdout)


def push(job):
    sh("scp", str(job), f"{HOST}:grunt/queue/{Path(job).name}")
    print(f"queued {Path(job).name}")


def pull():
    DONE.mkdir(parents=True, exist_ok=True)
    r = sh("scp", f"{HOST}:grunt/done/*", str(DONE), check=False)
    print(r.stderr.strip() or f"pulled into {DONE}")


def drop(name):
    """take a job out of the queue (its answers so far stay in done/, under a .dropped name)"""
    ssh(f"rm -f ~/grunt/queue/{name}.jsonl; mv ~/grunt/done/{name}.jsonl ~/grunt/done/{name}.dropped 2>/dev/null; true")
    print(f"dropped {name}")


def status():
    print(ssh("cat ~/grunt/status.json; echo; ls -la ~/grunt/queue ~/grunt/done | grep -v '^total'", check=False).stdout)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "drop":
        drop(sys.argv[2])
    else:
        {"install": install, "pull": pull, "status": status}.get(cmd, lambda: push(sys.argv[2]))()
