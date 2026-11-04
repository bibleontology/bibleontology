"""The orchestrator's launcher: acceptance tests (2026-11-03). Written before the code.

    python3 -X utf8 tests/test_orchestra_launch.py

THE INTERFACE (tools/orchestra/launch.py, Python 3.9, standard library only; it imports orchestra from its own folder):
  ProxyError(Exception)
  ProxyClient(base="http://127.0.0.1:8787", marks=<folder>, timeout=900)
      base must be http://127.0.0.1:<port> or http://localhost:<port>, else ValueError (it never talks elsewhere)
      health() -> dict                 GET <base>/health; any failure (refused, non-200, not JSON) raises ProxyError
      chat(job, messages, thinking) -> {"content": str, "cost": float}
          thinking true -> ProxyError, nothing sent. job must match ^orch-[A-Za-z0-9_-]{1,43}$ else ProxyError.
          Creates the empty file <marks>/<job> before the call and removes it after, whatever happens.
          POST <base>/j/<job>/v1/chat/completions, JSON {"model": "deepseek-flash", "messages": messages,
          "temperature": 0}. A non-200 reply raises ProxyError carrying the status and the reply's "error" text
          (never returns an empty answer: an empty answer would be filed as DeepSeek's). On 200, content is
          choices[0].message.content; cost is the "cost" of GET <base>/j/<job>/usage (0.0 if unreadable).
  load_rates(path) -> dict             a JSON object of model -> positive number (calls a minute); a missing file,
                                       bad JSON, or a bad value falls back to DEFAULT_RATES for that model
  DEFAULT_RATES = {"gemma4:26b": 58.0, "qwen3.8:27b": 19.0}
  run_once(home, grunt, proxy, now=None) -> int
      one orchestra.cycle(Env(home, grunt, now, proxy, load_rates(home/"rates.json"))). A lock file home/cycle.lock
      (created exclusively) keeps two cycles apart: if it exists and is under 2 hours old, return 2 without a cycle;
      older, it is removed and the cycle runs. Any exception from the cycle is caught: home/status.json becomes
      {"error": "<ExceptionType>: <message>", "now": <ISO UTC>} and it returns 1. Otherwise 0. The lock is always
      removed.
  main(argv)  "once": run_once(~/orchestra, ~/grunt, ProxyClient(marks=~/orchestra/proxy-jobs)); exit code its return
"""
import http.server
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "orchestra"))
try:
    import launch as L  # noqa: E402
    import orchestra as O  # noqa: E402
except ImportError as e:
    print("FAIL tools/orchestra/launch.py does not import:", e)
    sys.exit(1)

fails = []


def check(ok, what):
    if not ok:
        fails.append(what)


SEEN = []          # (method, path, body, marker existed during the call)
STATE = {"chat": (200, {"choices": [{"message": {"content": "1: stated"}}], "usage": {}}), "health": (200, {"ok": True, "week_usd": 1.0, "cap": 5.0}),
         "usage": (200, {"cost": 0.0123}), "marks": None}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, obj):
        raw = (obj if isinstance(obj, str) else json.dumps(obj)).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        SEEN.append(("GET", self.path, None, None))
        self.reply(*(STATE["health"] if self.path == "/health" else STATE["usage"]))

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        job = self.path.split("/")[2] if self.path.startswith("/j/") else ""
        SEEN.append(("POST", self.path, body, (Path(STATE["marks"]) / job).exists()))
        self.reply(*STATE["chat"])


srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d" % srv.server_address[1]
tmp = Path(tempfile.mkdtemp())
marks = tmp / "marks"
marks.mkdir()
STATE["marks"] = str(marks)
P = L.ProxyClient(base=BASE, marks=marks, timeout=10)
MSG = [{"role": "user", "content": "x"}]

# 1. only the local proxy
for bad in ("http://192.0.2.10:8787", "https://api.deepseek.com", "http://127.0.0.1.evil.com:8787", "file:///etc"):
    try:
        L.ProxyClient(base=bad, marks=marks)
        check(False, "1: accepted base %s" % bad)
    except ValueError:
        pass

# 2. a good call: marker present during, gone after, the request as specified, cost from /usage
SEEN.clear()
a = P.chat("orch-sweep-0-run0", MSG, False)
check(a == {"content": "1: stated", "cost": 0.0123}, "2: answer %r" % (a,))
post = [s for s in SEEN if s[0] == "POST"]
check(len(post) == 1 and post[0][1] == "/j/orch-sweep-0-run0/v1/chat/completions", "2: path %r" % (post,))
check(post and post[0][2] == {"model": "deepseek-flash", "messages": MSG, "temperature": 0}, "2: body %r" % (post and post[0][2],))
check(post and post[0][3] is True, "2: the job's marker was not there during the call")
check(not (marks / "orch-sweep-0-run0").exists(), "2: the marker was left behind")
check(any(s[1] == "/j/orch-sweep-0-run0/usage" for s in SEEN), "2: cost not read from the job's usage")

# 3. refusals raise, never an empty answer, and the marker still goes
STATE["chat"] = (429, {"error": "weekly cap reached"})
try:
    P.chat("orch-sweep-1-run0", MSG, False)
    check(False, "3: a 429 returned an answer")
except L.ProxyError as e:
    check("429" in str(e) and "weekly cap" in str(e), "3: error text %s" % e)
check(not (marks / "orch-sweep-1-run0").exists(), "3: the marker was left after a refusal")
STATE["chat"] = (200, {"choices": [{"message": {"content": "ok"}}]})

# 4. thinking, bad job names: refused before anything is sent
for job, thinking in (("orch-x", True), ("sweep-0", False), ("orch-../../etc", False), ("orch-" + "a" * 44, False)):
    SEEN.clear()
    try:
        P.chat(job, MSG, thinking)
        check(False, "4: sent %s thinking=%s" % (job, thinking))
    except L.ProxyError:
        check(not SEEN, "4: something was sent for %s" % job)

# 5. health: a dict, or ProxyError
check(P.health().get("cap") == 5.0, "5: health")
STATE["health"] = (500, {"error": "x"})
try:
    P.health()
    check(False, "5: a 500 health passed")
except L.ProxyError:
    pass
try:
    L.ProxyClient(base="http://127.0.0.1:1", marks=marks, timeout=2).health()
    check(False, "5: nothing listening, and health passed")
except L.ProxyError:
    pass
STATE["health"] = (200, {"ok": True, "week_usd": 1.0, "cap": 5.0})

# 6. rates
(tmp / "rates.json").write_text(json.dumps({"gemma4:26b": 40, "qwen3.8:27b": -1, "other": 5}), encoding="utf-8")
r = L.load_rates(tmp / "rates.json")
check(r.get("gemma4:26b") == 40 and r.get("qwen3.8:27b") == 19.0 and r.get("other") == 5, "6: rates %r" % r)
check(L.load_rates(tmp / "missing.json") == L.DEFAULT_RATES, "6: missing file")
(tmp / "bad.json").write_text("{", encoding="utf-8")
check(L.load_rates(tmp / "bad.json") == L.DEFAULT_RATES, "6: bad JSON")

# 7. run_once: a cycle, the lock, a crash recorded
home, grunt = tmp / "orchestra", tmp / "grunt"
for d in (home / "intake", home / "passes", home / "results", grunt / "queue", grunt / "done"):
    d.mkdir(parents=True)
(home / "proxy-jobs").mkdir()
(home / "proxy-jobs" / "orch-left-0-run0").write_text("", encoding="utf-8")     # a killed cycle's marker
check(L.run_once(home, grunt, P) == 0 and (home / "status.json").exists(), "7: a quiet cycle")
check(not (home / "proxy-jobs" / "orch-left-0-run0").exists(), "7: a stale marker survived the cycle (the security seat)")
check(not (home / "cycle.lock").exists(), "7: the lock was left")
(home / "cycle.lock").write_text("", encoding="utf-8")
(home / "status.json").unlink()
check(L.run_once(home, grunt, P) == 2 and not (home / "status.json").exists(), "7: ran through a fresh lock")
old = time.time() - 3 * 3600
os.utime(home / "cycle.lock", (old, old))
check(L.run_once(home, grunt, P) == 0, "7: a stale lock blocked the cycle")
real = O.cycle
O.cycle = lambda env: (_ for _ in ()).throw(RuntimeError("boom"))
try:
    rc = L.run_once(home, grunt, P)
finally:
    O.cycle = real
st = json.loads((home / "status.json").read_text(encoding="utf-8"))
check(rc == 1 and st.get("error") == "RuntimeError: boom" and "now" in st, "7: crash status %r rc %s" % (st, rc))
check(not (home / "cycle.lock").exists(), "7: the lock was left after a crash")

srv.shutdown()
for f in fails:
    print("FAIL", f)
print("orchestra launch: 7 groups of checks; %d failures" % len(fails))
sys.exit(1 if fails else 0)
