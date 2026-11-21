"""The app keeps the last good copy of each public page, and nothing else (plan A.49; 2026-11-12).

app2/page_copies.py writes a page to <folder>/site as the app serves it, for Caddy to serve while the app restarts.
The app gains a writable folder for it, so what it may write is held as tightly as the unit's other rules:

  1. ONLY PUBLIC PAGES: the server's send hook keeps a GET answered 200, HTML, public Cache-Control, no query. A
     no-store page (/ops), JSON, a 404, a redirect, a POST and a query are never kept (each planted and refused)
  2. ONLY UNDER site/: a path that climbs out, doubles a slash or carries a query is refused; nothing is ever written
     to assets/ by the app (the shell files every reader runs are the upload's alone)
  3. NEVER IN THE WAY: offer() does not block or raise when the queue is full; the queue is bounded
  4. THE COPY IS THE PAGE: the file is the served body plus one <meta> with its policy (no frame-ancestors); the same
     body offered twice is written once
  5. THE UNIT: the app may write /srv/bibleontology-data and /var/cache/bibleontology/site, nothing else, and the
     second path is optional ("-"), so a missing folder cannot stop the site; Caddy serves copies under its own
     policy, with no inline script

No graph needed. Run: python tests/test_page_copies.py"""
import queue
import re
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app2"))
import page_copies as PC  # noqa: E402

fails, plants = [], 0


def check(ok, msg):
    if not ok:
        fails.append(msg)
        print("FAIL", msg)


def drain(pc, timeout=5):
    t = time.time()
    while not pc.q.empty() and time.time() - t < timeout:
        time.sleep(0.02)
    time.sleep(0.1)


tmp = Path(tempfile.mkdtemp())
pc = PC.PageCopies(tmp)
CSP = "default-src 'self'; script-src 'self' 'sha256-abc'; frame-ancestors 'none'"
PAGE = b'<!doctype html><html><head><meta charset="utf-8"><title>t</title></head><body>David</body></html>'

# ---- 1. only public pages, through the server's own send hook
import server as S  # noqa: E402
S.PAGE_COPIES = pc


class Fake(S.Handler):
    def __init__(self, path, command="GET"):
        self.path, self.command, self.request_version = path, command, "HTTP/1.1"
        self.wfile = __import__("io").BytesIO()
        self._headers_buffer = []

    def send_response(self, *a, **k):
        pass

    def send_header(self, *a, **k):
        pass

    def end_headers(self):
        pass


def served(path, code=200, ctype="text/html; charset=utf-8", cache="public, max-age=300", command="GET"):
    before = pc.q.qsize() + pc.written + pc.dropped
    Fake(path, command)._send(code, PAGE, ctype, {"Cache-Control": cache, "Content-Security-Policy": CSP})
    return pc.q.qsize() + pc.written + pc.dropped > before


check(served("/e/david"), "a public page was not kept")
refused = {"no-store (/ops)": served("/ops", cache="no-store"), "JSON": served("/api/x", ctype="application/json"),
           "a 404": served("/e/nobody", code=404), "a redirect": served("/e/old", code=301),
           "a POST": served("/e/david", command="POST"), "a query": served("/e/david?k=secret")}
plants += len(refused)
for what, kept in refused.items():
    check(not kept, f"planted: {what} was kept")

# ---- 2. only under site/
for bad in ("/../x", "/e/../../etc/passwd", "//etc/x", "/e/david?q=1", "e/no_slash", "/e/da vid"):
    plants += 1
    try:
        PC.file_for(bad)
        check(False, f"planted: {bad!r} named a file")
    except ValueError:
        pass
drain(pc)
written = [p.relative_to(tmp).as_posix() for p in tmp.rglob("*") if p.is_file()]
check(written and all(w.startswith("site/") for w in written), f"the app wrote outside site/: {written}")
check(not (tmp / "assets").exists(), "the app created assets/, which is the upload's alone")
src = (ROOT / "app2" / "page_copies.py").read_text(encoding="utf-8")
check('"assets"' not in src.split('"""', 2)[2], "page_copies.py writes to assets/")

# ---- 3. never in the way
full = PC.PageCopies.__new__(PC.PageCopies)
full.q, full.dropped, full.allowed = queue.Queue(maxsize=1), 0, None
full.q.put(("x", b"", ""))
t = time.time()
full.offer("/e/david", PAGE, CSP)
check(time.time() - t < 0.05 and full.dropped == 1, "offer() waited on, or did not drop for, a full queue")
check(PC.QUEUE <= 256, f"the queue is not small: {PC.QUEUE}")

# ---- 4. the copy is the page
f = tmp / "site" / "e" / "david.html"
body = f.read_bytes() if f.exists() else b""
meta = re.search(rb'\n<meta http-equiv="Content-Security-Policy" content="([^"]+)">', body)
check(meta and body.replace(meta.group(0), b"", 1) == PAGE, "the copy is not the served page plus one <meta>")
check(meta and b"frame-ancestors" not in meta.group(1) and b"'sha256-abc'" in meta.group(1),
      "the copy's policy is not the page's, without frame-ancestors")
n = pc.written
pc.offer("/e/david", PAGE, CSP)
drain(pc)
check(pc.written == n, "the same page was written twice")

# ---- 5. the unit and Caddy
unit = (ROOT / "deploy" / "bibleontology.service").read_text(encoding="utf-8")
rw = re.findall(r"^ReadWritePaths=(.*)$", unit, flags=re.M)
check(rw == ["/srv/bibleontology-data -/var/cache/bibleontology/site"], f"the writable paths are not exactly these: {rw}")
check("Environment=BIBLEONT_PAGE_COPIES=/var/cache/bibleontology" in unit, "the unit does not name the copies' folder")
check("ProtectSystem=strict" in unit, "the unit is no longer strict")
cf = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
copy = cf[cf.index("handle @copy {"):cf.index("handle @down {")]
pol = re.search(r'Content-Security-Policy "([^"]+)"', copy)
check(pol and "script-src 'self';" in pol.group(1) and "unsafe-inline'" not in pol.group(1).split("style-src")[0],
      "Caddy does not serve copies under its own policy without inline script")

# ---- 6. THE SECURITY SEAT'S FINDINGS (2026-11-12), each held
# (a) only the sitemap's pages: a variant address that also answers 200 is not kept (disk fill)
listed = PC.sitemap_paths(ROOT / "deploy" / "www")
check(len(listed) > 40_000 and "/e/david" in listed and "/" in listed, f"the sitemap's pages were not read: {len(listed)}")
plants += 1
check("/p/Gen.01.1" not in listed and "/graph/david" not in listed, "planted: a variant address is in the allowed set")
tmp2 = Path(tempfile.mkdtemp())
only = PC.PageCopies(tmp2, allowed={"/e/david"})
only.offer("/p/Gen.01.1", PAGE, CSP)
only.offer("/e/david", PAGE, CSP)
drain(only)
kept = sorted(p.relative_to(tmp2).as_posix() for p in tmp2.rglob("*.html"))
check(kept == ["site/e/david.html"], f"a page outside the allowed set was kept: {kept}")
# (b) nothing kept while the invite gate is on
was = S._invites_on
S._invites_on = lambda: True
try:
    plants += 1
    check(not served("/e/moses"), "planted: a page was kept while the invite gate is on")
finally:
    S._invites_on = was
# (c) the root sweep of symlinks and special files: after every stop, and before every upload
check("ExecStopPost=-+/usr/bin/find /var/cache/bibleontology/site -mindepth 1 -not -type f -not -type d -delete" in unit,
      "the unit does not sweep non-regular files from site/ after a stop")
up = (ROOT / "tools" / "upload_pages.py").read_text(encoding="utf-8")
check(up.index("-not -type f -not -type d -delete") < up.index("sudo tar -xzf"), "the upload does not sweep before unpacking")
# (d) no canonical redirect of a copy back to the app that is down
check("disable_canonical_uris" in copy, "Caddy may redirect a copy of / or /blog/ back to the app")

# (e) EVERY VERSE AND WORD PAGE, A CLOSED SET (P-2026-11-15-2): the allowlist grows by canonical verse and word paths
# only; a variant, a pattern or anything else planted among them is refused; an empty allowlist (the sitemap could not
# be read) stays empty; a None allowlist (every page) is left alone
ext = PC.PageCopies(Path(tempfile.mkdtemp()), allowed={"/e/david"})
got = PC.extend_allowed(ext, {"/p/Prov.24.32", "/word/G972"})
check(got == 2 and {"/p/Prov.24.32", "/word/G972"} <= ext.allowed, f"verse and word paths not added: {ext.allowed}")
for bad in ("/p/Gen.01.1", "/p/Gen.1.1/", "/p/Gen.1.1?x=1", "/word/g26", "/word/G026", "/e/anything", "/p/../etc",
            "/p/*"):
    plants += 1
    before = set(ext.allowed)
    PC.extend_allowed(ext, {bad})
    check(ext.allowed == before, f"planted: a non-canonical path entered the allowlist: {bad}")
plants += 1
empty = PC.PageCopies(Path(tempfile.mkdtemp()), allowed=set())
check(PC.extend_allowed(empty, {"/p/Gen.1.1"}) == 0 and not empty.allowed,
      "planted: an unreadable sitemap's empty allowlist was widened")
everything = PC.PageCopies(Path(tempfile.mkdtemp()), allowed=None)
check(PC.extend_allowed(everything, {"/p/Gen.1.1"}) == 0 and everything.allowed is None, "a None allowlist was narrowed")
# and the server's own list is canonical and real: every verse of the text, and every word it uses
fake = {"verses": {("Gen", 1, 1): "", ("1Sam", 17, 49): "", ("Rev", 22, 21): ""},
        "lemmas": {"g26": "ἀγάπη", "h157": "אָהַב", "x9": "?"}, "profiles": {"g4102": {"gloss": "faith"}}}
pths = S.every_page_paths(fake)
check(pths == {"/p/Gen.1.1", "/p/1Sam.17.49", "/p/Rev.22.21", "/word/G26", "/word/H157", "/word/G4102"}
      and all(PC._CANON.fullmatch(p) for p in pths),
      f"the server's page list holds a non-canonical path: {[p for p in pths if not PC._CANON.fullmatch(p)][:3]}")

print(f"page copies: 7 classes checked; {plants} planted faults; {len(fails)} failures")
sys.exit(1 if fails else 0)
