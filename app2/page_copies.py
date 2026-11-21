"""The last good copy of each public page, kept on disk for Caddy to serve while the app restarts (plan A.49).

Doug, 2026-11-12: *"honestly the initial build and then live updates when each page is hit works - because the file
lives on"*. One full build (tools/build_pages.py) seeds the folder; after that the app refreshes a page's copy each
time it serves the page, so the copies follow the live site and outlive every restart.

WHAT IS WRITTEN: a page the app has just answered to a GET with 200, text/html, a public Cache-Control, and no query
string. That excludes /ops (no-store), the API (JSON), errors, redirects, and anything reached with a query. The file
is named by file_for() alone, which refuses anything but a plain page path, so nothing can be written outside
<folder>/site. The page gains one <meta> carrying the content-security policy it was sent with, since Caddy serving
the copy cannot know it.

WHAT IT COSTS: a queue of at most QUEUE pages waiting for one writer thread; a full queue drops the page (it is
written on a later visit), so serving never waits on disk. A page identical to the copy this process already wrote
is not written again: a digest per path (about 42,000 sitemap pages, a few MB). Disk is bounded by the site's real
pages (unknown addresses are 404s, which are never written).

WHERE: <folder>/site/<path>.html only, <folder> from BIBLEONT_PAGE_COPIES (deploy/bibleontology.service). Unset,
or site/ not writable, and nothing is written: a laptop writes no copies unless asked.

WHAT IT MAY NOT WRITE: <folder>/assets, the app's shell files (/app-<hash>.js), which Caddy serves to every reader
at all times. The unit makes only <folder>/site writable, and the upload (tools/upload_pages.py, run by Doug, as
root) is the only thing that fills assets/. A compromised app could otherwise replace the script every reader runs,
and the change would outlive every restart and deploy: the one thing the unit's ProtectSystem=strict exists to
prevent ("a compromised process cannot rewrite the code it is running"). The copies in site/ are served only while
the app is down, and Caddy sends them under its own strict policy (no inline script), so a tampered copy can run
nothing (deploy/Caddyfile, THE LAST GOOD COPY).
"""
from __future__ import annotations

import hashlib
import os
import queue
import re
import threading
from pathlib import Path

QUEUE = 64
_PATH = re.compile(r"/[A-Za-z0-9_.\-/]*")


def file_for(path: str) -> str:
    """The file a page is kept in, relative to <folder>/site: '/' -> index.html, '/e/david' -> e/david.html,
    '/blog/' -> blog/index.html. Anything but a plain page path is refused (ValueError)."""
    p = path
    if "?" in p or not _PATH.fullmatch(p) or ".." in p or "//" in p:    # a query names no copy: refused, not dropped
        raise ValueError(f"not a page path: {path!r}")
    return (p.rstrip("/") + "/index.html" if p.endswith("/") else p + ".html").lstrip("/")


def with_policy(body: bytes, csp: str) -> bytes:
    """The page with its content-security policy as a <meta> after <head>, frame-ancestors dropped (a <meta> cannot
    carry it). The copy's one difference from what the app sent."""
    policy = "; ".join(d for d in (csp or "").split("; ") if d and not d.startswith("frame-ancestors"))
    if not policy:
        return body
    meta = ('<meta http-equiv="Content-Security-Policy" content="%s">' % policy.replace('"', "&quot;")).encode()
    return re.sub(rb"(<head[^>]*>)", lambda m: m.group(1) + b"\n" + meta, body, count=1)


def write_atomic(f: Path, data: bytes):
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".tmp-%d" % threading.get_ident())
    tmp.write_bytes(data)
    os.replace(tmp, f)


def sitemap_paths(www: Path) -> set:
    """The page paths the sitemaps list (deploy/www/sitemap-*.xml), without the site's address. The only pages kept:
    the security seat's review (2026-11-12) found that variant addresses answer 200 too -- /p/Gen.01.1 beside
    /p/Gen.1.1, alias names under /graph/, trailing slashes -- each a new file, so a stranger could fill the disk.
    The sitemap's ~42,000 are the bound. Unreadable sitemaps keep nothing, the safe failure."""
    out = set()
    try:
        for f in sorted(Path(www).glob("sitemap-*.xml")):
            for loc in re.findall(r"<loc>https://bibleontology\.org([^<]*)</loc>", f.read_text(encoding="utf-8")):
                out.add(loc or "/")
    except OSError:
        return set()
    return out


# THE VERSES AND WORDS BEYOND THE SITEMAP (P-2026-11-15-2): the sitemap lists 20,287 of 31,102 verses, and a crawler
# that followed a link into an unlisted one during a push met "back in a moment" (27 of 34 503s, 2026-11-15). The
# server adds the pages it serves by their own keys, so the set stays closed and bounded as the security seat asked:
# every path canonical (/p/Gen.1.1, never /p/Gen.01.1), at most EXTEND_MAX of them, and a sitemap that failed to read
# still keeps nothing (the extension never turns a safe failure into a wide one).
EXTEND_MAX = 20000          # about twice the real count (11,947 on 2026-11-15), so the bound bites (the review's advice)
_CANON = re.compile(r"/p/[1-3]?[A-Za-z]+\.[1-9]\d{0,2}\.[1-9]\d{0,2}|/word/[HG][1-9]\d{0,4}")


def extend_allowed(copies, paths) -> int:
    """Add canonical verse and word paths to a writer's allowlist; returns how many were new. Never on a writer
    whose allowlist is None (every page, the tests) or empty (the sitemap could not be read)."""
    if copies is None or not copies.allowed:
        return 0
    new = {p for p in paths if _CANON.fullmatch(p or "")} - copies.allowed
    new = set(sorted(new)[:EXTEND_MAX])
    copies.allowed |= new
    return len(new)


class PageCopies:
    def __init__(self, folder: Path, allowed: set | None = None):
        self.dir = Path(folder)
        # None keeps every page offered (tests); the server always passes the sitemap's set (from_env)
        self.allowed = allowed
        self.q: queue.Queue = queue.Queue(maxsize=QUEUE)
        self.seen: dict[str, str] = {}
        self.dropped = 0
        self.written = 0
        threading.Thread(target=self._run, daemon=True).start()

    @classmethod
    def from_env(cls):
        """A writer for BIBLEONT_PAGE_COPIES, or None when it is unset or the folder cannot be written."""
        folder = os.environ.get("BIBLEONT_PAGE_COPIES")
        if not folder:
            return None
        p = Path(folder)
        try:
            (p / "site").mkdir(parents=True, exist_ok=True)
            probe = p / "site" / ".write-probe"
            probe.write_bytes(b"")
            probe.unlink()
        except OSError:
            return None
        return cls(p, sitemap_paths(Path(__file__).resolve().parents[1] / "deploy" / "www"))

    def offer(self, path: str, body: bytes, csp: str):
        """Queue a served page to be kept. Never blocks and never raises: serving must not wait on disk."""
        try:
            if self.allowed is not None and path not in self.allowed:
                self.dropped += 1
                return
            name = file_for(path)
            self.q.put_nowait((name, body, csp))
        except (ValueError, queue.Full):
            self.dropped += 1

    def _run(self):
        while True:
            name, body, csp = self.q.get()
            try:
                digest = hashlib.sha256(body).hexdigest()
                if self.seen.get(name) == digest:
                    continue
                write_atomic(self.dir / "site" / name, with_policy(body, csp))
                self.seen[name] = digest
                self.written += 1
            except Exception:                                    # noqa: BLE001 -- a copy is never worth a crash
                pass
