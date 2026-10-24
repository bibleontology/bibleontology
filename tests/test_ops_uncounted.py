"""The browsers that open /ops are not in its counts (2026-10-22).

The cookie that opens /ops is on Path=/ops, so it never reaches the pages
being counted. Opening /ops therefore also sets a site-wide cookie with no
secret in it, bo_uncounted, and a request carrying it is not recorded. This
checks, against the real handler on a spare port with a scratch folder:
  - a request without the cookie is counted, and one with it is not;
  - opening /ops with its link sets both cookies, the token only on /ops;
  - a browser that already held the /ops cookie gets bo_uncounted on its
    next visit;
Planted: a cookie whose name merely begins with bo_uncounted is still counted.

    python tests/test_ops_uncounted.py
"""
import http.client
import os
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = tempfile.mkdtemp(prefix="bo-uncounted-")
os.environ["BIBLEONT_FEEDBACK"] = TMP          # before anything reads it
sys.path.insert(0, str(ROOT / "app2"))
sys.path.insert(0, str(ROOT / "src"))
import activity  # noqa: E402
import server as S  # noqa: E402

PORT = 8096
TOKEN = "test-ops-token-0123456789abcdef0123456789"     # 32 or more, as activity.ops_token wants
(Path(TMP) / "ops-token").write_text(TOKEN + "\n", encoding="utf-8")
fails = []


class Spy(activity.Activity):
    n = 0

    def record(self, *a, **k):
        Spy.n += 1
        return super().record(*a, **k)


def ask(method, path, cookie=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=60)
    h = {"Origin": "https://evil.example", "Content-Type": "application/json"}
    if cookie:
        h["Cookie"] = cookie
    # an empty body: the refusal never reads one, and Windows resets a socket
    # closed with unread bytes before the reply is read (seen 2026-10-22)
    c.request(method, path, body=b"" if method == "POST" else None, headers=h)
    r = c.getresponse()
    r.read()
    c.close()
    return r.status, r.headers.get_all("Set-Cookie") or []


def counted_after(before, want):
    """How many requests were recorded since `before`. The handler records a
    request after its reply is sent, so the count can lag the reply: wait up
    to two seconds for it to reach `want` (the gate caught the race,
    2026-10-22: a look-alike cookie read as uncounted)."""
    import time
    end = time.time() + 2
    while Spy.n - before < want and time.time() < end:
        time.sleep(0.02)
    time.sleep(0.1 if want == 0 else 0)      # a request that should not count has had its chance
    return Spy.n - before


def check(name, got, want):
    if got != want:
        fails.append(f"{name}: got {got}, want {want}")
    print(("ok  " if got == want else "FAIL"), name, got)


S.ACTIVITY = Spy()
srv = ThreadingHTTPServer(("127.0.0.1", PORT), S.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()

before = Spy.n
ask("POST", "/api/feedback")                                   # refused, 403, but a request
check("a request without the cookie is counted", counted_after(before, 1), 1)
before = Spy.n
ask("POST", "/api/feedback", "theme=dark; bo_uncounted=1")
check("a request with it is not", counted_after(before, 0), 0)
before = Spy.n
ask("POST", "/api/feedback", "bo_uncountedX=1")
check("planted: a look-alike name is still counted", counted_after(before, 1), 1)

status, cookies = ask("GET", f"/ops?k={TOKEN}")
check("the /ops link answers with a redirect", status, 302)
ops = [c for c in cookies if c.startswith("bo_ops=")]
unc = [c for c in cookies if c.startswith("bo_uncounted=")]
check("... sets the /ops cookie on /ops only", len(ops) == 1 and "Path=/ops;" in ops[0], True)
check("... and bo_uncounted site-wide", len(unc) == 1 and "Path=/;" in unc[0], True)
check("... with no secret in it", bool(unc) and TOKEN not in unc[0], True)

status, cookies = ask("GET", "/ops", f"bo_ops={TOKEN}")
check("a browser with the old /ops cookie opens /ops", status, 200)
check("... and is given bo_uncounted", any(c.startswith("bo_uncounted=1;") for c in cookies), True)
status, cookies = ask("GET", "/ops", f"bo_ops={TOKEN}; bo_uncounted=1")
check("... once only", any(c.startswith("bo_uncounted=") for c in cookies), False)
check("without the token /ops is still a 404, cookie or not", ask("GET", "/ops", "bo_uncounted=1")[0], 404)
srv.shutdown()
print("all held" if not fails else f"{len(fails)} failed")
sys.exit(1 if fails else 0)
