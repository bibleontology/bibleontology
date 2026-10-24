"""Site activity, counted by the app as it answers -- for the site's owner and for Claude.

2026-10-01, planning a quiet public week: clear visibility into activity, and
easy access to the report so that it is checked regularly and the owner is told
if something needs a response; and on searches, counted with their terms but
never tied to an address. docs/LAUNCH.md has the decision.

WHAT IS KEPT, per day, in <data dir>/activity/YYYY-MM-DD.json:
    requests by people and by bots; page loads; distinct visitors (a count);
    cards, themes, tags and chapters opened; structure and connections panels
    opened; card sections opened, by the section's id alone (not which
    card); searches by term; the sites visitors came from (host only);
    visitors by device type, browser and operating system (totals, each
    visitor counted once a day, read from the browser string and dropped);
    status codes; the last 20 server errors and the last 20 slow requests
    (path and time, no query, no address); and for each kind of request, how
    many and how long they took, as a count per time bucket and the slowest.

WHAT IS NEVER KEPT: an address, a browser string, a country, a cookie, or anything that
ties one request to another. A visitor is counted by a one-way hash of the
masked address (/24, /48) and the browser string under a random key drawn
each day. The key and the day's hashes are kept in the data folder for that
day only, so a restart does not count a returning visitor twice, and are
deleted when the day ends (see _read_key). An overcount is still possible
(one person, two browsers); an identification is not. Only a browser counts:
anything not saying it is one is a bot request. This keeps the promise in
About and OPERATIONS.md: reader
data is read by the maintainer and his tools and nobody else, and there is
nothing here worth reading about any one reader.

The /ops page and /ops.json are served by app2/server.py behind their own
token (ops_token()), separate from the invite tokens; without it they are a
plain 404, as if they did not exist.
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import threading
from pathlib import Path
from urllib.parse import urlparse

BOTS = re.compile(r"(?i)bot|crawl|spider|slurp|curl|wget|python-|httpclient|go-http|"
                  r"java/|libwww|headless|scan|monitor|uptime|preview|fetch|okhttp")
# A PERSON'S BROWSER SAYS SO. Every mainstream browser opens its user agent
# with "Mozilla/5.0 (" and names a rendering engine. The first public day
# counted 37 "visitors", 12 of them with browser and system "other": Claude's
# and Fable's checks ("Mozilla/5.0 probe", Python), which named no engine and
# matched no bot word. Anything that does not look like a browser is now a
# bot request, not a visitor (2026-10-01: perfect stats are not needed
# yet).
LOOKS_LIKE_BROWSER = re.compile(r"^Mozilla/5\.0 \(.*(AppleWebKit|Gecko/|Trident/)")
# PERFORMANCE BY ACTIVITY (2026-10-01: detailed performance info
# by activity): each kind of request into time buckets, so the report can
# give a typical time, the slow tail and the slowest without keeping every
# timing. Bucket upper bounds in ms; the last catches everything slower.
BUCKETS = (50, 100, 200, 500, 1000, 2000, 5000, 10**9)
KINDS = {"/api/entity": "card", "/api/chapter": "chapter", "/api/search": "search",
         "/api/structure": "structure panel", "/api/echoes": "connections",
         "/api/majortheme": "theme", "/api/tag": "tag", "/api/entity-verses": "card verses",
         "/api/unit": "unit", "/api/sense": "word page", "/api/recurs": "explore patterns",
         "/api/upper": "explore ontologies", "/api/lists": "explore lists",
         "/api/events": "explore events", "/api/majorthemes": "explore themes"}
# WHAT VISITORS USE (2026-10-01, totals chosen over a row per visitor:
# country stays with Cloudflare's dashboard, so the site never asks it). Read
# from the browser string as the request arrives, counted once per visitor
# per day, and the string itself is dropped. First match wins, so the order
# matters: Edge and Opera also say "Chrome", Chrome also says "Safari".
# An iPad in its default mode says "Macintosh" and counts as a desktop.
DEVICE = (("tablet", re.compile(r"iPad|Tablet|Android(?!.*Mobile)")),
          ("phone", re.compile(r"Mobi|iPhone|iPod|Android")))
BROWSER = (("Edge", re.compile(r"Edg/|EdgiOS|EdgA")), ("Opera", re.compile(r"OPR/|Opera")),
           ("Samsung Internet", re.compile(r"SamsungBrowser")),
           ("Firefox", re.compile(r"Firefox|FxiOS")), ("Chrome", re.compile(r"Chrome|CriOS")),
           ("Safari", re.compile(r"Safari")))
OS = (("iOS", re.compile(r"iPhone|iPad|iPod")), ("Android", re.compile(r"Android")),
      ("Windows", re.compile(r"Windows")), ("ChromeOS", re.compile(r"CrOS")),
      ("macOS", re.compile(r"Macintosh|Mac OS X")), ("Linux", re.compile(r"Linux")))


# THE DAY IS NEW YORK'S. 2026-10-01: the day on the ops site
# turns on Eastern time. The server runs on UTC, so the day had turned at
# 8 pm Eastern and an evening's reading was split across two days. Eastern
# time with daylight saving (America/New_York), not a fixed -5: EDT is -4 for
# most of the year. Without the time-zone database (a bare Windows Python),
# a fixed -5.
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/New_York")
except Exception:                                           # noqa: BLE001
    TZ = dt.timezone(dt.timedelta(hours=-5), "EST")


def _now() -> dt.datetime:
    return dt.datetime.now(TZ)


def _first(rules, ua, default):
    return next((name for name, rx in rules if rx.search(ua)), default)


PAGES = ("/", "/index.html")
# the blog's pages are pages too, and each post's views are counted by name
# (2026-10-05: track blog views on ops)
PAGE_PREFIXES = ("/e/", "/p/", "/theme/", "/tag/", "/blog")
# a counter stops taking new keys past this, so a flood of junk terms cannot
# grow the file or the memory without bound; the rest count under "(other)"
MAX_KEYS = 500
KEEP_RECENT = 20
SEEN_MAX = 50_000     # distinct visitors counted in a day, at most
SOURCES_MAX = 3       # distinct sites one reader can be counted as coming from in a day


def store_dir() -> Path:
    """The same place the invite list lives (bibleont.invites)."""
    from bibleont import invites
    return Path(invites.store_dir())


def ops_token() -> str | None:
    """The token that opens /ops: <data dir>/ops-token, one line. None when
    there is no such file, and then /ops does not exist."""
    p = store_dir() / "ops-token"
    try:
        t = p.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return t if len(t) >= 32 else None


def ops_ok(given: str | None) -> bool:
    want = ops_token()
    return bool(want and given and given.isascii() and hmac.compare_digest(want, given))


def _mask(ip: str) -> str:
    try:
        a = ipaddress.ip_address(ip.strip())
    except ValueError:
        return "?"
    net = ipaddress.ip_network(f"{a}/{24 if a.version == 4 else 48}", strict=False)
    return str(net.network_address)


class Activity:
    def __init__(self):
        self.lock = threading.Lock()
        self.dir = store_dir() / "activity"
        self.day = None
        self._roll(_now().date().isoformat())
        threading.Thread(target=self._flusher, daemon=True).start()

    # ---- the day's counters ------------------------------------------------
    def _blank(self):
        # readers start at 0 on a new day, so a day of farm traffic alone shows
        # 0 readers, not the dash kept for days before readers were counted
        return {"requests_people": 0, "requests_bots": 0, "pages": 0, "visitors": 0, "readers": 0,
                "cards": {}, "themes": {}, "tags": {}, "chapters": {}, "searches": {},
                "structure": 0, "connections": 0, "referrers": {}, "status": {},
                "errors": [], "slow": [], "perf": {}}

    def _roll(self, day):
        """A new day (or the first request after a start): load what the day
        already holds, and the day's visitor key -- the one already drawn, if
        the server restarted during the day, else a fresh one."""
        self.day = day
        self.c = self._read(day) or self._blank()
        self.key, self.seen = self._read_key(day)
        self.base_visitors = max(0, self.c.get("visitors", 0) - len(self.seen))
        self.readers = self._read_readers(day)
        self.base_readers = max(0, self.c.get("readers", 0) - len(self.readers))
        # (reader, site) pairs already counted today, in memory: a restart may
        # count a pair twice, which is the lesser fault
        self.sources = {}

    # READERS: VISITORS WHOSE BROWSER RAN THE PAGE (2026-10-22). From 21
    # October a farm of desktop "Chrome" and "Edge" clients loaded one page each,
    # about 2,000 an hour, and never ran its script: 8,611 "visitors" made 8,599
    # page loads and almost nothing else (a real reader's page calls the API at
    # once). The page now sends /api/open when its script starts, marked
    # no-store so Cloudflare never answers it from cache; a visitor who sends it
    # is a reader. Same one-way daily hash, kept the same way, for the day only.
    def _readers_file(self, day):
        return self.dir / f".{day}.readers"

    def _read_readers(self, day):
        try:
            raw = self._readers_file(day).read_bytes()
            if len(raw) % 8 == 0:
                return {raw[i:i + 8] for i in range(0, len(raw), 8)}
        except OSError:
            pass
        try:                                        # earlier days' go
            for old in self.dir.glob(".*.readers"):
                if old.name != self._readers_file(day).name:
                    old.unlink()
        except OSError:
            pass
        return set()

    # THE DAY'S KEY IS KEPT FOR THE DAY, and only for the day.
    # 2026-10-01, approving the visitor-count fixes for this release:
    # the visibility changes go out with that release as well.
    # It had been held in memory and never written, so each restart -- every
    # deploy -- drew a new key and counted every returning visitor again.
    # Now <data dir>/activity/.<day>.visitors holds the key and the day's
    # one-way hashes, is rewritten with the counts, and is deleted when the
    # day rolls over (and any older one with it). Still no address, browser
    # string or cookie. What it does allow, for that day only, is checking a
    # guessed masked address and browser string against the list -- the same
    # data folder's access log already holds more than that, for longer.
    def _keyfile(self, day):
        return self.dir / f".{day}.visitors"

    def _read_key(self, day):
        try:
            raw = self._keyfile(day).read_bytes()
            if len(raw) >= 32 and (len(raw) - 32) % 8 == 0:
                return raw[:32], {raw[i:i + 8] for i in range(32, len(raw), 8)}
        except OSError:
            pass
        try:                                        # earlier days' keys go
            for old in self.dir.glob(".*.visitors"):
                if old.name != self._keyfile(day).name:
                    old.unlink()
        except OSError:
            pass
        return secrets.token_bytes(32), set()

    def _read(self, day):
        try:
            return json.loads((self.dir / f"{day}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    @staticmethod
    def _bump(counter: dict, key: str, n: int = 1):
        if key in counter or len(counter) < MAX_KEYS:
            counter[key] = counter.get(key, 0) + n
        else:
            counter["(other)"] = counter.get("(other)", 0) + n

    def record(self, path, query, status, ms, ip, ua, referer, own_host):
        """One answered request. Never raises: counting must not break serving."""
        try:
            self._record(path, query, status, ms, ip, ua, referer, own_host)
        except Exception:                                   # noqa: BLE001
            pass

    def _record(self, path, query, status, ms, ip, ua, referer, own_host):
        now = _now()
        today = now.date().isoformat()
        bot = not ua or bool(BOTS.search(ua)) or not LOOKS_LIKE_BROWSER.search(ua)
        q = {k: (v[0] if v else "") for k, v in (query or {}).items()}
        with self.lock:
            if today != self.day:
                self._flush_locked()
                self._roll(today)
            c = self.c
            # OUR OWN CHECKS COUNT AS NOTHING BUT THEMSELVES. A load test or a
            # probe sends "bibleont-check/..." and is tallied here and nowhere
            # else, so it cannot move the visitors, the timings or the hourly
            # charts (the counting fixes, 2026-10-01: "I'll label my own checks
            # with a name the bot filter recognises, so my tests never count").
            if ua and ua.startswith("bibleont-check"):
                c["checks"] = c.get("checks", 0) + 1
                return
            c["requests_bots" if bot else "requests_people"] += 1
            self._bump(c["status"], str(status))
            at = now.strftime("%H:%M:%S")
            if status >= 500:
                c["errors"] = (c["errors"] + [{"at": at, "path": path[:80],
                                               "status": status}])[-KEEP_RECENT:]
            if ms >= 2000:
                c["slow"] = (c["slow"] + [{"at": at, "path": path[:80],
                                           "ms": int(ms)}])[-KEEP_RECENT:]
            # BY THE HOUR (2026-10-01: time-based graphs or
            # buckets with volumes, response times, and errors): requests by
            # people and by bots, page loads, 4xx and 5xx, and every answered
            # request's time into the same buckets as the per-activity table
            hr = c.setdefault("hours", {}).setdefault(now.strftime("%H"), {
                "people": 0, "bots": 0, "pages": 0, "e4": 0, "e5": 0,
                "n": 0, "max": 0, "b": [0] * len(BUCKETS)})
            hr["bots" if bot else "people"] += 1
            if 400 <= status < 500:
                hr["e4"] += 1
            elif status >= 500:
                hr["e5"] += 1
            elif not bot and (path in PAGES or path.startswith(PAGE_PREFIXES)):
                hr["pages"] += 1
            if status < 400:
                hr["n"] += 1
                hr["max"] = max(hr["max"], int(ms))
                hr["b"][next(i for i, ub in enumerate(BUCKETS) if ms <= ub)] += 1
            # every answered /api route is a kind of its own (a fixed set: an
            # unknown path is a 404 and is not timed); the common ones by name
            kind = ("page" if (path in PAGES or path.startswith(PAGE_PREFIXES))
                    else KINDS.get(path) or (path[:40] if path.startswith("/api/") else None))
            if kind and status < 400:
                p = c.setdefault("perf", {}).setdefault(
                    kind, {"n": 0, "max": 0, "b": [0] * len(BUCKETS)})
                p["n"] += 1
                p["max"] = max(p["max"], int(ms))
                p["b"][next(i for i, ub in enumerate(BUCKETS) if ms <= ub)] += 1
            # THE PUBLISHED ONTOLOGY (/ns: the vocabularies, the map, the
            # alignment; the committee's practitioner, W1, 2026-10-20): what
            # the r/semanticweb post sends people to, and what tools fetch as
            # Turtle -- counted apart, since a tool is a reader here too
            if path.startswith("/ns") and status < 400:
                self._bump(c.setdefault("ns_tools" if bot else "ns", {}), path.rstrip("/")[:80] or "/ns")
            if bot:
                return
            h = hashlib.blake2b((_mask(ip or "") + "|" + (ua or "")).encode(),
                                key=self.key, digest_size=8).digest()
            # capped (Fable's final review, L2): a script varying its browser
            # name counts as a new visitor each time and would grow this set
            # without end; past SEEN_MAX the day's count stops rising
            if h not in self.seen and len(self.seen) < SEEN_MAX:
                self.seen.add(h)
                c["visitors"] = self.base_visitors + len(self.seen)
            # a reader: the page's script ran and said so (above). Devices,
            # browsers and systems are counted for readers only, from
            # 2026-10-22, so a farm that never runs the page cannot skew them
            if path == "/api/open":
                if h not in self.readers and len(self.readers) < SEEN_MAX:
                    self.readers.add(h)
                    c["readers"] = self.base_readers + len(self.readers)
                    for name, rules, default in (("devices", DEVICE, "desktop"),
                                                 ("browsers", BROWSER, "other"), ("systems", OS, "other")):
                        self._bump(c.setdefault(name, {}), _first(rules, ua, default))
                # WHERE THEY CAME FROM, by the site's name alone, as the page
                # read it (document.referrer), cached page or not (2026-10-22:
                # the redirect to the site is the number watched closest).
                # Once per reader AND SITE a day, at most SOURCES_MAX sites per
                # reader: counted on every /api/open, one client could write
                # the line Doug reads (the security seat, 2026-10-22); counted
                # on a reader's first open only, a reader back from Google
                # that evening was never counted (Doug, 2026-10-22: "I
                # redirected from google and bing and neither bumped the
                # count"). Our own host in either form is not a source
                # (2026-10-21: www only redirects here); a port is dropped,
                # and only ASCII names are kept.
                host = (q.get("r") or "").strip().lower()[:80].split(":")[0]
                own = (own_host or "").split(":")[0].lower().removeprefix("www.")
                if host and re.fullmatch(r"[a-z0-9.-]+", host, re.ASCII) and host.removeprefix("www.") != own:
                    mine = self.sources.setdefault(h, set()) if len(self.sources) < SEEN_MAX else set()
                    if host not in mine and len(mine) < SOURCES_MAX and h in self.readers:
                        mine.add(host)
                        self._bump(c["referrers"], host)
                return
            if status >= 400:
                return
            if path in PAGES or path.startswith(PAGE_PREFIXES):
                c["pages"] += 1
                if path.startswith("/blog"):
                    self._bump(c.setdefault("blog", {}), path.rstrip("/")[:100] or "/blog")
            elif path == "/api/entity" and q.get("id"):
                self._bump(c["cards"], q["id"][:80])
            elif path == "/api/majortheme" and q.get("id"):
                self._bump(c["themes"], q["id"][:80])
            elif path == "/api/tag" and q.get("id"):
                self._bump(c["tags"], q["id"][:80])
            elif path == "/api/chapter" and q.get("b"):
                self._bump(c["chapters"], f'{q["b"][:12]} {q.get("c", "")[:4]}')
            elif path == "/api/search" and q.get("q"):
                # the term, never who typed it
                self._bump(c["searches"], " ".join(q["q"].lower().split())[:60])
            elif path == "/api/seen" and q.get("s"):
                # a card section a reader opened, by the section's id alone --
                # not which card, not who (2026-10-13, the card-sections
                # review: approved as a counter with no per-card, per-visitor or
                # personal data)
                self._bump(c.setdefault("sections", {}), q["s"][:60])
            elif path == "/api/structure":
                c["structure"] += 1
            elif path == "/api/echoes":
                c["connections"] += 1
            # (Where readers came from is counted from /api/open's `r`, above,
            # from 2026-10-22: the page that carried the Referer header is
            # mostly answered by Cloudflare's cache and never reached here.)

    # ---- keeping it ---------------------------------------------------------
    def _flush_locked(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / f".{self.day}.json.tmp"
        tmp.write_text(json.dumps(self.c, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.dir / f"{self.day}.json")
        ktmp = self.dir / f".{self.day}.visitors.tmp"
        ktmp.write_bytes(self.key + b"".join(sorted(self.seen)))
        os.replace(ktmp, self._keyfile(self.day))
        rtmp = self.dir / f".{self.day}.readers.tmp"
        rtmp.write_bytes(b"".join(sorted(self.readers)))
        os.replace(rtmp, self._readers_file(self.day))

    def _flusher(self):
        import time
        while True:
            time.sleep(60)
            try:
                with self.lock:
                    self._flush_locked()
            except Exception:                                # noqa: BLE001
                pass

    # ---- the report ---------------------------------------------------------
    def one_day(self, d: str) -> dict | None:
        """One day's counts, today's live from memory. (Not `day`: that is
        the attribute holding today's date.)"""
        with self.lock:
            if d == self.day:
                return dict(self.c)
        return self._read(d)

    def report(self, days: int = 7) -> dict:
        """The last `days` days, today live from memory, newest first; and the
        server's resident memory now."""
        with self.lock:
            today = dict(self.c)
        out = []
        for i in range(days):
            d = (_now().date() - dt.timedelta(days=i)).isoformat()
            c = today if d == self.day else self._read(d)
            if c:
                out.append({"day": d, **c})
        return {"days": out, "memory_mb": _rss_mb(),
                "note": "Counts only. No address, browser string or cookie is stored. "
                        "Readers are visitors whose browser ran the page (from 2026-10-22); "
                        "visitors are anything that looked like a browser, the automated "
                        "ones included. Both are daily one-way counts, kept across restarts "
                        "within the day. A browser that has opened /ops is not counted "
                        "(from 2026-10-22)."}


def _pct(p: dict, q: float) -> int:
    """The upper bound of the bucket the q-th percentile falls in, never above
    the slowest actually seen."""
    k, acc = q * p["n"], 0
    for ub, cnt in zip(BUCKETS, p["b"]):
        acc += cnt
        if acc >= k:
            return min(ub, p["max"] + 1)
    return p["max"] + 1


def perf_summary(perf: dict) -> list[dict]:
    """[{kind, n, p50, p95, max}], slowest tail first; p50 and p95 are the
    upper bound of the bucket the percentile falls in ("under 200 ms")."""
    out = []
    for kind, p in (perf or {}).items():
        if not p.get("n"):
            continue
        out.append({"kind": kind, "n": p["n"], "p50": _pct(p, 0.5),
                    "p95": _pct(p, 0.95), "max": p["max"]})
    return sorted(out, key=lambda r: -r["p95"])


def hour_summary(hours: dict) -> list[dict]:
    """All 24 hours of a day (New York time), each {hour, people, bots, pages,
    e4, e5, n, p50, p95, max}; an hour with nothing is zeros."""
    out = []
    for h in range(24):
        p = (hours or {}).get(f"{h:02d}") or {}
        n = p.get("n", 0)
        out.append({"hour": h, "people": p.get("people", 0), "bots": p.get("bots", 0),
                    "pages": p.get("pages", 0), "e4": p.get("e4", 0), "e5": p.get("e5", 0),
                    "n": n, "p50": _pct(p, 0.5) if n else 0,
                    "p95": _pct(p, 0.95) if n else 0, "max": p.get("max", 0)})
    return out


def _rss_mb():
    """This process's resident memory (Linux /proc; None elsewhere)."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return round(int(line.split()[1]) / 1024)
    except OSError:
        return None
    return None
