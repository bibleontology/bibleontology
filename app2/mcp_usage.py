"""How assistants use the MCP server, counted with no person logged (plan 8.7d, 2026-11-12).

Doug, 2026-11-12: "I also want clear tracking of MCP use and a path to continual improvement"; the design's questions
ruled "1-6 as recommended". Found the same day: POST /mcp counted nothing beyond its rate limiter, so v1 had no
baseline to measure v1.1 against.

WHAT IS KEPT, per day, in <data dir>/mcp/YYYY-MM-DD.json:
    calls by JSON-RPC method and by tool; the client by the product name its User-Agent gives (self-reported, never
    treated as verified) and by the clientInfo name and protocol version it sends at initialize; the arguments used,
    by name only ("get_relations.kind"), so v1.1's shaping options are counted the day they exist; sessions, and calls
    per session as a histogram; THE FOLLOW RATE: a call for an id that a previous answer in the same session offered
    (a link, a move, a search hit, a map entry's call), against a call for one it did not; the longest chain of
    followed links; errors by kind; ids asked for that do not exist; searches with no results, by their text (cut to
    100 characters); and per tool, the time and size of the answers.

WHAT IS NEVER KEPT: an address, a browser string, a query tied to anyone, or anything that joins one day to the next.
A session is a one-way 8-byte hash of the masked address (/24, /48) and the User-Agent under a key drawn each day and
held in memory only: never written, so it cannot be read back from the data folder, and gone when the day or the
process ends. (A restart mid-day splits a session in two: the lesser fault.) What a session remembers, in memory
only, is the ids its recent answers offered, so the next call can be counted as followed or not; it is dropped after
30 idle minutes. Searches with no results are kept 90 days, then removed from the day's file (Doug, 2026-11-12, the
first of his "1-6 as recommended").
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

import activity

MAX_KEYS = activity.MAX_KEYS          # a counter takes no new keys past this; the rest count under "(other)"
SESSIONS_MAX = 20_000                 # sessions remembered at once
OFFERED_MAX = 400                     # ids one session remembers as offered
IDLE = 30 * 60                        # a session is forgotten after this many seconds without a call
NO_RESULTS_DAYS = 90
QUERY_MAX = 100
HIST = ((1, "1"), (2, "2"), (5, "3-5"), (10, "6-10"), (20, "11-20"), (10 ** 9, "21+"))
FOLLOWABLE = ("fetch", "get_relations", "get_verse", "get_word")
_REF = re.compile(r"(\w+)\s*[.: ]\s*(\d{1,3})\s*[.:]\s*(\d{1,3})")
_CLIENT = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,39}")


def client_name(ua: str) -> str:
    """The product the User-Agent names first ("claude-user/1.0" -> "claude-user"), or "unnamed"."""
    m = _CLIENT.match((ua or "").strip())
    return m.group(0) if m else "unnamed"


def target_id(tool: str, args: dict) -> str | None:
    """The id a followable call asks for, in the form answers offer it."""
    if not isinstance(args, dict):
        return None
    if tool in ("fetch", "get_relations"):
        v = args.get("id")
        return v if isinstance(v, str) else None
    if tool == "get_verse" and isinstance(args.get("ref"), str):
        m = _REF.fullmatch(args["ref"].strip())
        return "verse:%s.%d.%d" % (m.group(1), int(m.group(2)), int(m.group(3))) if m else None
    if tool == "get_word" and isinstance(args.get("strong"), str):
        return "word:" + args["strong"].strip()
    return None


def offered_ids(structured: dict) -> list[str]:
    """Every id an answer offers as a next call: links, moves, relations, search hits and their links, map calls."""
    out = []
    if not isinstance(structured, dict):
        return out

    def take(xs):
        for x in xs or []:
            if isinstance(x, dict) and isinstance(x.get("id"), str):
                out.append(x["id"])
                take(x.get("links"))
    take(structured.get("links"))
    take(structured.get("moves"))
    take(structured.get("relations"))
    take(structured.get("results"))
    for m in structured.get("map") or []:
        a = ((m or {}).get("get") or {}).get("arguments") or {}
        if isinstance(a.get("id"), str):
            out.append(a["id"])
    return out


def _bucket(n: int) -> str:
    return next(label for top, label in HIST if n <= top)


class Usage:
    def __init__(self, folder: Path | None = None, flusher: bool = True):
        self.lock = threading.Lock()
        self.dir = Path(folder) if folder else activity.store_dir() / "mcp"
        self.day = None
        self._roll(activity._now().date().isoformat())
        if flusher:
            threading.Thread(target=self._flusher, daemon=True).start()

    # ---- the day ------------------------------------------------------------
    def _blank(self):
        return {"calls": 0, "methods": {}, "tools": {}, "clients": {}, "init_clients": {}, "protocols": {},
                "args": {}, "sessions": 0, "per_session": {}, "followed": 0, "fresh": 0, "chain_max": 0,
                "errors": {}, "missing_ids": {}, "no_results": {}, "perf": {}}

    def _read(self, day):
        try:
            return json.loads((self.dir / f"{day}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _roll(self, day):
        """A new day: the day's counts so far (a restart continues them), a fresh key held in memory only, no
        sessions; and searches older than NO_RESULTS_DAYS cut from their days' files."""
        if self.day is not None and self.day != day:
            try:
                self._flush_locked()
            except OSError:
                pass
        self.day = day
        self.c = self._read(day) or self._blank()
        self.key = secrets.token_bytes(32)
        self.sessions = collections.OrderedDict()          # hash -> {"t", "n", "offered", "chain"}
        self.base_hist = dict(self.c.get("per_session") or {})
        self._prune_no_results(day)

    def _prune_no_results(self, day):
        cut = (dt.date.fromisoformat(day) - dt.timedelta(days=NO_RESULTS_DAYS)).isoformat()
        try:
            for f in self.dir.glob("????-??-??.json"):
                if f.stem < cut:
                    c = json.loads(f.read_text(encoding="utf-8"))
                    if c.get("no_results"):
                        c["no_results"] = {}
                        c["no_results_removed"] = True
                        tmp = f.with_suffix(".tmp")
                        tmp.write_text(json.dumps(c, ensure_ascii=False, sort_keys=True), encoding="utf-8")
                        os.replace(tmp, f)
        except (OSError, ValueError):
            pass

    @staticmethod
    def _bump(counter: dict, key: str, n: int = 1):
        activity.Activity._bump(counter, key, n)

    def _session(self, ip, ua, now):
        h = hashlib.blake2b((activity._mask(ip or "") + "|" + (ua or "")).encode(),
                            key=self.key, digest_size=8).digest()
        s = self.sessions.get(h)
        if s is not None and now - s["t"] > IDLE:            # back after the idle gap: a new session
            self._close(h)
            s = None
        if s is None:
            if len(self.sessions) >= SESSIONS_MAX:
                self._close(next(iter(self.sessions)))
            s = self.sessions[h] = {"t": now, "n": 0, "offered": collections.OrderedDict(), "chain": 0}
            self.c["sessions"] = self.c.get("sessions", 0) + 1
        self.sessions.move_to_end(h)
        s["t"] = now
        return s

    # ---- one call -----------------------------------------------------------
    def record(self, msg, out, ip, ua, ms, size):
        """One JSON-RPC message and its answer. Never raises: counting must not break serving."""
        try:
            with self.lock:
                self._record(msg, out, ip, ua, ms, size, time.time())
        except Exception:                                    # noqa: BLE001
            pass

    def _record(self, msg, out, ip, ua, ms, size, now):
        day = activity._now().date().isoformat()
        if day != self.day:
            self._roll(day)
        c = self.c
        if not isinstance(msg, dict):
            self._bump(c["errors"], "not an object")
            return
        method = msg.get("method") if isinstance(msg.get("method"), str) else "(none)"
        if method.startswith("notifications/"):
            return                                           # not a call: the client telling, not asking
        c["calls"] += 1
        self._bump(c["methods"], method[:40])
        self._bump(c["clients"], client_name(ua))
        params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
        if method == "initialize":
            info = params.get("clientInfo") if isinstance(params.get("clientInfo"), dict) else {}
            m = _CLIENT.match(info["name"].strip()) if isinstance(info.get("name"), str) else None
            self._bump(c["init_clients"], m.group(0) if m else "unnamed")
            pv = params.get("protocolVersion")
            self._bump(c["protocols"], pv[:20] if isinstance(pv, str) else "(none)")
        s = self._session(ip, ua, now)
        s["n"] += 1
        result = (out or {}).get("result") if isinstance(out, dict) else None
        if isinstance(out, dict) and out.get("error"):
            self._bump(c["errors"], str((out["error"] or {}).get("message", "error"))[:40])
        if method != "tools/call":
            return
        tool = params.get("name") if isinstance(params.get("name"), str) else "(none)"
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        self._bump(c["tools"], tool[:40])
        for a in list(args)[:10]:
            if isinstance(a, str):
                self._bump(c["args"], f"{tool[:40]}.{a[:30]}")
        p = c["perf"].setdefault(tool[:40], [0, 0, 0, 0])   # calls, total ms, slowest ms, total bytes
        p[0] += 1
        p[1] += int(ms)
        p[2] = max(p[2], int(ms))
        p[3] += int(size)
        is_error = bool(isinstance(result, dict) and result.get("isError"))
        if is_error:
            # by the error's code (from 2026-11-12 every tool error carries one); the old bare text otherwise
            sc = result.get("structuredContent") if isinstance(result.get("structuredContent"), dict) else {}
            code = sc.get("error") or ((result.get("content") or [{}])[0] or {}).get("text", "error")
            self._bump(c["errors"], str(code)[:40])
            if code in ("not_found", "no such item"):
                tid = target_id(tool, args)
                if tid:
                    self._bump(c["missing_ids"], tid[:90])
        structured = result.get("structuredContent") if isinstance(result, dict) else None
        # THE FOLLOW RATE: was what this call asks for offered by an answer this session already had? A failed call
        # (a missing id, a malformed reference) is counted under errors, never as navigation either way
        if tool in FOLLOWABLE and not is_error:
            tid = target_id(tool, args)
            if tid is not None and (tid in s["offered"] or (tool == "get_relations" and args.get("cursor"))):
                c["followed"] += 1
                s["chain"] += 1
                c["chain_max"] = max(c["chain_max"], s["chain"])
            else:
                c["fresh"] += 1
                s["chain"] = 0
        elif tool == "search":
            s["chain"] = 0
            if isinstance(structured, dict) and not structured.get("results") and not is_error:
                q = args.get("query")
                if isinstance(q, str) and q.strip():
                    self._bump(c["no_results"], q.strip()[:QUERY_MAX])
        for oid in offered_ids(structured):
            s["offered"][oid] = True
            s["offered"].move_to_end(oid)
            while len(s["offered"]) > OFFERED_MAX:
                s["offered"].popitem(last=False)

    # ---- keeping it -----------------------------------------------------------
    def _hist_now(self):
        hist = dict(self.base_hist)
        for s in self.sessions.values():
            b = _bucket(s["n"])
            hist[b] = hist.get(b, 0) + 1
        return hist

    def _flush_locked(self):
        # sessions still open are counted in the histogram as they stand; the base keeps only those already gone
        self.c["per_session"] = self._hist_now()
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / f".{self.day}.json.tmp"
        tmp.write_text(json.dumps(self.c, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.dir / f"{self.day}.json")

    def _close(self, k):
        """A session ends: its call count moves into the base histogram, and what it remembered is dropped."""
        b = _bucket(self.sessions.pop(k)["n"])
        self.base_hist[b] = self.base_hist.get(b, 0) + 1

    def _close_idle(self, now):
        """Sessions idle past IDLE end, so the next flush does not count them twice."""
        for k in [k for k, s in self.sessions.items() if now - s["t"] > IDLE]:
            self._close(k)

    def _flusher(self):
        while True:
            time.sleep(60)
            try:
                with self.lock:
                    self._close_idle(time.time())
                    self._flush_locked()
            except Exception:                                # noqa: BLE001
                pass

    # ---- the report -----------------------------------------------------------
    def report(self, days: int = 7) -> dict:
        with self.lock:
            today = dict(self.c, per_session=self._hist_now())
            d0 = self.day
        out = []
        for i in range(days):
            d = (activity._now().date() - dt.timedelta(days=i)).isoformat()
            c = today if d == d0 else self._read(d)
            if c:
                out.append({"day": d, **c})
        return {"days": out,
                "note": "Counts only. No address or browser string is stored; a session is a daily one-way hash "
                        "under a key held in memory only. Followed: a call for an id an earlier answer in the same "
                        "session offered. Searches with no results are kept 90 days."}
