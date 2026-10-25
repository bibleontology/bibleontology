"""THE GRUNT RUNNER: runs on the Mac mini, unattended (plan 8.2j, 2026-10-24).

Doug: "figure out how to get the Mac in a mode where when I am not around it keeps itself working". This is the
whole of what runs there. It knows nothing about the graph: a job is a file of model calls, and the answers are
written back raw. What the calls mean, the answer keys and any planted faults stay on the PC (tools/grunt/grunt.py).

    ~/grunt/queue/<name>.jsonl   line 1 {"_job": {"model": ..., "options": {...}}}, then {"key", "messages"} per call
    ~/grunt/done/<name>.jsonl    {"key", "content", "secs", "in_tok", "out_tok"} or {"key", "error"} per call
    ~/grunt/done/<name>.complete written when every call has an answer
    ~/grunt/status.json          what it is doing, refreshed after every call

Jobs run in name order, so a name's prefix is its priority; a higher-priority job queued later is taken up after
the current call, and the interrupted job resumes after it. Resumable: a call with an answer is never repeated. If
Ollama is not answering, it waits and retries the same call rather than recording a failure. Standard library only
(macOS ships Python 3.9). Started and kept alive by launchd (tools/grunt/org.bibleontology.grunt.plist).
"""
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request

HOME = os.path.expanduser("~/grunt")
QUEUE, DONE = os.path.join(HOME, "queue"), os.path.join(HOME, "done")
URL = "http://127.0.0.1:11434/api/chat"
# WATCHDOG (2026-10-24): over hours the model's memory grew from 17 GB to 25 GB on this 24 GB Mac, it swapped, and
# Ollama stopped answering; one call then sat out a 15-minute timeout and the night's rate fell to ~4 a minute. The
# slowest healthy call seen was 53 s. So a call past HUNG seconds restarts Ollama and is retried, and Ollama is
# recycled every FRESH calls (~17 minutes, ~30 s each) so its memory starts again. "restarts" counts both.
HUNG, FRESH = 120, 100  # 240/250 at first; a fresh process hung after 64 calls, twice in five minutes
BREW = "/opt/homebrew/bin/brew"
calls_since_fresh = 0
restarts = 0


def restart_ollama():
    global restarts
    restarts += 1
    subprocess.run([BREW, "services", "restart", "ollama"], capture_output=True, timeout=120)
    time.sleep(20)


def unload(model):
    body = {"model": model, "keep_alive": 0}
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=60).read()
    except Exception:
        pass


def status(**kw):
    kw["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = os.path.join(HOME, "status.json.tmp")
    with open(tmp, "w") as f:
        json.dump(kw, f)
    os.replace(tmp, os.path.join(HOME, "status.json"))


def call(model, options, messages):
    body = {"model": model, "stream": False, "think": False, "options": options, "messages": messages}
    req = urllib.request.Request(URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=HUNG) as r:
        d = json.load(r)
    return {"content": d["message"]["content"], "secs": round(time.time() - t, 2),
            "in_tok": d.get("prompt_eval_count"), "out_tok": d.get("eval_count")}


def run_job(name):
    path, out = os.path.join(QUEUE, name), os.path.join(DONE, name)
    with open(path) as f:
        lines = [json.loads(l) for l in f if l.strip()]
    head = lines[0].get("_job") or {}
    calls = lines[1:]
    done = set()
    if os.path.exists(out):
        with open(out) as f:
            done = {json.loads(l)["key"] for l in f if l.strip()}
    todo = [c for c in calls if c["key"] not in done]
    n_done = len(calls) - len(todo)
    with open(out, "a") as f:
        global calls_since_fresh
        model = head.get("model", "gemma4:26b")
        for c in todo:
            if calls_since_fresh >= FRESH:
                # recycle the process, not just unload the model (Doug: "periodic process recycles might be
                # needed"): an unload may leave the MLX runner's cache held; a restart returns all of it
                unload(model)
                restart_ollama()
                calls_since_fresh = 0
            while True:
                try:
                    r = call(model, head.get("options") or {}, c["messages"])
                    calls_since_fresh += 1
                    break
                except (socket.timeout, TimeoutError) as e:  # hung: restart it and ask again
                    status(state="restarting a hung Ollama", job=name, error=str(e)[:200], done=n_done,
                           of=len(calls), restarts=restarts)
                    restart_ollama()
                    calls_since_fresh = 0
                except (urllib.error.URLError, ConnectionError) as e:
                    if isinstance(getattr(e, "reason", None), socket.timeout):
                        restart_ollama()
                        calls_since_fresh = 0
                        continue
                    status(state="waiting for Ollama", job=name, error=str(e)[:200], done=n_done, of=len(calls))
                    time.sleep(60)
                except Exception as e:  # a bad call is recorded, never retried forever
                    r = {"error": str(e)[:300]}
                    break
            f.write(json.dumps(dict(key=c["key"], **r)) + "\n")
            f.flush()
            n_done += 1
            status(state="working", job=name, done=n_done, of=len(calls), restarts=restarts)
            if pending() and pending()[0] < name:  # a higher-priority job arrived: do it first, come back after
                return
    open(out[:-len(".jsonl")] + ".complete", "w").close()


def pending():
    return sorted(n for n in os.listdir(QUEUE) if n.endswith(".jsonl")
                  and not os.path.exists(os.path.join(DONE, n[:-len(".jsonl")] + ".complete")))


def main():
    os.makedirs(QUEUE, exist_ok=True)
    os.makedirs(DONE, exist_ok=True)
    while True:
        jobs = pending()
        if not jobs:
            status(state="idle")
            time.sleep(60)
            continue
        run_job(jobs[0])


if __name__ == "__main__":
    main()
